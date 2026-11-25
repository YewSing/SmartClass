"""S45: grading (FR-616, FR-617, NFR-55) and the `quiz.graded` notification (FR-206).

The LLM is scripted here, or replayed from the replies the live tests recorded.
"""
import asyncio
import json
from datetime import timedelta
from decimal import Decimal

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.models.class_ import Enrollment
from app.models.notification import Notification
from app.models.quiz import Quiz, QuizAnswer, QuizAttempt
from app.models.user import User
from app.services import notify, quiz_grading, quiz_release, quiz_timer
from app.services.kb import llm
from app.services.quiz import checks, grading
from tests import quiz_grading_cases as cases
from tests.test_quiz_attempts import (
    MINUTE,
    SECRETS,
    answers,
    choose,
    ids,
    next_,
    quiz_ids,
    quiz_with,
    read,
    row,
    save,
    start,
    student,
    submit,
)
from tests.test_quiz_crud import URL, call, create, game, insert, patch, question_row
from tests.test_quiz_publish import HOUR, NOW, act, audits, clock  # noqa: F401 (clock: fixture)

db = pytest.mark.db


@pytest.fixture(autouse=True)
def _fixed_time(clock):     # noqa: F811
    """Every test runs on the fake clock."""


class Grader:
    """Grades each answer by its text, e.g. "0.5 because"; "down", "junk" and "crash" fail the call."""

    def __init__(self):
        self.calls, self.confidence, self.before_reply = [], 0.9, None

    async def chat(self, messages, max_tokens=None, temperature=0.2):
        self.calls.append(messages)
        items = [json.loads(line) for line in messages[1]["content"].splitlines()[1:]]
        if self.before_reply:
            await self.before_reply()
        texts = [i["student_answer"] for i in items]
        for word, error in (("down", llm.LLMUnavailable("down")), ("quota", llm.LLMQuotaExhausted("quota")),
                            ("crash", RuntimeError("bug"))):
            if word in texts:
                raise error
        if "junk" in texts:
            return "no json here"
        return json.dumps({"grades": [
            {"number": i["number"], "score": float(i["student_answer"].split()[0]), "reason": "Because.",
             "confidence": self.confidence} for i in items]})


@pytest.fixture
def grader(monkeypatch):
    fake = Grader()
    monkeypatch.setattr(llm, "chat", fake.chat)
    return fake


async def answered(c, *texts, i=0, quiz=None, submitted=True, **over):
    """A quiz of short questions, answered by student `i` with `texts`; the quiz."""
    quiz = quiz or await quiz_with(c, mcq=0, short=len(texts), **over)
    out = await start(c, quiz["id"], i=i)
    for qid, t in zip(ids(out), texts, strict=True):
        if t is not None:
            await save(c, quiz["id"], qid, {"text": t}, i=i)
    if submitted:
        await submit(c, quiz["id"], i=i)
    return quiz


async def listed(c, quiz, state=None, expect=200, **kw):
    params = {"state": state} if state else {}
    return await call(c, "GET", f"{URL}/{quiz['id']}/short-answers", expect, params=params, **kw)


async def set_score(c, quiz, answer_id, score=0.75, feedback="Good point", expect=200, **kw):
    kw.setdefault("json", {"score": score, "feedback": feedback})
    return await call(c, "PUT", f"{URL}/{quiz['id']}/short-answers/{answer_id}/score", expect, **kw)


def scores(rows):
    return [None if a.score is None else float(a.score) for a in rows]


# ── multiple choice, on submit ───────────────────────────────────────────────

async def three_choices(c, **over):
    """Started, with a right, a wrong and no answer (the right option is 2)."""
    quiz = await quiz_with(c, mcq=3, **over)
    await start(c, quiz["id"])
    qids = await quiz_ids(quiz["id"])
    for qid, option in zip(qids, (2, 0, None), strict=True):
        if option is not None:
            await choose(c, quiz["id"], qid, option)
    return quiz


