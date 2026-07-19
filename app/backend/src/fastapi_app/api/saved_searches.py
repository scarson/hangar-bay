# ABOUTME: F005 saved-searches router — bare-mounted /me/saved-searches (PROXY-1), auth-gated via get_current_user.
# ABOUTME: Declares 400/401/404/409 with ErrorDetail so the typed client sees the real error bodies (design §4.5).
from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.current_user import get_current_user
from ..db import get_db
from ..models import User
from ..schemas.account import SavedSearchCreate, SavedSearchSchema, SavedSearchUpdate
from ..schemas.auth import ErrorDetail
from ..services import saved_search_service

router = APIRouter(prefix="/me/saved-searches", tags=["Saved Searches"])

_UNAUTH = {401: {"model": ErrorDetail, "description": "Not authenticated"}}
_NOT_FOUND = {404: {"model": ErrorDetail, "description": "Saved search not found"}}
_DUPLICATE = {409: {"model": ErrorDetail, "description": "Duplicate saved-search name"}}
_CAP = {400: {"model": ErrorDetail, "description": "Per-user saved-search cap reached"}}


@router.get("/", response_model=list[SavedSearchSchema], responses={**_UNAUTH})
async def list_saved_searches(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await saved_search_service.list_saved_searches(db, user.id)


@router.post(
    "/",
    response_model=SavedSearchSchema,
    status_code=status.HTTP_201_CREATED,
    responses={**_UNAUTH, **_CAP, **_DUPLICATE},
)
async def create_saved_search(
    payload: SavedSearchCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await saved_search_service.create_saved_search(db, user.id, payload)


@router.put(
    "/{search_id}",
    response_model=SavedSearchSchema,
    responses={**_UNAUTH, **_NOT_FOUND, **_DUPLICATE},
)
async def rename_saved_search(
    search_id: int,
    payload: SavedSearchUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await saved_search_service.rename_saved_search(db, user.id, search_id, payload)


@router.delete(
    "/{search_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={**_UNAUTH, **_NOT_FOUND},
)
async def delete_saved_search(
    search_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await saved_search_service.delete_saved_search(db, user.id, search_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
