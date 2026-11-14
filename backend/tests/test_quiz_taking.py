"""Tests for taking quizzes + auto-grade (FR-606, FR-607, FR-608, S32).

Covers: published-quiz list for enrolled courses, one attempt per quiz, open-window
enforcement, MCQ auto-grade on submission, short answers left unscored, expiry rejection,
and the background auto-submit of expired attempts.
"""

from datetime import datetime, timedelta

import pytest
from sqlalchemy import select

from app.models.quiz import Quiz, QuizQuestion
from app.models.quiz_attempt import QuizAnswer, QuizAttempt
from app.services.quiz_taking import auto_submit_expired_attempts

pytestmark = pytest.mark.db


def _naive(dt) -> datetime:
    return dt.replace(tzinfo=None) if getattr(dt, "tzinfo", None) else dt


async def _setup_published_quiz(db_session, classroom, time_limit_minutes=30,
                                closes_in_future=True):
    """Insert an enrolled student, a published quiz with one MCQ (correct="A") and one
    short-answer question. Returns (student_id, quiz_id, mcq_id, sa_id)."""
    student_id = classroom["student_ids"][0]
    closes_at = (datetime.now() + timedelta(days=7)) if closes_in_future else (datetime.now() - timedelta(days=1))
    quiz = Quiz(
        course_id=classroom["course_id"], title="Sample Quiz",
        time_limit_minutes=time_limit_minutes,
        opens_at=datetime.now(), closes_at=closes_at,
        status="published", created_by=classroom["lecturer_id"],
    )
    db_session.add(quiz)
    await db_session.flush()
    mcq = QuizQuestion(
        quiz_id=quiz.id, course_id=classroom["course_id"], type="mcq",
        question="Capital of France?", options=["A", "B", "C", "D"],
        correct_answer="A", level="beginner", topic="geo", status="approved",
    )
    sa = QuizQuestion(
        quiz_id=quiz.id, course_id=classroom["course_id"], type="short_answer",
        question="Explain gravity.", suggested_answer="mass attraction", level="beginner",
        topic="physics", status="approved",
    )
    db_session.add_all([mcq, sa])
    await db_session.commit()
    return student_id, quiz.id, mcq.id, sa.id


async def _start_attempt(student_client, quiz_id):
    resp = await student_client.post(f"/student/quizzes/{quiz_id}/attempt")
    assert resp.status_code == 201, resp.text
    return resp.json()["attempt_id"]


# ── list ────────────────────────────────────────────────────────────────────

async def test_list_student_quizzes_shows_enrolled_published(student_client, classroom, db_session):
    student_id, quiz_id, _, _ = await _setup_published_quiz(db_session, classroom)

    resp = await student_client.get("/student/quizzes")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert any(q["id"] == quiz_id and q["status"] == "published" for q in body)
    entry = [q for q in body if q["id"] == quiz_id][0]
    assert entry["has_attempt"] is False


async def test_list_student_quizzes_unpublished_not_visible(student_client, classroom, db_session):
    student_id, quiz_id, _, _ = await _setup_published_quiz(db_session, classroom)
    quiz = (await db_session.execute(select(Quiz).where(Quiz.id == quiz_id))).scalar_one()
    quiz.status = "draft"
    await db_session.commit()

    resp = await student_client.get("/student/quizzes")
    assert resp.status_code == 200, resp.text
    assert all(q["id"] != quiz_id for q in resp.json())


# ── start attempt ───────────────────────────────────────────────────────────

async def test_start_attempt(student_client, classroom, db_session):
    _, quiz_id, _, _ = await _setup_published_quiz(db_session, classroom)

    resp = await student_client.post(f"/student/quizzes/{quiz_id}/attempt")
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["attempt_id"] is not None
    assert body["deadline"] is not None


async def test_start_attempt_second_is_409(student_client, classroom, db_session):
    _, quiz_id, _, _ = await _setup_published_quiz(db_session, classroom)
    await _start_attempt(student_client, quiz_id)

    resp = await student_client.post(f"/student/quizzes/{quiz_id}/attempt")
    assert resp.status_code == 409, resp.text


async def test_start_attempt_closed_quiz_is_403(student_client, classroom, db_session):
    _, quiz_id, _, _ = await _setup_published_quiz(db_session, classroom, closes_in_future=False)
    resp = await student_client.post(f"/student/quizzes/{quiz_id}/attempt")
    assert resp.status_code == 403, resp.text


