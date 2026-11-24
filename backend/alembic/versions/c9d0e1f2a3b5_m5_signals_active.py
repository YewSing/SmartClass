"""S38g: reactions and "I don't understand" are on/off (ended_at), one active per student per class.

Existing rows were momentary presses, so they are ended at the moment they were made.

Revision ID: c9d0e1f2a3b5
Revises: b8c9d0e1f2a4
Create Date: 2026-11-25
"""
import sqlalchemy as sa
from alembic import op

revision = "c9d0e1f2a3b5"
down_revision = "b8c9d0e1f2a4"
branch_labels = None
depends_on = None

TABLES = {"m5_reactions": "uq_m5_reactions_active", "m5_confusion_presses": "uq_m5_confusion_presses_active"}


def upgrade() -> None:
    for table, index in TABLES.items():
        op.add_column(table, sa.Column("ended_at", sa.DateTime(), nullable=True))
        op.execute(f"UPDATE {table} SET ended_at = created_at")  # noqa: S608 - fixed table names
        op.create_index(index, table, ["attendance_session_id", "student_id"], unique=True,
                        postgresql_where=sa.text("ended_at IS NULL"))


def downgrade() -> None:
    for table, index in TABLES.items():
        op.drop_index(index, table_name=table)
        op.drop_column(table, "ended_at")
