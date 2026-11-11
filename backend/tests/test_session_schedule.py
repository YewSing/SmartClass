"""T29: sessions open from the class schedule (FR-301, FR-315–FR-317).

Every time-dependent case uses a controlled clock: the job gets `now` as an argument and the
routers read `session_schedule.clock()`, which the `fixed_clock` fixture patches.
"""
import asyncio
import json
from datetime import date, datetime, timedelta

import pytest
from sqlalchemy import select

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.models.attendance import AttendanceRecord
from app.models.audit import AuditLog
from app.models.camera import Camera
from app.models.class_ import ClassOccurrence
from app.models.face_review import FaceReviewEntry
from app.models.session import AttendanceSession
from app.services import moodle_sync, session_schedule

pytestmark = pytest.mark.db

MON = date(2026, 11, 16)
TUE = MON + timedelta(days=1)


def at(h: int, m: int, d: date = MON) -> datetime:
    return datetime(d.year, d.month, d.day, h, m)


@pytest.fixture
def fixed_clock(monkeypatch):
    def set_clock(t: datetime) -> None:
        monkeypatch.setattr(session_schedule, "clock", lambda: t)
    return set_clock


async def run_tick(now: datetime) -> session_schedule.TickReport:
    async with AsyncSessionLocal() as db:
        report = await session_schedule.tick(db, now)
        await db.commit()
    return report


async def rows_for(db, occurrence_id: int) -> list[AttendanceSession]:
    db.expire_all()
    return (await db.execute(
        select(AttendanceSession)
        .where(AttendanceSession.occurrence_id == occurrence_id)
        .order_by(AttendanceSession.id)
    )).scalars().all()


async def records_for(db, session_id: int) -> list[AttendanceRecord]:
    db.expire_all()
    return (await db.execute(
        select(AttendanceRecord).where(AttendanceRecord.session_id == session_id)
        .order_by(AttendanceRecord.student_id)
    )).scalars().all()


async def audit(db, action: str) -> list[AuditLog]:
    db.expire_all()
    return (await db.execute(
        select(AuditLog).where(AuditLog.action == action).order_by(AuditLog.id)
    )).scalars().all()


def schedule_url(occurrence_id: int) -> str:
    return f"/lecturer/classes/{occurrence_id}/schedule"


def date_url(occurrence_id: int, d: date = MON) -> str:
    return f"/lecturer/classes/{occurrence_id}/dates/{d.isoformat()}"


# ── The job (R2/R3) ───────────────────────────────────────────────────────────

async def test_opens_15_minutes_before_start(lecturer_client, classroom, db_session):
    assert MON.weekday() == 0
    cam = Camera(label="DK1 camera", room="DK1", device_id="cam-dk1")
    db_session.add(cam)
    await db_session.commit()
    camera_id = cam.id

    assert await run_tick(at(7, 44)) == session_schedule.TickReport()
    report = await run_tick(at(7, 45))

    rows = await rows_for(db_session, classroom["occurrence_id"])
    assert len(rows) == 1
    row = rows[0]
    assert report.opened == [row.id]
    assert (row.status, row.source) == ("open", "schedule")
    assert row.class_date == MON
    assert row.starts_at == at(8, 0)
    assert row.ends_at == at(10, 0)
    assert row.opened_at == at(7, 45)
    assert row.camera_id == camera_id
    assert row.lecturer_id == classroom["lecturer_id"]


async def test_opens_once_per_class_date(lecturer_client, classroom, db_session):
    await run_tick(at(7, 45))
    assert await run_tick(at(7, 50)) == session_schedule.TickReport()
    assert await run_tick(at(9, 0)) == session_schedule.TickReport()
    assert len(await rows_for(db_session, classroom["occurrence_id"])) == 1


async def test_does_not_reopen_after_close(lecturer_client, classroom, db_session, fixed_clock):
    await run_tick(at(7, 45))
    [row] = await rows_for(db_session, classroom["occurrence_id"])

    fixed_clock(at(8, 30))
    resp = await lecturer_client.put(f"/lecturer/sessions/{row.id}/close")
    assert resp.status_code == 200, resp.text

    await run_tick(at(9, 0))
    [after] = await rows_for(db_session, classroom["occurrence_id"])
    assert after.id == row.id
    assert after.status == "closed"


