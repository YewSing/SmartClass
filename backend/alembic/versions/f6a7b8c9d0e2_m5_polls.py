"""S32: m5_polls, m5_poll_options, m5_poll_votes (FR-507–FR-509), live polls.

Revision ID: f6a7b8c9d0e2
Revises: e5f6a7b8c9d1
Create Date: 2026-11-22
"""
import sqlalchemy as sa
from alembic import op

revision = "f6a7b8c9d0e2"
down_revision = "e5f6a7b8c9d1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "m5_polls",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("attendance_session_id", sa.Integer(),
                  sa.ForeignKey("attendance_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("question", sa.String(300), nullable=False),
        sa.Column("multiple", sa.Boolean(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("show_results", sa.Boolean(), nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"),
                  nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("closed_at", sa.DateTime(), nullable=True),
        sa.CheckConstraint("status IN ('draft','open','closed')", name="ck_m5_polls_status"),
        sa.CheckConstraint("char_length(question) BETWEEN 1 AND 300", name="ck_m5_polls_question_length"),
    )
    op.create_index("ix_m5_polls_session", "m5_polls", ["attendance_session_id"])
    op.create_table(
        "m5_poll_options",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("poll_id", sa.Integer(), sa.ForeignKey("m5_polls.id", ondelete="CASCADE"), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("text", sa.String(120), nullable=False),
        sa.UniqueConstraint("poll_id", "position", name="uq_m5_poll_options_poll_position"),
        sa.CheckConstraint("char_length(text) BETWEEN 1 AND 120", name="ck_m5_poll_options_text_length"),
    )
    op.create_table(
        "m5_poll_votes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("poll_id", sa.Integer(), sa.ForeignKey("m5_polls.id", ondelete="CASCADE"), nullable=False),
        sa.Column("option_id", sa.Integer(), sa.ForeignKey("m5_poll_options.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("student_id", sa.Integer(), sa.ForeignKey("students.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("poll_id", "student_id", "option_id", name="uq_m5_poll_votes_poll_student_option"),
    )
    op.create_index("ix_m5_poll_votes_student", "m5_poll_votes", ["student_id"])


def downgrade() -> None:
    op.drop_index("ix_m5_poll_votes_student", table_name="m5_poll_votes")
    op.drop_table("m5_poll_votes")
    op.drop_table("m5_poll_options")
    op.drop_index("ix_m5_polls_session", table_name="m5_polls")
    op.drop_table("m5_polls")
