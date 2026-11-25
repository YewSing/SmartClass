"""S42: regenerating one question and refining a draft with the AI (FR-604, FR-602, NFR-55).

The LLM is scripted here, or replayed from the replies the live tests recorded. Retrieval is faked,
except in the replay tests, which search the synthetic course. Access and 409s before the LLM is
called are in test_quiz_questions.py.
"""
import json

import pytest
from fastapi import HTTPException
from sqlalchemy import update

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.models.class_ import ClassOccurrence
from app.models.quiz import Quiz
from app.models.user import User
from app.schemas.quiz import AiScope, QuestionRegenerateIn, QuizRefineIn
from app.services import quiz_store
from app.services.kb import llm
from app.services.quiz import checks, draft, prompts, refine
from tests import quiz_refine_cases as cases
from tests.test_quiz_crud import URL, attempt_row, call, get, insert
from tests.test_quiz_draft import FakeSearch, ScriptedLLM, mcq, passage, plan, questions, short
from tests.test_quiz_questions import approve, edit, ids, quiz_with, remove
from tests.test_quiz_questions import mcq as stored


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


def about(*numbers, **over) -> dict:
    return {"questions": list(numbers), "topics": [], "sections": [], "only_material": None, **over}


def changes(*items) -> dict:
    return {"changes": list(items)}


def replace(number, question) -> dict:
    return {"action": "replace", "number": number, "question": question}


def drop(number) -> dict:
    return {"action": "remove", "number": number}


def new(question) -> dict:
    return {"action": "add", "question": question}


async def regenerate(c, quiz, number, expect=200, **body):
    url = f"{URL}/{quiz['id']}/questions/{ids(quiz)[number - 1]}/regenerate"
    return await call(c, "POST", url, expect, json=body)


async def refine_(c, quiz, expect=200, prompt="Make question 1 harder", **kw):
    return await call(c, "POST", f"{URL}/{quiz['id']}/refine", expect, json={"prompt": prompt}, **kw)


async def set_scope(quiz, **scope):
    async with AsyncSessionLocal() as db:
        await cases.set_scope(db, quiz["id"], AiScope(**scope))


async def scope_of(quiz) -> dict | None:
    async with AsyncSessionLocal() as db:
        return (await db.get(Quiz, quiz["id"])).ai_scope


async def approved_quiz(c, *bodies):
    quiz = await quiz_with(c, *(bodies or (stored("A?"), stored("B?"), stored("C?"))))
    return await approve(c, quiz["id"], ids(quiz))


def texts(quiz) -> list[str]:
    return [q["text"] for q in quiz["questions"]]


# ── regenerate ───────────────────────────────────────────────────────────────

@pytest.mark.db
async def test_regenerate_replaces_one_question_in_its_place_unapproved(shino_class, script, search):
    c = shino_class
    quiz = await approved_quiz(c)
    fake, found = script(questions(mcq("New?"))), search(passage(1, start=7))
    after = await regenerate(c, quiz, 2)
    assert ids(after) == ids(quiz) and texts(after) == ["A?", "New?", "C?"]
    assert [q["approved"] for q in after["questions"]] == [True, False, True]
    changed = after["questions"][1]
    assert (changed["source_file"], changed["source_page"]) == ("Week 5 Testing.pptx", 7)
    assert changed["explanation"] == "It is the edge.\n(Source: Week 5 Testing.pptx, slide 7)"
    assert [after["questions"][0], after["questions"][2]] == [quiz["questions"][0], quiz["questions"][2]]
    assert found.calls == [(c.course_id, "Sums B?", draft.SEARCH_K)]
    [messages] = fake.calls
    assert "exactly 1 \"mcq\" and 0 \"short\"" in messages[0]["content"]
    assert '"text": "B?"' in messages[1]["content"] and "- A?\n- C?" in messages[1]["content"]
    assert await get(c, quiz["id"]) == after


@pytest.mark.db
async def test_regenerate_keeps_the_type_and_follows_the_instruction(shino_class, script, search):
    c = shino_class
    quiz = await quiz_with(c, {"type": "short", "text": "Why?", "suggested_answer": "Because"})
    fake, found = script(questions(short("How?"))), search(passage(1))
    after = await regenerate(c, quiz, 1, instruction=" about edges ")
    assert (after["questions"][0]["type"], texts(after)) == ("short", ["How?"])
    assert [q for _, q, _ in found.calls] == ["Why?", "about edges"]
    assert "What the new question should be like:\nabout edges" in fake.calls[0][1]["content"]


