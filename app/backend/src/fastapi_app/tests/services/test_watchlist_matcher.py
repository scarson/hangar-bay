# ABOUTME: Service-level tests for WatchlistMatcherService (F007 matcher) — the design §6 matcher matrix.
# ABOUTME: Inner methods take the test db_session directly (run_matching builds its own engine, §6).
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import delete, func, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

import fastapi_app.services.watchlist_matcher as wm
from fastapi_app.models import Contract, ContractItem, Notification, User, WatchlistItem
from fastapi_app.schemas.contracts import (
    ITEM_BEARING_CONTRACT_TYPES,
    ITEMLESS_CONTRACT_TYPES,
)
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
    # A real int, not the MagicMock default: the lock TTL derives from this, and a
    # Mock would make any TTL comparison pass vacuously (TEST-12).
    s.WATCHLIST_MATCH_INTERVAL_SECONDS = 900
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
                    location="Jita IV - Moon 4", region_id=10000002, last_seen_at=None):
    c = Contract(
        contract_id=cid, title="t", price=price, collateral=0, status="unknown", type=ctype,
        issuer_id=1, issuer_corporation_id=1, start_location_id=60003760,
        start_location_region_id=region_id, for_corporation=False,
        date_issued=datetime.now(timezone.utc) - timedelta(days=1),
        date_expired=datetime.now(timezone.utc) + timedelta(days=expired_in_days),
        date_completed=(datetime.now(timezone.utc) if completed else None),
        start_location_name=location,
        last_seen_at=last_seen_at,
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

async def test_an_item_exchange_contract_matches_and_renders_its_own_label(
    db_session: AsyncSession,
):
    """The positive arm of the contract-type gate, and the only route to its label.

    Every matcher fixture is an auction (the `_contract` default), so item_exchange —
    the commoner of the two item-bearing types — was never matched and
    _SHIP_TYPE_LABELS' "an item exchange" was never rendered. Dropping item_exchange
    from the gate's tuple passed the entire suite.
    """
    u = await _user(db_session)
    await _watch(db_session, u, type_id=621, type_name="Caracal", max_price=20_000_000)
    await _contract(db_session, cid=5011, price=10_500_000, ctype="item_exchange",
                    location="Jita IV - Moon 4")
    await _item(db_session, cid=5011, type_id=621)

    matched, created = await _service()._match_and_notify(db_session)
    assert matched == 1 and created == 1
    note = (await db_session.execute(select(Notification))).scalar_one()
    assert note.contract_id == 5011
    assert note.message == (
        "Caracal available in an item exchange priced 10,500,000 ISK in Jita IV - Moon 4"
    )


@pytest.mark.parametrize("item_bearing_type", sorted(ITEM_BEARING_CONTRACT_TYPES))
async def test_every_item_bearing_contract_type_matches(
    db_session: AsyncSession, item_bearing_type: str
):
    """The positive arm, parametrized over the partition rather than a hand-listed pair.

    The matcher's gate is the third site that used to restate `(item_exchange, auction)`
    as a literal; it now reads the same enum-derived constant as the ingestion writer and
    the read path. Deriving the parametrization too is what makes that load-bearing: a
    sixth item-bearing ContractType is covered here the moment it is added, instead of
    ingesting items nobody is ever alerted about.
    """
    u = await _user(db_session)
    await _watch(db_session, u, type_id=621, max_price=None)
    await _contract(db_session, cid=5031, price=1_000_000, ctype=item_bearing_type)
    await _item(db_session, cid=5031, type_id=621)

    matched, created = await _service()._match_and_notify(db_session)

    assert (matched, created) == (1, 1)
    note = (await db_session.execute(select(Notification))).scalar_one()
    assert note.contract_id == 5031


@pytest.mark.parametrize("itemless_type", sorted(ITEMLESS_CONTRACT_TYPES))
async def test_a_contract_outside_the_item_bearing_types_never_matches(
    db_session: AsyncSession, itemless_type: str
):
    """The negative arm: a type the gate excludes must not alert, even when the row
    carries an INCLUDED item of a watched type at a matching price.

    A control auction of the same shape runs alongside it, so this cannot pass
    vacuously — the fixture is proven to satisfy every OTHER clause of the predicate,
    leaving the type gate as the only thing that can be excluding it.
    """
    u = await _user(db_session)
    await _watch(db_session, u, type_id=621, max_price=None)

    await _contract(db_session, cid=5021, price=1_000_000, ctype=itemless_type)
    await _item(db_session, cid=5021, type_id=621)

    control = 5022
    await _contract(db_session, cid=control, price=1_000_000, ctype="auction")
    await _item(db_session, cid=control, type_id=621)

    matched, created = await _service()._match_and_notify(db_session)

    assert (matched, created) == (1, 1)  # the control matched; the gated one did not
    note = (await db_session.execute(select(Notification))).scalar_one()
    assert note.contract_id == control


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


async def test_delisted_contract_excluded(db_session: AsyncSession):
    """A contract that stopped appearing in ESI's public list — accepted, sold, or
    withdrawn — keeps a future date_expired, so expiry alone still matches it. It is
    told apart by its last_seen_at trailing the newest stamp in its own region."""
    u = await _user(db_session)
    await _watch(db_session, u, type_id=621, max_price=None)
    fresh = datetime.now(timezone.utc)
    # The region's watermark: some other contract was restamped by the latest run.
    await _contract(db_session, cid=6310, price=1, last_seen_at=fresh)
    await _item(db_session, cid=6310, type_id=34, record_id=63100)
    # Watched hull, unexpired, but last observed a run ago.
    await _contract(db_session, cid=6311, price=1, last_seen_at=fresh - timedelta(hours=1))
    await _item(db_session, cid=6311, type_id=621, record_id=63110)
    _, created = await _service()._match_and_notify(db_session)
    assert created == 0


async def test_contract_at_its_region_watermark_notifies(db_session: AsyncSession):
    """The positive half of the delisting gate: a contract restamped by the latest run
    carries the region's newest stamp and must still match."""
    u = await _user(db_session)
    await _watch(db_session, u, type_id=621, max_price=None)
    fresh = datetime.now(timezone.utc)
    await _contract(db_session, cid=6320, price=1, last_seen_at=fresh - timedelta(hours=1))
    await _item(db_session, cid=6320, type_id=34, record_id=63200)
    await _contract(db_session, cid=6321, price=1, last_seen_at=fresh)
    await _item(db_session, cid=6321, type_id=621, record_id=63210)
    _, created = await _service()._match_and_notify(db_session)
    assert created == 1
    note = (await db_session.execute(select(Notification))).scalar_one()
    assert note.contract_id == 6321


async def test_stalled_region_is_judged_against_its_own_watermark(db_session: AsyncSession):
    """The watermark is per-region so a region whose ESI fetch failed keeps its own,
    older stamp. Judged against a fresher region's stamp, every contract the stalled
    region holds would be silenced at once."""
    u = await _user(db_session)
    await _watch(db_session, u, type_id=621, max_price=None)
    fresh = datetime.now(timezone.utc)
    # Region 10000002 was restamped by the latest run.
    await _contract(db_session, cid=6330, price=1, region_id=10000002, last_seen_at=fresh)
    await _item(db_session, cid=6330, type_id=34, record_id=63300)
    # Region 10000043's fetch failed, so nothing in it was restamped — but the watched
    # hull is still the newest thing its own region has seen.
    await _contract(db_session, cid=6331, price=1, region_id=10000043,
                    last_seen_at=fresh - timedelta(hours=6))
    await _item(db_session, cid=6331, type_id=621, record_id=63310)
    _, created = await _service()._match_and_notify(db_session)
    assert created == 1


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


async def test_prune_deletes_old_when_contract_delisted(db_session: AsyncSession):
    """The prune's no-resurrection guard keeps aged notifications whose contract is still
    outstanding. It has to read "outstanding" exactly as the match query does — a contract
    that is unexpired but gone from ESI no longer matches, so nothing recreates its
    notification and holding the row back serves nobody."""
    u = await _user(db_session)
    fresh = datetime.now(timezone.utc)
    await _contract(db_session, cid=7250, price=1, last_seen_at=fresh)
    await _contract(db_session, cid=7251, price=1, expired_in_days=7,
                    last_seen_at=fresh - timedelta(hours=1))
    await _note(db_session, u, cid=7251, created_at=NOW - timedelta(days=100))
    pruned = await _service(now=NOW)._prune(db_session)
    assert pruned == 1
    assert (await db_session.scalar(select(func.count()).select_from(Notification))) == 0


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


async def test_lock_ttl_exceeds_the_match_interval():
    """The lock TTL is the mutual-exclusion window: a TTL equal to the tick
    interval expires exactly as the next tick fires, so any run slower than one
    interval leaves the lock free and the next tick starts a concurrent matcher
    (the aggregation lock's shape in the 2026-07-23 production incident). The
    TTL must strictly exceed the interval so the overlapping tick always skips.
    The interval is pinned to a real int here because settings is a MagicMock —
    an unset attribute compares truthy and the assertion would pass vacuously."""
    store: dict = {}
    fake = FakeLockRedis(store)
    with patch.object(wm.aioredis, "from_url", return_value=fake):
        svc = _service()
        svc.settings.WATCHLIST_MATCH_INTERVAL_SECONDS = 900
        async with svc._concurrency_lock():
            pass
    assert fake.set_ttls[wm.WATCHLIST_MATCH_LOCK_KEY] > 900


async def test_lock_ttl_follows_a_reconfigured_interval():
    """The window must track the configured interval — a constant merely raised
    above today's interval silently re-opens the gap when the interval grows."""
    store: dict = {}
    fake = FakeLockRedis(store)
    with patch.object(wm.aioredis, "from_url", return_value=fake):
        svc = _service()
        svc.settings.WATCHLIST_MATCH_INTERVAL_SECONDS = 3600
        async with svc._concurrency_lock():
            pass
    assert fake.set_ttls[wm.WATCHLIST_MATCH_LOCK_KEY] > 3600


@pytest.mark.asyncio
async def test_run_matching_reuses_app_session_factory(monkeypatch: pytest.MonkeyPatch):
    """Pool-policy coverage (M4 spec §5): the matcher must source its session from
    fastapi_app.db.AsyncSessionLocal — a per-run create_async_engine() would sit outside
    the tuned pre-ping/bounded pool and multiply connections against Render Basic's budget."""
    import fastapi_app.db as app_db

    service = wm.WatchlistMatcherService(settings=MagicMock())
    service.settings.CACHE_URL = "redis://unused/0"
    service.settings.WATCHLIST_MATCH_INTERVAL_SECONDS = 900
    service.settings.NOTIFICATION_RETENTION_DAYS = 90

    entered = {"count": 0}
    real_factory = app_db.AsyncSessionLocal

    def recording_factory():
        entered["count"] += 1
        return real_factory()

    monkeypatch.setattr(wm, "AsyncSessionLocal", recording_factory, raising=False)

    async def _no_match(self_, db_session):
        return 0, 0

    async def _no_prune(self_, db_session):
        return 0

    monkeypatch.setattr(wm.WatchlistMatcherService, "_match_and_notify", _no_match)
    monkeypatch.setattr(wm.WatchlistMatcherService, "_prune", _no_prune)

    store: dict = {}
    with patch.object(wm.aioredis, "from_url", return_value=FakeLockRedis(store)):
        await service.run_matching()

    assert entered["count"] == 1, (
        "run_matching must obtain its session from fastapi_app.db.AsyncSessionLocal"
    )

@pytest.mark.parametrize("failing_step", ["match", "prune", "commit"])
async def test_run_matching_swallows_a_failure_at_the_job_boundary(
    db_session: AsyncSession, caplog, monkeypatch: pytest.MonkeyPatch, failing_step: str
):
    """An APScheduler job must never let an exception escape: the scheduler treats a
    raising job as a crashing one and the matcher stops running until a redeploy.

    The three failure sites inside the lock — the match query, the prune, and the
    commit — all funnel into one generic handler that has to log the structured
    failure event and return. Nothing exercised any of them, so narrowing that
    `except Exception` (or removing it in favour of "let it bubble") was invisible.
    """
    from fastapi_app.tests.conftest import TEST_DATABASE_URL
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    events: list[tuple[tuple, dict]] = []
    real_log_key_event = wm.log_key_event

    def recording_log_key_event(*args, **kwargs):
        events.append((args, kwargs))
        return real_log_key_event(*args, **kwargs)

    monkeypatch.setattr(wm, "log_key_event", recording_log_key_event)

    async def _boom_match(self_, db):
        raise RuntimeError("simulated match failure")

    async def _boom_prune(self_, db):
        raise RuntimeError("simulated prune failure")

    async def _ok_match(self_, db):
        return 0, 0

    async def _ok_prune(self_, db):
        return 0

    monkeypatch.setattr(
        wm.WatchlistMatcherService, "_match_and_notify",
        _boom_match if failing_step == "match" else _ok_match,
    )
    monkeypatch.setattr(
        wm.WatchlistMatcherService, "_prune",
        _boom_prune if failing_step == "prune" else _ok_prune,
    )

    engine = create_async_engine(TEST_DATABASE_URL)
    maker = async_sessionmaker(engine, expire_on_commit=False)

    def session_factory():
        session = maker()
        if failing_step == "commit":
            async def boom():
                raise RuntimeError("simulated commit failure")
            session.commit = boom
        return session

    monkeypatch.setattr(wm, "AsyncSessionLocal", session_factory, raising=False)

    store: dict = {}
    with patch.object(wm.aioredis, "from_url", return_value=FakeLockRedis(store)):
        with caplog.at_level("ERROR"):
            await _service().run_matching()  # must not raise
    await engine.dispose()

    assert "Watchlist matcher run failed" in caplog.text
    run_events = [kw for args, kw in events if args[1] == "watchlist_match_run"]
    assert len(run_events) == 1
    assert run_events[0]["success"] is False
    assert f"simulated {failing_step} failure" in run_events[0]["error_message"]
    # The lock is released even on the failing path, so the next tick can run.
    assert wm.WATCHLIST_MATCH_LOCK_KEY not in store


# ---------- NULL price: ESI marks price optional; the column is nullable ----------

async def test_a_priceless_contract_matches_an_unbounded_watch_and_renders_a_dash(db_session: AsyncSession):
    """No price bound means any price, the unknown one included — hiding the match
    would silently drop a real contract over a display concern. The message carries
    the same bare dash the list surface uses, with no ISK suffix: a dash is not an
    amount of ISK."""
    u = await _user(db_session)
    await _watch(db_session, u, type_id=621, type_name="Caracal", max_price=None)
    await _contract(db_session, cid=5901, price=None, ctype="auction", location="Jita IV - Moon 4")
    await _item(db_session, cid=5901, type_id=621)

    matched, created = await _service()._match_and_notify(db_session)
    assert matched == 1 and created == 1
    note = (await db_session.execute(select(Notification))).scalar_one()
    assert note.message == "Caracal available in an auction priced — in Jita IV - Moon 4"


async def test_a_priceless_contract_never_satisfies_a_numeric_price_bound(db_session: AsyncSession):
    """SQL three-valued logic: NULL <= bound is not true, so a priced watch cannot
    match a contract whose price is unknown — an unknown price is not a low one."""
    u = await _user(db_session)
    await _watch(db_session, u, type_id=621, type_name="Caracal", max_price=20_000_000)
    await _contract(db_session, cid=5902, price=None, ctype="auction", location="Jita IV - Moon 4")
    await _item(db_session, cid=5902, type_id=621)

    matched, created = await _service()._match_and_notify(db_session)
    assert matched == 0 and created == 0


async def test_a_match_at_an_unresolved_location_says_so_rather_than_naming_nothing(
    db_session: AsyncSession,
):
    """`_render_message`'s `location or "an unknown location"` arm.

    Station names are resolved by a separate ESI call that can fail or lag, so a live
    contract routinely carries a NULL `start_location_name` — this is the ordinary
    state right after ingestion, not a defensive corner. Without the fallback the
    notification renders "... in None", which is the kind of string that reaches a
    reader before anyone notices.

    Driven through `_match_and_notify` against a real unresolved row, and asserted on
    the STORED notification. A direct `_render_message` call constrains the renderer but
    not the rendering: the call site passes `r.start_location_name`, and wrapping that in
    `str()` — which is how a "make the type checker happy" edit reads — produces the
    literal "None" while every unit-level assertion on the renderer still passes
    (TEST-25: observe the value the reader receives, at the point they receive it).

    Asserted on the whole message rather than on a substring: the location is the last
    field, so a substring check passes for a message that lost everything before it.
    """
    u = await _user(db_session)
    await _watch(db_session, u, type_id=621, type_name="Caracal", max_price=None)
    await _contract(db_session, cid=5921, price=10_500_000, ctype="auction", location=None)
    await _item(db_session, cid=5921, type_id=621)

    matched, created = await _service()._match_and_notify(db_session)
    assert matched == 1 and created == 1
    note = (await db_session.execute(select(Notification))).scalar_one()
    assert note.message == (
        "Caracal available in an auction priced 10,500,000 ISK in an unknown location"
    )


async def test_the_unknown_location_fallback_covers_every_falsy_name(
    db_session: AsyncSession,
):
    """The guard is `location or ...`, not `is None`, and the difference is reachable.

    An empty string is what a name lookup returns for a station it resolved to nothing,
    and narrowing the guard to `is None` would render a message ending in "in " — which
    reads as truncated rather than as unknown. Kept at the renderer because the point
    here is the SHAPE of the guard, while the integration test above pins the call site.
    """
    for absent in (None, ""):
        assert wm._render_message("Caracal", "auction", 10_500_000, absent) == (
            "Caracal available in an auction priced 10,500,000 ISK in an unknown location"
        ), f"location={absent!r}"


async def test_every_item_bearing_type_has_a_label_of_its_own():
    """The label table and the matcher's type gate must name the same set of types.

    These two update ASYMMETRICALLY, which is the whole reason this test exists.
    `ITEM_BEARING_CONTRACT_TYPES` is DERIVED — every `ContractType` member minus the
    item-less ones — so adding a member to the enum (which is forced, since an unknown
    value 422s) silently widens the matcher's gate to admit it. `_SHIP_TYPE_LABELS` is a
    hand-written dict and does not widen with it. Nobody has to forget anything: one
    side maintains itself and the other does not.

    Without this test the consequence is a notification reading "Caracal available in a
    contract priced ..." — the `.get` fallback, which reads as a rendering bug to the
    person receiving the alert and is invisible to every other test, because the gate,
    the match count and the notification row are all still correct.

    Comparing the two constants is NOT the self-referential trap: they are independently
    authored in different modules, one derived from the enum and one written by hand, so
    the comparison is a genuine cross-check rather than an expectation computed from the
    thing under test.
    """
    assert set(wm._SHIP_TYPE_LABELS) == ITEM_BEARING_CONTRACT_TYPES


# ---------- fan-out shapes and the join's distinct() (register N-12) ----------


async def test_two_included_items_of_the_watched_type_produce_one_match(
    db_session: AsyncSession,
):
    """A contract listing the same hull twice is one opportunity, not two.

    The match joins watchlist items to contract items, so a contract carrying two
    INCLUDED rows of the watched type_id (ESI sends separately-stacked items as
    separate records) produces two identical join rows. Only distinct() collapses them.

    Both numbers are asserted because they fail differently: created stays correct
    without distinct() — the second insert hits the dedup index and is not returned —
    so a test reading only created passes with distinct() deleted, while the matched
    count that the run summary reports silently doubles.
    """
    u = await _user(db_session)
    await _watch(db_session, u, type_id=621, type_name="Caracal", max_price=None)
    await _contract(db_session, cid=6400, price=9_000_000)
    await _item(db_session, cid=6400, type_id=621, record_id=64000)
    await _item(db_session, cid=6400, type_id=621, record_id=64001)

    matched, created = await _service()._match_and_notify(db_session)
    assert (matched, created) == (1, 1)
    assert (await db_session.scalar(select(func.count()).select_from(Notification))) == 1


async def test_two_users_watching_the_same_type_each_get_their_own_notification(
    db_session: AsyncSession,
):
    """One contract fans out to every watching user. The dedup index is keyed on
    user_id first, so a mistake that treated (contract_id, watch_type_id) as the
    identity would deliver the alert to whoever matched first and silently drop the
    rest — a single-user suite cannot see it."""
    first = await _user(db_session, cid=91000101)
    second = await _user(db_session, cid=91000102)
    await _watch(db_session, first, type_id=621, type_name="Caracal", max_price=None)
    await _watch(db_session, second, type_id=621, type_name="Caracal", max_price=None)
    await _contract(db_session, cid=6410, price=9_000_000)
    await _item(db_session, cid=6410, type_id=621, record_id=64100)

    matched, created = await _service()._match_and_notify(db_session)
    assert (matched, created) == (2, 2)
    rows = (await db_session.execute(select(Notification))).scalars().all()
    assert {n.user_id for n in rows} == {first.id, second.id}
    assert {n.contract_id for n in rows} == {6410}


async def test_one_user_watching_two_types_in_one_contract_gets_a_notification_each(
    db_session: AsyncSession,
):
    """A contract satisfying two of one user's watches owes that user two alerts.

    The two rows differ only in watch_type_id, which is the third column of the partial
    unique index — so this is the case that proves the index is keyed on the watched
    type as well as on the user and the contract. Dropping watch_type_id from the
    conflict target would collapse them into one alert naming only whichever hull was
    inserted first.
    """
    u = await _user(db_session)
    await _watch(db_session, u, type_id=621, type_name="Caracal", max_price=None)
    await _watch(db_session, u, type_id=587, type_name="Rifter", max_price=None)
    await _contract(db_session, cid=6420, price=9_000_000)
    await _item(db_session, cid=6420, type_id=621, record_id=64200)
    await _item(db_session, cid=6420, type_id=587, record_id=64201)

    matched, created = await _service()._match_and_notify(db_session)
    assert (matched, created) == (2, 2)
    rows = (await db_session.execute(select(Notification))).scalars().all()
    assert {n.watch_type_id for n in rows} == {621, 587}
    assert {n.user_id for n in rows} == {u.id}


# ---------- the prune's other "not outstanding" arms (register N-13) ----------


@pytest.mark.parametrize(
    "why_not_outstanding", ["expired", "completed"], ids=["expired", "completed"]
)
async def test_prune_deletes_an_aged_notification_whose_contract_is_present_but_finished(
    db_session: AsyncSession, why_not_outstanding: str
):
    """"No longer outstanding" has three shapes and only the absent-row one was tested.

    A contract that expired, and one that was completed, are both still IN the table —
    the existing delete-when-gone test has no row at all, so it passes with either
    predicate of the outstanding subquery deleted. Each arm here is the only thing that
    fails when its own predicate goes.
    """
    u = await _user(db_session)
    await _contract(
        db_session,
        cid=7260 if why_not_outstanding == "expired" else 7261,
        price=1,
        expired_in_days=-1 if why_not_outstanding == "expired" else 7,
        completed=(why_not_outstanding == "completed"),
    )
    cid = 7260 if why_not_outstanding == "expired" else 7261
    await _note(db_session, u, cid=cid, created_at=NOW - timedelta(days=100))

    pruned = await _service(now=NOW)._prune(db_session)
    assert pruned == 1
    assert (await db_session.scalar(select(func.count()).select_from(Notification))) == 0


async def test_prune_keeps_a_notification_created_exactly_at_the_cutoff(
    db_session: AsyncSession,
):
    """The retention window boundary is strict: created_at == cutoff is INSIDE it.

    Retention is a promise about how long history is kept, so the instant that is
    exactly N days old must survive — `<` and `<=` differ by exactly this one row and
    every other prune fixture sits days away from the boundary, where the two are
    indistinguishable. No contract row is seeded, so the outstanding guard is satisfied
    and age is the only predicate under test.
    """
    u = await _user(db_session)
    service = _service(now=NOW)
    cutoff = NOW - timedelta(days=service.settings.NOTIFICATION_RETENTION_DAYS)
    await _note(db_session, u, cid=7310, created_at=cutoff)

    assert await service._prune(db_session) == 0
    assert (await db_session.scalar(select(func.count()).select_from(Notification))) == 1

    # And one microsecond older is outside it — pinning the boundary needs both sides,
    # or "keeps everything" passes the half above.
    await _note(db_session, u, cid=7311, created_at=cutoff - timedelta(microseconds=1))
    assert await service._prune(db_session) == 1
    survivors = (await db_session.execute(select(Notification.contract_id))).scalars().all()
    assert survivors == [7310]


# ---------- run_matching end to end (register N-14) ----------


async def test_run_matching_drives_a_real_match_through_to_a_committed_notification(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
):
    """The whole job, once, with nothing stubbed out.

    Every other run_matching test either holds the lock or replaces _match_and_notify
    and _prune with no-ops, so the wiring between them — that the session reaches both,
    that the commit lands, and that the success event reports the counts they returned
    rather than the zeros they were initialised to — was never exercised. Deleting the
    commit, or reporting the initial 0/0/0, passed the entire suite.

    The notification is read back through a session that did NOT run the job, because
    an assertion on the job's own session cannot tell committed state from
    uncommitted. db_session is requested for the schema it creates, and the seed is
    committed through the same factory the job uses so the job can see it at all —
    without both, the run dies on a missing relation and records a failure that an
    outcome assertion would have accepted for the wrong reason.
    """
    from fastapi_app.tests.conftest import TEST_DATABASE_URL
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    engine = create_async_engine(TEST_DATABASE_URL)
    maker = async_sessionmaker(engine, expire_on_commit=False)

    async with maker() as seed:
        u = await _user(seed)
        await _watch(seed, u, type_id=621, type_name="Caracal", max_price=20_000_000)
        await _contract(seed, cid=7500, price=10_500_000, ctype="item_exchange",
                        location="Jita IV - Moon 4")
        await _item(seed, cid=7500, type_id=621, record_id=75000)
        await seed.commit()
        seeded_user_id = u.id

    monkeypatch.setattr(wm, "AsyncSessionLocal", maker, raising=False)

    events: list[tuple[tuple, dict]] = []
    real_log_key_event = wm.log_key_event

    def recording_log_key_event(*args, **kwargs):
        events.append((args, kwargs))
        return real_log_key_event(*args, **kwargs)

    monkeypatch.setattr(wm, "log_key_event", recording_log_key_event)

    store: dict = {}
    try:
        with patch.object(wm.aioredis, "from_url", return_value=FakeLockRedis(store)):
            await _service().run_matching()

        async with maker() as check:
            notes = (await check.execute(select(Notification))).scalars().all()
            assert len(notes) == 1
            assert notes[0].user_id == seeded_user_id
            assert notes[0].contract_id == 7500
            assert notes[0].watch_type_id == 621
            assert notes[0].message == (
                "Caracal available in an item exchange priced 10,500,000 ISK "
                "in Jita IV - Moon 4"
            )
    finally:
        async with maker() as cleanup:
            await cleanup.execute(delete(Notification))
            await cleanup.execute(delete(WatchlistItem))
            await cleanup.execute(delete(ContractItem))
            await cleanup.execute(delete(Contract))
            await cleanup.execute(delete(User))
            await cleanup.commit()
        await engine.dispose()

    run_events = [kw for args, kw in events if args[1] == "watchlist_match_run"]
    assert len(run_events) == 1
    assert run_events[0]["success"] is True
    assert run_events[0]["matches"] == 1
    assert run_events[0]["created"] == 1
    assert run_events[0]["pruned"] == 0
    # The lock is handed back so the next scheduler tick can run.
    assert wm.WATCHLIST_MATCH_LOCK_KEY not in store


async def test_an_unlabelled_contract_type_renders_a_vague_noun_rather_than_raising():
    """The label fallback is defense in depth, and this is the only way to reach it.

    The match query gates on ITEM_BEARING_CONTRACT_TYPES and the label table is asserted
    equal to that set, so no fixture can drive an unlabelled type through
    _match_and_notify — the branch is unreachable by construction and stays that way
    only for as long as the drift guard holds. What it defends against is the window
    where a new ContractType has widened the gate but not yet the table: a KeyError
    there aborts the whole matching run over one alert's wording, silencing every
    user's alerts, so degrading to a vague noun is the deliberate behaviour and worth
    pinning directly rather than recording as dead code.

    Called as a unit because there is no other route; the type is a string the enum
    does not contain, which is exactly the shape a not-yet-labelled member arrives in.
    """
    rendered = wm._render_message("Caracal", "a_type_nobody_labelled", 10_500_000, "Jita IV")
    assert rendered == "Caracal available in a contract priced 10,500,000 ISK in Jita IV"
