"""Module 2 in-app notifications (FR-205–FR-207, FR-209, FR-216) — S10.

One row per recipient. Only the rendered title, message and app-relative link are stored, never
the raw event payload (it can hold names and matric numbers)."""
from datetime import datetime
from typing import Optional

from sqlalchemy import CheckConstraint, ForeignKey, Index, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base

PRIORITIES = ("urgent", "important", "general")   # FR-207


class Notification(Base):
    __tablename__ = "m2_notifications"
    __table_args__ = (
        CheckConstraint("priority IN ('urgent','important','general')", name="ck_m2_notifications_priority"),
        Index("ix_m2_notifications_user_created", "user_id", "created_at"),
        Index("ix_m2_notifications_dedup", "user_id", "event", "subject_key", "created_at"),
        Index("ix_m2_notifications_created", "created_at"),     # retention purge (FR-218, S15)
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    event: Mapped[str] = mapped_column(String(64), nullable=False)
    priority: Mapped[str] = mapped_column(String(16), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    link: Mapped[Optional[str]] = mapped_column(String(300))           # app-relative, e.g. /quizzes/3
    subject_key: Mapped[str] = mapped_column(String(200), nullable=False)
    read_at: Mapped[Optional[datetime]] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=text("(NOW() AT TIME ZONE 'Asia/Kuala_Lumpur')")
    )
