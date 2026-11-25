"""S47: read interfaces for M8 (FR-609, FR-620) and M7 (FR-621)."""
import inspect
from dataclasses import FrozenInstanceError, fields
from datetime import date, timedelta

import pytest
from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.models.class_ import ClassOccurrence, Enrollment
from app.models.quiz import Quiz, QuizAnswer, QuizAttempt, QuizQuestion
from app.services import quiz_grading, quiz_read
from tests.test_quiz_attempts import MINUTE, SEC, answers, choose, next_, quiz_ids, quiz_with, row, start, submit
from tests.test_quiz_crud import create, game, graded, insert, question_row
from tests.test_quiz_grading import grader, set_score  # noqa: F401 (grader: fixture)
from tests.test_quiz_publish import HOUR, NOW, act, clock  # noqa: F401 (clock: fixture)
from tests.test_quiz_results import ANSWERS, BOTH, MARKS, NEITHER, release, result, results, take, taken

pytestmark = pytest.mark.db

DAY = timedelta(days=1)
TODAY = NOW.date()
BOTH_AUDIENCES = ("student", "lecturer")


@pytest.fixture(autouse=True)
def _fixed_time(clock):     # noqa: F811
    """Every test runs on the fake clock."""


async def ask(name, *args, **kw):
    """Call a function of `quiz_read` in a session of its own."""
    async with AsyncSessionLocal() as db:
        out = await getattr(quiz_read, name)(db, *args, **kw)
        assert not db.new and not db.dirty and not db.deleted
        return out


async def active(c, i=0, course_id=None) -> bool:
    return await ask("has_active_graded_attempt", c.student_ids[i], course_id or c.course_id)


async def game_with(c, *topics, **over) -> dict:
    """A published game with one question per topic (right option: 1)."""
    quiz = await create(c, game(c, **over))
    await insert(*(question_row(quiz["id"], i, text=f"Game {i}?", topic=t, approved=True)
                   for i, t in enumerate(topics)))
    return await act(c, quiz["id"], "publish")


async def play(quiz, student_id, *given, at=NOW, status="submitted"):
    """What the live game (S48) stores: the student's options by question; None = not answered."""
    [attempt_id] = await insert(QuizAttempt(quiz_id=quiz["id"], student_id=student_id, status=status, started_at=at,
                                            submitted_at=at if status == "submitted" else None))
    await insert(*(QuizAnswer(attempt_id=attempt_id, question_id=qid, option_index=option, correct=option == 1,
                              score=int(option == 1), graded_by="auto", answered_at=at)
                   for qid, option in zip(await quiz_ids(quiz["id"]), given, strict=True) if option is not None))


async def set_topics(quiz, *topics):
    async with AsyncSessionLocal() as db:
        for qid, topic in zip(await quiz_ids(quiz["id"]), topics, strict=True):
            (await db.get(QuizQuestion, qid)).topic = topic
        await db.commit()


async def leave(student_id):
    async with AsyncSessionLocal() as db:
        await db.delete(await db.scalar(select(Enrollment).where(Enrollment.student_id == student_id)))
        await db.commit()


async def tutorial_for(c, student_id):
    """A second class of the course, with the student in it too."""
    [occ] = await insert(ClassOccurrence(course_id=c.course_id, type="TUTORIAL", lecturer_id=c.lecturer_id))
    await insert(Enrollment(student_id=student_id, occurrence_id=occ))


# ── has_active_graded_attempt (FR-609) ───────────────────────────────────────

async def test_active_while_a_graded_attempt_runs(shino_class):
    c = shino_class
    quiz = await quiz_with(c)
    assert await active(c) is False
    await start(c, quiz["id"])
    assert await active(c) is True
    assert await active(c, i=1) is False                        # another student
    assert await active(c, course_id=c.course_id + 999) is False    # an unknown course
    await submit(c, quiz["id"])
    assert await active(c) is False


async def test_active_is_per_course(shino_class):
    c = shino_class
    quiz = await quiz_with(c)
    await start(c, quiz["id"])
    async with AsyncSessionLocal() as db:
        other = (await db.get(ClassOccurrence, c.other_occurrence_id)).course_id
    await insert(Enrollment(student_id=c.student_ids[0], occurrence_id=c.other_occurrence_id))
    assert await active(c) is True and await active(c, course_id=other) is False


