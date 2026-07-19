# ABOUTME: User upsert (create + owner-hash transfer), token encryption, invalid-grant nulling.
# ABOUTME: Refresh-on-demand: rotation persistence, outages keep the vault, wrong-key/empty-vault re-auth.
import asyncio
from datetime import datetime, timedelta, timezone

import pytest
from cryptography.fernet import Fernet
from pydantic import SecretStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from fastapi_app.core import token_cipher as tc
from fastapi_app.core.config import settings
from fastapi_app.db import Base
from fastapi_app.models import User
from fastapi_app.services import auth_service
from fastapi_app.services.sso import VerifiedIdentity


@pytest.fixture(autouse=True)
def _configured_cipher(monkeypatch):
    monkeypatch.setattr(settings, "TOKEN_CIPHER_KEYS", SecretStr(Fernet.generate_key().decode()))


def _tokens():
    # Zero-scope (F004/M2) wire shape: no refresh_token key at all (D-DELTA-2).
    return {"access_token": "AT", "expires_in": 1200}


def _tokens_with_refresh():
    # M3-shaped response — scoped grants return refresh tokens; kept as tested foundation.
    return {"access_token": "AT", "refresh_token": "RT", "expires_in": 1200}


@pytest.mark.asyncio
async def test_upsert_creates_user_and_encrypts_tokens(db_session):
    ident = VerifiedIdentity(character_id=91000001, character_name="Sesta Hound", owner_hash="OWN1")
    user = await auth_service.upsert_user(db_session, ident, _tokens())
    assert user.character_id == 91000001
    assert user.character_name == "Sesta Hound"
    assert user.owner_hash == "OWN1"
    assert user.esi_access_token != "AT"                      # ciphertext, not plaintext
    assert tc.decrypt_token(user.esi_access_token) == "AT"    # round-trips
    assert user.esi_refresh_token is None                     # zero scopes ⇒ no refresh token stored
    # expires_at is now + expires_in (1200s), not a sign-flipped past instant.
    assert user.esi_access_token_expires_at > datetime.now(timezone.utc) + timedelta(seconds=1000)
    assert user.esi_access_token_expires_at < datetime.now(timezone.utc) + timedelta(seconds=1300)
    assert user.last_login_at is not None


@pytest.mark.asyncio
async def test_upsert_encrypts_refresh_token_when_present(db_session):
    # M3-shaped grant: when a refresh token IS returned, it is encrypted and round-trips.
    ident = VerifiedIdentity(character_id=91000001, character_name="Sesta Hound", owner_hash="OWN1")
    user = await auth_service.upsert_user(db_session, ident, _tokens_with_refresh())
    assert user.esi_refresh_token != "RT"
    assert tc.decrypt_token(user.esi_refresh_token) == "RT"


@pytest.mark.asyncio
async def test_upsert_transfers_owner_hash_on_mismatch(db_session):
    ident1 = VerifiedIdentity(character_id=91000001, character_name="Old Name", owner_hash="OWN1")
    first = await auth_service.upsert_user(db_session, ident1, _tokens())
    first_login_at = first.last_login_at
    ident2 = VerifiedIdentity(character_id=91000001, character_name="New Name", owner_hash="OWN2")
    user = await auth_service.upsert_user(db_session, ident2, {"access_token": "AT2", "expires_in": 1200})
    rows = (await db_session.execute(select(User).where(User.character_id == 91000001))).scalars().all()
    assert len(rows) == 1                          # updated in place, no duplicate row
    assert user.owner_hash == "OWN2"               # ownership transferred
    assert user.character_name == "New Name"
    assert user.last_login_at > first_login_at     # re-login refreshes the timestamp in place
    assert tc.decrypt_token(user.esi_access_token) == "AT2"


@pytest.mark.asyncio
async def test_mark_for_reauth_nulls_esi_columns(db_session):
    ident = VerifiedIdentity(character_id=91000001, character_name="Sesta Hound", owner_hash="OWN1")
    user = await auth_service.upsert_user(db_session, ident, _tokens())
    await auth_service.mark_for_reauth(db_session, user)
    assert user.esi_access_token is None
    assert user.esi_refresh_token is None
    assert user.esi_access_token_expires_at is None


