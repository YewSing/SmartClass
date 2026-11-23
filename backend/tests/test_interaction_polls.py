"""S32: live polls (FR-507–FR-509, NFR-04, FR-513).

Lecturer creates (2–6 options, single/multiple), starts and closes; students vote once and may
change their vote until the poll closes; the lecturer sees live counts and chooses whether
students see them; starting a poll sends `poll.started` to the enrolled students. The class is
started and ended through M3's own services (see shino_helpers).
"""
import asyncio
import json

import pytest
from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.models.interaction import PollVote
from app.models.notification import Notification
from app.services import session_service
from tests.shino_helpers import second_session_time

pytestmark = pytest.mark.db


def lurl(c, *rest) -> str:
    return "/".join([f"/lecturer/interaction/{c.session_id}/polls", *map(str, rest)])


def surl(c, *rest) -> str:
    return "/".join([f"/interaction/{c.session_id}/polls", *map(str, rest)])


async def create(c, body=None, expect=201, uid=None, role="lecturer"):
    body = body or {"question": "Which topic next?", "options": ["Trees", "Graphs", "Heaps"]}
    async with c.client(uid or c.lecturer_user_id, role) as api:
        r = await api.post(lurl(c), json=body)
    assert r.status_code == expect, r.text
    return r.json()


async def lecturer_post(c, pid, action, expect=200):
    async with c.client(c.lecturer_user_id, "lecturer") as api:
        r = await api.post(lurl(c, pid, action))
    assert r.status_code == expect, r.text
    return r.json()


async def vote(c, uid, pid, option_ids, expect=200, role="student"):
    async with c.client(uid, role) as api:
        r = await api.post(surl(c, pid, "vote"), json={"option_ids": option_ids})
    assert r.status_code == expect, r.text
    return r.json()


async def listing(c, uid, role):
    async with c.client(uid, role) as api:
        r = await api.get(surl(c))
    assert r.status_code == 200, r.text
    return r.json()


async def poll_as(c, uid, role, pid):
    found = [p for p in (await listing(c, uid, role))["polls"] if p["id"] == pid]
    return found[0] if found else None


async def started(c, body=None):
    p = await create(c, body)
    return await lecturer_post(c, p["id"], "start")


async def end_class(session_id: int) -> None:
    async with AsyncSessionLocal() as db:
        await session_service.close_session(session_id, db)
        await db.commit()


def counts(poll) -> list:
    return [o["votes"] for o in poll["options"]]


# ── create / validation / access ─────────────────────────────────────────────

async def test_lecturer_creates_draft(shino_class):
    c = shino_class
    p = await create(c, {"question": "  Ready?  ", "options": [" Yes ", "No"], "multiple": True})
    assert p["question"] == "Ready?" and p["status"] == "draft" and p["multiple"] is True
    assert [o["text"] for o in p["options"]] == ["Yes", "No"] and counts(p) == [0, 0]
    assert p["show_results"] is False and p["total_voters"] == 0 and p["my_option_ids"] == []
    assert p["started_at"] is None and p["closed_at"] is None

    # students never see drafts and can't vote on them
    assert (await listing(c, c.student_user_ids[0], "student"))["polls"] == []
    await vote(c, c.student_user_ids[0], p["id"], [p["options"][0]["id"]], expect=404)
    lec = await listing(c, c.lecturer_user_id, "lecturer")
    assert lec["status"] == "open" and [x["id"] for x in lec["polls"]] == [p["id"]]


@pytest.mark.parametrize("body", [
    {"question": "Q", "options": ["only one"]},
    {"question": "Q", "options": [f"o{i}" for i in range(7)]},
    {"question": "Q", "options": ["Same", "same "]},
    {"question": "Q", "options": ["A", "   "]},
    {"question": "   ", "options": ["A", "B"]},
    {"question": "x" * 301, "options": ["A", "B"]},
    {"question": "Q", "options": ["A", "x" * 121]},
    {"question": "Q", "options": ["A", "B"], "graded": True},
])
async def test_create_validation(shino_class, body):
    await create(shino_class, body, expect=422)


async def test_six_options_and_limits_allowed(shino_class):
    p = await create(shino_class, {"question": "x" * 300, "options": [f"o{i}" for i in range(5)] + ["x" * 120]})
    assert len(p["options"]) == 6


