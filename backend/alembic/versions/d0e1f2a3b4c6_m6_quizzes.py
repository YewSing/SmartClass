"""S40: m6_quizzes, m6_questions, m6_attempts, m6_answers (FR-605, FR-606).

Revision ID: d0e1f2a3b4c6
Revises: c9d0e1f2a3b5
Create Date: 2026-11-25
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "d0e1f2a3b4c6"
down_revision = "c9d0e1f2a3b5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "m6_quizzes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("course_id", sa.Integer(), sa.ForeignKey("courses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"),
                  nullable=True),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("type", sa.String(16), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("timer_mode", sa.String(16), nullable=False),
        sa.Column("timer_seconds", sa.Integer(), nullable=False),
        sa.Column("opens_at", sa.DateTime(), nullable=True),
        sa.Column("closes_at", sa.DateTime(), nullable=True),
        sa.Column("shuffle", sa.Boolean(), nullable=False),
        sa.Column("release", sa.String(16), nullable=False),
        sa.Column("release_marks", sa.Boolean(), nullable=False),
        sa.Column("release_answers", sa.Boolean(), nullable=False),
        sa.Column("speed_bonus", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("type IN ('game','graded')", name="ck_m6_quizzes_type"),
        sa.CheckConstraint("status IN ('draft','published','closed')", name="ck_m6_quizzes_status"),
        sa.CheckConstraint("timer_mode IN ('question','quiz')", name="ck_m6_quizzes_timer_mode"),
        sa.CheckConstraint("type <> 'game' OR timer_mode = 'question'", name="ck_m6_quizzes_game_timer"),
        sa.CheckConstraint("(timer_mode = 'question' AND timer_seconds BETWEEN 5 AND 600) OR "
                           "(timer_mode = 'quiz' AND timer_seconds BETWEEN 60 AND 14400)",
                           name="ck_m6_quizzes_timer_seconds"),
        sa.CheckConstraint("opens_at IS NULL OR closes_at IS NULL OR closes_at > opens_at",
                           name="ck_m6_quizzes_open_close"),
        sa.CheckConstraint("release IN ('manual','on_close')", name="ck_m6_quizzes_release"),
        sa.CheckConstraint("char_length(title) BETWEEN 1 AND 200", name="ck_m6_quizzes_title_length"),
    )
    op.create_index("ix_m6_quizzes_course", "m6_quizzes", ["course_id", "status"])
    op.create_table(
        "m6_questions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("quiz_id", sa.Integer(), sa.ForeignKey("m6_quizzes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("type", sa.String(16), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("options", postgresql.JSONB(), nullable=True),
        sa.Column("answer", sa.Integer(), nullable=True),
        sa.Column("suggested_answer", sa.Text(), nullable=True),
        sa.Column("topic", sa.String(120), nullable=True),
        sa.Column("source_file", sa.String(512), nullable=True),
        sa.Column("source_type", sa.String(16), nullable=True),
        sa.Column("source_page", sa.Integer(), nullable=True),
        sa.Column("origin", sa.String(16), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=True),
        sa.Column("approved", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("quiz_id", "position", name="uq_m6_questions_quiz_position",
                            deferrable=True, initially="DEFERRED"),
        sa.CheckConstraint("type IN ('mcq','short')", name="ck_m6_questions_type"),
        sa.CheckConstraint("origin IN ('from_material','extended')", name="ck_m6_questions_origin"),
        sa.CheckConstraint("position >= 0", name="ck_m6_questions_position"),
        sa.CheckConstraint("char_length(text) BETWEEN 1 AND 1000", name="ck_m6_questions_text_length"),
        sa.CheckConstraint(
            "CASE WHEN type = 'mcq' THEN suggested_answer IS NULL AND answer IS NOT NULL AND options IS NOT NULL "
            "AND CASE WHEN jsonb_typeof(options) = 'array' THEN jsonb_array_length(options) BETWEEN 2 AND 6 "
            "AND answer >= 0 AND answer < jsonb_array_length(options) ELSE false END "
            "ELSE options IS NULL AND answer IS NULL AND suggested_answer IS NOT NULL END",
            name="ck_m6_questions_shape"),
        sa.CheckConstraint("source_type IS NULL OR source_type IN ('page','slide','section')",
                           name="ck_m6_questions_source_type"),
        sa.CheckConstraint("origin <> 'from_material' OR (source_file IS NOT NULL AND source_type IS NOT NULL "
                           "AND source_page IS NOT NULL)", name="ck_m6_questions_source"),
    )
    op.create_table(
        "m6_attempts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("quiz_id", sa.Integer(), sa.ForeignKey("m6_quizzes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("student_id", sa.Integer(), sa.ForeignKey("students.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("ends_at", sa.DateTime(), nullable=True),
        sa.Column("submitted_at", sa.DateTime(), nullable=True),
        sa.Column("auto_submitted", sa.Boolean(), nullable=False),
        sa.UniqueConstraint("quiz_id", "student_id", name="uq_m6_attempts_quiz_student"),
        sa.CheckConstraint("status IN ('in_progress','submitted')", name="ck_m6_attempts_status"),
    )
    op.create_index("ix_m6_attempts_student", "m6_attempts", ["student_id", "status"])
    op.create_table(
        "m6_answers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("attempt_id", sa.Integer(), sa.ForeignKey("m6_attempts.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("question_id", sa.Integer(), sa.ForeignKey("m6_questions.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("option_index", sa.Integer(), nullable=True),
        sa.Column("text", sa.Text(), nullable=True),
        sa.Column("correct", sa.Boolean(), nullable=True),
        sa.Column("score", sa.Numeric(4, 3), nullable=True),
        sa.Column("answered_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("attempt_id", "question_id", name="uq_m6_answers_attempt_question"),
        sa.CheckConstraint("score IS NULL OR score BETWEEN 0 AND 1", name="ck_m6_answers_score"),
        sa.CheckConstraint("text IS NULL OR char_length(text) <= 2000", name="ck_m6_answers_text_length"),
    )
    op.create_index("ix_m6_answers_question", "m6_answers", ["question_id"])


def downgrade() -> None:
    op.drop_index("ix_m6_answers_question", table_name="m6_answers")
    op.drop_table("m6_answers")
    op.drop_index("ix_m6_attempts_student", table_name="m6_attempts")
    op.drop_table("m6_attempts")
    op.drop_table("m6_questions")
    op.drop_index("ix_m6_quizzes_course", table_name="m6_quizzes")
    op.drop_table("m6_quizzes")
