"""S44: graded attempts (FR-607, FR-608): the attempt's own order, its current question and deadline.

Revision ID: a3b4c5d6e7f9
Revises: f2a3b4c5d6e8
Create Date: 2026-11-25
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "a3b4c5d6e7f9"
down_revision = "f2a3b4c5d6e8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("m6_attempts", sa.Column("layout", postgresql.JSONB(), nullable=True))
    op.add_column("m6_attempts", sa.Column("current_index", sa.Integer(), nullable=True))
    op.add_column("m6_attempts", sa.Column("question_ends_at", sa.DateTime(), nullable=True))
    op.create_check_constraint("ck_m6_attempts_current_index", "m6_attempts",
                               "current_index IS NULL OR current_index >= 0")
    op.create_index("ix_m6_attempts_running", "m6_attempts", ["ends_at"],
                    postgresql_where=sa.text("status = 'in_progress'"))


def downgrade() -> None:
    op.drop_index("ix_m6_attempts_running", table_name="m6_attempts")
    op.drop_constraint("ck_m6_attempts_current_index", "m6_attempts", type_="check")
    op.drop_column("m6_attempts", "question_ends_at")
    op.drop_column("m6_attempts", "current_index")
    op.drop_column("m6_attempts", "layout")
