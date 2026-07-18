# ABOUTME: HTTP-level EVE SSO flow — login params, callback exits, cookies, /me, 503-not-configured.
# ABOUTME: Every callback exit is driven end-to-end over ASGITransport against the fake Valkey.
# NOTE: cookies are set on the client JAR (httpx >= 0.28 deprecates per-request cookies=);
# the auth_client fixture is function-scoped, so jar state cannot leak across tests.
import json
import time
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from fastapi_app.core import session as sess
from fastapi_app.core.config import settings

CLIENT_ID = "test-client"
TOKEN_URL = settings.ESI_SSO_TOKEN_URL


@pytest.fixture(scope="module")
def rsa_keypair():
    priv = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return priv, priv.public_key()


def _sign_access_token(priv, **overrides):
    now = int(time.time())
    claims = {
        "iss": "login.eveonline.com", "sub": "CHARACTER:EVE:91000001",
        "aud": [CLIENT_ID, "EVE Online"], "name": "Sesta Hound", "owner": "OWN1",
        "exp": now + 1200, "iat": now,
    }
    claims.update(overrides)
    return jwt.encode(claims, priv, algorithm="RS256", headers={"kid": "JWT-Signature-Key"})


def _inject_jwks(monkeypatch, pub):
    from fastapi_app.api import auth as auth_api
    monkeypatch.setattr(auth_api, "_signing_key_provider", lambda: SimpleNamespace(
        get_signing_key_from_jwt=lambda token: SimpleNamespace(key=pub)))


async def _seed_state(client, state="STATE123", next_="/contracts?type=bpc&page=2"):
    await client.fake_redis.set(f"sso_state:{state}", json.dumps({"next": next_}), ex=600)


def _session_set_cookie(resp):
    """The specific hb_session Set-Cookie header. Never assert on the JOINED header
    string: the hb_sso_state DELETION cookie also carries samesite=lax, which would
    mask a lost attribute on the session cookie."""
    cookies = resp.headers.get_list("set-cookie")
    return next(c for c in cookies if c.startswith(f"{settings.SESSION_COOKIE_NAME}="))


# ---------- login ----------
@pytest.mark.asyncio
async def test_login_redirects_to_authorize_with_exact_params_and_sets_state(auth_client, configured_sso):
    resp = await auth_client.get("/auth/sso/login", params={"next": "/contracts"}, follow_redirects=False)
    assert resp.status_code == 302
    loc = urlsplit(resp.headers["location"])
    assert f"{loc.scheme}://{loc.netloc}{loc.path}" == settings.ESI_SSO_AUTHORIZE_URL
    q = parse_qs(loc.query, keep_blank_values=True)   # parse_qs DROPS blank values by default
    assert q["response_type"] == ["code"] and q["client_id"] == [CLIENT_ID]
    assert q["redirect_uri"] == [settings.ESI_SSO_CALLBACK_URL]
    assert q["scope"] == [""]   # KeyError if scope is missing; must be present AND empty (F004)
    state = q["state"][0]
    assert await auth_client.fake_redis.exists(f"sso_state:{state}") == 1
    assert auth_client.fake_redis.ttl_for(f"sso_state:{state}") == 600
    set_cookie = resp.headers["set-cookie"].lower()
    assert "hb_sso_state=" in set_cookie and "httponly" in set_cookie and "max-age=600" in set_cookie


@pytest.mark.parametrize("bad", ["//evil.com", "/\\evil.com", "https://evil.com", "javascript:alert(1)", "garbage"])
@pytest.mark.asyncio
async def test_login_open_redirect_next_falls_back_to_root(auth_client, configured_sso, bad):
    resp = await auth_client.get("/auth/sso/login", params={"next": bad}, follow_redirects=False)
    state = parse_qs(urlsplit(resp.headers["location"]).query)["state"][0]
    stored = json.loads(await auth_client.fake_redis.get(f"sso_state:{state}"))
    assert stored["next"] == "/"


@pytest.mark.asyncio
async def test_login_without_next_param_stores_root(auth_client, configured_sso):
    # Spec §6's "missing" case, pinned over HTTP: FastAPI's query binding of the
    # `next: str = "/"` default is exactly the layer the pure-helper tests never touch.
    resp = await auth_client.get("/auth/sso/login", follow_redirects=False)
    state = parse_qs(urlsplit(resp.headers["location"]).query)["state"][0]
    stored = json.loads(await auth_client.fake_redis.get(f"sso_state:{state}"))
    assert stored["next"] == "/"


