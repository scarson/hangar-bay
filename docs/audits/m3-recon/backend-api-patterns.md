# M3 Recon — Backend API + Schemas + Services Conventions

ABOUTME: Read-only recon of the Hangar Bay FastAPI backend for M3 (F005 Saved Searches, F006 Watchlists, F007 Alerts).
ABOUTME: Facts + file:line so a designer can build per-user CRUD tables, a matcher job, and auth-gated /me/* routes without re-reading source.

Scope root: `/Users/sam/Code/hangar-bay/.claude/worktrees/drama-pass-implementation-ae2eeb`
All paths below are relative to `app/backend/src/fastapi_app/` unless otherwise noted. Recon date: 2026-07-17.

---

## 0. TL;DR for M3 designers

- **Routers mount bare (no `/api/v1`), per PROXY-1.** Each router declares its own `prefix` + `tags` and is `app.include_router(...)`ed in `main.py`. M3 per-user routes should follow the same shape — a new `api/` module with an `APIRouter(prefix="/me/saved-searches", tags=["Saved Searches"])` etc., included in `main.py`.
- **Auth-gating is one dependency:** `Depends(get_current_session)` (returns the session dict, 401s if absent). There is NO `get_current_user` that loads the `User` row — only the session payload (`user_id`, `character_id`, `character_name`) is available without an extra DB read. M3 CRUD FK'd to `users.id` will need `session["user_id"]` (already in the payload — no DB round-trip required to get the owning user id).
- **Pagination envelope is `PaginatedResponse[T]`** with exactly four fields: `total`, `page`, `size`, `items`. Reuse it for any M3 list route.
- **The saved-search "search_parameters" payload = the `ContractFilters` fields** (§3/§4 below give the exact set, types, defaults, and which are inert). Four params (`min_me/max_me/min_te/max_te`) are accepted-but-inert (FASTAPI-2) — a saved search must not treat them as functional.
- **`/me` declares only a 200 in OpenAPI; its 401 is NOT declared.** M3 auth-gated routes inherit the same gap unless they add `responses={401: {"model": ErrorDetail}, ...}` explicitly (see §6).
- **Error-body shape is `ErrorDetail` = `{"detail": str}`** (`schemas/auth.py`). Declared on the auth 400/503 responses so the typed client sees a real body. M3 routes returning 401/403/404/409 should declare `ErrorDetail` the same way.

---

## 1. api/ — routers, prefixes, paths, mounting

Two router modules under `api/` (plus empty `routers/__init__.py` and `api/__init__.py` — the `routers/` package is vestigial/empty; real routers live in `api/`).

### 1.1 `api/contracts.py`

- Router: `router = APIRouter(prefix="/contracts", tags=["Contracts"])` — `api/contracts.py:17-20`.
- **Routes:**
  - `GET /contracts/` (trailing slash) — `list_public_contracts` — `api/contracts.py:27-38`.
    - Decorator: `@router.get("/", response_model=PaginatedResponse[ContractSchema])`.
    - Signature: `async def list_public_contracts(filters: Annotated[ContractFilters, Query()], db: AsyncSession = Depends(get_db))`.
    - **`Annotated[ContractFilters, Query()]` — NOT `Depends(ContractFilters)`** (FASTAPI-1: a bare `Depends` on a model pushes `List[int]` fields to the GET body). M3 GET list routes with list filters MUST copy this.
    - Delegates entirely to `get_contracts(db=db, filters=filters)`.
  - `GET /contracts/{contract_id}` — `get_contract` — `api/contracts.py:41-60`. `response_model=ContractSchema`; `contract_id: int` path param; raises `HTTPException(status_code=404, detail="Contract not found")` when missing; loads items via `selectinload(Contract.items)`.
    - **Ordering matters:** the comment at `api/contracts.py:23-26` warns `/{contract_id}` must be declared AFTER `/` (here it's fine because `/` and `/{id}` don't collide, but the pattern note is about a hypothetical `/ships` static route being shadowed by `/{contract_id}`).
- No status_code override on the list route → default 200. No explicit `responses=` error declarations on either contracts route.

### 1.2 `api/auth.py`

Two routers in one module (both mounted bare):

- `router = APIRouter(prefix="/auth/sso", tags=["Auth"])` — `api/auth.py:28`.
- `me_router = APIRouter(tags=["Auth"])` — `api/auth.py:29` (no prefix; owns bare `/me`).

**Routes:**

| Method + path | Function | line | status/response decl |
|---|---|---|---|
| `GET /auth/sso/login` | `login` | `89-115` | `status_code=302`, `response_class=RedirectResponse`, `responses={503: {"model": ErrorDetail, ...}}`, `dependencies=[Depends(require_sso_configured)]` |
| `GET /auth/sso/callback` | `callback` | `184-282` | `status_code=302`, `response_class=RedirectResponse`, `responses={400: {"model": ErrorDetail}, 503: {"model": ErrorDetail}}` |
| `POST /auth/sso/logout` | `logout` | `285-293` | `status_code=204` |
| `GET /me` | `me` | `296-300` | `response_model=CurrentUserSchema` (200 only — 401 undeclared) |

- `/me` handler: `async def me(session: dict = Depends(get_current_session))` → returns `CurrentUserSchema(character_id=session["character_id"], character_name=session["character_name"])`. **No DB read** — serves from session payload alone (`api/auth.py:297-300`).
- `require_sso_configured` (`api/auth.py:36-39`) raises `503` when `ESI_CLIENT_ID` empty or token cipher unconfigured — relevant only to SSO flow, not M3 CRUD.

### 1.3 Router mounting — `main.py:189-194`

```python
app.include_router(contracts_router.router)   # /contracts/*
app.include_router(auth_router.router)         # /auth/sso/login|callback|logout (bare, PROXY-1)
app.include_router(auth_router.me_router)      # /me (bare)
```

- Imports at `main.py:25-26`: `from .api import contracts as contracts_router`, `from .api import auth as auth_router`.
- **No `/api/v1` anywhere** — the Vite proxy / deploy edge owns that prefix (PROXY-1). `main.py:190-191` comment restates this. Test sentinel `tests/api/test_me_schema.py:12-13` asserts no path starts with `/api/v1`.
- App-level (non-router) routes in `main.py`: `GET /` (`116`), `GET /health` (`123`), `GET /cache-test` (`169`, tagged `Development/Test`, marked `CASCADE-PROD-CHECK` for removal), plus `/metrics` from Prometheus instrumentator (`main.py:112-113`).
- Global exception handler `main.py:81-97` catches all unhandled `Exception` → `500 {"detail": "An unexpected server error occurred."}`. `RequestIDMiddleware` added `main.py:100`.

### 1.4 Trailing-slash convention (PROXY-1)

- Collection routes use a trailing slash on the **route decorator relative to the prefix**: `@router.get("/")` under `prefix="/contracts"` → `/contracts/`. Confirmed exposed as `/contracts/` in `openapi.json`.
- Detail routes have no trailing slash: `/contracts/{contract_id}`.
- Clients must call schema paths **verbatim including the trailing slash**; a bare-path request 307-redirects and the `Location` escapes the proxy. M3 collection routes (`/me/saved-searches/`) should keep the trailing-slash-on-collection convention for consistency.

---

## 2. schemas/ — naming, pagination envelope, error bodies

### 2.1 Files & naming conventions

- `schemas/contracts.py` — response models suffixed `Schema` (`ContractSchema`, `ContractItemSchema`); the query-param model is `ContractFilters` (suffix `Filters`); enums are plain names (`SortableContractFields`, `SortDirection`).
- `schemas/common.py` — `PaginatedResponse` (generic envelope).
- `schemas/auth.py` — `CurrentUserSchema`, `ErrorDetail`.
- Response schemas set `model_config = ConfigDict(from_attributes=True)` so they can `.model_validate(orm_obj)` (e.g. `ContractSchema` `schemas/contracts.py:49`, `ContractItemSchema:22`, `CurrentUserSchema` `schemas/auth.py:9`). M3 response schemas over ORM rows should do the same.
- `schemas/__init__.py` is EMPTY — schemas are imported by full module path (`from ..schemas.contracts import ...`), not re-exported. M3 can follow the same pattern.

### 2.2 Pagination envelope — EXACT fields (`schemas/common.py:1-11`)

```python
T = TypeVar('T')

class PaginatedResponse(BaseModel, Generic[T]):
    total: int   # "Total number of items"
    page: int    # "Current page number"
    size: int    # "Number of items per page"
    items: List[T]  # "List of items for the current page"
```

- Generic over `T`. Used as `PaginatedResponse[ContractSchema]` in both the route `response_model` and the service return type.
- In OpenAPI it materializes as component schema `PaginatedResponse_ContractSchema_` (confirmed in `openapi.json`). An M3 `PaginatedResponse[SavedSearchSchema]` would generate `PaginatedResponse_SavedSearchSchema_`.
- **No `pages`/`has_next`/`next_cursor` field** — offset/limit style, caller computes page count from `total`/`size`.

### 2.3 Error-response declarations in OpenAPI (the hardening-PR shape)

- `ErrorDetail` (`schemas/auth.py:12-17`): a single-field model `detail: str`, deliberately mirroring FastAPI's `HTTPException`/`JSONResponse` body `{"detail": ...}`. Its docstring says it exists so the 400/503 responses "carry their real JSON body in the OpenAPI contract instead of an empty one."
- Declared via the `responses=` dict on the route decorator, e.g. `api/auth.py:97-99` (`503: {"model": ErrorDetail, "description": "EVE SSO is not configured."}`) and `api/auth.py:195-198` (`400` + `503`).
- Confirmed in exported `openapi.json`: login → responses `302, 422, 503`; callback → `302, 400, 422, 503` (422 is FastAPI's auto validation-error). The 400/503 bodies `$ref` `#/components/schemas/ErrorDetail`.
- **Gap for M3:** `get_current_session` raises `401` but that 401 is NOT in any `responses=` dict, so `/me` shows **only 200** in OpenAPI (verified — `/me` responses = `['200']`). If M3 wants the typed client to know about 401/403/404/409, each route must add them explicitly, e.g. `responses={401: {"model": ErrorDetail, "description": "Not authenticated"}}`.

---

## 3. services/contract_service.py — get_contracts, applied vs inert filters, SQLA-1 shape

### 3.1 Signature

```python
async def get_contracts(db: AsyncSession, filters: ContractFilters) -> PaginatedResponse[ContractSchema]
```
`services/contract_service.py:35-37`. Pure function (no request/response objects) — takes a session + a `ContractFilters`, returns the envelope. Instantiable directly in tests and reusable by a background job. **M3's watchlist matcher can call `get_contracts` directly** (or reuse its filter-application logic) to evaluate a saved `ContractFilters` against current contracts.

### 3.2 Which filters are APPLIED (source of truth for what a saved search can actually do)

Applied in the query body (`services/contract_service.py:84-129`):

| Filter | Applied? | How | line |
|---|---|---|---|
| `search` | ✅ | `ILIKE %term%` on `Contract.title` OR `ContractItem.type_name` (forces item join) | 88-96 |
| `min_price` / `max_price` | ✅ | `Contract.price >= / <=` | 99-102 |
| `min_collateral` / `max_collateral` | ✅ | `Contract.collateral >= / <=` | 103-106 |
| `is_ship_contract` | ✅ | `Contract.is_ship_contract ==` (indexed, no item join) | 109-110 |
| `region_ids` | ✅ | `Contract.start_location_region_id.in_(...)` | 113-114 |
| `system_ids` | ✅ | `Contract.start_location_system_id.in_(...)` | 115-116 |
| `station_ids` | ✅ | `Contract.start_location_id.in_(...)` | 117-118 |
| `type_ids` | ✅ | `ContractItem.type_id.in_(...)` (item join) | 121-122 |
| `is_bpc` | ✅ | `ContractItem.is_blueprint_copy ==` (item join) | 123-124 |
| `min_runs` / `max_runs` | ✅ | `ContractItem.raw_quantity >= / <=` (item join) | 126-129 |
| `sort_by` | ✅ | via `SORT_MAP` (see §3.4) | 160-163 |
| `sort_direction` | ✅ | asc/desc | 165 |
| `page` / `size` | ✅ | offset/limit | 182-183, 202-204 |
| **`min_me` / `max_me`** | ❌ **INERT** | never referenced in service (ME data not in model) | — |
| **`min_te` / `max_te`** | ❌ **INERT** | never referenced in service (TE data not in model) | — |

- **FASTAPI-2 confirmed:** `min_me/max_me/min_te/max_te` are accepted by the schema and appear in OpenAPI but are silently ignored. Comment at `services/contract_service.py:125` ("ME/TE not implemented as data is not in model") and schema descriptions `schemas/contracts.py:97-132` flag them `NOT IMPLEMENTED — accepted but ignored by the service; do not expose in clients`. **A saved search must not present these four as working filters.**
- The item-join trigger set (`needs_item_join`, `contract_service.py:69-77`): `search`, `type_ids`, `is_bpc`, `min_runs`, `max_runs`, or `sort_by == ship_name`.

### 3.3 SQLA-1 pagination fix (distinct-parent-IDs subquery)

- **Count** (`contract_service.py:131-139`): counts DISTINCT contract IDs via a subquery, because the item join duplicates contract rows:
  ```python
  count_subquery = select(query.subquery().c.contract_id).distinct().subquery()
  count_query = select(func.count()).select_from(count_subquery)
  ```
- **Data page, join path** (`contract_service.py:167-197`): does NOT offset/limit the joined query. Instead:
  1. `id_query`: `query.with_only_columns(Contract.contract_id).group_by(contract_id).order_by(<aggregate>, contract_id.asc()).offset(...).limit(...)` — paginates over distinct contract IDs.
  2. Ordering uses `func.max(sort_column)` when descending else `func.min(sort_column)` (aggregate picks the direction-appropriate representative when a contract has multiple items) with `contract_id.asc()` as a deterministic tiebreaker (`contract_service.py:176-177`).
  3. Loads that page's contracts via `select(Contract).where(contract_id.in_(page_ids)).options(selectinload(Contract.items))`, then re-sorts in Python to restore `page_ids` order (`contract_service.py:188-197`).
- **Non-join path** (`contract_service.py:198-207`): straight `order_by(...).offset().limit().options(selectinload(items))`.
- Early-return `PaginatedResponse(total=0, page, size, items=[])` when count is 0 (`contract_service.py:141-156`).
- **M3 relevance:** any M3 list route that joins a one-to-many (e.g. a watchlist with matched-contracts) must replicate this distinct-parent-ID pagination, not offset/limit the joined rows (SQLA-1). `selectinload` is the eager-load pattern used throughout.

### 3.4 SORT_MAP (allowlisted sort columns — `contract_service.py:24-32`)

Maps `SortableContractFields` enum → real columns (security allowlist against arbitrary-column sort):
`date_issued→Contract.date_issued`, `date_expired→Contract.date_expired`, `price→Contract.price`, `collateral→Contract.collateral`, `volume→Contract.volume`, `ship_name→ContractItem.type_name`.
The enum `SortableContractFields` (`schemas/contracts.py:52-60`) has six members — `date_issued, date_expired, price, collateral, ship_name, volume` — and SORT_MAP covers all six, so every declared sort key resolves to a real column. Unknown keys fall back to `Contract.date_issued` (`contract_service.py:160-163`).

---

## 4. /contracts/ query params AS EXPOSED IN OpenAPI (saved-search round-trip contract)

From exported `app/frontend/web/openapi.json`, path `/contracts/`, `operationId: list_public_contracts_contracts__get`. Every param is `in: query`, `required: false`. This is the exact set a saved search's `search_parameters` must round-trip:

| name | JSON type | constraints | default | applied? |
|---|---|---|---|---|
| `search` | string \| null | minLength 3 | null | ✅ |
| `min_price` | number \| null | ≥ 0 | null | ✅ |
| `max_price` | number \| null | ≥ 0 | null | ✅ |
| `min_collateral` | number \| null | ≥ 0 | null | ✅ |
| `max_collateral` | number \| null | ≥ 0 | null | ✅ |
| `min_runs` | integer \| null | ≥ -1 | null | ✅ |
| `max_runs` | integer \| null | ≥ -1 | null | ✅ |
| `min_me` | integer \| null | ≥ 0 | null | ❌ inert |
| `max_me` | integer \| null | ≥ 0 | null | ❌ inert |
| `min_te` | integer \| null | ≥ 0 | null | ❌ inert |
| `max_te` | integer \| null | ≥ 0 | null | ❌ inert |
| `region_ids` | array<integer> \| null | — | null | ✅ |
| `system_ids` | array<integer> \| null | — | null | ✅ |
| `station_ids` | array<integer> \| null | — | null | ✅ |
| `type_ids` | array<integer> \| null | — | null | ✅ |
| `is_bpc` | boolean \| null | — | null | ✅ |
| `is_ship_contract` | boolean \| null | — | null | ✅ |
| `page` | integer | 1..(no max) | **1** | ✅ |
| `size` | integer | 1..100 | **50** | ✅ |
| `sort_by` | enum `SortableContractFields` | date_issued\|date_expired\|price\|collateral\|ship_name\|volume | **date_issued** | ✅ |
| `sort_direction` | enum `SortDirection` | asc\|desc | **desc** | ✅ |

- Source Pydantic definition: `schemas/contracts.py:68-164` (`ContractFilters`). Field constraints via `Field(default=..., ge=..., le=..., min_length=..., description=...)`.
- **Design implication for F005 Saved Searches:** the persisted `search_parameters` blob is naturally a subset/all of these 20 params. Recommend persisting only the **applied** 16 (exclude the 4 inert ME/TE) plus sort/page/size, OR persist the whole `ContractFilters` shape but never surface ME/TE as editable. `page` is per-view, not really a saved-search property — designer decision.
- Array params serialize as repeated query params (`region_ids=1&region_ids=2`), bound via `Annotated[ContractFilters, Query()]`.

---

## 5. export_openapi — how it works + the _ENV_DEFAULTS trap

**Location note:** the task referenced `scripts/export_openapi.py`, but the actual file is **`app/backend/src/export_openapi.py`** (there is no `scripts/` dir). PDM script: `export-openapi = "python src/export_openapi.py"` (`app/backend/pyproject.toml`), run from `app/backend/`.

- `export_openapi.py:16-23`: before importing `fastapi_app.main`, it `os.environ.setdefault(...)`s four dummy values:
  ```python
  _ENV_DEFAULTS = {
      "ESI_USER_AGENT": "hangar-bay-openapi-export (build tooling)",
      "AGGREGATION_REGION_IDS": "[10000002]",
      "DATABASE_URL": "postgresql+asyncpg://export:export@localhost:5432/export_dummy",
      "CACHE_URL": "redis://localhost:6379/15",
  }
  ```
- **The trap:** `Settings` (`core/config.py`) has FOUR **required-without-default** fields — `ESI_USER_AGENT` (`config.py:32`), `DATABASE_URL` (`config.py:61`), `CACHE_URL` (`config.py:62`), and `AGGREGATION_REGION_IDS` needs a parseable value. Importing `main` constructs `settings = Settings()` at module load (`config.py:95`) AND `db.py:9` builds an engine from `DATABASE_URL` at import. Without the dummy env, codegen crashes on missing settings before any schema is produced. `setdefault` means **real env always wins** — dummies are import-time-only and never open a real connection (only `app.openapi()` is called).
- **M3 impact:** if M3 adds any NEW required-without-default `Settings` field (no default), `export_openapi.py`'s `_ENV_DEFAULTS` MUST be extended with a dummy for it, or `pdm run export-openapi` (and the frontend `npm run generate:api` chain) breaks. Prefer giving new settings safe defaults; if a secret must be required, add it to `_ENV_DEFAULTS`. Regression test exists: `tests/test_export_openapi.py`.
- Output: `app.openapi()` dumped to `../frontend/web/openapi.json` (default) with `indent=2, sort_keys=True` + trailing newline (`export_openapi.py:28-34`).

---

## 6. /me-related surfaces (auth-gating pattern for M3 /me/* routes)

### 6.1 `CurrentUserSchema` (`schemas/auth.py:5-9`)

```python
class CurrentUserSchema(BaseModel):
    character_id: int
    character_name: str
    model_config = ConfigDict(from_attributes=True)
```
- **Does NOT expose `users.id`** — only EVE character identity. `/me` builds it from the session payload, no DB read. Test `tests/api/test_me_schema.py:28-35` pins the shape to exactly `{character_id, character_name}`.

### 6.2 Auth router shape & tags

- SSO router: `prefix="/auth/sso"`, `tags=["Auth"]` (`api/auth.py:28`).
- `/me` router: no prefix, `tags=["Auth"]` (`api/auth.py:29`).
- Both mounted bare in `main.py:193-194`.

### 6.3 The auth-gating dependency (the key M3 building block)

- `get_current_session(request, redis=Depends(get_cache)) -> dict` (`core/session.py:116-123`): reads the `hb_session` cookie (name from `settings.SESSION_COOKIE_NAME`, default `"hb_session"`, `config.py:47`), calls `read_session`, and **raises `HTTPException(401, "Not authenticated")`** if the cookie is missing OR the session is absent/expired. Returns the session **dict**.
- `get_optional_session(...) -> Optional[dict]` (`core/session.py:126-130`): same but returns `None` instead of 401 — use for routes that vary by auth but don't require it.
- **Session payload dict shape** (`core/session.py:60-65`, validated in `_parse_session_payload` `28-46`): `{"user_id": int, "character_id": int, "character_name": str, "created_at": int}`. So **`session["user_id"]` is the `users.id` FK an M3 CRUD row needs — no extra DB read to get the owner.**
- There is **no `get_current_user` dependency** that loads the ORM `User`. If an M3 route needs the full `User` row (e.g. ESI tokens for watchlist matching against private data), it must `select(User).where(User.id == session["user_id"])` itself. For F005/F006/F007 which are keyed on public contract data, `session["user_id"]` alone should suffice as the FK.

### 6.4 M3 pattern to copy for auth-gated `/me/saved-searches` etc.

```python
me_router = APIRouter(prefix="/me/saved-searches", tags=["Saved Searches"])

@me_router.get("/", response_model=PaginatedResponse[SavedSearchSchema],
               responses={401: {"model": ErrorDetail, "description": "Not authenticated"}})
async def list_saved_searches(session: dict = Depends(get_current_session),
                              db: AsyncSession = Depends(get_db)):
    ...  # filter by owner: WHERE user_id == session["user_id"]
```
Then `app.include_router(...)` in `main.py`. Note the explicit `responses={401: ...}` — without it the 401 won't appear in OpenAPI (the `/me` gap in §2.3).

---

## 7. Models — patterns for M3 per-user tables

- `Base = declarative_base()` in `db.py:8`; models import it via `from ..db import Base`. `models/__init__.py` re-exports `User, Contract, ContractItem, EsiMarketGroupCache` and, crucially, **importing `models` is what registers tables on `Base.metadata`** (`main.py:27` comment: "crucial for Base.metadata to find the tables"). **M3 must add new model modules to `models/__init__.py`** (and ensure they're imported before `create_db_tables` runs) or `drop_all/create_all` won't see them.
- **`User` model** (`models/user.py:12-32`), `__tablename__ = "users"`:
  - PK: `id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)` — **this is the FK target for M3 per-user tables** (`ForeignKey("users.id")`).
  - `character_id`: **`BigInteger`** (EVE IDs are 64-bit — comment warns a 32-bit Integer overflows), `unique=True, index=True`.
  - `character_name` `String(255)`, `owner_hash` `String(255)` indexed, encrypted token columns `esi_access_token`/`esi_refresh_token` (`Text`, Fernet ciphertext), `esi_scopes` (`Text`, "empty in F004; F005+ fills" — **F005 is expected to populate scopes**), `last_login_at`, `created_at`/`updated_at` with `server_default=func.now()` / `onupdate=func.now()`.
- **Timestamp convention:** `Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)`; for updates add `onupdate=func.now()` (see `user.py:24-29`). M3 CRUD tables should follow this for `created_at`/`updated_at`.
- **ID column widths:** contract-related IDs and any EVE-origin IDs use `BigInteger`; internal autoincrement PKs use plain `Integer`/default (`user.id`). `contract_id` PK is `BigInteger, autoincrement=False` (ESI-assigned). For M3: watchlist type_ids/region_ids etc. that reference EVE entities should be `BigInteger` if they can hold character/location IDs; type_ids fit in Integer but be deliberate.
- **Relationship/eager-load pattern:** `relationship(back_populates=..., cascade="all, delete-orphan")` on the parent (`Contract.items`, `models/contracts.py:68`); loaded via `selectinload(...)` in queries. `__table_args__` holds explicit `Index(...)` definitions.
- **JSON column precedent:** `EsiMarketGroupCache.raw_esi_response: Mapped[Any] = mapped_column(JSON, ...)` (`models/contracts.py:29`) — **a JSON column pattern already exists**, useful if F005 stores `search_parameters` as a JSON blob rather than normalized columns.

---

## 8. Background job pattern (for F006/F007 the watchlist-vs-contracts matcher)

- Scheduler wiring lives in `core/scheduler.py`; the aggregation job is added in `main.py:49-57` (`create_scheduler`, `add_aggregation_job`) inside the `lifespan` context. The existing ingestion job is `services/background_aggregation.py` / `services/scheduled_jobs.py`. **A periodic M3 matcher job should register the same way** (APScheduler, added in `lifespan`).
- Interval config precedent: `AGGREGATION_SCHEDULER_INTERVAL_SECONDS` (`config.py:53`). An M3 matcher would add its own interval setting (with a default, to avoid the `_ENV_DEFAULTS` trap in §5).
- **DB session in a background job:** routes get `AsyncSession` via `Depends(get_db)` (`db.py:30-43`, commits on success / rolls back on error). A background job has no request scope — it must build its own session via `AsyncSessionLocal()` (as `db_upsert.py` / aggregation service do) rather than `get_db`. Worth checking `services/background_aggregation.py` for the exact session-management idiom when designing the matcher (not fully read in this recon — flagged).

---

## 9. Risks / traps the M3 design MUST account for

1. **FASTAPI-2 inert params:** `min_me/max_me/min_te/max_te` are dead. A saved search that stores/replays `ContractFilters` must not present these as functional; ideally exclude them from the persisted `search_parameters` schema entirely.
2. **`/me` 401 is undeclared in OpenAPI.** M3 auth-gated routes inherit this — add explicit `responses={401: {"model": ErrorDetail}}` (and 403/404/409 as needed) so the typed frontend client knows about them.
3. **No `get_current_user` (ORM) dependency exists** — only `get_current_session` (dict). `session["user_id"]` gives the FK cheaply; loading the full `User` needs an explicit query. Decide per route whether the dict suffices (it does for public-contract-keyed features).
4. **`_ENV_DEFAULTS` trap (§5):** any new **required-without-default** `Settings` field breaks `export-openapi` + frontend codegen until added to `export_openapi.py`. Prefer defaults; add dummies for genuinely-required secrets. Regression test: `tests/test_export_openapi.py`.
5. **New models must be imported into `Base.metadata`** (add to `models/__init__.py`, ensure import path reached before `create_db_tables`) or dev `drop_all/create_all` silently omits them.
6. **SQLA-1 pagination:** any M3 list route joining a one-to-many must use the distinct-parent-ID pagination shape (§3.3), not offset/limit over joined rows.
7. **PROXY-1 trailing slashes:** keep collection routes trailing-slashed, no `/api/v1` in FastAPI, clients call verbatim.
8. **Dev-destructive startup (ENV-2/3):** every backend `.py` save under `--reload` runs `drop_all/create_all` + re-ingests (gated on `ENVIRONMENT==development` AND `DB_RECREATE_ON_STARTUP`, `main.py:128-150`). M3 dev data (saved searches, watchlists) is wiped on every reload — batch edits, and don't rely on persisted user data surviving a restart in dev.
9. **`ContractFilters` is a plain `BaseModel` used both as query-binding AND as a pure data container** (its own docstring, `schemas/contracts.py:68-76`, notes it's decoupled so tests/services can instantiate it). F005 can reuse it to represent a saved search's filter payload and feed it straight into `get_contracts` — strong reuse opportunity for the matcher.
10. **`create_session` is the only session minter** and it takes `user_id, character_id, character_name` (`session.py:49-67`). If M3 changes what identity data routes need (e.g. scopes for private ESI calls), the session payload shape and `_parse_session_payload` validation (`session.py:28-46`) must both change in lockstep, plus `read_session`'s field checks.
11. **`refresh_user_tokens` / `mark_for_reauth` exist but are M3-foundation, unused in M2** (`auth_service.py:52-105`, multiple `TODO(M3)` markers). If F005+ makes authenticated ESI calls (scopes), these are the token-refresh entry points — but they carry known TODO gaps (invalid_grant discrimination on status alone; concurrent-refresh race with no row lock). The first-login race (`upsert_user`, `auth_service.py:16-49`) also has a `TODO(M3)` to make the loser succeed via `ON CONFLICT` instead of retry.

---

## Appendix — exact signatures/definitions (quick reference)

- `PaginatedResponse(BaseModel, Generic[T])`: `total:int, page:int, size:int, items:List[T]` — `schemas/common.py:7-11`.
- `ContractFilters(BaseModel)` fields — `schemas/contracts.py:78-164` (see §4 table for types/defaults).
- `SortableContractFields(str, Enum)`: `date_issued, date_expired, price, collateral, ship_name, volume` — `schemas/contracts.py:52-60`.
- `SortDirection(str, Enum)`: `asc, desc` — `schemas/contracts.py:63-65`.
- `CurrentUserSchema`: `character_id:int, character_name:str` — `schemas/auth.py:5-9`.
- `ErrorDetail`: `detail:str` — `schemas/auth.py:12-17`.
- `get_contracts(db: AsyncSession, filters: ContractFilters) -> PaginatedResponse[ContractSchema]` — `services/contract_service.py:35`.
- `get_current_session(request, redis=Depends(get_cache)) -> dict` (401s) — `core/session.py:116`.
- `get_optional_session(request, redis=Depends(get_cache)) -> Optional[dict]` — `core/session.py:126`.
- `create_session(redis, *, user_id, character_id, character_name, now=None) -> str` — `core/session.py:49`.
- `get_db() -> AsyncSession` (yields, commit-on-success) — `db.py:30`.
- `User`: PK `id:int` (autoincrement) — FK target; `character_id:BigInteger unique index` — `models/user.py:12`.
- Router mount order — `main.py:192-194`.
