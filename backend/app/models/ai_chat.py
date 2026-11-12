"""Chat sessions for the AI Learning Assistant (Module 8)."""
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import CheckConstraint, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class ChatSession(Base):
    __tablename__ = "ai_chat_sessions"
    __table_args__ = (
        # A chat has exactly one owner: a student (student chat) or a lecturer
        # ("ask my materials", FR-815) — never both, never neither.
        CheckConstraint(
            "(student_id IS NOT NULL) <> (lecturer_id IS NOT NULL)",
            name="ck_ai_chat_sessions_single_owner",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("students.id", ondelete="CASCADE"), nullable=True, index=True
    )
    lecturer_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("lecturers.id", ondelete="CASCADE"), nullable=True, index=True
    )
    course_id: Mapped[int] = mapped_column(
        ForeignKey("courses.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())

    messages: Mapped[list["ChatMessage"]] = relationship(
        back_populates="session", cascade="all, delete-orphan", passive_deletes=True,
        order_by="ChatMessage.id",
    )


class ChatMessage(Base):
    __tablename__ = "ai_chat_messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("ai_chat_sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)  # user | assistant
    content: Mapped[str] = mapped_column(Text, nullable=False)
    citations: Mapped[Optional[list[dict[str, Any]]]] = mapped_column(JSONB, nullable=True)
    source_type: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)  # course | general | refused
    # Standalone query used for retrieval (user messages). Kept for later
    # features: confusion topics and material-gap detection.
    retrieval_query: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # Topic of the question (assistant messages): the cited material title for a course
    # answer, or a short LLM label for a general-knowledge answer (FR-813).
    topic: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())

    session: Mapped["ChatSession"] = relationship(back_populates="messages")
