# ABOUTME: Server-side Valkey sessions — sliding idle TTL + 30-day absolute cap (m2-eve-sso design spec §4.2; plan decision D4).
# ABOUTME: get_current_session 401s on absence; get_optional_session returns None.
import json
import secrets
import time
from typing import Optional

from fastapi import Depends, HTTPException, Request, status
from redis.asyncio import Redis

from .config import get_settings
from .dependencies import get_cache


def _session_key(sid: str) -> str:
    return f"session:{sid}"


async def create_session(
    redis: Redis,
    *,
    user_id: int,
    character_id: int,
    character_name: str,
    now: Optional[int] = None,
) -> str:
    s = get_settings()
    now = int(time.time()) if now is None else now
    sid = secrets.token_urlsafe(32)   # 256-bit, minted only post-auth (fixation defense)
    payload = {
        "user_id": user_id,
        "character_id": character_id,
        "character_name": character_name,
        "created_at": now,   # int Unix epoch seconds (UTC)
    }
    await redis.set(_session_key(sid), json.dumps(payload), ex=s.SESSION_IDLE_TTL_SECONDS)
    return sid


async def read_session(redis: Redis, sid: str, *, now: Optional[int] = None) -> Optional[dict]:
    s = get_settings()
    now = int(time.time()) if now is None else now
    key = _session_key(sid)
    raw = await redis.getex(key, ex=s.SESSION_IDLE_TTL_SECONDS)  # atomic read + idle renew (D4)
    if raw is None:
        return None
    payload = json.loads(raw)
    deadline = payload["created_at"] + s.SESSION_ABSOLUTE_TTL_SECONDS
    if now >= deadline:
        await redis.delete(key)   # over the 30-day cap: delete in the same request
        return None
    remaining = deadline - now
    if remaining < s.SESSION_IDLE_TTL_SECONDS:
        await redis.expire(key, remaining)  # never outlive the absolute cap
    return payload


async def destroy_session(redis: Redis, sid: str) -> None:
    await redis.delete(_session_key(sid))


async def get_current_session(request: Request, redis: Redis = Depends(get_cache)) -> dict:
    sid = request.cookies.get(get_settings().SESSION_COOKIE_NAME)
    if not sid:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    payload = await read_session(redis, sid)
    if payload is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return payload


async def get_optional_session(request: Request, redis: Redis = Depends(get_cache)) -> Optional[dict]:
    sid = request.cookies.get(get_settings().SESSION_COOKIE_NAME)
    if not sid:
        return None
    return await read_session(redis, sid)
