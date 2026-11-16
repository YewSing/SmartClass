"""Add score column to quiz_questions (S35/Module 6 scoring).

Revision ID: b1c2d3e4f5a6
Revises: c0d1e2f3a4b5
Create Date: 2026-11-16
"""

from alembic import op
import sqlalchemy as sa

revision = "b1c2d3e4f5a6"
down_revision = "c0d1e2f3a4b5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "quiz_questions",
        sa.Column("score", sa.Float(), nullable=False, server_default="1.0"),
    )


def downgrade() -> None:
    op.drop_column("quiz_questions", "score")
