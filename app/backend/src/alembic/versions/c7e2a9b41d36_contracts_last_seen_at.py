"""contracts.last_seen_at for delisted detection

A contract that is accepted disappears from ESI's public list while keeping a future
date_expired, so the expiry filter cannot catch it. Ingestion now restamps last_seen_at
on every sighting, and the list endpoint keeps only contracts whose stamp matches the
newest stamp in their own region.

Revision ID: c7e2a9b41d36
Revises: b1c4d7e9f204
Create Date: 2026-07-26 18:15:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c7e2a9b41d36'
down_revision: Union[str, None] = 'b1c4d7e9f204'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Same rationale as the previous migration: the outgoing instance's ingestion holds a
    # transaction on `contracts` during its upsert phase, and this runs as a pre-deploy
    # command. Fail fast and retryably rather than stalling the release.
    op.execute("SET lock_timeout = '30s'")

    op.add_column('contracts', sa.Column('last_seen_at', sa.DateTime(timezone=True), nullable=True))

    # Backfill every existing row with one identical timestamp. This is load-bearing, not
    # tidiness: the filter keeps contracts whose stamp matches the newest in their region, so
    # leaving rows NULL and treating NULL as absent would blank the site between this
    # migration and the first stamping run. One shared value makes every existing contract
    # its region's watermark, so all stay visible until a real run reclassifies them.
    op.execute("UPDATE contracts SET last_seen_at = now()")

    op.create_index(
        'ix_contracts_region_last_seen',
        'contracts',
        ['start_location_region_id', 'last_seen_at'],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_contracts_region_last_seen', table_name='contracts')
    op.drop_column('contracts', 'last_seen_at')
