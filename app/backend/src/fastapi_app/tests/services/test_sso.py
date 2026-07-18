# ABOUTME: EVE SSO protocol — authorize URL, code exchange, refresh grant, JWT validation.
# ABOUTME: JWTs are real-signed; kid selection runs through a real PyJWKClient over an in-test JWKS.
import base64
from urllib.parse import parse_qs, urlsplit

import pytest

from fastapi_app.services import sso


def test_build_authorize_url_has_exact_params():
    url = sso.build_authorize_url(
        state="STATE123",
        client_id="my-client",
        redirect_uri="https://localhost:5173/api/v1/auth/sso/callback",
        authorize_url="https://login.eveonline.com/v2/oauth/authorize",
    )
    split = urlsplit(url)
    assert f"{split.scheme}://{split.netloc}{split.path}" == "https://login.eveonline.com/v2/oauth/authorize"
    q = parse_qs(split.query, keep_blank_values=True)   # parse_qs DROPS blank values by default
    assert q["response_type"] == ["code"]
    assert q["client_id"] == ["my-client"]
    assert q["redirect_uri"] == ["https://localhost:5173/api/v1/auth/sso/callback"]
    assert q["state"] == ["STATE123"]
    assert q["scope"] == [""]   # KeyError if scope is missing; must be present AND empty (F004)


@pytest.mark.asyncio
async def test_exchange_code_uses_basic_auth_and_form_body(httpx_mock):
    import httpx
    httpx_mock.add_response(
        url="https://login.eveonline.com/v2/oauth/token",
        # Zero-scope (F004) wire shape: NO refresh_token key at all (D-DELTA-2).
        json={"access_token": "AT", "expires_in": 1200, "token_type": "Bearer"},
    )
    async with httpx.AsyncClient() as client:
        tokens = await sso.exchange_code(
            client, code="CODE",
            token_url="https://login.eveonline.com/v2/oauth/token",
            client_id="cid", client_secret="secret",
        )
    assert tokens["access_token"] == "AT"
    assert "refresh_token" not in tokens   # zero scopes ⇒ EVE issues none; callers treat as absent
    assert tokens["expires_in"] == 1200
    req = httpx_mock.get_requests()[0]
    assert req.headers["Authorization"] == "Basic " + base64.b64encode(b"cid:secret").decode()
    assert req.headers["Content-Type"].startswith("application/x-www-form-urlencoded")
    body = parse_qs(req.content.decode())
    assert body["grant_type"] == ["authorization_code"]
    assert body["code"] == ["CODE"]


@pytest.mark.asyncio
async def test_refresh_grant_returns_rotated_token(httpx_mock):
    import httpx
    httpx_mock.add_response(
        url="https://login.eveonline.com/v2/oauth/token",
        json={"access_token": "AT2", "refresh_token": "RT_ROTATED", "expires_in": 1200},
    )
    async with httpx.AsyncClient() as client:
        tokens = await sso.refresh_token_pair(
            client, refresh_token="RT_OLD",
            token_url="https://login.eveonline.com/v2/oauth/token",
            client_id="cid", client_secret="secret",
        )
    assert tokens["refresh_token"] == "RT_ROTATED"   # rotation-safe: caller persists this
    req = httpx_mock.get_requests()[0]
    body = parse_qs(req.content.decode())
    assert body["grant_type"] == ["refresh_token"]
    assert body["refresh_token"] == ["RT_OLD"]


@pytest.mark.asyncio
async def test_exchange_code_non_200_raises_with_status(httpx_mock):
    import httpx
    httpx_mock.add_response(url="https://login.eveonline.com/v2/oauth/token", status_code=400, json={"error": "invalid_grant"})
    async with httpx.AsyncClient() as client:
        with pytest.raises(sso.SsoTokenError) as exc:
            await sso.exchange_code(
                client, code="BAD",
                token_url="https://login.eveonline.com/v2/oauth/token",
                client_id="cid", client_secret="secret",
            )
    assert exc.value.status_code == 400   # callers discriminate invalid-grant 400s from outages (§4.3)


