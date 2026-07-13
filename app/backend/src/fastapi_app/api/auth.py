# ABOUTME: EVE SSO routes — login, callback, logout, /me — mounted bare (PROXY-1).
# ABOUTME: state is single-use (GETDEL) AND browser-bound (hb_sso_state cookie) so the callback matches the login this browser started (§7).
import asyncio
import functools
import json
import secrets
import time
from typing import Optional
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse, RedirectResponse
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config import get_settings
from ..core.dependencies import get_cache, get_http_client
from ..core.logging import get_logger, log_key_event
from ..core.session import create_session, destroy_session, get_current_session
from ..core.token_cipher import is_token_cipher_configured
from ..db import get_db
from ..schemas.auth import CurrentUserSchema
from ..services import auth_service, sso

logger = get_logger(__name__)

router = APIRouter(prefix="/auth/sso", tags=["Auth"])   # bare; SPA reaches via /api/v1/auth/sso/*
me_router = APIRouter(tags=["Auth"])                    # bare /me

_STATE_TTL_SECONDS = 600
_STATE_COOKIE = "hb_sso_state"


# --- shared not-configured guard (login + callback only) ---
async def require_sso_configured() -> None:
    s = get_settings()
    if not s.ESI_CLIENT_ID or not is_token_cipher_configured():
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="EVE SSO is not configured")


# --- pure helpers (unit-tested in test_auth_helpers.py) ---
def validate_next(value: Optional[str]) -> str:
    if not value or not value.startswith("/"):
        return "/"
    if value.startswith("//"):
        return "/"                          # protocol-relative
    if len(value) > 1 and value[1] == "\\":
        return "/"                          # /\evil.com
    return value


def build_redirect(frontend_origin: str, next_path: str, flag: Optional[str]) -> str:
    split = urlsplit(next_path)
    query = parse_qsl(split.query, keep_blank_values=True)
    if flag is not None:
        query.append(("sso", flag))
    rebuilt = urlunsplit(("", "", split.path or "/", urlencode(query), split.fragment))
    return frontend_origin + rebuilt


def _cookie_secure() -> bool:
    return get_settings().ENVIRONMENT != "development"


def _clear_state_cookie(resp: Response) -> None:
    resp.delete_cookie(_STATE_COOKIE, path="/")


# --- routes ---
@router.get("/login", dependencies=[Depends(require_sso_configured)])
async def login(request: Request, next: str = "/", redis: Redis = Depends(get_cache)):
    s = get_settings()
    validated_next = validate_next(next)
    state = secrets.token_urlsafe(24)   # 192-bit
    await redis.set(f"sso_state:{state}", json.dumps({"next": validated_next}), ex=_STATE_TTL_SECONDS)
    authorize_url = sso.build_authorize_url(
        state=state, client_id=s.ESI_CLIENT_ID,
        redirect_uri=s.ESI_SSO_CALLBACK_URL, authorize_url=s.ESI_SSO_AUTHORIZE_URL,
    )
    resp = RedirectResponse(authorize_url, status_code=status.HTTP_302_FOUND)
    resp.set_cookie(
        _STATE_COOKIE, state, max_age=_STATE_TTL_SECONDS, httponly=True,
        samesite="lax", secure=_cookie_secure(), path="/",
    )
    return resp


@functools.lru_cache(maxsize=1)
def _signing_key_provider() -> jwt.PyJWKClient:
    """Process-wide PyJWKClient: its JWKS cache (300 s TTL, kid-keyed) must persist
    across logins — a per-request client would refetch the JWKS on every callback
    (§3.2). Tests monkeypatch this module attribute, which shadows the cached
    callable; a test that changes ESI_SSO_JWKS_URI must call
    _signing_key_provider.cache_clear()."""
    return jwt.PyJWKClient(get_settings().ESI_SSO_JWKS_URI)


