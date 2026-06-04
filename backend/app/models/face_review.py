from datetime import datetime
from typing import Optional

from sqlalchemy import ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column
from pgvector.sqlalchemy import Vector

from app.core.database import Base


class FaceReviewEntry(Base):
    __tablename__ = "face_review_entries"

    id: Mapped[int] = mapped_column(primary_key=True)
    embedding: Mapped[list[float]] = mapped_column(Vector(512), nullable=False)
    session_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("attendance_sessions.id", ondelete="SET NULL"), nullable=True
    )
    camera_device_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    similarity: Mapped[float] = mapped_column(nullable=False, default=0.0)
    occurrences: Mapped[int] = mapped_column(nullable=False, default=1)
    flagged_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())
