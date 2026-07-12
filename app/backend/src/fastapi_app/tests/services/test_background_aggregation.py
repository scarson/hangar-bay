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

from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from fastapi_app.models.contracts import Contract
from fastapi_app.services.background_aggregation import ContractAggregationService

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
