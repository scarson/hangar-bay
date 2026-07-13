# ABOUTME: FakeRedis must honor TTL for real (a key past its expiry reads as absent)
# ABOUTME: so idle-expiration and post-expiry session behavior can be tested honestly.
import pytest

from fastapi_app.tests.fake_redis import FakeRedis


class _Clock:
    """Mutable fake clock: tests advance `.t` to simulate wall-time passing."""

    def __init__(self, start: float = 0.0):
        self.t = start

    def __call__(self) -> float:
        return self.t


@pytest.mark.asyncio
async def test_get_returns_none_after_ttl_expiry():
    clock = _Clock(1000.0)
    r = FakeRedis(clock=clock)
    await r.set("k", "v", ex=10)
    assert await r.get("k") == "v"
    clock.t = 1000.0 + 10  # exactly at expiry: already expired
    assert await r.get("k") is None


@pytest.mark.asyncio
async def test_get_returns_value_before_ttl_expiry():
    clock = _Clock(1000.0)
    r = FakeRedis(clock=clock)
    await r.set("k", "v", ex=10)
    clock.t = 1000.0 + 9
    assert await r.get("k") == "v"


@pytest.mark.asyncio
async def test_getex_returns_none_after_ttl_expiry():
    clock = _Clock(0.0)
    r = FakeRedis(clock=clock)
    await r.set("k", "v", ex=5)
    clock.t = 5.001
    assert await r.getex("k", ex=5) is None


@pytest.mark.asyncio
async def test_exists_is_false_after_ttl_expiry():
    clock = _Clock(0.0)
    r = FakeRedis(clock=clock)
    await r.set("k", "v", ex=5)
    clock.t = 6.0
    assert await r.exists("k") == 0


@pytest.mark.asyncio
async def test_getdel_returns_none_after_ttl_expiry():
    clock = _Clock(0.0)
    r = FakeRedis(clock=clock)
    await r.set("k", "v", ex=5)
    clock.t = 6.0
    assert await r.getdel("k") is None


@pytest.mark.asyncio
async def test_getex_renewal_extends_past_previous_deadline():
    # A GETEX before the old deadline renews the idle window from the current
    # clock, not the original set() time.
    clock = _Clock(0.0)
    r = FakeRedis(clock=clock)
    await r.set("k", "v", ex=5)
    clock.t = 4.0
    assert await r.getex("k", ex=5) == "v"   # renew: new deadline is 4.0 + 5 = 9.0
    clock.t = 8.9
    assert await r.get("k") == "v"           # still alive past the ORIGINAL 5s deadline
    clock.t = 9.1
    assert await r.get("k") is None          # but not past the RENEWED deadline


@pytest.mark.asyncio
async def test_persistent_set_without_ex_never_expires():
    clock = _Clock(0.0)
    r = FakeRedis(clock=clock)
    await r.set("k", "v")
    clock.t = 10_000_000.0
    assert await r.get("k") == "v"


@pytest.mark.asyncio
async def test_expireat_sets_absolute_deadline():
    clock = _Clock(100.0)
    r = FakeRedis(clock=clock)
    await r.set("k", "v", ex=5)   # relative deadline would be 105
    await r.expireat("k", 200)    # override with an absolute deadline far later
    clock.t = 150.0
    assert await r.get("k") == "v"
    clock.t = 200.0
    assert await r.get("k") is None   # expireat deadline reached


@pytest.mark.asyncio
async def test_expireat_in_the_past_deletes_immediately():
    clock = _Clock(100.0)
    r = FakeRedis(clock=clock)
    await r.set("k", "v")
    await r.expireat("k", 50)   # already in the past relative to clock
    assert await r.get("k") is None
    assert await r.exists("k") == 0


@pytest.mark.asyncio
async def test_expireat_on_missing_key_returns_false():
    r = FakeRedis(clock=_Clock(0.0))
    assert await r.expireat("nope", 100) is False


@pytest.mark.asyncio
async def test_default_clock_is_real_time_and_does_not_immediately_expire():
    # No clock passed: defaults to real wall time. A key set with a real TTL must
    # still be readable immediately after (regression guard against a fixed t=0
    # default clock that would make everything look pre-expired).
    r = FakeRedis()
    await r.set("k", "v", ex=60)
    assert await r.get("k") == "v"
