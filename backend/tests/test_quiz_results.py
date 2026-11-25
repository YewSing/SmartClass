"""S46: releasing results (FR-618, NFR-41) and the lecturer's results (FR-619, NFR-50)."""
import asyncio
import json

import pytest
from sqlalchemy import select

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.models.class_ import ClassOccurrence, Enrollment
from app.models.quiz import Quiz, QuizAttempt
from app.schemas.quiz import MarksOut, StudentResultOut, StudentResultQuestionOut
from app.services import notify, quiz_attempts, quiz_grading, quiz_release
from tests.test_quiz_attempts import (
    MINUTE,
    MINE,
    SECRETS,
    answers,
    choose,
    ids,
    quiz_ids,
    quiz_with,
    read,
    row,
    save,
    start,
    student,
    submit,
)
from tests.test_quiz_crud import URL, call, create, game, get, insert, question_row
from tests.test_quiz_grading import graded_notes, grader, released_at, set_score  # noqa: F401 (grader: fixture)
from tests.test_quiz_publish import HOUR, NOW, act, audits, cards, clock, published_by_other  # noqa: F401 (fixture)

pytestmark = pytest.mark.db

BOTH, MARKS, ANSWERS, NEITHER = (True, True), (True, False), (False, True), (False, False)
MARK_WORDS = ("because.", "wellspotted")        # the AI's reason, the lecturer's feedback


@pytest.fixture(autouse=True)
def _fixed_time(clock):     # noqa: F811
    """Every test runs on the fake clock."""


async def release(c, quiz, parts=BOTH, expect=200, **kw):
    kw.setdefault("json", {"marks": parts[0], "answers": parts[1]})
    return await call(c, "PUT", f"{URL}/{quiz['id']}/release", expect, **kw)


async def results(c, quiz, expect=200, **kw):
    return await call(c, "GET", f"{URL}/{quiz['id']}/results", expect, **kw)


async def result(c, quiz, expect=200, i=0, **kw):
    kw = {"uid": c.student_user_ids[i], "role": "student", **kw}
    return await call(c, "GET", f"{MINE}/{quiz['id']}/result", expect, **kw)


async def take(c, quiz, *given, i=0, done=True):
    """Student `i` answers the questions in order: an option, a text or None."""
    await start(c, quiz["id"], i=i)
    for qid, answer in zip(await quiz_ids(quiz["id"]), given, strict=True):
        if answer is not None:
            body = {"text": answer} if isinstance(answer, str) else {"option_index": answer}
            await save(c, quiz["id"], qid, body, i=i)
    if done:
        await submit(c, quiz["id"], i=i)


async def taken(c, close=True, **over):
    """A right choice, a wrong one, none, and a half-right short answer the lecturer commented on (right
    option: 2)."""
    quiz = await quiz_with(c, mcq=3, short=1, **over)
    await take(c, quiz, 2, 0, None, "0.25 partly")
    await quiz_grading.grade_pending()
    short = next(a for a in await answers() if a.text)
    await set_score(c, quiz, short.id, 0.5, "Wellspotted")
    if close:
        await act(c, quiz["id"], "close")
    return quiz


# ── what a student sees (FR-618, NFR-41) ─────────────────────────────────────

@pytest.mark.parametrize("parts", [None, NEITHER])
async def test_nothing_is_shown_before_the_release(shino_class, grader, parts):     # noqa: F811
    c = shino_class
    quiz = await taken(c)
    if parts:
        await release(c, quiz, parts)
    assert await result(c, quiz) == {
        "quiz_id": quiz["id"], "title": "Week 5", "course_code": "SH101", "status": "submitted",
        "submitted_at": NOW.isoformat(), "auto_submitted": False, "released_at": None, "marks_released": False,
        "answers_released": False, "marks": None, "questions": None}