async def test_not_active_at_the_deadline_even_before_the_sweep(shino_class, clock):     # noqa: F811
    c = shino_class
    quiz = await quiz_with(c, timer_seconds=600)
    await start(c, quiz["id"])
    clock.now = NOW + 10 * MINUTE - SEC
    assert await active(c) is True
    clock.now = NOW + 10 * MINUTE
    assert await active(c) is False
    assert (await row(quiz["id"], c.student_ids[0])).status == "in_progress"       # it only reads


async def test_active_ends_with_the_quizs_closing_time(shino_class, clock):     # noqa: F811
    c = shino_class
    quiz = await quiz_with(c, timer_seconds=600, closes_at=(NOW + 5 * MINUTE).isoformat())
    await start(c, quiz["id"])
    clock.now = NOW + 5 * MINUTE - SEC
    assert await active(c) is True
    clock.now = NOW + 5 * MINUTE
    assert await active(c) is False


async def test_active_with_a_timer_per_question(shino_class, clock):     # noqa: F811
    c = shino_class
    quiz = await quiz_with(c, mcq=3, timer_mode="question", timer_seconds=60)
    await start(c, quiz["id"])
    clock.now = NOW + 2 * MINUTE + 30 * SEC     # in the last question, untouched so far
    assert await active(c) is True
    clock.now = NOW + 3 * MINUTE
    assert await active(c) is False
    # moving on early brings the end forward
    await start(c, quiz["id"], i=1)
    await next_(c, quiz["id"], (await quiz_ids(quiz["id"]))[0], i=1)
    clock.now += 2 * MINUTE - SEC
    assert await active(c, i=1) is True
    clock.now += SEC
    assert await active(c, i=1) is False


async def test_closing_the_quiz_ends_it(shino_class):
    c = shino_class
    quiz = await quiz_with(c)
    await start(c, quiz["id"])
    await act(c, quiz["id"], "close")
    assert await active(c) is False


async def test_a_running_game_is_not_active(shino_class):
    c = shino_class
    quiz = await game_with(c, "Sums")
    await play(quiz, c.student_ids[0], None, status="in_progress")
    assert await active(c) is False


async def test_any_running_attempt_counts(shino_class):
    """One quiz done, another one running."""
    c = shino_class
    done, running = await quiz_with(c), await quiz_with(c)
    await start(c, running["id"])
    await start(c, done["id"])
    await submit(c, done["id"])
    assert await active(c) is True


# ── answers (FR-620) ─────────────────────────────────────────────────────────

async def test_answers_carry_topic_source_and_type(shino_class, grader):     # noqa: F811
    c = shino_class
    quiz = await taken(c)
    a, b, d, e = await quiz_ids(quiz["id"])
    got = await ask("student_answers", c.student_ids[0], audience="lecturer")
    common = {
        "student_id": c.student_ids[0], "matric_no": "SH000001", "name": "Shino Student 1", "course_id": c.course_id,
        "course_code": "SH101", "quiz_id": quiz["id"], "quiz_title": "Week 5", "quiz_type": "graded",
        "submitted_at": NOW, "topic": "Topicword", "source_file": "filename.pdf", "source_type": "slide",
        "source_page": 3, "origin": "from_material", "explanation": "Secret explanation", "pending": False}
    choice = {**common, "question_type": "mcq", "options": ("W", "X", "Y", "Z"), "answer_text": None,
              "correct_option_index": 2, "suggested_answer": None}
    assert [vars(x) for x in got] == [
        {**choice, "question_id": a, "question_number": 1, "question_text": "Question 0?", "answered": True,
         "option_index": 2, "correct": True, "score": 1.0},
        {**choice, "question_id": b, "question_number": 2, "question_text": "Question 1?", "answered": True,
         "option_index": 0, "correct": False, "score": 0.0},
        {**choice, "question_id": d, "question_number": 3, "question_text": "Question 2?", "answered": False,
         "option_index": None, "correct": False, "score": 0.0},
        {**common, "question_id": e, "question_number": 4, "question_type": "short", "question_text": "Why 0?",
         "options": None, "answered": True, "option_index": None, "answer_text": "0.25 partly",
         "correct_option_index": None, "suggested_answer": "SHA-answer", "correct": True, "score": 0.5}]
    assert await ask("course_answers", c.course_id) == got
    with pytest.raises(FrozenInstanceError):
        got[0].correct = False


async def test_game_answers_have_only_answered_questions(shino_class):
    c = shino_class
    quiz = await game_with(c, "A", "B", "C")
    await play(quiz, c.student_ids[0], None, 1, 0)      # a late joiner
    for audience in BOTH_AUDIENCES:
        got = await ask("student_answers", c.student_ids[0], audience=audience)
        assert [(x.quiz_type, x.question_number, x.topic, x.answered, x.correct, x.score) for x in got] == [
            ("game", 2, "B", True, True, 1.0), ("game", 3, "C", True, False, 0.0)]


@pytest.mark.parametrize("audience", BOTH_AUDIENCES)
async def test_nothing_of_a_running_attempt(shino_class, audience):
    c = shino_class
    quiz, played = await quiz_with(c, mcq=1), await game_with(c, "A")
    await take(c, quiz, 2, done=False)
    await play(played, c.student_ids[0], 1, status="in_progress")
    sid = c.student_ids[0]
    for name in ("student_answers", "student_graded_scores", "student_topic_results"):
        assert await ask(name, sid, audience=audience) == []
    for name in ("course_answers", "course_graded_scores", "course_topic_results", "course_game_participation"):
        assert await ask(name, c.course_id) == []
    assert await ask("student_game_participation", sid) == []


async def test_a_pending_answer_is_neither_right_nor_wrong(shino_class, grader):     # noqa: F811
    c = shino_class
    quiz = await quiz_with(c, mcq=0, short=2)
    await take(c, quiz, "1 full", None)
    [waiting, empty] = await ask("course_answers", c.course_id)
    assert (waiting.answered, waiting.pending, waiting.correct, waiting.score) == (True, True, None, None)
    assert (empty.answered, empty.pending, empty.correct, empty.score) == (False, False, False, 0.0)
    await quiz_grading.grade_pending()
    [graded_, _] = await ask("course_answers", c.course_id)
    assert (graded_.pending, graded_.correct, graded_.score) == (False, True, 1.0)
    # the lecturer's score counts
    [answer] = await answers()
    await set_score(c, quiz, answer.id, 0.25)
    [changed, _] = await ask("course_answers", c.course_id)
    assert (changed.correct, changed.score) == (False, 0.25)


async def test_unapproved_questions_are_left_out(shino_class):
    c = shino_class
    quiz = await create(c, graded(c))
    await insert(question_row(quiz["id"], 0, text="Not ready"), question_row(quiz["id"], 1, approved=True))
    await act(c, quiz["id"], "publish")
    await take(c, quiz, 1)
    [only] = await ask("course_answers", c.course_id)
    assert (only.question_text, only.question_number) == ("2+2?", 1)


async def test_the_questions_keep_the_quizs_own_order_when_shuffled(shino_class):
    c = shino_class
    quiz = await quiz_with(c, mcq=8, shuffle=True)
    for i in range(2):
        await start(c, quiz["id"], i=i)
        await submit(c, quiz["id"], i=i)
    got = await ask("course_answers", c.course_id)
    assert [x.question_id for x in got] == 2 * await quiz_ids(quiz["id"])
    assert [x.question_number for x in got] == 2 * list(range(1, 9))


async def test_choices_are_the_questions_own_options_when_shuffled(shino_class):
    c = shino_class
    quiz = await quiz_with(c, mcq=1, shuffle=True)
    await start(c, quiz["id"])
    await choose(c, quiz["id"], (await quiz_ids(quiz["id"]))[0], 2)
    await submit(c, quiz["id"])
    [x] = await ask("course_answers", c.course_id)
    assert (x.options[x.option_index], x.correct) == ("Y", True)


