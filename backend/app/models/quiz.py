"""Quiz models (FR-601, FR-602, FR-603, S30).

A `Quiz` holds a published/closed assessment; `QuizQuestion`s are drafted standalone
(quiz_id NULL) in S30 and linked to a quiz in S31. Every question carries its source
material id and topic (from the Passage source, never parsed).
"""

from datetime import datetime
from typing import Optional, TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, Text
import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.user import User


class Quiz(Base):
    """One published or closed quiz for a course."""

    __tablename__ = "quizzes"

    id: Mapped[int] = mapped_column(primary_key=True)
    course_id: Mapped[int] = mapped_column(
        ForeignKey("courses.id"), nullable=False, index=True
    )
    title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    time_limit_minutes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    opens_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    closes_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    # draft | published | closed
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="draft")
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=sa.func.now()
    )

    creator: Mapped["User"] = relationship(foreign_keys=[created_by])
    questions: Mapped[list["QuizQuestion"]] = relationship(
        back_populates="quiz", cascade="all, delete-orphan"
    )


class QuizQuestion(Base):
    """One drafted/approved/deleted quiz question.

    `quiz_id` is NULL until S31 publishes a quiz that references this question.
    `source_material_id` and `topic` come from the Passage the LLM based the question on.
    """

    __tablename__ = "quiz_questions"

    id: Mapped[int] = mapped_column(primary_key=True)
    quiz_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("quizzes.id", ondelete="CASCADE"), nullable=True, index=True
    )
    course_id: Mapped[int] = mapped_column(
        ForeignKey("courses.id"), nullable=False, index=True
    )
    # mcq | short_answer
    type: Mapped[str] = mapped_column(String(20), nullable=False)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    options: Mapped[Optional[list[str]]] = mapped_column(JSON, nullable=True)
    correct_answer: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    suggested_answer: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # beginner | intermediate | advanced
    level: Mapped[str] = mapped_column(String(20), nullable=False)
    source_material_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    topic: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    # draft | approved | deleted
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="draft")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=sa.func.now()
    )

    quiz: Mapped[Optional["Quiz"]] = relationship(back_populates="questions")
