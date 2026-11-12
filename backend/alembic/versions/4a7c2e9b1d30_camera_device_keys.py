"""camera_device_keys

T40 (FR-408, NFR-07, NFR-23): each camera device authenticates with its own key (stored as a
SHA-256 hash) and reports a heartbeat. Online/offline is computed from the last heartbeat, so the
stored `status` column (never updated by anything) is dropped.

Revision ID: 4a7c2e9b1d30
Revises: d0e1f2a3b4c5
Create Date: 2026-11-12
"""
import sqlalchemy as sa
from alembic import op

revision = "4a7c2e9b1d30"
down_revision = "d0e1f2a3b4c5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("cameras", sa.Column("key_hash", sa.String(64), nullable=True))
    op.add_column("cameras", sa.Column("key_created_at", sa.DateTime(), nullable=True))
    op.add_column("cameras", sa.Column("last_heartbeat_at", sa.DateTime(), nullable=True))
    op.create_index("ix_cameras_key_hash", "cameras", ["key_hash"], unique=True)
    op.drop_column("cameras", "status")


def downgrade() -> None:
    op.add_column("cameras", sa.Column("status", sa.String(20), nullable=False, server_default="online"))
    op.drop_index("ix_cameras_key_hash", table_name="cameras")
    op.drop_column("cameras", "last_heartbeat_at")
    op.drop_column("cameras", "key_created_at")
    op.drop_column("cameras", "key_hash")
