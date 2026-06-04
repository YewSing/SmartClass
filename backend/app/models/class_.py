from typing import Optional, TYPE_CHECKING

from sqlalchemy import String, UniqueConstraint, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.user import Student, Lecturer
    from app.models.session import AttendanceSession


class Course(Base):
    __tablename__ = "courses"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(20), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)

    occurrences: Mapped[list["ClassOccurrence"]] = relationship(
        back_populates="course", cascade="all, delete-orphan"
    )


class ClassOccurrence(Base):
    __tablename__ = "class_occurrences"

    id: Mapped[int] = mapped_column(primary_key=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id"), nullable=False, index=True)
    type: Mapped[str] = mapped_column(String(20), nullable=False)        # LECTURE | TUTORIAL
    day_of_week: Mapped[str] = mapped_column(String(10), nullable=False) # Mon | Tue | Wed | Thu | Fri
    start_time: Mapped[str] = mapped_column(String(10), nullable=False)  # "08:00"
    end_time: Mapped[str] = mapped_column(String(10), nullable=False)    # "10:00"
    room: Mapped[Optional[str]] = mapped_column(String(255))
    lecturer_id: Mapped[int] = mapped_column(ForeignKey("lecturers.id"), nullable=False, index=True)
    label: Mapped[Optional[str]] = mapped_column(String(100))            # "Tutorial Group 1"

    course: Mapped["Course"] = relationship(back_populates="occurrences")
    lecturer: Mapped["Lecturer"] = relationship(back_populates="occurrences")
    enrollments: Mapped[list["Enrollment"]] = relationship(
        back_populates="occurrence", cascade="all, delete-orphan"
    )
    sessions: Mapped[list["AttendanceSession"]] = relationship(back_populates="occurrence")


class Enrollment(Base):
    __tablename__ = "enrollments"
    __table_args__ = (UniqueConstraint("student_id", "occurrence_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"), nullable=False, index=True)
    occurrence_id: Mapped[int] = mapped_column(
        ForeignKey("class_occurrences.id"), nullable=False, index=True
    )

    student: Mapped["Student"] = relationship(back_populates="enrollments")
    occurrence: Mapped["ClassOccurrence"] = relationship(back_populates="enrollments")
