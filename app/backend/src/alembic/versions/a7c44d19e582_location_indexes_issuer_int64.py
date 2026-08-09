"""location filter indexes + issuer columns to int64

Two remainders from the 2026-08-08 perf disposition and bug hunt:

- ix_contracts_start_location_system_id / ix_contracts_start_location_id —
  the system/station filter columns were the last unindexed IN-list predicates
  on the browse path (the 2026-08-02 audit used start_location_id's missing
  index as its scan-cost control), and start_location_system_id is scanned
  IS NULL by the unknown-system residual count on every system-filtered
  request.
- issuer_id / issuer_corporation_id widen to BigInteger: ESI publishes both
  as int64, and a CCP id above 2^31 would poison ingestion the same way a
  price-less contract did before f2a91c3b7e04.

Revision ID: a7c44d19e582
Revises: f2a91c3b7e04
Create Date: 2026-08-08 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a7c44d19e582'
down_revision: Union[str, None] = 'f2a91c3b7e04'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Pre-deploy command on a live database; fail fast rather than queue behind
    # the outgoing instance's ingestion transaction.
    op.execute("SET lock_timeout = '30s'")
    op.create_index(
        'ix_contracts_start_location_system_id', 'contracts',
        ['start_location_system_id'], unique=False,
    )
    op.create_index(
        'ix_contracts_start_location_id', 'contracts',
        ['start_location_id'], unique=False,
    )
    # One statement for both columns: a width change rewrites the table, and
    # separate ALTERs would do that twice under the same exclusive lock.
    op.execute(
        "ALTER TABLE contracts "
        "ALTER COLUMN issuer_id TYPE BIGINT, "
        "ALTER COLUMN issuer_corporation_id TYPE BIGINT"
    )


def downgrade() -> None:
    """Downgrade schema.

    Narrowing back to Integer is impossible once an id above 2^31-1 is stored;
    the guard turns the incidental out-of-range error into a stated refusal,
    emitted as SQL under an exclusive lock so it renders offline and cannot
    race a writer (the f2a91c3b7e04 pattern).
    """
    op.execute("SET lock_timeout = '30s'")
    op.execute("LOCK TABLE contracts IN ACCESS EXCLUSIVE MODE")
    op.execute(
        """
        DO $$
        DECLARE oversized bigint;
        BEGIN
            SELECT COUNT(*) INTO oversized FROM contracts
            WHERE issuer_id > 2147483647 OR issuer_corporation_id > 2147483647;
            IF oversized > 0 THEN
                RAISE EXCEPTION 'cannot narrow issuer columns to int32: % stored contract(s) carry an id above 2147483647. CCP has allocated beyond int32; deleting those rows is a data decision this migration refuses to make.', oversized;
            END IF;
        END
        $$
        """
    )
    # Single statement, single table rewrite — mirror of the upgrade.
    op.execute(
        "ALTER TABLE contracts "
        "ALTER COLUMN issuer_corporation_id TYPE INTEGER, "
        "ALTER COLUMN issuer_id TYPE INTEGER"
    )
    op.drop_index('ix_contracts_start_location_id', table_name='contracts')
    op.drop_index('ix_contracts_start_location_system_id', table_name='contracts')
