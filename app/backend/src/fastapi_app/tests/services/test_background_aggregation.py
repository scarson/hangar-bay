"""Regression tests for the contract aggregation pipeline's field mapping.

Discovered during M1 Task 9 acceptance (2026-07-11): the aggregation loop
fetches contracts per region — the region ID is in hand at fetch time — but
never wrote it to Contract.start_location_region_id, leaving the column NULL
for ALL real ingested data. The region filter (part of the M1 minimum UI
surface) therefore matched nothing in production while every fixture-based
test passed (fixtures set the column by hand). See pitfall TEST-1 for the
general shape of this trap: the gap only shows up when the real pipeline,
not a hand-built fixture, writes the row.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import fastapi_app.services.background_aggregation as bg_agg
from fastapi_app.models.contracts import Contract, ContractItem
from fastapi_app.services.background_aggregation import ContractAggregationService
from fastapi_app.tests.lock_double import FakeLockRedis as _FakeLockRedis

pytestmark = pytest.mark.asyncio


def _make_service() -> ContractAggregationService:
    esi_client = MagicMock()
    esi_client.resolve_ids_to_names = AsyncMock(
        return_value={60003760: "Jita IV - Moon 4 - Caldari Navy Assembly Plant"}
    )
    # get_contract_items is exercised by other flows; keep it inert here.
    esi_client.get_contract_items = AsyncMock(return_value=[])
    settings = MagicMock()
    return ContractAggregationService(esi_client=esi_client, settings=settings)


async def test_process_contracts_persists_fetch_region_id(db_session: AsyncSession):
    """A contract fetched from region R must be stored with
    start_location_region_id == R (stamped by the fetch loop as _hb_region_id)."""
    service = _make_service()
    esi_contract = {
        "contract_id": 900001,
        "issuer_id": 1,
        "issuer_corporation_id": 1,
        "start_location_id": 60003760,
        "type": "item_exchange",
        "price": 1000000.0,
        "date_issued": "2026-07-01T00:00:00Z",
        "date_expired": "2026-07-08T00:00:00Z",
        "_hb_region_id": 10000002,
    }

    await service._process_contracts(db_session, [esi_contract])

    row = (
        await db_session.execute(
            select(Contract).where(Contract.contract_id == 900001)
        )
    ).scalar_one()
    assert row.start_location_region_id == 10000002


async def test_process_contracts_without_region_stamp_stores_null(
    db_session: AsyncSession,
):
    """Contracts lacking the stamp (defensive path) store NULL, not garbage."""
    service = _make_service()
    esi_contract = {
        "contract_id": 900002,
        "issuer_id": 1,
        "issuer_corporation_id": 1,
        "start_location_id": 60003760,
        "type": "item_exchange",
        "price": 1000000.0,
        "date_issued": "2026-07-01T00:00:00Z",
        "date_expired": "2026-07-08T00:00:00Z",
    }

    await service._process_contracts(db_session, [esi_contract])

    row = (
        await db_session.execute(
            select(Contract).where(Contract.contract_id == 900002)
        )
    ).scalar_one()
    assert row.start_location_region_id is None


def _ship_contract_dict(cid: int) -> dict:
    from datetime import datetime, timezone

    return {
        "contract_id": cid,
        "issuer_id": 1,
        "issuer_corporation_id": 1,
        "start_location_id": 60003760,
        "type": "item_exchange",
        "price": 1_000_000.0,
        "date_issued": "2026-07-01T00:00:00Z",
        "date_expired": "2026-07-08T00:00:00Z",
        "_hb_region_id": 10000002,
    }


async def test_process_contracts_flags_ships_and_resolves_type_names(
    db_session: AsyncSession,
):
    """F001/F002 enabler: is_ship_contract previously defaulted to False forever
    ('will be updated later' — later never came), so the ships-only default view
    matched nothing. Item processing must resolve type→group→category via ESI,
    enrich items (type_name, market_group_id, category), and flag contracts
    whose INCLUDED items contain a ship (EVE category 6)."""
    from fastapi_app.models.contracts import ContractItem

    service = _make_service()
    service.esi_client.get_contract_items = AsyncMock(
        return_value=[
            {"record_id": 11, "type_id": 587, "quantity": 1, "is_included": True},
            {"record_id": 12, "type_id": 34, "quantity": 5000, "is_included": True},
        ]
    )
    service.esi_client.get_universe_type = AsyncMock(
        side_effect=lambda type_id: {
            587: {"name": "Tristan", "group_id": 25, "market_group_id": 1367},
            34: {"name": "Tritanium", "group_id": 18, "market_group_id": 1857},
        }[type_id]
    )
    service.esi_client.get_universe_group = AsyncMock(
        side_effect=lambda group_id: {
            25: {"name": "Frigate", "category_id": 6},
            18: {"name": "Mineral", "category_id": 4},
        }[group_id]
    )

    await service._process_contracts(db_session, [_ship_contract_dict(900101)])

    contract = (
        await db_session.execute(select(Contract).where(Contract.contract_id == 900101))
    ).scalar_one()
    assert contract.is_ship_contract is True
    assert contract.item_processing_status == "COMPLETED"

    items = (
        (await db_session.execute(select(ContractItem).order_by(ContractItem.record_id)))
        .scalars()
        .all()
    )
    assert [item.type_name for item in items] == ["Tristan", "Tritanium"]
    assert items[0].category == "ship"
    assert items[1].category is None
    assert items[0].market_group_id == 1367


async def test_process_contracts_excluded_ship_does_not_flag(db_session: AsyncSession):
    """A ship that is merely ASKED FOR (is_included=False) must not make the
    contract a ship contract — only included ships count."""
    service = _make_service()
    service.esi_client.get_contract_items = AsyncMock(
        return_value=[{"record_id": 21, "type_id": 587, "quantity": 1, "is_included": False}]
    )
    service.esi_client.get_universe_type = AsyncMock(
        return_value={"name": "Tristan", "group_id": 25, "market_group_id": 1367}
    )
    service.esi_client.get_universe_group = AsyncMock(
        return_value={"name": "Frigate", "category_id": 6}
    )

    await service._process_contracts(db_session, [_ship_contract_dict(900102)])

    contract = (
        await db_session.execute(select(Contract).where(Contract.contract_id == 900102))
    ).scalar_one()
    assert contract.is_ship_contract is False


async def test_process_contracts_type_resolution_failure_degrades_gracefully(
    db_session: AsyncSession,
):
    """ESI type lookups can fail; items keep NULL enrichment and the contract
    stays unflagged rather than the whole aggregation run dying (assertion on
    the mechanism: rows still land — TEST-2 mechanism-over-symptom)."""
    from fastapi_app.models.contracts import ContractItem

    service = _make_service()
    service.esi_client.get_contract_items = AsyncMock(
        return_value=[{"record_id": 31, "type_id": 99999, "quantity": 1, "is_included": True}]
    )
    service.esi_client.get_universe_type = AsyncMock(side_effect=RuntimeError("ESI down"))
    service.esi_client.get_universe_group = AsyncMock(side_effect=RuntimeError("ESI down"))

    await service._process_contracts(db_session, [_ship_contract_dict(900103)])

    contract = (
        await db_session.execute(select(Contract).where(Contract.contract_id == 900103))
    ).scalar_one()
    assert contract.is_ship_contract is False
    # Enrichment failed for this contract's item, so its status must NOT claim
    # COMPLETED — a future consumer trusting COMPLETED would skip re-enriching it.
    assert contract.item_processing_status == "ENRICHMENT_INCOMPLETE"
    item = (
        await db_session.execute(
            select(ContractItem).where(ContractItem.record_id == 31)
        )
    ).scalar_one()
    assert item.type_name is None


async def test_reingestion_with_unmodified_items_keeps_ship_flag(
    db_session: AsyncSession,
):
    """Regression: the contract upsert used to write is_ship_contract=False on
    every run, while ETag-304'd items skip enrichment — so ship flags decayed
    to False on the next aggregation cycle. The upsert must leave
    enrichment-maintained columns untouched on conflict."""
    from fastapi_app.core.exceptions import ESINotModifiedError

    service = _make_service()
    service.esi_client.get_contract_items = AsyncMock(
        return_value=[{"record_id": 41, "type_id": 587, "quantity": 1, "is_included": True}]
    )
    service.esi_client.get_universe_type = AsyncMock(
        return_value={"name": "Tristan", "group_id": 25, "market_group_id": 1367}
    )
    service.esi_client.get_universe_group = AsyncMock(
        return_value={"name": "Frigate", "category_id": 6}
    )
    await service._process_contracts(db_session, [_ship_contract_dict(900104)])

    # Second run: same contract, items unchanged (ESI answers 304).
    service.esi_client.get_contract_items = AsyncMock(side_effect=ESINotModifiedError())
    await service._process_contracts(db_session, [_ship_contract_dict(900104)])

    contract = (
        await db_session.execute(select(Contract).where(Contract.contract_id == 900104))
    ).scalar_one()
    assert contract.is_ship_contract is True, "ship flag must survive 304'd re-ingestion"
    assert contract.item_processing_status == "COMPLETED"


async def test_id_list_updates_batch_across_the_chunk_boundary(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
):
    """The post-enrichment is_ship_contract / item_processing_status UPDATEs must
    chunk their id lists (asyncpg 32767 bind-param cap). With the chunk size
    forced to 2 and THREE ship contracts, every contract must still be flagged
    and completed — i.e. the loop crosses the batch boundary (TEST-4 spirit).
    Before batching, one oversized IN() would have rolled back the whole run."""
    monkeypatch.setattr(bg_agg, "UPDATE_ID_CHUNK_SIZE", 2)

    service = _make_service()
    service.esi_client.get_contract_items = AsyncMock(
        side_effect=lambda cid: [{"record_id": cid, "type_id": 587, "quantity": 1, "is_included": True}]
    )
    service.esi_client.get_universe_type = AsyncMock(
        return_value={"name": "Tristan", "group_id": 25, "market_group_id": 1367}
    )
    service.esi_client.get_universe_group = AsyncMock(
        return_value={"name": "Frigate", "category_id": 6}
    )

    cids = [900301, 900302, 900303]
    await service._process_contracts(db_session, [_ship_contract_dict(c) for c in cids])

    rows = (
        (await db_session.execute(select(Contract).where(Contract.contract_id.in_(cids))))
        .scalars()
        .all()
    )
    assert len(rows) == 3
    assert all(r.is_ship_contract is True for r in rows)
    assert all(r.item_processing_status == "COMPLETED" for r in rows)


async def test_lock_release_deletes_only_its_own_token():
    """Happy path: the holder acquires, then compare-and-deletes its own token."""
    store: dict = {}
    with patch.object(bg_agg.aioredis, "from_url", return_value=_FakeLockRedis(store)):
        service = _make_service()
        async with service._concurrency_lock():
            assert bg_agg.AGGREGATION_LOCK_KEY in store  # held during the run
        assert bg_agg.AGGREGATION_LOCK_KEY not in store  # released after


async def test_lock_release_does_not_delete_a_reacquired_lock(caplog):
    """If the TTL expires mid-run and a second runner reacquires the key, the
    first runner's finally must NOT delete the second runner's lock (fencing
    token mismatch), and it must warn — preventing cascading concurrent runs."""
    store: dict = {}
    with patch.object(bg_agg.aioredis, "from_url", return_value=_FakeLockRedis(store)):
        service = _make_service()
        with caplog.at_level("WARNING"):
            async with service._concurrency_lock():
                # Simulate our TTL expiring mid-run; another runner grabs the key.
                store[bg_agg.AGGREGATION_LOCK_KEY] = "second-runner-token"

    assert store.get(bg_agg.AGGREGATION_LOCK_KEY) == "second-runner-token"
    assert "token mismatch" in caplog.text


async def test_process_contracts_persists_bpc_flag_and_is_bpc_filter_matches(
    db_session: AsyncSession, client: AsyncClient
):
    """Ingestion must map ESI's is_blueprint_copy onto the item — it was dropped
    before, leaving the is_bpc filter dead on real data (same class as the
    ship-flag gap). Drives the full pipeline: ingest a BPC item, then match it
    over HTTP with ?is_bpc=true (TEST-1: prove the request-bound filter, not just
    the column)."""
    service = _make_service()
    service.esi_client.get_contract_items = AsyncMock(
        return_value=[
            {
                "record_id": 51,
                "type_id": 621,
                "quantity": 1,
                "is_included": True,
                "is_blueprint_copy": True,
                "raw_quantity": 10,
            }
        ]
    )
    service.esi_client.get_universe_type = AsyncMock(
        return_value={"name": "Caracal Blueprint", "group_id": 105, "market_group_id": 2}
    )
    service.esi_client.get_universe_group = AsyncMock(
        return_value={"name": "Cruiser Blueprint", "category_id": 9}
    )

    await service._process_contracts(db_session, [_ship_contract_dict(900201)])
    await db_session.flush()

    item = (
        await db_session.execute(select(ContractItem).where(ContractItem.record_id == 51))
    ).scalar_one()
    assert item.is_blueprint_copy is True

    response = await client.get("/contracts/?is_bpc=true")
    assert response.status_code == 200
    matched_ids = [c["contract_id"] for c in response.json()["items"]]
    assert 900201 in matched_ids


async def test_item_fetch_failure_for_one_contract_does_not_abort_batch(db_session: AsyncSession):
    """One contract's item fetch raising must not prevent the other contract's
    items from landing, and the failed contract must never be marked processed."""
    service = _make_service()

    async def items_side_effect(contract_id):
        if contract_id == 910001:
            raise RuntimeError("simulated ESI items failure")
        return [{"record_id": 21, "type_id": 587, "quantity": 1, "is_included": True}]

    service.esi_client.get_contract_items = AsyncMock(side_effect=items_side_effect)
    service.esi_client.get_universe_type = AsyncMock(
        return_value={"name": "Rifter", "group_id": 25, "market_group_id": 64}
    )
    service.esi_client.get_universe_group = AsyncMock(
        return_value={"name": "Frigate", "category_id": 6}
    )
    contracts = [
        dict(_ship_contract_dict(910001)),
        dict(_ship_contract_dict(910002)),
    ]

    await service._process_contracts(db_session, contracts)

    item_rows = (
        await db_session.execute(
            select(ContractItem).where(ContractItem.contract_id == 910002)
        )
    ).scalars().all()
    assert len(item_rows) == 1  # the healthy contract's items landed

    failed_row = (
        await db_session.execute(
            select(Contract).where(Contract.contract_id == 910001)
        )
    ).scalar_one()
    healthy_row = (
        await db_session.execute(
            select(Contract).where(Contract.contract_id == 910002)
        )
    ).scalar_one()
    # The model default is 'PENDING_ITEMS' (models/contracts.py) — a contract
    # whose item fetch failed keeps the default, it is NEVER marked COMPLETED
    # or ENRICHMENT_INCOMPLETE (both require membership in processed ids).
    assert failed_row.item_processing_status == "PENDING_ITEMS"
    assert healthy_row.item_processing_status == "COMPLETED"


async def test_structure_ids_are_excluded_from_name_resolution(db_session: AsyncSession, caplog):
    """The resolvable-ID cut is `id < 100_000_000_000` (10^11): player-structure
    IDs at or above 10^11 are unresolvable via /universe/names/ and are filtered
    out of the resolve batch (name column stays NULL). Pin BOTH sides of the
    boundary so an off-by-one in the extracted helper cannot slip through."""
    caplog.set_level("INFO")  # the filter log is INFO; default capture level misses it
    service = _make_service()

    # Name whatever IDs actually reach the resolver. A static map would make the
    # NULL assertion below pass for the wrong reason (id simply absent from the
    # map); naming everything passed means a NULL name proves the id was FILTERED.
    async def name_everything_passed(ids):
        return {id_: f"Structure {id_}" for id_ in ids}

    service.esi_client.resolve_ids_to_names = AsyncMock(side_effect=name_everything_passed)

    contract = dict(_ship_contract_dict(910003))
    contract["start_location_id"] = 100_000_000_000      # first excluded id
    contract["end_location_id"] = 99_999_999_999         # last resolvable id
    contract["type"] = "courier"  # skip the item-fetch loop entirely

    await service._process_contracts(db_session, [contract])

    resolved_ids = service.esi_client.resolve_ids_to_names.await_args.args[0]
    assert 99_999_999_999 in resolved_ids
    assert 100_000_000_000 not in resolved_ids
    assert "Filtered out 1 unresolvable structure IDs." in caplog.text
    row = (
        await db_session.execute(
            select(Contract).where(Contract.contract_id == 910003)
        )
    ).scalar_one()
    # Excluded from the resolve batch, so it can never acquire a name. Widening the
    # cut to `<=` would name it "Structure 100000000000" and fail this assertion.
    assert row.start_location_name is None


async def test_resolved_location_names_land_on_persisted_contract_rows(db_session: AsyncSession):
    """Resolved names reach all three denormalized columns on the persisted row.

    `_build_contract_rows` takes `id_to_name_map` as an explicit parameter, so the
    resolve step and the row build are wired together at the call site. Nothing else
    in the suite asserts a POPULATED name, which leaves that wiring free to break
    silently — an empty map would still produce rows, just nameless ones. This pins
    all three lookups (start location, issuer, issuer corporation) through the full
    build-and-upsert path.
    """
    service = _make_service()
    service.esi_client.resolve_ids_to_names = AsyncMock(
        return_value={
            60003760: "Jita IV - Moon 4 - Caldari Navy Assembly Plant",
            1001: "Test Issuer",
            2002: "Test Issuer Corp",
        }
    )
    contract = dict(_ship_contract_dict(910004))
    contract["start_location_id"] = 60003760
    contract["issuer_id"] = 1001
    contract["issuer_corporation_id"] = 2002
    contract["type"] = "courier"  # skip the item-fetch loop entirely

    await service._process_contracts(db_session, [contract])

    row = (
        await db_session.execute(
            select(Contract).where(Contract.contract_id == 910004)
        )
    ).scalar_one()
    assert row.start_location_name == "Jita IV - Moon 4 - Caldari Navy Assembly Plant"
    assert row.issuer_name == "Test Issuer"
    assert row.issuer_corporation_name == "Test Issuer Corp"


async def test_failed_item_fetch_recovers_on_the_next_run(db_session: AsyncSession):
    """A contract whose item fetch failed is retried by the NEXT run, with no sweep.

    `_fetch_item_rows` gates only on contract type, never on item_processing_status,
    so every run re-fetches items for every item_exchange/auction contract in the
    batch. A contract left at PENDING_ITEMS by a transient ESI failure therefore
    recovers on the following run without any retry machinery. Adding a status gate
    as an "optimization" would strand those contracts permanently — this test is what
    catches that.
    """
    service = _make_service()
    service.esi_client.get_universe_type = AsyncMock(
        return_value={"name": "Rifter", "group_id": 25, "market_group_id": 64}
    )
    service.esi_client.get_universe_group = AsyncMock(
        return_value={"name": "Frigate", "category_id": 6}
    )
    contract = dict(_ship_contract_dict(910005))

    # Run 1: the item fetch fails, so the contract is left at the model default.
    service.esi_client.get_contract_items = AsyncMock(
        side_effect=RuntimeError("simulated ESI items failure")
    )
    await service._process_contracts(db_session, [contract])

    row = (
        await db_session.execute(
            select(Contract).where(Contract.contract_id == 910005)
        )
    ).scalar_one()
    assert row.item_processing_status == "PENDING_ITEMS"

    # Run 2: ESI recovers. The same contract is re-fetched with no intervention.
    service.esi_client.get_contract_items = AsyncMock(
        return_value=[{"record_id": 31, "type_id": 587, "quantity": 1, "is_included": True}]
    )
    await service._process_contracts(db_session, [contract])

    await db_session.refresh(row)
    assert row.item_processing_status == "COMPLETED"
    item_rows = (
        await db_session.execute(
            select(ContractItem).where(ContractItem.contract_id == 910005)
        )
    ).scalars().all()
    assert len(item_rows) == 1
async def test_run_aggregation_reuses_app_session_factory_and_never_logs_database_url(
    caplog, monkeypatch: pytest.MonkeyPatch
):
    """Secret-hygiene + single-engine contract (M4 spec §2/§6): run_aggregation must
    source its session from fastapi_app.db.AsyncSessionLocal (no per-run engine) and
    no log line may carry any fragment of DATABASE_URL (a real managed-PG URL prefix
    can include username and password)."""
    import fastapi_app.db as app_db

    service = _make_service()
    service.settings.AGGREGATION_REGION_IDS = [10000002]
    service.settings.AGGREGATION_DEV_CONTRACT_LIMIT = 0
    service.settings.DATABASE_URL = (
        "postgresql+asyncpg://secret_user:secret_pw@db.internal:5432/hb"
    )
    service.esi_client.get_public_contracts = AsyncMock(return_value=[])

    entered = {"count": 0}
    real_factory = app_db.AsyncSessionLocal

    def recording_factory():
        entered["count"] += 1
        return real_factory()

    monkeypatch.setattr(bg_agg, "AsyncSessionLocal", recording_factory, raising=False)

    store: dict = {}
    with patch.object(bg_agg.aioredis, "from_url", return_value=_FakeLockRedis(store)):
        with caplog.at_level("INFO"):
            await service.run_aggregation()

    assert entered["count"] == 1, (
        "run_aggregation must obtain its session from fastapi_app.db.AsyncSessionLocal"
    )
    for rec in caplog.records:
        msg = rec.getMessage()
        assert "Creating database engine" not in msg
        assert service.settings.DATABASE_URL[:16] not in msg


# --- ingestion-freshness recording (M4 Task 3.3) ---
# Key contract, pinned: JSON {"finished_at": iso, "outcome": "success|partial|failure",
# "regions_ok": int, "regions_failed": int, "last_success_at": iso-or-null} at key
# "hangar-bay:ingest:last_run", no TTL. regions_ok counts regions CHECKED OK — a fetch
# success AND an ETag-304 both count; success/partial may be recorded only after the
# shared transaction commits or completes as a valid no-op (the all-304 path);
# any processing/commit/top-level failure forces outcome="failure".

INGEST_KEY = "hangar-bay:ingest:last_run"


def _freshness_service(regions):
    service = _make_service()
    service.settings.AGGREGATION_REGION_IDS = list(regions)
    service.settings.AGGREGATION_DEV_CONTRACT_LIMIT = 0
    service.settings.DATABASE_URL = "postgresql+asyncpg://u:p@localhost:5432/unused"
    return service


def _gauge_value():
    from fastapi_app.core.metrics import last_ingest_success_timestamp
    return last_ingest_success_timestamp._value.get()


async def test_freshness_success_when_all_regions_fetch_ok(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
):
    """All regions fetch ok and the transaction commits → outcome success, gauge advances."""
    import json as _json
    from datetime import datetime as _dt

    from fastapi_app.tests.conftest import TEST_DATABASE_URL
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    engine = create_async_engine(TEST_DATABASE_URL)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(bg_agg, "AsyncSessionLocal", maker, raising=False)

    service = _freshness_service([10000002])
    service.esi_client.get_public_contracts = AsyncMock(
        return_value=[_ship_contract_dict(910001)]
    )

    store: dict = {}
    before = _gauge_value()
    with patch.object(bg_agg.aioredis, "from_url", return_value=_FakeLockRedis(store)):
        await service.run_aggregation()
    await engine.dispose()

    record = _json.loads(store[INGEST_KEY])
    assert record["outcome"] == "success"
    assert record["regions_ok"] == 1
    assert record["regions_failed"] == 0
    _dt.fromisoformat(record["finished_at"])  # raises if not ISO-8601
    assert record["last_success_at"] == record["finished_at"]
    assert _gauge_value() > before


async def test_freshness_success_when_all_regions_304(monkeypatch: pytest.MonkeyPatch):
    """The all-304 steady state is a SUCCESS (checked-ok), never a failure."""
    import json as _json

    service = _freshness_service([10000002, 10000043])
    from fastapi_app.core.exceptions import ESINotModifiedError as _NotModified
    service.esi_client.get_public_contracts = AsyncMock(side_effect=_NotModified("304"))

    store: dict = {}
    before = _gauge_value()
    with patch.object(bg_agg.aioredis, "from_url", return_value=_FakeLockRedis(store)):
        await service.run_aggregation()

    record = _json.loads(store[INGEST_KEY])
    assert record["outcome"] == "success"
    assert record["regions_ok"] == 2
    assert record["regions_failed"] == 0
    assert record["last_success_at"] == record["finished_at"]
    assert _gauge_value() > before


async def test_freshness_partial_when_one_region_fails(monkeypatch: pytest.MonkeyPatch):
    """One region checked ok, one fetch error → partial; timestamp still advances."""
    import json as _json

    service = _freshness_service([10000002, 10000043])
    service.esi_client.get_public_contracts = AsyncMock(
        side_effect=[[], RuntimeError("ESI 500")]
    )

    store: dict = {}
    before = _gauge_value()
    with patch.object(bg_agg.aioredis, "from_url", return_value=_FakeLockRedis(store)):
        await service.run_aggregation()

    record = _json.loads(store[INGEST_KEY])
    assert record["outcome"] == "partial"
    assert record["regions_ok"] == 1
    assert record["regions_failed"] == 1
    assert record["last_success_at"] == record["finished_at"]
    assert _gauge_value() > before


async def test_freshness_failure_when_commit_raises(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
):
    """A commit failure forces outcome=failure regardless of fetch counters;
    last_success_at preserves the PRIOR success and the gauge does not move."""
    import json as _json

    from fastapi_app.tests.conftest import TEST_DATABASE_URL
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    engine = create_async_engine(TEST_DATABASE_URL)
    maker = async_sessionmaker(engine, expire_on_commit=False)

    def boom_factory():
        session = maker()

        async def boom():
            raise RuntimeError("simulated commit failure")

        session.commit = boom
        return session

    monkeypatch.setattr(bg_agg, "AsyncSessionLocal", boom_factory, raising=False)

    service = _freshness_service([10000002])
    service.esi_client.get_public_contracts = AsyncMock(
        return_value=[_ship_contract_dict(910002)]
    )

    prior = "2026-07-18T00:00:00+00:00"
    store: dict = {
        INGEST_KEY: _json.dumps(
            {
                "finished_at": prior,
                "outcome": "success",
                "regions_ok": 1,
                "regions_failed": 0,
                "last_success_at": prior,
            }
        )
    }
    before = _gauge_value()
    with patch.object(bg_agg.aioredis, "from_url", return_value=_FakeLockRedis(store)):
        await service.run_aggregation()
    await engine.dispose()

    record = _json.loads(store[INGEST_KEY])
    assert record["outcome"] == "failure"
    assert record["regions_ok"] == 1
    assert record["regions_failed"] == 0
    assert record["last_success_at"] == prior
    assert _gauge_value() == before
