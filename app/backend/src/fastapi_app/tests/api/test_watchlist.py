# ABOUTME: HTTP-level tests for the /me/watchlist-items surface (F006) — add pipeline, CRUD, auth.
# ABOUTME: ESI is mocked at the app.state.http_client seam (base http://sso.test) via pytest-httpx.
import pytest
from sqlalchemy import select

from fastapi_app.main import app as real_app
from fastapi_app.models import WatchlistItem
from fastapi_app.core.config import settings


ESI = "http://sso.test"
IDS_URL = f"{ESI}/v1/universe/ids/"


def _type_url(type_id: int) -> str:
    return f"{ESI}/v3/universe/types/{type_id}/"


def _group_url(group_id: int) -> str:
    return f"{ESI}/v1/universe/groups/{group_id}/"


def _published_ship(name="Rifter", group_id=25):
    return {"name": name, "group_id": group_id, "published": True, "market_group_id": 1}


def _ship_group(group_id=25):
    return {"name": "Frigate", "category_id": 6}


# ---------- happy paths ----------

@pytest.mark.asyncio
async def test_add_by_type_id_denormalizes_name(authed_user, httpx_mock, db_session):
    user, client = authed_user
    httpx_mock.add_response(method="GET", url=_type_url(587), json=_published_ship("Rifter", 25))
    httpx_mock.add_response(method="GET", url=_group_url(25), json=_ship_group(25))

    resp = await client.post("/me/watchlist-items/", json={"type_id": 587, "max_price": 5000000})
    assert resp.status_code == 201
    body = resp.json()
    assert body["type_id"] == 587
    assert body["type_name"] == "Rifter"
    assert body["max_price"] == 5000000.0

    row = (await db_session.execute(select(WatchlistItem).where(WatchlistItem.user_id == user.id))).scalar_one()
    assert row.type_name == "Rifter"


@pytest.mark.asyncio
async def test_add_by_name_resolves_then_validates(authed_user, httpx_mock, db_session):
    user, client = authed_user
    httpx_mock.add_response(method="POST", url=IDS_URL,
                            json={"inventory_types": [{"id": 587, "name": "Rifter"}]})
    httpx_mock.add_response(method="GET", url=_type_url(587), json=_published_ship("Rifter", 25))
    httpx_mock.add_response(method="GET", url=_group_url(25), json=_ship_group(25))

    resp = await client.post("/me/watchlist-items/", json={"type_name": "Rifter", "notes": "wishlist"})
    assert resp.status_code == 201
    assert resp.json()["type_id"] == 587
    assert resp.json()["notes"] == "wishlist"


# ---------- validation / ESI error discrimination (no row inserted) ----------

@pytest.mark.asyncio
async def test_add_non_ship_category_400(authed_user, httpx_mock, db_session):
    user, client = authed_user
    httpx_mock.add_response(method="GET", url=_type_url(34), json=_published_ship("Tritanium", 18))
    httpx_mock.add_response(method="GET", url=_group_url(18), json={"name": "Mineral", "category_id": 4})
    resp = await client.post("/me/watchlist-items/", json={"type_id": 34})
    assert resp.status_code == 400
    assert (await db_session.execute(select(WatchlistItem))).first() is None


@pytest.mark.asyncio
async def test_add_unpublished_400(authed_user, httpx_mock, db_session):
    user, client = authed_user
    httpx_mock.add_response(method="GET", url=_type_url(999),
                            json={"name": "Old Hull", "group_id": 25, "published": False})
    resp = await client.post("/me/watchlist-items/", json={"type_id": 999})
    assert resp.status_code == 400
    assert (await db_session.execute(select(WatchlistItem))).first() is None


@pytest.mark.asyncio
async def test_add_esi_type_404_is_400_not_502(authed_user, httpx_mock, db_session):
    # _get_esi_object 4xx -> httpx.HTTPStatusError (NOT ESIRequestFailedError); service maps 4xx->400.
    user, client = authed_user
    httpx_mock.add_response(method="GET", url=_type_url(424242), status_code=404, json={"error": "nope"})
    resp = await client.post("/me/watchlist-items/", json={"type_id": 424242})
    assert resp.status_code == 400
    assert (await db_session.execute(select(WatchlistItem))).first() is None


