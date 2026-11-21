"""Lecturer announcements (FR-217) — S17."""
import re
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, StrictBool, StrictStr, field_validator

TITLE_MAX = 200       # = notification title limit (registry.TITLE_MAX)
MESSAGE_MAX = 1000    # = notification message limit (registry.MESSAGE_MAX)

_SPACE = re.compile(r"\s+")
_CONTROL = re.compile(r"[\x00-\x08\x0b-\x1f\x7f]")   # keeps \t and \n


class AnnouncementIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: StrictStr
    message: StrictStr
    post_to_moodle: StrictBool = False

    @field_validator("title")
    @classmethod
    def _title(cls, value: str) -> str:
        value = _SPACE.sub(" ", value).strip()          # one line
        if not value:
            raise ValueError("title must not be empty")
        if len(value) > TITLE_MAX:
            raise ValueError(f"title must be at most {TITLE_MAX} characters")
        return value

    @field_validator("message")
    @classmethod
    def _message(cls, value: str) -> str:
        value = _CONTROL.sub("", value.replace("\r\n", "\n").replace("\r", "\n")).strip()
        if not value:
            raise ValueError("message must not be empty")
        if len(value) > MESSAGE_MAX:
            raise ValueError(f"message must be at most {MESSAGE_MAX} characters")
        return value


class MoodlePostOut(BaseModel):
    status: str                        # not_requested | pending | posted | failed
    attempts: int
    last_attempt_at: Optional[datetime]
    next_try_at: Optional[datetime]    # while pending
    error: Optional[str]               # last failure (short Moodle error code / reason)
    discussion_id: Optional[int]
    link: Optional[str]                # the Moodle forum discussion once posted
    posted_at: Optional[datetime]


class AnnouncementOut(BaseModel):
    id: int
    occurrence_id: int
    course_code: str
    title: str
    message: str
    author_name: Optional[str]
    recipient_count: int
    created_at: datetime
    moodle: MoodlePostOut
