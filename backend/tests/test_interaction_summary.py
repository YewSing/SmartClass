"""S36: after class — session summary, CSV export, a student's own questions (FR-518–FR-520).

The class is run through the real endpoints (S31–S33) and ended through M3's own service. The
summary must show what happened without any student identity for anonymous questions, quick
answers, reactions or confusion; the CSV must keep anonymous questions anonymous and escape
formula-like cells; students list only their own questions with the answered status.
"""
import csv
import io
import json
from datetime import datetime, timedelta

import pytest

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.models.class_ import ClassOccurrence
from app.models.user import Lecturer
from app.services import session_schedule, session_service
from app.services.interaction import sessions, summary
from tests.test_interaction_questions import assert_no_identity, identity

pytestmark = pytest.mark.db

T0 = datetime(2026, 11, 23, 9, 0)


def iurl(c, *rest, sid=None) -> str:
    return "/".join([f"/interaction/{sid or c.session_id}", *map(str, rest)])


def lurl(c, *rest, sid=None) -> str:
    return "/".join([f"/lecturer/interaction/{sid or c.session_id}", *map(str, rest)])


async def call(c, uid, role, method, url, expect=None, **kw):
    async with c.client(uid, role) as api:
        r = await getattr(api, method)(url, **kw)
    if expect is not None:
        assert r.status_code == expect, r.text
    return r


async def end_class(session_id: int) -> None:
    async with AsyncSessionLocal() as db:
        await session_service.close_session(session_id, db)
        await db.commit()


async def second_session(c) -> int:
    async with AsyncSessionLocal() as db:
        occ = await db.get(ClassOccurrence, c.occurrence_id)
        lec = await db.get(Lecturer, c.lecturer_id)
        s = await session_schedule.start_now(db, occ, lec, session_schedule.clock(), duration_minutes=60)
        await db.commit()
        return s.id


@pytest.fixture
def clock(monkeypatch):
    """A clock that moves on by one minute per call (orderable times, no cooldown hits)."""
    state = {"t": T0}

    def tick():
        state["t"] += timedelta(minutes=1)
        return state["t"]

    monkeypatch.setattr(sessions, "clock", tick)
    monkeypatch.setattr(settings, "INTERACTION_CONFUSION_COOLDOWN_SECONDS", 0)
    monkeypatch.setattr(settings, "INTERACTION_REACTION_COOLDOWN_SECONDS", 0)
    return state


async def run_class(c) -> dict:
    """Questions (named, anonymous, answered, hidden), a poll that ran plus a draft, a quick
    question with answers, reactions and confusion presses."""
    s1, s2, s3, s4 = c.student_user_ids
    L = c.lecturer_user_id
    named = (await call(c, s1, "student", "post", iurl(c, "questions"),
                        json={"text": "=HYPERLINK(\"http://x\")", "anonymous": False}, expect=201)).json()
    anon = (await call(c, s2, "student", "post", iurl(c, "questions"),
                       json={"text": "Can you repeat slide 4?", "anonymous": True}, expect=201)).json()
    hidden = (await call(c, s3, "student", "post", iurl(c, "questions"),
                         json={"text": "off-topic", "anonymous": False}, expect=201)).json()
    await call(c, s3, "student", "post", iurl(c, "questions", anon["id"], "upvote"), expect=200)
    await call(c, s4, "student", "post", iurl(c, "questions", anon["id"], "upvote"), expect=200)
    await call(c, L, "lecturer", "patch", lurl(c, "questions", anon["id"]), json={"answered": True}, expect=200)
    await call(c, L, "lecturer", "patch", lurl(c, "questions", hidden["id"]), json={"hidden": True}, expect=200)

    poll = (await call(c, L, "lecturer", "post", lurl(c, "polls"),
                       json={"question": "Best sort?", "options": ["+quick", "merge"]}, expect=201)).json()
    draft = (await call(c, L, "lecturer", "post", lurl(c, "polls"),
                        json={"question": "Never started", "options": ["a", "b"]}, expect=201)).json()
    await call(c, L, "lecturer", "post", lurl(c, "polls", poll["id"], "start"), expect=200)
    opt_quick, opt_merge = [o["id"] for o in poll["options"]]
    for uid, oid in [(s1, opt_quick), (s2, opt_merge), (s3, opt_merge)]:
        await call(c, uid, "student", "post", iurl(c, "polls", poll["id"], "vote"),
                   json={"option_ids": [oid]}, expect=200)
    await call(c, L, "lecturer", "post", lurl(c, "polls", poll["id"], "close"), expect=200)

    qq = (await call(c, L, "lecturer", "post", lurl(c, "quick-questions"),
                     json={"prompt": "One word for recursion?"}, expect=201)).json()
    await call(c, s1, "student", "post", iurl(c, "quick-questions", qq["id"], "answer"),
               json={"text": "@self"}, expect=200)
    await call(c, s2, "student", "post", iurl(c, "quick-questions", qq["id"], "answer"),
               json={"text": "loops"}, expect=200)

    for uid, kind in [(s1, "thumbs_up"), (s2, "thumbs_up"), (s3, "too_fast")]:
        await call(c, uid, "student", "post", iurl(c, "reactions"), json={"kind": kind}, expect=201)
    for uid, topic in [(s1, "recursion"), (s2, "recursion"), (s4, None)]:
        await call(c, uid, "student", "post", iurl(c, "confusion"), json={"topic": topic}, expect=201)
    return {"named": named, "anon": anon, "hidden": hidden, "poll": poll, "draft": draft, "qq": qq}


