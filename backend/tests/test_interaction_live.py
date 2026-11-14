"""Tests for live question, reactions and IDU signals (FR-506, FR-507, FR-508, FR-509 part, S23).

Covers: lecturer posts a live question and sees responses in real time; students send one of
a predefined reaction set and the lecturer sees live distinct-student counts; IDU button
records at most one signal per student per session and the lecturer sees distinct students;
all writes carry session, student and timestamp; websocket broadcasts after commit.
"""

import pytest
from sqlalchemy import select

from app.core.security import create_access_token
from app.main import app
from app.models.interaction_live import (
    InteractionIDUSignal,
    InteractionReaction,
)
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


async def _open_interaction(client, occurrence_id: int) -> int:
    resp = await client.post("/lecturer/interactions", json={"occurrence_id": occurrence_id})
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


async def _ask_live(client, interaction_id: int, question: str):
    return await client.post(
        f"/lecturer/interactions/{interaction_id}/live-question",
        json={"question": question},
    )


# ── live question ───────────────────────────────────────────────────────────

async def test_lecturer_posts_live_question(lecturer_client, classroom):
    interaction_id = await _open_interaction(lecturer_client, classroom["occurrence_id"])

    resp = await _ask_live(lecturer_client, interaction_id, "Is everyone following?")
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["question"] == "Is everyone following?"
    assert body["is_active"] is True
    assert body["asked_by"] is not None
    assert body["responses"] == []


async def test_lecturer_gets_live_question_with_responses(
    lecturer_client, student_client, classroom
):
    interaction_id = await _open_interaction(lecturer_client, classroom["occurrence_id"])
    resp = await _ask_live(lecturer_client, interaction_id, "Is everyone following?")
    live_q_id = resp.json()["id"]

    await student_client.post(
        f"/student/interactions/{interaction_id}/live-question/{live_q_id}/response",
        json={"response": "Yes"},
    )

    resp = await lecturer_client.get(f"/lecturer/interactions/{interaction_id}/live-question")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["id"] == live_q_id
    assert body["is_active"] is True
    assert len(body["responses"]) == 1
    assert body["responses"][0]["response"] == "Yes"
    assert body["responses"][0]["student_id"] is not None
    assert body["responses"][0]["student_name"] == "Test Student"


async def test_student_responds_once_per_live_question(
    lecturer_client, student_client, classroom
):
    interaction_id = await _open_interaction(lecturer_client, classroom["occurrence_id"])
    resp = await _ask_live(lecturer_client, interaction_id, "q")
    live_q_id = resp.json()["id"]

    r1 = await student_client.post(
        f"/student/interactions/{interaction_id}/live-question/{live_q_id}/response",
        json={"response": "first"},
    )
    assert r1.status_code == 201, r1.text

    r2 = await student_client.post(
        f"/student/interactions/{interaction_id}/live-question/{live_q_id}/response",
        json={"response": "second"},
    )
    assert r2.status_code == 409, r2.text


async def test_respond_inactive_live_question_is_409(lecturer_client, student_client, classroom):
    interaction_id = await _open_interaction(lecturer_client, classroom["occurrence_id"])
    resp = await _ask_live(lecturer_client, interaction_id, "q1")
    live_q_id = resp.json()["id"]
    await _ask_live(lecturer_client, interaction_id, "q2")  # closes q1

    resp = await student_client.post(
        f"/student/interactions/{interaction_id}/live-question/{live_q_id}/response",
        json={"response": "late"},
    )
    assert resp.status_code == 409, resp.text


async def test_respond_not_enrolled_is_403(student_client, classroom, other_lecturer_client):
    interaction_id = await _open_interaction(other_lecturer_client, classroom["other_occurrence_id"])
    resp = await _ask_live(other_lecturer_client, interaction_id, "q")
    live_q_id = resp.json()["id"]

    resp = await student_client.post(
        f"/student/interactions/{interaction_id}/live-question/{live_q_id}/response",
        json={"response": "not enrolled"},
    )
    assert resp.status_code == 403, resp.text


async def test_other_lecturer_cannot_post_live_question(
    other_lecturer_client, lecturer_client, classroom
):
    interaction_id = await _open_interaction(lecturer_client, classroom["occurrence_id"])
    resp = await _ask_live(other_lecturer_client, interaction_id, "not my class")
    assert resp.status_code == 403, resp.text


# ── reactions ───────────────────────────────────────────────────────────────

async def test_student_sends_reaction_and_lecturer_sees_counts(
    lecturer_client, student_client, classroom, db_session
):
    interaction_id = await _open_interaction(lecturer_client, classroom["occurrence_id"])

    resp = await student_client.post(
        f"/student/interactions/{interaction_id}/reactions", json={"reaction": "confused"}
    )
    assert resp.status_code == 204, resp.text

    resp = await lecturer_client.get(f"/lecturer/interactions/{interaction_id}/reactions")
    assert resp.status_code == 200, resp.text
    counts = {c["reaction"]: c["count"] for c in resp.json()}
    assert counts == {"confused": 1}