@db
async def test_choices_are_graded_on_submit_and_not_before(shino_class, clock):     # noqa: F811
    c = shino_class
    quiz = await three_choices(c)
    assert [(a.score, a.correct, a.graded_by) for a in await answers()] == [(None, None, None)] * 2
    clock.now += MINUTE
    out = await submit(c, quiz["id"])
    first = await answers()
    assert [(a.score, a.correct, a.graded_by, a.graded_at, a.flagged) for a in first] == [
        (Decimal(1), True, "auto", clock.now, False), (Decimal(0), False, "auto", clock.now, False)]
    # a repeated submit changes nothing, and students still see no marks (NFR-41)
    clock.now += MINUTE
    await submit(c, quiz["id"])
    assert [a.graded_at for a in await answers()] == [a.graded_at for a in first]
    seen = json.dumps([out, await read(c, quiz["id"])]).lower()
    assert not any(s in seen for s in (*SECRETS, "score", "correct", "flagged"))


@db
@pytest.mark.parametrize("touch", ["read", "start", "submit", "save", "sweep", "close"])
async def test_choices_are_graded_however_the_attempt_ends(shino_class, clock, touch):     # noqa: F811
    c = shino_class
    quiz = await three_choices(c)
    clock.now = NOW + HOUR
    if touch == "sweep":
        assert await quiz_timer.sweep() == 1
    elif touch == "close":
        await act(c, quiz["id"], "close")
    elif touch == "save":       # refused (409), and the time-out it noticed is kept
        await choose(c, quiz["id"], (await quiz_ids(quiz["id"]))[2], 2, expect=409)
    else:
        await {"read": read, "start": start, "submit": submit}[touch](
            c, quiz["id"], expect=409 if touch == "start" else 200)
    assert scores(await answers()) == [1, 0]


@db
async def test_choices_are_graded_after_the_last_next(shino_class):
    c = shino_class
    quiz = await quiz_with(c, mcq=2, timer_mode="question", timer_seconds=60, shuffle=True)
    out = await start(c, quiz["id"])
    while out["questions"]:
        qid = ids(out)[0]
        await choose(c, quiz["id"], qid, 2)
        out = await next_(c, quiz["id"], qid)
    assert scores(await answers()) == [1, 1]


@db
async def test_closing_grades_every_student_and_only_that_quiz(shino_class):
    c = shino_class
    quiz, other = await three_choices(c), await quiz_with(c, mcq=1)
    await start(c, quiz["id"], i=1)
    await choose(c, quiz["id"], (await quiz_ids(quiz["id"]))[0], 1, i=1)
    await start(c, other["id"])
    await choose(c, other["id"], (await quiz_ids(other["id"]))[0], 2)
    await act(c, quiz["id"], "close")
    assert scores(await answers()) == [1, 0, 0, None]


@db
async def test_the_ai_is_not_asked_about_choices_or_running_attempts(shino_class, grader):
    c = shino_class
    quiz = await three_choices(c)
    await submit(c, quiz["id"])
    await answered(c, "1 running", submitted=False)
    assert await quiz_grading.grade_pending() is True
    assert grader.calls == []


# ── short answers: the AI ────────────────────────────────────────────────────

@db
async def test_short_answers_are_graded_by_the_ai(shino_class, grader, clock):     # noqa: F811
    c = shino_class
    quiz = await answered(c, "1 full", "0.5 half", "0.25 bit", None)
    assert scores(await answers()) == [None] * 3
    clock.now += MINUTE
    assert await quiz_grading.grade_pending() is True
    got = await answers()
    assert scores(got) == [1, 0.5, 0.25] and [a.correct for a in got] == [True, True, False]
    assert {(a.graded_by, a.graded_at, a.reason, a.confidence, a.flagged, a.feedback) for a in got} == {
        ("ai", clock.now, "Because.", Decimal("0.9"), False, None)}
    # one call for the student's answers; the scores are final
    [messages] = grader.calls
    assert json.loads(messages[1]["content"].splitlines()[2]) == {
        "number": 2, "question": "Why 1?", "suggested_answer": "SHA-answer", "student_answer": "0.5 half"}
    await quiz_grading.grade_pending()
    assert len(grader.calls) == 1
    assert [a["state"] for a in (await listed(c, quiz))["answers"]] == ["graded"] * 3


@db
async def test_the_ai_gets_nothing_about_the_student(shino_class, grader):
    c = shino_class
    await answered(c, "1 full")
    await quiz_grading.grade_pending()
    said = json.dumps(grader.calls).lower()
    assert "shino" not in said and "sh000001" not in said and "siswa" not in said


