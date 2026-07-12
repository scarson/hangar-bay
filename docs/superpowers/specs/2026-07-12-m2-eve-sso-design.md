# M2 — EVE SSO Authentication (F004) — Design Spec

**Date:** 2026-07-12 (overnight session)
**Status:** Approved for planning under Sam's delegated overnight authority (2026-07-12); flagged items awaiting Sam's morning review are marked `[MORNING-REVIEW]`.
**Feature authority:** [design/features/F004-User-Authentication-SSO.md](../../../design/features/F004-User-Authentication-SSO.md) — this spec refines F004 with verified 2026 EVE SSO facts and binds its open choices.
**Verified-facts provenance:** live recon 2026-07-12 — EVE SSO metadata/JWKS fetched from login.eveonline.com; library versions from PyPI/GitHub; codebase facts from the worktree at commit `15a7195`+.

## 1. Decisions register

Settled by Sam (do not reopen):

- **Client state:** HTTPOnly cookie session + `GET /api/v1/me` + a `useCurrentUser` TanStack Query hook. No tokens in the browser, no client auth store.
- **F004 [DECIDED] baseline stands:** no ESI scopes in F004; confidential client + `state` binding; Valkey-backed server-side sessions; tokens encrypted at rest; owner-hash transfer handling; token refresh on demand only.
- **Dev callback URL:** `http://localhost:8000/auth/sso/callback` (Sam registers the EVE developer app tomorrow; implementation and tests do not block on it).
- **M2 UI scope:** header identity — login button when anonymous; character portrait + name + logout when authenticated. Structure-name resolution deferred to M3 (scope-bearing).
- **Session semantics:** sliding 7-day idle timeout + 30-day absolute cap.

Decided tonight under delegated authority (rationale in §3 and Appendix A):

- OAuth client: **hand-rolled `httpx` flow** (no Authlib, no fastapi-sso).
- JWT validation: **PyJWT 2.13 + PyJWKClient**, algorithms RS256+ES256.
- Sessions: **hand-rolled FastAPI dependency** over the existing Valkey client (no starsessions).
- Token encryption: **Fernet via MultiFernet** with env-provided key list (rotation-ready).
- Settings home: **consolidate the two Settings classes into `fastapi_app/core/config.py`** as part of M2 `[MORNING-REVIEW]` (pre-blessed as a candidate improvement in the 2026-07-12 handoff).
- Prod safety rider: startup `drop_all/create_all` becomes development-only `[MORNING-REVIEW]`.
- CI: a GitHub Actions workflow (backend pytest + frontend lint/types/unit/E2E-fixture) ships as part of M2, in its own PR, so the merge-authority policy's "green CI" gate is real.

## 2. Corrections to F004 (verified against live EVE SSO, 2026-07-12)

These override F004's text where they conflict:

1. **There is no ID token.** EVE SSO is OAuth 2.0, not OIDC. The **access token itself is the JWT** validated against the JWKS. Everywhere F004 says "ID token JWT", read "JWT access token".
2. **`iss` comes in two historical forms**: `login.eveonline.com` and `https://login.eveonline.com`. Accept exactly those two values, reject everything else (official docs recommend checking both).
3. **`aud` is an array** containing the app's `client_id` AND the literal `"EVE Online"`. Validate that `client_id` is present.
4. **`sub`** is `CHARACTER:EVE:<character_id>`; character name is the `name` claim; owner hash is the `owner` claim.
5. **JWKS** advertises two signing keys: RS256 (`kid: JWT-Signature-Key`) and ES256. Select by `kid`; allow both algorithms; never accept HS256 (the metadata's `id_token_signing_alg_values_supported: ["HS256"]` is a red herring — no id_token exists).
6. **`GET /oauth/verify` is deprecated** (since 2021-11-01, removable any time). Do not use it, even as secondary verification. Local JWT validation is the only identity source.
7. **Access tokens live 20 minutes** (`expires_in: 1200`). **Refresh responses may rotate the refresh token** — always persist the `refresh_token` returned by every token-endpoint response.
8. **Token exchange auth:** HTTP Basic (`client_id:client_secret`), `application/x-www-form-urlencoded` body — the form shown in official docs.
9. **Endpoints** (from the live metadata document): authorize `https://login.eveonline.com/v2/oauth/authorize`, token `https://login.eveonline.com/v2/oauth/token`, JWKS `https://login.eveonline.com/oauth/jwks`, revocation `https://login.eveonline.com/v2/oauth/revoke` (F004 §3.3 stands: we do not revoke on logout).
10. **Portraits:** `https://images.evetech.net/characters/<id>/portrait?size=<2^n, 32–1024>` — unauthenticated CDN, JPEG; CCP says use directly, no local caching required.

## 3. Approaches considered (per axis)

### 3.1 OAuth client

- **(a) Hand-rolled httpx + JWT library — CHOSEN.** The confidential-client code flow against one fixed provider is two POSTs and one redirect URL. EVE's quirks (dual `iss`, array `aud`, JWT-access-token-not-OIDC) defeat every library's autopilot anyway, so a library would run with overrides while adding a dependency surface. The existing shared `httpx.AsyncClient` (`core/http_client.py`, app-state, correct User-Agent) accepts absolute URLs, so token calls reuse it. The token-endpoint POSTs are testable with the already-installed `pytest-httpx`; JWKS fetching goes through a separate injectable seam (below) because PyJWKClient's fetch is synchronous urllib and pytest-httpx cannot intercept it (§3.2, §6).
- (b) Authlib 1.7.2 `AsyncOAuth2Client` — active, but its Starlette integration requires `SessionMiddleware` (we build our own sessions), its auto-refresh duplicates logic we must own (refresh-token rotation persistence), and its JOSE layer is mid-deprecation toward joserfc. Two 2025 CVEs (fixed) in exactly the layers we'd lean on. Rejected: costs exceed the ~100 lines it saves.
- (c) fastapi-sso 0.21.1 — maintained, but userinfo-flow-shaped (`OpenID` result objects) and explicitly "does not try to solve login and authentication" persistence; no JWKS validation surface. Wrong shape. Rejected.

### 3.2 JWT validation

- **(a) PyJWT 2.13 + PyJWKClient — CHOSEN.** 2.13.0 tightened JWT validation (alg-confusion fixes, JWKS URI scheme restrictions); `PyJWKClient` gives kid-matching + JWKS caching (300 s TTL, auto-refetch-on-kid-miss). Its fetch is synchronous urllib — mitigated by calling through `asyncio.to_thread` (rare: cache-miss only). `jwt.decode` handles array `aud` natively (matches any entry). Dual-`iss` handled by disabling built-in iss verification and checking against the two-value allowlist explicitly. `jwt.decode` is called with a small `leeway` (30–60 s) on time-based claims so a few seconds of clock skew against EVE's `exp`/`nbf` does not spuriously reject a freshly-issued token (access tokens live only 1200 s); `iat`/`nbf` are validated when present. **JWKS test seam:** because the urllib fetch is un-mockable by pytest-httpx, `services/sso.py` obtains its signing key through an injectable seam — a `PyJWKClient` (or signing-key provider) supplied via constructor/dependency — which tests replace with one backed by an in-test JWKS dict (or by monkeypatching `PyJWKClient.fetch_data`). The validator still runs for real (signature, kid selection, alg allowlist) against a test-signed key; pytest-httpx is reserved for the token-endpoint POSTs only.
- (b) joserfc 1.7.3 — active, async-friendly (BYO JWKS fetch), but we'd hand-roll the JWKS cache/refresh PyJWT ships. Rejected on lines-of-code-we-own.
- (c) python-jose — dormant (zero 2026 commits), CVE history with year-long unfixed windows. Rejected outright.

### 3.3 Session mechanism

- **(a) Hand-rolled FastAPI dependency + opaque cookie + Valkey — CHOSEN.** ~80 lines against the existing `get_cache` house pattern. The deciding requirement is the **absolute cap**: no candidate middleware implements idle+absolute dual timeouts, so custom logic exists either way. A dependency (vs middleware) is also the shape `tests/conftest.py` already knows how to override.
- (b) starsessions 2.2.1 — closest fit (`rolling=True` = sliding, RedisStore, `regenerate_session_id`), but: 21 months without a release, no Python 3.14 classifier, lazy-load footgun (`SessionNotLoaded`), global-middleware model for what is ~4 authed routes, and still no absolute cap. Rejected.
- (c) starlette-session / fastapi-sessions — unmaintained (2022 / 2021). Rejected outright.

### 3.4 Token encryption at rest

- **(a) Fernet + MultiFernet keyring from env — CHOSEN.** Authenticated encryption recipe from `cryptography` (49.0.0), purpose-built key rotation (`MultiFernet.rotate`), urlsafe-base64 strings that fit TEXT columns and `decode_responses=True` conventions. Config is a comma-separated key list; first key encrypts, all keys decrypt. **`TOKEN_CIPHER_KEYS` parsing:** split on comma, strip whitespace/newlines per element, reject empty elements; an empty or whitespace-only setting ⇒ not-configured (so a stray trailing newline from `.env` cannot reach `Fernet("")`). The cipher is built **lazily** (on first use, not at import/startup), so empty keys never crash boot — they surface as the shared not-configured 503 (§4.4).
- (b) AES-GCM (hazmat) — buys AAD binding (ciphertext↔character_id) and smaller tokens at the cost of nonce discipline (catastrophic on reuse) and DIY rotation/versioning. The AAD win is real but marginal for a single-table vault; misuse-resistance wins. Rejected for M2; revisit if the token vault grows.

### 3.5 Settings home `[MORNING-REVIEW — pre-blessed candidate]`

- **(a) Consolidate into `core/config.py`, delete legacy `fastapi_app/config.py` — CHOSEN.** The split is a live trap (ENV-1): the legacy class holds the `ESI_CLIENT_ID/SECRET` stubs but `main.py` and the DI layer read the core class — SSO config added to either side alone would be half-invisible. Blast radius is mapped and mechanical: 5 legacy importers (`db.py`, `core/cache.py`, `core/http_client.py`, `tests/conftest.py`, `alembic/env.py`) move to the core import; type-hint-only importers are renames. (Note `alembic/env.py` also carries the separate `common_models`/`User` imports deleted in §4.5 — same file, same PR, so both edits land together.) **`get_settings()` target:** four of those importers (`db.py`, `core/cache.py`, `core/http_client.py`, `alembic/env.py`) call `get_settings()`, which today exists **only** in the legacy module — `core/config.py` exposes only the module-level `settings` instance, and `core/dependencies.py` has its own `get_settings` DI wrapper. So consolidation MUST have `core/config.py` **gain a `get_settings()`** (or switch those call sites to the module-level `settings`); it must NOT repoint them at `core/dependencies.get_settings`, which would create an import cycle (`dependencies` imports `esi_client_class`). `core/dependencies.get_settings` stays as the DI wrapper.
- (b) Add SSO fields to core/config.py only, leave the split — smaller diff, but perpetuates two import-time singletons parsing the same `.env` with conflicting defaults, and M2's new fields would deepen the divergence. Rejected.
- Consolidation semantics (current *effective* behavior wins, since `main.py` runs the core class): `ENVIRONMENT` becomes `Literal["development","production","test"]` (legacy's stricter type); `AGGREGATION_SCHEDULER_INTERVAL_SECONDS` stays 3600; `AGGREGATION_REGION_IDS` keeps default `[10000002]`; `DATABASE_URL`/`CACHE_URL`/`ESI_USER_AGENT` stay required; `ESI_TIMEOUT` and `AGGREGATION_DEV_CONTRACT_LIMIT` (with its do-not-remove comment) survive; legacy-only `POSTGRES_*`, `SQLITE_DB_NAME`, `BASE_DIR` and the SQLite-fallback validator are dropped (dead in practice — compose provides Postgres, `.env` provides `DATABASE_URL`); `DATABASE_URL_TESTS`/`CACHE_URL_TESTS` survive (conftest depends on the former). The env-file path adopts an **absolute** form resolving to `app/backend/src/.env`, fixing the cwd-relative silent-miss — but the depth must be recomputed for the new home: legacy `config.py` sits at `src/fastapi_app/config.py` where `parent.parent` = `src/`, whereas `core/config.py` is one level deeper, so the correct expression from `core/config.py` is `Path(__file__).resolve().parents[2] / ".env"` (a verbatim copy of the legacy `parent.parent` form would wrongly resolve to `src/fastapi_app/.env`). All import-time debug `print()`s in both config modules die here.

## 4. Architecture

New backend surface, following the house layout:

- `fastapi_app/api/auth.py` — `APIRouter(prefix="/auth/sso")`: login, callback, logout; plus the bare `GET /me` route (`APIRouter(tags=["Auth"])`, path `/me`).
- `fastapi_app/services/sso.py` — EVE SSO protocol: authorize-URL builder, code exchange, refresh grant, JWT validation (returns a `VerifiedIdentity` dataclass: character_id, character_name, owner_hash). Its JWKS/signing key comes through an **injectable seam** (a `PyJWKClient` or signing-key provider supplied via constructor/dependency), so tests substitute an in-test-JWKS-backed client while the validator still runs for real (§3.2, §6).
- `fastapi_app/services/auth_service.py` — user upsert (owner-hash transfer rule), token encrypt/store, login/logout orchestration.
- `fastapi_app/core/session.py` — session create/read/renew/destroy against Valkey; FastAPI dependencies `get_current_session` (401 on absence) and `get_optional_session`.
- `fastapi_app/core/token_cipher.py` — MultiFernet wrapper built from settings.
- `fastapi_app/schemas/auth.py` — `CurrentUserSchema {character_id: int, character_name: str}`.
- `fastapi_app/models/user.py` — replacement `User` model; `models/common_models.py` (legacy User + UserType) is deleted `[MORNING-REVIEW — legacy model is never read at RUNTIME]`. Correction to the earlier "never read by any code path" claim: `src/alembic/env.py` imports it at **import time**, twice (`from fastapi_app.models import common_models, contracts` and `from fastapi_app.models.common_models import User`). Those two imports MUST be updated in the **same commit** that deletes the module — drop the `common_models`/`User` imports (optionally register `models/user.py` in their place) — or every alembic command dies with `ImportError`. See §4.5.
- `fastapi_app/core/sso_config.py` (or an equivalent guard in `api/auth.py`) — a shared "SSO configured" FastAPI dependency applied to **all** SSO routes (login AND callback), returning 503 before any cipher/exchange work (§4.4).

All routes mount **bare** (PROXY-1): the SPA reaches them as `/api/v1/...` through the Vite proxy (dev) / edge rewrite (prod); EVE reaches the callback directly at the backend origin.

**Prod cookie-origin invariant.** The `hb_session` cookie is host-scoped (no `Domain` attribute). It is set on the callback response and must accompany the SPA's `/api/v1/*` calls, so **in production the registered callback host MUST be the same registrable origin the SPA is served from** — the edge routes both `/auth/sso/callback` and `/api/v1/*` to the backend on that one public origin. If the callback host differs from `FRONTEND_ORIGIN`'s host, the host-scoped cookie is never sent with SPA API calls and login silently no-ops (redirect lands, `/me` returns 401, header stays anonymous). Dev's `:8000`-direct callback works only because browsers ignore ports for cookie scope (`localhost:8000` sets, `localhost:5173` sends).

### 4.1 Login flow

1. SPA header button navigates (full page) to `/api/v1/auth/sso/login?next=<encodeURIComponent(pathname+search)>`. The SPA MUST `encodeURIComponent` the `next` value so an `&` inside the search does not truncate it into stray query params of the login endpoint (§5).
2. Backend validates `next` with the return-path validator (see below; invalid → fall back to `/`), generates `state = secrets.token_urlsafe(24)`, writes `sso_state:{state}` → JSON `{"next": ...}` with 600 s TTL, sets a short-lived **binding cookie** `hb_sso_state` carrying the same `state` value (HttpOnly, SameSite=Lax, `Secure` when `ENVIRONMENT != "development"`, Path=/, Max-Age 600 s), then 302-redirects to the authorize URL (`response_type=code`, `client_id`, `redirect_uri = settings.ESI_SSO_CALLBACK_URL`, empty `scope`, `state`).
   - **Return-path `next` validator:** the value must be a same-app relative path — start with a single `/` and not be a protocol-relative or backslash form — so reject `//…`, `/\…`, any leading backslash, and any scheme/authority (`https://…`, `javascript:…`); on any rejection fall back to `/`. This keeps login returning users inside Hangar Bay. The same validator is re-run at the callback on the value pulled from Valkey (step 4) so a malformed or externally-pointing `next` can never produce a protocol-relative `Location`.
3. EVE authenticates the user and 302s the browser to the registered callback (dev: directly to `:8000/auth/sso/callback`) with `code` + `state`.
4. Callback — **state binding check.** Read `state` from the query and `hb_sso_state` from the request cookie, and `GETDEL sso_state:{state}` from Valkey. Require **both** that the cookie value equals the returned `state` query param **and** that the GETDEL hit. The callback response clears the `hb_sso_state` cookie in all cases.
   - **State present but binding fails** (cookie missing or `hb_sso_state` ≠ `state`) → **hard 400** (bare JSON) — the callback did not come from a login this browser started, so it is the only exit that does not redirect.
   - **State simply missing/expired at callback** (GETDEL miss — e.g. the 600 s TTL lapsed during EVE 2FA, or Valkey was restarted) → redirect `FRONTEND_ORIGIN` with `?sso=error` and **no session** (an innocent user should not see a bare 400). No `next` is recoverable in this case, so redirect to `FRONTEND_ORIGIN/` with the flag.
   - **EVE-side denial** (`error` query param, no code) → re-validate the Valkey `next` and redirect to `FRONTEND_ORIGIN + <validated-next>` with `sso=denied` merged into the query, **no session**.
5. Exchange `code` at the token endpoint (shared httpx client, absolute URL, Basic auth, form body). Non-200 → structured log + redirect to `FRONTEND_ORIGIN + <validated-next>` with `sso=error` merged in.
6. Validate the JWT access token (per §2 checklist, incl. `leeway` on `exp`/`nbf`). Failure → log + redirect to `FRONTEND_ORIGIN + <validated-next>` with `sso=error` merged in. Extract character_id/name/owner.
7. Upsert user by `character_id`. **Owner-hash rule (F004 Criterion 1.6):** mismatch → update `owner_hash` and tokens in place; Hangar Bay data follows the character.
8. Encrypt access+refresh tokens (Fernet), store with `esi_access_token_expires_at = now + expires_in`, `last_login_at = now`.
9. Create session (fresh id — fixation defense by construction: ids are only ever minted server-side post-auth), set the `hb_session` cookie, clear the `hb_sso_state` binding cookie, and 302 to `FRONTEND_ORIGIN + <validated-next>` (with no `sso` flag on success).

**Query-merge rule (all redirecting exits).** Every callback exit that carries an `sso` flag — `denied`, `error`, and success (no flag) — builds its `Location` by parsing the validated `next` with `urllib.parse.urlsplit`/`parse_qsl`, adding `sso=<value>` via `urlencode`, and re-composing. NEVER string-concatenate a second `?`: a query-bearing `next` such as `/contracts?type=bpc&page=2` must yield `…/contracts?type=bpc&page=2&sso=denied`, not a malformed double-`?`. All redirect targets are absolute (`FRONTEND_ORIGIN` + path), so the denial/error UX always reaches the SPA at `:5173`, never the backend at `:8000`.

**Login-endpoint hard failures (bare JSON, accepted for M2).** The *login* endpoint has two failure modes that render as bare JSON rather than a friendly redirect — **not configured → 503** (§4.4) and **Valkey down at login click → 503** (`get_cache`, §4.2) — because they occur before any redirect context exists and the user has not yet left the app. Both are accepted for M2. Note the contrast with the *callback*, where the innocent-user state-missing/expired case redirects with `?sso=error` and only a genuine binding-cookie mismatch hard-400s.

### 4.2 Session mechanics

- Cookie `hb_session`: HttpOnly, SameSite=Lax (Lax cookies ride top-level navigations, so the callback→SPA redirect carries it), Path=/, `Secure` when `ENVIRONMENT != "development"`, Max-Age = absolute cap (30 d). It is host-scoped (no `Domain`), which is why the **prod cookie-origin invariant** in §4 requires the callback host to equal the SPA origin.
- Valkey `session:{sid}`, sid = `secrets.token_urlsafe(32)`; JSON value `{user_id, character_id, character_name, created_at}` (str client, `decode_responses=True` house pattern). **`created_at` is an integer Unix epoch seconds (UTC)** — pinned so the absolute-cap arithmetic and the clock-injection tests agree on one representation.
- **Idle renewal + absolute cap (one round trip).** Every authenticated read renews the idle window and enforces the absolute cap with a single `GETEX session:{sid} EX <ttl>`, where `<ttl> = min(idle_ttl, absolute_deadline - now)` and `absolute_deadline = created_at + 30 d`. Capping the renewal TTL this way means the Redis key **never outlives the 30-day absolute cap** (no stale session data survives past the deadline). After the `GETEX`, the absolute-cap check runs on the returned payload's `created_at`: if `now - created_at > 30 d` (i.e. `absolute_deadline - now <= 0`) → `DEL session:{sid}` + return 401. There is no separate write, and no "checked before renewal" ordering — the single `GETEX` reads and renews atomically, and an over-cap session is deleted in the same request so any incidental TTL is moot.
- `/me` serves from the session payload alone (no DB read). Consequence embraced: dev DB wipes (ENV-2) don't log anyone out; the user row is recreated at next login; M2 has no endpoint that needs the token vault, so a wiped vault row is inert. Any future token-using endpoint must handle a missing user row by forcing re-login (noted for M3).
- Logout: **idempotent** `POST /auth/sso/logout` → `DEL session:{sid}` (if any) + expiring Set-Cookie, always **204** — including for a missing/invalid/expired session (it is NOT gated behind `get_current_session`/401, so a user whose idle window lapsed gets a clean no-op, not a mutation error). Cross-site posture: the load-bearing control is **SameSite=Lax** — Lax withholds the cookie on cross-site POST/fetch, so a cookie-bearing logout POST can only originate from Hangar Bay's own pages. (CORS is not the control: CORS never blocks a request from being *sent*, only from being *read*; relying on "no CORS" would be wrong and would mislead a future change.) No separate cross-site request token is needed for M2's logout-only mutation surface, but any future move to `SameSite=None` or a cross-origin mutation surface would require one.
- Valkey down (`app.state.redis` None): session dependency 503s via the existing `get_cache` behavior — same failure contract as the rest of the app.

### 4.3 Token refresh (mechanism only in M2)

`services/sso.refresh_token_pair(user)` implements the refresh grant (Basic auth, `grant_type=refresh_token`), persists the **returned** refresh token (rotation-safe), re-encrypts, updates expiry. **Invalid-grant response → "mark for re-auth", which in M2 means concretely: null out the `esi_*` token columns (`esi_access_token`, `esi_access_token_expires_at`, `esi_refresh_token`) and nothing more.** F004's refresh-failure [DECIDED] flow also calls for invalidating the user's Hangar Bay session, but that half is **explicitly deferred to M3's caller**: the M2 session store is keyed by `sid` with no user→sid index (§4.2), so per-user session invalidation is not buildable on it. This is a recorded deviation from F004 (also logged in Appendix B); M3, which introduces the token-using caller, enforces re-auth per-request by checking token presence. **No M2 endpoint calls it** — it exists with full test coverage because F004 Story 4 requires the mechanism and M3 consumes it immediately. `[MORNING-REVIEW — thin-YAGNI call: mechanism+tests without a caller]`

### 4.4 Config additions (consolidated Settings)

```
ESI_CLIENT_ID: str = ""                     # empty ⇒ SSO endpoints 503 "not configured"
ESI_CLIENT_SECRET: SecretStr = SecretStr("")
ESI_SSO_AUTHORIZE_URL / _TOKEN_URL / _JWKS_URI: str  # defaults = verified §2 endpoints
ESI_SSO_CALLBACK_URL: str = "http://localhost:8000/auth/sso/callback"
FRONTEND_ORIGIN: str = "http://localhost:5173"       # post-login redirect base
SESSION_COOKIE_NAME: str = "hb_session"
SESSION_IDLE_TTL_SECONDS: int = 604_800     # 7 d
SESSION_ABSOLUTE_TTL_SECONDS: int = 2_592_000  # 30 d
TOKEN_CIPHER_KEYS: SecretStr = SecretStr("")  # comma-separated Fernet keys, first=primary
```

Secrets are `SecretStr` (log/repr safe). The not-configured guard is a **shared FastAPI dependency applied to ALL SSO routes (login AND callback)**, not just login: if `ESI_CLIENT_ID` is empty or `TOKEN_CIPHER_KEYS` is empty/whitespace-only (per the §3.4 parse rule), the route responds **503** `{"detail": "EVE SSO is not configured"}` **before any cipher construction or token exchange** — so a direct hit to the callback with empty cipher keys returns a clean 503, never a 500 from `MultiFernet([])`/`Fernet("")`. Combined with the lazy cipher build (§3.4), empty keys never crash boot. One startup warning is logged in development. **All new fields carry defaults**, so `export_openapi.py`'s `_ENV_DEFAULTS` needs no additions (verified requirement from recon: required-without-default fields break codegen). `app/backend/.env.example` is updated to document every actually-required key (it currently omits `ESI_USER_AGENT` and `DATABASE_URL_TESTS`) plus the new SSO block with a `Fernet.generate_key()` one-liner. Sam's manual step tomorrow remains only `ESI_CLIENT_ID`/`ESI_CLIENT_SECRET`; the cipher key is machine-generated during dev bring-up.

### 4.5 Data model

`User` (replaces the legacy stub wholesale — Integer character_id would overflow modern IDs):

```
id                            int PK autoincrement
character_id                  BigInteger, unique, indexed, not null
character_name                String(255), not null
owner_hash                    String(255), not null, indexed
esi_access_token              Text, nullable        (Fernet ciphertext)
esi_access_token_expires_at   DateTime(timezone=True), nullable
esi_refresh_token             Text, nullable        (Fernet ciphertext)
esi_scopes                    Text, nullable        (empty in F004; filled by F005+)
last_login_at                 DateTime(timezone=True)
created_at / updated_at       DateTime(timezone=True), server defaults
```

SQLAlchemy 2.0 `Mapped`/`mapped_column` style per `models/contracts.py`. Registered via `models/__init__.py`. **Migrations:** dev keeps drop/create (ENV-2); the stale SQLite-era Alembic *revision chain* is left untouched and explicitly out of scope — but `src/alembic/env.py` is **not** out of scope for imports: it currently imports the deleted `common_models`/`User` (see §4 and §3.5 blast radius), so the **same commit that deletes `common_models.py` MUST update `env.py`'s imports** (drop the `common_models`/`User` imports; optionally register `models/user.py`) or every alembic command breaks with `ImportError`. `create_db_tables()` gains an `ENVIRONMENT == "development"` gate with a logged skip otherwise (prod schema management = future migrations work, flagged in §8).

## 5. Frontend design

- **Hook:** `src/features/auth/hooks/useCurrentUser.ts` — key `['auth','me']`, `api.GET('/me')`; 401 (or any failure) resolves to `null` (anonymous) rather than throwing — no retry storm (global retry:1 is bypassed by resolving, not rejecting, on 401), no error UI for the anonymous state. `staleTime` 60 s.
- **Header** (`routes/__root.tsx`): right side via `ml-auto`. Anonymous → ghost `Button` (h-8) as an anchor to `` `/api/v1/auth/sso/login?next=${encodeURIComponent(pathname + search)}` `` — full navigation, not SPA route; the `encodeURIComponent` is required so a query-bearing path (the common case, given the filter-heavy URLs) round-trips intact (§4.1 step 1). Authenticated → 24 px portrait `<img src="https://images.evetech.net/characters/{id}/portrait?size=64" alt="">` (64 = 2× for retina; decorative alt), character name in `text-ink text-sm`, and a ghost Logout button. Container stays `items-baseline`; the identity cluster self-aligns (`items-center` on its own flex).
- **Logout:** `useLogout` mutation → `POST /auth/sso/logout` → on settle, `queryClient.invalidateQueries(['auth','me'])`. No redirect; header re-renders to anonymous.
- **Login-result feedback:** the `?sso=denied|error` notice lives in `__root.tsx` and reads the raw query via `useLocation().search` — deliberately **outside** the typed per-route `validateSearch` (e.g. `/contracts`'s `parseContractSearch`), which drops unknown keys, so `sso` would never survive into typed search state; the root route has no `validateSearch` of its own. On `denied`/`error` it renders one dismissible inline notice near the header (polite live region); no toast infrastructure invented for M2. **Dismissing performs a replace-navigation that strips the `sso` param** from the URL, so a refresh, a back-navigation, or a copied link does not re-show the notice or carry `?sso=error` forever. Both variants render (`denied` from EVE-side denial; `error` from token-exchange/JWT failure or state-missing-at-callback).
- Codegen chain after backend lands: `pdm run export-openapi` → `npm run generate:api`; `CurrentUser` type alias added in `lib/api/client.ts` per house pattern.
- All new strings hardcoded English (i18n deferred per M1 precedent); buttons keyboard-accessible with the global focus-visible outline; portrait is decorative (name is the accessible identity).

## 6. Testing strategy (TDD throughout)

**Backend (pytest, HTTP-level per TEST-1):**
- **JWT validation via the injected JWKS seam (§3.2).** The token-endpoint POST(s) are mocked with `pytest-httpx` (real-shaped token responses matching the verified wire shape); the JWKS/signing key is supplied through the injectable `PyJWKClient`/signing-key provider — backed by an in-test JWKS dict, or with `PyJWKClient.fetch_data` monkeypatched — because pytest-httpx cannot intercept PyJWKClient's synchronous urllib fetch. JWTs are **actually signed** by a test key so the validator runs for real (signature, kid selection, alg allowlist; ESI-seam lesson: no dict-shaped fantasies). Quirk tests: both `iss` forms accepted, wrong `iss` rejected, `aud` array **with** `client_id` accepted and **without** it rejected, HS256 token rejected, `exp` a few seconds past-**within**-`leeway` accepted, `exp` **beyond** leeway rejected, kid-miss behavior.
- **Auth-test fixture (app.state wiring).** ASGITransport does not run lifespan, so neither `app.state.redis` nor `app.state.http_client` exists in tests. A fixture sets BOTH on the module-global `real_app`: `app.state.redis` = the fake Valkey, and `app.state.http_client` = a real `httpx.AsyncClient` created **in-test** (so pytest-httpx intercepts its transport for the token POSTs); it **DELETES both attributes in teardown** (no cross-test leakage, since `real_app` is module-global). The 503-when-cache-absent test relies on the attribute being absent by default (lifespan never ran under ASGITransport).
- **Sessions: in-memory fake Valkey** — extend the `_FakeLockRedis` house precedent with get / set (with `ex`) / getex / getdel / delete / exists + TTL bookkeeping. `getdel` is modeled **atomically** so the single-use state test is honest; `getex` renews the TTL. Injected via `app.state.redis`/`get_cache` override — no new dependency. Tests: idle renewal on read (`GETEX EX min(idle_ttl, deadline - now)`), the renewal TTL capped so the key never outlives the 30-day deadline, absolute-cap expiry via `created_at` clock injection (over-cap → `DEL` + 401), single-use state consumption (a second `GETDEL` misses), logout deletion, 503 when cache absent.
- **Login-endpoint / return-path validation tests** (HTTP-level on `GET /auth/sso/login`): `next` in {`//evil.com`, `/\evil.com`, `https://evil.com`, `javascript:alert(1)`, missing, garbage} all store `'/'`; the 302 `Location` is the authorize URL with exact params (`response_type=code`, `client_id`, `redirect_uri`, empty `scope`, `state`); `sso_state:{state}` is written with the 600 s TTL; the `hb_sso_state` binding cookie is set.
- **Callback flow tests:** full happy path (user created, tokens encrypted — assert ciphertext ≠ plaintext and round-trips; `hb_session` cookie set), owner-hash transfer update, **state present but binding cookie missing/mismatched → 400** (binding check failed, no redirect), **state missing/expired → redirect `FRONTEND_ORIGIN` with `?sso=error`, no session**, EVE denial → absolute `FRONTEND_ORIGIN` Location with `sso=denied` merged, token-endpoint non-200 → `sso=error` redirect, JWT failure → `sso=error` redirect, `next=//evil.com` and `next=/\evil.com` **cannot** yield a protocol-relative Location, a query-bearing `next` (`/contracts?type=bpc&page=2`) round-trips and merges `sso` with `&` (never a double-`?`), `/me` 200/401, refresh grant incl. rotation persistence and invalid-grant `esi_*` token-column nulling, **callback with unconfigured cipher → 503 (not 500)**.
- **Cookie-attribute tests:** assert the callback `Set-Cookie` for `hb_session` carries HttpOnly, SameSite=Lax, Path=/, Max-Age; a **parametrized settings-override** test asserts `Secure` present when `ENVIRONMENT` is `production`/`test` and absent in `development`; assert the logout response's expiring `Set-Cookie`.
- **Config / boot:** consolidated Settings load test **including the resolved `.env`-path assertion** (`Path(__file__).resolve().parents[2] / ".env"` → `app/backend/src/.env`); a test that the **app boots with empty `ESI_CLIENT_ID` and empty `TOKEN_CIPHER_KEYS`** (lazy cipher — no crash) and `/auth/sso/login` returns the 503 body — this is **AC-4's verifying test**; `app.openapi()` schema assertions for `/me` (TEST-1 schema check).

**Frontend (vitest):**
- `useCurrentUser` (200 → user, 401 → null with no retry, fetch seam per TEST-5 asserting URL), header render states, logout mutation **asserting the fetch URL + method** (not just query invalidation), and `?sso=denied` / `?sso=error` header-notice render + dismissal-strips-the-param. Component tests via `renderApp`.
- **Existing-component-test sweep (mirrors the E2E rule):** `renderApp` mounts the real routeTree → header → fires `GET /api/v1/me`. Existing URL-agnostic fetch stubs would answer `/me` with a contract-shaped 200, so the header renders a bogus authenticated state (name undefined, portrait src `.../characters/undefined/portrait`). Fix: **URL-aware stubs that answer `/api/v1/me` with 401 by default**, via a shared helper in `src/test/http.ts` (one line per test) or a `renderApp` default `/me`=401 handler.

**E2E (Playwright fixture lane):** new `e2e/fixtures/auth.ts` (`WireCurrentUser`, `makeCurrentUser`) + `interceptCurrentUser(page, responder)` and `interceptLogout(page, responder)` helpers (the latter returns captured calls). **Every existing spec gains the anonymous default** (`{status: 401}`) — the header now queries `/me` on every page. The mechanism is not uniform: `failUnexpectedApiCalls` is registered in only **one** spec (`detail.spec.ts`), so only there would an unpatched `/me` abort the test; the other spec files would instead **leak `/me` to the Vite proxy** (backend absent in the fixture lane → connection error → the fail-open hook resolves anonymous), which is non-hermetic and timing-dependent. Either way explicit 401 interception is required in **every** spec — for determinism and call-count assertions — regardless of whether it uses `failUnexpectedApiCalls`. New specs: anonymous header, authenticated header (name + portrait + logout), logout flow — the logout spec asserts **exactly one POST to `/api/v1/auth/sso/logout` fulfilled 204** (via `interceptLogout`) **before** asserting the anonymous transition (so the test cannot pass on a logout POST that never reached the backend). Retries stay 0; TEST-7 double-attempt accounting is moot because the hook doesn't retry-then-error on 401. **Live-lane SSO login is explicitly deferred** until Sam registers the app; a `?sso=denied` fixture spec covers the denial UX.

**CI (new, own PR):** `.github/workflows/ci.yml` — backend job (Postgres 16 + Valkey 7.2 services, pdm install, pytest) and frontend job (npm ci, eslint, tsc -b, vitest, Playwright fixture lane with browser install). Green CI becomes the merge gate the git-strategy policy assumes.
- **Backend job env (required, or collection/boot fails).** `conftest.py` hard-fails at import without `DATABASE_URL_TESTS`, and the consolidated Settings keeps `DATABASE_URL`/`CACHE_URL`/`ESI_USER_AGENT` required with `.env` untracked, so the workflow MUST export: `DATABASE_URL`, `DATABASE_URL_TESTS` (pointing at a database the job creates or the service's `POSTGRES_DB`), `CACHE_URL`, `ESI_USER_AGENT`, and `TOKEN_CIPHER_KEYS` (a generated throwaway `Fernet.generate_key()` value) — all pointing at the service containers. The Postgres service MUST have the `DATABASE_URL_TESTS` database available (the suite drops/recreates it). **Pin Python to 3.12** — the locked `pydantic-core` wheels don't support 3.14.
- **Frontend job:** cache the Playwright browsers to avoid re-downloading on every run.

## 7. Security review checklist (design-time)

- State: single-use (`GETDEL`), 600 s TTL, 192-bit entropy, **AND browser-bound** via the `hb_sso_state` cookie set at login and required to equal the returned `state` at callback (§4.1). Single-use + entropy confirm the value wasn't guessed or replayed; the browser binding confirms the callback is completing the same login this browser started — the returned `state` must match the cookie set when the flow began, so a callback can only finish a login the same browser began. Session ids 256-bit, minted only post-auth.
- Return-path validation on `next` (same-app relative paths only: single-leading-`/` allowlist; rejects `//`, `/\`, backslashes, and scheme/authority forms → `/`), **re-run at the callback** on the value pulled from Valkey; the callback redirects only to `FRONTEND_ORIGIN` + validated path, and every `sso` flag is merged into the query via a parsed-URL builder (never a second `?`).
- JWT: signature (RS256/ES256 by kid, JWKS cached), `exp` enforced with a small `leeway` (30–60 s) against clock skew, `nbf`/`iat` validated when present, `aud` must contain client_id, `iss` two-value allowlist, algorithm allowlist excludes HS256.
- Cookies: HttpOnly + SameSite=Lax + Secure-outside-dev; no token material ever leaves the backend; no CORS middleware exists (same-origin contract).
- Secrets: `SecretStr` fields; Basic-auth header built at call time; **no tokens, cipher keys, or JWTs in logs** — `log_key_event` payloads carry character_id/outcome/duration only (Universal Gotcha: no secrets in logs; character_id is public EVE data, not PII).
- Encryption: Fernet (AES-CBC+HMAC, authenticated); keyring rotation via MultiFernet; wrong-key decrypt raises → treated as missing tokens (re-auth path), never a 500.
- `.env` stays untracked; Sam hand-places EVE credentials; nothing secret enters chat, commits, or PR bodies.

## 8. Deferred / out of scope

- ESI scopes, structure-name resolution (M3, gets its own feature spec and EVE app consent change).
- Live SSO end-to-end test + live-smoke auth lane — blocked on Sam's app registration (tomorrow).
- Real migrations (Alembic revival) for production schema management; M2 only gates the destructive dev path.
- Multi-character account linking, session listing/revocation UI, cross-site request tokens beyond SameSite (unneeded until cross-origin or non-Lax surfaces exist), i18n.
- Token revocation call on logout (F004 [DECIDED]: sessions die locally; users manage grants at EVE's authorized-apps page).

## 9. Riding-along improvements (each small, each serving M2's touched files)

1. Settings consolidation (§3.5) — the SSO config home demands it.
2. Debug `print()` cleanup in both config modules + validators (dies with consolidation), **plus `main.py`'s import-time debug print** (`PYDANTIC_VERSION_CHECK_PRINT`). Including it here keeps AC-5 ("no debug prints at import") literally true across the whole import path, not just the config modules.
3. `db.py` duplicate `Base`/`get_db_session_factory` dead-code removal (file is touched for the import swap anyway).
4. `.env.example` corrected to the real required set (ENV-1 documentation debt).
5. Dev-only gate on `create_db_tables()` (§4.5).
6. Closing-gate UI nits from the M1 handoff, batched into the frontend PR: singular "1 contracts" live region fix, price Min/Max 14px-vs-13px label drift. **The "1 contracts" fix is not test-free:** `pages.test.tsx` asserts the exact string `'X contracts match your filters'`, so that exact-match vitest assertion MUST be updated in the same change (the E2E matcher is loose, but the unit assertion is not). (Aggregation-lock TTL watchdog and the theoretical out-of-range-redirect edge stay deferred — unrelated to files M2 touches.)

**PR plan.** M2 ships as ordered PRs, each getting an independent `/codex` review (gpt-5.6-sol, xhigh) before merge per repo policy:
1. **CI PR first** — `.github/workflows/ci.yml`, green on the current tree, so the merge-authority policy's "green CI" gate is real for everything after it.
2. **Settings-consolidation + backend auth PR** — consolidation must precede or accompany the auth code because it gates where SSO config lives; the two ship together (or consolidation immediately before). Codegen artifacts (`openapi.json`, `schema.d.ts`) are committed **with** the backend schema change per CLAUDE.md.
3. **Frontend PR** — header identity, `useCurrentUser`/`useLogout`, `?sso` notice, and the batched UI nits.

## 10. Acceptance criteria (M2 done =)

1. All F004 Story 1–4 criteria met under the §2 corrections (login, session persistence, logout, secure token custody), verified by the §6 suites.
2. Header shows login button (anonymous) / portrait + name + logout (authenticated); `?sso=denied|error` feedback renders.
3. Backend pytest, frontend vitest + eslint + `tsc -b` + Playwright fixture lane: all green, locally and in the new CI.
4. Boots cleanly with **no** EVE credentials and **empty `TOKEN_CIPHER_KEYS`** (lazy cipher build — no startup crash), and every SSO route returns the 503-not-configured body via the shared guard — Sam can register the app tomorrow and only edit `.env`. Verified by the §6 boot-with-empty-keys test.
5. Two Settings classes are one; `.env.example` is truthful; no debug prints at import.
6. Docs updated: F004 status → Implemented-with-corrections note, README implementation status, pitfalls entries for any new traps discovered during implementation.

---

## Appendix A — Reasoning chain & alternatives (per CLAUDE.md thinking-documentation discipline)

**Why hand-rolled beats Authlib here (the closest call in §3):** the axis that decided it was *what we must own regardless*. Refresh-rotation persistence, dual-iss validation, state-in-Valkey (not in a Starlette session), and the absolute-cap session policy are all custom code under either option; Authlib would contribute only the authorize-URL builder and the token POST — the two easiest parts — while adding a dependency whose session-middleware assumption actively fights the design. If a later feature needs PKCE-public-client flows or multiple providers, revisit.

**Why the JWKS client's sync fetch is acceptable:** it fires on cache miss only (300 s TTL + kid-keyed LRU); wrapped in `asyncio.to_thread` it cannot stall the loop. The alternative (async httpx fetch + joserfc) trades a rare threadpool hop for owning cache/refresh/kid-retry logic — worse trade at this scale.

**Why sessions don't touch the DB on read:** `/me` is on every page load; the session payload already carries the two fields the UI needs. The cost is accepting that a renamed character shows a stale name until next login (EVE renames are rare and paid); the benefit is that ENV-2 dev wipes stop mattering for logged-in UX. Rejected alternative: DB-hydrated `/me` (fresh names, but couples the hot path to the wiped-nightly table).

**Why Fernet despite no AAD:** the swap-ciphertexts-between-rows concern that AAD addresses only matters to someone with direct DB write access — who could equally edit `character_id` directly. Nonce-reuse under AES-GCM is a sharper edge than anything Fernet exposes. Misuse-resistance is the criterion for a codebase where future contributors are agents.

**Why the `state` cookie (browser-binding) is required, not just single-use + entropy:** a `state` value stored only server-side, keyed by its own value, confirms the value wasn't guessed or replayed — but on its own it does not confirm that the callback is completing the login *this browser* started (the property the `state` parameter exists to provide, per RFC 6749 §10.12 and RFC 6819). Without browser-binding, a callback carrying any otherwise-valid `(code, state)` pair would be accepted no matter which browser began the flow, so a user could end up signed in as a character other than their own. Binding `state` to a short-lived `hb_sso_state` cookie set at `/login`, and requiring the returned `state` to equal that cookie at the callback (§4.1, §7), ties the callback to the browser that started it — the cookie is only present in the browser that began the login. That is why the callback checks **both** the cookie match and the Valkey `GETDEL` hit, and why a cookie mismatch is the one exit that returns a plain 400 instead of redirecting.

**Considered and ruled out, kept visible:** starsessions (maintenance + no absolute cap), python-jose (dormant + CVE history), fastapi-sso (wrong shape), Authlib (dependency > contribution), AES-GCM (nonce discipline), reviving Alembic tonight (ocean, not lake — flagged instead), cross-site request tokens (no cross-origin mutation surface exists), storing sessions in signed cookies (server-side revocation required by F004), SPA-origin callback via Vite proxy (`:5173/api/v1/...` → works in dev but bakes the dev proxy into the EVE registration). The `:8000` direct callback keeps the registration **deploy-shaped in its path** (`/auth/sso/callback`, no dev-proxy `/api/v1` prefix baked in) — but "deploy-shaped" is about the path only: **in production the callback MUST be fronted on the same registrable origin the SPA is served from** (edge routes `/auth/sso/callback` and `/api/v1/*` to the backend there), because the `hb_session` cookie is host-scoped (§4 prod cookie-origin invariant). Dev's split-port callback works only because browsers ignore ports for cookie scope; a split-*host* prod deployment without that edge routing would silently no-op login.

**What I'm still uncertain about:** (1) whether EVE has quietly enabled refresh-token rotation for confidential clients in 2026 — designed for rotation either way; (2) whether the dev portal still hard-limits one callback URL per app — if it now allows several, dev+prod could share an app, but the design assumes separate registrations (safer); (3) `GETEX` availability is Redis ≥ 6.2 / Valkey 7.2 — satisfied by the pinned compose image, but a fallback (`GET`+`EXPIRE` pipeline) is noted for the implementer if the fake-Redis test double makes GETEX awkward.

**Things the recon caught that would have been bugs:** F004's ID-token language (§2.1 — validation code written against an id_token field would fail at runtime against the real token endpoint); `Integer` character_id overflow; `export_openapi._ENV_DEFAULTS` breaking on required-no-default settings; every existing E2E spec leaking `/me` once the header queries it; the two-Settings trap making naively-placed SSO config invisible to the DI layer.

## Appendix B — Morning-review register

Items Sam should eyeball, none blocking overnight execution: §3.5 settings consolidation scope (pre-blessed as candidate), §4.3 refresh-mechanism-without-caller, §4.5 legacy User model deletion, the dev-only `drop_all` gate, CI workflow addition as M2 scope, and the design-review reordering (the multi-lens Fable spec review ran before Sam's gate instead of after — re-runnable after any morning edits).

**Recorded deviation from F004 (§4.3):** F004's refresh-failure [DECIDED] flow calls for invalidating the user's Hangar Bay session on invalid-grant, but the M2 session store is keyed by `sid` with no user→sid index, so per-user session invalidation is not buildable on it. M2 therefore implements "mark for re-auth" as **nulling the `esi_*` token columns only**; the session-invalidation half is deferred to M3's token-using caller (which enforces re-auth per-request by checking token presence). Recorded here so the narrowing is deliberate, not accidental.