async def test_marks_alone_are_the_totals(shino_class, grader):     # noqa: F811
    c = shino_class
    quiz = await taken(c)
    await release(c, quiz, MARKS)
    out = await result(c, quiz)
    assert (out["marks_released"], out["answers_released"], out["released_at"]) == (True, False, NOW.isoformat())
    assert out["marks"] == {"score": 1.5, "max_score": 4, "percent": 37.5, "pending_count": 0}
    assert out["questions"] is None
    seen = json.dumps(out).lower()
    assert not any(w in seen for w in (*SECRETS, *MARK_WORDS, "partly", "question 0?"))


async def test_answers_alone_carry_no_marks(shino_class, grader):     # noqa: F811
    c = shino_class
    quiz = await taken(c)
    await release(c, quiz, ANSWERS)
    out = await result(c, quiz)
    assert (out["marks_released"], out["answers_released"], out["marks"]) == (False, True, None)
    a, b, d, e = await quiz_ids(quiz["id"])
    hidden = {"pending": None, "score": None, "correct": None, "reason": None, "feedback": None}
    choice = {"type": "mcq", "options": [{"index": i, "text": t} for i, t in enumerate("WXYZ")], "answer_text": None,
              "correct_option_index": 2, "suggested_answer": None, "explanation": "Secret explanation", **hidden}
    assert out["questions"] == [
        {"id": a, "number": 1, "text": "Question 0?", "option_index": 2, **choice},
        {"id": b, "number": 2, "text": "Question 1?", "option_index": 0, **choice},
        {"id": d, "number": 3, "text": "Question 2?", "option_index": None, **choice},
        {"id": e, "number": 4, "type": "short", "text": "Why 0?", "options": None, "option_index": None,
         "answer_text": "0.25 partly", "correct_option_index": None, "suggested_answer": "SHA-answer",
         "explanation": "Secret explanation", **hidden}]
    assert not any(w in json.dumps(out).lower() for w in MARK_WORDS)


async def test_marks_and_answers_show_everything(shino_class, grader):     # noqa: F811
    c = shino_class
    quiz = await taken(c)
    await release(c, quiz, BOTH)
    out = await result(c, quiz)
    assert out["marks"]["score"] == 1.5
    assert [(q["score"], q["correct"], q["pending"], q["reason"], q["feedback"]) for q in out["questions"]] == [
        (1, True, False, None, None), (0, False, False, None, None), (0, False, False, None, None),
        (0.5, True, False, "Because.", "Wellspotted")]
    assert [q["correct_option_index"] for q in out["questions"]] == [2, 2, 2, None]
    # what only the lecturer sees stays with them
    assert not any(w in json.dumps(out) for w in ("confidence", "flagged", "graded_by", "topic", "Topicword"))


def test_the_student_schemas_hold_nothing_else():
    """A new field here must be checked against what is released."""
    assert set(MarksOut.model_fields) == {"score", "max_score", "percent", "pending_count"}
    assert set(StudentResultOut.model_fields) == {
        "quiz_id", "title", "course_code", "status", "submitted_at", "auto_submitted", "released_at",
        "marks_released", "answers_released", "marks", "questions"}
    assert set(StudentResultQuestionOut.model_fields) == {
        "id", "number", "type", "text", "options", "option_index", "answer_text", "correct_option_index",
        "suggested_answer", "explanation", "pending", "score", "correct", "reason", "feedback"}


async def test_a_part_that_is_taken_back_is_hidden_again(shino_class, grader, clock):     # noqa: F811
    c = shino_class
    quiz = await taken(c)
    for parts in (BOTH, MARKS, ANSWERS, NEITHER, MARKS, NEITHER, BOTH):
        clock.now += MINUTE
        state = await release(c, quiz, parts)
        out = await result(c, quiz)
        assert (state["marks_released"], state["answers_released"]) == parts
        assert (out["marks_released"], out["answers_released"]) == parts
        assert (out["marks"] is not None, out["questions"] is not None) == parts
        assert out["released_at"] == state["released_at"]


@pytest.mark.parametrize(("marks", "answers_"), [BOTH, MARKS, ANSWERS])
async def test_a_release_on_closing_shows_the_chosen_parts(shino_class, grader, marks, answers_):     # noqa: F811
    c = shino_class
    quiz = await taken(c, release="on_close", release_marks=marks, release_answers=answers_)
    assert (await result(c, quiz))["marks_released"] is False     # closed, but not released yet
    assert await quiz_release.release_due() == 1
    out = await result(c, quiz)
    assert (out["marks"] is not None, out["questions"] is not None) == (marks, answers_)