@db
async def test_students_are_never_graded_in_one_call(shino_class, grader):
    c = shino_class
    quiz = await answered(c, "1 a", "1 b")
    await answered(c, "0 c", "0 d", i=1, quiz=quiz)
    await quiz_grading.grade_pending()
    assert sorted(m[1]["content"].count("student_answer") for m in grader.calls) == [2, 2]
    assert not any("1 a" in m[1]["content"] and "0 c" in m[1]["content"] for m in grader.calls)
    assert scores(await answers()) == [1, 1, 0, 0]


@db
async def test_many_answers_take_several_calls_and_rounds(shino_class, grader, monkeypatch):
    c = shino_class
    monkeypatch.setattr(settings, "QUIZ_GRADE_BATCH", 2)
    monkeypatch.setattr(settings, "QUIZ_GRADE_CONCURRENCY", 2)
    quiz = await answered(c, *["1 x"] * 3)
    await answered(c, *["0 y"] * 3, i=1, quiz=quiz)
    for done in (3, 6):     # two calls a round, at most two answers each, never of two students
        await quiz_grading.grade_pending()
        assert sum(s is not None for s in scores(await answers())) == done
    assert len(grader.calls) == 4 and scores(await answers()) == [1, 1, 1, 0, 0, 0]


@db
@pytest.mark.parametrize(("confidence", "flagged"), [(0.69, True), (0.7, False), (0, True), (1, False)])
async def test_a_score_the_ai_is_not_sure_of_is_flagged(shino_class, grader, confidence, flagged):
    c = shino_class
    grader.confidence = confidence
    quiz = await answered(c, "0.5 maybe")
    await quiz_grading.grade_pending()
    [a] = await answers()
    assert (a.flagged, a.score) == (flagged, Decimal("0.5"))     # still final
    assert (await listed(c, quiz))["flagged_count"] == int(flagged)


@db
async def test_a_game_is_not_graded_here(shino_class, grader):
    c = shino_class
    quiz = await create(c, game(c))
    [question] = await insert(question_row(quiz["id"], type="short", options=None, answer=None, approved=True,
                                           suggested_answer="Because"))
    [attempt] = await insert(QuizAttempt(quiz_id=quiz["id"], student_id=c.student_ids[0], status="submitted",
                                         started_at=NOW, submitted_at=NOW))
    [answer] = await insert(QuizAnswer(attempt_id=attempt, question_id=question, text="1 x", answered_at=NOW))
    await quiz_grading.grade_pending()
    assert grader.calls == [] and scores(await answers()) == [None]
    await listed(c, quiz, expect=409)
    await set_score(c, quiz, answer, expect=409)


# ── when the AI fails (NFR-55) ───────────────────────────────────────────────

async def retext(answer_text, new):
    async with AsyncSessionLocal() as s:
        await s.execute(text("UPDATE m6_answers SET text = :new WHERE text = :old"), {"new": new, "old": answer_text})
        await s.commit()


@db
@pytest.mark.parametrize("failure", ["down", "quota"])
async def test_an_outage_leaves_answers_pending_until_the_ai_is_back(shino_class, grader, clock,  # noqa: F811
                                                                     failure):
    c = shino_class
    quiz = await answered(c, failure, "1 fine")
    for _ in range(3):
        assert await quiz_grading.grade_pending() is False      # nobody reached it
        clock.now += timedelta(seconds=settings.QUIZ_GRADE_RETRY_SECONDS)
    assert scores(await answers()) == [None, None]
    assert (await listed(c, quiz))["pending_count"] == 2
    # the lecturer's and the student's pages work meanwhile (NFR-24)
    assert (await read(c, quiz["id"]))["status"] == "submitted"
    await retext(failure, "0.5 back")
    assert await quiz_grading.grade_pending() is True
    assert scores(await answers()) == [0.5, 1]      # an outage doesn't split the student's answers up
    assert len(grader.calls) == 4


@db
async def test_a_failed_answer_waits_and_new_ones_go_first(shino_class, grader, clock, monkeypatch):     # noqa: F811
    c = shino_class
    monkeypatch.setattr(settings, "QUIZ_GRADE_CONCURRENCY", 1)
    quiz = await answered(c, "down")
    assert await quiz_grading.grade_pending() is False
    assert await quiz_grading.grade_pending() is True and len(grader.calls) == 1     # not due again yet
    clock.now += timedelta(seconds=settings.QUIZ_GRADE_RETRY_SECONDS)
    await answered(c, "1 new", i=1, quiz=quiz)
    assert await quiz_grading.grade_pending() is True
    assert scores(await answers()) == [None, 1]


