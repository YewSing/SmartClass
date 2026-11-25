"""Changing a draft with the AI (FR-604) — S42.

- `regenerate` writes one new question in place of another, of the same type.
- `refine` follows a further prompt ("make question 3 harder"): the LLM says what the request is
  about, passages are found for that, and it replies with a list of changes. Questions it doesn't
  list are never touched.

Both keep to the quiz's `ai_scope` (chosen materials, named weeks, "only the material"); a refine
prompt that says otherwise about "only the material" changes it for the quiz. What the AI writes is
checked like a new draft and is unapproved.

No lock or transaction is held while the LLM works. The draft is compared afterwards, under the
lock: if someone changed it meanwhile, nothing is saved (409).
"""
from __future__ import annotations

from dataclasses import dataclass

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.class_ import Course
from app.models.quiz import Quiz, QuizQuestion
from app.models.user import User
from app.schemas.quiz import AiScope, QuestionOut, QuestionRegenerateIn, QuizDetailOut, QuizRefineIn
from app.services import quiz_questions, quiz_store
from app.services.kb import llm
from app.services.kb.search import Passage
from app.services.quiz import prompts
from app.services.quiz.checks import Changes, PlanReply, RefinePlan, check_changes, check_refine_plan
from app.services.quiz.draft import ask, find_passages, interleave, write_questions


# ── the draft, before and after the LLM works ────────────────────────────────

@dataclass(frozen=True)
class Draft:
    course: Course
    scope: AiScope
    questions: list[QuestionOut]


async def _read(db: AsyncSession, actor: User, quiz_id: int) -> Draft:
    """The draft as it is now; 403 / 409 as for any change. The caller commits, which frees the lock."""
    quiz = await quiz_store.editable(db, actor, quiz_id)
    return Draft(
        course=await db.get(Course, quiz.course_id),
        scope=AiScope.model_validate(quiz.ai_scope or {}),
        questions=[QuestionOut.model_validate(q) for q in await quiz_store.questions_of(db, quiz.id)])


async def _lock(db: AsyncSession, actor: User, quiz_id: int) -> tuple[Quiz, list[QuizQuestion]]:
    quiz = await quiz_store.editable(db, actor, quiz_id)
    return quiz, await quiz_store.questions_of(db, quiz.id)


def _same(row: QuizQuestion, seen: QuestionOut) -> bool:
    """The question still reads as it did (its place and approval may have changed)."""
    return row.id == seen.id and quiz_questions.content(row) == seen.model_dump(include=set(quiz_questions.CONTENT))


def _changed() -> HTTPException:
    return HTTPException(status.HTTP_409_CONFLICT,
                         detail="The draft was changed while the AI was working. Check it and try again.")


def _query(q: QuestionOut) -> str:
    return f"{q.topic} {q.text}" if q.topic else q.text


# ── one question ─────────────────────────────────────────────────────────────

async def regenerate(db: AsyncSession, actor: User, quiz_id: int, question_id: int,
                     body: QuestionRegenerateIn) -> QuizDetailOut:
    draft = await _read(db, actor, quiz_id)
    old = quiz_questions.find(draft.questions, question_id)
    await db.commit()

    scope = draft.scope
    topics = list(dict.fromkeys([_query(old)] + ([body.instruction] if body.instruction else [])))
    plan = PlanReply(topics=topics, sections=scope.sections, only_material=scope.only_material)
    passages = await find_passages(draft.course.id, old.text, plan, scope.material_ids)
    others = [q.text for q in draft.questions if q.id != old.id]
    counts = {"mcq": 0, "short": 0, old.type: 1}
    [new] = await write_questions(draft.course, prompts.regenerate_request(old, others, body.instruction), passages,
                                  counts, scope.only_material, taken=[old.text, *others])

    quiz, rows = await _lock(db, actor, quiz_id)
    row = next((r for r in rows if r.id == old.id), None)
    if row is None or not _same(row, old):
        raise _changed()
    quiz_questions.put(quiz, row, new)
    return await quiz_questions.saved(db, quiz)


