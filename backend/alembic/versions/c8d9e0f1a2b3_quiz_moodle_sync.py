"""Quiz -> Moodle sync: per-quiz Moodle identity + sync bookkeeping, question and
attempt mappings (same pattern as the attendance sync, FR-311)."""

import sqlalchemy as sa
from alembic import op

revision = "c8d9e0f1a2b3"
down_revision = "e4f5a6b7c8d9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("quizzes", sa.Column("moodle_quiz_id", sa.Integer(), nullable=True))
    op.add_column("quizzes", sa.Column("moodle_cmid", sa.Integer(), nullable=True))
    op.add_column("quizzes", sa.Column(
        "moodle_sync_status", sa.String(20), nullable=True))
    op.create_index("ix_quizzes_moodle_sync_status", "quizzes", ["moodle_sync_status"])
    op.add_column("quizzes", sa.Column(
        "moodle_sync_attempts", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("quizzes", sa.Column("moodle_sync_next_at", sa.DateTime(), nullable=True))
    op.add_column("quizzes", sa.Column("moodle_synced_at", sa.DateTime(), nullable=True))
    op.add_column("quizzes", sa.Column("moodle_sync_error", sa.String(255), nullable=True))

    op.add_column("quiz_questions", sa.Column("moodle_question_id", sa.Integer(), nullable=True))
    op.add_column("quiz_attempts", sa.Column("moodle_attempt_id", sa.Integer(), nullable=True))
    op.create_index("ix_quiz_attempts_moodle_attempt_id", "quiz_attempts",
                    ["moodle_attempt_id"], unique=True,
                    postgresql_where=sa.text("moodle_attempt_id IS NOT NULL"))


def downgrade() -> None:
    op.drop_index("ix_quiz_attempts_moodle_attempt_id", table_name="quiz_attempts")
    op.drop_column("quiz_attempts", "moodle_attempt_id")
    op.drop_column("quiz_questions", "moodle_question_id")
    op.drop_column("quizzes", "moodle_sync_error")
    op.drop_column("quizzes", "moodle_synced_at")
    op.drop_column("quizzes", "moodle_sync_next_at")
    op.drop_column("quizzes", "moodle_sync_attempts")
    op.drop_index("ix_quizzes_moodle_sync_status", table_name="quizzes")
    op.drop_column("quizzes", "moodle_sync_status")
    op.drop_column("quizzes", "moodle_cmid")
    op.drop_column("quizzes", "moodle_quiz_id")
