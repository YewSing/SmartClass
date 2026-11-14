"""Notification model (FR-205, FR-206, FR-211, S10/S31 prerequisite)."""

from datetime import datetime
from typing import Optional, TYPE_CHECKING

import sqlalchemy as sa
from sqlalchemy import Boolean, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.user import User


class Notification(Base):
    """One in-app notification for a user.

    Priority `urgent`/`important` also go through a delivery channel (S11); `general`
    is feed-only.
    """

    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    event: Mapped[str] = mapped_column(String(100), nullable=False)
    # urgent | important | general
    priority: Mapped[str] = mapped_column(String(20), nullable=False, server_default="general")
    payload: Mapped[Optional[dict]] = mapped_column(JSONB(astext_type=sa.Text()), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=sa.func.now()
    )
    read_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    delivered_push: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=sa.sql.false())
    delivered_email: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=sa.sql.false())

    user: Mapped["User"] = relationship(foreign_keys=[user_id])
