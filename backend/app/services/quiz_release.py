"""The moment a graded quiz's results come out (FR-618) and its `quiz.graded` notification — S45.

`release` is the only way. `release_due` (every `QUIZ_RELEASE_SECONDS`) calls it for quizzes set to
"release when the quiz closes": once the quiz is closed, by hand or by its closing time, and every short
answer has a score (so nobody gets half a result). Releasing by hand, and what students then see, is S46.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime

from sqlalchemy import exists, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import AsyncSessionLocal, after_commit, run_after_commit
from app.models.quiz import Quiz, QuizAnswer, QuizAttempt
from app.models.user import Student
from app.services import notify, quiz_publish, quiz_store
from app.services.quiz_grading import is_pending

log = logging.getLogger(__name__)

EVENT_GRADED = "quiz.graded"


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
