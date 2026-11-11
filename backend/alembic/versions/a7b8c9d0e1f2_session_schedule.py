"""session_schedule

T29 (FR-301, FR-315–FR-317): a class occurrence may have no schedule, and an attendance
session knows its class date, its effective start/end, whether it came from the timetable
or was started by hand, and the last in-class lecturer action.

Revision ID: a7b8c9d0e1f2
Revises: f7a8b9c0d1e2
Create Date: 2026-11-11
"""
import sqlalchemy as sa
from alembic import op

revision = "a7b8c9d0e1f2"
down_revision = "f7a8b9c0d1e2"
branch_labels = None
depends_on = None

BACKFILL = sa.text("""
    UPDATE attendance_sessions
    SET class_date = opened_at::date, starts_at = opened_at, ends_at = closed_at
""")


def upgrade() -> None:
    for column in ("day_of_week", "start_time", "end_time"):
        op.alter_column("class_occurrences", column, existing_type=sa.String(10), nullable=True)

    op.add_column("attendance_sessions", sa.Column("class_date", sa.Date(), nullable=True))
    op.add_column("attendance_sessions", sa.Column("starts_at", sa.DateTime(), nullable=True))
    op.add_column("attendance_sessions", sa.Column("ends_at", sa.DateTime(), nullable=True))
    op.add_column("attendance_sessions", sa.Column("source", sa.String(20), nullable=False,
                                                   server_default="manual"))
    op.add_column("attendance_sessions", sa.Column("lecturer_action_at", sa.DateTime(), nullable=True))
    op.alter_column("attendance_sessions", "opened_at", existing_type=sa.DateTime(), nullable=True)
    op.create_index("ix_attendance_sessions_class_date", "attendance_sessions", ["class_date"])

    op.execute(BACKFILL)

    op.create_check_constraint(
        "ck_attendance_sessions_status", "attendance_sessions",
        "status IN ('scheduled','open','closed','needs_confirmation','cancelled')",
    )
    op.create_check_constraint(
        "ck_attendance_sessions_source", "attendance_sessions",
        "source IN ('schedule','manual')",
    )
    op.create_index(
        "uq_attendance_sessions_schedule_date", "attendance_sessions",
        ["occurrence_id", "class_date"], unique=True,
        postgresql_where=sa.text("source = 'schedule'"),
    )


def downgrade() -> None:
    op.drop_index("uq_attendance_sessions_schedule_date", table_name="attendance_sessions",
                  postgresql_where=sa.text("source = 'schedule'"))
    op.drop_constraint("ck_attendance_sessions_source", "attendance_sessions", type_="check")
    op.drop_constraint("ck_attendance_sessions_status", "attendance_sessions", type_="check")

    # Rows that were never opened (scheduled / cancelled ahead) cannot exist without the column.
    op.execute("DELETE FROM attendance_sessions WHERE opened_at IS NULL")
    op.alter_column("attendance_sessions", "opened_at", existing_type=sa.DateTime(), nullable=False)

    op.drop_index("ix_attendance_sessions_class_date", table_name="attendance_sessions")
    for column in ("lecturer_action_at", "source", "ends_at", "starts_at", "class_date"):
        op.drop_column("attendance_sessions", column)

    # Lossy (dev only): a class without a schedule has no representation before T29.
    op.execute("""
        UPDATE class_occurrences
        SET day_of_week = 'Mon', start_time = '00:00', end_time = '00:00'
        WHERE day_of_week IS NULL OR start_time IS NULL OR end_time IS NULL
    """)
    for column in ("day_of_week", "start_time", "end_time"):
        op.alter_column("class_occurrences", column, existing_type=sa.String(10), nullable=False)
