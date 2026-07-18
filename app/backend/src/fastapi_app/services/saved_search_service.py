# ABOUTME: F005 saved-search CRUD — ownership-scoped queries, best-effort per-user cap, and unique-name
# ABOUTME: 409 mapping via a SAVEPOINT (so a duplicate leaves the sibling row + outer transaction intact).
from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config import get_settings
from ..models.account import SavedSearch
from ..schemas.account import SavedSearchCreate, SavedSearchUpdate

_DUPLICATE_DETAIL = "A saved search with this name already exists."


async def list_saved_searches(db: AsyncSession, user_id: int) -> list[SavedSearch]:
    result = await db.execute(
        select(SavedSearch)
        .where(SavedSearch.user_id == user_id)
        .order_by(SavedSearch.name.asc())
    )
    return list(result.scalars().all())


async def _get_owned(db: AsyncSession, user_id: int, search_id: int) -> SavedSearch:
    # Scope by user_id so not-owned is indistinguishable from not-found — a uniform 404
    # (anti-enumeration, design §4.5).
    row = (
        await db.execute(
            select(SavedSearch).where(
                SavedSearch.id == search_id, SavedSearch.user_id == user_id
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Saved search not found")
    return row


async def create_saved_search(
    db: AsyncSession, user_id: int, payload: SavedSearchCreate
) -> SavedSearch:
    settings = get_settings()
    count = (
        await db.execute(
            select(func.count()).select_from(SavedSearch).where(SavedSearch.user_id == user_id)
        )
    ).scalar_one()
    if count >= settings.MAX_SAVED_SEARCHES_PER_USER:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Saved search limit reached (maximum {settings.MAX_SAVED_SEARCHES_PER_USER}).",
        )
    row = SavedSearch(
        user_id=user_id,
        name=payload.name,
        search_parameters=payload.search_parameters.model_dump(),
    )
    try:
        # SAVEPOINT: a unique-name violation rolls back only this insert, keeping the outer
        # transaction (and any sibling rows) alive — the 409 is race-safe (no pre-check).
        async with db.begin_nested():
            db.add(row)
            await db.flush()
    except IntegrityError:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=_DUPLICATE_DETAIL)
    # Reload server-default columns (created_at/updated_at) so response serialization is
    # pure in-memory and never triggers an async lazy-load (MissingGreenlet).
    await db.refresh(row)
    return row


async def rename_saved_search(
    db: AsyncSession, user_id: int, search_id: int, payload: SavedSearchUpdate
) -> SavedSearch:
    row = await _get_owned(db, user_id, search_id)
    try:
        # begin_nested() flushes pending state when the savepoint is ENTERED, so the rename
        # assignment MUST happen INSIDE the savepoint. If `row.name = payload.name` were set
        # before `begin_nested()`, the unique-name violation would flush OUTSIDE the savepoint
        # and poison the begin-once outer transaction instead of rolling back only this statement.
        async with db.begin_nested():
            row.name = payload.name
            await db.flush()
    except IntegrityError:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=_DUPLICATE_DETAIL)
    await db.refresh(row)
    return row


async def delete_saved_search(db: AsyncSession, user_id: int, search_id: int) -> None:
    row = await _get_owned(db, user_id, search_id)
    await db.delete(row)
    await db.flush()
