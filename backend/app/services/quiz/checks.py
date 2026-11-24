"""Validation of what the LLM returns for a quiz draft (FR-601–FR-603) — S41.

Everything the model says is checked here before anything is saved. A `ValueError` message is sent
back to the model for its one corrected try, so it says plainly what is wrong.
"""
from __future__ import annotations

from typing import Annotated, Literal, Optional

from pydantic import BaseModel, Field, ValidationError

from app.models.quiz import QUESTION_TYPES, TITLE_MAX_CHARS
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


def check_questions(data: dict, passages: list[Passage], *, counts: dict[str, int],
                    only_material: bool) -> list[QuestionIn]:
    """The drafted questions, exactly `counts[type]` of each type (any extra ones are left out)."""
    try:
        reply = _Reply.model_validate(data)
    except ValidationError as exc:
        raise ValueError(describe(exc)) from None
    if only_material and not reply.questions:
        raise NotCovered
    problems: list[str] = []
    kept: list[QuestionIn] = []
    left = dict(counts)
    seen: set[str] = set()
    for n, raw in enumerate(reply.questions, start=1):
        kind = raw.get("type")
        if kind in QUESTION_TYPES and left.get(kind, 0) == 0:
            continue
        try:
            question = check_question(raw, passages, only_material=only_material)
            key = " ".join(question.text.casefold().split())
            if key in seen:
                raise ValueError("the same question appears twice")
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
