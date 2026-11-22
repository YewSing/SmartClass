"""S31: m5_questions and m5_question_votes (FR-503–FR-506), live questions.

Revision ID: e5f6a7b8c9d1
Revises: d2e3f4a5b6c7
Create Date: 2026-11-22
"""
import sqlalchemy as sa
from alembic import op

revision = "e5f6a7b8c9d1"
down_revision = "d2e3f4a5b6c7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "m5_questions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("attendance_session_id", sa.Integer(),
                  sa.ForeignKey("attendance_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("student_id", sa.Integer(), sa.ForeignKey("students.id", ondelete="SET NULL"),
                  nullable=True),
        sa.Column("text", sa.String(500), nullable=False),
        sa.Column("anonymous", sa.Boolean(), nullable=False),
        sa.Column("answered_at", sa.DateTime(), nullable=True),
        sa.Column("pinned", sa.Boolean(), nullable=False),
        sa.Column("hidden", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("char_length(text) BETWEEN 1 AND 500", name="ck_m5_questions_text_length"),
    )
    op.create_index("ix_m5_questions_session", "m5_questions", ["attendance_session_id"])
    op.create_index("ix_m5_questions_student", "m5_questions", ["student_id"])
    op.create_table(
        "m5_question_votes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("question_id", sa.Integer(), sa.ForeignKey("m5_questions.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("student_id", sa.Integer(), sa.ForeignKey("students.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("question_id", "student_id", name="uq_m5_question_votes_question_student"),
    )


def downgrade() -> None:
    op.drop_table("m5_question_votes")
    op.drop_index("ix_m5_questions_student", table_name="m5_questions")
    op.drop_index("ix_m5_questions_session", table_name="m5_questions")
    op.drop_table("m5_questions")
