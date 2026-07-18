# ABOUTME: get_current_user — the M3 auth backbone: resolves the session to a live users row and
# ABOUTME: verifies character_id, forcing re-login (destroy session + 401) on a missing/reassigned row (design §4.1).
from fastapi import Depends, HTTPException, Request, status
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_db
from ..models import User
from .config import get_settings
from .dependencies import get_cache
from .session import destroy_session, get_current_session


async def get_current_user(
    request: Request,
    session: dict = Depends(get_current_session),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_cache),
) -> User:
    user = (
        await db.execute(select(User).where(User.id == session["user_id"]))
    ).scalar_one_or_none()
    if user is None or user.character_id != session["character_id"]:
        # The row is gone (dev wipe) or the autoincrement id was reassigned to a different
        # character. Either way the stale session must not resolve to anyone — destroy it
        # (re-reading the sid from the request cookie, since the payload carries no sid) so the
        # browser cookie points at nothing and the next login replaces it (design §4.1 step 2).
        sid = request.cookies.get(get_settings().SESSION_COOKIE_NAME)
        if sid:
            await destroy_session(redis, sid)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return user
