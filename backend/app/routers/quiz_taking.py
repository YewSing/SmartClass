"""Taking quizzes + auto-grade (FR-606, FR-607, FR-608, S32).

GET    /student/quizzes                              published quizzes of enrolled courses
POST   /student/quizzes/{quiz_id}/attempt            start one attempt
POST   /student/quizzes/attempts/{attempt_id}/submit submit; MCQ auto-graded
POST   /student/quizzes/attempts/auto-submit-expired background check (lecturer/admin)
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import require_role
from app.models.quiz_attempt import QuizAnswer
from app.models.user import Student, User
from app.schemas.quiz import (
    QuizAnswerOut,
    StudentQuizOut,
    SubmitAttemptRequest,
)
from app.services.quiz_taking import (
    auto_submit_expired_attempts,
    list_student_quizzes as _svc_list_student_quizzes,
    start_attempt as _svc_start_attempt,
    submit_attempt as _svc_submit_attempt,
)

router = APIRouter(tags=["quizzes"])

_student = require_role("student")

_ERROR_TO_STATUS = {
    "quiz_not_published": status.HTTP_404_NOT_FOUND,
    "not_enrolled": status.HTTP_403_FORBIDDEN,
    "already_attempted": status.HTTP_409_CONFLICT,
    "not_yet_open": status.HTTP_403_FORBIDDEN,
    "quiz_closed": status.HTTP_403_FORBIDDEN,
    "attempt_not_found": status.HTTP_404_NOT_FOUND,
    "already_submitted": status.HTTP_409_CONFLICT,
    "expired": status.HTTP_403_FORBIDDEN,
}


def _http_error(exc: ValueError) -> HTTPException:
    return HTTPException(
        status_code=_ERROR_TO_STATUS.get(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR),
        detail=str(exc),
    )


async def _student_for_actor(db: AsyncSession, actor: User) -> Student:
    student = (await db.execute(select(Student).where(Student.user_id == actor.id))).scalar_one_or_none()
    if not student:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Student profile not found")
    return student


@router.get("/student/quizzes", response_model=list[StudentQuizOut])
async def list_student_quizzes(
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(_student),
):
    """Published quizzes of courses the student is enrolled in (FR-607)."""
    student = await _student_for_actor(db, actor)
    rows = await _svc_list_student_quizzes(db, student.id)
    return [StudentQuizOut.model_validate(r) for r in rows]


@router.post("/student/quizzes/{quiz_id}/attempt", status_code=status.HTTP_201_CREATED)
async def start_quiz_attempt(
    quiz_id: int,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(_student),
):
    """Start one attempt at a published quiz of an enrolled course (FR-606, FR-607)."""
    student = await _student_for_actor(db, actor)
    try:
        attempt = await _svc_start_attempt(db, quiz_id, student.id)
    except ValueError as exc:
        raise _http_error(exc)
    return {"attempt_id": attempt.id, "started_at": attempt.started_at, "deadline": attempt.deadline}


@router.post("/student/quizzes/attempts/{attempt_id}/submit")
async def submit_quiz_attempt(
    attempt_id: int,
    body: SubmitAttemptRequest,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(_student),
):
    """Submit an attempt; MCQ answers auto-graded, short answers unscored (FR-608)."""
    student = await _student_for_actor(db, actor)
    try:
        attempt = await _svc_submit_attempt(
            db, attempt_id,
            [{"question_id": a.question_id, "answer": a.answer} for a in body.answers],
            student.id,
        )
    except ValueError as exc:
        raise _http_error(exc)
    answer_rows = (await db.execute(
        select(QuizAnswer).where(QuizAnswer.attempt_id == attempt.id)
    )).scalars().all()
    answers = [
        QuizAnswerOut(
            question_id=a.question_id, answer=a.answer, score=a.score, auto_graded=a.auto_graded,
        )
        for a in answer_rows
    ]
    return {
        "attempt_id": attempt.id, "status": attempt.status, "score": attempt.score,
        "auto_submitted": attempt.auto_submitted, "answers": answers,
    }


@router.post("/student/quizzes/attempts/auto-submit-expired", status_code=status.HTTP_204_NO_CONTENT)
async def auto_submit_expired(
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(require_role("lecturer", "admin")),
):
    """Background check: auto-submit started attempts past their deadline."""
    await auto_submit_expired_attempts(db)
    return None
