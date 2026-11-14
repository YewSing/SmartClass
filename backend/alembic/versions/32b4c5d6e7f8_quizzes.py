"""quizzes

S30 (FR-601, FR-602, FR-603): quiz model + LLM question generation. Draft questions are
created standalone (quiz_id NULL) and linked to a published quiz in S31.

Revision ID: 32b4c5d6e7f8
Revises: 21a3b4c5d6e7
Create Date: 2026-11-13
"""
import sqlalchemy as sa
from alembic import op

revision = "32b4c5d6e7f8"
down_revision = "21a3b4c5d6e7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "quizzes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("course_id", sa.Integer(), nullable=False, index=True),
        sa.Column("title", sa.String(255), nullable=True),
        sa.Column("time_limit_minutes", sa.Integer(), nullable=True),
        sa.Column("opens_at", sa.DateTime(), nullable=True),
        sa.Column("closes_at", sa.DateTime(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("created_by", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["course_id"], ["courses.id"], name="fk_quizzes_course"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], name="fk_quizzes_created_by"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("status IN ('draft','published','closed')", name="ck_quizzes_status"),
    )
    op.create_table(
        "quiz_questions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("quiz_id", sa.Integer(), nullable=True, index=True),
        sa.Column("course_id", sa.Integer(), nullable=False, index=True),
        sa.Column("type", sa.String(20), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("options", sa.JSON(), nullable=True),
        sa.Column("correct_answer", sa.String(255), nullable=True),
        sa.Column("suggested_answer", sa.Text(), nullable=True),
        sa.Column("level", sa.String(20), nullable=False),
        sa.Column("source_material_id", sa.Integer(), nullable=True),
        sa.Column("topic", sa.String(255), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["quiz_id"], ["quizzes.id"], name="fk_quiz_questions_quiz",
                                ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["course_id"], ["courses.id"], name="fk_quiz_questions_course"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("type IN ('mcq','short_answer')", name="ck_quiz_questions_type"),
        sa.CheckConstraint("status IN ('draft','approved','deleted')", name="ck_quiz_questions_status"),
        sa.CheckConstraint("level IN ('beginner','intermediate','advanced')",
                           name="ck_quiz_questions_level"),
    )


def downgrade() -> None:
    op.drop_table("quiz_questions")
    op.drop_table("quizzes")
