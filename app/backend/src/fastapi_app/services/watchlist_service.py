# ABOUTME: F006 watchlist CRUD + the design §4.5 add pipeline (cap -> resolve -> validate -> insert).
# ABOUTME: ESI error discrimination: 4xx -> 400 (bad request); 5xx/network/malformed/throttle (420,429) -> 502 (retryable).
from typing import Any, Optional

import httpx
from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config import settings
from ..core.esi_client_class import ESIClient
from ..core.exceptions import ESIRequestFailedError
from ..models import User, WatchlistItem
from ..schemas.account import WatchlistItemCreate, WatchlistItemUpdate

SHIP_CATEGORY_ID = 6  # EVE static "Ship" category


_UPSTREAM_UNAVAILABLE = "Ship metadata service is unavailable; try again."
_RATE_LIMITED = "ESI is rate-limiting requests; try again shortly"


def _map_esi_failure(status_code: int, invalid_msg: str) -> HTTPException:
    """Map an ESI failure status to the account-API surface.

    ESI 420 (error-limited) / 429 (rate-limited) are upstream throttling, not user error, so they
    surface as a retryable outage (502) — same shape as 5xx. Other 4xx is a genuine bad request
    (400); 5xx / network / malformed body (status 0) is a retryable outage (502).
    """
    if status_code in (420, 429):
        return HTTPException(status_code=502, detail=_RATE_LIMITED)
    if 400 <= status_code < 500:
        return HTTPException(status_code=400, detail=invalid_msg)
    return HTTPException(status_code=502, detail=_UPSTREAM_UNAVAILABLE)


async def _fetch_type_or_400_502(esi_client: ESIClient, type_id: int) -> dict[str, Any]:
    try:
        return await esi_client.get_universe_type(type_id)
    except ESIRequestFailedError as e:                 # 5xx / network / malformed body after retries
        raise _map_esi_failure(e.status_code, "unknown or invalid type")
    except httpx.HTTPStatusError as e:                 # 4xx (404, 420, 429) — see source note #1
        raise _map_esi_failure(e.response.status_code, "unknown or invalid type")
    except httpx.RequestError:                         # transport failure the client retry didn't catch
        raise HTTPException(status_code=502, detail=_UPSTREAM_UNAVAILABLE)


async def _fetch_group_or_400_502(esi_client: ESIClient, group_id: int) -> dict[str, Any]:
    try:
        return await esi_client.get_universe_group(group_id)
    except ESIRequestFailedError as e:
        raise _map_esi_failure(e.status_code, "unknown or invalid type")
    except httpx.HTTPStatusError as e:
        raise _map_esi_failure(e.response.status_code, "unknown or invalid type")
    except httpx.RequestError:                         # transport failure the client retry didn't catch
        raise HTTPException(status_code=502, detail=_UPSTREAM_UNAVAILABLE)


async def _resolve_name_to_type_id(esi_client: ESIClient, name: str) -> int:
    try:
        body = await esi_client.resolve_names([name])
    except ESIRequestFailedError as e:
        raise _map_esi_failure(e.status_code, "unknown ship name")
    inventory_types = body.get("inventory_types") or []
    if not inventory_types:
        raise HTTPException(status_code=400, detail="unknown ship name")
    # ESI exact-matches; a non-empty inventory_types means the name resolved.
    return int(inventory_types[0]["id"])


async def add_watchlist_item(
    db: AsyncSession, esi_client: ESIClient, user: User, payload: WatchlistItemCreate
) -> WatchlistItem:
    # (1) cap-count check — BEFORE any ESI traffic (design §4.5 binding order).
    count = await db.scalar(
        select(func.count()).select_from(WatchlistItem).where(WatchlistItem.user_id == user.id)
    )
    if count >= settings.MAX_WATCHLIST_ITEMS_PER_USER:
        raise HTTPException(
            status_code=400,
            detail=f"watchlist is full (max {settings.MAX_WATCHLIST_ITEMS_PER_USER} items)",
        )

    # (2) resolution — name -> type_id when type_id absent.
    type_id = payload.type_id
    if type_id is None:
        type_id = await _resolve_name_to_type_id(esi_client, payload.type_name)

    # (3) validation — published ship (category 6).
    type_info = await _fetch_type_or_400_502(esi_client, type_id)
    if not type_info.get("published"):
        raise HTTPException(status_code=400, detail="type is not a published item")
    group_info = await _fetch_group_or_400_502(esi_client, type_info.get("group_id"))
    if group_info.get("category_id") != SHIP_CATEGORY_ID:
        raise HTTPException(status_code=400, detail="type is not a ship")

    # (4) insert — duplicate caught via the real unique constraint (no pre-check; race-safe).
    item = WatchlistItem(
        user_id=user.id,
        type_id=type_id,
        type_name=type_info.get("name"),
        max_price=payload.max_price,
        notes=payload.notes,
    )
    try:
        async with db.begin_nested():   # SAVEPOINT: an IntegrityError rolls back only this insert
            db.add(item)
            await db.flush()
    except IntegrityError:
        raise HTTPException(status_code=409, detail="already watching this type")
    return item


async def list_watchlist_items(db: AsyncSession, user: User) -> list[WatchlistItem]:
    result = await db.execute(
        select(WatchlistItem)
        .where(WatchlistItem.user_id == user.id)
        .order_by(WatchlistItem.type_name.asc(), WatchlistItem.type_id.asc())   # names not unique
    )
    return list(result.scalars().all())


async def update_watchlist_item(
    db: AsyncSession, user: User, item_id: int, payload: WatchlistItemUpdate
) -> WatchlistItem:
    item = (
        await db.execute(
            select(WatchlistItem).where(
                WatchlistItem.id == item_id, WatchlistItem.user_id == user.id
            )
        )
    ).scalar_one_or_none()
    if item is None:
        raise HTTPException(status_code=404, detail="Watchlist item not found")
    # Omit preserves, explicit null clears — driven by which keys the client actually sent.
    fields = payload.model_fields_set
    if "max_price" in fields:
        item.max_price = payload.max_price
    if "notes" in fields:
        item.notes = payload.notes
    await db.flush()
    # updated_at carries onupdate=func.now() (a server-evaluated UPDATE default). SQLAlchemy fetches
    # UPDATE-generated defaults only on refresh — without this the router's WatchlistItemSchema
    # serialization reads an expired attribute and raises MissingGreenlet (implicit async IO). Section A.
    await db.refresh(item)
    return item


async def delete_watchlist_item(db: AsyncSession, user: User, item_id: int) -> None:
    item = (
        await db.execute(
            select(WatchlistItem).where(
                WatchlistItem.id == item_id, WatchlistItem.user_id == user.id
            )
        )
    ).scalar_one_or_none()
    if item is None:
        raise HTTPException(status_code=404, detail="Watchlist item not found")
    await db.delete(item)
    await db.flush()
