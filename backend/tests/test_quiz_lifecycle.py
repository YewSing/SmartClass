"""Tests for quiz draft lifecycle + publish (FR-604, FR-605, FR-211, S31).

Covers: list draft questions, edit/approve/delete a draft (status machine), publish approved
questions as a quiz (server-enforced: only approved, same course, lecturer teaches it),
and publish emitting a quiz.published notification to the lecturer (priority important).
No real channels are used.
"""

import pytest
from sqlalchemy import select

from app.models.notify import Notification
from app.models.quiz import QuizQuestion
from app.services.notify import emit

pytestmark = pytest.mark.db


def _draft(course_id: int, qtype: str = "mcq", status: str = "draft",
           question: str = "Q?", topic: str = "t") -> QuizQuestion:
    return QuizQuestion(
        course_id=course_id, type=qtype, question=question, level="beginner",
        source_material_id=101, topic=topic, status=status,
    )


async def _make_drafts(db_session, classroom, n: int = 3, approved: int = 0) -> list[int]:
    ids = []
    for i in range(n):
        st = "approved" if i < approved else "draft"
        q = _draft(classroom["course_id"], question=f"draft {i}", status=st)
        db_session.add(q)
        await db_session.flush()
        ids.append(q.id)
    await db_session.commit()
    return ids


async def _lecturer_user_id(db_session, classroom) -> int:
    from app.models.user import Lecturer
    lecturer = await db_session.get(Lecturer, classroom["lecturer_id"])
    return lecturer.user_id


# ── draft lifecycle ─────────────────────────────────────────────────────────