async def test_respects_early_open_setting(lecturer_client, classroom, db_session, monkeypatch):
    monkeypatch.setattr(settings, "SESSION_EARLY_OPEN_MINUTES", 5)

    assert await run_tick(at(7, 54)) == session_schedule.TickReport()
    assert await run_tick(at(7, 55)) != session_schedule.TickReport()
    assert len(await rows_for(db_session, classroom["occurrence_id"])) == 1


async def test_wrong_day_and_after_end_do_nothing(lecturer_client, classroom, db_session):
    assert await run_tick(at(7, 50, TUE)) == session_schedule.TickReport()
    assert await run_tick(at(10, 0)) == session_schedule.TickReport()
    assert await rows_for(db_session, classroom["occurrence_id"]) == []


async def test_closes_at_end_and_marks_absent_when_someone_was_recognised(
    lecturer_client, classroom, db_session
):
    await run_tick(at(7, 45))
    [row] = await rows_for(db_session, classroom["occurrence_id"])
    db_session.add(AttendanceRecord(session_id=row.id, student_id=classroom["student_ids"][0],
                                    status="present"))
    await db_session.commit()

    assert await run_tick(at(9, 59)) == session_schedule.TickReport()
    report = await run_tick(at(10, 0))

    [row] = await rows_for(db_session, classroom["occurrence_id"])
    assert report.closed == [row.id]
    assert row.status == "closed"
    assert row.closed_at == at(10, 0)
    by_student = {r.student_id: r.status for r in await records_for(db_session, row.id)}
    assert by_student == {
        classroom["student_ids"][0]: "present",
        classroom["student_ids"][1]: "absent",
        classroom["student_ids"][2]: "absent",
    }


async def test_no_activity_becomes_needs_confirmation(lecturer_client, classroom, db_session):
    await run_tick(at(7, 45))
    [row] = await rows_for(db_session, classroom["occurrence_id"])

    report = await run_tick(at(10, 0))
    [row] = await rows_for(db_session, classroom["occurrence_id"])
    assert report.needs_confirmation == [row.id]
    assert row.status == "needs_confirmation"
    assert row.closed_at == at(10, 0)
    assert await records_for(db_session, row.id) == []


async def test_override_counts_as_activity(lecturer_client, classroom, db_session):
    await run_tick(at(7, 45))
    [row] = await rows_for(db_session, classroom["occurrence_id"])
    resp = await lecturer_client.put(
        f"/lecturer/sessions/{row.id}/attendance/override",
        json={"student_id": classroom["student_ids"][0], "status": "present", "reason": "test"},
    )
    assert resp.status_code == 200, resp.text

    await run_tick(at(10, 0))
    [row] = await rows_for(db_session, classroom["occurrence_id"])
    assert row.status == "closed"
    statuses = sorted(r.status for r in await records_for(db_session, row.id))
    assert statuses == ["absent", "absent", "present"]


async def test_unidentified_face_is_not_a_recognition(lecturer_client, classroom, db_session):
    await run_tick(at(7, 45))
    [row] = await rows_for(db_session, classroom["occurrence_id"])
    db_session.add(FaceReviewEntry(session_id=row.id, embedding=[1.0] + [0.0] * 511, similarity=0.2))
    await db_session.commit()

    await run_tick(at(10, 0))
    [row] = await rows_for(db_session, classroom["occurrence_id"])
    assert row.status == "needs_confirmation"
    assert await records_for(db_session, row.id) == []


async def test_no_schedule_never_opens(lecturer_client, classroom, db_session, fixed_clock):
    fixed_clock(at(7, 0))
    resp = await lecturer_client.put(schedule_url(classroom["occurrence_id"]), json={})
    assert resp.status_code == 200, resp.text
    assert resp.json()["day_of_week"] is None

    await run_tick(at(7, 45))
    await run_tick(at(9, 0))
    assert await rows_for(db_session, classroom["occurrence_id"]) == []

    resp = await lecturer_client.post("/lecturer/sessions",
                                      json={"occurrence_id": classroom["occurrence_id"]})
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["source"] == "manual"
    assert datetime.fromisoformat(body["ends_at"]) - datetime.fromisoformat(body["starts_at"]) \
        == timedelta(minutes=120)


