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


# --- /metrics gate + /cache-test removal (M4 Tasks 3.5/3.6) ---

from pydantic import SecretStr  # noqa: E402

from fastapi_app.core.config import settings as _settings  # noqa: E402


async def test_metrics_open_when_no_token_configured(client: AsyncClient):
    assert (await client.get("/metrics")).status_code == 200


async def test_metrics_401_without_bearer_when_token_set(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(_settings, "METRICS_TOKEN", SecretStr("test-metrics-token"))
    assert (await client.get("/metrics")).status_code == 401


async def test_metrics_200_with_correct_bearer(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(_settings, "METRICS_TOKEN", SecretStr("test-metrics-token"))
    r = await client.get("/metrics", headers={"Authorization": "Bearer test-metrics-token"})
    assert r.status_code == 200
    assert b"hangar_bay" in r.content


async def test_cache_test_endpoint_is_gone(client: AsyncClient):
    assert (await client.get("/cache-test")).status_code == 404
