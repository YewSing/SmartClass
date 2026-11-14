"""quiz_attempts

S32 (FR-606, FR-607, FR-608): taking quizzes + auto-grade. One attempt per student per
published quiz, a server-side deadline (started_at + time limit), submission after expiry
rejected, MCQ answers auto-graded on submission, short answers left unscored, and a
background check that auto-submits expired attempts.

Revision ID: 55e7f8a9b0c1
Revises: 44d6e7f8a9b0
Create Date: 2026-11-13
"""
import sqlalchemy as sa
from alembic import op

revision = "55e7f8a9b0c1"
down_revision = "44d6e7f8a9b0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "quiz_attempts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("quiz_id", sa.Integer(), nullable=False, index=True),
        sa.Column("student_id", sa.Integer(), nullable=False, index=True),
        sa.Column("started_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("deadline", sa.DateTime(), nullable=False),
        sa.Column("submitted_at", sa.DateTime(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="started"),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("auto_submitted", sa.Boolean(), nullable=False, server_default=sa.sql.false()),
        sa.ForeignKeyConstraint(["quiz_id"], ["quizzes.id"], name="fk_quiz_attempts_quiz"),
        sa.ForeignKeyConstraint(["student_id"], ["students.id"], name="fk_quiz_attempts_student"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("status IN ('started','submitted','auto_submitted')",
                           name="ck_quiz_attempts_status"),
        sa.UniqueConstraint("quiz_id", "student_id", name="uq_quiz_attempts_quiz_student"),
    )
    op.create_table(
        "quiz_answers",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("attempt_id", sa.Integer(), nullable=False, index=True),
        sa.Column("question_id", sa.Integer(), nullable=False, index=True),
        sa.Column("answer", sa.Text(), nullable=True),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("auto_graded", sa.Boolean(), nullable=False, server_default=sa.sql.false()),
        sa.ForeignKeyConstraint(["attempt_id"], ["quiz_attempts.id"],
                                name="fk_quiz_answers_attempt", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["question_id"], ["quiz_questions.id"],
                                name="fk_quiz_answers_question"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("attempt_id", "question_id", name="uq_quiz_answers_attempt_question"),
    )


def downgrade() -> None:
    op.drop_table("quiz_answers")
    op.drop_table("quiz_attempts")