@pytest.mark.asyncio
async def test_refresh_user_tokens_persists_rotated_refresh_token(db_session, httpx_mock):
    import httpx
    ident = VerifiedIdentity(character_id=91000001, character_name="Sesta Hound", owner_hash="OWN1")
    # Seed a near-immediate expiry so the post-refresh assertion below can only pass
    # if the REFRESH advanced it — not by inheriting a long upsert-time expiry.
    user = await auth_service.upsert_user(db_session, ident, {"access_token": "AT", "refresh_token": "RT_OLD", "expires_in": 1})
    httpx_mock.add_response(
        url=settings.ESI_SSO_TOKEN_URL,
        json={"access_token": "AT2", "refresh_token": "RT_ROTATED", "expires_in": 1200},
    )
    async with httpx.AsyncClient() as client:
        await auth_service.refresh_user_tokens(db_session, client, user)
    assert tc.decrypt_token(user.esi_access_token) == "AT2"
    assert tc.decrypt_token(user.esi_refresh_token) == "RT_ROTATED"   # rotation persisted
    # the refreshed access token carries a forward expiry, so M3's caller won't re-hit EVE every request.
    assert user.esi_access_token_expires_at > datetime.now(timezone.utc) + timedelta(seconds=1000)


@pytest.mark.asyncio
async def test_refresh_user_tokens_invalid_grant_nulls_columns(db_session, httpx_mock):
    import httpx
    ident = VerifiedIdentity(character_id=91000001, character_name="Sesta Hound", owner_hash="OWN1")
    user = await auth_service.upsert_user(db_session, ident, {"access_token": "AT", "refresh_token": "RT", "expires_in": 1200})
    httpx_mock.add_response(url=settings.ESI_SSO_TOKEN_URL, status_code=400, json={"error": "invalid_grant"})
    async with httpx.AsyncClient() as client:
        await auth_service.refresh_user_tokens(db_session, client, user)
    assert user.esi_access_token is None
    assert user.esi_refresh_token is None
    assert user.esi_access_token_expires_at is None


@pytest.mark.asyncio
async def test_refresh_user_tokens_5xx_leaves_columns_and_raises(db_session, httpx_mock):
    # §4.3: only an invalid-grant-shaped 400 nulls the vault. An EVE outage (5xx)
    # surfaces to the caller with the encrypted tokens untouched.
    import httpx
    from fastapi_app.services import sso
    ident = VerifiedIdentity(character_id=91000001, character_name="Sesta Hound", owner_hash="OWN1")
    user = await auth_service.upsert_user(db_session, ident, {"access_token": "AT", "refresh_token": "RT", "expires_in": 1200})
    httpx_mock.add_response(url=settings.ESI_SSO_TOKEN_URL, status_code=502, json={"error": "bad_gateway"})
    async with httpx.AsyncClient() as client:
        with pytest.raises(sso.SsoTokenError):
            await auth_service.refresh_user_tokens(db_session, client, user)
    assert tc.decrypt_token(user.esi_refresh_token) == "RT"   # vault untouched
    assert user.esi_access_token is not None


@pytest.mark.asyncio
async def test_refresh_user_tokens_transport_error_leaves_columns_and_raises(db_session, httpx_mock):
    import httpx
    from fastapi_app.services import sso
    ident = VerifiedIdentity(character_id=91000001, character_name="Sesta Hound", owner_hash="OWN1")
    user = await auth_service.upsert_user(db_session, ident, {"access_token": "AT", "refresh_token": "RT", "expires_in": 1200})
    httpx_mock.add_exception(httpx.ConnectError("connection refused"), url=settings.ESI_SSO_TOKEN_URL)
    async with httpx.AsyncClient() as client:
        with pytest.raises(sso.SsoTokenError):
            await auth_service.refresh_user_tokens(db_session, client, user)
    assert tc.decrypt_token(user.esi_refresh_token) == "RT"   # vault untouched


@pytest.mark.asyncio
async def test_refresh_user_tokens_without_stored_refresh_token_marks_reauth(db_session, httpx_mock):
    # M2 reality: zero-scope logins bank no refresh token (D-DELTA-2), so M3's caller
    # will meet users with an empty vault — that IS the needs-re-auth state; no HTTP
    # call is attempted. httpx_mock is requested WITH NO responses registered so an
    # accidental request fails loudly and hermetically instead of reaching the network.
    import httpx
    ident = VerifiedIdentity(character_id=91000001, character_name="Sesta Hound", owner_hash="OWN1")
    user = await auth_service.upsert_user(db_session, ident, _tokens())
    async with httpx.AsyncClient() as client:
        await auth_service.refresh_user_tokens(db_session, client, user)
    assert user.esi_access_token is None and user.esi_refresh_token is None