@db
async def test_one_student_failing_doesnt_stop_the_others(shino_class, grader):
    c = shino_class
    quiz = await answered(c, "down")
    for i, t in enumerate(("1 fine", "junk", "crash"), start=1):
        await answered(c, t, i=i, quiz=quiz)
    assert await quiz_grading.grade_pending() is True
    assert scores(await answers()) == [None, 1, None, None]


@db
@pytest.mark.parametrize("failure", ["junk", "crash"])
async def test_an_unusable_grade_is_retried_alone_with_longer_waits(shino_class, grader, clock,  # noqa: F811
                                                                   monkeypatch, failure):
    c = shino_class
    monkeypatch.setattr(settings, "QUIZ_GRADE_RETRY_MAX_SECONDS", 200)
    await answered(c, "1 fine", failure, "0 bad")
    assert await quiz_grading.grade_pending() is True
    assert scores(await answers()) == [None] * 3
    clock.now += timedelta(seconds=60)
    await quiz_grading.grade_pending()
    assert scores(await answers()) == [1, None, 0]      # the student's others are done
    waits = []
    for _ in range(3):
        [left] = [a for a in await answers() if a.score is None]
        waits.append((left.grade_tries, (left.grade_after - clock.now).total_seconds()))
        clock.now = left.grade_after
        await quiz_grading.grade_pending()
    assert waits == [(2, 120), (3, 200), (4, 200)]
    await retext(failure, "1 fixed")
    clock.now += timedelta(seconds=200)
    await quiz_grading.grade_pending()
    assert scores(await answers()) == [1, 1, 0]
    assert all(a.grade_after is None for a in await answers())


@db
async def test_a_corrected_reply_is_used(shino_class, monkeypatch):
    c = shino_class
    good = {"grades": [{"number": 1, "score": 1, "reason": "Yes.", "confidence": 1}]}
    replies, calls = [{"grades": []}, good], []

    async def chat(messages, max_tokens=None, temperature=0.2):
        calls.append(messages)
        return json.dumps(replies.pop(0))

    monkeypatch.setattr(llm, "chat", chat)
    await answered(c, "x")
    await quiz_grading.grade_pending()
    assert scores(await answers()) == [1] and "from 1 to 1" in calls[1][-1]["content"]


# ── what the AI may reply ────────────────────────────────────────────────────

def a_grade(number=1, **over):
    return {"number": number, "score": 0.5, "reason": "why", "confidence": 0.9, **over}


def test_grades_come_back_in_order_with_clean_reasons():
    got = checks.check_grades({"grades": [a_grade(2, score=1), a_grade(1, score=0, reason=" a\x00\n b ")]}, 2)
    assert [(g.number, g.score) for g in got] == [(1, 0), (2, 1)] and got[0].reason == "a b"
    [long] = checks.check_grades({"grades": [a_grade(reason="x" * 600)]}, 1)
    assert len(long.reason) == 500


@pytest.mark.parametrize("data", [
    {}, {"grades": None}, {"grades": {}}, {"grades": []}, [],
    {"grades": [a_grade(), a_grade()]}, {"grades": [a_grade(0)]}, {"grades": [a_grade(2)]},
    {"grades": [a_grade(), a_grade(2)]},
    *({"grades": [a_grade(score=s)]} for s in (-0.1, 1.1, 5, "0.5", True, None, float("nan"), float("inf"))),
    *({"grades": [a_grade(confidence=s)]} for s in (-0.1, 1.1, "high", True, None, float("nan"))),
    *({"grades": [a_grade(reason=r)]} for r in ("", "  ", "\x00", None, 5)),
])
def test_bad_grades_are_refused(data):
    with pytest.raises(ValueError):
        checks.check_grades(data, 1)


async def test_unusable_grades_are_malformed_output(monkeypatch):
    async def chat(messages, max_tokens=None, temperature=0.2):
        return '{"grades": []}'

    monkeypatch.setattr(llm, "chat", chat)
    with pytest.raises(llm.LLMMalformedOutput):
        await grading.grade([grading.ShortAnswer("Q?", "A", "B")])


# ── the lecturer (FR-617) ────────────────────────────────────────────────────

