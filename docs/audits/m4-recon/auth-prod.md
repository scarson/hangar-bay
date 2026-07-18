# M4 Recon — Auth / SSO Production Constraints

ABOUTME: Read-only recon of Hangar Bay's EVE SSO auth plumbing for the M4 (production readiness / deployment) designer — cookie/origin invariant, session & cookie config, token cipher key format, JWKS network dependency, deferred live-verification thread, and prod EVE app-registration needs.
ABOUTME: Facts only, described in correctness/configuration terms — exact cookie attributes, Settings fields, key formats, and the two prod hazards (no prod schema-creation path; JWKS needs egress). No code was modified.

Scope: `app/backend/src/fastapi_app/`. All paths below are relative to
`/Users/sam/Code/hangar-bay/.claude/worktrees/hangar-bay-frontend-rebuild-2e4fe7/`.
Canonical design source is the M2 EVE SSO design spec at
`docs/superpowers/specs/2026-07-12-m2-eve-sso-design.md` (cited as "design spec §N").

---

## 1. The prod cookie-origin invariant (design spec §4) — quoted + implications

### The invariant, quoted verbatim (design spec §4, `2026-07-12-m2-eve-sso-design.md:89`)

> **Prod cookie-origin invariant.** The `hb_session` cookie is host-scoped (no `Domain` attribute). It is set on the callback response and must accompany the SPA's `/api/v1/*` calls, so **in production the registered callback host MUST be the same registrable origin the SPA is served from** — the edge routes both `/auth/sso/callback` and `/api/v1/*` to the backend on that one public origin. If the callback host differs from `FRONTEND_ORIGIN`'s host, the host-scoped cookie is never sent with SPA API calls and login silently no-ops (redirect lands, `/me` returns 401, header stays anonymous).

Reinforced at design spec §4.2 (`:113`): "It is host-scoped (no `Domain`), which is why the **prod cookie-origin invariant** in §4 requires the callback host to equal the SPA origin."

### What the invariant implies for deployment topology

The whole system assumes **one public origin (scheme + host + port)** that fronts three things through the edge:

1. **The SPA static assets** (served from `FRONTEND_ORIGIN`).
2. **The API** at `/api/v1/*` — the edge strips `/api/v1` and proxies to bare FastAPI routes (PROXY-1; design spec §4 `:87`, and the router mounts are bare in `main.py:192-194`).
3. **The SSO callback** at `/api/v1/auth/sso/callback` — same edge, same origin, also stripped to the bare `/auth/sso/callback` route (`api/auth.py:184`).

Concrete deployment consequences the M4 designer must satisfy:

- **No split-origin topology.** You cannot serve the SPA from e.g. `app.hangarbay.example` and the API from `api.hangarbay.example`: the host-scoped `hb_session` set on the API host would never be sent by the browser on requests to the SPA host, and vice-versa. Login would appear to succeed (302 lands) but `/me` returns 401 forever. A single origin with path-based routing (`/` → SPA, `/api/v1/*` → backend, `/api/v1/auth/sso/*` → backend) is required, OR a same-registrable-domain setup where the cookie is deliberately made domain-scoped (which the current code does NOT do — see §2).
- **The edge owns the `/api/v1` prefix and trailing-slash handling** (design spec §4 `:87-89`; PROXY-1). FastAPI never sees `/api/v1`. The reverse proxy / CDN / edge worker must rewrite `/api/v1/...` → `/...` before hitting the backend, for both API calls and the callback.
- **HTTPS end-to-end at the edge.** The cookie is `Secure` outside development (§2 / §6), so the public origin must be `https://`. In dev this is faked with `@vitejs/plugin-basic-ssl` on `https://localhost:5173` (design spec §5 `:166`); prod needs a real cert on the public origin.
- **`FRONTEND_ORIGIN` and `ESI_SSO_CALLBACK_URL` must be set to the same public host in prod** (both currently default to `https://localhost:5173`; see §2/§5). All callback redirect targets are built as `FRONTEND_ORIGIN + <validated-next>` (`api/auth.py:224,228,271,276`), so a wrong `FRONTEND_ORIGIN` sends users to the wrong origin post-login.
- **No CORS layer exists and none is wanted** (design spec §7 `:195`: "no CORS middleware exists (same-origin contract)"). The same-origin topology is load-bearing; introducing a cross-origin split would require inventing CORS + likely `SameSite=None` + a cross-site request token (design spec §4.2 `:117` calls this out explicitly).

