from typing import Optional
from datetime import datetime

from pydantic import BaseModel


class SessionOut(BaseModel):
    id: int
    occurrence_id: Optional[int] = None
    class_id: Optional[int] = None      # alias for occurrence_id — keeps lecturer/student frontends working
    camera_id: Optional[int] = None
    class_code: str
    class_name: str
    lecturer_id: int
    opened_at: datetime
    closed_at: Optional[datetime] = None
    status: str
    present: int = 0
    absent: int = 0
    unid: int = 0

    model_config = {"from_attributes": True}


class OpenSessionRequest(BaseModel):
    occurrence_id: int


class AttendanceStudentOut(BaseModel):
    record_id: Optional[int] = None
    student_id: int
    matric_no: str
    name: str
    status: str  # present | absent | unidentified | not_recorded
    detected_at: Optional[datetime] = None
    overridden: bool = False

    model_config = {"from_attributes": True}


class OverrideRequest(BaseModel):
    status: str  # present | absent


class SessionOverrideRequest(BaseModel):
    student_id: int
    status: str  # present | absent


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