async def test_start_attempt_unpublished_is_404(student_client, classroom, db_session):
    _, quiz_id, _, _ = await _setup_published_quiz(db_session, classroom)
    quiz = (await db_session.execute(select(Quiz).where(Quiz.id == quiz_id))).scalar_one()
    quiz.status = "draft"
    await db_session.commit()

    resp = await student_client.post(f"/student/quizzes/{quiz_id}/attempt")
    assert resp.status_code == 404, resp.text


# ── submit ──────────────────────────────────────────────────────────────────

async def test_submit_mcq_auto_grade(student_client, classroom, db_session):
    student_id, quiz_id, mcq_id, sa_id = await _setup_published_quiz(db_session, classroom)
    attempt_id = await _start_attempt(student_client, quiz_id)

    resp = await student_client.post(
        f"/student/quizzes/attempts/{attempt_id}/submit",
        json={"answers": [
            {"question_id": mcq_id, "answer": "A"},
            {"question_id": sa_id, "answer": "gravity pulls"},
        ]},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "submitted"
    assert body["score"] == 1.0
    mcq = [a for a in body["answers"] if a["question_id"] == mcq_id][0]
    assert mcq["auto_graded"] is True and mcq["score"] == 1.0
    sa = [a for a in body["answers"] if a["question_id"] == sa_id][0]
    assert sa["auto_graded"] is False and sa["score"] is None

    result = await db_session.execute(select(QuizAttempt).where(QuizAttempt.id == attempt_id))
    attempt = result.scalar_one()
    assert attempt.status == "submitted"
    assert attempt.submitted_at is not None


async def test_submit_wrong_mcq_is_zero(student_client, classroom, db_session):
    _, quiz_id, mcq_id, _ = await _setup_published_quiz(db_session, classroom)
    attempt_id = await _start_attempt(student_client, quiz_id)

    resp = await student_client.post(
        f"/student/quizzes/attempts/{attempt_id}/submit",
        json={"answers": [{"question_id": mcq_id, "answer": "B"}]},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["score"] == 0.0


async def test_submit_after_expiry_is_403(student_client, classroom, db_session):
    _, quiz_id, _, _ = await _setup_published_quiz(db_session, classroom)
    attempt_id = await _start_attempt(student_client, quiz_id)
    # move the deadline to the past
    attempt = (await db_session.execute(select(QuizAttempt).where(QuizAttempt.id == attempt_id))).scalar_one()
    attempt.deadline = datetime.now() - timedelta(minutes=5)
    await db_session.commit()

    resp = await student_client.post(
        f"/student/quizzes/attempts/{attempt_id}/submit",
        json={"answers": []},
    )
    assert resp.status_code == 403, resp.text


async def test_submit_already_submitted_is_409(student_client, classroom, db_session):
    _, quiz_id, mcq_id, _ = await _setup_published_quiz(db_session, classroom)
    attempt_id = await _start_attempt(student_client, quiz_id)
    await student_client.post(
        f"/student/quizzes/attempts/{attempt_id}/submit",
        json={"answers": [{"question_id": mcq_id, "answer": "A"}]},
    )
    resp = await student_client.post(
        f"/student/quizzes/attempts/{attempt_id}/submit",
        json={"answers": [{"question_id": mcq_id, "answer": "A"}]},
    )
    assert resp.status_code == 409, resp.text


# ── background auto-submit ──────────────────────────────────────────────────

async def test_auto_submit_expired_attempts(db_session, classroom):
    student_id, quiz_id, mcq_id, _ = await _setup_published_quiz(db_session, classroom)
    attempt = QuizAttempt(
        quiz_id=quiz_id, student_id=student_id,
        started_at=datetime.now() - timedelta(hours=2),
        deadline=datetime.now() - timedelta(minutes=5),
        status="started",
    )
    db_session.add(attempt)
    await db_session.flush()
    db_session.add(QuizAnswer(
        attempt_id=attempt.id, question_id=mcq_id, answer="A", score=1.0, auto_graded=True,
    ))
    await db_session.commit()

    count = await auto_submit_expired_attempts(db_session)
    assert count == 1

    result = await db_session.execute(select(QuizAttempt).where(QuizAttempt.id == attempt.id))
    attempt = result.scalar_one()
    assert attempt.status == "auto_submitted"
    assert attempt.auto_submitted is True
    assert attempt.score == 1.0
    assert attempt.submitted_at is not None