@db
async def test_the_lecturer_lists_the_short_answers(shino_class, grader, clock):     # noqa: F811
    c = shino_class
    quiz = await quiz_with(c, mcq=1, short=2)
    a, b, d = await quiz_ids(quiz["id"])
    for i, submitted in enumerate((True, True, False)):
        await start(c, quiz["id"], i=i)
        await choose(c, quiz["id"], a, 2, i=i)
        await save(c, quiz["id"], b, {"text": f"0.{i + 1} x"}, i=i)
        if submitted:
            await submit(c, quiz["id"], i=i)
    grader.confidence = 0.4
    await quiz_grading.grade_pending()
    await save(c, quiz["id"], d, {"text": "late"}, i=2)
    await submit(c, quiz["id"], i=2)
    everything = await listed(c, quiz)
    assert (everything["pending_count"], everything["flagged_count"]) == (2, 2)
    got = everything["answers"]
    assert [(x["question_id"], x["student_id"], x["state"]) for x in got] == [
        (b, c.student_ids[0], "flagged"), (b, c.student_ids[1], "flagged"), (b, c.student_ids[2], "pending"),
        (d, c.student_ids[2], "pending")]
    assert got[0] == {
        "id": got[0]["id"], "student_id": c.student_ids[0], "student_name": "Shino Student 1",
        "matric_no": "SH000001", "question_id": b, "question_text": "Why 0?", "suggested_answer": "SHA-answer",
        "text": "0.1 x", "state": "flagged", "score": 0.1, "correct": False, "graded_by": "ai",
        "graded_at": NOW.isoformat(), "reason": "Because.", "confidence": 0.4, "feedback": None}
    assert (got[2]["score"], got[2]["graded_by"], got[2]["reason"]) == (None, None, None)
    for state, expected in [("flagged", got[:2]), ("pending", got[2:]), ("graded", [])]:
        narrowed = await listed(c, quiz, state)
        assert narrowed == {**everything, "answers": expected}
    await listed(c, quiz, "best", expect=422)


@db
async def test_the_lecturer_changes_a_score_with_feedback(shino_class, grader, clock):     # noqa: F811
    c = shino_class
    grader.confidence = 0.2
    quiz = await answered(c, "0.25 low")
    await quiz_grading.grade_pending()
    [a] = await answers()
    clock.now += HOUR
    out = await set_score(c, quiz, a.id, 0.5, "  You also named the cause  ")
    assert (out["score"], out["correct"], out["state"], out["graded_by"], out["feedback"], out["graded_at"]) == (
        0.5, True, "graded", "lecturer", "You also named the cause", clock.now.isoformat())
    assert (out["reason"], out["confidence"]) == ("Because.", 0.2)      # what the AI said stays
    assert (await listed(c, quiz))["answers"] == [out]
    [entry] = await audits("QUIZ_SCORE_CHANGE")
    assert (entry.actor_id, entry.target_type, entry.target_id) == (c.lecturer_user_id, "m6_answer", str(a.id))
    assert entry.ts is not None
    assert json.loads(entry.old_val) == {"score": 0.25, "graded_by": "ai", "flagged": True, "feedback": None}
    assert json.loads(entry.new_val) == {
        "score": 0.5, "feedback": "You also named the cause", "quiz_id": quiz["id"], "question_id": a.question_id,
        "student_id": c.student_ids[0]}
    # again: each change is logged with the score it replaced
    assert (await set_score(c, quiz, a.id, 0, "Second look"))["correct"] is False
    changes = await audits("QUIZ_SCORE_CHANGE")
    assert [(json.loads(x.old_val)["score"], json.loads(x.new_val)["score"]) for x in changes] == [(0.25, 0.5), (0.5, 0)]
    await quiz_grading.grade_pending()
    assert scores(await answers()) == [0] and len(grader.calls) == 1


@db
async def test_the_lecturer_scores_a_pending_answer_and_the_ai_leaves_it(shino_class, grader):
    c = shino_class
    quiz = await answered(c, "0 x", "1 y")
    first = (await answers())[0]

    async def meanwhile():
        await set_score(c, quiz, first.id, 1, "Right")

    grader.before_reply = meanwhile     # the lecturer scores it while the AI is thinking
    await quiz_grading.grade_pending()
    got = await answers()
    assert [(float(a.score), a.graded_by, a.reason) for a in got] == [(1, "lecturer", None), (1, "ai", "Because.")]
    [entry] = await audits("QUIZ_SCORE_CHANGE")
    assert json.loads(entry.old_val)["score"] is None