# ── the whole draft ──────────────────────────────────────────────────────────

async def read_request(prompt: str, questions: list[QuestionOut]) -> RefinePlan:
    try:
        return await ask(prompts.refine_plan_messages(prompt, questions),
                         lambda data: check_refine_plan(data, len(questions)),
                         max_tokens=settings.QUIZ_DRAFT_PLAN_TOKENS)
    except ValueError as exc:
        raise llm.LLMMalformedOutput(f"request: {exc}") from None


async def request_passages(course_id: int, prompt: str, plan: RefinePlan, questions: list[QuestionOut],
                           scope: AiScope) -> list[Passage]:
    """Passages for the questions the request changes and for the topics or weeks it names, taking
    turns. A week named in the request replaces the quiz's own weeks, but for its topics only."""
    async def find(topics: list[str], sections: list[str]) -> list[Passage]:
        reply = PlanReply(topics=list(dict.fromkeys(topics)), sections=sections, only_material=scope.only_material)
        return await find_passages(course_id, prompt, reply, scope.material_ids)

    groups = []
    changed = [_query(questions[n - 1]) for n in plan.questions][:settings.QUIZ_DRAFT_MAX_PASSAGES]
    if changed:
        groups.append(await find(changed, scope.sections))
    if plan.topics or plan.sections or not changed:
        groups.append(await find(plan.topics, plan.sections or scope.sections))
    group_of: dict[int, int] = {}
    unique: dict[int, Passage] = {}
    for n, group in enumerate(groups):
        for p in group:
            group_of.setdefault(p.chunk_id, n)
            unique.setdefault(p.chunk_id, p)
    return interleave(unique.values(), lambda p: group_of[p.chunk_id])[:settings.QUIZ_DRAFT_MAX_PASSAGES]


async def write_changes(draft: Draft, prompt: str, passages: list[Passage], only_material: bool) -> Changes:
    messages = prompts.refine_messages(f"{draft.course.code} {draft.course.name}", prompt, draft.questions, passages,
                                       only_material=only_material)
    texts = [q.text for q in draft.questions]
    try:
        changes = await ask(messages, lambda data: check_changes(data, passages, texts, only_material=only_material),
                            max_tokens=settings.QUIZ_DRAFT_OUTPUT_TOKENS)
    except ValueError as exc:
        raise llm.LLMMalformedOutput(f"changes: {exc}") from None
    if not (changes.replaced or changes.removed or changes.added):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail=(
            "The AI found nothing to change for this request" +
            (", or the course material doesn't cover it" if only_material else "") +
            ". Say which questions to change, or edit them by hand."))
    return changes


async def refine(db: AsyncSession, actor: User, quiz_id: int, body: QuizRefineIn) -> QuizDetailOut:
    draft = await _read(db, actor, quiz_id)
    await db.commit()

    plan = await read_request(body.prompt, draft.questions)
    scope = draft.scope
    if plan.only_material is not None:
        scope = scope.model_copy(update={"only_material": plan.only_material})
    passages = await request_passages(draft.course.id, body.prompt, plan, draft.questions, scope)
    changes = await write_changes(draft, body.prompt, passages, scope.only_material)

    quiz, rows = await _lock(db, actor, quiz_id)
    if len(rows) != len(draft.questions) or not all(map(_same, rows, draft.questions)):
        raise _changed()
    kept = [row for n, row in enumerate(rows, start=1) if n not in changes.removed]
    quiz_questions.ensure_room(len(kept) + len(changes.added))
    for n, new in changes.replaced.items():
        quiz_questions.put(quiz, rows[n - 1], new)
    for n in changes.removed:
        await quiz_questions.remove(db, quiz, rows[n - 1])
    quiz_questions.renumber(quiz, kept)
    for i, new in enumerate(changes.added, start=len(kept)):
        quiz_questions.append(db, quiz, i, new)
    if scope != draft.scope:
        quiz.ai_scope = scope.model_dump()
    return await quiz_questions.saved(db, quiz)
