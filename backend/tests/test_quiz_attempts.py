"""S44: graded attempts and the server's timers (FR-607, FR-608, NFR-41, NFR-47, NFR-54)."""
import asyncio
import json
import random
from datetime import datetime, timedelta

import pytest
from sqlalchemy import select

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.models.class_ import Enrollment
from app.models.quiz import Quiz, QuizAnswer, QuizAttempt
from app.schemas.quiz import AttemptOptionOut, AttemptOut, AttemptQuestionOut
from app.services import quiz_attempts, quiz_publish, quiz_timer
from tests.test_quiz_crud import URL, call, count, create, game, graded, insert, question_row, set_status
from tests.test_quiz_publish import HOUR, MINE, NOW, act, cards, clock, published_by_other  # noqa: F401 (clock: fixture)

pytestmark = pytest.mark.db

SEC = timedelta(seconds=1)
MINUTE = timedelta(minutes=1)
SECRETS = ("secret", "topicword", "filename", "sha-answer")


@pytest.fixture(autouse=True)
def _fixed_time(clock):     # noqa: F811
    """Every test runs on the fake clock."""


async def quiz_with(c, mcq=3, short=0, **over) -> dict:
    """A published quiz whose questions carry things a student must not get."""
    quiz = await create(c, graded(c, **{"timer_mode": "quiz", "timer_seconds": 600, **over}))
    hidden = {"approved": True, "topic": "Topicword", "explanation": "Secret explanation",
              "origin": "from_material", "source_file": "filename.pdf", "source_type": "slide", "source_page": 3}
    rows = [question_row(quiz["id"], i, text=f"Question {i}?", options=["W", "X", "Y", "Z"], answer=2, **hidden)
            for i in range(mcq)]
    rows += [question_row(quiz["id"], mcq + i, type="short", text=f"Why {i}?", options=None, answer=None,
                          suggested_answer="SHA-answer", **hidden) for i in range(short)]
    await insert(*rows)
    return await act(c, quiz["id"], "publish")


async def student(c, method, quiz_id, path="", expect=200, i=0, **kw):
    kw = {"uid": c.student_user_ids[i], "role": "student", **kw}
    return await call(c, method, f"{MINE}/{quiz_id}/attempt{path}", expect, **kw)


async def start(c, quiz_id, expect=201, **kw):
    return await student(c, "POST", quiz_id, expect=expect, **kw)


async def read(c, quiz_id, expect=200, **kw):
    return await student(c, "GET", quiz_id, expect=expect, **kw)


async def save(c, quiz_id, question_id, body, expect=200, **kw):
    return await student(c, "PUT", quiz_id, f"/answers/{question_id}", expect, json=body, **kw)


async def choose(c, quiz_id, question_id, option, expect=200, **kw):
    return await save(c, quiz_id, question_id, {"option_index": option}, expect, **kw)


async def next_(c, quiz_id, question_id, expect=200, **kw):
    return await student(c, "POST", quiz_id, "/next", expect, json={"question_id": question_id}, **kw)


async def submit(c, quiz_id, expect=200, **kw):
    return await student(c, "POST", quiz_id, "/submit", expect, **kw)


def ids(attempt) -> list[int]:
    return [q["id"] for q in attempt["questions"]]


async def quiz_ids(quiz_id) -> list[int]:
    async with AsyncSessionLocal() as db:
        return [q.id for q in await quiz_publish.published_questions(db, quiz_id)]


async def row(quiz_id, student_id) -> QuizAttempt:
    async with AsyncSessionLocal() as db:
        return (await db.execute(select(QuizAttempt).where(
            QuizAttempt.quiz_id == quiz_id, QuizAttempt.student_id == student_id))).scalar_one()


async def answers() -> list[QuizAnswer]:
    async with AsyncSessionLocal() as db:
        return list((await db.execute(select(QuizAnswer).order_by(QuizAnswer.id))).scalars())


# ── start and resume ─────────────────────────────────────────────────────────

async def test_start_gives_the_questions_and_the_deadline(shino_class, clock):     # noqa: F811
    c = shino_class
    quiz = await quiz_with(c, mcq=1, short=1)
    out = await start(c, quiz["id"])
    first, second = await quiz_ids(quiz["id"])
    assert out == {
        "quiz_id": quiz["id"], "title": "Week 5", "course_code": "SH101", "timer_mode": "quiz",
        "timer_seconds": 600, "status": "in_progress", "started_at": NOW.isoformat(),
        "ends_at": (NOW + 10 * MINUTE).isoformat(), "submitted_at": None, "auto_submitted": False,
        "server_time": NOW.isoformat(), "remaining_seconds": 600.0, "current_number": None,
        "question_ends_at": None, "question_remaining_seconds": None, "question_count": 2, "answered_count": 0,
        "questions": [
            {"id": first, "number": 1, "type": "mcq", "text": "Question 0?", "option_index": None,
             "options": [{"index": 0, "text": "W"}, {"index": 1, "text": "X"}, {"index": 2, "text": "Y"},
                         {"index": 3, "text": "Z"}], "answer_text": None, "answered_at": None},
            {"id": second, "number": 2, "type": "short", "text": "Why 0?", "options": None, "option_index": None,
             "answer_text": None, "answered_at": None}]}