@db
async def test_scoring_at_once_logs_a_chain(shino_class, grader):
    c = shino_class
    quiz = await answered(c, "0 x")
    await quiz_grading.grade_pending()
    [a] = await answers()
    values = [0.1, 0.2, 0.3, 0.4]
    await asyncio.gather(*(set_score(c, quiz, a.id, v) for v in values))
    chain = [(json.loads(x.old_val)["score"], json.loads(x.new_val)["score"])
             for x in await audits("QUIZ_SCORE_CHANGE")]
    follows = dict(chain)
    seen, score = [], 0
    while score in follows:
        score = follows[score]
        seen.append(score)
    assert sorted(seen) == values and scores(await answers()) == [seen[-1]]


@db
@pytest.mark.parametrize("body", [
    {"score": 1.1, "feedback": "x"}, {"score": -0.1, "feedback": "x"}, {"score": "1", "feedback": "x"},
    {"score": True, "feedback": "x"}, {"score": None, "feedback": "x"}, {"feedback": "x"}, {"score": 1},
    {"score": 1, "feedback": "  "}, {"score": 1, "feedback": ""}, {"score": 1, "feedback": None},
    {"score": 1, "feedback": "x" * 1001}, {"score": 1, "feedback": "a\x00b"},
    {"score": 1, "feedback": "x", "flagged": True},
])
async def test_a_score_change_is_validated(shino_class, grader, body):
    c = shino_class
    quiz = await answered(c, "0.5 x")
    await quiz_grading.grade_pending()
    [a] = await answers()
    await set_score(c, quiz, a.id, json=body, expect=422)
    assert scores(await answers()) == [0.5] and await audits("QUIZ_SCORE_CHANGE") == []


@db
async def test_only_submitted_short_answers_of_the_quiz_can_be_scored(shino_class):
    c = shino_class
    quiz, running = await three_choices(c), await answered(c, "x", submitted=False)
    await submit(c, quiz["id"])
    choice, short = (await answers())[0], (await answers())[-1]
    await set_score(c, quiz, choice.id, expect=404)         # multiple choice
    await set_score(c, quiz, short.id, expect=404)          # another quiz's
    await set_score(c, running, short.id, expect=404)       # not submitted yet
    await set_score(c, quiz, 99999, expect=404)
    assert scores(await answers()) == [1, 0, None] and await audits("QUIZ_SCORE_CHANGE") == []


@db
async def test_access(shino_class, users, grader):
    c = shino_class
    quiz = await answered(c, "0.5 x")
    await quiz_grading.grade_pending()
    [a] = await answers()
    for uid, role in [(c.other_lecturer_user_id, "lecturer"), (c.student_user_ids[0], "student"),
                      (users["admin"].id, "admin")]:
        await listed(c, quiz, expect=403, uid=uid, role=role)
        await set_score(c, quiz, a.id, expect=403, uid=uid, role=role)
    await listed(c, {"id": 99999}, expect=403)
    await set_score(c, {"id": 99999}, a.id, expect=403)
    async with c.client() as api:
        assert (await api.get(f"{URL}/{quiz['id']}/short-answers")).status_code in (401, 403)
    assert scores(await answers()) == [0.5]


@db
async def test_students_get_no_score_reason_or_feedback(shino_class, grader):
    c = shino_class
    quiz = await answered(c, "0.5 x")
    await quiz_grading.grade_pending()
    [a] = await answers()
    await set_score(c, quiz, a.id, 1, "Wellspotted")
    out = [await read(c, quiz["id"]), await submit(c, quiz["id"]),
           await call(c, "GET", "/student/me/quizzes", 200, uid=c.student_user_ids[0], role="student")]
    assert not any(w in json.dumps(out).lower() for w in ("because.", "wellspotted", "score", "reason", "feedback"))
    await student(c, "GET", quiz["id"], "/short-answers", expect=404)


# ── quiz.graded when the results are released ────────────────────────────────

async def graded_notes() -> list[Notification]:
    async with AsyncSessionLocal() as s:
        return list((await s.execute(select(Notification).where(Notification.event == "quiz.graded")
                                     .order_by(Notification.user_id))).scalars())


async def released_at(quiz):
    async with AsyncSessionLocal() as s:
        return (await s.get(Quiz, quiz["id"])).released_at


