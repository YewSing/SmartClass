from typing import Annotated, Optional
from datetime import date, datetime

from pydantic import BaseModel, Field, StringConstraints

# FR-305: an override must carry a reason. Trimming first makes whitespace-only invalid.
OverrideReason = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]


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

    model_config = {"from_attributes": True}


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
    reason: OverrideReason  # FR-305: mandatory, audited


class SessionOverrideRequest(BaseModel):
    student_id: int
    status: str  # present | late | excused | absent
    reason: OverrideReason  # FR-305: mandatory, audited


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
