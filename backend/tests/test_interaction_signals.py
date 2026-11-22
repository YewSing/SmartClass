"""S33: quick questions, reactions and "I don't understand" (FR-510–FR-512, FR-514, FR-515, NFR-04).

Quick questions collect length-limited text answers that the lecturer sees as a list with no names;
reactions have a per-student cooldown and running counts; confusion presses have a configurable
cooldown (default 2 min) and the lecturer sees only the count, timeline and topics; a
`confusion.spike` goes to the lecturer once per spike when the presses in the window reach the
configured share of the class (defaults 2 min / 25%). The clock (`sessions.clock`) is
monkeypatched; the class is started and ended through M3's own services (see shino_helpers).
"""
import asyncio
import json
from datetime import timedelta

import pytest
from sqlalchemy import select

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.core.timezone import now_myt
from app.models.interaction import ConfusionPress, QuickAnswer, Reaction
from app.models.notification import Notification
from app.services import session_service
from app.services.interaction import sessions, signals

pytestmark = pytest.mark.db


class Clock:
    def __init__(self):
        self.now = now_myt().replace(microsecond=0)

    def __call__(self):
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += timedelta(seconds=seconds)


@pytest.fixture
def clock(monkeypatch) -> Clock:
    c = Clock()
    monkeypatch.setattr(sessions, "clock", c)
    return c


async def call(c, method, url, uid, role, json_body=None, expect=200):
    async with c.client(uid, role) as api:
        r = await api.request(method, url, json=json_body)
    assert r.status_code == expect, r.text
    return r


async def end_class(session_id: int) -> None:
    async with AsyncSessionLocal() as db:
        await session_service.close_session(session_id, db)
        await db.commit()


async def close_interaction(c) -> None:
    await call(c, "POST", f"/lecturer/interaction/{c.session_id}/close", c.lecturer_user_id, "lecturer")


def no_identity(c, payload) -> None:
    raw = json.dumps(payload)
    for i in range(1, 5):
        assert f"Shino Student {i}" not in raw
    for key in ("student_id", "user_id", "name", "author_name", "students", "matric_no"):
        assert f'"{key}"' not in raw


# ── quick questions (FR-510) ─────────────────────────────────────────────────

def qurl(c, *rest, lecturer=False) -> str:
    base = f"/lecturer/interaction/{c.session_id}" if lecturer else f"/interaction/{c.session_id}"
    return "/".join([f"{base}/quick-questions", *map(str, rest)])


async def ask_quick(c, body=None, expect=201, uid=None):
    body = body or {"prompt": "One word for today's lecture?"}
    r = await call(c, "POST", qurl(c, lecturer=True), uid or c.lecturer_user_id, "lecturer", body, expect)
    return r.json()


async def answer(c, uid, qid, text, expect=200, role="student"):
    return (await call(c, "POST", qurl(c, qid, "answer"), uid, role, {"text": text}, expect)).json()


async def quick_list(c, uid, role):
    return (await call(c, "GET", qurl(c), uid, role)).json()


