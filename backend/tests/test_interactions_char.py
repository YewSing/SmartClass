"""Characterisation + tests for the interaction session lifecycle (FR-501, S20).

Covers: open / close / list interaction sessions, enrolment + access control (NFR-04),
and the per-interaction websocket room (open/close announced after commit).
No production code changes beyond S20's own router/model/migration.
"""

import pytest
from fastapi import WebSocketDisconnect
from sqlalchemy import select

from app.core.security import create_access_token
from app.main import app
from app.models.interaction import InteractionSession
from app.websocket.router import interaction_ws
from httpx import ASGITransport, AsyncClient
from ws_room import InteractionRoom

pytestmark = pytest.mark.db


async def _open_interaction(client, occurrence_id: int) -> int:
    resp = await client.post("/lecturer/interactions", json={"occurrence_id": occurrence_id})
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


async def _close_interaction(client, interaction_id: int):
    return await client.post(f"/lecturer/interactions/{interaction_id}/close")


class _AuthedClient:
    """An httpx AsyncClient against the real app with a given access token."""

    def __init__(self, token: str):
        self.token = token

    async def __aenter__(self):
        self.client = AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            headers={"Authorization": f"Bearer {self.token}"},
        )
        await self.client.__aenter__()
        return self.client

    async def __aexit__(self, *exc):
        return await self.client.__aexit__(*exc)


class _FakeWebSocket:
    """Runs the real endpoint with real auth and DB; disconnects after the first message."""

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


async def _connect_interaction_ws(interaction_id: int, token: str):
    ws = _FakeWebSocket()
    await interaction_ws(interaction_id, ws, token=token)
    return ws


# ── HTTP lifecycle ──────────────────────────────────────────────────────────

