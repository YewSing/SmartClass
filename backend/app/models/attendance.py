from datetime import datetime
from typing import Optional, TYPE_CHECKING

from sqlalchemy import String, ForeignKey, UniqueConstraint, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.session import AttendanceSession
    from app.models.user import Student, User

ATTENDANCE_STATUSES = ("present", "late", "excused", "absent")   # FR-304
ATTENDED_STATUSES = ("present", "late")                          # Late counts as attended


class AttendanceRecord(Base):
    __tablename__ = "attendance_records"
    __table_args__ = (
        UniqueConstraint("session_id", "student_id"),
        CheckConstraint("status IN ('present','late','excused','absent')",
                        name="ck_attendance_records_status"),
        CheckConstraint("moodle_status_sent IN ('present','late','excused','absent')",
                        name="ck_attendance_records_moodle_status_sent"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("attendance_sessions.id"), nullable=False, index=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False)  # present | late | excused | absent
    detected_at: Mapped[Optional[datetime]] = mapped_column()
    override_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"))
    override_at: Mapped[Optional[datetime]] = mapped_column()
    moodle_status_sent: Mapped[Optional[str]] = mapped_column(String(20))  # last status sent to Moodle (FR-311)

    session: Mapped["AttendanceSession"] = relationship(back_populates="attendance_records")
    student: Mapped["Student"] = relationship(back_populates="attendance_records")
    override_actor: Mapped[Optional["User"]] = relationship(foreign_keys=[override_by])
