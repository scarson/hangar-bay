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

from fastapi_app.core.config import settings
from fastapi_app.core import session as sess
from fastapi_app.models import User
from fastapi_app.models.contracts import Contract, ContractItem

# Use a separate, real Postgres database for testing to match production.
# This ensures that tests run against the same database engine as the live application.
# The URL is loaded from the DATABASE_URL_TESTS environment variable.
if not settings.DATABASE_URL_TESTS:
    raise ValueError("DATABASE_URL_TESTS environment variable must be set for testing")

TEST_DATABASE_URL = str(settings.DATABASE_URL_TESTS)


# --- Database Fixtures ---


# --- Database Fixtures (Authoritative Pattern) ---
# The following fixture implements the authoritative pattern for SQLAlchemy 2.0
# and pytest-asyncio in strict mode. It ensures maximum test isolation at the
# cost of performance, as the engine and tables are created and destroyed
# for each test function.

@pytest_asyncio.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Provides a clean, transactional database session for each test function.

    This fixture implements the recommended pattern for testing with SQLAlchemy 2.0
    and pytest-asyncio in strict mode. It ensures complete test isolation by:
    1.  Creating a new engine and tables for each test function, bound to the
        test's specific event loop.
    2.  Wrapping the entire test in a single transaction that is rolled back
        at the end.
    """
    # Create a new engine for each test function, ensuring it's bound to the
    # correct event loop.
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)

    # Drop all tables to ensure a clean state, in case a previous test failed
    # during teardown.
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    # Create all tables fresh for the test.
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Use the "begin once" pattern for the session. A single transaction is
    # started and rolled back for the entire test.
    session_maker = async_sessionmaker(engine, expire_on_commit=False)
    async with session_maker.begin() as session:
        yield session

    # Drop all tables after the test is done.
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    # Dispose of the engine to release connections.
    await engine.dispose()


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
            contract_id=101, title="Tristan for Sale", price=1_000_000, collateral=0, status="outstanding", type="item_exchange",
            issuer_id=1, issuer_corporation_id=101, start_location_id=60003760, start_location_system_id=30000142, start_location_region_id=10000002,
            for_corporation=False, date_issued=datetime.now(timezone.utc), date_expired=datetime.now(timezone.utc) + timedelta(days=7),
            items=[
                ContractItem(record_id=1011, type_id=587, type_name="Tristan", quantity=1, is_included=True, is_singleton=False, is_blueprint_copy=False)
            ]
        ),
        # Contract 2: BPC auction (Caracal) with specific runs for testing
        Contract(
            contract_id=102, title="Caracal BPC Auction", price=5_000_000, collateral=1_000_000, status="outstanding", type="auction",
            issuer_id=2, issuer_corporation_id=102, start_location_id=60003760, start_location_system_id=30000142, start_location_region_id=10000002,
            for_corporation=True, date_issued=datetime.now(timezone.utc), date_expired=datetime.now(timezone.utc) + timedelta(days=3),
            items=[
                ContractItem(record_id=1021, type_id=621, type_name="Caracal Blueprint", quantity=1, is_included=True, is_singleton=True, is_blueprint_copy=True, raw_quantity=10)
            ]
        ),
        # Contract 3: Multi-item contract in a different region (Venture, Tristan)
        Contract(
            contract_id=103, title="Mining Starter Pack", price=2_500_000, collateral=500_000, status="outstanding", type="item_exchange",
            issuer_id=3, issuer_corporation_id=103, start_location_id=60008494, start_location_system_id=30002187, start_location_region_id=10000020,
            for_corporation=False, date_issued=datetime.now(timezone.utc), date_expired=datetime.now(timezone.utc) + timedelta(days=14),
            items=[
                ContractItem(record_id=1031, type_id=17480, type_name="Venture", quantity=1, is_included=True, is_singleton=False, is_blueprint_copy=False),
                ContractItem(record_id=1032, type_id=587, type_name="Tristan", quantity=1, is_included=True, is_singleton=False, is_blueprint_copy=False)
            ]
        ),
        # Contract 4: High-price, high-collateral contract (Rokh)
        Contract(
            contract_id=104, title="Battleship Rokh", price=200_000_000, collateral=100_000_000, status="outstanding", type="item_exchange",
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


import httpx
import pytest_asyncio
from pydantic import SecretStr
from cryptography.fernet import Fernet

from fastapi_app.tests.fake_redis import FakeRedis


@pytest_asyncio.fixture(scope="function")
async def auth_client(db_session, httpx_mock):
    """HTTP client over real_app with the auth routers mounted, app.state wired, and get_db overridden.
    Does NOT configure SSO settings — use the `configured_sso` fixture for happy-path flow tests.
    Depends on httpx_mock STRUCTURALLY: pytest-httpx patches the async transport class,
    so app.state.http_client can never reach the real network in ANY auth test — an
    un-mocked token POST fails loudly instead of leaving the process. (The outer
    ASGITransport client is a different transport class and is unaffected.) Tests
    that need token responses request httpx_mock themselves and get the same instance."""
    from fastapi_app.main import app as real_app
    from fastapi_app.db import get_db as get_db_dep

    fake = FakeRedis()
    real_app.state.redis = fake
    real_app.state.http_client = httpx.AsyncClient(base_url="http://sso.test")  # pytest-httpx intercepts this
    real_app.dependency_overrides[get_db_dep] = lambda: db_session

    transport = httpx.ASGITransport(app=real_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        client.fake_redis = fake     # expose to tests for state/session assertions
        yield client

    await real_app.state.http_client.aclose()
    del real_app.state.redis
    del real_app.state.http_client
    real_app.dependency_overrides.clear()


@pytest.fixture
def configured_sso(monkeypatch):
    """Configure the settings singleton for a working SSO flow. (Plain pytest fixture —
    it is synchronous; pytest_asyncio.fixture is reserved for the async auth_client.)"""
    from fastapi_app.core.config import settings
    monkeypatch.setattr(settings, "ESI_CLIENT_ID", "test-client")
    monkeypatch.setattr(settings, "ESI_CLIENT_SECRET", SecretStr("test-secret"))
    monkeypatch.setattr(settings, "TOKEN_CIPHER_KEYS", SecretStr(Fernet.generate_key().decode()))
    return settings


async def login_as(auth_client, db_session, *, character_id, character_name, owner_hash):
    """Insert a real User, mint a server-side session pointing at its users.id, and set the
    session cookie on auth_client. OVERWRITES the client cookie, so cross-user tests either
    capture each user's sid before switching or accept that the last login_as wins. Returns
    the User (for FK'd-row arrangement and assertions)."""
    user = User(character_id=character_id, character_name=character_name, owner_hash=owner_hash)
    db_session.add(user)
    await db_session.flush()  # populates user.id (the FK target for M3 tables)
    sid = await sess.create_session(
        auth_client.fake_redis,
        user_id=user.id, character_id=user.character_id, character_name=user.character_name,
    )
    auth_client.cookies.set(settings.SESSION_COOKIE_NAME, sid)
    return user


@pytest_asyncio.fixture
async def authed_user(auth_client, db_session):
    """The canonical authenticated M3 caller: a real User row + a real session, returned as
    (user, auth_client). Use for happy-path and single-user CRUD tests; use login_as for the
    second identity in cross-user isolation tests."""
    user = await login_as(
        auth_client, db_session,
        character_id=91000001, character_name="Sesta Hound", owner_hash="OWN1",
    )
    return user, auth_client
