"""S34: the interaction event log (FR-517) and the M7 read interface (FR-702, FR-713, FR-513).

Every student action through the M5 API leaves one `m5_events` row (type, student, session, time);
`app.services.interaction_read` turns them into per-student counts (anonymous questions never
counted for the individual) and per-session class totals (anonymous questions counted without
identity). Nothing is graded. The actions go through the real API on the SH101 class (shino_helpers).
"""
import dataclasses
from datetime import timedelta

import pytest
from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.core.timezone import now_myt
from app.models.interaction import EVENT_TYPES, InteractionEvent
from app.services import interaction_read, session_schedule
from app.services.interaction import events, sessions
from tests.shino_helpers import second_session_time

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


async def call(c, method, url, uid, role, body=None, expect=200):
    async with c.client(uid, role) as api:
        r = await api.request(method, url, json=body)
    assert r.status_code == expect, r.text
    return r.json()


async def run_class(c, clock):
    """Drive one class through the API; returns the ids used."""
    s1, s2, s3, _s4 = c.student_user_ids
    sid = c.session_id
    lec = c.lecturer_user_id
    named = await call(c, "POST", f"/interaction/{sid}/questions", s1, "student",
                       {"text": "What is a heap?", "anonymous": False}, 201)
    anon = await call(c, "POST", f"/interaction/{sid}/questions", s1, "student",
                      {"text": "Is this on the exam?", "anonymous": True}, 201)
    anon2 = await call(c, "POST", f"/interaction/{sid}/questions", s2, "student",
                       {"text": "Only anonymous from s2", "anonymous": True}, 201)
    await call(c, "POST", f"/interaction/{sid}/questions/{named['id']}/upvote", s2, "student")
    await call(c, "POST", f"/interaction/{sid}/questions/{named['id']}/upvote", s2, "student")  # repeat
    await call(c, "POST", f"/interaction/{sid}/questions/{anon['id']}/upvote", s3, "student")

    poll = await call(c, "POST", f"/lecturer/interaction/{sid}/polls", lec, "lecturer",
                      {"question": "Pick one", "options": ["A", "B"]}, 201)
    await call(c, "POST", f"/lecturer/interaction/{sid}/polls/{poll['id']}/start", lec, "lecturer")
    a, b = (o["id"] for o in poll["options"])
    await call(c, "POST", f"/interaction/{sid}/polls/{poll['id']}/vote", s1, "student", {"option_ids": [a]})
    await call(c, "POST", f"/interaction/{sid}/polls/{poll['id']}/vote", s1, "student", {"option_ids": [b]})
    await call(c, "POST", f"/interaction/{sid}/polls/{poll['id']}/vote", s2, "student", {"option_ids": [a]})
    # a draft poll is not "run"
    await call(c, "POST", f"/lecturer/interaction/{sid}/polls", lec, "lecturer",
               {"question": "Draft", "options": ["X", "Y"]}, 201)

    quick = await call(c, "POST", f"/lecturer/interaction/{sid}/quick-questions", lec, "lecturer",
                       {"prompt": "One word?"}, 201)
    await call(c, "POST", f"/interaction/{sid}/quick-questions/{quick['id']}/answer", s3, "student",
               {"text": "Trees"})
    await call(c, "POST", f"/interaction/{sid}/quick-questions/{quick['id']}/answer", s3, "student",
               {"text": "Heaps"})                                            # replaced, still one

    await call(c, "POST", f"/interaction/{sid}/reactions", s1, "student", {"kind": "clear"}, 201)
    clock.advance(10)
    await call(c, "POST", f"/interaction/{sid}/reactions", s1, "student", {"kind": "too_fast"}, 201)
    await call(c, "POST", f"/interaction/{sid}/reactions", s3, "student", {"kind": "thumbs_up"}, 201)
    await call(c, "POST", f"/interaction/{sid}/confusion", s3, "student", {"topic": "heaps"}, 201)
    clock.advance(200)
    await call(c, "POST", f"/interaction/{sid}/confusion", s3, "student", {}, 201)
    return {"named": named["id"], "anon": anon["id"], "anon2": anon2["id"], "poll": poll["id"], "quick": quick["id"]}


