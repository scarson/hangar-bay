import asyncio
from typing import AsyncGenerator, Generator

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from fastapi_app.main import app as real_app
from fastapi_app.db import get_db
from fastapi_app.db import Base

# Use a predictable, in-memory SQLite database for testing
# This is faster and avoids creating files on disk.
TEST_DATABASE_URL = "sqlite+aiosqlite:///./test.db"


# Create an async engine for the test database
engine = create_async_engine(TEST_DATABASE_URL, echo=False)
TestingSessionLocal = async_sessionmaker(autocommit=False, autoflush=False, bind=engine)

# --- Database Fixtures ---

@pytest.fixture(scope="session")
def event_loop() -> Generator:
    """Creates an instance of the default event loop for the session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest_asyncio.fixture(scope="session", autouse=True)
async def setup_database():
    """
    Session-scoped fixture to create and tear down the test database.
    `autouse=True` ensures it runs automatically for the session.
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

@pytest_asyncio.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Function-scoped fixture to provide a clean database session for each test.
    This is the fixture tests will request to interact with the database.
    """
    async with TestingSessionLocal() as session:
        yield session
        await session.rollback() # Ensure tests are isolated

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