async def test_whose_answers(shino_class):
    c = shino_class
    quiz = await quiz_with(c, mcq=1)
    await take(c, quiz, 0, i=1)
    await take(c, quiz, 2, i=0)
    await tutorial_for(c, c.student_ids[0])     # in two classes of the course: still one row
    got = await ask("course_answers", c.course_id)
    assert [(x.matric_no, x.correct) for x in got] == [("SH000001", True), ("SH000002", False)]
    mine = await ask("student_answers", c.student_ids[1], audience="lecturer")
    assert [(x.matric_no, x.correct) for x in mine] == [("SH000002", False)]
    assert await ask("student_answers", c.outsider_student_id, audience="lecturer") == []
    assert await ask("student_answers", 999999, audience="lecturer") == []
    assert await ask("course_answers", 999999) == []


async def test_a_student_who_left_the_course_is_left_out(shino_class):
    c = shino_class
    sid = c.student_ids[0]
    quiz, played = await quiz_with(c, mcq=1), await game_with(c, "A")
    await take(c, quiz, 2)
    await play(played, sid, 1)
    await leave(sid)
    for name in ("course_answers", "course_graded_scores", "course_topic_results"):
        assert await ask(name, c.course_id) == []
    for name in ("student_answers", "student_graded_scores", "student_topic_results"):
        assert await ask(name, sid, audience="lecturer") == []
    assert await ask("student_game_participation", sid) == []
    assert [(x.matric_no, x.played, x.questions_asked) for x in await ask("course_game_participation", c.course_id)
            ] == [(f"SH00000{i}", False, 1) for i in (2, 3, 4)]


async def other_course_quiz(c, i=0):
    """The student also takes a quiz of the other course, which they enrol in."""
    async with AsyncSessionLocal() as db:
        other = (await db.get(ClassOccurrence, c.other_occurrence_id)).course_id
    await insert(Enrollment(student_id=c.student_ids[i], occurrence_id=c.other_occurrence_id))
    quiz = await create(c, {"course_id": other, "title": "Other", "type": "graded"}, uid=c.other_lecturer_user_id)
    await insert(question_row(quiz["id"], approved=True))
    await act(c, quiz["id"], "publish", uid=c.other_lecturer_user_id)
    await take(c, quiz, 1, i=i)
    return other


async def test_the_course_filter(shino_class):
    c = shino_class
    await take(c, await quiz_with(c, mcq=1), 2)
    other = await other_course_quiz(c)
    sid = c.student_ids[0]
    for name in ("student_answers", "student_graded_scores", "student_topic_results"):
        codes = [x.course_code for x in await ask(name, sid, audience="lecturer")]
        assert sorted(codes) == ["SH101", "SH202"]
        assert [x.course_code for x in await ask(name, sid, other, audience="lecturer")] == ["SH202"]
    for name in ("course_answers", "course_graded_scores", "course_topic_results"):
        assert [x.course_code for x in await ask(name, other)] == ["SH202"]


# ── what the student may see (FR-618, NFR-41) ────────────────────────────────

@pytest.mark.parametrize(("parts", "score", "full"), [
    (None, False, False), (NEITHER, False, False), (MARKS, True, False), (ANSWERS, False, False), (BOTH, True, True)])
async def test_the_student_audience_gets_what_is_released(shino_class, grader, parts, score, full):     # noqa: F811
    c = shino_class
    quiz = await taken(c)
    if parts:
        await release(c, quiz, parts)
    sid = c.student_ids[0]
    assert len(await ask("student_graded_scores", sid, audience="student")) == score
    assert len(await ask("student_answers", sid, audience="student")) == 4 * full
    assert len(await ask("student_topic_results", sid, audience="student")) == full
    # the lecturer's view never depends on it
    assert len(await ask("student_graded_scores", sid, audience="lecturer")) == 1
    assert len(await ask("student_answers", sid, audience="lecturer")) == 4
    assert len(await ask("student_topic_results", sid, audience="lecturer")) == 1


async def test_results_taken_back_are_hidden_again(shino_class, grader):     # noqa: F811
    c = shino_class
    quiz = await taken(c)
    await release(c, quiz, BOTH)
    await release(c, quiz, NEITHER)
    for name in ("student_graded_scores", "student_answers", "student_topic_results"):
        assert await ask(name, c.student_ids[0], audience="student") == []


async def test_each_quiz_is_released_on_its_own(shino_class, grader):     # noqa: F811
    c = shino_class
    out, hidden = await quiz_with(c, mcq=1, title="Out"), await quiz_with(c, mcq=1, title="Hidden")
    for quiz in (out, hidden):
        await take(c, quiz, 2)
        await act(c, quiz["id"], "close")
    await release(c, out)
    sid = c.student_ids[0]
    for name in ("student_graded_scores", "student_answers"):
        assert [x.quiz_title for x in await ask(name, sid, audience="student")] == ["Out"]


@pytest.mark.parametrize("name", ["student_answers", "student_graded_scores", "student_topic_results"])
async def test_the_audience_must_be_chosen(shino_class, name):
    """No default: a caller can't show a student unreleased results by forgetting about it."""
    with pytest.raises(TypeError):
        await ask(name, shino_class.student_ids[0])
    with pytest.raises(ValueError, match="audience"):
        await ask(name, shino_class.student_ids[0], audience="admin")
    with pytest.raises(TypeError):
        await ask(name, shino_class.student_ids[0], None, "lecturer")
    assert inspect.signature(getattr(quiz_read, name)).parameters["audience"].default is inspect.Parameter.empty


# ── graded scores with dates (FR-621) ────────────────────────────────────────

async def test_graded_scores(shino_class, grader, clock):     # noqa: F811
    c = shino_class
    quiz = await taken(c)
    [x] = await ask("student_graded_scores", c.student_ids[0], audience="lecturer")
    assert vars(x) == {
        "student_id": c.student_ids[0], "matric_no": "SH000001", "name": "Shino Student 1", "course_id": c.course_id,
        "course_code": "SH101", "quiz_id": quiz["id"], "quiz_title": "Week 5", "date": TODAY, "submitted_at": NOW,
        "score": 1.5, "max_score": 4, "percent": 37.5, "pending_count": 0}
    assert await ask("course_graded_scores", c.course_id) == [x]
    # the same numbers as the results screens
    await release(c, quiz, BOTH)
    mine = (await result(c, quiz))["marks"]
    assert mine == {"score": x.score, "max_score": x.max_score, "percent": x.percent, "pending_count": 0}
    assert (await results(c, quiz))["submissions"][0]["marks"] == mine


async def test_a_score_that_is_not_complete_says_so(shino_class, grader):     # noqa: F811
    c = shino_class
    quiz = await quiz_with(c, mcq=1, short=1)
    await take(c, quiz, 2, "0.5 half")
    [x] = await ask("course_graded_scores", c.course_id)
    assert (x.score, x.pending_count) == (1.0, 1)
    await quiz_grading.grade_pending()
    [x] = await ask("course_graded_scores", c.course_id)
    assert (x.score, x.percent, x.pending_count) == (1.5, 75.0, 0)


async def test_nothing_answered_scores_zero(shino_class):
    c = shino_class
    await take(c, await quiz_with(c, mcq=2), None, None)
    [x] = await ask("course_graded_scores", c.course_id)
    assert (x.score, x.max_score, x.percent) == (0.0, 2, 0.0)


async def test_scores_are_in_the_order_they_were_submitted(shino_class, clock):     # noqa: F811
    c = shino_class
    first, second = await quiz_with(c, mcq=1, title="First"), await quiz_with(c, mcq=1, title="Second")
    await take(c, second, 2)
    await take(c, first, 2, i=1)
    clock.now += DAY
    await take(c, first, 0)
    got = await ask("course_graded_scores", c.course_id)
    assert [(x.matric_no, x.quiz_title, x.date, x.percent) for x in got] == [
        ("SH000001", "Second", TODAY, 100.0), ("SH000001", "First", TODAY + DAY, 0.0),
        ("SH000002", "First", TODAY, 100.0)]
    mine = await ask("student_graded_scores", c.student_ids[0], audience="lecturer")
    assert [x.quiz_title for x in mine] == ["Second", "First"]