@router.get("/callback", dependencies=[Depends(require_sso_configured)])
async def callback(
    request: Request,
    state: Optional[str] = None,
    code: Optional[str] = None,
    error: Optional[str] = None,
    redis: Redis = Depends(get_cache),
    http_client=Depends(get_http_client),
    db: AsyncSession = Depends(get_db),
):
    s = get_settings()
    started = time.perf_counter()
    cookie_state = request.cookies.get(_STATE_COOKIE)
    stored = None
    if state:
        raw = await redis.getdel(f"sso_state:{state}")   # single-use consume
        if raw is not None:
            stored = json.loads(raw)

    # (A) EVE-side denial — no session, redirect with sso=denied.
    # Sanctioned ordering (plan-review round 2): the denial exit precedes the binding
    # check (C). No session is ever minted on denial, so innocent-user UX (a friendly
    # redirect) wins over the hard 400; a pinning test covers denial+cookie-mismatch.
    if error is not None:
        nxt = validate_next(stored["next"]) if stored else "/"
        resp = RedirectResponse(build_redirect(s.FRONTEND_ORIGIN, nxt, "denied"), status_code=status.HTTP_302_FOUND)
        _clear_state_cookie(resp)
        return resp

    # (B) State missing/expired (GETDEL miss) — innocent, redirect with sso=error.
    if stored is None:
        resp = RedirectResponse(build_redirect(s.FRONTEND_ORIGIN, "/", "error"), status_code=status.HTTP_302_FOUND)
        _clear_state_cookie(resp)
        return resp

    # (C) State live but browser binding fails — the only hard-400 exit (callback doesn't match this browser's login).
    if cookie_state is None or cookie_state != state:
        resp = JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={"detail": "Invalid SSO state"})
        _clear_state_cookie(resp)
        return resp

    validated_next = validate_next(stored["next"])

    # (D) Exchange code — non-200 → sso=error redirect.
    try:
        tokens = await sso.exchange_code(
            http_client, code=code or "", token_url=s.ESI_SSO_TOKEN_URL,
            client_id=s.ESI_CLIENT_ID, client_secret=s.ESI_CLIENT_SECRET.get_secret_value(),
        )
    except sso.SsoTokenError:
        # Structured failure log (§4.1 step 5) — status/outcome only, no token material (§7).
        log_key_event(logger, "sso_callback", success=False,
                      duration_ms=(time.perf_counter() - started) * 1000,
                      outcome="token_exchange_failed")
        resp = RedirectResponse(build_redirect(s.FRONTEND_ORIGIN, validated_next, "error"), status_code=status.HTTP_302_FOUND)
        _clear_state_cookie(resp)
        return resp

    # (E) Validate JWT — the JWKS fetch inside is synchronous urllib, so run the whole
    # validation off the event loop (§3.2). Failure → sso=error redirect.
    try:
        provider = _signing_key_provider()
        identity = await asyncio.to_thread(
            sso.validate_access_token, tokens["access_token"], key_provider=provider, client_id=s.ESI_CLIENT_ID
        )
    except (sso.SsoJwtError, KeyError, jwt.exceptions.PyJWKClientError):
        # Structured failure log (§4.1 step 6) — outcome only, never the JWT itself (§7).
        log_key_event(logger, "sso_callback", success=False,
                      duration_ms=(time.perf_counter() - started) * 1000,
                      outcome="jwt_validation_failed")
        resp = RedirectResponse(build_redirect(s.FRONTEND_ORIGIN, validated_next, "error"), status_code=status.HTTP_302_FOUND)
        _clear_state_cookie(resp)
        return resp

    # (F) Upsert + session.
    user = await auth_service.upsert_user(db, identity, tokens)
    sid = await create_session(redis, user_id=user.id, character_id=identity.character_id, character_name=identity.character_name)
    log_key_event(logger, "sso_callback", success=True,
                  duration_ms=(time.perf_counter() - started) * 1000,
                  outcome="login", character_id=identity.character_id)

    resp = RedirectResponse(build_redirect(s.FRONTEND_ORIGIN, validated_next, None), status_code=status.HTTP_302_FOUND)
    resp.set_cookie(
        s.SESSION_COOKIE_NAME, sid, max_age=s.SESSION_ABSOLUTE_TTL_SECONDS, httponly=True,
        samesite="lax", secure=_cookie_secure(), path="/",
    )
    _clear_state_cookie(resp)
    return resp


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(request: Request, redis: Redis = Depends(get_cache)):
    s = get_settings()
    sid = request.cookies.get(s.SESSION_COOKIE_NAME)
    if sid:
        await destroy_session(redis, sid)   # no-op if already gone (idempotent)
    resp = Response(status_code=status.HTTP_204_NO_CONTENT)
    resp.delete_cookie(s.SESSION_COOKIE_NAME, path="/")
    return resp


@me_router.get("/me", response_model=CurrentUserSchema)
async def me(session: dict = Depends(get_current_session)):
    # get_current_session 401s when there is no valid session; /me serves from the
    # session payload alone (no DB read — §4.2).
    return CurrentUserSchema(character_id=session["character_id"], character_name=session["character_name"])
