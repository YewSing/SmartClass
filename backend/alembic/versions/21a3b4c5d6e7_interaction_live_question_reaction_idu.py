"""interaction_live_question_reaction_idu

S23 (FR-506, FR-507, FR-508, FR-509 part): live questions, reactions and
"I Don't Understand" signals in an interaction session. All writes carry session,
student and timestamp.

Revision ID: 21a3b4c5d6e7
Revises: 10b2c3d4e5f6
Create Date: 2026-11-13
"""
import sqlalchemy as sa
from alembic import op

revision = "21a3b4c5d6e7"
down_revision = "10b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "interaction_live_questions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("interaction_id", sa.Integer(), nullable=False, index=True),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("asked_by", sa.Integer(), nullable=False),
        sa.Column("asked_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.sql.true()),
        sa.ForeignKeyConstraint(
            ["interaction_id"], ["interaction_sessions.id"],
            name="fk_interaction_live_questions_interaction",
        ),
        sa.ForeignKeyConstraint(["asked_by"], ["users.id"], name="fk_interaction_live_questions_asked_by"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "interaction_live_question_responses",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("live_question_id", sa.Integer(), nullable=False, index=True),
        sa.Column("student_id", sa.Integer(), nullable=False, index=True),
        sa.Column("response", sa.Text(), nullable=False),
        sa.Column("responded_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(
            ["live_question_id"], ["interaction_live_questions.id"],
            name="fk_live_question_responses_question", ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["student_id"], ["students.id"],
            name="fk_live_question_responses_student",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "live_question_id", "student_id",
            name="uq_live_question_responses_question_student",
        ),
    )
    op.create_table(
        "interaction_reactions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("interaction_id", sa.Integer(), nullable=False, index=True),
        sa.Column("student_id", sa.Integer(), nullable=False, index=True),
        sa.Column("reaction", sa.String(40), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(
            ["interaction_id"], ["interaction_sessions.id"],
            name="fk_interaction_reactions_interaction", ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["student_id"], ["students.id"], name="fk_interaction_reactions_student",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "interaction_id", "student_id",
            name="uq_interaction_reactions_interaction_student",
        ),
    )
    op.create_table(
        "interaction_idu_signals",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("interaction_id", sa.Integer(), nullable=False, index=True),
        sa.Column("student_id", sa.Integer(), nullable=False, index=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(
            ["interaction_id"], ["interaction_sessions.id"],
            name="fk_interaction_idu_signals_interaction", ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["student_id"], ["students.id"], name="fk_interaction_idu_signals_student",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "interaction_id", "student_id",
            name="uq_interaction_idu_signals_interaction_student",
        ),
    )


def downgrade() -> None:
    op.drop_table("interaction_idu_signals")
    op.drop_table("interaction_reactions")
    op.drop_table("interaction_live_question_responses")
    op.drop_table("interaction_live_questions")
