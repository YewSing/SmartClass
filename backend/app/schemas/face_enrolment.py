from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, field_validator


class FaceEnrolmentOut(BaseModel):
    """The student's face enrolment status (FR-115)."""
    status: Literal["not_enrolled", "pending_review", "active", "rejected"]
    reason: Optional[str] = None            # why it was rejected
    submitted_at: Optional[datetime] = None
    decided_at: Optional[datetime] = None
    blocked_attempts: int = 0               # card photos blocked since the last real submission
    can_submit_anyway: bool = False         # the app may offer "submit anyway" (T16)


class ReviewImageOut(BaseModel):
    id: int
    kind: Literal["selfie", "card"]
    position: int
    url: str                                # API path; fetch it with the reviewer's token


class PendingEnrolmentOut(BaseModel):
    """A submission in the lecturer verification queue (FR-113): the account's details next to
    what the checks read from the photos."""
    id: int
    student_user_id: int
    student_name: str                       # account name (from Moodle)
    matric_no: str                          # account matric number
    courses: list[str]                      # course codes shared with the reviewer (all, for admins)
    submitted_at: datetime
    submitted_anyway: bool
    check_reasons: list[str]                # why it wasn't auto-approved
    face_score: Optional[float] = None      # selfie ↔ card face similarity
    ocr_matric: Optional[str] = None        # matric number read from the card
    ocr_matric_confidence: Optional[float] = None
    name_score: Optional[float] = None      # share of the account name found on the card
    ocr_lines: list[str] = []
    quality_scores: Optional[dict[str, Any]] = None
    images: list[ReviewImageOut]


class RejectIn(BaseModel):
    reason: str = Field(max_length=500)

    @field_validator("reason")
    @classmethod
    def _not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("A reason is required")
        return v
