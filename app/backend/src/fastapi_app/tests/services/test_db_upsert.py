"""ABOUTME: Tests for bulk_upsert's on-conflict semantics, chiefly preserve_on_null:
ABOUTME: NULL in a preserved update column keeps the stored value instead of blanking it.

A transient /universe/names outage makes resolve_ids_to_names return a partial map,
so every re-sighted contract's row carries NULL in the denormalized name columns.
Without per-column coalesce semantics the upsert copies that NULL over names it had
already resolved (F008 decision log D10). These tests pin the preserve_on_null
contract at the bulk_upsert level; the aggregation-pipeline tests cover the same
hazard end-to-end.
"""

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from fastapi_app.models.contracts import Contract
from fastapi_app.services.background_aggregation import (
    NAME_COLUMNS_PRESERVED_ON_NULL,
)
from fastapi_app.services.db_upsert import bulk_upsert

pytestmark = pytest.mark.asyncio


def _contract_row(contract_id: int, **overrides) -> dict:
    row = {
        "contract_id": contract_id,
        "issuer_id": 1,
        "issuer_corporation_id": 1,
        "type": "item_exchange",
        "status": "outstanding",
        "price": 100.0,
        "collateral": 0.0,
        "for_corporation": False,
        "date_issued": datetime(2026, 7, 1, tzinfo=timezone.utc),
        "date_expired": datetime(2027, 7, 1, tzinfo=timezone.utc),
        "issuer_name": "Original Pilot",
        "title": "first sighting",
    }
    row.update(overrides)
    return row


async def _fetch(db_session: AsyncSession, contract_id: int) -> Contract:
    return (
        await db_session.execute(
            select(Contract).where(Contract.contract_id == contract_id)
        )
    ).scalar_one()


async def test_preserved_column_keeps_stored_value_when_update_supplies_null(
    db_session: AsyncSession,
):
    await bulk_upsert(db_session, Contract, [_contract_row(910001)])

    await bulk_upsert(
        db_session,
        Contract,
        [_contract_row(910001, issuer_name=None, title="second sighting")],
        preserve_on_null={"issuer_name"},
    )

    row = await _fetch(db_session, 910001)
    assert row.issuer_name == "Original Pilot"
    # Non-preserved columns keep plain copy semantics within the same statement.
    assert row.title == "second sighting"


async def test_preserved_column_still_updates_on_a_non_null_value(
    db_session: AsyncSession,
):
    await bulk_upsert(db_session, Contract, [_contract_row(910002)])

    await bulk_upsert(
        db_session,
        Contract,
        [_contract_row(910002, issuer_name="Renamed Pilot")],
        preserve_on_null={"issuer_name"},
    )

    row = await _fetch(db_session, 910002)
    assert row.issuer_name == "Renamed Pilot"


async def test_unpreserved_column_null_still_overwrites(db_session: AsyncSession):
    """preserve_on_null is opt-in per column; everything else keeps copy semantics."""
    await bulk_upsert(db_session, Contract, [_contract_row(910003)])

    await bulk_upsert(
        db_session,
        Contract,
        [_contract_row(910003, title=None)],
        preserve_on_null={"issuer_name"},
    )

    row = await _fetch(db_session, 910003)
    assert row.title is None


async def test_preserve_on_null_rejects_dialects_without_conflict_support():
    """The generic merge fallback cannot tell an insert from an update, so it
    cannot honor NULL-preservation (a column default would silently replace a
    requested NULL on fresh inserts — codex probe on PR #142). Refuse loudly."""

    class _RecordingSession:
        def __init__(self, dialect_name: str):
            self.bind = SimpleNamespace(dialect=SimpleNamespace(name=dialect_name))
            self.merged = []

        async def merge(self, obj):
            self.merged.append(obj)

        async def flush(self):
            pass

    db = _RecordingSession("mysql")
    with pytest.raises(NotImplementedError):
        await bulk_upsert(
            db, Contract, [_contract_row(910005)], preserve_on_null={"issuer_name"}
        )
    assert db.merged == []


