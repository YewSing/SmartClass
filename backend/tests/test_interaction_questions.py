"""Tests for interaction questions (FR-502, FR-503, FR-509 part, S21).

Covers: ask a question (anonymous + named), identity always stored but stripped when
anonymous, ask only while open and only when enrolled, lecturer list, mark answered,
and the question_asked websocket broadcast.
"""

import pytest

from app.core.security import create_access_token
from app.main import app
from app.models.interaction_question import InteractionQuestion
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


async def _ask(client, interaction_id: int, text: str, anonymous: bool):
    return await client.post(
        f"/student/interactions/{interaction_id}/questions",
        json={"text": text, "anonymous": anonymous},
    )


async def _open_interaction(client, occurrence_id: int) -> int:
    resp = await client.post("/lecturer/interactions", json={"occurrence_id": occurrence_id})
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


# ── ask a question ──────────────────────────────────────────────────────────

async def test_student_asks_named_question(lecturer_client, student_client, classroom):
    interaction_id = await _open_interaction(lecturer_client, classroom["occurrence_id"])

    resp = await _ask(student_client, interaction_id, "Is the exam optional?", anonymous=False)
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["text"] == "Is the exam optional?"
    assert body["anonymous"] is False
    assert body["answered"] is False
    assert body["student_id"] is not None          # identity stored
    assert body["student_name"] == "Test Student"


async def test_student_asks_anonymous_question_strips_identity(
    lecturer_client, student_client, classroom, db_session
):
    interaction_id = await _open_interaction(lecturer_client, classroom["occurrence_id"])

    resp = await _ask(student_client, interaction_id, "Can we reschedule?", anonymous=True)
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["anonymous"] is True
    assert body["student_id"] is None              # stripped from the response
    assert body["student_name"] is None

    # Identity is still stored in the DB (FR-509 counting).
    q = await db_session.get(InteractionQuestion, body["id"])
    assert q.student_id == classroom["student_ids"][0]
    assert q.anonymous is True