@pytest.mark.asyncio
async def test_exchange_code_transport_error_raises_with_no_status(httpx_mock):
    import httpx
    httpx_mock.add_exception(httpx.ConnectError("connection refused"), url="https://login.eveonline.com/v2/oauth/token")
    async with httpx.AsyncClient() as client:
        with pytest.raises(sso.SsoTokenError) as exc:
            await sso.exchange_code(
                client, code="C",
                token_url="https://login.eveonline.com/v2/oauth/token",
                client_id="cid", client_secret="secret",
            )
    assert exc.value.status_code is None   # transport failure: no HTTP status to blame


@pytest.mark.asyncio
async def test_exchange_code_200_with_non_json_body_raises(httpx_mock):
    import httpx
    httpx_mock.add_response(
        url="https://login.eveonline.com/v2/oauth/token",
        text="<!doctype html><html>gateway error page</html>",
    )
    async with httpx.AsyncClient() as client:
        with pytest.raises(sso.SsoTokenError) as exc:
            await sso.exchange_code(
                client, code="C",
                token_url="https://login.eveonline.com/v2/oauth/token",
                client_id="cid", client_secret="secret",
            )
    assert exc.value.status_code == 200   # the body was malformed, not the HTTP layer


@pytest.mark.asyncio
async def test_exchange_code_200_with_non_object_json_raises(httpx_mock):
    import httpx
    httpx_mock.add_response(url="https://login.eveonline.com/v2/oauth/token", json="just-a-string")
    async with httpx.AsyncClient() as client:
        with pytest.raises(sso.SsoTokenError) as exc:
            await sso.exchange_code(
                client, code="C",
                token_url="https://login.eveonline.com/v2/oauth/token",
                client_id="cid", client_secret="secret",
            )
    assert exc.value.status_code == 200


# --- finding 2: a 200 body that lacks/malforms access_token or expires_in must raise
# SsoTokenError (its declared contract) here, not KeyError/ValueError downstream in
# upsert_user/refresh_token_pair, which would 500 the callback instead of sso=error. ---

@pytest.mark.asyncio
async def test_exchange_code_200_missing_access_token_raises_sso_token_error(httpx_mock):
    import httpx
    httpx_mock.add_response(url="https://login.eveonline.com/v2/oauth/token", json={"expires_in": 1200})
    async with httpx.AsyncClient() as client:
        with pytest.raises(sso.SsoTokenError) as exc:
            await sso.exchange_code(
                client, code="C",
                token_url="https://login.eveonline.com/v2/oauth/token",
                client_id="cid", client_secret="secret",
            )
    assert exc.value.status_code == 200


@pytest.mark.asyncio
async def test_exchange_code_200_non_string_access_token_raises_sso_token_error(httpx_mock):
    import httpx
    httpx_mock.add_response(
        url="https://login.eveonline.com/v2/oauth/token",
        json={"access_token": 12345, "expires_in": 1200},
    )
    async with httpx.AsyncClient() as client:
        with pytest.raises(sso.SsoTokenError):
            await sso.exchange_code(
                client, code="C",
                token_url="https://login.eveonline.com/v2/oauth/token",
                client_id="cid", client_secret="secret",
            )


@pytest.mark.asyncio
async def test_exchange_code_200_missing_expires_in_raises_sso_token_error(httpx_mock):
    import httpx
    httpx_mock.add_response(url="https://login.eveonline.com/v2/oauth/token", json={"access_token": "AT"})
    async with httpx.AsyncClient() as client:
        with pytest.raises(sso.SsoTokenError):
            await sso.exchange_code(
                client, code="C",
                token_url="https://login.eveonline.com/v2/oauth/token",
                client_id="cid", client_secret="secret",
            )


@pytest.mark.asyncio
async def test_exchange_code_200_non_numeric_expires_in_raises_sso_token_error(httpx_mock):
    import httpx
    httpx_mock.add_response(
        url="https://login.eveonline.com/v2/oauth/token",
        json={"access_token": "AT", "expires_in": "not-a-number"},
    )
    async with httpx.AsyncClient() as client:
        with pytest.raises(sso.SsoTokenError):
            await sso.exchange_code(
                client, code="C",
                token_url="https://login.eveonline.com/v2/oauth/token",
                client_id="cid", client_secret="secret",
            )


