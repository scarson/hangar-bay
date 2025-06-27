import pytest
from httpx import AsyncClient

# Mark all tests in this file for VCR, our custom live marker, and asyncio
pytestmark = [
    pytest.mark.vcr,
    pytest.mark.esi_live,
    pytest.mark.asyncio,
]


async def test_get_contracts_live(client: AsyncClient):
    """
    Tests the /api/v1/contracts endpoint against a recorded live ESI response.
    This test will fail if the ESI API changes its contract data structure in a
    way that breaks our models.
    """
    # Act: Make a request to the endpoint. On the first run, this will hit the
    # live ESI API and record the response in a "cassette" file.
    # On subsequent runs, it will replay the response from the cassette.
    response = await client.get("/api/v1/contracts/")

    # Assert: Check for a successful response
    assert response.status_code == 200

    # Assert: Check the paginated response structure
    data = response.json()
    assert isinstance(data, dict)
    assert "items" in data
    assert "total" in data
    assert "page" in data
    assert "size" in data
    assert isinstance(data["items"], list)

    # Assert: If contracts are returned, check the structure of the first one
    # This provides a basic contract validation against the live data.
    if data["items"]:
        first_contract = data["items"][0]
        assert "contract_id" in first_contract
        assert "issuer_id" in first_contract
        assert "status" in first_contract
        assert "type" in first_contract