async def test_access_matrix(shino_class):
    c = shino_class
    p = await started(c)
    oid = p["options"][0]["id"]
    s = c.student_user_ids[0]
    # students can't create, start, close or change results; the lecturer can't vote
    async with c.client(s, "student") as api:
        assert (await api.post(lurl(c), json={"question": "Q", "options": ["A", "B"]})).status_code == 403
        assert (await api.post(lurl(c, p["id"], "close"))).status_code == 403
        assert (await api.patch(lurl(c, p["id"]), json={"show_results": True})).status_code == 403
    await vote(c, c.lecturer_user_id, p["id"], [oid], expect=403, role="lecturer")
    # outsiders: a not-enrolled student and a lecturer of another class
    for uid, role in [(c.outsider_user_id, "student"), (c.other_lecturer_user_id, "lecturer")]:
        async with c.client(uid, role) as api:
            assert (await api.get(surl(c))).status_code == 403
            assert (await api.post(surl(c, p["id"], "vote"), json={"option_ids": [oid]})).status_code == 403
    await create(c, expect=403, uid=c.other_lecturer_user_id)
    async with c.client(c.other_lecturer_user_id, "lecturer") as api:
        assert (await api.post(lurl(c, p["id"], "close"))).status_code == 403
        assert (await api.patch(lurl(c, p["id"]), json={"show_results": True})).status_code == 403
    async with c.client() as api:
        assert (await api.get(surl(c))).status_code in (401, 403)
    async with c.client(s, "student") as api:
        assert (await api.get(f"/interaction/{c.session_id + 999}/polls")).status_code == 403


# ── lifecycle ────────────────────────────────────────────────────────────────

async def test_start_and_close_lifecycle(shino_class):
    c = shino_class
    p = await create(c)
    await lecturer_post(c, p["id"], "close", expect=409)          # a draft can't be closed
    opened = await lecturer_post(c, p["id"], "start")
    assert opened["status"] == "open" and opened["started_at"]
    await lecturer_post(c, p["id"], "start", expect=409)          # once only
    seen = await poll_as(c, c.student_user_ids[0], "student", p["id"])
    assert seen["status"] == "open"

    closed = await lecturer_post(c, p["id"], "close")
    assert closed["status"] == "closed" and closed["closed_at"]
    again = await lecturer_post(c, p["id"], "close")              # idempotent
    assert again["closed_at"] == closed["closed_at"]
    await lecturer_post(c, p["id"], "start", expect=409)          # can't reopen
    await vote(c, c.student_user_ids[0], p["id"], [p["options"][0]["id"]], expect=409)
    await lecturer_post(c, p["id"] + 999, "start", expect=404)


async def test_poll_of_another_class_session_is_404(shino_class):
    c = shino_class
    p = await started(c)
    await end_class(c.session_id)
    from app.models.class_ import ClassOccurrence
    from app.models.user import Lecturer
    from app.services import session_schedule
    async with AsyncSessionLocal() as db:
        occ = await db.get(ClassOccurrence, c.occurrence_id)
        lec = await db.get(Lecturer, c.lecturer_id)
        s2 = await session_schedule.start_now(db, occ, lec, second_session_time(), duration_minutes=60)
        await db.commit()
        second = s2.id
    async with c.client(c.student_user_ids[0], "student") as api:
        r = await api.post(f"/interaction/{second}/polls/{p['id']}/vote",
                           json={"option_ids": [p["options"][0]["id"]]})
        assert r.status_code == 404
        assert (await api.get(f"/interaction/{second}/polls")).json()["polls"] == []
    async with c.client(c.lecturer_user_id, "lecturer") as api:
        assert (await api.post(f"/lecturer/interaction/{second}/polls/{p['id']}/close")).status_code == 404
        r = await api.patch(f"/lecturer/interaction/{second}/polls/{p['id']}", json={"show_results": True})
        assert r.status_code == 404


# ── voting ───────────────────────────────────────────────────────────────────

