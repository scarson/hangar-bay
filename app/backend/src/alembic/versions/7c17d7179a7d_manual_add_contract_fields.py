"""manual_add_contract_fields

Revision ID: 7c17d7179a7d
Revises: c199a09ccc55
Create Date: 2025-06-12 04:28:07.018913

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7c17d7179a7d'
down_revision: Union[str, None] = 'c199a09ccc55'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('contracts', sa.Column('item_processing_status', sa.VARCHAR(), nullable=False, server_default='PENDING_ITEMS'))
    op.add_column('contracts', sa.Column('items_last_fetched_at', sa.DATETIME(), nullable=True))
    op.add_column('contracts', sa.Column('contract_esi_etag', sa.VARCHAR(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('contracts', 'contract_esi_etag')
    op.drop_column('contracts', 'items_last_fetched_at')
    op.drop_column('contracts', 'item_processing_status')
