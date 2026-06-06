"""nullable_occurrence_lecturer

Allow class_occurrences.lecturer_id to be NULL so admins can unassign
a lecturer from an occurrence without requiring an immediate replacement.

Revision ID: a1b2c3d4e5f6
Revises: e1f2a3b4c5d6
Create Date: 2026-06-06
"""
import sqlalchemy as sa
from alembic import op

revision = "a1b2c3d4e5f6"
down_revision = "e1f2a3b4c5d6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "class_occurrences",
        "lecturer_id",
        existing_type=sa.Integer(),
        nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "class_occurrences",
        "lecturer_id",
        existing_type=sa.Integer(),
        nullable=False,
    )
