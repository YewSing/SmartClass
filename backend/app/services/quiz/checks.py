"""Validation of what the LLM returns for a quiz draft (FR-601–FR-603, S41), its changes (FR-604, S42)
and the grades of short answers (FR-616, S45).

Everything the model says is checked here before anything is saved. A `ValueError` message is sent
back to the model for its one corrected try, so it says plainly what is wrong.
"""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Annotated, Literal, Optional

from pydantic import BaseModel, Field, ValidationError

from app.models.quiz import QUESTION_TYPES, REASON_MAX_CHARS, TITLE_MAX_CHARS
from app.schemas.quiz import Moment, QuestionIn, QuizType, TimerMode
from app.services.kb.search import Passage

MAX_TOPICS = 5
MAX_SECTIONS = 5


class TooFewQuestions(ValueError):
    """Every question is fine, but there are fewer than asked for."""


class NotCovered(Exception):
    """"Only the material" and the model says the material doesn't cover the request."""


def describe(exc: ValidationError) -> str:
    """A pydantic error without the rejected values."""
    out = []
    for e in exc.errors(include_input=False, include_url=False):
        where = ".".join(str(part) for part in e["loc"])
        out.append(f"{where}: {e['msg']}" if where else e["msg"])
    return "; ".join(out)


# ── settings read from the prompt (FR-601) ───────────────────────────────────

Count = Annotated[int, Field(ge=0, le=1000)]


class PlanReply(BaseModel):
    """None = the prompt doesn't say. Unknown keys are ignored."""
    title: Optional[str] = None
    type: Optional[QuizType] = None
    mcq_count: Optional[Count] = None
    short_count: Optional[Count] = None
    timer_mode: Optional[TimerMode] = None
    timer_seconds: Optional[Annotated[int, Field(ge=1, le=10**6)]] = None
    opens_at: Moment = None
    closes_at: Moment = None
    shuffle: Optional[bool] = None
    only_material: Optional[bool] = None
    topics: Optional[list[str]] = None
    sections: Optional[list[str]] = None

    def settings(self) -> dict:
        """The quiz settings the prompt gives (FR-606), ready for `quiz_store.resolve_settings`."""
        given = {name: getattr(self, name)
                 for name in ("type", "timer_mode", "timer_seconds", "opens_at", "closes_at", "shuffle")}
        out = {name: value for name, value in given.items() if value is not None}
        title = " ".join((self.title or "").replace("\x00", "").split())[:TITLE_MAX_CHARS].strip()
        if title:
            out["title"] = title
        return out


def _clean(items: list[str] | None, limit: int) -> list[str]:
    cleaned = (" ".join(i.replace("\x00", "").split()) for i in items or [])
    return list(dict.fromkeys(i for i in cleaned if i))[:limit]


def check_plan(data: dict) -> PlanReply:
    try:
        plan = PlanReply.model_validate(data)
    except ValidationError as exc:
        raise ValueError(describe(exc)) from None
    if plan.timer_seconds is not None and plan.timer_mode is None and plan.type != "game":
        raise ValueError('"timer_seconds" needs "timer_mode"')   # a game's time is always per question
    plan.topics = _clean(plan.topics, MAX_TOPICS)
    plan.sections = _clean(plan.sections, MAX_SECTIONS)
    return plan


# ── drafted questions (FR-602, FR-603) ───────────────────────────────────────

class _Reply(BaseModel):
    questions: list[dict]


class _Extra(BaseModel):
    """What the model adds to a question besides the question itself."""
    answer_text: Optional[str] = None
    topic: str
    origin: Literal["from_material", "extended"]
    source: Optional[int] = None
    explanation: str


_CONTENT = ("type", "text", "options", "answer", "suggested_answer")


def check_question(raw: dict, passages: list[Passage], *, only_material: bool) -> QuestionIn:
    """One drafted question with its source filled in from the passage it cites."""
    try:
        extra = _Extra.model_validate(raw)
    except ValidationError as exc:
        raise ValueError(describe(exc)) from None
    if not extra.topic.strip():
        raise ValueError('"topic" is empty')
    explanation = extra.explanation.strip()
    if not explanation:
        raise ValueError('"explanation" is empty')
    if only_material and extra.origin != "from_material":
        raise ValueError('"origin" must be "from_material": the lecturer wants only the material')
    if extra.source is not None and not 1 <= extra.source <= len(passages):
        raise ValueError(f'"source" must be a passage number from 1 to {len(passages)}')
    if extra.origin == "from_material" and extra.source is None:
        raise ValueError('a "from_material" question needs its "source" passage number')

    values = {k: raw[k] for k in _CONTENT if raw.get(k) not in (None, "", [])}   # models pad unused fields
    values |= {"topic": extra.topic, "origin": extra.origin}
    if extra.source is not None:
        p = passages[extra.source - 1]
        values |= {"source_file": p.title, "source_type": p.location_type, "source_page": p.location_start}
        # The citation is written here, not by the model, so it can't name a source that doesn't exist.
        label = "Source" if extra.origin == "from_material" else "Related material"
        explanation = f"{explanation}\n({label}: {p.title}, {p.location_label})"
    try:
        question = QuestionIn.model_validate({**values, "explanation": explanation})
    except ValidationError as exc:
        raise ValueError(describe(exc)) from None
    if question.type == "mcq":
        chosen = question.options[question.answer]
        if (extra.answer_text or "").strip().casefold() != chosen.casefold():
            raise ValueError(f'"answer" ({question.answer}) and "answer_text" must be the same option; '
                             '"answer" counts from 0')
    return question


def text_key(text: str) -> str:
    """Two questions with the same key are the same question."""
    return " ".join(text.casefold().split())


