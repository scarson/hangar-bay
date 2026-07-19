# ABOUTME: F007 notifications router (/me/notifications) + settings router (/me/notification-settings).
# ABOUTME: List total is computed AFTER the is_read filter — the unread badge reads it (design §4.5).
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.current_user import get_current_user
from ..db import get_db
from ..models import Notification, User
from ..schemas.account import (
    NotificationFilters,
    NotificationSchema,
    NotificationSettingsSchema,
)
from ..schemas.auth import ErrorDetail
from ..schemas.common import PaginatedResponse

router = APIRouter(prefix="/me/notifications", tags=["Notifications"])
settings_router = APIRouter(prefix="/me/notification-settings", tags=["Notifications"])

_AUTH = {401: {"model": ErrorDetail, "description": "Not authenticated"}}
_NOT_FOUND = {404: {"model": ErrorDetail, "description": "Not found"}}


@router.get("/", response_model=PaginatedResponse[NotificationSchema], responses={**_AUTH})
async def list_notifications(
    filters: Annotated[NotificationFilters, Query()],   # FASTAPI-1: Annotated[..., Query()], not Depends
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PaginatedResponse[NotificationSchema]:
    base = select(Notification).where(Notification.user_id == user.id)
    if filters.is_read is not None:
        base = base.where(Notification.is_read == filters.is_read)
    # total is computed AFTER the is_read filter so the unread badge is honest.
    total = await db.scalar(select(func.count()).select_from(base.subquery()))
    rows = (
        await db.execute(
            base.order_by(Notification.created_at.desc(), Notification.id.desc())
            .offset((filters.page - 1) * filters.size)
            .limit(filters.size)
        )
    ).scalars().all()
    return PaginatedResponse[NotificationSchema](
        total=total or 0,
        page=filters.page,
        size=filters.size,
        items=[NotificationSchema.model_validate(r) for r in rows],
    )


# NOTE: /mark-all-read (one segment) and /{notification_id}/mark-read (two segments) never collide.
@router.post("/mark-all-read", status_code=status.HTTP_204_NO_CONTENT, responses={**_AUTH})
async def mark_all_read(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    await db.execute(
        update(Notification)
        .where(Notification.user_id == user.id, Notification.is_read.is_(False))
        .values(is_read=True)
    )
    await db.flush()   # idempotent: a second call updates zero rows


@router.post(
    "/{notification_id}/mark-read",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={**_AUTH, **_NOT_FOUND},
)
async def mark_read(
    notification_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    result = await db.execute(
        update(Notification)
        .where(Notification.id == notification_id, Notification.user_id == user.id)
        .values(is_read=True)
    )
    if result.rowcount == 0:   # not found OR not owned — uniform 404 (anti-enumeration)
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Notification not found")
    await db.flush()


@settings_router.get("", response_model=NotificationSettingsSchema, responses={**_AUTH})
async def get_notification_settings(
    user: User = Depends(get_current_user),
) -> NotificationSettingsSchema:
    return NotificationSettingsSchema.model_validate(user)


@settings_router.put("", response_model=NotificationSettingsSchema, responses={**_AUTH})
async def update_notification_settings(
    payload: NotificationSettingsSchema,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> NotificationSettingsSchema:
    user.watchlist_alerts_enabled = payload.watchlist_alerts_enabled
    await db.flush()
    return NotificationSettingsSchema.model_validate(user)