async def test_lecturer_view_strips_anonymous_identity(
    lecturer_client, student_client, classroom, db_session
):
    interaction_id = await _open_interaction(lecturer_client, classroom["occurrence_id"])
    await _ask(student_client, interaction_id, "anonymous one", anonymous=True)
    await _ask(student_client, interaction_id, "named one", anonymous=False)

    resp = await lecturer_client.get(
        f"/lecturer/interactions/{interaction_id}/questions"
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert len(body) == 2
    anonymous_q = [q for q in body if q["text"] == "anonymous one"][0]
    named_q = [q for q in body if q["text"] == "named one"][0]
    assert anonymous_q["anonymous"] is True
    assert anonymous_q["student_id"] is None       # stripped for lecturer too
    assert anonymous_q["student_name"] is None
    assert named_q["anonymous"] is False
    assert named_q["student_id"] is not None
    assert named_q["student_name"] == "Test Student"


async def test_ask_while_closed_is_409(lecturer_client, student_client, classroom):
    interaction_id = await _open_interaction(lecturer_client, classroom["occurrence_id"])
    await lecturer_client.post(f"/lecturer/interactions/{interaction_id}/close")

    resp = await _ask(student_client, interaction_id, "too late", anonymous=False)
    assert resp.status_code == 409, resp.text


async def test_ask_not_enrolled_is_403(student_client, other_lecturer_client, classroom):
    # other_lecturer's class CS202; student_client is not enrolled.
    interaction_id = await _open_interaction(other_lecturer_client, classroom["other_occurrence_id"])
    resp = await _ask(student_client, interaction_id, "not enrolled", anonymous=False)
    assert resp.status_code == 403, resp.text


async def test_ask_unknown_interaction_is_404(student_client):
    resp = await _ask(student_client, 999999, "hello", anonymous=False)
    assert resp.status_code == 404


async def test_lecturer_cannot_ask(lecturer_client, classroom):
    # lecturer role is not allowed on the student endpoint
    interaction_id = await _open_interaction(lecturer_client, classroom["occurrence_id"])
    resp = await _ask(lecturer_client, interaction_id, "lecturer asking", anonymous=False)
    assert resp.status_code == 403


# ── lecturer list / mark answered ──────────────────────────────────────────

async def test_lecturer_lists_questions(lecturer_client, student_client, classroom):
    interaction_id = await _open_interaction(lecturer_client, classroom["occurrence_id"])
    await _ask(student_client, interaction_id, "q1", anonymous=False)
    await _ask(student_client, interaction_id, "q2", anonymous=True)

    resp = await lecturer_client.get(f"/lecturer/interactions/{interaction_id}/questions")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert [q["text"] for q in body] == ["q2", "q1"]   # newest first


async def test_other_lecturer_cannot_list(other_lecturer_client, lecturer_client, classroom):
    interaction_id = await _open_interaction(lecturer_client, classroom["occurrence_id"])
    resp = await other_lecturer_client.get(f"/lecturer/interactions/{interaction_id}/questions")
    assert resp.status_code == 403, resp.text


async def test_mark_question_answered(lecturer_client, student_client, classroom):
    interaction_id = await _open_interaction(lecturer_client, classroom["occurrence_id"])
    resp = await _ask(student_client, interaction_id, "please answer", anonymous=False)
    question_id = resp.json()["id"]

    resp = await lecturer_client.post(
        f"/lecturer/interactions/{interaction_id}/questions/{question_id}/answered"
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["answered"] is True
    assert body["answered_by"] is not None
    assert body["answered_at"] is not None


async def test_mark_answered_twice_is_409(lecturer_client, student_client, classroom):
    interaction_id = await _open_interaction(lecturer_client, classroom["occurrence_id"])
    resp = await _ask(student_client, interaction_id, "q", anonymous=False)
    question_id = resp.json()["id"]
    await lecturer_client.post(
        f"/lecturer/interactions/{interaction_id}/questions/{question_id}/answered"
    )
    resp = await lecturer_client.post(
        f"/lecturer/interactions/{interaction_id}/questions/{question_id}/answered"
    )
    assert resp.status_code == 409, resp.text


async def test_mark_unknown_question_is_404(lecturer_client, classroom):
    interaction_id = await _open_interaction(lecturer_client, classroom["occurrence_id"])
    resp = await lecturer_client.post(
        f"/lecturer/interactions/{interaction_id}/questions/999999/answered"
    )
    assert resp.status_code == 404


# ── websocket broadcast ─────────────────────────────────────────────────────

async def test_question_asked_broadcast_on_room(users, classroom, lecturer_client, student_client):
    interaction_id = await _open_interaction(lecturer_client, classroom["occurrence_id"])

    async with InteractionRoom(
        interaction_id, create_access_token(users["student"].id, "student")
    ) as room:
        await _ask(student_client, interaction_id, "broadcast me", anonymous=False)

        events = [e["event"] for e in room.sent]
        assert "question_asked" in events, events
        q_event = [e for e in room.sent if e["event"] == "question_asked"][0]
        assert q_event["interaction_id"] == interaction_id
        assert q_event["question_id"] is not None
        assert q_event["anonymous"] is False


# ── S28: session-wide question feed + question_answered broadcast ────────────


async def test_student_state_lists_all_session_questions(
    lecturer_client, student_client, classroom, users, db_session
):
    """The student state endpoint now carries every question of the session (FR-502/503),
    newest first, answered flag included; anonymous identity stays hidden."""
    interaction_id = await _open_interaction(lecturer_client, classroom["occurrence_id"])

    r1 = await _ask(student_client, interaction_id, "first question", anonymous=False)
    assert r1.status_code == 201
    # A second student (if the fixture has one) asks anonymously.
    second = users.get("student2")
    if second:
        async with _AuthedClient(create_access_token(second.id, "student")) as c2:
            await _ask(c2, interaction_id, "someone else asks", anonymous=True)

    resp = await student_client.get(f"/student/interactions/{interaction_id}")
    assert resp.status_code == 200, resp.text
    feed = resp.json()["questions"]
    assert [q["text"] for q in feed][0] == ("someone else asks" if second else "first question")
    for q in feed:
        if q["anonymous"]:
            assert q["student_id"] is None and q["student_name"] is None


async def test_mark_answered_broadcasts_question_answered(
    users, lecturer_client, student_client, classroom
):
    """Marking answered now notifies the room, so student screens update live."""
    interaction_id = await _open_interaction(lecturer_client, classroom["occurrence_id"])
    resp = await _ask(student_client, interaction_id, "please answer", anonymous=False)
    question_id = resp.json()["id"]

    async with InteractionRoom(
        interaction_id, create_access_token(users["student"].id, "student")
    ) as room:
        mark = await lecturer_client.post(
            f"/lecturer/interactions/{interaction_id}/questions/{question_id}/answered"
        )
        assert mark.status_code == 200, mark.text

        events = [e["event"] for e in room.sent]
        assert "question_answered" in events, events
        ev = [e for e in room.sent if e["event"] == "question_answered"][0]
        assert ev["question_id"] == question_id
