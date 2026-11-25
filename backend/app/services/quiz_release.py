"""The moment a graded quiz's results come out (FR-618) and its `quiz.graded` notification — S45, S46.

Students see a part (marks, answers) while `released_at` is set and the quiz releases that part
(`released_parts`); what that shows is in `quiz_results`. `release` is the only way to set `released_at`.

`set_release` is the lecturer's: marks, answers, both or neither. Only once the quiz is closed and every
attempt is over, so that nobody still taking it can be told the answers (NFR-41). `release_due` (every `QUIZ_RELEASE_SECONDS`) calls it for quizzes set to
"release when the quiz closes": once the quiz is closed, by hand or by its closing time, and every short
answer has a score (so nobody gets half a result).
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime

from fastapi import HTTPException, status
from sqlalchemy import exists, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import AsyncSessionLocal, after_commit, run_after_commit
from app.models.quiz import Quiz, QuizAnswer, QuizAttempt
from app.models.user import Student, User
from app.schemas.quiz import QuizReleaseIn, QuizReleaseOut
from app.services import notify, quiz_grading, quiz_publish, quiz_store, quiz_timer
from app.services.audit_service import write_log
from app.services.quiz_grading import is_pending

log = logging.getLogger(__name__)

EVENT_GRADED = "quiz.graded"


def released_parts(quiz: Quiz) -> tuple[bool, bool]:
    """Whether students see their marks, and their answers with the correct ones, now."""
    out = quiz.released_at is not None
    return out and quiz.release_marks, out and quiz.release_answers


def release_out(quiz: Quiz, now: datetime) -> QuizReleaseOut:
    marks, answers = released_parts(quiz)
    return QuizReleaseOut(
        release=quiz.release, marks_released=marks, answers_released=answers, released_at=quiz.released_at,
        can_release=quiz.status != "draft" and quiz_publish.window(quiz, now) == "closed")


async def release(db: AsyncSession, quiz: Quiz, now: datetime) -> bool:
    """Mark the results released and, after the commit, notify the enrolled students who took the quiz;
    False when they were already out. The caller holds the quiz's lock."""
    if quiz.released_at is not None:
        return False
    quiz.released_at = now
    await db.flush()
    took = set((await db.execute(
        select(Student.user_id).join(QuizAttempt, QuizAttempt.student_id == Student.id)
        .where(QuizAttempt.quiz_id == quiz.id, QuizAttempt.status == "submitted"))).scalars())
    user_ids = [uid for uid in await quiz_publish.enrolled_user_ids(db, quiz.course_id) if uid in took]
    payload = {"quiz_id": quiz.id, "quiz_title": quiz.title}

    async def _after() -> None:
        await notify.emit(EVENT_GRADED, user_ids, payload)

    if user_ids:
        after_commit(db, _after)
    return True


def _logged(state: QuizReleaseOut) -> dict:
    return {"marks": state.marks_released, "answers": state.answers_released, "release": state.release}


async def set_release(db: AsyncSession, actor: User, quiz_id: int, body: QuizReleaseIn) -> QuizReleaseOut:
    """The lecturer's choice of what students see from now on; audited. Neither part takes the results
    back, or stops a release on closing that hasn't happened yet: after that they only come out by hand."""
    quiz = await quiz_grading.graded_quiz(db, actor, quiz_id, lock=True)
    if quiz.status == "draft":
        raise HTTPException(status.HTTP_409_CONFLICT, detail="This quiz is not published")
    now = quiz_store.clock()
    before = release_out(quiz, now)
    if body.marks or body.answers:
        if not before.can_release:
            raise HTTPException(status.HTTP_409_CONFLICT, detail="Close the quiz before releasing its results")
        await quiz_timer.end_attempts(db, quiz)     # those whose time is up but that the sweep hasn't reached
        quiz.release_marks, quiz.release_answers = body.marks, body.answers
        await release(db, quiz, now)
    else:
        quiz.release, quiz.released_at = "manual", None
    after = release_out(quiz, now)
    if after != before:
        quiz.updated_at = now
        await write_log(db, actor.id, "QUIZ_RELEASE", "m6_quiz", quiz.id, _logged(before),
                        {**_logged(after), "title": quiz.title})
    await db.flush()
    return after


async def release_due() -> int:
    """Release the quizzes whose results come out by themselves now; how many. One that is being changed
    or started right now is left for the next round."""
    async with AsyncSessionLocal() as db:
        now = quiz_store.clock()
        unfinished = (exists().where(QuizAttempt.quiz_id == Quiz.id, QuizAttempt.status == "in_progress"),
                      exists().where(QuizAttempt.quiz_id == Quiz.id, QuizAnswer.attempt_id == QuizAttempt.id,
                                     is_pending))
        quizzes = (await db.execute(
            select(Quiz)
            .where(Quiz.type == "graded", Quiz.release == "on_close", Quiz.released_at.is_(None),
                   or_(Quiz.status == "closed", (Quiz.status == "published") & (Quiz.closes_at <= now)),
                   *(~u.correlate(Quiz) for u in unfinished))
            .order_by(Quiz.id).with_for_update(of=Quiz, skip_locked=True))).scalars().all()
        for quiz in quizzes:
            await release(db, quiz, now)
        await db.commit()
        await run_after_commit(db)
    return len(quizzes)


async def quiz_release_loop() -> None:
    """Background task started in main.py. `QUIZ_RELEASE_SECONDS` <= 0 turns it off."""
    if settings.QUIZ_RELEASE_SECONDS <= 0:
        return
    while True:
        try:
            await release_due()
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("quiz release failed")
        await _sleep(settings.QUIZ_RELEASE_SECONDS)


_sleep = asyncio.sleep   # tests replace this (not asyncio.sleep itself)
