"""interaction_sessions

S20 (FR-501): classroom interaction sessions. A lecturer opens an interaction session
for a class they teach (status open|closed), closes it, and lists the sessions for a class.
A websocket room per interaction session broadcasts open/close (and, later, questions,
votes and reactions) after commit. No permission checks inside the model: the router
enforces NFR-04 via ensure_teaches_occurrence.

Revision ID: e7f8a9b0c1d2
Revises: d1e2f3a4b5c6
Create Date: 2026-11-13
"""
import sqlalchemy as sa
from alembic import op

revision = "e7f8a9b0c1d2"
down_revision = "d1e2f3a4b5c6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "interaction_sessions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("occurrence_id", sa.Integer(), nullable=False, index=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="open"),
        sa.Column("opened_by", sa.Integer(), nullable=False),
        sa.Column("opened_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("closed_by", sa.Integer(), nullable=True),
        sa.Column("closed_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["closed_by"], ["users.id"], name="fk_interaction_sessions_closed_by_users"),
        sa.ForeignKeyConstraint(["occurrence_id"], ["class_occurrences.id"], name="fk_interaction_sessions_occurrence"),
        sa.ForeignKeyConstraint(["opened_by"], ["users.id"], name="fk_interaction_sessions_opened_by_users"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("status IN ('open','closed')", name="ck_interaction_sessions_status"),
    )


def downgrade() -> None:
    op.drop_table("interaction_sessions")
