# ABOUTME: F006 watchlist router — /me/watchlist-items (bare-mounted, PROXY-1; auth-gated per user).
# ABOUTME: Declares error bodies (400/401/409/502) so the typed client sees them (closes the /me gap).
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.current_user import get_current_user
from ..core.dependencies import get_esi_client
from ..core.esi_client_class import ESIClient
from ..db import get_db
from ..models import User
from ..schemas.account import (
    WatchlistItemCreate,
    WatchlistItemSchema,
    WatchlistItemUpdate,
)
from ..schemas.auth import ErrorDetail
from ..services import watchlist_service

router = APIRouter(prefix="/me/watchlist-items", tags=["Watchlist"])

_AUTH = {401: {"model": ErrorDetail, "description": "Not authenticated"}}
_NOT_FOUND = {404: {"model": ErrorDetail, "description": "Not found"}}


@router.post(
    "/",
    response_model=WatchlistItemSchema,
    status_code=status.HTTP_201_CREATED,
    responses={
        **_AUTH,
        400: {"model": ErrorDetail, "description": "Cap reached / unknown name / not a published ship"},
        409: {"model": ErrorDetail, "description": "Already watching this type"},
        502: {"model": ErrorDetail, "description": "ESI unreachable"},
    },
)
async def add_watchlist_item(
    payload: WatchlistItemCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    esi_client: ESIClient = Depends(get_esi_client),
) -> WatchlistItemSchema:
    item = await watchlist_service.add_watchlist_item(db, esi_client, user, payload)
    return WatchlistItemSchema.model_validate(item)


@router.get("/", response_model=list[WatchlistItemSchema], responses={**_AUTH})
async def list_watchlist_items(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[WatchlistItemSchema]:
    items = await watchlist_service.list_watchlist_items(db, user)
    return [WatchlistItemSchema.model_validate(i) for i in items]


@router.put(
    "/{item_id}",
    response_model=WatchlistItemSchema,
    responses={**_AUTH, **_NOT_FOUND},
)
async def update_watchlist_item(
    item_id: int,
    payload: WatchlistItemUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> WatchlistItemSchema:
    item = await watchlist_service.update_watchlist_item(db, user, item_id, payload)
    return WatchlistItemSchema.model_validate(item)


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT, responses={**_AUTH, **_NOT_FOUND})
async def delete_watchlist_item(
    item_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    await watchlist_service.delete_watchlist_item(db, user, item_id)
