"""S43: publishing, unpublishing and closing quizzes (FR-604, FR-606) and a student's quiz cards (FR-607)."""
import asyncio
import json
from datetime import datetime, timedelta

import pytest
from sqlalchemy import select, update

from app.core.database import AsyncSessionLocal
from app.core.timezone import MYT
from app.models.audit import AuditLog
from app.models.class_ import ClassOccurrence, Enrollment
from app.models.notification import Notification
from app.models.quiz import Quiz, QuizAttempt
from app.models.user import User
from app.schemas.quiz import QuizCardOut
from app.services import notify, quiz_publish, quiz_store
from app.services.quiz_cards import card_state
from tests.test_quiz_crud import (
    URL,
    attempt_row,
    call,
    count,
    create,
    delete,
    game,
    get,
    graded,
    insert,
    patch,
    question_row,
    set_status,
)
from tests.test_quiz_questions import add, approve, edit, ids, mcq, order, remove

MINE = "/student/me/quizzes"
NOW = datetime(2026, 12, 1, 9, 0)
HOUR = timedelta(hours=1)


@pytest.fixture
def clock(monkeypatch):
    class Clock:
        now = NOW

        def __call__(self):
            return self.now

    c = Clock()
    monkeypatch.setattr(quiz_store, "clock", c)
    return c


async def ready(c, body=None, approved=1, unapproved=0) -> dict:
    """A draft with approved and unapproved questions."""
    quiz = await create(c, body)
    await insert(*(question_row(quiz["id"], i, text=f"Secret question {i}", approved=i < approved,
                                explanation="Secret explanation")
                   for i in range(approved + unapproved)))
    return quiz


async def act(c, qid, action, expect=200, **kw):
    return await call(c, "POST", f"{URL}/{qid}/{action}", expect, **kw)


async def published(c, body=None, **kw) -> dict:
    return await act(c, (await ready(c, body, **kw))["id"], "publish")


async def cards(c, i=0, expect=200, **kw):
    kw = {"uid": c.student_user_ids[i], "role": "student", **kw}
    body = await call(c, "GET", MINE, expect, **kw)
    return body["quizzes"] if expect == 200 else body


async def notifications() -> list[Notification]:
    async with AsyncSessionLocal() as db:
        return list((await db.execute(select(Notification).where(Notification.event == "quiz.published")
                                      .order_by(Notification.user_id))).scalars())


async def audits(*actions) -> list[AuditLog]:
    async with AsyncSessionLocal() as db:
        return list((await db.execute(select(AuditLog).where(AuditLog.action.in_(actions))
                                      .order_by(AuditLog.id))).scalars())


# ── publish ──────────────────────────────────────────────────────────────────

@pytest.mark.db
@pytest.mark.parametrize("make", [graded, game])
async def test_publish(shino_class, clock, make):
    c = shino_class
    quiz = await ready(c, make(c))
    assert quiz["published_at"] is None
    clock.now += HOUR
    out = await act(c, quiz["id"], "publish")
    assert out["status"] == "published"
    assert out["published_at"] == out["updated_at"] == clock.now.isoformat()
    assert out["questions"][0]["approved"] is True
    assert await get(c, quiz["id"]) == out
    [row] = await audits("QUIZ_PUBLISH")
    assert (row.actor_id, row.target_type, row.target_id) == (c.lecturer_user_id, "m6_quiz", str(quiz["id"]))
    assert json.loads(row.old_val) == {"status": "draft"}
    assert json.loads(row.new_val) == {"status": "published", "title": "Week 5", "questions": 1}


@pytest.mark.db
@pytest.mark.parametrize("unapproved", [0, 2])
async def test_publish_needs_an_approved_question(shino_class, unapproved):
    c = shino_class
    quiz = await ready(c, approved=0, unapproved=unapproved)
    assert "Approve at least one" in (await act(c, quiz["id"], "publish", expect=422))["detail"]
    assert (await get(c, quiz["id"]))["status"] == "draft"
    assert await notifications() == [] and await audits("QUIZ_PUBLISH") == [] and await cards(c) == []


