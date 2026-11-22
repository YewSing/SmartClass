from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.interaction import (
    POLL_MAX_OPTIONS,
    POLL_MIN_OPTIONS,
    POLL_OPTION_MAX_CHARS,
    POLL_QUESTION_MAX_CHARS,
    QUESTION_MAX_CHARS,
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