@pytest.mark.asyncio
async def test_exchange_code_200_null_expires_in_raises_sso_token_error(httpx_mock):
    import httpx
    httpx_mock.add_response(
        url="https://login.eveonline.com/v2/oauth/token",
        json={"access_token": "AT", "expires_in": None},
    )
    async with httpx.AsyncClient() as client:
        with pytest.raises(sso.SsoTokenError):
            await sso.exchange_code(
                client, code="C",
                token_url="https://login.eveonline.com/v2/oauth/token",
                client_id="cid", client_secret="secret",
            )


@pytest.mark.asyncio
async def test_exchange_code_200_non_finite_expires_in_raises_sso_token_error(httpx_mock):
    # Finding 4: a body whose expires_in is out-of-range (1e309) parses to float
    # inf via resp.json(); int(inf) raises OverflowError, which is neither
    # ValueError nor TypeError, so it would escape _validate_token_body and 500
    # the callback instead of taking the sso=error path. Sent as raw text (the
    # wire form a real endpoint could emit) because strict JSON serialization
    # refuses to encode inf.
    import httpx
    httpx_mock.add_response(
        url="https://login.eveonline.com/v2/oauth/token",
        text='{"access_token": "AT", "expires_in": 1e309}',
        headers={"content-type": "application/json"},
    )
    async with httpx.AsyncClient() as client:
        with pytest.raises(sso.SsoTokenError):
            await sso.exchange_code(
                client, code="C",
                token_url="https://login.eveonline.com/v2/oauth/token",
                client_id="cid", client_secret="secret",
            )


import time

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa

from fastapi_app.services.sso import VerifiedIdentity, validate_access_token

CLIENT_ID = "my-client"


class _StaticKeyProvider:
    """Injectable JWKS seam stand-in: returns one signing key regardless of kid lookup."""

    def __init__(self, public_key):
        self._key = public_key

    def get_signing_key_from_jwt(self, token):
        from types import SimpleNamespace
        return SimpleNamespace(key=self._key)


@pytest.fixture(scope="module")
def rsa_keypair():
    priv = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return priv, priv.public_key()


def _sign(priv, claims, *, alg="RS256", kid="JWT-Signature-Key"):
    return jwt.encode(claims, priv, algorithm=alg, headers={"kid": kid})


def _claims(**overrides):
    now = int(time.time())
    base = {
        "iss": "login.eveonline.com",
        "sub": "CHARACTER:EVE:91000001",
        "aud": [CLIENT_ID, "EVE Online"],
        "name": "Sesta Hound",
        "owner": "ownerHASH==",
        "exp": now + 1200,
        "iat": now,
    }
    base.update(overrides)
    return base


def test_valid_token_returns_identity(rsa_keypair):
    priv, pub = rsa_keypair
    ident = validate_access_token(_sign(priv, _claims()), key_provider=_StaticKeyProvider(pub), client_id=CLIENT_ID)
    assert isinstance(ident, VerifiedIdentity)
    assert ident.character_id == 91000001
    assert ident.character_name == "Sesta Hound"
    assert ident.owner_hash == "ownerHASH=="


def test_both_iss_forms_accepted(rsa_keypair):
    priv, pub = rsa_keypair
    for iss in ("login.eveonline.com", "https://login.eveonline.com"):
        ident = validate_access_token(_sign(priv, _claims(iss=iss)), key_provider=_StaticKeyProvider(pub), client_id=CLIENT_ID)
        assert ident.character_id == 91000001


def test_wrong_iss_rejected(rsa_keypair):
    priv, pub = rsa_keypair
    with pytest.raises(sso.SsoJwtError):
        validate_access_token(_sign(priv, _claims(iss="evil.example.com")), key_provider=_StaticKeyProvider(pub), client_id=CLIENT_ID)


def test_aud_without_client_id_rejected(rsa_keypair):
    priv, pub = rsa_keypair
    with pytest.raises(sso.SsoJwtError):
        validate_access_token(_sign(priv, _claims(aud=["someone-else", "EVE Online"])), key_provider=_StaticKeyProvider(pub), client_id=CLIENT_ID)


def test_aud_array_with_client_id_accepted(rsa_keypair):
    priv, pub = rsa_keypair
    ident = validate_access_token(_sign(priv, _claims(aud=[CLIENT_ID, "EVE Online"])), key_provider=_StaticKeyProvider(pub), client_id=CLIENT_ID)
    assert ident.character_id == 91000001


