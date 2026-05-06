"""Merge multiple heads

Revision ID: cce87ff9d714
Revises: 20260416_16a, 2e880a245f2d
Create Date: 2026-05-06 17:16:04.528971

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'cce87ff9d714'
down_revision: Union[str, Sequence[str], None] = ('20260416_16a', '2e880a245f2d')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
