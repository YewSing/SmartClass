from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel


class FaceEnrolmentOut(BaseModel):
    """The student's face enrolment status (FR-115)."""
    status: Literal["not_enrolled", "pending_review", "active", "rejected"]
    reason: Optional[str] = None            # why it was rejected
    submitted_at: Optional[datetime] = None
    decided_at: Optional[datetime] = None
    blocked_attempts: int = 0               # card photos blocked since the last real submission
    can_submit_anyway: bool = False         # the app may offer "submit anyway" (T16)
