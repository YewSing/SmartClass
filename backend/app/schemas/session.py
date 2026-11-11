from typing import Annotated, Literal, Optional
from datetime import date, datetime

from pydantic import BaseModel, BeforeValidator, Field, StringConstraints


def _blank_reason_to_none(value):
    """Trim the reason; an empty or whitespace-only reason counts as no reason."""
    if isinstance(value, str):
        value = value.strip()
        return value or None
    return value


# FR-305: an override may carry a reason (optional since 2026-11-12); it is audited when given.
OverrideReason = Annotated[
    Optional[Annotated[str, StringConstraints(max_length=500)]],
    BeforeValidator(_blank_reason_to_none),
]


class MoodleConflictOut(BaseModel):
    """A student whose status was changed in Moodle after SmartClass sent it (FR-320)."""
    record_id: int
    student_id: int
    matric_no: str
    name: str
    smartclass_status: str              # present | late | excused | absent
    moodle_status: str                  # present | late | excused | absent | none (no mark) | other
    keep_smartclass: bool = False       # chosen; sent on the next sync if Moodle hasn't changed again


class SessionOut(BaseModel):
    id: int
    occurrence_id: Optional[int] = None
    class_id: Optional[int] = None      # alias for occurrence_id — keeps lecturer/student frontends working
    camera_id: Optional[int] = None
    class_code: str
    class_name: str
    lecturer_id: int
    opened_at: Optional[datetime] = None
    closed_at: Optional[datetime] = None
    status: str                         # scheduled | open | closed | needs_confirmation | cancelled
    class_date: Optional[date] = None
    starts_at: Optional[datetime] = None
    ends_at: Optional[datetime] = None
    source: str = "manual"              # schedule | manual
    present: int = 0
    absent: int = 0
    late: int = 0
    excused: int = 0
    unid: int = 0
    # Moodle Attendance sync (FR-312, FR-320); status None = never queued (not closed yet)
    moodle_sync_status: Optional[str] = None   # pending | synced | failed | conflict
    moodle_synced_at: Optional[datetime] = None
    moodle_sync_next_at: Optional[datetime] = None
    moodle_sync_error: Optional[str] = None
    moodle_conflicts: list[MoodleConflictOut] = []

    model_config = {"from_attributes": True}


class ResolveConflictRequest(BaseModel):
    keep: Literal["smartclass", "moodle"]


class OpenSessionRequest(BaseModel):
    occurrence_id: int
    duration_minutes: Optional[int] = Field(None, ge=1, le=600)


class ExtendRequest(BaseModel):
    minutes: int = Field(ge=1, le=240)


class ConfirmRequest(BaseModel):
    held: bool


class AttendanceStudentOut(BaseModel):
    record_id: Optional[int] = None
    student_id: int
    matric_no: str
    name: str
    status: str  # present | late | excused | absent | not_recorded
    detected_at: Optional[datetime] = None
    overridden: bool = False

    model_config = {"from_attributes": True}


class OverrideRequest(BaseModel):
    status: str  # present | late | excused | absent
    reason: OverrideReason = None  # FR-305: optional, audited when given


class SessionOverrideRequest(BaseModel):
    student_id: int
    status: str  # present | late | excused | absent
    reason: OverrideReason = None  # FR-305: optional, audited when given


class FaceMatchRequest(BaseModel):
    embedding: list[float]
    session_id: int
    dry_run: bool = False


class FaceMatchResponse(BaseModel):
    matched: bool
    student_id: Optional[int] = None
    student_name: Optional[str] = None
    similarity: Optional[float] = None
    already_present: bool = False
    reason: Optional[str] = None  # "not_enrolled" when face matches but student not in class
