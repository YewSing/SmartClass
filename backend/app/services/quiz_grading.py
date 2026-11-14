"""Short-answer scoring + AI suggestion (FR-609, FR-610, FR-611, S33).

- Lecturer lists unscored short answers per quiz attempt and scores them (FR-609).
- `POST .../suggest-score` returns an AI-suggested score via `chat_json` (record/replay +
  1 live case; malformed output retried once then 502, like T86) (FR-610).
- A quiz attempt becomes "grading complete" when no short answer is unscored, and only then
  can the student see their score and per-question results (FR-611 — tested: not visible
  before completion).

No schema change: reuses `quiz_answers.score` (nullable) created in S32. Grading complete is
computed (all short_answer answers on the attempt have a non-null score).
"""

import sqlalchemy as sa
from sqlalchemy import select
from fastapi import HTTPException, status

from app.core.database import AsyncSession
from app.models.class_ import ClassOccurrence
from app.models.quiz import Quiz, QuizQuestion
from app.models.quiz_attempt import QuizAttempt, QuizAnswer
from app.models.user import Lecturer
from app.schemas.quiz import SuggestScoreOut
from app.services.kb import llm

_SUGGEST_SCORE_PROMPT = """You are an exam marker. Suggest a score (0-100) for the student's
short-answer response, based on the question and the ideal answer. Return a single JSON
object with keys:
- "suggested_score": number 0-100
- "reasoning": one sentence explaining the score

Question: {question}
Ideal answer: {ideal}
Student's answer: {answer}

Reply with only the JSON object."""


async def _accessible_attempt(db: AsyncSession, attempt_id: int, lecturer: Lecturer) -> QuizAttempt:
    attempt = await db.get(QuizAttempt, attempt_id)
    if not attempt:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attempt not found")
    quiz = await db.get(Quiz, attempt.quiz_id)
    if not quiz:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quiz not found")
    teaches = await db.scalar(
        select(ClassOccurrence.id).where(
            ClassOccurrence.course_id == quiz.course_id,
            ClassOccurrence.lecturer_id == lecturer.id,
        ).limit(1)
    )
    if not teaches:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not teach this course")
    return attempt


async def list_unscored_short_answers(
    db: AsyncSession, attempt_id: int, lecturer: Lecturer
) -> list[dict]:
    """Short answers on the attempt that are not yet scored (score is null) (FR-609)."""
    await _accessible_attempt(db, attempt_id, lecturer)
    result = await db.execute(
        select(QuizAnswer, QuizQuestion)
        .join(QuizQuestion, QuizQuestion.id == QuizAnswer.question_id)
        .where(
            QuizAnswer.attempt_id == attempt_id,
            QuizQuestion.type == "short_answer",
            QuizAnswer.score.is_(None),
        )
        .order_by(QuizAnswer.id)
    )
    return [
        {
            "answer_id": a.id,
            "question_id": q.id,
            "question": q.question,
            "answer": a.answer,
            "suggested_answer": q.suggested_answer,
            "score": a.score,
        }
        for a, q in result.all()
    ]


async def score_short_answer(
    db: AsyncSession, answer_id: int, score: float, lecturer: Lecturer
) -> QuizAnswer:
    """Lecturer scores a short answer (FR-609)."""
    answer = await db.get(QuizAnswer, answer_id)
    if not answer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Answer not found")
    question = await db.get(QuizQuestion, answer.question_id)
    if question.type != "short_answer":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Not a short answer")
    await _accessible_attempt(db, answer.attempt_id, lecturer)
    answer.score = score
    await db.commit()
    await db.refresh(answer)
    return answer


async def suggest_score(db: AsyncSession, answer_id: int) -> dict:
    """AI-suggested score for a short answer (FR-610). Malformed output retried once,
    then LLMMalformedOutput (502)."""
    answer = await db.get(QuizAnswer, answer_id)
    if not answer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Answer not found")
    question = await db.get(QuizQuestion, answer.question_id)
    if question.type != "short_answer":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Not a short answer")

    prompt = _SUGGEST_SCORE_PROMPT.format(
        question=question.question,
        ideal=question.suggested_answer or "(no ideal answer recorded)",
        answer=answer.answer or "(no answer)",
    )
    suggestion = await llm.chat_json(
        [{"role": "user", "content": prompt}],
        validator=SuggestScoreOut,
    )
    return {
        "suggested_score": suggestion.suggested_score,
        "reasoning": suggestion.reasoning,
    }


async def _is_grading_complete(db: AsyncSession, attempt_id: int) -> bool:
    """True when every short_answer on the attempt has a non-null score."""
    unscored = await db.scalar(
        select(sa.func.count(QuizAnswer.id)).join(
            QuizQuestion, QuizQuestion.id == QuizAnswer.question_id
        ).where(
            QuizAnswer.attempt_id == attempt_id,
            QuizQuestion.type == "short_answer",
            QuizAnswer.score.is_(None),
        )
    )
    return (unscored or 0) == 0


async def get_attempt_result(
    db: AsyncSession, attempt_id: int, student_id: int
) -> dict:
    """Student result for an attempt, gated on grading complete (FR-611)."""
    attempt = await db.get(QuizAttempt, attempt_id)
    if not attempt:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attempt not found")
    if attempt.student_id != student_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your attempt")
    complete = await _is_grading_complete(db, attempt_id)
    student_visible = complete and attempt.status in ("submitted", "auto_submitted")
    result = await db.execute(
        select(QuizAnswer, QuizQuestion)
        .join(QuizQuestion, QuizQuestion.id == QuizAnswer.question_id)
        .where(QuizAnswer.attempt_id == attempt_id)
        .order_by(QuizAnswer.id)
    )
    answers = []
    for a, q in result.all():
        answers.append({
            "question_id": q.id,
            "question": q.question,
            "type": q.type,
            "answer": a.answer,
            "score": a.score if (student_visible or q.type == "mcq") else None,
            "auto_graded": a.auto_graded,
            "suggested_answer": q.suggested_answer if student_visible else None,
        })
    return {
        "attempt_id": attempt.id,
        "status": attempt.status,
        "score": attempt.score if student_visible else None,
        "auto_submitted": attempt.auto_submitted,
        "grading_complete": complete,
        "student_score_visible": student_visible,
        "answers": answers,
    }


async def list_quiz_attempts(
    db: AsyncSession, quiz_id: int, lecturer: Lecturer
) -> list[dict]:
    """Attempts for a quiz (lecturer, NFR-04)."""
    quiz = await db.get(Quiz, quiz_id)
    if not quiz:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quiz not found")
    teaches = await db.scalar(
        select(ClassOccurrence.id).where(
            ClassOccurrence.course_id == quiz.course_id,
            ClassOccurrence.lecturer_id == lecturer.id,
        ).limit(1)
    )
    if not teaches:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not teach this course")
    result = await db.execute(
        select(QuizAttempt).where(QuizAttempt.quiz_id == quiz_id).order_by(QuizAttempt.started_at.desc())
    )
    out = []
    for a in result.scalars().all():
        complete = await _is_grading_complete(db, a.id)
        out.append({
            "attempt_id": a.id,
            "student_id": a.student_id,
            "status": a.status,
            "score": a.score,
            "auto_submitted": a.auto_submitted,
            "grading_complete": complete,
            "started_at": a.started_at,
            "submitted_at": a.submitted_at,
        })
    return out
