# ABOUTME: F007 watchlist matcher — set-based match of enabled users' watchlists vs outstanding
# ABOUTME: contracts; dedup via a partial unique index (ON CONFLICT); defensive age-based prune.
import logging
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import Callable, Optional

import redis.asyncio as aioredis
from sqlalchemy import delete, func, or_, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config import Settings
from ..db import AsyncSessionLocal
from ..core.logging import get_logger, log_key_event
from ..models.account import Notification, WatchlistItem
from ..models.contracts import Contract, ContractItem
from ..models.user import User

logger = logging.getLogger(__name__)
slog = get_logger(__name__)

# Own lock key — never the aggregation lock (reusing it would mutually serialize the two jobs).
WATCHLIST_MATCH_LOCK_KEY = "hangar-bay:watchlist-match:lock"

# asyncpg caps a statement at 32767 bind params; ~7 params/row keeps 1000 comfortably safe.
NOTIFICATION_INSERT_CHUNK = 1000

# Compare-and-delete: release only if THIS runner still holds the token (guards TTL-expiry-then-reacquire).
_RELEASE_LOCK_LUA = (
    "if redis.call('get', KEYS[1]) == ARGV[1] then "
    "return redis.call('del', KEYS[1]) else return 0 end"
)

_SHIP_TYPE_LABELS = {"item_exchange": "an item exchange", "auction": "an auction"}


class ConcurrencyLockError(Exception):
    """Raised when the watchlist-match lock cannot be acquired (another run holds it)."""


def _render_message(type_name: str, contract_type: str, price, location: Optional[str]) -> str:
    # Price-honest: name the CONTRACT as the priced thing (bundle price), not the ship (design §4.4).
    label = _SHIP_TYPE_LABELS.get(contract_type, "a contract")
    where = location or "an unknown location"
    return f"{type_name} available in {label} priced {price:,.0f} ISK in {where}"


class WatchlistMatcherService:
    """Picklable (no live clients at rest) so RedisJobStore can persist the job — mirrors
    ContractAggregationService. `now_fn` stays None in production (a lambda would not pickle);
    tests inject a fixed clock for the retention boundary."""

    def __init__(self, settings: Settings, now_fn: Optional[Callable[[], datetime]] = None):
        self.settings = settings
        self.now_fn = now_fn

    def _now(self) -> datetime:
        return self.now_fn() if self.now_fn is not None else datetime.now(timezone.utc)

    @asynccontextmanager
    async def _concurrency_lock(self):
        redis_client = aioredis.from_url(str(self.settings.CACHE_URL))
        lock_token = uuid.uuid4().hex
        lock_acquired = False
        try:
            lock_acquired = await redis_client.set(
                WATCHLIST_MATCH_LOCK_KEY, lock_token,
                nx=True, ex=self.settings.WATCHLIST_MATCH_LOCK_TTL_SECONDS,
            )
            if not lock_acquired:
                raise ConcurrencyLockError("Could not acquire watchlist-match lock.")
            yield
        finally:
            if lock_acquired:
                released = await redis_client.eval(
                    _RELEASE_LOCK_LUA, 1, WATCHLIST_MATCH_LOCK_KEY, lock_token
                )
                if not released:
                    logger.warning(
                        "Watchlist-match lock token mismatch on release: the %ss TTL likely "
                        "expired mid-run and was reacquired by another runner. Leaving it intact.",
                        self.settings.WATCHLIST_MATCH_LOCK_TTL_SECONDS,
                    )
            await redis_client.close()

    async def run_matching(self) -> None:
        started = time.monotonic()
        matched = created = pruned = 0
        try:
            async with self._concurrency_lock():
                async with AsyncSessionLocal() as db_session:
                    matched, created = await self._match_and_notify(db_session)
                    pruned = await self._prune(db_session)
                    await db_session.commit()
        except ConcurrencyLockError:
            logger.info("Watchlist matcher skipped: lock held by another run.")
            return
        except Exception as e:  # noqa: BLE001 — job boundary: log, don't propagate to the scheduler
            log_key_event(
                slog, "watchlist_match_run", success=False,
                duration_ms=(time.monotonic() - started) * 1000, error_message=str(e),
            )
            logger.error("Watchlist matcher run failed: %s", e, exc_info=True)
            return
        log_key_event(
            slog, "watchlist_match_run", success=True,
            duration_ms=(time.monotonic() - started) * 1000,
            matches=matched, created=created, pruned=pruned,
        )

    async def _match_and_notify(self, db_session: AsyncSession) -> tuple[int, int]:
        # Set-based match: enabled users' watchlists vs OUTSTANDING item_exchange/auction contracts
        # carrying an INCLUDED item of the watched type_id, at or under the (optional) max_price.
        stmt = (
            select(
                WatchlistItem.user_id,
                WatchlistItem.type_id,
                WatchlistItem.type_name,
                Contract.contract_id,
                Contract.price,
                Contract.type,
                Contract.start_location_name,
            )
            .join(User, User.id == WatchlistItem.user_id)
            .join(ContractItem, ContractItem.type_id == WatchlistItem.type_id)
            .join(Contract, Contract.contract_id == ContractItem.contract_id)
            .where(
                User.watchlist_alerts_enabled.is_(True),
                ContractItem.is_included.is_(True),
                Contract.type.in_(("item_exchange", "auction")),
                Contract.date_expired > func.now(),
                Contract.date_completed.is_(None),
                or_(WatchlistItem.max_price.is_(None), Contract.price <= WatchlistItem.max_price),
            )
            .distinct()
        )
        rows = (await db_session.execute(stmt)).all()
        if not rows:
            return 0, 0

        payloads = [
            {
                "user_id": r.user_id,
                "type": "watchlist_match",
                "message": _render_message(r.type_name, r.type, r.price, r.start_location_name),
                "contract_id": r.contract_id,
                "watch_type_id": r.type_id,
                "price": r.price,
                "is_read": False,
            }
            for r in rows
        ]

        created = 0
        for start in range(0, len(payloads), NOTIFICATION_INSERT_CHUNK):
            chunk = payloads[start : start + NOTIFICATION_INSERT_CHUNK]
            # The conflict target MUST restate the partial-index predicate (index_where) or Postgres
            # raises "no unique or exclusion constraint matching the ON CONFLICT specification". The
            # predicate MUST be a literal identical to the index DDL: a parameterized predicate
            # compiles to `type = $1`, which Postgres's partial-index implication check cannot match
            # against the index's literal predicate, so inference can fail.
            stmt_ins = (
                pg_insert(Notification)
                .values(chunk)
                .on_conflict_do_nothing(
                    index_elements=["user_id", "contract_id", "watch_type_id"],
                    index_where=text("type = 'watchlist_match'"),
                )
                .returning(Notification.id)
            )
            result = await db_session.execute(stmt_ins)
            created += len(result.fetchall())
        return len(rows), created

    async def _prune(self, db_session: AsyncSession) -> int:
        cutoff = self._now() - timedelta(days=self.settings.NOTIFICATION_RETENTION_DAYS)
        outstanding = select(Contract.contract_id).where(
            Contract.contract_id == Notification.contract_id,
            Contract.date_expired > func.now(),
            Contract.date_completed.is_(None),
        )
        # Delete only aged rows whose target contract is no longer outstanding (no-resurrection guard).
        stmt = delete(Notification).where(
            Notification.created_at < cutoff,
            ~outstanding.exists(),
        )
        result = await db_session.execute(stmt)
        return result.rowcount
