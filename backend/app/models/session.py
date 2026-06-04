from datetime import datetime
from typing import Optional, TYPE_CHECKING

from sqlalchemy import String, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.class_ import ClassOccurrence
    from app.models.user import Lecturer
    from app.models.attendance import AttendanceRecord
    from app.models.camera import Camera


class AttendanceSession(Base):
    __tablename__ = "attendance_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    occurrence_id: Mapped[int] = mapped_column(
        ForeignKey("class_occurrences.id"), nullable=True, index=True
    )
    lecturer_id: Mapped[int] = mapped_column(ForeignKey("lecturers.id"), nullable=False, index=True)
    camera_id: Mapped[Optional[int]] = mapped_column(ForeignKey("cameras.id"), nullable=True, index=True)
    opened_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())
    closed_at: Mapped[Optional[datetime]] = mapped_column()
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="open")

    occurrence: Mapped[Optional["ClassOccurrence"]] = relationship(back_populates="sessions")
    lecturer: Mapped["Lecturer"] = relationship(back_populates="sessions")
    camera: Mapped[Optional["Camera"]] = relationship(back_populates="sessions")
    attendance_records: Mapped[list["AttendanceRecord"]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )
