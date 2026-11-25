"""S43: m6_quizzes.published_at, when the quiz was published (FR-606).

Revision ID: f2a3b4c5d6e8
Revises: e1f2a3b4c5d7
Create Date: 2026-11-25
"""
import sqlalchemy as sa
from alembic import op

revision = "f2a3b4c5d6e8"
down_revision = "e1f2a3b4c5d7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("m6_quizzes", sa.Column("published_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("m6_quizzes", "published_at")
