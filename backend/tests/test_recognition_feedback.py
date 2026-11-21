"""T44: recognition feedback events (FR-406, NFR-12).

A Present/Late record tells the lecturer's session channel (existing) and the student's own
channel (new). `notify.emit` is the Module 2 hook: it only logs for now. InsightFace is faked as
in `test_device_faces.py`: `embed_crop` returns the vector registered for the crop's bytes.
"""
import logging
from datetime import date, datetime
from types import SimpleNamespace

import numpy as np
import pytest
from fastapi import WebSocketDisconnect
from sqlalchemy import select

from app.core.database import AsyncSessionLocal, discard_after_commit
from app.core.security import create_access_token, create_refresh_token
from app.main import app
from app.models.attendance import AttendanceRecord
from app.models.face import FaceEmbedding
from app.models.session import AttendanceSession
from app.models.user import User
from app.services import attendance_flags, attendance_service, notify, recognition_service, session_schedule
from app.websocket.manager import ConnectionManager, manager
from app.websocket.router import student_ws

pytestmark = pytest.mark.db

MON = date(2026, 11, 16)
URL = "/device/faces"

VECS: dict[bytes, np.ndarray] = {}


def at(h: int, m: int, s: int = 0) -> datetime:
    return datetime(2026, 11, 16, h, m, s)


def unit(k: int) -> np.ndarray:
    vec = np.zeros(512, dtype=np.float32)
    vec[k] = 1.0
    return vec


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
    """`session_schedule.clock` decides Present/Late; `attendance_flags.clock` the flag time."""
    def set_clock(t: datetime) -> None:
        monkeypatch.setattr(session_schedule, "clock", lambda: t)
        monkeypatch.setattr(attendance_flags, "clock", lambda: t)
    set_clock(at(8, 5))
    return set_clock


@pytest.fixture
def channels(monkeypatch):
    """Everything the real code sends: lecturer sessions, student channels, and notify events."""
    sessions: list[tuple[int, dict]] = []
    users_: list[tuple[int, dict]] = []
    emitted: list[tuple[str, list[int], dict]] = []

    async def fake_broadcast(session_id, payload):
        sessions.append((session_id, payload))

    async def fake_send_to_user(user_id, payload):
        users_.append((user_id, payload))

    async def fake_emit(event, user_ids, payload):
        emitted.append((event, list(user_ids), payload))

    monkeypatch.setattr(manager, "broadcast", fake_broadcast)
    monkeypatch.setattr(manager, "send_to_user", fake_send_to_user)
    monkeypatch.setattr(notify, "emit", fake_emit)   # attendance_service calls notify.emit
    return SimpleNamespace(sessions=sessions, users=users_, emitted=emitted)


async def enrol_face(student_id: int, k: int) -> None:
    async with AsyncSessionLocal() as db:
        db.add(FaceEmbedding(student_id=student_id, embedding=unit(k).tolist()))
        await db.commit()


async def open_session(classroom: dict, camera_id: int | None = None) -> int:
    async with AsyncSessionLocal() as db:
        session = AttendanceSession(
            occurrence_id=classroom["occurrence_id"],
            lecturer_id=classroom["lecturer_id"],
            camera_id=camera_id,
            status="open",
            source="manual",
            class_date=MON,
            opened_at=at(7, 45),
            starts_at=at(8, 0),
            ends_at=at(10, 0),
        )
        db.add(session)
        await db.commit()
        return session.id


async def post(client, device, *names: bytes):
    return await client.post(
        URL,
        files=[("crops", (f"c{i}.jpg", name, "image/jpeg")) for i, name in enumerate(names)],
        headers=device["headers"],
    )


async def flag(student_client, session_id: int):
    return await student_client.post(f"/student/me/sessions/{session_id}/flag")


def _updates(channels) -> list[tuple[int, dict]]:
    return [(sid, p) for sid, p in channels.sessions if p["event"] == "attendance_update"]


# ── Recognition (camera path) ────────────────────────────────────────────────

