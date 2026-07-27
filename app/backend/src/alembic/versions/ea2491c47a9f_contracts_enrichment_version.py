"""contracts.enrichment_version

Stamps which enrichment-logic generation produced a contract's items, so an
enrichment fix can re-queue the corpus by bumping a constant instead of relying
on the refetch-everything loop to eventually repair rows by accident.

Revision ID: ea2491c47a9f
Revises: d5f83b17c0ae
Create Date: 2026-07-26 23:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ea2491c47a9f'
down_revision: Union[str, None] = 'd5f83b17c0ae'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Pre-deploy command on a live database; fail fast rather than queue behind
    # the outgoing instance's ingestion transaction.
    op.execute("SET lock_timeout = '30s'")
    op.add_column(
        "contracts",
        sa.Column("enrichment_version", sa.Integer(), nullable=False, server_default="0"),
    )
    # Backfill already-enriched rows to the CURRENT version. Without this every existing
    # COMPLETED contract mismatches version 1 and the first deploy triggers a full ~46k
    # re-enrichment backfill — the exact cost this plan exists to remove.
    # The literal 1 MUST equal ENRICHMENT_VERSION at ship time. If that constant is
    # bumped before this migration runs, update both together or the backfill stamps
    # a version that no longer matches and re-queues the whole corpus.
    op.execute("UPDATE contracts SET enrichment_version = 1 WHERE item_processing_status = 'COMPLETED'")


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("contracts", "enrichment_version")