async def test_open_interaction_for_taught_class(lecturer_client, classroom, db_session):
    interaction_id = await _open_interaction(lecturer_client, classroom["occurrence_id"])

    resp = await lecturer_client.get(
        "/lecturer/interactions", params={"occurrence_id": classroom["occurrence_id"]}
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert len(body) == 1
    assert body[0]["id"] == interaction_id
    assert body[0]["status"] == "open"
    assert body[0]["occurrence_id"] == classroom["occurrence_id"]
    assert body[0]["class_code"] == "CS101"
    assert body[0]["closed_by"] is None and body[0]["closed_at"] is None

    row = await db_session.get(InteractionSession, interaction_id)
    assert row.status == "open"
    assert row.opened_by is not None


async def test_open_interaction_unknown_occurrence_is_404(lecturer_client):
    resp = await lecturer_client.post("/lecturer/interactions", json={"occurrence_id": 999999})
    assert resp.status_code == 404


async def test_open_interaction_other_lecturer_is_403(other_lecturer_client, classroom, db_session):
    resp = await other_lecturer_client.post(
        "/lecturer/interactions", json={"occurrence_id": classroom["occurrence_id"]}
    )
    assert resp.status_code == 403, resp.text
    assert (await db_session.execute(select(InteractionSession))).scalars().all() == []


async def test_open_interaction_admin_is_403(admin_client, classroom):
    resp = await admin_client.post("/lecturer/interactions", json={"occurrence_id": classroom["occurrence_id"]})
    assert resp.status_code == 403


async def test_open_interaction_student_is_403(student_client, classroom):
    resp = await student_client.post("/lecturer/interactions", json={"occurrence_id": classroom["occurrence_id"]})
    assert resp.status_code == 403


async def test_close_interaction(lecturer_client, classroom, db_session):
    interaction_id = await _open_interaction(lecturer_client, classroom["occurrence_id"])

    resp = await _close_interaction(lecturer_client, interaction_id)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["id"] == interaction_id
    assert body["status"] == "closed"
    assert body["closed_by"] is not None
    assert body["closed_at"] is not None

    row = await db_session.get(InteractionSession, interaction_id)
    assert row.status == "closed"
    assert row.closed_at is not None


async def test_close_interaction_already_closed_is_409(lecturer_client, classroom):
    interaction_id = await _open_interaction(lecturer_client, classroom["occurrence_id"])
    await _close_interaction(lecturer_client, interaction_id)

    resp = await _close_interaction(lecturer_client, interaction_id)
    assert resp.status_code == 409, resp.text


async def test_close_interaction_other_lecturer_is_403(lecturer_client, other_lecturer_client, classroom, db_session):
    interaction_id = await _open_interaction(lecturer_client, classroom["occurrence_id"])

    resp = await _close_interaction(other_lecturer_client, interaction_id)
    assert resp.status_code == 403, resp.text

    row = await db_session.get(InteractionSession, interaction_id)
    assert row.status == "open"


async def test_close_unknown_interaction_is_404(lecturer_client):
    resp = await _close_interaction(lecturer_client, 999999)
    assert resp.status_code == 404


async def test_list_interactions_newest_first(lecturer_client, classroom):
    first = await _open_interaction(lecturer_client, classroom["occurrence_id"])
    second = await _open_interaction(lecturer_client, classroom["occurrence_id"])

    resp = await lecturer_client.get(
        "/lecturer/interactions", params={"occurrence_id": classroom["occurrence_id"]}
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert [b["id"] for b in body] == [second, first]
    assert all(b["status"] == "open" for b in body)


async def test_list_interactions_other_lecturer_is_403(other_lecturer_client, classroom):
    resp = await other_lecturer_client.get(
        "/lecturer/interactions", params={"occurrence_id": classroom["occurrence_id"]}
    )
    assert resp.status_code == 403


async def test_list_interactions_requires_occurrence_id(lecturer_client):
    resp = await lecturer_client.get("/lecturer/interactions")
    assert resp.status_code == 422


# ── websocket room ──────────────────────────────────────────────────────────

async def _lecturer_token() -> str:
    return create_access_token("user-lecturer", "lecturer")  # replaced by caller with real id


async def test_interaction_ws_teaching_lecturer_can_connect(users, classroom):
    async with _AuthedClient(create_access_token(users["lecturer"].id, "lecturer")) as c:
        interaction_id = await _open_interaction(c, classroom["occurrence_id"])

    ws = await _connect_interaction_ws(interaction_id, create_access_token(users["lecturer"].id, "lecturer"))
    assert ws.closed_code is None, ws.sent


async def test_interaction_ws_other_lecturer_rejected(users, classroom):
    async with _AuthedClient(create_access_token(users["lecturer"].id, "lecturer")) as c:
        interaction_id = await _open_interaction(c, classroom["occurrence_id"])

    ws = await _connect_interaction_ws(interaction_id, create_access_token(classroom["other_lecturer_user_id"], "lecturer"))
    assert ws.closed_code == 1008
    assert ws.sent == []


async def test_interaction_ws_enrolled_student_can_connect(users, classroom):
    async with _AuthedClient(create_access_token(users["lecturer"].id, "lecturer")) as c:
        interaction_id = await _open_interaction(c, classroom["occurrence_id"])

    ws = await _connect_interaction_ws(interaction_id, create_access_token(users["student"].id, "student"))
    assert ws.closed_code is None, ws.sent


async def test_interaction_close_announced_on_websocket_room(users, classroom):
    """Closing an interaction broadcasts interaction_closed to a connected room member."""
    async with _AuthedClient(create_access_token(users["lecturer"].id, "lecturer")) as c:
        interaction_id = await _open_interaction(c, classroom["occurrence_id"])

    async with InteractionRoom(
        interaction_id,
        create_access_token(users["lecturer"].id, "lecturer"),
    ) as room:
        async with _AuthedClient(create_access_token(users["lecturer"].id, "lecturer")) as c:
            resp = await _close_interaction(c, interaction_id)
        assert resp.status_code == 200, resp.text

        events = [e["event"] for e in room.sent]
        assert "interaction_closed" in events, events
        closed = [e for e in room.sent if e["event"] == "interaction_closed"][0]
        assert closed["interaction_id"] == interaction_id
        assert closed["status"] == "closed"


# ── open-sessions list for the Home card (S26) ──────────────────────────────

async def test_list_open_interactions_across_classes(lecturer_client, classroom, db_session):
    """GET /lecturer/interactions/open returns open sessions across the lecturer's classes."""
    interaction_id = await _open_interaction(lecturer_client, classroom["occurrence_id"])

    resp = await lecturer_client.get("/lecturer/interactions/open")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert len(body) == 1
    assert body[0]["id"] == interaction_id
    assert body[0]["status"] == "open"
    assert body[0]["occurrence_id"] == classroom["occurrence_id"]
    assert body[0]["class_code"] == "CS101"


async def test_open_interactions_exclude_closed(lecturer_client, classroom):
    interaction_id = await _open_interaction(lecturer_client, classroom["occurrence_id"])
    await _close_interaction(lecturer_client, interaction_id)

    resp = await lecturer_client.get("/lecturer/interactions/open")
    assert resp.status_code == 200, resp.text
    assert all(b["id"] != interaction_id for b in resp.json())


async def test_open_interactions_other_lecturer_sees_nothing(other_lecturer_client, classroom):
    """NFR-04: another lecturer's open sessions never appear in my list."""
    resp = await other_lecturer_client.get("/lecturer/interactions/open")
    assert resp.status_code == 200, resp.text
    assert resp.json() == []


async def test_open_interactions_student_403(student_client, classroom):
    resp = await student_client.get("/lecturer/interactions/open")
    assert resp.status_code == 403


# ── close poll (FR-504, S22/S26) ────────────────────────────────────────────

async def _create_poll(client, interaction_id: int, n: int = 2) -> int:
    resp = await client.post(
        f"/lecturer/interactions/{interaction_id}/polls",
        json={"question": "Pick one", "options": [f"opt{i}" for i in range(n)]},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


async def test_close_poll(lecturer_client, classroom, db_session):
    interaction_id = await _open_interaction(lecturer_client, classroom["occurrence_id"])
    poll_id = await _create_poll(lecturer_client, interaction_id)

    resp = await lecturer_client.post(
        f"/lecturer/interactions/{interaction_id}/polls/{poll_id}/close"
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["is_open"] is False
    assert body["closed_by"] is not None and body["closed_at"] is not None

    # The session itself is still open — closing a poll must not close the session (UC-501).
    open_list = (await lecturer_client.get("/lecturer/interactions/open")).json()
    assert any(b["id"] == interaction_id for b in open_list)


async def test_close_poll_twice_is_409(lecturer_client, classroom):
    interaction_id = await _open_interaction(lecturer_client, classroom["occurrence_id"])
    poll_id = await _create_poll(lecturer_client, interaction_id)
    await lecturer_client.post(f"/lecturer/interactions/{interaction_id}/polls/{poll_id}/close")

    resp = await lecturer_client.post(
        f"/lecturer/interactions/{interaction_id}/polls/{poll_id}/close"
    )
    assert resp.status_code == 409


async def test_close_poll_other_lecturer_is_403(lecturer_client, other_lecturer_client, classroom):
    interaction_id = await _open_interaction(lecturer_client, classroom["occurrence_id"])
    poll_id = await _create_poll(lecturer_client, interaction_id)

    resp = await other_lecturer_client.post(
        f"/lecturer/interactions/{interaction_id}/polls/{poll_id}/close"
    )
    assert resp.status_code == 403


async def test_close_poll_unknown_is_404(lecturer_client, classroom):
    interaction_id = await _open_interaction(lecturer_client, classroom["occurrence_id"])
    resp = await lecturer_client.post(
        f"/lecturer/interactions/{interaction_id}/polls/999999/close"
    )
    assert resp.status_code == 404


async def test_close_poll_broadcast_on_room(users, classroom):
    """Closing a poll announces poll_closed to the room."""
    async with _AuthedClient(create_access_token(users["lecturer"].id, "lecturer")) as c:
        interaction_id = await _open_interaction(c, classroom["occurrence_id"])
        poll_id = await _create_poll(c, interaction_id)

    async with InteractionRoom(
        interaction_id, create_access_token(users["lecturer"].id, "lecturer")
    ) as room:
        async with _AuthedClient(create_access_token(users["lecturer"].id, "lecturer")) as c:
            resp = await c.post(f"/lecturer/interactions/{interaction_id}/polls/{poll_id}/close")
        assert resp.status_code == 200, resp.text

        events = [e["event"] for e in room.sent]
        assert "poll_closed" in events, events