async def test_plain_upsert_still_merges_on_dialects_without_conflict_support():
    """Without preserve_on_null the generic fallback keeps its merge behavior."""

    class _RecordingSession:
        def __init__(self, dialect_name: str):
            self.bind = SimpleNamespace(dialect=SimpleNamespace(name=dialect_name))
            self.merged = []

        async def merge(self, obj):
            self.merged.append(obj)

        async def flush(self):
            pass

    db = _RecordingSession("mysql")
    await bulk_upsert(db, Contract, [_contract_row(910006)])
    assert len(db.merged) == 1


async def test_preserved_null_on_a_fresh_insert_stays_null(db_session: AsyncSession):
    """The coalesce fallback only fires on conflict; an unresolved name on first
    sighting inserts as NULL exactly as before."""
    await bulk_upsert(
        db_session,
        Contract,
        [_contract_row(910004, issuer_name=None)],
        preserve_on_null={"issuer_name"},
    )

    row = await _fetch(db_session, 910004)
    assert row.issuer_name is None


async def test_the_sqlite_branch_upserts_and_honors_preserve_on_null():
    """bulk_upsert's SQLite branch executes for the first time here.

    The docstring promises "compatible with both PostgreSQL and SQLite" and
    "Supported on PostgreSQL and SQLite only", but the suite runs PostgreSQL
    exclusively, so the sqlite arm — including its preserve_on_null coalesce — had
    never run in any test. A compatibility claim no test backs is indistinguishable
    from dead code; aiosqlite is already a declared dependency, so backing it costs an
    in-memory engine.

    EsiTaxonomyCache is the model under test because its composite (kind, esi_id)
    primary key also exercises multi-column index_elements, and parent_category_id is
    the nullable column the coalesce needs.
    """
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from sqlalchemy.pool import StaticPool

    from fastapi_app.models.contracts import EsiTaxonomyCache

    # StaticPool so every checkout reaches the SAME in-memory database.
    engine = create_async_engine("sqlite+aiosqlite://", poolclass=StaticPool)
    try:
        async with engine.begin() as conn:
            await conn.run_sync(EsiTaxonomyCache.__table__.create)

        async with async_sessionmaker(engine, expire_on_commit=False)() as db:
            assert db.bind.dialect.name == "sqlite"  # the branch under test really ran

            base = {"kind": "group", "esi_id": 25, "fetched_at": datetime(2026, 7, 1, tzinfo=timezone.utc)}
            await bulk_upsert(db, EsiTaxonomyCache, [
                {**base, "name": "Frigate", "parent_category_id": 6},
            ])

            await bulk_upsert(
                db, EsiTaxonomyCache,
                [{**base, "name": "Frigate Mk2", "parent_category_id": None}],
                preserve_on_null={"parent_category_id"},
            )
            row = (await db.execute(select(EsiTaxonomyCache))).scalar_one()
            assert row.name == "Frigate Mk2"     # ON CONFLICT DO UPDATE fired on sqlite
            assert row.parent_category_id == 6   # ...and the NULL was coalesced away

            # Control: the same NULL without preserve_on_null clears the column, so the
            # assertion above is about the coalesce and not about sqlite ignoring NULLs.
            await bulk_upsert(db, EsiTaxonomyCache, [
                {**base, "name": "Frigate Mk3", "parent_category_id": None},
            ])
            await db.refresh(row)
            assert row.parent_category_id is None
    finally:
        await engine.dispose()


