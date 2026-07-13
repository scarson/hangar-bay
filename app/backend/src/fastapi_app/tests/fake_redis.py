# ABOUTME: In-memory async Valkey double for session + SSO-state tests (decode_responses=True).
# ABOUTME: Extends the _FakeLockRedis precedent with get/set(ex)/getex/getdel/delete/exists + TTL.
from typing import Dict, Optional


class FakeRedis:
    """Minimal async Valkey. Values are str (house pattern: decode_responses=True).

    Deliberately mirrors real Redis semantics: SET without EX makes the key
    persistent (any recorded TTL is cleared), and EXPIRE with ttl <= 0 deletes the key.
    """

    def __init__(self) -> None:
        self.store: Dict[str, str] = {}
        self.ttls: Dict[str, int] = {}   # last-set TTL per key, for test assertions

    async def get(self, key: str) -> Optional[str]:
        return self.store.get(key)

    async def set(self, key: str, value: str, ex: Optional[int] = None, nx: bool = False):
        if nx and key in self.store:
            return None
        self.store[key] = value
        if ex is not None:
            self.ttls[key] = ex
        else:
            self.ttls.pop(key, None)
        return True

    async def getex(self, key: str, ex: Optional[int] = None) -> Optional[str]:
        value = self.store.get(key)
        if value is not None and ex is not None:
            self.ttls[key] = ex
        return value

    async def getdel(self, key: str) -> Optional[str]:
        self.ttls.pop(key, None)
        return self.store.pop(key, None)   # atomic single-use consume

    async def expire(self, key: str, ttl: int) -> bool:
        if key in self.store:
            if ttl <= 0:
                del self.store[key]
                self.ttls.pop(key, None)
                return True
            self.ttls[key] = ttl
            return True
        return False

    async def delete(self, *keys: str) -> int:
        removed = 0
        for key in keys:
            if key in self.store:
                del self.store[key]
                self.ttls.pop(key, None)
                removed += 1
        return removed

    async def exists(self, key: str) -> int:
        return 1 if key in self.store else 0

    def ttl_for(self, key: str) -> Optional[int]:
        """Test-only introspection of the last-applied TTL."""
        return self.ttls.get(key)
