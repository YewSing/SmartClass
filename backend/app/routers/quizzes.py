"""Lecturer quizzes (FR-605, FR-606) — S40.

Lecturers who teach a class of the course only (403 for everyone else and for unknown ids).
"""
from typing import Optional

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import require_role
from app.models.user import User
from app.schemas.quiz import QuizCreate, QuizDetailOut, QuizListOut, QuizUpdate
from app.services import quiz_store

router = APIRouter(prefix="/lecturer/quizzes", tags=["quizzes"])

_lecturer = require_role("lecturer")


@router.get("", response_model=QuizListOut)
async def list_quizzes(
    course_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(_lecturer),
):
    """The quizzes of the lecturer's courses, newest first, without their questions."""
    return QuizListOut(quizzes=await quiz_store.list_quizzes(db, actor, course_id))


@router.post("", response_model=QuizDetailOut, status_code=status.HTTP_201_CREATED)
async def create_quiz(body: QuizCreate, db: AsyncSession = Depends(get_db), actor: User = Depends(_lecturer)):
    """A new, empty draft. A game quiz always gets a per-question timer."""
    return await quiz_store.create(db, actor, body)


@router.get("/{quiz_id}", response_model=QuizDetailOut)
async def read_quiz(quiz_id: int, db: AsyncSession = Depends(get_db), actor: User = Depends(_lecturer)):
    """The quiz with its questions, answers included."""
    return await quiz_store.detail(db, await quiz_store.get_quiz(db, actor, quiz_id))


@router.patch("/{quiz_id}", response_model=QuizDetailOut)
async def update_quiz(quiz_id: int, body: QuizUpdate, db: AsyncSession = Depends(get_db),
                      actor: User = Depends(_lecturer)):
    """Change a draft's settings (409 once published, closed or attempted)."""
    return await quiz_store.update(db, actor, quiz_id, body)


@router.delete("/{quiz_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_quiz(quiz_id: int, db: AsyncSession = Depends(get_db), actor: User = Depends(_lecturer)):
    """Delete a draft and its questions (409 once published, closed or attempted)."""
    await quiz_store.delete(db, actor, quiz_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
