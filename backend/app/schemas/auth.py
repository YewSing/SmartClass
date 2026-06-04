from typing import Optional

from pydantic import BaseModel, EmailStr

from app.schemas.user import StudentProfileOut, LecturerProfileOut


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    id: int
    email: str
    name: str
    role: str
    phone: Optional[str] = None
    status: str
    student: Optional[StudentProfileOut] = None
    lecturer: Optional[LecturerProfileOut] = None

    model_config = {"from_attributes": True}


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
