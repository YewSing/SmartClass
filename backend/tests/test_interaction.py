import asyncio
from datetime import datetime
from types import SimpleNamespace

import httpx
import pytest
from fastapi import WebSocketDisconnect
from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.core.config import settings
from app.core.security import create_access_token
from app.main import app
from app.models.audit import AuditLog
from app.models.class_ import ClassOccurrence, Enrollment
from app.models.interaction import InteractionEvent, InteractionQuestion
from app.models.session import AttendanceSession
from app.routers.interaction import interaction_ws
from app.services import interaction_read, session_schedule
from app.websocket.manager import manager

pytestmark = pytest.mark.db


@pytest.fixture
async def open_session(classroom):
    async with AsyncSessionLocal() as db:
        session = AttendanceSession(
            occurrence_id=classroom["occurrence_id"],
            lecturer_id=classroom["lecturer_id"],
            status="open",
            opened_at=datetime(2026, 11, 21, 8, 0),
            starts_at=datetime(2026, 11, 21, 8, 0),
            ends_at=datetime(2026, 11, 21, 10, 0),
        )
        db.add(session)
        await db.commit()
        return session.id


@pytest.fixture
def interaction_channels(monkeypatch):
    broadcasts = []
    notifications = []

    async def broadcast(session_id, payload, *, roles=("lecturer", "student")):
        broadcasts.append((session_id, payload, roles))

    async def emit(event, user_ids, payload):
        notifications.append((event, list(user_ids), payload))

    monkeypatch.setattr(manager, "broadcast_interaction", broadcast)
    monkeypatch.setattr("app.routers.interaction.notify.emit", emit)
    return {"broadcasts": broadcasts, "notifications": notifications}


async def _student_client(user_id):
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
        headers={"Authorization": f"Bearer {create_access_token(user_id, 'student')}"},
    )


async def test_access_and_shared_session_lifecycle(
    open_session, classroom, lecturer_client, student_client, other_lecturer_client, admin_client
):
    path = f"/interaction/sessions/{open_session}"
    assert (await lecturer_client.get(path)).status_code == 200
    student_state = await student_client.get(path)
    assert student_state.status_code == 200
    assert student_state.json()["can_participate"] is True
    assert (await other_lecturer_client.get(path)).status_code == 403
    assert (await admin_client.get(path)).status_code == 403

    async with AsyncSessionLocal() as db:
        session = await db.get(AttendanceSession, open_session)
        session.status = "closed"
        session.closed_at = datetime(2026, 11, 21, 10, 0)
        await db.commit()
    assert (await student_client.post(path + "/questions", json={"text": "Too late"})).status_code == 409
    closed = await student_client.get(path)
    assert closed.status_code == 200
    assert closed.json()["can_participate"] is False


async def test_anonymous_question_privacy_upvote_hide_and_audit(
    open_session, lecturer_client, student_client, users, interaction_channels
):
    base = f"/interaction/sessions/{open_session}"
    made = await student_client.post(base + "/questions", json={"text": "Please explain this", "anonymous": True})
    assert made.status_code == 201
    question = made.json()
    assert question["author_name"] is None
    assert "student_id" not in question

    lecturer_view = (await lecturer_client.get(base + "/questions")).json()[0]
    assert lecturer_view["author_name"] is None
    assert "student_id" not in lecturer_view

    first = await student_client.put(base + f"/questions/{question['id']}/upvote")
    second = await student_client.put(base + f"/questions/{question['id']}/upvote")
    assert first.json()["votes"] == second.json()["votes"] == 1
    assert (await student_client.get(base + "/questions")).json()[0]["upvoted_by_me"] is True
    assert (await lecturer_client.get(base + "/questions")).json()[0]["upvoted_by_me"] is False

    hidden = await lecturer_client.patch(base + f"/questions/{question['id']}", json={"hidden": True})
    assert hidden.status_code == 200 and hidden.json()["hidden"] is True
    assert (await student_client.get(base + "/questions")).json() == []
    async with AsyncSessionLocal() as db:
        audit = await db.scalar(select(AuditLog).where(AuditLog.action == "INTERACTION_QUESTION_HIDDEN"))
        assert audit.actor_id == users["lecturer"].id
        assert "student" not in (audit.old_val + audit.new_val).lower()
        stored = await db.get(InteractionQuestion, question["id"])
        assert stored.student_id is not None  # retained privately for M7 only

    for _, payload, _ in interaction_channels["broadcasts"]:
        encoded = str(payload).lower()
        assert "student_id" not in encoded and "matric" not in encoded