# ---------- callback happy path ----------
@pytest.mark.asyncio
async def test_callback_happy_path_creates_user_sets_session_cookie(auth_client, configured_sso, httpx_mock, rsa_keypair, monkeypatch, db_session):
    from sqlalchemy import select
    from fastapi_app.core import token_cipher as tc
    from fastapi_app.models import User
    priv, pub = rsa_keypair
    _inject_jwks(monkeypatch, pub)
    at = _sign_access_token(priv)
    # Zero-scope (F004) wire shape: NO refresh_token key (D-DELTA-2).
    httpx_mock.add_response(url=TOKEN_URL, json={"access_token": at, "expires_in": 1200, "token_type": "Bearer"})
    await _seed_state(auth_client, next_="/contracts?type=bpc&page=2")

    auth_client.cookies.set("hb_sso_state", "STATE123")
    resp = await auth_client.get("/auth/sso/callback", params={"state": "STATE123", "code": "CODE"}, follow_redirects=False)
    assert resp.status_code == 302
    assert resp.headers["location"] == f"{settings.FRONTEND_ORIGIN}/contracts?type=bpc&page=2"  # success: no sso flag, & merge
    assert "hb_session=" in _session_set_cookie(resp)
    state_clear = next(c for c in resp.headers.get_list("set-cookie") if c.startswith("hb_sso_state="))
    assert "max-age=0" in state_clear.lower() or "expires=" in state_clear.lower()   # binding cookie cleared (§4.1 step 4)
    user = (await db_session.execute(select(User).where(User.character_id == 91000001))).scalar_one()
    assert user.esi_access_token != at                       # ciphertext, not plaintext
    assert tc.decrypt_token(user.esi_access_token) == at     # real Fernet round-trip under the fixture key
    assert user.esi_refresh_token is None                    # zero scopes ⇒ no refresh token (D-DELTA-2)


# ---------- callback binding / state exits ----------
@pytest.mark.asyncio
async def test_callback_binding_cookie_missing_hard_400(auth_client, configured_sso):
    await _seed_state(auth_client)
    resp = await auth_client.get("/auth/sso/callback", params={"state": "STATE123", "code": "CODE"}, follow_redirects=False)
    assert resp.status_code == 400     # GETDEL hit but no hb_sso_state cookie → binding check fails
    assert resp.json() == {"detail": "Invalid SSO state"}
    state_clear = next(c for c in resp.headers.get_list("set-cookie") if c.startswith("hb_sso_state="))
    assert "max-age=0" in state_clear.lower() or "expires=" in state_clear.lower()   # cleared even on the 400 exit


@pytest.mark.asyncio
async def test_callback_binding_cookie_mismatch_hard_400(auth_client, configured_sso):
    await _seed_state(auth_client)
    auth_client.cookies.set("hb_sso_state", "DIFFERENT")
    resp = await auth_client.get("/auth/sso/callback", params={"state": "STATE123", "code": "CODE"}, follow_redirects=False)
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_callback_state_missing_redirects_sso_error_no_session(auth_client, configured_sso):
    auth_client.cookies.set("hb_sso_state", "GONE")
    resp = await auth_client.get("/auth/sso/callback", params={"state": "GONE", "code": "CODE"}, follow_redirects=False)
    assert resp.status_code == 302
    assert resp.headers["location"] == f"{settings.FRONTEND_ORIGIN}/?sso=error"
    assert "hb_session=" not in resp.headers.get("set-cookie", "")


@pytest.mark.asyncio
async def test_callback_eve_denial_redirects_sso_denied_merged(auth_client, configured_sso):
    await _seed_state(auth_client, next_="/contracts?type=bpc&page=2")
    auth_client.cookies.set("hb_sso_state", "STATE123")
    resp = await auth_client.get("/auth/sso/callback", params={"state": "STATE123", "error": "access_denied"}, follow_redirects=False)
    assert resp.headers["location"] == f"{settings.FRONTEND_ORIGIN}/contracts?type=bpc&page=2&sso=denied"


