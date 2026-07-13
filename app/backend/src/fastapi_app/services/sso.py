# ABOUTME: EVE SSO protocol — authorize URL, code exchange, refresh grant, local JWT validation.
# ABOUTME: JWKS comes through an injectable key-provider seam so the validator runs for real in tests (§3.2).
from dataclasses import dataclass
from typing import Optional, Protocol
from urllib.parse import urlencode

import httpx
import jwt

# EVE presents iss in two historical forms (§2.2); accept exactly these, reject all else.
_VALID_ISSUERS = frozenset({"login.eveonline.com", "https://login.eveonline.com"})
_ALGORITHMS = ["RS256", "ES256"]   # never HS256 (§2.5 — the id_token HS256 metadata is a red herring)
_LEEWAY_SECONDS = 45               # clock-skew tolerance on exp/nbf (§3.2)


class SsoTokenError(Exception):
    """Token-endpoint call failed (non-200 or transport error).

    status_code carries the HTTP status when a response existed (None on transport
    errors) so callers can tell an invalid-grant 400 from a transient outage (§4.3).
    """

    def __init__(self, message: str, *, status_code: Optional[int] = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class SsoJwtError(Exception):
    """JWT signature/claims validation failed."""


@dataclass(frozen=True)
class VerifiedIdentity:
    character_id: int
    character_name: str
    owner_hash: str


class SigningKeyProvider(Protocol):
    def get_signing_key_from_jwt(self, token: str):
        ...


def build_authorize_url(*, state: str, client_id: str, redirect_uri: str, authorize_url: str) -> str:
    params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "scope": "",   # no ESI scopes in F004
        "state": state,
    }
    return f"{authorize_url}?{urlencode(params)}"


async def _post_token(client: httpx.AsyncClient, *, token_url: str, client_id: str, client_secret: str, form: dict) -> dict:
    try:
        resp = await client.post(
            token_url,
            data=form,
            auth=(client_id, client_secret),   # HTTP Basic (§2.8)
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
    except httpx.HTTPError as exc:
        raise SsoTokenError(f"token endpoint transport error: {exc}") from exc
    if resp.status_code != 200:
        # No token material in the log — status only (§7).
        raise SsoTokenError(f"token endpoint returned {resp.status_code}", status_code=resp.status_code)
    return resp.json()


async def exchange_code(client: httpx.AsyncClient, *, code: str, token_url: str, client_id: str, client_secret: str) -> dict:
    return await _post_token(
        client, token_url=token_url, client_id=client_id, client_secret=client_secret,
        form={"grant_type": "authorization_code", "code": code},
    )


async def refresh_token_pair(client: httpx.AsyncClient, *, refresh_token: str, token_url: str, client_id: str, client_secret: str) -> dict:
    return await _post_token(
        client, token_url=token_url, client_id=client_id, client_secret=client_secret,
        form={"grant_type": "refresh_token", "refresh_token": refresh_token},
    )


def validate_access_token(token: str, *, key_provider: SigningKeyProvider, client_id: str) -> VerifiedIdentity:
    """Validate EVE's JWT ACCESS token (not an OIDC id token — §2.1) and extract identity."""
    try:
        signing_key = key_provider.get_signing_key_from_jwt(token)
        claims = jwt.decode(
            token,
            signing_key.key,
            algorithms=_ALGORITHMS,         # kid-selected RS256/ES256; HS256 excluded
            audience=client_id,             # PyJWT requires client_id to be IN the aud array (§2.3)
            leeway=_LEEWAY_SECONDS,         # exp/nbf skew tolerance (§3.2)
            options={"verify_iss": False, "require": ["exp", "sub", "aud"]},
        )
    except (jwt.InvalidTokenError, jwt.exceptions.PyJWKClientError) as exc:
        # PyJWKClientError (kid miss / JWKS fetch failure) is NOT an InvalidTokenError
        # subclass — without this clause a kid miss escapes as a 500 at the callback.
        raise SsoJwtError(f"jwt validation failed: {exc}") from exc

    iss = claims.get("iss")
    if iss not in _VALID_ISSUERS:            # dual-iss allowlist checked explicitly (§2.2)
        raise SsoJwtError(f"unexpected iss: {iss!r}")

    sub = claims.get("sub", "")
    prefix = "CHARACTER:EVE:"
    if not sub.startswith(prefix):
        raise SsoJwtError(f"unexpected sub shape: {sub!r}")
    try:
        character_id = int(sub[len(prefix):])
    except ValueError as exc:
        raise SsoJwtError(f"non-integer character id in sub: {sub!r}") from exc

    name = claims.get("name")
    owner = claims.get("owner")
    if not name or not owner:
        raise SsoJwtError("missing name/owner claim")
    return VerifiedIdentity(character_id=character_id, character_name=name, owner_hash=owner)
