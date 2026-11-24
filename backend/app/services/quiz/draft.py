"""AI quiz draft from a lecturer's prompt (FR-601–FR-603) — S41.

1. The LLM reads the settings, question counts and topics from the prompt.
2. Passages come from the course knowledge base, only through `retrieval_api.search` (FR-814).
3. The LLM writes the questions; `checks` validates them (one corrected try).
4. Only then the draft is saved, every question unapproved (FR-604).

`LLMUnavailable` / `LLMMalformedOutput` propagate before anything is written.
"""
from __future__ import annotations

import json
import re
from collections.abc import Callable, Hashable, Iterable
from typing import TypeVar

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.class_ import Course
from app.models.quiz import TITLE_MAX_CHARS
from app.models.user import User
from app.schemas.quiz import QuestionIn, QuizCreate, QuizDetailOut, QuizDraftIn
from app.services import quiz_store
from app.services.kb import llm, retrieval_api
from app.services.kb.search import Passage
from app.services.quiz import prompts
from app.services.quiz.checks import NotCovered, PlanReply, TooFewQuestions, check_plan, check_questions

T = TypeVar("T")

SEARCH_K = 12
# Search has no filter by material or week, so it is asked for everything it can rank (30 vector +
# 30 keyword hits) and filtered here.
SEARCH_WIDE_K = 60


def _invalid(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=detail)


# ── LLM with a corrected try ─────────────────────────────────────────────────

async def ask(messages: list[dict], check: Callable[[dict], T], *, max_tokens: int) -> T:
    """The checked reply. When `check` raises a ValueError the model gets one more try, told what was
    wrong; a second ValueError is raised as it is."""
    data = await llm.chat_json(messages, max_tokens=max_tokens)
    try:
        return check(data)
    except ValueError as exc:
        problem = str(exc)
    again = prompts.correction_messages(messages, json.dumps(data, ensure_ascii=False), problem)
    return check(await llm.chat_json(again, max_tokens=max_tokens, retries=0))


# ── settings (FR-601) ────────────────────────────────────────────────────────

async def read_plan(prompt: str) -> PlanReply:
    try:
        return await ask(prompts.plan_messages(prompt, quiz_store.clock()), check_plan,
                         max_tokens=settings.QUIZ_DRAFT_PLAN_TOKENS)
    except ValueError as exc:
        raise llm.LLMMalformedOutput(f"settings: {exc}") from None


def question_counts(plan: PlanReply) -> dict[str, int]:
    """How many of each type. 422 when the prompt asks for more than one draft may have."""
    mcq, short = plan.mcq_count or 0, plan.short_count or 0
    if mcq + short == 0:
        mcq = settings.QUIZ_DRAFT_DEFAULT_QUESTIONS
    if mcq + short > settings.QUIZ_DRAFT_MAX_QUESTIONS:
        raise _invalid(f"A draft can have at most {settings.QUIZ_DRAFT_MAX_QUESTIONS} questions. "
                       "Ask for fewer; you can add more to the draft afterwards.")
    return {"mcq": mcq, "short": short}


def quiz_settings(plan: PlanReply, course: Course) -> dict:
    """The full settings of the new quiz; 422 when the prompt's settings don't fit together."""
    return quiz_store.resolve_settings(None, {
        "type": "graded",       # private and never ranked, unless the prompt says game (FR-605)
        "title": f"{course.code} quiz"[:TITLE_MAX_CHARS],
        **plan.settings(),
    })


# ── passages (FR-814) ────────────────────────────────────────────────────────

_ALIASES = {"w": "week", "wk": "week", "ch": "chapter", "chap": "chapter", "lec": "lecture", "lect": "lecture"}


def _words(text: str) -> list[str]:
    """"Wk05_Testing.pptx" -> week, 5, testing, pptx: so "week 5" finds it and "week 50" doesn't."""
    parts = re.findall(r"\d+|[^\W\d_]+", text.casefold())
    return [_ALIASES.get(p, p) if not p.isdigit() else (p.lstrip("0") or "0") for p in parts]


def in_section(passage: Passage, section: str) -> bool:
    """The passage's Moodle section or file name contains the words of `section` in a row."""
    want = _words(section)
    for name in (passage.section_name or "", passage.title):
        have = _words(name)
        if want and any(have[i:i + len(want)] == want for i in range(len(have) - len(want) + 1)):
            return True
    return False


