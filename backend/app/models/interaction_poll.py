"""Interaction poll models (FR-504, FR-505, FR-509 part)."""

import sqlalchemy as sa
from datetime import datetime
from typing import Optional, TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.interaction import InteractionSession
    from app.models.user import Student, User


class InteractionPoll(Base):
    """One live poll in an interaction session."""

    __tablename__ = "interaction_polls"

    id: Mapped[int] = mapped_column(primary_key=True)
    interaction_id: Mapped[int] = mapped_column(
        ForeignKey("interaction_sessions.id"), nullable=False, index=True
    )
    question: Mapped[str] = mapped_column(Text, nullable=False)
    is_open: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=sa.sql.true())
    opened_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    opened_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=sa.func.now()
    )
    closed_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    closed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    interaction: Mapped["InteractionSession"] = relationship(back_populates="polls")
    options: Mapped[list["InteractionPollOption"]] = relationship(
        back_populates="poll", cascade="all, delete-orphan", order_by="InteractionPollOption.position"
    )
    votes: Mapped[list["InteractionPollVote"]] = relationship(
        back_populates="poll", cascade="all, delete-orphan"
    )
    opened_by_user: Mapped["User"] = relationship(foreign_keys=[opened_by])
    closed_by_user: Mapped[Optional["User"]] = relationship(foreign_keys=[closed_by])


class InteractionPollOption(Base):
    """One option of a poll."""

    __tablename__ = "interaction_poll_options"

    id: Mapped[int] = mapped_column(primary_key=True)
    poll_id: Mapped[int] = mapped_column(
        ForeignKey("interaction_polls.id", ondelete="CASCADE"), nullable=False, index=True
    )
    option_text: Mapped[str] = mapped_column(Text, nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)

    poll: Mapped["InteractionPoll"] = relationship(back_populates="options")
    votes: Mapped[list["InteractionPollVote"]] = relationship(
        back_populates="option", cascade="all, delete-orphan"
    )


class InteractionPollVote(Base):
    """One student's vote for one poll option (at most one per poll per student)."""

    __tablename__ = "interaction_poll_votes"

    id: Mapped[int] = mapped_column(primary_key=True)
    poll_id: Mapped[int] = mapped_column(
        ForeignKey("interaction_polls.id", ondelete="CASCADE"), nullable=False, index=True
    )
    option_id: Mapped[int] = mapped_column(
        ForeignKey("interaction_poll_options.id", ondelete="CASCADE"), nullable=False, index=True
    )
    student_id: Mapped[int] = mapped_column(
        ForeignKey("students.id"), nullable=False, index=True
    )
    voted_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=sa.func.now()
    )

    poll: Mapped["InteractionPoll"] = relationship(back_populates="votes")
    option: Mapped["InteractionPollOption"] = relationship(back_populates="votes")
    student: Mapped["Student"] = relationship(back_populates="interaction_poll_votes")
