import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from datetime import datetime, timedelta, timezone
from fastapi_app.models.contracts import Contract, ContractItem
from fastapi_app.schemas.contracts import ContractFilters, ContractSortBy, SortDirection
from fastapi_app.services.contract_service import get_contracts

# Mark all tests in this file as asyncio
pytestmark = pytest.mark.asyncio


@pytest.fixture(scope="function")
async def setup_contracts(db_session: AsyncSession):
    """Fixture to populate the DB with a diverse set of contracts for testing."""
    contracts_data = [
        # Contract 1: Standard ship sale (Tristan)
        Contract(
            contract_id=101, title="Tristan for Sale", price=1_000_000, collateral=0, status="outstanding", contract_type="item_exchange",
            issuer_id=1, issuer_corporation_id=101, start_location_id=60003760, start_location_system_id=30000142, start_location_region_id=10000002,
            for_corporation=False, date_issued=datetime.now(timezone.utc), date_expired=datetime.now(timezone.utc) + timedelta(days=7),
            items=[
                ContractItem(record_id=1011, type_id=587, type_name="Tristan", quantity=1, is_included=True, is_singleton=False, is_blueprint_copy=False)
            ]
        ),
        # Contract 2: BPC auction (Caracal)
        Contract(
            contract_id=102, title="Caracal BPC Auction", price=5_000_000, collateral=1_000_000, status="outstanding", contract_type="auction",
            issuer_id=2, issuer_corporation_id=102, start_location_id=60003760, start_location_system_id=30000142, start_location_region_id=10000002,
            for_corporation=True, date_issued=datetime.now(timezone.utc), date_expired=datetime.now(timezone.utc) + timedelta(days=3),
            items=[
                ContractItem(record_id=1021, type_id=621, type_name="Caracal Blueprint", quantity=1, is_included=True, is_singleton=True, is_blueprint_copy=True)
            ]
        ),
        # Contract 3: Multi-item contract in a different region (Venture, Tristan)
        Contract(
            contract_id=103, title="Mining Starter Pack", price=2_500_000, collateral=500_000, status="outstanding", contract_type="item_exchange",
            issuer_id=3, issuer_corporation_id=103, start_location_id=60008494, start_location_system_id=30002187, start_location_region_id=10000020,
            for_corporation=False, date_issued=datetime.now(timezone.utc), date_expired=datetime.now(timezone.utc) + timedelta(days=14),
            items=[
                ContractItem(record_id=1031, type_id=17480, type_name="Venture", quantity=1, is_included=True, is_singleton=False, is_blueprint_copy=False),
                ContractItem(record_id=1032, type_id=587, type_name="Tristan", quantity=1, is_included=True, is_singleton=False, is_blueprint_copy=False)
            ]
        ),
        # Contract 4: High-price, high-collateral contract (Rokh)
        Contract(
            contract_id=104, title="Battleship Rokh", price=200_000_000, collateral=100_000_000, status="outstanding", contract_type="item_exchange",
            issuer_id=4, issuer_corporation_id=104, start_location_id=60003760, start_location_system_id=30000142, start_location_region_id=10000002,
            for_corporation=False, date_issued=datetime.now(timezone.utc), date_expired=datetime.now(timezone.utc) + timedelta(days=7),
            items=[
                ContractItem(record_id=1041, type_id=24698, type_name="Rokh", quantity=1, is_included=True, is_singleton=False, is_blueprint_copy=False)
            ]
        ),
    ]
    db_session.add_all(contracts_data)
    await db_session.commit()
    return contracts_data


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
    filters = ContractFilters(sort_by=ContractSortBy.price, sort_direction=SortDirection.asc)

    result = await get_contracts(db=db_session, filters=filters)

    assert result.total == 4
    prices = [c.price for c in result.items]
    assert prices == [1_000_000, 2_500_000, 5_000_000, 200_000_000]


async def test_pagination(db_session: AsyncSession, setup_contracts):
    """Test the pagination functionality."""
    # Get the second page, with 2 items per page
    filters = ContractFilters(page=2, size=2, sort_by=ContractSortBy.price, sort_direction=SortDirection.asc)

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
        sort_by=ContractSortBy.price,
        sort_direction=SortDirection.asc
    )

    result = await get_contracts(db=db_session, filters=filters)

    # Only contract 101 should match all these criteria
    assert result.total == 1
    assert len(result.items) == 1
    assert result.items[0].contract_id == 101