async def test_resuming_keeps_the_answers_and_never_extends_the_time(shino_class, clock):     # noqa: F811
    c = shino_class
    quiz = await quiz_with(c)
    first = await start(c, quiz["id"])
    await choose(c, quiz["id"], ids(first)[0], 1)
    for minutes in (3, 9):
        clock.now = NOW + minutes * MINUTE
        for got in (await start(c, quiz["id"], expect=200), await read(c, quiz["id"])):
            assert (got["started_at"], got["ends_at"]) == (first["started_at"], first["ends_at"])
            assert got["remaining_seconds"] == (10 - minutes) * 60
            assert got["questions"][0]["option_index"] == 1 and got["answered_count"] == 1
    assert await count(QuizAttempt) == 1


async def test_one_attempt_only(shino_class, clock):     # noqa: F811
    c = shino_class
    quiz = await quiz_with(c)
    await start(c, quiz["id"])
    await submit(c, quiz["id"])
    assert "already submitted" in (await start(c, quiz["id"], expect=409))["detail"]
    clock.now += 30 * 24 * HOUR
    await start(c, quiz["id"], expect=409)
    assert await count(QuizAttempt) == 1
    # another student has their own
    assert (await start(c, quiz["id"], i=1))["status"] == "in_progress"


async def test_starting_twice_at_once_makes_one_attempt(shino_class):
    c = shino_class
    quiz = await quiz_with(c, mcq=6, shuffle=True)

    async def one():
        async with c.client(c.student_user_ids[0], "student") as api:
            return await api.post(f"{MINE}/{quiz['id']}/attempt")

    got = await asyncio.gather(*(one() for _ in range(4)))
    assert sorted(r.status_code for r in got) == [200, 200, 200, 201]
    assert len({json.dumps(r.json()["questions"]) for r in got}) == 1 and await count(QuizAttempt) == 1


async def test_only_approved_questions_are_asked(shino_class):
    c = shino_class
    quiz = await create(c)
    await insert(question_row(quiz["id"], 0, approved=True), question_row(quiz["id"], 1, text="Not ready"))
    await act(c, quiz["id"], "publish")
    assert [q["text"] for q in (await start(c, quiz["id"]))["questions"]] == ["2+2?"]


async def test_only_an_open_quiz_can_be_started(shino_class, clock):     # noqa: F811
    c = shino_class
    quiz = await quiz_with(c, opens_at=(NOW + HOUR).isoformat(), closes_at=(NOW + 2 * HOUR).isoformat())
    by_hand = await quiz_with(c)
    await act(c, by_hand["id"], "close")
    assert "closed" in (await start(c, by_hand["id"], expect=409))["detail"]
    assert "isn't open yet" in (await start(c, quiz["id"], expect=409))["detail"]
    clock.now = NOW + 2 * HOUR
    assert "closed" in (await start(c, quiz["id"], expect=409))["detail"]
    assert await count(QuizAttempt) == 0
    clock.now = NOW + HOUR
    await start(c, quiz["id"])


async def test_a_game_is_not_taken_this_way(shino_class):
    c = shino_class
    quiz = await create(c, game(c))
    [question] = await insert(question_row(quiz["id"], approved=True))
    await act(c, quiz["id"], "publish")
    await start(c, quiz["id"], expect=409)
    await read(c, quiz["id"], expect=409)
    await choose(c, quiz["id"], question, 0, expect=409)
    await next_(c, quiz["id"], question, expect=409)
    await submit(c, quiz["id"], expect=409)
    assert await count(QuizAttempt) == 0


async def test_nothing_works_before_the_start(shino_class):
    c = shino_class
    quiz = await quiz_with(c)
    question = (await quiz_ids(quiz["id"]))[0]
    await read(c, quiz["id"], expect=404)
    await choose(c, quiz["id"], question, 0, expect=404)
    await next_(c, quiz["id"], question, expect=404)
    await submit(c, quiz["id"], expect=404)


# ── access (NFR-04) ──────────────────────────────────────────────────────────

async def test_access(shino_class, users):
    c = shino_class
    quiz, draft = await quiz_with(c), await create(c)
    other = await published_by_other(c)
    question = (await quiz_ids(quiz["id"]))[0]
    await start(c, quiz["id"])

    async def refused(quiz_id, expect=403, **who):
        await start(c, quiz_id, expect=expect, **who)
        await read(c, quiz_id, expect=expect, **who)
        await choose(c, quiz_id, question, 0, expect=expect, **who)
        await next_(c, quiz_id, question, expect=expect, **who)
        await submit(c, quiz_id, expect=expect, **who)

    for uid, role in [(c.outsider_user_id, "student"), (c.lecturer_user_id, "lecturer"),
                      (c.other_lecturer_user_id, "lecturer"), (users["admin"].id, "admin")]:
        await refused(quiz["id"], uid=uid, role=role)
    for quiz_id in (draft["id"], other["id"], 99999):
        await refused(quiz_id)
    async with c.client() as api:
        assert (await api.post(f"{MINE}/{quiz['id']}/attempt")).status_code in (401, 403)
    assert await count(QuizAttempt) == 1 and await answers() == []


