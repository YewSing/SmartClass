"""timezone_myt_server_defaults

Change server_default on all timestamp columns from NOW() (UTC) to
NOW() AT TIME ZONE 'Asia/Kuala_Lumpur' so DB-generated timestamps
are stored in Malaysia Time (UTC+8).

Revision ID: e1f2a3b4c5d6
Revises: d9e0f1a2b3c4
Create Date: 2026-06-06
"""
import sqlalchemy as sa
from alembic import op

revision = "e1f2a3b4c5d6"
down_revision = "d9e0f1a2b3c4"
branch_labels = None
depends_on = None

_MYT_DEFAULT = sa.text("(NOW() AT TIME ZONE 'Asia/Kuala_Lumpur')")
_UTC_DEFAULT  = sa.text("now()")

_COLUMNS = [
    ("users",                "created_at"),
    ("attendance_sessions",  "opened_at"),
    ("audit_logs",           "ts"),
    ("face_embeddings",      "created_at"),
    ("face_review_entries",  "flagged_at"),
]


def upgrade() -> None:
    for table, col in _COLUMNS:
        op.alter_column(table, col, server_default=_MYT_DEFAULT)


def downgrade() -> None:
    for table, col in _COLUMNS:
        op.alter_column(table, col, server_default=_UTC_DEFAULT)