@pytest.mark.asyncio
async def test_callback_denial_wins_over_binding_mismatch(auth_client, configured_sso):
    # Pins the sanctioned ordering (Task 6.2 exit A): denial short-circuits BEFORE the
    # binding check — no session is minted on denial, so the friendly redirect beats
    # the hard 400 for an innocent user whose cookie went stale mid-flow.
    await _seed_state(auth_client, next_="/contracts")
    auth_client.cookies.set("hb_sso_state", "SOMETHING-ELSE")
    resp = await auth_client.get("/auth/sso/callback", params={"state": "STATE123", "error": "access_denied"}, follow_redirects=False)
    assert resp.status_code == 302
    assert resp.headers["location"] == f"{settings.FRONTEND_ORIGIN}/contracts?sso=denied"
    assert "hb_session=" not in resp.headers.get("set-cookie", "")


@pytest.mark.asyncio
async def test_callback_token_non_200_redirects_sso_error_and_logs_outcome(auth_client, configured_sso, httpx_mock, caplog, capsys):
    import logging
    httpx_mock.add_response(url=TOKEN_URL, status_code=400, json={"error": "invalid_grant"})
    await _seed_state(auth_client, next_="/contracts")
    auth_client.cookies.set("hb_sso_state", "STATE123")
    with caplog.at_level(logging.INFO):
        resp = await auth_client.get("/auth/sso/callback", params={"state": "STATE123", "code": "BAD"}, follow_redirects=False)
    assert resp.headers["location"] == f"{settings.FRONTEND_ORIGIN}/contracts?sso=error"
    # Structured failure log (§4.1 step 5). structlog's test-time sink depends on
    # whether setup_logging ran (it does not under ASGITransport) — capture BOTH
    # channels so the assertion is sink-agnostic.
    combined = caplog.text + capsys.readouterr().out
    assert "token_exchange_failed" in combined


@pytest.mark.asyncio
async def test_callback_jwt_failure_redirects_sso_error_and_never_logs_the_token(auth_client, configured_sso, httpx_mock, rsa_keypair, monkeypatch, caplog, capsys):
    import logging
    priv, pub = rsa_keypair
    _inject_jwks(monkeypatch, pub)
    bad_token = _sign_access_token(priv, iss="evil.example.com")
    httpx_mock.add_response(url=TOKEN_URL, json={"access_token": bad_token, "expires_in": 1200, "token_type": "Bearer"})
    await _seed_state(auth_client, next_="/contracts")
    auth_client.cookies.set("hb_sso_state", "STATE123")
    with caplog.at_level(logging.INFO):
        resp = await auth_client.get("/auth/sso/callback", params={"state": "STATE123", "code": "CODE"}, follow_redirects=False)
    assert resp.headers["location"] == f"{settings.FRONTEND_ORIGIN}/contracts?sso=error"
    combined = caplog.text + capsys.readouterr().out
    assert "jwt_validation_failed" in combined
    assert bad_token not in combined     # §7: never token material in logs


@pytest.mark.asyncio
async def test_callback_unknown_kid_redirects_sso_error_not_500(auth_client, configured_sso, httpx_mock, rsa_keypair, monkeypatch):
    # A kid miss surfaces as PyJWKClientError inside validation → mapped to SsoJwtError
    # (Phase 4) → the callback's sso=error redirect, never an unhandled 500.
    from jwt.exceptions import PyJWKClientError
    from fastapi_app.api import auth as auth_api
    priv, _pub = rsa_keypair

    def _raise(token):
        raise PyJWKClientError("Unable to find a signing key that matches")

    monkeypatch.setattr(auth_api, "_signing_key_provider",
                        lambda: SimpleNamespace(get_signing_key_from_jwt=_raise))
    httpx_mock.add_response(url=TOKEN_URL, json={"access_token": _sign_access_token(priv), "expires_in": 1200, "token_type": "Bearer"})
    await _seed_state(auth_client, next_="/contracts")
    auth_client.cookies.set("hb_sso_state", "STATE123")
    resp = await auth_client.get("/auth/sso/callback", params={"state": "STATE123", "code": "CODE"}, follow_redirects=False)
    assert resp.status_code == 302     # not a 500
    assert resp.headers["location"] == f"{settings.FRONTEND_ORIGIN}/contracts?sso=error"


@pytest.mark.parametrize("evil_next", ["//evil.com", "/\\evil.com"])
@pytest.mark.asyncio
async def test_callback_never_yields_protocol_relative_location(auth_client, configured_sso, evil_next):
    # A malformed or externally-pointing next in Valkey is re-validated at the callback (§7).
    await auth_client.fake_redis.set("sso_state:STATE123", json.dumps({"next": evil_next}), ex=600)
    auth_client.cookies.set("hb_sso_state", "STATE123")
    resp = await auth_client.get("/auth/sso/callback", params={"state": "STATE123", "error": "access_denied"}, follow_redirects=False)
    assert resp.headers["location"] == f"{settings.FRONTEND_ORIGIN}/?sso=denied"


@pytest.mark.asyncio
async def test_callback_malformed_state_json_redirects_sso_error_not_500(auth_client, configured_sso):
    # Finding 8a: a truncated/undecodable stored state value must not 500 the
    # callback — it must fall through the same path as a missing/expired state.
    await auth_client.fake_redis.set("sso_state:STATE123", "{not valid json", ex=600)
    auth_client.cookies.set("hb_sso_state", "STATE123")
    resp = await auth_client.get("/auth/sso/callback", params={"state": "STATE123", "code": "CODE"}, follow_redirects=False)
    assert resp.status_code == 302
    assert resp.headers["location"] == f"{settings.FRONTEND_ORIGIN}/?sso=error"
    state_clear = next(c for c in resp.headers.get_list("set-cookie") if c.startswith("hb_sso_state="))
    assert "max-age=0" in state_clear.lower() or "expires=" in state_clear.lower()


@pytest.mark.asyncio
async def test_callback_state_payload_not_object_redirects_sso_error_not_500(auth_client, configured_sso):
    await auth_client.fake_redis.set("sso_state:STATE123", json.dumps(["not", "an", "object"]), ex=600)
    auth_client.cookies.set("hb_sso_state", "STATE123")
    resp = await auth_client.get("/auth/sso/callback", params={"state": "STATE123", "code": "CODE"}, follow_redirects=False)
    assert resp.status_code == 302
    assert resp.headers["location"] == f"{settings.FRONTEND_ORIGIN}/?sso=error"


@pytest.mark.asyncio
async def test_callback_state_payload_missing_next_redirects_sso_error_not_500(auth_client, configured_sso):
    await auth_client.fake_redis.set("sso_state:STATE123", json.dumps({"foo": "bar"}), ex=600)
    auth_client.cookies.set("hb_sso_state", "STATE123")
    resp = await auth_client.get("/auth/sso/callback", params={"state": "STATE123", "code": "CODE"}, follow_redirects=False)
    assert resp.status_code == 302
    assert resp.headers["location"] == f"{settings.FRONTEND_ORIGIN}/?sso=error"


@pytest.mark.asyncio
async def test_callback_denial_with_malformed_state_payload_falls_back_to_root(auth_client, configured_sso):
    # Exit (A) also indexes stored["next"] — a malformed-but-present state payload
    # must fall back to "/" rather than 500 on the denial path too.
    await auth_client.fake_redis.set("sso_state:STATE123", json.dumps({"foo": "bar"}), ex=600)
    auth_client.cookies.set("hb_sso_state", "STATE123")
    resp = await auth_client.get("/auth/sso/callback", params={"state": "STATE123", "error": "access_denied"}, follow_redirects=False)
    assert resp.status_code == 302
    assert resp.headers["location"] == f"{settings.FRONTEND_ORIGIN}/?sso=denied"


@pytest.mark.asyncio
async def test_callback_upsert_user_failure_redirects_sso_error_not_500(
    auth_client, configured_sso, httpx_mock, rsa_keypair, monkeypatch
):
    # Finding 8b: exit F (upsert_user) must never 500 the callback — any error
    # there takes the same sso=error redirect as the earlier exchange/JWT exits.
    from fastapi_app.api import auth as auth_api
    priv, pub = rsa_keypair
    _inject_jwks(monkeypatch, pub)
    httpx_mock.add_response(
        url=TOKEN_URL, json={"access_token": _sign_access_token(priv), "expires_in": 1200, "token_type": "Bearer"}
    )
    await _seed_state(auth_client, next_="/contracts")
    auth_client.cookies.set("hb_sso_state", "STATE123")

    async def _boom(db, identity, tokens):
        raise RuntimeError("db exploded")

    monkeypatch.setattr(auth_api.auth_service, "upsert_user", _boom)

    resp = await auth_client.get("/auth/sso/callback", params={"state": "STATE123", "code": "CODE"}, follow_redirects=False)
    assert resp.status_code == 302
    assert resp.headers["location"] == f"{settings.FRONTEND_ORIGIN}/contracts?sso=error"
    assert "hb_session=" not in resp.headers.get("set-cookie", "")


