"""S31: live questions (FR-503–FR-506, NFR-04, NFR-06).

Ask (optionally anonymous), upvote once, list by votes then time, lecturer answers / pins / hides
(hide audited), and anonymity: an anonymous question's asker shows up in no response shape and no
audit value. The class is started and ended through M3's own services (see shino_helpers).
"""
import json

import pytest
from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.models.audit import AuditLog
from app.models.interaction import Question
from app.models.user import Student, User
from app.services import session_service
from app.services.interaction import sessions

pytestmark = pytest.mark.db


def qurl(c, *rest) -> str:
    return "/".join([f"/interaction/{c.session_id}/questions", *map(str, rest)]).rstrip("/")


def murl(c, qid) -> str:
    return f"/lecturer/interaction/{c.session_id}/questions/{qid}"


async def ask(c, uid, text="What is a monad?", anonymous=False, expect=201):
    async with c.client(uid, "student") as api:
        r = await api.post(qurl(c), json={"text": text, "anonymous": anonymous})
    assert r.status_code == expect, r.text
    return r.json()


async def upvote(c, uid, qid, role="student"):
    async with c.client(uid, role) as api:
        return await api.post(qurl(c, qid, "upvote"))


async def listing(c, uid, role):
    async with c.client(uid, role) as api:
        r = await api.get(qurl(c))
    assert r.status_code == 200, r.text
    return r.json()


async def moderate(c, qid, body, uid=None):
    async with c.client(uid or c.lecturer_user_id, "lecturer") as api:
        return await api.patch(murl(c, qid), json=body)


async def end_class(session_id: int) -> None:
    async with AsyncSessionLocal() as db:
        await session_service.close_session(session_id, db)
        await db.commit()


async def identity(user_id: int) -> dict:
    """Everything that could identify a student in a response."""
    async with AsyncSessionLocal() as db:
        u = await db.get(User, user_id)
        s = await db.scalar(select(Student).where(Student.user_id == user_id))
    return {"user_id": u.id, "student_id": s.id, "name": u.name, "email": u.email, "matric": s.matric_no}


def assert_no_identity(payload, who: dict, where: str) -> None:
    """No name/email/matric text anywhere and no id-bearing key in the payload."""
    raw = json.dumps(payload)
    for key in ("name", "email", "matric"):
        assert who[key] not in raw, f"{where}: {key} leaked"

    def walk(v):
        if isinstance(v, dict):
            for k, val in v.items():
                assert k not in ("student_id", "user_id", "asker_id", "email", "matric_no"), f"{where}: key {k}"
                walk(val)
        elif isinstance(v, list):
            for x in v:
                walk(x)
    walk(payload)


# ── asking ───────────────────────────────────────────────────────────────────

async def test_student_asks_named_and_anonymous(shino_class):
    c = shino_class
    s1, s2 = c.student_user_ids[:2]
    named = await ask(c, s1, "  Why is the sky blue?  ")
    assert named["text"] == "Why is the sky blue?"
    assert named["anonymous"] is False and named["author_name"] == "Shino Student 1"
    assert named["mine"] is True and named["upvotes"] == 0 and named["upvoted_by_me"] is False
    assert named["answered"] is False and named["pinned"] is False and named["hidden"] is False

    anon = await ask(c, s2, "Can you repeat slide 4?", anonymous=True)
    assert anon["anonymous"] is True and anon["author_name"] is None and anon["mine"] is True

    lec = await listing(c, c.lecturer_user_id, "lecturer")
    assert lec["status"] == "open"
    by_id = {q["id"]: q for q in lec["questions"]}
    assert by_id[named["id"]]["author_name"] == "Shino Student 1"
    assert by_id[anon["id"]]["author_name"] is None
    assert all(q["mine"] is False for q in lec["questions"])

    other = await listing(c, c.student_user_ids[2], "student")
    assert {q["id"]: q["mine"] for q in other["questions"]} == {named["id"]: False, anon["id"]: False}

    # The identity is stored for class totals (FR-504, FR-713).
    async with AsyncSessionLocal() as db:
        row = await db.get(Question, anon["id"])
    assert row.student_id == c.student_ids[1]


async def test_question_validation(shino_class):
    c = shino_class
    s = c.student_user_ids[0]
    await ask(c, s, "   ", expect=422)
    await ask(c, s, "x" * 501, expect=422)
    await ask(c, s, "x" * 500)
    async with c.client(s, "student") as api:
        r = await api.post(qurl(c), json={"text": "hi", "anonymous": False, "student_id": 1})
    assert r.status_code == 422


