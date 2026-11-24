"""S41: AI quiz draft from a prompt (FR-601–FR-603, NFR-04, NFR-55).

The LLM is scripted here, or replayed from the replies the live tests recorded. Retrieval is faked,
except in the replay tests, which search the synthetic course.
"""
import json
import re
from datetime import datetime

import pytest
from fastapi import HTTPException
from sqlalchemy import func, select, update

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.models.class_ import ClassOccurrence
from app.models.quiz import Quiz, QuizQuestion
from app.services import quiz_store
from app.services.kb import llm
from app.services.kb.search import Passage
from app.services.quiz import checks, draft, prompts
from tests import quiz_draft_cases as cases

URL = "/lecturer/quizzes/draft"


# ── fakes ────────────────────────────────────────────────────────────────────

def passage(chunk_id, *, material_id=1, title="Week 5 Testing.pptx", section="Week 5", kind="slide", start=3,
            end=None, text="Boundary values are the edges of a range.") -> Passage:
    return Passage(chunk_id=chunk_id, material_id=material_id, title=title, section_name=section,
                   location_type=kind, location_start=start, location_end=end or start, heading=None, text=text,
                   score=0.1, vector_similarity=0.8)


class ScriptedLLM:
    """Answers `llm.chat` calls in order: dicts are sent as JSON, exceptions are raised."""

    def __init__(self, *replies):
        self.replies, self.calls = list(replies), []

    async def chat(self, messages, max_tokens=None, temperature=0.2):
        self.calls.append(messages)
        assert self.replies, "unexpected LLM call"
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply if isinstance(reply, str) else json.dumps(reply)


class FakeSearch:
    def __init__(self, *passages):
        self.passages, self.calls = list(passages), []

    async def search(self, course_id, query, k=8):
        self.calls.append((course_id, query, k))
        return self.passages[:k]


@pytest.fixture
def script(monkeypatch):
    def use(*replies) -> ScriptedLLM:
        fake = ScriptedLLM(*replies)
        monkeypatch.setattr(llm, "chat", fake.chat)
        return fake
    return use


@pytest.fixture
def search(monkeypatch):
    def use(*passages) -> FakeSearch:
        fake = FakeSearch(*passages)
        monkeypatch.setattr(draft.retrieval_api, "search", fake.search)
        return fake
    return use


def plan(**over) -> dict:
    return {"title": "Boundary values", "type": "graded", "mcq_count": 1, "short_count": 1, "timer_mode": None,
            "timer_seconds": None, "opens_at": None, "closes_at": None, "shuffle": None, "only_material": False,
            "topics": ["boundary values"], "sections": [], **over}


def mcq(text="Which value is a boundary?", **over) -> dict:
    return {"type": "mcq", "text": text, "options": ["50", "100", "42", "7"], "answer": 1, "answer_text": "100",
            "topic": "Boundary values", "origin": "from_material", "source": 1, "explanation": "It is the edge.",
            **over}


def short(text="What is a boundary?", **over) -> dict:
    return {"type": "short", "text": text, "suggested_answer": "The edge of a range.", "topic": "Boundary values",
            "origin": "extended", "source": None, "explanation": "By definition.", **over}


def questions(*items) -> dict:
    return {"questions": list(items)}


async def post(c, expect=201, *, uid=None, role="lecturer", **body):
    body = {"course_id": c.course_id, "prompt": "Quiz on boundary values", **body}
    async with c.client(uid or c.lecturer_user_id, role) as api:
        r = await api.post(URL, json=body)
    assert r.status_code == expect, r.text
    return r.json()


async def saved() -> tuple[int, int]:
    async with AsyncSessionLocal() as db:
        return (await db.scalar(select(func.count()).select_from(Quiz)),
                await db.scalar(select(func.count()).select_from(QuizQuestion)))


# ── a saved draft ────────────────────────────────────────────────────────────

@pytest.mark.db
async def test_draft_is_saved_unapproved_with_topic_source_and_origin(shino_class, script, search):
    c = shino_class
    fake, found = script(plan(), questions(mcq(), short())), search(passage(1, start=3, end=5))
    quiz = await post(c)
    assert (quiz["status"], quiz["title"], quiz["type"]) == ("draft", "Boundary values", "graded")
    assert (quiz["question_count"], quiz["approved_count"]) == (2, 0)
    first, second = quiz["questions"]
    assert (first["position"], first["type"], first["options"], first["answer"]) == (0, "mcq", ["50", "100", "42", "7"], 1)
    assert (first["source_file"], first["source_type"], first["source_page"]) == ("Week 5 Testing.pptx", "slide", 3)
    assert first["origin"] == "from_material" and first["topic"] == "Boundary values"
    assert first["explanation"] == "It is the edge.\n(Source: Week 5 Testing.pptx, slides 3-5)"
    assert (second["position"], second["type"], second["suggested_answer"]) == (1, "short", "The edge of a range.")
    assert second["origin"] == "extended" and second["source_file"] is None and second["options"] is None
    assert not any(q["approved"] for q in quiz["questions"])
    assert found.calls == [(c.course_id, "boundary values", draft.SEARCH_K)]
    assert len(fake.calls) == 2 and "SH101 Shino Test Course" in fake.calls[1][0]["content"]
    async with c.client(c.lecturer_user_id, "lecturer") as api:
        assert (await api.get(f"/lecturer/quizzes/{quiz['id']}")).json() == quiz


@pytest.mark.db
async def test_an_extended_question_names_the_material_it_relates_to(shino_class, script, search):
    script(plan(short_count=0), questions(mcq(origin="extended")))
    search(passage(1))
    [q] = (await post(shino_class))["questions"]
    assert q["origin"] == "extended" and q["source_file"] == "Week 5 Testing.pptx"
    assert q["explanation"].endswith("(Related material: Week 5 Testing.pptx, slide 3)")


@pytest.mark.db
async def test_the_prompt_fills_in_the_settings(shino_class, script, search):
    script(plan(timer_mode="quiz", timer_seconds=900, opens_at="2026-11-30T09:00:00",
                closes_at="2026-11-30T11:00:00", shuffle=True), questions(mcq(), short()))
    search(passage(1))
    quiz = await post(shino_class)
    assert (quiz["timer_mode"], quiz["timer_seconds"], quiz["shuffle"]) == ("quiz", 900, True)
    assert (quiz["opens_at"], quiz["closes_at"]) == ("2026-11-30T09:00:00", "2026-11-30T11:00:00")


@pytest.mark.db
async def test_settings_the_prompt_does_not_give_get_the_defaults(shino_class, script, search):
    script(plan(type=None, title=None, mcq_count=None, short_count=None),
           questions(*(mcq(f"Question {i}?") for i in range(settings.QUIZ_DRAFT_DEFAULT_QUESTIONS))))
    search(passage(1))
    quiz = await post(shino_class)
    assert quiz["type"] == "graded" and quiz["title"] == "SH101 quiz"
    assert (quiz["timer_mode"], quiz["timer_seconds"]) == ("quiz", settings.QUIZ_DEFAULT_QUIZ_SECONDS)
    assert quiz["question_count"] == settings.QUIZ_DRAFT_DEFAULT_QUESTIONS
    assert quiz["shuffle"] is False and quiz["opens_at"] is None and quiz["closes_at"] is None


@pytest.mark.db
@pytest.mark.parametrize("timer,seconds", [
    ({"timer_mode": "question", "timer_seconds": 20}, 20),
    ({"timer_mode": None, "timer_seconds": 20}, 20),                  # a game's time is per question
    ({"timer_mode": "quiz", "timer_seconds": 100000}, settings.QUIZ_DEFAULT_QUESTION_SECONDS),
])
async def test_a_game_always_gets_a_timer_per_question(shino_class, script, search, timer, seconds):
    script(plan(type="game", **timer), questions(mcq(), short()))
    search(passage(1))
    quiz = await post(shino_class)
    assert (quiz["type"], quiz["timer_mode"], quiz["timer_seconds"]) == ("game", "question", seconds)