@db
async def test_on_close_results_come_out_when_the_lecturer_closes(shino_class, clock):     # noqa: F811
    c = shino_class
    quiz = await three_choices(c, release="on_close")
    await start(c, quiz["id"], i=1)
    await submit(c, quiz["id"], i=1)
    assert await quiz_release.release_due() == 0 and await graded_notes() == []
    await act(c, quiz["id"], "close")
    clock.now += MINUTE
    assert await quiz_release.release_due() == 1
    assert await released_at(quiz) == clock.now
    notes = await graded_notes()
    # those who took it, not the rest of the class
    assert [n.user_id for n in notes] == sorted(c.student_user_ids[:2])
    assert {(n.priority, n.title, n.message, n.link) for n in notes} == {
        ("important", "Quiz results released: Week 5", "Your results for Week 5 are ready.",
         f"/quizzes/{quiz['id']}/result")}     # no marks (NFR-42)
    clock.now += 48 * HOUR
    assert await quiz_release.release_due() == 0 and len(await graded_notes()) == 2     # once


@db
async def test_on_close_results_come_out_at_the_closing_time(shino_class, clock):     # noqa: F811
    c = shino_class
    await three_choices(c, release="on_close", timer_seconds=14400, closes_at=(NOW + HOUR).isoformat())
    clock.now = NOW + HOUR - MINUTE
    assert await quiz_release.release_due() == 0
    clock.now = NOW + HOUR
    assert await quiz_release.release_due() == 0        # the attempt is still to be submitted
    await quiz_timer.sweep()
    assert await quiz_release.release_due() == 1
    assert [n.user_id for n in await graded_notes()] == [c.student_user_ids[0]]


@db
async def test_results_wait_for_the_last_short_answer(shino_class, grader, clock):     # noqa: F811
    c = shino_class
    quiz = await answered(c, "down", release="on_close")
    await answered(c, "1 fine", i=1, quiz=quiz)
    await act(c, quiz["id"], "close")
    await quiz_grading.grade_pending()
    assert await quiz_release.release_due() == 0 and await graded_notes() == []
    waiting = next(a for a in await answers() if a.score is None)
    await set_score(c, quiz, waiting.id)        # the lecturer needn't wait for the AI
    assert await quiz_release.release_due() == 1 and len(await graded_notes()) == 2


@db
async def test_a_manual_release_is_never_automatic(shino_class, clock):     # noqa: F811
    c = shino_class
    quiz = await three_choices(c, release="manual", closes_at=(NOW + HOUR).isoformat())
    await act(c, quiz["id"], "close")
    clock.now = NOW + 2 * HOUR
    assert await quiz_release.release_due() == 0 and await released_at(quiz) is None
    # the lecturer's release (S46) goes through the same function
    async with AsyncSessionLocal() as s:
        row_ = await s.get(Quiz, quiz["id"])
        assert await quiz_release.release(s, row_, clock.now) is True
        assert await quiz_release.release(s, row_, clock.now + HOUR) is False
        assert await graded_notes() == []       # not before the commit
        await s.commit()
        await quiz_release.run_after_commit(s)
    assert len(await graded_notes()) == 1 and await released_at(quiz) == NOW + 2 * HOUR


@db
async def test_games_drafts_and_open_quizzes_are_not_released(shino_class, clock):     # noqa: F811
    c = shino_class
    await create(c, game(c, release="on_close", closes_at=(NOW + HOUR).isoformat()))
    live = await create(c, game(c, release="on_close", closes_at=(NOW + HOUR).isoformat()))
    await insert(question_row(live["id"], approved=True))
    await act(c, live["id"], "publish")
    await act(c, live["id"], "close")
    draft = await create(c)
    await patch(c, draft["id"], {"release": "on_close", "closes_at": (NOW + HOUR).isoformat()})
    await three_choices(c, release="on_close")
    clock.now = NOW + 2 * HOUR
    assert await quiz_release.release_due() == 0


@db
async def test_only_active_enrolled_students_are_notified(shino_class):
    c = shino_class
    quiz = await three_choices(c, release="on_close")
    for i in (1, 2):
        await start(c, quiz["id"], i=i)
        await submit(c, quiz["id"], i=i)
    async with AsyncSessionLocal() as s:
        await s.delete(await s.scalar(select(Enrollment).where(Enrollment.student_id == c.student_ids[0])))
        (await s.get(User, c.student_user_ids[1])).status = "suspended"
        await s.commit()
    await act(c, quiz["id"], "close")
    assert await quiz_release.release_due() == 1
    assert [n.user_id for n in await graded_notes()] == [c.student_user_ids[2]]


