"""Quiz read interface (FR-612, FR-613, FR-614, S34) — the M7/M8 handover.

Read-only aggregation of quiz results: per student per question (correct/score, question
topic + source material) and whether the student has an active graded attempt in the
course — the data FR-820–FR-824 (M8, Yew Sing) need. No permission checks inside;
callers (M7 lecturer/student endpoints) enforce NFR-04.

Described in docs/interfaces.md.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.class_ import ClassOccurrence
from app.models.quiz import Quiz, QuizQuestion
from app.models.quiz_attempt import QuizAttempt, QuizAnswer


def _course_occurrences(db: AsyncSession, course_id: int):
    """Subquery of occurrence ids belonging to a course."""
    return select(ClassOccurrence.id).where(ClassOccurrence.course_id == course_id)


async def quiz_result_per_student_per_question(
    db: AsyncSession, course_id: int, student_id: int
) -> list[dict]:
    """For one student in one course: per attempted quiz question, correct/score,
    question topic + source material, and whether the question belongs to a quiz the
    student has an active graded attempt in.

    Returns list of dicts: student_id, course_id, quiz_id, quiz_title, question_id,
    question, type, topic, source_material_id, correct (bool for mcq), score, answered,
    has_active_graded_attempt (in course).
    """
    occ_sub = _course_occurrences(db, course_id)

    # Does the student have an active (started, not yet submitted) graded attempt in
    # any published quiz of this course?
    active_attempt = await db.scalar(
        select(QuizAttempt.id)
        .join(Quiz, Quiz.id == QuizAttempt.quiz_id)
        .where(
            QuizAttempt.student_id == student_id,
            QuizAttempt.status == "started",
            Quiz.course_id.in_(occ_sub),
            Quiz.status == "published",
        ).limit(1)
    )
    has_active = active_attempt is not None

    # All of the student's answers on published quizzes in this course.
    result = await db.execute(
        select(QuizAnswer, QuizQuestion, Quiz)
        .join(QuizQuestion, QuizQuestion.id == QuizAnswer.question_id)
        .join(Quiz, Quiz.id == QuizQuestion.quiz_id)
        .where(
            QuizAnswer.attempt_id.in_(
                select(QuizAttempt.id).where(QuizAttempt.student_id == student_id)
            ),
            Quiz.status == "published",
            Quiz.course_id.in_(occ_sub),
        )
        .order_by(Quiz.id, QuizQuestion.id)
    )
    rows = result.all()
    out = []
    for answer, question, quiz in rows:
        correct = None
        if question.type == "mcq":
            correct = (answer.answer is not None and answer.answer == question.correct_answer)
        out.append({
            "student_id": student_id,
            "course_id": course_id,
            "quiz_id": quiz.id,
            "quiz_title": quiz.title,
            "question_id": question.id,
            "question": question.question,
            "type": question.type,
            "topic": question.topic,
            "source_material_id": question.source_material_id,
            "correct": correct,
            "score": answer.score,
            "answered": answer.answer is not None,
            "has_active_graded_attempt_in_course": has_active,
        })
    return out


async def quiz_results_per_student(
    db: AsyncSession, course_id: int, student_id: int
) -> dict:
    """One student's overall quiz results in a course (FR-612 data).

    Returns: student_id, course_id, quizzes (list with id, title, score, status,
    grading_complete), average_score across graded quizzes.
    """
    occ_sub = _course_occurrences(db, course_id)

    quizzes = await db.execute(
        select(Quiz).where(
            Quiz.status == "published",
            Quiz.course_id.in_(occ_sub),
        ).order_by(Quiz.created_at.desc())
    )
    quiz_list = []
    for quiz in quizzes.scalars().all():
        attempt = await db.scalar(
            select(QuizAttempt).where(
                QuizAttempt.quiz_id == quiz.id,
                QuizAttempt.student_id == student_id,
            ).order_by(QuizAttempt.started_at.desc()).limit(1)
        )
        quiz_list.append({
            "quiz_id": quiz.id,
            "title": quiz.title,
            "status": quiz.status,
            "attempt_id": attempt.id if attempt else None,
            "attempt_status": attempt.status if attempt else None,
            "score": attempt.score if attempt else None,
        })

    scored = [q["score"] for q in quiz_list if q["score"] is not None]
    average = (sum(scored) / len(scored)) if scored else None

    return {
        "student_id": student_id,
        "course_id": course_id,
        "quizzes": quiz_list,
        "average_score": average,
    }


async def student_has_active_graded_attempt_in_course(
    db: AsyncSession, student_id: int, course_id: int
) -> bool:
    """Whether the student has a started (not yet submitted) attempt on a published
    quiz in the course — used by M8's quiz lock (FR-614 data)."""
    occ_sub = _course_occurrences(db, course_id)
    active = await db.scalar(
        select(QuizAttempt.id)
        .join(Quiz, Quiz.id == QuizAttempt.quiz_id)
        .where(
            QuizAttempt.student_id == student_id,
            QuizAttempt.status == "started",
            Quiz.course_id.in_(occ_sub),
            Quiz.status == "published",
        ).limit(1)
    )
    return active is not None