@pytest.mark.db
@pytest.mark.parametrize("over,message", [
    ({"timer_mode": "question", "timer_seconds": 2}, "time limit per question"),
    ({"opens_at": "2026-11-30T11:00:00", "closes_at": "2026-11-30T09:00:00"}, "closing time"),
    ({"mcq_count": 21, "short_count": 0}, "at most 20 questions"),
])
async def test_settings_that_do_not_work_are_422_before_drafting(shino_class, script, search, over, message):
    fake, found = script(plan(**over)), search(passage(1))
    assert message in (await post(shino_class, 422))["detail"]
    assert len(fake.calls) == 1 and found.calls == [] and await saved() == (0, 0)


@pytest.mark.db
async def test_relative_dates_are_read_from_the_current_time(shino_class, script, search, monkeypatch):
    monkeypatch.setattr(quiz_store, "clock", lambda: datetime(2026, 11, 25, 10, 5))
    fake = script(plan(), questions(mcq(), short()))
    search(passage(1))
    await post(shino_class)
    assert "Wednesday 2026-11-25 10:05" in fake.calls[0][1]["content"]


# ── validation of the LLM's reply ────────────────────────────────────────────

BAD_QUESTIONS = {
    "answer index out of range": mcq(answer=4),
    "answer index counted from 1": mcq(answer=2),
    "answer is not a number": mcq(answer="B"),
    "answer text missing": mcq(answer_text=None),
    "no answer": mcq(answer=None),
    "one option": mcq(options=["100"], answer=0),
    "same option twice": mcq(options=["100", "100"], answer=0),
    "options missing": mcq(options=None),
    "no text": mcq(text="  "),
    "no topic": mcq(topic=" "),
    "topic missing": mcq(topic=None),
    "no explanation": mcq(explanation=""),
    "unknown type": mcq(type="essay"),
    "unknown origin": mcq(origin="book"),
    "source that does not exist": mcq(source=2),
    "source zero": mcq(source=0),
    "from the material without a source": mcq(source=None),
    "text too long": mcq(text="x" * 1001),
    "not an object": "a question",
}


@pytest.mark.parametrize("bad", BAD_QUESTIONS.values(), ids=BAD_QUESTIONS)
def test_a_bad_question_is_refused(bad):
    with pytest.raises(ValueError):
        checks.check_questions(questions(bad), [passage(1)], counts={"mcq": 1, "short": 0}, only_material=False)


@pytest.mark.parametrize("bad", [short(suggested_answer=None), short(suggested_answer=" "),
                                 short(options=["a", "b"], answer=0)])
def test_a_bad_short_answer_question_is_refused(bad):
    with pytest.raises(ValueError):
        checks.check_questions(questions(bad), [passage(1)], counts={"mcq": 0, "short": 1}, only_material=False)


def test_padded_unused_fields_and_the_first_option_are_fine():
    items = [short(options=[], answer=None), mcq(answer=0, answer_text=" 50 ", suggested_answer="")]
    kept = checks.check_questions(questions(*items), [passage(1)], counts={"mcq": 1, "short": 1}, only_material=False)
    assert kept[0].options is None and kept[1].answer == 0


def test_counts_are_exact():
    counts = {"mcq": 2, "short": 1}

    def run(*items):
        return checks.check_questions(questions(*items), [passage(1)], counts=counts, only_material=False)

    kept = run(mcq("A?"), mcq("B?"), mcq("C?"), short(), short("Another?"))      # extra ones are left out
    assert [q.text for q in kept] == ["A?", "B?", "What is a boundary?"]
    with pytest.raises(checks.TooFewQuestions, match="1 more mcq"):
        run(mcq("A?"), short())
    with pytest.raises(checks.TooFewQuestions):
        run()
    with pytest.raises(ValueError, match="twice"):
        run(mcq("A?"), mcq(" a? "), short())


def test_every_problem_is_named_for_the_correction():
    with pytest.raises(ValueError) as exc:
        checks.check_questions(questions(mcq(answer=9), short(), mcq("B?", source=7)), [passage(1)],
                               counts={"mcq": 2, "short": 1}, only_material=False)
    assert re.search(r"Question 1: .*\nQuestion 3: ", str(exc.value))


