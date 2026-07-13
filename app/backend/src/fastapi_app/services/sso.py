# ABOUTME: EVE SSO protocol — authorize URL, code exchange, refresh grant, local JWT validation.
# ABOUTME: JWKS comes through an injectable key-provider seam so the validator runs for real in tests (m2-eve-sso design spec §3.2; §-refs below cite that spec).
import re
from dataclasses import dataclass
from typing import Optional, Protocol
from urllib.parse import urlencode

import httpx
import jwt

# EVE presents iss in two historical forms (§2.2); accept exactly these, reject all else.
_VALID_ISSUERS = frozenset({"login.eveonline.com", "https://login.eveonline.com"})
_ALGORITHMS = ["RS256", "ES256"]   # never HS256 (§2.5 — the id_token HS256 metadata is a red herring)
_LEEWAY_SECONDS = 45               # clock-skew tolerance on exp/nbf/iat (§3.2)


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


def _validate_token_body(payload: dict, *, status_code: int) -> None:
    """A 200 with a malformed success body (missing/wrong-typed access_token or
    expires_in) must fail here — SsoTokenError is _post_token's declared contract —
    rather than let downstream callers (upsert_user, refresh_token_pair) raise a raw
    KeyError/ValueError and turn the callback into a 500 instead of taking the
    sso=error path."""
    access_token = payload.get("access_token")
    if not isinstance(access_token, str) or not access_token:
        raise SsoTokenError("token endpoint response missing access_token", status_code=status_code)
    expires_in = payload.get("expires_in")
    if expires_in is None or isinstance(expires_in, bool):
        raise SsoTokenError("token endpoint response missing expires_in", status_code=status_code)
    try:
        int(expires_in)
    except (TypeError, ValueError) as exc:
        raise SsoTokenError(
            "token endpoint response has non-numeric expires_in", status_code=status_code
        ) from exc


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
    try:
        payload = resp.json()
    except ValueError as exc:
        raise SsoTokenError("token endpoint returned a non-JSON body", status_code=resp.status_code) from exc
    if not isinstance(payload, dict):
        raise SsoTokenError("token endpoint returned a non-object body", status_code=resp.status_code)
    _validate_token_body(payload, status_code=resp.status_code)
    return payload


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
            leeway=_LEEWAY_SECONDS,         # exp/nbf/iat skew tolerance (§3.2)
            options={"verify_iss": False, "require": ["exp", "sub", "aud"]},
        )
    except (
        jwt.InvalidTokenError,
        jwt.exceptions.PyJWKClientError,
        jwt.exceptions.PyJWKSetError,
    ) as exc:
        # PyJWKClientError (kid miss / JWKS fetch failure) and PyJWKSetError (an
        # empty/keyless JWKS document) are NOT InvalidTokenError subclasses — and
        # PyJWKSetError is not even a PyJWKClientError subclass — without this
        # clause either escapes as a 500 at the callback instead of SsoJwtError.
        raise SsoJwtError(f"jwt validation failed: {exc}") from exc

    iss = claims.get("iss")
    # iss must be a string to be checked for allowlist membership at all — a
    # list/dict iss is unhashable and would raise a raw TypeError from the
    # frozenset `in` check below rather than the declared SsoJwtError contract.
    if not isinstance(iss, str) or iss not in _VALID_ISSUERS:  # dual-iss allowlist (§2.2)
        raise SsoJwtError(f"unexpected iss: {iss!r}")

    sub = claims.get("sub", "")
    prefix = "CHARACTER:EVE:"
    if not sub.startswith(prefix):
        raise SsoJwtError(f"unexpected sub shape: {sub!r}")
    id_part = sub[len(prefix):]
    # ASCII digits only — int() alone accepts sign/underscore/whitespace/non-ASCII digits.
    # Also bound the length: int() rejects digit strings past Python's integer-string
    # conversion limit (sys.int_info.default_max_str_digits, ~4300) with a raw
    # ValueError, and no real EVE character id is anywhere near that long.
    if not re.fullmatch(r"[0-9]+", id_part) or len(id_part) > 20:
        raise SsoJwtError(f"non-canonical character id in sub: {sub!r}")
    character_id = int(id_part)

    name = claims.get("name")
    owner = claims.get("owner")
    if not isinstance(name, str) or not isinstance(owner, str) or not name or not owner:
        raise SsoJwtError("missing or non-string name/owner claim")
    return VerifiedIdentity(character_id=character_id, character_name=name, owner_hash=owner)