async def test_recognition_tells_lecturer_and_student(client, classroom, device, channels, clock):
    student_id = classroom["student_ids"][0]
    student_user_id = classroom["student_user_ids"][0]
    await enrol_face(student_id, 0)
    VECS[b"A"] = unit(0)
    session_id = await open_session(classroom, device["id"])

    for second in (0, 1, 2):
        clock(at(8, 5, second))
        assert (await post(client, device, b"A")).status_code == 200

    updates = _updates(channels)
    assert len(updates) == 1
    assert updates[0][0] == session_id

    assert len(channels.users) == 1
    user_id, event = channels.users[0]
    assert user_id == student_user_id
    assert event == {
        "event": "attendance_recorded",
        "session_id": session_id,
        "course_code": "CS101",
        "course_name": "Intro to Testing",
        "status": "present",
        "detected_at": at(8, 5, 2).isoformat(),
        "source": "recognition",
        "message": "Attendance recorded for CS101",
    }
    assert channels.emitted == [("attendance.recorded", [student_user_id], event)]


async def test_late_recognition_says_late(client, classroom, device, channels, clock):
    student_id = classroom["student_ids"][0]
    await enrol_face(student_id, 0)
    VECS[b"A"] = unit(0)
    session_id = await open_session(classroom, device["id"])

    for second in (0, 1, 2):
        clock(at(8, 20, second))
        assert (await post(client, device, b"A")).status_code == 200

    [(user_id, event)] = channels.users
    assert user_id == classroom["student_user_ids"][0]
    assert event["status"] == "late"
    assert event["session_id"] == session_id


async def test_no_student_event_while_voting_or_duplicate(client, classroom, device, channels, clock):
    student_id = classroom["student_ids"][0]
    await enrol_face(student_id, 0)
    VECS[b"A"] = unit(0)
    await open_session(classroom, device["id"])

    for second in (0, 1):
        clock(at(8, 5, second))
        assert (await post(client, device, b"A")).status_code == 200
    assert channels.users == []
    assert channels.emitted == []

    clock(at(8, 5, 2))
    assert (await post(client, device, b"A")).status_code == 200
    assert len(channels.users) == 1
    assert len(channels.emitted) == 1

    clock(at(8, 5, 3))
    resp = await post(client, device, b"A")
    assert resp.json()["results"][0]["outcome"] == "already_recorded"
    assert len(channels.users) == 1
    assert len(channels.emitted) == 1


async def test_no_event_when_the_request_fails(classroom, channels, clock):
    """After-commit only: a record that was never committed is never announced (NFR-12)."""
    student_id = classroom["student_ids"][0]
    session_id = await open_session(classroom)

    async with AsyncSessionLocal() as db:
        record = AttendanceRecord(session_id=session_id, student_id=student_id, status="present",
                                  detected_at=at(8, 1))
        db.add(record)
        await db.flush()
        await attendance_service.broadcast_attendance_update(
            session_id, record, "Test Student", "S0000001", db)
        discard_after_commit(db)
        await db.rollback()

    assert channels.users == []
    assert channels.emitted == []

    async with AsyncSessionLocal() as db:
        assert await db.scalar(select(AttendanceRecord.id).where(
            AttendanceRecord.session_id == session_id)) is None


# ── Flag confirmed / rejected ────────────────────────────────────────────────

async def test_confirmed_flag_tells_the_student_twice(student_client, lecturer_client, classroom,
                                                      channels, clock):
    session_id = await open_session(classroom)
    resp = await flag(student_client, session_id)
    assert resp.status_code == 201, resp.text
    flag_id = resp.json()["id"]

    resp = await lecturer_client.post(f"/lecturer/flags/{flag_id}/confirm")
    assert resp.status_code == 200, resp.text

    student_user_id = classroom["student_user_ids"][0]
    assert [uid for uid, _ in channels.users] == [student_user_id, student_user_id]
    recorded, resolved = [payload for _, payload in channels.users]
    assert recorded["event"] == "attendance_recorded"
    assert recorded["source"] == "student_flag"
    assert recorded["status"] == "present"
    assert recorded["session_id"] == session_id
    assert resolved["event"] == "attendance_flag_resolved"
    assert resolved["flag"]["status"] == "confirmed"

    assert [(event, ids) for event, ids, _ in channels.emitted] == [
        ("attendance.recorded", [student_user_id])]