async def test_reaction_replaces_previous_one_per_student(
    lecturer_client, student_client, classroom, db_session
):
    interaction_id = await _open_interaction(lecturer_client, classroom["occurrence_id"])

    await student_client.post(
        f"/student/interactions/{interaction_id}/reactions", json={"reaction": "confused"}
    )
    await student_client.post(
        f"/student/interactions/{interaction_id}/reactions", json={"reaction": "understood"}
    )

    resp = await lecturer_client.get(f"/lecturer/interactions/{interaction_id}/reactions")
    counts = {c["reaction"]: c["count"] for c in resp.json()}
    assert counts == {"understood": 1}
    rows = await db_session.execute(
        select(InteractionReaction).where(InteractionReaction.interaction_id == interaction_id)
    )
    assert len(rows.scalars().all()) == 1  # one row per student per session


async def test_student_state_shows_my_reaction_none_after_cancel(
    lecturer_client, student_client, classroom
):
    interaction_id = await _open_interaction(lecturer_client, classroom["occurrence_id"])

    await student_client.post(
        f"/student/interactions/{interaction_id}/reactions", json={"reaction": "agree"}
    )
    state = await student_client.get(f"/student/interactions/{interaction_id}")
    assert state.json()["my_reaction"] == "agree"

    # Cancel by tapping the same reaction again.
    await student_client.post(
        f"/student/interactions/{interaction_id}/reactions", json={"reaction": "agree"}
    )
    state = await student_client.get(f"/student/interactions/{interaction_id}")
    assert state.json()["my_reaction"] is None
    assert state.json()["reaction_counts"] == {}


async def test_invalid_reaction_is_422(lecturer_client, student_client, classroom):
    interaction_id = await _open_interaction(lecturer_client, classroom["occurrence_id"])
    resp = await student_client.post(
        f"/student/interactions/{interaction_id}/reactions", json={"reaction": "bogus"}
    )
    assert resp.status_code == 422, resp.text


async def test_reaction_not_enrolled_is_403(student_client, classroom, other_lecturer_client):
    interaction_id = await _open_interaction(other_lecturer_client, classroom["other_occurrence_id"])
    resp = await student_client.post(
        f"/student/interactions/{interaction_id}/reactions", json={"reaction": "confused"}
    )
    assert resp.status_code == 403, resp.text


# ── IDU ─────────────────────────────────────────────────────────────────────

async def test_idu_signal_counts_distinct_students(
    lecturer_client, student_client, classroom, db_session
):
    interaction_id = await _open_interaction(lecturer_client, classroom["occurrence_id"])

    resp = await student_client.post(f"/student/interactions/{interaction_id}/idu", json={})
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["distinct_students"] == 1
    assert body["has_signal"] is True

    # Second POST toggles: same student cancelling then re-signalling still leaves one row.
    resp = await student_client.post(f"/student/interactions/{interaction_id}/idu", json={})
    assert resp.status_code == 201, resp.text
    assert resp.json()["has_signal"] is False  # the second tap cancelled

    resp = await student_client.post(f"/student/interactions/{interaction_id}/idu", json={})
    assert resp.status_code == 201, resp.text
    assert resp.json()["distinct_students"] == 1
    assert resp.json()["has_signal"] is True

    rows = await db_session.execute(
        select(InteractionIDUSignal).where(InteractionIDUSignal.interaction_id == interaction_id)
    )
    assert len(rows.scalars().all()) == 1  # at most one per student per session


async def test_idu_lecturer_sees_distinct_count(lecturer_client, student_client, classroom):
    interaction_id = await _open_interaction(lecturer_client, classroom["occurrence_id"])
    await student_client.post(f"/student/interactions/{interaction_id}/idu", json={})

    resp = await lecturer_client.get(f"/lecturer/interactions/{interaction_id}/idu")
    assert resp.status_code == 200, resp.text
    assert resp.json()["distinct_students"] == 1


async def test_idu_not_enrolled_is_403(student_client, classroom, other_lecturer_client):
    interaction_id = await _open_interaction(other_lecturer_client, classroom["other_occurrence_id"])
    resp = await student_client.post(f"/student/interactions/{interaction_id}/idu", json={})
    assert resp.status_code == 403, resp.text


# ── websocket broadcasts ────────────────────────────────────────────────────

async def test_live_question_broadcasts(users, lecturer_client, classroom):
    interaction_id = await _open_interaction(lecturer_client, classroom["occurrence_id"])

    async with InteractionRoom(
        interaction_id, create_access_token(users["lecturer"].id, "lecturer")
    ) as room:
        await _ask_live(lecturer_client, interaction_id, "broadcast me")

        events = [e["event"] for e in room.sent]
        assert "live_question_posted" in events, events
        ev = [e for e in room.sent if e["event"] == "live_question_posted"][0]
        assert ev["interaction_id"] == interaction_id
        assert ev["question"] == "broadcast me"


