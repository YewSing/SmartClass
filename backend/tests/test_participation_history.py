"""Tests for the student participation-history endpoints (FR-509 read side).

`GET /student/me/participation/sessions` lists every interaction session of the
student's enrolled classes with their own counts; `GET .../sessions/{id}` returns the
full per-session detail (poll with class distribution and my choice, live-question
responses, own questions). NFR-04: a student sees only their own activity and only in
classes they are enrolled in.
"""

import pytest

pytestmark = pytest.mark.db


async def _open(client, occurrence_id: int) -> int:
    resp = await client.post("/lecturer/interactions", json={"occurrence_id": occurrence_id})
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


async def test_sessions_list_and_detail(
    lecturer_client, student_client, classroom
):
    interaction_id = await _open(lecturer_client, classroom["occurrence_id"])
    poll = await lecturer_client.post(
        f"/lecturer/interactions/{interaction_id}/polls",
        json={"question": "Ready?", "options": ["Yes", "No"]},
    )
    assert poll.status_code == 201, poll.text
    poll_body = poll.json()
    yes_id = next(o["id"] for o in poll_body["options"] if o["option_text"] == "Yes")

    live = await lecturer_client.post(
        f"/lecturer/interactions/{interaction_id}/live-question",
        json={"question": "Following?"},
    )
    assert live.status_code == 201, live.text

    # The student participates: vote, respond, ask, react, IDU
    await student_client.post(f"/student/polls/{poll_body['id']}/vote", json={"option_id": yes_id})
    await student_client.post(
        f"/student/interactions/{interaction_id}/live-question/{live.json()['id']}/response",
        json={"response": "almost"},
    )
    await student_client.post(
        f"/student/interactions/{interaction_id}/questions",
        json={"text": "Is this on the exam?", "anonymous": True},
    )
    await student_client.post(
        f"/student/interactions/{interaction_id}/reactions", json={"reaction": "confused"}
    )
    await student_client.post(f"/student/interactions/{interaction_id}/idu", json={})

    # List shows the session with the student's counts
    resp = await student_client.get("/student/me/participation/sessions")
    assert resp.status_code == 200, resp.text
    sessions = resp.json()
    assert len(sessions) == 1
    row = sessions[0]
    assert row["id"] == interaction_id
    assert row["class_code"] == "CS101"
    assert row["votes"] == 1
    assert row["responses"] == 1
    assert row["questions"] == 1
    assert row["reactions"] == 1
    assert row["idu_signals"] == 1

    # Detail: poll distribution with my choice, live response, own question
    detail = await student_client.get(
        f"/student/me/participation/sessions/{interaction_id}"
    )
    assert detail.status_code == 200, detail.text
    body = detail.json()
    assert body["stats"]["votes"] == 1
    assert body["class_participants"] == 1
    assert len(body["polls"]) == 1
    assert body["polls"][0]["my_option"] == "Yes"
    dist = {o["option_text"]: o["votes"] for o in body["polls"][0]["options"]}
    assert dist == {"Yes": 1, "No": 0}
    assert body["live_questions"][0]["my_response"] == "almost"
    assert [q["text"] for q in body["my_questions"]] == ["Is this on the exam?"]
    assert body["my_questions"][0]["anonymous"] is True


async def test_sessions_exclude_other_classes(student_client, classroom):
    """Only enrolled classes appear (the CS202 occurrence belongs to another lecturer)."""
    resp = await student_client.get("/student/me/participation/sessions")
    assert resp.status_code == 200
    assert all(s["class_code"] == "CS101" for s in resp.json())


async def test_detail_of_other_class_is_403(lecturer_client, other_lecturer_client,
                                            student_client, classroom):
    """A session of a class the student is not enrolled in is 403 (NFR-04)."""
    interaction_id = await _open(other_lecturer_client, classroom["other_occurrence_id"])
    resp = await student_client.get(f"/student/me/participation/sessions/{interaction_id}")
    assert resp.status_code == 403


async def test_detail_unknown_is_404(student_client):
    resp = await student_client.get("/student/me/participation/sessions/99999")
    assert resp.status_code == 404


async def test_requires_student_role(lecturer_client):
    resp = await lecturer_client.get("/student/me/participation/sessions")
    assert resp.status_code == 403
