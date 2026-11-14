"""interaction_polls

S22 (FR-504, FR-505, FR-509 part): live polls in an interaction session. A lecturer
creates a poll (2+ options), students vote at most once per poll while it is open, and
per-option results are broadcast on the interaction's websocket room after commit.

Revision ID: 10b2c3d4e5f6
Revises: f8a9b0c1d2e3
Create Date: 2026-11-13
"""
import sqlalchemy as sa
from alembic import op

revision = "10b2c3d4e5f6"
down_revision = "f8a9b0c1d2e3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "interaction_polls",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("interaction_id", sa.Integer(), nullable=False, index=True),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("is_open", sa.Boolean(), nullable=False, server_default=sa.sql.true()),
        sa.Column("opened_by", sa.Integer(), nullable=False),
        sa.Column("opened_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("closed_by", sa.Integer(), nullable=True),
        sa.Column("closed_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ["interaction_id"], ["interaction_sessions.id"],
            name="fk_interaction_polls_interaction",
        ),
        sa.ForeignKeyConstraint(["opened_by"], ["users.id"], name="fk_interaction_polls_opened_by_users"),
        sa.ForeignKeyConstraint(["closed_by"], ["users.id"], name="fk_interaction_polls_closed_by_users"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "interaction_poll_options",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("poll_id", sa.Integer(), nullable=False, index=True),
        sa.Column("option_text", sa.Text(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["poll_id"], ["interaction_polls.id"],
            name="fk_interaction_poll_options_poll", ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "interaction_poll_votes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("poll_id", sa.Integer(), nullable=False, index=True),
        sa.Column("option_id", sa.Integer(), nullable=False, index=True),
        sa.Column("student_id", sa.Integer(), nullable=False, index=True),
        sa.Column("voted_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(
            ["poll_id"], ["interaction_polls.id"], name="fk_interaction_poll_votes_poll", ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["option_id"], ["interaction_poll_options.id"],
            name="fk_interaction_poll_votes_option", ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["student_id"], ["students.id"], name="fk_interaction_poll_votes_student"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("poll_id", "student_id", name="uq_interaction_poll_votes_poll_student"),
    )


def downgrade() -> None:
    op.drop_table("interaction_poll_votes")
    op.drop_table("interaction_poll_options")
    op.drop_table("interaction_polls")