async def test_live_question_response_broadcasts(users, lecturer_client, student_client, classroom):
    interaction_id = await _open_interaction(lecturer_client, classroom["occurrence_id"])
    resp = await _ask_live(lecturer_client, interaction_id, "q")
    live_q_id = resp.json()["id"]

    async with InteractionRoom(
        interaction_id, create_access_token(users["lecturer"].id, "lecturer")
    ) as room:
        await student_client.post(
            f"/student/interactions/{interaction_id}/live-question/{live_q_id}/response",
            json={"response": "yes"},
        )

        events = [e["event"] for e in room.sent]
        assert "live_question_response" in events, events


async def test_reaction_updated_broadcasts(users, lecturer_client, student_client, classroom):
    interaction_id = await _open_interaction(lecturer_client, classroom["occurrence_id"])

    async with InteractionRoom(
        interaction_id, create_access_token(users["lecturer"].id, "lecturer")
    ) as room:
        await student_client.post(
            f"/student/interactions/{interaction_id}/reactions", json={"reaction": "confused"}
        )

        events = [e["event"] for e in room.sent]
        assert "reaction_updated" in events, events
        ev = [e for e in room.sent if e["event"] == "reaction_updated"][0]
        assert ev["counts"] == {"confused": 1}


async def test_idu_signal_broadcasts(users, lecturer_client, student_client, classroom):
    interaction_id = await _open_interaction(lecturer_client, classroom["occurrence_id"])

    async with InteractionRoom(
        interaction_id, create_access_token(users["lecturer"].id, "lecturer")
    ) as room:
        await student_client.post(f"/student/interactions/{interaction_id}/idu", json={})

        events = [e["event"] for e in room.sent]
        assert "idu_signal" in events, events
        ev = [e for e in room.sent if e["event"] == "idu_signal"][0]
        assert ev["distinct_students"] == 1


# ── reaction cancel (S28): sending the same reaction again deletes the row ────


async def test_reaction_cancel_removes_row(
    lecturer_client, student_client, classroom, db_session
):
    interaction_id = await _open_interaction(lecturer_client, classroom["occurrence_id"])

    await student_client.post(
        f"/student/interactions/{interaction_id}/reactions", json={"reaction": "confused"}
    )
    # Tap the same reaction again -> cancel (row deleted).
    resp = await student_client.post(
        f"/student/interactions/{interaction_id}/reactions", json={"reaction": "confused"}
    )
    assert resp.status_code == 204, resp.text

    rows = (
        await db_session.execute(
            select(InteractionReaction).where(
                InteractionReaction.interaction_id == interaction_id
            )
        )
    ).scalars().all()
    assert rows == []

    counts = await lecturer_client.get(
        f"/lecturer/interactions/{interaction_id}/reactions"
    )
    assert counts.json() == []


async def test_reaction_switch_still_replaces(
    lecturer_client, student_client, classroom, db_session
):
    """A different reaction still replaces (only the identical tap cancels)."""
    interaction_id = await _open_interaction(lecturer_client, classroom["occurrence_id"])

    await student_client.post(
        f"/student/interactions/{interaction_id}/reactions", json={"reaction": "confused"}
    )
    await student_client.post(
        f"/student/interactions/{interaction_id}/reactions", json={"reaction": "agree"}
    )

    rows = (
        await db_session.execute(
            select(InteractionReaction).where(
                InteractionReaction.interaction_id == interaction_id
            )
        )
    ).scalars().all()
    assert len(rows) == 1 and rows[0].reaction == "agree"


async def test_reaction_cancel_broadcasts_empty_counts(
    users, lecturer_client, student_client, classroom
):
    interaction_id = await _open_interaction(lecturer_client, classroom["occurrence_id"])
    await student_client.post(
        f"/student/interactions/{interaction_id}/reactions", json={"reaction": "confused"}
    )

    async with InteractionRoom(
        interaction_id, create_access_token(users["lecturer"].id, "lecturer")
    ) as room:
        await student_client.post(
            f"/student/interactions/{interaction_id}/reactions", json={"reaction": "confused"}
        )
        ev = [e for e in room.sent if e["event"] == "reaction_updated"][-1]
        assert ev["counts"] == {}
        assert ev["cancelled"] is True


# ── S29 follow-up: IDU toggle (tap again cancels) ────────────────────────────


async def test_idu_toggle_cancel(lecturer_client, student_client, classroom, db_session):
    interaction_id = await _open_interaction(lecturer_client, classroom["occurrence_id"])

    first = await student_client.post(f"/student/interactions/{interaction_id}/idu", json={})
    assert first.status_code == 201, first.text
    assert first.json()["has_signal"] is True

    # Second tap cancels the signal.
    second = await student_client.post(f"/student/interactions/{interaction_id}/idu", json={})
    assert second.status_code == 201, second.text
    assert second.json()["has_signal"] is False
    assert second.json()["distinct_students"] == 0

    rows = (
        await db_session.execute(
            select(InteractionIDUSignal).where(
                InteractionIDUSignal.interaction_id == interaction_id
            )
        )
    ).scalars().all()
    assert rows == []

    count = await lecturer_client.get(f"/lecturer/interactions/{interaction_id}/idu")
    assert count.json()["distinct_students"] == 0
