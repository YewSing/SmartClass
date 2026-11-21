"""S13: m2_push_tokens — Expo push tokens, one row per device (FR-210, FR-212).

Revision ID: f8a9b0c1d2e3
Revises: e7f8a9b0c1d2
Create Date: 2026-11-22
"""
import sqlalchemy as sa
from alembic import op

revision = "f8a9b0c1d2e3"
down_revision = "e7f8a9b0c1d2"
branch_labels = None
depends_on = None

_NOW = sa.text("(NOW() AT TIME ZONE 'Asia/Kuala_Lumpur')")


def upgrade() -> None:
    op.create_table(
        "m2_push_tokens",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token", sa.String(200), nullable=False, unique=True),
        sa.Column("platform", sa.String(16), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=_NOW),
        sa.Column("last_seen_at", sa.DateTime(), nullable=False, server_default=_NOW),
        sa.CheckConstraint("platform IN ('android','ios')", name="ck_m2_push_tokens_platform"),
    )
    op.create_index("ix_m2_push_tokens_user", "m2_push_tokens", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_m2_push_tokens_user", table_name="m2_push_tokens")
    op.drop_table("m2_push_tokens")
