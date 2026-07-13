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
    # Injected clock in lockstep with the business timestamps: read_session now
    # applies an ABSOLUTE EXPIREAT(min(now + idle_ttl, deadline)), so the fake's
    # own clock must share the timeline of `now`/`created` for the renewal to land
    # where expected (a real-wall-clock fake with a 1970-era injected now would put
    # the absolute deadline in the distant past and purge the key immediately).
    now = 1_000_000
    clock = {"t": float(now)}
    r = FakeRedis(clock=lambda: clock["t"])
    sid = await sess.create_session(r, user_id=1, character_id=91, character_name="X", now=now)
    key = f"session:{sid}"
    assert r.ttl_for(key) == IDLE
    # Degrade the TTL first so the post-read IDLE assertion observes the renewal
    # itself — straight after create it would hold even if read never renewed.
    await r.expire(key, 123)
    assert r.ttl_for(key) == 123
    clock["t"] = float(now + 100)
    payload = await sess.read_session(r, sid, now=now + 100)
    assert payload["character_id"] == 91
    assert payload["created_at"] == now
    assert r.ttl_for(key) == IDLE            # read renewed the idle window (min(now+idle, deadline) == now+idle)


@pytest.mark.asyncio
async def test_read_caps_ttl_so_key_never_outlives_absolute_deadline():
    # Injected clock kept in lockstep with the business `now`/`created` values:
    # the cap step now applies an ABSOLUTE EXPIREAT(deadline) (§7), so ttl_for's
    # introspection (when - fake-clock-now) is only meaningful if the fake's own
    # clock shares the same timeline as the business timestamps under test.
    created = 1_000_000
    clock = {"t": float(created)}
    r = FakeRedis(clock=lambda: clock["t"])
    sid = await sess.create_session(r, user_id=1, character_id=91, character_name="X", now=created)
    key = f"session:{sid}"
    # 100s before the 30-day deadline: renewal must cap at 100, not idle (604800).
    # Pin the fake's TTL bookkeeping to "freshly renewed" before the jump — this
    # test is about the cap-application step, not about surviving ~30 days of
    # simulated time with zero intervening renewals (a real deployment renews on
    # every request; see test_idle_expiry_actually_expires_key_when_never_renewed
    # for the honest idle-lapse case).
    now = created + ABSOLUTE - 100
    r.expires_at[key] = now + 10_000
    clock["t"] = float(now)
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
async def test_read_malformed_json_payload_is_treated_as_absent():
    # Finding 6: a truncated/undecodable value must not 500 read_session — it
    # must be treated the same as "no session" (and the corrupt key purged).
    r = FakeRedis()
    key = "session:bad-sid"
    r.store[key] = "{not valid json"
    assert await sess.read_session(r, "bad-sid", now=1) is None
    assert await r.exists(key) == 0


@pytest.mark.asyncio
async def test_read_non_object_json_payload_is_treated_as_absent():
    r = FakeRedis()
    key = "session:bad-sid"
    r.store[key] = json.dumps(["not", "an", "object"])
    assert await sess.read_session(r, "bad-sid", now=1) is None
    assert await r.exists(key) == 0


@pytest.mark.asyncio
async def test_read_payload_missing_created_at_is_treated_as_absent():
    r = FakeRedis()
    key = "session:bad-sid"
    r.store[key] = json.dumps({"user_id": 1, "character_id": 91, "character_name": "X"})
    assert await sess.read_session(r, "bad-sid", now=1) is None
    assert await r.exists(key) == 0


@pytest.mark.asyncio
async def test_read_payload_with_non_int_created_at_is_treated_as_absent():
    r = FakeRedis()
    key = "session:bad-sid"
    r.store[key] = json.dumps(
        {"user_id": 1, "character_id": 91, "character_name": "X", "created_at": "not-a-number"}
    )
    assert await sess.read_session(r, "bad-sid", now=1) is None
    assert await r.exists(key) == 0


@pytest.mark.asyncio
async def test_get_current_session_401s_on_corrupt_payload():
    from types import SimpleNamespace
    from fastapi import HTTPException
    r = FakeRedis()
    key = "session:bad-sid"
    r.store[key] = "{not valid json"
    request = SimpleNamespace(cookies={settings.SESSION_COOKIE_NAME: "bad-sid"})
    with pytest.raises(HTTPException) as exc:
        await sess.get_current_session(request, redis=r)
    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_get_optional_session_none_on_corrupt_payload():
    from types import SimpleNamespace
    r = FakeRedis()
    key = "session:bad-sid"
    r.store[key] = "{not valid json"
    request = SimpleNamespace(cookies={settings.SESSION_COOKIE_NAME: "bad-sid"})
    assert await sess.get_optional_session(request, redis=r) is None


