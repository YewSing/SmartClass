"""Authoritative Module 6 quiz state (questions and answers are versioned JSON)."""
from datetime import datetime
from sqlalchemy import Boolean, ForeignKey, JSON, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base


class Quiz(Base):
    __tablename__ = "m6_quizzes"
    id: Mapped[int] = mapped_column(primary_key=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id"), index=True)
    lecturer_id: Mapped[int] = mapped_column(ForeignKey("lecturers.id"), index=True)
    title: Mapped[str] = mapped_column(String(255))
    quiz_type: Mapped[str] = mapped_column(String(12))  # game | graded
    status: Mapped[str] = mapped_column(String(16), server_default="draft")
    timer_mode: Mapped[str] = mapped_column(String(16), server_default="whole")
    timer_seconds: Mapped[int | None] = mapped_column()
    opens_at: Mapped[datetime | None] = mapped_column()
    closes_at: Mapped[datetime | None] = mapped_column()
    shuffle: Mapped[bool] = mapped_column(Boolean, server_default="false")
    release_marks: Mapped[bool] = mapped_column(Boolean, server_default="false")
    release_answers: Mapped[bool] = mapped_column(Boolean, server_default="false")
    speed_bonus: Mapped[bool] = mapped_column(Boolean, server_default="true")
    current_question: Mapped[int | None] = mapped_column()
    questions: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())


class QuizAttempt(Base):
    __tablename__ = "m6_attempts"
    __table_args__ = (UniqueConstraint("quiz_id", "student_id", name="uq_m6_attempt_quiz_student"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    quiz_id: Mapped[int] = mapped_column(ForeignKey("m6_quizzes.id", ondelete="CASCADE"), index=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"), index=True)
    status: Mapped[str] = mapped_column(String(16), server_default="in_progress")
    answers: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    score: Mapped[float | None] = mapped_column()
    started_at: Mapped[datetime] = mapped_column(server_default=func.now())
    deadline_at: Mapped[datetime | None] = mapped_column()
    submitted_at: Mapped[datetime | None] = mapped_column()
