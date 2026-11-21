"""Tests for student self view (FR-706, S43).

Covers: `GET /student/me/analytics` returns the student's own attendance status and
engagement indicators across enrolled courses, and nothing about other students.
NFR-04: lecturer endpoints reject students (a student cannot read another student's
indicators via lecturer endpoints).

No schema change — reads via attendance_read / participation_read / quiz_read.
"""

from datetime import datetime, timedelta

import pytest
from sqlalchemy import select

from app.models.attendance import AttendanceRecord
from app.models.class_ import ClassOccurrence, Enrollment
from app.models.quiz import Quiz, QuizQuestion
from app.models.quiz_attempt import QuizAttempt, QuizAnswer
from app.models.session import AttendanceSession

pytestmark = pytest.mark.db


async def _setup(db_session, classroom):
    """Student enrolled in a course with one closed session (present), one published
    quiz with an mcq and a submitted attempt scored 1.0.
    Returns (student_id, occurrence_id, course_id)."""
    s1 = classroom["student_ids"][0]
    db_session.add(Enrollment(student_id=s1, occurrence_id=classroom["occurrence_id"]))
    now = datetime.now()
    occ = (
        await db_session.execute(
            select(ClassOccurrence).where(ClassOccurrence.id == classroom["occurrence_id"])
        )
    ).scalar_one()
    a_sess = AttendanceSession(
        occurrence_id=occ.id, lecturer_id=classroom["lecturer_id"],
        status="closed", opened_at=now, closed_at=now,
    )
    db_session.add(a_sess)
    await db_session.flush()
    db_session.add(AttendanceRecord(session_id=a_sess.id, student_id=s1, status="present"))
    quiz = Quiz(
        course_id=classroom["course_id"], title="Quiz 1",
        time_limit_minutes=30, opens_at=now, closes_at=now + timedelta(days=7),
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
        started_at=now - timedelta(minutes=5),
        deadline=now + timedelta(minutes=25), status="submitted", score=1.0,
    )
    db_session.add(attempt)
    await db_session.flush()
    db_session.add(QuizAnswer(
        attempt_id=attempt.id, question_id=mcq.id, answer="A", score=1.0, auto_graded=True,
    ))
    await db_session.commit()
    return s1, classroom["occurrence_id"], classroom["course_id"]


# ── HTTP endpoint ───────────────────────────────────────────────────────────

async def test_student_self_view_own_data(student_client, classroom, db_session):
    student_id, occurrence_id, course_id = await _setup(db_session, classroom)

    resp = await student_client.get("/student/me/analytics")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["student_id"] == student_id
    assert body["overall_attendance_rate"] is not None
    assert len(body["courses"]) == 1
    course = body["courses"][0]
    assert course["course_id"] == course_id
    assert course["attendance"]["rate"] is not None
    assert course["quizzes"]["scores"] == [1.0]
    assert course["quizzes"]["average_score"] == 1.0


async def test_student_self_view_no_data(student_client, classroom, db_session):
    """Student enrolled but with no attendance/quiz data."""
    s1 = classroom["student_ids"][1]
    db_session.add(Enrollment(student_id=s1, occurrence_id=classroom["occurrence_id"]))
    await db_session.commit()

    # Use a different client auth for the second student is complex; instead call the
    # service directly via the existing student_client's student. We just assert the
    # endpoint returns 200 with empty courses for an enrolled-but-inactive student.
    # Since student_client is fixed to student_ids[0], we test via service instead.
    from app.services.engagement_read import student_self_view
    result = await student_self_view(db_session, s1)
    assert result["student_id"] == s1
    assert result["overall_attendance_rate"] is None
    assert result["courses"] == []


async def test_student_cannot_read_another_student_via_lecturer_endpoint(
    student_client, classroom, db_session
):
    """A student calling a lecturer endpoint gets 403 (NFR-04)."""
    student_id, occurrence_id, course_id = await _setup(db_session, classroom)
    resp = await student_client.get(
        f"/lecturer/analytics/{occurrence_id}/students"
    )
    assert resp.status_code == 403, resp.text


async def test_student_self_view_enrolled_only(student_client, classroom, db_session):
    """Student only sees their own courses, not others'."""
    student_id, _, course_id = await _setup(db_session, classroom)
    resp = await student_client.get("/student/me/analytics")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert all(c["course_id"] == course_id for c in body["courses"])
