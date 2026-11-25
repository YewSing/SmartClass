"""Grading graded quizzes (FR-616, FR-617, NFR-45, NFR-55) — S45.

- Multiple choice: `on_submit`, in the transaction that submits the attempt (`quiz_timer.submit`'s callers).
- Short answers: the AI, in the background. `grade_pending` (every `QUIZ_GRADE_SECONDS`) takes the pending
  ones (`is_pending`) from the table, so nothing is lost when the server restarts or the AI is down: they
  stay pending and are tried again. No lock or transaction is held while the LLM works.
- The scores are final. The lecturer may change a short answer's score with feedback (`change_score`); the
  AI never writes over a score that is there.

Students see none of this until the results are released (S46).
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import timedelta
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import Select, and_, case, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.models.quiz import SHORT_CORRECT_FROM, Quiz, QuizAnswer, QuizAttempt, QuizQuestion
from app.models.user import Student, User
from app.schemas.quiz import ScoreIn, ShortAnswerListOut, ShortAnswerOut, ShortAnswerState
from app.services import quiz_store
from app.services.audit_service import write_log
from app.services.kb.llm import LLMMalformedOutput, LLMUnavailable
from app.services.quiz import grading
from app.services.quiz.checks import Grade

log = logging.getLogger(__name__)

# a short answer that waits for its score (join the attempt)
is_pending = and_(QuizAnswer.score.is_(None), QuizAnswer.text.is_not(None), QuizAttempt.status == "submitted")


def _score(value: float) -> Decimal:
    return Decimal(str(round(value, 3)))


# ── multiple choice ──────────────────────────────────────────────────────────

async def on_submit(db: AsyncSession, attempt_ids: list[int]) -> None:
    """Grade the multiple-choice answers of attempts that were just submitted (the caller holds their
    locks). A chosen option is right or wrong; a question without an answer has no row and scores 0."""
    if not attempt_ids:
        return
    await db.flush()
    right = QuizAnswer.option_index == QuizQuestion.answer
    await db.execute(
        update(QuizAnswer)
        .where(QuizAnswer.attempt_id.in_(attempt_ids), QuizAnswer.score.is_(None),
               QuizQuestion.id == QuizAnswer.question_id, QuizQuestion.type == "mcq")
        .values(correct=right, score=case((right, 1), else_=0), graded_by="auto", graded_at=quiz_store.clock())
        .execution_options(synchronize_session=False))


# ── short answers: the AI ────────────────────────────────────────────────────

@dataclass
class _Job:
    """Answers of one student, graded in one LLM call."""
    tries: int = 0
    answer_ids: list[int] = field(default_factory=list)
    answers: list[grading.ShortAnswer] = field(default_factory=list)


async def _due_jobs() -> list[_Job]:
    """The next answers to grade, those that never failed first. One whose grade came back unusable is
    tried alone, so it can't hold up the student's others."""
    size = settings.QUIZ_GRADE_BATCH
    async with AsyncSessionLocal() as db:
        rows = (await db.execute(
            select(QuizAnswer.id, QuizAnswer.attempt_id, QuizAnswer.grade_tries, QuizQuestion.text,
                   QuizQuestion.suggested_answer, QuizAnswer.text)
            .join(QuizAttempt, QuizAttempt.id == QuizAnswer.attempt_id)
            .join(Quiz, Quiz.id == QuizAttempt.quiz_id)
            .join(QuizQuestion, QuizQuestion.id == QuizAnswer.question_id)
            .where(is_pending, Quiz.type == "graded",
                   QuizAnswer.grade_after.is_(None) | (QuizAnswer.grade_after <= quiz_store.clock()))
            .order_by(QuizAnswer.grade_after.asc().nulls_first(), QuizAttempt.submitted_at, QuizAttempt.id,
                      QuizQuestion.position, QuizAnswer.id)
            .limit(size * settings.QUIZ_GRADE_CONCURRENCY))).all()
    jobs: list[_Job] = []
    open_jobs: dict[int, _Job] = {}         # by attempt
    for answer_id, attempt_id, tries, question, suggested, text in rows:
        job = open_jobs.get(attempt_id) if tries == 0 else None
        if job is None or len(job.answers) >= size:
            if len(jobs) >= settings.QUIZ_GRADE_CONCURRENCY:
                continue        # next round
            job = _Job(tries=tries)
            jobs.append(job)
            if tries == 0:
                open_jobs[attempt_id] = job
        job.answer_ids.append(answer_id)
        job.answers.append(grading.ShortAnswer(question, suggested, text))
    return jobs


async def _save(job: _Job, grades: list[Grade]) -> None:
    now = quiz_store.clock()
    async with AsyncSessionLocal() as db:
        for answer_id, grade in zip(job.answer_ids, grades, strict=True):
            await db.execute(
                update(QuizAnswer)
                # the lecturer may have scored it meanwhile: that score stands
                .where(QuizAnswer.id == answer_id, QuizAnswer.score.is_(None))
                .values(score=_score(grade.score), correct=_score(grade.score) >= SHORT_CORRECT_FROM, graded_by="ai",
                        graded_at=now, reason=grade.reason, confidence=_score(grade.confidence),
                        flagged=grade.confidence < settings.QUIZ_GRADE_CONFIDENT, grade_after=None)
                .execution_options(synchronize_session=False))
        await db.commit()


async def _put_off(job: _Job, seconds: float, *, tries: int) -> None:
    async with AsyncSessionLocal() as db:
        await db.execute(
            update(QuizAnswer).where(QuizAnswer.id.in_(job.answer_ids), QuizAnswer.score.is_(None))
            .values(grade_tries=tries, grade_after=quiz_store.clock() + timedelta(seconds=seconds))
            .execution_options(synchronize_session=False))
        await db.commit()


async def _run(job: _Job) -> bool:
    """Grade one job; False when the AI can't be reached."""
    retry = settings.QUIZ_GRADE_RETRY_SECONDS
    try:
        await _save(job, await grading.grade(job.answers))
        return True
    except LLMUnavailable as exc:
        if not isinstance(exc, LLMMalformedOutput):
            log.warning("quiz grading: LLM unavailable (%s); %d answer(s) stay pending", exc, len(job.answer_ids))
            await _put_off(job, retry, tries=job.tries)
            return False
        log.warning("quiz grading: unusable LLM reply (%s)", exc)
    except Exception:       # one answer must never stop the others
        log.exception("quiz grading failed for %d answer(s)", len(job.answer_ids))
    # the exponent is capped so that it can't overflow; the wait itself is capped anyway
    wait = min(retry * 2 ** min(job.tries, 20), settings.QUIZ_GRADE_RETRY_MAX_SECONDS)
    await _put_off(job, wait, tries=job.tries + 1)
    return True


