"""Quiz attempt / answer models (FR-606, FR-607, FR-608, S32).

A `QuizAttempt` is one student's attempt at one quiz — at most one per quiz+student
(server-enforced unique constraint). It has a server-side deadline (started_at + time
limit); submission after expiry is rejected and a background check auto-submits expired
attempts. `QuizAnswer` holds one answer; MCQ answers are auto-graded on submission,
short answers are left unscored.
"""

from datetime import datetime
from typing import Optional, TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Float, String, Text
import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.quiz import Quiz, QuizQuestion
    from app.models.user import Student


class QuizAttempt(Base):
    """One student's attempt at one quiz."""

    __tablename__ = "quiz_attempts"

    id: Mapped[int] = mapped_column(primary_key=True)
    quiz_id: Mapped[int] = mapped_column(ForeignKey("quizzes.id"), nullable=False, index=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"), nullable=False, index=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=sa.func.now()
    )
    deadline: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    submitted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    # started | submitted | auto_submitted
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="started")
    score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    auto_submitted: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=sa.sql.false())

    quiz: Mapped["Quiz"] = relationship(foreign_keys=[quiz_id])
    student: Mapped["Student"] = relationship(foreign_keys=[student_id])
    answers: Mapped[list["QuizAnswer"]] = relationship(
        back_populates="attempt", cascade="all, delete-orphan"
    )


class QuizAnswer(Base):
    """One answer within one attempt."""

    __tablename__ = "quiz_answers"

    id: Mapped[int] = mapped_column(primary_key=True)
    attempt_id: Mapped[int] = mapped_column(
        ForeignKey("quiz_attempts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    question_id: Mapped[int] = mapped_column(
        ForeignKey("quiz_questions.id"), nullable=False, index=True
    )
    # mcq: the selected option text; short_answer: the student's text
    answer: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    auto_graded: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=sa.sql.false())

    attempt: Mapped["QuizAttempt"] = relationship(back_populates="answers")
    question: Mapped["QuizQuestion"] = relationship(foreign_keys=[question_id])
