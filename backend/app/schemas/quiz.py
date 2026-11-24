"""Quiz settings and questions (FR-603–FR-606) — S40."""
from datetime import datetime
from typing import Annotated, Literal, Optional

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, StrictInt, model_validator

from app.core.timezone import MYT
from app.models.quiz import (
    EXPLANATION_MAX_CHARS,
    MAX_OPTIONS,
    MIN_OPTIONS,
    OPTION_MAX_CHARS,
    QUESTION_TEXT_MAX_CHARS,
    SOURCE_FILE_MAX_CHARS,
    SUGGESTED_ANSWER_MAX_CHARS,
    TIMER_LIMITS,
    TITLE_MAX_CHARS,
    TOPIC_MAX_CHARS,
)

QuizType = Literal["game", "graded"]
QuizStatus = Literal["draft", "published", "closed"]
TimerMode = Literal["question", "quiz"]
Release = Literal["manual", "on_close"]
SourceType = Literal["page", "slide", "section"]

_MAX_ID = 2**31 - 1


def _no_nul(v: str) -> str:
    if "\x00" in v:     # Postgres text can't hold it
        raise ValueError("Text contains an invalid character")
    return v.strip()


def _required(v: str) -> str:
    v = _no_nul(v)
    if not v:
        raise ValueError("Text can't be empty")
    return v


def _optional(v: Optional[str]) -> Optional[str]:
    return (_no_nul(v) or None) if v is not None else None


def _myt(v: Optional[datetime]) -> Optional[datetime]:
    """Times are stored as naive Malaysia time; one sent with an offset is converted."""
    if v is None or v.tzinfo is None:
        return v
    try:
        return v.astimezone(MYT).replace(tzinfo=None)
    except OverflowError:
        raise ValueError("Time is out of range") from None


Title = Annotated[str, Field(min_length=1, max_length=TITLE_MAX_CHARS), AfterValidator(_required)]
Moment = Annotated[Optional[datetime], AfterValidator(_myt)]
# the limit for the quiz's own timer mode is checked by the service (the mode may be stored)
Seconds = Annotated[int, Field(ge=min(lo for lo, _ in TIMER_LIMITS.values()),
                               le=max(hi for _, hi in TIMER_LIMITS.values()))]


class QuizCreate(BaseModel):
    """Unset settings get their defaults. A game quiz always ends up with a per-question timer."""
    model_config = ConfigDict(extra="forbid")
    course_id: int = Field(ge=1, le=_MAX_ID)
    title: Title
    type: QuizType
    timer_mode: TimerMode = None
    timer_seconds: Seconds = None
    opens_at: Moment = None
    closes_at: Moment = None
    shuffle: bool = None
    release: Release = None
    release_marks: bool = None
    release_answers: bool = None
    speed_bonus: bool = None


class QuizUpdate(BaseModel):
    """Only the given fields change. `null` clears `opens_at`/`closes_at` and is refused elsewhere
    (the None defaults only mean "not given")."""
    model_config = ConfigDict(extra="forbid")
    title: Title = None
    type: QuizType = None
    timer_mode: TimerMode = None
    timer_seconds: Seconds = None
    opens_at: Moment = None
    closes_at: Moment = None
    shuffle: bool = None
    release: Release = None
    release_marks: bool = None
    release_answers: bool = None
    speed_bonus: bool = None


DRAFT_PROMPT_MAX_CHARS = 2000
MAX_DRAFT_MATERIALS = 50
_MaterialId = Annotated[int, Field(ge=1, le=_MAX_ID)]


class QuizDraftIn(BaseModel):
    """FR-601: what the lecturer wants, in their own words. With `material_ids` the questions come
    from those materials only (Module 8's `material_id`s of the course)."""
    model_config = ConfigDict(extra="forbid")
    course_id: int = Field(ge=1, le=_MAX_ID)
    prompt: Annotated[str, Field(min_length=1, max_length=DRAFT_PROMPT_MAX_CHARS), AfterValidator(_required)]
    material_ids: Optional[Annotated[list[_MaterialId], Field(min_length=1, max_length=MAX_DRAFT_MATERIALS)]] = None


