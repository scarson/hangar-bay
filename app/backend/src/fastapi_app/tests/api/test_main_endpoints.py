import pytest
from httpx import AsyncClient

# Mark all tests in this file as asyncio
pytestmark = pytest.mark.asyncio


async def test_health_check(client: AsyncClient):
    """
    Tests that the /health endpoint is reachable and returns the correct response.
    """
    # Act
    response = await client.get("/health")

    # Assert
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
