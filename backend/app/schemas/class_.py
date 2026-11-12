from typing import Literal, Optional
from datetime import datetime

from pydantic import BaseModel, Field, model_validator

_HHMM = r"^([01]\d|2[0-3]):[0-5]\d$"


class CourseOut(BaseModel):
    id: int
    code: str
    name: str

    model_config = {"from_attributes": True}


class CourseListOut(BaseModel):
    id: int
    code: str
    name: str
    occurrence_count: int = 0
    enrolled_count: int = 0

    model_config = {"from_attributes": True}


class OccurrenceOut(BaseModel):
    id: int
    course_id: int
    course_code: str
    course_name: str
    type: str           # LECTURE | TUTORIAL
    day_of_week: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    room: Optional[str] = None
    lecturer_id: Optional[int] = None
    lecturer_name: Optional[str] = None
    label: Optional[str] = None
    enrolled_count: int = 0

    model_config = {"from_attributes": True}


class WeeklyScheduleRequest(BaseModel):
    """The weekly timetable slot of a class. All three time fields together, or none to clear it."""

    day_of_week: Optional[Literal["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]] = None
    start_time: Optional[str] = Field(None, pattern=_HHMM)
    end_time: Optional[str] = Field(None, pattern=_HHMM)
    room: Optional[str] = Field(None, max_length=255)

    @model_validator(mode="after")
    def _check(self) -> "WeeklyScheduleRequest":
        given = [self.day_of_week, self.start_time, self.end_time]
        if any(v is not None for v in given) and not all(v is not None for v in given):
            raise ValueError("Give day, start and end together, or none to clear the schedule")
        if self.start_time and self.end_time and self.end_time <= self.start_time:
            raise ValueError("The end time must be after the start time")
        return self


class OccurrenceStudentOut(BaseModel):
    id: int
    user_id: int
    matric_no: str
    name: str
    face_enrolled: bool
    face_enrolled_at: Optional[datetime] = None

    model_config = {"from_attributes": True}
