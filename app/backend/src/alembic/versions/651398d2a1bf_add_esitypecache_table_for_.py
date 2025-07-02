"""Add EsiTypeCache table for comprehensive ESI type data

Revision ID: 651398d2a1bf
Revises: 3fa2eefb2d7e
Create Date: 2025-07-02 02:31:41.289862

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '651398d2a1bf'
down_revision: Union[str, None] = '3fa2eefb2d7e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