---

## 2. Session cookie attributes, callback mount, and SSO config fields

### `hb_session` cookie attributes (set in `api/auth.py:277-280`)

```python
resp.set_cookie(
    s.SESSION_COOKIE_NAME, sid, max_age=s.SESSION_ABSOLUTE_TTL_SECONDS, httponly=True,
    samesite="lax", secure=_cookie_secure(), path="/",
)
```

| Attribute | Value | Source |
|---|---|---|
| Name | `hb_session` | `SESSION_COOKIE_NAME`, `core/config.py:47` |
| `HttpOnly` | yes | `api/auth.py:278` |
| `SameSite` | `Lax` | `api/auth.py:279` |
| `Secure` | `ENVIRONMENT != "development"` | `_cookie_secure()`, `api/auth.py:80-81` |
| `Domain` | **absent (host-scoped)** — never set | (no `domain=` kwarg) — this is what §1 hinges on |
| `Path` | `/` | `api/auth.py:279` |
| `Max-Age` | `SESSION_ABSOLUTE_TTL_SECONDS` = 2,592,000 (30 d) | `core/config.py:49` |

Cookie value is the opaque `sid` = `secrets.token_urlsafe(32)` (256-bit), minted only post-auth (`core/session.py:59`). The session payload lives server-side in Valkey under `session:{sid}` (`core/session.py:15,66`); the cookie carries no identity data.

The short-lived login binding cookie `hb_sso_state` shares the same attribute pattern (HttpOnly, SameSite=Lax, `secure=_cookie_secure()`, Path=/, Max-Age 600 s) at `api/auth.py:111-114`.

### Where the callback route is mounted

- Router: `router = APIRouter(prefix="/auth/sso", tags=["Auth"])` (`api/auth.py:28`) — **bare, no `/api/v1`**.
- Callback path: `@router.get("/callback", ...)` (`api/auth.py:184`) → bare `/auth/sso/callback`.
- Login: `@router.get("/login", ...)` (`api/auth.py:89`). Logout: `@router.post("/logout", ...)` (`api/auth.py:285`). `/me`: separate `me_router = APIRouter(tags=["Auth"])` mounting bare `/me` (`api/auth.py:29,296`).
- All mounted with **no prefix** in `main.py:192-194` (`app.include_router(auth_router.router)`, `app.include_router(auth_router.me_router)`). The SPA reaches the callback at `/api/v1/auth/sso/callback`; the edge strips `/api/v1` (PROXY-1).

### EVE SSO redirect / callback URL + client-credential Settings (all in `core/config.py:35-50`)

```python
ESI_CLIENT_ID: str = ""                                        # empty ⇒ SSO routes 503 "not configured"
ESI_CLIENT_SECRET: SecretStr = SecretStr("")                   # SecretStr — log/repr safe
ESI_SSO_AUTHORIZE_URL: str = "https://login.eveonline.com/v2/oauth/authorize"
ESI_SSO_TOKEN_URL: str    = "https://login.eveonline.com/v2/oauth/token"
ESI_SSO_JWKS_URI: str     = "https://login.eveonline.com/oauth/jwks"
ESI_SSO_CALLBACK_URL: str = "https://localhost:5173/api/v1/auth/sso/callback"  # MUST match dev-portal char-for-char
FRONTEND_ORIGIN: str      = "https://localhost:5173"           # post-login redirect base
SESSION_COOKIE_NAME: str  = "hb_session"
SESSION_IDLE_TTL_SECONDS: int = 604_800                        # 7 d sliding
SESSION_ABSOLUTE_TTL_SECONDS: int = 2_592_000                  # 30 d hard cap
TOKEN_CIPHER_KEYS: SecretStr = SecretStr("")                   # comma-separated Fernet keys, first=primary
```

