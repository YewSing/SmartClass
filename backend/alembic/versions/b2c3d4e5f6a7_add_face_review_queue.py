"""add_face_review_queue

Adds face_review_entries table for UC-07: flagged/unrecognised faces that the
admin can review and promote to student enrollment (FR-005).

Revision ID: b2c3d4e5f6a7
Revises: f1e2d3c4b5a6
Create Date: 2026-06-05
"""
from alembic import op
import sqlalchemy as sa
import pgvector.sqlalchemy

revision = "b2c3d4e5f6a7"
down_revision = "f1e2d3c4b5a6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "face_review_entries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("embedding", pgvector.sqlalchemy.Vector(512), nullable=False),
        sa.Column("session_id", sa.Integer(), sa.ForeignKey("attendance_sessions.id", ondelete="SET NULL"), nullable=True),
        sa.Column("camera_device_id", sa.String(50), nullable=True),
        sa.Column("similarity", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("occurrences", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("flagged_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_face_review_entries_flagged_at", "face_review_entries", ["flagged_at"])


def downgrade() -> None:
    op.drop_index("ix_face_review_entries_flagged_at", table_name="face_review_entries")
    op.drop_table("face_review_entries")
