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
