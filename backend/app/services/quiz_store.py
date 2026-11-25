"""Draft quizzes and their settings (FR-605, FR-606) — S40.

Kept outside `app/services/quiz/`, which holds the AI drafting code (S41) and triggers the live LLM
tests when it changes.

Access (NFR-04): a quiz belongs to a course, so every lecturer assigned to a class of that course
may work on it. Everyone else, and an unknown quiz or course id, gets 403 (ids can't be probed).

Only a draft without attempts can be changed or deleted (409). Both lock the quiz row first; code
that publishes a quiz (`quiz_publish`) or starts an attempt (S44) must lock it too, so neither can slip in
between the check and the write.
"""
from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.timezone import now_myt
from app.models.class_ import ClassOccurrence, Course
from app.models.quiz import TIMER_LIMITS, Quiz, QuizAttempt, QuizQuestion
from app.models.user import Lecturer, User
from app.schemas.quiz import AiScope, QuestionIn, QuestionOut, QuizCreate, QuizDetailOut, QuizOut, QuizUpdate
from app.services.audit_service import write_log

DEFAULTS: dict[str, Any] = {
    "opens_at": None, "closes_at": None, "shuffle": False, "release": "manual",
    "release_marks": True, "release_answers": True, "speed_bonus": True,
}
SETTINGS = ("title", "type", "timer_mode", "timer_seconds", *DEFAULTS)


def clock() -> datetime:
    """Current naive MYT time. Tests monkeypatch this."""
    return now_myt()


def _invalid(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=detail)


# ── settings ─────────────────────────────────────────────────────────────────

def _default_seconds(timer_mode: str) -> int:
    return (settings.QUIZ_DEFAULT_QUESTION_SECONDS if timer_mode == "question"
            else settings.QUIZ_DEFAULT_QUIZ_SECONDS)


def resolve_settings(current: dict[str, Any] | None, changes: dict[str, Any]) -> dict[str, Any]:
    """The full settings after applying `changes` to `current` (None for a new quiz); 422 when they
    don't fit together.

    Timer (FR-606): a game is always per question. A whole-quiz time sent along with that forced
    change is dropped, not reused as a per-question time. Changing the mode without a new time
    gives the mode's default."""
    out = {**DEFAULTS, **(current or {}), **changes}
    mode = out.get("timer_mode") or ("question" if out["type"] == "game" else "quiz")
    forced = out["type"] == "game" and mode == "quiz"
    if forced:
        mode = "question"
    meant_for_the_whole_quiz = forced and changes.get("timer_mode") == "quiz"
    if "timer_seconds" in changes and not meant_for_the_whole_quiz:
        seconds = changes["timer_seconds"]
    elif current is not None and current["timer_mode"] == mode:
        seconds = current["timer_seconds"]
    else:
        seconds = _default_seconds(mode)
    low, high = TIMER_LIMITS[mode]
    if not low <= seconds <= high:
        what = "per question" if mode == "question" else "for the whole quiz"
        raise _invalid(f"The time limit {what} must be {low} to {high} seconds")
    out["timer_mode"], out["timer_seconds"] = mode, seconds

    if out["opens_at"] is not None and out["closes_at"] is not None and out["closes_at"] <= out["opens_at"]:
        raise _invalid("The closing time must be after the opening time")
    if out["release"] == "on_close" and not (out["release_marks"] or out["release_answers"]):
        raise _invalid("Choose what to release when the quiz closes: marks, answers or both")
    return out


# ── access ───────────────────────────────────────────────────────────────────

def _taught_course_ids(actor: User):
    return (select(ClassOccurrence.course_id)
            .join(Lecturer, Lecturer.id == ClassOccurrence.lecturer_id)
            .where(Lecturer.user_id == actor.id))


async def ensure_teaches_course(db: AsyncSession, actor: User, course_id: int) -> None:
    """403 unless the actor is the lecturer of at least one class of the course."""
    teaches = await db.scalar(_taught_course_ids(actor).where(ClassOccurrence.course_id == course_id).limit(1))
    if teaches is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not teach this course")


async def get_quiz(db: AsyncSession, actor: User, quiz_id: int, *, lock: bool = False) -> Quiz:
    """A quiz of a course the actor teaches (403 otherwise), row-locked for a write with `lock`."""
    stmt = select(Quiz).where(Quiz.id == quiz_id, Quiz.course_id.in_(_taught_course_ids(actor)))
    if lock:
        stmt = stmt.with_for_update().execution_options(populate_existing=True)
    quiz = (await db.execute(stmt)).scalar_one_or_none()
    if quiz is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not teach this quiz's course")
    return quiz


async def has_attempts(db: AsyncSession, quiz_id: int) -> bool:
    return await db.scalar(select(QuizAttempt.id).where(QuizAttempt.quiz_id == quiz_id).limit(1)) is not None


