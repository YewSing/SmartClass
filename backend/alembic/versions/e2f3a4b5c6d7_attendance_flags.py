"""attendance_flags

T43: students flag "I'm here but wasn't recognised" (FR-318) and the lecturer confirms or rejects
(FR-319); unmatched face crops are kept per session as evidence (FR-407, FR-410, NFR-02).
`attendance_records.source` is 'student_flag' for a record made by confirming a flag.

Revision ID: e2f3a4b5c6d7
Revises: d1e2f3a4b5c6
Create Date: 2026-11-13
"""
from alembic import op
import sqlalchemy as sa
import pgvector.sqlalchemy

revision = "e2f3a4b5c6d7"
down_revision = "d1e2f3a4b5c6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "attendance_flags",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("session_id", sa.Integer(),
                  sa.ForeignKey("attendance_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("student_id", sa.Integer(), sa.ForeignKey("students.id", ondelete="CASCADE"), nullable=False),
        sa.Column("flagged_at", sa.DateTime(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("resolved_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("resolved_at", sa.DateTime(), nullable=True),
        sa.Column("reject_reason", sa.String(500), nullable=True),
        sa.Column("record_status", sa.String(20), nullable=True),
        sa.UniqueConstraint("session_id", "student_id", name="uq_attendance_flags_session_student"),
        sa.CheckConstraint("status IN ('pending','confirmed','rejected')", name="ck_attendance_flags_status"),
    )
    op.create_index("ix_attendance_flags_session_id", "attendance_flags", ["session_id"])
    op.create_index("ix_attendance_flags_student_id", "attendance_flags", ["student_id"])
    op.create_index("ix_attendance_flags_status", "attendance_flags", ["status"])

    op.create_table(
        "unmatched_faces",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("session_id", sa.Integer(),
                  sa.ForeignKey("attendance_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("camera_id", sa.Integer(), sa.ForeignKey("cameras.id", ondelete="SET NULL"), nullable=True),
        sa.Column("embedding", pgvector.sqlalchemy.Vector(512), nullable=False),
        sa.Column("image", sa.LargeBinary(), nullable=False),
        sa.Column("similarity", sa.Float(), nullable=True),
        sa.Column("captured_at", sa.DateTime(), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_unmatched_faces_session_id", "unmatched_faces", ["session_id"])
    op.create_index("ix_unmatched_faces_captured_at", "unmatched_faces", ["captured_at"])

    op.add_column("attendance_records", sa.Column("source", sa.String(20), nullable=True))


def downgrade() -> None:
    op.drop_column("attendance_records", "source")
    op.drop_index("ix_unmatched_faces_captured_at", table_name="unmatched_faces")
    op.drop_index("ix_unmatched_faces_session_id", table_name="unmatched_faces")
    op.drop_table("unmatched_faces")
    op.drop_index("ix_attendance_flags_status", table_name="attendance_flags")
    op.drop_index("ix_attendance_flags_student_id", table_name="attendance_flags")
    op.drop_index("ix_attendance_flags_session_id", table_name="attendance_flags")
    op.drop_table("attendance_flags")
