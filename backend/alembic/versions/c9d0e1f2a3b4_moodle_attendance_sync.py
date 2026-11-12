"""moodle_attendance_sync

T35 (FR-311, NFR-20, NFR-22): sync state of closed sessions to Moodle Attendance.
Sessions closed before this migration keep a NULL sync status, so they are never sent.

Revision ID: c9d0e1f2a3b4
Revises: b8c9d0e1f2a3
Create Date: 2026-11-12
"""
import sqlalchemy as sa
from alembic import op

revision = "c9d0e1f2a3b4"
down_revision = "b8c9d0e1f2a3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("attendance_sessions", sa.Column("moodle_sync_status", sa.String(20), nullable=True))
    op.add_column("attendance_sessions", sa.Column("moodle_session_id", sa.Integer(), nullable=True))
    op.add_column("attendance_sessions", sa.Column("moodle_sync_attempts", sa.Integer(), nullable=False,
                                                   server_default="0"))
    op.add_column("attendance_sessions", sa.Column("moodle_sync_next_at", sa.DateTime(), nullable=True))
    op.add_column("attendance_sessions", sa.Column("moodle_synced_at", sa.DateTime(), nullable=True))
    op.add_column("attendance_sessions", sa.Column("moodle_sync_error", sa.String(255), nullable=True))
    op.create_check_constraint(
        "ck_attendance_sessions_moodle_sync_status", "attendance_sessions",
        "moodle_sync_status IN ('pending','synced','failed','conflict')",
    )
    op.create_index("ix_attendance_sessions_moodle_sync_status", "attendance_sessions", ["moodle_sync_status"])

    op.add_column("attendance_records", sa.Column("moodle_status_sent", sa.String(20), nullable=True))
    op.create_check_constraint(
        "ck_attendance_records_moodle_status_sent", "attendance_records",
        "moodle_status_sent IN ('present','late','excused','absent')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_attendance_records_moodle_status_sent", "attendance_records", type_="check")
    op.drop_column("attendance_records", "moodle_status_sent")
    op.drop_index("ix_attendance_sessions_moodle_sync_status", table_name="attendance_sessions")
    op.drop_constraint("ck_attendance_sessions_moodle_sync_status", "attendance_sessions", type_="check")
    for col in ("moodle_sync_error", "moodle_synced_at", "moodle_sync_next_at", "moodle_sync_attempts",
                "moodle_session_id", "moodle_sync_status"):
        op.drop_column("attendance_sessions", col)
