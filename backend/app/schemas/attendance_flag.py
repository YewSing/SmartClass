from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class ClosestCropOut(BaseModel):
    """The session's unmatched face closest to the flagging student's enrolled face (FR-407)."""
    id: int
    similarity: float


class FlagOut(BaseModel):
    """A flag as the lecturer (or an admin) sees it."""
    id: int
    session_id: int
    session_status: str
    class_code: str
    class_name: str
    class_date: Optional[date] = None
    student_id: int
    name: str
    matric_no: str
    flagged_at: datetime
    status: str                           # pending | confirmed | rejected
    record_status: Optional[str] = None   # the student's current record, if any (e.g. recognised since)
    reject_reason: Optional[str] = None
    resolved_at: Optional[datetime] = None
    closest_crop: Optional[ClosestCropOut] = None   # only while pending


class StudentFlagOut(BaseModel):
    """A student's own flag and its result."""
    id: int
    session_id: int
    class_code: str
    class_name: str
    class_date: Optional[date] = None
    flagged_at: datetime
    status: str
    record_status: Optional[str] = None   # present | late once confirmed
    reject_reason: Optional[str] = None
    resolved_at: Optional[datetime] = None


class RejectFlagRequest(BaseModel):
    reason: str = Field(..., max_length=500)

    @field_validator("reason")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("A reason is required")
        return value
