"""T46b: delete the legacy face-review rows (NFR-02).

The old face_worker reported unrecognised faces (with their embeddings) to /internal/face-review.
That path is gone, so nothing adds rows; the ones left are biometric data with no use, deleted
here. The table itself stays until frontend/admin is retired (T96).

Revision ID: b5c6d7e8f9a0
Revises: a4b5c6d7e8f9
Create Date: 2026-11-13
"""
import sqlalchemy as sa
from alembic import op

revision = "b5c6d7e8f9a0"
down_revision = "a4b5c6d7e8f9"
branch_labels = None
depends_on = None

DELETE_LEGACY_ROWS = sa.text("DELETE FROM face_review_entries")


def upgrade() -> None:
    op.execute(DELETE_LEGACY_ROWS)


def downgrade() -> None:
    pass  # deleted rows can't come back
