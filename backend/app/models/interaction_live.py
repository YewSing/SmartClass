"""Live question, reaction and IDU signal models (FR-506, FR-507, FR-508, FR-509 part).

All writes carry session, student and timestamp. A student may respond once to a live
question, keep one current reaction per session, and send at most one IDU signal per
session (the lecturer sees distinct students, not click counts).
"""

import sqlalchemy as sa
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.interaction import InteractionSession
    from app.models.user import Student, User


class InteractionLiveQuestion(Base):
    """A live question the lecturer posts to the class."""

    __tablename__ = "interaction_live_questions"

    id: Mapped[int] = mapped_column(primary_key=True)
    interaction_id: Mapped[int] = mapped_column(
        ForeignKey("interaction_sessions.id"), nullable=False, index=True
    )
    question: Mapped[str] = mapped_column(Text, nullable=False)
    asked_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    asked_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=sa.func.now()
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=sa.sql.true())

    interaction: Mapped["InteractionSession"] = relationship(back_populates="live_questions")
    responses: Mapped[list["InteractionLiveQuestionResponse"]] = relationship(
        back_populates="live_question", cascade="all, delete-orphan"
    )
    asked_by_user: Mapped["User"] = relationship(foreign_keys=[asked_by])


class InteractionLiveQuestionResponse(Base):
    """One student's response to a live question."""

    __tablename__ = "interaction_live_question_responses"

    id: Mapped[int] = mapped_column(primary_key=True)
    live_question_id: Mapped[int] = mapped_column(
        ForeignKey("interaction_live_questions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"), nullable=False, index=True)
    response: Mapped[str] = mapped_column(Text, nullable=False)
    responded_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=sa.func.now()
    )

    live_question: Mapped["InteractionLiveQuestion"] = relationship(back_populates="responses")
    student: Mapped["Student"] = relationship(back_populates="live_question_responses")


class InteractionReaction(Base):
    """One student's current reaction in a session (one of a predefined set)."""

    __tablename__ = "interaction_reactions"

    id: Mapped[int] = mapped_column(primary_key=True)
    interaction_id: Mapped[int] = mapped_column(
        ForeignKey("interaction_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"), nullable=False, index=True)
    reaction: Mapped[str] = mapped_column(String(40), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=sa.func.now()
    )

    interaction: Mapped["InteractionSession"] = relationship(back_populates="reactions")
    student: Mapped["Student"] = relationship(back_populates="interaction_reactions")


class InteractionIDUSignal(Base):
    """One 'I Don't Understand' signal per student per session."""

    __tablename__ = "interaction_idu_signals"

    id: Mapped[int] = mapped_column(primary_key=True)
    interaction_id: Mapped[int] = mapped_column(
        ForeignKey("interaction_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=sa.func.now()
    )

    interaction: Mapped["InteractionSession"] = relationship(back_populates="idu_signals")
    student: Mapped["Student"] = relationship(back_populates="idu_signals")