@pytest.mark.parametrize("column", sorted(NAME_COLUMNS_PRESERVED_ON_NULL))
async def test_every_preserved_column_still_overwrites_on_a_non_null_value(
    db_session: AsyncSession, column: str
):
    """preserve_on_null must not become preserve-always, for any of the four columns.

    The NULL-keeps direction is asserted for all four end to end, but the overwrite arm
    was asserted for one column only and the other three rode on it. They do not share
    an implementation detail worth riding on: `_update_cols` builds one COALESCE per
    column name, so a column mis-typed into the preserved set — or a set that grew a
    fifth member nobody meant — is a column that silently stops taking updates. A name
    that never updates is worse than one that blanks, because nothing looks wrong: the
    site keeps serving a pilot's old corporation forever.

    Parametrized over `NAME_COLUMNS_PRESERVED_ON_NULL` itself rather than a hand-listed
    four, so a fifth member is covered the moment it joins the frozenset.
    """
    contract_id = 910100 + sorted(NAME_COLUMNS_PRESERVED_ON_NULL).index(column)
    await bulk_upsert(
        db_session, Contract, [_contract_row(contract_id, **{column: "Before"})]
    )

    await bulk_upsert(
        db_session,
        Contract,
        [_contract_row(contract_id, **{column: "After"})],
        preserve_on_null=NAME_COLUMNS_PRESERVED_ON_NULL,
    )

    row = await _fetch(db_session, contract_id)
    assert getattr(row, column) == "After", f"{column} stopped taking updates"


async def test_one_statement_coalesces_per_row_not_per_statement(
    db_session: AsyncSession,
):
    """The COALESCE is per ROW, and a real ingestion statement carries both kinds at once.

    A degraded /universe/names map does not fail uniformly — it answers for some ids and
    not others — so the single upsert a run issues carries rows where the preserved
    column is NULL beside rows where it is freshly resolved. Every existing test issues a
    statement that is entirely one kind or the other, and both pass under an
    implementation that decided per STATEMENT: "this batch has a NULL, preserve
    everything" would keep the stored value for both rows, and "this batch has a value,
    copy everything" would blank the first.

    Observed as both rows' values together, since either row alone is satisfied by the
    wrong per-statement rule in one of its two directions (TEST-25).
    """
    await bulk_upsert(
        db_session,
        Contract,
        [
            _contract_row(910201, issuer_name="Kept Pilot"),
            _contract_row(910202, issuer_name="Replaced Pilot"),
        ],
    )

    await bulk_upsert(
        db_session,
        Contract,
        [
            # Unresolved this run: the stored name must survive.
            _contract_row(910201, issuer_name=None),
            # Resolved this run, in the SAME statement: the new name must land.
            _contract_row(910202, issuer_name="Renamed Pilot"),
        ],
        preserve_on_null=NAME_COLUMNS_PRESERVED_ON_NULL,
    )

    kept = await _fetch(db_session, 910201)
    replaced = await _fetch(db_session, 910202)
    assert (kept.issuer_name, replaced.issuer_name) == ("Kept Pilot", "Renamed Pilot")


async def test_an_empty_batch_is_a_no_op_rather_than_an_error(
    db_session: AsyncSession,
):
    """The aggregation calls this with nothing to write on ordinary paths.

    A region that returned no contracts, a run where every item fetch was skipped, an
    all-304 sweep — each reaches the upsert with an empty list, and the early return is
    the only thing standing between those and a crash. The guard reads as defensive
    politeness, but it is load-bearing: `supplied_cols` derives the column list from
    `values[0]`, so reordering the return below it — the natural tidy-up, since the
    dialect branch looks like the "real" start of the function — turns every quiet
    no-op run into an IndexError that aborts the whole aggregation.

    Asserted as a no-op, not merely as "did not raise": a return that fell through to an
    INSERT with no VALUES is a different failure that a raises-check would miss.
    """
    before = (await db_session.execute(select(Contract))).scalars().all()

    await bulk_upsert(db_session, Contract, [], preserve_on_null=frozenset())
    await bulk_upsert(db_session, Contract, [])

    after = (await db_session.execute(select(Contract))).scalars().all()
    assert len(after) == len(before)