@pytest.mark.db
@pytest.mark.parametrize("same", [" a? ", "B?"])
async def test_a_regenerated_question_is_never_one_already_in_the_quiz(shino_class, script, search, same):
    c = shino_class
    quiz = await approved_quiz(c)
    search(passage(1))
    fake = script(questions(mcq(same)), questions(mcq("New?")))
    assert texts(await regenerate(c, quiz, 2)) == ["A?", "New?", "C?"]
    assert "already in the quiz" in fake.calls[1][-1]["content"]
    script(questions(mcq("C?")), questions(mcq("C?")))
    await regenerate(c, quiz, 2, expect=502)


@pytest.mark.db
async def test_regenerate_keeps_to_the_drafts_scope(shino_class, script, search):
    c = shino_class
    quiz = await approved_quiz(c)
    await set_scope(quiz, only_material=True, material_ids=[2])
    search(passage(1, material_id=1, title="Other.pdf"), passage(2, material_id=2, title="Chosen.pdf"))
    fake = script(questions(mcq("New?", origin="extended", source=None)), questions(mcq("New?")))
    after = await regenerate(c, quiz, 1)
    assert (after["questions"][0]["origin"], after["questions"][0]["source_file"]) == ("from_material", "Chosen.pdf")
    assert "Other.pdf" not in fake.calls[0][1]["content"] and "ONLY the material" in fake.calls[0][0]["content"]

    script(questions())
    assert "doesn't cover" in (await regenerate(c, quiz, 1, expect=422))["detail"]
    search(passage(1, material_id=1))
    assert "selected materials" in (await regenerate(c, quiz, 1, expect=422))["detail"]
    assert await get(c, quiz["id"]) == after


@pytest.mark.db
async def test_regenerate_keeps_to_the_drafts_week(shino_class, script, search):
    c = shino_class
    quiz = await approved_quiz(c)
    await set_scope(quiz, only_material=True, sections=["week 5"])
    search(passage(1, section="Week 4", title="Four.pdf"), passage(2, section="Week 5", title="Five.pdf"))
    script(questions(mcq("New?")))
    assert (await regenerate(c, quiz, 1))["questions"][0]["source_file"] == "Five.pdf"


# ── refine ───────────────────────────────────────────────────────────────────

@pytest.mark.db
async def test_refine_makes_only_the_listed_changes(shino_class, script, search):
    c = shino_class
    quiz = await approved_quiz(c)
    a, b, d = ids(quiz)
    fake = script(about(2, 1), changes(drop(1), replace(2, mcq("B harder?")), new(short("Added?"))))
    search(passage(1))
    after = await refine_(c, quiz, prompt="Make 2 harder, drop 1, add a short one")
    assert texts(after) == ["B harder?", "C?", "Added?"] and ids(after)[:2] == [b, d]
    assert [q["position"] for q in after["questions"]] == [0, 1, 2]
    assert [q["approved"] for q in after["questions"]] == [False, True, False]
    assert {**after["questions"][1], "position": 2} == quiz["questions"][2]
    assert after["questions"][0]["source_file"] == "Week 5 Testing.pptx"
    assert after["questions"][2]["origin"] == "extended"
    assert (after["question_count"], after["approved_count"]) == (3, 1)
    for messages in fake.calls:
        assert '"number": 2, "type": "mcq", "text": "B?"' in messages[1]["content"]
        assert "Make 2 harder, drop 1" in messages[1]["content"]
    assert "SH101 Shino Test Course" in fake.calls[1][0]["content"]
    assert await get(c, quiz["id"]) == after


@pytest.mark.db
async def test_refine_can_fill_an_empty_draft(shino_class, script, search):
    c = shino_class
    quiz = await quiz_with(c)
    fake, found = script(about(topics=["edges"]), changes(new(mcq("A?")), new(short()))), search(passage(1))
    assert texts(await refine_(c, quiz, prompt="Add two")) == ["A?", "What is a boundary?"]
    assert "(none yet)" in fake.calls[0][1]["content"] and [q for _, q, _ in found.calls] == ["edges"]