async def test_every_action_is_logged_with_type_student_session_time(shino_class, clock):
    c = shino_class
    start = clock.now
    ids = await run_class(c, clock)
    async with AsyncSessionLocal() as db:
        rows = list((await db.execute(select(InteractionEvent).order_by(InteractionEvent.id))).scalars())
    s1, s2, s3, _ = c.student_ids
    got = [(e.type, e.student_id, e.ref_id, e.anonymous) for e in rows]
    assert got == [
        ("question_asked", s1, ids["named"], False),
        ("question_asked", s1, ids["anon"], True),
        ("question_asked", s2, ids["anon2"], True),
        ("question_upvoted", s2, ids["named"], False),                      # the repeat adds nothing
        ("question_upvoted", s3, ids["anon"], False),
        ("poll_voted", s1, ids["poll"], False),
        ("poll_voted", s1, ids["poll"], False),                             # each change is an event
        ("poll_voted", s2, ids["poll"], False),
        ("quick_answered", s3, ids["quick"], False),
        ("quick_answered", s3, ids["quick"], False),
        ("reaction", s1, None, False),
        ("reaction", s1, None, False),
        ("reaction", s3, None, False),
        ("confusion", s3, None, False),
        ("confusion", s3, None, False),
    ]
    assert {e.attendance_session_id for e in rows} == {c.session_id}
    assert all(start <= e.created_at <= clock.now for e in rows)
    assert rows[-1].created_at == clock.now
    assert {e.type for e in rows} == set(EVENT_TYPES)


async def test_rejected_actions_leave_no_event(shino_class, clock):
    c = shino_class
    sid = c.session_id
    s1 = c.student_user_ids[0]
    await call(c, "POST", f"/interaction/{sid}/reactions", s1, "student", {"kind": "clear"}, 201)
    await call(c, "POST", f"/interaction/{sid}/reactions", s1, "student", {"kind": "clear"}, 429)  # cooldown
    await call(c, "POST", f"/interaction/{sid}/reactions", c.outsider_user_id, "student",
               {"kind": "clear"}, 403)
    await call(c, "POST", f"/lecturer/interaction/{sid}/close", c.lecturer_user_id, "lecturer")
    await call(c, "POST", f"/interaction/{sid}/confusion", s1, "student", {}, 409)
    async with AsyncSessionLocal() as db:
        types = list((await db.execute(select(InteractionEvent.type))).scalars())
    assert types == ["reaction"]


def test_record_rejects_unknown_type():
    with pytest.raises(ValueError):
        events.record(None, "graded_answer", 1, 1, now_myt())


async def test_per_student_counts_exclude_anonymous_questions(shino_class, clock):
    c = shino_class
    await run_class(c, clock)
    s1, s2, s3, s4 = c.student_ids
    async with AsyncSessionLocal() as db:
        course = await interaction_read.course_student_counts(db, c.course_id)
        per_session = await interaction_read.session_student_counts(db, c.session_id)
        mine = await interaction_read.student_counts(db, s1)
    by = {r.student_id: r for r in course}
    assert [r.student_id for r in course] == [s1, s2, s3, s4]                # matric order, zeros kept
    assert c.outsider_student_id not in by
    r1, r2, r3, r4 = by[s1], by[s2], by[s3], by[s4]
    assert (r1.questions, r1.polls_answered, r1.reactions, r1.upvotes, r1.confusion) == (1, 1, 2, 0, 0)
    assert r1.sessions_active == 1 and r1.course_code == "SH101" and r1.name == "Shino Student 1"
    # s2 only asked anonymously: no question counted for them (FR-713)
    assert (r2.questions, r2.upvotes, r2.polls_answered) == (0, 1, 1)
    assert (r3.quick_answers, r3.reactions, r3.confusion, r3.upvotes) == (1, 1, 2, 1)
    assert dataclasses.astuple(r4)[5:] == (0,) * 7
    assert [dataclasses.astuple(r) for r in per_session] == [dataclasses.astuple(r) for r in course]
    assert len(mine) == 1 and mine[0] == r1


async def test_anonymous_only_student_has_no_trace_in_individual_figures(shino_class, clock):
    c = shino_class
    s4 = c.student_user_ids[3]
    await call(c, "POST", f"/interaction/{c.session_id}/questions", s4, "student",
               {"text": "Secret", "anonymous": True}, 201)
    async with AsyncSessionLocal() as db:
        row = next(r for r in await interaction_read.course_student_counts(db, c.course_id)
                   if r.student_id == c.student_ids[3])
        totals = await interaction_read.session_totals(db, c.session_id)
    assert row.questions == 0 and row.sessions_active == 0       # not even "active" from it
    assert totals.questions == 1 and totals.anonymous_questions == 1