async def test_games_have_no_graded_score(shino_class):
    c = shino_class
    await play(await game_with(c, "A"), c.student_ids[0], 1)
    assert await ask("course_graded_scores", c.course_id) == []
    for audience in BOTH_AUDIENCES:
        assert await ask("student_graded_scores", c.student_ids[0], audience=audience) == []


# ── date ranges ──────────────────────────────────────────────────────────────

async def test_date_ranges_are_inclusive(shino_class, clock):     # noqa: F811
    c = shino_class
    sid = c.student_ids[0]
    clock.now = NOW.replace(hour=23, minute=59)
    await take(c, await quiz_with(c, mcq=1), 2)
    await play(await game_with(c, "A"), sid, 1, at=clock.now)
    for lo, hi, n in [(None, None, 1), (TODAY, TODAY, 1), (TODAY, None, 1), (None, TODAY, 1), (TODAY + DAY, None, 0),
                      (None, TODAY - DAY, 0)]:
        days = {"from_date": lo, "to_date": hi}
        assert len(await ask("student_answers", sid, audience="lecturer", **days)) == 2 * n
        assert len(await ask("course_answers", c.course_id, lo, hi)) == 2 * n
        assert len(await ask("student_graded_scores", sid, audience="lecturer", **days)) == n
        assert len(await ask("course_graded_scores", c.course_id, lo, hi)) == n
        assert len(await ask("student_topic_results", sid, audience="lecturer", **days)) == 2 * n
        assert len(await ask("course_topic_results", c.course_id, lo, hi)) == 2 * n
        assert len(await ask("student_game_participation", sid, **days)) == n
        assert len(await ask("course_game_participation", c.course_id, lo, hi)) == 4 * n


async def test_a_range_the_wrong_way_round(shino_class):
    days = {"from_date": date(2026, 12, 2), "to_date": date(2026, 12, 1)}
    sid, cid = shino_class.student_ids[0], shino_class.course_id
    for name in ("student_answers", "student_graded_scores", "student_topic_results"):
        with pytest.raises(ValueError, match="from_date"):
            await ask(name, sid, audience="student", **days)
    for name, first in [("course_answers", cid), ("course_graded_scores", cid), ("course_topic_results", cid),
                        ("course_game_participation", cid), ("student_game_participation", sid)]:
        with pytest.raises(ValueError, match="from_date"):
            await ask(name, first, **days)


# ── topics (FR-621, FR-702) ──────────────────────────────────────────────────

async def test_topics_keep_graded_and_game_apart(shino_class, grader):     # noqa: F811
    c = shino_class
    quiz = await quiz_with(c, mcq=4, short=1)
    await set_topics(quiz, "Sums", "Sums", "Sums", "Sets", None)
    await take(c, quiz, 2, 0, None, 2, "1 pending")
    await play(await game_with(c, "Sums", "Sums", "Sets"), c.student_ids[0], 1, None, 0)
    got = await ask("course_topic_results", c.course_id)
    assert [(x.quiz_type, x.topic, x.question_count, x.answered_count, x.correct_count, x.pending_count,
             x.correct_rate) for x in got] == [
        ("game", "Sets", 1, 1, 0, 0, 0.0), ("game", "Sums", 1, 1, 1, 0, 1.0),
        ("graded", "Sets", 1, 1, 1, 0, 1.0), ("graded", "Sums", 3, 2, 1, 0, 0.333), ("graded", None, 1, 1, 0, 1, None)]
    assert {(x.student_id, x.matric_no, x.name, x.course_id, x.course_code) for x in got} == {
        (c.student_ids[0], "SH000001", "Shino Student 1", c.course_id, "SH101")}
    assert await ask("student_topic_results", c.student_ids[0], audience="lecturer") == got
    # the student: the game only, until the quiz is released
    seen = await ask("student_topic_results", c.student_ids[0], audience="student")
    assert seen == [x for x in got if x.quiz_type == "game"]