@pytest.mark.db
async def test_only_approved_questions_are_published(shino_class):
    c = shino_class
    quiz = await create(c)
    for text in ("A?", "B?", "C?"):
        quiz = await add(c, quiz["id"], mcq(text))
    a, b, d = ids(quiz)
    await approve(c, quiz["id"], [a, d])
    await order(c, quiz["id"], [d, b, a])
    out = await act(c, quiz["id"], "publish")
    async with AsyncSessionLocal() as db:
        assert [q.id for q in await quiz_publish.published_questions(db, quiz["id"])] == [d, a]
    assert [x["question_count"] for x in await cards(c)] == [2]
    # the lecturer still has the other one, unapproved
    assert (out["question_count"], out["approved_count"]) == (3, 2)


@pytest.mark.db
async def test_publish_refuses_a_closing_time_in_the_past(shino_class, clock):
    c = shino_class
    quiz = await ready(c, graded(c, closes_at=(NOW + HOUR).isoformat()))
    clock.now = NOW + HOUR
    assert "closing time" in (await act(c, quiz["id"], "publish", expect=422))["detail"]
    await patch(c, quiz["id"], {"closes_at": (NOW + 2 * HOUR).isoformat()})
    assert (await act(c, quiz["id"], "publish"))["status"] == "published"


@pytest.mark.db
@pytest.mark.parametrize("status", ["published", "closed"])
async def test_only_a_draft_can_be_published(shino_class, status):
    c = shino_class
    quiz = await ready(c)
    await set_status(quiz["id"], status)
    await act(c, quiz["id"], "publish", expect=409)
    assert (await get(c, quiz["id"]))["status"] == status and await notifications() == []


@pytest.mark.db
async def test_a_published_quiz_cannot_be_edited(shino_class):
    c = shino_class
    quiz = await published(c, approved=2)
    qid, (a, b) = quiz["id"], ids(quiz)
    await patch(c, qid, {"title": "New"}, expect=409)
    await delete(c, qid, expect=409)
    await add(c, qid, mcq(), expect=409)
    await edit(c, qid, a, mcq(), expect=409)
    await remove(c, qid, a, expect=409)
    await order(c, qid, [b, a], expect=409)
    await approve(c, qid, [a], approved=False, expect=409)
    assert await get(c, qid) == quiz


@pytest.mark.db
async def test_publishing_twice_at_once_publishes_and_notifies_once(shino_class):
    c = shino_class
    quiz = await ready(c)

    async def one():
        async with c.client(c.lecturer_user_id, "lecturer") as api:
            return (await api.post(f"{URL}/{quiz['id']}/publish")).status_code

    assert sorted(await asyncio.gather(*(one() for _ in range(4)))) == [200, 409, 409, 409]
    assert len(await notifications()) == len(c.student_user_ids) and len(await audits("QUIZ_PUBLISH")) == 1


@pytest.mark.db
async def test_publishing_while_the_last_approval_is_taken_back(shino_class):
    """Whichever comes first, no quiz is ever published without an approved question."""
    c = shino_class
    for _ in range(3):
        quiz = await ready(c)
        qid = quiz["id"]
        question = ids(await get(c, qid))[0]
        async with c.client(c.lecturer_user_id, "lecturer") as api:
            pub, un = await asyncio.gather(
                api.post(f"{URL}/{qid}/publish"),
                api.put(f"{URL}/{qid}/questions/approval", json={"question_ids": [question], "approved": False}))
        assert (pub.status_code, un.status_code) in [(200, 409), (422, 200)]
        got = await get(c, qid)
        assert (got["status"], got["approved_count"]) == (("published", 1) if pub.status_code == 200 else ("draft", 0))


# ── quiz.published ───────────────────────────────────────────────────────────

@pytest.mark.db
async def test_publishing_notifies_the_enrolled_students_once(shino_class):
    c = shino_class
    # in a second class of the course too, and one account that is not active
    [tutorial] = await insert(ClassOccurrence(course_id=c.course_id, type="TUTORIAL", lecturer_id=c.lecturer_id))
    await insert(Enrollment(student_id=c.student_ids[0], occurrence_id=tutorial))
    async with AsyncSessionLocal() as db:
        await db.execute(update(User).where(User.id == c.student_user_ids[3]).values(status="inactive"))
        await db.commit()
    quiz = await published(c)
    rows = await notifications()
    assert [r.user_id for r in rows] == sorted(c.student_user_ids[:3])
    assert {(r.priority, r.title, r.message, r.link) for r in rows} == {
        ("important", "New quiz: Week 5", "A new quiz is available in SH101.", f"/quizzes/{quiz['id']}")}


