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


def _is_plain_int(value: object) -> bool:
    """True ints only — bool is an int subclass in Python and JSON true/false
    must not silently pass as a timestamp/id."""
    return isinstance(value, int) and not isinstance(value, bool)


def _parse_session_payload(raw: str) -> Optional[dict]:
    """Decode + shape-validate a stored session payload. Returns None for anything
    undecodable or malformed — truncated JSON, a non-object document, or one
    missing/mistyping the fields read_session and downstream consumers (get_
    current_session, /me) rely on — so the caller can treat it as an absent
    session (DEL + None) instead of a raw exception reaching the callback/route
    as a 500."""
    try:
        payload = json.loads(raw)
    except (json.JSONDecodeError, TypeError, ValueError):
        return None
    if not isinstance(payload, dict):
        return None
    if not _is_plain_int(payload.get("created_at")):
        return None
    if not _is_plain_int(payload.get("user_id")):
        return None
    if not _is_plain_int(payload.get("character_id")):
        return None
    if not isinstance(payload.get("character_name"), str):
        return None
    return payload


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
    key = _session_key(sid)
    raw = await redis.getex(key, ex=s.SESSION_IDLE_TTL_SECONDS)  # atomic read + idle renew (D4)
    # Capture the clock AFTER the GETEX round-trip (not before), so the deadline check
    # and the absolute EXPIREAT below reflect the time the renewal actually landed —
    # never a pre-await `now` that command latency could have left stale. An injected
    # `now` (tests) is used verbatim for determinism.
    now = int(time.time()) if now is None else now
    if raw is None:
        return None
    payload = _parse_session_payload(raw)
    if payload is None:
        await redis.delete(key)   # corrupt/malformed payload: treat as absent, never 500
        return None
    deadline = payload["created_at"] + s.SESSION_ABSOLUTE_TTL_SECONDS
    if now >= deadline:
        await redis.delete(key)   # over the 30-day cap: delete in the same request
        return None
    # Always apply an ABSOLUTE EXPIREAT at min(sliding idle window, deadline), never
    # a conditional relative EXPIRE. The GETEX above renewed the key RELATIVE to the
    # command's own (server-side) execution time, which can be later than the `now`
    # captured before the await; a cap gated on that stale `now` can be skipped even
    # though the renewal actually lands past the deadline (§7). EXPIREAT at an
    # absolute timestamp is immune to that latency: it caps at `deadline` when near
    # it, and slides at `now + idle_ttl` otherwise, so the key can never be
    # scheduled to outlive the 30-day deadline regardless of command latency.
    #
    # ACCEPTED TRADEOFF (spec §4.2 / D4, sanctioned two-command read): GETEX and this
    # EXPIREAT are two separate commands, not one atomic op — a single capped-renew is
    # impossible because the cap needs `created_at`, which lives inside the value being
    # read. So two bounded, non-security edges remain: (a) a crash/cancel between GETEX
    # and EXPIREAT can leave the key stored up to idle_ttl past `deadline`, and
    # (b) concurrent reads can move the idle expiry a few seconds. NEITHER serves an
    # over-cap session — the `now >= deadline` check above (keyed on `created_at`) is the
    # authoritative boundary and rejects+deletes any expired session on read, whatever
    # the physical key TTL. Closing these fully needs a Lua/EVAL atomic read-and-capped-
    # renew; deferred to M3 as a session-store enhancement, out of scope for M2.
    await redis.expireat(key, min(now + s.SESSION_IDLE_TTL_SECONDS, deadline))
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
