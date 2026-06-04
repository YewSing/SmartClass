from datetime import datetime
from typing import Optional, TYPE_CHECKING

from sqlalchemy import String, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.session import AttendanceSession
    from app.models.user import Student, User


class AttendanceRecord(Base):
    __tablename__ = "attendance_records"
    __table_args__ = (UniqueConstraint("session_id", "student_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("attendance_sessions.id"), nullable=False, index=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False)  # present | absent | unidentified
    detected_at: Mapped[Optional[datetime]] = mapped_column()
    override_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"))
    override_at: Mapped[Optional[datetime]] = mapped_column()

    session: Mapped["AttendanceSession"] = relationship(back_populates="attendance_records")
    student: Mapped["Student"] = relationship(back_populates="attendance_records")
    override_actor: Mapped[Optional["User"]] = relationship(foreign_keys=[override_by])
