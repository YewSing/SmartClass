"""S42: reviewing a draft's questions by hand (FR-604, NFR-04): add, edit, delete, reorder, approve."""
import asyncio

import pytest
from sqlalchemy import update

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.models.class_ import ClassOccurrence
from app.models.quiz import Quiz, QuizQuestion
from tests.test_quiz_crud import URL, attempt_row, call, count, create, get, insert, set_status

pytestmark = pytest.mark.db


def mcq(text="2+2?", **over) -> dict:
    return {"type": "mcq", "text": text, "options": ["3", "4"], "answer": 1, "topic": "Sums",
            "origin": "from_material", "source_file": "w5.pdf", "source_type": "slide", "source_page": 3,
            "explanation": "Count.", **over}


def short(text="Why?", **over) -> dict:
    return {"type": "short", "text": text, "suggested_answer": "Because", **over}


async def add(c, qid, body, expect=201, **kw):
    return await call(c, "POST", f"{URL}/{qid}/questions", expect, json=body, **kw)


async def edit(c, qid, question_id, body, expect=200, **kw):
    return await call(c, "PUT", f"{URL}/{qid}/questions/{question_id}", expect, json=body, **kw)


async def remove(c, qid, question_id, expect=200, **kw):
    return await call(c, "DELETE", f"{URL}/{qid}/questions/{question_id}", expect, **kw)


async def order(c, qid, ids, expect=200, **kw):
    return await call(c, "PUT", f"{URL}/{qid}/questions/order", expect, json={"question_ids": ids}, **kw)


async def approve(c, qid, ids, approved=True, expect=200, **kw):
    return await call(c, "PUT", f"{URL}/{qid}/questions/approval", expect,
                      json={"question_ids": ids, "approved": approved}, **kw)


async def quiz_with(c, *bodies) -> dict:
    """A draft with these questions, as the last reply showed it."""
    quiz = await create(c)
    for body in bodies:
        quiz = await add(c, quiz["id"], body)
    return quiz


def texts(quiz) -> list[str]:
    assert [q["position"] for q in quiz["questions"]] == list(range(len(quiz["questions"])))
    return [q["text"] for q in quiz["questions"]]


def ids(quiz) -> list[int]:
    return [q["id"] for q in quiz["questions"]]


# ── add ──────────────────────────────────────────────────────────────────────

async def test_added_questions_go_to_the_end_unapproved(shino_class):
    c = shino_class
    quiz = await quiz_with(c, mcq(" A? "), short("B?"))
    assert texts(quiz) == ["A?", "B?"] and (quiz["question_count"], quiz["approved_count"]) == (2, 0)
    first, second = quiz["questions"]
    assert {k: first[k] for k in mcq()} == mcq("A?")
    assert second["suggested_answer"] == "Because" and second["origin"] == "extended" and second["options"] is None
    assert quiz["updated_at"] > quiz["created_at"]
    assert await get(c, quiz["id"]) == quiz


@pytest.mark.parametrize("bad", [
    mcq(answer=2), mcq(options=["4"], answer=0), mcq(options=["4", "4"]), mcq(text="  "), mcq(source_page=None),
    mcq(suggested_answer="4"), short(suggested_answer=None), short(options=["a", "b"]), mcq(approved=True),
    mcq(position=0), mcq(text="x" * 1001), {"type": "essay", "text": "?"}, {},
])
async def test_a_bad_question_is_422(shino_class, bad):
    c = shino_class
    quiz = await quiz_with(c, mcq("A?"))
    await add(c, quiz["id"], bad, expect=422)
    await edit(c, quiz["id"], ids(quiz)[0], bad, expect=422)
    assert await get(c, quiz["id"]) == quiz


async def test_a_quiz_has_a_question_limit(shino_class, monkeypatch):
    c = shino_class
    monkeypatch.setattr(settings, "QUIZ_MAX_QUESTIONS", 1)
    quiz = await quiz_with(c, mcq("A?"))
    assert "at most 1" in (await add(c, quiz["id"], mcq("B?"), expect=422))["detail"]


