# M3 Recon — Backend Data Model + Auth Plumbing

ABOUTME: Read-only recon of Hangar Bay's backend data model + auth plumbing for the M3 designer (F005 Saved Searches, F006 Watchlists, F007 Alerts).
ABOUTME: Facts only — exact columns, signatures, dependency wiring, and the missing-user-row hazard. No code was modified.

Scope: `app/backend/src/fastapi_app/`. All paths below are relative to
`/Users/sam/Code/hangar-bay/.claude/worktrees/drama-pass-implementation-ae2eeb/`.
Design specs for the M3 features live at `design/features/F005-Saved-Searches.md`,
`design/features/F006-Watchlists.md`, `design/features/F007-Alerts-Notifications.md`.

---

## 1. Models

### Base class

- `Base = declarative_base()` is defined in **`app/backend/src/fastapi_app/db.py:8`**.
  Every model imports it as `from ..db import Base`. This is the classic
  `declarative_base()` (not the 2.0 `DeclarativeBase` subclass), but models use the
  2.0 typed `Mapped[...]` / `mapped_column(...)` style on top of it.
- `Base.metadata` is the single registry that `create_db_tables()` (dev startup) and the
  pytest `db_session` fixture both use via `create_all`/`drop_all`. **A new M3 table exists
  for schema-creation purposes iff its model module is imported so the class body runs and
  registers on `Base.metadata`.**

### Model registration — `models/__init__.py`

Full file (`app/backend/src/fastapi_app/models/__init__.py`):

```python
from .user import User
from .contracts import Contract, ContractItem, EsiMarketGroupCache

__all__ = ["User", "Contract", "ContractItem", "EsiMarketGroupCache"]
```

So new M3 models (e.g. `SavedSearch`, `Watchlist`, `WatchlistMatch`/alert rows) should be
added as new modules under `models/` and re-exported here. **Import-for-registration matters:**
`main.py:27` has an explicit `from .models import contracts  # This import is crucial for
Base.metadata to find the tables.` and the pytest `conftest.py:26` explicitly imports
`Contract, ContractItem`. A new M3 model module MUST be reachable in the import graph at table-create
time (add it to `models/__init__.py` AND make sure `main.py` / any create_all path imports the package)
or `create_all` silently omits the table.

### `User` — `models/user.py` (the FK target for all M3 per-user tables)

`__tablename__ = "users"`. Columns (line numbers in `models/user.py`):

| Column | Type | Constraints | Line |
|---|---|---|---|
| `id` | `Integer` (inferred from `Mapped[int]`, autoincrement PK) | `primary_key=True, autoincrement=True` | 15 |
| `character_id` | `BigInteger` | `unique=True, index=True, nullable=False` | 16 |
| `character_name` | `String(255)` | `nullable=False` | 17 |
| `owner_hash` | `String(255)` | `index=True, nullable=False` | 18 |
| `esi_access_token` | `Text` | nullable (Fernet ciphertext) | 19 |
| `esi_access_token_expires_at` | `DateTime(timezone=True)` | nullable | 20 |
| `esi_refresh_token` | `Text` | nullable (Fernet ciphertext) | 21 |
| `esi_scopes` | `Text` | nullable — comment: "empty in F004; F005+ fills" | 22 |
| `last_login_at` | `DateTime(timezone=True)` | nullable | 23 |
| `created_at` | `DateTime(timezone=True)` | `server_default=func.now(), nullable=False` | 24-26 |
| `updated_at` | `DateTime(timezone=True)` | `server_default=func.now(), onupdate=func.now(), nullable=False` | 27-29 |

**Critical for M3 FK design:** the primary key is **`users.id` — an `Integer` (32-bit)
autoincrement surrogate**, NOT `character_id`. The session payload carries this `id` as
`user_id` (see §2/§5). So per-user M3 tables should declare
`user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), ...)`.
`character_id` is `BigInteger` and is the natural EVE key (unique), but it is not the PK.
Note the `esi_scopes` comment already anticipates F005+ needing scopes.

### `Contract` — `models/contracts.py:37` (what the F006 matcher scans)

`__tablename__ = 'contracts'`. Key columns for a watchlist-vs-contracts matcher:

- `contract_id` — `BigInteger`, `primary_key=True, autoincrement=False` (line 40). This is the
  natural ESI id; a watchlist "match" row would reference this.
