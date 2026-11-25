"""S45: grading (FR-616, FR-617): how an answer was graded, and when a quiz's results came out.

Revision ID: b4c5d6e7f8a0
Revises: a3b4c5d6e7f9
Create Date: 2026-11-25
"""
import sqlalchemy as sa
from alembic import op

revision = "b4c5d6e7f8a0"
down_revision = "a3b4c5d6e7f9"
branch_labels = None
depends_on = None

_CHECKS = {
    "ck_m6_answers_graded_by": "graded_by IS NULL OR graded_by IN ('auto','ai','lecturer')",
    "ck_m6_answers_confidence": "confidence IS NULL OR confidence BETWEEN 0 AND 1",
    "ck_m6_answers_reason_length": "reason IS NULL OR char_length(reason) <= 500",
    "ck_m6_answers_feedback_length": "feedback IS NULL OR char_length(feedback) <= 1000",
}
_COLUMNS = ("graded_by", "graded_at", "reason", "confidence", "flagged", "feedback", "grade_tries", "grade_after")


def upgrade() -> None:
    op.add_column("m6_quizzes", sa.Column("released_at", sa.DateTime(), nullable=True))
    op.add_column("m6_answers", sa.Column("graded_by", sa.String(16), nullable=True))
    op.add_column("m6_answers", sa.Column("graded_at", sa.DateTime(), nullable=True))
    op.add_column("m6_answers", sa.Column("reason", sa.Text(), nullable=True))
    op.add_column("m6_answers", sa.Column("confidence", sa.Numeric(4, 3), nullable=True))
    op.add_column("m6_answers", sa.Column("flagged", sa.Boolean(), nullable=False, server_default=sa.text("false")))
    op.add_column("m6_answers", sa.Column("feedback", sa.Text(), nullable=True))
    op.add_column("m6_answers", sa.Column("grade_tries", sa.Integer(), nullable=False, server_default=sa.text("0")))
    op.add_column("m6_answers", sa.Column("grade_after", sa.DateTime(), nullable=True))
    for name, rule in _CHECKS.items():
        op.create_check_constraint(name, "m6_answers", rule)
    op.create_index("ix_m6_answers_pending", "m6_answers", ["attempt_id"],
                    postgresql_where=sa.text("score IS NULL AND text IS NOT NULL"))


def downgrade() -> None:
    op.drop_index("ix_m6_answers_pending", table_name="m6_answers")
    for name in _CHECKS:
        op.drop_constraint(name, "m6_answers", type_="check")
    for name in reversed(_COLUMNS):
        op.drop_column("m6_answers", name)
    op.drop_column("m6_quizzes", "released_at")
