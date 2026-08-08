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
    into a stated refusal. The suite exercises upgrades plus this guard's
    refusal path; a clean-database downgrade remains untested by the suite.
    """
    op.execute("SET lock_timeout = '30s'")
    null_prices = op.get_bind().execute(
        sa.text("SELECT COUNT(*) FROM contracts WHERE price IS NULL")
    ).scalar_one()
    if null_prices:
        raise RuntimeError(
            f"cannot restore NOT NULL on contracts.price: {null_prices} stored "
            "contract(s) have no price. ESI omits price on some spec-conformant "
            "contracts; deleting or zero-filling those rows is a data decision "
            "this migration refuses to make."
        )
    op.alter_column('contracts', 'price', existing_type=sa.Numeric(), nullable=False)