- `title` (String, nullable, indexed `ix_contracts_title`), `price` (Numeric), `collateral`
  (Numeric), `status` (String), `type` (String), `issuer_id`/`issuer_corporation_id` (Integer),
  `start_location_id` (BigInteger), `start_location_system_id`/`start_location_region_id` (Integer),
  `end_location_id` (BigInteger nullable), `for_corporation` (Boolean), `date_issued`/`date_expired`
  (`DateTime(tz)`), `date_completed` (nullable), `reward`/`volume` (Float nullable).
- Denormalized search fields (lines 60-66): `start_location_name`, `issuer_name`,
  `issuer_corporation_name` (String nullable), `is_ship_contract` (Boolean default False),
  `item_processing_status` (String default `'PENDING_ITEMS'`, indexed), `items_last_fetched_at`,
  `contract_esi_etag`.
- Relationship: `items: Mapped[List["ContractItem"]] = relationship(back_populates="contract",
  cascade="all, delete-orphan")` (line 68).
- Existing indexes (lines 70-80): composite `ix_contracts_type_status`, plus singles on
  `start_location_name`, `title`, `is_ship_contract`, `price`, `date_issued`, `collateral`,
  `volume`. **These are exactly the fields the F005/F006 filter model (`ContractFilters`) already
  filters on** — the matcher can reuse the same query surface.

### `ContractItem` — `models/contracts.py:86`

`__tablename__ = 'contract_items'`. `record_id` BigInteger autoincrement PK; `contract_id`
BigInteger `ForeignKey('contracts.contract_id')` nullable=False; `type_id`, `quantity` Integer;
`is_included`/`is_singleton` Boolean; `is_blueprint_copy` (nullable Boolean), `raw_quantity` (nullable
Integer); denormalized `type_name`, `category`, `market_group_id`. Indexes on `contract_id`,
`type_id`, `is_blueprint_copy`, `raw_quantity`.

### `EsiMarketGroupCache` — `models/contracts.py:21`

`market_group_id` Integer PK; `name`/`description` String; self-referential
`parent_group_id` FK to `esi_market_group_cache.market_group_id`; `raw_esi_response` JSON.

**Existing FK pattern to copy (M3 relevance):** `ContractItem.contract_id` uses the string form
`ForeignKey('contracts.contract_id')` with a `relationship(back_populates=...)` and, on the parent
side, `cascade="all, delete-orphan"`. This is the template for M3 `user_id`/`saved_search_id`
foreign keys and cascades.

---

## 2. `core/session.py` — session dependencies + mechanics

File: `app/backend/src/fastapi_app/core/session.py`. Sessions are **server-side, stored in Valkey
(Redis)** under key `session:{sid}`; the cookie holds only the opaque `sid`
(`secrets.token_urlsafe(32)`, 256-bit, minted post-auth).

### Session payload shape

`create_session` (lines 49-67) writes this JSON dict:

```python
payload = {
    "user_id": user_id,            # int — the users.id surrogate PK (see §5)
    "character_id": character_id,  # int — EVE BigInteger character id
    "character_name": character_name,  # str
    "created_at": now,             # int Unix epoch seconds (UTC)
}
```

`_parse_session_payload` (lines 25-46) shape-validates on read: requires `created_at`, `user_id`,
`character_id` to be **plain ints** (bool rejected — `_is_plain_int`, lines 19-22) and
`character_name` to be a `str`; anything else → treated as absent (key DELeted, `None` returned).
**So the payload always carries `user_id` — an M3 route can read `session["user_id"]` directly
without a DB round-trip to identify the row owner.**

### The two FastAPI dependencies (exact signatures)

```python
async def get_current_session(request: Request, redis: Redis = Depends(get_cache)) -> dict:   # line 116
async def get_optional_session(request: Request, redis: Redis = Depends(get_cache)) -> Optional[dict]:  # line 126
```

- **`get_current_session`** (lines 116-123): reads cookie `SESSION_COOKIE_NAME` (default
  `"hb_session"`); if no cookie → `HTTPException(401, "Not authenticated")`; calls `read_session`;
  if `None` → `HTTPException(401, "Not authenticated")`; else returns the payload `dict`.
  **This is the auth gate for all M3 `/me/*` routes.**
- **`get_optional_session`** (lines 126-130): same source, returns `None` instead of raising when
  cookie missing or session invalid. Use for routes that render differently for anon vs. logged-in.
