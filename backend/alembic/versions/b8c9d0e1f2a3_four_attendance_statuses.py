"""four_attendance_statuses

T30 (FR-302–FR-304): attendance records may only be present | late | excused | absent.
Existing 'unidentified' (and any other) rows become 'absent'; unidentified faces live only
in face_review_entries.

Revision ID: b8c9d0e1f2a3
Revises: a7b8c9d0e1f2
Create Date: 2026-11-11
"""
import sqlalchemy as sa
from alembic import op

revision = "b8c9d0e1f2a3"
down_revision = "a7b8c9d0e1f2"
branch_labels = None
depends_on = None

MAP_UNKNOWN_TO_ABSENT = sa.text("""
    UPDATE attendance_records
    SET status = 'absent'
    WHERE status NOT IN ('present','late','excused','absent')
""")


def upgrade() -> None:
    op.execute(MAP_UNKNOWN_TO_ABSENT)
    op.create_check_constraint(
        "ck_attendance_records_status", "attendance_records",
        "status IN ('present','late','excused','absent')",
    )


def downgrade() -> None:
    # The 'unidentified' rows cannot be restored; the upgrade mapped every unknown status to
    # 'absent', so only the constraint is dropped here.
    op.drop_constraint("ck_attendance_records_status", "attendance_records", type_="check")