async def test_single_choice_vote_once_and_change(shino_class):
    c = shino_class
    s1, s2, s3 = c.student_user_ids[:3]
    p = await started(c)
    a, b, d = (o["id"] for o in p["options"])

    r = await vote(c, s1, p["id"], [a])
    assert r["my_option_ids"] == [a]
    await vote(c, s2, p["id"], [a])
    r = await vote(c, s1, p["id"], [b])                            # change of mind
    assert r["my_option_ids"] == [b]
    await vote(c, s1, p["id"], [b])                                # same again: still one vote

    lec = await poll_as(c, c.lecturer_user_id, "lecturer", p["id"])
    assert counts(lec) == [1, 1, 0] and lec["total_voters"] == 2 and lec["my_option_ids"] == []
    assert (await poll_as(c, s3, "student", p["id"]))["my_option_ids"] == []

    await vote(c, s3, p["id"], [a, b], expect=422)                 # single choice: exactly one
    await vote(c, s3, p["id"], [], expect=422)
    other = await create(c, {"question": "Other", "options": ["X", "Y"]})
    await vote(c, s3, p["id"], [other["options"][0]["id"]], expect=422)   # option of another poll
    async with c.client(s3, "student") as api:
        r = await api.post(surl(c, p["id"], "vote"), json={"option_ids": [d], "student_id": 1})
    assert r.status_code == 422

    async with AsyncSessionLocal() as db:
        rows = (await db.execute(select(PollVote.student_id, PollVote.option_id)
                                 .where(PollVote.poll_id == p["id"]))).all()
    assert sorted(rows) == sorted([(c.student_ids[0], b), (c.student_ids[1], a)])


async def test_multiple_choice_vote_and_change(shino_class):
    c = shino_class
    s1, s2 = c.student_user_ids[:2]
    p = await started(c, {"question": "Which do you use?", "options": ["Vim", "VS Code", "Emacs"],
                          "multiple": True})
    v, code, e = (o["id"] for o in p["options"])
    assert (await vote(c, s1, p["id"], [e, v]))["my_option_ids"] == [v, e]   # option order
    await vote(c, s2, p["id"], [v])
    lec = await poll_as(c, c.lecturer_user_id, "lecturer", p["id"])
    assert counts(lec) == [2, 0, 1] and lec["total_voters"] == 2

    assert (await vote(c, s1, p["id"], [code]))["my_option_ids"] == [code]
    lec = await poll_as(c, c.lecturer_user_id, "lecturer", p["id"])
    assert counts(lec) == [1, 1, 0] and lec["total_voters"] == 2
    await vote(c, s1, p["id"], [code, code], expect=422)


async def test_concurrent_votes_leave_one_choice(shino_class):
    c = shino_class
    s1 = c.student_user_ids[0]
    p = await started(c)
    ids = [o["id"] for o in p["options"]]

    async def one(oid):
        async with c.client(s1, "student") as api:
            return await api.post(surl(c, p["id"], "vote"), json={"option_ids": [oid]})

    results = await asyncio.gather(*(one(ids[i % 3]) for i in range(9)))
    assert all(r.status_code == 200 for r in results)
    async with AsyncSessionLocal() as db:
        n = len((await db.execute(select(PollVote.id).where(PollVote.poll_id == p["id"]))).all())
    assert n == 1


# ── results visibility (FR-509) ──────────────────────────────────────────────

async def test_lecturer_sees_live_results_and_chooses_for_students(shino_class):
    c = shino_class
    s1, s2 = c.student_user_ids[:2]
    p = await started(c)
    a = p["options"][0]["id"]
    after_vote = await vote(c, s1, p["id"], [a])
    assert counts(after_vote) == [None, None, None] and after_vote["total_voters"] is None
    assert after_vote["my_option_ids"] == [a]                      # own vote is always shown
    hidden = await poll_as(c, s2, "student", p["id"])
    assert counts(hidden) == [None, None, None] and hidden["show_results"] is False
    assert counts(await poll_as(c, c.lecturer_user_id, "lecturer", p["id"])) == [1, 0, 0]

    async with c.client(c.lecturer_user_id, "lecturer") as api:
        r = await api.patch(lurl(c, p["id"]), json={"show_results": True})
        assert r.status_code == 200 and r.json()["show_results"] is True
        assert (await api.patch(lurl(c, p["id"]), json={"show_results": "yes please"})).status_code == 422
    shown = await poll_as(c, s2, "student", p["id"])
    assert counts(shown) == [1, 0, 0] and shown["total_voters"] == 1

    await lecturer_post(c, p["id"], "close")                       # still shown after close
    assert counts(await poll_as(c, s2, "student", p["id"])) == [1, 0, 0]
    async with c.client(c.lecturer_user_id, "lecturer") as api:
        assert (await api.patch(lurl(c, p["id"]), json={"show_results": False})).status_code == 200
    assert counts(await poll_as(c, s2, "student", p["id"])) == [None, None, None]

    # created with results shown from the start
    q = await started(c, {"question": "Q2", "options": ["A", "B"], "show_results": True})
    assert counts(await poll_as(c, s2, "student", q["id"])) == [0, 0]


