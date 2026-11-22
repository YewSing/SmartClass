from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.interaction import QUESTION_MAX_CHARS


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
