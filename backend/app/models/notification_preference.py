"""Module 2 notification preferences, one row per user (FR-214) — S15.

Only general notifications have a choice: urgent and important are always pushed and emailed, so
they have no column. No row = the defaults (general push and email off, as FR-210/FR-211 send only
urgent/important unless the user opts in)."""
from datetime import datetime

from sqlalchemy import Boolean, ForeignKey, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class NotificationPreference(Base):
    __tablename__ = "m2_notification_preferences"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    push_general: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    email_general: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    updated_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=text("(NOW() AT TIME ZONE 'Asia/Kuala_Lumpur')")
    )