async def test_a_student_only_reaches_their_own_attempt(shino_class):
    c = shino_class
    quiz = await quiz_with(c)
    question = ids(await start(c, quiz["id"]))[0]
    await start(c, quiz["id"], i=1)
    await choose(c, quiz["id"], question, 1)
    await choose(c, quiz["id"], question, 3, i=1)
    await submit(c, quiz["id"], i=1)
    mine = await read(c, quiz["id"])
    assert mine["status"] == "in_progress" and mine["questions"][0]["option_index"] == 1


async def test_leaving_the_course_ends_access(shino_class):
    c = shino_class
    quiz = await quiz_with(c)
    question = ids(await start(c, quiz["id"]))[0]
    async with AsyncSessionLocal() as db:
        await db.delete(await db.scalar(select(Enrollment).where(Enrollment.student_id == c.student_ids[0])))
        await db.commit()
    await read(c, quiz["id"], expect=403)
    await choose(c, quiz["id"], question, 0, expect=403)


# ── nothing hidden reaches a student (NFR-41) ────────────────────────────────

@pytest.mark.parametrize("mode", ["quiz", "question"])
async def test_no_response_carries_answers_or_sources(shino_class, clock, mode):     # noqa: F811
    c = shino_class
    quiz = await quiz_with(c, mcq=2, short=1, timer_mode=mode, timer_seconds=60, shuffle=True)
    seen = [await start(c, quiz["id"]), await start(c, quiz["id"], expect=200), await read(c, quiz["id"])]
    shown = seen[0]["questions"][0]
    seen.append(await save(c, quiz["id"], shown["id"],
                           {"option_index": 0} if shown["type"] == "mcq" else {"text": "Because"}))
    if mode == "question":
        seen.append(await next_(c, quiz["id"], shown["id"]))
    seen += [await submit(c, quiz["id"]), await read(c, quiz["id"]), await start(c, quiz["id"], expect=409)]
    await act(c, quiz["id"], "close")
    seen.append(await read(c, quiz["id"]))
    for out in seen:
        assert not any(s in json.dumps(out).lower() for s in SECRETS), out
    assert seen[-1]["questions"] == []


def test_the_student_schemas_have_no_hidden_fields():
    assert set(AttemptQuestionOut.model_fields) == {"id", "number", "type", "text", "options", "option_index",
                                                    "answer_text", "answered_at"}
    assert set(AttemptOptionOut.model_fields) == {"index", "text"}
    assert not {"score", "correct", "marks"} & set(AttemptOut.model_fields)


# ── autosave ─────────────────────────────────────────────────────────────────

async def test_answers_are_saved_changed_and_cleared(shino_class, clock):     # noqa: F811
    c = shino_class
    quiz = await quiz_with(c, mcq=1, short=1)
    a, b = ids(await start(c, quiz["id"]))
    out = await choose(c, quiz["id"], a, 2)
    assert (out["questions"][0]["option_index"], out["answered_count"]) == (2, 1)
    clock.now += MINUTE
    out = await save(c, quiz["id"], b, {"text": "  Because it is  "})
    assert (out["questions"][1]["answer_text"], out["answered_count"]) == ("Because it is", 2)
    out = await choose(c, quiz["id"], a, 0)
    assert out["questions"][0]["option_index"] == 0
    assert await read(c, quiz["id"]) == out
    saved = {x.question_id: x for x in await answers()}
    assert (saved[a].option_index, saved[a].text, saved[a].answered_at) == (0, None, NOW + MINUTE)
    assert (saved[b].option_index, saved[b].text, saved[b].correct, saved[b].score) == (None, "Because it is",
                                                                                       None, None)
    for question, body in [(a, {"option_index": None}), (b, {"text": "   "})]:
        out = await save(c, quiz["id"], question, body)
    assert out["answered_count"] == 0 and await answers() == []
    assert (await save(c, quiz["id"], a, {}))["answered_count"] == 0      # nothing to clear


async def test_saving_the_same_answer_again_changes_nothing(shino_class, clock):     # noqa: F811
    c = shino_class
    quiz = await quiz_with(c)
    question = ids(await start(c, quiz["id"]))[0]
    await choose(c, quiz["id"], question, 2)
    clock.now += MINUTE
    out = await choose(c, quiz["id"], question, 2)
    assert out["questions"][0]["answered_at"] == NOW.isoformat() and len(await answers()) == 1


@pytest.mark.parametrize(("kind", "body"), [
    ("mcq", {"option_index": 4}), ("mcq", {"option_index": -1}), ("mcq", {"option_index": "1"}),
    ("mcq", {"option_index": True}), ("mcq", {"text": "X"}), ("mcq", {"option_index": 1, "text": "X"}),
    ("short", {"option_index": 0}), ("short", {"text": "x" * 2001}), ("short", {"text": "a\x00b"}),
    ("short", {"text": 5}), ("mcq", {"option_index": 1, "score": 1}),
])
async def test_answers_are_validated(shino_class, kind, body):
    c = shino_class
    quiz = await quiz_with(c, mcq=1, short=1)
    a, b = ids(await start(c, quiz["id"]))
    await save(c, quiz["id"], a if kind == "mcq" else b, body, expect=422)
    assert await answers() == []