async def test_access_matrix(shino_class):
    c = shino_class
    q = await ask(c, c.student_user_ids[0])
    # the lecturer reads and moderates but doesn't ask or upvote
    async with c.client(c.lecturer_user_id, "lecturer") as api:
        assert (await api.post(qurl(c), json={"text": "hi"})).status_code == 403
    assert (await upvote(c, c.lecturer_user_id, q["id"], "lecturer")).status_code == 403
    # outsiders: not enrolled student, lecturer of another class, no token
    for uid, role in [(c.outsider_user_id, "student"), (c.other_lecturer_user_id, "lecturer")]:
        async with c.client(uid, role) as api:
            assert (await api.get(qurl(c))).status_code == 403
            assert (await api.post(qurl(c), json={"text": "hi"})).status_code == 403
            assert (await api.post(qurl(c, q["id"], "upvote"))).status_code == 403
    assert (await moderate(c, q["id"], {"pinned": True}, uid=c.other_lecturer_user_id)).status_code == 403
    async with c.client(c.student_user_ids[1], "student") as api:
        assert (await api.patch(murl(c, q["id"]), json={"pinned": True})).status_code == 403
    async with c.client() as api:
        assert (await api.get(qurl(c))).status_code in (401, 403)   # no token (HTTPBearer)
    # unknown class session id: 403, can't be probed
    async with c.client(c.student_user_ids[0], "student") as api:
        assert (await api.get(f"/interaction/{c.session_id + 999}/questions")).status_code == 403


# ── upvotes and order ────────────────────────────────────────────────────────

async def test_upvote_once_and_not_own(shino_class):
    c = shino_class
    s1, s2, s3 = c.student_user_ids[:3]
    q = await ask(c, s1)
    r = await upvote(c, s2, q["id"])
    assert r.status_code == 200 and r.json()["upvotes"] == 1 and r.json()["upvoted_by_me"] is True
    r = await upvote(c, s2, q["id"])                      # a repeat changes nothing
    assert r.status_code == 200 and r.json()["upvotes"] == 1
    r = await upvote(c, s3, q["id"])
    assert r.json()["upvotes"] == 2
    assert (await upvote(c, s1, q["id"])).status_code == 409   # own question
    assert (await upvote(c, s2, q["id"] + 999)).status_code == 404

    seen = {x["id"]: x for x in (await listing(c, s1, "student"))["questions"]}
    assert seen[q["id"]]["upvotes"] == 2 and seen[q["id"]]["upvoted_by_me"] is False


async def test_question_from_another_class_session_is_404(shino_class):
    c = shino_class
    q = await ask(c, c.student_user_ids[0])
    # a second class session of the same class (M3 ends the first, starts another)
    await end_class(c.session_id)
    from app.models.class_ import ClassOccurrence
    from app.models.user import Lecturer
    from app.services import session_schedule
    async with AsyncSessionLocal() as db:
        occ = await db.get(ClassOccurrence, c.occurrence_id)
        lec = await db.get(Lecturer, c.lecturer_id)
        s2 = await session_schedule.start_now(db, occ, lec, session_schedule.clock(), duration_minutes=60)
        await db.commit()
        second = s2.id
    async with c.client(c.student_user_ids[1], "student") as api:
        assert (await api.post(f"/interaction/{second}/questions/{q['id']}/upvote")).status_code == 404
    async with c.client(c.lecturer_user_id, "lecturer") as api:
        r = await api.patch(f"/lecturer/interaction/{second}/questions/{q['id']}", json={"pinned": True})
        assert r.status_code == 404
        assert (await api.get(f"/interaction/{second}/questions")).json()["questions"] == []


async def test_listed_pinned_first_then_votes_then_time(shino_class, monkeypatch):
    c = shino_class
    s1, s2, s3, s4 = c.student_user_ids
    from datetime import datetime, timedelta
    t0 = datetime(2026, 11, 23, 9, 0)
    times = iter([t0 + timedelta(minutes=i) for i in range(10)])
    monkeypatch.setattr(sessions, "clock", lambda: next(times))
    a = await ask(c, s1, "A oldest")          # 0 votes
    b = await ask(c, s2, "B")                 # 2 votes
    d = await ask(c, s3, "D")                 # 1 vote
    e = await ask(c, s4, "E newest")          # 0 votes
    for uid in (s1, s3):
        assert (await upvote(c, uid, b["id"])).status_code == 200
    assert (await upvote(c, s1, d["id"])).status_code == 200

    order = [q["id"] for q in (await listing(c, s1, "student"))["questions"]]
    assert order == [b["id"], d["id"], a["id"], e["id"]]

    assert (await moderate(c, e["id"], {"pinned": True})).status_code == 200
    for uid, role in [(s2, "student"), (c.lecturer_user_id, "lecturer")]:
        order = [q["id"] for q in (await listing(c, uid, role))["questions"]]
        assert order == [e["id"], b["id"], d["id"], a["id"]]


# ── lecturer moderation ──────────────────────────────────────────────────────

