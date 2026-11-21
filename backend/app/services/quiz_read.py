"""Read-only Module 6 interface for analytics (FR-621).

No caller receives answer text here: M7 gets only outcomes, topics and participation.
"""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.quiz import Quiz, QuizAttempt


async def course_outcomes(db: AsyncSession, course_id: int) -> list[dict]:
    rows = (await db.execute(
        select(Quiz, QuizAttempt).join(QuizAttempt, QuizAttempt.quiz_id == Quiz.id).where(
            Quiz.course_id == course_id, QuizAttempt.status == "submitted"
        )
    )).all()
    return [{
        "student_id": attempt.student_id,
        "quiz_id": quiz.id,
        "quiz_type": quiz.quiz_type,
        "submitted_at": attempt.submitted_at,
        "score": attempt.score,
        "topics": [question.get("topic") for question in quiz.questions if question.get("topic")],
        "participated": True,
    } for quiz, attempt in rows]
