"""merge attendance and interaction branches

Revision ID: 5eeca85bd0fa
Revises: 55e7f8a9b0c1, b5c6d7e8f9a0
Create Date: 2026-11-14 05:24:32.055013

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5eeca85bd0fa'
down_revision: Union[str, None] = ('55e7f8a9b0c1', 'b5c6d7e8f9a0')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
