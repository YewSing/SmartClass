"""T43: student "not recognised" flags; the lecturer confirms or rejects (FR-318, FR-319, FR-407, FR-410, NFR-02).

Unmatched crops come through the real `POST /device/faces` with the InsightFace model faked as in
`test_device_faces.py`: `embed_crop` returns the vector registered for the crop's bytes.
"""
import json
from datetime import date, datetime, timedelta

import numpy as np
import pytest
from sqlalchemy import func, select

from app.core.database import AsyncSessionLocal
from app.core.security import create_access_token, hash_password
from app.main import app
from app.models.attendance import AttendanceRecord
from app.models.attendance_flag import UnmatchedFace
from app.models.audit import AuditLog
from app.models.face import FaceEmbedding
from app.models.session import AttendanceSession
from app.models.user import Student, User
from app.services import attendance_flags, recognition_service, session_schedule
from app.websocket.manager import manager
from tests.conftest import _client

pytestmark = pytest.mark.db

MON = date(2026, 11, 16)
VECS: dict[bytes, np.ndarray] = {}


def at(h: int, m: int, s: int = 0) -> datetime:
    return datetime(2026, 11, 16, h, m, s)


def unit(k: int, mix: int | None = None, weight: float = 0.0) -> np.ndarray:
    """A unit vector on axis k, optionally tilted towards axis `mix` (cosine to axis k = 1/sqrt(1+w²))."""
    vec = np.zeros(512, dtype=np.float32)
    vec[k] = 1.0
    if mix is not None:
        vec[mix] = weight
    return vec / np.linalg.norm(vec)


@pytest.fixture(autouse=True)
def _state(monkeypatch):
    VECS.clear()
    recognition_service.reset_votes()
    monkeypatch.setattr(app.state, "face_app", object(), raising=False)
    monkeypatch.setattr(recognition_service, "embed_crop", lambda face_app, data: VECS.get(data))
    yield
    VECS.clear()
    recognition_service.reset_votes()


@pytest.fixture
def clock(monkeypatch):
    def set_clock(t: datetime) -> None:
        monkeypatch.setattr(session_schedule, "clock", lambda: t)
        monkeypatch.setattr(attendance_flags, "clock", lambda: t)
    set_clock(at(8, 5))
    return set_clock


@pytest.fixture
def events(monkeypatch):
    sent: list[tuple[int, dict]] = []

    async def fake_broadcast(session_id, payload):
        sent.append((session_id, payload))

    monkeypatch.setattr(manager, "broadcast", fake_broadcast)
    return sent


async def open_session(classroom: dict, occurrence_key: str = "occurrence_id", status: str = "open",
                       camera_id: int | None = None) -> int:
    lecturer_key = "lecturer_id" if occurrence_key == "occurrence_id" else "other_lecturer_id"
    async with AsyncSessionLocal() as db:
        session = AttendanceSession(
            occurrence_id=classroom[occurrence_key], lecturer_id=classroom[lecturer_key], camera_id=camera_id,
            status=status, source="manual", class_date=MON, opened_at=at(7, 45), starts_at=at(8, 0),
            ends_at=at(10, 0), closed_at=at(10, 0) if status == "closed" else None,
        )
        db.add(session)
        await db.commit()
        return session.id


async def set_session(session_id: int, **values) -> None:
    async with AsyncSessionLocal() as db:
        session = await db.get(AttendanceSession, session_id)
        for key, value in values.items():
            setattr(session, key, value)
        await db.commit()


async def enrol_face(student_id: int, k: int) -> None:
    async with AsyncSessionLocal() as db:
        db.add(FaceEmbedding(student_id=student_id, embedding=unit(k).tolist()))
        await db.commit()


async def add_record(session_id: int, student_id: int, status: str = "present") -> None:
    async with AsyncSessionLocal() as db:
        db.add(AttendanceRecord(session_id=session_id, student_id=student_id, status=status, detected_at=at(8, 1)))
        await db.commit()


async def unmatched_count(session_id: int | None = None) -> int:
    async with AsyncSessionLocal() as db:
        q = select(func.count()).select_from(UnmatchedFace)
        if session_id is not None:
            q = q.where(UnmatchedFace.session_id == session_id)
        return await db.scalar(q)


async def flag(student_client, session_id: int):
    return await student_client.post(f"/student/me/sessions/{session_id}/flag")


