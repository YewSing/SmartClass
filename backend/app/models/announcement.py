"""Module 2 lecturer announcements (FR-217) — S17.

A lecturer sends a short announcement to the students of a class they teach. It is delivered as
an *important* `announcement.posted` notification and, when asked for, posted to the course's
news forum in Moodle. The Moodle post is a small queue on this row: `pending` until it is posted
(`posted`), retried with backoff, and `failed` after the last try. `not_requested` = in-app only.
"""
from datetime import datetime
from typing import Optional

from sqlalchemy import CheckConstraint, ForeignKey, Index, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base

MOODLE_STATUSES = ("not_requested", "pending", "posted", "failed")


class Announcement(Base):
    __tablename__ = "m2_announcements"
    __table_args__ = (
        CheckConstraint("moodle_status IN ('not_requested','pending','posted','failed')",
                        name="ck_m2_announcements_moodle_status"),
        Index("ix_m2_announcements_occurrence_created", "occurrence_id", "created_at"),
        Index("ix_m2_announcements_moodle_due", "moodle_status", "moodle_next_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    occurrence_id: Mapped[int] = mapped_column(
        ForeignKey("class_occurrences.id", ondelete="CASCADE"), nullable=False)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id", ondelete="CASCADE"), nullable=False)
    author_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    recipient_count: Mapped[int] = mapped_column(nullable=False, default=0)
    moodle_status: Mapped[str] = mapped_column(String(16), nullable=False, default="not_requested")
    moodle_attempts: Mapped[int] = mapped_column(nullable=False, default=0)
    moodle_next_at: Mapped[Optional[datetime]] = mapped_column()       # naive MYT; next try when pending
    moodle_last_attempt_at: Mapped[Optional[datetime]] = mapped_column()
    moodle_error: Mapped[Optional[str]] = mapped_column(String(255))    # short code, never secrets
    moodle_discussion_id: Mapped[Optional[int]] = mapped_column()
    moodle_posted_at: Mapped[Optional[datetime]] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=text("(NOW() AT TIME ZONE 'Asia/Kuala_Lumpur')")
    )