async def test_a_question_of_another_quiz_is_404(shino_class):
    c = shino_class
    quiz, other = await quiz_with(c), await quiz_with(c)
    await start(c, quiz["id"])
    await choose(c, quiz["id"], (await quiz_ids(other["id"]))[0], 0, expect=404)
    # nor one of this quiz that wasn't published
    [hidden] = await insert(question_row(quiz["id"], 9))
    await choose(c, quiz["id"], hidden, 0, expect=404)
    assert await answers() == []


async def test_saving_two_answers_at_once(shino_class):
    c = shino_class
    quiz = await quiz_with(c)
    question = ids(await start(c, quiz["id"]))[0]

    async def one(option):
        async with c.client(c.student_user_ids[0], "student") as api:
            r = await api.put(f"{MINE}/{quiz['id']}/attempt/answers/{question}", json={"option_index": option})
            return r.status_code

    assert await asyncio.gather(*(one(i) for i in range(4))) == [200] * 4
    assert len(await answers()) == 1


# ── submitting ───────────────────────────────────────────────────────────────

async def test_submit_ends_the_attempt(shino_class, clock):     # noqa: F811
    c = shino_class
    quiz = await quiz_with(c)
    question = ids(await start(c, quiz["id"]))[0]
    await choose(c, quiz["id"], question, 1)
    clock.now += MINUTE
    out = await submit(c, quiz["id"])
    assert (out["status"], out["submitted_at"], out["auto_submitted"]) == ("submitted", clock.now.isoformat(), False)
    assert (out["remaining_seconds"], out["questions"], out["answered_count"]) == (0, [], 1)
    assert "already submitted" in (await choose(c, quiz["id"], question, 2, expect=409))["detail"]
    clock.now += HOUR
    again = await submit(c, quiz["id"])
    assert again == {**out, "server_time": clock.now.isoformat()}
    assert await quiz_timer.sweep() == 0
    assert [x.option_index for x in await answers()] == [1]
    [card] = await cards(c)
    assert (card["state"], card["attempt_status"]) == ("attempted", "submitted")


async def test_concurrent_submits_submit_once(shino_class, monkeypatch):
    c = shino_class
    quiz = await quiz_with(c)
    await start(c, quiz["id"])
    ticks = iter(range(1, 100))     # every look at the clock is later than the one before
    monkeypatch.setattr(quiz_attempts.quiz_store, "clock", lambda: NOW + next(ticks) * SEC)

    async def one():
        async with c.client(c.student_user_ids[0], "student") as api:
            return await api.post(f"{MINE}/{quiz['id']}/attempt/submit")

    got = await asyncio.gather(*(one() for _ in range(5)))
    assert [r.status_code for r in got] == [200] * 5
    assert len({r.json()["submitted_at"] for r in got}) == 1
    saved = await row(quiz["id"], c.student_ids[0])
    assert (saved.status, saved.auto_submitted) == ("submitted", False)


async def test_an_answer_racing_the_submit_is_in_or_refused(shino_class):
    """Either the answer was saved before the submit, or it got 409: never saved after it."""
    c = shino_class
    quiz = await quiz_with(c)
    for i in range(4):
        question = ids(await start(c, quiz["id"], i=i))[0]
        async with c.client(c.student_user_ids[i], "student") as api:
            saved, done = await asyncio.gather(
                api.put(f"{MINE}/{quiz['id']}/attempt/answers/{question}", json={"option_index": 1}),
                api.post(f"{MINE}/{quiz['id']}/attempt/submit"))
        assert done.status_code == 200 and saved.status_code in (200, 409)
        assert done.json()["answered_count"] == (1 if saved.status_code == 200 else 0)
        assert (await read(c, quiz["id"], i=i))["answered_count"] == done.json()["answered_count"]


async def test_the_clock_is_read_after_waiting_for_the_attempt(shino_class, clock):     # noqa: F811
    """A request that waited for the row past the deadline is late."""
    c = shino_class
    quiz = await quiz_with(c)
    question = ids(await start(c, quiz["id"]))[0]
    async with AsyncSessionLocal() as db:
        await db.execute(select(QuizAttempt).with_for_update())
        waiting = asyncio.create_task(choose(c, quiz["id"], question, 1, expect=409))
        await asyncio.sleep(0.3)
        assert not waiting.done()
        clock.now = NOW + 10 * MINUTE
        await db.rollback()
    await waiting
    assert await answers() == [] and (await row(quiz["id"], c.student_ids[0])).status == "submitted"


# ── whole-quiz timer (FR-608) ────────────────────────────────────────────────

async def test_answers_count_until_just_before_the_end(shino_class, clock):     # noqa: F811
    c = shino_class
    quiz = await quiz_with(c)
    a, b, _ = ids(await start(c, quiz["id"]))
    clock.now = NOW + 10 * MINUTE - SEC
    assert (await choose(c, quiz["id"], a, 1))["remaining_seconds"] == 1
    clock.now = NOW + 10 * MINUTE
    assert "over" in (await choose(c, quiz["id"], b, 1, expect=409))["detail"]
    # the refused request submitted the attempt, at its deadline
    saved = await row(quiz["id"], c.student_ids[0])
    assert (saved.status, saved.submitted_at, saved.auto_submitted) == ("submitted", NOW + 10 * MINUTE, True)
    assert [x.question_id for x in await answers()] == [a]


@pytest.mark.parametrize("touch", ["read", "start", "submit", "sweep", "close"])
async def test_any_touch_after_the_end_submits_at_the_deadline(shino_class, clock, touch):     # noqa: F811
    c = shino_class
    quiz = await quiz_with(c)
    await choose(c, quiz["id"], ids(await start(c, quiz["id"]))[0], 1)
    clock.now = NOW + HOUR
    if touch == "read":
        assert (await read(c, quiz["id"]))["status"] == "submitted"
    elif touch == "start":
        await start(c, quiz["id"], expect=409)
    elif touch == "submit":
        assert (await submit(c, quiz["id"]))["auto_submitted"] is True
    elif touch == "sweep":
        assert await quiz_timer.sweep() == 1
    else:
        await act(c, quiz["id"], "close")
    saved = await row(quiz["id"], c.student_ids[0])
    assert (saved.status, saved.submitted_at, saved.auto_submitted) == ("submitted", NOW + 10 * MINUTE, True)
    assert len(await answers()) == 1


@pytest.mark.parametrize("mode", ["quiz", "question"])
async def test_the_closing_time_ends_attempts_too(shino_class, clock, mode):     # noqa: F811
    c = shino_class
    quiz = await quiz_with(c, timer_mode=mode, timer_seconds=600, closes_at=(NOW + 5 * MINUTE).isoformat())
    out = await start(c, quiz["id"])
    closes = (NOW + 5 * MINUTE).isoformat()
    assert out["ends_at"] == closes and out["remaining_seconds"] == 300
    if mode == "question":
        assert out["question_ends_at"] == closes
        out = await next_(c, quiz["id"], ids(out)[0])
        assert (out["ends_at"], out["question_ends_at"]) == (closes, closes)
    clock.now = NOW + 5 * MINUTE
    await choose(c, quiz["id"], ids(out)[0], 1, expect=409)
    assert (await row(quiz["id"], c.student_ids[0])).submitted_at == NOW + 5 * MINUTE


# ── closing by hand ──────────────────────────────────────────────────────────

async def test_closing_the_quiz_submits_running_attempts(shino_class, clock):     # noqa: F811
    c = shino_class
    quiz, untouched = await quiz_with(c), await quiz_with(c)
    question = ids(await start(c, quiz["id"]))[0]
    await start(c, untouched["id"])
    await choose(c, quiz["id"], question, 1)
    await start(c, quiz["id"], i=1)
    clock.now = NOW + MINUTE
    await submit(c, quiz["id"], i=1)
    clock.now = NOW + 2 * MINUTE
    await act(c, quiz["id"], "close")
    mine, theirs = await row(quiz["id"], c.student_ids[0]), await row(quiz["id"], c.student_ids[1])
    assert (mine.status, mine.submitted_at, mine.auto_submitted) == ("submitted", NOW + 2 * MINUTE, True)
    assert (theirs.status, theirs.submitted_at, theirs.auto_submitted) == ("submitted", NOW + MINUTE, False)
    await choose(c, quiz["id"], question, 2, expect=409)
    assert [x.option_index for x in await answers()] == [1]
    assert (await read(c, untouched["id"]))["status"] == "in_progress"


async def test_closing_while_students_start(shino_class):
    """No attempt is ever left running in a closed quiz."""
    c = shino_class
    for _ in range(3):
        quiz = await quiz_with(c)

        async def one(i, quiz_id):
            async with c.client(c.student_user_ids[i], "student") as api:
                return (await api.post(f"{MINE}/{quiz_id}/attempt")).status_code

        async def shut(quiz_id):
            async with c.client(c.lecturer_user_id, "lecturer") as api:
                return (await api.post(f"{URL}/{quiz_id}/close")).status_code

        *started, closed = await asyncio.gather(*(one(i, quiz["id"]) for i in range(4)), shut(quiz["id"]))
        assert closed == 200 and set(started) <= {201, 409}
        async with AsyncSessionLocal() as db:
            states = list((await db.execute(
                select(QuizAttempt.status).where(QuizAttempt.quiz_id == quiz["id"]))).scalars())
        assert states == ["submitted"] * started.count(201)


async def test_unpublishing_while_a_student_starts(shino_class):
    """A quiz with an attempt stays published; an unpublished one has none."""
    c = shino_class
    for _ in range(3):
        quiz = await quiz_with(c)
        async with c.client(c.student_user_ids[0], "student") as api, \
                c.client(c.lecturer_user_id, "lecturer") as lecturer:
            began, back = await asyncio.gather(api.post(f"{MINE}/{quiz['id']}/attempt"),
                                               lecturer.post(f"{URL}/{quiz['id']}/unpublish"))
        assert (began.status_code, back.status_code) in [(201, 409), (403, 200)]
        async with AsyncSessionLocal() as db:
            has = await db.scalar(select(QuizAttempt.id).where(QuizAttempt.quiz_id == quiz["id"])) is not None
            assert (await db.get(Quiz, quiz["id"])).status == ("published" if has else "draft")


# ── per-question timer (FR-608) ──────────────────────────────────────────────

async def per_question(c, n=3, **over):
    quiz = await quiz_with(c, mcq=n, timer_mode="question", timer_seconds=60, **over)
    return quiz["id"], await quiz_ids(quiz["id"])


async def test_one_question_at_a_time(shino_class, clock):     # noqa: F811
    c = shino_class
    qid, (a, b, d) = await per_question(c)
    out = await start(c, qid)
    assert (ids(out), out["current_number"], out["question_count"]) == ([a], 1, 3)
    assert out["question_ends_at"] == (NOW + MINUTE).isoformat() and out["question_remaining_seconds"] == 60
    assert out["ends_at"] == (NOW + 3 * MINUTE).isoformat() and out["remaining_seconds"] == 180
    assert "hasn't started" in (await choose(c, qid, b, 1, expect=409))["detail"]
    assert "hasn't started" in (await next_(c, qid, b, expect=409))["detail"]
    await choose(c, qid, a, 1)
    out = await next_(c, qid, a)
    assert (ids(out), out["current_number"], out["answered_count"]) == ([b], 2, 1)
    assert "time is over" in (await choose(c, qid, a, 2, expect=409))["detail"]
    await choose(c, qid, d, 1, expect=409)
    assert [(x.question_id, x.option_index) for x in await answers()] == [(a, 1)]


async def test_moving_on_early_gives_no_time_away(shino_class, clock):     # noqa: F811
    c = shino_class
    qid, (a, b, d) = await per_question(c)
    await start(c, qid)
    clock.now = NOW + 20 * SEC
    out = await next_(c, qid, a)
    assert out["question_ends_at"] == (NOW + 80 * SEC).isoformat()
    assert out["ends_at"] == (NOW + 140 * SEC).isoformat()      # 20 s + two full questions
    clock.now = NOW + 30 * SEC
    out = await next_(c, qid, b)
    assert (out["question_ends_at"], out["ends_at"]) == ((NOW + 90 * SEC).isoformat(),) * 2
    clock.now = NOW + 40 * SEC
    out = await next_(c, qid, d)
    assert (out["status"], out["auto_submitted"], out["submitted_at"]) == ("submitted", False, clock.now.isoformat())


async def test_a_repeated_next_skips_nothing(shino_class, clock):     # noqa: F811
    c = shino_class
    qid, (a, b, d) = await per_question(c)
    await start(c, qid)
    assert ids(await next_(c, qid, a)) == [b]
    clock.now = NOW + 10 * SEC
    again = await next_(c, qid, a)
    assert ids(again) == [b] and again["question_ends_at"] == (NOW + MINUTE).isoformat()
    await next_(c, qid, b)
    done = await next_(c, qid, d)
    assert await next_(c, qid, d) == done and done["status"] == "submitted"

    async def one(i):
        async with c.client(c.student_user_ids[1], "student") as api:
            return await api.post(f"{MINE}/{qid}/attempt/next", json={"question_id": a})

    await start(c, qid, i=1)
    got = await asyncio.gather(*(one(i) for i in range(4)))
    assert [(r.status_code, r.json()["current_number"]) for r in got] == [(200, 2)] * 4


async def test_the_attempt_moves_on_when_a_questions_time_is_up(shino_class, clock):     # noqa: F811
    c = shino_class
    qid, (a, b, d) = await per_question(c)
    await start(c, qid)
    clock.now = NOW + MINUTE - SEC
    await choose(c, qid, a, 1)
    clock.now = NOW + MINUTE
    assert "time is over" in (await choose(c, qid, a, 2, expect=409))["detail"]
    saved = await row(qid, c.student_ids[0])
    assert (saved.current_index, saved.question_ends_at) == (1, NOW + 2 * MINUTE)
    # a "next" for the question that ran out doesn't skip the new one
    out = await next_(c, qid, a)
    assert (ids(out), out["question_remaining_seconds"]) == ([b], 60)
    assert out["ends_at"] == (NOW + 3 * MINUTE).isoformat()
    assert [x.option_index for x in await answers()] == [1]


async def test_being_away_costs_the_questions_that_ran_out(shino_class, clock):     # noqa: F811
    c = shino_class
    qid, (a, b, d) = await per_question(c)
    await start(c, qid)
    clock.now = NOW + 150 * SEC
    for out in (await start(c, qid, expect=200), await read(c, qid)):
        assert (ids(out), out["current_number"], out["question_remaining_seconds"]) == ([d], 3, 30)
        assert out["ends_at"] == (NOW + 3 * MINUTE).isoformat()
    await choose(c, qid, b, 1, expect=409)
    await choose(c, qid, d, 1)
    clock.now = NOW + 3 * MINUTE
    out = await read(c, qid)
    assert (out["status"], out["auto_submitted"]) == ("submitted", True)
    assert out["submitted_at"] == (NOW + 3 * MINUTE).isoformat() and out["answered_count"] == 1


async def test_the_sweep_ends_a_per_question_attempt(shino_class, clock):     # noqa: F811
    c = shino_class
    qid, (a, _b, _d) = await per_question(c)
    await start(c, qid)
    clock.now = NOW + 10 * SEC
    await next_(c, qid, a)
    clock.now = NOW + 130 * SEC - SEC
    assert await quiz_timer.sweep() == 0
    clock.now = NOW + 130 * SEC
    assert await quiz_timer.sweep() == 1
    saved = await row(qid, c.student_ids[0])
    assert (saved.status, saved.submitted_at, saved.auto_submitted) == ("submitted", NOW + 130 * SEC, True)


async def test_submitting_early_with_questions_left(shino_class):
    c = shino_class
    qid, (a, b, _d) = await per_question(c)
    await start(c, qid)
    await choose(c, qid, a, 1)
    out = await submit(c, qid)
    assert (out["status"], out["auto_submitted"], out["current_number"]) == ("submitted", False, None)
    assert (await next_(c, qid, a))["status"] == "submitted"
    await choose(c, qid, b, 1, expect=409)


async def test_next_is_only_for_per_question_timers(shino_class):
    c = shino_class
    quiz = await quiz_with(c)
    out = await start(c, quiz["id"])
    await next_(c, quiz["id"], ids(out)[0], expect=409)
    qid, _ = await per_question(c)
    await start(c, qid)
    await next_(c, qid, ids(out)[0], expect=404)      # another quiz's question


# ── shuffle ──────────────────────────────────────────────────────────────────

def orders(out):
    return [(q["id"], [o["index"] for o in q["options"]]) for q in out["questions"]]


async def test_shuffle_is_the_students_own_and_stable(shino_class, monkeypatch, clock):     # noqa: F811
    c = shino_class
    monkeypatch.setattr(quiz_attempts, "_random", random.Random(7))
    quiz = await quiz_with(c, mcq=6, shuffle=True)
    stored = await quiz_ids(quiz["id"])
    first, other = await start(c, quiz["id"]), await start(c, quiz["id"], i=1)
    assert sorted(ids(first)) == sorted(stored) and ids(first) != stored
    assert orders(first) != orders(other)
    assert [q["number"] for q in first["questions"]] == [1, 2, 3, 4, 5, 6]
    assert any(o != [0, 1, 2, 3] for _, o in orders(first))
    for q in first["questions"]:      # each option keeps its own index
        assert {o["index"]: o["text"] for o in q["options"]} == {0: "W", 1: "X", 2: "Y", 3: "Z"}
    clock.now += MINUTE
    assert orders(await start(c, quiz["id"], expect=200)) == orders(await read(c, quiz["id"])) == orders(first)
    target = ids(first)[0]
    assert orders(await choose(c, quiz["id"], target, 2)) == orders(first)
    assert [(x.question_id, x.option_index) for x in await answers()] == [(target, 2)]


async def test_no_shuffle_keeps_the_lecturers_order(shino_class):
    c = shino_class
    quiz = await quiz_with(c, mcq=6)
    assert orders(await start(c, quiz["id"])) == [(i, [0, 1, 2, 3]) for i in await quiz_ids(quiz["id"])]


async def test_a_shuffled_per_question_quiz_follows_its_own_order(shino_class, monkeypatch):
    c = shino_class
    monkeypatch.setattr(quiz_attempts, "_random", random.Random(3))
    qid, stored = await per_question(c, n=5, shuffle=True)
    out, seen = await start(c, qid), []
    while out["questions"]:
        seen += ids(out)
        out = await next_(c, qid, seen[-1])
    assert sorted(seen) == sorted(stored) and seen != stored
    assert seen == [x["question_id"] for x in (await row(qid, c.student_ids[0])).layout]


@pytest.mark.parametrize(("options", "kept"), [
    (["A tree", "A graph", "A list", "All of the above"], True),
    (["O(1)", "O(n)", "None of these", "O(log n)"], True),
    (["Stack", "Queue", "Both A and B", "Neither"], True),
    (["Stack", "Queue", "Heap", "Both ends of a deque"], False),
    (["W", "X", "Y", "Z"], False),
])
def test_options_that_refer_to_each_other_keep_their_order(monkeypatch, options, kept):
    monkeypatch.setattr(quiz_attempts, "_random", random.Random(1))
    quiz = Quiz(shuffle=True)
    [item] = quiz_attempts._layout(quiz, [question_row(1, options=options)])
    assert (item["options"] == [0, 1, 2, 3]) is kept and sorted(item["options"]) == [0, 1, 2, 3]


# ── sweep ────────────────────────────────────────────────────────────────────

async def test_the_sweep_submits_only_what_is_over(shino_class, clock):     # noqa: F811
    c = shino_class
    early = await quiz_with(c, timer_seconds=60)
    late = await quiz_with(c, timer_seconds=600)
    live = await create(c, game(c))
    await insert(question_row(live["id"], approved=True))
    await act(c, live["id"], "publish")
    await insert(QuizAttempt(quiz_id=live["id"], student_id=c.student_ids[0], status="in_progress", started_at=NOW,
                             ends_at=NOW))
    for quiz in (early, late):
        await start(c, quiz["id"])
        await start(c, quiz["id"], i=1)
    await submit(c, early["id"], i=1)
    clock.now = NOW + 61 * SEC
    assert await quiz_timer.sweep() == 1
    assert await quiz_timer.sweep() == 0
    got = [await row(quiz["id"], c.student_ids[i]) for quiz in (early, late) for i in (0, 1)]
    assert [(a.status, a.auto_submitted) for a in got] == [
        ("submitted", True), ("submitted", False), ("in_progress", False), ("in_progress", False)]
    assert got[0].submitted_at == NOW + 60 * SEC
    assert (await row(live["id"], c.student_ids[0])).status == "in_progress"


async def test_the_sweep_doesnt_wait_for_a_student(shino_class, clock):     # noqa: F811
    c = shino_class
    quiz = await quiz_with(c)
    await start(c, quiz["id"])
    await start(c, quiz["id"], i=1)
    clock.now = NOW + HOUR
    async with AsyncSessionLocal() as db:
        await db.execute(select(QuizAttempt).where(QuizAttempt.student_id == c.student_ids[0]).with_for_update())
        assert await asyncio.wait_for(quiz_timer.sweep(), 5) == 1
        await db.rollback()
    assert await quiz_timer.sweep() == 1


async def test_a_submitted_attempt_stays_out_of_reach_of_a_status_change(shino_class, clock):     # noqa: F811
    """A quiz closed and (wrongly) set back to published doesn't reopen its attempts."""
    c = shino_class
    quiz = await quiz_with(c)
    question = ids(await start(c, quiz["id"]))[0]
    await act(c, quiz["id"], "close")
    await set_status(quiz["id"], "published")
    await start(c, quiz["id"], expect=409)
    await choose(c, quiz["id"], question, 1, expect=409)


async def test_the_sweep_loop_runs_until_cancelled_and_survives_errors(monkeypatch):
    calls = {"sweep": 0, "sleep": []}

    async def fake_sweep():
        calls["sweep"] += 1
        if calls["sweep"] == 1:
            raise RuntimeError("db down")
        return 1

    async def fake_sleep(seconds):
        calls["sleep"].append(seconds)
        if len(calls["sleep"]) >= 2:
            raise asyncio.CancelledError

    monkeypatch.setattr(settings, "QUIZ_SWEEP_SECONDS", 1)
    monkeypatch.setattr(quiz_timer, "sweep", fake_sweep)
    monkeypatch.setattr(quiz_timer, "_sleep", fake_sleep)
    with pytest.raises(asyncio.CancelledError):
        await quiz_timer.quiz_sweep_loop()
    assert calls == {"sweep": 2, "sleep": [1, 1]}


async def test_the_sweep_loop_is_off_when_the_interval_is_not_positive(monkeypatch):
    monkeypatch.setattr(settings, "QUIZ_SWEEP_SECONDS", 0)
    monkeypatch.setattr(quiz_timer, "sweep", lambda: pytest.fail("must not sweep"))
    await quiz_timer.quiz_sweep_loop()


def test_the_sweep_runs_often_enough():
    assert 0 < settings.QUIZ_SWEEP_SECONDS < 2      # NFR-47


# ── the timer rules (pure) ───────────────────────────────────────────────────

@pytest.mark.parametrize("gap", [7, 60, 61, 125])
def test_the_deadlines_dont_depend_on_how_often_the_attempt_is_touched(gap):
    """One settle at the end gives what many settles on the way give."""
    quiz = Quiz(timer_mode="question", timer_seconds=60, closes_at=NOW + timedelta(seconds=270))

    def fresh():
        attempt = QuizAttempt(status="in_progress", auto_submitted=False, layout=[{}] * 5)
        quiz_timer.start_clock(quiz, attempt, NOW, 5)
        return attempt

    often = fresh()
    for s in range(0, 400, gap):
        now = NOW + timedelta(seconds=s)
        quiz_timer.settle(quiz, often, now)
        once = fresh()
        quiz_timer.settle(quiz, once, now)
        assert [(a.status, a.current_index if a.status == "in_progress" else None, a.question_ends_at, a.ends_at,
                 a.submitted_at) for a in (often, once)] == [
            ("submitted" if s >= 270 else "in_progress", s // 60 if s < 270 else None,
             min(NOW + timedelta(seconds=(s // 60 + 1) * 60), quiz.closes_at) if s < 270 else None,
             quiz.closes_at, quiz.closes_at if s >= 270 else None)] * 2


def test_midnight_is_no_special_case():
    quiz = Quiz(timer_mode="quiz", timer_seconds=600, closes_at=None)
    attempt = QuizAttempt(status="in_progress")
    quiz_timer.start_clock(quiz, attempt, datetime(2026, 12, 31, 23, 55), 3)
    assert attempt.ends_at == datetime(2027, 1, 1, 0, 5)