- **503 behavior:** neither dep raises 503 itself. The 503 comes from the injected `get_cache`
  dependency (`core/dependencies.py:11-22`) when `app.state.redis` is absent — i.e. if Valkey is
  down, the session dep chain surfaces `HTTPException(503, "Redis client is not available.")`.
  A dedicated wiring test asserts the seam is literally `get_cache` (test_session.py:135-153).

### Idle renewal + absolute cap mechanics (`read_session`, lines 70-109)

- **Idle (sliding) TTL:** `SESSION_IDLE_TTL_SECONDS = 604_800` (7 days, `config.py:48`). The read
  uses `redis.getex(key, ex=IDLE)` — atomic read + idle renew.
- **Absolute cap:** `SESSION_ABSOLUTE_TTL_SECONDS = 2_592_000` (30 days, `config.py:49`).
  `deadline = payload["created_at"] + ABSOLUTE`; if `now >= deadline` → `redis.delete(key)` and
  return `None`. Boundary is inclusive (`>=`): a session at exactly `created_at + 30d` is expired.
- **Post-read scheduling:** always applies `redis.expireat(key, min(now + IDLE, deadline))` — an
  absolute EXPIREAT, deliberately immune to command latency (extensive comment lines 89-107 and
  tests test_session.py:227-286). `now` is captured **after** the GETEX round-trip.
- **Accepted, documented tradeoff (lines 98-107):** GETEX + EXPIREAT are two commands, not atomic.
  Two bounded non-security edges remain (a crash between them can leave a key alive up to idle_ttl
  past deadline; concurrent reads can nudge idle expiry a few seconds). **Neither ever serves an
  over-cap session** because the `now >= deadline` check keyed on `created_at` is authoritative.
  The comment explicitly defers a Lua/EVAL atomic capped-renew **to M3 as a session-store
  enhancement** ("out of scope for M2"). This is an optional M3 improvement, not a blocker.

Other functions: `create_session` (49), `read_session` (70), `destroy_session` (112,
`redis.delete`), `_session_key` (15, `f"session:{sid}"`).

---

## 3. How routers obtain a DB session + combine with auth

### DB session dependency

- **`get_db`** in `app/backend/src/fastapi_app/db.py:30-43` — async generator dependency.
  Yields an `AsyncSession` from `AsyncSessionLocal`, **commits on clean exit, rolls back on
  exception, closes in `finally`**. Import as `from ..db import get_db`.
- Session factory: `AsyncSessionLocal = async_sessionmaker(bind=async_engine, class_=AsyncSession,
  expire_on_commit=False, autoflush=False)` (`db.py:17-22`).
- There is also `get_db_session_factory` (`db.py:25-27`) returning the factory itself — used by
  background jobs that need to open their own sessions outside a request (relevant for the F006
  matcher job, which runs under APScheduler, not a request). See §note below.

### Current usage patterns

- **DB-only routes:** `api/contracts.py` — both routes use `db: AsyncSession = Depends(get_db)`
  (lines 30, 44). GET filter model uses `filters: Annotated[ContractFilters, Query()]`
  (line 29) — the FASTAPI-1 pattern; **M3 `/me/searches` list/create endpoints that accept filter
  criteria must follow the same `Annotated[..., Query()]` rule, never bare `Depends(Model)`.**
- **Session-only route:** `api/auth.py:296-300` — `/me`:
  ```python
  @me_router.get("/me", response_model=CurrentUserSchema)
  async def me(session: dict = Depends(get_current_session)):
      return CurrentUserSchema(character_id=session["character_id"], character_name=session["character_name"])
  ```
  It reads **only the session payload, no DB** (comment: "no DB read — §4.2").
- **DB + cache + http in one route:** `api/auth.py` `callback` (lines 200-208) combines
  `redis=Depends(get_cache)`, `http_client=Depends(get_http_client)`, `db: AsyncSession =
  Depends(get_db)` — proof the combination composes cleanly.

### The combination an M3 `/me/*` route needs (does NOT exist yet)

**No route today combines `get_current_session` + `get_db`.** The M3 pattern to introduce:

```python
@router.get("/me/searches")
async def list_my_searches(
    session: dict = Depends(get_current_session),   # 401s if unauthenticated
    db: AsyncSession = Depends(get_db),
):
    user_id = session["user_id"]
    ...  # query WHERE saved_searches.user_id == user_id
```

`get_current_session` gates access (401 on no session); `session["user_id"]` scopes the query;
`get_db` supplies the session. This is a new composition but every piece already exists and is
tested independently.