async def test_the_other_student_endpoints_still_show_nothing(shino_class, grader):     # noqa: F811
    c = shino_class
    quiz = await taken(c)
    await release(c, quiz, BOTH)
    seen = json.dumps([await read(c, quiz["id"]), await submit(c, quiz["id"]), await cards(c)]).lower()
    assert not any(w in seen for w in (*SECRETS, *MARK_WORDS, "score", "correct", "marks"))


async def test_the_result_keeps_the_students_own_order(shino_class, monkeypatch):
    c = shino_class

    class Backwards:
        def shuffle(self, items):
            items.reverse()

    monkeypatch.setattr(quiz_attempts, "_random", Backwards())
    quiz = await quiz_with(c, mcq=2, shuffle=True)
    out = await start(c, quiz["id"])
    order = ids(out)
    assert order == list(reversed(await quiz_ids(quiz["id"])))
    await choose(c, quiz["id"], order[0], 2)
    await act(c, quiz["id"], "close")
    await release(c, quiz, BOTH)
    first, second = (await result(c, quiz))["questions"]
    assert [first["id"], second["id"]] == order and (first["number"], second["number"]) == (1, 2)
    assert [o["index"] for o in first["options"]] == [3, 2, 1, 0]
    assert (first["option_index"], first["correct_option_index"], first["correct"]) == (2, 2, True)
    assert second["correct"] is False


async def test_pending_answers_and_later_scores(shino_class, grader):     # noqa: F811
    """Released by hand before the AI is done: the marks say so, and are read live."""
    c = shino_class
    quiz = await quiz_with(c, mcq=1, short=1)
    await take(c, quiz, 2, "0.25 partly")
    await act(c, quiz["id"], "close")
    await release(c, quiz, BOTH)
    out = await result(c, quiz)
    assert out["marks"] == {"score": 1.0, "max_score": 2, "percent": 50.0, "pending_count": 1}
    short = out["questions"][1]
    assert (short["pending"], short["score"], short["correct"], short["reason"]) == (True, None, None, None)
    await quiz_grading.grade_pending()
    assert (await result(c, quiz))["marks"] == {"score": 1.25, "max_score": 2, "percent": 62.5, "pending_count": 0}
    await set_score(c, quiz, next(a.id for a in await answers() if a.text), 1, "Right after all")
    out = await result(c, quiz)
    assert out["marks"]["percent"] == 100 and out["questions"][1]["feedback"] == "Right after all"


async def test_percentages_are_rounded_half_up(shino_class, grader):     # noqa: F811
    c = shino_class
    quiz = await quiz_with(c, mcq=16)
    await take(c, quiz, 2, *[None] * 15)
    await act(c, quiz["id"], "close")
    await release(c, quiz, MARKS)
    assert (await result(c, quiz))["marks"]["percent"] == 6.3       # 6.25


# ── access (NFR-04) ──────────────────────────────────────────────────────────

async def test_access(shino_class, users, grader):     # noqa: F811
    c = shino_class
    quiz = await taken(c)
    for uid, role in [(c.other_lecturer_user_id, "lecturer"), (c.student_user_ids[0], "student"),
                      (users["admin"].id, "admin")]:
        await results(c, quiz, expect=403, uid=uid, role=role)
        await release(c, quiz, expect=403, uid=uid, role=role)
    assert await released_at(quiz) is None
    await release(c, quiz)
    for uid, role in [(c.outsider_user_id, "student"), (c.lecturer_user_id, "lecturer"), (users["admin"].id, "admin")]:
        await result(c, quiz, expect=403, uid=uid, role=role)
    unknown = {"id": 99999}
    await results(c, unknown, expect=403)
    await release(c, unknown, expect=403)
    for hidden in (unknown, await create(c), await published_by_other(c)):
        await result(c, hidden, expect=403)
    async with c.client() as api:
        for path in (f"{URL}/{quiz['id']}/results", f"{MINE}/{quiz['id']}/result"):
            assert (await api.get(path)).status_code in (401, 403)
    # another lecturer of the course shares its quizzes
    await insert(ClassOccurrence(course_id=c.course_id, type="TUTORIAL", lecturer_id=c.other_lecturer_id))
    other = c.other_lecturer_user_id
    assert (await results(c, quiz, uid=other))["submitted_count"] == 1
    await release(c, quiz, NEITHER, uid=other)
    assert (await audits("QUIZ_RELEASE"))[-1].actor_id == other


