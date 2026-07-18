# ABOUTME: HTTP-level tests for /me/notifications and /me/notification-settings (F007).
# ABOUTME: total-after-filter (badge contract), pagination boundary (TEST-4), ownership, settings.
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from fastapi_app.main import app as real_app
from fastapi_app.models import Notification


BASE = datetime(2026, 7, 1, 12, 0, 0, tzinfo=timezone.utc)


async def _seed(db_session, user, *, n, is_read=False, start=0):
    # Distinct, strictly-decreasing created_at + id tiebreaker (TEST-3).
    for i in range(start, start + n):
        db_session.add(Notification(
            user_id=user.id, type="watchlist_match", message=f"m{i}",
            contract_id=1000 + i, watch_type_id=587, price=1000000 + i,
            is_read=is_read, created_at=BASE - timedelta(minutes=i),
        ))
    await db_session.flush()


@pytest.mark.asyncio
async def test_list_orders_created_desc_id_desc(authed_user, db_session):
    user, client = authed_user
    await _seed(db_session, user, n=3)
    resp = await client.get("/me/notifications/")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 3
    msgs = [i["message"] for i in body["items"]]
    assert msgs == ["m0", "m1", "m2"]   # created_at desc (m0 newest)


@pytest.mark.asyncio
async def test_pagination_crosses_boundary(authed_user, db_session):
    user, client = authed_user
    await _seed(db_session, user, n=5)
    p1 = (await client.get("/me/notifications/?page=1&size=2")).json()
    p2 = (await client.get("/me/notifications/?page=2&size=2")).json()
    p3 = (await client.get("/me/notifications/?page=3&size=2")).json()
    assert p1["total"] == p2["total"] == p3["total"] == 5
    assert len(p1["items"]) == 2 and len(p2["items"]) == 2 and len(p3["items"]) == 1
    ids = [i["id"] for i in p1["items"] + p2["items"] + p3["items"]]
    assert len(ids) == len(set(ids)) == 5   # union == full set, no dup/skip across boundary


@pytest.mark.asyncio
async def test_total_reflects_is_read_filter(authed_user, db_session):
    # Badge contract: total under is_read=false == unread count, NOT the all-time row count.
    user, client = authed_user
    await _seed(db_session, user, n=2, is_read=False, start=0)
    await _seed(db_session, user, n=3, is_read=True, start=10)
    unread = (await client.get("/me/notifications/?is_read=false")).json()
    allrows = (await client.get("/me/notifications/")).json()
    assert unread["total"] == 2
    assert allrows["total"] == 5


@pytest.mark.asyncio
async def test_mark_read_and_ownership(authed_user, db_session):
    user, client = authed_user
    await _seed(db_session, user, n=1)
    row = (await db_session.execute(select(Notification))).scalar_one()
    assert (await client.post(f"/me/notifications/{row.id}/mark-read")).status_code == 204
    await db_session.refresh(row)
    assert row.is_read is True
    assert (await client.post("/me/notifications/999999/mark-read")).status_code == 404


@pytest.mark.asyncio
async def test_mark_all_read_idempotent(authed_user, db_session):
    user, client = authed_user
    await _seed(db_session, user, n=3)
    assert (await client.post("/me/notifications/mark-all-read")).status_code == 204
    assert (await client.post("/me/notifications/mark-all-read")).status_code == 204   # idempotent
    rows = (await db_session.execute(select(Notification).where(Notification.user_id == user.id))).scalars().all()
    assert all(r.is_read for r in rows)


@pytest.mark.asyncio
async def test_cross_user_mark_read_404(authed_user, db_session):
    user_a, client = authed_user
    await _seed(db_session, user_a, n=1)
    row = (await db_session.execute(select(Notification))).scalar_one()
    from fastapi_app.tests.conftest import login_as
    await login_as(client, db_session, character_id=91000002, character_name="Other", owner_hash="OWN2")
    assert (await client.post(f"/me/notifications/{row.id}/mark-read")).status_code == 404
    await db_session.refresh(row)
    assert row.is_read is False   # B could not touch A's row


@pytest.mark.asyncio
async def test_settings_round_trip(authed_user, db_session):
    user, client = authed_user
    get1 = await client.get("/me/notification-settings")
    assert get1.status_code == 200
    assert get1.json()["watchlist_alerts_enabled"] is True   # server_default true
    put = await client.put("/me/notification-settings", json={"watchlist_alerts_enabled": False})
    assert put.status_code == 200
    assert put.json()["watchlist_alerts_enabled"] is False
    await db_session.refresh(user)
    assert user.watchlist_alerts_enabled is False


# ---------- anonymous 401 on EVERY route+method (auth_client sets app.state.redis; no session cookie) ----------

@pytest.mark.parametrize("method, path, json_body", [
    ("GET", "/me/notifications/", None),
    ("POST", "/me/notifications/1/mark-read", None),
    ("POST", "/me/notifications/mark-all-read", None),
    ("GET", "/me/notification-settings", None),
    ("PUT", "/me/notification-settings", {"watchlist_alerts_enabled": False}),
])
@pytest.mark.asyncio
async def test_every_notification_route_401_anonymous(auth_client, method, path, json_body):
    # get_current_user 401s a cookieless request before any handler body runs — assert it on
    # every method/path the two routers declare.
    resp = await auth_client.request(method, path, json=json_body)
    assert resp.status_code == 401


def test_openapi_notification_paths_bare():
    schema = real_app.openapi()
    paths = schema["paths"]
    for p in ("/me/notifications/", "/me/notifications/{notification_id}/mark-read",
              "/me/notifications/mark-all-read", "/me/notification-settings"):
        assert p in paths
    assert not any(p.startswith("/api/v1") for p in paths)
    # 401 declared on every new notification operation (design §4.5 acceptance criterion).
    for path, method in [
        ("/me/notifications/", "get"),
        ("/me/notifications/{notification_id}/mark-read", "post"),
        ("/me/notifications/mark-all-read", "post"),
        ("/me/notification-settings", "get"),
        ("/me/notification-settings", "put"),
    ]:
        assert "401" in paths[path][method]["responses"]
