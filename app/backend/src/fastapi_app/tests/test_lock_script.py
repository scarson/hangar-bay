# ABOUTME: Runs the REAL compare-and-delete Lua release script against a live cache.
# ABOUTME: The shared FakeLockRedis reimplements it in Python, so the source never executed.

import uuid

import pytest
import redis.asyncio as aioredis

import fastapi_app.services.background_aggregation as bg_agg
import fastapi_app.services.watchlist_matcher as wm
from fastapi_app.core.config import settings

pytestmark = pytest.mark.asyncio


@pytest.mark.parametrize(
    "script, label",
    [
        (bg_agg._RELEASE_LOCK_LUA, "aggregation"),
        (wm._RELEASE_LOCK_LUA, "watchlist-matcher"),
    ],
)
async def test_the_release_lock_script_compares_and_deletes_on_a_real_cache(
    script: str, label: str
):
    """Both locks release through a Lua compare-and-delete, and neither script had ever
    been executed by a test.

    Every lock test drives `FakeLockRedis.eval`, which reimplements the compare-and-
    delete in Python. The double's semantics match, so the tests are meaningful about
    the CALLERS — but the Lua source itself is only ever passed through as an opaque
    string. A KEYS[1]/ARGV[1] swap, or any typo, keeps every one of those tests green
    while release either silently stops working or (worse) deletes another runner's
    lock. Running the real script against a real cache is the only thing that can tell.

    The two modules hold separate constants with identical text, so both are exercised;
    a divergence in either is caught here rather than in production.
    """
    client = aioredis.from_url(str(settings.CACHE_URL_TESTS or settings.CACHE_URL))
    # Unique per run: CACHE_URL_TESTS is unset in CI, so this falls back to the shared
    # application cache, where a fixed key would let two concurrent runs (or a parallel
    # worktree) observe each other's writes and delete each other's fixture on cleanup.
    key = f"hangar-bay:test:release-lock-script:{label}:{uuid.uuid4().hex}"
    try:
        # TTL as a backstop to the finally: a unique key is unrecoverable by any later
        # run, so a worker killed mid-test would otherwise strand it in the shared cache
        # forever. Far longer than the test, short enough to self-clean.
        await client.set(key, "our-token", ex=60)

        # Another runner's token: refuse, report 0, and leave THEIR value intact. This
        # is the arm that matters — an unconditional DEL here cascades concurrent runs.
        assert await client.eval(script, 1, key, "another-runners-token") == 0
        assert await client.get(key) == b"our-token"

        # Our own token: delete, and report that it did.
        assert await client.eval(script, 1, key, "our-token") == 1
        assert await client.get(key) is None
    finally:
        # Nested so a failing delete cannot skip the connection close.
        try:
            await client.delete(key)
        finally:
            await client.aclose()