async def test_a_student_gets_their_own_result(shino_class, grader):     # noqa: F811
    c = shino_class
    quiz = await quiz_with(c, mcq=2)
    await take(c, quiz, 2, 2)
    await take(c, quiz, 2, 0, i=1)
    await act(c, quiz["id"], "close")
    await release(c, quiz)
    assert [(await result(c, quiz, i=i))["marks"]["score"] for i in range(2)] == [2, 1]
    assert [q["option_index"] for q in (await result(c, quiz, i=1))["questions"]] == [2, 0]
    await result(c, quiz, expect=404, i=2)      # didn't take it: not even the answers
    await student(c, "GET", quiz["id"], "/results", expect=404)


async def test_leaving_the_course_takes_the_result_away(shino_class, grader):     # noqa: F811
    c = shino_class
    quiz = await taken(c)
    await release(c, quiz)
    async with AsyncSessionLocal() as s:
        await s.delete(await s.scalar(select(Enrollment).where(Enrollment.student_id == c.student_ids[0])))
        await s.commit()
    await result(c, quiz, expect=403)
    assert (await results(c, quiz))["submitted_count"] == 1     # their attempt still counts


async def test_games_and_drafts_have_no_results(shino_class):
    c = shino_class
    quiz = await create(c, game(c))
    await insert(question_row(quiz["id"], approved=True))
    await act(c, quiz["id"], "publish")
    await act(c, quiz["id"], "close")
    await release(c, quiz, expect=409)
    await results(c, quiz, expect=409)
    await result(c, quiz, expect=409)
    draft = await create(c)
    await release(c, draft, expect=409)
    await release(c, draft, NEITHER, expect=409)
    assert (await results(c, draft))["can_release"] is False
    assert await audits("QUIZ_RELEASE") == []


# ── the lecturer's release ───────────────────────────────────────────────────

@pytest.mark.parametrize("parts", [BOTH, MARKS, ANSWERS])
async def test_an_open_quiz_cant_be_released(shino_class, grader, clock, parts):     # noqa: F811
    c = shino_class
    quiz = await taken(c, close=False, opens_at=NOW.isoformat(), closes_at=(NOW + HOUR).isoformat())
    assert (await results(c, quiz))["can_release"] is False
    assert "Close the quiz" in (await release(c, quiz, parts, expect=409))["detail"]
    clock.now = NOW + HOUR - MINUTE
    await release(c, quiz, parts, expect=409)
    assert await released_at(quiz) is None and await audits("QUIZ_RELEASE") == []
    clock.now = NOW + HOUR      # over by its closing time, without closing it by hand
    assert (await results(c, quiz))["can_release"] is True
    await release(c, quiz, parts)
    assert await released_at(quiz) == clock.now


async def test_a_quiz_that_hasnt_opened_cant_be_released(shino_class):
    c = shino_class
    quiz = await quiz_with(c, opens_at=(NOW + HOUR).isoformat())
    await release(c, quiz, expect=409)


async def test_releasing_submits_the_attempts_whose_time_is_up(shino_class, clock):     # noqa: F811
    """The sweep may not have come by yet."""
    c = shino_class
    quiz = await quiz_with(c, mcq=1, timer_seconds=14400, closes_at=(NOW + HOUR).isoformat())
    await take(c, quiz, 2, done=False)
    clock.now = NOW + HOUR
    await release(c, quiz)
    saved = await row(quiz["id"], c.student_ids[0])
    assert (saved.status, saved.submitted_at, saved.auto_submitted) == ("submitted", NOW + HOUR, True)
    assert (await result(c, quiz))["marks"]["percent"] == 100
    assert [n.user_id for n in await graded_notes()] == [c.student_user_ids[0]]


