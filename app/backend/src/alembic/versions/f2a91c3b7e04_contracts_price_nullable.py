"""contracts.price nullable

ESI marks price optional on the public contracts route, so a spec-conformant
payload may omit it; with the column NOT NULL, one such contract aborts the
whole aggregation batch with an IntegrityError and re-fails every run until
the contract delists. Absence must stay distinguishable from zero (ESI-3) —
a missing price is not "free" — so the column goes nullable rather than the
writer defaulting to 0.0. NULL sorts last via NULLABLE_SORTS; the wire schema
was already Optional.

Revision ID: f2a91c3b7e04
Revises: 685dab7d6df5
Create Date: 2026-08-08 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f2a91c3b7e04'
down_revision: Union[str, None] = '685dab7d6df5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Pre-deploy command on a live database; fail fast rather than queue behind
    # the outgoing instance's ingestion transaction.
    op.execute("SET lock_timeout = '30s'")
    op.alter_column('contracts', 'price', existing_type=sa.Numeric(), nullable=True)


def downgrade() -> None:
    """Downgrade schema.

    Restoring NOT NULL is impossible once the corpus holds price-less
    contracts, and inventing 0.0 for them would publish prices the corpus
    does not have (ESI-3). The guard turns the incidental NotNullViolation
    into a stated refusal; it runs as emitted SQL under an exclusive table
    lock so it works offline (--sql) and cannot race a concurrent writer.
    The suite exercises both the refusal path and the clean downgrade.
    """
    op.execute("SET lock_timeout = '30s'")
    # The guard is emitted SQL, not a Python-side query: `alembic downgrade --sql`
    # (offline mode) has no connection to query, and an exclusive lock ahead of
    # the check makes guard + alteration atomic against a concurrent ingestion
    # inserting a price-less row between them.
    op.execute("LOCK TABLE contracts IN ACCESS EXCLUSIVE MODE")
    op.execute(
        """
        DO $$
        DECLARE null_prices bigint;
        BEGIN
            SELECT COUNT(*) INTO null_prices FROM contracts WHERE price IS NULL;
            IF null_prices > 0 THEN
                RAISE EXCEPTION 'cannot restore NOT NULL on contracts.price: % stored contract(s) have no price. ESI omits price on some spec-conformant contracts; deleting or zero-filling those rows is a data decision this migration refuses to make.', null_prices;
            END IF;
        END
        $$
        """
    )
    op.alter_column('contracts', 'price', existing_type=sa.Numeric(), nullable=False)
