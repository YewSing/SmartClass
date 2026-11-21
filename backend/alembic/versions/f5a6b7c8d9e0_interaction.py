"""Module 5 classroom interaction tables.

Revision ID: f5a6b7c8d9e0
Revises: e4f5a6b7c8d9
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "f5a6b7c8d9e0"
down_revision: str | None = "e4f5a6b7c8d9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "m5_questions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("attendance_session_id", sa.Integer(), sa.ForeignKey("attendance_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("student_id", sa.Integer(), sa.ForeignKey("students.id"), nullable=False),
        sa.Column("text", sa.String(1000), nullable=False),
        sa.Column("anonymous", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("answered", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("pinned", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("hidden", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_m5_questions_attendance_session_id", "m5_questions", ["attendance_session_id"])
    op.create_index("ix_m5_questions_student_id", "m5_questions", ["student_id"])

    op.create_table(
        "m5_polls",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("attendance_session_id", sa.Integer(), sa.ForeignKey("attendance_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("prompt", sa.String(500), nullable=False),
        sa.Column("options", sa.JSON(), nullable=False),
        sa.Column("multiple", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("show_results", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("started_at", sa.DateTime()),
        sa.Column("closed_at", sa.DateTime()),
        sa.CheckConstraint("status IN ('draft','open','closed')", name="ck_m5_polls_status"),
    )
    op.create_index("ix_m5_polls_attendance_session_id", "m5_polls", ["attendance_session_id"])

    op.create_table(
        "m5_ballots",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("poll_id", sa.Integer(), sa.ForeignKey("m5_polls.id", ondelete="CASCADE"), nullable=False),
        sa.Column("student_id", sa.Integer(), sa.ForeignKey("students.id"), nullable=False),
        sa.Column("option_indexes", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("poll_id", "student_id", name="uq_m5_ballot_student"),
    )
    op.create_index("ix_m5_ballots_poll_id", "m5_ballots", ["poll_id"])
    op.create_index("ix_m5_ballots_student_id", "m5_ballots", ["student_id"])

    op.create_table(
        "m5_quick_prompts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("attendance_session_id", sa.Integer(), sa.ForeignKey("attendance_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("prompt", sa.String(500), nullable=False),
        sa.Column("max_length", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="open"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("closed_at", sa.DateTime()),
        sa.CheckConstraint("status IN ('open','closed')", name="ck_m5_quick_prompts_status"),
    )
    op.create_index("ix_m5_quick_prompts_attendance_session_id", "m5_quick_prompts", ["attendance_session_id"])

    op.create_table(
        "m5_quick_answers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("quick_prompt_id", sa.Integer(), sa.ForeignKey("m5_quick_prompts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("student_id", sa.Integer(), sa.ForeignKey("students.id"), nullable=False),
        sa.Column("text", sa.String(1000), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("quick_prompt_id", "student_id", name="uq_m5_quick_answer_student"),
    )
    op.create_index("ix_m5_quick_answers_quick_prompt_id", "m5_quick_answers", ["quick_prompt_id"])
    op.create_index("ix_m5_quick_answers_student_id", "m5_quick_answers", ["student_id"])

    op.create_table(
        "m5_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("attendance_session_id", sa.Integer(), sa.ForeignKey("attendance_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("student_id", sa.Integer(), sa.ForeignKey("students.id"), nullable=False),
        sa.Column("kind", sa.String(40), nullable=False),
        sa.Column("occurred_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("question_id", sa.Integer(), sa.ForeignKey("m5_questions.id", ondelete="CASCADE")),
        sa.Column("poll_id", sa.Integer(), sa.ForeignKey("m5_polls.id", ondelete="CASCADE")),
        sa.Column("quick_prompt_id", sa.Integer(), sa.ForeignKey("m5_quick_prompts.id", ondelete="CASCADE")),
        sa.Column("reaction", sa.String(30)),
        sa.Column("topic_tag", sa.String(100)),
    )
    op.create_index("ix_m5_events_session_kind_time", "m5_events", ["attendance_session_id", "kind", "occurred_at"])
    op.create_index("ix_m5_events_session_student_kind_time", "m5_events", ["attendance_session_id", "student_id", "kind", "occurred_at"])
    op.create_index("uq_m5_question_upvote_student", "m5_events", ["question_id", "student_id"], unique=True, postgresql_where=sa.text("kind = 'question.upvoted'"))


def downgrade() -> None:
    op.drop_table("m5_events")
    op.drop_table("m5_quick_answers")
    op.drop_table("m5_quick_prompts")
    op.drop_table("m5_ballots")
    op.drop_table("m5_polls")
    op.drop_table("m5_questions")

