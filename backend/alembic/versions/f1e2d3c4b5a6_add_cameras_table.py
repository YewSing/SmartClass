"""add_cameras_table

Adds the cameras table and a nullable camera_id FK on attendance_sessions.
Each camera maps to a physical room; sessions are auto-assigned the camera
for their occurrence's room at open time.

Revision ID: f1e2d3c4b5a6
Revises: 3f8a1b2c4d5e
Create Date: 2026-06-05
"""
from alembic import op
import sqlalchemy as sa

revision = "f1e2d3c4b5a6"
down_revision = "3f8a1b2c4d5e"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "cameras",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("label", sa.String(255), nullable=False),
        sa.Column("room", sa.String(255), nullable=False),
        sa.Column("device_id", sa.String(50), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="online"),
        sa.Column("ip_address", sa.String(50), nullable=True),
    )
    op.create_index("ix_cameras_room", "cameras", ["room"], unique=True)
    op.create_index("ix_cameras_device_id", "cameras", ["device_id"], unique=True)

    with op.batch_alter_table("attendance_sessions") as batch_op:
        batch_op.add_column(sa.Column("camera_id", sa.Integer(), nullable=True))
        batch_op.create_index("ix_attendance_sessions_camera_id", ["camera_id"])
        batch_op.create_foreign_key(
            "fk_attendance_sessions_camera_id",
            "cameras",
            ["camera_id"],
            ["id"],
        )


def downgrade() -> None:
    with op.batch_alter_table("attendance_sessions") as batch_op:
        batch_op.drop_constraint("fk_attendance_sessions_camera_id", type_="foreignkey")
        batch_op.drop_index("ix_attendance_sessions_camera_id")
        batch_op.drop_column("camera_id")

    op.drop_index("ix_cameras_device_id", table_name="cameras")
    op.drop_index("ix_cameras_room", table_name="cameras")
    op.drop_table("cameras")