async def seen_by_device(client, device, *crops: bytes) -> None:
    resp = await client.post("/device/faces", headers=device["headers"],
                             files=[("crops", (f"c{i}.jpg", c, "image/jpeg")) for i, c in enumerate(crops)])
    assert resp.status_code == 200, resp.text


# ── Student flags (FR-318) ───────────────────────────────────────────────────

async def test_student_flags_once_and_lecturer_channel_is_told(student_client, classroom, clock, events):
    session_id = await open_session(classroom)

    resp = await flag(student_client, session_id)
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["status"] == "pending"
    assert body["session_id"] == session_id
    assert body["class_code"] == "CS101"
    assert body["flagged_at"] == at(8, 5).isoformat()

    [(sid, payload)] = events
    assert sid == session_id
    assert payload["event"] == "attendance_flagged"
    assert payload["flag"]["matric_no"] == "S0000001"
    assert payload["flag"]["name"] == "Test Student"
    assert payload["flag"]["status"] == "pending"

    again = await flag(student_client, session_id)
    assert again.status_code == 409
    assert "already flagged" in again.json()["detail"]


async def test_flag_outside_an_open_session_is_refused(student_client, classroom, clock):
    for status in ("closed", "scheduled", "needs_confirmation", "cancelled"):
        session_id = await open_session(classroom, status=status)
        resp = await flag(student_client, session_id)
        assert resp.status_code == 409, status
        assert "open" in resp.json()["detail"]
    assert (await flag(student_client, 999999)).status_code == 404


async def test_flag_when_not_enrolled_is_403(student_client, classroom, clock):
    other_session = await open_session(classroom, occurrence_key="other_occurrence_id")
    resp = await flag(student_client, other_session)
    assert resp.status_code == 403


async def test_flag_when_already_recorded_is_409(student_client, classroom, clock):
    session_id = await open_session(classroom)
    await add_record(session_id, classroom["student_ids"][0], "late")
    resp = await flag(student_client, session_id)
    assert resp.status_code == 409
    assert "already recorded (late)" in resp.json()["detail"]


async def test_only_students_can_flag(lecturer_client, admin_client, classroom, clock):
    session_id = await open_session(classroom)
    assert (await lecturer_client.post(f"/student/me/sessions/{session_id}/flag")).status_code == 403
    assert (await admin_client.post(f"/student/me/sessions/{session_id}/flag")).status_code == 403


# ── Lecturer list + closest unmatched crop (FR-407) ──────────────────────────

async def test_lecturer_sees_flag_with_name_matric_and_closest_crop(
        client, student_client, lecturer_client, classroom, device, clock):
    student_id = classroom["student_ids"][0]
    await enrol_face(student_id, 0)
    session_id = await open_session(classroom, camera_id=device["id"])

    # Two strangers below the threshold: one resembles the student a bit (cos 0.38), one not at all.
    VECS[b"near"] = unit(0, mix=50, weight=2.43)
    VECS[b"far"] = unit(100)
    await seen_by_device(client, device, b"near", b"far")
    assert await unmatched_count(session_id) == 2

    assert (await flag(student_client, session_id)).status_code == 201
    resp = await lecturer_client.get("/lecturer/flags", params={"session_id": session_id})
    assert resp.status_code == 200, resp.text
    [item] = resp.json()
    assert item["name"] == "Test Student"
    assert item["matric_no"] == "S0000001"
    assert item["status"] == "pending"
    assert item["session_status"] == "open"
    assert item["record_status"] is None
    crop = item["closest_crop"]
    assert crop is not None
    assert crop["similarity"] == pytest.approx(0.38, abs=0.01)

    image = await lecturer_client.get(f"/lecturer/flags/{item['id']}/crop")
    assert image.status_code == 200
    assert image.headers["content-type"] == "image/jpeg"
    assert image.content == b"near"


async def test_no_crop_when_none_kept_or_student_has_no_face(student_client, lecturer_client, classroom, clock):
    session_id = await open_session(classroom)
    await flag(student_client, session_id)
    [item] = (await lecturer_client.get("/lecturer/flags")).json()
    assert item["closest_crop"] is None
    assert (await lecturer_client.get(f"/lecturer/flags/{item['id']}/crop")).status_code == 404


