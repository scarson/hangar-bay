# ABOUTME: Service-level tests for WatchlistMatcherService (F007 matcher) — the design §6 matcher matrix.
# ABOUTME: Inner methods take the test db_session directly (run_matching builds its own engine, §6).
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

import fastapi_app.services.watchlist_matcher as wm
from fastapi_app.models import Contract, ContractItem, Notification, User, WatchlistItem
from fastapi_app.services.watchlist_matcher import (
    ConcurrencyLockError,
    WatchlistMatcherService,
)
from fastapi_app.tests.lock_double import FakeLockRedis

pytestmark = pytest.mark.asyncio

NOW = datetime(2026, 7, 10, 12, 0, 0, tzinfo=timezone.utc)


def _settings():
    s = MagicMock()
    s.NOTIFICATION_RETENTION_DAYS = 90
    s.WATCHLIST_MATCH_LOCK_TTL_SECONDS = 900
    s.DATABASE_URL = "postgresql+asyncpg://unused/unused"
    s.CACHE_URL = "redis://unused"
    return s


def _service(now=None):
    return WatchlistMatcherService(settings=_settings(), now_fn=(lambda: now) if now else None)


async def _user(db, *, enabled=True, cid=91000001):
    u = User(character_id=cid, character_name="Pilot", owner_hash=f"OWN{cid}",
             watchlist_alerts_enabled=enabled)
    db.add(u)
    await db.flush()
    return u


async def _contract(db, *, cid, price, ctype="auction", expired_in_days=7, completed=False,
                    location="Jita IV - Moon 4"):
    c = Contract(
        contract_id=cid, title="t", price=price, collateral=0, status="unknown", type=ctype,
        issuer_id=1, issuer_corporation_id=1, start_location_id=60003760,
        start_location_region_id=10000002, for_corporation=False,
        date_issued=datetime.now(timezone.utc) - timedelta(days=1),
        date_expired=datetime.now(timezone.utc) + timedelta(days=expired_in_days),
        date_completed=(datetime.now(timezone.utc) if completed else None),
        start_location_name=location,
    )
    db.add(c)
    await db.flush()
    return c


async def _item(db, *, cid, type_id, is_included=True, record_id=None):
    it = ContractItem(record_id=record_id or (cid * 10 + type_id) % 10_000_000, contract_id=cid,
                      type_id=type_id, quantity=1, is_included=is_included, is_singleton=False)
    db.add(it)
    await db.flush()
    return it


async def _watch(db, user, *, type_id, type_name="Caracal", max_price=None):
    w = WatchlistItem(user_id=user.id, type_id=type_id, type_name=type_name, max_price=max_price)
    db.add(w)
    await db.flush()
    return w


# ---------- happy match + price-honest message ----------

async def test_match_creates_price_honest_notification(db_session: AsyncSession):
    u = await _user(db_session)
    await _watch(db_session, u, type_id=621, type_name="Caracal", max_price=20_000_000)
    await _contract(db_session, cid=5001, price=10_500_000, ctype="auction", location="Jita IV - Moon 4")
    await _item(db_session, cid=5001, type_id=621)

    matched, created = await _service()._match_and_notify(db_session)
    assert matched == 1 and created == 1
    note = (await db_session.execute(select(Notification))).scalar_one()
    assert note.watch_type_id == 621
    assert note.contract_id == 5001
    assert note.message == "Caracal available in an auction priced 10,500,000 ISK in Jita IV - Moon 4"


# ---------- idempotency: first run N>0, second run zero ----------

async def test_second_run_creates_zero(db_session: AsyncSession):
    u = await _user(db_session)
    await _watch(db_session, u, type_id=621, max_price=None)
    await _contract(db_session, cid=5002, price=1_000_000)
    await _item(db_session, cid=5002, type_id=621)
    svc = _service()
    _, created1 = await svc._match_and_notify(db_session)
    _, created2 = await svc._match_and_notify(db_session)
    assert created1 == 1
    assert created2 == 0   # ON CONFLICT DO NOTHING against the partial unique index
    assert (await db_session.scalar(select(func.count()).select_from(Notification))) == 1


