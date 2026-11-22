from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel


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
