"""S30: m5_interaction_sessions (FR-501, FR-502), interaction tied to the M3 class session.

Revision ID: d2e3f4a5b6c7
Revises: c1d2e3f4a5b6
Create Date: 2026-11-22
"""
import sqlalchemy as sa
from alembic import op

revision = "d2e3f4a5b6c7"
down_revision = "c1d2e3f4a5b6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "m5_interaction_sessions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("attendance_session_id", sa.Integer(),
                  sa.ForeignKey("attendance_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("closed_reason", sa.String(16), nullable=True),
        sa.Column("opened_at", sa.DateTime(), nullable=True),
        sa.Column("closed_at", sa.DateTime(), nullable=True),
        sa.Column("closed_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"),
                  nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False,
                  server_default=sa.text("(NOW() AT TIME ZONE 'Asia/Kuala_Lumpur')")),
        sa.CheckConstraint("status IN ('open','closed')", name="ck_m5_interaction_sessions_status"),
        sa.CheckConstraint("closed_reason IS NULL OR closed_reason IN ('lecturer','class_ended')",
                           name="ck_m5_interaction_sessions_closed_reason"),
        sa.UniqueConstraint("attendance_session_id",
                            name="m5_interaction_sessions_attendance_session_id_key"),
    )
    op.create_index("ix_m5_interaction_sessions_status", "m5_interaction_sessions", ["status"])


def downgrade() -> None:
    op.drop_index("ix_m5_interaction_sessions_status", table_name="m5_interaction_sessions")
    op.drop_table("m5_interaction_sessions")