async def test_quick_question_answers_list_for_lecturer_anonymous_to_class(shino_class, clock):
    c = shino_class
    s1, s2, s3 = c.student_user_ids[:3]
    q = await ask_quick(c, {"prompt": "  One word?  "})
    assert q["prompt"] == "One word?" and q["status"] == "open"
    assert q["max_chars"] == settings.INTERACTION_QUICK_ANSWER_DEFAULT_CHARS == 140
    assert q["answers"] == [] and q["answer_count"] == 0

    mine = await answer(c, s1, q["id"], "  Recursion ")
    assert mine["my_answer"] == "Recursion" and mine["answers"] is None and mine["answer_count"] is None
    clock.advance(5)
    await answer(c, s2, q["id"], "Trees")
    clock.advance(5)
    await answer(c, s1, q["id"], "Stacks")                          # replaces s1's answer

    lec = (await quick_list(c, c.lecturer_user_id, "lecturer"))["quick_questions"][0]
    assert lec["answer_count"] == 2
    assert [a["text"] for a in lec["answers"]] == ["Trees", "Stacks"]   # oldest change first
    # students see only their own answer, never the others'
    st1 = (await quick_list(c, s1, "student"))["quick_questions"][0]
    st3 = (await quick_list(c, s3, "student"))["quick_questions"][0]
    assert st1["my_answer"] == "Stacks" and st1["answers"] is None
    assert st3["my_answer"] is None and st3["answers"] is None
    for payload in (lec, st1, st3):
        no_identity(c, payload)
    assert "Trees" not in json.dumps(st1) and "Stacks" not in json.dumps(st3)

    async with AsyncSessionLocal() as db:                           # one row per student
        rows = list((await db.execute(select(QuickAnswer).where(QuickAnswer.quick_question_id == q["id"]))).scalars())
    assert sorted(r.student_id for r in rows) == sorted(c.student_ids[:2])


async def test_quick_answer_length_limit(shino_class, clock):
    c = shino_class
    q = await ask_quick(c, {"prompt": "Short?", "max_chars": 10})
    assert q["max_chars"] == 10
    await answer(c, c.student_user_ids[0], q["id"], "x" * 11, expect=422)
    await answer(c, c.student_user_ids[0], q["id"], "x" * 10)
    await answer(c, c.student_user_ids[0], q["id"], "   ", expect=422)
    await answer(c, c.student_user_ids[0], q["id"], "x" * 501, expect=422)


@pytest.mark.parametrize("body", [
    {"prompt": "   "},
    {"prompt": "x" * 301},
    {"prompt": "Q", "max_chars": 0},
    {"prompt": "Q", "max_chars": 501},
    {"prompt": "Q", "graded": True},
])
async def test_quick_question_validation(shino_class, body):
    await ask_quick(shino_class, body, expect=422)


async def test_quick_question_default_length_is_configurable(shino_class, monkeypatch):
    monkeypatch.setattr(settings, "INTERACTION_QUICK_ANSWER_DEFAULT_CHARS", 20)
    assert (await ask_quick(shino_class))["max_chars"] == 20


async def test_quick_question_close_and_access(shino_class, clock):
    c = shino_class
    s = c.student_user_ids[0]
    q = await ask_quick(c)
    # students can't ask or close; the lecturer can't answer; outsiders get 403
    await call(c, "POST", qurl(c, lecturer=True), s, "student", {"prompt": "Q"}, 403)
    await call(c, "POST", qurl(c, q["id"], "close", lecturer=True), s, "student", None, 403)
    await answer(c, c.lecturer_user_id, q["id"], "hi", expect=403, role="lecturer")
    for uid, role in [(c.outsider_user_id, "student"), (c.other_lecturer_user_id, "lecturer")]:
        await call(c, "GET", qurl(c), uid, role, None, 403)
        await call(c, "POST", qurl(c, q["id"], "answer"), uid, role, {"text": "hi"}, 403)
    await ask_quick(c, expect=403, uid=c.other_lecturer_user_id)
    await answer(c, s, q["id"] + 999, "hi", expect=404)

    closed = (await call(c, "POST", qurl(c, q["id"], "close", lecturer=True),
                         c.lecturer_user_id, "lecturer")).json()
    assert closed["status"] == "closed" and closed["closed_at"] is not None
    again = (await call(c, "POST", qurl(c, q["id"], "close", lecturer=True),
                        c.lecturer_user_id, "lecturer")).json()
    assert again["closed_at"] == closed["closed_at"]                # idempotent
    await answer(c, s, q["id"], "late", expect=409)


