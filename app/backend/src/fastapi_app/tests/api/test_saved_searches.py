# ABOUTME: HTTP-level (TEST-1) + app.openapi() schema tests for the F005 saved-searches CRUD surface.
# ABOUTME: Covers CRUD, 401 anon, cross-user 404, 409 duplicate/rename via real constraint, cap 400, 422s, ordering, PROXY-1.
import pytest

from fastapi_app.main import app
from fastapi_app.tests.conftest import login_as


def _body(name="Frigs", **params):
    return {"name": name, "search_parameters": params}


# ---------- happy-path CRUD ----------
@pytest.mark.asyncio
async def test_create_and_list_roundtrip(authed_user):
    user, client = authed_user
    resp = await client.post("/me/saved-searches/", json=_body(
        name="Cheap frigates", search="frigate", max_price=5_000_000, region_ids=[10000002], ships_only=True
    ))
    assert resp.status_code == 201
    created = resp.json()
    assert created["name"] == "Cheap frigates"
    assert created["search_parameters"]["search"] == "frigate"
    assert created["search_parameters"]["region_ids"] == [10000002]
    assert created["search_parameters"]["size"] == 50          # default materialized
    assert created["search_parameters"]["sort_by"] == "date_issued"
    assert "id" in created and "created_at" in created and "updated_at" in created

    listed = await client.get("/me/saved-searches/")
    assert listed.status_code == 200
    assert [s["id"] for s in listed.json()] == [created["id"]]


@pytest.mark.asyncio
async def test_rename_happy(authed_user):
    user, client = authed_user
    a = (await client.post("/me/saved-searches/", json=_body(name="Old"))).json()
    resp = await client.put(f"/me/saved-searches/{a['id']}", json={"name": "New"})
    assert resp.status_code == 200
    assert resp.json()["name"] == "New"


@pytest.mark.asyncio
async def test_delete_happy_then_404(authed_user):
    user, client = authed_user
    a = (await client.post("/me/saved-searches/", json=_body(name="Temp"))).json()
    assert (await client.delete(f"/me/saved-searches/{a['id']}")).status_code == 204
    assert (await client.delete(f"/me/saved-searches/{a['id']}")).status_code == 404


@pytest.mark.asyncio
async def test_list_ordered_name_asc(authed_user):
    user, client = authed_user
    for n in ["Zeta", "Alpha", "Mike"]:
        await client.post("/me/saved-searches/", json=_body(name=n))
    names = [s["name"] for s in (await client.get("/me/saved-searches/")).json()]
    assert names == ["Alpha", "Mike", "Zeta"]


# ---------- 401 anonymous on every route ----------
@pytest.mark.asyncio
async def test_all_routes_401_anonymous(auth_client):
    assert (await auth_client.get("/me/saved-searches/")).status_code == 401
    assert (await auth_client.post("/me/saved-searches/", json=_body())).status_code == 401
    assert (await auth_client.put("/me/saved-searches/1", json={"name": "x"})).status_code == 401
    assert (await auth_client.delete("/me/saved-searches/1")).status_code == 401


# ---------- cross-user isolation (404, indistinguishable from not-found) ----------
@pytest.mark.asyncio
async def test_cross_user_isolation(authed_user, db_session):
    user_a, client = authed_user
    a = (await client.post("/me/saved-searches/", json=_body(name="A-secret"))).json()
    # Switch to user B (login_as overwrites the cookie on the same client).
    await login_as(client, db_session, character_id=91000002, character_name="Bravo", owner_hash="OWN2")
    b_list = (await client.get("/me/saved-searches/")).json()
    assert all(s["id"] != a["id"] for s in b_list)  # B never sees A's row
    assert (await client.put(f"/me/saved-searches/{a['id']}", json={"name": "hijack"})).status_code == 404
    assert (await client.delete(f"/me/saved-searches/{a['id']}")).status_code == 404


# ---------- 409 duplicate name via the real constraint (no pre-check) ----------
@pytest.mark.asyncio
async def test_duplicate_name_409_and_leaves_one_row(authed_user):
    user, client = authed_user
    assert (await client.post("/me/saved-searches/", json=_body(name="Dup"))).status_code == 201
    assert (await client.post("/me/saved-searches/", json=_body(name="Dup"))).status_code == 409
    # The 409 must NOT have rolled back the first row (savepoint discipline).
    dups = [s for s in (await client.get("/me/saved-searches/")).json() if s["name"] == "Dup"]
    assert len(dups) == 1


@pytest.mark.asyncio
async def test_rename_to_existing_name_409(authed_user):
    user, client = authed_user
    a = (await client.post("/me/saved-searches/", json=_body(name="A"))).json()
    b = (await client.post("/me/saved-searches/", json=_body(name="B"))).json()
    assert (await client.put(f"/me/saved-searches/{b['id']}", json={"name": "A"})).status_code == 409
    # B keeps its own name; A untouched.
    by_id = {s["id"]: s["name"] for s in (await client.get("/me/saved-searches/")).json()}
    assert by_id[b["id"]] == "B" and by_id[a["id"]] == "A"


# ---------- per-user cap (best-effort, sequential — design §3.5) ----------
@pytest.mark.asyncio
async def test_cap_returns_400(authed_user, monkeypatch):
    from fastapi_app.core.config import settings
    monkeypatch.setattr(settings, "MAX_SAVED_SEARCHES_PER_USER", 2)
    user, client = authed_user
    for i in range(2):
        assert (await client.post("/me/saved-searches/", json=_body(name=f"S{i}"))).status_code == 201
    resp = await client.post("/me/saved-searches/", json=_body(name="S2"))
    assert resp.status_code == 400
    assert "limit" in resp.json()["detail"].lower()


# ---------- 422 validation (bad search_parameters + name) ----------
@pytest.mark.asyncio
async def test_validation_422(authed_user):
    user, client = authed_user
    assert (await client.post("/me/saved-searches/", json=_body(search="ab"))).status_code == 422       # short search
    assert (await client.post("/me/saved-searches/", json=_body(min_price=-1))).status_code == 422      # negative price
    assert (await client.post("/me/saved-searches/", json=_body(min_me=5))).status_code == 422          # unknown key (extra=forbid)
    assert (await client.post("/me/saved-searches/", json={"search_parameters": {}})).status_code == 422  # missing name
    assert (await client.post("/me/saved-searches/", json=_body(name="   "))).status_code == 422         # blank name


# ---------- app.openapi() schema assertions ----------
def test_saved_searches_schema_bare_and_declares_errors():
    schema = app.openapi()
    assert "/me/saved-searches/" in schema["paths"]
    assert "/me/saved-searches/{search_id}" in schema["paths"]
    assert not any(p.startswith("/api/v1") for p in schema["paths"])  # PROXY-1 sentinel
    post_responses = schema["paths"]["/me/saved-searches/"]["post"]["responses"]
    for code in ("400", "401", "409"):
        assert code in post_responses
        assert post_responses[code]["content"]["application/json"]["schema"]["$ref"].endswith("ErrorDetail")
    put_responses = schema["paths"]["/me/saved-searches/{search_id}"]["put"]["responses"]
    assert "404" in put_responses and "409" in put_responses
    comps = schema["components"]["schemas"]
    assert comps["SavedSearchParameters"]["additionalProperties"] is False  # extra="forbid"
