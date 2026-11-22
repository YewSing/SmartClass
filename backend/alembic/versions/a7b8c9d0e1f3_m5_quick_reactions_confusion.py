"""S33: m5_quick_questions, m5_quick_answers, m5_reactions, m5_confusion_presses, m5_confusion_spikes
(FR-510–FR-512, FR-514, FR-515).

Revision ID: a7b8c9d0e1f3
Revises: f6a7b8c9d0e2
Create Date: 2026-11-22
"""
import sqlalchemy as sa
from alembic import op

revision = "a7b8c9d0e1f3"
down_revision = "f6a7b8c9d0e2"
branch_labels = None
depends_on = None


def _session_fk() -> sa.Column:
    return sa.Column("attendance_session_id", sa.Integer(),
                     sa.ForeignKey("attendance_sessions.id", ondelete="CASCADE"), nullable=False)


def upgrade() -> None:
    op.create_table(
        "m5_quick_questions",
        sa.Column("id", sa.Integer(), primary_key=True),
        _session_fk(),
        sa.Column("prompt", sa.String(300), nullable=False),
        sa.Column("max_chars", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"),
                  nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("closed_at", sa.DateTime(), nullable=True),
        sa.CheckConstraint("status IN ('open','closed')", name="ck_m5_quick_questions_status"),
        sa.CheckConstraint("char_length(prompt) BETWEEN 1 AND 300", name="ck_m5_quick_questions_prompt_length"),
        sa.CheckConstraint("max_chars BETWEEN 1 AND 500", name="ck_m5_quick_questions_max_chars"),
    )
    op.create_index("ix_m5_quick_questions_session", "m5_quick_questions", ["attendance_session_id"])
    op.create_table(
        "m5_quick_answers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("quick_question_id", sa.Integer(),
                  sa.ForeignKey("m5_quick_questions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("student_id", sa.Integer(), sa.ForeignKey("students.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("text", sa.String(500), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("quick_question_id", "student_id", name="uq_m5_quick_answers_question_student"),
        sa.CheckConstraint("char_length(text) BETWEEN 1 AND 500", name="ck_m5_quick_answers_text_length"),
    )
    op.create_index("ix_m5_quick_answers_student", "m5_quick_answers", ["student_id"])
    op.create_table(
        "m5_reactions",
        sa.Column("id", sa.Integer(), primary_key=True),
        _session_fk(),
        sa.Column("student_id", sa.Integer(), sa.ForeignKey("students.id", ondelete="SET NULL"),
                  nullable=True),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("kind IN ('thumbs_up','clear','too_fast','too_slow')", name="ck_m5_reactions_kind"),
    )
    op.create_index("ix_m5_reactions_session", "m5_reactions", ["attendance_session_id", "created_at"])
    op.create_index("ix_m5_reactions_student", "m5_reactions", ["student_id"])
    op.create_table(
        "m5_confusion_presses",
        sa.Column("id", sa.Integer(), primary_key=True),
        _session_fk(),
        sa.Column("student_id", sa.Integer(), sa.ForeignKey("students.id", ondelete="SET NULL"),
                  nullable=True),
        sa.Column("topic", sa.String(60), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("topic IS NULL OR char_length(topic) BETWEEN 1 AND 60",
                           name="ck_m5_confusion_presses_topic_length"),
    )
    op.create_index("ix_m5_confusion_presses_session", "m5_confusion_presses",
                    ["attendance_session_id", "created_at"])
    op.create_index("ix_m5_confusion_presses_student", "m5_confusion_presses", ["student_id"])
    op.create_table(
        "m5_confusion_spikes",
        sa.Column("id", sa.Integer(), primary_key=True),
        _session_fk(),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("last_at", sa.DateTime(), nullable=False),
        sa.Column("peak_students", sa.Integer(), nullable=False),
        sa.Column("class_size", sa.Integer(), nullable=False),
    )
    op.create_index("ix_m5_confusion_spikes_session", "m5_confusion_spikes",
                    ["attendance_session_id", "started_at"])


def downgrade() -> None:
    op.drop_index("ix_m5_confusion_spikes_session", table_name="m5_confusion_spikes")
    op.drop_table("m5_confusion_spikes")
    op.drop_index("ix_m5_confusion_presses_student", table_name="m5_confusion_presses")
    op.drop_index("ix_m5_confusion_presses_session", table_name="m5_confusion_presses")
    op.drop_table("m5_confusion_presses")
    op.drop_index("ix_m5_reactions_student", table_name="m5_reactions")
    op.drop_index("ix_m5_reactions_session", table_name="m5_reactions")
    op.drop_table("m5_reactions")
    op.drop_index("ix_m5_quick_answers_student", table_name="m5_quick_answers")
    op.drop_table("m5_quick_answers")
    op.drop_index("ix_m5_quick_questions_session", table_name="m5_quick_questions")
    op.drop_table("m5_quick_questions")
