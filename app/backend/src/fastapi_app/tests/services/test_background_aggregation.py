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

import json
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

import fastapi_app.services.background_aggregation as bg_agg
from fastapi_app.models.contracts import Contract, ContractItem, EsiTaxonomyCache
from fastapi_app.services.background_aggregation import ContractAggregationService
from fastapi_app.tests.core.test_esi_client import _etag_client, _etag_response
from fastapi_app.tests.lock_double import FakeLockRedis as _FakeLockRedis

pytestmark = pytest.mark.asyncio


def _make_service() -> ContractAggregationService:
    esi_client = MagicMock()
    esi_client.resolve_ids_to_names = AsyncMock(
        return_value={60003760: "Jita IV - Moon 4 - Caldari Navy Assembly Plant"}
    )
    # get_contract_items is exercised by other flows; keep it inert here.
    esi_client.get_contract_items = AsyncMock(return_value=[])
    # A resolvable default keeps captured logs free of "can't be awaited" warnings
    # from the taxonomy-name fan-out; tests that exercise failure paths override it.
    esi_client.get_universe_category = AsyncMock(return_value={"name": "Ship"})
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
    from datetime import datetime, timedelta, timezone

    # date_expired must stay in the FUTURE. The contracts list endpoint excludes expired
    # contracts, so a fixture pinned to a past date is invisible to any test that queries
    # over HTTP rather than reading rows directly — which is exactly how this helper's
    # original hardcoded 2026-07-08 expiry broke the is_bpc filter test the moment that
    # exclusion landed. Relative to now, so it cannot rot back into the past.
    live_expiry = datetime.now(timezone.utc) + timedelta(days=7)
    return {
        "contract_id": cid,
        "issuer_id": 1,
        "issuer_corporation_id": 1,
        "start_location_id": 60003760,
        "type": "item_exchange",
        "price": 1_000_000.0,
        "date_issued": "2026-07-01T00:00:00Z",
        "date_expired": live_expiry.strftime("%Y-%m-%dT%H:%M:%SZ"),
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
    # ...and it must NOT carry the current enrichment stamp either. The stamp means
    # "enriched at this version"; stamping a degraded row would make the skip predicate
    # withhold it the moment anything repaired its status, stranding it unenriched.
    assert contract.enrichment_version == 0
    item = (
        await db_session.execute(
            select(ContractItem).where(ContractItem.record_id == 31)
        )
    ).scalar_one()
    assert item.type_name is None


async def test_reingestion_with_unmodified_items_keeps_ship_flag(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
):
    """Regression: the contract upsert used to write is_ship_contract=False on
    every run, while ETag-304'd items skip enrichment — so ship flags decayed
    to False on the next aggregation cycle. The upsert must leave
    enrichment-maintained columns untouched on conflict.

    The version bump is what puts the contract back in the fetch set, so the 304
    branch is actually reached: an already-enriched contract is skipped before ESI
    is asked at all. A 304 leaves the contract unenriched this cycle, so its stamp
    must stay at the old version — stamping the new one on a 304 would claim an
    enrichment that never ran."""
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
    stamped_version = bg_agg.ENRICHMENT_VERSION

    # Second run: same contract, re-queued by a version bump, items unchanged
    # (ESI answers 304).
    monkeypatch.setattr(bg_agg, "ENRICHMENT_VERSION", bg_agg.ENRICHMENT_VERSION + 1)
    service.esi_client.get_contract_items = AsyncMock(side_effect=ESINotModifiedError())
    await service._process_contracts(db_session, [_ship_contract_dict(900104)])
    assert service.esi_client.get_contract_items.await_count == 1, (
        "the re-queued contract must actually reach ESI, or the 304 branch is untested"
    )

    contract = (
        await db_session.execute(select(Contract).where(Contract.contract_id == 900104))
    ).scalar_one()
    assert contract.is_ship_contract is True, "ship flag must survive 304'd re-ingestion"
    assert contract.item_processing_status == "COMPLETED"
    assert contract.enrichment_version == stamped_version
    assert contract.enrichment_version != bg_agg.ENRICHMENT_VERSION, (
        "a 304 enriches nothing, so the contract stays queued at the old version"
    )


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


async def test_lock_ttl_exceeds_the_scheduler_interval():
    """The lock TTL is the mutual-exclusion window: if it is shorter than a real
    run, it expires mid-run and the next scheduler tick legally starts a second
    concurrent run (production 2026-07-23: a ~70-minute run overran a fixed
    1800s TTL). The TTL must strictly exceed the tick interval so the one
    overlapping tick always finds the lock held and skips."""
    store: dict = {}
    fake = _FakeLockRedis(store)
    with patch.object(bg_agg.aioredis, "from_url", return_value=fake):
        service = _make_service()
        service.settings.AGGREGATION_SCHEDULER_INTERVAL_SECONDS = 3600
        async with service._concurrency_lock():
            pass
    assert fake.set_ttls[bg_agg.AGGREGATION_LOCK_KEY] > 3600


async def test_lock_ttl_follows_a_reconfigured_interval():
    """The window must track the configured interval — a constant merely raised
    above today's interval silently re-opens the gap when the interval grows."""
    store: dict = {}
    fake = _FakeLockRedis(store)
    with patch.object(bg_agg.aioredis, "from_url", return_value=fake):
        service = _make_service()
        service.settings.AGGREGATION_SCHEDULER_INTERVAL_SECONDS = 7200
        async with service._concurrency_lock():
            pass
    assert fake.set_ttls[bg_agg.AGGREGATION_LOCK_KEY] > 7200


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


async def test_contract_returning_no_items_is_not_marked_completed(
    db_session: AsyncSession, caplog
):
    """An item_exchange contract with zero items is impossible — the fetch failed or
    returned an evicted-cache empty page. COMPLETED must mean the items were actually
    fetched, so a zero-item result must not claim success. The exclusion is per
    contract: a healthy contract in the same batch still completes."""
    service = _make_service()
    service.esi_client.get_contract_items = AsyncMock(
        side_effect=lambda cid: (
            []
            if cid == 930001
            # record_id is deliberately NOT the contract_id: the bookkeeping keys on
            # contract_id, and an item-keyed confusion would pass unnoticed if the two
            # were equal here.
            else [
                {
                    "record_id": cid + 500_000,
                    "type_id": 587,
                    "quantity": 1,
                    "is_included": True,
                }
            ]
        )
    )
    service.esi_client.get_universe_type = AsyncMock(
        return_value={"name": "Tristan", "group_id": 25, "market_group_id": 1367}
    )
    service.esi_client.get_universe_group = AsyncMock(
        return_value={"name": "Frigate", "category_id": 6}
    )

    with caplog.at_level("WARNING"):
        await service._process_contracts(
            db_session, [_ship_contract_dict(930001), _ship_contract_dict(930002)]
        )

    rows = {
        row.contract_id: row
        for row in (
            await db_session.execute(
                select(Contract).where(Contract.contract_id.in_([930001, 930002]))
            )
        ).scalars()
    }
    assert rows[930001].item_processing_status != "COMPLETED"
    # PENDING_ITEMS specifically — the model default, which the empty result leaves
    # untouched — and not a third status: a contract not marked COMPLETED stays in
    # the re-fetch set.
    assert rows[930001].item_processing_status == "PENDING_ITEMS"
    # The exclusion is per contract; it must not spill onto a healthy one.
    assert rows[930002].item_processing_status == "COMPLETED"

    # The count pins that only the empty contract was excluded.
    assert any(
        "1 contracts returned zero items and were not marked COMPLETED" in rec.getMessage()
        for rec in caplog.records
        if rec.levelname == "WARNING"
    ), f"expected the zero-item warning; got {[r.getMessage() for r in caplog.records]}"


async def test_multipage_item_fetch_persists_every_row_and_completes(db_session: AsyncSession):
    """Drives _process_contracts through a REAL ESIClient over a mocked transport,
    so the pagination walk and the enrichment bookkeeping are exercised together —
    a fixture-satisfied seam between them cannot hide truncation."""
    items_path = "/v1/contracts/public/items/940001/"
    pages = {
        f"{items_path}?page=1": [
            {"record_id": 990001, "type_id": 587, "quantity": 1, "is_included": True}
        ],
        f"{items_path}?page=2": [
            {"record_id": 990002, "type_id": 587, "quantity": 1, "is_included": True}
        ],
    }

    def serve_page(path, headers=None):
        # An unexpected path raises KeyError rather than serving a default: a walk
        # that runs past page 2 must fail loudly, not quietly repeat a page.
        body = pages[path]
        return _etag_response(
            200,
            json_data=body,
            content=json.dumps(body).encode(),
            headers={"X-Pages": "2"},
        )

    client = _etag_client(AsyncMock(side_effect=serve_page))
    # Location-name resolution is a POST sitting above this seam; serve it over the
    # same transport so the real method runs and logs no resolution failure.
    client.http_client.post = AsyncMock(
        return_value=_etag_response(
            200,
            json_data=[
                {"id": 60003760, "name": "Jita IV - Moon 4 - Caldari Navy Assembly Plant"}
            ],
        )
    )
    client.get_universe_type = AsyncMock(
        return_value={"name": "Rifter", "group_id": 25, "market_group_id": 64}
    )
    client.get_universe_group = AsyncMock(return_value={"name": "Frigate", "category_id": 6})

    service = ContractAggregationService(esi_client=client, settings=MagicMock())

    await service._process_contracts(db_session, [_ship_contract_dict(940001)])

    row = (
        await db_session.execute(select(Contract).where(Contract.contract_id == 940001))
    ).scalar_one()
    assert row.item_processing_status == "COMPLETED"

    # Both pages must have landed: a truncated walk yields {990001} while the status
    # still reads COMPLETED, which is exactly the failure this seam can hide.
    record_ids = set(
        (
            await db_session.execute(
                select(ContractItem.record_id).where(ContractItem.contract_id == 940001)
            )
        ).scalars()
    )
    assert record_ids == {990001, 990002}


async def test_successful_enrichment_stamps_the_current_version(db_session: AsyncSession):
    """The version stamp is what lets a future enrichment bug re-queue the corpus
    deliberately, replacing the refetch loop's accidental self-healing."""
    service = _make_service()
    service.esi_client.get_contract_items = AsyncMock(
        return_value=[{"record_id": 71, "type_id": 587, "quantity": 1, "is_included": True}]
    )
    service.esi_client.get_universe_type = AsyncMock(
        return_value={"name": "Rifter", "group_id": 25, "market_group_id": 4}
    )
    service.esi_client.get_universe_group = AsyncMock(
        return_value={"name": "Frigate", "category_id": 6}
    )

    await service._process_contracts(db_session, [_ship_contract_dict(930101)])

    row = (
        await db_session.execute(select(Contract).where(Contract.contract_id == 930101))
    ).scalar_one()
    assert row.enrichment_version == bg_agg.ENRICHMENT_VERSION


async def test_already_enriched_contracts_are_not_refetched(
    db_session: AsyncSession, caplog
):
    """The whole point: public contracts are immutable, so a contract enriched at the
    current version never needs fetching again."""
    service = _make_service()
    service.esi_client.get_contract_items = AsyncMock(
        return_value=[{"record_id": 81, "type_id": 587, "quantity": 1, "is_included": True}]
    )
    service.esi_client.get_universe_type = AsyncMock(
        return_value={"name": "Rifter", "group_id": 25, "market_group_id": 4}
    )
    service.esi_client.get_universe_group = AsyncMock(
        return_value={"name": "Frigate", "category_id": 6}
    )

    await service._process_contracts(db_session, [_ship_contract_dict(930201)])
    first_call_count = service.esi_client.get_contract_items.await_count

    # at_level only sets the capture level; records from run 1 are still in the
    # buffer, so clear it — the assertion below must only be satisfiable by run 2.
    caplog.clear()
    with caplog.at_level("INFO"):
        await service._process_contracts(db_session, [_ship_contract_dict(930201)])

    assert service.esi_client.get_contract_items.await_count == first_call_count
    # The run must REPORT the skip it performed, not the skip it intended: the fetched
    # count is what a disabled skip cannot fake.
    assert any(
        "Fetched items for 0 contracts (1 skipped as already enriched)."
        in rec.getMessage()
        for rec in caplog.records
    ), f"expected the fetched-vs-skipped line; got {[r.getMessage() for r in caplog.records]}"


async def test_a_demoted_contract_is_refetched_despite_a_current_stamp(
    db_session: AsyncSession,
):
    """The skip predicate needs BOTH arms: status AND version.

    Demoting item_processing_status is the repair lever — it is exactly what the
    zero-item repair migration pulls to put damaged rows back in the fetch set. That
    lever only works if the skip actually reads the status: a version-only predicate
    would keep skipping a demoted row forever, because a repair demotes the status
    without touching the stamp.
    """
    service = _make_service()
    service.esi_client.get_contract_items = AsyncMock(
        return_value=[{"record_id": 83, "type_id": 587, "quantity": 1, "is_included": True}]
    )
    service.esi_client.get_universe_type = AsyncMock(
        return_value={"name": "Rifter", "group_id": 25, "market_group_id": 4}
    )
    service.esi_client.get_universe_group = AsyncMock(
        return_value={"name": "Frigate", "category_id": 6}
    )

    await service._process_contracts(db_session, [_ship_contract_dict(930203)])
    before = service.esi_client.get_contract_items.await_count

    # The repair: status demoted, stamp deliberately LEFT at the current version.
    await db_session.execute(
        update(Contract)
        .where(Contract.contract_id == 930203)
        .values(item_processing_status="PENDING_ITEMS")
    )
    db_session.expire_all()

    await service._process_contracts(db_session, [_ship_contract_dict(930203)])

    assert service.esi_client.get_contract_items.await_count == before + 1
    row = (
        await db_session.execute(select(Contract).where(Contract.contract_id == 930203))
    ).scalar_one()
    assert row.item_processing_status == "COMPLETED"
    assert row.enrichment_version == bg_agg.ENRICHMENT_VERSION


async def test_bumping_the_enrichment_version_requeues_a_contract(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
):
    """Version bump is the deliberate replacement for accidental self-healing, so it
    must actually re-fetch."""
    service = _make_service()
    service.esi_client.get_contract_items = AsyncMock(
        return_value=[{"record_id": 82, "type_id": 587, "quantity": 1, "is_included": True}]
    )
    service.esi_client.get_universe_type = AsyncMock(
        return_value={"name": "Rifter", "group_id": 25, "market_group_id": 4}
    )
    service.esi_client.get_universe_group = AsyncMock(
        return_value={"name": "Frigate", "category_id": 6}
    )

    await service._process_contracts(db_session, [_ship_contract_dict(930202)])
    before = service.esi_client.get_contract_items.await_count

    monkeypatch.setattr(bg_agg, "ENRICHMENT_VERSION", bg_agg.ENRICHMENT_VERSION + 1)
    await service._process_contracts(db_session, [_ship_contract_dict(930202)])

    assert service.esi_client.get_contract_items.await_count == before + 1
    # Stamp and skip must read the SAME constant. If either side hardcoded a literal
    # they would agree at version 1 forever: the re-fetch above would still happen,
    # while the contract never advanced past the old version and would be re-fetched
    # on every subsequent run — the skip silently doing nothing.
    row = (
        await db_session.execute(select(Contract).where(Contract.contract_id == 930202))
    ).scalar_one()
    assert row.enrichment_version == bg_agg.ENRICHMENT_VERSION


async def test_a_version_bump_clears_a_stale_ship_flag(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
):
    """is_ship_contract must not be monotonic. Enrichment that only ever SET the flag
    left a false positive from a past enrichment bug surviving every re-enrichment,
    which breaks what the version bump is for: it is the deliberate repair lever for
    enrichment-logic fixes, and flags are exactly what such a fix must repair."""
    service = _make_service()
    service.esi_client.get_contract_items = AsyncMock(
        return_value=[{"record_id": 84, "type_id": 587, "quantity": 1, "is_included": True}]
    )
    service.esi_client.get_universe_type = AsyncMock(
        return_value={"name": "Rifter", "group_id": 25, "market_group_id": 4}
    )
    service.esi_client.get_universe_group = AsyncMock(
        return_value={"name": "Frigate", "category_id": 6}
    )

    await service._process_contracts(db_session, [_ship_contract_dict(930207)])
    row = (
        await db_session.execute(select(Contract).where(Contract.contract_id == 930207))
    ).scalar_one()
    assert row.is_ship_contract is True, "precondition: the stale flag must be set first"

    # The repaired enrichment: same item, now correctly resolved as a non-ship. The
    # group RESOLVES — this is a corrected answer, not a degraded one.
    monkeypatch.setattr(bg_agg, "ENRICHMENT_VERSION", bg_agg.ENRICHMENT_VERSION + 1)
    service.esi_client.get_universe_group = AsyncMock(
        return_value={"name": "Mineral", "category_id": 4}
    )
    await service._process_contracts(db_session, [_ship_contract_dict(930207)])

    await db_session.refresh(row)
    assert row.is_ship_contract is False
    assert row.item_processing_status == "COMPLETED"
    assert row.enrichment_version == bg_agg.ENRICHMENT_VERSION


async def test_unresolved_category_leaves_a_contract_retryable(db_session: AsyncSession):
    """An unresolved item category is an incomplete enrichment, not a success.

    The type resolves, so the older rule (every item resolved a type_name) called this
    contract COMPLETED and stamped it — after which the skip withheld it forever,
    silently unenriched and mis-flagged, recoverable only by a version bump. It is the
    same invariant the zero-item guard enforces: COMPLETED must mean enrichment
    actually succeeded. Left incomplete, the contract simply retries next run.
    """
    service = _make_service()
    service.esi_client.get_contract_items = AsyncMock(
        return_value=[{"record_id": 86, "type_id": 587, "quantity": 1, "is_included": True}]
    )
    service.esi_client.get_universe_type = AsyncMock(
        return_value={"name": "Rifter", "group_id": 25, "market_group_id": 4}
    )
    service.esi_client.get_universe_group = AsyncMock(side_effect=RuntimeError("ESI down"))

    await service._process_contracts(db_session, [_ship_contract_dict(930209)])
    before = service.esi_client.get_contract_items.await_count

    row = (
        await db_session.execute(select(Contract).where(Contract.contract_id == 930209))
    ).scalar_one()
    assert row.item_processing_status == "ENRICHMENT_INCOMPLETE"
    assert row.enrichment_version == 0

    # ESI recovers. No version bump and no sweep: the contract was never marked
    # COMPLETED, so the skip never withheld it.
    service.esi_client.get_universe_group = AsyncMock(
        return_value={"name": "Frigate", "category_id": 6}
    )
    await service._process_contracts(db_session, [_ship_contract_dict(930209)])

    assert service.esi_client.get_contract_items.await_count == before + 1
    await db_session.refresh(row)
    assert row.item_processing_status == "COMPLETED"
    assert row.enrichment_version == bg_agg.ENRICHMENT_VERSION
    assert row.is_ship_contract is True


async def test_degraded_category_resolution_does_not_clear_a_ship_flag(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
):
    """Clearing may only act on an authoritative determination.

    A failed /universe/groups/ lookup yields is_ship=False while the item's type_name
    resolves fine, so a clear keyed on "not in the ship set" would strip correct flags
    on a transient ESI blip — worse than the stale flag it repairs, since the
    ships-only default view is the app's landing page. What protects the flag is that
    an unresolved category leaves the contract ENRICHMENT_INCOMPLETE, and the clear
    only ever draws from the completed set."""
    service = _make_service()
    service.esi_client.get_contract_items = AsyncMock(
        return_value=[{"record_id": 85, "type_id": 587, "quantity": 1, "is_included": True}]
    )
    service.esi_client.get_universe_type = AsyncMock(
        return_value={"name": "Rifter", "group_id": 25, "market_group_id": 4}
    )
    service.esi_client.get_universe_group = AsyncMock(
        return_value={"name": "Frigate", "category_id": 6}
    )

    await service._process_contracts(db_session, [_ship_contract_dict(930208)])
    row = (
        await db_session.execute(select(Contract).where(Contract.contract_id == 930208))
    ).scalar_one()
    assert row.is_ship_contract is True

    monkeypatch.setattr(bg_agg, "ENRICHMENT_VERSION", bg_agg.ENRICHMENT_VERSION + 1)
    service.esi_client.get_universe_group = AsyncMock(side_effect=RuntimeError("ESI down"))
    await service._process_contracts(db_session, [_ship_contract_dict(930208)])

    await db_session.refresh(row)
    assert row.is_ship_contract is True, "a degraded category read must not clear a flag"


async def test_a_requested_items_failed_category_leaves_the_contract_retryable(
    db_session: AsyncSession,
):
    """Want-to-buy side: an EXCLUDED item with no resolvable group must block
    COMPLETED, or the contract is withheld from every future re-fetch with a
    permanently blank requested side. The requested half is rendered and
    summarized by category, so its taxonomy is load-bearing, not cosmetic."""
    service = _make_service()
    service.esi_client.get_contract_items = AsyncMock(
        return_value=[
            {"record_id": 8411, "type_id": 587, "quantity": 1, "is_included": True},
            {"record_id": 8412, "type_id": 99999, "quantity": 1, "is_included": False},
        ]
    )
    service.esi_client.get_universe_type = AsyncMock(
        side_effect=lambda tid: {
            587: {"name": "Tristan", "group_id": 25},
            99999: {"name": "Mystery Meat"},  # no group_id: the chain stops here
        }[tid]
    )
    service.esi_client.get_universe_group = AsyncMock(
        return_value={"name": "Frigate", "category_id": 6}
    )

    await service._process_contracts(db_session, [_ship_contract_dict(841)])

    row = (
        await db_session.execute(select(Contract).where(Contract.contract_id == 841))
    ).scalar_one()
    assert row.item_processing_status == "ENRICHMENT_INCOMPLETE"
    assert row.enrichment_version == 0


async def test_a_category_less_group_payload_leaves_the_contract_retryable(
    db_session: AsyncSession,
):
    """A non-empty group payload that omits category_id is a resolution failure too.

    Testing the group dict for emptiness passes on this shape, category_id lands NULL,
    and the contract is stamped COMPLETED forever — the silent unenrichment the
    predicate exists to prevent. The test that decides is the resolved category itself.
    """
    service = _make_service()
    service.esi_client.get_contract_items = AsyncMock(
        return_value=[
            {"record_id": 8421, "type_id": 587, "quantity": 1, "is_included": True},
            {"record_id": 8422, "type_id": 99999, "quantity": 1, "is_included": False},
        ]
    )
    service.esi_client.get_universe_type = AsyncMock(
        side_effect=lambda tid: {
            587: {"name": "Tristan", "group_id": 25},
            99999: {"name": "Mystery Meat", "group_id": 26},
        }[tid]
    )
    service.esi_client.get_universe_group = AsyncMock(
        side_effect=lambda gid: {
            25: {"name": "Frigate", "category_id": 6},
            26: {"name": "Salvaged Materials"},  # no category_id
        }[gid]
    )

    await service._process_contracts(db_session, [_ship_contract_dict(842)])

    row = (
        await db_session.execute(select(Contract).where(Contract.contract_id == 842))
    ).scalar_one()
    assert row.item_processing_status == "ENRICHMENT_INCOMPLETE"
    assert row.enrichment_version == 0


async def test_skip_select_reads_across_the_chunk_boundary(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch, caplog
):
    """The already-enriched SELECT chunks its id list for the same reason the UPDATEs
    do (asyncpg's 32767 bind-param cap; a corpus-scale IN() rolls the run back), and
    a read that stops after the first chunk silently re-fetches the rest — cheaper to
    miss than a crash, so it needs its own boundary crossing. With the chunk size
    forced to 2 and THREE enriched contracts, all three must be skipped."""
    monkeypatch.setattr(bg_agg, "UPDATE_ID_CHUNK_SIZE", 2)

    service = _make_service()
    service.esi_client.get_contract_items = AsyncMock(
        side_effect=lambda cid: [
            {"record_id": cid + 500_000, "type_id": 587, "quantity": 1, "is_included": True}
        ]
    )
    service.esi_client.get_universe_type = AsyncMock(
        return_value={"name": "Rifter", "group_id": 25, "market_group_id": 4}
    )
    service.esi_client.get_universe_group = AsyncMock(
        return_value={"name": "Frigate", "category_id": 6}
    )

    cids = [930204, 930205, 930206]
    batch = [_ship_contract_dict(c) for c in cids]
    await service._process_contracts(db_session, batch)
    after_first_run = service.esi_client.get_contract_items.await_count
    assert after_first_run == 3

    with caplog.at_level("INFO"):
        await service._process_contracts(db_session, [_ship_contract_dict(c) for c in cids])

    assert service.esi_client.get_contract_items.await_count == after_first_run
    # The count is the boundary evidence: a read that stopped after the first chunk
    # reports 2 skipped, not 3, while still looking like the skip works.
    assert any(
        "Fetched items for 0 contracts (3 skipped as already enriched)."
        in rec.getMessage()
        for rec in caplog.records
    ), f"expected all three skipped; got {[r.getMessage() for r in caplog.records]}"


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


async def test_type_specific_contract_fields_land_on_persisted_rows(db_session: AsyncSession):
    """buyout / days_to_complete / end_location_name persist from the ESI payload.

    _build_contract_rows is only exercised end-to-end (nothing unit-tests its dict
    literal), so each new key needs a persisted-row assertion or its wiring can
    silently drop (same rationale as the location-names test above).
    """
    service = _make_service()
    contract = _ship_contract_dict(801)
    contract["type"] = "auction"
    contract["buyout"] = 950_000_000.0
    contract["days_to_complete"] = 3          # ESI sends it on couriers; mapping is type-agnostic
    contract["end_location_id"] = 60008494
    service.esi_client.resolve_ids_to_names = AsyncMock(
        return_value={
            60003760: "Jita IV - Moon 4 - Caldari Navy Assembly Plant",
            60008494: "Amarr VIII (Oris) - Emperor Family Academy",
        }
    )
    # A real item keeps the auction off the zero-items warning path, so the run's
    # captured logs stay pristine (an item_exchange/auction cannot be empty).
    service.esi_client.get_contract_items = AsyncMock(return_value=[
        {"record_id": 8011, "type_id": 587, "quantity": 1, "is_included": True},
    ])
    service.esi_client.get_universe_type = AsyncMock(
        return_value={"name": "Tristan", "group_id": 25, "market_group_id": 5}
    )
    service.esi_client.get_universe_group = AsyncMock(
        return_value={"name": "Frigate", "category_id": 6}
    )
    await service._process_contracts(db_session, [contract])

    row = (await db_session.execute(
        select(Contract).where(Contract.contract_id == 801)
    )).scalar_one()
    assert row.buyout == 950_000_000
    assert row.days_to_complete == 3
    assert row.end_location_name == "Amarr VIII (Oris) - Emperor Family Academy"

    # Absence stays NULL (ESI-3): a payload without the fields must not write zeros.
    # Fresh record_id so the upsert cannot move contract 801's item row here.
    service.esi_client.get_contract_items = AsyncMock(return_value=[
        {"record_id": 8021, "type_id": 587, "quantity": 1, "is_included": True},
    ])
    bare = _ship_contract_dict(802)
    await service._process_contracts(db_session, [bare])
    bare_row = (await db_session.execute(
        select(Contract).where(Contract.contract_id == 802)
    )).scalar_one()
    assert bare_row.buyout is None
    assert bare_row.days_to_complete is None
    assert bare_row.end_location_name is None


async def test_item_level_columns_persist_from_payload_and_enrichment(db_session: AsyncSession):
    """runs/ME/TE/item_id come off the item payload; category_id/group_id off the
    type→group chain the ship flag already walks. A blueprint ORIGINAL omits runs
    entirely (ESI-3) and must persist NULL, not zero."""
    service = _make_service()
    contract = _ship_contract_dict(821)
    service.esi_client.get_contract_items = AsyncMock(return_value=[
        {"record_id": 8211, "type_id": 621, "quantity": 1, "is_included": True,
         "is_blueprint_copy": True, "runs": 10, "material_efficiency": 8,
         "time_efficiency": 14, "item_id": 1_000_000_001},
        {"record_id": 8212, "type_id": 621, "quantity": 1, "is_included": True},  # original: runs absent
        # A type whose payload carries no group_id: taxonomy ids must persist as
        # NULL, never a fabricated default (ESI-3 — absence is not zero).
        {"record_id": 8213, "type_id": 999, "quantity": 1, "is_included": True},
    ])
    service.esi_client.get_universe_type = AsyncMock(
        side_effect=lambda type_id: {
            621: {"name": "Caracal Blueprint", "group_id": 105, "market_group_id": 4},
            999: {"name": "Mystery Meat"},
        }[type_id]
    )
    service.esi_client.get_universe_group = AsyncMock(
        return_value={"name": "Cruiser Blueprint", "category_id": 9}
    )
    await service._process_contracts(db_session, [contract])

    rows = {r.record_id: r for r in (await db_session.execute(
        select(ContractItem).where(ContractItem.contract_id == 821)
    )).scalars()}
    copy, original = rows[8211], rows[8212]
    assert (copy.runs, copy.material_efficiency, copy.time_efficiency) == (10, 8, 14)
    assert copy.item_id == 1_000_000_001
    assert copy.category_id == 9 and copy.group_id == 105
    assert original.runs is None
    assert original.material_efficiency is None
    assert original.time_efficiency is None
    assert original.item_id is None
    assert original.category_id == 9          # taxonomy resolves regardless of blueprint fields
    groupless = rows[8213]
    assert groupless.group_id is None
    assert groupless.category_id is None


async def test_enrichment_fills_the_taxonomy_name_cache(db_session: AsyncSession):
    """Group names ride the payloads enrichment already fetches; category names come
    from the one new ESI call (spec §5.2), cache-first so the tiny immutable set is
    fetched once, ever."""
    service = _make_service()
    contract = _ship_contract_dict(831)
    service.esi_client.get_contract_items = AsyncMock(return_value=[
        {"record_id": 8311, "type_id": 587, "quantity": 1, "is_included": True},
    ])
    service.esi_client.get_universe_type = AsyncMock(
        return_value={"name": "Tristan", "group_id": 25, "market_group_id": 5}
    )
    service.esi_client.get_universe_group = AsyncMock(
        return_value={"name": "Frigate", "category_id": 6}
    )
    service.esi_client.get_universe_category = AsyncMock(return_value={"name": "Ship"})
    await service._process_contracts(db_session, [contract])

    rows = {(r.kind, r.esi_id): r for r in (await db_session.execute(
        select(EsiTaxonomyCache)
    )).scalars()}
    assert rows[("group", 25)].name == "Frigate"
    assert rows[("group", 25)].parent_category_id == 6
    assert rows[("category", 6)].name == "Ship"

    # Second run: category already cached — the ESI call must not repeat.
    service.esi_client.get_universe_category.reset_mock()
    again = _ship_contract_dict(832)
    service.esi_client.get_contract_items = AsyncMock(return_value=[
        {"record_id": 8321, "type_id": 587, "quantity": 1, "is_included": True},
    ])
    await service._process_contracts(db_session, [again])
    service.esi_client.get_universe_category.assert_not_awaited()


async def test_a_failed_category_name_fetch_is_repaired_from_observed_items(
    db_session: AsyncSession,
):
    """A category whose name fetch failed must be retried without re-enrichment.

    The contract that carried it is stamped COMPLETED (a missing NAME is not a
    missing category), so the item-fetch skip withholds it from every later run
    and its group payload never reaches the cache writer again. The categories to
    fetch therefore include the ones observed on stored items but absent from the
    cache — which is what makes the repair happen on a run whose own batch carries
    no items at all.
    """
    service = _make_service()
    service.esi_client.get_contract_items = AsyncMock(return_value=[
        {"record_id": 8411, "type_id": 587, "quantity": 1, "is_included": True},
    ])
    service.esi_client.get_universe_type = AsyncMock(
        return_value={"name": "Tristan", "group_id": 25, "market_group_id": 5}
    )
    service.esi_client.get_universe_group = AsyncMock(
        return_value={"name": "Frigate", "category_id": 6}
    )
    service.esi_client.get_universe_category = AsyncMock(
        side_effect=RuntimeError("ESI down")
    )

    await service._process_contracts(db_session, [_ship_contract_dict(841)])

    assert (await db_session.execute(
        select(EsiTaxonomyCache).where(EsiTaxonomyCache.kind == "category")
    )).scalars().all() == []
    contract = (await db_session.execute(
        select(Contract).where(Contract.contract_id == 841)
    )).scalar_one()
    assert contract.item_processing_status == "COMPLETED"

    # Next run: ESI recovers, the batch is courier-only — no items are fetched, so
    # nothing in this run's enrichment mentions category 6. The stored item does.
    # A FRESH service proves the retry is DB-observed, not in-memory state that a
    # process restart would lose.
    service = _make_service()
    courier = _ship_contract_dict(842)
    courier["type"] = "courier"
    await service._process_contracts(db_session, [courier])

    row = (await db_session.execute(
        select(EsiTaxonomyCache).where(
            EsiTaxonomyCache.kind == "category", EsiTaxonomyCache.esi_id == 6
        )
    )).scalar_one()
    assert row.name == "Ship"


async def test_a_nameless_group_payload_is_repaired_from_observed_items(
    db_session: AsyncSession,
):
    """A group payload carrying category_id but no name must not be lost forever.

    The item resolves (category_id present), the contract is stamped COMPLETED, and
    the enrichment skip withholds it from every later run — so without a DB-observed
    retry the group would stay absent from the taxonomy option list permanently.
    Same self-healing shape as categories, one level down.
    """
    service = _make_service()
    service.esi_client.get_contract_items = AsyncMock(return_value=[
        {"record_id": 8511, "type_id": 587, "quantity": 1, "is_included": True},
    ])
    service.esi_client.get_universe_type = AsyncMock(
        return_value={"name": "Tristan", "group_id": 25, "market_group_id": 5}
    )
    # The codex-flagged shape: category resolves, the group name is absent.
    service.esi_client.get_universe_group = AsyncMock(
        return_value={"category_id": 6}
    )

    await service._process_contracts(db_session, [_ship_contract_dict(851)])

    assert (await db_session.execute(
        select(EsiTaxonomyCache).where(EsiTaxonomyCache.kind == "group")
    )).scalars().all() == []
    contract = (await db_session.execute(
        select(Contract).where(Contract.contract_id == 851)
    )).scalar_one()
    assert contract.item_processing_status == "COMPLETED"

    # Next run, fresh service, healed ESI, courier-only batch: the stored item's
    # group_id is the only mention of group 25, and it must be enough.
    service = _make_service()
    service.esi_client.get_universe_group = AsyncMock(
        return_value={"name": "Frigate", "category_id": 6}
    )
    courier = _ship_contract_dict(852)
    courier["type"] = "courier"
    await service._process_contracts(db_session, [courier])

    row = (await db_session.execute(
        select(EsiTaxonomyCache).where(
            EsiTaxonomyCache.kind == "group", EsiTaxonomyCache.esi_id == 25
        )
    )).scalar_one()
    assert row.name == "Frigate"
    assert row.parent_category_id == 6


async def test_failed_item_fetch_recovers_on_the_next_run(db_session: AsyncSession):
    """A contract whose item fetch failed is retried by the NEXT run, with no sweep.

    The item-fetch skip is narrow by design: only COMPLETED-at-the-current-version
    contracts are withheld. A contract left at PENDING_ITEMS by a transient ESI
    failure is still fetched every run and therefore recovers without any retry
    machinery. Widening the gate to "any contract we already have a status for"
    would strand those contracts permanently — this test is what catches that.
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


async def test_freshness_recorder_overwrites_a_non_object_prior_record(
    monkeypatch: pytest.MonkeyPatch,
):
    """A corrupt (valid JSON, non-object) prior record must be treated as no-prior and
    OVERWRITTEN — an uncaught AttributeError would skip the SET forever, leaving every
    future run unable to repair the key."""
    import json as _json

    service = _freshness_service([10000002])
    from fastapi_app.core.exceptions import ESINotModifiedError as _NotModified
    service.esi_client.get_public_contracts = AsyncMock(side_effect=_NotModified("304"))

    store: dict = {INGEST_KEY: "[]"}
    with patch.object(bg_agg.aioredis, "from_url", return_value=_FakeLockRedis(store)):
        await service.run_aggregation()

    record = _json.loads(store[INGEST_KEY])
    assert isinstance(record, dict)
    assert record["outcome"] == "success"
    assert record["last_success_at"] == record["finished_at"]


async def test_run_aggregation_rejects_non_list_region_config(caplog):
    """A region config that is not a list of int aborts the run before the
    concurrency lock is ever created, so a misconfigured deployment cannot
    occupy the lock slot or open a database engine it will never use."""
    caplog.set_level("ERROR")  # the type guard logs at ERROR
    service = _make_service()
    service.settings.AGGREGATION_REGION_IDS = "10000002"  # str, not list[int]

    with patch.object(service, "_concurrency_lock") as lock:
        await service.run_aggregation()

    lock.assert_not_called()  # bailed before ever touching the lock
    assert "CRITICAL_ERROR_AGG_SERVICE" in caplog.text


async def test_run_aggregation_rejects_region_list_containing_a_non_int(caplog):
    """The type guard has two clauses — `not isinstance(..., list)` AND
    `not all(isinstance(x, int) ...)`. A LIST carrying a non-int element clears
    the first clause and must be caught by the second: env parsing can yield
    `["10000002"]` from a JSON string list, which would otherwise reach ESI as a
    string region id. Asserts the exact level and full message, so dropping the
    element check cannot be masked by some other ERROR record."""
    caplog.set_level("ERROR")
    service = _make_service()
    service.settings.AGGREGATION_REGION_IDS = [10000002, "not-an-int"]

    with patch.object(service, "_concurrency_lock") as lock:
        await service.run_aggregation()

    lock.assert_not_called()  # bailed before ever touching the lock
    assert [(r.levelname, r.getMessage()) for r in caplog.records] == [
        (
            "ERROR",
            "CRITICAL_ERROR_AGG_SERVICE: AGGREGATION_REGION_IDS is not a list of int: "
            "[10000002, 'not-an-int'] (type: <class 'list'>) Aborting aggregation.",
        )
    ]


async def test_run_aggregation_skips_on_empty_region_list(caplog):
    """An empty list clears the type guard (all() is vacuously true) and trips
    the separate emptiness guard, which is a WARNING skip rather than an ERROR
    abort — and still returns ahead of the lock."""
    caplog.set_level("WARNING")  # the emptiness guard logs at WARNING
    service = _make_service()
    service.settings.AGGREGATION_REGION_IDS = []

    with patch.object(service, "_concurrency_lock") as lock:
        await service.run_aggregation()

    lock.assert_not_called()
    assert "AGGREGATION_REGION_IDS is empty" in caplog.text


# --- Per-region fetch loop -------------------------------------------------
# regions_ok/regions_failed are load-bearing: they are the sole input to the
# freshness record's outcome, so a miscount silently changes what readiness
# reports. These exercise the loop directly; the end-to-end consequences of the
# same counters are covered by the freshness tests above.


async def test_fetch_regions_isolates_one_regions_failure(caplog):
    """A fetch error in one region must not lose the other region's contracts,
    and must land in regions_failed rather than regions_ok."""
    caplog.set_level("ERROR")  # the per-region failure logs at ERROR
    service = _make_service()
    service.esi_client.get_public_contracts = AsyncMock(
        side_effect=[RuntimeError("ESI 500"), [_ship_contract_dict(920001)]]
    )

    contracts, regions_ok, regions_failed = await service._fetch_regions(
        [10000002, 10000043]
    )

    assert [c["contract_id"] for c in contracts] == [920001]
    assert regions_ok == 1
    assert regions_failed == 1
    assert "Failed to fetch contracts for region 10000002" in caplog.text


async def test_fetch_regions_counts_a_304_region_as_ok():
    """A 304 means ESI answered healthily and our data is current — it is a
    CHECKED-OK region, not a failure, so an all-304 run still reports success."""
    from fastapi_app.core.exceptions import ESINotModifiedError as _NotModified

    service = _make_service()
    service.esi_client.get_public_contracts = AsyncMock(
        side_effect=[_NotModified("304"), [_ship_contract_dict(920002)]]
    )

    contracts, regions_ok, regions_failed = await service._fetch_regions(
        [10000002, 10000043]
    )

    assert [c["contract_id"] for c in contracts] == [920002]
    assert regions_ok == 2
    assert regions_failed == 0


async def test_fetch_regions_stamps_each_contract_with_its_own_region():
    """Two successful regions: each contract must carry the region it was
    fetched FROM. A global stamp would give both contracts the same id."""
    service = _make_service()
    first = _ship_contract_dict(920003)
    second = _ship_contract_dict(920004)
    # The shared fixture pre-stamps every contract with region 10000002, which is
    # also the FIRST region fetched here — so a run that never stamped anything
    # would still satisfy the first contract's assertion by accident. Overwrite
    # both stamps with a value no region uses, making the assertion reachable
    # only if the fetch loop actually writes the stamp.
    first["_hb_region_id"] = -1
    second["_hb_region_id"] = -1
    service.esi_client.get_public_contracts = AsyncMock(side_effect=[[first], [second]])

    contracts, regions_ok, regions_failed = await service._fetch_regions(
        [10000002, 10000043]
    )

    stamped = {c["contract_id"]: c["_hb_region_id"] for c in contracts}
    assert stamped == {920003: 10000002, 920004: 10000043}
    assert regions_ok == 2
    assert regions_failed == 0


async def test_apply_dev_limit_truncates_and_warns(caplog):
    """With a limit configured, an over-limit batch is truncated to the limit."""
    caplog.set_level("WARNING")  # the DEV_MODE truncation logs at WARNING
    service = _make_service()
    service.settings.AGGREGATION_DEV_CONTRACT_LIMIT = 2
    batch = [_ship_contract_dict(cid) for cid in (920005, 920006, 920007)]

    limited = service._apply_dev_limit(batch)

    assert [c["contract_id"] for c in limited] == [920005, 920006]
    assert "DEV_MODE: Limiting contracts to process from 3 to 2." in caplog.text


async def test_apply_dev_limit_passes_through_when_unset(caplog):
    """Limit 0 (the production setting) must not truncate or warn."""
    caplog.set_level("WARNING")
    service = _make_service()
    service.settings.AGGREGATION_DEV_CONTRACT_LIMIT = 0
    batch = [_ship_contract_dict(cid) for cid in (920008, 920009, 920010)]

    limited = service._apply_dev_limit(batch)

    assert [c["contract_id"] for c in limited] == [920008, 920009, 920010]
    assert "DEV_MODE" not in caplog.text


async def test_apply_dev_limit_passes_through_when_none(caplog):
    """AGGREGATION_DEV_CONTRACT_LIMIT is typed `int | None`, so None is a reachable
    value distinct from 0. The guard is truthiness-first, so None short-circuits
    before the `> 0` comparison that would raise on a None operand — the batch
    passes through untruncated and unwarned, exactly as it does for 0."""
    caplog.set_level("WARNING")
    service = _make_service()
    service.settings.AGGREGATION_DEV_CONTRACT_LIMIT = None
    batch = [_ship_contract_dict(cid) for cid in (920011, 920012, 920013)]

    limited = service._apply_dev_limit(batch)

    assert [c["contract_id"] for c in limited] == [920011, 920012, 920013]
    assert "DEV_MODE" not in caplog.text


# --- Start-location system resolution ---------------------------------------
#
# ESI's public contract payload carries a location id and no system id, so
# Contract.start_location_system_id stayed NULL for every ingested row and the
# system_ids filter matched nothing. Ingestion resolves NPC stations through
# GET /v2/universe/stations/, which is public and returns `system_id`.
#
# Coverage is partial by construction. A systematic 5.9% sample of production
# (2,000 contracts, 2026-08-01) found 99.80% in NPC stations and 0.20% in
# player-owned Upwell structures, whose /universe/structures/ route needs a token
# carrying esi-universe.read_structures.v1 and 403s for structures the character
# cannot reach. Ingestion holds no user tokens, so structures stay NULL. That
# ratio is a property of The Forge; structure-heavy regions would shift it hard.


async def test_npc_station_contract_gets_its_solar_system(db_session: AsyncSession):
    """A contract in an NPC station stores the system id ESI reports for that station."""
    service = _make_service()
    service.esi_client.get_universe_station = AsyncMock(
        return_value={"station_id": 60003760, "system_id": 30000142, "name": "Jita IV - Moon 4"}
    )
    contract = dict(_ship_contract_dict(910101))
    contract["start_location_id"] = 60003760
    contract["type"] = "courier"  # skip the item-fetch loop entirely

    await service._process_contracts(db_session, [contract])

    row = (
        await db_session.execute(select(Contract).where(Contract.contract_id == 910101))
    ).scalar_one()
    assert row.start_location_system_id == 30000142
    service.esi_client.get_universe_station.assert_awaited_once_with(60003760)


async def test_player_structure_contract_keeps_a_null_system_and_is_never_requested(
    db_session: AsyncSession,
):
    """An Upwell structure resolves to nothing AND costs no ESI request.

    /universe/structures/ requires an ACL-scoped token, so a tokenless lookup can only
    fail. Issuing it anyway would spend ESI error budget (100 errors/60s buys a 420)
    on a location that still could not be resolved — so the range gate must keep the
    request from being made at all, not merely swallow its failure.
    """
    service = _make_service()
    service.esi_client.get_universe_station = AsyncMock(
        return_value={"station_id": 0, "system_id": 30000142}
    )
    contract = dict(_ship_contract_dict(910102))
    contract["start_location_id"] = 1_035_466_617_946  # Upwell structure id
    contract["type"] = "courier"

    await service._process_contracts(db_session, [contract])

    row = (
        await db_session.execute(select(Contract).where(Contract.contract_id == 910102))
    ).scalar_one()
    assert row.start_location_system_id is None
    service.esi_client.get_universe_station.assert_not_awaited()


async def test_a_known_station_survives_an_esi_outage_and_is_not_refetched(
    db_session: AsyncSession,
):
    """Station→system is static, so an already-resolved pair is read back from the
    contracts table instead of ESI.

    Two properties in one, because they are the same mechanism: the lookup is skipped
    (steady state costs zero requests) and the stored system survives a total ESI
    failure. Without the read-back, the upsert — which copies every supplied column on
    conflict — would write NULL over every resolved system the moment
    /universe/stations/ went down, blanking the filter site-wide for a full cycle.
    """
    service = _make_service()
    service.esi_client.get_universe_station = AsyncMock(
        side_effect=RuntimeError("ESI is down")
    )
    # A prior run already resolved this station.
    seed = dict(_ship_contract_dict(910103))
    seed["start_location_id"] = 60008494
    seed["type"] = "courier"
    db_session.add(
        Contract(
            contract_id=910103,
            title="Seed",
            price=1,
            collateral=0,
            status="outstanding",
            type="courier",
            issuer_id=1,
            issuer_corporation_id=1,
            start_location_id=60008494,
            start_location_system_id=30002187,
            start_location_region_id=10000020,
            for_corporation=False,
            date_issued=datetime.now(timezone.utc) - timedelta(days=1),
            date_expired=datetime.now(timezone.utc) + timedelta(days=7),
        )
    )
    await db_session.flush()

    # A NEW contract in the SAME station, re-ingested alongside the existing one.
    fresh = dict(_ship_contract_dict(910104))
    fresh["start_location_id"] = 60008494
    fresh["type"] = "courier"

    await service._process_contracts(db_session, [seed, fresh])

    rows = (
        await db_session.execute(
            select(Contract).where(Contract.contract_id.in_([910103, 910104]))
        )
    ).scalars().all()
    assert {r.contract_id: r.start_location_system_id for r in rows} == {
        910103: 30002187,
        910104: 30002187,
    }
    service.esi_client.get_universe_station.assert_not_awaited()


async def test_station_resolution_failure_leaves_the_system_null_without_aborting(
    db_session: AsyncSession,
):
    """A failed station lookup degrades that one location to NULL; the run continues
    and the contract's other columns still persist. The row stays retryable because
    the next run finds no stored pair for that station and asks again."""
    service = _make_service()
    service.esi_client.get_universe_station = AsyncMock(
        side_effect=RuntimeError("ESI 500")
    )
    contract = dict(_ship_contract_dict(910105))
    contract["start_location_id"] = 60003760
    contract["type"] = "courier"

    await service._process_contracts(db_session, [contract])

    row = (
        await db_session.execute(select(Contract).where(Contract.contract_id == 910105))
    ).scalar_one()
    assert row.start_location_system_id is None
    assert row.start_location_region_id == 10000002  # the rest of the row survived
    service.esi_client.get_universe_station.assert_awaited_once_with(60003760)


async def test_a_station_payload_without_a_system_id_resolves_to_null(
    db_session: AsyncSession,
):
    """ESI omits fields rather than sending falsy ones (ESI-3), so a payload missing
    `system_id` must read as unresolved rather than as system 0. Note the STRUCTURE
    route names the same concept `solar_system_id` — a future structure path copying
    this code path unchanged would silently read None for every structure."""
    service = _make_service()
    service.esi_client.get_universe_station = AsyncMock(
        return_value={"station_id": 60003760, "name": "Jita IV - Moon 4"}
    )
    contract = dict(_ship_contract_dict(910106))
    contract["start_location_id"] = 60003760
    contract["type"] = "courier"

    await service._process_contracts(db_session, [contract])

    row = (
        await db_session.execute(select(Contract).where(Contract.contract_id == 910106))
    ).scalar_one()
    assert row.start_location_system_id is None


async def test_station_id_range_boundaries_decide_what_is_requested(
    db_session: AsyncSession,
):
    """Pin BOTH edges of the NPC-station id range so an off-by-one cannot slip through.

    60,000,000 is the first station id and 63,999,999 the last; 59,999,999 and
    64,000,000 are outside and must never be requested.
    """
    service = _make_service()

    async def system_for(station_id: int) -> dict:
        return {"station_id": station_id, "system_id": 30000142}

    service.esi_client.get_universe_station = AsyncMock(side_effect=system_for)

    contracts = []
    for index, location_id in enumerate(
        (59_999_999, 60_000_000, 63_999_999, 64_000_000)
    ):
        contract = dict(_ship_contract_dict(910110 + index))
        contract["start_location_id"] = location_id
        contract["type"] = "courier"
        contracts.append(contract)

    await service._process_contracts(db_session, contracts)

    requested = {
        call.args[0] for call in service.esi_client.get_universe_station.await_args_list
    }
    assert requested == {60_000_000, 63_999_999}


# --- End-location system resolution -----------------------------------------
#
# A courier contract's destination is a location id exactly like its origin, and
# /universe/stations/ answers for it on the same terms. Both halves of the
# station path — the fetch set and the contracts-table read-back — carry the end
# role alongside the start role, because the upsert copies every supplied column
# on conflict: a read-back that covered only starts would let one ESI outage
# write NULL over every known destination corpus-wide.


async def test_courier_end_station_resolves_to_its_solar_system(db_session: AsyncSession):
    """end_location_system_id persists via the same station path as starts."""
    service = _make_service()
    contract = _ship_contract_dict(811)
    contract["type"] = "courier"  # skips item fetching entirely
    contract["end_location_id"] = 60008494
    service.esi_client.get_universe_station = AsyncMock(
        side_effect=lambda sid: {
            60003760: {"system_id": 30000142},
            60008494: {"system_id": 30002187},
        }[sid]
    )

    await service._process_contracts(db_session, [contract])

    row = (
        await db_session.execute(select(Contract).where(Contract.contract_id == 811))
    ).scalar_one()
    assert row.start_location_system_id == 30000142
    assert row.end_location_system_id == 30002187


async def test_structure_end_location_keeps_null_system_and_is_never_requested(
    db_session: AsyncSession,
):
    """Player-structure destinations stay NULL and never spend ESI error budget."""
    service = _make_service()
    contract = _ship_contract_dict(812)
    contract["type"] = "courier"
    contract["end_location_id"] = 1_040_000_000_000  # Upwell structure id range
    calls = []
    service.esi_client.get_universe_station = AsyncMock(
        side_effect=lambda sid: calls.append(sid) or {"system_id": 30000142}
    )

    await service._process_contracts(db_session, [contract])

    row = (
        await db_session.execute(select(Contract).where(Contract.contract_id == 812))
    ).scalar_one()
    assert row.end_location_system_id is None
    assert 1_040_000_000_000 not in calls


async def test_a_known_end_station_survives_an_esi_outage(db_session: AsyncSession):
    """The DB read-back covers END pairs too — without it, an outage run would
    re-resolve from scratch, get nothing, and bulk_upsert would write NULL over
    every known destination (the start-side hazard, end-column edition)."""
    service = _make_service()
    first = _ship_contract_dict(813)
    first["type"] = "courier"
    first["end_location_id"] = 60008494
    service.esi_client.get_universe_station = AsyncMock(
        side_effect=lambda sid: {
            60003760: {"system_id": 30000142},
            60008494: {"system_id": 30002187},
        }[sid]
    )
    await service._process_contracts(db_session, [first])

    # Second sighting: ESI down for stations. The pair must come from the table.
    service.esi_client.get_universe_station = AsyncMock(side_effect=Exception("ESI down"))
    again = _ship_contract_dict(813)
    again["type"] = "courier"
    again["end_location_id"] = 60008494
    await service._process_contracts(db_session, [again])

    row = (
        await db_session.execute(select(Contract).where(Contract.contract_id == 813))
    ).scalar_one()
    assert row.end_location_system_id == 30002187


async def test_resolved_names_survive_a_degraded_name_resolution_run(
    db_session: AsyncSession,
):
    """A transient /universe/names failure makes resolve_ids_to_names return a
    partial map (per-chunk errors are swallowed in the ESI client). Re-sighted
    contracts must keep their previously-resolved display names rather than
    having them blanked until the next successful run (F008 decision log D10)."""
    service = _make_service()
    first = _ship_contract_dict(814)
    first["type"] = "courier"  # skips item fetching; carries both location columns
    first["end_location_id"] = 60008494
    first["issuer_id"] = 91000001
    first["issuer_corporation_id"] = 98000001
    service.esi_client.resolve_ids_to_names = AsyncMock(
        return_value={
            60003760: "Jita IV - Moon 4 - Caldari Navy Assembly Plant",
            60008494: "Amarr VIII (Oris) - Emperor Family Academy",
            91000001: "Resolved Pilot",
            98000001: "Resolved Corp",
        }
    )
    service.esi_client.get_universe_station = AsyncMock(
        side_effect=lambda sid: {
            60003760: {"system_id": 30000142},
            60008494: {"system_id": 30002187},
        }[sid]
    )
    await service._process_contracts(db_session, [first])

    # Second sighting: the names outage yields an empty map for every ID.
    service.esi_client.resolve_ids_to_names = AsyncMock(return_value={})
    again = dict(first)
    await service._process_contracts(db_session, [again])

    row = (
        await db_session.execute(select(Contract).where(Contract.contract_id == 814))
    ).scalar_one()
    assert row.start_location_name == "Jita IV - Moon 4 - Caldari Navy Assembly Plant"
    assert row.end_location_name == "Amarr VIII (Oris) - Emperor Family Academy"
    assert row.issuer_name == "Resolved Pilot"
    assert row.issuer_corporation_name == "Resolved Corp"


async def test_a_renamed_entity_updates_on_the_next_successful_run(
    db_session: AsyncSession,
):
    """Preserving names on NULL must not freeze them: a successful resolution
    carrying a genuinely changed name still overwrites the stored one."""
    service = _make_service()
    contract = _ship_contract_dict(815)
    contract["issuer_corporation_id"] = 98000001
    service.esi_client.resolve_ids_to_names = AsyncMock(
        return_value={
            60003760: "Jita IV - Moon 4 - Caldari Navy Assembly Plant",
            1: "Resolved Pilot",
            98000001: "Old Corp Name",
        }
    )
    await service._process_contracts(db_session, [contract])

    service.esi_client.resolve_ids_to_names = AsyncMock(
        return_value={
            60003760: "Jita IV - Moon 4 - Caldari Navy Assembly Plant",
            1: "Resolved Pilot",
            98000001: "New Corp Name",
        }
    )
    await service._process_contracts(db_session, [dict(contract)])

    row = (
        await db_session.execute(select(Contract).where(Contract.contract_id == 815))
    ).scalar_one()
    assert row.issuer_corporation_name == "New Corp Name"