async def test_the_release_notifies_once_and_is_audited(shino_class, grader, clock):     # noqa: F811
    c = shino_class
    quiz = await taken(c)
    out = await release(c, quiz, MARKS)
    assert out == {"release": "manual", "marks_released": True, "answers_released": False,
                   "released_at": NOW.isoformat(), "can_release": True}
    assert (await get(c, quiz["id"]))["released_at"] == NOW.isoformat()
    [note] = await graded_notes()
    assert note.user_id == c.student_user_ids[0] and not any(ch.isdigit() for ch in note.message.replace("Week 5", ""))
    clock.now += MINUTE
    assert await release(c, quiz, MARKS) == out          # again: nothing happens
    assert (await release(c, quiz, BOTH))["released_at"] == NOW.isoformat()
    await release(c, quiz, NEITHER)
    await release(c, quiz, NEITHER)
    assert len(await graded_notes()) == 1
    log = await audits("QUIZ_RELEASE")
    assert {(x.actor_id, x.target_type, x.target_id) for x in log} == {
        (c.lecturer_user_id, "m6_quiz", str(quiz["id"]))}
    changes = [(json.loads(x.old_val), json.loads(x.new_val)) for x in log]
    assert [((old["marks"], old["answers"]), (new["marks"], new["answers"])) for old, new in changes] == [
        (NEITHER, MARKS), (MARKS, BOTH), (BOTH, NEITHER)]
    assert changes[0][1] == {"marks": True, "answers": False, "release": "manual", "title": "Week 5"}


async def test_neither_stops_a_release_on_closing(shino_class, grader):     # noqa: F811
    c = shino_class
    quiz = await taken(c, close=False, release="on_close")
    out = await release(c, quiz, NEITHER)       # allowed while the quiz is open
    assert (out["release"], out["released_at"]) == ("manual", None)
    await act(c, quiz["id"], "close")
    assert await quiz_release.release_due() == 0 and await graded_notes() == []
    assert len(await audits("QUIZ_RELEASE")) == 1
    await release(c, quiz, MARKS)
    assert (await result(c, quiz))["marks"]["score"] == 1.5


async def test_results_taken_back_stay_back(shino_class, grader):     # noqa: F811
    c = shino_class
    quiz = await taken(c, release="on_close")
    assert await quiz_release.release_due() == 1
    await release(c, quiz, NEITHER)
    assert await quiz_release.release_due() == 0
    assert (await result(c, quiz))["marks"] is None


async def test_releasing_at_once_notifies_once(shino_class, grader, monkeypatch):     # noqa: F811
    c = shino_class
    quiz = await taken(c, release="on_close")
    sent = []

    async def emit(event, user_ids, payload):
        sent.append((event, user_ids))

    monkeypatch.setattr(notify, "emit", emit)
    await asyncio.gather(*(release(c, quiz) for _ in range(3)), quiz_release.release_due())
    assert sent == [("quiz.graded", [c.student_user_ids[0]])] and len(await audits("QUIZ_RELEASE")) <= 1


@pytest.mark.parametrize("body", [
    {}, {"marks": True}, {"answers": True}, {"marks": "yes", "answers": True}, {"marks": 1, "answers": 0},
    {"marks": None, "answers": True}, {"marks": True, "answers": True, "ranks": True},
])
async def test_the_release_is_validated(shino_class, grader, body):     # noqa: F811
    c = shino_class
    quiz = await taken(c)
    await release(c, quiz, json=body, expect=422)
    assert await released_at(quiz) is None


# ── the lecturer's results (FR-619) ──────────────────────────────────────────