@pytest.mark.db
async def test_the_notification_says_when_a_later_quiz_opens(shino_class, clock):
    c = shino_class
    await published(c, graded(c, opens_at="2026-12-03T14:05:00"))
    assert {r.message for r in await notifications()} == {"A new quiz in SH101 opens on 3 Dec 2026, 14:05."}


@pytest.mark.db
async def test_students_are_notified_after_the_commit(shino_class, monkeypatch):
    c = shino_class
    seen = []

    async def emit(event, user_ids, payload):
        async with AsyncSessionLocal() as db:
            seen.append((event, list(user_ids), payload["quiz_id"], (await db.get(Quiz, payload["quiz_id"])).status))

    monkeypatch.setattr(notify, "emit", emit)
    quiz = await published(c)
    assert seen == [("quiz.published", sorted(c.student_user_ids), quiz["id"], "published")]


@pytest.mark.db
async def test_republishing_the_same_day_does_not_notify_again(shino_class):
    c = shino_class
    quiz = await published(c)
    await act(c, quiz["id"], "unpublish")
    await act(c, quiz["id"], "publish")
    assert len(await notifications()) == len(c.student_user_ids)


# ── unpublish and close ──────────────────────────────────────────────────────

@pytest.mark.db
async def test_unpublish_gives_back_an_editable_draft(shino_class):
    c = shino_class
    quiz = await published(c, approved=1, unapproved=1)
    assert len(await cards(c)) == 1
    out = await act(c, quiz["id"], "unpublish")
    assert out["status"] == "draft" and out["published_at"] is None
    assert [q["approved"] for q in out["questions"]] == [True, False]
    assert await cards(c) == []
    await patch(c, quiz["id"], {"title": "New"})
    [row] = await audits("QUIZ_UNPUBLISH")
    assert json.loads(row.old_val) == {"status": "published"}
    assert json.loads(row.new_val) == {"status": "draft", "title": "Week 5"}


@pytest.mark.db
async def test_close(shino_class):
    c = shino_class
    quiz = await published(c)
    out = await act(c, quiz["id"], "close")
    assert out["status"] == "closed" and out["published_at"] == quiz["published_at"]
    assert [x["state"] for x in await cards(c)] == ["closed"]
    await act(c, quiz["id"], "close", expect=409)
    [row] = await audits("QUIZ_CLOSE")
    assert json.loads(row.old_val) == {"status": "published"} and json.loads(row.new_val)["status"] == "closed"


@pytest.mark.db
async def test_a_closed_quiz_without_attempts_can_be_unpublished(shino_class):
    c = shino_class
    quiz = await published(c)
    await act(c, quiz["id"], "close")
    assert (await act(c, quiz["id"], "unpublish"))["status"] == "draft"
    assert (await act(c, quiz["id"], "publish"))["status"] == "published"


@pytest.mark.db
async def test_a_draft_cannot_be_closed_or_unpublished(shino_class):
    c = shino_class
    quiz = await ready(c)
    await act(c, quiz["id"], "close", expect=409)
    await act(c, quiz["id"], "unpublish", expect=409)
    assert (await get(c, quiz["id"]))["status"] == "draft"


@pytest.mark.db
async def test_a_quiz_with_attempts_can_be_closed_but_not_unpublished(shino_class):
    c = shino_class
    quiz = await published(c)
    await insert(attempt_row(quiz["id"], c.student_ids[0]))
    await act(c, quiz["id"], "unpublish", expect=409)
    assert (await get(c, quiz["id"]))["status"] == "published"
    await act(c, quiz["id"], "close")
    await act(c, quiz["id"], "unpublish", expect=409)
    assert (await get(c, quiz["id"]))["status"] == "closed" and await count(QuizAttempt) == 1


# ── access (NFR-04) ──────────────────────────────────────────────────────────

