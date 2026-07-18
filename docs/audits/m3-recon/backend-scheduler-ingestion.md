# M3 Recon — Backend Scheduler / Ingestion / Type Cache

ABOUTME: Read-only recon of Hangar Bay's APScheduler wiring, aggregation/ingestion pipeline, and ESI type cache.
ABOUTME: Facts + file:line for the M3 designer building F005 Saved Searches, F006 Watchlists, F007 Alerts (watchlist-vs-contracts matcher job + /me/* CRUD).

Scope: scheduler + ingestion + type cache. All paths under
`app/backend/src/fastapi_app/` unless noted. Line numbers are as of this recon.

---

## 1. APScheduler wiring

**Files:** `core/scheduler.py`, `main.py` (lifespan), `services/scheduled_jobs.py`.

### Scheduler creation — `core/scheduler.py:17-30`
```python
def create_scheduler(app: FastAPI, settings: Settings) -> AsyncIOScheduler:
    redis_url = urlparse(settings.CACHE_URL)
    jobstores = {"default": RedisJobStore(host=..., port=..., db=..., password=...)}
    scheduler = AsyncIOScheduler(jobstores=jobstores)
    app.state.scheduler = scheduler
    return scheduler
```
- Scheduler type: **`apscheduler.schedulers.asyncio.AsyncIOScheduler`** (runs on the app's asyncio loop).
- Job store: **`RedisJobStore`** (`apscheduler.jobstores.redis`) — single store named `"default"`, pointed at `settings.CACHE_URL` (host/port/db/password parsed via `urlparse`). **Jobs and their args are pickled into Valkey** and persist across restarts. Default APScheduler Redis keys use the `apscheduler.*` prefix (jobs hash + run-times zset).
- The scheduler instance is stashed on **`app.state.scheduler`**.

### Job registration — `core/scheduler.py:33-48`
```python
def add_aggregation_job(scheduler, aggregation_service, settings):
    scheduler.add_job(
        run_aggregation_job,
        trigger="interval",
        args=[aggregation_service],
        seconds=settings.AGGREGATION_SCHEDULER_INTERVAL_SECONDS,
        id="aggregate_public_contracts",
        replace_existing=True,
        misfire_grace_time=300,      # 5 min
        next_run_time=datetime.now() # fire immediately on startup
    )
```
- One job today: id **`"aggregate_public_contracts"`**, interval trigger.
- `next_run_time=datetime.now()` means it runs **immediately at startup** then every interval.
- `replace_existing=True` so re-adding on each boot overwrites the persisted job (safe with the Redis store).

### Lifespan wiring — `main.py:38-71` (`lifespan`)
Order at startup: `setup_logging` → `warn_if_sso_unconfigured` → `create_db_tables` → `init_http_client` → `init_cache` → then:
```python
scheduler = create_scheduler(app, settings)
esi_client = ESIClient(settings=settings)                       # no injected http/redis clients
aggregation_service = ContractAggregationService(esi_client=esi_client, settings=settings)
add_aggregation_job(scheduler, aggregation_service, settings)
scheduler.start()
```
Shutdown (`main.py:63-71`): `if app.state.scheduler.running: app.state.scheduler.shutdown()` then close http/cache.

### How to add a SECOND periodic job (e.g. the watchlist matcher)
1. Write a **top-level, importable** job function (mirror `services/scheduled_jobs.run_aggregation_job`). Because `RedisJobStore` **pickles the function reference AND its `args`**, either:
   - pass a picklable service instance as an arg (the current pattern — `ContractAggregationService` is picklable because `ESIClient` defers all http/redis client creation to `__aenter__`, holding only `settings` + `None` at rest), **or**
   - register a zero-arg function that builds its own deps inside the run.
2. In `main.py` lifespan, after `create_scheduler(...)` and before `scheduler.start()`, call `scheduler.add_job(matcher_fn, trigger="interval", args=[...], seconds=<interval>, id="<unique_id>", replace_existing=True, misfire_grace_time=..., next_run_time=...)`. Use a **new unique `id`** (id collides silently overwrite).
3. There is **no dependency/chaining** between jobs — APScheduler fires each on its own schedule. If the matcher must see freshly-ingested data, it cannot "run after ingestion completes"; it runs on its own clock and reads whatever is committed (see §6 risks).

---

## 2. The aggregation job (ingestion pipeline)

**File:** `services/background_aggregation.py`. Entry wrapper: `services/scheduled_jobs.py`.

### Entry chain
- `scheduled_jobs.run_aggregation_job(aggregation_service)` (`scheduled_jobs.py:13-25`) → `await aggregation_service.run_aggregation()`, wrapped in try/except that logs and swallows.
- `ContractAggregationService.run_aggregation()` (`background_aggregation.py:124-211`):
  - Validates `settings.AGGREGATION_REGION_IDS` is a non-empty `list[int]`.
  - Acquires the Valkey lock via `async with self._concurrency_lock()`.
  - Opens the ESI client as an async CM (`async with self.esi_client`).
  - **Creates its OWN engine per run**: `create_async_engine(self.settings.DATABASE_URL)` + `sessionmaker(... AsyncSession, expire_on_commit=False)` (lines 147-156), disposed in `finally` (208-211). It does **not** use `db.AsyncSessionLocal`.
  - Fetches per region: `esi_client.get_public_contracts(region_id)`, stamps `contract_data["_hb_region_id"] = region_id` (166-171).
  - Applies the dev limit (183-187), then `_process_contracts(db_session, all_contracts_data)` and a single `db_session.commit()` at the end (189-192).

### The Valkey lock (module-level, `background_aggregation.py:26-37, 81-122`)
- **Key:** `AGGREGATION_LOCK_KEY = "hangar-bay:aggregation:lock"`.
- **TTL:** `AGGREGATION_LOCK_TIMEOUT = 1800` seconds (**30 min**), set via `SET NX EX`.
- **Fencing token:** `lock_token = uuid.uuid4().hex`, stored as the lock value.
- **Release:** Lua compare-and-delete `_RELEASE_LOCK_LUA` — deletes only if the stored value still equals this runner's token (guards against TTL-expiry-then-reacquire).
- Not acquired ⇒ raises `ConcurrencyLockError` (subclass of `Exception`, line 58) ⇒ run skips (logged, no error).
- **The lock client is created ad hoc**: `aioredis.from_url(str(self.settings.CACHE_URL))` (line 87) — **no `decode_responses`** (bytes-mode), separate from the app's `app.state.redis`.

### structlog usage
- **The aggregation pipeline uses plain stdlib logging**, NOT structlog: `logger = logging.getLogger(__name__)` (`background_aggregation.py:23`, `scheduled_jobs.py:10`, `scheduler.py:14`). These records still render as JSON because `setup_logging` (`core/logging.py:50-97`) reconfigures the **root** logger through structlog's stdlib pipeline.
- The **structured** helpers live in `core/logging.py`: `get_logger(name)` → `structlog.stdlib.BoundLogger`, and `log_key_event(logger, event, success, duration_ms, error_message=None, **kwargs)` which emits `event_name`/`success`/`duration_ms`/... Used today only by `services/contract_service.py` and `api/auth.py`. **The aggregation job emits NO `log_key_event` and records NO structured "run succeeded/failed" event or timestamp** (see §6 risk 1). Request-scoped logs get a `request_id` via `RequestIDMiddleware` (`core/logging.py:27-47`); background jobs have no request_id.

---

## 3. Type cache — there is NO `esi_type_cache` DB table

**Type/group resolution is Valkey-JSON-cached only; nothing durable in Postgres.**

### The cache mechanism — `core/esi_client_class.py:192-261`
- `_get_esi_object(path, cache_seconds=86_400)` (192-253): GET a single ESI **object** endpoint; cache the raw response body in Valkey under key **`esi-object:{path}`** with a **plain 24-hour TTL** (not ETag). Retries 5xx/network 3× with backoff; raises `ESIRequestFailedError` on non-2xx.
- `get_universe_type(type_id)` (255-257) → `GET /v3/universe/types/{type_id}/` → dict incl. `name`, `group_id`, `market_group_id`, and (from ESI, **not captured**) `published`.
- `get_universe_group(group_id)` (259-261) → `GET /v1/universe/groups/{group_id}/` → dict incl. `name`, `category_id`.

### "Is `type_id` a published ship?" — computed at ingestion, denormalized onto rows
`_enrich_items_and_find_ships` (`background_aggregation.py:384-455`):
- `SHIP_CATEGORY_ID = 6` (EVE static "Ship" category, line 384).
- Resolves type→group→category with bounded concurrency (`ENRICHMENT_CONCURRENCY = 8`, line 48), degrading a failed/odd id to NULL enrichment (never kills the run).
- Writes onto each item dict: `type_name = info.get("name")`, `market_group_id = info.get("market_group_id")`, `category = "ship" if category_id==6 else None` (450-452).
- A contract is flagged a ship contract iff it has an **`is_included`** item whose category is ship (453-454) → `Contract.is_ship_contract = True` (348-355).

**Consequence for M3:** there is **no queryable type table** to answer "is arbitrary `type_id` a published ship" outside of types that have appeared in contracts. The only local signals are `ContractItem.category == 'ship'`, `ContractItem.type_name`, `ContractItem.market_group_id`, and `Contract.is_ship_contract`. The ESI `published` flag is **not stored anywhere**. If the matcher needs ship metadata for a `type_id` the user picked but which isn't in any current contract, it must call ESI (`get_universe_type`, Valkey-cached) or build its own type table.

### `EsiMarketGroupCache` — a DEFINED-BUT-DEAD table
`models/contracts.py:21-34`, table `esi_market_group_cache`:
`market_group_id` (PK Integer), `name`, `description`, `parent_group_id` (self-FK, nullable), `raw_esi_response` (JSON). **No code reads or writes it** — grep shows it only in the model, `models/__init__.py`, and `alembic/env.py` metadata import. It is a reserved/empty shell, not a live type cache.

### Restart behavior (ENV-2)
- The **Valkey `esi-object:*` cache is NOT wiped on restart** (Redis persists; entries live 24 h by TTL). Type/group lookups are near-free on subsequent runs.
- The **Postgres tables ARE dropped+recreated** on dev boot when `ENVIRONMENT == "development"` AND `DB_RECREATE_ON_STARTUP` is true (`main.py:139-165`, `create_db_tables`, fail-closed gate). So `contracts`, `contract_items`, `users`, `esi_market_group_cache` rows are wiped every dev restart; the ESI JSON cache in Valkey survives. **M3 tables will be dropped+recreated too** (they're `Base` models picked up by `metadata.create_all`) — any user-owned watchlist/saved-search rows created in dev vanish on restart.

---

## 4. Contract + ContractItem models (matcher-relevant columns)

**File:** `models/contracts.py`.

### `Contract` — table `contracts` (lines 37-83)
| column | type | notes for matching |
|---|---|---|
| `contract_id` | `BigInteger` PK, `autoincrement=False` | ESI-supplied id |
| `title` | `String` nullable | indexed (`ix_contracts_title`); title-text match |
| `price` | `Numeric` **NOT NULL** | ISK price; ingestion writes `c.get("price")` |
| `collateral` | `Numeric` **NOT NULL** | |
| `status` | `String` **NOT NULL** | **UNRELIABLE**: public ESI feed carries no status; ingestion stores `c.get("status", "unknown")` → effectively always `"unknown"`. Do **not** use as an outstanding signal. |
| `type` | `String` **NOT NULL** | `"item_exchange"`, `"auction"`, or `"courier"` (mapped verbatim from ESI). Only `item_exchange`/`auction` get items fetched (line 300). |
| `issuer_id` / `issuer_corporation_id` | `Integer` NOT NULL | |
| `start_location_id` | `BigInteger` nullable | station/structure id; location match granularity that works |
| `start_location_system_id` | `Integer` nullable | **NEVER populated by ingestion** — always NULL on real data (`system_ids` filter is dead) |
| `start_location_region_id` | `Integer` nullable | populated from fetch region `_hb_region_id`; the working region signal |
| `end_location_id` | `BigInteger` nullable | courier only |
| `for_corporation` | `Boolean` NOT NULL | |
| `date_issued` | `DateTime(tz)` NOT NULL | indexed; "new since" proxy |
| `date_expired` | `DateTime(tz)` NOT NULL | indexed; **the outstanding-window signal — matcher must filter `date_expired > now()`** |
| `date_completed` | `DateTime(tz)` nullable | |
| `reward` | `Float` nullable | courier reward |
| `volume` | `Float` nullable | |
| `start_location_name` / `issuer_name` / `issuer_corporation_name` | `String` nullable | denormalized names |
| `is_ship_contract` | `Boolean` default False | **indexed** (`ix_contracts_is_ship_contract`); set by enrichment |
| `item_processing_status` | `String` default `'PENDING_ITEMS'` | **indexed**; values `'PENDING_ITEMS'`/`'COMPLETED'`/`'ENRICHMENT_INCOMPLETE'` |
| `items_last_fetched_at` | `DateTime(tz)` nullable | **declared but NEVER written** by ingestion |
| `contract_esi_etag` | `String` nullable | **declared but NEVER written** by ingestion |

`items` relationship → `ContractItem`, `cascade="all, delete-orphan"` (line 68).
Indexes (70-80): `(type,status)`, `start_location_name`, `title`, `is_ship_contract`, `price`, `date_issued`, `collateral`, `volume`.

### `ContractItem` — table `contract_items` (lines 86-114)
| column | type | notes |
|---|---|---|
| `record_id` | `BigInteger` PK, `autoincrement=True` | **but ingestion writes ESI's `i["record_id"]`** — upsert conflict key is this ESI-supplied value |
| `contract_id` | `BigInteger` FK→`contracts.contract_id` NOT NULL | indexed |
| `type_id` | `Integer` NOT NULL | **indexed** (`ix_contract_items_type_id`); the matcher's primary join key |
| `quantity` | `Integer` NOT NULL | |
| `is_included` | `Boolean` NOT NULL | true = item is being offered (vs. requested) |
| `is_singleton` | `Boolean` NOT NULL | |
| `is_blueprint_copy` | `Boolean` nullable | **indexed**; the `is_bpc` filter |
| `raw_quantity` | `Integer` nullable | **indexed**; BPC runs (-1 = original) |
| `type_name` | `String` nullable | denormalized from `get_universe_type` |
| `category` | `String` nullable | `'ship'` or NULL (enrichment) |
| `market_group_id` | `Integer` nullable | denormalized |

### Identifying a "current/outstanding" contract
There is **no reliable status column**. The `/contracts/public/{region}/` feed returns only currently-listed contracts, and ingestion stores `status="unknown"`. **Ingestion UPSERTS and NEVER DELETES** (see §6). Therefore:
- **Outstanding ⇒ present in `contracts` AND `date_expired > now()`** (and optionally `date_completed IS NULL`).
- Row presence alone is NOT "outstanding" in production — completed/expired/vanished contracts linger until (if ever) purged. In dev the drop/recreate masks this. The matcher **must** date-filter, not trust presence.

---

## 5. Valkey cache client

**File:** `core/cache.py`, accessed via `core/dependencies.py`.

- App-level client init (`cache.py:36-51`, `CacheManager.initialize`):
  ```python
  from_url(cache_url, encoding="utf-8", decode_responses=True)
  ```
  **`decode_responses=True`** — GET/GETEX etc. return `str`, not bytes. PINGed at startup; stored on **`app.state.redis`** (`init_cache`, 73-82).
- Services/routes get it via **`core/dependencies.get_cache(request) -> Redis`** (`dependencies.py:11-22`) → returns `request.app.state.redis` or raises **503** if unavailable. Session/auth/ESI-DI all funnel through this.
- **Client inconsistency to know:** background jobs and the ESI client that they instantiate build **their own** clients with `aioredis.from_url(str(settings.CACHE_URL))` and **no `decode_responses`** (bytes-mode) — see `background_aggregation.py:87` (lock) and `esi_client_class.py:71-73` (`__aenter__`). A matcher job that reuses `get_cache`'s client gets `str`; one that mints its own like the aggregation job gets `bytes`. Pick deliberately.

### Existing key-naming conventions
| key pattern | source | client mode |
|---|---|---|
| `session:{sid}` | `core/session.py:15` (`_session_key`) | app client (str) |
| `sso_state:{state}` | `api/auth.py:105,149` | app client (str) |
| `etag:{path}?page={n}` / `data:{path}?page={n}` | `esi_client_class.py:97-98` | job/DI client (bytes) |
| `esi-object:{path}` | `esi_client_class.py:201` (type/group cache) | job/DI client (bytes) |
| `hangar-bay:aggregation:lock` | `background_aggregation.py:26` | ad-hoc bytes client |
| `apscheduler.*` | `RedisJobStore` (default prefix) | APScheduler-managed |
| `hb_sso_state` | browser cookie (not Redis) | n/a |

Suggested M3 keys should adopt a namespace prefix (e.g. `hangar-bay:matcher:lock`, `session:`-style `watchlist:...`) to stay consistent — note the two existing styles: bare `session:`/`sso_state:` vs. namespaced `hangar-bay:aggregation:`.

---

## 6. Ingestion cadence, dev limit, upsert semantics — matcher-affecting facts

### Cadence / limits (all in `core/config.py:52-58`)
- `AGGREGATION_SCHEDULER_INTERVAL_SECONDS` default **3600** (1 h); runs immediately at boot (`next_run_time=now`).
- `AGGREGATION_REGION_IDS` default **`[10000002]`** (The Forge / Jita). JSON-list or CSV parsing via `parse_aggregation_region_ids` validator (ENV-1).
- `AGGREGATION_DEV_CONTRACT_LIMIT` default **100**, marked `# DO NOT REMOVE UNLESS INSTRUCTED BY USER`. Truncates the aggregated list to 100 before processing (`background_aggregation.py:183-187`). **In dev only ~100 contracts (one region) exist — a watchlist matcher has a tiny test surface.** Set to `None`/`0` to disable.

### Upsert / delete semantics
- Contracts and items are written via **`bulk_upsert`** (`services/db_upsert.py`) = `INSERT ... ON CONFLICT DO UPDATE`, and crucially **only updates the columns the caller actually supplied** (`db_upsert.py:33-49`) so enrichment-maintained columns aren't clobbered to defaults on ETag-304 re-ingest.
- **There is NO deletion / pruning anywhere in the pipeline** (grep-confirmed): contracts that disappear from ESI, expire, or complete are never removed. Rows accumulate in production. → the matcher must filter on `date_expired > now()`.
- Contract upsert conflict key: `contract_id`. Item upsert conflict key: `record_id` (ESI-supplied). asyncpg 32767-bind-param cap handled by `UPDATE_ID_CHUNK_SIZE = 1000` for the ship/status back-fills; contract batch 500, item batch 50.

### No "last successful run" marker
No timestamp/outcome of the last aggregation run is persisted (confirmed: no `last_run`/`last_success`/`high_water` in the service; `items_last_fetched_at` and `contract_esi_etag` columns exist but are never written). The observability spec explicitly defers this: **`design/specifications/observability-spec.md` §2.5** ("Ingestion freshness / data-staleness indicator") says the system *should* record last-successful-run timestamps per region/global but this is unbuilt. A matcher that wants "new since last run" must maintain its own high-water mark (Redis key or a small table), or scan by `date_issued`.

---

## Risks / constraints the M3 design MUST account for

1. **No status truth + no deletion ⇒ matcher must gate on `date_expired > now()`** (and likely `date_completed IS NULL`). `Contract.status` is always `"unknown"` from the public feed; row presence ≠ outstanding in production (dev's drop/recreate hides this). This is the single biggest correctness trap for a watchlist-vs-contracts matcher.

2. **No last-successful-ingestion timestamp exists** (deferred per observability-spec §2.5). "New contracts since last check" has no ready anchor — the matcher must own a high-water mark (per-user or global), e.g. `max(date_issued)` seen, or a Redis/DB cursor. Note `date_issued` is set-by-issuer time, not ingestion time, so late-arriving older contracts can slip a naive `date_issued > cursor` window.

3. **Use a SEPARATE lock, not the aggregation lock.** Ingestion holds `hangar-bay:aggregation:lock` (30-min TTL) for a full run. A 15-30 min matcher must use its own key (e.g. `hangar-bay:matcher:lock`) with its own TTL sized to its worst-case runtime; reusing the aggregation key would serialize the two and cause mutual skips.

4. **Jobs don't chain.** APScheduler fires ingestion and the matcher on independent clocks (`add_job` per §1). The matcher reads whatever ingestion has committed. Ingestion commits **once at the end** of a run (`background_aggregation.py:191`), so a concurrent matcher sees a consistent pre-commit snapshot — but it may be matching last cycle's data. If "match only against this cycle's new contracts" matters, design an explicit cursor/handoff; don't assume ordering.

5. **RedisJobStore pickles job func + args.** The matcher job function must be top-level importable and its args picklable (mirror `run_aggregation_job(service)` where `ESIClient`/`ContractAggregationService` are picklable because clients are created lazily in `__aenter__`). A closure or a job carrying a live DB/Redis connection will fail to persist.

6. **New M3 models need a `Base` import to exist in dev.** Dev schema comes from `Base.metadata.create_all` (`main.py:create_db_tables`), NOT Alembic. A new model file must be imported so its table registers on `Base.metadata` — follow `models/__init__.py` (imports `User`, `Contract`, ...) and `main.py:26` (`from .models import contracts`). Watchlist/saved-search rows FK to `users.id` (`models/user.py:15`, `Integer` PK autoincrement; `character_id` is `BigInteger`). Alembic exists (`app/backend/src/alembic/`, linear head `3fa2eefb2d7e`) but is **not run on dev boot** and appears out of step with current models — decide explicitly whether M3 adds migrations (needed for any real deploy) or rides drop/create.

7. **Enrichment degrades to NULL/False on ESI hiccups.** `is_ship_contract` / `ContractItem.category` can be False/NULL when type/group resolution transiently fails (`item_processing_status == 'ENRICHMENT_INCOMPLETE'`, `background_aggregation.py:357-382`). A matcher filtering on `category == 'ship'` or `is_ship_contract` can miss a genuinely-ship contract that failed enrichment this cycle. `type_id` (raw, always present) is the robust match key; ship/category are best-effort denormalizations.

8. **`decode_responses` mismatch.** App client (`get_cache`) returns `str`; job-minted clients return `bytes`. Choose one intentionally in the matcher and don't mix (the ESI etag path already has to `.decode()` because of this).

9. **Type metadata is not durably queryable.** No `esi_type_cache` table; only Valkey `esi-object:{path}` JSON (24 h TTL) plus per-contract denormalized `type_name`/`category`/`market_group_id`. `EsiMarketGroupCache` is a dead/empty table. Answering "is this `type_id` a published ship" for a type the user selected but that isn't in any live contract requires an ESI call (Valkey-cached) or a new type table. ESI's `published` flag is currently discarded.

10. **Location granularity: region works, system does not.** `start_location_system_id` is never populated (always NULL). Matcher location criteria should use `start_location_region_id` (populated) or `start_location_id` (station/structure), not system.

11. **Dev dataset is tiny** (100 contracts, one region). Design test/fixtures for the matcher accordingly; don't rely on production-scale variety being present locally.

12. **`/me/*` auth-gate pattern to reuse:** `Depends(get_current_session)` (`core/session.py:116-123`) 401s on missing/invalid session and returns the session dict `{user_id, character_id, character_name, created_at}`; `get_optional_session` returns `None` instead. `/me` (`api/auth.py:296-300`) reads from the session payload with **no DB hit**. F005/6/7 CRUD routes will need `user_id` from `get_current_session` to scope rows — the session already carries `user_id`, so no extra DB lookup is needed to identify the owner. Routers mount **bare** (no `/api/v1`, PROXY-1); add a new `APIRouter(...)` and `app.include_router(...)` in `main.py` like `me_router`.
