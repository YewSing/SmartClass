"""Module 2 per-user Moodle snapshot: announcements and deadlines (FR-203) — S16.

Written only on a successful Moodle login, with the user's own transient token; read-only for the
dashboard (S18). One row per user; a failed refresh leaves the previous row untouched."""
from datetime import datetime

from sqlalchemy import JSON, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class MoodleSnapshot(Base):
    __tablename__ = "m2_moodle_snapshot"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    announcements: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    deadlines: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    refreshed_at: Mapped[datetime] = mapped_column(nullable=False)   # naive MYT, like other tables
