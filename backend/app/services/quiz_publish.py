"""Publishing, unpublishing and closing quizzes (FR-604, FR-606) — S43.

    draft --publish--> published --close--> closed
    published | closed --unpublish--> draft      (only without attempts)

Access is `quiz_store.get_quiz`'s (the course's lecturers only, 403). Each change locks the quiz row
first, so it runs one after the other with question edits, with each other and with attempt starts
(S44, which must lock it too).

Only approved questions are in a published quiz (`published_questions`). The others stay stored for
the lecturer, who finds them again after unpublishing. A published quiz can't be edited, so its
approved questions don't change while students can see it.
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import after_commit
from app.models.class_ import ClassOccurrence, Enrollment
from app.models.quiz import Quiz, QuizQuestion
from app.models.user import Student, User
from app.schemas.quiz import QuizDetailOut
from app.services import notify, quiz_store
from app.services.audit_service import write_log

EVENT_PUBLISHED = "quiz.published"


# ── what students may see ────────────────────────────────────────────────────

def window(quiz: Quiz, now: datetime) -> Literal["upcoming", "open", "closed"]:
    """Whether a published or closed quiz can be taken now: from `opens_at` until just before
    `closes_at`, or until the lecturer closes it."""
    if quiz.status == "closed" or (quiz.closes_at is not None and quiz.closes_at <= now):
        return "closed"
    if quiz.opens_at is not None and quiz.opens_at > now:
        return "upcoming"
    return "open"


async def published_questions(db: AsyncSession, quiz_id: int) -> list[QuizQuestion]:
    """The questions of a published quiz, in order: the approved ones only (FR-604)."""
    return [q for q in await quiz_store.questions_of(db, quiz_id) if q.approved]


async def enrolled_user_ids(db: AsyncSession, course_id: int) -> list[int]:
    """users.id of the active students enrolled in any class of the course, each once."""
    return list((await db.execute(
        select(User.id)
        .join(Student, Student.user_id == User.id)
        .join(Enrollment, Enrollment.student_id == Student.id)
        .join(ClassOccurrence, ClassOccurrence.id == Enrollment.occurrence_id)
        .where(ClassOccurrence.course_id == course_id, User.status == "active", User.role == "student")
        .distinct().order_by(User.id))).scalars())


# ── the lecturer's actions ───────────────────────────────────────────────────

def _conflict(detail: str) -> HTTPException:
    return HTTPException(status.HTTP_409_CONFLICT, detail=detail)


def _invalid(detail: str) -> HTTPException:
    return HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail=detail)


async def _move(db: AsyncSession, actor: User, quiz: Quiz, to: str, action: str, **extra) -> QuizDetailOut:
    await write_log(db, actor.id, action, "m6_quiz", quiz.id,
                    {"status": quiz.status}, {"status": to, "title": quiz.title, **extra})
    quiz.status, quiz.updated_at = to, quiz_store.clock()
    await db.flush()
    return await quiz_store.detail(db, quiz)


async def publish(db: AsyncSession, actor: User, quiz_id: int) -> QuizDetailOut:
    """Draft → published, and `quiz.published` to the course's students after the commit."""
    quiz = await quiz_store.get_quiz(db, actor, quiz_id, lock=True)
    if quiz.status != "draft":
        raise _conflict("Only a draft quiz can be published")
    questions = await published_questions(db, quiz.id)
    if not questions:
        raise _invalid("Approve at least one question before publishing")
    now = quiz_store.clock()
    if quiz.closes_at is not None and quiz.closes_at <= now:
        raise _invalid("The closing time has passed. Change it before publishing.")
    quiz.published_at = now
    out = await _move(db, actor, quiz, "published", "QUIZ_PUBLISH", questions=len(questions))

    user_ids = await enrolled_user_ids(db, quiz.course_id)
    payload = {"quiz_id": quiz.id, "quiz_title": quiz.title, "course_code": out.course_code}
    if window(quiz, now) == "upcoming":
        when = f"{quiz.opens_at.day} {quiz.opens_at:%b %Y, %H:%M}"
        payload["message"] = f"A new quiz in {out.course_code} opens on {when}."

    async def _after() -> None:
        await notify.emit(EVENT_PUBLISHED, user_ids, payload)

    after_commit(db, _after)
    return out


async def unpublish(db: AsyncSession, actor: User, quiz_id: int) -> QuizDetailOut:
    """Back to a draft the lecturer can edit. Not once students have attempts: those would be left
    without their quiz (close it instead)."""
    quiz = await quiz_store.get_quiz(db, actor, quiz_id, lock=True)
    if quiz.status == "draft":
        raise _conflict("This quiz is not published")
    if await quiz_store.has_attempts(db, quiz.id):
        raise _conflict("Students have already started this quiz, so it can't be unpublished")
    quiz.published_at = None
    return await _move(db, actor, quiz, "draft", "QUIZ_UNPUBLISH")


async def close(db: AsyncSession, actor: User, quiz_id: int) -> QuizDetailOut:
    """Published → closed, whatever its closing time."""
    quiz = await quiz_store.get_quiz(db, actor, quiz_id, lock=True)
    if quiz.status != "published":
        raise _conflict("Only a published quiz can be closed")
    return await _move(db, actor, quiz, "closed", "QUIZ_CLOSE")
