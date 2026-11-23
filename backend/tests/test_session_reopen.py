"""S38a: one class slot = one session (Shino's rule, 2026-11-23).

Start now again inside today's slot reopens the slot's ended session (same id, records kept,
`SESSION_REOPEN`), recognition can still turn an automatic Absent into Present/Late, overrides
stay, the next close marks Absent again and queues the Moodle sync once, and the M5 interaction
of that session opens again with its history (a lecturer's early close stays closed).

SH101 (shino_helpers) runs Mon 08:00-10:00. Every case uses a controlled clock.
"""
import json
from datetime import date, datetime

import numpy as np
import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.models.attendance import AttendanceRecord
from app.models.audit import AuditLog
from app.models.camera import Camera
from app.models.face import FaceEmbedding
from app.models.interaction import InteractionSession
from app.models.session import AttendanceSession
from app.models.user import Student
from app.services import (attendance_flags, attendance_moodle_sync, attendance_service, recognition_service,
                          session_schedule, session_service)
from app.services.interaction import sessions as interaction_sessions
from tests.shino_helpers import build_shino_class

pytestmark = pytest.mark.db

MON = date(2026, 11, 16)


def at(h: int, m: int = 0, d: date = MON) -> datetime:
    return datetime(d.year, d.month, d.day, h, m)


@pytest.fixture
async def c():
    return await build_shino_class(open_session=False)


@pytest.fixture
def clock(monkeypatch):
    def set_clock(t: datetime) -> None:
        monkeypatch.setattr(session_schedule, "clock", lambda: t)
    return set_clock


@pytest.fixture
def sync_calls(monkeypatch):
    calls: list[int] = []
    monkeypatch.setattr(attendance_moodle_sync, "sync_soon", lambda db, sid: calls.append(sid))
    return calls


async def start(c, **body) -> dict:
    async with c.client(c.lecturer_user_id, "lecturer") as api:
        r = await api.post("/lecturer/sessions", json={"occurrence_id": c.occurrence_id, **body})
    assert r.status_code == 201, r.text
    return r.json()


async def end(c, session_id: int) -> dict:
    async with c.client(c.lecturer_user_id, "lecturer") as api:
        r = await api.put(f"/lecturer/sessions/{session_id}/close")
    assert r.status_code == 200, r.text
    return r.json()


async def sessions_of(c) -> list[AttendanceSession]:
    async with AsyncSessionLocal() as db:
        return list((await db.scalars(select(AttendanceSession)
                                      .where(AttendanceSession.occurrence_id == c.occurrence_id)
                                      .order_by(AttendanceSession.id))).all())


async def records(session_id: int) -> dict[int, AttendanceRecord]:
    async with AsyncSessionLocal() as db:
        rows = (await db.scalars(select(AttendanceRecord)
                                 .where(AttendanceRecord.session_id == session_id))).all()
        return {r.student_id: r for r in rows}


async def audits(action: str) -> list[AuditLog]:
    async with AsyncSessionLocal() as db:
        return list((await db.scalars(select(AuditLog).where(AuditLog.action == action)
                                      .order_by(AuditLog.id))).all())


async def recognise(session_id: int, student_id: int, now: datetime) -> tuple[str, bool]:
    async with AsyncSessionLocal() as db:
        record, was_new = await attendance_service.mark_present(session_id, student_id, db, now=now)
        await db.commit()
        return record.status, was_new


# ── M3: reopen inside the slot ─────────────────────────────────────────────────

async def test_reopen_inside_the_slot_keeps_one_session(c, clock):
    clock(at(7, 50))
    first = await start(c)
    assert first["source"] == "schedule"
    await recognise(first["id"], c.student_ids[0], at(7, 55))

    clock(at(8, 30))
    await end(c, first["id"])

    clock(at(8, 40))
    again = await start(c)
    assert again["id"] == first["id"]
    assert again["status"] == "open" and again["closed_at"] is None
    assert datetime.fromisoformat(again["ends_at"]) == at(10)        # back to the slot's end
    assert datetime.fromisoformat(again["starts_at"]) == at(7, 50)   # Late still counts from the start

    rows = await sessions_of(c)
    assert [r.id for r in rows] == [first["id"]]                     # no new manual row
    recs = await records(first["id"])
    assert recs[c.student_ids[0]].status == "present"                # records kept
    assert len(recs) == len(c.student_ids)

    [log] = await audits("SESSION_REOPEN")
    assert log.target_id == str(first["id"])
    assert json.loads(log.old_val)["status"] == "closed"
    assert json.loads(log.new_val) == {"status": "open", "ends_at": at(10).isoformat()}