@pytest.mark.db
async def test_lecturer_actions_access(shino_class, users):
    c = shino_class
    draft, live = await ready(c), await published(c)
    people = [(c.student_user_ids[0], "student"), (c.outsider_user_id, "student"),
              (c.other_lecturer_user_id, "lecturer"), (users["admin"].id, "admin")]
    for uid, role in people:
        await act(c, draft["id"], "publish", expect=403, uid=uid, role=role)
        await act(c, live["id"], "unpublish", expect=403, uid=uid, role=role)
        await act(c, live["id"], "close", expect=403, uid=uid, role=role)
    for action in ("publish", "unpublish", "close"):
        await act(c, 99999, action, expect=403)
        async with c.client() as api:
            assert (await api.post(f"{URL}/{draft['id']}/{action}")).status_code in (401, 403)
    assert (await get(c, draft["id"]))["status"] == "draft" and await get(c, live["id"]) == live


@pytest.mark.db
async def test_another_lecturer_of_the_course_may_publish(shino_class):
    c = shino_class
    quiz = await ready(c)
    await insert(ClassOccurrence(course_id=c.course_id, type="TUTORIAL", lecturer_id=c.other_lecturer_id))
    await act(c, quiz["id"], "publish", uid=c.other_lecturer_user_id)


@pytest.mark.db
async def test_cards_are_for_students_only(shino_class, users):
    c = shino_class
    await published(c)
    await cards(c, expect=403, uid=c.lecturer_user_id, role="lecturer")
    await cards(c, expect=403, uid=users["admin"].id, role="admin")
    async with c.client() as api:
        assert (await api.get(MINE)).status_code in (401, 403)


# ── student cards ────────────────────────────────────────────────────────────

@pytest.mark.db
async def test_a_card_shows_the_quiz_and_never_its_questions(shino_class, clock):
    c = shino_class
    quiz = await ready(c, graded(c, timer_mode="question", timer_seconds=45, opens_at="2026-11-30T09:00:00",
                                 closes_at="2026-12-02T09:00:00"), approved=2, unapproved=1)
    await act(c, quiz["id"], "publish")
    [card] = await cards(c)
    assert card == {
        "id": quiz["id"], "course_id": c.course_id, "course_code": "SH101", "course_name": "Shino Test Course",
        "title": "Week 5", "type": "graded", "state": "open", "timer_mode": "question", "timer_seconds": 45,
        "question_count": 2, "opens_at": "2026-11-30T09:00:00", "closes_at": "2026-12-02T09:00:00",
        "published_at": NOW.isoformat(), "attempt_status": None, "submitted_at": None}
    assert "secret" not in json.dumps(card).lower()
    # in every state
    for status in ("published", "closed"):
        await set_status(quiz["id"], status)
        assert "secret" not in json.dumps(await cards(c)).lower()


def test_the_card_schema_has_no_question_content():
    assert set(QuizCardOut.model_fields) == {
        "id", "course_id", "course_code", "course_name", "title", "type", "state", "timer_mode", "timer_seconds",
        "question_count", "opens_at", "closes_at", "published_at", "attempt_status", "submitted_at"}


@pytest.mark.db
async def test_drafts_and_other_courses_have_no_card(shino_class):
    c = shino_class
    await ready(c)
    quiz = await published(c)
    await published_by_other(c)
    assert [x["id"] for x in await cards(c)] == [quiz["id"]]
    assert await cards(c, uid=c.outsider_user_id) == []


async def published_by_other(c) -> dict:
    """A published quiz of SH202, which no student takes."""
    async with AsyncSessionLocal() as db:
        course_id = (await db.get(ClassOccurrence, c.other_occurrence_id)).course_id
    quiz = await create(c, graded(c, course_id=course_id), uid=c.other_lecturer_user_id)
    await insert(question_row(quiz["id"], approved=True))
    return await act(c, quiz["id"], "publish", uid=c.other_lecturer_user_id)


@pytest.mark.db
async def test_two_classes_of_a_course_give_one_card(shino_class):
    c = shino_class
    [tutorial] = await insert(ClassOccurrence(course_id=c.course_id, type="TUTORIAL", lecturer_id=c.lecturer_id))
    await insert(Enrollment(student_id=c.student_ids[0], occurrence_id=tutorial))
    await published(c)
    assert len(await cards(c)) == 1


