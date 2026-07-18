# ABOUTME: User upsert (owner-hash transfer rule) + token encrypt/store + invalid-grant nulling.
# ABOUTME: Hangar Bay data follows the character on owner-hash change (F004 Criterion 1.6, §4.1).
from datetime import datetime, timedelta, timezone

import httpx
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from ..core import token_cipher
from ..core.config import get_settings
from ..models import User
from . import sso
from .sso import VerifiedIdentity


async def upsert_user(db: AsyncSession, identity: VerifiedIdentity, tokens: dict) -> User:
    # Race-safe first login: INSERT ... ON CONFLICT (character_id) DO UPDATE so two simultaneous
    # first logins for the same character_id both succeed against the single row (the loser updates
    # the winner's row instead of raising IntegrityError). Owner-hash transfer stays: on any login
    # the mutable identity/token columns are overwritten — data follows the character (§4.1).
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(seconds=int(tokens["expires_in"]))
    encrypted_access = token_cipher.encrypt_token(tokens["access_token"])
    # Zero-scope logins carry no refresh_token key (D-DELTA-2); store NULL, never "".
    refresh_token = tokens.get("refresh_token")
    encrypted_refresh = (
        token_cipher.encrypt_token(refresh_token) if refresh_token is not None else None
    )
    mutable = {
        "character_name": identity.character_name,
        "owner_hash": identity.owner_hash,
        "esi_access_token": encrypted_access,
        "esi_refresh_token": encrypted_refresh,
        "esi_access_token_expires_at": expires_at,
        "last_login_at": now,
    }
    stmt = (
        pg_insert(User)
        .values(character_id=identity.character_id, **mutable)
        .on_conflict_do_update(
            index_elements=["character_id"],
            set_={**mutable, "updated_at": func.now()},
        )
    )
    await db.execute(stmt)
    # Re-select with populate_existing so an already-identity-mapped instance (e.g. a prior
    # upsert in the same session) is refreshed with the new column values, and so the returned
    # ORM row is fully loaded (no expired server-default columns) for the caller.
    user = (
        await db.execute(
            select(User)
            .where(User.character_id == identity.character_id)
            .execution_options(populate_existing=True)
        )
    ).scalar_one()
    return user


async def mark_for_reauth(db: AsyncSession, user: User) -> None:
    """Invalid-grant handling (§4.3): null the esi_* columns only.
    The session-invalidation half is deferred to M3's token-using caller."""
    user.esi_access_token = None
    user.esi_refresh_token = None
    user.esi_access_token_expires_at = None
    await db.flush()


async def refresh_user_tokens(db: AsyncSession, http_client: "httpx.AsyncClient", user: User) -> None:
    """Refresh a user's ESI tokens on demand (§4.3). Persists the returned refresh
    token when the response carries one; keeps the stored one when it doesn't
    (§2.7: rotation is optional). Only an invalid-grant-shaped 400 — or a vault
    entry the current keyring cannot decrypt (§7) — marks the user for re-auth
    (nulls the esi_* columns); 5xx and transport failures re-raise with the vault
    untouched. No M2 endpoint calls this — M3's token-using caller does."""
    from cryptography.fernet import InvalidToken

    from ..core import token_cipher
    s = get_settings()
    if user.esi_refresh_token is None:
        # Zero-scope logins bank no refresh token (D-DELTA-2): already the re-auth state.
        await mark_for_reauth(db, user)
        return
    try:
        refresh_token = token_cipher.decrypt_token(user.esi_refresh_token)
    except InvalidToken:
        # Rotated-away/wrong keyring: treated as missing tokens (§7), never a 500.
        await mark_for_reauth(db, user)
        return
    try:
        tokens = await sso.refresh_token_pair(
            http_client, refresh_token=refresh_token, token_url=s.ESI_SSO_TOKEN_URL,
            client_id=s.ESI_CLIENT_ID, client_secret=s.ESI_CLIENT_SECRET.get_secret_value(),
        )
    except sso.SsoTokenError as exc:
        # TODO(M3): not every 400 here is actually invalid_grant (EVE can 400 for
        # other request-shape reasons too) — this should discriminate on the
        # response body's error field, not status_code alone. Also: concurrent
        # callers refreshing the same user's tokens can race on this read-modify-
        # write (no row lock / optimistic version check); needs a concurrency-safe
        # rotation strategy. Deferred: no M2 endpoint calls refresh_user_tokens —
        # it's M3 foundation only.
        if exc.status_code == 400:   # invalid-grant shape: the grant itself is dead
            await mark_for_reauth(db, user)
            return
        raise                        # outage (5xx/transport): surface it, keep the vault
    now = datetime.now(timezone.utc)
    user.esi_access_token = token_cipher.encrypt_token(tokens["access_token"])
    returned_refresh = tokens.get("refresh_token")
    if returned_refresh is not None:
        user.esi_refresh_token = token_cipher.encrypt_token(returned_refresh)  # persist rotation
    user.esi_access_token_expires_at = now + timedelta(seconds=int(tokens["expires_in"]))
    await db.flush()
