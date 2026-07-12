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