async def test_poll_draft_vote_change_visibility_and_notification(
    open_session, classroom, lecturer_client, student_client, interaction_channels
):
    base = f"/interaction/sessions/{open_session}"
    poll = (await lecturer_client.post(base + "/polls", json={
        "prompt": "Which topics?",
        "options": ["A", "B", "C"],
        "multiple": True,
        "show_results": False,
    })).json()
    assert (await student_client.get(base + "/polls")).json() == []

    started = await lecturer_client.post(base + f"/polls/{poll['id']}/start")
    assert started.status_code == 200
    [notification] = interaction_channels["notifications"]
    assert notification[0] == "poll.started"
    assert set(notification[1]) == set(classroom["student_user_ids"])

    voted = await student_client.put(base + f"/polls/{poll['id']}/vote", json={"option_indexes": [0, 2]})
    assert voted.status_code == 200
    assert voted.json()["my_option_indexes"] == [0, 2]
    assert voted.json()["results"] is None
    revised = await student_client.put(base + f"/polls/{poll['id']}/vote", json={"option_indexes": [1]})
    assert revised.status_code == 200

    shown = await lecturer_client.patch(base + f"/polls/{poll['id']}", json={"show_results": True})
    assert shown.json()["results"] == {"respondent_count": 1, "option_counts": [0, 1, 0]}
    student_poll = (await student_client.get(base + "/polls")).json()[0]
    assert student_poll["results"]["respondent_count"] == 1

    assert (await lecturer_client.post(base + f"/polls/{poll['id']}/close")).status_code == 200
    assert (await student_client.put(base + f"/polls/{poll['id']}/vote", json={"option_indexes": [0]})).status_code == 409


async def test_poll_validation_and_cross_session_child_substitution(
    open_session, classroom, lecturer_client, student_client
):
    base = f"/interaction/sessions/{open_session}"
    duplicate = await lecturer_client.post(base + "/polls", json={
        "prompt": "Bad", "options": ["Same", "same"]
    })
    assert duplicate.status_code == 422

    draft = (await lecturer_client.post(base + "/polls", json={
        "prompt": "Never published", "options": ["Yes", "No"]
    })).json()
    assert (await lecturer_client.post(base + f"/polls/{draft['id']}/close")).status_code == 409
    assert (await student_client.get(base + "/polls")).json() == []

    async with AsyncSessionLocal() as db:
        other = AttendanceSession(
            occurrence_id=classroom["occurrence_id"], lecturer_id=classroom["lecturer_id"], status="open"
        )
        db.add(other)
        await db.commit()
        other_id = other.id
    poll = (await lecturer_client.post(f"/interaction/sessions/{other_id}/polls", json={
        "prompt": "Other", "options": ["Yes", "No"]
    })).json()
    response = await student_client.put(base + f"/polls/{poll['id']}/vote", json={"option_indexes": [0]})
    assert response.status_code == 404


async def test_quick_answers_reactions_and_private_lecturer_list(
    open_session, lecturer_client, student_client
):
    base = f"/interaction/sessions/{open_session}"
    prompt = (await lecturer_client.post(base + "/quick-prompts", json={
        "prompt": "One sentence", "max_length": 20
    })).json()
    answer_path = base + f"/quick-prompts/{prompt['id']}/answers"
    assert (await student_client.post(answer_path, json={"text": "A short answer"})).status_code == 200
    assert (await student_client.get(answer_path)).status_code == 403
    answers = (await lecturer_client.get(answer_path)).json()
    assert answers[0]["student_name"] == "Test Student"

    assert (await student_client.post(base + "/reactions", json={"kind": "clear"})).status_code == 201
    limited = await student_client.post(base + "/reactions", json={"kind": "too_fast"})
    assert limited.status_code == 429
    assert int(limited.headers["Retry-After"]) >= 1


async def test_confusion_is_aggregate_rate_limited_and_notifies_without_identity(
    open_session, lecturer_client, student_client, interaction_channels
):
    base = f"/interaction/sessions/{open_session}"
    first = await student_client.post(base + "/confusion", json={"topic_tag": "recursion"})
    assert first.status_code == 201
    assert (await student_client.post(base + "/confusion", json={})).status_code == 429
    signals = (await lecturer_client.get(base + "/signals")).json()
    assert signals["confusion_total"] == 1
    assert all("student" not in str(item).lower() for item in signals["confusion_timeline"])
    spike = next(item for item in interaction_channels["notifications"] if item[0] == "confusion.spike")
    encoded = str(spike[2]).lower()
    assert "student_id" not in encoded and "matric" not in encoded and "test student" not in encoded
    assert "recursion" not in encoded