@pytest.mark.db
@pytest.mark.parametrize("bad", [
    [replace(4, mcq("X?"))], [replace(0, mcq("X?"))], [replace(None, mcq("X?"))], [drop(9)], [drop(None)],
    [drop(1), replace(1, mcq("X?"))], [drop(1), drop(1)], [replace(1, mcq("X?")), replace(1, mcq("Y?"))],
    [replace(1, None)], [new(None)], [{"action": "move", "number": 1}],
    [replace(1, mcq("b?"))],                                    # question 2, which stays
    [new(mcq("X?")), new(mcq(" x? "))],
    [new(mcq("X?", answer=9))], [replace(1, mcq("X?", source=5))], [new(short(suggested_answer=None))],
    [new(mcq("X?", explanation=""))],
    [drop(1), drop(2), drop(3)],                                # nothing left
    ["a change"],
])
async def test_bad_changes_get_one_corrected_try_then_502(shino_class, script, search, bad):
    c = shino_class
    quiz = await approved_quiz(c)
    search(passage(1))
    fake = script(about(1), changes(*bad), changes(*bad))
    assert "usable changes" in (await refine_(c, quiz, expect=502))["detail"]
    assert fake.replies == [] and "can't be used" in fake.calls[2][-1]["content"]
    assert await get(c, quiz["id"]) == quiz

    script(about(1), changes(*bad), changes(replace(1, mcq("Good?"))))
    assert texts(await refine_(c, quiz)) == ["Good?", "B?", "C?"]


def test_a_replaced_or_removed_text_may_be_used_again():
    out = checks.check_changes(changes(drop(1), replace(2, mcq("B?", answer=0, answer_text="50")), new(mcq("A?"))),
                               [passage(1)], ["A?", "B?"], only_material=False)
    assert out.removed == {1} and out.replaced[2].answer == 0 and [q.text for q in out.added] == ["A?"]


@pytest.mark.db
@pytest.mark.parametrize("only", [False, True])
async def test_nothing_to_change_is_422(shino_class, script, search, only):
    c = shino_class
    quiz = await approved_quiz(c)
    await set_scope(quiz, only_material=only)
    search(passage(1))
    script(about(), changes())
    detail = (await refine_(c, quiz, expect=422, prompt="20 seconds each"))["detail"]
    assert "nothing to change" in detail and ("doesn't cover" in detail) is only
    assert await get(c, quiz["id"]) == quiz


@pytest.mark.db
async def test_refine_may_not_go_over_the_question_limit(shino_class, script, search, monkeypatch):
    c = shino_class
    quiz = await approved_quiz(c)
    monkeypatch.setattr(settings, "QUIZ_MAX_QUESTIONS", 3)
    search(passage(1))
    script(about(), changes(new(mcq("X?"))))
    assert "at most 3" in (await refine_(c, quiz, expect=422))["detail"]
    script(about(), changes(drop(1), new(mcq("X?"))))
    assert texts(await refine_(c, quiz)) == ["B?", "C?", "X?"]


@pytest.mark.db
async def test_only_the_material_is_kept_from_the_draft_and_can_be_changed_by_the_request(shino_class, script, search):
    c = shino_class
    quiz = await approved_quiz(c)
    await set_scope(quiz, only_material=True, sections=["Week 5"])
    search(passage(1))
    extended, grounded = changes(new(short("X?"))), changes(new(short("X?", origin="from_material", source=1)))
    fake = script(about(), extended, grounded)
    assert (await refine_(c, quiz))["questions"][3]["origin"] == "from_material"
    assert "only the material" in fake.calls[2][-1]["content"] and '{"changes": []}' in fake.calls[1][0]["content"]

    script(about(only_material=False), changes(new(short("Y?"))))
    assert (await refine_(c, quiz, prompt="Add one beyond the slides"))["questions"][4]["origin"] == "extended"
    assert await scope_of(quiz) == {"only_material": False, "material_ids": None, "sections": ["Week 5"]}

    script(about(only_material=True), changes(new(short("Z?"))), changes(new(short("Z?"))))
    await refine_(c, quiz, expect=502, prompt="Add one, only the slides")
    assert (await scope_of(quiz))["only_material"] is False     # nothing was saved


@pytest.mark.db
async def test_a_draft_remembers_its_scope(shino_class, script, search):
    c = shino_class
    script(plan(short_count=0, only_material=True, sections=["week 5"]), questions(mcq()))
    search(passage(1, material_id=2))
    quiz = await call(c, "POST", f"{URL}/draft", 201,
                      json={"course_id": c.course_id, "prompt": "Quiz", "material_ids": [2]})
    assert await scope_of(quiz) == {"only_material": True, "material_ids": [2], "sections": ["week 5"]}
    assert await scope_of(await quiz_with(c)) is None           # written by hand: no limit