async def test_rejected_flag_tells_the_student(student_client, lecturer_client, classroom,
                                               channels, clock):
    session_id = await open_session(classroom)
    resp = await flag(student_client, session_id)
    assert resp.status_code == 201, resp.text
    flag_id = resp.json()["id"]

    resp = await lecturer_client.post(f"/lecturer/flags/{flag_id}/reject",
                                      json={"reason": "Not seen in class"})
    assert resp.status_code == 200, resp.text

    assert len(channels.users) == 1
    user_id, event = channels.users[0]
    assert user_id == classroom["student_user_ids"][0]
    assert event["event"] == "attendance_flag_resolved"
    assert event["flag"]["status"] == "rejected"
    assert event["flag"]["reject_reason"] == "Not seen in class"
    assert channels.emitted == []


# ── The student's channel ────────────────────────────────────────────────────

class _FakeWebSocket:
    """Runs the real endpoint with real auth and DB; the client disconnects after the first message."""

    def __init__(self):
        self.closed_code = None
        self.sent = []

    async def accept(self):
        pass

    async def close(self, code=1000):
        self.closed_code = code

    async def send_json(self, data):
        self.sent.append(data)

    async def receive_text(self):
        raise WebSocketDisconnect()


async def _connect(token: str) -> _FakeWebSocket:
    ws = _FakeWebSocket()
    await student_ws(ws, token=token)
    return ws


async def test_student_channel_auth(users):
    ws = await _connect(create_access_token(users["student"].id, "student"))
    assert ws.closed_code is None
    assert ws.sent[0] == {"event": "connected", "user_id": users["student"].id}
    assert not manager._user_connections.get(users["student"].id)

    for token in (
        create_access_token(users["lecturer"].id, "lecturer"),
        create_access_token(users["admin"].id, "admin"),
        create_refresh_token(users["student"].id),
        "garbage",
    ):
        ws = await _connect(token)
        assert ws.closed_code == 1008
        assert ws.sent == []

    async with AsyncSessionLocal() as db:
        student_user = await db.get(User, users["student"].id)
        student_user.status = "deactivated"
        await db.commit()

    ws = await _connect(create_access_token(users["student"].id, "student"))
    assert ws.closed_code == 1008
    assert ws.sent == []


# ── Unit: user channels and the emit stub ────────────────────────────────────

class _Socket:
    def __init__(self, fail: bool = False):
        self.fail = fail
        self.sent: list[dict] = []

    async def accept(self):
        pass

    async def send_json(self, payload: dict):
        if self.fail:
            raise RuntimeError("socket closed")
        self.sent.append(payload)


async def test_send_to_user_reaches_only_that_user():
    mgr = ConnectionManager()
    first, second, other = _Socket(), _Socket(), _Socket()
    await mgr.connect_user(1, first)
    await mgr.connect_user(1, second)
    await mgr.connect_user(2, other)

    await mgr.send_to_user(1, {"event": "one"})
    assert first.sent == [{"event": "one"}]
    assert second.sent == [{"event": "one"}]
    assert other.sent == []

    broken = _Socket(fail=True)
    await mgr.connect_user(1, broken)
    await mgr.send_to_user(1, {"event": "two"})
    assert broken.sent == []
    assert first.sent[-1] == {"event": "two"}
    assert broken not in mgr._user_connections[1]


async def test_emit_logs_without_payload(caplog):
    caplog.set_level(logging.INFO, logger="app.services.notify")

    await notify.emit("attendance.recorded", [5, 3, 5], {"name": "Secret Name"})
    records = [r for r in caplog.records if r.name == "app.services.notify"]
    assert len(records) == 1
    message = records[0].getMessage()
    assert "attendance.recorded" in message
    assert "[3, 5]" in message
    assert "Secret Name" not in caplog.text

    caplog.clear()
    await notify.emit("x", [], {})
    assert [r for r in caplog.records if r.name == "app.services.notify"] == []
