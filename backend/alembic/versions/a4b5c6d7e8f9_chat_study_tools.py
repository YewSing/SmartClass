"""chat_study_tools

Study tools live in the chat (2026-11-13): a summary, study guide, flashcards or practice
set is saved as a chat message, so it shows in history and can be reopened.
`ai_chat_messages.kind` says which ("chat" for a normal question/answer) and `payload`
holds the cards or questions (and the student's last practice score).

Revision ID: a4b5c6d7e8f9
Revises: f3a4b5c6d7e8
Create Date: 2026-11-13
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "a4b5c6d7e8f9"
down_revision = "f3a4b5c6d7e8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "ai_chat_messages",
        sa.Column("kind", sa.String(20), nullable=False, server_default="chat"),
    )
    op.add_column("ai_chat_messages", sa.Column("payload", JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column("ai_chat_messages", "payload")
    op.drop_column("ai_chat_messages", "kind")
