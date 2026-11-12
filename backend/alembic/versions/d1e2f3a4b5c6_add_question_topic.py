"""add_question_topic

Tags each assistant answer with the topic the student asked about (FR-813): the cited
material title for a course answer, or a short LLM label for a general-knowledge answer.
The lecturer trends endpoint aggregates by this column.

Revision ID: d1e2f3a4b5c6
Revises: 5b8d3f0a2c41
Create Date: 2026-11-12
"""
import sqlalchemy as sa
from alembic import op

revision = "d1e2f3a4b5c6"
down_revision = "5b8d3f0a2c41"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("ai_chat_messages", sa.Column("topic", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("ai_chat_messages", "topic")
