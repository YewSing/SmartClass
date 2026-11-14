"""Tests for short-answer scoring + AI suggestion (FR-609, FR-610, FR-611, S33).

Mocks `llm.chat_json` so no real LLM is needed. Covers: lecturer lists unscored short
answers, scores a short answer, result gated on grading complete (student can't see before
completion), AI suggest-score (and 502 on malformed output), and NFR-04 access control.
No schema change: reuses `quiz_answers.score` (S32).
"""

from datetime import datetime, timedelta

import pytest
from sqlalchemy import select

from app.models.class_ import Enrollment
from app.models.quiz import Quiz, QuizQuestion
from app.models.quiz_attempt import QuizAttempt, QuizAnswer
from app.services.kb.llm import LLMMalformedOutput

pytestmark = pytest.mark.db


async def _setup(db_session, classroom):
    """Enrolled student, published quiz with one short-answer question, submitted attempt
    with one unscored short answer. Returns (student_id, quiz_id, attempt_id, answer_id)."""
    student_id = classroom["student_ids"][0]
    db_session.add(Enrollment(student_id=student_id, occurrence_id=classroom["occurrence_id"]))
    quiz = Quiz(
        course_id=classroom["course_id"], title="Sample Quiz",
        time_limit_minutes=30, opens_at=datetime.now(),
        closes_at=datetime.now() + timedelta(days=7),
        status="published", created_by=classroom["lecturer_id"],
    )
    db_session.add(quiz)
    await db_session.flush()
    sa = QuizQuestion(
        quiz_id=quiz.id, course_id=classroom["course_id"], type="short_answer",
        question="Explain gravity.", suggested_answer="mass attraction",
        level="beginner", topic="physics", status="approved",
    )
    db_session.add(sa)
    await db_session.flush()
    attempt = QuizAttempt(
        quiz_id=quiz.id, student_id=student_id,
        started_at=datetime.now() - timedelta(minutes=5),
        deadline=datetime.now() + timedelta(minutes=25),
        status="submitted", score=None,
    )
    db_session.add(attempt)
    await db_session.flush()
    answer = QuizAnswer(
        attempt_id=attempt.id, question_id=sa.id, answer="gravity pulls",
        score=None, auto_graded=False,
    )
    db_session.add(answer)
    await db_session.commit()
    return student_id, quiz.id, attempt.id, answer.id


async def _fake_suggest(messages, *, max_tokens=None, temperature=0.2, retries=1, validator=None):
    from app.schemas.quiz import SuggestScoreOut
    return SuggestScoreOut(suggested_score=75.0, reasoning="covers the key idea")


async def _raise_suggest(messages, *, max_tokens=None, temperature=0.2, retries=1, validator=None):
    raise LLMMalformedOutput("bad json")


# ── lecturer: list / score unscored short answers ───────────────────────────

