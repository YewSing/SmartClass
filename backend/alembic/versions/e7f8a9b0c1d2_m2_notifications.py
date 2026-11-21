"""S10: m2_notifications — Module 2 in-app notification store (FR-205–FR-207, FR-216).

Revision ID: e7f8a9b0c1d2
Revises: b5c6d7e8f9a0
Create Date: 2026-11-22
"""
import sqlalchemy as sa
from alembic import op

revision = "e7f8a9b0c1d2"
down_revision = "b5c6d7e8f9a0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "m2_notifications",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("event", sa.String(64), nullable=False),
        sa.Column("priority", sa.String(16), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("link", sa.String(300), nullable=True),
        sa.Column("subject_key", sa.String(200), nullable=False),
        sa.Column("read_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False,
                  server_default=sa.text("(NOW() AT TIME ZONE 'Asia/Kuala_Lumpur')")),
        sa.CheckConstraint("priority IN ('urgent','important','general')", name="ck_m2_notifications_priority"),
    )
    op.create_index("ix_m2_notifications_user_created", "m2_notifications", ["user_id", "created_at"])
    op.create_index("ix_m2_notifications_dedup", "m2_notifications",
                    ["user_id", "event", "subject_key", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_m2_notifications_dedup", table_name="m2_notifications")
    op.drop_index("ix_m2_notifications_user_created", table_name="m2_notifications")
    op.drop_table("m2_notifications")
