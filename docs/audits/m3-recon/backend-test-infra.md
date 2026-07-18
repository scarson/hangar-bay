# M3 Recon — Backend Test Infrastructure (pytest)

ABOUTME: Facts a designer needs to build M3 (F005 Saved Searches, F006 Watchlists, F007 Alerts)
ABOUTME: test coverage — fixtures, the fake Valkey double, the auth-request pattern, TEST-1 house style, and gaps.

Read-only recon. All paths absolute. Backend test root:
`/Users/sam/Code/hangar-bay/.claude/worktrees/drama-pass-implementation-ae2eeb/app/backend/src/fastapi_app/tests/`
(abbreviated below as `tests/`). There is exactly **one** `conftest.py` — `tests/conftest.py`. No top-level/`src/` conftest.

---

## 1. `tests/conftest.py` — fixtures, DB lifecycle, app instance, teardown

**App instance: a module-global real app, mutated in place.** `conftest.py:20` does
`from fastapi_app.main import app as real_app`. Every client fixture uses the ASGI app over
`httpx.ASGITransport` — there is **no** live uvicorn/network server. Both `test_app` and `auth_client`
mutate the SAME global `real_app` (its `.dependency_overrides` and `.state`) and clean up on teardown.

**`DATABASE_URL_TESTS`** (`conftest.py:31-34`): conftest raises `ValueError` at import time if
`settings.DATABASE_URL_TESTS` is unset. `TEST_DATABASE_URL = str(settings.DATABASE_URL_TESTS)`. This is a
**separate real Postgres database** (the dedicated `hangar_bay_test` DB), not SQLite, not the dev DB.
Settings field: `config.py:63` `DATABASE_URL_TESTS: Optional[PostgresDsn] = None`.

### Fixtures (all function-scoped)

- **`db_session`** (`conftest.py:46-82`, `@pytest_asyncio.fixture`): the authoritative isolation pattern.
  Per test it: creates a fresh `create_async_engine(TEST_DATABASE_URL, echo=False)`; `Base.metadata.drop_all`;
  `Base.metadata.create_all`; then `session_maker = async_sessionmaker(engine, expire_on_commit=False)` and
  **`async with session_maker.begin() as session: yield session`** — a single "begin once" transaction that is
  **rolled back** at the end (never committed). Then `drop_all` + `engine.dispose()`.
  **Consequence (documented in test files):** persist rows with `await db_session.flush()`, **NEVER**
  `commit()` — the fixture owns the transaction. `expire_on_commit=False` means ORM objects stay usable after flush.

- **`test_app`** (`conftest.py:87-97`, plain `@pytest.fixture`): takes `db_session`, sets
  `real_app.dependency_overrides[get_db] = lambda: db_session`, yields `real_app`, then
  `real_app.dependency_overrides.clear()`.

- **`client`** (`conftest.py:100-107`, `@pytest_asyncio.fixture`): `ASGITransport(app=test_app)` wrapped in
  `AsyncClient(base_url="http://test")`. **Does NOT set `app.state.redis`** — so any route depending on
  `get_cache` (which reads `request.app.state.redis`) returns **503** under `client`. This is why auth-gated
  routes CANNOT be tested through `client` — use `auth_client` (below).

- **`setup_contracts`** (`conftest.py:114-158`, `@pytest_asyncio.fixture`): inserts 4 diverse `Contract` rows
  (ids 101–104, with `ContractItem`s), `flush`, returns them. Reused by `test_contract_filters.py`.