async def test_class_without_lecturer_is_skipped(lecturer_client, classroom, db_session):
    occ = await db_session.get(ClassOccurrence, classroom["occurrence_id"])
    occ.lecturer_id = None
    await db_session.commit()

    assert await run_tick(at(7, 45)) == session_schedule.TickReport()
    assert await rows_for(db_session, classroom["occurrence_id"]) == []


async def test_midnight_start_opens_previous_evening(lecturer_client, classroom, db_session):
    resp = await lecturer_client.put(schedule_url(classroom["occurrence_id"]), json={
        "day_of_week": "Tue", "start_time": "00:00", "end_time": "01:00", "room": "DK1",
    })
    assert resp.status_code == 200, resp.text

    await run_tick(at(23, 45))
    [row] = await rows_for(db_session, classroom["occurrence_id"])
    assert row.class_date == TUE
    assert row.starts_at == at(0, 0, TUE)
    assert row.opened_at == at(23, 45)


async def test_all_day_class_closes_and_does_not_reopen_same_date(
    lecturer_client, classroom, db_session
):
    resp = await lecturer_client.put(schedule_url(classroom["occurrence_id"]), json={
        "day_of_week": "Mon", "start_time": "00:00", "end_time": "23:59", "room": "DK1",
    })
    assert resp.status_code == 200, resp.text

    await run_tick(at(8, 0))
    [first] = await rows_for(db_session, classroom["occurrence_id"])
    assert first.class_date == MON

    report = await run_tick(at(23, 59))
    rows = await rows_for(db_session, classroom["occurrence_id"])
    assert len(rows) == 1
    assert rows[0].status == "needs_confirmation"
    assert report.needs_confirmation == [first.id]

    week_later = MON + timedelta(days=7)
    await run_tick(at(0, 0, week_later))
    rows = await rows_for(db_session, classroom["occurrence_id"])
    assert len(rows) == 2
    assert rows[1].class_date == week_later
    assert rows[1].status == "open"


# ── Lecturer controls ─────────────────────────────────────────────────────────

async def test_set_weekly_schedule(lecturer_client, classroom, db_session):
    resp = await lecturer_client.put(schedule_url(classroom["occurrence_id"]), json={
        "day_of_week": "Wed", "start_time": "14:00", "end_time": "16:00", "room": "DK3",
    })
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert (body["day_of_week"], body["start_time"], body["end_time"], body["room"]) \
        == ("Wed", "14:00", "16:00", "DK3")

    classes = (await lecturer_client.get("/classes?full=true")).json()
    occ = next(o for o in classes if o["id"] == classroom["occurrence_id"])
    assert (occ["day_of_week"], occ["start_time"], occ["end_time"], occ["room"]) \
        == ("Wed", "14:00", "16:00", "DK3")

    [log] = await audit(db_session, "CLASS_SCHEDULE_SET")
    assert log.target_type == "class_occurrence" and log.target_id == str(classroom["occurrence_id"])
    assert json.loads(log.old_val) == {
        "day_of_week": "Mon", "start_time": "08:00", "end_time": "10:00", "room": "DK1",
    }
    assert json.loads(log.new_val) == {
        "day_of_week": "Wed", "start_time": "14:00", "end_time": "16:00", "room": "DK3",
    }


async def test_weekly_schedule_validation(lecturer_client, classroom):
    url = schedule_url(classroom["occurrence_id"])
    for body in (
        {"day_of_week": "Wed"},
        {"day_of_week": "Wed", "start_time": "10:00", "end_time": "10:00"},
        {"day_of_week": "Wed", "start_time": "11:00", "end_time": "10:00"},
        {"day_of_week": "Wed", "start_time": "25:00", "end_time": "26:00"},
        {"day_of_week": "Monday", "start_time": "09:00", "end_time": "10:00"},
    ):
        resp = await lecturer_client.put(url, json=body)
        assert resp.status_code == 422, (body, resp.text)


