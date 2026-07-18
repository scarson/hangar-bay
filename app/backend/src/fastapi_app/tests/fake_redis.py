# ABOUTME: In-memory async Valkey double for session + SSO-state tests (decode_responses=True).
# ABOUTME: Extends the _FakeLockRedis precedent with get/set(ex)/getex/getdel/delete/exists + TTL.
import time as _time_module
from typing import Callable, Dict, Optional, Union


class FakeRedis:
    """Minimal async Valkey. Values are str (house pattern: decode_responses=True).

    Deliberately mirrors real Redis semantics: SET without EX makes the key
    persistent (any recorded TTL is cleared), and EXPIRE with ttl <= 0 deletes the key.

    TTL is honored for real: a key past its absolute expiry reads as absent on
    get/getex/getdel/exists, purged lazily on access. The clock is injectable (any
    zero-arg callable returning epoch seconds) so tests can simulate time passing
    without real sleeps; it defaults to time.time for callers that don't care.
    """

    def __init__(self, *, clock: Optional[Callable[[], float]] = None) -> None:
        self.store: Dict[str, str] = {}
        self.ttls: Dict[str, int] = {}   # last-set TTL per key, for test assertions
        self.expires_at: Dict[str, float] = {}  # absolute expiry (epoch seconds), honored on read
        self._clock: Callable[[], float] = clock or _time_module.time

    def _now(self) -> float:
        return self._clock()

    def _purge_if_expired(self, key: str) -> None:
        deadline = self.expires_at.get(key)
        if deadline is not None and self._now() >= deadline:
            self.store.pop(key, None)
            self.ttls.pop(key, None)
            self.expires_at.pop(key, None)

    def _set_relative_ttl(self, key: str, ttl: int) -> None:
        self.ttls[key] = ttl
        self.expires_at[key] = self._now() + ttl

    async def get(self, key: str) -> Optional[str]:
        self._purge_if_expired(key)
        return self.store.get(key)

    async def set(self, key: str, value: str, ex: Optional[int] = None, nx: bool = False):
        self._purge_if_expired(key)
        if nx and key in self.store:
            return None
        self.store[key] = value
        if ex is not None:
            self._set_relative_ttl(key, ex)
        else:
            self.ttls.pop(key, None)
            self.expires_at.pop(key, None)
        return True

    async def getex(self, key: str, ex: Optional[int] = None) -> Optional[str]:
        self._purge_if_expired(key)
        value = self.store.get(key)
        if value is not None and ex is not None:
            self._set_relative_ttl(key, ex)
        return value

    async def getdel(self, key: str) -> Optional[str]:
        self._purge_if_expired(key)
        self.ttls.pop(key, None)
        self.expires_at.pop(key, None)
        return self.store.pop(key, None)   # atomic single-use consume

    async def expire(self, key: str, ttl: int) -> bool:
        self._purge_if_expired(key)
        if key in self.store:
            if ttl <= 0:
                del self.store[key]
                self.ttls.pop(key, None)
                self.expires_at.pop(key, None)
                return True
            self._set_relative_ttl(key, ttl)
            return True
        return False

    async def expireat(self, key: str, when: Union[int, float]) -> bool:
        """Absolute-deadline expiry (race-free vs. a relative EXPIRE computed
        against a stale `now`captured before an earlier await — see session.py's
        read path). `when` is an epoch-seconds timestamp, matching redis-py's
        int/datetime `when` param (datetimes aren't accepted here; callers pass ints)."""
        self._purge_if_expired(key)
        if key not in self.store:
            return False
        if when <= self._now():
            del self.store[key]
            self.ttls.pop(key, None)
            self.expires_at.pop(key, None)
            return True
        self.expires_at[key] = when
        self.ttls[key] = int(when - self._now())
        return True

    async def delete(self, *keys: str) -> int:
        removed = 0
        for key in keys:
            self._purge_if_expired(key)
            if key in self.store:
                del self.store[key]
                self.ttls.pop(key, None)
                self.expires_at.pop(key, None)
                removed += 1
        return removed

    async def exists(self, key: str) -> int:
        self._purge_if_expired(key)
        return 1 if key in self.store else 0

    def ttl_for(self, key: str) -> Optional[int]:
        """Test-only introspection of the last-applied TTL."""
        self._purge_if_expired(key)
        return self.ttls.get(key)
