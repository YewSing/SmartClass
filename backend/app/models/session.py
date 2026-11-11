from datetime import date, datetime
from typing import Optional, TYPE_CHECKING

from sqlalchemy import CheckConstraint, Date, ForeignKey, Index, String, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.class_ import ClassOccurrence
    from app.models.user import Lecturer
    from app.models.attendance import AttendanceRecord
    from app.models.camera import Camera


class AttendanceSession(Base):
    __tablename__ = "attendance_sessions"
    __table_args__ = (
        CheckConstraint("status IN ('scheduled','open','closed','needs_confirmation','cancelled')",
                        name="ck_attendance_sessions_status"),
        CheckConstraint("source IN ('schedule','manual')", name="ck_attendance_sessions_source"),
        CheckConstraint("moodle_sync_status IN ('pending','synced','failed','conflict')",
                        name="ck_attendance_sessions_moodle_sync_status"),
        Index("uq_attendance_sessions_schedule_date", "occurrence_id", "class_date", unique=True,
              postgresql_where=text("source = 'schedule'")),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    occurrence_id: Mapped[int] = mapped_column(
        ForeignKey("class_occurrences.id"), nullable=True, index=True
    )
    lecturer_id: Mapped[int] = mapped_column(ForeignKey("lecturers.id"), nullable=False, index=True)
    camera_id: Mapped[Optional[int]] = mapped_column(ForeignKey("cameras.id"), nullable=True, index=True)
    opened_at: Mapped[Optional[datetime]] = mapped_column(nullable=True, server_default=func.now())
    closed_at: Mapped[Optional[datetime]] = mapped_column()
    # scheduled | open | closed | needs_confirmation | cancelled
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="open")
    class_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True, index=True)  # MYT date of the class
    starts_at: Mapped[Optional[datetime]] = mapped_column()   # effective start (Late clock in T30 uses this)
    ends_at: Mapped[Optional[datetime]] = mapped_column()     # effective end; the job closes the session here
    source: Mapped[str] = mapped_column(String(20), nullable=False, server_default="manual")  # schedule | manual
    lecturer_action_at: Mapped[Optional[datetime]] = mapped_column()  # last in-class lecturer action (FR-317)

    # Moodle Attendance sync (FR-311). NULL status = never queued (sessions closed before T35).
    moodle_sync_status: Mapped[Optional[str]] = mapped_column(String(20), index=True)  # pending | synced | failed | conflict
    moodle_session_id: Mapped[Optional[int]] = mapped_column()      # mod_attendance session id
    moodle_sync_attempts: Mapped[int] = mapped_column(nullable=False, server_default="0")  # failures in a row
    moodle_sync_next_at: Mapped[Optional[datetime]] = mapped_column()  # next try (backoff after a failure)
    moodle_synced_at: Mapped[Optional[datetime]] = mapped_column()
    moodle_sync_error: Mapped[Optional[str]] = mapped_column(String(255))  # last error, or a note on a synced session
    moodle_checked_at: Mapped[Optional[datetime]] = mapped_column()  # last scheduled read of Moodle (FR-320)

    occurrence: Mapped[Optional["ClassOccurrence"]] = relationship(back_populates="sessions")
    lecturer: Mapped["Lecturer"] = relationship(back_populates="sessions")
    camera: Mapped[Optional["Camera"]] = relationship(back_populates="sessions")
    attendance_records: Mapped[list["AttendanceRecord"]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )
