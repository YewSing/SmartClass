"""Reviewing a draft's questions by hand (FR-604) — S42.

Access and state rules are `quiz_store.editable`'s: the course's lecturers only (403), a draft
without attempts only (409), and the quiz row is locked, so changes to one quiz run one after the
other. A question that isn't in the quiz is 404.

Approval belongs to the exact content the lecturer approved: changing a question, by hand or by the
AI, makes it unapproved again.
"""
from __future__ import annotations

from collections.abc import Iterable

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.quiz import Quiz, QuizQuestion
from app.models.user import User
from app.schemas.quiz import QuestionIn, QuizDetailOut
from app.services import quiz_store

CONTENT = tuple(QuestionIn.model_fields)


def content(question: QuizQuestion) -> dict:
    return {name: getattr(question, name) for name in CONTENT}


# ── changes shared with the AI (quiz/refine.py); the caller holds the quiz lock ──────────────

def find(questions: Iterable[QuizQuestion], question_id: int) -> QuizQuestion:
    for q in questions:
        if q.id == question_id:
            return q
    raise HTTPException(status.HTTP_404_NOT_FOUND, detail="This quiz has no such question")


def ensure_room(total: int) -> None:
    """422 when the quiz would hold more questions than it may."""
    if total > settings.QUIZ_MAX_QUESTIONS:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                            detail=f"A quiz can have at most {settings.QUIZ_MAX_QUESTIONS} questions")


def put(quiz: Quiz, question: QuizQuestion, new: QuestionIn) -> None:
    """Give a question new content. It becomes unapproved, unless nothing changed."""
    values = new.model_dump()
    if content(question) == values:
        return
    for name, value in values.items():
        setattr(question, name, value)
    question.approved = False
    question.updated_at = quiz.updated_at = quiz_store.clock()


def append(db: AsyncSession, quiz: Quiz, position: int, new: QuestionIn) -> QuizQuestion:
    now = quiz_store.clock()
    question = QuizQuestion(quiz_id=quiz.id, position=position, approved=False, created_at=now, updated_at=now,
                            **new.model_dump())
    db.add(question)
    quiz.updated_at = now
    return question


async def remove(db: AsyncSession, quiz: Quiz, question: QuizQuestion) -> None:
    await db.delete(question)
    quiz.updated_at = quiz_store.clock()


def renumber(quiz: Quiz, questions: list[QuizQuestion]) -> None:
    """Positions 0, 1, 2, ... in the order given (the unique constraint is deferred)."""
    for i, q in enumerate(questions):
        if q.position != i:
            q.position = i
            quiz.updated_at = quiz_store.clock()


async def saved(db: AsyncSession, quiz: Quiz) -> QuizDetailOut:
    await db.flush()
    return await quiz_store.detail(db, quiz)


# ── the lecturer's own changes ───────────────────────────────────────────────

async def add(db: AsyncSession, actor: User, quiz_id: int, body: QuestionIn) -> QuizDetailOut:
    """Add a question at the end."""
    quiz = await quiz_store.editable(db, actor, quiz_id)
    questions = await quiz_store.questions_of(db, quiz.id)
    ensure_room(len(questions) + 1)
    append(db, quiz, len(questions), body)
    return await saved(db, quiz)


async def edit(db: AsyncSession, actor: User, quiz_id: int, question_id: int, body: QuestionIn) -> QuizDetailOut:
    quiz = await quiz_store.editable(db, actor, quiz_id)
    put(quiz, find(await quiz_store.questions_of(db, quiz.id), question_id), body)
    return await saved(db, quiz)


async def delete(db: AsyncSession, actor: User, quiz_id: int, question_id: int) -> QuizDetailOut:
    quiz = await quiz_store.editable(db, actor, quiz_id)
    questions = await quiz_store.questions_of(db, quiz.id)
    question = find(questions, question_id)
    await remove(db, quiz, question)
    renumber(quiz, [q for q in questions if q is not question])
    return await saved(db, quiz)


async def reorder(db: AsyncSession, actor: User, quiz_id: int, question_ids: list[int]) -> QuizDetailOut:
    quiz = await quiz_store.editable(db, actor, quiz_id)
    questions = {q.id: q for q in await quiz_store.questions_of(db, quiz.id)}
    if len(set(question_ids)) != len(question_ids):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail="A question is listed twice")
    if set(question_ids) != set(questions):
        raise HTTPException(status.HTTP_409_CONFLICT, detail="The quiz's questions have changed. Reload the quiz.")
    renumber(quiz, [questions[i] for i in question_ids])
    return await saved(db, quiz)


async def set_approval(db: AsyncSession, actor: User, quiz_id: int, question_ids: list[int],
                       approved: bool) -> QuizDetailOut:
    quiz = await quiz_store.editable(db, actor, quiz_id)
    questions = await quiz_store.questions_of(db, quiz.id)
    for question in [find(questions, i) for i in question_ids]:     # all of them, or none
        if question.approved != approved:
            question.approved = approved
            question.updated_at = quiz.updated_at = quiz_store.clock()
    return await saved(db, quiz)
