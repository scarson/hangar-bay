"""check_after_manual_add

Revision ID: 01e3c3fb3e96
Revises: 7c17d7179a7d
Create Date: 2025-06-12 04:24:16.680857

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '01e3c3fb3e96'
down_revision: Union[str, None] = '7c17d7179a7d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_index(op.f('ix_contracts_item_processing_status'), 'contracts', ['item_processing_status'], unique=False)
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.alter_column('is_active',
                              existing_type=sa.BOOLEAN(),
                              nullable=False)
    # ### end Alembic commands ###


def downgrade() -> None:
    """Downgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.alter_column('is_active',
                              existing_type=sa.BOOLEAN(),
                              nullable=True)
    op.drop_index(op.f('ix_contracts_item_processing_status'), table_name='contracts')
    # ### end Alembic commands ###
