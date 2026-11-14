"""Tests for the quiz read interface (FR-612, FR-613, FR-614, S34).

Exercises app.services.quiz_read against seeded quiz data: per-student per-question
results (correct/score/topic/source_material_id), per-student overall results, and the
active-graded-attempt check (M8 quiz lock data). No permission checks inside the service;
these tests call it directly.
"""

from datetime import datetime, timedelta

import pytest

from app.models.class_ import Enrollment
from app.models.quiz import Quiz, QuizQuestion
from app.models.quiz_attempt import QuizAttempt, QuizAnswer
from app.services import quiz_read

pytestmark = pytest.mark.db


async def _setup(db_session, classroom):
    """Two students in a course; one published quiz (mcq correct="A" + short answer),
    one submitted attempt with both answered, one started attempt on another quiz.
    Returns (student1_id, student2_id, quiz_id, mcq_id, sa_id, attempt1_id)."""
    s1 = classroom["student_ids"][0]
    s2 = classroom["student_ids"][1]
    db_session.add_all([
        Enrollment(student_id=s1, occurrence_id=classroom["occurrence_id"]),
        Enrollment(student_id=s2, occurrence_id=classroom["occurrence_id"]),
    ])
    quiz = Quiz(
        course_id=classroom["course_id"], title="Sample Quiz",
        time_limit_minutes=30, opens_at=datetime.now(),
        closes_at=datetime.now() + timedelta(days=7),
        status="published", created_by=classroom["lecturer_id"],
    )
    db_session.add(quiz)
    await db_session.flush()
    mcq = QuizQuestion(
        quiz_id=quiz.id, course_id=classroom["course_id"], type="mcq",
        question="Capital?", options=["A", "B"], correct_answer="A",
        level="beginner", topic="geo", source_material_id=101, status="approved",
    )
    sa = QuizQuestion(
        quiz_id=quiz.id, course_id=classroom["course_id"], type="short_answer",
        question="Explain gravity.", suggested_answer="mass attraction",
        level="beginner", topic="physics", source_material_id=102, status="approved",
    )
    db_session.add_all([mcq, sa])
    await db_session.flush()
    attempt1 = QuizAttempt(
        quiz_id=quiz.id, student_id=s1,
        started_at=datetime.now() - timedelta(minutes=10),
        deadline=datetime.now() + timedelta(minutes=20),
        status="submitted", score=1.0,
    )
    db_session.add(attempt1)
    await db_session.flush()
    db_session.add_all([
        QuizAnswer(attempt_id=attempt1.id, question_id=mcq.id, answer="A",
                   score=1.0, auto_graded=True),
        QuizAnswer(attempt_id=attempt1.id, question_id=sa.id, answer="gravity pulls",
                   score=None, auto_graded=False),
    ])
    # second quiz, started (active) attempt by s1 -> active graded attempt in course
    quiz2 = Quiz(
        course_id=classroom["course_id"], title="Quiz 2",
        time_limit_minutes=30, opens_at=datetime.now(),
        closes_at=datetime.now() + timedelta(days=7),
        status="published", created_by=classroom["lecturer_id"],
    )
    db_session.add(quiz2)
    await db_session.flush()
    attempt2 = QuizAttempt(
        quiz_id=quiz2.id, student_id=s1,
        started_at=datetime.now() - timedelta(minutes=2),
        deadline=datetime.now() + timedelta(minutes=28),
        status="started", score=None,
    )
    db_session.add(attempt2)
    await db_session.commit()
    return s1, s2, quiz.id, mcq.id, sa.id, attempt1.id


async def test_quiz_result_per_student_per_question(db_session, classroom):
    s1, s2, quiz_id, mcq_id, sa_id, attempt1_id = await _setup(db_session, classroom)

    rows = await quiz_read.quiz_result_per_student_per_question(
        db_session, classroom["course_id"], s1
    )
    assert len(rows) == 2
    mcq_row = [r for r in rows if r["question_id"] == mcq_id][0]
    assert mcq_row["quiz_id"] == quiz_id
    assert mcq_row["type"] == "mcq"
    assert mcq_row["topic"] == "geo"
    assert mcq_row["source_material_id"] == 101
    assert mcq_row["correct"] is True
    assert mcq_row["score"] == 1.0
    assert mcq_row["answered"] is True
    assert mcq_row["has_active_graded_attempt_in_course"] is True  # quiz2 started

    sa_row = [r for r in rows if r["question_id"] == sa_id][0]
    assert sa_row["type"] == "short_answer"
    assert sa_row["topic"] == "physics"
    assert sa_row["source_material_id"] == 102
    assert sa_row["correct"] is None
    assert sa_row["score"] is None
    assert sa_row["answered"] is True


async def test_quiz_result_student2_has_no_answers(db_session, classroom):
    s1, s2, quiz_id, mcq_id, sa_id, attempt1_id = await _setup(db_session, classroom)

    rows = await quiz_read.quiz_result_per_student_per_question(
        db_session, classroom["course_id"], s2
    )
    assert rows == []


async def test_quiz_result_unknown_course_empty(db_session, classroom):
    s1, *_ = await _setup(db_session, classroom)
    rows = await quiz_read.quiz_result_per_student_per_question(
        db_session, 999999, s1
    )
    assert rows == []


async def test_quiz_results_per_student(db_session, classroom):
    s1, s2, quiz_id, mcq_id, sa_id, attempt1_id = await _setup(db_session, classroom)

    summary = await quiz_read.quiz_results_per_student(
        db_session, classroom["course_id"], s1
    )
    assert summary["student_id"] == s1
    assert summary["course_id"] == classroom["course_id"]
    assert len(summary["quizzes"]) == 2
    q = summary["quizzes"][0]
    assert q["attempt_status"] in ("submitted", "started")
    assert summary["average_score"] is not None


async def test_student_has_active_graded_attempt_in_course(db_session, classroom):
    s1, s2, *_ = await _setup(db_session, classroom)

    assert await quiz_read.student_has_active_graded_attempt_in_course(
        db_session, s1, classroom["course_id"]
    ) is True
    assert await quiz_read.student_has_active_graded_attempt_in_course(
        db_session, s2, classroom["course_id"]
    ) is False
    assert await quiz_read.student_has_active_graded_attempt_in_course(
        db_session, s1, 999999
    ) is False