**Router mounting reminder (PROXY-1):** routers mount **bare** — `contracts` router is
`APIRouter(prefix="/contracts")`, auth is `APIRouter(prefix="/auth/sso")`, and `me_router =
APIRouter()` mounts `/me` bare (`api/auth.py:28-29`). All three are `app.include_router(...)`
in `main.py:192-194` with **no `/api/v1`** prefix — that prefix is owned by the Vite proxy/edge.
M3 routers follow the same rule. A new `me_router.get("/me/searches")` would surface to the SPA at
`/api/v1/me/searches`.

---

## 4. `services/auth_service.py` — upsert shape + the TODO(M3) comments (quoted)

File: `app/backend/src/fastapi_app/services/auth_service.py`.

### `upsert_user(db, identity, tokens) -> User` (lines 16-49)

Signature: `async def upsert_user(db: AsyncSession, identity: VerifiedIdentity, tokens: dict) -> User`.
Behavior: `select(User).where(User.character_id == identity.character_id)` →
`scalar_one_or_none()`; if `None`, constructs `User(character_id=identity.character_id)` and
`db.add(user)`; then unconditionally sets `character_name`, `owner_hash` (owner-hash transfer:
data follows the character on mismatch), encrypts `esi_access_token`, stores `esi_refresh_token`
(NULL when no refresh token — zero-scope logins), `esi_access_token_expires_at`, `last_login_at`;
`await db.flush()`; returns `user`. **The row's `id` is assigned by the flush** and is what
`_finalize_login` then passes to `create_session` as `user_id`.

### TODO(M3) — first-login upsert race (lines 21-25, quoted verbatim)

> ```
> # A future optimization
> # (TODO(M3): catch IntegrityError + re-select, or INSERT ... ON CONFLICT)
> # could make the loser succeed transparently instead of retrying, but the
> # graceful-retry behavior is already correct for M2.
> ```

Context (lines 16-20): two simultaneous first logins for the same `character_id` can both see
`user is None` and both insert; the loser's flush raises `IntegrityError` (`character_id` unique).
Today this is handled at the callable boundary — `_finalize_login` (`api/auth.py:161-181`) catches
any exception, `await db.rollback()`, returns `None`, and the callback redirects `sso=error` so the
user retries. Correct but not transparent.

### TODO(M3) — `refresh_user_tokens` 400 discrimination + concurrency (lines 88-94, quoted verbatim)

> ```
> # TODO(M3): not every 400 here is actually invalid_grant (EVE can 400 for
> # other request-shape reasons too) — this should discriminate on the
> # response body's error field, not status_code alone. Also: concurrent
> # callers refreshing the same user's tokens can race on this read-modify-
> # write (no row lock / optimistic version check); needs a concurrency-safe
> # rotation strategy. Deferred: no M2 endpoint calls refresh_user_tokens —
> # it's M3 foundation only.
> ```

`refresh_user_tokens(db, http_client, user)` (lines 61-105) is the **M3 foundation for actually
using stored ESI tokens** (e.g. if F005+ needs authenticated ESI calls). Currently **no endpoint
calls it.** It refreshes via `sso.refresh_token_pair`, persists rotated refresh token when returned
(§2.7 rotation optional), and on invalid-grant-shaped 400 OR undecryptable vault (wrong keyring,
`InvalidToken`) calls `mark_for_reauth`. On 5xx/transport it re-raises and keeps the vault.

### `mark_for_reauth(db, user)` (lines 52-58, quoted TODO)

> `"""Invalid-grant handling (§4.3): null the esi_* columns only.`
> `The session-invalidation half is deferred to M3's token-using caller."""`

