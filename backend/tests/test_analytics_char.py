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

from datetime import date, timedelta

import pytest

from app.models.attendance import AttendanceRecord

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
    await _close_session(lecturer_client, session_id)
    await _add_record(db_session, session_id, classroom["student_ids"][0], "present")  # S0000001
    await _add_record(db_session, session_id, classroom["student_ids"][1], "late")     # S0000002
    await _add_record(db_session, session_id, classroom["student_ids"][2], "absent")   # S0000003

    resp = await lecturer_client.get(
        "/lecturer/analytics", params={"occurrence_id": classroom["occurrence_id"]}
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["sessions_held"] == 1
    bar = body["sessions"][0]
    assert bar["label"] == "Week 1"
    assert bar["present_count"] == 1      # only present
    assert bar["absent_count"] == 1       # late is NOT counted as absent here
    assert bar["total"] == 2              # late excluded from total
    assert body["avg_attendance_rate"] == 33.3  # 1 / (1 * 3) * 100

    # At-risk: rate < 80. S0000001=100 (not at risk), S0000002=0, S0000003=0.
    at_risk = body["at_risk_students"]
    assert [s["student_id"] for s in at_risk] == [
        classroom["student_ids"][1],
        classroom["student_ids"][2],
    ]
    assert at_risk[0]["rate"] == 0.0 and at_risk[1]["rate"] == 0.0


async def test_lecturer_analytics_any_lecturer_reads_any_class(
    other_lecturer_client, classroom, db_session
):
    # NFR-04 hole: no ensure_teaches_occurrence check, so another lecturer gets 200.
    session_id = await _open_session(other_lecturer_client, classroom["occurrence_id"])
    await _close_session(other_lecturer_client, session_id)
    await _add_record(db_session, session_id, classroom["student_ids"][0], "present")

    resp = await other_lecturer_client.get(
        "/lecturer/analytics", params={"occurrence_id": classroom["occurrence_id"]}
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["enrolled_count"] == 3


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
    assert all_sessions.json()["sessions_held"] == 2

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
