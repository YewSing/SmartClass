"""Characterisation: existing analytics endpoint (GET /lecturer/analytics).

Pins the current behaviour of `backend/app/routers/analytics.py` before S40 rebuilds it,
against unchanged code. Quirks pinned here:
- only `present` counts as attended (Late counts as absent);
- `unidentified` is treated as absent (defensive; the DB CHECK now excludes it, but the
  sums still list it);
- `GET /lecturer/analytics` has NO ownership check — any lecturer reads any class (NFR-04 hole).

No production code changes. At least 8 tests, all passing against unchanged code.
The two student endpoints (`GET /student/me/attendance[/summary]`) are dead code since T39
(the app uses T32's `GET /student/me/attendance/courses`); they are removed in S40, justified
by the `TEST-CHANGE:` line in PROGRESS-SHINO.md.
"""

from datetime import date, datetime, timedelta

import pytest

from app.models.attendance import AttendanceRecord
from app.models.interaction import InteractionSession
from app.models.interaction_question import InteractionQuestion
from app.models.quiz import Quiz, QuizQuestion
from app.models.quiz_attempt import QuizAttempt

pytestmark = pytest.mark.db


async def _open_session(client, occurrence_id: int) -> int:
    resp = await client.post("/lecturer/sessions", json={"occurrence_id": occurrence_id})
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


async def _close_session(client, session_id: int) -> None:
    resp = await client.put(f"/lecturer/sessions/{session_id}/close")
    assert resp.status_code == 200, resp.text


async def _add_record(db_session, session_id: int, student_id: int, status: str) -> int:
    rec = AttendanceRecord(session_id=session_id, student_id=student_id, status=status)
    db_session.add(rec)
    await db_session.commit()
    return rec.id


async def test_lecturer_analytics_unknown_occurrence_is_404(lecturer_client):
    resp = await lecturer_client.get("/lecturer/analytics", params={"occurrence_id": 999999})
    assert resp.status_code == 404