async def test_two_lecturers_adding_at_once_get_their_own_place(shino_class):
    c = shino_class
    quiz = await create(c)
    await asyncio.gather(*(add(c, quiz["id"], mcq(f"Q{i}?")) for i in range(4)))
    assert sorted(texts(await get(c, quiz["id"]))) == ["Q0?", "Q1?", "Q2?", "Q3?"]


# ── edit and approval ────────────────────────────────────────────────────────

async def test_edit_replaces_the_whole_question(shino_class):
    c = shino_class
    quiz = await quiz_with(c, mcq("A?"), mcq("B?"))
    a, b = ids(quiz)
    edited = await edit(c, quiz["id"], b, short("B2?"))
    assert ids(edited) == [a, b] and texts(edited) == ["A?", "B2?"]
    changed = edited["questions"][1]
    assert (changed["type"], changed["suggested_answer"], changed["options"], changed["answer"]) == (
        "short", "Because", None, None)
    assert changed["source_file"] is None and changed["topic"] is None and changed["explanation"] is None
    assert edited["questions"][0] == quiz["questions"][0] and edited["updated_at"] > quiz["updated_at"]


async def test_approve_and_unapprove(shino_class):
    c = shino_class
    quiz = await quiz_with(c, mcq("A?"), mcq("B?"), mcq("C?"))
    a, b, d = ids(quiz)
    quiz = await approve(c, quiz["id"], [a, d, a])
    assert [q["approved"] for q in quiz["questions"]] == [True, False, True] and quiz["approved_count"] == 2
    quiz = await approve(c, quiz["id"], [a, b], approved=False)
    assert [q["approved"] for q in quiz["questions"]] == [False, False, True]
    # all of them or none
    await approve(c, quiz["id"], [a, 999999], expect=404)
    assert (await get(c, quiz["id"]))["approved_count"] == 1


async def test_a_changed_question_is_unapproved_and_the_same_content_is_not_a_change(shino_class):
    c = shino_class
    quiz = await quiz_with(c, mcq("A?"), mcq("B?"))
    a, b = ids(quiz)
    approved = await approve(c, quiz["id"], [a, b])
    assert await edit(c, quiz["id"], a, mcq("A?")) == approved
    edited = await edit(c, quiz["id"], a, mcq("A?", answer=0))
    assert [q["approved"] for q in edited["questions"]] == [False, True]


async def test_moving_a_question_keeps_its_approval(shino_class):
    c = shino_class
    quiz = await quiz_with(c, mcq("A?"), mcq("B?"))
    a, b = ids(quiz)
    await approve(c, quiz["id"], [b])
    moved = await order(c, quiz["id"], [b, a])
    assert [(q["text"], q["approved"]) for q in moved["questions"]] == [("B?", True), ("A?", False)]


@pytest.mark.parametrize("body", [
    {"question_ids": [], "approved": True}, {"question_ids": [1]}, {"approved": True},
    {"question_ids": [1], "approved": "yes"}, {"question_ids": [0], "approved": True},
    {"question_ids": ["x"], "approved": True}, {"question_ids": [1], "approved": None},
])
async def test_bad_approval_input_is_422(shino_class, body):
    c = shino_class
    quiz = await create(c)
    await call(c, "PUT", f"{URL}/{quiz['id']}/questions/approval", 422, json=body)


# ── delete and reorder ───────────────────────────────────────────────────────

async def test_delete_closes_the_gap(shino_class):
    c = shino_class
    quiz = await quiz_with(c, mcq("A?"), mcq("B?"), mcq("C?"))
    after = await remove(c, quiz["id"], ids(quiz)[1])
    assert texts(after) == ["A?", "C?"] and after["question_count"] == 2
    assert texts(await add(c, quiz["id"], mcq("D?"))) == ["A?", "C?", "D?"]
    await remove(c, quiz["id"], ids(quiz)[1], expect=404)


async def test_reorder(shino_class):
    c = shino_class
    quiz = await quiz_with(c, mcq("A?"), mcq("B?"), mcq("C?"))
    a, b, d = ids(quiz)
    assert texts(await order(c, quiz["id"], [d, a, b])) == ["C?", "A?", "B?"]
    assert texts(await get(c, quiz["id"])) == ["C?", "A?", "B?"]