async def test_device_keeps_only_unmatched_crops_once_per_person(client, classroom, device, clock):
    student_id = classroom["student_ids"][0]
    await enrol_face(student_id, 0)
    session_id = await open_session(classroom, camera_id=device["id"])
    VECS[b"me"] = unit(0)                          # matches the enrolled student
    VECS[b"stranger"] = unit(7)                    # below threshold
    VECS[b"stranger-again"] = unit(7, mix=8, weight=0.2)   # the same stranger, next frame
    VECS[b"other-stranger"] = unit(9)

    await seen_by_device(client, device, b"me", b"stranger")
    await seen_by_device(client, device, b"stranger-again")
    assert await unmatched_count(session_id) == 1
    await seen_by_device(client, device, b"other-stranger")
    assert await unmatched_count(session_id) == 2

    async with AsyncSessionLocal() as db:
        images = sorted((await db.execute(select(UnmatchedFace.image))).scalars().all())
    assert images == [b"other-stranger", b"stranger"]   # the matched face was never stored


async def test_not_enrolled_match_is_not_kept(client, classroom, device, clock):
    async with AsyncSessionLocal() as db:
        user = User(email="outsider@siswa.um.edu.my", password_hash=hash_password("Student@1234"),
                    role="student", name="Outsider", status="active")
        db.add(user)
        await db.flush()
        outsider = Student(user_id=user.id, matric_no="S0000009")
        db.add(outsider)
        await db.commit()
        outsider_id = outsider.id
    await enrol_face(outsider_id, 3)
    session_id = await open_session(classroom, camera_id=device["id"])
    VECS[b"outsider"] = unit(3)
    await seen_by_device(client, device, b"outsider")
    assert await unmatched_count(session_id) == 0


# ── Confirm / reject (FR-319) ────────────────────────────────────────────────

async def _flag_id(student_client, session_id: int) -> int:
    resp = await flag(student_client, session_id)
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


async def test_confirm_before_late_records_present_from_flag_time(
        client, student_client, lecturer_client, classroom, users, device, clock, events):
    student_id = classroom["student_ids"][0]
    await enrol_face(student_id, 0)
    session_id = await open_session(classroom, camera_id=device["id"])
    VECS[b"near"] = unit(0, mix=50, weight=2.43)
    await seen_by_device(client, device, b"near")

    clock(at(8, 10))
    flag_id = await _flag_id(student_client, session_id)
    clock(at(8, 40))   # the lecturer confirms later; the flag time decides Present
    resp = await lecturer_client.post(f"/lecturer/flags/{flag_id}/confirm")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "confirmed"
    assert body["record_status"] == "present"
    assert body["closest_crop"] is None

    async with AsyncSessionLocal() as db:
        record = await db.scalar(select(AttendanceRecord).where(AttendanceRecord.session_id == session_id))
        assert record.status == "present"
        assert record.source == "student_flag"
        assert record.detected_at == at(8, 10)
        assert record.override_by == users["lecturer"].id
        assert record.override_at == at(8, 40)
        log = await db.scalar(select(AuditLog).where(AuditLog.action == "ATTENDANCE_FLAG_CONFIRM"))
        assert log.actor_id == users["lecturer"].id
        assert log.target_id == str(flag_id)
        assert json.loads(log.new_val)["status"] == "present"
    assert await unmatched_count(session_id) == 0   # the crop shown with the flag is deleted (FR-410)

    kinds = [payload["event"] for _, payload in events]
    assert "attendance_update" in kinds
    assert kinds[-1] == "attendance_flag_resolved"

    mine = (await student_client.get("/student/me/flags")).json()
    assert mine[0]["status"] == "confirmed"
    assert mine[0]["record_status"] == "present"


async def test_confirm_after_late_threshold_records_late(student_client, lecturer_client, classroom, clock):
    session_id = await open_session(classroom)
    clock(at(8, 20))   # starts_at 08:00 + 15 min
    flag_id = await _flag_id(student_client, session_id)
    resp = await lecturer_client.post(f"/lecturer/flags/{flag_id}/confirm")
    assert resp.json()["record_status"] == "late"


async def test_confirm_on_a_synced_closed_session_queues_moodle_resync(
        student_client, lecturer_client, classroom, clock):
    session_id = await open_session(classroom)
    flag_id = await _flag_id(student_client, session_id)
    await set_session(session_id, status="closed", closed_at=at(10, 0), moodle_sync_status="synced",
                      moodle_synced_at=at(10, 1))
    clock(at(11, 0))

    resp = await lecturer_client.post(f"/lecturer/flags/{flag_id}/confirm")
    assert resp.status_code == 200, resp.text
    async with AsyncSessionLocal() as db:
        session = await db.get(AttendanceSession, session_id)
        assert session.moodle_sync_status == "pending"
        assert session.moodle_sync_next_at == at(11, 0)


