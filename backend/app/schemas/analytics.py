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


# ── per-student engagement indicators (FR-701, FR-702, FR-703, S41) ──────────

class EngagementAttendanceOut(BaseModel):
    rate: Optional[float] = None        # percentage 0-100, None when no closed sessions
    absence_frequency: Optional[int] = None   # counted sessions not attended


class EngagementParticipationOut(BaseModel):
    frequency: int                      # total interaction actions
    questions: int
    votes: int
    responses: int
    reactions: int
    idu_signals: int


class EngagementQuizzesOut(BaseModel):
    scores: list[float] = []            # per-quiz scores (graded quizzes only)
    average_score: Optional[float] = None
    trend: list[dict] = []              # [{quiz_id, title, score}]


class EngagementIndicatorOut(BaseModel):
    student_id: int
    student_name: Optional[str] = None
    matric_no: Optional[str] = None
    course_id: int
    attendance: EngagementAttendanceOut
    participation: EngagementParticipationOut
    quizzes: EngagementQuizzesOut

    model_config = {"from_attributes": True}


# ── class-level trends + assessment (FR-704, FR-705, S42) ───────────────────

class ClassSessionTrendOut(BaseModel):
    session: int
    session_id: int
    date: Optional[str] = None
    attendance_rate: Optional[float] = None
    attended: int
    counted_sessions: int
    participation: int


class ClassAssessmentTopicOut(BaseModel):
    topic: str
    average_score: float
    question_count: int


class ClassAssessmentSessionOut(BaseModel):
    session: int
    session_id: int
    date: Optional[str] = None
    average_score: Optional[float] = None
    quiz_count: int


# ── student self view (FR-706, S43) ──────────────────────────────────────────

class StudentCourseIndicatorOut(BaseModel):
    course_id: int
    attendance: EngagementAttendanceOut
    participation: EngagementParticipationOut
    quizzes: EngagementQuizzesOut


class StudentSelfViewOut(BaseModel):
    student_id: int
    overall_attendance_rate: Optional[float] = None
    courses: list[StudentCourseIndicatorOut] = []