async def test_topics_add_up_over_quizzes_and_are_per_student(shino_class):
    c = shino_class
    for options in ((2, 0), (2, 2)):
        quiz = await quiz_with(c, mcq=1)
        await take(c, quiz, options[0])
        await take(c, quiz, options[1], i=1)
    got = await ask("course_topic_results", c.course_id)
    assert [(x.matric_no, x.topic, x.question_count, x.correct_count, x.correct_rate) for x in got] == [
        ("SH000001", "Topicword", 2, 2, 1.0), ("SH000002", "Topicword", 2, 1, 0.5)]


# ── game participation (FR-621, FR-702) ──────────────────────────────────────

async def test_game_participation(shino_class):
    c = shino_class
    quiz = await game_with(c, "A", "B", "C", title="Live")
    await game_with(c, "A")                             # published, never played
    await play(quiz, c.student_ids[0], 1, 0, None)      # nobody answers the third question
    await play(quiz, c.student_ids[1], None, None, None, at=NOW + HOUR)
    got = await ask("course_game_participation", c.course_id)
    assert [(x.matric_no, x.played, x.questions_asked, x.questions_answered, x.correct_count) for x in got] == [
        ("SH000001", True, 2, 2, 1), ("SH000002", True, 2, 0, 0), ("SH000003", False, 2, 0, 0),
        ("SH000004", False, 2, 0, 0)]
    assert vars(got[0]) == {
        "student_id": c.student_ids[0], "matric_no": "SH000001", "name": "Shino Student 1", "course_id": c.course_id,
        "course_code": "SH101", "quiz_id": quiz["id"], "quiz_title": "Live", "date": TODAY, "played": True,
        "questions_asked": 2, "questions_answered": 2, "correct_count": 1}
    for i, expected in enumerate(got):
        assert await ask("student_game_participation", c.student_ids[i]) == [expected]
    assert await ask("student_game_participation", c.outsider_student_id) == []


async def test_games_are_oldest_first_and_once_per_student(shino_class):
    c = shino_class
    sid = c.student_ids[0]
    late, early = await game_with(c, "A", title="Late"), await game_with(c, "A", title="Early")
    await play(late, sid, 1, at=NOW + DAY)
    await play(early, sid, 1)
    await tutorial_for(c, sid)
    got = await ask("student_game_participation", sid, c.course_id)
    assert [(x.quiz_title, x.date) for x in got] == [("Early", TODAY), ("Late", TODAY + DAY)]


async def test_game_participation_is_per_course(shino_class):
    c = shino_class
    sid = c.student_ids[0]
    other = await other_course_quiz(c)
    await play(await game_with(c, "A"), sid, 1)
    assert [x.course_code for x in await ask("student_game_participation", sid)] == ["SH101"]
    assert await ask("student_game_participation", sid, other) == []
    assert await ask("course_game_participation", other) == []


# ── the interface itself ─────────────────────────────────────────────────────

async def test_reads_see_changes_of_the_same_transaction(shino_class, grader):     # noqa: F811
    """M7 evaluates after a grade in the same session: no stale rows."""
    c = shino_class
    quiz = await quiz_with(c, mcq=1)
    await take(c, quiz, 0)
    async with AsyncSessionLocal() as db:
        [before] = await quiz_read.course_answers(db, c.course_id)
        answer = await db.scalar(select(QuizAnswer))
        async with AsyncSessionLocal() as other:
            row_ = await other.get(QuizAnswer, answer.id)
            row_.correct, row_.score = True, 1
            await other.commit()
        [after] = await quiz_read.course_answers(db, c.course_id)
        [score] = await quiz_read.course_graded_scores(db, c.course_id)
        (await db.get(Quiz, quiz["id"])).title = "Renamed"
        [renamed] = await quiz_read.course_graded_scores(db, c.course_id)
    assert (before.correct, after.correct, score.score, renamed.quiz_title) == (False, True, 1.0, "Renamed")


def test_every_result_says_whose_it_is_first():
    for cls in (quiz_read.StudentQuizAnswer, quiz_read.GradedScore, quiz_read.TopicResult,
                quiz_read.GameParticipation):
        assert [f.name for f in fields(cls)][:5] == ["student_id", "matric_no", "name", "course_id", "course_code"]
