"""face_review_closest_match

Adds closest_match_student_id and closest_match_confidence to
face_review_entries so the review queue can surface the best-guess
enrolled student for each unrecognised face (FR-005 enrichment).

Revision ID: d9e0f1a2b3c4
Revises: b2c3d4e5f6a7
Create Date: 2026-06-06
"""
from alembic import op
import sqlalchemy as sa

revision = "d9e0f1a2b3c4"
down_revision = "b2c3d4e5f6a7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "face_review_entries",
        sa.Column(
            "closest_match_student_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column(
        "face_review_entries",
        sa.Column("closest_match_confidence", sa.Float(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("face_review_entries", "closest_match_confidence")
    op.drop_column("face_review_entries", "closest_match_student_id")