# ── passages of a refine request ─────────────────────────────────────────────

async def found(monkeypatch, by_query, request, scope=None, texts=("A?", "B?")):
    calls = []

    async def fake(course_id, query, k=8):
        calls.append(query)
        return by_query.get(query, [])

    monkeypatch.setattr(draft.retrieval_api, "search", fake)
    qs = [cases.QuestionOut(id=i, position=i, approved=False, **{**cases.QUESTIONS[0].model_dump(), "text": t,
                                                                 "topic": None}) for i, t in enumerate(texts)]
    p = checks.check_refine_plan(request, len(qs))
    return calls, [x.chunk_id for x in await refine.request_passages(7, "the prompt", p, qs, scope or AiScope())]


async def test_the_changed_questions_and_the_new_topics_take_turns(monkeypatch):
    calls, got = await found(monkeypatch, {"B?": [passage(1), passage(2)], "x": [passage(2), passage(3)]},
                             about(2, topics=["x"]))
    assert calls == ["B?", "x"] and got == [1, 3, 2]


async def test_without_questions_or_topics_the_request_is_searched(monkeypatch):
    calls, got = await found(monkeypatch, {"the prompt": [passage(1)]}, about(7))     # no question 7
    assert calls == ["the prompt"] and got == [1]


async def test_a_week_named_in_the_request_is_for_its_new_topics_only(monkeypatch):
    four, five = passage(1, section="Week 4"), passage(2, section="Week 5")
    scope = AiScope(sections=["week 4"])
    _, got = await found(monkeypatch, {"A?": [five, four], "x": [five, four]}, about(1, topics=["x"]), scope)
    assert got == [1]
    _, got = await found(monkeypatch, {"A?": [five, four], "x": [five, four]},
                         about(1, topics=["x"], sections=["week 5"]), scope)
    assert got == [1, 2]
    with pytest.raises(HTTPException) as none:
        await found(monkeypatch, {"x": [five, four]}, about(topics=["x"], sections=["week 9"]),
                    AiScope(only_material=True))
    assert none.value.status_code == 422 and "week 9" in none.value.detail


async def test_chosen_materials_stay_a_hard_limit(monkeypatch):
    _, got = await found(monkeypatch, {"x": [passage(1, material_id=1), passage(2, material_id=2)]},
                         about(topics=["x"]), AiScope(material_ids=[2]))
    assert got == [2]


@pytest.mark.parametrize("bad", [{"questions": "all"}, {"questions": ["x"]}, {"only_material": "maybe"},
                                 {"topics": "x"}])
def test_a_bad_refine_plan_is_refused(bad):
    with pytest.raises(ValueError):
        checks.check_refine_plan({**about(), **bad}, 3)


def test_a_refine_plan_is_tidied():
    p = checks.check_refine_plan({"questions": [3, 1, 3, 9, 0, -1], "topics": None, "sections": [" week  5 "]}, 3)
    assert (p.questions, p.topics, p.sections, p.only_material) == ([3, 1], [], ["week 5"], None)


# ── failures save nothing (NFR-55) ───────────────────────────────────────────

@pytest.mark.db
@pytest.mark.parametrize("replies,status", [
    (["not json", "still not json"], 502),
    ([{"questions": "all"}, {"questions": "all"}], 502),
    ([about(1), "not json", "still not json"], 502),
    ([about(1), {"questions": []}, {"questions": []}], 502),
    ([llm.LLMUnavailable("down: secret-host")], 503),
    ([about(1), llm.LLMQuotaExhausted("quota")], 503),
    ([about(1), changes(drop(9)), llm.LLMUnavailable("down")], 503),
])
async def test_refine_llm_failures(shino_class, script, search, replies, status):
    c = shino_class
    quiz = await approved_quiz(c)
    fake = script(*replies)
    search(passage(1))
    assert "secret-host" not in (await refine_(c, quiz, expect=status))["detail"]
    assert fake.replies == [] and await get(c, quiz["id"]) == quiz