async def test_class_totals_include_anonymous_questions_without_identity(shino_class, clock):
    c = shino_class
    await run_class(c, clock)
    async with AsyncSessionLocal() as db:
        t = await interaction_read.session_totals(db, c.session_id)
        listed = await interaction_read.course_session_totals(db, c.course_id)
        assert await interaction_read.session_totals(db, 999_999) is None
    assert listed == [t]
    assert (t.questions, t.anonymous_questions, t.upvotes) == (3, 2, 2)
    assert (t.polls_run, t.poll_answers, t.quick_answers) == (1, 2, 1)
    assert (t.reactions, t.confusion, t.participants) == (3, 2, 3)
    assert t.course_id == c.course_id and t.course_code == "SH101" and t.date == now_myt().date()
    fields = {f.name for f in dataclasses.fields(t)}
    assert not fields & {"student_id", "student_ids", "name", "matric_no", "students"}


async def test_course_reads_join_sessions_filter_dates_and_isolate_courses(shino_class, clock):
    c = shino_class
    s1 = c.student_user_ids[0]
    await call(c, "POST", f"/interaction/{c.session_id}/reactions", s1, "student", {"kind": "clear"}, 201)
    # end this class, start a second one for the same class
    async with AsyncSessionLocal() as db:
        from app.services import session_service
        await session_service.close_session(c.session_id, db)
        await db.commit()
    async with AsyncSessionLocal() as db:
        from app.models.class_ import ClassOccurrence
        from app.models.user import Lecturer
        occ = await db.get(ClassOccurrence, c.occurrence_id)
        lec = await db.get(Lecturer, c.lecturer_id)
        second = await session_schedule.start_now(db, occ, lec, second_session_time(), duration_minutes=60)
        await db.commit()
        second_id = second.id
    clock.advance(10)
    await call(c, "POST", f"/interaction/{second_id}/reactions", s1, "student", {"kind": "clear"}, 201)
    await call(c, "POST", f"/interaction/{second_id}/confusion", s1, "student", {}, 201)

    today = now_myt().date()
    async with AsyncSessionLocal() as db:
        row = (await interaction_read.student_counts(db, c.student_ids[0], course_id=c.course_id))[0]
        totals = await interaction_read.course_session_totals(db, c.course_id)
        future = await interaction_read.course_student_counts(db, c.course_id, from_date=today + timedelta(days=1))
        other = await interaction_read.course_student_counts(db, c.course_id + 1_000_000)
        other_course = await interaction_read.student_counts(db, c.outsider_student_id)
        with pytest.raises(ValueError):
            await interaction_read.course_student_counts(db, c.course_id, from_date=today,
                                                         to_date=today - timedelta(days=1))
    assert (row.reactions, row.confusion, row.sessions_active) == (2, 1, 2)
    assert [t.session_id for t in totals] == [c.session_id, second_id]
    assert [t.reactions for t in totals] == [1, 1]
    assert all(r.reactions == 0 for r in future)
    assert other == [] and other_course == []


async def test_backfill_migration_matches_live_logging(shino_class, clock):
    """The migration's backfill SQL rebuilds the same counts from the S31–S33 tables."""
    from pathlib import Path

    from sqlalchemy import delete, text

    c = shino_class
    await run_class(c, clock)
    async with AsyncSessionLocal() as db:
        before = await interaction_read.course_student_counts(db, c.course_id)
        before_t = await interaction_read.session_totals(db, c.session_id)
        await db.execute(delete(InteractionEvent))
        src = (Path(__file__).resolve().parents[1] / "alembic" / "versions" / "b8c9d0e1f2a4_m5_events.py").read_text()
        sql = src.split('op.execute("""', 1)[1].split('""")', 1)[0]
        await db.execute(text(sql))
        await db.commit()
    async with AsyncSessionLocal() as db:
        after = await interaction_read.course_student_counts(db, c.course_id)
        after_t = await interaction_read.session_totals(db, c.session_id)
    assert after == before and after_t == before_t