async def test_no_voter_identity_in_responses(shino_class):
    c = shino_class
    p = await started(c, {"question": "Q", "options": ["A", "B"], "show_results": True})
    await vote(c, c.student_user_ids[0], p["id"], [p["options"][0]["id"]])
    payloads = [await listing(c, uid, role) for uid, role in
                [(c.lecturer_user_id, "lecturer"), (c.student_user_ids[1], "student")]]
    raw = json.dumps(payloads)
    assert "Shino Student 1" not in raw
    for key in ("student_id", "user_id", "voters", "name"):
        assert f'"{key}"' not in raw


# ── poll.started notification ────────────────────────────────────────────────

async def _notes():
    async with AsyncSessionLocal() as db:
        return list((await db.execute(select(Notification).where(Notification.event == "poll.started")
                                      .order_by(Notification.user_id))).scalars())


async def test_start_notifies_enrolled_students_only(shino_class):
    c = shino_class
    p = await create(c)
    assert await _notes() == []                                    # a draft sends nothing
    await lecturer_post(c, p["id"], "start")
    notes = await _notes()
    assert sorted(n.user_id for n in notes) == sorted(c.student_user_ids)
    for n in notes:
        assert n.priority == "general"
        assert n.link == f"/interaction/{c.session_id}"
        assert "SH101" in n.title
    await lecturer_post(c, p["id"], "close")
    assert len(await _notes()) == len(c.student_user_ids)          # close sends nothing more


async def test_failed_start_sends_nothing(shino_class):
    c = shino_class
    p = await create(c)
    async with c.client(c.lecturer_user_id, "lecturer") as api:
        assert (await api.post(f"/lecturer/interaction/{c.session_id}/close")).status_code == 200
    await lecturer_post(c, p["id"], "start", expect=409)
    assert await _notes() == []


# ── closed interaction ───────────────────────────────────────────────────────

async def test_writes_rejected_once_closed_but_list_still_works(shino_class):
    c = shino_class
    s1, s2 = c.student_user_ids[:2]
    p = await started(c)
    a, b = p["options"][0]["id"], p["options"][1]["id"]
    await vote(c, s1, p["id"], [a])
    draft = await create(c)

    async with c.client(c.lecturer_user_id, "lecturer") as api:     # lecturer closes early
        assert (await api.post(f"/lecturer/interaction/{c.session_id}/close")).status_code == 200
    await vote(c, s2, p["id"], [b], expect=409)
    await create(c, expect=409)
    await lecturer_post(c, draft["id"], "start", expect=409)
    await lecturer_post(c, p["id"], "close", expect=409)
    assert (await poll_as(c, s1, "student", p["id"]))["status"] == "closed"

    async with c.client(c.lecturer_user_id, "lecturer") as api:     # reopen: the poll is live again
        assert (await api.post(f"/lecturer/interaction/{c.session_id}/open")).status_code == 200
    assert (await poll_as(c, s1, "student", p["id"]))["status"] == "open"
    await vote(c, s2, p["id"], [b])

    await end_class(c.session_id)
    await vote(c, s1, p["id"], [b], expect=409)
    async with c.client(c.lecturer_user_id, "lecturer") as api:
        assert (await api.patch(lurl(c, p["id"]), json={"show_results": True})).status_code == 409
    body = await listing(c, c.lecturer_user_id, "lecturer")
    assert body["status"] == "closed"
    mine = [x for x in body["polls"] if x["id"] == p["id"]][0]
    assert mine["status"] == "closed" and counts(mine) == [1, 1, 0]
