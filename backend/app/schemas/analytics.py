from typing import Optional
from datetime import datetime

from pydantic import BaseModel


class SessionBarEntry(BaseModel):
    session_id: int
    label: str           # e.g. "Week 1 - Mon"
    date: str            # ISO date string
    present_count: int
    absent_count: int
    total: int


class AtRiskStudent(BaseModel):
    student_id: int
    matric_no: str
    name: str
    present: int
    total: int
    rate: float          # 0.0–100.0


class LecturerAnalyticsOut(BaseModel):
    occurrence_id: int
    class_id: int        # alias = occurrence_id for compat
    class_code: str      # from occurrence.course.code
    class_name: str      # from occurrence.course.name + label
    enrolled_count: int
    sessions_held: int
    avg_attendance_rate: float
    sessions: list[SessionBarEntry]
    at_risk_students: list[AtRiskStudent]


class StudentAttendanceSessionOut(BaseModel):
    session_id: int
    date: str
    class_code: str
    class_name: str
    status: str
    is_live: bool = False
    detected_at: Optional[datetime] = None
    overridden: bool = False


class StudentAttendanceGroupOut(BaseModel):
    occurrence_id: int
    class_id: int        # alias = occurrence_id for compat
    class_code: str
    class_name: str
    present: int
    absent: int
    total: int
    rate: float
    sessions: list[StudentAttendanceSessionOut]


class StudentAttendanceSummaryOut(BaseModel):
    present: int
    absent: int
    total: int
    rate: str            # e.g. "84.6%"
