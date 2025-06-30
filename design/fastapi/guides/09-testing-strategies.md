---
description: Outlines standard strategies and best practices for testing the FastAPI backend.
---

# Guide: FastAPI Testing Strategies

## 1. Core Philosophy: The Pragmatic Hybrid

Our testing strategy is a **Pragmatic Hybrid**, balancing the confidence of integration tests with the speed and isolation of unit tests.

-   **Primary Method: Integration Tests.** We test our application from the "outside-in." Tests interact with API endpoints using a real, but temporary, test database. This ensures all layers (API, services, database models) work together correctly. **All external network calls (e.g., to the ESI API) are mocked.**
-   **Secondary Method: Unit Tests.** Used for pure, isolated business logic, helper functions, Pydantic validators, or complex algorithms that have **no I/O dependencies** (no database, no network).
-   **Mandatory Method: Structural Tests.** Simple, fast tests that verify our classes correctly implement critical Python protocols (e.g., `AsyncContextManager`), preventing architectural bugs.

## 2. Core Tooling

-   **`pytest`**: The test runner.
-   **`pytest-asyncio`**: For testing `async` code.
-   **`httpx` & `TestClient`**: For making requests to our app in tests.
-   **`pytest-httpx`**: Crucial for mocking external HTTP requests made by our `ESIClient`.
-   **`pytest-vcr`**: Used for our specialized "Live ESI Contract Tests" to record and replay real API interactions.

## 3. The Test Environment: `conftest.py`

To ensure consistency, testability, and isolation, we use a root `conftest.py` file to define shared fixtures. This is the foundation of our test suite. The patterns defined here are **mandatory** to prevent subtle and difficult-to-debug concurrency errors.

**File Location:** `app/backend/src/fastapi_app/tests/conftest.py`

```python
# app/backend/src/fastapi_app/tests/conftest.py
import asyncio
from typing import AsyncGenerator, Generator

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import AsyncClient, ASGITransport
from pytest_httpx import HTTPXMock
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker, AsyncEngine

from fastapi_app.main import app as real_app
from fastapi_app.core.config import get_settings, Settings
from fastapi_app.db import get_db
from fastapi_app.models.base import Base

# --- Core Fixtures (No Global State) ---

### 3.1. The Authoritative Database Fixture (`db_session`)

The following `db_session` fixture is the **single, mandatory pattern** for all tests requiring database access. It solves critical concurrency issues by aligning the database engine's lifecycle with the test function's event loop.

```python
# app/backend/src/fastapi_app/tests/conftest.py
import asyncio
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from fastapi_app.core.config import get_settings
from fastapi_app.db.session import get_db
from fastapi_app.models.base import Base

# This is the DATABASE_URL for the test database
TEST_DATABASE_URL = get_settings().DATABASE_URL_TESTS

