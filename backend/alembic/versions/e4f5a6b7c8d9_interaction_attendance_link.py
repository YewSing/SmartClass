"""Link interaction sessions to attendance sessions.

Each interaction session now points at the attendance session of the same class
time range, so both share one lifecycle: the interaction session takes its
ends_at from the linked attendance session, and the scheduler's R3 pass (or the
Dashboard's End Class) governs both.

Revision ID: e4f5a6b7c8d9
Revises: d2e3f4a5b6c7
Create Date: 2026-11-19
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "e4f5a6b7c8d9"
down_revision = "d2e3f4a5b6c7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "interaction_sessions",
        sa.Column("attendance_session_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_interaction_sessions_attendance_session",
        "interaction_sessions",
        "attendance_sessions",
        ["attendance_session_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_interaction_sessions_attendance_session",
        "interaction_sessions",
        type_="foreignkey",
    )
    op.drop_column("interaction_sessions", "attendance_session_id")