@pytest.mark.asyncio
async def test_read_caps_ttl_with_absolute_expireat_immune_to_command_latency():
    # Finding 7: the old code captured `now` before GETEX, then applied a
    # RELATIVE EXPIRE(deadline-now) after another await — so if wall time moves
    # between that captured `now` and the EXPIRE actually landing (a concurrent
    # request, GC pause, network latency...), the key's real expiry drifts PAST
    # the 30-day absolute deadline. An absolute EXPIREAT(deadline) is immune to
    # this: it lands at exactly `deadline` no matter how much latency elapsed.
    clock = {"t": 0.0}
    r = FakeRedis(clock=lambda: clock["t"])
    created = 1_000_000
    clock["t"] = float(created)
    sid = await sess.create_session(r, user_id=1, character_id=91, character_name="X", now=created)
    key = f"session:{sid}"

    now = created + ABSOLUTE - 100   # 100s from the hard cap: renewal must cap
    LATENCY = 30
    # Only the cap-application step is under test here, so pin the key's fake-TTL
    # bookkeeping to "freshly renewed" first — otherwise fast-forwarding the clock
    # this far in one jump would also trip the (unrelated, and itself correct as
    # of finding 9) idle-TTL purge before the cap logic ever runs.
    r.expires_at[key] = now + LATENCY + 10_000
    # Simulate the command reaching the fake's clock LATENCY seconds after the
    # caller's captured `now` — the exact gap a relative EXPIRE mis-handles.
    clock["t"] = now + LATENCY
    payload = await sess.read_session(r, sid, now=now)
    assert payload is not None
    deadline = created + ABSOLUTE
    assert r.expires_at[key] == deadline   # exact — not deadline + LATENCY


@pytest.mark.asyncio
async def test_read_idle_renewal_cannot_outlive_deadline_under_latency():
    # Finding 3: the EXPIREAT cap was CONDITIONAL on the stale pre-GETEX `now`.
    # When the session is not near its deadline at that captured `now`
    # (deadline - now >= idle_ttl, so the old `< idle_ttl` branch was skipped),
    # GETEX's RELATIVE idle renewal still lands at getex_time + idle_ttl — which,
    # under command latency (getex_time > captured now), can cross the 30-day
    # absolute deadline with no cap ever applied. The key must NEVER be scheduled
    # to expire after the absolute deadline, regardless of latency.
    clock = {"t": 0.0}
    r = FakeRedis(clock=lambda: clock["t"])
    created = 1_000_000
    clock["t"] = float(created)
    sid = await sess.create_session(r, user_id=1, character_id=91, character_name="X", now=created)
    key = f"session:{sid}"
    deadline = created + ABSOLUTE

    # Captured now EXACTLY idle_ttl before the deadline: deadline - now == idle_ttl,
    # so the old conditional `deadline - now < idle_ttl` is False and skips the cap.
    now = deadline - IDLE
    LATENCY = 30
    # Pin the key freshly-renewed so it is still alive at read time (a real session
    # this close to its deadline has been renewed on every prior request).
    r.expires_at[key] = now + LATENCY + 1000
    # GETEX executes LATENCY seconds after the captured `now`.
    clock["t"] = now + LATENCY
    payload = await sess.read_session(r, sid, now=now)
    assert payload is not None
    assert r.expires_at[key] <= deadline   # capped — not (now+LATENCY)+IDLE == deadline+LATENCY


@pytest.mark.asyncio
async def test_idle_expiry_actually_expires_key_when_never_renewed():
    # Finding 9 follow-through: FakeRedis previously never expired keys, so this
    # scenario (idle TTL lapses with zero renewing reads in between) could not be
    # exercised honestly — read_session would still "succeed" via a stale GETEX.
    clock = {"t": 1_000_000.0}
    r = FakeRedis(clock=lambda: clock["t"])
    sid = await sess.create_session(r, user_id=1, character_id=91, character_name="X", now=int(clock["t"]))
    clock["t"] += IDLE + 1   # idle window lapsed with no intervening renewal
    assert await sess.read_session(r, sid, now=int(clock["t"])) is None


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