def check_questions(data: dict, passages: list[Passage], *, counts: dict[str, int], only_material: bool,
                    taken: Iterable[str] = ()) -> list[QuestionIn]:
    """The drafted questions, exactly `counts[type]` of each type (any extra ones are left out), none
    of them with a text that is `taken` already."""
    try:
        reply = _Reply.model_validate(data)
    except ValidationError as exc:
        raise ValueError(describe(exc)) from None
    if only_material and not reply.questions:
        raise NotCovered
    problems: list[str] = []
    kept: list[QuestionIn] = []
    left = dict(counts)
    in_quiz = {text_key(t) for t in taken}
    seen: set[str] = set()
    for n, raw in enumerate(reply.questions, start=1):
        kind = raw.get("type")
        if kind in QUESTION_TYPES and left.get(kind, 0) == 0:
            continue
        try:
            question = check_question(raw, passages, only_material=only_material)
            key = text_key(question.text)
            if key in seen:
                raise ValueError("the same question appears twice")
            if key in in_quiz:
                raise ValueError("this question is already in the quiz")
        except ValueError as exc:
            problems.append(f"Question {n}: {exc}")
            continue
        seen.add(key)
        left[question.type] -= 1
        kept.append(question)
    if problems:
        raise ValueError("\n".join(problems))
    if any(left.values()):
        missing = " and ".join(f"{n} more {kind}" for kind, n in left.items() if n)
        raise TooFewQuestions(f"There must be exactly {counts['mcq']} mcq and {counts['short']} short "
                              f"questions: write {missing}")
    return kept


# ── changes to a draft (FR-604) ──────────────────────────────────────────────

class RefinePlan(BaseModel):
    """What a refine request is about, to search the materials. `only_material` None = it doesn't say."""
    questions: list[int] = []
    topics: list[str] = []
    sections: list[str] = []
    only_material: Optional[bool] = None


def check_refine_plan(data: dict, total: int) -> RefinePlan:
    """The plan; numbers of questions that don't exist are left out (they only steer the search)."""
    given = {k: v for k, v in data.items() if v is not None} if isinstance(data, dict) else data
    try:
        plan = RefinePlan.model_validate(given)
    except ValidationError as exc:
        raise ValueError(describe(exc)) from None
    plan.questions = [n for n in dict.fromkeys(plan.questions) if 1 <= n <= total]
    plan.topics = _clean(plan.topics, MAX_TOPICS)
    plan.sections = _clean(plan.sections, MAX_SECTIONS)
    return plan


class _Change(BaseModel):
    action: Literal["replace", "remove", "add"]
    number: Optional[int] = None
    question: Optional[dict] = None


class _Changes(BaseModel):
    changes: list[_Change]


@dataclass
class Changes:
    """Checked changes to a draft: question numbers count from 1 in the draft's order."""
    replaced: dict[int, QuestionIn] = field(default_factory=dict)
    removed: set[int] = field(default_factory=set)
    added: list[QuestionIn] = field(default_factory=list)


def check_changes(data: dict, passages: list[Passage], texts: list[str], *, only_material: bool) -> Changes:
    """The changes to a draft whose questions have these `texts`; every new question is checked like
    a drafted one. Empty when the model says there is nothing to change."""
    try:
        reply = _Changes.model_validate(data)
    except ValidationError as exc:
        raise ValueError(describe(exc)) from None
    problems: list[str] = []
    out = Changes()
    new: list[tuple[int, QuestionIn]] = []      # (its place in the reply, question)
    for n, change in enumerate(reply.changes, start=1):
        try:
            if change.action != "add":
                if change.number is None or not 1 <= change.number <= len(texts):
                    raise ValueError(f'"number" must be a question number from 1 to {len(texts)}')
                if change.number in out.removed or change.number in out.replaced:
                    raise ValueError(f"question {change.number} is listed twice")
            if change.action == "remove":
                out.removed.add(change.number)
                continue
            if change.question is None:
                raise ValueError('"question" is missing')
            question = check_question(change.question, passages, only_material=only_material)
        except ValueError as exc:
            problems.append(f"Change {n}: {exc}")
            continue
        new.append((n, question))
        if change.action == "add":
            out.added.append(question)
        else:
            out.replaced[change.number] = question
    seen = {text_key(t) for i, t in enumerate(texts, start=1) if i not in out.removed and i not in out.replaced}
    for n, question in new:
        key = text_key(question.text)
        if key in seen:
            problems.append(f"Change {n}: this question is already in the quiz")
        seen.add(key)
    if reply.changes and not problems and not seen:
        problems.append("The quiz must keep at least one question")
    if problems:
        raise ValueError("\n".join(problems))
    return out


# ── grades of short answers (FR-616) ─────────────────────────────────────────

_Share = Annotated[float, Field(strict=True, ge=0, le=1, allow_inf_nan=False)]


class Grade(BaseModel):
    number: int
    score: _Share           # a share of the question's mark
    reason: str
    confidence: _Share      # how sure the model is of the score


class _Grades(BaseModel):
    grades: list[Grade]


def check_grades(data: dict, total: int) -> list[Grade]:
    """The grades of answers 1 to `total`, in that order, each with a reason."""
    try:
        reply = _Grades.model_validate(data)
    except ValidationError as exc:
        raise ValueError(describe(exc)) from None
    if sorted(g.number for g in reply.grades) != list(range(1, total + 1)):
        raise ValueError(f'"grades" must have exactly one grade for each number from 1 to {total}')
    for g in reply.grades:
        g.reason = " ".join(g.reason.replace("\x00", "").split())[:REASON_MAX_CHARS].strip()
        if not g.reason:
            raise ValueError(f'grade {g.number}: "reason" is empty')
    return sorted(reply.grades, key=lambda g: g.number)
