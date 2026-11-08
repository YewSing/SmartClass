"""moodle_login

Moodle (SPeCTRUM) login (T10, FR-101/FR-102): users.moodle_user_id links a SmartClass
account to its Moodle user, and password_hash becomes nullable because Moodle accounts
have no local password (NFR-05).

Revision ID: c3d4e5f6a7b8
Revises: b7c8d9e0f1a2
Create Date: 2026-11-09
"""
import sqlalchemy as sa
from alembic import op

revision = "c3d4e5f6a7b8"
down_revision = "b7c8d9e0f1a2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("moodle_user_id", sa.Integer(), nullable=True))
    op.create_index("ix_users_moodle_user_id", "users", ["moodle_user_id"], unique=True)
    op.alter_column("users", "password_hash", existing_type=sa.String(length=255), nullable=True)


def downgrade() -> None:
    # Moodle-only accounts have no password; give them an unusable one so NOT NULL holds.
    op.execute("UPDATE users SET password_hash = '!' WHERE password_hash IS NULL")
    op.alter_column("users", "password_hash", existing_type=sa.String(length=255), nullable=False)
    op.drop_index("ix_users_moodle_user_id", table_name="users")
    op.drop_column("users", "moodle_user_id")