async def test_lecturer_analytics_empty_occurrence(lecturer_client, classroom):
    resp = await lecturer_client.get(
        "/lecturer/analytics", params={"occurrence_id": classroom["occurrence_id"]}
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["occurrence_id"] == classroom["occurrence_id"]
    assert body["class_code"] == "CS101"
    assert body["enrolled_count"] == 3
    assert body["sessions_held"] == 0
    assert body["avg_attendance_rate"] == 0.0
    assert body["sessions"] == []
    assert body["at_risk_students"] == []


async def test_lecturer_analytics_only_present_counts(lecturer_client, classroom, db_session):
    session_id = await _open_session(lecturer_client, classroom["occurrence_id"])
    # Records go in BEFORE close: closing auto-marks every unrecorded student Absent,
    # so a post-close insert would collide with the (session, student) unique key.
    await _add_record(db_session, session_id, classroom["student_ids"][0], "present")  # S0000001
    await _add_record(db_session, session_id, classroom["student_ids"][1], "late")     # S0000002
    await _add_record(db_session, session_id, classroom["student_ids"][2], "absent")   # S0000003
    await _close_session(lecturer_client, session_id)

    resp = await lecturer_client.get(
        "/lecturer/analytics", params={"occurrence_id": classroom["occurrence_id"]}
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["sessions_held"] == 1
    bar = body["sessions"][0]
    assert bar["label"] == "Week 1"
    assert bar["present_count"] == 2      # Late counts as attended (FR-308)
    assert bar["absent_count"] == 1
    assert bar["total"] == 3
    assert body["avg_attendance_rate"] == 66.7  # (100 + 100 + 0) / 3

    # At-risk: rate < 80. S0000001=100 (not at risk), S0000002=100, S0000003=0.
    at_risk = body["at_risk_students"]
    assert [s["student_id"] for s in at_risk] == [classroom["student_ids"][2]]
    assert at_risk[0]["rate"] == 0.0


async def test_lecturer_analytics_other_lecturer_is_403(
    other_lecturer_client, classroom, db_session
):
    # NFR-04 (S40): a lecturer who does not teach the class is rejected — on write and read.
    resp = await other_lecturer_client.post(
        "/lecturer/sessions", json={"occurrence_id": classroom["occurrence_id"]}
    )
    assert resp.status_code == 403

    resp = await other_lecturer_client.get(
        "/lecturer/analytics", params={"occurrence_id": classroom["occurrence_id"]}
    )
    assert resp.status_code == 403


async def test_lecturer_analytics_date_range_filters_sessions(
    lecturer_client, classroom, db_session
):
    for _ in range(2):
        session_id = await _open_session(lecturer_client, classroom["occurrence_id"])
        await _close_session(lecturer_client, session_id)

    all_sessions = await lecturer_client.get(
        "/lecturer/analytics", params={"occurrence_id": classroom["occurrence_id"]}
    )
    assert all_sessions.status_code == 200
    # Reopening the same class time range reuses one session record (one row per
    # occurrence + date), so two open/close cycles still count as one session.
    assert all_sessions.json()["sessions_held"] == 1

    # A from-date in the future excludes today's sessions.
    future = (date.today() + timedelta(days=30)).isoformat()
    resp = await lecturer_client.get(
        "/lecturer/analytics",
        params={"occurrence_id": classroom["occurrence_id"], "from_date": future},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["sessions_held"] == 0
    assert body["avg_attendance_rate"] == 0.0
    assert body["sessions"] == []


async def test_student_cannot_read_lecturer_analytics(student_client, classroom):
    resp = await student_client.get(
        "/lecturer/analytics", params={"occurrence_id": classroom["occurrence_id"]}
    )
    assert resp.status_code == 403


# ── Participation at-risk (FR-702): rate = sessions participated / sessions held ──

async def _open_interaction(client, occurrence_id: int) -> int:
    resp = await client.post("/lecturer/interactions", json={"occurrence_id": occurrence_id})
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


async def _participate(db_session, interaction_id: int, student_id: int) -> None:
    db_session.add(InteractionQuestion(interaction_id=interaction_id, student_id=student_id, text="q"))
    await db_session.commit()


async def test_lecturer_analytics_participation_at_risk(lecturer_client, classroom, db_session):
    iid1 = await _open_interaction(lecturer_client, classroom["occurrence_id"])
    # A second POST would reuse the open session row (S26 behaviour), so seed
    # the second session directly.
    iid2 = InteractionSession(
        occurrence_id=classroom["occurrence_id"], status="open", opened_by=classroom["lecturer_id"]
    )
    db_session.add(iid2)
    await db_session.commit()
    # Student 0 takes part in both sessions; students 1 and 2 in none.
    await _participate(db_session, iid1, classroom["student_ids"][0])
    await _participate(db_session, iid2.id, classroom["student_ids"][0])

    resp = await lecturer_client.get(
        "/lecturer/analytics", params={"occurrence_id": classroom["occurrence_id"]}
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["interaction_sessions_held"] == 2
    assert [b["participants"] for b in body["participation_bars"]] == [1, 1]

    # Rates: 100 / 0 / 0 → avg 33.3; students 1 and 2 are at risk (<80).
    assert body["avg_participation_rate"] == 33.3
    at_risk = body["participation_at_risk"]
    assert [s["student_id"] for s in at_risk] == [
        classroom["student_ids"][1],
        classroom["student_ids"][2],
    ]
    assert at_risk[0]["present"] == 0 and at_risk[0]["total"] == 2
    assert at_risk[0]["rate"] == 0.0


async def test_lecturer_analytics_participation_empty(lecturer_client, classroom):
    resp = await lecturer_client.get(
        "/lecturer/analytics", params={"occurrence_id": classroom["occurrence_id"]}
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["interaction_sessions_held"] == 0
    assert body["avg_participation_rate"] == 0.0
    assert body["participation_bars"] == []
    assert body["participation_at_risk"] == []


# ── Quiz trend + very-low-score flagging (FR-612/613) ──────────────────────

async def _seed_quiz(db_session, classroom, title: str, points: float) -> int:
    """One published quiz with a single question worth `points`; returns the quiz id."""
    quiz = Quiz(
        course_id=classroom["course_id"], title=title,
        time_limit_minutes=30, opens_at=datetime.now(),
        closes_at=datetime.now() + timedelta(days=7),
        status="published", created_by=classroom["lecturer_id"],
    )
    db_session.add(quiz)
    await db_session.flush()
    db_session.add(QuizQuestion(
        quiz_id=quiz.id, course_id=classroom["course_id"], type="mcq",
        question="Q?", correct_answer="A", level="beginner", topic="T", score=points,
    ))
    await db_session.commit()
    return quiz.id


async def _seed_attempt(db_session, quiz_id: int, student_id: int, score: float) -> None:
    db_session.add(QuizAttempt(
        quiz_id=quiz_id, student_id=student_id, status="submitted", score=score,
        started_at=datetime.now(), submitted_at=datetime.now(),
        deadline=datetime.now() + timedelta(days=7),
    ))
    await db_session.commit()


async def test_lecturer_analytics_quiz_trend_and_at_risk(
    lecturer_client, classroom, db_session
):
    q1 = await _seed_quiz(db_session, classroom, "Quiz 1", points=1.0)
    q2 = await _seed_quiz(db_session, classroom, "Quiz 2", points=2.0)
    s1, s2, s3 = classroom["student_ids"]
    # Percentages: s1 = 100 + 100, s2 = 50 + 25, s3 = 0 + 0 → averages 100 / 37.5 / 0.
    await _seed_attempt(db_session, q1, s1, 1.0)
    await _seed_attempt(db_session, q2, s1, 2.0)
    await _seed_attempt(db_session, q1, s2, 0.5)
    await _seed_attempt(db_session, q2, s2, 0.5)
    await _seed_attempt(db_session, q1, s3, 0.0)
    await _seed_attempt(db_session, q2, s3, 0.0)

    resp = await lecturer_client.get(
        "/lecturer/analytics", params={"occurrence_id": classroom["occurrence_id"]}
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["quiz_count"] == 2
    assert body["avg_quiz_score"] == round((100 + 37.5 + 0) / 3, 1)

    # Trend, oldest quiz first: class average per quiz.
    trend = body["quiz_trend"]
    assert [(t["quiz_id"]) for t in trend] == [q1, q2]
    assert trend[0]["average_score"] == round((100 + 50 + 0) / 3, 1)   # 50.0
    assert trend[1]["average_score"] == round((100 + 25 + 0) / 3, 1)   # 41.7
    assert all(t["attempts"] == 3 for t in trend)

    # Very low score (<50): s2 (37.5) and s3 (0), worst first. s1 (100) not flagged.
    at_risk = body["quiz_at_risk"]
    assert [r["student_id"] for r in at_risk] == [s3, s2]
    assert at_risk[0]["average_score"] == 0.0 and at_risk[0]["quiz_count"] == 2
    assert at_risk[1]["average_score"] == 37.5


async def test_lecturer_analytics_quiz_empty(lecturer_client, classroom):
    resp = await lecturer_client.get(
        "/lecturer/analytics", params={"occurrence_id": classroom["occurrence_id"]}
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["quiz_count"] == 0
    assert body["avg_quiz_score"] is None
    assert body["quiz_trend"] == []
    assert body["quiz_at_risk"] == []


# ── CSV export for Participation / Quiz / Students tabs ──────────────────────

@pytest.mark.db
async def test_export_csv_participation_section(lecturer_client, classroom):
    resp = await lecturer_client.get(
        f"/lecturer/analytics/{classroom['occurrence_id']}/export-csv",
        params={"section": "participation"},
    )
    assert resp.status_code == 200, resp.text
    assert "text/csv" in resp.headers["content-type"]
    assert "Distinct participants" in resp.text


@pytest.mark.db
async def test_export_csv_students_section(lecturer_client, classroom):
    resp = await lecturer_client.get(
        f"/lecturer/analytics/{classroom['occurrence_id']}/export-csv",
        params={"section": "students"},
    )
    assert resp.status_code == 200, resp.text
    assert "Matric No" in resp.text


@pytest.mark.db
async def test_export_csv_quiz_section(lecturer_client, classroom):
    resp = await lecturer_client.get(
        f"/lecturer/analytics/{classroom['occurrence_id']}/export-csv",
        params={"section": "quiz"},
    )
    assert resp.status_code == 200, resp.text
    assert "Graded attempts" in resp.text


@pytest.mark.db
async def test_export_csv_unknown_section_is_422(lecturer_client, classroom):
    resp = await lecturer_client.get(
        f"/lecturer/analytics/{classroom['occurrence_id']}/export-csv",
        params={"section": "bogus"},
    )
    assert resp.status_code == 422


@pytest.mark.db
async def test_export_csv_other_lecturer_is_403(
    lecturer_client, other_lecturer_client, classroom
):
    resp = await other_lecturer_client.get(
        f"/lecturer/analytics/{classroom['occurrence_id']}/export-csv",
        params={"section": "students"},
    )
    assert resp.status_code == 403
