# --- Test Setup and Fixture Philosophy ---
#
# The tests in this file follow a specific pattern to ensure reliability and
# consistency, as defined in `design/fastapi/guides/09-testing-strategies.md`.
#
# Key Fixtures:
#
# - `client: AsyncClient`: Provided by `conftest.py`, this is an HTTPX client
#   that makes requests to a *real* instance of our FastAPI application. This
#   ensures we are testing against the actual application code, including all
#   routers and dependencies.
#
# - `db_session: AsyncSession`: Also from `conftest.py`, this fixture provides
#   a clean, isolated, PostgreSQL test-database session (the dedicated `hangar_bay_test` DB via `DATABASE_URL_TESTS`) for each individual
#   test function. It handles the creation and teardown of the database schema,
#   ensuring tests do not interfere with each other.
#
# How They Work Together:
# The `client` fixture uses the `test_app` fixture, which programmatically
# overrides the `get_db` dependency to point to the `db_session` for that
# specific test. This gives us the best of both worlds: testing the real app
# logic against a safe, temporary database.
#
# Data Persistence in Tests:
# To save data to the database within a test, use `await db_session.flush()`.
# Do NOT use `await db_session.commit()`, as the fixture manages the
# transaction lifecycle.

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from datetime import datetime, timedelta, timezone

from fastapi_app.models import Contract, ContractItem

# Fixture contracts must stay LIVE. The contracts list endpoint excludes anything past
# date_expired, so a hardcoded past expiry makes a fixture invisible to the very endpoint
# these tests exercise, and the failure reads as a baffling total==0 (TEST-17).
# Keep date_issued fixed where ordering is asserted; only the expiry tracks the clock.
LIVE_EXPIRY = datetime.now(timezone.utc) + timedelta(days=7)

# Asyncio only. These tests drive our OWN endpoints and database through ASGITransport, so
# `pytest.mark.vcr` must never be applied here: vcrpy intercepts below httpx and ahead of
# ASGITransport, which turns every request into a cassette replay that asserts nothing about
# the application (TEST-14). Per `design/fastapi/guides/09-testing-strategies.md` §5, the
# vcr/esi_live pair belongs only on tests of the client-to-ESI interaction — never on tests
# of our own database or internal endpoints. `tests/api/conftest.py` enforces this at
# collection time.
pytestmark = [pytest.mark.asyncio]


async def test_list_contracts_returns_paginated_envelope(
    client: AsyncClient, db_session: AsyncSession
):
    """The list endpoint wraps results in a page envelope carrying the core contract fields."""
    # Arrange
    db_session.add_all([
        Contract(contract_id=1, title="Envelope Probe", price=100, collateral=0.0, is_ship_contract=True, type="item_exchange", status="outstanding", issuer_id=7, issuer_corporation_id=9, for_corporation=False, date_issued=datetime.fromisoformat("2025-01-01T00:00:00Z"), date_expired=LIVE_EXPIRY, start_location_id=60003760),
        ContractItem(contract_id=1, type_id=101, type_name="Test Ship Alpha", quantity=1, is_included=True, is_singleton=True),
    ])
    await db_session.flush()

    # Act
    response = await client.get("/contracts/")

    # Assert
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, dict)
    assert data["total"] == 1
    assert data["page"] == 1
    assert data["size"] == 50
    assert isinstance(data["items"], list)

    # Unconditional on purpose: an `if data["items"]:` guard skips the entire point of the
    # test the moment the fixture stops reaching the endpoint, and reports that as a pass.
    first_contract = data["items"][0]
    assert first_contract["contract_id"] == 1
    assert first_contract["issuer_id"] == 7
    assert first_contract["title"] == "Envelope Probe"
    assert first_contract["type"] == "item_exchange"


@pytest.mark.asyncio
async def test_filter_contracts_by_search(client: AsyncClient, db_session: AsyncSession):
    """Tests text search against contract title and item name."""
    # Arrange
    contract1 = Contract(contract_id=1, title="My Special Contract", price=100, collateral=0.0, is_ship_contract=True, type="item_exchange", status="outstanding", issuer_id=1, issuer_corporation_id=1, for_corporation=False, date_issued=datetime.fromisoformat("2025-01-01T00:00:00Z"), date_expired=LIVE_EXPIRY, start_location_id=60003760)
    item1 = ContractItem(contract_id=1, type_id=101, type_name="Test Ship Alpha", quantity=1, is_included=True, is_singleton=True)
    
    contract2 = Contract(contract_id=2, title="Another Deal", price=200, collateral=0.0, is_ship_contract=True, type="item_exchange", status="outstanding", issuer_id=1, issuer_corporation_id=1, for_corporation=False, date_issued=datetime.fromisoformat("2025-01-01T00:00:00Z"), date_expired=LIVE_EXPIRY, start_location_id=60003760)
    item2 = ContractItem(contract_id=2, type_id=102, type_name="Test Ship Beta", quantity=1, is_included=True, is_singleton=True)
    
    db_session.add_all([contract1, item1, contract2, item2])
    await db_session.flush()  # Use flush to persist data within the ongoing transaction

    # Act: Search by contract title
    response = await client.get("/contracts/", params={"search": "Special"})
    data = response.json()
    assert response.status_code == 200
    assert data["total"] == 1
    assert data["items"][0]["contract_id"] == 1

    # Act: Search by item name
    response = await client.get("/contracts/", params={"search": "Beta"})
    data = response.json()
    assert response.status_code == 200
    assert data["total"] == 1
    assert data["items"][0]["contract_id"] == 2