Nulls `esi_access_token`, `esi_refresh_token`, `esi_access_token_expires_at`; flushes. **The
session-invalidation half (destroying the Valkey session when a user's grant dies) is explicitly
left to M3.** So an M3 token-using feature must decide: when `mark_for_reauth` fires, also call
`destroy_session` and force re-login.

`VerifiedIdentity` fields used: `identity.character_id`, `identity.character_name`,
`identity.owner_hash` (from `services/sso.py`).

---

## 5. The missing-user-row hazard (ENV-2 DB wipe vs. surviving Valkey session)

**This is a real, live trap for M3 and must be designed around.**

### What `user_id` the session carries

The session's `user_id` is the **`users.id` autoincrement surrogate PK** (an `Integer`). Set at
`api/auth.py:174-178` inside `_finalize_login`:

```python
user = await auth_service.upsert_user(db, identity, tokens)
return await create_session(
    redis, user_id=user.id, character_id=identity.character_id, character_name=identity.character_name
)
```

So `session["user_id"] == users.id` at the moment of login.

### Why the row can be absent under the session

- **Dev startup is destructive (ENV-2/ENV-3):** `create_db_tables()` (`main.py:128-150`) runs
  `Base.metadata.drop_all` then `create_all` on every boot **when `ENVIRONMENT == "development"
  AND `DB_RECREATE_ON_STARTUP` is true** (fail-closed gate, `main.py:140`; `.env.example` sets both).
  This **drops the `users` table and resets its autoincrement sequence.**
- **Valkey is NOT flushed at startup.** `init_cache` (`core/cache.py:73-82`) only connects + pings;
  there is no `FLUSHDB`/`FLUSHALL` anywhere in the startup path (confirmed by grep). Valkey runs as
  a separate compose container that survives a backend restart.
- **Result:** a browser holding an `hb_session` cookie keeps a valid Valkey session with, say,
  `user_id=1` after a dev restart, but the `users` table is now empty — or, after the operator
  logs in again, a *different* character has been re-assigned `id=1` by the reset sequence. The
  session's `user_id` now points at a nonexistent (or wrong) row.

### What happens today

**Nothing breaks today**, because the only authenticated route, `/me` (`api/auth.py:296-300`),
serves entirely from the session payload and **never touches the DB or `users.id`.** The hazard is
latent — it only bites once M3 introduces DB rows keyed on `user_id`.

### What an FK insert against `users.id` would do

An M3 `INSERT INTO saved_searches (user_id, ...) VALUES (<session user_id>, ...)` where
`saved_searches.user_id` is `ForeignKey("users.id")` and the referenced row is absent →
**PostgreSQL `ForeignKeyViolation`, surfaced by SQLAlchemy/asyncpg as an `IntegrityError`** at
flush/commit. With the current `get_db` (`db.py:30-43`) that exception rolls back and re-raises,
and the global handler (`main.py:81-97`) turns an uncaught one into a **500**. Worse silent-corruption
variant: if the reset sequence re-assigned `id=1` to a *different* character, the FK check passes and
the new row is silently attached to the **wrong user** — a data-integrity bug, not a crash.

### Design implications for M3 (recommendations, not decisions)

1. **Validate the session's `user_id` against a live `users` row before trusting it** for any
   write. Options the designer should weigh: (a) an auth dependency that loads the `User` by
   `session["user_id"]` and 401s (forcing re-login) if absent — turns the latent bug into a clean
   re-auth; (b) key M3 tables on `character_id` (BigInteger, stable across DB wipes because it's the
   natural EVE key and re-populated identically on re-login) instead of the volatile surrogate
   `id`. Note (b) trades the smaller Integer FK for a BigInteger and still needs the row to exist.
2. **The wrong-user silent case is the dangerous one** — an existence check alone (option a) closes
   both the crash and the mis-attribution, because after a wipe+relogin the same character gets a
   *new* `id` and the stale session's old `user_id` won't match a row for that character. Prefer a
   dependency that resolves session → User row and rejects on miss.
4. This interacts with the deferred **session-invalidation-on-reauth** TODO (§4): both point toward
   an M3 "resolve current User from session, else force re-login" dependency as shared foundation.

---

## 6. `db.py` — engine, session factory, table creation, migrations

File: `app/backend/src/fastapi_app/db.py`.

- **Engine** (lines 11-15): `async_engine = create_async_engine(settings.DATABASE_URL,
  echo=(ENVIRONMENT == "development"), future=True)`. Async (asyncpg) engine.
- **Session factory** (lines 17-22): `AsyncSessionLocal = async_sessionmaker(bind=async_engine,
  class_=AsyncSession, expire_on_commit=False, autoflush=False)`.
- **`Base`** (line 8): `declarative_base()`.

### How new tables get created — `create_all` only; **Alembic is vestigial and stale**

- **Dev runtime:** `main.create_db_tables()` (`main.py:128-150`) is the only schema path in the app
  runtime. It runs `Base.metadata.drop_all` + `Base.metadata.create_all` inside
  `async_engine.begin()`, gated on `ENVIRONMENT == "development" AND DB_RECREATE_ON_STARTUP`
  (secure-by-default; unset ENVIRONMENT resolves to `"production"` per `config.py:21` → skip).
- **Tests:** `conftest.py` `db_session` fixture (lines 46-82) does the same `drop_all` + `create_all`
  per test function against `DATABASE_URL_TESTS`, wraps the test in one transaction, rolls back,
  drops again. **No Alembic in the test path.** New M3 tables appear in tests automatically once the
  model is imported into the `Base.metadata` graph (see §1 registration note; `conftest.py:26`
  imports contracts models explicitly, and `from fastapi_app.main import app` at line 20 pulls the
  rest transitively).
- **Alembic exists but is NOT wired into the app or tests and is out of sync with the models.**
  - `app/backend/src/alembic/` (env.py, versions/), `alembic.ini`, `check_alembic_version.py`
    (the last one is SQLite-era: it opens `hangar_bay_dev.db` — a legacy local sqlite file, whereas
    runtime is PostgreSQL).
  - **No `alembic upgrade` / `command.upgrade` / `run_migrations` call anywhere in
    `fastapi_app/` runtime** (confirmed by grep — empty result). `env.py` is import-safe for pytest
    but the CLI block was removed (`env.py:156`).
  - **The `users` migration is STALE / wrong schema:** `versions/baa67b53c016_create_users_table_
    with_account_types_.py` creates a totally different `users` table — `username`, `email`,
    `hashed_password`, `is_active`, `eve_character_id` (Integer!), `user_type` Enum(EVE_SSO/LOCAL),
    `is_admin`, `is_test_user`. The current SSO `User` model (`character_id` BigInteger,
    `owner_hash`, `esi_*` vault) bears **no resemblance** to it. `tests/models/test_user_model.py`
    even asserts the legacy columns are GONE (`test_legacy_user_columns_are_gone`). **Do not treat
    Alembic as the source of truth for M3 schema.**

**M3 schema takeaway:** the sanctioned way to add M3 tables today is **new SQLAlchemy models →
register on `Base.metadata` → picked up by `create_all`** in dev startup and tests. There is **no
live migration system**; production schema management is still listed as future work
(`main.py:130-131` comment: "production schema management is future migrations work"). If M3 wants
durable (non-drop-recreate) schema for a real deployment, that is a genuine gap the designer must
flag — but for dev + CI, `create_all` is the mechanism and it "just works" once the model is imported.

### The F006 matcher job's DB access (background, not request-scoped)

The watchlist-vs-contracts matcher will run under APScheduler, outside any HTTP request, so it
cannot use `Depends(get_db)`. Precedent: the aggregation job. `get_db_session_factory` (`db.py:25-27`)
returns `AsyncSessionLocal` for exactly this "open my own session" case; the ESI aggregation service
is constructed in `main.lifespan` (`main.py:50-56`) and scheduled via
`core/scheduler.add_aggregation_job`. The M3 matcher job should follow that shape: instantiate with
the session factory (or `async with AsyncSessionLocal() as session:`) and register through the same
scheduler. Interval config precedent: `AGGREGATION_SCHEDULER_INTERVAL_SECONDS` (`config.py:53`).

---

## Quick-reference: exact names/imports for the M3 designer

| Need | Symbol | Import |
|---|---|---|
| Auth gate (401 on anon) | `get_current_session(request, redis) -> dict` | `from ..core.session import get_current_session` |
| Optional auth | `get_optional_session(...) -> Optional[dict]` | `from ..core.session import get_optional_session` |
| DB session (request) | `get_db() -> AsyncSession` | `from ..db import get_db` |
| DB session (background) | `AsyncSessionLocal` / `get_db_session_factory()` | `from ..db import AsyncSessionLocal` |
| Owner id in session | `session["user_id"]` (== `users.id`, Integer) | — |
| EVE char id in session | `session["character_id"]` (BigInteger) | — |
| Model base | `Base` | `from ..db import Base` |
| FK target | `users.id` (Integer PK) | `ForeignKey("users.id")` |
| Token refresh foundation | `refresh_user_tokens(db, http_client, user)` | `from ..services import auth_service` |
| Filter-model GET rule | `Annotated[Model, Query()]` (never bare `Depends`) | FASTAPI-1 |

Session cookie name: `hb_session` (`SESSION_COOKIE_NAME`, `config.py:47`).
Idle TTL 7d / absolute cap 30d (`config.py:48-49`).