def interleave(passages: Iterable[Passage], key: Callable[[Passage], Hashable]) -> list[Passage]:
    """Take turns between the groups, keeping each group's order, so one topic or file can't fill
    every place."""
    groups: dict[Hashable, list[Passage]] = {}
    for p in passages:
        groups.setdefault(key(p), []).append(p)
    lists = list(groups.values())
    return [g[i] for i in range(max(map(len, lists), default=0)) for g in lists if i < len(g)]


async def find_passages(course_id: int, prompt: str, plan: PlanReply,
                        material_ids: list[int] | None) -> list[Passage]:
    """The course passages to draft from; 422 when there are none.

    Chosen materials are a hard limit. Weeks or chapters named in the prompt are followed when a
    material matches; when none does, the whole course is used, unless the lecturer wants only the
    material (then drafting from another week would be wrong)."""
    narrowed = bool(material_ids or plan.sections)
    queries = list(dict.fromkeys(plan.topics + (plan.sections if narrowed else []))) or [prompt]
    found: dict[int, tuple[int, Passage]] = {}
    for n, query in enumerate(queries):
        for p in await retrieval_api.search(course_id, query, k=SEARCH_WIDE_K if narrowed else SEARCH_K):
            found.setdefault(p.chunk_id, (n, p))
    query_of = {p.chunk_id: n for n, p in found.values()}
    passages = [p for _, p in found.values()]

    if material_ids:
        passages = [p for p in passages if p.material_id in set(material_ids)]
        if not passages:
            raise _invalid("Nothing in the selected materials matches this request. Check that they are indexed.")
    if plan.sections:
        matching = [p for p in passages if any(in_section(p, s) for s in plan.sections)]
        if matching:
            passages = matching
        elif plan.only_material and not material_ids:
            raise _invalid(f"No indexed course material matches \"{', '.join(plan.sections)}\".")
        else:   # hits for the words "week 5" alone say nothing about the topic
            passages = [p for p in passages if query_of[p.chunk_id] < len(plan.topics)] or passages
    if not passages:
        raise _invalid("This course has no indexed materials for this request. Sync the course materials, "
                       "or write the questions by hand.")
    key = (lambda p: p.material_id) if material_ids else (lambda p: query_of[p.chunk_id])
    return interleave(passages, key)[:settings.QUIZ_DRAFT_MAX_PASSAGES]


# ── questions (FR-602, FR-603) ───────────────────────────────────────────────

async def write_questions(course: Course, prompt: str, passages: list[Passage], counts: dict[str, int],
                          only_material: bool) -> list[QuestionIn]:
    messages = prompts.draft_messages(f"{course.code} {course.name}", prompt, passages, mcq=counts["mcq"],
                                      short=counts["short"], only_material=only_material)

    def check(data: dict) -> list[QuestionIn]:
        return check_questions(data, passages, counts=counts, only_material=only_material)

    try:
        return await ask(messages, check, max_tokens=settings.QUIZ_DRAFT_OUTPUT_TOKENS)
    except NotCovered:
        raise _invalid("The course material doesn't cover this request. Change the topic, or allow "
                       "questions beyond the material.") from None
    except TooFewQuestions as exc:
        if only_material:
            raise _invalid("The course material is too short for that many questions. Ask for fewer, or allow "
                           "questions beyond the material.") from None
        raise llm.LLMMalformedOutput(f"questions: {exc}") from None
    except ValueError as exc:
        raise llm.LLMMalformedOutput(f"questions: {exc}") from None


async def create_draft(db: AsyncSession, actor: User, body: QuizDraftIn) -> QuizDetailOut:
    await quiz_store.ensure_teaches_course(db, actor, body.course_id)
    course = await db.get(Course, body.course_id)
    await db.commit()       # nothing written yet: give the connection back while the LLM works

    plan = await read_plan(body.prompt)
    counts = question_counts(plan)
    values = quiz_settings(plan, course)
    only_material = bool(plan.only_material)
    passages = await find_passages(course.id, body.prompt, plan, body.material_ids)
    questions = await write_questions(course, body.prompt, passages, counts, only_material)
    # create() checks the course access again: it may have changed while the LLM worked
    return await quiz_store.create(db, actor, QuizCreate(course_id=course.id, **values), questions)
