"""Response of POST /device/faces (FR-402–FR-405).

Only the minimum a device needs goes back (PDPA): never a student's name or matric number.
"""
from typing import Literal, Optional

from pydantic import BaseModel

CropOutcome = Literal["recorded", "voting", "already_recorded", "below_threshold", "not_enrolled", "no_face"]


class CropResult(BaseModel):
    index: int                         # position of the crop in the request
    outcome: CropOutcome
    student_id: Optional[int] = None   # students.id; set for recorded / voting / already_recorded only
    similarity: Optional[float] = None  # best similarity found (None for no_face, or when nobody has an embedding)
    votes: Optional[int] = None        # consecutive frames so far (voting / recorded)
    status: Optional[str] = None       # "present" | "late" for recorded, the existing status for already_recorded


class DeviceFacesResponse(BaseModel):
    session_id: int
    results: list[CropResult]


class DeviceSessionOut(BaseModel):
    """The open session a device records into, or 404 (GET /device/session, FR-401)."""

    session_id: int
    occurrence_id: Optional[int] = None
    room: str            # the device's room