async def test_lecturer_answers_pins_and_hides(shino_class):
    c = shino_class
    s1, s2 = c.student_user_ids[:2]
    q = await ask(c, s1, "Is this on the exam?")

    r = await moderate(c, q["id"], {"answered": True, "pinned": True})
    assert r.status_code == 200, r.text
    assert r.json()["answered"] is True and r.json()["answered_at"] and r.json()["pinned"] is True
    student_view = (await listing(c, s2, "student"))["questions"][0]
    assert student_view["answered"] is True and student_view["pinned"] is True

    r = await moderate(c, q["id"], {"answered": False, "pinned": False})
    assert r.json()["answered"] is False and r.json()["answered_at"] is None and r.json()["pinned"] is False

    r = await moderate(c, q["id"], {"hidden": True})
    assert r.json()["hidden"] is True
    assert (await listing(c, s2, "student"))["questions"] == []      # students never get it
    assert (await listing(c, s1, "student"))["questions"] == []      # nor the asker
    lec = (await listing(c, c.lecturer_user_id, "lecturer"))["questions"]
    assert [x["hidden"] for x in lec] == [True]                     # the lecturer can still unhide
    assert (await upvote(c, s2, q["id"])).status_code == 404

    await moderate(c, q["id"], {"hidden": True})                   # no change, no second audit
    r = await moderate(c, q["id"], {"hidden": False})
    assert r.json()["hidden"] is False
    assert len((await listing(c, s2, "student"))["questions"]) == 1

    assert (await moderate(c, q["id"] + 999, {"pinned": True})).status_code == 404
    assert (await moderate(c, q["id"], {"deleted": True})).status_code == 422

    async with AsyncSessionLocal() as db:
        logs = (await db.scalars(select(AuditLog).where(AuditLog.target_type == "m5_question",
                                                        AuditLog.target_id == str(q["id"]))
                                 .order_by(AuditLog.id))).all()
    assert [(x.action, x.actor_id, json.loads(x.old_val), json.loads(x.new_val)) for x in logs] == [
        ("INTERACTION_QUESTION_HIDDEN", c.lecturer_user_id, {"hidden": False}, {"hidden": True}),
        ("INTERACTION_QUESTION_UNHIDDEN", c.lecturer_user_id, {"hidden": True}, {"hidden": False}),
    ]


# ── closed interaction ───────────────────────────────────────────────────────

async def test_writes_rejected_once_closed_but_list_still_works(shino_class):
    c = shino_class
    s1, s2 = c.student_user_ids[:2]
    q = await ask(c, s1)

    async with c.client(c.lecturer_user_id, "lecturer") as api:      # lecturer closes early
        assert (await api.post(f"/lecturer/interaction/{c.session_id}/close")).status_code == 200
    await ask(c, s1, "late?", expect=409)
    assert (await upvote(c, s2, q["id"])).status_code == 409
    assert (await moderate(c, q["id"], {"answered": True})).status_code == 409

    async with c.client(c.lecturer_user_id, "lecturer") as api:      # reopen, then the class ends
        assert (await api.post(f"/lecturer/interaction/{c.session_id}/open")).status_code == 200
    assert (await upvote(c, s2, q["id"])).status_code == 200
    await end_class(c.session_id)
    await ask(c, s1, "after class?", expect=409)
    assert (await upvote(c, c.student_user_ids[2], q["id"])).status_code == 409
    assert (await moderate(c, q["id"], {"hidden": True})).status_code == 409

    body = await listing(c, s1, "student")
    assert body["status"] == "closed" and [x["upvotes"] for x in body["questions"]] == [1]


# ── anonymity on every response shape ────────────────────────────────────────

async def test_anonymous_identity_in_no_response_or_audit(shino_class):
    c = shino_class
    asker, s2 = c.student_user_ids[:2]
    who = await identity(asker)
    seen: list[tuple[str, object]] = []

    async with c.client(asker, "student") as api:
        r = await api.post(qurl(c), json={"text": "Anonymous worry", "anonymous": True})
        assert r.status_code == 201
        seen.append(("ask response (to the asker)", r.json()))
        qid = r.json()["id"]
        seen.append(("asker's own list", (await api.get(qurl(c))).json()))
        seen.append(("own upvote refusal", (await api.post(qurl(c, qid, "upvote"))).json()))

    async with c.client(s2, "student") as api:
        seen.append(("upvote response", (await api.post(qurl(c, qid, "upvote"))).json()))
        seen.append(("classmate list", (await api.get(qurl(c))).json()))

    for body in ({"answered": True}, {"pinned": True}, {"hidden": True}, {"hidden": False}):
        r = await moderate(c, qid, body)
        assert r.status_code == 200
        seen.append((f"moderate {body}", r.json()))
    seen.append(("lecturer list", await listing(c, c.lecturer_user_id, "lecturer")))
    async with c.client(c.lecturer_user_id, "lecturer") as api:
        seen.append(("join", (await api.get(f"/interaction/{c.session_id}")).json()))

    for where, payload in seen:
        assert_no_identity(payload, who, where)
    # `mine` is true only in the asker's own responses
    lecturer_and_classmate = [p for w, p in seen if not w.startswith(("ask response", "asker's", "own"))]
    for p in lecturer_and_classmate:
        for q in (p.get("questions") or [p]) if isinstance(p, dict) else []:
            assert q.get("mine", False) is False

    async with AsyncSessionLocal() as db:
        logs = (await db.scalars(select(AuditLog).where(AuditLog.target_type == "m5_question"))).all()
    assert len(logs) == 2
    for log in logs:
        values = {"old": json.loads(log.old_val), "new": json.loads(log.new_val)}
        assert_no_identity(values, who, f"audit {log.action}")
        assert log.actor_id == c.lecturer_user_id and str(who["student_id"]) not in (log.old_val + log.new_val)
