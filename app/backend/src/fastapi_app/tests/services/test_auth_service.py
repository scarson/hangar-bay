# ABOUTME: User upsert (create + owner-hash transfer), token encryption, invalid-grant nulling.
# ABOUTME: Refresh-on-demand: rotation persistence, outages keep the vault, wrong-key/empty-vault re-auth.
import pytest
from cryptography.fernet import Fernet
from pydantic import SecretStr
from sqlalchemy import select

from fastapi_app.core import token_cipher as tc
from fastapi_app.core.config import settings
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
    assert user.esi_access_token_expires_at is not None
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
    await auth_service.upsert_user(db_session, ident1, _tokens())
    ident2 = VerifiedIdentity(character_id=91000001, character_name="New Name", owner_hash="OWN2")
    user = await auth_service.upsert_user(db_session, ident2, {"access_token": "AT2", "expires_in": 1200})
    rows = (await db_session.execute(select(User).where(User.character_id == 91000001))).scalars().all()
    assert len(rows) == 1                          # updated in place, no duplicate row
    assert user.owner_hash == "OWN2"               # ownership transferred
    assert user.character_name == "New Name"
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
    user = await auth_service.upsert_user(db_session, ident, {"access_token": "AT", "refresh_token": "RT_OLD", "expires_in": 1200})
    httpx_mock.add_response(
        url=settings.ESI_SSO_TOKEN_URL,
        json={"access_token": "AT2", "refresh_token": "RT_ROTATED", "expires_in": 1200},
    )
    async with httpx.AsyncClient() as client:
        await auth_service.refresh_user_tokens(db_session, client, user)
    assert tc.decrypt_token(user.esi_access_token) == "AT2"
    assert tc.decrypt_token(user.esi_refresh_token) == "RT_ROTATED"   # rotation persisted


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