@pytest.mark.asyncio
async def test_add_esi_5xx_is_502(authed_user, httpx_mock, db_session):
    # _get_esi_object retries 5xx 3x (~1.5s) then raises ESIRequestFailedError(status=503) -> 502.
    # Repeatable response; DO NOT assert request count == 1 (retries are load-bearing).
    user, client = authed_user
    httpx_mock.add_response(method="GET", url=_type_url(587), status_code=503, text="down", is_reusable=True)
    resp = await client.post("/me/watchlist-items/", json={"type_id": 587})
    assert resp.status_code == 502
    assert (await db_session.execute(select(WatchlistItem))).first() is None


@pytest.mark.asyncio
async def test_add_unknown_name_400(authed_user, httpx_mock, db_session):
    user, client = authed_user
    httpx_mock.add_response(method="POST", url=IDS_URL, json={})   # no inventory_types
    resp = await client.post("/me/watchlist-items/", json={"type_name": "Notaship 9000"})
    assert resp.status_code == 400
    assert "unknown ship name" in resp.json()["detail"]
    assert (await db_session.execute(select(WatchlistItem))).first() is None


@pytest.mark.asyncio
async def test_add_neither_identifier_422(authed_user, db_session):
    user, client = authed_user
    resp = await client.post("/me/watchlist-items/", json={"max_price": 5})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_add_both_identifiers_422(authed_user, db_session):
    user, client = authed_user
    resp = await client.post("/me/watchlist-items/", json={"type_id": 587, "type_name": "Rifter"})
    assert resp.status_code == 422


# ---------- duplicate + cap ----------

@pytest.mark.asyncio
async def test_add_duplicate_type_409(authed_user, httpx_mock, db_session):
    user, client = authed_user
    # reusable because the 2nd add re-reads type/group (cache may or may not serve it).
    httpx_mock.add_response(method="GET", url=_type_url(587), json=_published_ship("Rifter", 25), is_reusable=True)
    httpx_mock.add_response(method="GET", url=_group_url(25), json=_ship_group(25), is_reusable=True)
    first = await client.post("/me/watchlist-items/", json={"type_id": 587})
    assert first.status_code == 201
    second = await client.post("/me/watchlist-items/", json={"type_id": 587})
    assert second.status_code == 409
    rows = (await db_session.execute(select(WatchlistItem).where(WatchlistItem.user_id == user.id))).scalars().all()
    assert len(rows) == 1


@pytest.mark.asyncio
async def test_cap_short_circuits_before_any_esi_call(authed_user, httpx_mock, db_session, monkeypatch):
    user, client = authed_user
    monkeypatch.setattr(settings, "MAX_WATCHLIST_ITEMS_PER_USER", 0)
    resp = await client.post("/me/watchlist-items/", json={"type_id": 587})
    assert resp.status_code == 400
    assert httpx_mock.get_requests() == []   # cap check fired before ESI traffic
    assert (await db_session.execute(select(WatchlistItem))).first() is None


# ---------- PUT partial-update semantics ----------

async def _seed_item(db_session, user, *, type_id=587, type_name="Rifter", max_price=100, notes="a"):
    item = WatchlistItem(user_id=user.id, type_id=type_id, type_name=type_name,
                         max_price=max_price, notes=notes)
    db_session.add(item)
    await db_session.flush()
    return item


