"""Student and lecturer dashboard shapes (FR-201, FR-202) — S18.

Fields owned by M5/M6/M7 (`live_activity`, `participation`, `quizzes`, `at_risk_alerts`) are
always present and `null` until S80 fills them.
"""
from datetime import date, datetime
from typing import Any, Optional

from pydantic import BaseModel

from app.schemas.notification import NotificationOut


class TodayClassOut(BaseModel):
    occurrence_id: int
    course_id: int
    course_code: str
    course_name: str
    class_type: str                     # LECTURE | TUTORIAL
    class_label: Optional[str]
    room: Optional[str]
    start_time: Optional[str]           # "HH:MM" (MYT): the session's start, else the weekly slot
    end_time: Optional[str]
    session_id: Optional[int]           # today's attendance session, or null before it opens
    session_status: Optional[str]       # open | closed | needs_confirmation | null


class StudentTodayClassOut(TodayClassOut):
    # present | late | excused | absent | not_recorded (session open, not yet seen) | null (no session)
    attendance_status: Optional[str]


class CourseRateOut(BaseModel):
    course_id: int
    course_code: str
    course_name: str
    present: int
    late: int
    excused: int
    absent: int
    closed_sessions: int
    rate: Optional[float]               # 0-100, 1 decimal; null when nothing counts (FR-308)


class MoodleItemsOut(BaseModel):
    announcements: list[dict[str, Any]]  # S16 snapshot items: course, title, date, link
    deadlines: list[dict[str, Any]]
    refreshed_at: Optional[datetime]     # null = never refreshed (no Moodle login yet)


class StudentDashboardOut(BaseModel):
    date: date                           # today (MYT)
    today_classes: list[StudentTodayClassOut]
    attendance_rates: list[CourseRateOut]
    moodle: MoodleItemsOut
    priority_notifications: list[NotificationOut]
    unread_count: int
    live_activity: Optional[Any] = None  # M5/M6, filled in S80


class AttendanceOverviewOut(BaseModel):
    session_id: int
    occurrence_id: int
    course_id: int
    course_code: str
    course_name: str
    class_type: str
    class_label: Optional[str]
    session_status: str                  # open (current) | closed (latest)
    date: Optional[date]
    starts_at: Optional[datetime]
    enrolled: int
    present: int
    late: int
    excused: int
    absent: int
    not_recorded: int                    # open session only: enrolled students not seen yet
    rate: Optional[float]                # closed session only: (present+late)/(enrolled-excused)


class LecturerDashboardOut(BaseModel):
    date: date
    today_classes: list[TodayClassOut]
    attendance_overview: Optional[AttendanceOverviewOut]   # null = no open or closed session yet
    priority_notifications: list[NotificationOut]
    unread_count: int
    participation: Optional[Any] = None   # M5, filled in S80
    quizzes: Optional[Any] = None         # M6, filled in S80
    at_risk_alerts: Optional[Any] = None  # M7, filled in S80