@pytest.mark.asyncio
async def test_callback_upsert_integrity_error_rolls_back_not_500(
    auth_client, configured_sso, httpx_mock, rsa_keypair, monkeypatch, db_session
):
    # Finding 2: a failing flush at exit F poisons the DB transaction. Without a
    # rollback in the exception handler the session stays poisoned, so get_db's
    # post-request commit() raises PendingRollbackError and turns the intended
    # sso=error redirect into a 500. This is the M2-reachable first-login race in
    # miniature: two concurrent same-character callbacks both insert character_id
    # -> IntegrityError.
    #
    # auth_client's default get_db override returns the begin()-wrapped db_session,
    # which never runs get_db's post-yield commit — the exact step that 500s. So
    # model production get_db faithfully here: a plain session (no begin() wrapper)
    # that commits after the request and rolls back + re-raises on error, on the
    # same test engine (tables already created by the db_session fixture).
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from fastapi_app.api import auth as auth_api
    from fastapi_app.db import get_db
    from fastapi_app.main import app as real_app
    from fastapi_app.models import User

    # Own async engine against the test DB (tables already created + committed by
    # the db_session fixture, so a separate connection sees them).
    engine = create_async_engine(str(settings.DATABASE_URL_TESTS), echo=False)
    maker = async_sessionmaker(bind=engine, expire_on_commit=False)

    async def _production_get_db():
        async with maker() as s:
            try:
                yield s
                await s.commit()
            except Exception:
                await s.rollback()
                raise

    real_app.dependency_overrides[get_db] = _production_get_db

    priv, pub = rsa_keypair
    _inject_jwks(monkeypatch, pub)
    httpx_mock.add_response(
        url=TOKEN_URL, json={"access_token": _sign_access_token(priv), "expires_in": 1200, "token_type": "Bearer"}
    )
    await _seed_state(auth_client, next_="/contracts")
    auth_client.cookies.set("hb_sso_state", "STATE123")

    async def _racing_upsert(db, identity, tokens):
        db.add(User(character_id=identity.character_id))
        await db.flush()                       # first insert lands
        db.add(User(character_id=identity.character_id))
        await db.flush()                       # duplicate character_id -> IntegrityError, poisons the session

    monkeypatch.setattr(auth_api.auth_service, "upsert_user", _racing_upsert)

    resp = await auth_client.get("/auth/sso/callback", params={"state": "STATE123", "code": "CODE"}, follow_redirects=False)
    assert resp.status_code == 302     # not a 500 from get_db committing a poisoned transaction
    assert resp.headers["location"] == f"{settings.FRONTEND_ORIGIN}/contracts?sso=error"
    assert "hb_session=" not in resp.headers.get("set-cookie", "")

    # The rollback undid the poisoned insert: a fresh session sees no rows, proving
    # both that the transaction was recovered and that nothing partial persisted.
    async with maker() as verify:
        rows = (await verify.execute(select(User))).scalars().all()
    assert rows == []
    await engine.dispose()


@pytest.mark.asyncio
async def test_callback_503_not_configured_clears_state_cookie(auth_client, monkeypatch):
    # Finding 8c: the shared not-configured guard runs before the callback body,
    # so it must clear hb_sso_state itself (defense-in-depth — the state is
    # unconsumed on a 503, but the cookie shouldn't be left stale on the browser).
    from pydantic import SecretStr
    monkeypatch.setattr(settings, "ESI_CLIENT_ID", "test-client")
    monkeypatch.setattr(settings, "TOKEN_CIPHER_KEYS", SecretStr("   "))
    auth_client.cookies.set("hb_sso_state", "STATE123")
    resp = await auth_client.get("/auth/sso/callback", params={"state": "STATE123", "code": "C"}, follow_redirects=False)
    assert resp.status_code == 503
    state_clear = next(
        (c for c in resp.headers.get_list("set-cookie") if c.startswith("hb_sso_state=")), None
    )
    assert state_clear is not None
    assert "max-age=0" in state_clear.lower() or "expires=" in state_clear.lower()