async def test_results_against_hand_worked_values(shino_class, grader, clock):     # noqa: F811
    c = shino_class
    quiz = await quiz_with(c, mcq=2, short=1)
    a, b, d = await quiz_ids(quiz["id"])
    await take(c, quiz, 2, 0, "1 full")             # 2 of 3
    await take(c, quiz, 2, 2, "0.4 bit", i=1)       # 2.4 of 3
    await take(c, quiz, None, None, None, i=2)      # 0
    await take(c, quiz, 1, 1, "1 running", i=3, done=False)
    await quiz_grading.grade_pending()
    out = await results(c, quiz)
    assert (out["quiz_id"], out["title"], out["status"], out["question_count"]) == (
        quiz["id"], "Week 5", "published", 3)
    assert (out["release"], out["marks_released"], out["answers_released"], out["released_at"],
            out["can_release"]) == ("manual", False, False, None, False)
    assert {k: out[k] for k in out if k.endswith("_count")} == {
        "question_count": 3, "enrolled_count": 4, "not_started_count": 0, "in_progress_count": 1,
        "submitted_count": 3, "graded_count": 3, "pending_answer_count": 0}
    # (2 + 2.4 + 0) / 3 = 1.467 marks; 4.4 of 9 = 48.9 %
    assert (out["average_score"], out["average_percent"], out["highest_score"], out["lowest_score"]) == (
        1.467, 48.9, 2.4, 0)
    assert [x["count"] for x in out["distribution"]] == [1, 0, 0, 0, 0, 0, 1, 0, 1, 0]      # 0, 66.7, 80
    assert (out["distribution"][0], out["distribution"][9]["to_percent"]) == (
        {"from_percent": 0, "to_percent": 10, "count": 1}, 100)
    assert out["questions"] == [
        {"id": a, "number": 1, "type": "mcq", "text": "Question 0?", "topic": "Topicword", "correct_count": 2,
         "incorrect_count": 0, "unanswered_count": 1, "pending_count": 0, "correct_rate": 0.667,
         "average_score": 0.667, "option_counts": [0, 0, 2, 0]},
        {"id": b, "number": 2, "type": "mcq", "text": "Question 1?", "topic": "Topicword", "correct_count": 1,
         "incorrect_count": 1, "unanswered_count": 1, "pending_count": 0, "correct_rate": 0.333,
         "average_score": 0.333, "option_counts": [1, 0, 1, 0]},
        {"id": d, "number": 3, "type": "short", "text": "Why 0?", "topic": "Topicword", "correct_count": 1,
         "incorrect_count": 1, "unanswered_count": 1, "pending_count": 0, "correct_rate": 0.333,
         "average_score": 0.467, "option_counts": None}]
    assert out["most_missed"] == [b, d, a]
    assert [(s["student_id"], s["status"], (s["marks"] or {}).get("percent")) for s in out["submissions"]] == [
        (c.student_ids[0], "submitted", 66.7), (c.student_ids[1], "submitted", 80),
        (c.student_ids[2], "submitted", 0), (c.student_ids[3], "in_progress", None)]
    assert out["submissions"][0] == {
        "student_id": c.student_ids[0], "student_name": "Shino Student 1", "matric_no": "SH000001",
        "status": "submitted", "started_at": NOW.isoformat(), "submitted_at": NOW.isoformat(),
        "auto_submitted": False, "marks": {"score": 2.0, "max_score": 3, "percent": 66.7, "pending_count": 0}}


async def test_pending_answers_are_left_out_of_the_numbers(shino_class, grader):     # noqa: F811
    c = shino_class
    quiz = await quiz_with(c, mcq=1, short=1)
    await take(c, quiz, 0, "0.5 half")
    await quiz_grading.grade_pending()
    await take(c, quiz, 2, "down", i=1)
    out = await results(c, quiz)
    assert (out["submitted_count"], out["graded_count"], out["pending_answer_count"]) == (2, 1, 1)
    assert (out["average_score"], out["average_percent"], out["highest_score"]) == (0.5, 25, 0.5)
    assert sum(x["count"] for x in out["distribution"]) == 1 and out["distribution"][2]["count"] == 1
    choice, short = out["questions"]
    assert (choice["correct_rate"], choice["average_score"]) == (0.5, 0.5)
    assert (short["correct_count"], short["incorrect_count"], short["pending_count"], short["correct_rate"],
            short["average_score"]) == (1, 0, 1, 1, 0.5)
    assert out["most_missed"] == [choice["id"]]
    assert [s["marks"]["pending_count"] for s in out["submissions"]] == [0, 1]
    # the lecturer's score counts at once
    await set_score(c, quiz, next(x.id for x in await answers() if x.text == "down"), 1, "Yes")
    out = await results(c, quiz)
    assert (out["graded_count"], out["average_score"], out["distribution"][9]["count"]) == (2, 1.25, 1)