# ── summary (FR-518) ─────────────────────────────────────────────────────────

async def test_summary_after_class(shino_class, clock):
    c = shino_class
    made = await run_class(c)
    await end_class(c.session_id)

    s = (await call(c, c.lecturer_user_id, "lecturer", "get", lurl(c, "summary"), expect=200)).json()
    assert s["attendance_session_id"] == c.session_id and s["course_code"] == "SH101"
    assert s["status"] == "closed" and s["class_status"] == "closed" and s["class_date"]
    assert s["question_counts"] == {"asked": 3, "answered": 1, "anonymous": 1, "hidden": 1, "upvotes": 2}
    by_id = {q["id"]: q for q in s["questions"]}
    assert by_id[made["anon"]["id"]]["author_name"] is None and by_id[made["anon"]["id"]]["answered"] is True
    assert by_id[made["named"]["id"]]["author_name"] == "Shino Student 1"
    assert by_id[made["hidden"]["id"]]["hidden"] is True

    assert [p["id"] for p in s["polls"]] == [made["poll"]["id"]]          # the draft never ran
    poll = s["polls"][0]
    assert poll["status"] == "closed" and poll["total_voters"] == 3
    assert [o["votes"] for o in poll["options"]] == [1, 2]

    [qq] = s["quick_questions"]
    assert qq["answer_count"] == 2 and sorted(a["text"] for a in qq["answers"]) == ["@self", "loops"]
    assert s["reactions"] == {"thumbs_up": 2, "clear": 0, "too_fast": 1, "too_slow": 0}
    assert s["reactions_total"] == 3
    conf = s["confusion"]
    assert conf["total"] == 3 and sum(b["count"] for b in conf["timeline"]) == 3
    assert conf["topics"] == [{"topic": "recursion", "count": 2}]

    # no student identity for anonymous questions, quick answers, reactions or confusion
    for uid in (c.student_user_ids[1], c.student_user_ids[3]):   # s1, s3 asked named questions
        assert_no_identity(s, await identity(uid), "summary")
    raw = json.dumps(s)
    assert "student_id" not in raw and "user_id" not in raw


async def test_summary_while_class_runs_and_empty(shino_class, clock):
    c = shino_class
    s = (await call(c, c.lecturer_user_id, "lecturer", "get", lurl(c, "summary"), expect=200)).json()
    assert s["status"] == "open" and s["question_counts"]["asked"] == 0
    assert s["questions"] == s["polls"] == s["quick_questions"] == []
    assert s["reactions_total"] == 0 and s["confusion"]["timeline"] == []
    await call(c, c.student_user_ids[0], "student", "post", iurl(c, "questions"),
               json={"text": "live?"}, expect=201)
    s = (await call(c, c.lecturer_user_id, "lecturer", "get", lurl(c, "summary"), expect=200)).json()
    assert s["question_counts"]["asked"] == 1


