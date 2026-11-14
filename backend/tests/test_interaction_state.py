"""Tests for the student interaction state endpoint (S20–S25 rebuild).

`GET /student/interactions/{id}` is what the student screen paints from: the poll with
per-option counts and this student's vote, the live question with this student's response,
the class reaction counts and this student's reaction, the distinct IDU count and whether
this student already signalled, plus this student's own questions. It stays readable after
the session closes so the screen can show the final state.
"""

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.security import create_access_token
from app.main import app

pytestmark = pytest.mark.db


async def _open(client, occurrence_id: int) -> int:
    resp = await client.post("/lecturer/interactions", json={"occurrence_id": occurrence_id})
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


async def _create_poll(client, interaction_id: int) -> dict:
    resp = await client.post(
        f"/lecturer/interactions/{interaction_id}/polls",
        json={"question": "Ready?", "options": ["Yes", "No"]},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _poll_response(client, interaction_id: int) -> dict:
    resp = await client.get(f"/student/interactions/{interaction_id}")
    assert resp.status_code == 200, resp.text
    return resp.json()


async def test_state_reports_poll_vote_reaction_idu_and_live_response(
    lecturer_client, student_client, classroom
):
    interaction_id = await _open(lecturer_client, classroom["occurrence_id"])
    poll = await _create_poll(lecturer_client, interaction_id)
    yes_id = next(o["id"] for o in poll["options"] if o["option_text"] == "Yes")

    live = await lecturer_client.post(
        f"/lecturer/interactions/{interaction_id}/live-question",
        json={"question": "Following?"},
    )
    assert live.status_code == 201, live.text
    live_id = live.json()["id"]

    await student_client.post(f"/student/polls/{poll['id']}/vote", json={"option_id": yes_id})
    await student_client.post(
        f"/student/interactions/{interaction_id}/reactions", json={"reaction": "confused"}
    )
    await student_client.post(f"/student/interactions/{interaction_id}/idu", json={})
    await student_client.post(
        f"/student/interactions/{interaction_id}/live-question/{live_id}/response",
        json={"response": "almost"},
    )
    await student_client.post(
        f"/student/interactions/{interaction_id}/questions",
        json={"text": "Is this on the exam?", "anonymous": False},
    )

    body = await _poll_response(student_client, interaction_id)

    votes = {o["option_text"]: o["votes"] for o in body["current_poll"]["options"]}
    assert votes == {"Yes": 1, "No": 0}
    assert body["current_poll"]["my_option_id"] == yes_id
    assert body["my_reaction"] == "confused"
    assert body["reaction_counts"] == {"confused": 1}
    assert body["idu_distinct_students"] == 1
    assert body["idu_has_signal"] is True
    assert body["live_question"]["id"] == live_id
    assert body["live_question"]["my_response"] == "almost"
    assert [q["text"] for q in body["my_questions"]] == ["Is this on the exam?"]


async def test_state_is_readable_after_close(lecturer_client, student_client, classroom):
    interaction_id = await _open(lecturer_client, classroom["occurrence_id"])
    await _create_poll(lecturer_client, interaction_id)
    await lecturer_client.post(f"/lecturer/interactions/{interaction_id}/close")

    body = await _poll_response(student_client, interaction_id)
    assert body["status"] == "closed"
    assert body["current_poll"]["is_open"] is False


async def test_state_hides_other_students_questions(
    lecturer_client, student_client, classroom
):
    interaction_id = await _open(lecturer_client, classroom["occurrence_id"])

    other_token = create_access_token(classroom["student_user_ids"][1], "student")
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"Authorization": f"Bearer {other_token}"},
    ) as other:
        resp = await other.post(
            f"/student/interactions/{interaction_id}/questions",
            json={"text": "Someone else's question", "anonymous": True},
        )
        assert resp.status_code == 201, resp.text
        other_state = await other.get(f"/student/interactions/{interaction_id}")
        assert [q["text"] for q in other_state.json()["my_questions"]] == [
            "Someone else's question"
        ]
        # Anonymous in the student's own view too.
        assert other_state.json()["my_questions"][0]["student_id"] is None

    body = await _poll_response(student_client, interaction_id)
    assert body["my_questions"] == []


async def test_state_not_enrolled_is_403(student_client, other_lecturer_client, classroom):
    interaction_id = await _open(other_lecturer_client, classroom["other_occurrence_id"])
    resp = await student_client.get(f"/student/interactions/{interaction_id}")
    assert resp.status_code == 403, resp.text


async def test_state_unknown_is_404(student_client):
    resp = await student_client.get("/student/interactions/999999")
    assert resp.status_code == 404


async def test_state_requires_student(student_client, lecturer_client, classroom):
    interaction_id = await _open(lecturer_client, classroom["occurrence_id"])
    resp = await lecturer_client.get(f"/student/interactions/{interaction_id}")
    assert resp.status_code == 403, resp.text


async def test_student_list_carries_live_poll_and_question(
    lecturer_client, student_client, classroom
):
    interaction_id = await _open(lecturer_client, classroom["occurrence_id"])
    poll = await _create_poll(lecturer_client, interaction_id)
    await lecturer_client.post(
        f"/lecturer/interactions/{interaction_id}/live-question", json={"question": "Following?"}
    )

    resp = await student_client.get("/student/interactions")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert len(body) == 1
    assert body[0]["id"] == interaction_id
    assert body[0]["current_poll"]["id"] == poll["id"]
    assert {o["option_text"] for o in body[0]["current_poll"]["options"]} == {"Yes", "No"}
    assert body[0]["live_question"]["question"] == "Following?"


async def test_closed_session_is_not_in_student_list(lecturer_client, student_client, classroom):
    interaction_id = await _open(lecturer_client, classroom["occurrence_id"])
    await lecturer_client.post(f"/lecturer/interactions/{interaction_id}/close")

    resp = await student_client.get("/student/interactions")
    assert resp.status_code == 200, resp.text
    assert resp.json() == []
