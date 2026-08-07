"""f008 type-aware columns

Ten nullable columns for type-aware browsing (auction buyout, courier fields,
blueprint stats, dogma taxonomy, dynamic-item join key) plus the taxonomy name
cache. All nullable because ESI omits each for contracts it does not apply to,
and absence must stay distinguishable from zero (ESI-3). No backfill: contract-
level columns fill on the next ordinary ingestion run, item-level columns via
the ENRICHMENT_VERSION resweep (spec §7).

Revision ID: 685dab7d6df5
Revises: ea2491c47a9f
Create Date: 2026-08-07 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '685dab7d6df5'
down_revision: Union[str, None] = 'ea2491c47a9f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Pre-deploy command on a live database; fail fast rather than queue behind
    # the outgoing instance's ingestion transaction.
    op.execute("SET lock_timeout = '30s'")
    op.add_column('contracts', sa.Column('buyout', sa.Numeric(), nullable=True))
    op.add_column('contracts', sa.Column('days_to_complete', sa.Integer(), nullable=True))
    op.add_column('contracts', sa.Column('end_location_name', sa.String(), nullable=True))
    op.add_column('contracts', sa.Column('end_location_system_id', sa.Integer(), nullable=True))
    op.create_index('ix_contracts_buyout', 'contracts', ['buyout'], unique=False)
    op.create_index('ix_contracts_days_to_complete', 'contracts', ['days_to_complete'], unique=False)

    op.add_column('contract_items', sa.Column('category_id', sa.Integer(), nullable=True))
    op.add_column('contract_items', sa.Column('group_id', sa.Integer(), nullable=True))
    op.add_column('contract_items', sa.Column('runs', sa.Integer(), nullable=True))
    op.add_column('contract_items', sa.Column('material_efficiency', sa.Integer(), nullable=True))
    op.add_column('contract_items', sa.Column('time_efficiency', sa.Integer(), nullable=True))
    op.add_column('contract_items', sa.Column('item_id', sa.BigInteger(), nullable=True))
    op.create_index('ix_contract_items_category_id', 'contract_items', ['category_id'], unique=False)
    op.create_index('ix_contract_items_group_id', 'contract_items', ['group_id'], unique=False)
    op.create_index('ix_contract_items_runs', 'contract_items', ['runs'], unique=False)
    op.create_index('ix_contract_items_material_efficiency', 'contract_items', ['material_efficiency'], unique=False)
    op.create_index('ix_contract_items_time_efficiency', 'contract_items', ['time_efficiency'], unique=False)

    op.create_table(
        'esi_taxonomy_cache',
        sa.Column('kind', sa.String(), nullable=False),
        sa.Column('esi_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('parent_category_id', sa.Integer(), nullable=True),
        sa.Column('fetched_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('kind', 'esi_id'),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('esi_taxonomy_cache')
    op.drop_index('ix_contract_items_time_efficiency', table_name='contract_items')
    op.drop_index('ix_contract_items_material_efficiency', table_name='contract_items')
    op.drop_index('ix_contract_items_runs', table_name='contract_items')
    op.drop_index('ix_contract_items_group_id', table_name='contract_items')
    op.drop_index('ix_contract_items_category_id', table_name='contract_items')
    op.drop_column('contract_items', 'item_id')
    op.drop_column('contract_items', 'time_efficiency')
    op.drop_column('contract_items', 'material_efficiency')
    op.drop_column('contract_items', 'runs')
    op.drop_column('contract_items', 'group_id')
    op.drop_column('contract_items', 'category_id')
    op.drop_index('ix_contracts_days_to_complete', table_name='contracts')
    op.drop_index('ix_contracts_buyout', table_name='contracts')
    op.drop_column('contracts', 'end_location_system_id')
    op.drop_column('contracts', 'end_location_name')
    op.drop_column('contracts', 'days_to_complete')
    op.drop_column('contracts', 'buyout')
