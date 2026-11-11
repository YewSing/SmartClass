from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class FaceConsentIn(BaseModel):
    version: str  # the notice version the app showed; must be the current one


class FaceConsentOut(BaseModel):
    active: bool
    version: Optional[str] = None
    accepted_at: Optional[datetime] = None
    current_version: str  # the app shows the notice again when this differs from `version`
