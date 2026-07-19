from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import declarative_base
from typing import Callable
from contextlib import AbstractAsyncContextManager

from .core.config import get_settings

Base = declarative_base()
settings = get_settings()

async_engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.ENVIRONMENT == "development",  # Log SQL queries in development
    future=True,  # Use SQLAlchemy 2.0 style
    pool_pre_ping=True,   # managed-PG restarts/pooler idle-kills must not surface as request 500s
    pool_size=5,          # Render Basic's connection budget is small; scheduler + API share it
    max_overflow=5,
)

AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,  # Good default for FastAPI dependencies
    autoflush=False,
)


async def get_db_session_factory() -> Callable[..., AbstractAsyncContextManager[AsyncSession]]:
    """FastAPI dependency that provides the async session factory."""
    return AsyncSessionLocal


async def get_db() -> AsyncSession:
    """
    FastAPI dependency that provides an asynchronous database session.
    Ensures the session is closed after the request is finished.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()  # Commit changes if no exceptions occurred
        except Exception:
            await session.rollback()  # Rollback on error
            raise
        finally:
            await session.close()  # Ensure session is closed
