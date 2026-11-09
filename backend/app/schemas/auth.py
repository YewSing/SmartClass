from typing import Optional

from pydantic import BaseModel, EmailStr, Field, model_validator

from app.schemas.user import StudentProfileOut, LecturerProfileOut


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class MoodleLoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=1, max_length=256)


class ProfileCourseOut(BaseModel):
    id: int
    code: str
    name: str

    model_config = {"from_attributes": True}


class UserOut(BaseModel):
    id: int
    email: str
    name: str
    role: str
    phone: Optional[str] = None
    status: str
    student: Optional[StudentProfileOut] = None
    lecturer: Optional[LecturerProfileOut] = None
    # Filled by GET /auth/me only (FR-107): enrolled or taught courses, and the student's
    # face enrolment status (FR-115). Login responses leave them empty.
    courses: list[ProfileCourseOut] = []
    face_status: Optional[str] = None

    model_config = {"from_attributes": True}

    @model_validator(mode="after")
    def _only_the_current_roles_profile(self):
        # After a Moodle role change the old profile row is kept (enrolments and attendance
        # point at it), but only the profile matching the current role is shown.
        if self.role != "student":
            self.student = None
        if self.role != "lecturer":
            self.lecturer = None
        return self


class LoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserOut


class RefreshRequest(BaseModel):
    refresh_token: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str