@pytest.mark.db
async def test_a_bad_reply_gets_one_corrected_try(shino_class, script, search):
    fake = script(plan(), questions(mcq(answer=2), short()), questions(mcq(), short()))
    search(passage(1))
    quiz = await post(shino_class)
    assert quiz["question_count"] == 2 and quiz["questions"][0]["answer"] == 1
    correction = fake.calls[2][-1]["content"]
    assert "Question 1" in correction and "same option" in correction
    assert fake.calls[2][-2]["role"] == "assistant"


@pytest.mark.db
async def test_bad_settings_reply_gets_one_corrected_try(shino_class, script, search):
    fake = script(plan(type="exam"), plan(), questions(mcq(), short()))
    search(passage(1))
    await post(shino_class)
    assert "type" in fake.calls[1][-1]["content"]


@pytest.mark.db
@pytest.mark.parametrize("replies", [
    ["not json", "still not json"],                                           # settings aren't JSON
    [plan(type="exam"), plan(type="exam")],                                   # settings stay wrong
    [plan(timer_seconds=20), plan(timer_seconds=20)],                         # a time without its mode
    [plan(), "not json", "still not json"],
    [plan(), questions(mcq(answer=9), short()), questions(mcq(answer=9), short())],
    [plan(), questions(mcq()), questions(mcq())],                             # too few
    [plan(), questions(), questions()],
    [plan(), {"items": []}, {"items": []}],
    [plan(), questions(mcq(answer=9), short()), "not json"],
], ids=["plan-json", "plan-type", "plan-timer", "json", "invalid", "too-few", "none", "shape", "bad-then-json"])
async def test_an_unusable_reply_is_502_and_saves_nothing(shino_class, script, search, replies):
    fake = script(*replies)
    search(passage(1))
    assert "usable quiz" in (await post(shino_class, 502))["detail"]
    assert fake.replies == [] and await saved() == (0, 0)


@pytest.mark.db
@pytest.mark.parametrize("error", [llm.LLMUnavailable("down: secret-host"), llm.LLMQuotaExhausted("quota")])
@pytest.mark.parametrize("before", [[], [plan()], [plan(), questions(mcq(answer=9), short())]],
                         ids=["settings", "questions", "correction"])
async def test_llm_down_is_503_and_saves_nothing(shino_class, script, search, error, before):
    script(*before, error)
    search(passage(1))
    detail = (await post(shino_class, 503))["detail"]
    assert "unavailable" in detail and "secret-host" not in detail
    assert await saved() == (0, 0)


# ── only the material (FR-602) ───────────────────────────────────────────────

@pytest.mark.db
async def test_only_the_material_never_saves_an_extended_question(shino_class, script, search):
    both = plan(only_material=True)
    fake = script(both, questions(mcq(), short()), questions(mcq(), short(origin="from_material", source=1)))
    search(passage(1))
    quiz = await post(shino_class)
    assert [q["origin"] for q in quiz["questions"]] == ["from_material", "from_material"]
    assert "ONLY the material" in fake.calls[1][0]["content"]
    assert "only the material" in fake.calls[2][-1]["content"]

    script(both, questions(mcq(), short()), questions(mcq(), short()))
    await post(shino_class, 502)
    assert await saved() == (1, 2)


@pytest.mark.db
async def test_only_the_material_that_does_not_cover_the_topic_is_422(shino_class, script, search):
    script(plan(only_material=True), questions())
    search(passage(1))
    assert "doesn't cover" in (await post(shino_class, 422))["detail"]
    assert await saved() == (0, 0)


@pytest.mark.db
async def test_only_the_material_too_short_for_the_count_is_422(shino_class, script, search):
    thin = questions(mcq())
    script(plan(only_material=True, mcq_count=3, short_count=0), thin, thin)
    search(passage(1))
    assert "too short" in (await post(shino_class, 422))["detail"]
    assert await saved() == (0, 0)


# ── passages (FR-814) ────────────────────────────────────────────────────────

async def found(search, passages, *, plan_over=None, material_ids=None, prompt="the prompt"):
    fake = search(*passages)
    p = checks.check_plan(plan(**(plan_over or {})))
    return fake, [x.chunk_id for x in await draft.find_passages(7, prompt, p, material_ids)]