@pytest.mark.asyncio
async def test_callback_owner_hash_transfer(auth_client, configured_sso, httpx_mock, rsa_keypair, monkeypatch, db_session):
    from sqlalchemy import select
    from fastapi_app.models import User
    priv, pub = rsa_keypair
    _inject_jwks(monkeypatch, pub)
    # first login
    httpx_mock.add_response(url=TOKEN_URL, json={"access_token": _sign_access_token(priv, owner="OWN1"), "expires_in": 1200, "token_type": "Bearer"})
    await _seed_state(auth_client, state="S1")
    auth_client.cookies.set("hb_sso_state", "S1")
    await auth_client.get("/auth/sso/callback", params={"state": "S1", "code": "C"}, follow_redirects=False)
    # Second login, new owner hash. Re-set the jar cookie explicitly: the response's
    # deletion Set-Cookie targets a host-scoped jar entry, NOT the domain-less entry
    # cookies.set() created, so each callback must set its own binding cookie.
    httpx_mock.add_response(url=TOKEN_URL, json={"access_token": _sign_access_token(priv, owner="OWN2"), "expires_in": 1200, "token_type": "Bearer"})
    await _seed_state(auth_client, state="S2")
    auth_client.cookies.set("hb_sso_state", "S2")
    await auth_client.get("/auth/sso/callback", params={"state": "S2", "code": "C"}, follow_redirects=False)
    rows = (await db_session.execute(select(User).where(User.character_id == 91000001))).scalars().all()
    assert len(rows) == 1 and rows[0].owner_hash == "OWN2"


# ---------- state single-use ([TIMING]) ----------
@pytest.mark.asyncio
async def test_state_is_single_use(auth_client, configured_sso):
    await _seed_state(auth_client, state="ONCE")
    # First callback: binding MISMATCH → hard 400 — but the GETDEL has already consumed
    # the state. (A matching cookie here would reach the code exchange, exit (D) —
    # blocked from the real network by the fixture's structural httpx_mock, but the
    # test would then fail confusingly at teardown instead of pinning single-use.)
    auth_client.cookies.set("hb_sso_state", "OTHER")
    resp1 = await auth_client.get("/auth/sso/callback", params={"state": "ONCE", "code": "C"}, follow_redirects=False)
    assert resp1.status_code == 400
    assert await auth_client.fake_redis.exists("sso_state:ONCE") == 0     # consumed even on the 400 exit
    # Second callback, now with a MATCHING cookie: GETDEL miss → innocent sso=error redirect, NOT a 400.
    auth_client.cookies.set("hb_sso_state", "ONCE")
    resp2 = await auth_client.get("/auth/sso/callback", params={"state": "ONCE", "code": "C"}, follow_redirects=False)
    assert resp2.status_code == 302 and resp2.headers["location"] == f"{settings.FRONTEND_ORIGIN}/?sso=error"


# ---------- cookie attributes ----------
@pytest.mark.parametrize("env,expect_secure", [("production", True), ("test", True), ("development", False)])
@pytest.mark.asyncio
async def test_session_cookie_attributes_and_secure_flag(auth_client, configured_sso, httpx_mock, rsa_keypair, monkeypatch, env, expect_secure):
    monkeypatch.setattr(settings, "ENVIRONMENT", env)
    priv, pub = rsa_keypair
    _inject_jwks(monkeypatch, pub)
    httpx_mock.add_response(url=TOKEN_URL, json={"access_token": _sign_access_token(priv), "expires_in": 1200, "token_type": "Bearer"})
    await _seed_state(auth_client, state="ENVS")
    auth_client.cookies.set("hb_sso_state", "ENVS")
    resp = await auth_client.get("/auth/sso/callback", params={"state": "ENVS", "code": "C"}, follow_redirects=False)
    sc = _session_set_cookie(resp).lower()   # ONLY the hb_session cookie — see helper docstring
    assert "httponly" in sc and "samesite=lax" in sc
    assert "path=/" in sc
    assert f"max-age={settings.SESSION_ABSOLUTE_TTL_SECONDS}" in sc   # §4.2: Max-Age = 30-day absolute cap
    assert ("secure" in sc) is expect_secure


