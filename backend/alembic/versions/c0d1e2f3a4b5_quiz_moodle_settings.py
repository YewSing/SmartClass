"""Moodle-style quiz settings: attempts_allowed + review_visible (S35).

`attempts_allowed` — how many attempts a student gets (default 1, FR-607's one attempt).
`review_visible` — whether the student may see their score / per-question results after
answering (Moodle's "review options"; default True).

Revision ID: c0d1e2f3a4b5
Revises: a9b8c7d6e5f4
Create Date: 2026-11-16
"""

from alembic import op
import sqlalchemy as sa

revision = "c0d1e2f3a4b5"
down_revision = "a9b8c7d6e5f4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "quizzes",
        sa.Column("attempts_allowed", sa.Integer(), nullable=False, server_default="1"),
    )
    op.add_column(
        "quizzes",
        sa.Column("review_visible", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    # attempts_allowed > 1 needs more than one attempt row per quiz+student — the S32
    # one-attempt constraint becomes a plain lookup index.
    op.drop_constraint("uq_quiz_attempts_quiz_student", "quiz_attempts", type_="unique")
    op.create_index("ix_quiz_attempts_quiz_student", "quiz_attempts", ["quiz_id", "student_id"])


def downgrade() -> None:
    op.drop_index("ix_quiz_attempts_quiz_student", table_name="quiz_attempts")
    op.create_unique_constraint("uq_quiz_attempts_quiz_student", "quiz_attempts", ["quiz_id", "student_id"])
    op.drop_column("quizzes", "review_visible")
    op.drop_column("quizzes", "attempts_allowed")
