from typing import Optional
from datetime import datetime

from pydantic import BaseModel


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
    day_of_week: str
    start_time: str
    end_time: str
    room: Optional[str] = None
    lecturer_id: Optional[int] = None
    lecturer_name: Optional[str] = None
    label: Optional[str] = None
    enrolled_count: int = 0

    model_config = {"from_attributes": True}


class OccurrenceStudentOut(BaseModel):
    id: int
    user_id: int
    matric_no: str
    name: str
    face_enrolled: bool
    face_enrolled_at: Optional[datetime] = None

    model_config = {"from_attributes": True}
