"""Tests for live polls (FR-504, FR-505, FR-509 part, S22).

Covers: lecturer creates a poll (2+ options, 422 with fewer), student votes at most once
per poll while open (second vote 409), only while open/enrolled, live per-option results
for the lecturer, and the poll_created / poll_vote websocket broadcasts.
"""

import pytest
from fastapi import WebSocketDisconnect
from sqlalchemy import select

from app.core.security import create_access_token
from app.main import app
from app.models.interaction_poll import InteractionPollVote
from app.websocket.router import interaction_ws
from httpx import ASGITransport, AsyncClient
from ws_room import InteractionRoom

pytestmark = pytest.mark.db


class _AuthedClient:
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


async def _open_interaction(client, occurrence_id: int) -> int:
    resp = await client.post("/lecturer/interactions", json={"occurrence_id": occurrence_id})
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


async def _create_poll(client, interaction_id: int, question: str, options: list[str]):
    return await client.post(
        f"/lecturer/interactions/{interaction_id}/polls",
        json={"question": question, "options": options},
    )


async def _vote(client, poll_id: int, option_id: int):
    return await client.post(f"/student/polls/{poll_id}/vote", json={"option_id": option_id})


# ── create a poll ───────────────────────────────────────────────────────────

async def test_lecturer_creates_poll(lecturer_client, classroom):
    interaction_id = await _open_interaction(lecturer_client, classroom["occurrence_id"])

    resp = await _create_poll(lecturer_client, interaction_id, "Ready for the quiz?", ["Yes", "No", "Maybe"])
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["question"] == "Ready for the quiz?"
    assert body["is_open"] is True
    assert [o["option_text"] for o in body["options"]] == ["Yes", "No", "Maybe"]
    assert all(o["votes"] == 0 for o in body["options"])
    assert body["opened_by"] is not None


async def test_create_poll_fewer_than_two_options_is_422(lecturer_client, classroom):
    interaction_id = await _open_interaction(lecturer_client, classroom["occurrence_id"])

    resp = await _create_poll(lecturer_client, interaction_id, "Only one?", ["Yes"])
    assert resp.status_code == 422, resp.text


async def test_create_poll_unknown_interaction_is_404(lecturer_client):
    resp = await _create_poll(lecturer_client, 999999, "q", ["A", "B"])
    assert resp.status_code == 404


async def test_create_poll_closed_session_is_409(lecturer_client, classroom):
    interaction_id = await _open_interaction(lecturer_client, classroom["occurrence_id"])
    await lecturer_client.post(f"/lecturer/interactions/{interaction_id}/close")

    resp = await _create_poll(lecturer_client, interaction_id, "too late", ["A", "B"])
    assert resp.status_code == 409, resp.text


async def test_create_poll_other_lecturer_is_403(lecturer_client, other_lecturer_client, classroom):
    interaction_id = await _open_interaction(lecturer_client, classroom["occurrence_id"])
    resp = await _create_poll(other_lecturer_client, interaction_id, "not my class", ["A", "B"])
    assert resp.status_code == 403, resp.text


# ── vote ────────────────────────────────────────────────────────────────────

async def test_student_votes_once_per_poll(lecturer_client, student_client, classroom, db_session):
    interaction_id = await _open_interaction(lecturer_client, classroom["occurrence_id"])
    resp = await _create_poll(lecturer_client, interaction_id, "Ready?", ["Yes", "No"])
    poll_id = resp.json()["id"]
    option_ids = [o["id"] for o in resp.json()["options"]]

    r1 = await _vote(student_client, poll_id, option_ids[0])
    assert r1.status_code == 201, r1.text

    r2 = await _vote(student_client, poll_id, option_ids[1])
    assert r2.status_code == 409, r2.text

    vote = await db_session.execute(
        select(InteractionPollVote).where(InteractionPollVote.student_id == classroom["student_ids"][0])
    )
    assert vote.scalar_one() is not None


