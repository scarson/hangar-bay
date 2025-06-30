import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from datetime import datetime

from fastapi_app.models import Contract, ContractItem

# Mark all tests in this file for VCR, our custom live marker, and asyncio
pytestmark = [
    pytest.mark.vcr,
    pytest.mark.esi_live,
    pytest.mark.asyncio,
]


async def test_get_contracts_live(client: AsyncClient):
    """
    Tests the /contracts/ endpoint against a recorded live ESI response.
    This test will fail if the ESI API changes its contract data structure in a
    way that breaks our models.
    """
    response = await client.get("/contracts/")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, dict)
    assert "items" in data
    assert "total" in data
    assert "page" in data
    assert "size" in data
    assert isinstance(data["items"], list)
    if data["items"]:
        first_contract = data["items"][0]
        assert "contract_id" in first_contract
        assert "issuer_id" in first_contract
        assert "status" in first_contract
        assert "contract_type" in first_contract


@pytest.mark.asyncio
async def test_filter_contracts_by_search(client: AsyncClient, db_session: AsyncSession):
    """Tests text search against contract title and item name."""
    # Arrange
    contract1 = Contract(contract_id=1, title="My Special Contract", price=100, collateral=0.0, is_ship_contract=True, contract_type="item_exchange", status="outstanding", issuer_id=1, issuer_corporation_id=1, for_corporation=False, date_issued=datetime.fromisoformat("2025-01-01T00:00:00Z"), date_expired=datetime.fromisoformat("2025-01-02T00:00:00Z"), start_location_id=60003760)
    item1 = ContractItem(contract_id=1, type_id=101, type_name="Test Ship Alpha", quantity=1, is_included=True, is_singleton=True)
    
    contract2 = Contract(contract_id=2, title="Another Deal", price=200, collateral=0.0, is_ship_contract=True, contract_type="item_exchange", status="outstanding", issuer_id=1, issuer_corporation_id=1, for_corporation=False, date_issued=datetime.fromisoformat("2025-01-01T00:00:00Z"), date_expired=datetime.fromisoformat("2025-01-02T00:00:00Z"), start_location_id=60003760)
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
        Contract(contract_id=1, title="C1", price=50.0, collateral=0.0, is_ship_contract=True, contract_type="item_exchange", status="outstanding", issuer_id=1, issuer_corporation_id=1, for_corporation=False, date_issued=datetime.fromisoformat("2025-01-01T00:00:00Z"), date_expired=datetime.fromisoformat("2025-01-02T00:00:00Z"), start_location_id=60003760),
        Contract(contract_id=2, title="C2", price=100.0, collateral=0.0, is_ship_contract=True, contract_type="item_exchange", status="outstanding", issuer_id=1, issuer_corporation_id=1, for_corporation=False, date_issued=datetime.fromisoformat("2025-01-01T00:00:00Z"), date_expired=datetime.fromisoformat("2025-01-02T00:00:00Z"), start_location_id=60003760),
        Contract(contract_id=3, title="C3", price=150.0, collateral=0.0, is_ship_contract=True, contract_type="item_exchange", status="outstanding", issuer_id=1, issuer_corporation_id=1, for_corporation=False, date_issued=datetime.fromisoformat("2025-01-01T00:00:00Z"), date_expired=datetime.fromisoformat("2025-01-02T00:00:00Z"), start_location_id=60003760),
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
    contract1 = Contract(contract_id=1, title="Z-Contract", price=2000.0, collateral=0.0, is_ship_contract=True, contract_type="item_exchange", status="outstanding", issuer_id=1, issuer_corporation_id=1, for_corporation=False, date_issued=datetime.fromisoformat("2025-01-01T00:00:00Z"), date_expired=datetime.fromisoformat("2025-01-02T00:00:00Z"), start_location_id=60003760)
    item1 = ContractItem(contract_id=1, type_id=102, type_name="Zephyr Frigate", quantity=1, is_included=True, is_singleton=True)

    contract2 = Contract(contract_id=2, title="A-Contract", price=1000.0, collateral=0.0, is_ship_contract=True, contract_type="item_exchange", status="outstanding", issuer_id=1, issuer_corporation_id=1, for_corporation=False, date_issued=datetime.fromisoformat("2025-01-01T00:00:00Z"), date_expired=datetime.fromisoformat("2025-01-02T00:00:00Z"), start_location_id=60003760)
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
    contracts = [Contract(contract_id=i, title=f"C{i}", price=i*10, collateral=0.0, is_ship_contract=True, contract_type="item_exchange", status="outstanding", issuer_id=1, issuer_corporation_id=1, for_corporation=False, date_issued=datetime.fromisoformat("2025-01-01T00:00:00Z"), date_expired=datetime.fromisoformat("2025-01-02T00:00:00Z"), start_location_id=60003760) for i in range(1, 11)]
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