async def test_summary_and_m7_read_hide_anonymous_individual_question(
    open_session, classroom, lecturer_client, student_client
):
    base = f"/interaction/sessions/{open_session}"
    await student_client.post(base + "/questions", json={"text": "Anonymous", "anonymous": True})
    await student_client.post(base + "/questions", json={"text": "Public", "anonymous": False})
    async with AsyncSessionLocal() as db:
        session = await db.get(AttendanceSession, open_session)
        session.status = "closed"
        await db.commit()
    summary = await lecturer_client.get(base + "/summary")
    assert summary.status_code == 200
    assert summary.json()["questions_asked"] == 2
    async with AsyncSessionLocal() as db:
        rows = await interaction_read.student_counts(db, classroom["occurrence_id"])
        mine = next(row for row in rows if row["student_id"] == classroom["student_ids"][0])
        assert mine["questions_submitted"] == 1
        totals = await interaction_read.class_totals(db, classroom["occurrence_id"])
        assert totals["questions_submitted"] == 2


async def test_anonymous_only_question_does_not_change_individual_m7_rows(
    open_session, classroom
):
    async with AsyncSessionLocal() as db:
        before = await interaction_read.student_counts(db, classroom["occurrence_id"])
        before_total = await interaction_read.class_totals(db, classroom["occurrence_id"])
    async with await _student_client(classroom["student_user_ids"][1]) as client:
        made = await client.post(
            f"/interaction/sessions/{open_session}/questions",
            json={"text": "Identity must stay hidden", "anonymous": True},
        )
        assert made.status_code == 201
    async with AsyncSessionLocal() as db:
        after = await interaction_read.student_counts(db, classroom["occurrence_id"])
        after_total = await interaction_read.class_totals(db, classroom["occurrence_id"])
    assert after == before
    assert after_total["questions_submitted"] == before_total["questions_submitted"] + 1


async def test_second_enrolled_student_can_participate(open_session, classroom):
    async with await _student_client(classroom["student_user_ids"][1]) as client:
        response = await client.post(
            f"/interaction/sessions/{open_session}/questions",
            json={"text": "Second student"},
        )
    assert response.status_code == 201
    async with AsyncSessionLocal() as db:
        events = (await db.scalars(select(InteractionEvent).where(
            InteractionEvent.attendance_session_id == open_session
        ))).all()
        assert events[0].student_id == classroom["student_ids"][1]


async def test_manual_class_close_projects_status_and_stops_interaction(
    open_session, lecturer_client, student_client, interaction_channels
):
    closed = await lecturer_client.put(f"/lecturer/sessions/{open_session}/close")
    assert closed.status_code == 200
    projected = [payload for _, payload, _ in interaction_channels["broadcasts"]
                 if payload["event"] == "interaction.session_status"]
    assert projected == [{
        "event": "interaction.session_status",
        "attendance_session_id": open_session,
        "status": "closed",
    }]
    response = await student_client.post(
        f"/interaction/sessions/{open_session}/questions", json={"text": "After close"}
    )
    assert response.status_code == 409


class _Socket:
    def __init__(self):
        self.accepted = False
        self.closed = None
        self.sent = []

    async def accept(self):
        self.accepted = True

    async def close(self, code):
        self.closed = code

    async def send_json(self, payload):
        self.sent.append(payload)

    async def receive_text(self):
        raise WebSocketDisconnect()


async def test_interaction_websocket_enforces_enrolment_and_sends_safe_bootstrap(
    open_session, classroom
):
    enrolled = _Socket()
    await interaction_ws(
        open_session,
        enrolled,
        create_access_token(classroom["student_user_ids"][0], "student"),
    )
    assert enrolled.accepted is True
    assert enrolled.sent == [{
        "event": "interaction.state",
        "attendance_session_id": open_session,
        "status": "open",
    }]
    assert "student" not in str(enrolled.sent).lower()

    unrelated = _Socket()
    await interaction_ws(
        open_session,
        unrelated,
        create_access_token(classroom["other_lecturer_user_id"], "lecturer"),
    )
    assert unrelated.accepted is False
    assert unrelated.closed == 1008

    stale_role = _Socket()
    await interaction_ws(
        open_session,
        stale_role,
        create_access_token(classroom["student_user_ids"][0], "lecturer"),
    )
    assert stale_role.accepted is False
    assert stale_role.closed == 1008