async def test_extended_end_is_not_shortened(c, clock):
    clock(at(8))
    first = await start(c)
    async with c.client(c.lecturer_user_id, "lecturer") as api:
        r = await api.post(f"/lecturer/sessions/{first['id']}/extend", json={"minutes": 30})
    assert r.status_code == 200, r.text
    assert datetime.fromisoformat(r.json()["ends_at"]) == at(10, 30)
    async with AsyncSessionLocal() as db:   # closed by M3's service, which keeps ends_at
        await session_service.close_session(first["id"], db, at(10, 5))
        await db.commit()

    clock(at(10, 15))   # after the scheduled end, before the extended one: still the slot
    again = await start(c, duration_minutes=5)
    assert again["id"] == first["id"]
    assert datetime.fromisoformat(again["ends_at"]) == at(10, 30)   # not cut to 10:20

    clock(at(10, 20))
    await end(c, first["id"])
    clock(at(10, 25))   # the lecturer's end moved ends_at to 10:20: the slot is over now
    assert (await start(c))["id"] != first["id"]


async def test_outside_the_slot_makes_a_new_session(c, clock):
    clock(at(8))
    first = await start(c)
    clock(at(9))
    await end(c, first["id"])

    clock(at(10, 5))    # the slot is over
    later = await start(c)
    assert later["id"] != first["id"] and later["source"] == "manual"
    assert await audits("SESSION_REOPEN") == []


async def test_other_day_and_no_schedule_make_a_new_session(c, clock):
    tue = date(2026, 11, 17)
    clock(at(8, d=tue))
    first = await start(c)
    clock(at(8, 30, tue))
    await end(c, first["id"])
    clock(at(8, 40, tue))
    assert (await start(c))["id"] != first["id"]          # not a class day: as before

    async with c.client(c.lecturer_user_id, "lecturer") as api:
        r = await api.put(f"/lecturer/classes/{c.occurrence_id}/schedule", json={})
    assert r.status_code == 200, r.text
    rows = await sessions_of(c)
    clock(at(9, 0, tue))
    await end(c, rows[-1].id)
    clock(at(9, 5, tue))
    assert (await start(c))["id"] not in {r.id for r in rows}   # no schedule: as before
    assert await audits("SESSION_REOPEN") == []


async def test_needs_confirmation_session_is_reopened(c, clock):
    clock(at(8))
    first = await start(c)
    async with AsyncSessionLocal() as db:   # left waiting for confirmation (FR-317)
        s = await db.get(AttendanceSession, first["id"])
        s.status, s.closed_at = "needs_confirmation", at(8, 20)
        await db.commit()
    clock(at(8, 30))
    again = await start(c)
    assert again["id"] == first["id"] and again["status"] == "open"


async def test_running_class_still_conflicts(c, clock):
    clock(at(8))
    await start(c)
    async with c.client(c.lecturer_user_id, "lecturer") as api:
        r = await api.post("/lecturer/sessions", json={"occurrence_id": c.occurrence_id})
    assert r.status_code == 409


# ── attendance after the reopen ────────────────────────────────────────────────

async def test_absent_then_recognised_becomes_present_and_override_is_kept(c, clock, sync_calls):
    s0, s1, s2, s3 = c.student_ids
    clock(at(8))
    first = await start(c)
    sid = first["id"]
    async with c.client(c.lecturer_user_id, "lecturer") as api:
        r = await api.put(f"/lecturer/sessions/{sid}/attendance/override",
                          json={"student_id": s1, "status": "absent", "reason": "left early"})
    assert r.status_code == 200, r.text

    clock(at(8, 5))
    await end(c, sid)
    recs = await records(sid)
    assert {s: recs[s].status for s in c.student_ids} == dict.fromkeys(c.student_ids, "absent")

    clock(at(8, 10))
    await start(c)
    assert await recognise(sid, s0, at(8, 10)) == ("present", True)     # automatic Absent -> Present
    assert await recognise(sid, s2, at(8, 40)) == ("late", True)        # counts from 08:00
    assert await recognise(sid, s0, at(8, 45)) == ("present", False)    # first recognition stays
    assert await recognise(sid, s1, at(8, 45)) == ("absent", False)     # lecturer's override kept

    recs = await records(sid)
    assert recs[s0].detected_at == at(8, 10)
    assert recs[s1].override_by is not None

    clock(at(9))
    closed = await end(c, sid)
    recs = await records(sid)
    assert {s: recs[s].status for s in c.student_ids} == {
        s0: "present", s1: "absent", s2: "late", s3: "absent"}
    assert len(recs) == 4                                               # absent marking re-ran, no duplicates
    assert closed["moodle_sync_status"] == "pending"


