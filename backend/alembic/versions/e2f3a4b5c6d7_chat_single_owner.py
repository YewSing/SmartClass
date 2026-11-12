"""chat_single_owner

Lets a lecturer own a chat ("ask my materials", FR-815). `ai_chat_sessions.student_id`
becomes nullable and a `lecturer_id` column is added; a CHECK constraint enforces exactly
one owner (a student or a lecturer), so a chat is always one or the other.

Revision ID: e2f3a4b5c6d7
Revises: d1e2f3a4b5c6
Create Date: 2026-11-13
"""
import sqlalchemy as sa
from alembic import op

revision = "e2f3a4b5c6d7"
down_revision = "d1e2f3a4b5c6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("ai_chat_sessions", "student_id", existing_type=sa.Integer(), nullable=True)
    op.add_column(
        "ai_chat_sessions",
        sa.Column("lecturer_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_ai_chat_sessions_lecturer_id_lecturers",
        "ai_chat_sessions",
        "lecturers",
        ["lecturer_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index("ix_ai_chat_sessions_lecturer_id", "ai_chat_sessions", ["lecturer_id"])
    op.create_check_constraint(
        "ck_ai_chat_sessions_single_owner",
        "ai_chat_sessions",
        "(student_id IS NOT NULL) <> (lecturer_id IS NOT NULL)",
    )


def downgrade() -> None:
    op.drop_constraint("ck_ai_chat_sessions_single_owner", "ai_chat_sessions", type_="check")
    op.drop_index("ix_ai_chat_sessions_lecturer_id", table_name="ai_chat_sessions")
    op.drop_constraint(
        "fk_ai_chat_sessions_lecturer_id_lecturers", "ai_chat_sessions", type_="foreignkey"
    )
    op.drop_column("ai_chat_sessions", "lecturer_id")
    op.alter_column("ai_chat_sessions", "student_id", existing_type=sa.Integer(), nullable=False)
