from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.interaction import (
    CONFUSION_TOPIC_MAX_CHARS,
    POLL_MAX_OPTIONS,
    POLL_MIN_OPTIONS,
    POLL_OPTION_MAX_CHARS,
    POLL_QUESTION_MAX_CHARS,
    QUESTION_MAX_CHARS,
    QUICK_ANSWER_MAX_CHARS,
    QUICK_PROMPT_MAX_CHARS,
)


class InteractionSessionOut(BaseModel):
    """The interaction of one class session as the caller sees it (S30)."""
    attendance_session_id: int
    occurrence_id: Optional[int]
    course_code: Optional[str]
    course_name: Optional[str]
    class_status: str                               # M3 session status
    status: Literal["open", "closed"]               # effective: open only while the class is open
    closed_reason: Optional[Literal["lecturer", "class_ended", "not_started"]]
    opened_at: Optional[datetime]
    closed_at: Optional[datetime]
    role: Literal["lecturer", "student"]            # the caller's role in this class


# ── live questions (S31, FR-503–FR-506) ─────────────────────────────────────────

class QuestionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str = Field(min_length=1, max_length=QUESTION_MAX_CHARS)
    anonymous: bool = False

    @field_validator("text")
    @classmethod
    def _strip(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Question can't be empty")
        return v


class QuestionModerate(BaseModel):
    """Lecturer moderation: any of the three flags; unset fields are left as they are."""
    model_config = ConfigDict(extra="forbid")
    answered: Optional[bool] = None
    pinned: Optional[bool] = None
    hidden: Optional[bool] = None


class QuestionOut(BaseModel):
    """A question as one caller sees it. No student/user id ever; `author_name` is null for an
    anonymous question to everyone, and `mine` is true only for the asker."""
    id: int
    attendance_session_id: int
    text: str
    anonymous: bool
    author_name: Optional[str]
    mine: bool
    upvotes: int
    upvoted_by_me: bool
    answered: bool
    answered_at: Optional[datetime]
    pinned: bool
    hidden: bool                                    # always false for students (they never get hidden ones)
    created_at: datetime


class QuestionListOut(BaseModel):
    attendance_session_id: int
    status: Literal["open", "closed"]               # effective interaction state
    questions: list[QuestionOut]


# ── live polls (S32, FR-507–FR-509) ─────────────────────────────────────────────

def _clean(v: str, what: str) -> str:
    v = v.strip()
    if not v:
        raise ValueError(f"{what} can't be empty")
    return v


class PollCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question: str = Field(min_length=1, max_length=POLL_QUESTION_MAX_CHARS)
    options: list[str] = Field(min_length=POLL_MIN_OPTIONS, max_length=POLL_MAX_OPTIONS)
    multiple: bool = False
    show_results: bool = False

    @field_validator("question")
    @classmethod
    def _q(cls, v: str) -> str:
        return _clean(v, "Question")

    @field_validator("options")
    @classmethod
    def _opts(cls, v: list[str]) -> list[str]:
        out = []
        for o in v:
            o = _clean(o, "Option")
            if len(o) > POLL_OPTION_MAX_CHARS:
                raise ValueError(f"An option can be at most {POLL_OPTION_MAX_CHARS} characters")
            out.append(o)
        if len({o.casefold() for o in out}) != len(out):
            raise ValueError("Options must be different")
        return out


class PollUpdate(BaseModel):
    """Lecturer chooses whether students see the results (FR-509)."""
    model_config = ConfigDict(extra="forbid")
    show_results: bool


class PollVoteIn(BaseModel):
    """The student's whole choice; it replaces any earlier vote on this poll (FR-508)."""
    model_config = ConfigDict(extra="forbid")
    option_ids: list[int] = Field(min_length=1, max_length=POLL_MAX_OPTIONS)


class PollOptionOut(BaseModel):
    id: int
    text: str
    votes: Optional[int]                            # null for students while results are hidden


class PollOut(BaseModel):
    """A poll as one caller sees it. Never who voted for what; `my_option_ids` is the caller's own
    vote (always [] for the lecturer)."""
    id: int
    attendance_session_id: int
    question: str
    multiple: bool
    status: Literal["draft", "open", "closed"]      # effective: open only while the interaction is
    show_results: bool
    options: list[PollOptionOut]
    total_voters: Optional[int]                     # null for students while results are hidden
    my_option_ids: list[int]
    created_at: datetime
    started_at: Optional[datetime]
    closed_at: Optional[datetime]


class PollListOut(BaseModel):
    attendance_session_id: int
    status: Literal["open", "closed"]               # effective interaction state
    polls: list[PollOut]


# ── quick questions, reactions, confusion (S33, FR-510–FR-515) ──────────────────

class QuickQuestionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    prompt: str = Field(min_length=1, max_length=QUICK_PROMPT_MAX_CHARS)
    max_chars: Optional[int] = Field(default=None, ge=1, le=QUICK_ANSWER_MAX_CHARS)  # null = setting

    @field_validator("prompt")
    @classmethod
    def _p(cls, v: str) -> str:
        return _clean(v, "Question")


class QuickAnswerIn(BaseModel):
    """The student's answer; it replaces their earlier one while the quick question is open. The
    length limit is the quick question's `max_chars` (422 above it)."""
    model_config = ConfigDict(extra="forbid")
    text: str = Field(min_length=1, max_length=QUICK_ANSWER_MAX_CHARS)

    @field_validator("text")
    @classmethod
    def _t(cls, v: str) -> str:
        return _clean(v, "Answer")


class QuickAnswerOut(BaseModel):
    """One answer in the lecturer's list. No student identity (anonymous, FR-510)."""
    id: int
    text: str
    created_at: datetime


class QuickQuestionOut(BaseModel):
    """A quick question as one caller sees it: the lecturer gets every answer (no names), a
    student only their own `my_answer`; `answers`/`answer_count` are null for students."""
    id: int
    attendance_session_id: int
    prompt: str
    max_chars: int
    status: Literal["open", "closed"]               # effective: open only while the interaction is
    answer_count: Optional[int]
    answers: Optional[list[QuickAnswerOut]]
    my_answer: Optional[str]
    created_at: datetime
    closed_at: Optional[datetime]


class QuickQuestionListOut(BaseModel):
    attendance_session_id: int
    status: Literal["open", "closed"]
    quick_questions: list[QuickQuestionOut]


ReactionKind = Literal["thumbs_up", "clear", "too_fast", "too_slow"]


class ReactionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: ReactionKind


class ReactionAck(BaseModel):
    """What the student gets back: their reaction and when the next one is allowed."""
    kind: ReactionKind
    created_at: datetime
    next_allowed_at: datetime


class ReactionCountsOut(BaseModel):
    """Running counts for the lecturer (FR-511). No identity."""
    attendance_session_id: int
    status: Literal["open", "closed"]
    counts: dict[str, int]                          # every kind, 0 when none
    total: int


class ConfusionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    topic: Optional[str] = Field(default=None, max_length=CONFUSION_TOPIC_MAX_CHARS)

    @field_validator("topic")
    @classmethod
    def _topic(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        return " ".join(v.split()) or None


class ConfusionAck(BaseModel):
    created_at: datetime
    next_allowed_at: datetime


class ConfusionBucket(BaseModel):
    start: datetime                                 # bucket start (naive MYT)
    count: int


class ConfusionTopicCount(BaseModel):
    topic: str
    count: int


class ConfusionOut(BaseModel):
    """The lecturer's confusion view (FR-512, FR-515): aggregates only, never who pressed."""
    attendance_session_id: int
    status: Literal["open", "closed"]
    total: int                                      # presses this class
    recent: int                                     # presses within the spike window
    recent_students: int                            # distinct students within the window
    class_size: int
    window_seconds: int
    spike_active: bool
    spikes: int                                     # spikes raised this class
    timeline: list[ConfusionBucket]                 # oldest first, non-empty buckets only
    topics: list[ConfusionTopicCount]               # most pressed first


# ── after class (S36, FR-518–FR-520) ────────────────────────────────────────────

class SummaryQuestionCounts(BaseModel):
    asked: int                                      # every question, hidden and anonymous included
    answered: int
    anonymous: int
    hidden: int
    upvotes: int


class SummaryQuickQuestion(BaseModel):
    """A quick question in the summary: answers without names (FR-510)."""
    id: int
    prompt: str
    status: Literal["open", "closed"]
    answer_count: int
    answers: list[QuickAnswerOut]
    created_at: datetime


class SummaryConfusion(BaseModel):
    """Confusion aggregates only (FR-515)."""
    total: int
    spikes: int
    timeline: list[ConfusionBucket]
    topics: list[ConfusionTopicCount]


class InteractionSummaryOut(BaseModel):
    """The lecturer's session summary (FR-518). Questions are the lecturer's view (`author_name`
    null for anonymous ones); polls exclude drafts; no student id anywhere."""
    attendance_session_id: int
    course_code: Optional[str]
    course_name: Optional[str]
    class_date: Optional[str]                       # ISO MYT date of the class
    class_status: str
    status: Literal["open", "closed"]               # effective interaction state
    question_counts: SummaryQuestionCounts
    questions: list[QuestionOut]
    polls: list[PollOut]
    quick_questions: list[SummaryQuickQuestion]
    reactions: dict[str, int]                       # every kind, 0 when none
    reactions_total: int
    confusion: SummaryConfusion


class MyQuestionOut(BaseModel):
    """One of the student's own past questions (FR-520)."""
    id: int
    attendance_session_id: int
    occurrence_id: Optional[int]
    course_code: Optional[str]
    course_name: Optional[str]
    class_date: Optional[str]
    text: str
    anonymous: bool
    upvotes: int
    answered: bool
    answered_at: Optional[datetime]
    created_at: datetime


class MyQuestionListOut(BaseModel):
    questions: list[MyQuestionOut]                  # newest first
    next_before: Optional[int]                      # pass as `before` for the next page; null at the end