class QuestionIn(BaseModel):
    """A whole question, from the AI draft (S41) or the lecturer (S42). Approval is a separate
    step, never part of the content."""
    model_config = ConfigDict(extra="forbid")
    type: Literal["mcq", "short"]
    text: Annotated[str, Field(min_length=1, max_length=QUESTION_TEXT_MAX_CHARS), AfterValidator(_required)]
    options: Optional[list[Annotated[str, Field(max_length=OPTION_MAX_CHARS), AfterValidator(_required)]]] = None
    answer: Optional[StrictInt] = None                  # MCQ: index of the correct option
    suggested_answer: Annotated[Optional[str], Field(max_length=SUGGESTED_ANSWER_MAX_CHARS),
                                AfterValidator(_optional)] = None
    topic: Annotated[Optional[str], Field(max_length=TOPIC_MAX_CHARS), AfterValidator(_optional)] = None
    origin: Literal["from_material", "extended"] = "extended"
    source_file: Annotated[Optional[str], Field(max_length=SOURCE_FILE_MAX_CHARS),
                           AfterValidator(_optional)] = None
    source_type: Optional[SourceType] = None
    source_page: Optional[int] = Field(default=None, ge=1, le=_MAX_ID)
    explanation: Annotated[Optional[str], Field(max_length=EXPLANATION_MAX_CHARS),
                           AfterValidator(_optional)] = None

    @model_validator(mode="after")
    def _shape(self) -> "QuestionIn":
        if self.type == "mcq":
            if self.options is None or not MIN_OPTIONS <= len(self.options) <= MAX_OPTIONS:
                raise ValueError(f"A multiple-choice question needs {MIN_OPTIONS} to {MAX_OPTIONS} options")
            if len({o.casefold() for o in self.options}) != len(self.options):
                raise ValueError("Options must be different")
            if self.answer is None or not 0 <= self.answer < len(self.options):
                raise ValueError("The answer must be one of the options")
            if self.suggested_answer is not None:
                raise ValueError("A multiple-choice question has no suggested answer")
        else:
            if self.options is not None or self.answer is not None:
                raise ValueError("A short-answer question has no options")
            if self.suggested_answer is None:
                raise ValueError("A short-answer question needs a suggested answer")
        if self.origin == "from_material" and None in (self.source_file, self.source_type, self.source_page):
            raise ValueError("A question from the material must name its source file and page or slide")
        return self


class QuestionOut(BaseModel):
    """Lecturer view: carries the answer, so it must never go to a student (NFR-41)."""
    model_config = ConfigDict(from_attributes=True)
    id: int
    position: int
    type: Literal["mcq", "short"]
    text: str
    options: Optional[list[str]]
    answer: Optional[int]
    suggested_answer: Optional[str]
    topic: Optional[str]
    origin: Literal["from_material", "extended"]
    source_file: Optional[str]
    source_type: Optional[SourceType]
    source_page: Optional[int]
    explanation: Optional[str]
    approved: bool


class QuizOut(BaseModel):
    id: int
    course_id: int
    course_code: str
    course_name: str
    title: str
    type: QuizType
    status: QuizStatus
    timer_mode: TimerMode
    timer_seconds: int
    opens_at: Optional[datetime]
    closes_at: Optional[datetime]
    shuffle: bool
    release: Release
    release_marks: bool
    release_answers: bool
    speed_bonus: bool
    question_count: int
    approved_count: int
    created_at: datetime
    updated_at: datetime


class QuizDetailOut(QuizOut):
    questions: list[QuestionOut]


class QuizListOut(BaseModel):
    quizzes: list[QuizOut]
