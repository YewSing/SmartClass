"""A student's quiz cards (FR-607) — S43.

Published and closed quizzes of the courses the student is enrolled in. A card says what the quiz is
and what the student can do with it; it carries nothing of its questions (NFR-41) except how many.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.class_ import ClassOccurrence, Course, Enrollment
from app.models.quiz import Quiz, QuizAttempt, QuizQuestion
from app.schemas.quiz import QuizCardOut, QuizCardState
from app.services import quiz_publish, quiz_store


def card_state(quiz: Quiz, attempt: QuizAttempt | None, now: datetime) -> QuizCardState:
    """`attempted` once the student's attempt is over. One they can still continue is `open`
    (the card's `attempt_status` tells the app to say Resume)."""
    window = quiz_publish.window(quiz, now)
    if attempt is None:
        return window
    time_up = attempt.ends_at is not None and attempt.ends_at <= now
    return "attempted" if attempt.status == "submitted" or window == "closed" or time_up else "open"


def _in_order(cards: list[QuizCardOut]) -> list[QuizCardOut]:
    """Open first (the soonest to close on top), then upcoming (the soonest to open), then the rest,
    newest first. Equal ones: newest first."""
    cards = sorted(cards, key=lambda c: c.id, reverse=True)
    now_open = sorted((c for c in cards if c.state == "open"), key=lambda c: c.closes_at or datetime.max)
    upcoming = sorted((c for c in cards if c.state == "upcoming"), key=lambda c: c.opens_at)
    rest = sorted((c for c in cards if c.state in ("attempted", "closed")),
                  key=lambda c: c.published_at or datetime.min, reverse=True)
    return [*now_open, *upcoming, *rest]


async def list_cards(db: AsyncSession, student_id: int) -> list[QuizCardOut]:
    enrolled = (select(ClassOccurrence.course_id)
                .join(Enrollment, Enrollment.occurrence_id == ClassOccurrence.id)
                .where(Enrollment.student_id == student_id))
    question_count = (select(func.count()).select_from(QuizQuestion)
                      .where(QuizQuestion.quiz_id == Quiz.id, QuizQuestion.approved)
                      .correlate(Quiz).scalar_subquery())
    rows = (await db.execute(
        select(Quiz, Course.code, Course.name, QuizAttempt, question_count)
        .join(Course, Course.id == Quiz.course_id)
        .outerjoin(QuizAttempt, and_(QuizAttempt.quiz_id == Quiz.id, QuizAttempt.student_id == student_id))
        .where(Quiz.course_id.in_(enrolled), Quiz.status.in_(("published", "closed"))))).all()
    now = quiz_store.clock()
    return _in_order([
        QuizCardOut(
            id=quiz.id, course_id=quiz.course_id, course_code=code, course_name=name, title=quiz.title,
            type=quiz.type, state=card_state(quiz, attempt, now), timer_mode=quiz.timer_mode,
            timer_seconds=quiz.timer_seconds, question_count=count, opens_at=quiz.opens_at,
            closes_at=quiz.closes_at, published_at=quiz.published_at,
            attempt_status=attempt.status if attempt else None,
            submitted_at=attempt.submitted_at if attempt else None)
        for quiz, code, name, attempt, count in rows])
