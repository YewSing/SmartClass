"""Add learning_hint column to quiz_questions.

Revision ID: d2e3f4a5b6c7
Revises: b1c2d3e4f5a6
Create Date: 2026-11-16
"""

from alembic import op
import sqlalchemy as sa

revision = "d2e3f4a5b6c7"
down_revision = "b1c2d3e4f5a6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "quiz_questions",
        sa.Column("learning_hint", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("quiz_questions", "learning_hint")
