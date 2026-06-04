from datetime import datetime
from typing import Optional, TYPE_CHECKING

from sqlalchemy import String, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.face import FaceEmbedding
    from app.models.class_ import Enrollment, ClassOccurrence
    from app.models.attendance import AttendanceRecord
    from app.models.session import AttendanceSession
    from app.models.audit import AuditLog


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)  # admin | lecturer | student
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[Optional[str]] = mapped_column(String(50))
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="active")
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())

    student: Mapped[Optional["Student"]] = relationship(back_populates="user", uselist=False)
    lecturer: Mapped[Optional["Lecturer"]] = relationship(back_populates="user", uselist=False)
    audit_logs: Mapped[list["AuditLog"]] = relationship(
        back_populates="actor", foreign_keys="AuditLog.actor_id"
    )


class Student(Base):
    __tablename__ = "students"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True, index=True, nullable=False)
    matric_no: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    programme: Mapped[Optional[str]] = mapped_column(String(255))
    faculty: Mapped[Optional[str]] = mapped_column(String(255))
    year_sem: Mapped[Optional[str]] = mapped_column(String(50))

    user: Mapped["User"] = relationship(back_populates="student", foreign_keys="[Student.user_id]")
    face_embeddings: Mapped[list["FaceEmbedding"]] = relationship(back_populates="student")
    enrollments: Mapped[list["Enrollment"]] = relationship(back_populates="student")
    attendance_records: Mapped[list["AttendanceRecord"]] = relationship(back_populates="student")


class Lecturer(Base):
    __tablename__ = "lecturers"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True, index=True, nullable=False)
    staff_id: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    dept: Mapped[Optional[str]] = mapped_column(String(255))

    user: Mapped["User"] = relationship(back_populates="lecturer", foreign_keys="[Lecturer.user_id]")
    occurrences: Mapped[list["ClassOccurrence"]] = relationship(back_populates="lecturer")
    sessions: Mapped[list["AttendanceSession"]] = relationship(back_populates="lecturer")