async def test_lecturer_lists_unscored_short_answers(lecturer_client, classroom, db_session):
    _, _, attempt_id, answer_id = await _setup(db_session, classroom)

    resp = await lecturer_client.get(
        f"/lecturer/quizzes/attempts/{attempt_id}/answers"
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert len(body) == 1
    assert body[0]["answer_id"] == answer_id
    assert body[0]["score"] is None


async def test_lecturer_scores_short_answer(lecturer_client, classroom, db_session):
    _, _, attempt_id, answer_id = await _setup(db_session, classroom)

    resp = await lecturer_client.post(
        f"/lecturer/quizzes/attempts/{attempt_id}/answers/{answer_id}/score",
        json={"score": 80.0},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["score"] == 80.0

    result = await db_session.execute(select(QuizAnswer).where(QuizAnswer.id == answer_id))
    assert result.scalar_one().score == 80.0


async def test_score_non_short_answer_is_400(lecturer_client, classroom, db_session):
    _, quiz_id, attempt_id, _ = await _setup(db_session, classroom)
    mcq = QuizQuestion(
        quiz_id=quiz_id, course_id=classroom["course_id"], type="mcq",
        question="Capital?", options=["A", "B"], correct_answer="A",
        level="beginner", topic="geo", status="approved",
    )
    db_session.add(mcq)
    await db_session.flush()
    mcq_answer = QuizAnswer(attempt_id=attempt_id, question_id=mcq.id, answer="A",
                            score=1.0, auto_graded=True)
    db_session.add(mcq_answer)
    await db_session.commit()

    resp = await lecturer_client.post(
        f"/lecturer/quizzes/attempts/{attempt_id}/answers/{mcq_answer.id}/score",
        json={"score": 50.0},
    )
    assert resp.status_code == 400, resp.text


async def test_score_other_lecturer_is_403(other_lecturer_client, classroom, db_session):
    _, _, attempt_id, answer_id = await _setup(db_session, classroom)
    resp = await other_lecturer_client.post(
        f"/lecturer/quizzes/attempts/{attempt_id}/answers/{answer_id}/score",
        json={"score": 80.0},
    )
    assert resp.status_code == 403, resp.text


# ── student result gating (FR-611) ──────────────────────────────────────────

async def test_student_result_before_complete_is_hidden(
    student_client, classroom, db_session
):
    _, _, attempt_id, _ = await _setup(db_session, classroom)

    resp = await student_client.get(f"/student/quizzes/attempts/{attempt_id}/result")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["grading_complete"] is False
    assert body["student_score_visible"] is False
    assert body["score"] is None
    for a in body["answers"]:
        assert a["score"] is None  # short answer hidden before completion


async def test_student_result_after_complete_is_visible(
    lecturer_client, student_client, classroom, db_session
):
    _, _, attempt_id, answer_id = await _setup(db_session, classroom)

    await lecturer_client.post(
        f"/lecturer/quizzes/attempts/{attempt_id}/answers/{answer_id}/score",
        json={"score": 80.0},
    )

    resp = await student_client.get(f"/student/quizzes/attempts/{attempt_id}/result")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["grading_complete"] is True
    assert body["student_score_visible"] is True
    assert body["score"] == 80.0
    a = body["answers"][0]
    assert a["score"] == 80.0
    assert a["suggested_answer"] == "mass attraction"


async def test_student_not_own_attempt_is_403(student_client, classroom, db_session):
    _, _, attempt_id, _ = await _setup(db_session, classroom)
    resp = await student_client.get(f"/student/quizzes/attempts/{attempt_id}/result")
    assert resp.status_code == 403, resp.text


# ── AI suggest-score (FR-610) ───────────────────────────────────────────────

async def test_suggest_score(lecturer_client, classroom, db_session, monkeypatch):
    monkeypatch.setattr("app.services.quiz_grading.llm.chat_json", _fake_suggest)
    _, _, attempt_id, answer_id = await _setup(db_session, classroom)

    resp = await lecturer_client.post(
        f"/lecturer/quizzes/attempts/{attempt_id}/answers/{answer_id}/suggest-score",
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["suggested_score"] == 75.0
    assert body["reasoning"] == "covers the key idea"


async def test_suggest_score_malformed_is_502(
    lecturer_client, classroom, db_session, monkeypatch
):
    monkeypatch.setattr("app.services.quiz_grading.llm.chat_json", _raise_suggest)
    _, _, attempt_id, answer_id = await _setup(db_session, classroom)

    resp = await lecturer_client.post(
        f"/lecturer/quizzes/attempts/{attempt_id}/answers/{answer_id}/suggest-score",
    )
    assert resp.status_code == 502, resp.text


async def test_suggest_score_other_lecturer_is_403(
    other_lecturer_client, classroom, db_session, monkeypatch
):
    monkeypatch.setattr("app.services.quiz_grading.llm.chat_json", _fake_suggest)
    _, _, attempt_id, answer_id = await _setup(db_session, classroom)
    resp = await other_lecturer_client.post(
        f"/lecturer/quizzes/attempts/{attempt_id}/answers/{answer_id}/suggest-score",
    )
    assert resp.status_code == 403, resp.text