async def test_reject_needs_a_reason_and_the_student_sees_it(
        student_client, lecturer_client, classroom, users, clock):
    session_id = await open_session(classroom)
    flag_id = await _flag_id(student_client, session_id)

    for bad in ({}, {"reason": ""}, {"reason": "   "}, {"reason": "x" * 501}):
        assert (await lecturer_client.post(f"/lecturer/flags/{flag_id}/reject", json=bad)).status_code == 422

    resp = await lecturer_client.post(f"/lecturer/flags/{flag_id}/reject", json={"reason": " Not seen in class "})
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "rejected"

    [mine] = (await student_client.get("/student/me/flags", params={"session_id": session_id})).json()
    assert mine["status"] == "rejected"
    assert mine["reject_reason"] == "Not seen in class"
    async with AsyncSessionLocal() as db:
        assert await db.scalar(select(AttendanceRecord.id).where(AttendanceRecord.session_id == session_id)) is None
        log = await db.scalar(select(AuditLog).where(AuditLog.action == "ATTENDANCE_FLAG_REJECT"))
        assert log.actor_id == users["lecturer"].id
        assert json.loads(log.new_val)["reason"] == "Not seen in class"

    # resolved once only
    assert (await lecturer_client.post(f"/lecturer/flags/{flag_id}/confirm")).status_code == 409
    assert (await lecturer_client.post(f"/lecturer/flags/{flag_id}/reject",
                                       json={"reason": "again"})).status_code == 409


async def test_confirm_when_recorded_since_is_409(student_client, lecturer_client, classroom, clock):
    session_id = await open_session(classroom)
    flag_id = await _flag_id(student_client, session_id)
    await add_record(session_id, classroom["student_ids"][0], "present")   # recognised after flagging

    [item] = (await lecturer_client.get("/lecturer/flags")).json()
    assert item["record_status"] == "present"
    resp = await lecturer_client.post(f"/lecturer/flags/{flag_id}/confirm")
    assert resp.status_code == 409


async def test_unresolved_flag_at_close_leaves_absent_and_stays_listed(
        student_client, lecturer_client, classroom, clock):
    session_id = await open_session(classroom)
    await _flag_id(student_client, session_id)
    clock(at(10, 0))
    assert (await lecturer_client.put(f"/lecturer/sessions/{session_id}/close")).status_code == 200

    sessions = (await lecturer_client.get("/lecturer/sessions")).json()
    [closed] = [s for s in sessions if s["id"] == session_id]
    assert closed["status"] == "closed"
    assert closed["absent"] == 3   # the flag did not count the student

    [item] = (await lecturer_client.get("/lecturer/flags", params={"status": "pending"})).json()
    assert item["session_status"] == "closed"
    assert item["status"] == "pending"
    assert item["record_status"] == "absent"   # written by close
    # still resolvable after close: the Absent from close becomes Present from the flag time
    resp = await lecturer_client.post(f"/lecturer/flags/{item['id']}/confirm")
    assert resp.status_code == 200, resp.text
    assert resp.json()["record_status"] == "present"
    async with AsyncSessionLocal() as db:
        record = await db.scalar(select(AttendanceRecord).where(
            AttendanceRecord.session_id == session_id, AttendanceRecord.student_id == classroom["student_ids"][0]))
        assert (record.status, record.source, record.detected_at) == ("present", "student_flag", at(8, 5))


async def test_confirm_never_changes_an_override_made_after_close(
        student_client, lecturer_client, classroom, clock):
    session_id = await open_session(classroom)
    flag_id = await _flag_id(student_client, session_id)
    await lecturer_client.put(f"/lecturer/sessions/{session_id}/close")
    resp = await lecturer_client.put(f"/lecturer/sessions/{session_id}/attendance/override",
                                     json={"student_id": classroom["student_ids"][0], "status": "excused"})
    assert resp.status_code == 200, resp.text
    assert (await lecturer_client.post(f"/lecturer/flags/{flag_id}/confirm")).status_code == 409