async def test_resync_is_queued_once_and_keeps_the_moodle_session(c, clock, sync_calls):
    clock(at(8))
    sid = (await start(c))["id"]
    clock(at(8, 30))
    await end(c, sid)
    assert sync_calls == [sid]
    async with AsyncSessionLocal() as db:   # the first sync went through
        s = await db.get(AttendanceSession, sid)
        s.moodle_sync_status, s.moodle_session_id = "synced", 4242
        for rec in (await db.scalars(select(AttendanceRecord)
                                     .where(AttendanceRecord.session_id == sid))).all():
            rec.moodle_status_sent = rec.status
        await db.commit()

    clock(at(8, 40))
    await start(c)
    async with AsyncSessionLocal() as db:
        s = await db.get(AttendanceSession, sid)
        assert s.moodle_sync_status is None        # nothing is sent while the class runs
        assert s.moodle_session_id == 4242         # same Moodle session next time
        assert sid not in await attendance_moodle_sync.due_session_ids(db, at(8, 50))
    assert sync_calls == [sid]

    await recognise(sid, c.student_ids[0], at(8, 45))
    clock(at(9, 30))
    await end(c, sid)
    assert sync_calls == [sid, sid]                # queued once more, by the second close
    async with AsyncSessionLocal() as db:
        s = await db.get(AttendanceSession, sid)
        assert (s.moodle_sync_status, s.moodle_session_id) == ("pending", 4242)
        rec = await db.scalar(select(AttendanceRecord).where(
            AttendanceRecord.session_id == sid, AttendanceRecord.student_id == c.student_ids[0]))
        assert (rec.status, rec.moodle_status_sent) == ("late", "absent")   # the change to send


async def test_device_recognition_after_reopen_records_the_absent_student(c, clock, monkeypatch):
    """The real device path (recognise_frame, what POST /device/faces runs) must not skip a
    student whose only record is the close's automatic Absent."""
    s0, s1 = c.student_ids[:2]
    vecs: dict[bytes, list[float]] = {}
    async with AsyncSessionLocal() as db:
        cam = Camera(label="SH camera", room="SH-R1", device_id="cam-sh-r1")
        db.add(cam)
        for i, sid in enumerate((s0, s1)):
            vec = [0.0] * 512
            vec[i] = 1.0
            vecs[f"student-{sid}".encode()] = vec
            db.add(FaceEmbedding(student_id=sid, embedding=vec))
        await db.commit()
        camera_id = cam.id
    monkeypatch.setattr(recognition_service, "embed_crop",
                        lambda face_app, data: np.array(vecs[data], dtype=np.float32) if data in vecs else None)
    recognition_service.reset_votes()

    async def frames(session_id: int, student_id: int, now: datetime) -> dict:
        clock(now)
        outcome = {}
        for _ in range(settings.FACE_VOTE_THRESHOLD):
            async with AsyncSessionLocal() as db:
                camera = await db.get(Camera, camera_id)
                session = await db.get(AttendanceSession, session_id)
                (outcome,) = await recognition_service.recognise_frame(
                    db, object(), camera, session, [f"student-{student_id}".encode()])
                await db.commit()
        return outcome

    clock(at(8))
    sid = (await start(c))["id"]
    assert (await frames(sid, s1, at(8, 2)))["outcome"] == "recorded"
    clock(at(8, 30))
    await end(c, sid)

    clock(at(8, 40))
    await start(c)
    outcome = await frames(sid, s0, at(8, 41))
    assert (outcome["outcome"], outcome["status"]) == ("recorded", "late")   # was Absent
    outcome = await frames(sid, s1, at(8, 42))
    assert (outcome["outcome"], outcome["status"]) == ("already_recorded", "present")
    recs = await records(sid)
    assert (recs[s0].status, recs[s0].camera_id) == ("late", camera_id)
    recognition_service.reset_votes()