- `ESI_SSO_CALLBACK_URL` is the value sent to EVE as `redirect_uri` in the authorize URL (`api/auth.py:106-108` → `sso.build_authorize_url(..., redirect_uri=s.ESI_SSO_CALLBACK_URL, ...)`, `services/sso.py:46-54`). **EVE requires this to match the registered callback char-for-char** (comment `core/config.py:41-42`). For prod this default `https://localhost:5173/...` MUST be overridden to the public origin's `.../api/v1/auth/sso/callback`.
- `ESI_CLIENT_ID` / `ESI_CLIENT_SECRET` are the confidential-client credentials; `ESI_CLIENT_SECRET` is used as HTTP Basic auth on the token POST (`services/sso.py:87` `auth=(client_id, client_secret)`, called from `api/auth.py:242` with `s.ESI_CLIENT_SECRET.get_secret_value()`).
- **Not-configured guard:** `require_sso_configured()` (`api/auth.py:36-39`) 503s `{"detail": "EVE SSO is not configured"}` if `ESI_CLIENT_ID` is empty OR the cipher is unconfigured. Applied to `/login` (declarative `dependencies=`, `api/auth.py:91`) and `/callback` (inline so it can also clear the state cookie, `api/auth.py:128-140,210-212`). **Logout is NOT gated** and always 204s (`api/auth.py:285`, and `main.py:158-160` comment).

### `TOKEN_CIPHER_KEYS` format, generation, rotation (`core/token_cipher.py`)

- **Format:** a **comma-separated list of Fernet keys**; each key is a urlsafe-base64-encoded 32-byte value (a standard `Fernet.generate_key()` output). First element is the primary (encrypt) key; the rest are decrypt-only for rotation. Parsing: `parse_cipher_keys` splits on comma, strips each element, drops empties (`token_cipher.py:10-12`).
- **Generation** (`.env.example:27-29`): `python3 -c "import base64,os; print(base64.urlsafe_b64encode(os.urandom(32)).decode())"` (dependency-free equivalent of `Fernet.generate_key()`).
- **Rotation via `MultiFernet`:** `_build_cipher()` builds `MultiFernet([Fernet(k) for k in keys])` (`token_cipher.py:20-26`). MultiFernet encrypts with the first key and decrypts by trying each in order — so to rotate, prepend the new key and keep the old one until all stored ciphertexts are re-encrypted. `_build_cipher()` is deliberately rebuilt per call (not memoized) precisely so keys can rotate between calls (`token_cipher.py:21-22`).
- **Empty/whitespace-only ⇒ not-configured, never a boot crash:** `is_token_cipher_configured()` returns `bool(parse_cipher_keys(raw))` (`token_cipher.py:15-17`); `_build_cipher()` raises `RuntimeError` only if actually invoked with no keys (`token_cipher.py:24-25`). Combined with the lazy build, empty keys 503 the SSO routes rather than crashing startup (design spec §4.4).
- **Wrong-key decrypt is treated as re-auth, not a 500** (design spec §7 `:197`): a `MultiFernet` `InvalidToken` on decrypt of a stored token surfaces through `auth_service.refresh_user_tokens` → `mark_for_reauth` (per the M3 recon `backend-data-auth.md` §4). Relevance to M4: **rotating out a still-in-use key silently invalidates every stored ESI token encrypted only under the dropped key** — a rotation-ordering constraint for ops.
- **Prod hazard:** `TOKEN_CIPHER_KEYS` is the at-rest encryption root for the ESI token vault. It must be provisioned as a real secret in prod (secret manager / scoped env), never a CLI flag (Universal Gotcha: no secrets in CLI flags). If lost, all stored refresh tokens become undecryptable and every user must re-login.

---

## 3. JWKS handling — "offline validation" does NOT mean "no network in prod"

**This is the single most easily-misread auth constraint for deployment.** The pitfall ESI-1 and the design docs say SSO JWTs are validated "offline against JWKS" — but that phrase means **validate the token signature locally against JWKS keys instead of round-tripping EVE's `/verify` endpoint per request**, NOT that the JWKS document is bundled on disk.

### Evidence the JWKS is fetched live over the network

