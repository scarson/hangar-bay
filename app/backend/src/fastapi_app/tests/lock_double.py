# ABOUTME: Shared in-memory async Redis double for the concurrency-lock set/eval(CAD)/close path.
# ABOUTME: Used by both the aggregation-lock tests and the watchlist-matcher-lock tests.


class FakeLockRedis:
    """Minimal in-memory async Redis for the lock's set / eval(CAD) / close path."""

    def __init__(self, store: dict):
        self.store = store
        # Records the ex= (TTL seconds) each successful set carried, keyed like store —
        # lets tests assert on the mutual-exclusion window, not just key presence.
        self.set_ttls: dict = {}
        # Counts aclose() so a test can observe the client being closed. Nothing about
        # the lock KEY changes when the close is skipped, so a connection leaked once
        # per run — including on the run that never acquired the lock — is invisible to
        # every other assertion available here.
        self.aclose_calls = 0
        # Every operation in order. A close COUNT cannot see a close that happens too
        # early: redis-py reopens the connection for any command issued afterwards, so
        # closing and then releasing the lock leaves a live pooled connection behind
        # while the counter still reads one. Order is what distinguishes them.
        self.ops: list[str] = []

    async def set(self, key, value, nx=False, ex=None):
        self.ops.append("set")
        if nx and key in self.store:
            return None
        self.store[key] = value
        self.set_ttls[key] = ex
        return True

    async def get(self, key):
        self.ops.append("get")
        return self.store.get(key)

    async def eval(self, script, numkeys, *args):
        self.ops.append("eval")
        key, token = args[0], args[1]
        if self.store.get(key) == token:
            del self.store[key]
            return 1
        return 0

    async def aclose(self):
        self.ops.append("aclose")
        self.aclose_calls += 1
