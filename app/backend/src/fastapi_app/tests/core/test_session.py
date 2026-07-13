# ABOUTME: Session create/read/renew/cap/destroy against the fake Valkey with injected clocks.
# ABOUTME: Covers both FastAPI deps: get_current_session (401s) and get_optional_session (None).
import json

import pytest

from fastapi_app.core import session as sess
from fastapi_app.core.config import settings
from fastapi_app.tests.fake_redis import FakeRedis

IDLE = settings.SESSION_IDLE_TTL_SECONDS       # 604800
ABSOLUTE = settings.SESSION_ABSOLUTE_TTL_SECONDS  # 2592000


@pytest.mark.asyncio
async def test_create_then_read_renews_idle_window():
    r = FakeRedis()
    now = 1_000_000
    sid = await sess.create_session(r, user_id=1, character_id=91, character_name="X", now=now)
    key = f"session:{sid}"
    assert r.ttl_for(key) == IDLE
    # Degrade the TTL first so the post-read IDLE assertion observes the renewal
    # itself — straight after create it would hold even if read never renewed.
    await r.expire(key, 123)
    assert r.ttl_for(key) == 123
    payload = await sess.read_session(r, sid, now=now + 100)
    assert payload["character_id"] == 91
    assert payload["created_at"] == now
    assert r.ttl_for(key) == IDLE            # GETEX renewed the idle window


@pytest.mark.asyncio
async def test_read_caps_ttl_so_key_never_outlives_absolute_deadline():
    r = FakeRedis()
    created = 1_000_000
    sid = await sess.create_session(r, user_id=1, character_id=91, character_name="X", now=created)
    key = f"session:{sid}"
    # 100s before the 30-day deadline: renewal must cap at 100, not idle (604800).
    now = created + ABSOLUTE - 100
    payload = await sess.read_session(r, sid, now=now)
    assert payload is not None
    assert r.ttl_for(key) == 100


@pytest.mark.asyncio
async def test_read_over_absolute_cap_deletes_and_returns_none():
    r = FakeRedis()
    created = 1_000_000
    sid = await sess.create_session(r, user_id=1, character_id=91, character_name="X", now=created)
    key = f"session:{sid}"
    now = created + ABSOLUTE + 1     # one second past the hard cap
    assert await sess.read_session(r, sid, now=now) is None
    assert await r.exists(key) == 0  # over-cap session deleted in the same request


@pytest.mark.asyncio
async def test_read_exactly_at_absolute_cap_deletes_and_returns_none():
    r = FakeRedis()
    created = 1_000_000
    sid = await sess.create_session(r, user_id=1, character_id=91, character_name="X", now=created)
    key = f"session:{sid}"
    # Exactly at the deadline: session lifetime is [created, created+ABSOLUTE),
    # so now == deadline is already expired (pins the >= boundary).
    now = created + ABSOLUTE
    assert await sess.read_session(r, sid, now=now) is None
    assert await r.exists(key) == 0


@pytest.mark.asyncio
async def test_read_missing_returns_none():
    r = FakeRedis()
    assert await sess.read_session(r, "nope", now=1) is None


@pytest.mark.asyncio
async def test_destroy_deletes_the_key():
    r = FakeRedis()
    sid = await sess.create_session(r, user_id=1, character_id=91, character_name="X", now=1)
    await sess.destroy_session(r, sid)
    assert await r.exists(f"session:{sid}") == 0


@pytest.mark.asyncio
async def test_created_at_is_integer_epoch_seconds():
    r = FakeRedis()
    sid = await sess.create_session(r, user_id=1, character_id=91, character_name="X", now=1_700_000_000)
    stored = json.loads(r.store[f"session:{sid}"])
    assert stored["created_at"] == 1_700_000_000
    assert isinstance(stored["created_at"], int)


@pytest.mark.asyncio
async def test_get_current_session_401_without_cookie():
    from types import SimpleNamespace
    from fastapi import HTTPException
    r = FakeRedis()
    request = SimpleNamespace(cookies={}, app=SimpleNamespace(state=SimpleNamespace(redis=r)))
    with pytest.raises(HTTPException) as exc:
        await sess.get_current_session(request, redis=r)
    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_get_current_session_401_with_stale_cookie():
    # Cookie present but no matching session in Valkey (expired or bogus sid):
    # read_session returns None and the dependency must still 401.
    from types import SimpleNamespace
    from fastapi import HTTPException
    r = FakeRedis()
    request = SimpleNamespace(cookies={settings.SESSION_COOKIE_NAME: "bogus-sid"})
    with pytest.raises(HTTPException) as exc:
        await sess.get_current_session(request, redis=r)
    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_get_current_session_sources_redis_through_get_cache_which_503s():
    # Wiring assertion first: the dependency seam must BE get_cache (the shared
    # 503-when-cache-absent contract), not an ad-hoc redis source — asserting only
    # get_cache's own behavior would pass even if the session dep dropped the seam.
    import inspect
    from types import SimpleNamespace
    from fastapi import HTTPException
    from fastapi import params as fastapi_params
    from fastapi_app.core.dependencies import get_cache

    redis_param = inspect.signature(sess.get_current_session).parameters["redis"]
    assert isinstance(redis_param.default, fastapi_params.Depends)
    assert redis_param.default.dependency is get_cache

    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace()))
    with pytest.raises(HTTPException) as exc:
        await get_cache(request)
    assert exc.value.status_code == 503


@pytest.mark.asyncio
async def test_get_optional_session_none_without_cookie():
    from types import SimpleNamespace
    r = FakeRedis()
    request = SimpleNamespace(cookies={})
    assert await sess.get_optional_session(request, redis=r) is None


@pytest.mark.asyncio
async def test_get_optional_session_returns_payload_for_valid_cookie():
    import time
    from types import SimpleNamespace
    r = FakeRedis()
    # Real-clock now is fine here: only "created within the last 30 days" matters,
    # and expiry semantics are already pinned by read_session's injected-clock tests.
    sid = await sess.create_session(r, user_id=1, character_id=91, character_name="X", now=int(time.time()))
    request = SimpleNamespace(cookies={settings.SESSION_COOKIE_NAME: sid})
    payload = await sess.get_optional_session(request, redis=r)
    assert payload is not None and payload["character_id"] == 91
