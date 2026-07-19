# ABOUTME: Alembic environment — async-engine CLI migrations + pytest-injected-connection support.
# ABOUTME: Import-safe: the invocation tail only fires under an alembic-provided context (tests import this module).
import asyncio
import os
import sys

# 'src' (parent of alembic/ and fastapi_app/) must be importable.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.ext.asyncio import create_async_engine

from alembic import context

from fastapi_app.core.config import get_settings
from fastapi_app.db import Base
from fastapi_app.models import user, contracts  # noqa: F401  (registers tables on Base.metadata)

settings = get_settings()
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    config = context.config
    if config.config_file_name is not None:
        fileConfig(config.config_file_name)
    context.configure(
        url=str(settings.DATABASE_URL),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )
    context.run_migrations()


def do_run_migrations(connection):
    """Run migrations on a caller-managed connection/transaction (CLI engine or pytest fixture)."""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
    )
    context.run_migrations()


async def run_migrations_online_async_cli():
    connectable = create_async_engine(
        str(settings.DATABASE_URL),
        poolclass=pool.NullPool,
        future=True,
    )
    async with connectable.begin() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online():
    config = context.config
    if config.config_file_name is not None:
        fileConfig(config.config_file_name)
    connectable = context.config.attributes.get("connection", None)
    if connectable is None:
        asyncio.run(run_migrations_online_async_cli())
    else:
        do_run_migrations(connectable)


def _running_under_alembic() -> bool:
    """True only when alembic's EnvironmentContext is active (i.e. invoked via the alembic CLI/API);
    plain `import env` from pytest must not trigger migrations."""
    try:
        context.config
        return True
    except AttributeError:
        return False


if _running_under_alembic():
    if context.is_offline_mode():
        run_migrations_offline()
    else:
        run_migrations_online()