@pytest.mark.db
@pytest.mark.parametrize("replies,status", [
    (["not json", "still not json"], 502),
    ([questions(mcq("X?", answer=9)), questions(mcq("X?", answer=9))], 502),
    ([questions(short("X?")), questions(short("X?"))], 502),        # the wrong type
    ([questions(), questions()], 502),
    ([llm.LLMUnavailable("down")], 503),
])
async def test_regenerate_llm_failures(shino_class, script, search, replies, status):
    c = shino_class
    quiz = await approved_quiz(c)
    fake = script(*replies)
    search(passage(1))
    await regenerate(c, quiz, 1, expect=status)
    assert fake.replies == [] and await get(c, quiz["id"]) == quiz


@pytest.mark.db
async def test_a_course_without_materials_is_422(shino_class, script, search):
    c = shino_class
    quiz = await approved_quiz(c)
    search()
    script()
    assert "no indexed materials" in (await regenerate(c, quiz, 1, expect=422))["detail"]
    script(about(1))
    assert "no indexed materials" in (await refine_(c, quiz, expect=422))["detail"]
    assert await get(c, quiz["id"]) == quiz


@pytest.mark.db
@pytest.mark.parametrize("body", [{}, {"prompt": ""}, {"prompt": "  "}, {"prompt": "x" * 2001}, {"prompt": None},
                                  {"prompt": "a\x00b"}, {"prompt": "x", "extra": 1}])
async def test_bad_refine_input_is_422(shino_class, script, body):
    c = shino_class
    quiz = await quiz_with(c)
    script()
    await call(c, "POST", f"{URL}/{quiz['id']}/refine", 422, json=body)


@pytest.mark.db
@pytest.mark.parametrize("body", [{"instruction": "x" * 2001}, {"instruction": "a\x00b"}, {"extra": 1}])
async def test_bad_regenerate_input_is_422(shino_class, script, body):
    c = shino_class
    quiz = await quiz_with(c, stored("A?"))
    script()
    await regenerate(c, quiz, 1, expect=422, **body)


# ── the draft changes while the LLM works ────────────────────────────────────

@pytest.fixture
def meanwhile(monkeypatch):
    """Run an action while the passages are being searched."""
    def use(action):
        async def fake(course_id, query, k=8):
            await action()
            return [passage(1)]
        monkeypatch.setattr(draft.retrieval_api, "search", fake)
    return use


REGENERATE, REFINE = [questions(mcq("New?"))], [about(1), changes(replace(1, mcq("New?")))]


@pytest.mark.db
@pytest.mark.parametrize("what", ["edited", "deleted"])
async def test_regenerate_never_overwrites_a_question_changed_meanwhile(shino_class, script, meanwhile, what):
    c = shino_class
    quiz = await approved_quiz(c)
    a = ids(quiz)[0]

    async def action():
        if what == "edited":
            await edit(c, quiz["id"], a, stored("Mine?"))
        else:
            await remove(c, quiz["id"], a)

    script(*REGENERATE)
    meanwhile(action)
    assert "while the AI was working" in (await regenerate(c, quiz, 1, expect=409))["detail"]
    assert texts(await get(c, quiz["id"])) == (["Mine?", "B?", "C?"] if what == "edited" else ["B?", "C?"])


@pytest.mark.db
async def test_regenerate_allows_changes_to_other_questions_meanwhile(shino_class, script, meanwhile):
    c = shino_class
    quiz = await approved_quiz(c)
    script(*REGENERATE)

    async def action():
        await edit(c, quiz["id"], ids(quiz)[1], stored("Mine?"))
    meanwhile(action)
    assert texts(await regenerate(c, quiz, 1)) == ["New?", "Mine?", "C?"]


@pytest.mark.db
@pytest.mark.parametrize("what", ["edited", "deleted", "reordered"])
async def test_refine_never_mixes_with_changes_made_meanwhile(shino_class, script, meanwhile, what):
    c = shino_class
    quiz = await approved_quiz(c)
    _, b, d = ids(quiz)

    async def action():
        if what == "edited":
            await edit(c, quiz["id"], b, stored("Mine?"))
        elif what == "deleted":
            await remove(c, quiz["id"], d)
        else:
            await call(c, "PUT", f"{URL}/{quiz['id']}/questions/order", 200,
                       json={"question_ids": ids(quiz)[::-1]})

    script(*REFINE)
    meanwhile(action)
    await refine_(c, quiz, expect=409)
    assert "New?" not in texts(await get(c, quiz["id"]))