async def test_another_lecturer_gets_403(student_client, other_lecturer_client, classroom, clock):
    session_id = await open_session(classroom)
    flag_id = await _flag_id(student_client, session_id)

    assert (await other_lecturer_client.get("/lecturer/flags")).json() == []
    assert (await other_lecturer_client.get("/lecturer/flags",
                                            params={"session_id": session_id})).status_code == 403
    assert (await other_lecturer_client.get(f"/lecturer/flags/{flag_id}/crop")).status_code == 403
    assert (await other_lecturer_client.post(f"/lecturer/flags/{flag_id}/confirm")).status_code == 403
    assert (await other_lecturer_client.post(f"/lecturer/flags/{flag_id}/reject",
                                             json={"reason": "no"})).status_code == 403


async def test_admin_keeps_access_as_fallback(student_client, admin_client, classroom, users, clock):
    session_id = await open_session(classroom)
    flag_id = await _flag_id(student_client, session_id)
    [item] = (await admin_client.get("/lecturer/flags")).json()
    assert item["id"] == flag_id
    resp = await admin_client.post(f"/lecturer/flags/{flag_id}/confirm")
    assert resp.status_code == 200, resp.text
    async with AsyncSessionLocal() as db:
        record = await db.scalar(select(AttendanceRecord).where(AttendanceRecord.session_id == session_id))
        assert record.override_by == users["admin"].id


async def test_students_cannot_use_the_lecturer_endpoints(student_client, classroom, clock):
    session_id = await open_session(classroom)
    flag_id = await _flag_id(student_client, session_id)
    assert (await student_client.get("/lecturer/flags")).status_code == 403
    assert (await student_client.post(f"/lecturer/flags/{flag_id}/confirm")).status_code == 403


async def test_a_student_sees_only_their_own_flags(student_client, classroom, clock):
    session_id = await open_session(classroom)
    await _flag_id(student_client, session_id)
    other_user_id = classroom["student_user_ids"][1]
    async with _client(create_access_token(other_user_id, "student")) as other:
        assert (await other.get("/student/me/flags")).json() == []
        assert (await other.post(f"/student/me/sessions/{session_id}/flag")).status_code == 201
    assert len((await student_client.get("/student/me/flags")).json()) == 1


async def test_lecturer_is_never_asked_to_identify_unclaimed_faces(lecturer_client, classroom):
    # The old identify-a-face queue is admin only; lecturers see crops only through a student's flag.
    assert (await lecturer_client.get("/admin/face-review")).status_code == 403


# ── Retention (FR-410, NFR-02) ───────────────────────────────────────────────

async def _crop(session_id: int, captured_at: datetime, k: int) -> None:
    async with AsyncSessionLocal() as db:
        db.add(UnmatchedFace(session_id=session_id, embedding=unit(k).tolist(), image=b"jpg",
                             captured_at=captured_at, last_seen_at=captured_at))
        await db.commit()


async def test_retention_job_deletes_old_and_finished_sessions_crops(student_client, classroom, clock):
    open_id = await open_session(classroom)
    finished_id = await open_session(classroom, status="closed")
    waiting_id = await open_session(classroom)
    await _crop(open_id, at(8, 0), 1)
    await _crop(open_id, at(8, 0) - timedelta(days=8), 2)   # past 7 days, even in an open session
    await _crop(finished_id, at(8, 0), 3)                  # session over, nobody flagged
    await _crop(waiting_id, at(8, 0), 4)
    await _flag_id(student_client, waiting_id)
    await set_session(waiting_id, status="closed", closed_at=at(10, 0))   # closed with a flag pending

    async with AsyncSessionLocal() as db:
        deleted = await attendance_flags.purge_unmatched(db, now=at(12, 0))
        await db.commit()
    assert deleted == 2
    assert await unmatched_count(open_id) == 1
    assert await unmatched_count(finished_id) == 0
    assert await unmatched_count(waiting_id) == 1

    async with AsyncSessionLocal() as db:
        await attendance_flags.purge_unmatched(db, now=at(8, 0) + timedelta(days=7, seconds=1))
        await db.commit()
    assert await unmatched_count() == 0


async def test_resolving_the_last_flag_of_a_closed_session_deletes_its_crops(
        student_client, lecturer_client, classroom, clock):
    session_id = await open_session(classroom)
    flag_id = await _flag_id(student_client, session_id)
    await _crop(session_id, at(8, 0), 5)
    await _crop(session_id, at(8, 1), 6)
    await set_session(session_id, status="closed", closed_at=at(10, 0))

    resp = await lecturer_client.post(f"/lecturer/flags/{flag_id}/reject", json={"reason": "Not in the room"})
    assert resp.status_code == 200
    assert await unmatched_count(session_id) == 0
