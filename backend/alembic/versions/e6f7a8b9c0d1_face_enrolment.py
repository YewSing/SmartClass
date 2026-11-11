"""face_enrolment

Face self-enrolment submissions (T16, FR-110–FR-115) and the photos of pending ones,
which are deleted once a decision is made (NFR-01).

Revision ID: e6f7a8b9c0d1
Revises: d4e5f6a7b8c9
Create Date: 2026-11-09
"""
import pgvector.sqlalchemy
import sqlalchemy as sa
from alembic import op

revision = "e6f7a8b9c0d1"
down_revision = "d4e5f6a7b8c9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "face_enrolments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("student_id", sa.Integer(), sa.ForeignKey("students.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("submitted_at", sa.DateTime(), nullable=False,
                  server_default=sa.text("(NOW() AT TIME ZONE 'Asia/Kuala_Lumpur')")),
        sa.Column("decided_at", sa.DateTime(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("check_reasons", sa.JSON(), nullable=False),
        sa.Column("submitted_anyway", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("face_score", sa.Float(), nullable=True),
        sa.Column("ocr_matric", sa.String(length=50), nullable=True),
        sa.Column("ocr_matric_confidence", sa.Float(), nullable=True),
        sa.Column("name_score", sa.Float(), nullable=True),
        sa.Column("quality_scores", sa.JSON(), nullable=True),
        sa.Column("ocr_lines", sa.JSON(), nullable=True),
        sa.Column("embedding", pgvector.sqlalchemy.Vector(512), nullable=True),
    )
    op.create_index("ix_face_enrolments_student_id", "face_enrolments", ["student_id"])
    op.create_table(
        "face_enrolment_images",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("enrolment_id", sa.Integer(),
                  sa.ForeignKey("face_enrolments.id", ondelete="CASCADE"), nullable=False),
        sa.Column("kind", sa.String(length=10), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("content_type", sa.String(length=50), nullable=False),
        sa.Column("data", sa.LargeBinary(), nullable=False),
    )
    op.create_index("ix_face_enrolment_images_enrolment_id", "face_enrolment_images", ["enrolment_id"])


def downgrade() -> None:
    op.drop_index("ix_face_enrolment_images_enrolment_id", table_name="face_enrolment_images")
    op.drop_table("face_enrolment_images")
    op.drop_index("ix_face_enrolments_student_id", table_name="face_enrolments")
    op.drop_table("face_enrolments")