@pytest.mark.asyncio
async def test_filter_contracts_by_price(client: AsyncClient, db_session: AsyncSession):
    """Tests filtering by min_price and max_price."""
    # Arrange
    contracts = [
        Contract(contract_id=1, title="C1", price=50.0, collateral=0.0, is_ship_contract=True, type="item_exchange", status="outstanding", issuer_id=1, issuer_corporation_id=1, for_corporation=False, date_issued=datetime.fromisoformat("2025-01-01T00:00:00Z"), date_expired=LIVE_EXPIRY, start_location_id=60003760),
        Contract(contract_id=2, title="C2", price=100.0, collateral=0.0, is_ship_contract=True, type="item_exchange", status="outstanding", issuer_id=1, issuer_corporation_id=1, for_corporation=False, date_issued=datetime.fromisoformat("2025-01-01T00:00:00Z"), date_expired=LIVE_EXPIRY, start_location_id=60003760),
        Contract(contract_id=3, title="C3", price=150.0, collateral=0.0, is_ship_contract=True, type="item_exchange", status="outstanding", issuer_id=1, issuer_corporation_id=1, for_corporation=False, date_issued=datetime.fromisoformat("2025-01-01T00:00:00Z"), date_expired=LIVE_EXPIRY, start_location_id=60003760),
    ]
    items = [ContractItem(contract_id=c.contract_id, type_id=101, type_name="Ship", quantity=1, is_included=True, is_singleton=True) for c in contracts]
    db_session.add_all(contracts + items)
    await db_session.flush()  # Use flush to persist data within the ongoing transaction

    # Act: Test min_price
    response = await client.get("/contracts/", params={"min_price": 99.0})
    data = response.json()
    assert response.status_code == 200
    assert data["total"] == 2
    assert {c["contract_id"] for c in data["items"]} == {2, 3}

    # Act: Test max_price
    response = await client.get("/contracts/", params={"max_price": 101.0})
    data = response.json()
    assert response.status_code == 200
    assert data["total"] == 2
    assert {c["contract_id"] for c in data["items"]} == {1, 2}

    # Act: Test both min and max price
    response = await client.get("/contracts/", params={"min_price": 75.0, "max_price": 125.0})
    data = response.json()
    assert response.status_code == 200
    assert data["total"] == 1
    assert data["items"][0]["contract_id"] == 2


@pytest.mark.asyncio
async def test_sort_contracts(client: AsyncClient, db_session: AsyncSession):
    """Tests sorting by different fields and directions."""
    # Arrange
    contract1 = Contract(contract_id=1, title="Z-Contract", price=2000.0, collateral=0.0, is_ship_contract=True, type="item_exchange", status="outstanding", issuer_id=1, issuer_corporation_id=1, for_corporation=False, date_issued=datetime.fromisoformat("2025-01-01T00:00:00Z"), date_expired=LIVE_EXPIRY, start_location_id=60003760)
    item1 = ContractItem(contract_id=1, type_id=102, type_name="Zephyr Frigate", quantity=1, is_included=True, is_singleton=True)

    contract2 = Contract(contract_id=2, title="A-Contract", price=1000.0, collateral=0.0, is_ship_contract=True, type="item_exchange", status="outstanding", issuer_id=1, issuer_corporation_id=1, for_corporation=False, date_issued=datetime.fromisoformat("2025-01-01T00:00:00Z"), date_expired=LIVE_EXPIRY, start_location_id=60003760)
    item2 = ContractItem(contract_id=2, type_id=101, type_name="Abyssal Cruiser", quantity=1, is_included=True, is_singleton=True)
    
    db_session.add_all([contract1, item1, contract2, item2])
    await db_session.flush()  # Use flush to persist data within the ongoing transaction

    # Act: Sort by price ascending
    response = await client.get("/contracts/", params={"sort_by": "price", "sort_direction": "asc"})
    data = response.json()
    assert response.status_code == 200
    assert [c["contract_id"] for c in data["items"]] == [2, 1]

    # Act: Sort by ship_name descending
    response = await client.get("/contracts/", params={"sort_by": "ship_name", "sort_direction": "desc"})
    data = response.json()
    assert response.status_code == 200
    assert [c["contract_id"] for c in data["items"]] == [1, 2]


@pytest.mark.asyncio
async def test_paginate_contracts(client: AsyncClient, db_session: AsyncSession):
    """Tests pagination logic."""
    # Arrange
    contracts = [Contract(contract_id=i, title=f"C{i}", price=i*10, collateral=0.0, is_ship_contract=True, type="item_exchange", status="outstanding", issuer_id=1, issuer_corporation_id=1, for_corporation=False, date_issued=datetime.fromisoformat("2025-01-01T00:00:00Z"), date_expired=LIVE_EXPIRY, start_location_id=60003760) for i in range(1, 11)]
    items = [ContractItem(contract_id=c.contract_id, type_id=101, type_name="Ship", quantity=1, is_included=True, is_singleton=True) for c in contracts]
    db_session.add_all(contracts + items)
    await db_session.flush()  # Use flush to persist data within the ongoing transaction

    # Act: Get page 2 with a size of 3
    response = await client.get("/contracts/", params={"page": 2, "size": 3, "sort_by": "price", "sort_direction": "asc"})
    data = response.json()

    # Assert
    assert response.status_code == 200
    assert data["total"] == 10
    assert data["page"] == 2
    assert data["size"] == 3
    assert [c["contract_id"] for c in data["items"]] == [4, 5, 6]
