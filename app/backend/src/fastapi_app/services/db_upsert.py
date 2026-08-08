from typing import AbstractSet, Any, Dict, List, Optional

from sqlalchemy import func, inspect
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession


async def bulk_upsert(
    db: AsyncSession,
    model_class,
    values: List[Dict[str, Any]],
    preserve_on_null: Optional[AbstractSet[str]] = None,
):
    """
    Performs a bulk "upsert" (insert on conflict update) operation.

    This function is compatible with both PostgreSQL and SQLite backends.

    Args:
        db: The SQLAlchemy AsyncSession.
        model_class: The SQLAlchemy ORM model class for the table.
        values: A list of dictionaries, where each dictionary represents a row to upsert.
        preserve_on_null: Column names for which NULL in an update row means
            "unknown this run", not "clear the value". On conflict these compile
            to COALESCE(excluded.col, table.col), so a degraded enrichment run
            (e.g. a partial /universe/names map) cannot blank a previously
            stored value; a non-NULL value still overwrites. Fresh inserts are
            unaffected — NULL inserts as NULL.
    """
    if not values:
        return

    preserve_on_null = preserve_on_null or frozenset()

    table = model_class.__table__
    primary_key_cols = [c.name for c in inspect(model_class).primary_key]
    # Only update columns the caller actually supplied. `stmt.excluded`
    # enumerates EVERY table column, so building set_ from it wholesale
    # clobbers omitted columns with their defaults on conflict — that decayed
    # enrichment-maintained fields (is_ship_contract) on ETag-304 re-ingestion.
    supplied_cols = [name for name in values[0] if name not in primary_key_cols]

    def _update_cols(stmt):
        return {
            name: (
                func.coalesce(stmt.excluded[name], table.c[name])
                if name in preserve_on_null
                else stmt.excluded[name]
            )
            for name in supplied_cols
        }

    dialect = db.bind.dialect.name
    if dialect == "postgresql":
        stmt = pg_insert(table).values(values)
        stmt = stmt.on_conflict_do_update(
            index_elements=primary_key_cols,
            set_=_update_cols(stmt),
        )
    elif dialect == "sqlite":
        stmt = sqlite_insert(table).values(values)
        stmt = stmt.on_conflict_do_update(
            index_elements=primary_key_cols,
            set_=_update_cols(stmt),
        )
    else:
        # A basic fallback for other dialects, though less performant. Dropping
        # NULL-valued preserved keys gives merge the same keep-the-stored-value
        # semantics: merge only copies attributes that were actually set.
        for value in values:
            preserved = {
                k: v
                for k, v in value.items()
                if not (v is None and k in preserve_on_null)
            }
            await db.merge(model_class(**preserved))
        await db.flush()
        return

    await db.execute(stmt)
