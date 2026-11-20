"""M2 recipient notifications."""
import sqlalchemy as sa
from alembic import op

revision = "e3f4a5b6c7d8"
down_revision = "b5c6d7e8f9a0"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("notifications",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column("event_key", sa.String(64), nullable=False),
        sa.Column("priority", sa.String(20), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("link", sa.String(500)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("user_id", "event_key", name="uq_notification_recipient_event"))
    op.create_index("ix_notifications_user_id", "notifications", ["user_id"])


def downgrade():
    op.drop_table("notifications")