async def test_reorder_needs_every_question_once(shino_class):
    c = shino_class
    quiz = await quiz_with(c, mcq("A?"), mcq("B?"))
    a, b = ids(quiz)
    await order(c, quiz["id"], [a, a, b], expect=422)
    for wrong in ([a], [a, b, 999999], []):
        assert "changed" in (await order(c, quiz["id"], wrong, expect=409))["detail"]
    assert await get(c, quiz["id"]) == quiz


# ── access and state ─────────────────────────────────────────────────────────

def every_call(c, qid, question_id):
    return {
        "add": lambda expect, **kw: add(c, qid, mcq("New?"), expect=expect, **kw),
        "edit": lambda expect, **kw: edit(c, qid, question_id, mcq("New?"), expect=expect, **kw),
        "delete": lambda expect, **kw: remove(c, qid, question_id, expect=expect, **kw),
        "order": lambda expect, **kw: order(c, qid, [question_id], expect=expect, **kw),
        "approve": lambda expect, **kw: approve(c, qid, [question_id], expect=expect, **kw),
        "regenerate": lambda expect, **kw: call(c, "POST", f"{URL}/{qid}/questions/{question_id}/regenerate",
                                                expect, json={}, **kw),
        "refine": lambda expect, **kw: call(c, "POST", f"{URL}/{qid}/refine", expect, json={"prompt": "x"}, **kw),
    }


@pytest.fixture(autouse=True)
def _no_llm(monkeypatch):
    from app.services.kb import llm

    async def chat(*_a, **_kw):
        raise AssertionError("no LLM call expected")

    monkeypatch.setattr(llm, "chat", chat)


async def test_only_the_courses_lecturers_reach_the_questions(shino_class):
    c = shino_class
    quiz = await quiz_with(c, mcq("A?"))
    for request in every_call(c, quiz["id"], ids(quiz)[0]).values():
        await request(403, uid=c.other_lecturer_user_id)
        await request(403, uid=c.student_user_ids[0], role="student")
    for request in every_call(c, 999999, ids(quiz)[0]).values():
        await request(403)
    assert await get(c, quiz["id"]) == quiz


async def test_a_lecturer_of_another_class_of_the_course_may_review(shino_class):
    c = shino_class
    quiz = await quiz_with(c, mcq("A?"))
    await insert(ClassOccurrence(course_id=c.course_id, type="TUTORIAL", label="T1",
                                 lecturer_id=c.other_lecturer_id))
    assert (await approve(c, quiz["id"], ids(quiz), uid=c.other_lecturer_user_id))["approved_count"] == 1


async def test_a_question_of_another_quiz_is_404(shino_class):
    c = shino_class
    mine, other = await quiz_with(c, mcq("A?")), await quiz_with(c, mcq("B?"))
    calls = every_call(c, mine["id"], ids(other)[0])
    for name in ("edit", "delete", "approve", "regenerate"):
        await calls[name](404)
    await calls["order"](409)
    assert await get(c, other["id"]) == other and await get(c, mine["id"]) == mine


@pytest.mark.parametrize("state", ["published", "closed", "attempted"])
async def test_questions_cannot_change_once_published_or_attempted(shino_class, state):
    c = shino_class
    quiz = await quiz_with(c, mcq("A?"))
    if state == "attempted":        # unpublished again, but a student has started it
        await insert(attempt_row(quiz["id"], c.student_ids[0]))
    else:
        await set_status(quiz["id"], state)
    before = await get(c, quiz["id"])
    for request in every_call(c, quiz["id"], ids(quiz)[0]).values():
        assert ("attempts" if state == "attempted" else "draft") in (await request(409))["detail"]
    assert await get(c, quiz["id"]) == before


async def test_an_attempt_starting_first_wins(shino_class):
    """The quiz row is locked: a change waits for the transaction that starts an attempt (S44)."""
    c = shino_class
    quiz = await quiz_with(c, mcq("A?"))
    async with AsyncSessionLocal() as db:
        await db.execute(update(Quiz).where(Quiz.id == quiz["id"]).values(title="locked"))
        pending = asyncio.create_task(remove(c, quiz["id"], ids(quiz)[0], expect=409))
        await asyncio.sleep(0.3)
        assert not pending.done()
        db.add(attempt_row(quiz["id"], c.student_ids[0]))
        await db.commit()
    await pending
    assert await count(QuizQuestion) == 1
