# ABOUTME: Shared in-memory async Redis double for the concurrency-lock set/eval(CAD)/close path.
# ABOUTME: Used by both the aggregation-lock tests and the watchlist-matcher-lock tests.


class FakeLockRedis:
    """Minimal in-memory async Redis for the lock's set / eval(CAD) / close path."""

    def __init__(self, store: dict):
        self.store = store

    async def set(self, key, value, nx=False, ex=None):
        if nx and key in self.store:
            return None
        self.store[key] = value
        return True

    async def get(self, key):
        return self.store.get(key)

    async def eval(self, script, numkeys, *args):
        key, token = args[0], args[1]
        if self.store.get(key) == token:
            del self.store[key]
            return 1
        return 0

    async def close(self):
        pass
