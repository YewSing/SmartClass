"""Characterisation: session roster, manual overrides (+ audit log) and CSV exports."""
import csv
import io
import json
from datetime import date, timedelta

import pytest
from sqlalchemy import select

from app.models.attendance import AttendanceRecord
from app.models.audit import AuditLog

pytestmark = pytest.mark.db


async def _open_session(c, classroom) -> int:
    resp = await c.post("/lecturer/sessions", json={"occurrence_id": classroom["occurrence_id"]})
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


async def _add_record(db, session_id, student_id, status) -> int:
    rec = AttendanceRecord(session_id=session_id, student_id=student_id, status=status)
    db.add(rec)
    await db.commit()
    return rec.id


def _csv_rows(resp) -> list[list[str]]:
    return list(csv.reader(io.StringIO(resp.text)))


async def test_roster_lists_enrolled_students_with_status(lecturer_client, classroom, db_session):
    session_id = await _open_session(lecturer_client, classroom)
    await _add_record(db_session, session_id, classroom["student_ids"][1], "present")

    resp = await lecturer_client.get(f"/lecturer/sessions/{session_id}/attendance")
    assert resp.status_code == 200, resp.text
    roster = resp.json()
    assert [r["matric_no"] for r in roster] == ["S0000001", "S0000002", "S0000003"]
    assert [r["status"] for r in roster] == ["not_recorded", "present", "not_recorded"]
    assert roster[0]["record_id"] is None
    assert roster[1]["record_id"] is not None
    assert not any(r["overridden"] for r in roster)


async def test_roster_unknown_session_is_404(lecturer_client, classroom):
    assert (await lecturer_client.get("/lecturer/sessions/999999/attendance")).status_code == 404


async def test_override_record_updates_status_and_writes_audit(
    lecturer_client, users, classroom, db_session
):
    session_id = await _open_session(lecturer_client, classroom)
    record_id = await _add_record(db_session, session_id, classroom["student_ids"][0], "absent")

    resp = await lecturer_client.put(f"/attendance/{record_id}/override", json={"status": "present"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "present"
    assert body["overridden"] is True

    db_session.expire_all()
    rec = await db_session.get(AttendanceRecord, record_id)
    assert rec.status == "present"
    assert rec.override_by == users["lecturer"].id
    assert rec.override_at is not None

    log = (await db_session.execute(select(AuditLog).where(AuditLog.action == "ATTENDANCE_OVERRIDE"))).scalar_one()
    assert log.action == "ATTENDANCE_OVERRIDE"
    assert log.actor_id == users["lecturer"].id
    assert (log.target_type, log.target_id) == ("attendance_record", str(record_id))
    assert json.loads(log.old_val) == {"status": "absent"}
    assert json.loads(log.new_val) == {"status": "present"}


async def test_override_rejects_other_statuses(lecturer_client, classroom, db_session):
    session_id = await _open_session(lecturer_client, classroom)
    record_id = await _add_record(db_session, session_id, classroom["student_ids"][0], "absent")
    resp = await lecturer_client.put(f"/attendance/{record_id}/override", json={"status": "late"})
    assert resp.status_code == 400
    assert (await lecturer_client.put("/attendance/999999/override", json={"status": "present"})).status_code == 404


async def test_student_cannot_override(student_client, lecturer_client, classroom, db_session):
    session_id = await _open_session(lecturer_client, classroom)
    record_id = await _add_record(db_session, session_id, classroom["student_ids"][0], "absent")
    resp = await student_client.put(f"/attendance/{record_id}/override", json={"status": "present"})
    assert resp.status_code == 403


async def test_session_override_creates_missing_record(lecturer_client, classroom, db_session):
    session_id = await _open_session(lecturer_client, classroom)
    student_id = classroom["student_ids"][2]

    resp = await lecturer_client.put(
        f"/lecturer/sessions/{session_id}/attendance/override",
        json={"student_id": student_id, "status": "present"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["record_id"] is not None
    assert resp.json()["overridden"] is True

    rec = (await db_session.execute(select(AttendanceRecord).where(
        AttendanceRecord.session_id == session_id, AttendanceRecord.student_id == student_id
    ))).scalar_one()
    assert rec.status == "present"

    log = (await db_session.execute(select(AuditLog).where(AuditLog.action == "ATTENDANCE_OVERRIDE"))).scalar_one()
    assert json.loads(log.old_val) == {"status": "not_recorded"}

    resp = await lecturer_client.put(
        f"/lecturer/sessions/{session_id}/attendance/override",
        json={"student_id": 999_999, "status": "present"},
    )
    assert resp.status_code == 404


async def test_session_csv_export(lecturer_client, classroom, db_session):
    session_id = await _open_session(lecturer_client, classroom)
    await _add_record(db_session, session_id, classroom["student_ids"][0], "present")
    await lecturer_client.put(
        f"/lecturer/sessions/{session_id}/attendance/override",
        json={"student_id": classroom["student_ids"][1], "status": "present"},
    )

    resp = await lecturer_client.get(f"/lecturer/sessions/{session_id}/export")
    assert resp.status_code == 200, resp.text
    assert resp.headers["content-type"].startswith("text/csv")
    assert "attachment; filename=attendance_CS101_" in resp.headers["content-disposition"]
    rows = _csv_rows(resp)
    assert rows[0] == ["Matric No", "Name", "Status", "Detected At", "Overridden"]
    assert [(r[0], r[1], r[2], r[4]) for r in rows[1:]] == [
        ("S0000001", "Test Student", "present", "No"),
        ("S0000002", "Student 2", "present", "Yes"),
        ("S0000003", "Student 3", "absent", "No"),  # no record yet → exported as absent
    ]


async def test_occurrence_csv_export_with_date_range(lecturer_client, classroom, db_session):
    first = await _open_session(lecturer_client, classroom)
    await _add_record(db_session, first, classroom["student_ids"][0], "present")
    await lecturer_client.put(f"/lecturer/sessions/{first}/close")
    second = await _open_session(lecturer_client, classroom)
    await _add_record(db_session, second, classroom["student_ids"][0], "present")
    await _add_record(db_session, second, classroom["student_ids"][1], "present")
    await lecturer_client.put(f"/lecturer/sessions/{second}/close")
    await _open_session(lecturer_client, classroom)  # open sessions are not exported

    url = f"/lecturer/occurrences/{classroom['occurrence_id']}/attendance/export"
    resp = await lecturer_client.get(url)
    assert resp.status_code == 200, resp.text
    assert "attendance_report_CS101_" in resp.headers["content-disposition"]
    rows = _csv_rows(resp)
    assert rows[0][:2] == ["Matric No", "Name"] and rows[0][-2:] == ["Total", "Rate"]
    assert len(rows[0]) == 2 + 2 + 2  # two closed sessions
    assert rows[1][2:] == ["P", "P", "2/2", "100.0%"]
    assert rows[2][2:] == ["A", "P", "1/2", "50.0%"]
    assert rows[3][2:] == ["A", "A", "0/2", "0.0%"]

    # A date range that excludes today leaves only the header + students with 0 sessions.
    future = (date.today() + timedelta(days=30)).isoformat()
    rows = _csv_rows(await lecturer_client.get(url, params={"from_date": future}))
    assert rows[0] == ["Matric No", "Name", "Total", "Rate"]
    assert rows[1][2:] == ["0/0", "0.0%"]

    assert (await lecturer_client.get("/lecturer/occurrences/999999/attendance/export")).status_code == 404
