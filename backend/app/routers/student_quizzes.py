"""A student's quizzes (FR-607) — S43. Own data of enrolled courses only (NFR-04)."""
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import require_role
from app.models.user import Student, User
from app.schemas.quiz import QuizCardListOut
from app.services import quiz_cards

router = APIRouter(prefix="/student/me/quizzes", tags=["quizzes"])


@router.get("", response_model=QuizCardListOut)
async def my_quizzes(db: AsyncSession = Depends(get_db), actor: User = Depends(require_role("student"))):
    """A card per published or closed quiz of the student's courses: open ones first, then upcoming,
    then the attempted and closed ones, newest first. Never the questions or answers."""
    student_id = await db.scalar(select(Student.id).where(Student.user_id == actor.id))
    if student_id is None:
        return QuizCardListOut(quizzes=[])
    return QuizCardListOut(quizzes=await quiz_cards.list_cards(db, student_id))