- **`auth_client`** (`conftest.py:169-194`, `@pytest_asyncio.fixture`): **the fixture M3 auth-gated CRUD tests
  will use.** Depends on `(db_session, httpx_mock)`. It:
  - sets `real_app.state.redis = FakeRedis()` (a fresh fake Valkey — see §2),
  - sets `real_app.state.http_client = httpx.AsyncClient(base_url="http://sso.test")` (intercepted by pytest-httpx),
  - overrides `get_db` → `lambda: db_session` (SAME session the test arranges rows in),
  - yields an `AsyncClient(transport=ASGITransport(real_app), base_url="http://test")`,
  - exposes the fake as **`client.fake_redis`** for state/session assertions,
  - teardown: `aclose()` the http_client, `del real_app.state.redis`, `del real_app.state.http_client`,
    `real_app.dependency_overrides.clear()`.
  - It **does NOT configure SSO settings** (that's `configured_sso`). `/me` and `/me/*` CRUD routes are NOT
    behind the not-configured guard, so CRUD tests generally do **not** need `configured_sso`.

- **`configured_sso`** (`conftest.py:197-205`, plain `@pytest.fixture`, synchronous, uses `monkeypatch`):
  monkeypatches the settings singleton — `ESI_CLIENT_ID="test-client"`, `ESI_CLIENT_SECRET=SecretStr("test-secret")`,
  `TOKEN_CIPHER_KEYS=SecretStr(Fernet.generate_key().decode())`. Needed only for SSO login/callback happy paths.

- **`httpx_mock`** / **`vcr`**: provided automatically by `pytest-httpx` / `pytest-vcr` plugins (see §4).

**pytest config** (`app/backend/pyproject.toml`): `asyncio_mode = "strict"` (every async test needs
`@pytest.mark.asyncio` or a file-level `pytestmark`); `testpaths = ["src/fastapi_app/tests"]`;
`pythonpath = ["src"]`; one custom marker `esi_live`. Async fixtures use `@pytest_asyncio.fixture`.
Dev deps include `pytest-asyncio`, `pytest-mock`, `pytest-httpx>=0.32`, `pytest-vcr`.

---

## 2. The fake Valkey double — `FakeRedis`

- **Class:** `FakeRedis`, file `tests/fake_redis.py`. Async, in-memory, `decode_responses=True` (values are `str`).
- **Commands modeled** (all `async`): `get(key)`, `set(key, value, ex=None, nx=False)`, `getex(key, ex=None)`,
  `getdel(key)`, `expire(key, ttl)`, `expireat(key, when)`, `delete(*keys)`, `exists(key)`. Plus a **test-only**
  synchronous introspector `ttl_for(key)` returning the last-applied relative TTL.
- **Real TTL semantics:** an injectable clock — `FakeRedis(clock=lambda: epoch_seconds)`, defaults to `time.time`.
  Keys past their absolute expiry read as absent (lazily purged on access via `_purge_if_expired`). `set` without
  `ex` clears any TTL (persistent); `expire`/`expireat` with a past deadline delete. `nx=True` on `set` is honored.
- **NOT modeled:** `eval`/Lua scripting, `hset`/`hgetall`, `incr`, pub/sub, pipelines, `scan`, sorted sets. Only the
  string+TTL surface the session store and SSO-state store need. **The aggregation concurrency lock uses a SEPARATE
  double** — `_FakeLockRedis` in `tests/services/test_background_aggregation.py:275-295`, which models
  `set(nx,ex)` / `eval(CAD script)` / `close()`. If an M3 watchlist-matcher job needs a Redis lock, it will need
  the `_FakeLockRedis` pattern (or FakeRedis extended with `eval`), NOT the session `FakeRedis`.
- **How it's injected:** via **`app.state.redis`** — `auth_client` sets `real_app.state.redis = FakeRedis()`.
  The production seam is `get_cache` (`core/dependencies.py:11-22`), which reads `getattr(request.app.state, "redis", None)`
  and 503s if absent. Session helpers receive the Redis client through FastAPI DI (`Depends(get_cache)`), so setting
  `app.state.redis` is sufficient; tests also reach the same instance via `auth_client.fake_redis`.
- **Directly-constructed use** (unit tests): `tests/core/test_session.py` and `tests/test_fake_redis.py` build
  `FakeRedis(...)` directly with injected `_Clock` objects and call `sess.*` against it — no app involved.

---

## 3. Minting an AUTHENTICATED request (the canonical pattern)

Auth tests do **not** override `get_current_session`. They mint a real server-side session into the fake Valkey and
set the session cookie, exercising the real `get_current_session → read_session → FakeRedis` path end-to-end.

**Exact helper + pattern** (from `tests/api/test_auth_flow.py:472-477`, `:456-461`, `:506-510`, `:520-524`):

```python
from fastapi_app.core import session as sess
from fastapi_app.core.config import settings

sid = await sess.create_session(
    auth_client.fake_redis, user_id=1, character_id=91000001, character_name="Sesta Hound"
)
auth_client.cookies.set(settings.SESSION_COOKIE_NAME, sid)   # cookie name == "hb_session"
resp = await auth_client.get("/me")   # -> 200, get_current_session served it
```

- **`create_session` signature** (`core/session.py:49-67`):
  `async def create_session(redis, *, user_id: int, character_id: int, character_name: str, now: Optional[int]=None) -> str`.
  It mints `sid = secrets.token_urlsafe(32)` and writes `session:{sid}` with `ex=SESSION_IDLE_TTL_SECONDS`.
- **Stored session payload JSON shape** (`core/session.py:60-65`) — the exact document written to Valkey:
  ```json
  {"user_id": <int>, "character_id": <int>, "character_name": "<str>", "created_at": <int epoch seconds UTC>}
  ```
- **`get_current_session`** (`core/session.py:116-123`): reads cookie `settings.SESSION_COOKIE_NAME`, calls
  `read_session`, **returns the full payload dict** (all four keys), raises `HTTPException(401, "Not authenticated")`
  on missing cookie or `None` payload. `get_optional_session` (`:126-131`) returns `None` instead of 401.
  **M3 `/me/*` routes will `Depends(get_current_session)` and read `session["user_id"]`** (the FK to `users.id`)
  and/or `session["character_id"]`. Both are present in the payload — no DB read needed to identify the caller.
- `/me` itself (`api/auth.py:296-300`) is on a **separate bare router `me_router`** (`api/auth.py:29`,
  mounted at `main.py:194`), and serves purely from the session payload (no DB). M3 CRUD routes will likely hang
  off a new bare router (or `me_router`) with prefix like `/me/saved-searches` — see §5 for PROXY-1 discipline.

**CRITICAL GAP for FK'd tables (see §6):** `create_session(user_id=1, ...)` writes a session whose `user_id` is a
**bare integer with no matching `users` row**. Every existing auth test uses `user_id=1` with no real user. For M3
tables that FK to `users.id`, a test must FIRST insert a real `User` via `db_session`, `flush()` to populate `.id`,
then mint the session with `user_id=user.id`. No fixture does this today.

**Alternative (not used in this codebase):** overriding `real_app.dependency_overrides[get_current_session] = ...`
is possible but nowhere used — the house style is the real-session-in-FakeRedis approach above, which is more faithful.

---

## 4. pytest-httpx usage — token POST mocks + JWKS seam

- **Outbound HTTP mocking:** the `httpx_mock` fixture (pytest-httpx). Token-endpoint POSTs are mocked with:
  - `httpx_mock.add_response(url=TOKEN_URL, json={"access_token": at, "expires_in": 1200, "token_type": "Bearer"})`
    (`test_auth_flow.py:103`),
  - error shapes: `httpx_mock.add_response(url=TOKEN_URL, status_code=400, json={"error": "invalid_grant"})`
    (`test_auth_flow.py:171`),
  - transport failures: `httpx_mock.add_exception(httpx.ConnectError("..."), url=...)`
    (`test_auth_service.py:136`).
  `TOKEN_URL = settings.ESI_SSO_TOKEN_URL` (`test_auth_flow.py:18`).
- **Structural dependency (TEST-10):** `auth_client` requires `httpx_mock` *structurally* — pytest-httpx patches
  httpx's async transport class, so `app.state.http_client` can never reach the real network in ANY auth test; an
  un-mocked token POST fails loudly. The outer `ASGITransport` client is a different transport class and is
  unaffected. A CRUD test that makes no outbound HTTP registers no responses and none are required.
- **JWKS injectable seam** (`test_auth_flow.py:38-42`):
  ```python
  def _inject_jwks(monkeypatch, pub):
      from fastapi_app.api import auth as auth_api
      monkeypatch.setattr(auth_api, "_signing_key_provider", lambda: SimpleNamespace(
          get_signing_key_from_jwt=lambda token: SimpleNamespace(key=pub)))
  ```
  The real `_signing_key_provider` (`api/auth.py:118-125`) is a `@functools.lru_cache(maxsize=1)` `PyJWKClient`.
  Tests shadow the module attribute; a test that changes `ESI_SSO_JWKS_URI` must call
  `_signing_key_provider.cache_clear()`.
- **Access-token minting** (`test_auth_flow.py:21-35`): a module-scoped `rsa_keypair` fixture
  (`rsa.generate_private_key(public_exponent=65537, key_size=2048)`), and `_sign_access_token(priv, **overrides)`
  → `jwt.encode(claims, priv, algorithm="RS256", headers={"kid": "JWT-Signature-Key"})`.
  (M3 CRUD tests likely need none of this JWT machinery — it's login/callback-only.)

---

## 5. TEST-1 house style

- **HTTP-level tests** through the `client` (or `auth_client`) fixture against the real ASGI app: send real query
  params / bodies through the test client. Examples: `await client.get("/contracts/?region_ids=10000020")`
  (`test_contract_filters.py:102`), `await client.get("/contracts/", params={...})`. A filter that works at the
  service layer but is unreachable over HTTP is the exact bug TEST-1 guards against (see §7).
- **Schema assertions via `app.openapi()`** — done as plain (often non-async) test functions importing the app
  directly:
  - `test_contract_filters.py:180-189` — `schema["paths"]["/contracts/"]["get"]`; assert `"requestBody" not in
    operation`; check `{p["name"] for p in operation["parameters"]}`.
  - `test_me_schema.py` (whole file) — asserts `/me`, `/auth/sso/*` present; **PROXY-1 sentinel**
    `assert not any(p.startswith("/api/v1") for p in schema["paths"])` (line 13); declared 302 responses
    (lines 16-25); and the `/me` 200 response `$ref` resolved into `schema["components"]["schemas"][name]["properties"]`
    with exact `{character_id: integer, character_name: string}` (lines 28-33). **M3 CRUD routes should get an
    analogous schema test: bare-mounted (no `/api/v1`), request/response body shapes present.**
- **Arranging DB rows in tests:** directly via `db_session.add(...)` / `add_all([...])` then `await
  db_session.flush()` — either inline in the test (e.g. `test_contracts.py:72-79`) or through a fixture
  (`setup_contracts`). Models imported from `fastapi_app.models`. Because `auth_client`'s `get_db` override and the
  test's `db_session` are the SAME begin()-wrapped session, rows flushed by the test are visible to the route
  handler within the same transaction (this is how `test_callback_happy_path` asserts on a user the route created).
- **Service-layer tests** (e.g. `test_background_aggregation.py`) call service methods directly with a real
  `db_session` and `MagicMock`/`AsyncMock` collaborators — see §6 for the matcher-job shape.
- **Markers:** files set `pytestmark = pytest.mark.asyncio` (or a list, e.g. `[pytest.mark.vcr,
  pytest.mark.esi_live, pytest.mark.asyncio]` in `test_contracts.py:38-42`).

---

## 6. What a new `/me/saved-searches` CRUD test module needs

### Fixtures/helpers it REUSES as-is
- **`auth_client`** — the one-stop fixture: real app, `app.state.redis = FakeRedis()`, `get_db → db_session`,
  exposes `.fake_redis`, and (via the structural `httpx_mock`) is hermetic. Use this, **not `client`** (which has no
  `app.state.redis`, so `get_current_session`/`get_cache` would 503).
- **`db_session`** — to insert the `User` row and to assert on `saved_searches` rows the route writes. Persist with
  `flush()`, never `commit()`.
- **`sess.create_session(...)` + `auth_client.cookies.set(settings.SESSION_COOKIE_NAME, sid)`** — to mint the
  authenticated request (§3).
- **`app.openapi()` schema assertions** — mirror `test_me_schema.py`: assert the new CRUD paths are bare (PROXY-1)
  and carry the right request/response schema `$ref`s.
- Standard imports: `from fastapi_app.models import User` (+ the new saved-search model once added), `from
  fastapi_app.core import session as sess`, `from fastapi_app.core.config import settings`, `from sqlalchemy import
  select`.

### GAPS the designer must close
1. **No user-row factory exists.** Every `User` insertion in the suite is ad-hoc: `test_user_model.py:34`,
   `test_auth_service.py` (via `auth_service.upsert_user`), and a closure in `test_auth_flow.py:348-351`. There is
   no fixture that (a) inserts a real `User`, (b) flushes to get `.id`, (c) mints a session with `user_id=user.id`,
   (d) sets the cookie. Because saved-searches/watchlists/alerts FK to `users.id`, this factory is a **prerequisite**
   — the existing `create_session(user_id=1, ...)` pattern writes a session whose `user_id` has no matching row and
   would violate an FK on insert. Recommend adding a fixture, e.g. returning `(user, authed_client)`:
   ```python
   @pytest_asyncio.fixture
   async def authed_user(auth_client, db_session):
       user = User(character_id=91000001, character_name="Sesta Hound", owner_hash="OWN1")
       db_session.add(user); await db_session.flush()             # populates user.id
       sid = await sess.create_session(auth_client.fake_redis,
             user_id=user.id, character_id=user.character_id, character_name=user.character_name)
       auth_client.cookies.set(settings.SESSION_COOKIE_NAME, sid)
       return user, auth_client
   ```
   (`User` requires non-null `character_name` and `owner_hash`; token/`esi_*` columns are all nullable —
   `models/user.py:12-29`.)
2. **New models must be import-reachable so `Base.metadata.create_all` builds their tables.** `db_session` calls
   `Base.metadata.create_all` (`conftest.py:69`). Tables only exist if the model class was imported by then. The
   aggregation point is **`fastapi_app/models/__init__.py`** (currently exports `User, Contract, ContractItem,
   EsiMarketGroupCache`) — it's executed whenever `fastapi_app.models(.anything)` is imported, and `real_app`'s
   import chain pulls it in. **Add each new M3 model to `models/__init__.py`** or its table silently won't be
   created in tests (and the schema-recreate on dev startup would miss it too).
3. **Auth-negative coverage is on the caller.** M3 CRUD routes must have tests for the 401 path (no cookie / stale
   cookie / corrupt payload) and cross-user isolation (user A cannot read/mutate user B's rows). The mechanisms
   exist (`test_auth_flow.py:466-468` for anonymous 401; `test_session.py:122-132, 205-224` for stale/corrupt), but
   cross-user isolation is a NEW scenario with no precedent — the designer must specify it. The session payload
   gives `user_id`; every query must be scoped by it.
4. **`FakeRedis` covers only the session command surface.** F007 alerts / F006 matcher, if they touch Redis beyond
   string+TTL (locks via `eval`, counters via `incr`, hashes), will need `_FakeLockRedis`-style extensions — the
   session `FakeRedis` lacks `eval`/Lua (§2).

### The periodic watchlist-vs-contracts matcher job (F006) — test shape
Model it on the aggregation service tests, NOT on APScheduler:
- Tests instantiate the service with mocked collaborators and call the **inner method** directly with a real
  `db_session`: `test_background_aggregation.py:27-35` builds `ContractAggregationService(esi_client=MagicMock(...),
  settings=MagicMock())`, then `await service._process_contracts(db_session, [...])` and asserts on rows via
  `select(...)`. Do the same for a `WatchlistMatcher.run(db_session)` — arrange `User` + watchlist + `Contract`
  rows, run the matcher, assert alert rows were created / not duplicated.
- The APScheduler wiring itself (`core/scheduler.py` `add_aggregation_job`, `services/scheduled_jobs.py`
  `run_aggregation_job`) is **thin and not exercised through a running scheduler** in tests — the top-level job fn
  just try/except-wraps the service call. A new matcher job would add a parallel `add_*_job` +
  `run_*_job`; unit-test the service method, not the scheduler.
- **Concurrency/idempotency:** if the matcher needs single-run protection, follow the aggregation lock:
  `service._concurrency_lock()` async-CM tested via `patch.object(bg_agg.aioredis, "from_url",
  return_value=_FakeLockRedis(store))` (`test_background_aggregation.py:298-321`). Re-run idempotency (an alert
  fired once must not re-fire on the next matcher pass over the same contract) is the F006/F007 analog of the
  "304'd re-ingestion keeps the flag" regression (`:209-238`).

---

## 7. Testing-pitfalls (`docs/pitfalls/testing-pitfalls.md`) — TEST-* entries relevant to M3

M3 = auth-gated per-user CRUD (F005/F006) + a periodic matcher job (F006) + frontend lists/forms/polling (F007).
Full file has §1–8 universal disciplines plus 10 project-specific `TEST-N` entries. Those bearing on M3:

**Backend CRUD + matcher job:**
- **TEST-1 — service-layer-only tests miss HTTP binding bugs.** Every API-facing filter/field gets an HTTP-level
  test through the client AND an `app.openapi()` schema assertion that the param/body appears where clients expect.
  Directly constructing a Pydantic model in Python bypasses FastAPI request binding. Applies to every M3 CRUD
  request body and query param. (Pairs with FASTAPI-1 in implementation-pitfalls.)
- **TEST-10 — `ASGITransport` does not run lifespan; wire `app.state` by hand.** The reason `auth_client` sets
  `app.state.redis`/`app.state.http_client` manually. Any M3 fixture that needs another app-state singleton must set
  it manually too; the `client` fixture has NO `app.state.redis` (so it can't serve auth-gated routes).
- **TEST-2 — never weaken assertions to fix flakes.** Fix races with deterministic sync/fixtures, prefer mechanism
  assertions (observe state) over symptom assertions (timing). Governs the matcher-job and polling tests.
- **TEST-3 — ordering assertions need deterministic fixtures with tiebreakers.** Any M3 list endpoint that returns
  ordered rows (saved searches, watchlist entries, alerts) needs strictly-ordered sort keys or a documented
  tiebreaker in the fixture (the contract suite uses distinct prices / `contract_id` tiebreak).
- **TEST-4 — pagination tests must cross page boundaries.** If any M3 list is paginated, build ≥2 pages of fixtures
  and assert union==full set, empty intersection, each non-final page is exactly `size`, `total` matches. (Pairs
  with SQLA-1: joined-row pagination.)
- **§3 Error Path Coverage / §5 Concurrency & TOCTOU (universal):** each error branch triggered and its message
  asserted; anti-enumeration (same status whether or not another user's row exists); "use once" and first-time
  races tested with two concurrent callers (directly relevant to alert de-duplication and a watchlist-matcher lock);
  idempotency under retry must not 500 on a constraint violation.
- **§7 Test Infrastructure Hygiene:** no shared mutable state (each `auth_client`/`db_session` is function-scoped
  and cleared/rolled back); injected clocks for time-sensitive logic (the `FakeRedis(clock=...)` pattern already in
  `test_session.py` — reuse for any alert TTL / freshness logic); no network in unit tests (pytest-httpx keeps auth
  tests hermetic).

**Frontend lists/forms/polling (F007) — for the frontend recon, noted here for completeness:**
- **TEST-5 — stub the network at the fetch seam** (`vi.stubGlobal`/openapi-fetch injectable `fetch`), assert both
  rendered outcome AND request URL; don't mock the hook itself.
- **TEST-7 — error-state tests must exhaust the QueryClient retry** (retry: 1 → fail calls 0 AND 1, then let Retry
  succeed). Critical for F007 polling error states.
- **TEST-9 — every fixture-lane E2E spec must intercept `GET /me`** (auth header issues a real `/me`); a logged-in
  M3 view means specs must stub `/me` with an authenticated identity, not just the 401 default.
- **TEST-6 — Vitest's glob swallows Playwright specs** (`*.spec.ts` under `e2e/`, `*.test.tsx` for unit); **TEST-8 —
  two `role="status"` nodes during list loading** (synchronize on skeleton unmount) — both bite any new M3 list view.

---

## Key file references (absolute)

- `.../app/backend/src/fastapi_app/tests/conftest.py` — all fixtures (§1)
- `.../app/backend/src/fastapi_app/tests/fake_redis.py` — `FakeRedis` (§2)
- `.../app/backend/src/fastapi_app/core/session.py` — `create_session`, `read_session`, `get_current_session`,
  `get_optional_session`, session payload shape (§3)
- `.../app/backend/src/fastapi_app/core/dependencies.py` — `get_cache` (503-when-absent seam)
- `.../app/backend/src/fastapi_app/api/auth.py` — `router` (`/auth/sso/*`), `me_router` (`/me`), route patterns
- `.../app/backend/src/fastapi_app/models/user.py` + `models/__init__.py` — `User` model + registration point
- `.../app/backend/src/fastapi_app/tests/api/test_auth_flow.py` — the authenticated-request pattern (§3), pytest-httpx + JWKS seam (§4)
- `.../app/backend/src/fastapi_app/tests/api/test_me_schema.py` — `app.openapi()` / PROXY-1 schema assertions (§5)
- `.../app/backend/src/fastapi_app/tests/api/test_contract_filters.py`, `test_contracts.py` — TEST-1 HTTP + row-arrangement house style (§5)
- `.../app/backend/src/fastapi_app/tests/services/test_background_aggregation.py` — service-method + lock double patterns for the matcher job (§6)
- `.../app/backend/src/fastapi_app/tests/services/test_auth_service.py` — `upsert_user` / user-row creation via the service
- `.../app/backend/pyproject.toml` — `asyncio_mode="strict"`, plugins, markers
- `.../docs/pitfalls/testing-pitfalls.md` — TEST-1..10 (§7)