# ---------- the partial unique index binds (needs index_where) ----------

async def test_dedup_partial_index_binds(db_session: AsyncSession):
    u = await _user(db_session)
    row = dict(user_id=u.id, type="watchlist_match", message="m", contract_id=7001,
               watch_type_id=621, price=1, is_read=False)
    db_session.add(Notification(**row))
    await db_session.flush()
    # A second insert with the SAME (user_id, contract_id, watch_type_id) must no-op — which only
    # works if the ON CONFLICT restates the partial-index predicate (index_where).
    stmt = pg_insert(Notification).values(**row).on_conflict_do_nothing(
        index_elements=["user_id", "contract_id", "watch_type_id"],
        index_where=text("type = 'watchlist_match'"),
    )
    await db_session.execute(stmt)
    assert (await db_session.scalar(select(func.count()).select_from(Notification))) == 1


# ---------- chunk boundary ----------

async def test_insert_crosses_chunk_boundary(db_session: AsyncSession, monkeypatch):
    monkeypatch.setattr(wm, "NOTIFICATION_INSERT_CHUNK", 2)
    u = await _user(db_session)
    await _watch(db_session, u, type_id=621, max_price=None)
    for cid in (6001, 6002, 6003):
        await _contract(db_session, cid=cid, price=1_000_000)
        await _item(db_session, cid=cid, type_id=621)
    _, created = await _service()._match_and_notify(db_session)
    assert created == 3
    assert (await db_session.scalar(select(func.count()).select_from(Notification))) == 3


# ---------- bundle-price semantics (whole-contract price) ----------

async def test_bundle_above_max_no_notification(db_session: AsyncSession):
    u = await _user(db_session)
    await _watch(db_session, u, type_id=621, max_price=5_000_000)
    await _contract(db_session, cid=6100, price=9_000_000)   # ship + extra item, bundle over max
    await _item(db_session, cid=6100, type_id=621)
    await _item(db_session, cid=6100, type_id=34, record_id=61001)
    _, created = await _service()._match_and_notify(db_session)
    assert created == 0


async def test_bundle_under_max_notifies_at_bundle_price(db_session: AsyncSession):
    u = await _user(db_session)
    await _watch(db_session, u, type_id=621, max_price=5_000_000)
    await _contract(db_session, cid=6101, price=4_000_000)
    await _item(db_session, cid=6101, type_id=621)
    await _item(db_session, cid=6101, type_id=34, record_id=61011)
    _, created = await _service()._match_and_notify(db_session)
    assert created == 1
    note = (await db_session.execute(select(Notification))).scalar_one()
    assert note.price == 4_000_000


# ---------- price boundary ==/> ----------

async def test_price_equal_to_max_matches(db_session: AsyncSession):
    u = await _user(db_session)
    await _watch(db_session, u, type_id=621, max_price=1_000_000)
    await _contract(db_session, cid=6200, price=1_000_000)
    await _item(db_session, cid=6200, type_id=621)
    _, created = await _service()._match_and_notify(db_session)
    assert created == 1


async def test_price_above_max_excluded(db_session: AsyncSession):
    u = await _user(db_session)
    await _watch(db_session, u, type_id=621, max_price=1_000_000)
    await _contract(db_session, cid=6201, price=1_000_001)
    await _item(db_session, cid=6201, type_id=621)
    _, created = await _service()._match_and_notify(db_session)
    assert created == 0


# ---------- date gates + is_included + disabled alerts ----------

async def test_expired_contract_excluded(db_session: AsyncSession):
    u = await _user(db_session)
    await _watch(db_session, u, type_id=621, max_price=None)
    await _contract(db_session, cid=6300, price=1, expired_in_days=-1)   # already expired
    await _item(db_session, cid=6300, type_id=621)
    _, created = await _service()._match_and_notify(db_session)
    assert created == 0