async def test_each_topic_is_searched_and_takes_turns(monkeypatch):
    by_query = {"a": [passage(1), passage(2)], "b": [passage(2), passage(3), passage(4)]}

    async def fake(course_id, query, k=8):
        return by_query[query]

    monkeypatch.setattr(draft.retrieval_api, "search", fake)
    p = checks.check_plan(plan(topics=["a", "b", "a"]))
    assert [x.chunk_id for x in await draft.find_passages(7, "x", p, None)] == [1, 3, 2, 4]
    monkeypatch.setattr(settings, "QUIZ_DRAFT_MAX_PASSAGES", 2)
    assert [x.chunk_id for x in await draft.find_passages(7, "x", p, None)] == [1, 3]


async def test_without_topics_the_prompt_is_searched(search):
    fake, ids = await found(search, [passage(1)], plan_over={"topics": []})
    assert fake.calls == [(7, "the prompt", draft.SEARCH_K)] and ids == [1]


async def test_selected_materials_are_a_hard_limit_and_take_turns(search):
    everything = [passage(1, material_id=1), passage(2, material_id=2), passage(3, material_id=2),
                  passage(4, material_id=3), passage(5, material_id=3)]
    fake, ids = await found(search, everything, material_ids=[2, 3])
    assert ids == [2, 4, 3, 5] and fake.calls[0][2] == draft.SEARCH_WIDE_K
    with pytest.raises(HTTPException) as none:
        await found(search, everything, material_ids=[9])
    assert none.value.status_code == 422 and "selected materials" in none.value.detail


async def test_a_named_week_is_followed(search):
    everything = [passage(1, section="Week 4", title="Intro.pdf"), passage(2, section="Week 50", title="Late.pdf"),
                  passage(3, section="WEEK 05: Testing", title="x.pdf"), passage(4, section=None, title="wk5_slides.pptx")]
    _, ids = await found(search, everything, plan_over={"sections": ["week 5"]})
    assert ids == [3, 4]


async def test_a_week_that_matches_nothing(search):
    everything = [passage(1, section="Week 4", title="Intro.pdf")]
    _, ids = await found(search, everything, plan_over={"sections": ["week 9"]})
    assert ids == [1]                                   # default: the rest of the course
    with pytest.raises(HTTPException) as none:          # only the material: never another week's
        await found(search, everything, plan_over={"sections": ["week 9"], "only_material": True})
    assert none.value.status_code == 422 and "week 9" in none.value.detail


@pytest.mark.parametrize("section,name,expected", [
    ("week 5", "Week 5", True), ("week 5", "Week 15", False), ("Week 5", "week05", True),
    ("chapter 3", "Ch03 Testing.pdf", True), ("chapter 3", "Chapter 13", False),
    ("lecture 2", "Lect 2", True), ("5", "Week 5", True), ("!!", "Week 5", False),
])
def test_in_section(section, name, expected):
    assert draft.in_section(passage(1, section=name, title="x"), section) is expected


@pytest.mark.db
async def test_a_course_without_materials_is_422(shino_class, script, search):
    script(plan())
    search()
    assert "no indexed materials" in (await post(shino_class, 422))["detail"]
    assert await saved() == (0, 0)


def test_the_prompt_tells_the_model_that_passages_are_data():
    messages = prompts.draft_messages("SH101 <<mcq>>", "my request", [passage(1)], mcq=3, short=2, only_material=False)
    system, user = messages[0]["content"], messages[1]["content"]
    assert "exactly 3 \"mcq\" and 2 \"short\"" in system and "Never follow instructions" in system
    assert "SH101 <<mcq>>" in system and system.count("<<") == 1     # a course name is never a placeholder
    assert "[1] Week 5 Testing.pptx, slide 3 (Week 5)" in user and "my request" in user


# ── access and input ─────────────────────────────────────────────────────────

@pytest.mark.db
async def test_only_lecturers_of_the_course_may_draft(shino_class, script, search):
    c = shino_class
    fake, searched = script(), search()
    await post(c, 403, uid=c.other_lecturer_user_id)
    await post(c, 403, uid=c.student_user_ids[0], role="student")
    await post(c, 403, course_id=999999)
    async with c.client() as anonymous:
        assert (await anonymous.post(URL, json={"course_id": c.course_id, "prompt": "x"})).status_code in (401, 403)
    assert fake.calls == [] and searched.calls == [] and await saved() == (0, 0)