@pytest_asyncio.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Authoritative, function-scoped fixture for creating a clean, isolated database session for each test.

    This is the **only** approved pattern for database testing. It ensures that:
    1. The Engine and its connection pool are created within the same async context
       (event loop) as the test function, preventing `RuntimeError`.
    2. The entire database schema is dropped and recreated for each test, guaranteeing
       test isolation and preventing `IntegrityError` from dirty state.
    3. The session is yielded within a transaction that is rolled back, further
       ensuring isolation.
    """
    # The engine must be created within the fixture's async context to ensure it's
    # bound to the same event loop as the test.
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)

    # Drop all tables to ensure a clean state, in case a previous test failed
    # during teardown.
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    # Create all tables fresh for the test.
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # The sessionmaker and session are created within the same context.
    session_maker = async_sessionmaker(engine, expire_on_commit=False)
    async with session_maker.begin() as session:
        yield session

    # Teardown: dispose of the engine to close all connections.
    await engine.dispose()
```

#### **Rationale: Why Function-Scoped Engines are Mandatory**

-   **The Problem:** `pytest-asyncio` in `strict` mode creates a **new event loop for every single test function**. A SQLAlchemy `AsyncEngine` and its underlying connection pool are bound to the event loop in which they are created.
-   **The Anti-Pattern (What We Fixed):** A `session`-scoped engine is created once on a single event loop at the start of the test session. When an individual test runs on its *own, different* event loop and tries to get a connection, it results in a `RuntimeError: Task <Task ...> got Future <Future ...> attached to a different loop`.
-   **The Solution:** By creating the engine *inside* the `function`-scoped fixture, we guarantee the engine, its connections, and the test itself all share the exact same event loop, eliminating the error.

# --- Application and Client Fixtures ---

@pytest.fixture(scope="function")
def test_app(db_session: AsyncSession) -> FastAPI:
    """
    Creates a new app instance for each test, with the database dependency
    overridden to use the isolated test session.
    """
    real_app.dependency_overrides[get_db] = lambda: db_session
    return real_app

@pytest_asyncio.fixture(scope="function")
async def client(test_app: FastAPI) -> AsyncGenerator[AsyncClient, None]:
    """
    Provides an HTTPX client for making API requests to the test app.
    """
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

# --- Mocking Fixtures ---

@pytest.fixture(scope="function")
def httpx_mock() -> HTTPXMock:
    """
    Provided by pytest-httpx automatically. This explicit definition is for clarity.
    """
    from pytest_httpx import httpx_mock as mock
    return mock
```

### 3.1. Overriding Settings in Tests

A key advantage of the fixture-based setup is the ability to easily override configuration for specific tests. This is invaluable for testing feature flags, different API keys, or any behavior that depends on environment settings.

**Example: Testing a feature flag**

Imagine a feature is controlled by `settings.ENABLE_SPECIAL_FEATURE`.

```python
# in tests/api/test_special_feature.py

import pytest
from fastapi_app.core.config import Settings, get_settings

# By defining a fixture with the same name ('settings') in this module,
# pytest will use this local version instead of the one in conftest.py.
@pytest.fixture(scope="module")
def settings() -> Settings:
    """
    Overrides the default settings to enable our special feature for this module.
    """
    # Start with default settings and modify them
    default_settings = get_settings()
    # Assume Settings model has this attribute for the example
    # default_settings.ENABLE_SPECIAL_FEATURE = True
    return default_settings

# Now, any test in this file that uses a fixture depending on 'settings'
# (like 'client' or 'db_session') will run with this modified configuration.
async def test_special_feature_is_active(client: AsyncClient):
    # This test would check an endpoint affected by the feature flag
    pass
```

This pattern provides powerful control and isolation for configuration-dependent tests.

## 4. Writing an Integration Test: A Practical Example

This example demonstrates how to use our fixtures to write a clean, effective integration test for an API endpoint.

```python
# app/backend/src/fastapi_app/tests/api/test_contracts_api.py
import pytest
from httpx import AsyncClient
from pytest_httpx import HTTPXMock
from sqlalchemy.ext.asyncio import AsyncSession

from fastapi_app.models.contracts import Contract # Import your model for setup

# Mark all tests in this file as asyncio tests
pytestmark = pytest.mark.asyncio

async def test_list_public_contracts_empty(client: AsyncClient):
    """
    Test Case: No contracts exist in the database.
    Expected: API returns 200 OK with an empty list.
    """
    # Act: Make a request to the endpoint
    response = await client.get("/contracts/")

    # Assert: Check the response
    assert response.status_code == 200
    data = response.json()
    assert data["items"] == []
    assert data["total"] == 0

async def test_list_public_contracts_with_data(
    client: AsyncClient,
    db_session: AsyncSession,
    httpx_mock: HTTPXMock # Request this fixture when you need to mock ESI
):
    """
    Test Case: Contracts exist in the database.
    Expected: API returns 200 OK with the contract data.
    """
    # Arrange:
    # 1. Mock any external calls this endpoint might trigger (if any).
    #    For a simple list endpoint, this might not be needed.
    #    If it triggered an ESI call, you would do:
    #    httpx_mock.add_response(url="https://esi.evetech.net/...", json={"name": "Test"})

    # 2. Create test data directly in the test database.
    test_contract = Contract(
        contract_id=123,
        issuer_id=456,
        issuer_corporation_id=789,
        start_location_id=101112,
        type="item_exchange",
        status="outstanding",
        # ... fill in other required fields ...
    )
    db_session.add(test_contract)
    await db_session.commit()

    # Act
    response = await client.get("/contracts/")

    # Assert
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert len(data["items"]) == 1
    assert data["items"][0]["contract_id"] == 123
```

## 5. Special Case: Live ESI Contract Testing

**Problem:** Our standard integration tests mock the ESI API for speed and reliability. However, as we've experienced, the live ESI API can have quirks and inconsistencies (e.g., missing fields instead of `null`). Mocking can give us a false sense of security that our parsing logic is robust enough for the real world.

**Solution:** We will maintain a small, separate suite of **Live ESI Contract Tests**. Their sole purpose is to validate that our `ESIClient` and Pydantic schemas can correctly handle responses from the *actual, live ESI API*.

### How It Works: Record & Replay with `pytest-vcr`

We use the `pytest-vcr` library to implement a "record-and-replay" strategy.

1.  **Recording:** The first time a test is run, `pytest-vcr` makes a **real network call** to the ESI API and saves the exact HTTP request and response to a YAML file called a "cassette" (e.g., `tests/cassettes/test_esi_client/test_get_real_contract.yaml`).
2.  **Replaying:** On all subsequent runs, `pytest-vcr` intercepts the network call. Instead of hitting the live API, it finds the matching request in the cassette and returns the saved response. This makes the test run instantly and without network access, but it's validating against a *real, historical* API response.
3.  **Re-recording:** To re-validate against the live API (e.g., before a release or when a bug is suspected), we can instruct `pytest-vcr` to re-record the cassettes.

### Implementation for Cascade

#### A. Mark the Tests

These tests **must** be marked with a custom `esi_live` marker. This allows us to run them separately from the main test suite. They should also be marked with `vcr`.

#### B. Write the Test

These tests should be focused *only* on the client-to-API interaction, not our own database or internal endpoints.

```python
# app/backend/src/fastapi_app/tests/services/test_esi_client_live.py
import pytest
from fastapi_app.core.esi_client import ESIClient
from fastapi_app.core.config import get_settings

# Mark all tests in this file for VCR and our custom marker
pytestmark = [
    pytest.mark.vcr,
    pytest.mark.esi_live
]

@pytest.mark.asyncio
async def test_get_real_public_contracts():
    """
    Tests that the ESIClient can fetch and parse real public contracts
    from the live ESI API. This test will be recorded and replayed by VCR.
    """
    # Arrange
    settings = get_settings()
    client = ESIClient(settings=settings)

    # Act
    # This will make a real HTTP request the first time it's run.
    # On subsequent runs, it will use the 'cassette'.
    async with client as esi:
        # Using a known region with public contracts, like The Forge
        contracts = await esi.get_public_contracts(region_id=10000002)

    # Assert
    # We don't know the exact data, but we can check the structure.
    assert isinstance(contracts, list)
    if contracts:
        # If any contracts were returned, check the first one's structure
        contract = contracts[0]
        assert "contract_id" in contract
        assert "issuer_id" in contract
        assert "type" in contract
        # This validates that our Pydantic model (or dict parsing)
        # can handle the real-world data structure.
```

#### C. Running the Tests

-   **Run all tests *except* live ESI tests (default for CI/dev):**
    ```bash
    pdm run pytest -m "not esi_live"
    ```
-   **Run *only* the live ESI tests (using cassettes):**
    ```bash
    pdm run pytest -m esi_live
    ```
-   **Re-record the cassettes from the live API:**
    ```bash
    pdm run pytest -m esi_live --vcr-record=all
    ```

This layered approach gives us fast, reliable day-to-day tests while providing a powerful, controlled safety net to ensure our application can handle the realities of the ESI API.

## 6. The Limits of Testing & Structural Contracts

*(This section remains critical and is preserved from the previous version.)*

Testing is not a silver bullet. It is weak against architectural or non-functional errors (performance, security). Our quality strategy relies on multiple layers:
1.  **Testing:** For functional correctness.
2.  **Documented Patterns:** For architectural consistency.
3.  **Code Review:** For human verification of both.

### Mandatory: Testing Structural Contracts

If a class is designed to implement a specific Python protocol (e.g., `AsyncContextManager`), a dedicated unit test **must** exist to verify its structural contract. This prevents runtime `TypeError` exceptions.

#### Example: Testing an Async Context Manager

This test would have caught the `ESIClient` implementation bug.

```python
# In a relevant test file, e.g., tests/core/test_esi_client_class.py
import pytest
from collections.abc import AsyncContextManager

from fastapi_app.core.esi_client_class import ESIClient
from fastapi_app.core.config import get_settings

@pytest.mark.asyncio
async def test_esi_client_is_valid_async_context_manager():
    """
    Verifies that ESIClient correctly implements the async context manager protocol.
    """
    settings = get_settings()
    client = ESIClient(settings=settings)

    assert isinstance(client, AsyncContextManager)
    try:
        async with client as client_instance:
            assert client_instance is client
    except Exception as e:
        pytest.fail(f"ESIClient failed to function as an async context manager. Error: {e}")
```