async def test_schedule_and_one_class_endpoints_are_lecturer_only(
    lecturer_client, other_lecturer_client, admin_client, student_client, classroom
):
    resp = await lecturer_client.post("/lecturer/sessions",
                                      json={"occurrence_id": classroom["occurrence_id"]})
    assert resp.status_code == 201, resp.text
    session_id = resp.json()["id"]

    endpoints = [
        ("PUT", schedule_url(classroom["occurrence_id"]),
         {"day_of_week": "Wed", "start_time": "14:00", "end_time": "16:00"}),
        ("PUT", date_url(classroom["occurrence_id"], MON + timedelta(days=2)),
         {"start_time": "09:00", "end_time": "10:00"}),
        ("POST", f"{date_url(classroom['occurrence_id'], MON + timedelta(days=2))}/cancel", None),
        ("POST", f"/lecturer/sessions/{session_id}/extend", {"minutes": 15}),
        ("POST", f"/lecturer/sessions/{session_id}/confirm", {"held": True}),
    ]
    for client in (other_lecturer_client, admin_client, student_client):
        for method, url, body in endpoints:
            resp = await client.request(method, url, json=body)
            assert resp.status_code == 403, (method, url, resp.text)

    for method, url, body in endpoints[:3]:
        unknown = url.replace(str(classroom["occurrence_id"]), "999999", 1)
        resp = await lecturer_client.request(method, unknown, json=body)
        assert resp.status_code == 404, (method, unknown, resp.text)


async def test_moodle_sync_keeps_schedule(lecturer_client, classroom, db_session):
    resp = await lecturer_client.put(schedule_url(classroom["occurrence_id"]), json={
        "day_of_week": "Wed", "start_time": "14:00", "end_time": "16:00", "room": "DK3",
    })
    assert resp.status_code == 200, resp.text

    await moodle_sync.apply(db_session, [moodle_sync.MoodleCourse(
        id=7070, shortname="CS101", fullname="Intro to Testing",
    )])
    await db_session.commit()
    db_session.expire_all()

    occ = await db_session.get(ClassOccurrence, classroom["occurrence_id"])
    assert (occ.day_of_week, occ.start_time, occ.end_time, occ.room) \
        == ("Wed", "14:00", "16:00", "DK3")


async def test_change_time_before_class(lecturer_client, classroom, db_session, fixed_clock):
    fixed_clock(at(7, 0))
    resp = await lecturer_client.put(date_url(classroom["occurrence_id"]), json={
        "start_time": "09:00", "end_time": "11:00",
    })
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "scheduled"
    assert datetime.fromisoformat(body["starts_at"]) == at(9, 0)
    session_id = body["id"]

    classes = (await lecturer_client.get("/classes?full=true")).json()
    occ = next(o for o in classes if o["id"] == classroom["occurrence_id"])
    assert (occ["day_of_week"], occ["start_time"], occ["end_time"]) == ("Mon", "08:00", "10:00")

    assert await run_tick(at(7, 45)) == session_schedule.TickReport()
    [row] = await rows_for(db_session, classroom["occurrence_id"])
    assert row.status == "scheduled"

    report = await run_tick(at(8, 45))
    assert report.opened == [session_id]
    [row] = await rows_for(db_session, classroom["occurrence_id"])
    assert row.id == session_id and row.status == "open"
    assert row.opened_at == at(8, 45)

    report = await run_tick(at(11, 0))
    assert report.needs_confirmation == [session_id]
    [row] = await rows_for(db_session, classroom["occurrence_id"])
    assert row.status == "needs_confirmation"
    assert row.lecturer_action_at is None

    [log] = await audit(db_session, "SESSION_TIME_CHANGED")
    assert json.loads(log.old_val) == {"starts_at": at(8, 0).isoformat(),
                                      "ends_at": at(10, 0).isoformat()}
    assert json.loads(log.new_val) == {"starts_at": at(9, 0).isoformat(),
                                       "ends_at": at(11, 0).isoformat()}


