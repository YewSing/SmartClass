"""M2 read-only Moodle dashboard snapshots."""
import sqlalchemy as sa
from alembic import op

revision = "e4f5a6b7c8d9"
down_revision = "e3f4a5b6c7d8"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("dashboard_moodle_cache",
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("data", sa.JSON(), nullable=False),
        sa.Column("refreshed_at", sa.DateTime(timezone=True), nullable=False))


def downgrade():
    op.drop_table("dashboard_moodle_cache")
