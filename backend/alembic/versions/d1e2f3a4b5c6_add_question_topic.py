"""add_question_topic

Tags each assistant answer with the topic the student asked about (FR-813): the cited
material title for a course answer, or a short LLM label for a general-knowledge answer.
The lecturer trends endpoint aggregates by this column.

Revision ID: d1e2f3a4b5c6
Revises: c9d0e1f2a3b4
Create Date: 2026-11-12
"""
import sqlalchemy as sa
from alembic import op

revision = "d1e2f3a4b5c6"
down_revision = "c9d0e1f2a3b4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("ai_chat_messages", sa.Column("topic", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("ai_chat_messages", "topic")