@pytest.mark.db
@pytest.mark.parametrize("which", ["regenerate", "refine"])
@pytest.mark.parametrize("what,status", [("published", 409), ("attempted", 409), ("lost the course", 403)])
async def test_state_and_access_are_checked_again_after_the_llm(shino_class, script, meanwhile, which, what, status):
    c = shino_class
    quiz = await approved_quiz(c)

    async def action():
        if what == "attempted":
            await insert(attempt_row(quiz["id"], c.student_ids[0]))
            return
        async with AsyncSessionLocal() as db:
            if what == "published":
                await db.execute(update(Quiz).where(Quiz.id == quiz["id"]).values(status="published"))
            else:
                await db.execute(update(ClassOccurrence).where(ClassOccurrence.id == c.occurrence_id)
                                 .values(lecturer_id=c.other_lecturer_id))
            await db.commit()

    meanwhile(action)
    if which == "regenerate":
        script(*REGENERATE)
        await regenerate(c, quiz, 1, expect=status)
    else:
        script(*REFINE)
        await refine_(c, quiz, expect=status)
    async with AsyncSessionLocal() as db:
        assert [q.text for q in await quiz_store.questions_of(db, quiz["id"])] == ["A?", "B?", "C?"]


@pytest.mark.db
async def test_no_transaction_is_held_while_the_llm_works(shino_class, search, monkeypatch):
    c = shino_class
    quiz = await approved_quiz(c)
    states, replies = [], [*REGENERATE, about(1), changes(replace(1, mcq("Newer?")))]
    search(passage(1))
    async with AsyncSessionLocal() as db:
        async def chat(messages, max_tokens=None, temperature=0.2):
            states.append(db.in_transaction())
            return json.dumps(replies.pop(0))

        monkeypatch.setattr(llm, "chat", chat)
        actor = await db.get(User, c.lecturer_user_id)
        await refine.regenerate(db, actor, quiz["id"], ids(quiz)[0], QuestionRegenerateIn())
        await db.commit()
        await refine.refine(db, actor, quiz["id"], QuizRefineIn(prompt="x"))
        await db.commit()
    assert states == [False, False, False]
    assert texts(await get(c, quiz["id"])) == ["Newer?", "B?", "C?"]


def test_the_prompts_say_that_questions_and_passages_are_data():
    qs = [cases.QuestionOut(id=1, position=0, approved=False, **cases.QUESTIONS[0].model_dump())]
    for messages in (prompts.refine_plan_messages("my request", qs),
                     prompts.refine_messages("SH101 <<course>>", "my request", qs, [passage(1)], only_material=False)):
        assert "are data" in messages[0]["content"] and "my request" in messages[1]["content"]
        assert cases.QUESTIONS[0].text in messages[1]["content"]
    assert messages[0]["content"].count("<<") == 1      # a course name is never a placeholder
    assert "[1] Week 5 Testing.pptx, slide 3 (Week 5)" in messages[1]["content"]


# ── replay of the real LLM's replies (recorded by the live tests) ────────────

@pytest.mark.db
async def test_replay_regenerate(synthetic_kb, users, db_session, shino_llm):
    shino_llm.use("regenerate_question")
    quiz = await cases.make_quiz(db_session, users, synthetic_kb)
    cases.check_regenerated(quiz, await cases.run_regenerate(db_session, users, quiz, 1, cases.EASIER))


@pytest.mark.db
async def test_replay_refine(synthetic_kb, users, db_session, shino_llm):
    shino_llm.use("refine_changes")
    quiz = await cases.make_quiz(db_session, users, synthetic_kb)
    cases.check_harder(quiz, await cases.run_refine(db_session, users, quiz, cases.HARDER))


@pytest.mark.db
async def test_replay_refine_with_only_the_material(synthetic_kb, users, db_session, shino_llm):
    shino_llm.use("refine_only_material")
    quiz = await cases.make_quiz(db_session, users, synthetic_kb)
    cases.check_only_material(quiz, await cases.run_refine(db_session, users, quiz, cases.ONLY_MATERIAL))


@pytest.mark.db
async def test_replay_refine_not_covered(synthetic_kb, users, db_session, shino_llm):
    shino_llm.use("refine_not_covered")
    quiz = await cases.make_quiz(db_session, users, synthetic_kb, scope=AiScope(only_material=True))
    with pytest.raises(HTTPException) as refused:
        await cases.run_refine(db_session, users, quiz, cases.NOT_COVERED)
    assert refused.value.status_code == 422