@pytest.mark.db
async def test_leaving_the_course_takes_the_cards_away(shino_class):
    c = shino_class
    quiz = await published(c)
    await insert(attempt_row(quiz["id"], c.student_ids[0]))
    async with AsyncSessionLocal() as db:
        row = await db.scalar(select(Enrollment).where(Enrollment.student_id == c.student_ids[0]))
        await db.delete(row)
        await db.commit()
    assert await cards(c) == [] and len(await cards(c, 1)) == 1


@pytest.mark.db
async def test_card_state_follows_the_times(shino_class, clock):
    c = shino_class
    opens, closes = NOW + HOUR, NOW + 2 * HOUR
    await published(c, graded(c, opens_at=opens.isoformat(), closes_at=closes.isoformat()))
    for now, state in [(NOW, "upcoming"), (opens - timedelta(seconds=1), "upcoming"), (opens, "open"),
                       (closes - timedelta(seconds=1), "open"), (closes, "closed")]:
        clock.now = now
        assert [x["state"] for x in await cards(c)] == [state], now


@pytest.mark.db
async def test_a_time_with_an_offset_opens_in_malaysia_time(shino_class, clock):
    c = shino_class
    await published(c, graded(c, opens_at=(NOW + HOUR).replace(tzinfo=MYT).isoformat()))
    clock.now = NOW + HOUR
    assert [x["state"] for x in await cards(c)] == ["open"]


@pytest.mark.db
async def test_the_attempt_on_the_card_is_the_students_own(shino_class, clock):
    c = shino_class
    quiz = await published(c)
    await insert(QuizAttempt(quiz_id=quiz["id"], student_id=c.student_ids[0], status="submitted", started_at=NOW,
                             submitted_at=NOW + HOUR),
                 attempt_row(quiz["id"], c.student_ids[1]))
    seen = [(x["state"], x["attempt_status"], x["submitted_at"]) for i in range(3) for x in await cards(c, i)]
    assert seen == [("attempted", "submitted", (NOW + HOUR).isoformat()), ("open", "in_progress", None),
                    ("open", None, None)]
    await act(c, quiz["id"], "close")
    assert [(await cards(c, i))[0]["state"] for i in range(3)] == ["attempted", "attempted", "closed"]


@pytest.mark.db
async def test_card_order(shino_class, clock):
    c = shino_class

    async def make(title, **over):
        clock.now += timedelta(minutes=1)
        return await published(c, graded(c, title=title, **over))

    def at(hours):
        return (NOW + hours * HOUR).isoformat()

    await make("closed early", closes_at=at(1))
    await make("later", opens_at=at(9))
    await make("no end")
    await make("soon", opens_at=at(8))
    await make("ends 7", closes_at=at(7))
    await make("ends 6", closes_at=at(6))
    await act(c, (await make("closed by hand"))["id"], "close")
    clock.now = NOW + 2 * HOUR
    assert [x["title"] for x in await cards(c)] == [
        "ends 6", "ends 7", "no end", "soon", "later", "closed by hand", "closed early"]


# ── the state rule (no database) ─────────────────────────────────────────────

def quiz_row(**over) -> Quiz:
    return Quiz(**{"status": "published", "opens_at": None, "closes_at": None, **over})


@pytest.mark.parametrize(("quiz", "attempt", "state"), [
    ({}, None, "open"),
    ({"opens_at": NOW + HOUR}, None, "upcoming"),
    ({"opens_at": NOW}, None, "open"),
    ({"closes_at": NOW}, None, "closed"),
    ({"status": "closed"}, None, "closed"),
    ({"status": "closed", "opens_at": NOW + HOUR}, None, "closed"),    # closed before it opened
    ({}, {"status": "in_progress"}, "open"),
    ({}, {"status": "in_progress", "ends_at": NOW + HOUR}, "open"),
    ({}, {"status": "in_progress", "ends_at": NOW}, "attempted"),      # its time is up
    ({"closes_at": NOW}, {"status": "in_progress"}, "attempted"),
    ({"status": "closed"}, {"status": "in_progress"}, "attempted"),
    ({}, {"status": "submitted"}, "attempted"),
    ({"status": "closed"}, {"status": "submitted"}, "attempted"),
])
def test_card_state(quiz, attempt, state):
    row = QuizAttempt(**{"ends_at": None, **attempt}) if attempt else None
    assert card_state(quiz_row(**quiz), row, NOW) == state