async def test_quick_writes_rejected_once_interaction_closed(shino_class, clock):
    c = shino_class
    s = c.student_user_ids[0]
    q = await ask_quick(c)
    await answer(c, s, q["id"], "before")
    await close_interaction(c)
    await answer(c, s, q["id"], "after", expect=409)
    await ask_quick(c, expect=409)
    body = await quick_list(c, s, "student")
    assert body["status"] == "closed" and body["quick_questions"][0]["status"] == "closed"
    assert body["quick_questions"][0]["my_answer"] == "before"


# ── reactions (FR-511) ───────────────────────────────────────────────────────

def rurl(c) -> str:
    return f"/interaction/{c.session_id}/reactions"


async def react(c, uid, kind, expect=201, role="student"):
    async with c.client(uid, role) as api:
        r = await api.post(rurl(c), json={"kind": kind})
    assert r.status_code == expect, r.text
    return r


async def counts(c):
    return (await call(c, "GET", f"/lecturer/interaction/{c.session_id}/reactions",
                       c.lecturer_user_id, "lecturer")).json()


async def test_reactions_running_counts_and_cooldown(shino_class, clock):
    c = shino_class
    s1, s2 = c.student_user_ids[:2]
    assert settings.INTERACTION_REACTION_COOLDOWN_SECONDS == 5
    ack = (await react(c, s1, "too_fast")).json()
    assert ack["kind"] == "too_fast"
    assert ack["next_allowed_at"] == (clock.now + timedelta(seconds=5)).isoformat()

    clock.advance(2)
    r = await react(c, s1, "thumbs_up", expect=429)                # cooldown is per student
    assert r.headers["Retry-After"] == "3"
    await react(c, s2, "too_fast")                                  # another student isn't blocked
    clock.advance(3)
    await react(c, s1, "clear")                                     # cooldown over

    body = await counts(c)
    assert body["counts"] == {"thumbs_up": 0, "clear": 1, "too_fast": 2, "too_slow": 0}
    assert body["total"] == 3 and body["status"] == "open"
    no_identity(c, body)


async def test_reaction_cooldown_configurable(shino_class, clock, monkeypatch):
    c = shino_class
    monkeypatch.setattr(settings, "INTERACTION_REACTION_COOLDOWN_SECONDS", 30)
    await react(c, c.student_user_ids[0], "clear")
    clock.advance(29)
    assert (await react(c, c.student_user_ids[0], "clear", expect=429)).headers["Retry-After"] == "1"
    clock.advance(1)
    await react(c, c.student_user_ids[0], "clear")


async def test_reaction_validation_and_access(shino_class, clock):
    c = shino_class
    s = c.student_user_ids[0]
    await react(c, s, "angry", expect=422)
    await react(c, c.lecturer_user_id, "clear", expect=403, role="lecturer")
    await react(c, c.outsider_user_id, "clear", expect=403)
    await call(c, "GET", f"/lecturer/interaction/{c.session_id}/reactions", s, "student", None, 403)
    await call(c, "GET", f"/lecturer/interaction/{c.session_id}/reactions",
               c.other_lecturer_user_id, "lecturer", None, 403)
    async with AsyncSessionLocal() as db:
        assert (await db.execute(select(Reaction))).first() is None


async def test_reactions_rejected_once_closed(shino_class, clock):
    c = shino_class
    await react(c, c.student_user_ids[0], "clear")
    await end_class(c.session_id)
    clock.advance(60)
    await react(c, c.student_user_ids[1], "clear", expect=409)
    body = await counts(c)
    assert body["status"] == "closed" and body["total"] == 1


# ── "I don't understand" (FR-512, FR-515) ────────────────────────────────────

def curl(c) -> str:
    return f"/interaction/{c.session_id}/confusion"


async def press(c, uid, topic=None, expect=201, role="student"):
    body = {} if topic is None else {"topic": topic}
    async with c.client(uid, role) as api:
        r = await api.post(curl(c), json=body)
    assert r.status_code == expect, r.text
    return r


async def view(c):
    return (await call(c, "GET", f"/lecturer/interaction/{c.session_id}/confusion",
                       c.lecturer_user_id, "lecturer")).json()


