"""Module 5 interaction session (FR-501, FR-502) — S30.

One row per M3 class session (`attendance_sessions`), the only class session there is. The
interaction is open only while that class session is `open`: the row's own `status` can only make
it *more* closed (a lecturer closing it early), never open it after the class has ended. A class
with no row yet counts as open while it runs, so M3 never has to create anything here.
"""
from datetime import datetime
from typing import Optional

from sqlalchemy import CheckConstraint, ForeignKey, Index, String, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base

STATUSES = ("open", "closed")
CLOSED_REASONS = ("lecturer", "class_ended")


class InteractionSession(Base):
    __tablename__ = "m5_interaction_sessions"
    __table_args__ = (
        CheckConstraint("status IN ('open','closed')", name="ck_m5_interaction_sessions_status"),
        CheckConstraint("closed_reason IS NULL OR closed_reason IN ('lecturer','class_ended')",
                        name="ck_m5_interaction_sessions_closed_reason"),
        Index("ix_m5_interaction_sessions_status", "status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    attendance_session_id: Mapped[int] = mapped_column(
        ForeignKey("attendance_sessions.id", ondelete="CASCADE"), nullable=False, unique=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="open")
    closed_reason: Mapped[Optional[str]] = mapped_column(String(16))   # lecturer | class_ended
    opened_at: Mapped[Optional[datetime]] = mapped_column()            # naive MYT, last (re)open
    closed_at: Mapped[Optional[datetime]] = mapped_column()            # naive MYT
    closed_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=text("(NOW() AT TIME ZONE 'Asia/Kuala_Lumpur')")
    )


QUESTION_MAX_CHARS = 500


