# --- Service-Level Test Setup ---
#
# The tests in this file focus on the business logic within the service layer.
# They follow patterns from `design/fastapi/guides/09-testing-strategies.md`.
#
# Key Fixture:
#
# - `db_session: AsyncSession`: Provided by `conftest.py`, this fixture gives
#   each test function a clean, isolated, PostgreSQL test-database session (the dedicated `hangar_bay_test` DB via `DATABASE_URL_TESTS`).
#   It handles the creation and teardown of the database schema, ensuring
#   tests do not interfere with each other and can run in parallel safely.
#
# Testing Approach:
# These tests call the service functions (e.g., `get_contracts`) directly,
# passing the `db_session` fixture to them. This allows for focused testing
# of data manipulation and business logic without the overhead of the HTTP
# request/response cycle.
#
# Data Persistence in Tests:
# To save data to the database within a test, use `await db_session.flush()`.
# Do NOT use `await db_session.commit()`, as the fixture manages the
# transaction lifecycle.

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from datetime import datetime, timedelta, timezone
from fastapi_app.models.contracts import Contract, ContractItem
from fastapi_app.schemas.contracts import (
    ContractFilters,
    SortableContractFields,
    SortDirection,
)
import fastapi_app.services.contract_service as contract_service
from fastapi_app.services.contract_service import get_contracts

# Mark all tests in this file as asyncio
pytestmark = pytest.mark.asyncio





async def test_search_by_ship_name(db_session: AsyncSession, setup_contracts):
    """Test searching for contracts by a specific ship name."""
    filters = ContractFilters(search="Tristan")

    result = await get_contracts(db=db_session, filters=filters)

    assert result.total == 2
    assert len(result.items) == 2
    # Verify that both contracts containing a Tristan are returned
    contract_ids = {c.contract_id for c in result.items}
    assert 101 in contract_ids
    assert 103 in contract_ids


async def test_search_by_contract_title(db_session: AsyncSession, setup_contracts):
    """Test searching for contracts by a word in the title."""
    filters = ContractFilters(search="Starter")

    result = await get_contracts(db=db_session, filters=filters)

    assert result.total == 1
    assert result.items[0].contract_id == 103


async def test_filter_by_min_price(db_session: AsyncSession, setup_contracts):
    """Test filtering contracts by a minimum price."""
    filters = ContractFilters(min_price=10_000_000)

    result = await get_contracts(db=db_session, filters=filters)

    assert result.total == 1
    assert result.items[0].contract_id == 104


async def test_filter_by_max_price(db_session: AsyncSession, setup_contracts):
    """Test filtering contracts by a maximum price."""
    filters = ContractFilters(max_price=1_500_000)

    result = await get_contracts(db=db_session, filters=filters)

    assert result.total == 1
    assert result.items[0].contract_id == 101


async def test_filter_by_price_and_collateral(db_session: AsyncSession, setup_contracts):
    """Test filtering with a combination of price and collateral."""
    filters = ContractFilters(min_price=4_000_000, max_collateral=1_000_000)

    result = await get_contracts(db=db_session, filters=filters)

    assert result.total == 1
    assert result.items[0].contract_id == 102


async def test_filter_by_type_id(db_session: AsyncSession, setup_contracts):
    """Test filtering by a specific ship type ID."""
    # Venture's type_id is 17480
    filters = ContractFilters(type_ids=[17480])

    result = await get_contracts(db=db_session, filters=filters)

    assert result.total == 1
    assert result.items[0].contract_id == 103


async def test_filter_by_region_id(db_session: AsyncSession, setup_contracts):
    """Test filtering by a specific region ID."""
    # Region ID for the "Mining Starter Pack"
    filters = ContractFilters(region_ids=[10000020])

    result = await get_contracts(db=db_session, filters=filters)

    assert result.total == 1
    assert result.items[0].contract_id == 103


async def test_filter_by_is_bpc(db_session: AsyncSession, setup_contracts):
    """Test filtering for contracts that are blueprint copies."""
    filters = ContractFilters(is_bpc=True)

    result = await get_contracts(db=db_session, filters=filters)

    assert result.total == 1
    assert result.items[0].contract_id == 102
    assert result.items[0].items[0].is_blueprint_copy is True


async def test_sorting_by_price_asc(db_session: AsyncSession, setup_contracts):
    """Test sorting contracts by price in ascending order."""
    filters = ContractFilters(sort_by=SortableContractFields.price, sort_direction=SortDirection.asc)

    result = await get_contracts(db=db_session, filters=filters)

    assert result.total == 4
    prices = [c.price for c in result.items]
    assert prices == [1_000_000, 2_500_000, 5_000_000, 200_000_000]


async def test_pagination(db_session: AsyncSession, setup_contracts):
    """Test the pagination functionality."""
    # Get the second page, with 2 items per page
    filters = ContractFilters(page=2, size=2, sort_by=SortableContractFields.price, sort_direction=SortDirection.asc)

    result = await get_contracts(db=db_session, filters=filters)

    assert result.total == 4
    assert result.page == 2
    assert result.size == 2
    assert len(result.items) == 2
    # The second page should have the 3rd and 4th items from the sorted list
    contract_ids = {c.contract_id for c in result.items}
    assert 102 in contract_ids  # price 5,000,000
    assert 104 in contract_ids  # price 200,000,000


