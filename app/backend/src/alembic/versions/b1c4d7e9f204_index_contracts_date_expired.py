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
    # Fail fast rather than queue behind a long transaction. This runs as Render's
    # pre-deploy command while the OUTGOING instance is still serving, and that instance's
    # in-process ingestion holds an open transaction on `contracts` across its upsert phase.
    # CREATE INDEX needs a SHARE lock, so without a timeout a deploy that overlaps an
    # aggregation run waits indefinitely and stalls the release. A bounded wait turns that
    # into a visible, retryable deploy failure instead. Scoped to this transaction.
    # (The build itself is trivial at ~50k rows; lock acquisition is the only real risk.)
    op.execute("SET lock_timeout = '30s'")
    op.create_index('ix_contracts_date_expired', 'contracts', ['date_expired'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_contracts_date_expired', table_name='contracts')
