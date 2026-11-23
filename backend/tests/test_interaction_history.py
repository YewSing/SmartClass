"""S38d: the lecturer's Interaction tab — `GET /lecturer/interaction/sessions`.

Classes are run through the real interaction endpoints and ended/started through M3's own services.
The list shows only class sessions the caller teaches that have interaction data (a draft poll alone
doesn't count), newest first by class start, with counts per category and no student identity.
"""
from datetime import datetime, timedelta

import pytest
from sqlalchemy import update

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.models.class_ import ClassOccurrence
from app.models.interaction import Reaction
from app.models.session import AttendanceSession
from app.models.user import Lecturer
from app.services import session_schedule
from app.services.interaction import sessions
from tests.test_interaction_questions import assert_no_identity, identity
from tests.test_interaction_summary import call, end_class, iurl, lurl, run_class, second_session

pytestmark = pytest.mark.db

URL = "/lecturer/interaction/sessions"
T0 = datetime(2026, 11, 23, 9, 0)


@pytest.fixture
def clock(monkeypatch):
    """One minute on per call, no cooldowns (as in test_interaction_summary)."""
    state = {"t": T0}

    def tick():
        state["t"] += timedelta(minutes=1)
        return state["t"]

    monkeypatch.setattr(sessions, "clock", tick)
    monkeypatch.setattr(settings, "INTERACTION_CONFUSION_COOLDOWN_SECONDS", 0)
    monkeypatch.setattr(settings, "INTERACTION_REACTION_COOLDOWN_SECONDS", 0)
    return state


async def listing(c, uid=None, expect=200, **params):
    r = await call(c, uid or c.lecturer_user_id, "lecturer", "get", URL, params=params, expect=expect)
    return r.json()


async def set_opened(session_id: int, when: datetime) -> None:
    async with AsyncSessionLocal() as db:
        await db.execute(update(AttendanceSession).where(AttendanceSession.id == session_id)
                         .values(opened_at=when))
        await db.commit()


async def other_lecturer_session(c) -> int:
    async with AsyncSessionLocal() as db:
        occ = await db.get(ClassOccurrence, c.other_occurrence_id)
        lec = await db.get(Lecturer, c.other_lecturer_id)
        s = await session_schedule.start_now(db, occ, lec, session_schedule.clock(), duration_minutes=60)
        await db.commit()
        return s.id


async def test_lists_taught_sessions_with_counts(shino_class, clock):
    c = shino_class
    await run_class(c)
    body = await listing(c)
    assert body["total"] == 1 and body["next_offset"] is None
    [item] = body["sessions"]
    assert item["attendance_session_id"] == c.session_id
    assert item["occurrence_id"] == c.occurrence_id
    assert (item["course_code"], item["course_name"]) == ("SH101", "Shino Test Course")
    assert item["class_type"] == "LECTURE"
    assert item["class_status"] == "open" and item["status"] == "open"
    assert item["class_date"] and item["starts_at"]
    # 3 questions (hidden one too), 1 poll that ran (draft left out), 1 quick question, 3 reactions,
    # 3 confusion presses — the same numbers as the S36 summary
    assert item["counts"] == {"questions": 3, "polls": 1, "quick_questions": 1, "reactions": 3, "confusion": 3}
    for uid in c.student_user_ids:
        assert_no_identity(body, await identity(uid), "interaction sessions")

    # After the class ends it stays listed, now closed
    await end_class(c.session_id)
    [item] = (await listing(c))["sessions"]
    assert item["class_status"] == "closed" and item["status"] == "closed"
    assert item["ends_at"] is not None


async def test_sessions_without_data_are_left_out(shino_class, clock):
    c = shino_class
    assert (await listing(c)) == {"sessions": [], "total": 0, "next_offset": None}
    # A draft poll alone is not interaction data (the summary leaves drafts out too)
    await call(c, c.lecturer_user_id, "lecturer", "post", lurl(c, "polls"),
               json={"question": "Never started", "options": ["a", "b"]}, expect=201)
    assert (await listing(c))["total"] == 0
    # A single reaction is
    await call(c, c.student_user_ids[0], "student", "post", iurl(c, "reactions"),
               json={"kind": "clear"}, expect=201)
    [item] = (await listing(c))["sessions"]
    assert item["counts"] == {"questions": 0, "polls": 0, "quick_questions": 0, "reactions": 1, "confusion": 0}


async def test_newest_first_and_paging(shino_class, clock):
    c = shino_class
    s1 = c.session_id
    await call(c, c.student_user_ids[0], "student", "post", iurl(c, "questions"),
               json={"text": "first class", "anonymous": False}, expect=201)
    await end_class(s1)
    s2 = await second_session(c)
    await call(c, c.student_user_ids[1], "student", "post", iurl(c, "confusion", sid=s2), json={}, expect=201)
    s3 = await second_session_after(c, s2)
    await call(c, c.student_user_ids[2], "student", "post", iurl(c, "reactions", sid=s3),
               json={"kind": "too_slow"}, expect=201)

    # Order is by class start, not by id: s1 started last, s3 first
    await set_opened(s1, datetime(2026, 11, 30, 8, 0))
    await set_opened(s2, datetime(2026, 11, 23, 8, 0))
    await set_opened(s3, datetime(2026, 11, 16, 8, 0))
    body = await listing(c)
    assert [s["attendance_session_id"] for s in body["sessions"]] == [s1, s2, s3]
    assert body["total"] == 3

    p1 = await listing(c, limit=2)
    assert [s["attendance_session_id"] for s in p1["sessions"]] == [s1, s2]
    assert p1["total"] == 3 and p1["next_offset"] == 2
    p2 = await listing(c, limit=2, offset=p1["next_offset"])
    assert [s["attendance_session_id"] for s in p2["sessions"]] == [s3]
    assert p2["next_offset"] is None
    assert (await listing(c, offset=10))["sessions"] == []
    await listing(c, expect=422, limit=0)
    await listing(c, expect=422, limit=101)
    await listing(c, expect=422, offset=-1)


async def second_session_after(c, previous: int) -> int:
    """A third SH101 session: end the previous one, then start another (outside the slot)."""
    await end_class(previous)
    return await second_session(c)


async def test_only_the_teaching_lecturer(shino_class, clock):
    c = shino_class
    await call(c, c.student_user_ids[0], "student", "post", iurl(c, "questions"),
               json={"text": "mine", "anonymous": True}, expect=201)
    other = await other_lecturer_session(c)
    # The other class has data too (nobody is enrolled there, so a raw row stands in for a reaction)
    async with AsyncSessionLocal() as db:
        db.add(Reaction(attendance_session_id=other, kind="clear", created_at=datetime(2026, 11, 23, 10, 5)))
        await db.commit()

    mine = await listing(c)
    assert [s["attendance_session_id"] for s in mine["sessions"]] == [c.session_id]
    theirs = await listing(c, uid=c.other_lecturer_user_id)
    assert [s["attendance_session_id"] for s in theirs["sessions"]] == [other]
    assert theirs["sessions"][0]["course_code"] == "SH202"

    # Students can't read it, nor can anyone without a token
    await call(c, c.student_user_ids[0], "student", "get", URL, expect=403)
    async with c.client() as anon:
        assert (await anon.get(URL)).status_code in (401, 403)
