"""delete_face_data_without_consent

Face embeddings stored before consent existed (T14) had no consent record, yet recognition
still matched them (NFR-03, FR-116). Yew Sing's decision (2026-11-10): they were test data,
so delete every embedding whose student has no active consent; those students re-enrol in
the app. Data-only; nothing to restore on downgrade.

Revision ID: f7a8b9c0d1e2
Revises: e6f7a8b9c0d1
Create Date: 2026-11-10
"""
import sqlalchemy as sa
from alembic import op

revision = "f7a8b9c0d1e2"
down_revision = "e6f7a8b9c0d1"
branch_labels = None
depends_on = None

DELETE_WITHOUT_CONSENT = sa.text("""
    DELETE FROM face_embeddings fe
    WHERE NOT EXISTS (
        SELECT 1 FROM face_consents fc
        WHERE fc.student_id = fe.student_id AND fc.withdrawn_at IS NULL
    )
""")


def upgrade() -> None:
    op.execute(DELETE_WITHOUT_CONSENT)


def downgrade() -> None:
    pass  # deleted face data is not brought back