async def test_summary_access(shino_class):
    c = shino_class
    for path in ("summary", "summary.csv"):
        await call(c, c.student_user_ids[0], "student", "get", lurl(c, path), expect=403)
        await call(c, c.outsider_user_id, "student", "get", lurl(c, path), expect=403)
        await call(c, c.other_lecturer_user_id, "lecturer", "get", lurl(c, path), expect=403)
        await call(c, c.lecturer_user_id, "lecturer", "get", lurl(c, path, sid=c.session_id + 999), expect=403)
        async with c.client() as api:
            assert (await api.get(lurl(c, path))).status_code in (401, 403)


async def test_summary_is_per_class_session(shino_class, clock):
    c = shino_class
    await run_class(c)
    await end_class(c.session_id)
    second = await second_session(c)
    s = (await call(c, c.lecturer_user_id, "lecturer", "get", lurl(c, "summary", sid=second), expect=200)).json()
    assert s["question_counts"]["asked"] == 0 and s["polls"] == [] and s["reactions_total"] == 0


# ── CSV (FR-519) ─────────────────────────────────────────────────────────────

def parse(text: str) -> list[list[str]]:
    return list(csv.reader(io.StringIO(text)))


async def test_csv_export(shino_class, clock):
    c = shino_class
    await run_class(c)
    await end_class(c.session_id)
    r = await call(c, c.lecturer_user_id, "lecturer", "get", lurl(c, "summary.csv"), expect=200)
    assert r.headers["content-type"].startswith("text/csv")
    disp = r.headers["content-disposition"]
    assert disp.startswith("attachment;") and "interaction_SH101_" in disp and disp.endswith('.csv"')

    rows = parse(r.text)
    assert rows[0] == summary.CSV_HEADER
    sections = {}
    for row in rows[1:]:
        sections.setdefault(row[0], []).append(row)
    assert {k: len(v) for k, v in sections.items() if k in ("Question", "Poll", "Poll option",
                                                             "Quick question", "Quick answer", "Reaction",
                                                             "Confusion topic")} == {
        "Question": 3, "Poll": 1, "Poll option": 2, "Quick question": 1, "Quick answer": 2,
        "Reaction": 4, "Confusion topic": 1}
    assert sections["Questions asked"][0][5] == "3" and sections["Questions answered"][0][5] == "1"
    assert sections["Anonymous questions"][0][5] == "1"

    questions = {row[2]: row for row in sections["Question"]}
    anon = questions["Can you repeat slide 4?"]
    assert anon[3] == "Anonymous" and anon[4] == "answered" and anon[5] == "2"
    assert questions["off-topic"][4] == "unanswered, hidden"
    assert "Never started" not in r.text                                   # drafts aren't exported

    # anonymous asker, quick answerers, reacting and confused students: no identity anywhere
    asker = await identity(c.student_user_ids[1])
    for key in ("name", "email", "matric"):
        assert asker[key] not in r.text
    assert all(row[3] == "" for row in sections["Quick answer"] + sections["Reaction"] + sections["Confusion"])

    # formula-like cells are escaped (= + - @), safe ones are left alone
    assert "'=HYPERLINK(\"http://x\")" in questions
    assert [o[2] for o in sections["Poll option"]] == ["'+quick", "merge"]
    assert sorted(a[2] for a in sections["Quick answer"]) == ["'@self", "loops"]
    for row in rows[1:]:
        for cell in row:
            assert not cell.startswith(("=", "+", "-", "@")), row


def test_safe_cell():
    for raw in ("=1+1", "+1", "-1", "@SUM(A1)", "\tx", "\rx"):
        assert summary.safe_cell(raw) == "'" + raw
    for raw in ("plain", "1-2", "", "'quoted", " =x"):
        assert summary.safe_cell(raw) == raw
    assert summary.safe_cell(-3) == -3 and summary.safe_cell(None) is None


async def test_csv_keeps_anonymous_question_text_but_not_author(shino_class, clock):
    c = shino_class
    who = await identity(c.student_user_ids[0])
    await call(c, c.student_user_ids[0], "student", "post", iurl(c, "questions"),
               json={"text": "Only anonymous", "anonymous": True}, expect=201)
    r = await call(c, c.lecturer_user_id, "lecturer", "get", lurl(c, "summary.csv"), expect=200)
    [row] = [x for x in parse(r.text) if x[0] == "Question"]
    assert row[2] == "Only anonymous" and row[3] == "Anonymous"
    for key in ("name", "email", "matric"):
        assert who[key] not in r.text


