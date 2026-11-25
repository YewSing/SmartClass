"""A student's quizzes (FR-607) — S43; graded attempts (FR-607, FR-608) — S44; results (FR-618) — S46.
Own data of enrolled courses only (NFR-04)."""
from fastapi import APIRouter, Depends, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import require_role
from app.models.user import Student, User
from app.schemas.quiz import AnswerIn, AttemptOut, NextQuestionIn, QuizCardListOut, StudentResultOut
from app.services import quiz_attempts, quiz_cards, quiz_results

router = APIRouter(prefix="/student/me/quizzes", tags=["quizzes"])

_student = require_role("student")


@router.get("", response_model=QuizCardListOut)
async def my_quizzes(db: AsyncSession = Depends(get_db), actor: User = Depends(_student)):
    """A card per published or closed quiz of the student's courses: open ones first, then upcoming,
    then the attempted and closed ones, newest first. Never the questions or answers."""
    student_id = await db.scalar(select(Student.id).where(Student.user_id == actor.id))
    if student_id is None:
        return QuizCardListOut(quizzes=[])
    return QuizCardListOut(quizzes=await quiz_cards.list_cards(db, student_id))


# ── graded attempts — S44 ────────────────────────────────────────────────────

@router.post("/{quiz_id}/attempt", response_model=AttemptOut)
async def start_attempt(quiz_id: int, response: Response, db: AsyncSession = Depends(get_db),
                        actor: User = Depends(_student)):
    """Start the quiz (201) or resume it (200). 409 when it isn't open, or the one attempt is over."""
    out, new = await quiz_attempts.start(db, actor, quiz_id)
    response.status_code = status.HTTP_201_CREATED if new else status.HTTP_200_OK
    return out


@router.get("/{quiz_id}/attempt", response_model=AttemptOut)
async def read_attempt(quiz_id: int, db: AsyncSession = Depends(get_db), actor: User = Depends(_student)):
    """The student's attempt as it is now (404 when not started)."""
    return await quiz_attempts.read(db, actor, quiz_id)


@router.put("/{quiz_id}/attempt/answers/{question_id}", response_model=AttemptOut)
async def save_answer(quiz_id: int, question_id: int, body: AnswerIn, db: AsyncSession = Depends(get_db),
                      actor: User = Depends(_student)):
    """Save, change or clear one answer. 409 when its time is up."""
    return await quiz_attempts.save_answer(db, actor, quiz_id, question_id, body)


@router.post("/{quiz_id}/attempt/next", response_model=AttemptOut)
async def next_question(quiz_id: int, body: NextQuestionIn, db: AsyncSession = Depends(get_db),
                        actor: User = Depends(_student)):
    """With a timer per question: go on to the next question, or submit after the last one."""
    return await quiz_attempts.next_question(db, actor, quiz_id, body.question_id)


@router.post("/{quiz_id}/attempt/submit", response_model=AttemptOut)
async def submit_attempt(quiz_id: int, db: AsyncSession = Depends(get_db), actor: User = Depends(_student)):
    """Submit the attempt (repeating it changes nothing)."""
    return await quiz_attempts.submit(db, actor, quiz_id)


# ── the result (FR-618) — S46 ────────────────────────────────────────────────

@router.get("/{quiz_id}/result", response_model=StudentResultOut)
async def my_result(quiz_id: int, db: AsyncSession = Depends(get_db), actor: User = Depends(_student)):
    """The student's own result: only the parts the lecturer has released (404 when not taken)."""
    return await quiz_results.student_result(db, actor, quiz_id)