def test_hs256_token_rejected(rsa_keypair):
    _, pub = rsa_keypair
    # Full-length key so PyJWT emits no key-length warning — the rejection is
    # driven by the RS256/ES256 allowlist, not the key.
    hs = jwt.encode(_claims(), "shared-secret-padded-to-32-bytes!", algorithm="HS256", headers={"kid": "JWT-Signature-Key"})
    with pytest.raises(sso.SsoJwtError):
        validate_access_token(hs, key_provider=_StaticKeyProvider(pub), client_id=CLIENT_ID)


def test_exp_within_leeway_accepted(rsa_keypair):
    priv, pub = rsa_keypair
    now = int(time.time())
    ident = validate_access_token(_sign(priv, _claims(exp=now - 5)), key_provider=_StaticKeyProvider(pub), client_id=CLIENT_ID)
    assert ident.character_id == 91000001   # 5s past, within the 30-60s leeway


def test_exp_beyond_leeway_rejected(rsa_keypair):
    priv, pub = rsa_keypair
    now = int(time.time())
    with pytest.raises(sso.SsoJwtError):
        validate_access_token(_sign(priv, _claims(exp=now - 3600)), key_provider=_StaticKeyProvider(pub), client_id=CLIENT_ID)


def test_nbf_in_future_beyond_leeway_rejected(rsa_keypair):
    # §3.2/§7: nbf is validated when present — a not-yet-valid token must be rejected.
    priv, pub = rsa_keypair
    now = int(time.time())
    with pytest.raises(sso.SsoJwtError):
        validate_access_token(_sign(priv, _claims(nbf=now + 3600)), key_provider=_StaticKeyProvider(pub), client_id=CLIENT_ID)


@pytest.mark.parametrize("bad_exp", [{}, 1e309])
def test_malformed_numericdate_exp_rejected_not_typeerror_or_overflow(rsa_keypair, bad_exp):
    # Finding 5: a NumericDate claim of the wrong shape makes PyJWT raise a raw
    # TypeError (exp: {}) or OverflowError (exp: 1e309 -> inf), neither of which
    # is an InvalidTokenError subclass — so without broadening the decode except
    # they escape validate_access_token and 500 the callback. Must map to
    # SsoJwtError. (jwt.encode passes these through unvalidated; jwt.decode is
    # where the raw error surfaces.)
    priv, pub = rsa_keypair
    with pytest.raises(sso.SsoJwtError):
        validate_access_token(_sign(priv, _claims(exp=bad_exp)), key_provider=_StaticKeyProvider(pub), client_id=CLIENT_ID)


def test_malformed_numericdate_iat_rejected_not_typeerror(rsa_keypair):
    # Same class of defect on another NumericDate claim (iat), for coverage breadth.
    priv, pub = rsa_keypair
    with pytest.raises(sso.SsoJwtError):
        validate_access_token(_sign(priv, _claims(iat={})), key_provider=_StaticKeyProvider(pub), client_id=CLIENT_ID)


def _jwks_for(pub, kid="JWT-Signature-Key"):
    import json as json_mod
    from jwt.algorithms import RSAAlgorithm
    jwk = json_mod.loads(RSAAlgorithm.to_jwk(pub))
    jwk.update({"kid": kid, "use": "sig", "alg": "RS256"})
    return {"keys": [jwk]}


def test_real_pyjwkclient_selects_key_by_kid(rsa_keypair, monkeypatch):
    # Spec §3.2/§6: kid selection must run for real at least once — a real PyJWKClient
    # over an in-test JWKS dict (fetch_data monkeypatched, so urllib is never called).
    priv, pub = rsa_keypair
    client = jwt.PyJWKClient("https://login.eveonline.com/oauth/jwks")
    monkeypatch.setattr(client, "fetch_data", lambda: _jwks_for(pub))
    ident = validate_access_token(_sign(priv, _claims()), key_provider=client, client_id=CLIENT_ID)
    assert ident.character_id == 91000001