async def test_vote_and_class_close_have_a_consistent_order(
    open_session, lecturer_client, student_client
):
    base = f"/interaction/sessions/{open_session}"
    poll = (await lecturer_client.post(base + "/polls", json={
        "prompt": "Race", "options": ["A", "B"]
    })).json()
    await lecturer_client.post(base + f"/polls/{poll['id']}/start")
    vote, close = await asyncio.gather(
        student_client.put(base + f"/polls/{poll['id']}/vote", json={"option_indexes": [0]}),
        lecturer_client.put(f"/lecturer/sessions/{open_session}/close"),
    )
    assert close.status_code == 200
    assert vote.status_code in (200, 409)  # whichever transaction acquired the session row first
    after = await student_client.put(base + f"/polls/{poll['id']}/vote", json={"option_indexes": [1]})
    assert after.status_code == 409


async def test_confusion_uses_current_roster_for_window_and_recipient(
    open_session, classroom, student_client, interaction_channels, monkeypatch
):
    monkeypatch.setattr(settings, "INTERACTION_CONFUSION_SHARE", 0.5)
    base = f"/interaction/sessions/{open_session}"
    assert (await student_client.post(base + "/confusion", json={})).status_code == 201
    assert interaction_channels["notifications"] == []  # one of three is below 50%

    async with AsyncSessionLocal() as db:
        enrollment = await db.scalar(select(Enrollment).where(
            Enrollment.occurrence_id == classroom["occurrence_id"],
            Enrollment.student_id == classroom["student_ids"][0],
        ))
        await db.delete(enrollment)
        await db.commit()
    async with await _student_client(classroom["student_user_ids"][1]) as second:
        assert (await second.post(base + "/confusion", json={})).status_code == 201
    [spike] = interaction_channels["notifications"]
    assert spike[0] == "confusion.spike"
    assert spike[2]["message"].startswith("1 student ")

    async with AsyncSessionLocal() as db:
        occurrence = await db.get(ClassOccurrence, classroom["occurrence_id"])
        occurrence.lecturer_id = classroom["other_lecturer_id"]
        await db.commit()
    interaction_channels["notifications"].clear()
    monkeypatch.setattr(settings, "INTERACTION_CONFUSION_SHARE", 1.0)
    async with await _student_client(classroom["student_user_ids"][2]) as third:
        assert (await third.post(base + "/confusion", json={})).status_code == 201
    # The current roster has two students; the second distinct current presser crosses 100%.
    [reassigned_spike] = interaction_channels["notifications"]
    assert reassigned_spike[1] == [classroom["other_lecturer_user_id"]]


async def test_websocket_registers_before_fresh_locked_bootstrap(
    open_session, classroom, monkeypatch
):
    socket = _Socket()

    async def connect_then_close(session_id, role, ws):
        await ws.accept()
        async with AsyncSessionLocal() as db:
            session = await db.get(AttendanceSession, session_id)
            session.status = "closed"
            await db.commit()

    monkeypatch.setattr(manager, "connect_interaction", connect_then_close)
    await interaction_ws(
        open_session,
        socket,
        create_access_token(classroom["student_user_ids"][0], "student"),
    )
    assert socket.sent[0]["status"] == "closed"


async def test_manual_and_scheduler_open_publish_interaction_status(
    classroom, lecturer_client, interaction_channels, monkeypatch
):
    opened = await lecturer_client.post(
        "/lecturer/sessions", json={"occurrence_id": classroom["occurrence_id"]}
    )
    assert opened.status_code == 201
    session_id = opened.json()["id"]
    assert any(payload == {
        "event": "interaction.session_status",
        "attendance_session_id": session_id,
        "status": "open",
    } for _, payload, _ in interaction_channels["broadcasts"])

    interaction_channels["broadcasts"].clear()

    async def fake_tick(_db):
        return SimpleNamespace(opened=[session_id], closed=[], needs_confirmation=[])

    async def stop_after_one(_seconds):
        raise asyncio.CancelledError

    monkeypatch.setattr(session_schedule, "tick", fake_tick)
    monkeypatch.setattr(session_schedule.asyncio, "sleep", stop_after_one)
    monkeypatch.setattr(settings, "SESSION_SCHEDULER_INTERVAL_SECONDS", 1)
    with pytest.raises(asyncio.CancelledError):
        await session_schedule.session_scheduler_loop()
    assert interaction_channels["broadcasts"] == [(session_id, {
        "event": "interaction.session_status",
        "attendance_session_id": session_id,
        "status": "open",
    }, ("lecturer", "student"))]

