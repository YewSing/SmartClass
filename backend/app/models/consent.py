from datetime import datetime
from typing import Optional

from sqlalchemy import ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class FaceConsent(Base):
    """One PDPA face-data consent given by a student (FR-109, NFR-03).

    A new row is added on every acceptance; withdrawing (FR-116) sets `withdrawn_at`,
    so the history of what was agreed and when stays on record.
    """
    __tablename__ = "face_consents"

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(
        ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version: Mapped[str] = mapped_column(String(50), nullable=False)
    accepted_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())
    withdrawn_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
