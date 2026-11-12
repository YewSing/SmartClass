"""T41: the real InsightFace model on the bundled sample photo (FR-402–FR-405, NFR-10).

Faces come from InsightFace's `t1.jpg`, cropped at test time (tests/card_images.py); nothing is
written to disk or committed. Skips when insightface or buffalo_sc is missing (conftest).
"""
import time
from datetime import date, datetime

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
from app.services import face_service, recognition_service, session_schedule
from tests import card_images

pytestmark = [pytest.mark.db, pytest.mark.face]

MON = date(2026, 11, 16)
URL = "/device/faces"


def at(h: int, m: int, s: int = 0) -> datetime:
    return datetime(2026, 11, 16, h, m, s)


@pytest.fixture(scope="module")
def real_face():
    from insightface.app import FaceAnalysis

    fa = FaceAnalysis(name=settings.INSIGHTFACE_MODEL, providers=["CPUExecutionProvider"])
    fa.prepare(ctx_id=-1, det_size=(640, 640))
    people = card_images.people(fa)
    return fa, card_images, people


@pytest.fixture(scope="module")
def enrolment_embeddings(real_face):
    """One averaged embedding per person, built from selfies (as the student app would)."""
    fa, ci, people = real_face
    return {
        index: face_service.average_embeddings(
            [face_service.extract_embeddings(fa, selfie)[0] for selfie in ci.selfies(person)])
        for index, person in enumerate(people[:2])
    }


@pytest.fixture(autouse=True)
def _state(real_face, monkeypatch):
    fa, _, _ = real_face
    recognition_service.reset_votes()
    monkeypatch.setattr(app.state, "face_app", fa, raising=False)
    yield
    recognition_service.reset_votes()


@pytest.fixture
def fixed_clock(monkeypatch):
    def set_clock(t: datetime) -> None:
        monkeypatch.setattr(session_schedule, "clock", lambda: t)
    return set_clock


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


@pytest.fixture
async def enrolled(db_session, classroom, outsider, enrolment_embeddings) -> None:
    """Person 0 is the enrolled student; person 1 is a student from another class."""
    db_session.add_all([
        FaceEmbedding(student_id=classroom["student_ids"][0],
                      embedding=enrolment_embeddings[0].tolist()),
        FaceEmbedding(student_id=outsider, embedding=enrolment_embeddings[1].tolist()),
    ])
    await db_session.commit()


async def open_session(classroom: dict, camera_id: int | None) -> int:
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


async def records_for(db, session_id: int) -> list[AttendanceRecord]:
    db.expire_all()
    return (await db.execute(
        select(AttendanceRecord).where(AttendanceRecord.session_id == session_id)
        .order_by(AttendanceRecord.student_id)
    )).scalars().all()


async def test_real_face_votes_then_records_present_once(
    client, classroom, device, db_session, fixed_clock, real_face, enrolled
):
    _, ci, people = real_face
    probe = ci._png(people[0])
    session_id = await open_session(classroom, device["id"])

    results = []
    for second in (0, 1, 2, 3):
        fixed_clock(at(8, 5, second))
        started = time.perf_counter()
        resp = await post(client, device, probe)
        elapsed = time.perf_counter() - started
        assert resp.status_code == 200, resp.text
        results.append(resp.json()["results"][0])
        if second == 2:
            assert elapsed < 2.0, f"the recording request took {elapsed:.2f} s (NFR-10)"

    assert [r["outcome"] for r in results] == ["voting", "voting", "recorded", "already_recorded"]
    assert [r["votes"] for r in results[:3]] == [1, 2, 3]
    assert results[2]["student_id"] == classroom["student_ids"][0]
    assert results[2]["status"] == "present"
    assert results[2]["similarity"] >= settings.FACE_MATCH_THRESHOLD

    [record] = await records_for(db_session, session_id)
    assert record.status == "present"
    assert record.camera_id == device["id"]


async def test_real_late_arrival(
    client, classroom, device, db_session, fixed_clock, real_face, enrolled
):
    _, ci, people = real_face
    probe = ci._png(people[0])
    session_id = await open_session(classroom, device["id"])

    for second in (0, 1, 2):
        fixed_clock(at(8, 20, second))
        resp = await post(client, device, probe)
        assert resp.status_code == 200, resp.text

    assert resp.json()["results"][0]["outcome"] == "recorded"
    assert resp.json()["results"][0]["status"] == "late"
    [record] = await records_for(db_session, session_id)
    assert record.status == "late"


async def test_real_stranger_is_below_threshold(
    client, classroom, device, db_session, fixed_clock, real_face, enrolled
):
    _, ci, people = real_face
    stranger = ci._png(people[2])
    session_id = await open_session(classroom, device["id"])

    fixed_clock(at(8, 5, 0))
    resp = await post(client, device, stranger)
    assert resp.status_code == 200, resp.text
    [result] = resp.json()["results"]
    assert result["outcome"] == "below_threshold"
    assert result["similarity"] < settings.FACE_MATCH_THRESHOLD
    assert result["student_id"] is None
    assert await records_for(db_session, session_id) == []


async def test_real_not_enrolled_student_is_not_recorded(
    client, classroom, device, db_session, fixed_clock, real_face, enrolled
):
    _, ci, people = real_face
    probe = ci._png(people[1])
    session_id = await open_session(classroom, device["id"])

    for second in (0, 1, 2):
        fixed_clock(at(8, 5, second))
        resp = await post(client, device, probe)
        assert resp.status_code == 200, resp.text
        [result] = resp.json()["results"]
        assert result["outcome"] == "not_enrolled"
        assert result["student_id"] is None

    assert await records_for(db_session, session_id) == []
