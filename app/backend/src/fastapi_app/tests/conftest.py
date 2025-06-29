import asyncio
from typing import AsyncGenerator, Generator

from sqlalchemy import text


import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import (
    create_async_engine,
    AsyncSession,
    async_sessionmaker,
    AsyncEngine,
    AsyncConnection,
)

from fastapi_app.main import app as real_app
from fastapi_app.db import get_db
from fastapi_app.db import Base
from datetime import datetime, timedelta, timezone

from fastapi_app.config import settings
from fastapi_app.models.contracts import Contract, ContractItem

# Use a separate, real Postgres database for testing to match production.
# This ensures that tests run against the same database engine as the live application.
# The URL is loaded from the DATABASE_URL_TESTS environment variable.
if not settings.DATABASE_URL_TESTS:
    raise ValueError("DATABASE_URL_TESTS environment variable must be set for testing")

TEST_DATABASE_URL = str(settings.DATABASE_URL_TESTS)


# --- Database Fixtures ---


# --- Database Fixtures (Scalable Version) ---
# The following fixtures are designed for performance and scalability.
# The database schema is created only ONCE per test session.
# Between each test, transactional data is rapidly cleared via TRUNCATE
# without the overhead of dropping and recreating tables.

# The custom event_loop fixture has been removed to restore the default pytest-asyncio
# behavior. Pytest-asyncio provides a new, isolated event loop for each test
# function, which is the correct pattern for ensuring test isolation and preventing
# the 'Task attached to a different loop' runtime error.


@pytest_asyncio.fixture(scope="session")
async def engine() -> AsyncGenerator[AsyncEngine, None]:
    """
    Session-scoped fixture to create and dispose of the test database engine.
    The schema is created once at the beginning of the session and dropped at the end.
    """
    db_engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with db_engine.begin() as conn:
        # Using run_sync for DDL operations is a robust pattern
        await conn.run_sync(Base.metadata.create_all)

    yield db_engine

    async with db_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await db_engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def db_session(engine: AsyncEngine) -> AsyncGenerator[AsyncSession, None]:
    """
    Provides a transactional session for each test function using a robust
    rollback strategy for test isolation.

    This fixture lets the session itself manage the connection and transaction
    state, which is a more robust pattern than manual connection handling.
    It creates a single transaction that is rolled back after the test completes.
    Nested transactions (SAVEPOINTs) are created implicitly by operations like
    `session.flush()`.
    """
    # Create a sessionmaker bound to the engine, not a specific connection.
    session_maker = async_sessionmaker(engine, expire_on_commit=False)
    async with session_maker() as session:
        # Begin a transaction. The session will acquire a connection from the
        # engine's pool and start a transaction on it.
        await session.begin()

        try:
            yield session
        finally:
            # Rollback the whole transaction.
            await session.rollback()
            # The `async with` block automatically closes the session and returns
            # the connection to the pool.


# --- Application and Client Fixtures ---

@pytest.fixture(scope="function")
def test_app(db_session: AsyncSession) -> Generator[FastAPI, None, None]:
    """
    Function-scoped fixture to create a new app instance for each test,
    with the database dependency overridden to use the test session.
    """
    # Override the get_db dependency to use our test database session
    real_app.dependency_overrides[get_db] = lambda: db_session
    yield real_app
    # Clean up overrides after the test
    real_app.dependency_overrides.clear()


@pytest_asyncio.fixture(scope="function")
async def client(test_app: FastAPI) -> AsyncGenerator[AsyncClient, None]:
    """
    Function-scoped fixture to get an HTTPX client for making API requests.
    """
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

# Note: The `httpx_mock` and `vcr` fixtures are provided automatically by their
# respective pytest plugins (`pytest-httpx` and `pytest-vcr`).
# Tests can simply request them as arguments or use the appropriate markers.


@pytest_asyncio.fixture(scope="function")
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
        # Contract 2: BPC auction (Caracal) with specific runs for testing
        Contract(
            contract_id=102, title="Caracal BPC Auction", price=5_000_000, collateral=1_000_000, status="outstanding", contract_type="auction",
            issuer_id=2, issuer_corporation_id=102, start_location_id=60003760, start_location_system_id=30000142, start_location_region_id=10000002,
            for_corporation=True, date_issued=datetime.now(timezone.utc), date_expired=datetime.now(timezone.utc) + timedelta(days=3),
            items=[
                ContractItem(record_id=1021, type_id=621, type_name="Caracal Blueprint", quantity=1, is_included=True, is_singleton=True, is_blueprint_copy=True, raw_quantity=10)
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
    await db_session.flush()  # Use flush to send data within the test's transaction
    return contracts_data
