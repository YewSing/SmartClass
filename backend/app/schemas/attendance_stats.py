from datetime import date as date_
from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class AttendanceCountsOut(BaseModel):
    present: int
    late: int
    excused: int
    absent: int
    closed_sessions: int      # present + late + excused + absent
    counted_sessions: int     # closed_sessions - excused (the rate's denominator)
    rate: Optional[float]     # 0.0–100.0, 1 decimal; null when counted_sessions == 0


class StudentSessionHistoryOut(BaseModel):
    session_id: int
    occurrence_id: int
    class_type: str           # LECTURE | TUTORIAL
    class_label: Optional[str] = None
    date: Optional[date_] = None
    starts_at: Optional[datetime] = None
    session_status: str       # open | closed
    status: str               # present | late | excused | absent | not_recorded (open session only)
    detected_at: Optional[datetime] = None
    overridden: bool = False


class StudentCourseAttendanceOut(AttendanceCountsOut):
    course_id: int
    course_code: str
    course_name: str
    sessions: list[StudentSessionHistoryOut]


class ClassStudentRateOut(AttendanceCountsOut):
    student_id: int
    matric_no: str
    name: str


class ClassAttendanceRatesOut(BaseModel):
    occurrence_id: int
    course_code: str
    course_name: str
    closed_sessions: int
    students: list[ClassStudentRateOut]


class ReportSessionOut(BaseModel):
    session_id: int
    date: Optional[date_] = None
    starts_at: Optional[datetime] = None
    label: str                # same text as the CSV column header


class ReportStudentRowOut(AttendanceCountsOut):
    student_id: int
    matric_no: str
    name: str
    statuses: list[str]       # present | late | excused | absent, one per session in `sessions` order


class ClassAttendanceReportOut(BaseModel):
    occurrence_id: int
    course_code: str
    course_name: str
    from_date: Optional[date_] = None
    to_date: Optional[date_] = None
    sessions: list[ReportSessionOut]
    students: list[ReportStudentRowOut]
