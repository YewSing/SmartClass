"""Interaction session model (FR-501)."""

import sqlalchemy as sa
from datetime import datetime
from typing import Optional, TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.class_ import ClassOccurrence
    from app.models.interaction_live import (
        InteractionIDUSignal,
        InteractionLiveQuestion,
        InteractionReaction,
    )
    from app.models.interaction_poll import InteractionPoll
    from app.models.interaction_question import InteractionQuestion
    from app.models.user import User


class InteractionSession(Base):
    """One open-or-closed interaction session for a class occurrence.

    `opened_by` is the lecturer who opened it (NFR-04: only that lecturer may close it).
    """

    __tablename__ = "interaction_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    occurrence_id: Mapped[int] = mapped_column(
        ForeignKey("class_occurrences.id"), nullable=False, index=True
    )
    # open | closed
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="open")
    opened_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    opened_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=sa.func.now()
    )
    closed_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    closed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    occurrence: Mapped["ClassOccurrence"] = relationship(back_populates="interaction_sessions")
    opened_by_user: Mapped["User"] = relationship(foreign_keys=[opened_by])
    closed_by_user: Mapped[Optional["User"]] = relationship(foreign_keys=[closed_by])
    questions: Mapped[list["InteractionQuestion"]] = relationship(
        back_populates="interaction", cascade="all, delete-orphan"
    )
    polls: Mapped[list["InteractionPoll"]] = relationship(
        back_populates="interaction", cascade="all, delete-orphan"
    )
    live_questions: Mapped[list["InteractionLiveQuestion"]] = relationship(
        back_populates="interaction", cascade="all, delete-orphan"
    )
    reactions: Mapped[list["InteractionReaction"]] = relationship(
        back_populates="interaction", cascade="all, delete-orphan"
    )
    idu_signals: Mapped[list["InteractionIDUSignal"]] = relationship(
        back_populates="interaction", cascade="all, delete-orphan"
    )