@pytest.mark.asyncio
async def test_refresh_user_tokens_wrong_key_vault_marks_reauth(db_session, httpx_mock, monkeypatch):
    # §7: a vault entry the current keyring cannot decrypt is treated as missing
    # tokens (re-auth path), never an exception. No responses registered — any
    # accidental HTTP call fails loudly.
    import httpx
    ident = VerifiedIdentity(character_id=91000001, character_name="Sesta Hound", owner_hash="OWN1")
    user = await auth_service.upsert_user(db_session, ident, {"access_token": "AT", "refresh_token": "RT", "expires_in": 1200})
    # Swap the keyring so the stored ciphertexts no longer decrypt.
    monkeypatch.setattr(settings, "TOKEN_CIPHER_KEYS", SecretStr(Fernet.generate_key().decode()))
    async with httpx.AsyncClient() as client:
        await auth_service.refresh_user_tokens(db_session, client, user)
    assert user.esi_access_token is None and user.esi_refresh_token is None


@pytest.mark.asyncio
async def test_refresh_response_without_refresh_token_keeps_stored_one(db_session, httpx_mock):
    # §2.7: rotation is optional — a refresh response with no refresh_token key
    # updates the access token and keeps the stored refresh token unchanged.
    import httpx
    ident = VerifiedIdentity(character_id=91000001, character_name="Sesta Hound", owner_hash="OWN1")
    user = await auth_service.upsert_user(db_session, ident, {"access_token": "AT", "refresh_token": "RT", "expires_in": 1200})
    httpx_mock.add_response(url=settings.ESI_SSO_TOKEN_URL, json={"access_token": "AT2", "expires_in": 1200})
    async with httpx.AsyncClient() as client:
        await auth_service.refresh_user_tokens(db_session, client, user)
    assert tc.decrypt_token(user.esi_access_token) == "AT2"
    assert tc.decrypt_token(user.esi_refresh_token) == "RT"   # unchanged, still decryptable


@pytest.mark.asyncio
async def test_concurrent_first_login_both_succeed_single_row():
    # Two genuinely concurrent first logins for the SAME character_id, on independent connections.
    # Blocking is enforced by Postgres's unique-index lock on session A's uncommitted insert — NOT
    # by sleep timing — so the ordering is deterministic. Against the current select-then-insert,
    # session B raises IntegrityError once A commits (RED); against ON CONFLICT DO UPDATE, B lands
    # on A's row (GREEN). This test does NOT take the db_session fixture: both sessions must commit
    # independently, so it manages its own two engines against DATABASE_URL_TESTS.
    url = str(settings.DATABASE_URL_TESTS)
    engine_a = create_async_engine(url)
    engine_b = create_async_engine(url)
    session_a = None
    task_b = None
    try:
        async with engine_a.begin() as conn:   # commit the schema so BOTH connections see the table
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)
        maker_a = async_sessionmaker(engine_a, expire_on_commit=False)
        maker_b = async_sessionmaker(engine_b, expire_on_commit=False)

        ident_a = VerifiedIdentity(character_id=91000001, character_name="First", owner_hash="OWN1")
        ident_b = VerifiedIdentity(character_id=91000001, character_name="Second", owner_hash="OWN2")

        session_a = maker_a()
        user_a = await auth_service.upsert_user(
            session_a, ident_a, {"access_token": "AT1", "expires_in": 1200}
        )   # A's insert is flushed but NOT committed — its unique-index entry now blocks B.

        b_out: dict = {}

        async def _upsert_in_session_b():
            async with maker_b() as session_b:
                b_out["user"] = await auth_service.upsert_user(
                    session_b, ident_b, {"access_token": "AT2", "expires_in": 1200}
                )
                await session_b.commit()

        task_b = asyncio.create_task(_upsert_in_session_b())
        await asyncio.sleep(0.1)     # let B reach its insert and BLOCK on A's lock (a lock wait, not a race)
        assert not task_b.done()     # B is parked on the lock — neither finished nor errored yet

        await session_a.commit()     # release the lock; B now resolves against A's committed row
        await task_b                  # RED: current select-then-insert raises IntegrityError here. GREEN: B succeeds.

        async with maker_a() as verify:
            rows = (
                await verify.execute(select(User).where(User.character_id == 91000001))
            ).scalars().all()
        assert len(rows) == 1                       # exactly one users row — no duplicate
        assert user_a.character_id == 91000001
        assert b_out["user"].character_id == 91000001
        assert rows[0].owner_hash == "OWN2"         # B was the last writer — updated A's row in place
    finally:
        if task_b is not None:       # never orphan the background task (keeps output pristine on failure)
            task_b.cancel()
            try:
                await task_b
            except BaseException:
                pass
        if session_a is not None:    # roll A's tx back BEFORE the DDL drop so it can't deadlock on A's lock
            await session_a.close()
        async with engine_a.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await engine_a.dispose()
        await engine_b.dispose()
