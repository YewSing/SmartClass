"""Tests for per-student engagement indicators (FR-701, FR-702, FR-703, S41).

Covers: attendance rate + absence frequency (from attendance_read), participation
frequency / questions / votes / responses / reactions / IDU signals (from
participation_read), quiz scores + trend across quizzes (from quiz_read), and the
NFR-04 access rule (lecturer who teaches the class; other lecturer 403; student 403).
No schema change — reads via attendance_read / participation_read / quiz_read.
"""

from datetime import datetime, timedelta

import pytest
from sqlalchemy import select

from app.models.class_ import ClassOccurrence, Enrollment
from app.models.quiz import Quiz, QuizQuestion
from app.models.quiz_attempt import QuizAttempt, QuizAnswer

pytestmark = pytest.mark.db


async def _setup(db_session, classroom):
    """Two enrolled students, one published quiz with one MCQ, one submitted attempt by
    s1 scored 1.0, one attendance closed session with s1 present, s2 absent.
    Returns (s1_id, s2_id, occurrence_id, course_id)."""
    s1 = classroom["student_ids"][0]
    s2 = classroom["student_ids"][1]
    db_session.add_all([
        Enrollment(student_id=s1, occurrence_id=classroom["occurrence_id"]),
        Enrollment(student_id=s2, occurrence_id=classroom["occurrence_id"]),
    ])
    # attendance closed session with one record (s1 present)
    sess = (
        await db_session.execute(
            select(ClassOccurrence).where(
                ClassOccurrence.id == classroom["occurrence_id"]
            )
        )
    ).scalar_one()
    from app.models.attendance import AttendanceRecord
    from app.models.session import AttendanceSession
    a_sess = AttendanceSession(
        occurrence_id=sess.id,
        lecturer_id=classroom["lecturer_id"],
        status="closed",
        opened_at=datetime.now(),
        closed_at=datetime.now(),
    )
    db_session.add(a_sess)
    await db_session.flush()
    db_session.add(AttendanceRecord(session_id=a_sess.id, student_id=s1, status="present"))
    # quiz + submitted attempt by s1 (mcq correct)
    quiz = Quiz(
        course_id=classroom["course_id"], title="Quiz 1",
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
    db_session.add(mcq)
    await db_session.flush()
    attempt = QuizAttempt(
        quiz_id=quiz.id, student_id=s1,
        started_at=datetime.now() - timedelta(minutes=5),
        deadline=datetime.now() + timedelta(minutes=25),
        status="submitted", score=1.0,
    )
    db_session.add(attempt)
    await db_session.flush()
    db_session.add(
        QuizAnswer(attempt_id=attempt.id, question_id=mcq.id, answer="A",
                   score=1.0, auto_graded=True)
    )
    await db_session.commit()
    return s1, s2, classroom["occurrence_id"], classroom["course_id"]


# ── HTTP endpoint ───────────────────────────────────────────────────────────

async def test_student_engagement_indicators(lecturer_client, classroom, db_session):
    s1, s2, occurrence_id, course_id = await _setup(db_session, classroom)

    resp = await lecturer_client.get(
        f"/lecturer/analytics/{occurrence_id}/students"
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert len(body) == 2
    s1_row = [r for r in body if r["student_id"] == s1][0]
    assert s1_row["course_id"] == course_id
    assert s1_row["attendance"]["rate"] is not None
    assert s1_row["participation"]["questions"] == 0
    assert s1_row["participation"]["idu_signals"] == 0
    assert s1_row["quizzes"]["scores"] == [1.0]
    assert s1_row["quizzes"]["average_score"] == 1.0
    assert len(s1_row["quizzes"]["trend"]) == 1
    assert s1_row["quizzes"]["trend"][0]["score"] == 1.0
    assert s1_row["student_name"] == "Test Student"


async def test_student_without_quiz_has_null_scores(
    lecturer_client, classroom, db_session
):
    s1, s2, occurrence_id, course_id = await _setup(db_session, classroom)

    resp = await lecturer_client.get(
        f"/lecturer/analytics/{occurrence_id}/students"
    )
    body = resp.json()
    s2_row = [r for r in body if r["student_id"] == s2][0]
    assert s2_row["quizzes"]["scores"] == []
    assert s2_row["quizzes"]["average_score"] is None
    assert s2_row["quizzes"]["trend"] == []


async def test_engagement_other_lecturer_is_403(
    other_lecturer_client, classroom, db_session
):
    await _setup(db_session, classroom)
    resp = await other_lecturer_client.get(
        f"/lecturer/analytics/{classroom['occurrence_id']}/students"
    )
    assert resp.status_code == 403, resp.text


async def test_engagement_student_is_403(student_client, classroom, db_session):
    await _setup(db_session, classroom)
    resp = await student_client.get(
        f"/lecturer/analytics/{classroom['occurrence_id']}/students"
    )
    assert resp.status_code == 403, resp.text


async def test_engagement_unknown_class_is_404(lecturer_client, classroom):
    resp = await lecturer_client.get("/lecturer/analytics/999999/students")
    assert resp.status_code == 404, resp.text