async def test_list_draft_questions(lecturer_client, classroom, db_session):
    await _make_drafts(db_session, classroom, n=3, approved=1)

    resp = await lecturer_client.get(
        "/lecturer/quizzes/drafts", params={"course_id": classroom["course_id"]}
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert len(body) == 3
    assert all(q["course_id"] == classroom["course_id"] for q in body)
    assert {q["status"] for q in body} == {"draft", "approved"}


async def test_list_drafts_other_lecturer_403(other_lecturer_client, classroom, db_session):
    await _make_drafts(db_session, classroom, n=1)

    resp = await other_lecturer_client.get(
        "/lecturer/quizzes/drafts", params={"course_id": classroom["course_id"]}
    )
    assert resp.status_code == 403, resp.text


async def test_edit_draft_question(lecturer_client, classroom, db_session):
    ids = await _make_drafts(db_session, classroom, n=1)
    qid = ids[0]

    resp = await lecturer_client.put(
        f"/lecturer/quizzes/questions/{qid}",
        json={"question": "updated?", "level": "intermediate"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["question"] == "updated?"
    assert body["level"] == "intermediate"
    assert body["status"] == "draft"


async def test_edit_non_draft_is_409(lecturer_client, classroom, db_session):
    ids = await _make_drafts(db_session, classroom, n=1, approved=1)
    resp = await lecturer_client.put(f"/lecturer/quizzes/questions/{ids[0]}", json={"question": "x"})
    assert resp.status_code == 409, resp.text


async def test_edit_other_lecturer_403(other_lecturer_client, classroom, db_session):
    ids = await _make_drafts(db_session, classroom, n=1)
    resp = await other_lecturer_client.put(f"/lecturer/quizzes/questions/{ids[0]}", json={"question": "x"})
    assert resp.status_code == 403, resp.text


async def test_approve_question(lecturer_client, classroom, db_session):
    ids = await _make_drafts(db_session, classroom, n=1)
    resp = await lecturer_client.post(f"/lecturer/quizzes/questions/{ids[0]}/approve")
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "approved"

    result = await db_session.execute(select(QuizQuestion).where(QuizQuestion.id == ids[0]))
    assert result.scalar_one().status == "approved"


async def test_approve_non_draft_is_409(lecturer_client, classroom, db_session):
    ids = await _make_drafts(db_session, classroom, n=1, approved=1)
    resp = await lecturer_client.post(f"/lecturer/quizzes/questions/{ids[0]}/approve")
    assert resp.status_code == 409, resp.text


async def test_delete_draft_question(lecturer_client, classroom, db_session):
    ids = await _make_drafts(db_session, classroom, n=1)
    resp = await lecturer_client.delete(f"/lecturer/quizzes/questions/{ids[0]}")
    assert resp.status_code == 204, resp.text

    result = await db_session.execute(select(QuizQuestion).where(QuizQuestion.id == ids[0]))
    assert result.scalar_one().status == "deleted"


async def test_delete_non_draft_is_409(lecturer_client, classroom, db_session):
    ids = await _make_drafts(db_session, classroom, n=1, approved=1)
    resp = await lecturer_client.delete(f"/lecturer/quizzes/questions/{ids[0]}")
    assert resp.status_code == 409, resp.text


# ── publish ─────────────────────────────────────────────────────────────────

async def test_publish_quiz(lecturer_client, classroom, db_session):
    ids = await _make_drafts(db_session, classroom, n=3, approved=3)
    # approve all via endpoint (already approved via _make_drafts, but re-approve is 409;
    # they're already approved, good)

    resp = await lecturer_client.post(
        "/lecturer/quizzes",
        json={"question_ids": ids, "time_limit_minutes": 30,
              "opens_at": "2026-11-20T08:00:00", "closes_at": "2026-11-20T10:00:00"},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["status"] == "published"
    assert body["course_id"] == classroom["course_id"]
    assert body["time_limit_minutes"] == 30
    assert body["question_count"] == 3

    # questions are now linked to the quiz
    result = await db_session.execute(select(QuizQuestion).where(QuizQuestion.id.in_(ids)))
    qs = result.scalars().all()
    assert all(q.quiz_id == body["id"] for q in qs)
    assert all(q.status == "approved" for q in qs)

    # quiz.published notification to the lecturer, priority important
    user_id = await _lecturer_user_id(db_session, classroom)
    result = await db_session.execute(
        select(Notification).where(
            Notification.user_id == user_id,
            Notification.event == "quiz.published",
            Notification.priority == "important",
        )
    )
    notif = result.scalar_one_or_none()
    assert notif is not None
    assert notif.payload["quiz_id"] == body["id"]


async def test_publish_rejects_non_approved_question(lecturer_client, classroom, db_session):
    draft_ids = await _make_drafts(db_session, classroom, n=1, approved=0)
    resp = await lecturer_client.post("/lecturer/quizzes", json={"question_ids": draft_ids})
    assert resp.status_code == 409, resp.text


async def test_publish_rejects_already_in_quiz(lecturer_client, classroom, db_session):
    ids = await _make_drafts(db_session, classroom, n=2, approved=2)
    # publish once
    resp = await lecturer_client.post("/lecturer/quizzes", json={"question_ids": ids})
    assert resp.status_code == 201, resp.text
    # publish again with same questions → already in a quiz
    resp = await lecturer_client.post("/lecturer/quizzes", json={"question_ids": ids})
    assert resp.status_code == 409, resp.text


async def test_publish_other_lecturer_403(other_lecturer_client, classroom, db_session):
    ids = await _make_drafts(db_session, classroom, n=2, approved=2)
    resp = await other_lecturer_client.post("/lecturer/quizzes", json={"question_ids": ids})
    assert resp.status_code == 403, resp.text


# ── notify.emit ─────────────────────────────────────────────────────────────

async def test_emit_creates_notifications(db_session, classroom):
    user_id = await _lecturer_user_id(db_session, classroom)
    ids = await emit("quiz.published", [user_id], {"quiz_id": 7}, priority="important")
    assert len(ids) == 1

    result = await db_session.execute(select(Notification).where(Notification.id == ids[0]))
    n = result.scalar_one()
    assert n.event == "quiz.published"
    assert n.priority == "important"
    assert n.payload == {"quiz_id": 7}
    assert n.read_at is None
    assert n.delivered_push is False
    assert n.delivered_email is False

    # default priority general
    ids2 = await emit("x", [user_id], None)
    assert len(ids2) == 1
    result = await db_session.execute(select(Notification).where(Notification.id == ids2[0]))
    assert result.scalar_one().priority == "general"

    # empty user_ids
    assert await emit("x", [], None) == []

    # invalid priority
    with pytest.raises(ValueError):
        await emit("x", [user_id], None, priority="bogus")