class Question(Base):
    """A live question (FR-503–FR-506) — S31. `student_id` is the asker, kept even for anonymous
    questions so they count in class totals (FR-504, FR-713); no API response, event or audit value
    ever carries it for an anonymous question."""
    __tablename__ = "m5_questions"
    __table_args__ = (
        CheckConstraint(f"char_length(text) BETWEEN 1 AND {QUESTION_MAX_CHARS}",
                        name="ck_m5_questions_text_length"),
        Index("ix_m5_questions_session", "attendance_session_id"),
        Index("ix_m5_questions_student", "student_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    attendance_session_id: Mapped[int] = mapped_column(
        ForeignKey("attendance_sessions.id", ondelete="CASCADE"), nullable=False)
    student_id: Mapped[Optional[int]] = mapped_column(ForeignKey("students.id", ondelete="SET NULL"))
    text: Mapped[str] = mapped_column(String(QUESTION_MAX_CHARS), nullable=False)
    anonymous: Mapped[bool] = mapped_column(nullable=False, default=False)
    answered_at: Mapped[Optional[datetime]] = mapped_column()          # naive MYT; null = not answered
    pinned: Mapped[bool] = mapped_column(nullable=False, default=False)
    hidden: Mapped[bool] = mapped_column(nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(nullable=False)        # naive MYT


class QuestionVote(Base):
    """One upvote per student per question (FR-505)."""
    __tablename__ = "m5_question_votes"
    __table_args__ = (
        UniqueConstraint("question_id", "student_id", name="uq_m5_question_votes_question_student"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    question_id: Mapped[int] = mapped_column(ForeignKey("m5_questions.id", ondelete="CASCADE"), nullable=False)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(nullable=False)


POLL_QUESTION_MAX_CHARS = 300
POLL_OPTION_MAX_CHARS = 120
POLL_MIN_OPTIONS = 2
POLL_MAX_OPTIONS = 6
POLL_STATUSES = ("draft", "open", "closed")


class Poll(Base):
    """A live poll (FR-507–FR-509) — S32. `draft` until the lecturer starts it, then `open`, then
    `closed`. Not graded (FR-513)."""
    __tablename__ = "m5_polls"
    __table_args__ = (
        CheckConstraint("status IN ('draft','open','closed')", name="ck_m5_polls_status"),
        CheckConstraint(f"char_length(question) BETWEEN 1 AND {POLL_QUESTION_MAX_CHARS}",
                        name="ck_m5_polls_question_length"),
        Index("ix_m5_polls_session", "attendance_session_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    attendance_session_id: Mapped[int] = mapped_column(
        ForeignKey("attendance_sessions.id", ondelete="CASCADE"), nullable=False)
    question: Mapped[str] = mapped_column(String(POLL_QUESTION_MAX_CHARS), nullable=False)
    multiple: Mapped[bool] = mapped_column(nullable=False, default=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="draft")
    show_results: Mapped[bool] = mapped_column(nullable=False, default=False)
    created_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(nullable=False)        # naive MYT
    started_at: Mapped[Optional[datetime]] = mapped_column()
    closed_at: Mapped[Optional[datetime]] = mapped_column()


class PollOption(Base):
    __tablename__ = "m5_poll_options"
    __table_args__ = (
        UniqueConstraint("poll_id", "position", name="uq_m5_poll_options_poll_position"),
        CheckConstraint(f"char_length(text) BETWEEN 1 AND {POLL_OPTION_MAX_CHARS}",
                        name="ck_m5_poll_options_text_length"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    poll_id: Mapped[int] = mapped_column(ForeignKey("m5_polls.id", ondelete="CASCADE"), nullable=False)
    position: Mapped[int] = mapped_column(nullable=False)
    text: Mapped[str] = mapped_column(String(POLL_OPTION_MAX_CHARS), nullable=False)


class PollVote(Base):
    """One row per chosen option; a single-choice poll has at most one row per student (the
    service replaces a student's whole vote under a per-student lock)."""
    __tablename__ = "m5_poll_votes"
    __table_args__ = (
        UniqueConstraint("poll_id", "student_id", "option_id", name="uq_m5_poll_votes_poll_student_option"),
        Index("ix_m5_poll_votes_student", "student_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    poll_id: Mapped[int] = mapped_column(ForeignKey("m5_polls.id", ondelete="CASCADE"), nullable=False)
    option_id: Mapped[int] = mapped_column(ForeignKey("m5_poll_options.id", ondelete="CASCADE"), nullable=False)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(nullable=False)


QUICK_PROMPT_MAX_CHARS = 300
QUICK_ANSWER_MAX_CHARS = 500          # hard cap; each quick question sets its own limit up to this
QUICK_ANSWER_DEFAULT_CHARS = 140
QUICK_STATUSES = ("open", "closed")


class QuickQuestion(Base):
    """A live quick question with short text answers (FR-510) — S33. Opens when asked, closes
    when the lecturer closes it. Not graded (FR-513)."""
    __tablename__ = "m5_quick_questions"
    __table_args__ = (
        CheckConstraint("status IN ('open','closed')", name="ck_m5_quick_questions_status"),
        CheckConstraint(f"char_length(prompt) BETWEEN 1 AND {QUICK_PROMPT_MAX_CHARS}",
                        name="ck_m5_quick_questions_prompt_length"),
        CheckConstraint(f"max_chars BETWEEN 1 AND {QUICK_ANSWER_MAX_CHARS}",
                        name="ck_m5_quick_questions_max_chars"),
        Index("ix_m5_quick_questions_session", "attendance_session_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    attendance_session_id: Mapped[int] = mapped_column(
        ForeignKey("attendance_sessions.id", ondelete="CASCADE"), nullable=False)
    prompt: Mapped[str] = mapped_column(String(QUICK_PROMPT_MAX_CHARS), nullable=False)
    max_chars: Mapped[int] = mapped_column(nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="open")
    created_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(nullable=False)        # naive MYT
    closed_at: Mapped[Optional[datetime]] = mapped_column()


class QuickAnswer(Base):
    """One answer per student per quick question; the student may replace it while it is open."""
    __tablename__ = "m5_quick_answers"
    __table_args__ = (
        UniqueConstraint("quick_question_id", "student_id", name="uq_m5_quick_answers_question_student"),
        CheckConstraint(f"char_length(text) BETWEEN 1 AND {QUICK_ANSWER_MAX_CHARS}",
                        name="ck_m5_quick_answers_text_length"),
        Index("ix_m5_quick_answers_student", "student_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    quick_question_id: Mapped[int] = mapped_column(
        ForeignKey("m5_quick_questions.id", ondelete="CASCADE"), nullable=False)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    text: Mapped[str] = mapped_column(String(QUICK_ANSWER_MAX_CHARS), nullable=False)
    created_at: Mapped[datetime] = mapped_column(nullable=False)        # naive MYT, last change


REACTION_KINDS = ("thumbs_up", "clear", "too_fast", "too_slow")


class Reaction(Base):
    """A quick reaction (FR-511) — S33. One row per press."""
    __tablename__ = "m5_reactions"
    __table_args__ = (
        CheckConstraint("kind IN ('thumbs_up','clear','too_fast','too_slow')", name="ck_m5_reactions_kind"),
        Index("ix_m5_reactions_session", "attendance_session_id", "created_at"),
        Index("ix_m5_reactions_student", "student_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    attendance_session_id: Mapped[int] = mapped_column(
        ForeignKey("attendance_sessions.id", ondelete="CASCADE"), nullable=False)
    student_id: Mapped[Optional[int]] = mapped_column(ForeignKey("students.id", ondelete="SET NULL"))
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    created_at: Mapped[datetime] = mapped_column(nullable=False)        # naive MYT


CONFUSION_TOPIC_MAX_CHARS = 60


class ConfusionPress(Base):
    """An "I don't understand" press (FR-512) — S33. `student_id` is kept for cooldowns, spike
    shares and M7 counts (FR-702); the lecturer's view never carries it (FR-515)."""
    __tablename__ = "m5_confusion_presses"
    __table_args__ = (
        CheckConstraint(f"topic IS NULL OR char_length(topic) BETWEEN 1 AND {CONFUSION_TOPIC_MAX_CHARS}",
                        name="ck_m5_confusion_presses_topic_length"),
        Index("ix_m5_confusion_presses_session", "attendance_session_id", "created_at"),
        Index("ix_m5_confusion_presses_student", "student_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    attendance_session_id: Mapped[int] = mapped_column(
        ForeignKey("attendance_sessions.id", ondelete="CASCADE"), nullable=False)
    student_id: Mapped[Optional[int]] = mapped_column(ForeignKey("students.id", ondelete="SET NULL"))
    topic: Mapped[Optional[str]] = mapped_column(String(CONFUSION_TOPIC_MAX_CHARS))
    created_at: Mapped[datetime] = mapped_column(nullable=False)        # naive MYT


class ConfusionSpike(Base):
    """One confusion spike (FR-514): opened when the share of the class pressing within the window
    reaches the threshold; `last_at` moves on while it stays at or above it. A new spike (and a new
    `confusion.spike` notification) needs a full window below the threshold first."""
    __tablename__ = "m5_confusion_spikes"
    __table_args__ = (Index("ix_m5_confusion_spikes_session", "attendance_session_id", "started_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    attendance_session_id: Mapped[int] = mapped_column(
        ForeignKey("attendance_sessions.id", ondelete="CASCADE"), nullable=False)
    started_at: Mapped[datetime] = mapped_column(nullable=False)        # naive MYT
    last_at: Mapped[datetime] = mapped_column(nullable=False)           # last press at/above threshold
    peak_students: Mapped[int] = mapped_column(nullable=False)
    class_size: Mapped[int] = mapped_column(nullable=False)
