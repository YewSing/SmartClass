"""Module 6 quizzes (FR-605, FR-606) — S40.

A quiz belongs to a course and is a `draft` until it is published (S43). Its questions come from
the AI draft (S41) or the lecturer (S42). Attempts and answers are filled by the graded quiz (S44)
and the live game (S48); those tasks add their own columns.
"""
from datetime import datetime
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy import CheckConstraint, ForeignKey, Index, Numeric, String, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base

QUIZ_TYPES = ("game", "graded")
QUIZ_STATUSES = ("draft", "published", "closed")
TIMER_MODES = ("question", "quiz")
RELEASES = ("manual", "on_close")
QUESTION_TYPES = ("mcq", "short")
ORIGINS = ("from_material", "extended")
SOURCE_TYPES = ("page", "slide", "section")     # as in Module 8's Passage.location_type (FR-814)
ATTEMPT_STATUSES = ("in_progress", "submitted")

TITLE_MAX_CHARS = 200
# timer limits in seconds, per timer mode (mirrored by ck_m6_quizzes_timer_seconds)
TIMER_LIMITS = {"question": (5, 600), "quiz": (60, 14400)}

QUESTION_TEXT_MAX_CHARS = 1000
OPTION_MAX_CHARS = 300
MIN_OPTIONS = 2
MAX_OPTIONS = 6
SUGGESTED_ANSWER_MAX_CHARS = 2000
EXPLANATION_MAX_CHARS = 2000
TOPIC_MAX_CHARS = 120
SOURCE_FILE_MAX_CHARS = 512
ANSWER_TEXT_MAX_CHARS = 2000


class Quiz(Base):
    """`timer_seconds` is per question or for the whole quiz, by `timer_mode`; a game is always per
    question (FR-606). `release` says when the results come out (by the lecturer's hand, or when the
    quiz closes) and `release_marks`/`release_answers` which parts (FR-618, S46); until then both
    stay hidden. `speed_bonus` is used by game quizzes only (FR-612). `ai_scope` is what the AI may
    draft from (`schemas.quiz.AiScope`, S42), so later AI changes keep to it; null = no limit."""
    __tablename__ = "m6_quizzes"
    __table_args__ = (
        CheckConstraint("type IN ('game','graded')", name="ck_m6_quizzes_type"),
        CheckConstraint("status IN ('draft','published','closed')", name="ck_m6_quizzes_status"),
        CheckConstraint("timer_mode IN ('question','quiz')", name="ck_m6_quizzes_timer_mode"),
        CheckConstraint("type <> 'game' OR timer_mode = 'question'", name="ck_m6_quizzes_game_timer"),
        CheckConstraint("(timer_mode = 'question' AND timer_seconds BETWEEN 5 AND 600) OR "
                        "(timer_mode = 'quiz' AND timer_seconds BETWEEN 60 AND 14400)",
                        name="ck_m6_quizzes_timer_seconds"),
        CheckConstraint("opens_at IS NULL OR closes_at IS NULL OR closes_at > opens_at",
                        name="ck_m6_quizzes_open_close"),
        CheckConstraint("release IN ('manual','on_close')", name="ck_m6_quizzes_release"),
        CheckConstraint(f"char_length(title) BETWEEN 1 AND {TITLE_MAX_CHARS}", name="ck_m6_quizzes_title_length"),
        Index("ix_m6_quizzes_course", "course_id", "status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id", ondelete="CASCADE"), nullable=False)
    created_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    title: Mapped[str] = mapped_column(String(TITLE_MAX_CHARS), nullable=False)
    type: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="draft")
    timer_mode: Mapped[str] = mapped_column(String(16), nullable=False)
    timer_seconds: Mapped[int] = mapped_column(nullable=False)
    opens_at: Mapped[Optional[datetime]] = mapped_column()             # naive MYT; null = once published
    closes_at: Mapped[Optional[datetime]] = mapped_column()            # naive MYT; null = until closed by hand
    shuffle: Mapped[bool] = mapped_column(nullable=False, default=False)
    release: Mapped[str] = mapped_column(String(16), nullable=False, default="manual")
    release_marks: Mapped[bool] = mapped_column(nullable=False, default=True)
    release_answers: Mapped[bool] = mapped_column(nullable=False, default=True)
    speed_bonus: Mapped[bool] = mapped_column(nullable=False, default=True)
    ai_scope: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB(none_as_null=True))
    published_at: Mapped[Optional[datetime]] = mapped_column()          # naive MYT; null in a draft (S43)
    created_at: Mapped[datetime] = mapped_column(nullable=False)        # naive MYT
    updated_at: Mapped[datetime] = mapped_column(nullable=False)        # naive MYT