async def test_vote_while_closed_is_409(lecturer_client, student_client, classroom):
    interaction_id = await _open_interaction(lecturer_client, classroom["occurrence_id"])
    resp = await _create_poll(lecturer_client, interaction_id, "q", ["A", "B"])
    poll_id = resp.json()["id"]
    option_ids = [o["id"] for o in resp.json()["options"]]
    await lecturer_client.post(f"/lecturer/interactions/{interaction_id}/close")

    resp = await _vote(student_client, poll_id, option_ids[0])
    assert resp.status_code == 409, resp.text


async def test_vote_not_enrolled_is_403(student_client, classroom, other_lecturer_client):
    interaction_id = await _open_interaction(other_lecturer_client, classroom["other_occurrence_id"])
    resp = await _create_poll(other_lecturer_client, interaction_id, "q", ["A", "B"])
    poll_id = resp.json()["id"]
    option_ids = [o["id"] for o in resp.json()["options"]]

    resp = await _vote(student_client, poll_id, option_ids[0])
    assert resp.status_code == 403, resp.text


async def test_vote_unknown_poll_is_404(student_client):
    resp = await _vote(student_client, 999999, 1)
    assert resp.status_code == 404


async def test_vote_unknown_option_is_404(lecturer_client, student_client, classroom):
    interaction_id = await _open_interaction(lecturer_client, classroom["occurrence_id"])
    resp = await _create_poll(lecturer_client, interaction_id, "q", ["A", "B"])
    poll_id = resp.json()["id"]

    resp = await _vote(student_client, poll_id, 999999)
    assert resp.status_code == 404


# ── lecturer list with live results ─────────────────────────────────────────

async def test_lecturer_sees_poll_results(lecturer_client, student_client, classroom, db_session):
    interaction_id = await _open_interaction(lecturer_client, classroom["occurrence_id"])
    resp = await _create_poll(lecturer_client, interaction_id, "Ready?", ["Yes", "No"])
    poll_id = resp.json()["id"]
    option_ids = [o["id"] for o in resp.json()["options"]]

    await _vote(student_client, poll_id, option_ids[0])

    resp = await lecturer_client.get(f"/lecturer/interactions/{interaction_id}/polls")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert len(body) == 1
    poll = body[0]
    assert poll["id"] == poll_id
    votes = {o["option_text"]: o["votes"] for o in poll["options"]}
    assert votes["Yes"] == 1
    assert votes["No"] == 0


async def test_other_lecturer_cannot_list_polls(other_lecturer_client, lecturer_client, classroom):
    interaction_id = await _open_interaction(lecturer_client, classroom["occurrence_id"])
    resp = await other_lecturer_client.get(f"/lecturer/interactions/{interaction_id}/polls")
    assert resp.status_code == 403, resp.text


# ── websocket broadcasts ────────────────────────────────────────────────────

async def test_poll_created_broadcast(users, lecturer_client, classroom):
    interaction_id = await _open_interaction(lecturer_client, classroom["occurrence_id"])

    async with InteractionRoom(
        interaction_id, create_access_token(users["lecturer"].id, "lecturer")
    ) as room:
        await _create_poll(lecturer_client, interaction_id, "broadcast me", ["A", "B"])

        events = [e["event"] for e in room.sent]
        assert "poll_created" in events, events
        ev = [e for e in room.sent if e["event"] == "poll_created"][0]
        assert ev["interaction_id"] == interaction_id
        assert ev["question"] == "broadcast me"


async def test_poll_vote_broadcast(users, lecturer_client, student_client, classroom):
    interaction_id = await _open_interaction(lecturer_client, classroom["occurrence_id"])
    resp = await _create_poll(lecturer_client, interaction_id, "q", ["A", "B"])
    poll_id = resp.json()["id"]
    option_ids = [o["id"] for o in resp.json()["options"]]

    async with InteractionRoom(
        interaction_id, create_access_token(users["lecturer"].id, "lecturer")
    ) as room:
        await _vote(student_client, poll_id, option_ids[0])

        events = [e["event"] for e in room.sent]
        assert "poll_vote" in events, events
        ev = [e for e in room.sent if e["event"] == "poll_vote"][0]
        assert ev["poll_id"] == poll_id
        assert ev["option_id"] == option_ids[0]
