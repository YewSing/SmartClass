"""S34: m5_events, the interaction event log (FR-517), backfilled from the S31–S33 tables.

Revision ID: b8c9d0e1f2a4
Revises: a7b8c9d0e1f3
Create Date: 2026-11-23
"""
import sqlalchemy as sa
from alembic import op

revision = "b8c9d0e1f2a4"
down_revision = "a7b8c9d0e1f3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "m5_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("attendance_session_id", sa.Integer(),
                  sa.ForeignKey("attendance_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("student_id", sa.Integer(), sa.ForeignKey("students.id", ondelete="SET NULL"),
                  nullable=True),
        sa.Column("type", sa.String(32), nullable=False),
        sa.Column("ref_id", sa.Integer(), nullable=True),
        sa.Column("anonymous", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("type IN ('question_asked','question_upvoted','poll_voted','quick_answered',"
                           "'reaction','confusion')", name="ck_m5_events_type"),
    )
    op.create_index("ix_m5_events_session", "m5_events", ["attendance_session_id", "created_at"])
    op.create_index("ix_m5_events_student", "m5_events", ["student_id"])

    # Backfill what S31–S33 already stored (one event per row; poll votes once per poll and student).
    op.execute("""
        INSERT INTO m5_events (attendance_session_id, student_id, type, ref_id, anonymous, created_at)
        SELECT attendance_session_id, student_id, 'question_asked', id, anonymous, created_at
          FROM m5_questions
        UNION ALL
        SELECT q.attendance_session_id, v.student_id, 'question_upvoted', q.id, false, v.created_at
          FROM m5_question_votes v JOIN m5_questions q ON q.id = v.question_id
        UNION ALL
        SELECT p.attendance_session_id, v.student_id, 'poll_voted', p.id, false, MIN(v.created_at)
          FROM m5_poll_votes v JOIN m5_polls p ON p.id = v.poll_id
         GROUP BY p.attendance_session_id, v.student_id, p.id
        UNION ALL
        SELECT q.attendance_session_id, a.student_id, 'quick_answered', q.id, false, a.created_at
          FROM m5_quick_answers a JOIN m5_quick_questions q ON q.id = a.quick_question_id
        UNION ALL
        SELECT attendance_session_id, student_id, 'reaction', NULL, false, created_at FROM m5_reactions
        UNION ALL
        SELECT attendance_session_id, student_id, 'confusion', NULL, false, created_at
          FROM m5_confusion_presses
    """)


def downgrade() -> None:
    op.drop_index("ix_m5_events_student", table_name="m5_events")
    op.drop_index("ix_m5_events_session", table_name="m5_events")
    op.drop_table("m5_events")