async def test_complex_query(db_session: AsyncSession, setup_contracts):
    """Test a complex query with multiple filters, sorting, and pagination."""
    # Search for "Tristan", in region 10000002, max price 2_000_000, sorted by price asc
    filters = ContractFilters(
        search="Tristan",
        region_ids=[10000002],
        max_price=2_000_000,
        sort_by=SortableContractFields.price,
        sort_direction=SortDirection.asc
    )

    result = await get_contracts(db=db_session, filters=filters)

    # Only contract 101 should match all these criteria
    assert result.total == 1
    assert len(result.items) == 1
    assert result.items[0].contract_id == 101


async def test_zero_results_returns_empty_page(db_session: AsyncSession, setup_contracts):
    """No matching contracts short-circuits to an empty page that still echoes page/size."""
    filters = ContractFilters(search="no-such-ship-name-anywhere", page=1, size=10)

    result = await get_contracts(db_session, filters)

    assert result.total == 0
    assert result.items == []
    assert result.page == 1
    assert result.size == 10


async def test_unmapped_sort_falls_back_to_date_issued(db_session: AsyncSession):
    """An unmapped sort key falls back to date_issued with the default desc direction.

    sort_by is NON-optional in the schema (default SortableContractFields.date_issued,
    sort_direction default desc), so SORT_MAP.get(filters.sort_by) can only return None
    if validation is bypassed — the fallback branch is defensive. It is characterized via
    model_construct, which skips validation while still populating declared defaults, so
    only the overrides need passing.

    TEST-3: setup_contracts is deliberately NOT used here — its date_issued values are
    independent datetime.now() calls (nondeterministic, possibly equal). These three
    contracts carry fixed, strictly distinct date_issued values in a region id no other
    fixture uses.
    """
    region_id = 99999901
    base_date = datetime(2026, 7, 1, tzinfo=timezone.utc)
    db_session.add_all([
        Contract(
            contract_id=940000 + offset,
            title=f"Sort Fallback {offset}",
            price=1_000_000,
            collateral=0,
            status="outstanding",
            type="item_exchange",
            issuer_id=940,
            issuer_corporation_id=940,
            start_location_id=60003760,
            start_location_system_id=30000142,
            start_location_region_id=region_id,
            for_corporation=False,
            date_issued=base_date + timedelta(days=offset - 1),
            date_expired=base_date + timedelta(days=30),
        )
        for offset in (1, 2, 3)
    ])
    await db_session.flush()

    filters = ContractFilters.model_construct(sort_by=None, region_ids=[region_id])

    result = await get_contracts(db_session, filters)

    # Fallback = Contract.date_issued, default direction desc, contract_id tiebreak:
    assert [item.contract_id for item in result.items] == [940003, 940002, 940001]


async def test_db_error_logs_failure_and_reraises(
    db_session: AsyncSession, setup_contracts, monkeypatch
):
    """A query failure logs a failure key event and the original exception propagates."""
    events = []
    real_log_key_event = contract_service.log_key_event

    def recording_log_key_event(*args, **kwargs):
        events.append(kwargs)
        return real_log_key_event(*args, **kwargs)

    monkeypatch.setattr(contract_service, "log_key_event", recording_log_key_event)

    async def boom(*args, **kwargs):
        raise RuntimeError("simulated db failure")

    monkeypatch.setattr(db_session, "execute", boom)

    filters = ContractFilters(page=1, size=10)
    with pytest.raises(RuntimeError, match="simulated db failure"):
        await get_contracts(db_session, filters)

    failure_events = [e for e in events if e.get("success") is False]
    assert len(failure_events) == 1
    assert "simulated db failure" in failure_events[0]["error_message"]


async def test_joined_pagination_tiebreaks_equal_sort_keys_by_contract_id(
    db_session: AsyncSession, setup_contracts
):
    """Equal sort keys under the item join split deterministically on contract_id ASC.

    SQLA-1 net: with the item join active (search filter) and EQUAL sort keys, pages must
    split on the contract_id tiebreaker with no contract skipped or repeated across the
    boundary (TEST-4).
    """
    db_session.add_all([
        Contract(
            contract_id=contract_id,
            title="Tiebreak Listing",
            price=500.0,
            collateral=0,
            status="outstanding",
            type="item_exchange",
            issuer_id=930,
            issuer_corporation_id=930,
            start_location_id=60003760,
            start_location_system_id=30000142,
            start_location_region_id=10000002,
            for_corporation=False,
            date_issued=datetime.now(timezone.utc),
            date_expired=datetime.now(timezone.utc) + timedelta(days=7),
            items=[
                ContractItem(
                    record_id=record_id,
                    type_id=587,
                    type_name="Tiebreakship",
                    quantity=1,
                    is_included=True,
                    is_singleton=False,
                    is_blueprint_copy=False,
                )
            ],
        )
        for contract_id, record_id in ((930001, 9300011), (930002, 9300021))
    ])
    await db_session.flush()

    filters_p1 = ContractFilters(search="tiebreakship", sort_by=SortableContractFields.price,
                                 sort_direction=SortDirection.asc, page=1, size=1)
    filters_p2 = filters_p1.model_copy(update={"page": 2})

    page1 = await get_contracts(db_session, filters_p1)
    page2 = await get_contracts(db_session, filters_p2)

    assert page1.total == 2 and page2.total == 2
    assert [c.contract_id for c in page1.items] == [930001]
    assert [c.contract_id for c in page2.items] == [930002]
