"""NFR-04: lecturer session endpoints are for the lecturer who teaches that class, and nobody else."""
import pytest
from fastapi import WebSocketDisconnect
from sqlalchemy import select

from app.core.security import create_access_token
from app.models.attendance import AttendanceRecord
from app.models.session import AttendanceSession
from app.websocket.router import attendance_ws

pytestmark = pytest.mark.db


@pytest.fixture
async def session_setup(lecturer_client, classroom, db_session) -> dict:
    """An open CS101 session owned by the test lecturer, with one 'absent' record."""
    resp = await lecturer_client.post("/lecturer/sessions", json={"occurrence_id": classroom["occurrence_id"]})
    assert resp.status_code == 201, resp.text
    session_id = resp.json()["id"]
    record = AttendanceRecord(session_id=session_id, student_id=classroom["student_ids"][0], status="absent")
    db_session.add(record)
    await db_session.commit()
    return {"session_id": session_id, "record_id": record.id, "student_id": classroom["student_ids"][0]}


def _requests(setup: dict, classroom: dict) -> dict[str, tuple[str, str, dict | None]]:
    sid = setup["session_id"]
    return {
        "close": ("PUT", f"/lecturer/sessions/{sid}/close", None),
        "roster": ("GET", f"/lecturer/sessions/{sid}/attendance", None),
        "record_override": ("PUT", f"/attendance/{setup['record_id']}/override", {"status": "present"}),
        "session_override": ("PUT", f"/lecturer/sessions/{sid}/attendance/override",
                             {"student_id": setup["student_id"], "status": "present"}),
        "session_export": ("GET", f"/lecturer/sessions/{sid}/export", None),
        "occurrence_export": ("GET", f"/lecturer/occurrences/{classroom['occurrence_id']}/attendance/export", None),
    }


ENDPOINTS = ["close", "roster", "record_override", "session_override", "session_export", "occurrence_export"]


async def _assert_untouched(db, setup: dict) -> None:
    db.expire_all()
    session = await db.get(AttendanceSession, setup["session_id"])
    assert session.status == "open"
    record = (await db.execute(select(AttendanceRecord).where(AttendanceRecord.id == setup["record_id"]))).scalar_one()
    assert record.status == "absent"
    assert record.override_by is None


@pytest.mark.parametrize("endpoint", ENDPOINTS)
async def test_other_lecturer_gets_403(other_lecturer_client, classroom, session_setup, db_session, endpoint):
    method, url, body = _requests(session_setup, classroom)[endpoint]
    resp = await other_lecturer_client.request(method, url, json=body)
    assert resp.status_code == 403, resp.text
    await _assert_untouched(db_session, session_setup)


@pytest.mark.parametrize("endpoint", ENDPOINTS)
async def test_admin_gets_403(admin_client, classroom, session_setup, db_session, endpoint):
    method, url, body = _requests(session_setup, classroom)[endpoint]
    resp = await admin_client.request(method, url, json=body)
    assert resp.status_code == 403, resp.text
    await _assert_untouched(db_session, session_setup)


@pytest.mark.parametrize("endpoint", ENDPOINTS)
async def test_teaching_lecturer_is_allowed(lecturer_client, classroom, session_setup, endpoint):
    method, url, body = _requests(session_setup, classroom)[endpoint]
    resp = await lecturer_client.request(method, url, json=body)
    assert resp.status_code == 200, resp.text


async def test_other_lecturer_cannot_open_session_for_a_class_they_dont_teach(other_lecturer_client, classroom, db_session):
    resp = await other_lecturer_client.post("/lecturer/sessions", json={"occurrence_id": classroom["occurrence_id"]})
    assert resp.status_code == 403
    assert (await db_session.execute(select(AttendanceSession))).scalars().all() == []


async def test_admin_cannot_open_session(admin_client, classroom, db_session):
    resp = await admin_client.post("/lecturer/sessions", json={"occurrence_id": classroom["occurrence_id"]})
    assert resp.status_code == 403
    assert (await db_session.execute(select(AttendanceSession))).scalars().all() == []


async def test_class_student_list_access(lecturer_client, other_lecturer_client, admin_client, student_client, classroom):
    url = f"/classes/{classroom['occurrence_id']}/students"
    assert (await lecturer_client.get(url)).status_code == 200
    assert (await admin_client.get(url)).status_code == 200
    assert (await other_lecturer_client.get(url)).status_code == 403
    assert (await student_client.get(url)).status_code == 403


class _FakeWebSocket:
    """Runs the real endpoint with real auth and DB; the client disconnects after the first state message."""

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


async def _connect_ws(session_id: int, token: str) -> _FakeWebSocket:
    ws = _FakeWebSocket()
    await attendance_ws(session_id, ws, token=token)
    return ws


async def test_live_feed_only_for_the_teaching_lecturer(users, classroom, session_setup):
    sid = session_setup["session_id"]

    ws = await _connect_ws(sid, create_access_token(users["lecturer"].id, "lecturer"))
    assert ws.closed_code is None
    assert ws.sent[0]["event"] == "session_state"

    for token in (
        create_access_token(classroom["other_lecturer_user_id"], "lecturer"),
        create_access_token(users["admin"].id, "admin"),
        create_access_token(users["student"].id, "student"),
    ):
        ws = await _connect_ws(sid, token)
        assert ws.closed_code == 1008
        assert ws.sent == []