async def test_confusion_default_cooldown_two_minutes(shino_class, clock):
    c = shino_class
    s = c.student_user_ids[0]
    assert settings.INTERACTION_CONFUSION_COOLDOWN_SECONDS == 120
    ack = (await press(c, s)).json()
    assert ack["next_allowed_at"] == (clock.now + timedelta(minutes=2)).isoformat()
    clock.advance(119)
    assert (await press(c, s, expect=429)).headers["Retry-After"] == "1"
    clock.advance(1)
    await press(c, s, "Recursion")


async def test_confusion_cooldown_configurable(shino_class, clock, monkeypatch):
    c = shino_class
    monkeypatch.setattr(settings, "INTERACTION_CONFUSION_COOLDOWN_SECONDS", 10)
    await press(c, c.student_user_ids[0])
    clock.advance(9)
    await press(c, c.student_user_ids[0], expect=429)
    clock.advance(1)
    await press(c, c.student_user_ids[0])


async def test_confusion_lecturer_sees_count_timeline_and_topics_only(shino_class, clock, monkeypatch):
    c = shino_class
    monkeypatch.setattr(settings, "INTERACTION_CONFUSION_SPIKE_SHARE", 1.0)   # no spike here
    s1, s2, s3 = c.student_user_ids[:3]
    start = clock.now
    await press(c, s1, "  Big   O ")
    clock.advance(10)
    await press(c, s2, "Big O")
    clock.advance(200)
    await press(c, s3)
    await press(c, s1, "Recursion")

    body = await view(c)
    assert body["total"] == 4 and body["recent"] == 2 and body["recent_students"] == 2
    assert body["class_size"] == 4 and body["window_seconds"] == 120
    assert body["spike_active"] is False and body["spikes"] == 0
    assert body["topics"] == [{"topic": "Big O", "count": 2}, {"topic": "Recursion", "count": 1}]
    assert sum(b["count"] for b in body["timeline"]) == 4
    starts = [b["start"] for b in body["timeline"]]
    assert starts == sorted(starts) and len(starts) >= 2
    first = start.replace(second=0)
    assert body["timeline"][0]["start"] == first.isoformat()
    no_identity(c, body)

    async with AsyncSessionLocal() as db:                           # stored with the student for M7
        rows = list((await db.execute(select(ConfusionPress).order_by(ConfusionPress.id))).scalars())
    assert [r.student_id for r in rows] == [c.student_ids[0], c.student_ids[1], c.student_ids[2], c.student_ids[0]]
    assert rows[0].topic == "Big O"


async def test_confusion_validation_and_access(shino_class, clock):
    c = shino_class
    s = c.student_user_ids[0]
    await press(c, s, "x" * 61, expect=422)
    await press(c, c.lecturer_user_id, expect=403, role="lecturer")
    await press(c, c.outsider_user_id, expect=403)
    await call(c, "GET", f"/lecturer/interaction/{c.session_id}/confusion", s, "student", None, 403)
    await call(c, "GET", f"/lecturer/interaction/{c.session_id}/confusion",
               c.other_lecturer_user_id, "lecturer", None, 403)
    async with c.client() as api:
        assert (await api.post(curl(c), json={})).status_code in (401, 403)
    await press(c, s, "   ")                                         # blank topic = no topic
    async with AsyncSessionLocal() as db:
        assert (await db.execute(select(ConfusionPress.topic))).scalar_one() is None


async def test_confusion_rejected_once_closed_view_still_works(shino_class, clock):
    c = shino_class
    await press(c, c.student_user_ids[0])
    await close_interaction(c)
    await press(c, c.student_user_ids[1], expect=409)
    body = await view(c)
    assert body["status"] == "closed" and body["total"] == 1


# ── confusion.spike (FR-514) ─────────────────────────────────────────────────

