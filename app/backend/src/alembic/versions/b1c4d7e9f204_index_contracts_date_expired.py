"""index contracts.date_expired

Every contracts list query now filters `date_expired > now()` to hide contracts that can
no longer be accepted, so this column moved onto the hot path for all of them — not only
for sorting by "Time left".

Revision ID: b1c4d7e9f204
Revises: 3aca702a74e3
Create Date: 2026-07-26 17:45:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'b1c4d7e9f204'
down_revision: Union[str, None] = '3aca702a74e3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_index('ix_contracts_date_expired', 'contracts', ['date_expired'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_contracts_date_expired', table_name='contracts')