async def test_everything_pending_has_no_rate(shino_class, grader):     # noqa: F811
    c = shino_class
    quiz = await quiz_with(c, mcq=0, short=1)
    await take(c, quiz, "down")
    out = await results(c, quiz)
    assert (out["graded_count"], out["average_score"]) == (0, None)
    assert (out["questions"][0]["correct_rate"], out["questions"][0]["average_score"], out["most_missed"]) == (
        None, None, [])


async def test_results_without_submissions(shino_class):
    c = shino_class
    quiz = await quiz_with(c, mcq=1)
    out = await results(c, quiz)
    assert (out["enrolled_count"], out["not_started_count"], out["submitted_count"], out["graded_count"]) == (4, 4, 0, 0)
    assert [out[k] for k in ("average_score", "average_percent", "highest_score", "lowest_score")] == [None] * 4
    assert (out["submissions"], out["most_missed"], out["questions"][0]["correct_rate"]) == ([], [], None)
    assert [x["count"] for x in out["distribution"]] == [0] * 10
    await start(c, quiz["id"])
    out = await results(c, quiz)
    assert (out["not_started_count"], out["in_progress_count"], out["average_score"]) == (3, 1, None)


async def test_most_missed_is_the_worst_first_and_limited(shino_class, monkeypatch):
    c = shino_class
    quiz = await quiz_with(c, mcq=4)
    a, b, d, e = await quiz_ids(quiz["id"])
    await take(c, quiz, 2, 0, 0, None)
    await take(c, quiz, 2, 2, 0, 2, i=1)
    await take(c, quiz, 2, 2, 1, 1, i=2)
    out = await results(c, quiz)
    assert out["most_missed"] == [d, e, b]          # rates 0, 1/3, 2/3; everybody got `a` right
    monkeypatch.setattr(settings, "QUIZ_MOST_MISSED", 2)
    assert (await results(c, quiz))["most_missed"] == [d, e]


async def test_only_this_quiz_and_its_published_questions_count(shino_class):
    c = shino_class
    quiz = await create(c)
    [asked, _] = await insert(question_row(quiz["id"], 0, approved=True), question_row(quiz["id"], 1, text="Not ready"))
    await act(c, quiz["id"], "publish")
    other = await quiz_with(c, mcq=1)
    await take(c, quiz, 1)
    await take(c, other, 0)
    out = await results(c, quiz)
    assert [q["id"] for q in out["questions"]] == [asked]
    assert (out["question_count"], out["submitted_count"], len(out["submissions"])) == (1, 1, 1)


async def test_two_classes_of_the_course_count_a_student_once(shino_class):
    c = shino_class
    quiz = await quiz_with(c, mcq=1)
    [tutorial] = await insert(ClassOccurrence(course_id=c.course_id, type="TUTORIAL", lecturer_id=c.lecturer_id))
    await insert(Enrollment(student_id=c.student_ids[0], occurrence_id=tutorial))
    await take(c, quiz, 2)
    out = await results(c, quiz)
    assert (out["enrolled_count"], out["not_started_count"], len(out["submissions"])) == (4, 3, 1)


async def test_reading_results_changes_nothing(shino_class, grader):     # noqa: F811
    c = shino_class
    quiz = await taken(c, close=False)
    before = await get(c, quiz["id"])
    await results(c, quiz)
    assert await get(c, quiz["id"]) == before and await audits("QUIZ_RELEASE") == []
    async with AsyncSessionLocal() as s:
        assert (await s.get(Quiz, quiz["id"])).released_at is None
        assert len((await s.execute(select(QuizAttempt))).scalars().all()) == 1