async def spikes():
    async with AsyncSessionLocal() as db:
        return list((await db.execute(select(Notification).where(Notification.event == "confusion.spike")
                                      .order_by(Notification.id))).scalars())


def test_spike_threshold_rule(monkeypatch):
    assert settings.INTERACTION_CONFUSION_SPIKE_SHARE == 0.25
    assert settings.INTERACTION_CONFUSION_WINDOW_SECONDS == 120
    assert signals.spike_reached(1, 4) and not signals.spike_reached(0, 4)
    assert not signals.spike_reached(2, 10) and signals.spike_reached(3, 10)   # ceil(2.5) = 3
    assert not signals.spike_reached(5, 0)
    monkeypatch.setattr(settings, "INTERACTION_CONFUSION_SPIKE_SHARE", 0.3)
    assert signals.spike_reached(3, 10) and not signals.spike_reached(2, 10)    # 0.3*10 is exactly 3


async def test_default_spike_notifies_lecturer_once(shino_class, clock):
    c = shino_class                                                  # 4 students: 25% = 1 press
    await press(c, c.student_user_ids[0])
    notes = await spikes()
    assert len(notes) == 1
    n = notes[0]
    assert n.user_id == c.lecturer_user_id and n.priority == "urgent"
    assert n.link == f"/interaction/{c.session_id}" and "SH101" in n.title
    clock.advance(30)
    await press(c, c.student_user_ids[1])                            # same spike: nothing new
    assert len(await spikes()) == 1
    assert (await view(c))["spike_active"] is True


async def test_spike_once_per_spike_and_again_after_a_quiet_window(shino_class, clock, monkeypatch):
    c = shino_class
    monkeypatch.setattr(settings, "INTERACTION_CONFUSION_SPIKE_SHARE", 0.5)   # 2 of 4 students
    s1, s2, s3, s4 = c.student_user_ids
    await press(c, s1)
    assert await spikes() == []                                      # 1 of 4 is below 50%
    clock.advance(30)
    await press(c, s2)
    assert len(await spikes()) == 1                                  # 2 of 4 within 2 min
    clock.advance(30)
    await press(c, s3)
    clock.advance(60)
    await press(c, s4)                                               # still the same spike
    assert len(await spikes()) == 1
    body = await view(c)
    assert body["spike_active"] is True and body["spikes"] == 1

    clock.advance(121)                                               # a whole window quiet
    assert (await view(c))["spike_active"] is False
    await press(c, s1)
    assert len(await spikes()) == 1
    clock.advance(10)
    await press(c, s2)
    notes = await spikes()
    assert len(notes) == 2 and {n.user_id for n in notes} == {c.lecturer_user_id}
    assert notes[0].subject_key != notes[1].subject_key


async def test_presses_outside_the_window_dont_add_up(shino_class, clock, monkeypatch):
    c = shino_class
    monkeypatch.setattr(settings, "INTERACTION_CONFUSION_SPIKE_SHARE", 0.5)
    await press(c, c.student_user_ids[0])
    clock.advance(121)
    await press(c, c.student_user_ids[1])
    assert await spikes() == []
    monkeypatch.setattr(settings, "INTERACTION_CONFUSION_WINDOW_SECONDS", 300)   # configurable window
    clock.advance(1)
    await press(c, c.student_user_ids[2])
    assert len(await spikes()) == 1


async def test_concurrent_presses_raise_one_spike(shino_class, clock, monkeypatch):
    c = shino_class
    monkeypatch.setattr(settings, "INTERACTION_CONFUSION_SPIKE_SHARE", 0.5)
    await asyncio.gather(*(press(c, uid) for uid in c.student_user_ids))
    assert len(await spikes()) == 1
    assert (await view(c))["spikes"] == 1


async def test_no_spike_notification_when_press_rejected(shino_class, clock):
    c = shino_class
    await close_interaction(c)
    await press(c, c.student_user_ids[0], expect=409)
    assert await spikes() == []
