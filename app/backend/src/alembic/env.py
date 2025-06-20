import sys
import os

# Add the 'src' directory to sys.path
# The 'src' directory is the parent of 'alembic' and 'fastapi_app'
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import asyncio
from logging.config import fileConfig

from sqlalchemy.ext.asyncio import (
    create_async_engine,
)  # For online mode if not using shared engine
from sqlalchemy import pool

from alembic import context

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Import your application's settings and Base model
# Ensure your application's path is discoverable by Alembic.
# The `prepend_sys_path = .` in alembic.ini should handle this if running alembic from app/backend/src
from fastapi_app.config import get_settings
from fastapi_app.db import Base
# Ensure all models are registered with Base.metadata
# Import the modules first to ensure their top-level code runs
from fastapi_app.models import common_models, contracts # noqa: F401
# Then, explicitly import the model classes themselves
from fastapi_app.models.common_models import User # noqa: F401
from fastapi_app.models.contracts import Contract, ContractItem, EsiMarketGroupCache # noqa: F401

settings = get_settings()



# Import your models here so that Alembic's autogenerate can detect them
# --- BEGIN ALEMBIC METADATA DEBUG ---
print("--- ALEMBIC METADATA DEBUG START (stdout) ---", flush=True)
sys.stderr.write("--- ALEMBIC METADATA DEBUG START (stderr) ---\n")
sys.stderr.flush()
if Base.metadata.tables:
    for table_name, table_obj in Base.metadata.tables.items():
        msg = f"  Table: {table_name}\n"
        print(msg, flush=True)
        sys.stderr.write(msg)
        for column in table_obj.columns:
            col_msg = f"    Column: {column.name} (Type: {column.type}, Nullable: {column.nullable}, Default: {column.default}, Server Default: {column.server_default})\n"
            print(col_msg, flush=True)
            sys.stderr.write(col_msg)
else:
    print("  No tables found in Base.metadata (stdout)", flush=True)
    sys.stderr.write("  No tables found in Base.metadata (stderr)\n")
print("--- ALEMBIC METADATA DEBUG END (stdout) ---", flush=True)
sys.stderr.write("--- ALEMBIC METADATA DEBUG END (stderr) ---\n")
sys.stderr.flush()
# --- END ALEMBIC METADATA DEBUG ---

target_metadata = Base.metadata

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    context.configure(
        url=str(settings.DATABASE_URL),  # Use URL from app settings
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        # compare_type=True,  # Temporarily commented out to detect type changes
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):
    context.configure(
        connection=connection, target_metadata=target_metadata, 
        # compare_type=True  # Temporarily commented out to detect type changes
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online_async() -> None:
    """Run migrations in 'online' mode for an async engine.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    # Option 1: Create a new engine specifically for Alembic
    connectable = create_async_engine(
        str(settings.DATABASE_URL),
        poolclass=pool.NullPool,  # Recommended for Alembic with async
        future=True,
    )

    # Option 2: Use the application's shared engine (if appropriate for your setup)
    # connectable = app_async_engine

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()  # Important for async engines


def run_migrations_online() -> None:
    """Entry point for 'online' mode."""
    asyncio.run(run_migrations_online_async())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