async def test_completed_contract_excluded(db_session: AsyncSession):
    u = await _user(db_session)
    await _watch(db_session, u, type_id=621, max_price=None)
    await _contract(db_session, cid=6301, price=1, completed=True)
    await _item(db_session, cid=6301, type_id=621)
    _, created = await _service()._match_and_notify(db_session)
    assert created == 0


async def test_requested_item_excluded(db_session: AsyncSession):
    u = await _user(db_session)
    await _watch(db_session, u, type_id=621, max_price=None)
    await _contract(db_session, cid=6302, price=1)
    await _item(db_session, cid=6302, type_id=621, is_included=False)   # asked-for, not offered
    _, created = await _service()._match_and_notify(db_session)
    assert created == 0


async def test_disabled_alerts_user_excluded(db_session: AsyncSession):
    u = await _user(db_session, enabled=False)
    await _watch(db_session, u, type_id=621, max_price=None)
    await _contract(db_session, cid=6303, price=1)
    await _item(db_session, cid=6303, type_id=621)
    _, created = await _service()._match_and_notify(db_session)
    assert created == 0


# ---------- prune (injectable now_fn + backdated created_at) ----------

async def _note(db, user, *, cid, created_at):
    n = Notification(user_id=user.id, type="watchlist_match", message="m", contract_id=cid,
                     watch_type_id=621, price=1, is_read=False, created_at=created_at)
    db.add(n)
    await db.flush()
    return n


async def test_prune_deletes_old_when_contract_gone(db_session: AsyncSession):
    u = await _user(db_session)
    # old notification (100 days before the injected now) whose contract is expired/absent.
    await _note(db_session, u, cid=7100, created_at=NOW - timedelta(days=100))
    pruned = await _service(now=NOW)._prune(db_session)
    assert pruned == 1
    assert (await db_session.scalar(select(func.count()).select_from(Notification))) == 0


async def test_prune_keeps_old_when_contract_outstanding(db_session: AsyncSession):
    u = await _user(db_session)
    await _contract(db_session, cid=7200, price=1, expired_in_days=7)   # still outstanding
    await _note(db_session, u, cid=7200, created_at=NOW - timedelta(days=100))
    pruned = await _service(now=NOW)._prune(db_session)
    assert pruned == 0
    assert (await db_session.scalar(select(func.count()).select_from(Notification))) == 1


async def test_prune_keeps_recent(db_session: AsyncSession):
    u = await _user(db_session)
    await _note(db_session, u, cid=7300, created_at=NOW - timedelta(days=10))   # inside window
    pruned = await _service(now=NOW)._prune(db_session)
    assert pruned == 0


# ---------- lock behavior (via the shared FakeLockRedis double) ----------

async def test_run_matching_skips_when_lock_held():
    store = {wm.WATCHLIST_MATCH_LOCK_KEY: "other-runner-token"}
    with patch.object(wm.aioredis, "from_url", return_value=FakeLockRedis(store)):
        await _service().run_matching()   # lock held -> ConcurrencyLockError caught -> returns
    assert store[wm.WATCHLIST_MATCH_LOCK_KEY] == "other-runner-token"   # untouched, no engine built


async def test_lock_release_declines_on_token_mismatch(caplog):
    store: dict = {}
    with patch.object(wm.aioredis, "from_url", return_value=FakeLockRedis(store)):
        svc = _service()
        with caplog.at_level("WARNING"):
            async with svc._concurrency_lock():
                store[wm.WATCHLIST_MATCH_LOCK_KEY] = "second-runner-token"   # our TTL "expired"
    assert store.get(wm.WATCHLIST_MATCH_LOCK_KEY) == "second-runner-token"
    assert "token mismatch" in caplog.text


async def test_concurrency_lock_raises_when_held():
    store = {wm.WATCHLIST_MATCH_LOCK_KEY: "held"}
    with patch.object(wm.aioredis, "from_url", return_value=FakeLockRedis(store)):
        svc = _service()
        with pytest.raises(ConcurrencyLockError):
            async with svc._concurrency_lock():
                pass
