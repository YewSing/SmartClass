from datetime import datetime
from typing import Optional

from pgvector.sqlalchemy import Vector
from sqlalchemy import CheckConstraint, ForeignKey, LargeBinary, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base

FLAG_STATUSES = ("pending", "confirmed", "rejected")


class AttendanceFlag(Base):
    """A student's "I'm here but wasn't recognised" flag for one session (FR-318, FR-319)."""
    __tablename__ = "attendance_flags"
    __table_args__ = (
        UniqueConstraint("session_id", "student_id", name="uq_attendance_flags_session_student"),
        CheckConstraint("status IN ('pending','confirmed','rejected')", name="ck_attendance_flags_status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("attendance_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True)
    flagged_at: Mapped[datetime] = mapped_column(nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="pending", index=True)
    resolved_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    resolved_at: Mapped[Optional[datetime]] = mapped_column()
    reject_reason: Mapped[Optional[str]] = mapped_column(String(500))
    record_status: Mapped[Optional[str]] = mapped_column(String(20))   # present | late, set on confirm


class UnmatchedFace(Base):
    """A face crop a device saw in a session that matched no enrolled student (FR-407).

    Kept only as evidence for a flag: deleted when the flag it was shown with is resolved, when its
    session is over with no flag pending, or after FACE_UNMATCHED_RETENTION_DAYS (FR-410, NFR-02).
    """
    __tablename__ = "unmatched_faces"

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("attendance_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    camera_id: Mapped[Optional[int]] = mapped_column(ForeignKey("cameras.id", ondelete="SET NULL"))
    embedding: Mapped[list[float]] = mapped_column(Vector(512), nullable=False)
    image: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)   # the JPEG crop as sent
    similarity: Mapped[Optional[float]] = mapped_column()   # best enrolled student's score (below threshold)
    captured_at: Mapped[datetime] = mapped_column(nullable=False, index=True)
    last_seen_at: Mapped[datetime] = mapped_column(nullable=False)
