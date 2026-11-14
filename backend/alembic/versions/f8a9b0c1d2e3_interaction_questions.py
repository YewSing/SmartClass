"""interaction_questions

S21 (FR-502, FR-503, FR-509 part): questions in an interaction session. The student's
identity is always stored (FR-509 counting) but never exposed in responses when anonymous.

Revision ID: f8a9b0c1d2e3
Revises: e7f8a9b0c1d2
Create Date: 2026-11-13
"""
import sqlalchemy as sa
from alembic import op

revision = "f8a9b0c1d2e3"
down_revision = "e7f8a9b0c1d2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "interaction_questions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("interaction_id", sa.Integer(), nullable=False, index=True),
        sa.Column("student_id", sa.Integer(), nullable=False, index=True),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("anonymous", sa.Boolean(), nullable=False, server_default=sa.sql.false()),
        sa.Column("answered", sa.Boolean(), nullable=False, server_default=sa.sql.false()),
        sa.Column("answered_by", sa.Integer(), nullable=True),
        sa.Column("answered_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(
            ["interaction_id"], ["interaction_sessions.id"],
            name="fk_interaction_questions_interaction",
        ),
        sa.ForeignKeyConstraint(
            ["student_id"], ["students.id"], name="fk_interaction_questions_student",
        ),
        sa.ForeignKeyConstraint(
            ["answered_by"], ["users.id"], name="fk_interaction_questions_answered_by",
        ),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("interaction_questions")