- The signing-key provider is a `jwt.PyJWKClient(get_settings().ESI_SSO_JWKS_URI)` (`api/auth.py:118-125`), i.e. it fetches from `https://login.eveonline.com/oauth/jwks` (`core/config.py:40`).
- `PyJWKClient` fetches the JWKS via **synchronous urllib** on cache miss — the code runs it in `asyncio.to_thread` precisely because it is a blocking network fetch (`api/auth.py:251-257`, comment "the JWKS fetch inside is synchronous urllib").
- Caching: the provider is a process-wide `@functools.lru_cache(maxsize=1)` singleton (`api/auth.py:118`) so its internal **JWKS cache (300 s TTL, kid-keyed)** persists across logins (`api/auth.py:120-124`). Design spec §3.2 (`:53`) and Appendix A (`:237`): the sync fetch "fires on cache miss only (300 s TTL + kid-keyed LRU)."

### Implications for prod

- **The backend needs outbound HTTPS egress to `login.eveonline.com`** (JWKS at cache-miss/startup + the token endpoint on every login + the authorize redirect target). A locked-down egress firewall that blocks `login.eveonline.com` breaks login: JWKS fetch fails → `PyJWKClientError` → `sso=error` redirect (`api/auth.py:258-263`). This is separate from the ESI *data* egress to `esi.evetech.net` (the shared httpx client's `base_url`, `core/http_client.py`).
- **Cold-start / cache-expiry behavior:** the first login after boot (and any login >300 s after the last JWKS fetch, or on a `kid` miss) pays a synchronous JWKS fetch. No JWKS is persisted across restarts — every process restart starts with an empty cache. There is **no pinned/bundled JWKS fallback**; if `login.eveonline.com` is unreachable at that moment, logins fail until it recovers.
- **What IS insulated (per pitfall ESI-1, `docs/pitfalls/implementation-pitfalls.md:199-217`):** Hangar Bay was unaffected by EVE's 24 March 2026 "Spring Cleaning" legacy-route removals because every data route pins explicit versions and SSO validation does not call the removed `/verify` endpoint — it validates locally against JWKS. That insulation is real and orthogonal to the egress requirement above. (Memory note `esi-spring-cleaning-2026` framed this as "offline JWKS"; the accurate reading is "local signature validation, JWKS still fetched live and cached 300 s" — not a network-free JWKS.)
- JWKS URI, token URL, authorize URL are all Settings-overridable (`core/config.py:38-40`), so a prod deployment could point them at an internal mirror/proxy if egress must be brokered — but nothing in the codebase does this today.

---

## 4. The deferred LIVE SSO VERIFICATION thread (what was deferred, what a prod-shaped env must provide)

M2 shipped code-complete but left exactly **one** thread open: a live end-to-end SSO login against real EVE. It is a **manual, hand-driven check — there is NO automated live-SSO test.**

### What was deferred (quoted)

- Design spec §8 (`:203`) and §10/plan: "**Live SSO end-to-end test + live-smoke auth lane** — the EVE app is registered (callback pinned in §1); blocked on **EVE credentials landing in the local `.env`** ... plus **a live verification pass**."
- Handoff `2026-07-17-project-continuation.md:37`: "**Deferred within M2:** the **live-lane SSO login test** (a real EVE SSO round trip) — gated on EVE credentials landing in the local `.env` plus a live end-to-end verification pass."
- Handoff `2026-07-13-m2-phases-5-9-complete-handoff.md:3` and `:34`: "there is **no automated live-SSO test** — `e2e/live-smoke.spec.ts` only exercises anonymous contract browsing" / "**Manual live SSO verification** ... This is a hand-driven check, NOT an automated test."

### What a prod-shaped (or live-dev) environment must provide to run it (quoted, `2026-07-13-m2-phases-5-9-complete-handoff.md:34`)

> Startup requires BOTH servers: the backend on `:8000` ... AND the Vite HTTPS dev server on `https://localhost:5173` ... plus EVE creds (`ESI_CLIENT_ID`/`ESI_CLIENT_SECRET`/`TOKEN_CIPHER_KEYS`) in `app/backend/src/.env`. Then drive a browser through the login → EVE consent → callback → identity-in-header → logout cycle by hand. Then a `dev` → `main` publication PR closes M2.

So the flows to exercise, end to end:
1. **Login** — SPA header button → `/api/v1/auth/sso/login?next=...` → 302 to EVE authorize.
2. **EVE consent** — real EVE account authenticates and consents.
3. **Callback** — EVE 302s back to the registered callback; state-binding check, code exchange, JWT validation, user upsert, session mint, `hb_session` set.
4. **Identity in header** — `/me` returns 200 with character id/name; portrait + name + Logout render.
5. **Logout** — `POST /api/v1/auth/sso/logout` → 204 + cookie cleared → header returns to anonymous.

For a **prod-shaped** run the same three prerequisites generalize: (a) real `ESI_CLIENT_ID`/`ESI_CLIENT_SECRET`/`TOKEN_CIPHER_KEYS` provisioned as secrets; (b) the SPA + API + callback all on one HTTPS public origin (§1); (c) `ESI_SSO_CALLBACK_URL` + `FRONTEND_ORIGIN` pointing at that origin, and the EVE app registration's callback matching it char-for-char (§5). Also required for a real login to persist: a **`users` table that actually exists** in the prod DB — see the §6 hazard, because there is currently no prod schema-creation path.

`.env` handling constraint (recurring across handoffs): **never read or print `app/backend/src/.env`**; Sam hand-places EVE credentials; nothing secret enters chat/commits/PRs (design spec §7 `:198`).

---

## 5. What a PRODUCTION EVE application registration needs (developers.eveonline.com)

Registration portal: `https://developers.eveonline.com/applications` (`.env.example:22`). From the codebase + design spec, a prod EVE app registration must supply:

- **Callback URL** — must equal `ESI_SSO_CALLBACK_URL` char-for-char (`core/config.py:41-42`). For prod that is `https://<public-origin>/api/v1/auth/sso/callback` (the `/api/v1` prefix is part of the registered URL because the *browser* lands on the edge origin before the edge strips it — design spec §4 `:87`). Dev registers `https://localhost:5173/api/v1/auth/sso/callback`.
- **Client ID + Secret** — become `ESI_CLIENT_ID` / `ESI_CLIENT_SECRET`. This is a **confidential client** (secret is used for HTTP Basic on the token endpoint, `services/sso.py:87`), so register as a web/confidential app, not a native/PKCE-only client.
- **Scopes — currently NONE.** The authorize request sends an **empty scope** string: `"scope": ""` (`services/sso.py:51`, comment "no ESI scopes in F004"; also design spec §4.1 step 2 and §2.7). Consequences pinned in the design: zero scopes ⇒ EVE issues **no refresh token** (`esi_refresh_token` stored NULL; design spec §4.1 step 8, §8). Login is identity-only (character id/name/owner_hash from the JWT `sub`/`name`/`owner` claims, `services/sso.py:154-171`).
- **Separate dev vs prod registrations assumed.** Design spec Appendix A (`:247`) records the open question of whether the portal still hard-limits one callback URL per app; the design "assumes separate registrations (safer)." So M4 should plan on a **distinct prod EVE app** (distinct client id/secret + distinct callback) rather than reusing the dev app.
- **Scope expansion is M3, not M4.** ESI scopes + structure-name resolution are explicitly deferred to M3, "gets its own feature spec and **EVE app consent change**" (design spec §8 `:202`). So if M3 lands before/with the prod cutover, the prod app registration will need its scope list updated then; M4's prod registration as-is needs no scopes.

---

## 6. ENVIRONMENT-based behavior differences (cookie Secure flag + the prod schema hazard)

`ENVIRONMENT` is a `Literal["development", "production", "test"]` that **defaults to `"production"`** — secure-by-default (`core/config.py:21`; an omitted var resolves to `"production"`, comment `:15-20`).

### Cookie `Secure` flag is OFF only in development

```python
def _cookie_secure() -> bool:
    return get_settings().ENVIRONMENT != "development"
```
(`api/auth.py:80-81`.) So `Secure` is **present** for `production` AND `test`, **absent** only for `development` (so the dev flow works over the local proxy). Design spec §4.2 (`:113`): "`Secure` when `ENVIRONMENT != "development"`." Applies to both `hb_session` (`api/auth.py:279`) and `hb_sso_state` (`api/auth.py:113`). Prod deployment therefore MUST serve over HTTPS or the browser will drop the `Secure` cookie and login silently no-ops (compounding the §1 origin invariant).

### Other ENVIRONMENT-keyed branches relevant to prod

- **SQL echo** on only in development: `echo=(ENVIRONMENT == "development")` (`db.py`, per config comment `core/config.py:17-18`).
- **SSO-unconfigured startup warning** logs only in development (`main.py:153-156` `warn_if_sso_unconfigured` returns early if `ENVIRONMENT != "development"`). So a prod deploy with empty SSO config logs no warning — the SSO routes just 503 at request time. M4 may want a prod-visible readiness/health signal for this.

### PROD SCHEMA HAZARD — there is no production table-creation path

The **only** schema-creation code in the app runtime is `create_db_tables()` (`main.py:128-150`), and it is **fail-closed gated to development**:

```python
if settings.ENVIRONMENT != "development" or not settings.DB_RECREATE_ON_STARTUP:
    logger.info("Skipping destructive create_db_tables ...")
    return
```
(`main.py:140-145`.) In production this early-returns and creates **nothing**. Per the M3 recon (`docs/audits/m3-recon/backend-data-auth.md` §6) Alembic is vestigial and stale (its `users` migration describes a totally different legacy schema). So **a fresh prod database has no `users` table** — and the very first real SSO login (`auth_service.upsert_user`) would fail at flush/commit. `main.py:130-131` states outright: "production schema management is future migrations work." This is a **hard M4 prerequisite**: auth cannot function in prod until a real migration path (Alembic revival or equivalent) creates the `users` table (and the M3 tables). This is primarily a data/migrations-lane concern but it directly gates whether SSO login works in prod, so it is flagged here.

### Related deferred prod-schema note

Design spec §8 (`:204`): "Real migrations (Alembic revival) for production schema management; M2 only gates the destructive dev path." The FastAPI/Python-3.14 chore prompt (`docs/superpowers/handoffs/2026-07-13-fastapi-python314-chore-prompt.md`) is unrelated to schema but confirms the backend is currently pinned to Python 3.12 with FastAPI held at `<0.116`; whether that migration lands before the prod cutover affects the prod runtime version the deploy must target.

---

## Quick-reference: exact fields/paths for the M4 designer

| Concern | Fact | Location |
|---|---|---|
| Session cookie name | `hb_session`, host-scoped, HttpOnly, SameSite=Lax, Secure≠dev, Path=/, Max-Age 30 d | `api/auth.py:277-280`; `core/config.py:47` |
| Origin invariant | callback host MUST equal SPA/`FRONTEND_ORIGIN` host (host-scoped cookie) | design spec §4 `:89` |
| Callback route (bare) | `/auth/sso/callback` → SPA sees `/api/v1/auth/sso/callback` | `api/auth.py:28,184`; `main.py:193` |
| Redirect_uri to EVE | `ESI_SSO_CALLBACK_URL` (default `https://localhost:5173/api/v1/auth/sso/callback`) | `core/config.py:43`; `api/auth.py:106-108` |
| Post-login redirect base | `FRONTEND_ORIGIN` (default `https://localhost:5173`) | `core/config.py:44`; `api/auth.py:224,271,276` |
| Client creds | `ESI_CLIENT_ID` / `ESI_CLIENT_SECRET` (SecretStr, Basic auth) | `core/config.py:36-37`; `services/sso.py:87` |
| Scopes requested | NONE — `"scope": ""` (zero-scope ⇒ no refresh token) | `services/sso.py:51` |
| Token cipher | `TOKEN_CIPHER_KEYS` — comma-sep Fernet keys, first=primary, MultiFernet rotation | `core/config.py:50`; `core/token_cipher.py:10-26` |
| JWKS | `ESI_SSO_JWKS_URI` fetched live via PyJWKClient, cached 300 s; needs egress to login.eveonline.com | `core/config.py:40`; `api/auth.py:118-125,251-257` |
| Not-configured guard | 503 if `ESI_CLIENT_ID` empty OR cipher unconfigured (login+callback; logout ungated) | `api/auth.py:36-39,285` |
| Cookie Secure gate | `ENVIRONMENT != "development"` → prod & test get Secure | `api/auth.py:80-81` |
| Prod schema gap | `create_db_tables` skips in prod; no live migrations → no `users` table | `main.py:140-145`; design spec §8 `:204` |
| Live verification | manual only; needs real EVE creds in `.env` + both servers; no automated live-SSO test | handoff `2026-07-13-m2-phases-5-9-complete-handoff.md:34` |
| Secret handling | never read/print `.env`; secrets via files/secret-manager, not CLI flags | design spec §7 `:198` |