@pytest.mark.asyncio
async def test_put_omitted_field_preserves(authed_user, db_session):
    user, client = authed_user
    item = await _seed_item(db_session, user, max_price=100, notes="a")
    resp = await client.put(f"/me/watchlist-items/{item.id}", json={"notes": "x"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["notes"] == "x"
    assert body["max_price"] == 100.0   # omitted -> preserved


@pytest.mark.asyncio
async def test_put_explicit_null_clears(authed_user, db_session):
    user, client = authed_user
    item = await _seed_item(db_session, user, max_price=100, notes="a")
    resp = await client.put(f"/me/watchlist-items/{item.id}", json={"max_price": None})
    assert resp.status_code == 200
    body = resp.json()
    assert body["max_price"] is None      # explicit null -> cleared
    assert body["notes"] == "a"           # omitted -> preserved


# ---------- list ordering (TEST-3: same-name tiebreaker on type_id) ----------

@pytest.mark.asyncio
async def test_list_ordered_type_name_then_type_id(authed_user, db_session):
    user, client = authed_user
    await _seed_item(db_session, user, type_id=200, type_name="Alpha", max_price=None, notes=None)
    await _seed_item(db_session, user, type_id=100, type_name="Alpha", max_price=None, notes=None)
    await _seed_item(db_session, user, type_id=50, type_name="Beta", max_price=None, notes=None)
    resp = await client.get("/me/watchlist-items/")
    assert resp.status_code == 200
    ordered = [(r["type_name"], r["type_id"]) for r in resp.json()]
    assert ordered == [("Alpha", 100), ("Alpha", 200), ("Beta", 50)]


# ---------- cross-user isolation (uniform 404) ----------

@pytest.mark.asyncio
async def test_cross_user_put_and_delete_404(authed_user, db_session):
    user_a, client = authed_user
    item = await _seed_item(db_session, user_a)
    # login_as overwrites the cookie to user B; A's item id must be invisible to B.
    from fastapi_app.tests.conftest import login_as  # helper defined by the earlier phase
    await login_as(client, db_session, character_id=91000002, character_name="Other Pilot", owner_hash="OWN2")
    assert (await client.put(f"/me/watchlist-items/{item.id}", json={"notes": "y"})).status_code == 404
    assert (await client.delete(f"/me/watchlist-items/{item.id}")).status_code == 404
    # A's row is untouched.
    still = (await db_session.execute(select(WatchlistItem).where(WatchlistItem.id == item.id))).scalar_one()
    assert still.notes == "a"


# ---------- delete happy + not-found ----------

@pytest.mark.asyncio
async def test_delete_removes_own_item(authed_user, db_session):
    user, client = authed_user
    item = await _seed_item(db_session, user)
    assert (await client.delete(f"/me/watchlist-items/{item.id}")).status_code == 204
    assert (await db_session.execute(select(WatchlistItem).where(WatchlistItem.id == item.id))).first() is None


@pytest.mark.asyncio
async def test_delete_missing_404(authed_user, db_session):
    user, client = authed_user
    assert (await client.delete("/me/watchlist-items/999999")).status_code == 404


# ---------- anonymous 401 on EVERY route+method (auth_client sets app.state.redis; no session cookie) ----------

@pytest.mark.parametrize("method, path, json_body", [
    ("POST", "/me/watchlist-items/", {"type_id": 587}),
    ("GET", "/me/watchlist-items/", None),
    ("PUT", "/me/watchlist-items/1", {"notes": "x"}),
    ("DELETE", "/me/watchlist-items/1", None),
])
@pytest.mark.asyncio
async def test_every_watchlist_route_401_anonymous(auth_client, method, path, json_body):
    # get_current_user's first dependency is get_current_session, so a cookieless request 401s
    # before any handler body runs — assert it for every method/path the router declares.
    resp = await auth_client.request(method, path, json=json_body)
    assert resp.status_code == 401


# ---------- OpenAPI schema (PROXY-1 + declared error bodies + 401 on every operation) ----------

def test_openapi_watchlist_paths_bare_and_declared():
    schema = real_app.openapi()
    paths = schema["paths"]
    assert "/me/watchlist-items/" in paths
    assert "/me/watchlist-items/{item_id}" in paths
    assert not any(p.startswith("/api/v1") for p in paths)   # PROXY-1 sentinel
    post = paths["/me/watchlist-items/"]["post"]
    assert set(post["responses"]) >= {"201", "400", "401", "409", "422", "502"}
    # every new watchlist operation must declare a 401 response (design §4.5 acceptance criterion).
    for path, method in [
        ("/me/watchlist-items/", "post"),
        ("/me/watchlist-items/", "get"),
        ("/me/watchlist-items/{item_id}", "put"),
        ("/me/watchlist-items/{item_id}", "delete"),
    ]:
        assert "401" in paths[path][method]["responses"]