# ---------- logout ----------
@pytest.mark.asyncio
async def test_logout_is_idempotent_204_and_expires_cookie(auth_client, configured_sso):
    # no session present → still 204 (not gated behind get_current_session)
    resp = await auth_client.post("/auth/sso/logout")
    assert resp.status_code == 204
    sc = resp.headers.get("set-cookie", "").lower()
    assert "hb_session=" in sc
    assert "max-age=0" in sc or "expires=" in sc   # actually EXPIRING, not (re)setting a live value


@pytest.mark.asyncio
async def test_logout_deletes_existing_session(auth_client, configured_sso):
    sid = await sess.create_session(auth_client.fake_redis, user_id=1, character_id=91000001, character_name="X")
    auth_client.cookies.set(settings.SESSION_COOKIE_NAME, sid)
    resp = await auth_client.post("/auth/sso/logout")
    assert resp.status_code == 204
    assert await auth_client.fake_redis.exists(f"session:{sid}") == 0


# ---------- /me ----------
@pytest.mark.asyncio
async def test_me_401_when_anonymous(auth_client, configured_sso):
    resp = await auth_client.get("/me")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_me_200_from_session_payload(auth_client, configured_sso):
    sid = await sess.create_session(auth_client.fake_redis, user_id=1, character_id=91000001, character_name="Sesta Hound")
    auth_client.cookies.set(settings.SESSION_COOKIE_NAME, sid)
    resp = await auth_client.get("/me")
    assert resp.status_code == 200
    assert resp.json() == {"character_id": 91000001, "character_name": "Sesta Hound"}


# ---------- not-configured (AC-4) ----------
@pytest.mark.asyncio
async def test_login_503_when_not_configured(auth_client, monkeypatch):
    from pydantic import SecretStr
    monkeypatch.setattr(settings, "ESI_CLIENT_ID", "")
    monkeypatch.setattr(settings, "TOKEN_CIPHER_KEYS", SecretStr(""))
    resp = await auth_client.get("/auth/sso/login", follow_redirects=False)
    assert resp.status_code == 503 and resp.json() == {"detail": "EVE SSO is not configured"}


@pytest.mark.asyncio
async def test_callback_503_when_cipher_unconfigured_not_500(auth_client, monkeypatch):
    from pydantic import SecretStr
    monkeypatch.setattr(settings, "ESI_CLIENT_ID", "test-client")
    monkeypatch.setattr(settings, "TOKEN_CIPHER_KEYS", SecretStr("   "))   # whitespace ⇒ not configured
    resp = await auth_client.get("/auth/sso/callback", params={"state": "X", "code": "C"}, follow_redirects=False)
    assert resp.status_code == 503     # guard fires before any cipher/exchange — never a 500 from MultiFernet([])


@pytest.mark.asyncio
async def test_logout_works_when_sso_not_configured(auth_client, monkeypatch):
    # §4.4: logout is intentionally NOT behind the not-configured guard, so an existing
    # session can always be cleared even when the SSO credentials are absent.
    from pydantic import SecretStr
    monkeypatch.setattr(settings, "ESI_CLIENT_ID", "")
    monkeypatch.setattr(settings, "TOKEN_CIPHER_KEYS", SecretStr(""))
    sid = await sess.create_session(auth_client.fake_redis, user_id=1, character_id=91000001, character_name="X")
    auth_client.cookies.set(settings.SESSION_COOKIE_NAME, sid)
    resp = await auth_client.post("/auth/sso/logout")
    assert resp.status_code == 204
    assert await auth_client.fake_redis.exists(f"session:{sid}") == 0


@pytest.mark.asyncio
async def test_me_works_when_sso_not_configured(auth_client, monkeypatch):
    # §4.4: /me reads only the session payload and is NOT behind the not-configured guard,
    # so an already-authenticated identity survives SSO being unconfigured.
    from pydantic import SecretStr
    monkeypatch.setattr(settings, "ESI_CLIENT_ID", "")
    monkeypatch.setattr(settings, "TOKEN_CIPHER_KEYS", SecretStr(""))
    sid = await sess.create_session(auth_client.fake_redis, user_id=1, character_id=91000001, character_name="Sesta Hound")
    auth_client.cookies.set(settings.SESSION_COOKIE_NAME, sid)
    resp = await auth_client.get("/me")
    assert resp.status_code == 200
    assert resp.json() == {"character_id": 91000001, "character_name": "Sesta Hound"}
