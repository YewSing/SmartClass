"""S17: m2_announcements (FR-217), lecturer announcements and their Moodle post status.

Revision ID: c1d2e3f4a5b6
Revises: b0c1d2e3f4a5
Create Date: 2026-11-22
"""
import sqlalchemy as sa
from alembic import op

revision = "c1d2e3f4a5b6"
down_revision = "b0c1d2e3f4a5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "m2_announcements",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("occurrence_id", sa.Integer(),
                  sa.ForeignKey("class_occurrences.id", ondelete="CASCADE"), nullable=False),
        sa.Column("course_id", sa.Integer(), sa.ForeignKey("courses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("author_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("recipient_count", sa.Integer(), nullable=False),
        sa.Column("moodle_status", sa.String(16), nullable=False),
        sa.Column("moodle_attempts", sa.Integer(), nullable=False),
        sa.Column("moodle_next_at", sa.DateTime(), nullable=True),
        sa.Column("moodle_last_attempt_at", sa.DateTime(), nullable=True),
        sa.Column("moodle_error", sa.String(255), nullable=True),
        sa.Column("moodle_discussion_id", sa.Integer(), nullable=True),
        sa.Column("moodle_posted_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False,
                  server_default=sa.text("(NOW() AT TIME ZONE 'Asia/Kuala_Lumpur')")),
        sa.CheckConstraint("moodle_status IN ('not_requested','pending','posted','failed')",
                           name="ck_m2_announcements_moodle_status"),
    )
    op.create_index("ix_m2_announcements_occurrence_created", "m2_announcements",
                    ["occurrence_id", "created_at"])
    op.create_index("ix_m2_announcements_moodle_due", "m2_announcements", ["moodle_status", "moodle_next_at"])


def downgrade() -> None:
    op.drop_index("ix_m2_announcements_moodle_due", table_name="m2_announcements")
    op.drop_index("ix_m2_announcements_occurrence_created", table_name="m2_announcements")
    op.drop_table("m2_announcements")