# ── a student's own questions (FR-520) ───────────────────────────────────────

async def test_student_lists_own_past_questions(shino_class, clock):
    c = shino_class
    s1, s2 = c.student_user_ids[:2]
    first = (await call(c, s1, "student", "post", iurl(c, "questions"),
                        json={"text": "First class q", "anonymous": False}, expect=201)).json()
    anon = (await call(c, s1, "student", "post", iurl(c, "questions"),
                       json={"text": "My anonymous q", "anonymous": True}, expect=201)).json()
    hid = (await call(c, s1, "student", "post", iurl(c, "questions"),
                      json={"text": "Hidden one", "anonymous": False}, expect=201)).json()
    await call(c, s2, "student", "post", iurl(c, "questions"), json={"text": "Not mine"}, expect=201)
    await call(c, s2, "student", "post", iurl(c, "questions", first["id"], "upvote"), expect=200)
    await call(c, c.lecturer_user_id, "lecturer", "patch", lurl(c, "questions", first["id"]),
               json={"answered": True}, expect=200)
    await call(c, c.lecturer_user_id, "lecturer", "patch", lurl(c, "questions", hid["id"]),
               json={"hidden": True}, expect=200)
    await end_class(c.session_id)
    second = await second_session(c)
    later = (await call(c, s1, "student", "post", iurl(c, "questions", sid=second),
                        json={"text": "Second class q"}, expect=201)).json()

    body = (await call(c, s1, "student", "get", "/student/me/questions", expect=200)).json()
    assert [q["id"] for q in body["questions"]] == [later["id"], anon["id"], first["id"]]
    assert body["next_before"] is None
    by_id = {q["id"]: q for q in body["questions"]}
    f = by_id[first["id"]]
    assert f["answered"] is True and f["answered_at"] and f["upvotes"] == 1
    assert f["attendance_session_id"] == c.session_id and f["course_code"] == "SH101"
    assert f["occurrence_id"] == c.occurrence_id and f["class_date"]
    assert by_id[anon["id"]]["anonymous"] is True and by_id[anon["id"]]["answered"] is False
    assert by_id[later["id"]]["attendance_session_id"] == second
    assert all("author_name" not in q and "student_id" not in q for q in body["questions"])

    one = (await call(c, s1, "student", "get", "/student/me/questions",
                      params={"attendance_session_id": second}, expect=200)).json()
    assert [q["id"] for q in one["questions"]] == [later["id"]]

    other = (await call(c, s2, "student", "get", "/student/me/questions", expect=200)).json()
    assert [q["text"] for q in other["questions"]] == ["Not mine"]
    none = (await call(c, c.outsider_user_id, "student", "get", "/student/me/questions", expect=200)).json()
    assert none == {"questions": [], "next_before": None}


async def test_my_questions_pagination_and_access(shino_class, clock):
    c = shino_class
    s1 = c.student_user_ids[0]
    ids = [(await call(c, s1, "student", "post", iurl(c, "questions"), json={"text": f"q{i}"},
                       expect=201)).json()["id"] for i in range(5)]
    page1 = (await call(c, s1, "student", "get", "/student/me/questions", params={"limit": 2}, expect=200)).json()
    assert [q["id"] for q in page1["questions"]] == ids[:-3:-1] and page1["next_before"] == ids[3]
    page2 = (await call(c, s1, "student", "get", "/student/me/questions",
                        params={"limit": 2, "before": page1["next_before"]}, expect=200)).json()
    assert [q["id"] for q in page2["questions"]] == [ids[2], ids[1]]
    page3 = (await call(c, s1, "student", "get", "/student/me/questions",
                        params={"limit": 2, "before": page2["next_before"]}, expect=200)).json()
    assert [q["id"] for q in page3["questions"]] == [ids[0]] and page3["next_before"] is None

    await call(c, s1, "student", "get", "/student/me/questions", params={"limit": 0}, expect=422)
    await call(c, s1, "student", "get", "/student/me/questions", params={"limit": 201}, expect=422)
    await call(c, c.lecturer_user_id, "lecturer", "get", "/student/me/questions", expect=403)
    async with c.client() as api:
        assert (await api.get("/student/me/questions")).status_code in (401, 403)
