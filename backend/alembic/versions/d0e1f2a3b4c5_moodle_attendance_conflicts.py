"""moodle_attendance_conflicts

T36 (FR-312, FR-320): statuses changed in Moodle are kept as conflicts for the lecturer to resolve,
and synced sessions are re-read on a schedule.

Revision ID: d0e1f2a3b4c5
Revises: c9d0e1f2a3b4
Create Date: 2026-11-12
"""
import sqlalchemy as sa
from alembic import op

revision = "d0e1f2a3b4c5"
down_revision = "c9d0e1f2a3b4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("attendance_records", sa.Column("moodle_status_found", sa.String(20), nullable=True))
    op.add_column("attendance_records", sa.Column("moodle_overwrite_ok", sa.Boolean(), nullable=False,
                                                  server_default=sa.false()))
    op.create_check_constraint(
        "ck_attendance_records_moodle_status_found", "attendance_records",
        "moodle_status_found IN ('present','late','excused','absent','none','other')",
    )
    op.add_column("attendance_sessions", sa.Column("moodle_checked_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("attendance_sessions", "moodle_checked_at")
    op.drop_constraint("ck_attendance_records_moodle_status_found", "attendance_records", type_="check")
    op.drop_column("attendance_records", "moodle_overwrite_ok")
    op.drop_column("attendance_records", "moodle_status_found")