async def editable(db: AsyncSession, actor: User, quiz_id: int) -> Quiz:
    """The quiz, row-locked, when its settings and questions may change (409 otherwise)."""
    quiz = await get_quiz(db, actor, quiz_id, lock=True)
    if quiz.status != "draft":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Only a draft quiz can be changed")
    if await has_attempts(db, quiz.id):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                            detail="This quiz has attempts, so it can't be changed")
    return quiz


# ── reads ────────────────────────────────────────────────────────────────────

async def _out(db: AsyncSession, quizzes: list[Quiz]) -> list[QuizOut]:
    if not quizzes:
        return []
    courses = {c.id: c for c in (await db.execute(
        select(Course).where(Course.id.in_({q.course_id for q in quizzes})))).scalars()}
    counts = {row[0]: (row[1], row[2]) for row in (await db.execute(
        select(QuizQuestion.quiz_id, func.count(), func.count().filter(QuizQuestion.approved))
        .where(QuizQuestion.quiz_id.in_([q.id for q in quizzes])).group_by(QuizQuestion.quiz_id))).all()}
    out = []
    for q in quizzes:
        total, approved = counts.get(q.id, (0, 0))
        course = courses[q.course_id]
        out.append(QuizOut(
            id=q.id, course_id=q.course_id, course_code=course.code, course_name=course.name, status=q.status,
            question_count=total, approved_count=approved, published_at=q.published_at, created_at=q.created_at,
            updated_at=q.updated_at,
            **{name: getattr(q, name) for name in SETTINGS}))
    return out


async def list_quizzes(db: AsyncSession, actor: User, course_id: int | None = None) -> list[QuizOut]:
    """The quizzes of the actor's courses (or of one of them), newest first."""
    stmt = select(Quiz).where(Quiz.course_id.in_(_taught_course_ids(actor)))
    if course_id is not None:
        await ensure_teaches_course(db, actor, course_id)
        stmt = stmt.where(Quiz.course_id == course_id)
    rows = (await db.execute(stmt.order_by(Quiz.created_at.desc(), Quiz.id.desc()))).scalars()
    return await _out(db, list(rows))


async def questions_of(db: AsyncSession, quiz_id: int) -> list[QuizQuestion]:
    """The quiz's questions in order, freshly read."""
    return list((await db.execute(
        select(QuizQuestion).where(QuizQuestion.quiz_id == quiz_id)
        .order_by(QuizQuestion.position, QuizQuestion.id)
        .execution_options(populate_existing=True))).scalars())


async def detail(db: AsyncSession, quiz: Quiz) -> QuizDetailOut:
    """The quiz with its questions and their answers (for its lecturers only)."""
    [base] = await _out(db, [quiz])
    questions = await questions_of(db, quiz.id)
    return QuizDetailOut(**base.model_dump(), questions=[QuestionOut.model_validate(q) for q in questions])


# ── writes ───────────────────────────────────────────────────────────────────

async def create(db: AsyncSession, actor: User, body: QuizCreate,
                 questions: Sequence[QuestionIn] = (), scope: AiScope | None = None) -> QuizDetailOut:
    """A new draft, with the AI's questions and scope when it was drafted from a prompt (S41).
    Questions are never approved here (FR-604)."""
    await ensure_teaches_course(db, actor, body.course_id)
    values = resolve_settings(None, body.model_dump(exclude_unset=True, exclude={"course_id"}))
    now = clock()
    quiz = Quiz(course_id=body.course_id, created_by_user_id=actor.id, status="draft",
                ai_scope=scope.model_dump() if scope else None, created_at=now, updated_at=now, **values)
    db.add(quiz)
    await db.flush()
    db.add_all([QuizQuestion(quiz_id=quiz.id, position=i, approved=False, created_at=now, updated_at=now,
                             **q.model_dump()) for i, q in enumerate(questions)])
    await db.flush()
    return await detail(db, quiz)


async def update(db: AsyncSession, actor: User, quiz_id: int, body: QuizUpdate) -> QuizDetailOut:
    quiz = await editable(db, actor, quiz_id)
    current = {name: getattr(quiz, name) for name in SETTINGS}
    values = resolve_settings(current, body.model_dump(exclude_unset=True))
    if values != current:
        for name, value in values.items():
            setattr(quiz, name, value)
        quiz.updated_at = clock()
        await db.flush()
    return await detail(db, quiz)


async def delete(db: AsyncSession, actor: User, quiz_id: int) -> None:
    quiz = await editable(db, actor, quiz_id)
    await write_log(db, actor.id, "QUIZ_DELETE", "m6_quiz", quiz.id,
                    {"course_id": quiz.course_id, "title": quiz.title, "type": quiz.type})
    await db.delete(quiz)
    await db.flush()
