"""S42: m6_quizzes.ai_scope, what the AI may draft from (FR-602, FR-604).

Revision ID: e1f2a3b4c5d7
Revises: d0e1f2a3b4c6
Create Date: 2026-11-25
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "e1f2a3b4c5d7"
down_revision = "d0e1f2a3b4c6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("m6_quizzes", sa.Column("ai_scope", postgresql.JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column("m6_quizzes", "ai_scope")
