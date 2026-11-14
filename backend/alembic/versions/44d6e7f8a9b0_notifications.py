"""notifications

S10/S31 prerequisite (FR-205, FR-206, FR-211): the notification store. A notification
belongs to a user, carries an event name, a priority (urgent|important|general with a
CHECK), a JSON payload, created_at, read_at and delivered flags. `notify.emit(event,
user_ids, payload, priority=...)` is the single entry point; priority defaults to
`general` so existing T44-style call sites keep working. General notifications are
feed-only (S11 leaves them out of channels).

Revision ID: 44d6e7f8a9b0
Revises: 32b4c5d6e7f8
Create Date: 2026-11-13
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "44d6e7f8a9b0"
down_revision = "32b4c5d6e7f8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "notifications",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False, index=True),
        sa.Column("event", sa.String(100), nullable=False),
        sa.Column("priority", sa.String(20), nullable=False, server_default="general"),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("read_at", sa.DateTime(), nullable=True),
        sa.Column("delivered_push", sa.Boolean(), nullable=False, server_default=sa.sql.false()),
        sa.Column("delivered_email", sa.Boolean(), nullable=False, server_default=sa.sql.false()),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_notifications_user"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("priority IN ('urgent','important','general')",
                           name="ck_notifications_priority"),
    )


def downgrade() -> None:
    op.drop_table("notifications")
