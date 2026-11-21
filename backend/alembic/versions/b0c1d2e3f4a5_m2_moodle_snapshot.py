"""S16: m2_moodle_snapshot (FR-203), per-user Moodle announcements and deadlines.

Revision ID: b0c1d2e3f4a5
Revises: a9b0c1d2e3f4
Create Date: 2026-11-22
"""
import sqlalchemy as sa
from alembic import op

revision = "b0c1d2e3f4a5"
down_revision = "a9b0c1d2e3f4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "m2_moodle_snapshot",
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("announcements", sa.JSON(), nullable=False),
        sa.Column("deadlines", sa.JSON(), nullable=False),
        sa.Column("refreshed_at", sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("m2_moodle_snapshot")