async def test_change_time_during_class(lecturer_client, classroom, db_session, fixed_clock):
    await run_tick(at(7, 45))
    [row] = await rows_for(db_session, classroom["occurrence_id"])

    fixed_clock(at(8, 30))
    resp = await lecturer_client.put(date_url(classroom["occurrence_id"]), json={
        "start_time": "08:00", "end_time": "10:30",
    })
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "open"

    [row] = await rows_for(db_session, classroom["occurrence_id"])
    assert row.ends_at == at(10, 30)
    assert row.lecturer_action_at == at(8, 30)

    assert await run_tick(at(10, 0)) == session_schedule.TickReport()
    await run_tick(at(10, 30))
    [row] = await rows_for(db_session, classroom["occurrence_id"])
    assert row.status == "closed"
    assert len(await records_for(db_session, row.id)) == 3


async def test_change_time_rejections(lecturer_client, classroom, db_session, fixed_clock):
    fixed_clock(at(7, 0))
    past = MON - timedelta(days=1)
    resp = await lecturer_client.put(date_url(classroom["occurrence_id"], past),
                                     json={"start_time": "09:00", "end_time": "10:00"})
    assert resp.status_code == 422, resp.text

    resp = await lecturer_client.put(date_url(classroom["occurrence_id"], TUE),
                                     json={"start_time": "09:00", "end_time": "10:00"})
    assert resp.status_code == 422, resp.text

    await run_tick(at(7, 45))
    [row] = await rows_for(db_session, classroom["occurrence_id"])

    fixed_clock(at(9, 30))
    resp = await lecturer_client.put(date_url(classroom["occurrence_id"]),
                                     json={"start_time": "08:30", "end_time": "09:00"})
    assert resp.status_code == 422, resp.text

    fixed_clock(at(9, 45))
    assert (await lecturer_client.put(f"/lecturer/sessions/{row.id}/close")).status_code == 200
    resp = await lecturer_client.put(date_url(classroom["occurrence_id"]),
                                     json={"start_time": "08:00", "end_time": "10:00"})
    assert resp.status_code == 409, resp.text


async def test_start_now_before_scheduled_time_uses_todays_slot(
    lecturer_client, classroom, db_session, fixed_clock
):
    fixed_clock(at(6, 0))
    resp = await lecturer_client.post("/lecturer/sessions",
                                      json={"occurrence_id": classroom["occurrence_id"]})
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["source"] == "schedule"
    assert body["class_date"] == MON.isoformat()
    assert datetime.fromisoformat(body["starts_at"]) == at(6, 0)
    assert datetime.fromisoformat(body["ends_at"]) == at(10, 0)

    assert await run_tick(at(7, 45)) == session_schedule.TickReport()
    assert len(await rows_for(db_session, classroom["occurrence_id"])) == 1


async def test_start_now_with_duration(lecturer_client, classroom, db_session, fixed_clock):
    fixed_clock(at(9, 0, TUE))
    resp = await lecturer_client.post("/lecturer/sessions", json={
        "occurrence_id": classroom["occurrence_id"], "duration_minutes": 30,
    })
    assert resp.status_code == 201, resp.text
    body = resp.json()
    session_id = body["id"]
    assert body["source"] == "manual"
    assert datetime.fromisoformat(body["starts_at"]) == at(9, 0, TUE)
    assert datetime.fromisoformat(body["ends_at"]) == at(9, 30, TUE)

    report = await run_tick(at(9, 30, TUE))
    assert report.closed == [session_id]
    [row] = await rows_for(db_session, classroom["occurrence_id"])
    assert row.status == "closed"
    assert sorted(r.status for r in await records_for(db_session, row.id)) == ["absent"] * 3

    [log] = await audit(db_session, "SESSION_START_NOW")
    assert log.target_id == str(session_id)
    assert json.loads(log.new_val)["source"] == "manual"