def test_unknown_kid_maps_to_sso_jwt_error(rsa_keypair, monkeypatch):
    # PyJWKClientError is NOT a subclass of InvalidTokenError — validate_access_token
    # must catch it explicitly, or a kid miss escapes as a 500 at the callback.
    priv, pub = rsa_keypair
    client = jwt.PyJWKClient("https://login.eveonline.com/oauth/jwks")
    monkeypatch.setattr(client, "fetch_data", lambda: _jwks_for(pub))
    with pytest.raises(sso.SsoJwtError):
        validate_access_token(_sign(priv, _claims(), kid="no-such-kid"), key_provider=client, client_id=CLIENT_ID)


@pytest.mark.parametrize("id_part", ["-91000001", "9_1", " 91000001 ", "+91000001", "٩١"])
def test_non_canonical_character_id_rejected(rsa_keypair, id_part):
    # int() alone accepts sign/underscore/whitespace/non-ASCII-digit forms; only
    # ASCII-digit character ids are canonical.
    priv, pub = rsa_keypair
    with pytest.raises(sso.SsoJwtError):
        validate_access_token(
            _sign(priv, _claims(sub=f"CHARACTER:EVE:{id_part}")),
            key_provider=_StaticKeyProvider(pub), client_id=CLIENT_ID,
        )


def test_non_string_name_claim_rejected(rsa_keypair):
    priv, pub = rsa_keypair
    with pytest.raises(sso.SsoJwtError):
        validate_access_token(_sign(priv, _claims(name=5)), key_provider=_StaticKeyProvider(pub), client_id=CLIENT_ID)


def _sign_raw_claims(priv, claims, *, alg="RS256", kid="JWT-Signature-Key"):
    """Like _sign, but bypasses PyJWT encode()'s own claim validation (e.g. its
    str-only check on iss, added for PyJWT issue #1039) by signing pre-serialized
    JSON bytes directly through the lower-level PyJWS. Used to reproduce claim
    shapes that a real signer external to this codebase's PyJWT version could
    still emit, or that a corrupted/forged token could carry."""
    import json as json_mod
    from jwt.api_jws import PyJWS
    payload_bytes = json_mod.dumps(claims).encode()
    return PyJWS().encode(payload_bytes, priv, algorithm=alg, headers={"kid": kid})


def test_non_string_iss_rejected_not_typeerror(rsa_keypair):
    # A signed token carrying iss as a list/dict must map to SsoJwtError, not an
    # unhandled TypeError from the frozenset membership check (`iss not in
    # _VALID_ISSUERS`) when iss is unhashable.
    priv, pub = rsa_keypair
    token = _sign_raw_claims(priv, _claims(iss=[]))
    with pytest.raises(sso.SsoJwtError):
        validate_access_token(token, key_provider=_StaticKeyProvider(pub), client_id=CLIENT_ID)


def test_non_string_iss_dict_rejected_not_typeerror(rsa_keypair):
    priv, pub = rsa_keypair
    token = _sign_raw_claims(priv, _claims(iss={}))
    with pytest.raises(sso.SsoJwtError):
        validate_access_token(token, key_provider=_StaticKeyProvider(pub), client_id=CLIENT_ID)


def test_oversized_digit_sub_rejected_not_valueerror(rsa_keypair):
    # int() rejects integer strings over Python's digit-conversion limit
    # (sys.int_info.default_max_str_digits, ~4300) with a raw ValueError; a
    # character id substring that is all ASCII digits but absurdly long must
    # still map to SsoJwtError, not escape as a 500.
    priv, pub = rsa_keypair
    huge_digits = "9" * 4301
    with pytest.raises(sso.SsoJwtError):
        validate_access_token(
            _sign(priv, _claims(sub=f"CHARACTER:EVE:{huge_digits}")),
            key_provider=_StaticKeyProvider(pub), client_id=CLIENT_ID,
        )


def test_empty_jwks_key_set_rejected_not_pyjwksseterror(rsa_keypair, monkeypatch):
    # PyJWKSetError (raised by PyJWKClient when the JWKS has zero keys) is NOT a
    # subclass of PyJWKClientError — the current except clause misses it, so an
    # empty/keyless JWKS document would escape validate_access_token uncaught.
    priv, pub = rsa_keypair
    client = jwt.PyJWKClient("https://login.eveonline.com/oauth/jwks")
    monkeypatch.setattr(client, "fetch_data", lambda: {"keys": []})
    with pytest.raises(sso.SsoJwtError):
        validate_access_token(_sign(priv, _claims()), key_provider=client, client_id=CLIENT_ID)
