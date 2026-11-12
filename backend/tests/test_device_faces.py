"""T41: server-side recognition from device face crops (FR-402–FR-405, NFR-10, NFR-22).

The InsightFace model is replaced with a fake: `recognition_service.embed_crop` returns the vector
registered for the crop's bytes in `VECS`. Everything else (pgvector matching, voting, records,
broadcast) is the real code. `test_device_faces_real.py` runs the real model.
"""
import logging
from datetime import date, datetime, timedelta

import numpy as np
import pytest
from sqlalchemy import select

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.core.security import hash_password
from app.main import app
from app.models.attendance import AttendanceRecord
from app.models.face import FaceEmbedding
from app.models.session import AttendanceSession
from app.models.user import Student, User
from app.services import attendance_service, recognition_service, session_schedule

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
def fixed_clock(monkeypatch):
    def set_clock(t: datetime) -> None:
        monkeypatch.setattr(session_schedule, "clock", lambda: t)
    return set_clock


async def enrol_faces(db, mapping: dict[int, int]) -> None:
    for student_id, k in mapping.items():
        db.add(FaceEmbedding(student_id=student_id, embedding=unit(k).tolist()))
    await db.commit()


async def open_session(classroom: dict, camera_id: int | None, occurrence_key: str = "occurrence_id") -> int:
    lecturer_key = "lecturer_id" if occurrence_key == "occurrence_id" else "other_lecturer_id"
    async with AsyncSessionLocal() as db:
        session = AttendanceSession(
            occurrence_id=classroom[occurrence_key],
            lecturer_id=classroom[lecturer_key],
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


async def records_for(db, session_id: int) -> list[AttendanceRecord]:
    db.expire_all()
    return (await db.execute(
        select(AttendanceRecord).where(AttendanceRecord.session_id == session_id)
        .order_by(AttendanceRecord.student_id)
    )).scalars().all()


@pytest.fixture
async def outsider() -> int:
    """A student with a stored face who is not enrolled in CS101."""
    async with AsyncSessionLocal() as db:
        user = User(email="outsider@siswa.um.edu.my", password_hash=hash_password("Student@1234"),
                    role="student", name="Outsider Student", status="active")
        db.add(user)
        await db.flush()
        student = Student(user_id=user.id, matric_no="S0000009", programme="Software Engineering")
        db.add(student)
        await db.commit()
        return student.id


# ── Recording ────────────────────────────────────────────────────────────────

async def test_three_consecutive_frames_record_present(client, classroom, device, db_session, fixed_clock):
    student_id = classroom["student_ids"][0]
    await enrol_faces(db_session, {student_id: 0})
    VECS[b"A"] = unit(0)
    session_id = await open_session(classroom, device["id"])

    results = []
    for second in (0, 1, 2):
        fixed_clock(at(8, 5, second))
        resp = await post(client, device, b"A")
        assert resp.status_code == 200, resp.text
        assert resp.json()["session_id"] == session_id
        results.append(resp.json()["results"][0])

    assert [r["outcome"] for r in results] == ["voting", "voting", "recorded"]
    assert [r["votes"] for r in results] == [1, 2, 3]
    assert results[-1]["student_id"] == student_id
    assert results[-1]["status"] == "present"

    [record] = await records_for(db_session, session_id)
    assert record.status == "present"
    assert record.detected_at == at(8, 5, 2)
    assert record.camera_id == device["id"]


async def test_late_arrival_records_late(client, classroom, device, db_session, fixed_clock):
    student_id = classroom["student_ids"][0]
    await enrol_faces(db_session, {student_id: 0})
    VECS[b"A"] = unit(0)
    session_id = await open_session(classroom, device["id"])

    for second in (0, 1, 2):
        fixed_clock(at(8, 20, second))
        resp = await post(client, device, b"A")
        assert resp.status_code == 200, resp.text
    assert resp.json()["results"][0]["outcome"] == "recorded"
    assert resp.json()["results"][0]["status"] == "late"

    [record] = await records_for(db_session, session_id)
    assert record.status == "late"


async def test_below_threshold_is_never_counted(client, classroom, device, db_session, fixed_clock):
    student_id = classroom["student_ids"][0]
    await enrol_faces(db_session, {student_id: 0})
    VECS[b"LOW"] = 0.3 * unit(0) + np.sqrt(1 - 0.09) * unit(10)
    session_id = await open_session(classroom, device["id"])

    for second in (0, 1, 2):
        fixed_clock(at(8, 5, second))
        resp = await post(client, device, b"LOW")
        assert resp.status_code == 200, resp.text
        [result] = resp.json()["results"]
        assert result["outcome"] == "below_threshold"
        assert result["similarity"] == pytest.approx(0.30, abs=0.01)
        assert result["student_id"] is None

    assert await records_for(db_session, session_id) == []


async def test_not_enrolled_match_is_logged_not_recorded(
    client, classroom, device, db_session, fixed_clock, outsider, caplog
):
    await enrol_faces(db_session, {classroom["student_ids"][0]: 0, outsider: 3})
    VECS[b"X"] = unit(3)
    session_id = await open_session(classroom, device["id"])
    caplog.set_level(logging.INFO, logger="app.services.recognition_service")

    for second in (0, 1, 2):
        fixed_clock(at(8, 5, second))
        resp = await post(client, device, b"X")
        assert resp.status_code == 200, resp.text
        [result] = resp.json()["results"]
        assert result["outcome"] == "not_enrolled"
        assert result["student_id"] is None
        assert result["similarity"] == pytest.approx(1.0, abs=0.01)

    assert await records_for(db_session, session_id) == []
    assert any(str(outsider) in message and "not enrolled" in message for message in caplog.messages)


async def test_missing_frame_restarts_the_count(client, classroom, device, db_session, fixed_clock):
    first, second = classroom["student_ids"][:2]
    await enrol_faces(db_session, {first: 0, second: 1})
    VECS[b"A"] = unit(0)
    VECS[b"B"] = unit(1)
    await open_session(classroom, device["id"])

    votes = []
    for index, name in enumerate((b"A", b"A", b"B", b"A")):
        fixed_clock(at(8, 5, index))
        resp = await post(client, device, name)
        assert resp.status_code == 200, resp.text
        [result] = resp.json()["results"]
        assert result["outcome"] == "voting"
        votes.append((result["student_id"], result["votes"]))

    assert votes == [(first, 1), (first, 2), (second, 1), (first, 1)]


async def test_frames_too_far_apart_restart_the_count(client, classroom, device, db_session, fixed_clock):
    student_id = classroom["student_ids"][0]
    await enrol_faces(db_session, {student_id: 0})
    VECS[b"A"] = unit(0)
    await open_session(classroom, device["id"])

    times = [at(8, 5, 0), at(8, 5, 1),
             at(8, 5, 1) + timedelta(seconds=settings.FACE_VOTE_MAX_GAP_SECONDS + 1)]
    votes = []
    for t in times:
        fixed_clock(t)
        resp = await post(client, device, b"A")
        assert resp.status_code == 200, resp.text
        votes.append(resp.json()["results"][0]["votes"])
    assert votes == [1, 2, 1]


async def test_two_faces_in_one_frame_vote_separately(client, classroom, device, db_session, fixed_clock):
    first, second, third = classroom["student_ids"]
    await enrol_faces(db_session, {first: 0, second: 1, third: 2})
    VECS[b"A"] = unit(0)
    VECS[b"B"] = unit(1)
    VECS[b"C"] = unit(2)
    session_id = await open_session(classroom, device["id"])

    for second_index in (0, 1, 2):
        fixed_clock(at(8, 5, second_index))
        resp = await post(client, device, b"A", b"B")
        assert resp.status_code == 200, resp.text

    assert [r["outcome"] for r in resp.json()["results"]] == ["recorded", "recorded"]
    records = await records_for(db_session, session_id)
    assert {r.student_id for r in records} == {first, second}

    recognition_service.reset_votes()
    resp = await post(client, device, b"C", b"C")
    assert resp.status_code == 200, resp.text
    assert [(r["outcome"], r["votes"]) for r in resp.json()["results"]] == [("voting", 1), ("voting", 1)]


async def test_duplicate_is_not_recorded_again(client, classroom, device, db_session, fixed_clock):
    student_id = classroom["student_ids"][0]
    await enrol_faces(db_session, {student_id: 0})
    VECS[b"A"] = unit(0)
    session_id = await open_session(classroom, device["id"])

    for second in (0, 1, 2):
        fixed_clock(at(8, 5, second))
        assert (await post(client, device, b"A")).status_code == 200

    fixed_clock(at(8, 5, 3))
    resp = await post(client, device, b"A")
    assert resp.status_code == 200, resp.text
    [result] = resp.json()["results"]
    assert result["outcome"] == "already_recorded"
    assert result["status"] == "present"

    [record] = await records_for(db_session, session_id)
    assert record.detected_at == at(8, 5, 2)


async def test_existing_override_is_kept(client, classroom, device, db_session, fixed_clock):
    student_id = classroom["student_ids"][1]
    await enrol_faces(db_session, {student_id: 0})
    VECS[b"B"] = unit(0)
    session_id = await open_session(classroom, device["id"])
    db_session.add(AttendanceRecord(session_id=session_id, student_id=student_id, status="excused"))
    await db_session.commit()

    fixed_clock(at(8, 5, 0))
    resp = await post(client, device, b"B")
    assert resp.status_code == 200, resp.text
    [result] = resp.json()["results"]
    assert result["outcome"] == "already_recorded"
    assert result["status"] == "excused"

    [record] = await records_for(db_session, session_id)
    assert record.status == "excused"


async def test_no_face_crop_is_ignored_and_keeps_votes(client, classroom, device, db_session, fixed_clock):
    student_id = classroom["student_ids"][0]
    await enrol_faces(db_session, {student_id: 0})
    VECS[b"A"] = unit(0)
    await open_session(classroom, device["id"])

    fixed_clock(at(8, 5, 0))
    assert (await post(client, device, b"A")).json()["results"][0]["votes"] == 1
    fixed_clock(at(8, 5, 1))
    assert (await post(client, device, b"A")).json()["results"][0]["votes"] == 2

    fixed_clock(at(8, 5, 2))
    resp = await post(client, device, b"NOFACE")   # not in VECS → embed_crop returns None
    assert resp.status_code == 200, resp.text
    assert resp.json()["results"][0]["outcome"] == "no_face"

    fixed_clock(at(8, 5, 3))
    resp = await post(client, device, b"A")
    [result] = resp.json()["results"]
    assert result["outcome"] == "recorded"
    assert result["votes"] == 3


def test_vote_counts_are_per_device_and_session():
    recognition_service.reset_votes()
    t = at(8, 5, 0)
    assert recognition_service.vote(1, 10, {5}, t) == {5: 1}
    assert recognition_service.vote(2, 10, {5}, t) == {5: 1}
    assert recognition_service.vote(1, 10, {5}, t) == {5: 2}
    assert recognition_service.vote(1, 11, {5}, t) == {5: 1}


# ── Which session the device records into ────────────────────────────────────

async def test_session_of_the_room_without_a_camera_is_used(client, classroom, device, db_session, fixed_clock):
    student_id = classroom["student_ids"][0]
    await enrol_faces(db_session, {student_id: 0})
    VECS[b"A"] = unit(0)
    session_id = await open_session(classroom, None)

    for second in (0, 1, 2):
        fixed_clock(at(8, 5, second))
        resp = await post(client, device, b"A")
        assert resp.status_code == 200, resp.text
    assert resp.json()["results"][0]["outcome"] == "recorded"
    assert resp.json()["session_id"] == session_id
    assert len(await records_for(db_session, session_id)) == 1


async def test_another_rooms_session_is_not_used(client, classroom, device, fixed_clock):
    VECS[b"A"] = unit(0)
    await open_session(classroom, None, "other_occurrence_id")

    fixed_clock(at(8, 5, 0))
    resp = await post(client, device, b"A")
    assert resp.status_code == 404


async def test_no_open_session_is_404(client, classroom, device, fixed_clock):
    VECS[b"A"] = unit(0)
    fixed_clock(at(8, 5, 0))
    assert (await post(client, device, b"A")).status_code == 404


# ── Input and access rules ───────────────────────────────────────────────────

async def test_device_key_is_required(client):
    files = [("crops", ("c0.jpg", b"A", "image/jpeg"))]
    assert (await client.post(URL, files=files)).status_code == 422   # header missing
    assert (await client.post(URL, files=files, headers={"X-Device-Key": "scd_wrong"})).status_code == 401


async def test_model_not_loaded_is_503(client, device, monkeypatch, fixed_clock):
    monkeypatch.setattr(app.state, "face_app", None, raising=False)
    VECS[b"A"] = unit(0)
    fixed_clock(at(8, 5, 0))
    assert (await post(client, device, b"A")).status_code == 503


async def test_crop_limits(client, device, monkeypatch, fixed_clock):
    fixed_clock(at(8, 5, 0))
    resp = await post(client, device, *[b"A"] * 11)
    assert resp.status_code == 422, resp.text

    monkeypatch.setattr(settings, "DEVICE_MAX_CROP_BYTES", 10)
    resp = await client.post(
        URL, files=[("crops", ("c0.jpg", b"A" * 20, "image/jpeg"))], headers=device["headers"])
    assert resp.status_code == 413, resp.text


async def test_recording_broadcasts_to_the_lecturer_channel(
    client, classroom, device, db_session, fixed_clock, monkeypatch
):
    student_id = classroom["student_ids"][0]
    await enrol_faces(db_session, {student_id: 0})
    VECS[b"A"] = unit(0)
    session_id = await open_session(classroom, device["id"])

    sent: list[tuple[int, dict]] = []

    async def capture(channel_session_id: int, payload: dict) -> None:
        sent.append((channel_session_id, payload))

    monkeypatch.setattr(attendance_service.manager, "broadcast", capture)

    for second in (0, 1):
        fixed_clock(at(8, 5, second))
        assert (await post(client, device, b"A")).status_code == 200
    assert [p for _, p in sent if p["event"] == "attendance_update"] == []

    fixed_clock(at(8, 5, 2))
    assert (await post(client, device, b"A")).status_code == 200
    updates = [(sid, p) for sid, p in sent if p["event"] == "attendance_update"]
    assert len(updates) == 1
    channel_session_id, payload = updates[0]
    assert channel_session_id == session_id
    assert payload["student"]["id"] == student_id
    assert payload["student"]["status"] == "present"
