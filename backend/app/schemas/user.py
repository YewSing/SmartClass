from typing import Optional
from datetime import datetime

from pydantic import BaseModel, EmailStr


class OccurrenceEnrollmentOut(BaseModel):
    id: int
    course_code: str
    course_name: str
    type: str
    label: Optional[str] = None
    day_of_week: str
    start_time: str
    end_time: str

    model_config = {"from_attributes": True}


class StudentProfileOut(BaseModel):
    matric_no: str
    programme: Optional[str] = None
    faculty: Optional[str] = None
    year_sem: Optional[str] = None

    model_config = {"from_attributes": True}


class LecturerProfileOut(BaseModel):
    staff_id: str
    dept: Optional[str] = None

    model_config = {"from_attributes": True}


class UserDetailOut(BaseModel):
    id: int
    email: str
    name: str
    role: str
    phone: Optional[str] = None
    status: str
    created_at: datetime
    face_enrolled: bool = False
    face_enrolled_at: Optional[datetime] = None
    student: Optional[StudentProfileOut] = None
    lecturer: Optional[LecturerProfileOut] = None
    enrolled_classes: list[OccurrenceEnrollmentOut] = []

    model_config = {"from_attributes": True}


class UserCreateRequest(BaseModel):
    email: EmailStr
    password: str
    name: str
    role: str  # admin | lecturer | student
    phone: Optional[str] = None
    matric_no: Optional[str] = None       # required when role=student
    programme: Optional[str] = None
    faculty: Optional[str] = None
    year_sem: Optional[str] = None
    staff_id: Optional[str] = None        # required when role=lecturer
    dept: Optional[str] = None


class UserUpdateRequest(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    status: Optional[str] = None
    programme: Optional[str] = None
    faculty: Optional[str] = None
    year_sem: Optional[str] = None
    dept: Optional[str] = None


class AdminPasswordResetRequest(BaseModel):
    new_password: str


class UserListOut(BaseModel):
    items: list[UserDetailOut]
    total: int
    page: int
    limit: int
