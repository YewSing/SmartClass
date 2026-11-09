"""Characterisation: attendance session open/close and lecturer session list."""
import pytest
from sqlalchemy import select

from app.models.attendance import AttendanceRecord

pytestmark = pytest.mark.db


async def _open(c, occurrence_id):
    return await c.post("/lecturer/sessions", json={"occurrence_id": occurrence_id})


async def test_open_session(lecturer_client, classroom):
    resp = await _open(lecturer_client, classroom["occurrence_id"])
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["status"] == "open"
    assert body["occurrence_id"] == body["class_id"] == classroom["occurrence_id"]
    assert body["class_code"] == "CS101"
    assert body["class_name"] == "Intro to Testing"
    assert body["lecturer_id"] == classroom["lecturer_id"]
    assert body["closed_at"] is None
    assert (body["present"], body["absent"], body["unid"]) == (0, 3, 0)


async def test_open_twice_conflicts(lecturer_client, classroom):
    assert (await _open(lecturer_client, classroom["occurrence_id"])).status_code == 201
    assert (await _open(lecturer_client, classroom["occurrence_id"])).status_code == 409


async def test_open_unknown_occurrence_is_404(lecturer_client, classroom):
    assert (await _open(lecturer_client, 999_999)).status_code == 404


async def test_student_cannot_open_session(student_client, classroom):
    assert (await _open(student_client, classroom["occurrence_id"])).status_code == 403


async def test_close_marks_unrecorded_students_absent(lecturer_client, classroom, db_session):
    session_id = (await _open(lecturer_client, classroom["occurrence_id"])).json()["id"]
    present_student = classroom["student_ids"][0]
    resp = await lecturer_client.put(
        f"/lecturer/sessions/{session_id}/attendance/override",
        json={"student_id": present_student, "status": "present"},
    )
    assert resp.status_code == 200, resp.text

    resp = await lecturer_client.put(f"/lecturer/sessions/{session_id}/close")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "closed"
    assert body["closed_at"] is not None
    assert (body["present"], body["absent"]) == (1, 2)

    records = (await db_session.execute(
        select(AttendanceRecord).where(AttendanceRecord.session_id == session_id)
    )).scalars().all()
    by_student = {r.student_id: r.status for r in records}
    assert by_student == {
        classroom["student_ids"][0]: "present",
        classroom["student_ids"][1]: "absent",
        classroom["student_ids"][2]: "absent",
    }


async def test_close_twice_conflicts_and_unknown_is_404(lecturer_client, classroom):
    session_id = (await _open(lecturer_client, classroom["occurrence_id"])).json()["id"]
    assert (await lecturer_client.put(f"/lecturer/sessions/{session_id}/close")).status_code == 200
    assert (await lecturer_client.put(f"/lecturer/sessions/{session_id}/close")).status_code == 409
    assert (await lecturer_client.put("/lecturer/sessions/999999/close")).status_code == 404


async def test_closed_occurrence_can_be_reopened(lecturer_client, classroom):
    first = (await _open(lecturer_client, classroom["occurrence_id"])).json()["id"]
    await lecturer_client.put(f"/lecturer/sessions/{first}/close")
    resp = await _open(lecturer_client, classroom["occurrence_id"])
    assert resp.status_code == 201
    assert resp.json()["id"] != first


async def test_lecturer_list_shows_only_own_sessions(
    lecturer_client, other_lecturer_client, admin_client, classroom
):
    mine = (await _open(lecturer_client, classroom["occurrence_id"])).json()["id"]
    theirs = (await _open(other_lecturer_client, classroom["other_occurrence_id"])).json()["id"]

    own = await lecturer_client.get("/lecturer/sessions")
    assert own.status_code == 200
    assert [s["id"] for s in own.json()] == [mine]

    # Admin sees every session.
    all_ids = {s["id"] for s in (await admin_client.get("/lecturer/sessions")).json()}
    assert all_ids == {mine, theirs}
