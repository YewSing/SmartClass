"""attendance_record_camera

T41 (FR-405): keep the device that recognised the student on the attendance record, so a
recognition can be traced to its camera. Nullable: records made by an override or a device
without a camera have none, and deleting a camera clears it (SET NULL).

Revision ID: 5b8d3f0a2c41
Revises: 4a7c2e9b1d30
Create Date: 2026-11-12
"""
import sqlalchemy as sa
from alembic import op

revision = "5b8d3f0a2c41"
down_revision = "4a7c2e9b1d30"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("attendance_records", sa.Column("camera_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_attendance_records_camera_id",
        "attendance_records",
        "cameras",
        ["camera_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_attendance_records_camera_id", "attendance_records", type_="foreignkey")
    op.drop_column("attendance_records", "camera_id")