class QuizQuestion(Base):
    """An MCQ has `options` and `answer` (index of the correct one); a short answer has
    `suggested_answer`. `from_material` questions name their source file and page (FR-603, NFR-48).
    Never sent to students as is (NFR-41): `answer`, `suggested_answer`, `explanation` are hidden."""
    __tablename__ = "m6_questions"
    __table_args__ = (
        # deferred, so a reorder may pass through duplicates inside its transaction (S42)
        UniqueConstraint("quiz_id", "position", name="uq_m6_questions_quiz_position",
                         deferrable=True, initially="DEFERRED"),
        CheckConstraint("type IN ('mcq','short')", name="ck_m6_questions_type"),
        CheckConstraint("origin IN ('from_material','extended')", name="ck_m6_questions_origin"),
        CheckConstraint("position >= 0", name="ck_m6_questions_position"),
        CheckConstraint(f"char_length(text) BETWEEN 1 AND {QUESTION_TEXT_MAX_CHARS}",
                        name="ck_m6_questions_text_length"),
        # CASE, because Postgres doesn't promise to test `type` before jsonb_array_length
        CheckConstraint(
            "CASE WHEN type = 'mcq' THEN suggested_answer IS NULL AND answer IS NOT NULL AND options IS NOT NULL "
            "AND CASE WHEN jsonb_typeof(options) = 'array' THEN jsonb_array_length(options) BETWEEN 2 AND 6 "
            "AND answer >= 0 AND answer < jsonb_array_length(options) ELSE false END "
            "ELSE options IS NULL AND answer IS NULL AND suggested_answer IS NOT NULL END",
            name="ck_m6_questions_shape"),
        CheckConstraint("source_type IS NULL OR source_type IN ('page','slide','section')",
                        name="ck_m6_questions_source_type"),
        CheckConstraint("origin <> 'from_material' OR (source_file IS NOT NULL AND source_type IS NOT NULL "
                        "AND source_page IS NOT NULL)", name="ck_m6_questions_source"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    quiz_id: Mapped[int] = mapped_column(ForeignKey("m6_quizzes.id", ondelete="CASCADE"), nullable=False)
    position: Mapped[int] = mapped_column(nullable=False)               # 0-based order in the quiz
    type: Mapped[str] = mapped_column(String(16), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    # none_as_null: a Python None is SQL NULL, not the JSON value null
    options: Mapped[Optional[list[str]]] = mapped_column(JSONB(none_as_null=True))
    answer: Mapped[Optional[int]] = mapped_column()
    suggested_answer: Mapped[Optional[str]] = mapped_column(Text)
    topic: Mapped[Optional[str]] = mapped_column(String(TOPIC_MAX_CHARS))
    source_file: Mapped[Optional[str]] = mapped_column(String(SOURCE_FILE_MAX_CHARS))
    source_type: Mapped[Optional[str]] = mapped_column(String(16))      # page | slide | section
    source_page: Mapped[Optional[int]] = mapped_column()                # its number
    origin: Mapped[str] = mapped_column(String(16), nullable=False)
    explanation: Mapped[Optional[str]] = mapped_column(Text)
    approved: Mapped[bool] = mapped_column(nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(nullable=False)        # naive MYT
    updated_at: Mapped[datetime] = mapped_column(nullable=False)        # naive MYT


class QuizAttempt(Base):
    """One student's go at one quiz, graded or game (FR-607: one per student).

    Graded attempts (S44; rules in `quiz_timer`): `ends_at` is the server's final deadline of the whole
    attempt, whatever the timer mode. With a timer per question, the question at `current_index` of the
    layout ends at `question_ends_at`; both are as of the last touch, so read them through
    `quiz_timer.settle`. `layout` is the attempt's own order, fixed when it starts:
    `[{"question_id": 5, "options": [2, 0, 1]}, ...]` (`options`: stored option indexes in the order
    shown, null for a short answer)."""
    __tablename__ = "m6_attempts"
    __table_args__ = (
        UniqueConstraint("quiz_id", "student_id", name="uq_m6_attempts_quiz_student"),
        CheckConstraint("status IN ('in_progress','submitted')", name="ck_m6_attempts_status"),
        CheckConstraint("current_index IS NULL OR current_index >= 0", name="ck_m6_attempts_current_index"),
        Index("ix_m6_attempts_student", "student_id", "status"),
        Index("ix_m6_attempts_running", "ends_at", postgresql_where=text("status = 'in_progress'")),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    quiz_id: Mapped[int] = mapped_column(ForeignKey("m6_quizzes.id", ondelete="CASCADE"), nullable=False)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="in_progress")
    started_at: Mapped[datetime] = mapped_column(nullable=False)        # naive MYT
    ends_at: Mapped[Optional[datetime]] = mapped_column()               # server deadline of the attempt
    question_ends_at: Mapped[Optional[datetime]] = mapped_column()      # ...of its current question
    current_index: Mapped[Optional[int]] = mapped_column()              # per-question timer only
    layout: Mapped[Optional[list[dict[str, Any]]]] = mapped_column(JSONB(none_as_null=True))
    submitted_at: Mapped[Optional[datetime]] = mapped_column()
    auto_submitted: Mapped[bool] = mapped_column(nullable=False, default=False)


class QuizAnswer(Base):
    """The student's answer to one question; `option_index` for an MCQ, `text` for a short answer.
    Grading fills `correct` and `score` (a share of the question's mark, 0 to 1)."""
    __tablename__ = "m6_answers"
    __table_args__ = (
        UniqueConstraint("attempt_id", "question_id", name="uq_m6_answers_attempt_question"),
        CheckConstraint("score IS NULL OR score BETWEEN 0 AND 1", name="ck_m6_answers_score"),
        CheckConstraint(f"text IS NULL OR char_length(text) <= {ANSWER_TEXT_MAX_CHARS}",
                        name="ck_m6_answers_text_length"),
        Index("ix_m6_answers_question", "question_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    attempt_id: Mapped[int] = mapped_column(ForeignKey("m6_attempts.id", ondelete="CASCADE"), nullable=False)
    question_id: Mapped[int] = mapped_column(ForeignKey("m6_questions.id", ondelete="CASCADE"), nullable=False)
    option_index: Mapped[Optional[int]] = mapped_column()
    text: Mapped[Optional[str]] = mapped_column(Text)
    correct: Mapped[Optional[bool]] = mapped_column()
    score: Mapped[Optional[Decimal]] = mapped_column(Numeric(4, 3))
    answered_at: Mapped[datetime] = mapped_column(nullable=False)       # naive MYT, last change
