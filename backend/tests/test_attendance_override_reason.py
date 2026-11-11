"""FR-305 / NFR-06: every attendance override needs a reason and is fully audited."""
import json

import pytest
from sqlalchemy import func, select

from app.models.attendance import AttendanceRecord
from app.models.audit import AuditLog

pytestmark = pytest.mark.db

OVERRIDE = "ATTENDANCE_OVERRIDE"

BAD_REASON_BODIES = [
    {"status": "present"},                        # missing
    {"status": "present", "reason": ""},          # empty
    {"status": "present", "reason": "   "},       # whitespace-only
    {"status": "present", "reason": "x" * 501},   # too long
]


async def _open_session(c, classroom) -> int:
    resp = await c.post("/lecturer/sessions", json={"occurrence_id": classroom["occurrence_id"]})
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


async def _add_record(db, session_id, student_id, status) -> int:
    rec = AttendanceRecord(session_id=session_id, student_id=student_id, status=status)
    db.add(rec)
    await db.commit()
    return rec.id


async def _override_logs(db) -> list[AuditLog]:
    result = await db.execute(
        select(AuditLog).where(AuditLog.action == OVERRIDE).order_by(AuditLog.id)
    )
    return list(result.scalars().all())


async def _override_log_count(db) -> int:
    return await db.scalar(
        select(func.count()).select_from(AuditLog).where(AuditLog.action == OVERRIDE)
    )


@pytest.mark.parametrize("body", BAD_REASON_BODIES)
async def test_record_override_requires_reason(lecturer_client, classroom, db_session, body):
    session_id = await _open_session(lecturer_client, classroom)
    record_id = await _add_record(db_session, session_id, classroom["student_ids"][0], "absent")

    resp = await lecturer_client.put(f"/attendance/{record_id}/override", json=body)
    assert resp.status_code == 422, resp.text

    db_session.expire_all()
    rec = await db_session.get(AttendanceRecord, record_id)
    assert rec.status == "absent"
    assert rec.override_by is None
    assert await _override_log_count(db_session) == 0


@pytest.mark.parametrize("body", BAD_REASON_BODIES)
async def test_session_override_requires_reason(lecturer_client, classroom, db_session, body):
    session_id = await _open_session(lecturer_client, classroom)
    student_id = classroom["student_ids"][2]

    resp = await lecturer_client.put(
        f"/lecturer/sessions/{session_id}/attendance/override",
        json={"student_id": student_id, **body},
    )
    assert resp.status_code == 422, resp.text

    db_session.expire_all()
    record_count = await db_session.scalar(
        select(func.count()).select_from(AttendanceRecord).where(
            AttendanceRecord.session_id == session_id,
            AttendanceRecord.student_id == student_id,
        )
    )
    assert record_count == 0
    assert await _override_log_count(db_session) == 0


async def test_record_override_audits_actor_old_new_reason_time(
    lecturer_client, users, classroom, db_session
):
    session_id = await _open_session(lecturer_client, classroom)
    record_id = await _add_record(db_session, session_id, classroom["student_ids"][0], "absent")

    resp = await lecturer_client.put(
        f"/attendance/{record_id}/override",
        json={"status": "excused", "reason": "  Medical certificate  "},
    )
    assert resp.status_code == 200, resp.text

    logs = await _override_logs(db_session)
    assert len(logs) == 1
    log = logs[0]
    assert log.actor_id == users["lecturer"].id
    assert log.target_type == "attendance_record"
    assert log.target_id == str(record_id)
    assert json.loads(log.old_val) == {"status": "absent"}
    assert json.loads(log.new_val) == {"status": "excused", "reason": "Medical certificate"}
    assert log.ts is not None

    db_session.expire_all()
    rec = await db_session.get(AttendanceRecord, record_id)
    assert rec.status == "excused"
    assert rec.override_by == users["lecturer"].id
    assert rec.override_at is not None


async def test_session_override_audits_reason_for_new_record(
    lecturer_client, users, classroom, db_session
):
    session_id = await _open_session(lecturer_client, classroom)
    student_id = classroom["student_ids"][2]

    resp = await lecturer_client.put(
        f"/lecturer/sessions/{session_id}/attendance/override",
        json={"student_id": student_id, "status": "late", "reason": "Arrived after camera closed"},
    )
    assert resp.status_code == 200, resp.text

    logs = await _override_logs(db_session)
    assert len(logs) == 1
    log = logs[0]
    assert log.actor_id == users["lecturer"].id
    assert json.loads(log.old_val) == {"status": "not_recorded"}
    assert json.loads(log.new_val) == {
        "status": "late", "reason": "Arrived after camera closed",
    }
    assert log.ts is not None


async def test_each_override_writes_its_own_audit_row(lecturer_client, classroom, db_session):
    session_id = await _open_session(lecturer_client, classroom)
    record_id = await _add_record(db_session, session_id, classroom["student_ids"][0], "absent")

    first = await lecturer_client.put(
        f"/attendance/{record_id}/override",
        json={"status": "present", "reason": "reason A"},
    )
    assert first.status_code == 200, first.text
    second = await lecturer_client.put(
        f"/attendance/{record_id}/override",
        json={"status": "excused", "reason": "reason B"},
    )
    assert second.status_code == 200, second.text

    logs = await _override_logs(db_session)
    assert len(logs) == 2
    assert [json.loads(log.old_val) for log in logs] == [
        {"status": "absent"}, {"status": "present"},
    ]
    assert [json.loads(log.new_val) for log in logs] == [
        {"status": "present", "reason": "reason A"},
        {"status": "excused", "reason": "reason B"},
    ]


async def test_bad_status_with_reason_is_still_400(lecturer_client, classroom, db_session):
    session_id = await _open_session(lecturer_client, classroom)
    record_id = await _add_record(db_session, session_id, classroom["student_ids"][0], "absent")

    resp = await lecturer_client.put(
        f"/attendance/{record_id}/override",
        json={"status": "unidentified", "reason": "r"},
    )
    assert resp.status_code == 400, resp.text

    resp = await lecturer_client.put(
        f"/lecturer/sessions/{session_id}/attendance/override",
        json={"student_id": classroom["student_ids"][2], "status": "unidentified", "reason": "r"},
    )
    assert resp.status_code == 400, resp.text

    db_session.expire_all()
    assert (await db_session.get(AttendanceRecord, record_id)).status == "absent"
    assert await _override_log_count(db_session) == 0


async def test_audit_log_has_no_edit_or_delete_endpoint(
    lecturer_client, admin_client, classroom, db_session
):
    session_id = await _open_session(lecturer_client, classroom)
    record_id = await _add_record(db_session, session_id, classroom["student_ids"][0], "absent")
    resp = await lecturer_client.put(
        f"/attendance/{record_id}/override",
        json={"status": "present", "reason": "Seen in class"},
    )
    assert resp.status_code == 200, resp.text

    [log] = await _override_logs(db_session)
    log_id = log.id
    url = f"/admin/audit-logs/{log_id}"

    assert (await admin_client.put(url, json={})).status_code in (404, 405)
    assert (await admin_client.delete(url)).status_code in (404, 405)

    db_session.expire_all()
    unchanged = await db_session.get(AuditLog, log_id)
    assert unchanged is not None
    assert json.loads(unchanged.new_val) == {"status": "present", "reason": "Seen in class"}