async def test_start_now_opens_a_scheduled_row(lecturer_client, classroom, fixed_clock):
    fixed_clock(at(7, 0))
    resp = await lecturer_client.put(date_url(classroom["occurrence_id"]), json={
        "start_time": "09:00", "end_time": "11:00",
    })
    assert resp.status_code == 200, resp.text
    session_id = resp.json()["id"]

    fixed_clock(at(8, 0))
    resp = await lecturer_client.post("/lecturer/sessions",
                                      json={"occurrence_id": classroom["occurrence_id"]})
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["id"] == session_id
    assert body["status"] == "open"
    assert datetime.fromisoformat(body["starts_at"]) == at(8, 0)
    assert datetime.fromisoformat(body["ends_at"]) == at(11, 0)


async def test_extend(lecturer_client, classroom, db_session, fixed_clock):
    await run_tick(at(7, 45))
    [row] = await rows_for(db_session, classroom["occurrence_id"])

    fixed_clock(at(8, 0))
    resp = await lecturer_client.post(f"/lecturer/sessions/{row.id}/extend", json={"minutes": 15})
    assert resp.status_code == 200, resp.text
    assert datetime.fromisoformat(resp.json()["ends_at"]) == at(10, 15)

    assert await run_tick(at(10, 0)) == session_schedule.TickReport()
    await run_tick(at(10, 15))
    [row] = await rows_for(db_session, classroom["occurrence_id"])
    assert row.status == "closed"

    resp = await lecturer_client.post(f"/lecturer/sessions/{row.id}/extend", json={"minutes": 0})
    assert resp.status_code == 422, resp.text
    resp = await lecturer_client.post(f"/lecturer/sessions/{row.id}/extend", json={"minutes": 15})
    assert resp.status_code == 409, resp.text

    [log] = await audit(db_session, "SESSION_EXTENDED")
    assert json.loads(log.old_val) == {"ends_at": at(10, 0).isoformat()}
    assert json.loads(log.new_val) == {"ends_at": at(10, 15).isoformat()}


async def test_end_early(lecturer_client, classroom, db_session, fixed_clock):
    await run_tick(at(7, 45))
    [row] = await rows_for(db_session, classroom["occurrence_id"])

    fixed_clock(at(8, 40))
    resp = await lecturer_client.put(f"/lecturer/sessions/{row.id}/close")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "closed"
    assert datetime.fromisoformat(body["ends_at"]) == at(8, 40)
    assert datetime.fromisoformat(body["closed_at"]) == at(8, 40)
    assert body["absent"] == 3

    assert len(await records_for(db_session, row.id)) == 3
    [log] = await audit(db_session, "SESSION_ENDED")
    assert json.loads(log.new_val) == {"status": "closed", "ends_at": at(8, 40).isoformat()}


async def test_cancel_before_class(lecturer_client, classroom, db_session, fixed_clock):
    fixed_clock(at(7, 0))
    resp = await lecturer_client.post(f"{date_url(classroom['occurrence_id'])}/cancel")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "cancelled"
    assert body["opened_at"] is None

    await run_tick(at(7, 45))
    await run_tick(at(9, 0))
    [row] = await rows_for(db_session, classroom["occurrence_id"])
    assert row.status == "cancelled"
    assert row.opened_at is None
    assert await records_for(db_session, row.id) == []

    assert (await lecturer_client.get("/lecturer/sessions")).json() == []

    classes = (await lecturer_client.get("/classes?full=true")).json()
    occ = next(o for o in classes if o["id"] == classroom["occurrence_id"])
    assert (occ["day_of_week"], occ["start_time"], occ["end_time"]) == ("Mon", "08:00", "10:00")

    [log] = await audit(db_session, "SESSION_CANCELLED")
    assert json.loads(log.new_val) == {"status": "cancelled"}


