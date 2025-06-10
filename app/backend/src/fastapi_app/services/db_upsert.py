from typing import Any, Dict, List

from sqlalchemy import inspect
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession


async def bulk_upsert(
    db: AsyncSession,
    model_class,
    values: List[Dict[str, Any]],
):
    """
    Performs a bulk "upsert" (insert on conflict update) operation.

    This function is compatible with both PostgreSQL and SQLite backends.

    Args:
        db: The SQLAlchemy AsyncSession.
        model_class: The SQLAlchemy ORM model class for the table.
        values: A list of dictionaries, where each dictionary represents a row to upsert.
    """
    if not values:
        return

    table = model_class.__table__
    primary_key_cols = [c.name for c in inspect(model_class).primary_key]

    dialect = db.bind.dialect.name
    if dialect == "postgresql":
        stmt = pg_insert(table).values(values)
        update_cols = {
            c.name: c for c in stmt.excluded if c.name not in primary_key_cols
        }
        stmt = stmt.on_conflict_do_update(
            index_elements=primary_key_cols,
            set_=update_cols,
        )
    elif dialect == "sqlite":
        stmt = sqlite_insert(table).values(values)
        update_cols = {
            c.name: c for c in stmt.excluded if c.name not in primary_key_cols
        }
        stmt = stmt.on_conflict_do_update(
            index_elements=primary_key_cols,
            set_=update_cols,
        )
    else:
        # A basic fallback for other dialects, though less performant.
        for value in values:
            await db.merge(model_class(**value))
        await db.flush()
        return

    await db.execute(stmt)
