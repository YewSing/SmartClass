"""Module 2 Expo push tokens, one row per device (FR-210, FR-212) — S13.

The token is unique: a phone that signs in as another user moves its token to that user, so a
device never receives someone else's notifications."""
from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, Index, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base

PLATFORMS = ("android", "ios")


class PushToken(Base):
    __tablename__ = "m2_push_tokens"
    __table_args__ = (
        CheckConstraint("platform IN ('android','ios')", name="ck_m2_push_tokens_platform"),
        Index("ix_m2_push_tokens_user", "user_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    token: Mapped[str] = mapped_column(String(200), nullable=False, unique=True)
    platform: Mapped[str] = mapped_column(String(16), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=text("(NOW() AT TIME ZONE 'Asia/Kuala_Lumpur')")
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=text("(NOW() AT TIME ZONE 'Asia/Kuala_Lumpur')")
    )