async def grade_pending() -> bool:
    """One round of grading; False when every LLM call failed to reach the provider (NFR-55)."""
    jobs = await _due_jobs()
    reached = await asyncio.gather(*(_run(job) for job in jobs))
    return not jobs or any(reached)


async def quiz_grading_loop() -> None:
    """Background task started in main.py. `QUIZ_GRADE_SECONDS` <= 0 turns it off."""
    if settings.QUIZ_GRADE_SECONDS <= 0:
        return
    while True:
        wait = settings.QUIZ_GRADE_SECONDS
        try:
            if not await grade_pending():
                wait = settings.QUIZ_GRADE_RETRY_SECONDS
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("quiz grading round failed")
        await _sleep(wait)


_sleep = asyncio.sleep   # tests replace this (not asyncio.sleep itself)


# ── short answers: the lecturer (FR-617) ─────────────────────────────────────

def _state(answer: QuizAnswer) -> ShortAnswerState:
    if answer.score is None:
        return "pending"
    return "flagged" if answer.flagged else "graded"


def _short_answers(quiz_id: int) -> Select:
    return (select(QuizAnswer, QuizQuestion, Student, User.name)
            .join(QuizAttempt, QuizAttempt.id == QuizAnswer.attempt_id)
            .join(QuizQuestion, QuizQuestion.id == QuizAnswer.question_id)
            .join(Student, Student.id == QuizAttempt.student_id)
            .join(User, User.id == Student.user_id)
            .where(QuizAttempt.quiz_id == quiz_id, QuizAttempt.status == "submitted", QuizQuestion.type == "short"))


def _out(answer: QuizAnswer, question: QuizQuestion, student: Student, name: str) -> ShortAnswerOut:
    def number(value: Decimal | None) -> float | None:
        return None if value is None else float(value)

    return ShortAnswerOut(
        id=answer.id, student_id=student.id, student_name=name, matric_no=student.matric_no, question_id=question.id,
        question_text=question.text, suggested_answer=question.suggested_answer, text=answer.text,
        state=_state(answer), score=number(answer.score), correct=answer.correct, graded_by=answer.graded_by,
        graded_at=answer.graded_at, reason=answer.reason, confidence=number(answer.confidence),
        feedback=answer.feedback)


async def _graded_quiz(db: AsyncSession, actor: User, quiz_id: int) -> Quiz:
    quiz = await quiz_store.get_quiz(db, actor, quiz_id)
    if quiz.type != "graded":
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Only a graded quiz's answers are scored")
    return quiz


async def list_short_answers(db: AsyncSession, actor: User, quiz_id: int,
                             state: ShortAnswerState | None = None) -> ShortAnswerListOut:
    """The short answers of submitted attempts, by question and then student."""
    quiz = await _graded_quiz(db, actor, quiz_id)
    rows = (await db.execute(
        _short_answers(quiz.id).order_by(QuizQuestion.position, QuizQuestion.id, User.name, QuizAnswer.id)
        .execution_options(populate_existing=True))).all()
    states = [_state(answer) for answer, *_ in rows]
    return ShortAnswerListOut(
        pending_count=states.count("pending"), flagged_count=states.count("flagged"),
        answers=[_out(*row) for row, its in zip(rows, states, strict=True) if state in (None, its)])


async def change_score(db: AsyncSession, actor: User, quiz_id: int, answer_id: int, body: ScoreIn) -> ShortAnswerOut:
    """The lecturer's score for a short answer, graded or still pending; 404 unless it is one of the
    quiz's submitted ones. Audited with the old and the new score."""
    quiz = await _graded_quiz(db, actor, quiz_id)
    row = (await db.execute(
        _short_answers(quiz.id).where(QuizAnswer.id == answer_id)
        .with_for_update(of=QuizAnswer).execution_options(populate_existing=True))).one_or_none()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="This quiz has no such short answer")
    answer: QuizAnswer = row[0]
    before = _out(*row)
    answer.score, answer.graded_by, answer.graded_at = _score(body.score), "lecturer", quiz_store.clock()
    answer.correct = answer.score >= SHORT_CORRECT_FROM
    answer.feedback, answer.flagged, answer.grade_after = body.feedback, False, None
    after = _out(*row)
    await write_log(
        db, actor.id, "QUIZ_SCORE_CHANGE", "m6_answer", answer.id,
        {"score": before.score, "graded_by": before.graded_by, "flagged": before.state == "flagged",
         "feedback": before.feedback},
        {"score": after.score, "feedback": after.feedback, "quiz_id": quiz.id, "question_id": after.question_id,
         "student_id": after.student_id})
    await db.flush()
    return after
