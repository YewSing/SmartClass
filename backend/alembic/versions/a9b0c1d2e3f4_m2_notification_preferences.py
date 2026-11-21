"""S15: m2_notification_preferences (FR-214) + created_at index for retention (FR-218).

Revision ID: a9b0c1d2e3f4
Revises: f8a9b0c1d2e3
Create Date: 2026-11-22
"""
import sqlalchemy as sa
from alembic import op

revision = "a9b0c1d2e3f4"
down_revision = "f8a9b0c1d2e3"
branch_labels = None
depends_on = None

_NOW = sa.text("(NOW() AT TIME ZONE 'Asia/Kuala_Lumpur')")


def upgrade() -> None:
    op.create_table(
        "m2_notification_preferences",
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("push_general", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("email_general", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=_NOW),
    )
    op.create_index("ix_m2_notifications_created", "m2_notifications", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_m2_notifications_created", table_name="m2_notifications")
    op.drop_table("m2_notification_preferences")