@db
async def test_unpublishing_takes_the_release_back(shino_class):
    """Only possible without attempts: nobody had a result."""
    c = shino_class
    quiz = await quiz_with(c, release="on_close")
    await act(c, quiz["id"], "close")
    assert await quiz_release.release_due() == 1 and await graded_notes() == []
    await act(c, quiz["id"], "unpublish")
    assert await released_at(quiz) is None
    await act(c, quiz["id"], "publish")
    await start(c, quiz["id"])
    await act(c, quiz["id"], "close")
    assert await quiz_release.release_due() == 1 and len(await graded_notes()) == 1


@db
async def test_releasing_at_once_notifies_once(shino_class, monkeypatch):
    c = shino_class
    quiz = await three_choices(c, release="on_close")
    await act(c, quiz["id"], "close")
    sent = []

    async def emit(event, user_ids, payload):
        sent.append((event, user_ids, payload))

    monkeypatch.setattr(notify, "emit", emit)
    assert sorted(await asyncio.gather(*(quiz_release.release_due() for _ in range(4)))) == [0, 0, 0, 1]
    assert sent == [("quiz.graded", [c.student_user_ids[0]], {"quiz_id": quiz["id"], "quiz_title": "Week 5"})]


# ── the table ────────────────────────────────────────────────────────────────

@db
@pytest.mark.parametrize("bad", [{"graded_by": "robot"}, {"confidence": Decimal("1.5")}, {"reason": "x" * 501},
                                 {"feedback": "x" * 1001}, {"score": Decimal("1.5")}])
async def test_the_table_refuses_bad_grades(shino_class, bad):
    c = shino_class
    quiz = await answered(c, "x")
    attempt = await row(quiz["id"], c.student_ids[0])
    [question] = await insert(question_row(quiz["id"], 5))
    with pytest.raises(IntegrityError):
        await insert(QuizAnswer(attempt_id=attempt.id, question_id=question, text="y", answered_at=NOW, **bad))


# ── the loops ────────────────────────────────────────────────────────────────

@pytest.mark.parametrize(("module", "loop", "job", "setting"), [
    (quiz_grading, "quiz_grading_loop", "grade_pending", "QUIZ_GRADE_SECONDS"),
    (quiz_release, "quiz_release_loop", "release_due", "QUIZ_RELEASE_SECONDS"),
])
async def test_the_loops_survive_errors_and_can_be_off(monkeypatch, module, loop, job, setting):
    runs, sleeps = [], []

    async def work():
        runs.append(1)
        if len(runs) == 1:
            raise RuntimeError("db down")
        return True

    async def fake_sleep(seconds):
        sleeps.append(seconds)
        if len(sleeps) == 2:
            raise asyncio.CancelledError

    monkeypatch.setattr(module, job, work)
    monkeypatch.setattr(module, "_sleep", fake_sleep)
    monkeypatch.setattr(settings, setting, 3)
    with pytest.raises(asyncio.CancelledError):
        await getattr(module, loop)()
    assert len(runs) == 2 and sleeps == [3, 3]
    monkeypatch.setattr(settings, setting, 0)
    await getattr(module, loop)()
    assert len(runs) == 2


async def test_the_grading_loop_waits_longer_during_an_outage(monkeypatch):
    sleeps, results = [], [False, True]

    async def work():
        return results.pop(0)

    async def fake_sleep(seconds):
        sleeps.append(seconds)
        if len(sleeps) == 2:
            raise asyncio.CancelledError

    monkeypatch.setattr(quiz_grading, "grade_pending", work)
    monkeypatch.setattr(quiz_grading, "_sleep", fake_sleep)
    with pytest.raises(asyncio.CancelledError):
        await quiz_grading.quiz_grading_loop()
    assert sleeps == [settings.QUIZ_GRADE_RETRY_SECONDS, settings.QUIZ_GRADE_SECONDS]


# ── replay of the real LLM's replies (recorded by the live tests) ────────────

@pytest.mark.parametrize(("name", "given", "check"), [
    ("grade_right", cases.RIGHT, cases.check_right),
    ("grade_wrong", cases.WRONG, cases.check_wrong),
    ("grade_mixed", cases.MIXED, cases.check_mixed),
    ("grade_injection", cases.INJECTED, cases.check_injected),
])
async def test_replay(shino_llm, name, given, check):
    shino_llm.use(name)
    check(await cases.run(given))
