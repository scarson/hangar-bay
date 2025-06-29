import pytest
from httpx import AsyncClient

# Mark all tests in this file as asyncio
pytestmark = pytest.mark.asyncio


async def test_sort_by_price_asc(
    client: AsyncClient, setup_contracts
):
    """Test sorting contracts by price in ascending order at the API level."""
    response = await client.get("/api/v1/contracts/?sort_by=price&sort_direction=asc")

    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) > 1
    # Check that the prices are sorted in ascending order
    prices = [item["price"] for item in data["items"]]
    assert prices == sorted(prices)


async def test_filter_by_is_bpc(client: AsyncClient, setup_contracts):
    """Test filtering for contracts that are blueprint copies."""
    response = await client.get("/api/v1/contracts/?is_bpc=true")

    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) > 0
    # Check that all returned contracts are BPCs
    for item in data["items"]:
        # A contract is a BPC contract if it has at least one item that is a BPC
        assert any(i.get("is_blueprint_copy") for i in item["items"])


async def test_filter_by_bpc_runs(client: AsyncClient, setup_contracts):
    """Test filtering BPCs by the number of runs."""
    # There is a BPC with 10 runs in the test data.
    response = await client.get("/api/v1/contracts/?is_bpc=true&min_runs=10&max_runs=10")

    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 1
    bpc_item = data["items"][0]["items"][0]
    assert bpc_item["raw_quantity"] == 10


async def test_complex_filter_api(client: AsyncClient, setup_contracts):
    """Test a complex query combining multiple filters at the API level."""
    # Search for a specific ship (Tristan), with a max price, sorted by price.
    params = {
        "search": "Tristan",
        "max_price": 1_500_000,
        "sort_by": "price",
        "sort_direction": "asc",
    }
    response = await client.get("/api/v1/contracts/", params=params)

    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 1
    assert data["items"][0]["items"][0]["type_name"] == "Tristan"
    assert data["items"][0]["price"] < 1_500_000
