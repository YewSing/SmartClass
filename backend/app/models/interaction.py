"""Module 5 interaction session (FR-501, FR-502) — S30.

One row per M3 class session (`attendance_sessions`), the only class session there is. The
interaction is open only while that class session is `open`: the row's own `status` can only make
it *more* closed (a lecturer closing it early), never open it after the class has ended. A class
with no row yet counts as open while it runs, so M3 never has to create anything here.
"""
from datetime import datetime
from typing import Optional

from sqlalchemy import CheckConstraint, ForeignKey, Index, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base

STATUSES = ("open", "closed")
CLOSED_REASONS = ("lecturer", "class_ended")


class InteractionSession(Base):
    __tablename__ = "m5_interaction_sessions"
    __table_args__ = (
        CheckConstraint("status IN ('open','closed')", name="ck_m5_interaction_sessions_status"),
        CheckConstraint("closed_reason IS NULL OR closed_reason IN ('lecturer','class_ended')",
                        name="ck_m5_interaction_sessions_closed_reason"),
        Index("ix_m5_interaction_sessions_status", "status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    attendance_session_id: Mapped[int] = mapped_column(
        ForeignKey("attendance_sessions.id", ondelete="CASCADE"), nullable=False, unique=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="open")
    closed_reason: Mapped[Optional[str]] = mapped_column(String(16))   # lecturer | class_ended
    opened_at: Mapped[Optional[datetime]] = mapped_column()            # naive MYT, last (re)open
    closed_at: Mapped[Optional[datetime]] = mapped_column()            # naive MYT
    closed_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=text("(NOW() AT TIME ZONE 'Asia/Kuala_Lumpur')")
    )
