"""The server's timers of graded attempts (FR-608, NFR-47) — S44.

`ends_at` is an attempt's final deadline: its start plus the whole-quiz time, or plus the time of every
question, and never after the quiz's `closes_at`. With a timer per question, each question's time starts
when the one before it ends, whether the student moved on or its time ran out. So being away never adds
time: the questions that ran out meanwhile are over. Moving on early brings `ends_at` forward.

Every deadline is exclusive: at `ends_at` the time is up.

`settle` brings a locked attempt up to now. It runs before anything reads or changes an attempt, so a
late answer is refused however late the sweep is. `sweep` (every `QUIZ_SWEEP_SECONDS`) submits the
attempts nobody touches any more.

Locks: a student's request and `sweep` lock the attempt row; closing the quiz locks the quiz, then its
attempts (`end_attempts`); starting share-locks the quiz (`quiz_attempts`). Always quiz before attempt.
Read the clock after the lock: waiting for it takes time too.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import AsyncSessionLocal, run_after_commit
from app.models.quiz import Quiz, QuizAttempt
from app.services import quiz_grading, quiz_store

log = logging.getLogger(__name__)

SWEEP_BATCH = 500


def _capped(quiz: Quiz, at: datetime) -> datetime:
    return at if quiz.closes_at is None else min(at, quiz.closes_at)


def start_clock(quiz: Quiz, attempt: QuizAttempt, now: datetime, question_count: int) -> None:
    """Set a new attempt's deadlines."""
    seconds = timedelta(seconds=quiz.timer_seconds)
    if quiz.timer_mode == "quiz":
        attempt.ends_at = _capped(quiz, now + seconds)
        return
    attempt.current_index = 0
    attempt.question_ends_at = _capped(quiz, now + seconds)
    attempt.ends_at = _capped(quiz, now + question_count * seconds)


def submit(attempt: QuizAttempt, at: datetime, *, auto: bool) -> None:
    """The only way an attempt ends. Once submitted it never changes. Whoever calls this (also through
    `settle` or `advance`) then calls `quiz_grading.on_submit` in the same transaction."""
    if attempt.status == "submitted":
        return
    attempt.status, attempt.submitted_at, attempt.auto_submitted = "submitted", at, auto
    attempt.question_ends_at = None


def settle(quiz: Quiz, attempt: QuizAttempt, now: datetime) -> None:
    """Submit the attempt if its time is up, else move it past the questions whose time is up."""
    if attempt.status == "submitted":
        return
    if attempt.ends_at is not None and attempt.ends_at <= now:
        submit(attempt, attempt.ends_at, auto=True)
        return
    while attempt.question_ends_at is not None and attempt.question_ends_at <= now:
        attempt.current_index += 1
        attempt.question_ends_at = min(attempt.question_ends_at + timedelta(seconds=quiz.timer_seconds),
                                       attempt.ends_at)


def advance(quiz: Quiz, attempt: QuizAttempt, now: datetime) -> None:
    """The student is done with the current question: start the next one's time, or submit after the
    last. The attempt must be settled."""
    remaining = len(attempt.layout) - 1 - attempt.current_index
    if remaining <= 0:
        submit(attempt, now, auto=False)
        return
    seconds = timedelta(seconds=quiz.timer_seconds)
    attempt.current_index += 1
    attempt.question_ends_at = _capped(quiz, now + seconds)
    attempt.ends_at = _capped(quiz, now + remaining * seconds)


async def end_attempts(db: AsyncSession, quiz: Quiz) -> None:
    """Submit every running graded attempt of a quiz being closed. The caller holds the quiz's lock, so
    none can start meanwhile."""
    if quiz.type != "graded":
        return
    attempts = list((await db.execute(
        select(QuizAttempt).where(QuizAttempt.quiz_id == quiz.id, QuizAttempt.status == "in_progress")
        .order_by(QuizAttempt.id).with_for_update().execution_options(populate_existing=True))).scalars())
    now = quiz_store.clock()
    for attempt in attempts:
        settle(quiz, attempt, now)
        submit(attempt, now, auto=True)
    await quiz_grading.on_submit(db, [a.id for a in attempts])


# ── sweep ────────────────────────────────────────────────────────────────────

async def sweep() -> int:
    """Submit the graded attempts whose time is up; how many. One a student is touching right now is
    skipped: that request settles it."""
    async with AsyncSessionLocal() as db:
        rows = (await db.execute(
            select(QuizAttempt).join(Quiz, Quiz.id == QuizAttempt.quiz_id)
            .where(QuizAttempt.status == "in_progress", QuizAttempt.ends_at <= quiz_store.clock(),
                   Quiz.type == "graded")
            .order_by(QuizAttempt.ends_at).limit(SWEEP_BATCH)
            .with_for_update(of=QuizAttempt, skip_locked=True))).scalars().all()
        for attempt in rows:
            submit(attempt, attempt.ends_at, auto=True)
        await quiz_grading.on_submit(db, [a.id for a in rows])
        await db.commit()
        await run_after_commit(db)
    return len(rows)


async def quiz_sweep_loop() -> None:
    """Background task started in main.py. `QUIZ_SWEEP_SECONDS` <= 0 turns it off."""
    if settings.QUIZ_SWEEP_SECONDS <= 0:
        return
    while True:
        try:
            ended = await sweep()
            if ended:
                log.info("quiz sweep: submitted %d attempt(s) whose time was up", ended)
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("quiz sweep failed")
        await _sleep(settings.QUIZ_SWEEP_SECONDS)


_sleep = asyncio.sleep   # tests replace this (not asyncio.sleep itself)
