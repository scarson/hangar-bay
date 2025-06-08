from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import declarative_base

from .config import get_settings

settings = get_settings()

async_engine = create_async_engine(
    str(
        settings.DATABASE_URL
    ),  # Pydantic DSN types need to be cast to str for SQLAlchemy
    echo=settings.ENVIRONMENT == "development",  # Log SQL queries in development
    future=True,  # Use SQLAlchemy 2.0 style
)

AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,  # Good default for FastAPI dependencies
    autoflush=False,
)

Base = declarative_base()


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