async def test_student_can_flag_after_reopen(c, clock, monkeypatch):
    """A student the close marked Absent can flag "not recognised" once the class is reopened;
    one the lecturer overrode still can't."""
    clock(at(8))
    sid = (await start(c))["id"]
    async with c.client(c.lecturer_user_id, "lecturer") as api:
        r = await api.put(f"/lecturer/sessions/{sid}/attendance/override",
                          json={"student_id": c.student_ids[1], "status": "absent", "reason": "left"})
    assert r.status_code == 200, r.text
    clock(at(8, 30))
    await end(c, sid)
    clock(at(8, 40))
    await start(c)
    monkeypatch.setattr(attendance_flags, "clock", lambda: at(8, 45))
    async with AsyncSessionLocal() as db:
        flag = await attendance_flags.create_flag(db, await db.get(Student, c.student_ids[0]), sid)
        await db.commit()
        assert flag.status == "pending"
        with pytest.raises(HTTPException) as exc:
            await attendance_flags.create_flag(db, await db.get(Student, c.student_ids[1]), sid)
        assert exc.value.status_code == 409


# ── M5: the interaction follows the reopened class ─────────────────────────────

async def test_interaction_reopens_with_its_history(c, clock):
    clock(at(8))
    sid = (await start(c))["id"]
    async with c.client(c.student_user_ids[0], "student") as api:
        r = await api.post(f"/interaction/{sid}/questions", json={"text": "Before the break?"})
    assert r.status_code == 201, r.text

    clock(at(8, 30))
    await end(c, sid)
    assert await interaction_sessions.sweep() == [sid]      # the class end closed it
    async with c.client(c.student_user_ids[0], "student") as api:
        assert (await api.get(f"/interaction/{sid}")).json()["status"] == "closed"
        r = await api.post(f"/interaction/{sid}/questions", json={"text": "During the break?"})
        assert r.status_code == 409

    clock(at(8, 40))
    await start(c)
    async with c.client(c.student_user_ids[1], "student") as api:
        body = (await api.get(f"/interaction/{sid}")).json()
        assert body["status"] == "open" and body["closed_reason"] is None
        r = await api.post(f"/interaction/{sid}/questions", json={"text": "After the break?"})
        assert r.status_code == 201, r.text
        texts = [q["text"] for q in (await api.get(f"/interaction/{sid}/questions")).json()["questions"]]
    assert sorted(texts) == ["After the break?", "Before the break?"]
    async with AsyncSessionLocal() as db:
        rows = (await db.scalars(select(InteractionSession)
                                 .where(InteractionSession.attendance_session_id == sid))).all()
    assert len(rows) == 1 and rows[0].status == "open" and rows[0].closed_at is None

    clock(at(9))
    await end(c, sid)                                       # and closes again with the class
    assert await interaction_sessions.sweep() == [sid]


async def test_interaction_reopens_before_the_sweep_ran(c, clock):
    clock(at(8))
    sid = (await start(c))["id"]
    async with c.client(c.lecturer_user_id, "lecturer") as api:
        assert (await api.get(f"/interaction/{sid}")).json()["status"] == "open"
    clock(at(8, 30))
    await end(c, sid)
    clock(at(8, 31))
    await start(c)
    async with c.client(c.student_user_ids[0], "student") as api:
        r = await api.post(f"/interaction/{sid}/questions", json={"text": "Still here?"})
    assert r.status_code == 201, r.text


async def test_lecturer_early_close_of_interaction_stays_closed(c, clock):
    clock(at(8))
    sid = (await start(c))["id"]
    async with c.client(c.lecturer_user_id, "lecturer") as api:
        r = await api.post(f"/lecturer/interaction/{sid}/close")
    assert r.status_code == 200 and r.json()["closed_reason"] == "lecturer"
    clock(at(8, 30))
    await end(c, sid)
    await interaction_sessions.sweep()

    clock(at(8, 40))
    await start(c)
    async with c.client(c.student_user_ids[0], "student") as api:
        body = (await api.get(f"/interaction/{sid}")).json()
        assert body["status"] == "closed" and body["closed_reason"] == "lecturer"
        r = await api.post(f"/interaction/{sid}/questions", json={"text": "Can I ask?"})
        assert r.status_code == 409
    async with c.client(c.lecturer_user_id, "lecturer") as api:   # the lecturer can still open it
        r = await api.post(f"/lecturer/interaction/{sid}/open")
    assert r.status_code == 200 and r.json()["status"] == "open"
