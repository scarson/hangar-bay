"""rename contract_type to type

Revision ID: 3fa2eefb2d7e
Revises: 01e3c3fb3e96
Create Date: 2025-07-01 22:09:27.340380

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3fa2eefb2d7e'
down_revision: Union[str, None] = '01e3c3fb3e96'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Drop the old index that references contract_type
    op.drop_index('ix_contracts_type_status', table_name='contracts')
    
    # Rename the column from contract_type to type
    with op.batch_alter_table('contracts', schema=None) as batch_op:
        batch_op.alter_column('contract_type', new_column_name='type')
    
    # Recreate the index with the new column name
    op.create_index('ix_contracts_type_status', 'contracts', ['type', 'status'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    # Drop the new index
    op.drop_index('ix_contracts_type_status', table_name='contracts')
    
    # Rename the column back from type to contract_type
    with op.batch_alter_table('contracts', schema=None) as batch_op:
        batch_op.alter_column('type', new_column_name='contract_type')
    
    # Recreate the original index
    op.create_index('ix_contracts_type_status', 'contracts', ['contract_type', 'status'], unique=False)
