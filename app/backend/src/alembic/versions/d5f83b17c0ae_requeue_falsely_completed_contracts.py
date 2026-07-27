"""requeue falsely-completed contracts

Contracts marked COMPLETED while holding zero items never actually enriched; a
zero-item item_exchange/auction contract is impossible. Also re-queues item counts
at an exact multiple of 1,000 — the signature of the page-1 truncation fixed in the
same release. Both are permanent once enrichment becomes fetch-once.

Revision ID: d5f83b17c0ae
Revises: c7e2a9b41d36
Create Date: 2026-07-26 22:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd5f83b17c0ae'
down_revision: Union[str, None] = 'c7e2a9b41d36'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


REQUEUE = sa.text("""
    UPDATE contracts c
       SET item_processing_status = 'PENDING_ITEMS'
     WHERE c.item_processing_status = 'COMPLETED'
       AND (
             -- NOT EXISTS is logically implied by the % 1000 arm but short-circuits the
             -- count() for zero-item rows and keeps the two repair intents legible.
             NOT EXISTS (SELECT 1 FROM contract_items i WHERE i.contract_id = c.contract_id)
          OR (SELECT count(*) FROM contract_items i WHERE i.contract_id = c.contract_id) % 1000 = 0
           )
""")

COUNT_EMPTY = sa.text("""
    SELECT count(*) FROM contracts c
     WHERE c.item_processing_status = 'COMPLETED'
       AND NOT EXISTS (SELECT 1 FROM contract_items i WHERE i.contract_id = c.contract_id)
""")

COUNT_TRUNCATED = sa.text("""
    SELECT count(*) FROM contracts c
     WHERE c.item_processing_status = 'COMPLETED'
       AND (SELECT count(*) FROM contract_items i WHERE i.contract_id = c.contract_id) % 1000 = 0
       AND EXISTS (SELECT 1 FROM contract_items i WHERE i.contract_id = c.contract_id)
""")


def upgrade() -> None:
    """Upgrade schema."""
    # Pre-deploy command on a live database; fail fast rather than queue behind
    # the outgoing instance's ingestion transaction, the same lock-contention risk
    # the preceding two migrations guard against.
    op.execute("SET lock_timeout = '30s'")
    bind = op.get_bind()
    # Logged deliberately: the 3.1% rate is measured (15 of a 384-contract production
    # sample, 2026-07-27) but the mechanism behind it is still inferred, and this is
    # the one cheap opportunity to see the real split.
    empty = bind.execute(COUNT_EMPTY).scalar()
    truncated = bind.execute(COUNT_TRUNCATED).scalar()
    print(f"[requeue] zero-item COMPLETED contracts: {empty}")
    print(f"[requeue] 1000-multiple (truncation suspect) contracts: {truncated}")

    total = bind.execute(sa.text(
        "SELECT count(*) FROM contracts WHERE item_processing_status = 'COMPLETED'"
    )).scalar()
    # Guard against running with an unpopulated contract_items table (e.g. an
    # out-of-order restore): that would match every COMPLETED row and silently
    # re-queue the whole corpus. The measured defect rate is ~3.1%; 25% is far
    # above any plausible repair and far below "the join table is missing".
    if total and (empty + truncated) > total * 0.25:
        raise RuntimeError(
            f"refusing to re-queue {empty + truncated} of {total} COMPLETED contracts: "
            "contract_items looks unpopulated, not a percent-scale repair"
        )

    bind.execute(REQUEUE)


def downgrade() -> None:
    """Downgrade schema."""
    # Irreversible by nature: the prior status was wrong, and re-marking these
    # COMPLETED would restore the defect. Re-enrichment is the recovery path.
    pass