async def test_cancel_during_class(lecturer_client, classroom, db_session, fixed_clock):
    await run_tick(at(7, 45))
    [row] = await rows_for(db_session, classroom["occurrence_id"])

    fixed_clock(at(8, 0))
    resp = await lecturer_client.put(
        f"/lecturer/sessions/{row.id}/attendance/override",
        json={"student_id": classroom["student_ids"][0], "status": "present", "reason": "test"},
    )
    assert resp.status_code == 200, resp.text
    resp = await lecturer_client.post(f"{date_url(classroom['occurrence_id'])}/cancel")
    assert resp.status_code == 409, resp.text

    [record] = await records_for(db_session, row.id)
    await db_session.delete(record)
    await db_session.commit()

    fixed_clock(at(8, 10))
    resp = await lecturer_client.post(f"{date_url(classroom['occurrence_id'])}/cancel")
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "cancelled"

    [row] = await rows_for(db_session, classroom["occurrence_id"])
    assert row.status == "cancelled"
    assert row.closed_at == at(8, 10)
    assert await records_for(db_session, row.id) == []


async def test_confirm_held_marks_absent(lecturer_client, classroom, db_session, fixed_clock):
    await run_tick(at(7, 45))
    [row] = await rows_for(db_session, classroom["occurrence_id"])
    await run_tick(at(10, 0))
    [row] = await rows_for(db_session, classroom["occurrence_id"])
    assert row.status == "needs_confirmation"

    fixed_clock(at(10, 30))
    resp = await lecturer_client.post(f"/lecturer/sessions/{row.id}/confirm", json={"held": True})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "closed"
    assert datetime.fromisoformat(body["closed_at"]) == at(10, 0)  # the end the job recorded

    [row] = await rows_for(db_session, classroom["occurrence_id"])
    assert row.closed_at == at(10, 0)
    session_id = row.id
    assert sorted(r.status for r in await records_for(db_session, session_id)) == ["absent"] * 3

    [log] = await audit(db_session, "SESSION_CONFIRMED_HELD")
    assert log.target_id == str(session_id)


async def test_confirm_not_held(lecturer_client, classroom, db_session, fixed_clock):
    await run_tick(at(7, 45))
    [row] = await rows_for(db_session, classroom["occurrence_id"])
    await run_tick(at(10, 0))

    fixed_clock(at(10, 30))
    resp = await lecturer_client.post(f"/lecturer/sessions/{row.id}/confirm", json={"held": False})
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "cancelled"
    [row] = await rows_for(db_session, classroom["occurrence_id"])
    assert row.status == "cancelled"
    assert await records_for(db_session, row.id) == []
    assert await audit(db_session, "SESSION_CONFIRMED_NOT_HELD")

    resp = await lecturer_client.post("/lecturer/sessions",
                                      json={"occurrence_id": classroom["occurrence_id"]})
    assert resp.status_code == 201, resp.text
    open_id = resp.json()["id"]
    resp = await lecturer_client.post(f"/lecturer/sessions/{open_id}/confirm", json={"held": True})
    assert resp.status_code == 409, resp.text


async def test_scheduled_rows_hidden_from_list(lecturer_client, classroom, fixed_clock):
    fixed_clock(at(7, 0))
    resp = await lecturer_client.put(date_url(classroom["occurrence_id"]), json={
        "start_time": "09:00", "end_time": "11:00",
    })
    session_id = resp.json()["id"]

    fixed_clock(at(7, 30))
    assert (await lecturer_client.get("/lecturer/sessions")).json() == []

    fixed_clock(at(8, 0))
    resp = await lecturer_client.post("/lecturer/sessions",
                                      json={"occurrence_id": classroom["occurrence_id"]})
    assert resp.status_code == 201, resp.text
    assert resp.json()["id"] == session_id

    fixed_clock(at(8, 30))
    assert (await lecturer_client.post(
        f"{date_url(classroom['occurrence_id'])}/cancel")).status_code == 200

    listed = (await lecturer_client.get("/lecturer/sessions")).json()
    assert [(s["id"], s["status"]) for s in listed] == [(session_id, "cancelled")]


async def test_scheduler_loop_disabled_at_zero(monkeypatch):
    monkeypatch.setattr(settings, "SESSION_SCHEDULER_INTERVAL_SECONDS", 0)
    assert await asyncio.wait_for(session_schedule.session_scheduler_loop(), 1) is None
