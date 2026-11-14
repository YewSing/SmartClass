"""interaction_session_ends_at

Shino lecturer dashboard: interaction sessions now carry an effective `ends_at` so the
"+15 min" button can extend an interaction session the same way it extends an attendance
session. Both sessions share one record per course time range (the session id is retained
across open/close), so `ends_at` is set on open and moved by extend.

Revision ID: a9b8c7d6e5f4
Revises: 5eeca85bd0fa
Create Date: 2026-11-14
"""
from alembic import op
import sqlalchemy as sa

revision = "a9b8c7d6e5f4"
down_revision = "5eeca85bd0fa"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("interaction_sessions", sa.Column("ends_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("interaction_sessions", "ends_at")