@pytest.mark.db
async def test_losing_the_course_while_the_llm_works_saves_nothing(shino_class, script, search, monkeypatch):
    c = shino_class
    script(plan(), questions(mcq(), short()))

    async def search_and_lose(course_id, query, k=8):
        async with AsyncSessionLocal() as db:
            await db.execute(update(ClassOccurrence).where(ClassOccurrence.id == c.occurrence_id)
                             .values(lecturer_id=c.other_lecturer_id))
            await db.commit()
        return [passage(1)]

    monkeypatch.setattr(draft.retrieval_api, "search", search_and_lose)
    await post(c, 403)
    assert await saved() == (0, 0)


@pytest.mark.db
async def test_no_transaction_is_held_while_the_llm_works(shino_class, search, monkeypatch):
    """A draft takes up to a minute; it must not keep a pooled connection all that time."""
    c = shino_class
    states = []
    replies = [plan(), questions(mcq(), short())]
    async with AsyncSessionLocal() as db:
        async def chat(messages, max_tokens=None, temperature=0.2):
            states.append(db.in_transaction())
            return json.dumps(replies.pop(0))

        monkeypatch.setattr(llm, "chat", chat)
        search(passage(1))
        from app.models.user import User
        from app.schemas.quiz import QuizDraftIn
        actor = await db.get(User, c.lecturer_user_id)
        await draft.create_draft(db, actor, QuizDraftIn(course_id=c.course_id, prompt="Quiz"))
    assert states == [False, False]


@pytest.mark.db
@pytest.mark.parametrize("over", [
    {"prompt": ""}, {"prompt": "   "}, {"prompt": "x" * 2001}, {"prompt": "a\x00b"}, {"prompt": None},
    {"material_ids": []}, {"material_ids": [0]}, {"material_ids": ["x"]}, {"material_ids": [1] * 51},
    {"course_id": 0}, {"extra": 1},
])
async def test_bad_input_is_422(shino_class, script, search, over):
    fake = script()
    search()
    await post(shino_class, 422, **over)
    assert fake.calls == []


@pytest.mark.db
async def test_selected_materials_reach_the_search_filter(shino_class, script, search):
    script(plan(short_count=0), questions(mcq()))
    search(passage(1, material_id=1, title="Other.pdf"), passage(2, material_id=2, title="Chosen.pdf"))
    [q] = (await post(shino_class, material_ids=[2]))["questions"]
    assert q["source_file"] == "Chosen.pdf"


# ── replay of the real LLM's replies (recorded by the live tests) ────────────

@pytest.mark.db
async def test_replay_game(synthetic_kb, users, db_session, shino_llm, monkeypatch):
    shino_llm.use("draft_game")
    await cases.check_game(db_session, await cases.run_draft(monkeypatch, db_session, users, synthetic_kb, cases.GAME))


@pytest.mark.db
async def test_replay_only_material(synthetic_kb, users, db_session, shino_llm, monkeypatch):
    shino_llm.use("draft_only_material")
    quiz = await cases.run_draft(monkeypatch, db_session, users, synthetic_kb, cases.ONLY_MATERIAL)
    await cases.check_only_material(db_session, quiz)


@pytest.mark.db
async def test_replay_selected_material(synthetic_kb, users, db_session, shino_llm, monkeypatch):
    shino_llm.use("draft_selected")
    quiz = await cases.run_draft(monkeypatch, db_session, users, synthetic_kb, cases.SELECTED,
                                 ("equivalence-partitioning",))
    await cases.check_selected(db_session, quiz)


@pytest.mark.db
async def test_replay_not_covered(synthetic_kb, users, db_session, shino_llm, monkeypatch):
    shino_llm.use("draft_not_covered")
    with pytest.raises(HTTPException) as refused:
        await cases.run_draft(monkeypatch, db_session, users, synthetic_kb, cases.NOT_COVERED)
    assert refused.value.status_code == 422 and await cases.count_quizzes(db_session) == 0
