"""Interaction question model (FR-502, FR-503, FR-509 part)."""

import sqlalchemy as sa
from datetime import datetime
from typing import Optional, TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.interaction import InteractionSession
    from app.models.user import Student, User


class InteractionQuestion(Base):
    """One question asked in an interaction session.

    `student_id` is always stored (FR-509 counting) but is stripped from responses when
    `anonymous` is true (FR-503).
    """

    __tablename__ = "interaction_questions"

    id: Mapped[int] = mapped_column(primary_key=True)
    interaction_id: Mapped[int] = mapped_column(
        ForeignKey("interaction_sessions.id"), nullable=False, index=True
    )
    student_id: Mapped[int] = mapped_column(
        ForeignKey("students.id"), nullable=False, index=True
    )
    text: Mapped[str] = mapped_column(Text, nullable=False)
    anonymous: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=sa.sql.false())
    answered: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=sa.sql.false())
    answered_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    answered_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=sa.func.now()
    )

    interaction: Mapped["InteractionSession"] = relationship(back_populates="questions")
    student: Mapped["Student"] = relationship(back_populates="interaction_questions")
    answered_by_user: Mapped[Optional["User"]] = relationship(foreign_keys=[answered_by])
