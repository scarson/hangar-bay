# ABOUTME: Registration + constraint-binding guards for the M3 account tables.
# ABOUTME: Proves FK-to-users, the two UniqueConstraints, and the notifications partial dedup index.
import pytest
from sqlalchemy import insert, select
from sqlalchemy.exc import IntegrityError

from fastapi_app.db import Base
from fastapi_app.models import Notification, SavedSearch, User, WatchlistItem


def test_account_tables_registered():
    for table in ("saved_searches", "watchlist_items", "notifications"):
        assert table in Base.metadata.tables


def test_user_has_watchlist_alerts_enabled_not_null():
    col = Base.metadata.tables["users"].columns["watchlist_alerts_enabled"]
    assert col.nullable is False


async def _make_user(db_session, character_id=91000001):
    user = User(character_id=character_id, character_name="Sesta Hound", owner_hash="OWN1")
    db_session.add(user)
    await db_session.flush()
    return user


@pytest.mark.asyncio
async def test_watchlist_alerts_enabled_defaults_true(db_session):
    user = await _make_user(db_session, character_id=91000201)
    await db_session.refresh(user)
    assert user.watchlist_alerts_enabled is True


@pytest.mark.asyncio
async def test_saved_search_fk_requires_real_user(db_session):
    # A row FK'd to a nonexistent users.id raises IntegrityError (savepoint keeps the tx alive).
    with pytest.raises(IntegrityError):
        async with db_session.begin_nested():
            db_session.add(SavedSearch(user_id=987654, name="orphan", search_parameters={}))
            await db_session.flush()


@pytest.mark.asyncio
async def test_saved_search_fk_accepts_real_user(db_session):
    user = await _make_user(db_session, character_id=91000202)
    db_session.add(SavedSearch(user_id=user.id, name="ok", search_parameters={}))
    await db_session.flush()  # succeeds — FK satisfied


@pytest.mark.asyncio
async def test_saved_search_unique_user_name(db_session):
    user = await _make_user(db_session, character_id=91000203)
    db_session.add(SavedSearch(user_id=user.id, name="dup", search_parameters={}))
    await db_session.flush()
    with pytest.raises(IntegrityError):
        async with db_session.begin_nested():
            db_session.add(SavedSearch(user_id=user.id, name="dup", search_parameters={}))
            await db_session.flush()


@pytest.mark.asyncio
async def test_watchlist_item_unique_user_type(db_session):
    user = await _make_user(db_session, character_id=91000204)
    db_session.add(WatchlistItem(user_id=user.id, type_id=587, type_name="Rifter"))
    await db_session.flush()
    with pytest.raises(IntegrityError):
        async with db_session.begin_nested():
            db_session.add(WatchlistItem(user_id=user.id, type_id=587, type_name="Rifter"))
            await db_session.flush()


@pytest.mark.asyncio
async def test_notifications_partial_dedup_index_blocks_duplicate_watchlist_match(db_session):
    user = await _make_user(db_session, character_id=91000205)
    await db_session.execute(insert(Notification).values(
        user_id=user.id, type="watchlist_match", message="first",
        contract_id=777, watch_type_id=587, is_read=False,
    ))
    await db_session.flush()
    # A second identical (user_id, contract_id, watch_type_id) watchlist_match row is blocked.
    with pytest.raises(IntegrityError):
        async with db_session.begin_nested():
            await db_session.execute(insert(Notification).values(
                user_id=user.id, type="watchlist_match", message="second",
                contract_id=777, watch_type_id=587, is_read=False,
            ))
    # A row with a DIFFERENT type value (outside the partial index predicate) is allowed through.
    await db_session.execute(insert(Notification).values(
        user_id=user.id, type="other_kind", message="third",
        contract_id=777, watch_type_id=587, is_read=False,
    ))
    await db_session.flush()  # succeeds — predicate WHERE type='watchlist_match' excludes it
    rows = (await db_session.execute(
        select(Notification).where(Notification.user_id == user.id)
    )).scalars().all()
    assert len(rows) == 2  # the first watchlist_match + the other_kind row
