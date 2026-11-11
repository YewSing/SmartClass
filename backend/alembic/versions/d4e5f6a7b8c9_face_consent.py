"""face_consent

PDPA face-data consent records (T14, FR-109, FR-116, NFR-03): one row per acceptance with
the notice version and time; withdrawal sets withdrawn_at.

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-11-09
"""
import sqlalchemy as sa
from alembic import op

revision = "d4e5f6a7b8c9"
down_revision = "c3d4e5f6a7b8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "face_consents",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("student_id", sa.Integer(), sa.ForeignKey("students.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version", sa.String(length=50), nullable=False),
        sa.Column("accepted_at", sa.DateTime(), nullable=False,
                  server_default=sa.text("(NOW() AT TIME ZONE 'Asia/Kuala_Lumpur')")),
        sa.Column("withdrawn_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_face_consents_student_id", "face_consents", ["student_id"])


def downgrade() -> None:
    op.drop_index("ix_face_consents_student_id", table_name="face_consents")
    op.drop_table("face_consents")
