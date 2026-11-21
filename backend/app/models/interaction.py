"""Module 5 persistence. The attendance session remains the only live-session lifecycle."""
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    JSON,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class InteractionQuestion(Base):
    __tablename__ = "m5_questions"

    id: Mapped[int] = mapped_column(primary_key=True)
    attendance_session_id: Mapped[int] = mapped_column(
        ForeignKey("attendance_sessions.id", ondelete="CASCADE"), index=True, nullable=False
    )
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"), index=True, nullable=False)
    text: Mapped[str] = mapped_column(String(1000), nullable=False)
    anonymous: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    answered: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    pinned: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    hidden: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())


class InteractionPoll(Base):
    __tablename__ = "m5_polls"
    __table_args__ = (
        CheckConstraint("status IN ('draft','open','closed')", name="ck_m5_polls_status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    attendance_session_id: Mapped[int] = mapped_column(
        ForeignKey("attendance_sessions.id", ondelete="CASCADE"), index=True, nullable=False
    )
    prompt: Mapped[str] = mapped_column(String(500), nullable=False)
    options: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    multiple: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    show_results: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="draft")
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())
    started_at: Mapped[datetime | None] = mapped_column()
    closed_at: Mapped[datetime | None] = mapped_column()


class InteractionBallot(Base):
    __tablename__ = "m5_ballots"
    __table_args__ = (UniqueConstraint("poll_id", "student_id", name="uq_m5_ballot_student"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    poll_id: Mapped[int] = mapped_column(
        ForeignKey("m5_polls.id", ondelete="CASCADE"), index=True, nullable=False
    )
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"), index=True, nullable=False)
    option_indexes: Mapped[list[int]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())


class InteractionQuickPrompt(Base):
    __tablename__ = "m5_quick_prompts"
    __table_args__ = (
        CheckConstraint("status IN ('open','closed')", name="ck_m5_quick_prompts_status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    attendance_session_id: Mapped[int] = mapped_column(
        ForeignKey("attendance_sessions.id", ondelete="CASCADE"), index=True, nullable=False
    )
    prompt: Mapped[str] = mapped_column(String(500), nullable=False)
    max_length: Mapped[int] = mapped_column(nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="open")
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())
    closed_at: Mapped[datetime | None] = mapped_column()


class InteractionQuickAnswer(Base):
    __tablename__ = "m5_quick_answers"
    __table_args__ = (
        UniqueConstraint("quick_prompt_id", "student_id", name="uq_m5_quick_answer_student"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    quick_prompt_id: Mapped[int] = mapped_column(
        ForeignKey("m5_quick_prompts.id", ondelete="CASCADE"), index=True, nullable=False
    )
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"), index=True, nullable=False)
    text: Mapped[str] = mapped_column(String(1000), nullable=False)
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())


class InteractionEvent(Base):
    __tablename__ = "m5_events"
    __table_args__ = (
        Index("ix_m5_events_session_kind_time", "attendance_session_id", "kind", "occurred_at"),
        Index("ix_m5_events_session_student_kind_time", "attendance_session_id", "student_id", "kind", "occurred_at"),
        Index(
            "uq_m5_question_upvote_student",
            "question_id",
            "student_id",
            unique=True,
            postgresql_where=text("kind = 'question.upvoted'"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    attendance_session_id: Mapped[int] = mapped_column(
        ForeignKey("attendance_sessions.id", ondelete="CASCADE"), nullable=False
    )
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"), nullable=False)
    kind: Mapped[str] = mapped_column(String(40), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())
    question_id: Mapped[int | None] = mapped_column(
        ForeignKey("m5_questions.id", ondelete="CASCADE")
    )
    poll_id: Mapped[int | None] = mapped_column(
        ForeignKey("m5_polls.id", ondelete="CASCADE")
    )
    quick_prompt_id: Mapped[int | None] = mapped_column(
        ForeignKey("m5_quick_prompts.id", ondelete="CASCADE")
    )
    reaction: Mapped[str | None] = mapped_column(String(30))
    topic_tag: Mapped[str | None] = mapped_column(String(100))

