import asyncio
from typing import AsyncGenerator, Generator



import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker, AsyncEngine

from fastapi_app.main import app as real_app
from fastapi_app.db import get_db
from fastapi_app.db import Base
from fastapi_app.config import settings

# Use a separate, real Postgres database for testing to match production.
# This ensures that tests run against the same database engine as the live application.
# The URL is loaded from the DATABASE_URL_TESTS environment variable.
if not settings.DATABASE_URL_TESTS:
    raise ValueError("DATABASE_URL_TESTS environment variable must be set for testing")

TEST_DATABASE_URL = str(settings.DATABASE_URL_TESTS)


# --- Database Fixtures ---


@pytest_asyncio.fixture(scope="function")
async def engine() -> AsyncGenerator[AsyncEngine, None]:
    """
    Function-scoped engine fixture.
    Creates a new SQLAlchemy engine for each test function and disposes of it properly.
    """
    db_engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    yield db_engine
    await db_engine.dispose()


@pytest.fixture(scope="function")
def TestingSessionLocal(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Creates a sessionmaker bound to the test engine for each function."""
    return async_sessionmaker(autocommit=False, autoflush=False, bind=engine)




@pytest_asyncio.fixture(scope="function", autouse=True)
async def setup_database(engine: AsyncEngine):
    # This fixture ensures that the database is clean before each test.
    # It connects, drops all tables, and recreates them.
    # DDL operations are run inside a transaction to ensure atomicity.
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

@pytest_asyncio.fixture(scope="function")
async def db_session(
    TestingSessionLocal: async_sessionmaker[AsyncSession],
) -> AsyncGenerator[AsyncSession, None]:
    """
    Function-scoped fixture to provide a clean database session for each test.
    This is the fixture tests will request to interact with the database.
    """
    async with TestingSessionLocal() as session:
        yield session
        await session.rollback()  # Ensure tests are isolated

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
