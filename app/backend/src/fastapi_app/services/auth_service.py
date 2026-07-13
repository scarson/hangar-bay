# ABOUTME: User upsert (owner-hash transfer rule) + token encrypt/store + invalid-grant nulling.
# ABOUTME: Hangar Bay data follows the character on owner-hash change (F004 Criterion 1.6, §4.1).
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core import token_cipher
from ..models import User
from .sso import VerifiedIdentity


async def upsert_user(db: AsyncSession, identity: VerifiedIdentity, tokens: dict) -> User:
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(seconds=int(tokens["expires_in"]))
    user = (
        await db.execute(select(User).where(User.character_id == identity.character_id))
    ).scalar_one_or_none()

    if user is None:
        user = User(character_id=identity.character_id)
        db.add(user)

    # Owner-hash transfer: on mismatch we update in place — data follows the character.
    user.character_name = identity.character_name
    user.owner_hash = identity.owner_hash
    user.esi_access_token = token_cipher.encrypt_token(tokens["access_token"])
    # Zero-scope logins carry no refresh_token key (D-DELTA-2); store NULL, never "".
    refresh_token = tokens.get("refresh_token")
    user.esi_refresh_token = (
        token_cipher.encrypt_token(refresh_token) if refresh_token is not None else None
    )
    user.esi_access_token_expires_at = expires_at
    user.last_login_at = now

    await db.flush()
    return user


async def mark_for_reauth(db: AsyncSession, user: User) -> None:
    """Invalid-grant handling (§4.3): null the esi_* columns only.
    The session-invalidation half is deferred to M3's token-using caller."""
    user.esi_access_token = None
    user.esi_refresh_token = None
    user.esi_access_token_expires_at = None
    await db.flush()
