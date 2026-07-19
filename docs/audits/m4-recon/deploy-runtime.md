# M4 Recon — Backend Deploy & Runtime

ABOUTME: Read-only recon of how the Hangar Bay backend RUNS, for the M4 (production readiness / deployment) designer.
ABOUTME: Facts only — exact startup behavior, the full Settings inventory, scheduler/lock mechanics, launch surface, and container/env contract. No code was modified.

Scope: `app/backend/`. All paths below are relative to
`/Users/sam/Code/hangar-bay/.claude/worktrees/hangar-bay-frontend-rebuild-2e4fe7/`.
Cross-cutting sibling recon: `docs/audits/m3-recon/backend-data-auth.md` (data model, sessions,
the ENV-2-wipe-vs-surviving-session hazard, and the "Alembic is vestigial" finding — all still load-bearing for M4).

---

## 1. Startup / lifespan behavior — what runs on every boot

File: `app/backend/src/fastapi_app/main.py`. The `lifespan` async context manager (`main.py:37-68`)
runs this sequence on **every** boot, in order:

1. `setup_logging(settings)` (`main.py:42`) — structlog to **stdout**, JSON renderer, level from `LOG_LEVEL` (`core/logging.py:73,87,93`).
2. `warn_if_sso_unconfigured()` (`main.py:43`) — dev-only log warning; no-op when `ENVIRONMENT != "development"` (`main.py:155-156`).
3. `await create_db_tables()` (`main.py:45`) — **the destructive drop+create (ENV-2/ENV-3), see gate below.**
4. `init_http_client(app)` (`main.py:46`) — shared httpx client on `app.state`.
5. `await init_cache(app)` (`main.py:47`) — connects to Valkey via `CACHE_URL` and `ping()`s; stores client on `app.state.redis` (`core/cache.py:44,47,73-78`). **No FLUSHDB** — cache/sessions survive a restart.
6. Scheduler bring-up (`main.py:50-57`): `create_scheduler(app, settings)`, construct `ESIClient(settings)` + `ContractAggregationService`, `add_aggregation_job(...)`, then `scheduler.start()`. **The aggregation job is registered with `next_run_time=datetime.now()` so ingestion fires immediately on startup** (`core/scheduler.py:43`), not just on the interval.

Shutdown (`main.py:62-68`): shuts the scheduler down if running, closes http client and cache.

### The destructive recreate IS gated (fail-closed) — quote

`create_db_tables()` (`main.py:128-150`) is the only schema path in the app runtime. It is gated on
**two** conditions and skips unless BOTH hold:

```python
if settings.ENVIRONMENT != "development" or not settings.DB_RECREATE_ON_STARTUP:
    logger.info(
        "Skipping destructive create_db_tables (ENVIRONMENT=%s, DB_RECREATE_ON_STARTUP=%s).",
        settings.ENVIRONMENT, settings.DB_RECREATE_ON_STARTUP,
    )
    return
logger.info("Dropping and recreating database tables...")
async with async_engine.begin() as conn:
    await conn.run_sync(Base.metadata.drop_all)
    await conn.run_sync(Base.metadata.create_all)
```

`main.py:133-138` documents the intent: **secure-by-default**. `ENVIRONMENT` defaults to `"production"`
when unset (`core/config.py:21`), so an operator who forgets to set it never trips the drop path even
if `DB_RECREATE_ON_STARTUP` was copied as true. Recreate requires `ENVIRONMENT == "development"` AND
`DB_RECREATE_ON_STARTUP` true, both explicit. **Production safety of the drop is therefore already handled.**

### What is NOT gated — the production gap

- **The aggregation job runs unconditionally in every environment.** `add_aggregation_job` + `scheduler.start()` (`main.py:56-57`) are outside any `ENVIRONMENT` guard. In production the scheduler still starts and ingestion still fires immediately (`next_run_time=datetime.now()`, `core/scheduler.py:43`) and every `AGGREGATION_SCHEDULER_INTERVAL_SECONDS` (default 3600). This is intended (it's the product's data pipeline) but see §3 for the multi-instance implication.
- **`AGGREGATION_DEV_CONTRACT_LIMIT` is NOT keyed on `ENVIRONMENT`** (`core/config.py:55-58`, default 100). It's a plain setting; a prod deploy that inherits the default would silently cap ingestion at 100 contracts. Must be explicitly set to `None`/`0` for full ingestion. Flagged `# DO NOT REMOVE UNLESS INSTRUCTED BY USER`.
- **Two dev/test endpoints ship in the app object unconditionally:** `/cache-test` (`main.py:168-186`, carries its own `# CASCADE-PROD-CHECK: Remove or disable this endpoint for production` comment) and `/metrics` (Prometheus, always enabled — `should_respect_env_var=False`, `main.py:106,113`). `/metrics` is unauthenticated and exposes request-level metrics to anyone who can reach it.
- **`/health` (`main.py:123-125`) is a static `{"status": "ok"}`** — it does NOT check DB or cache connectivity. Not usable as a real readiness/liveness probe for a load balancer that needs to know if Postgres/Valkey are reachable. (The deferred `/meta/status` + readiness/freshness work is spec'd in `design/specifications/observability-spec.md` §2.5 per pitfall ESI-1 — see MEMORY `esi-spring-cleaning-2026`.)
- **The global exception handler returns a generic 500** (`main.py:81-97`) and logs via structlog — fine for prod.

---

## 2. Settings inventory — `core/config.py`

File: `app/backend/src/fastapi_app/core/config.py`. Single consolidated `Settings(BaseSettings)`
(`config.py:11`). `model_config` (`config.py:88-92`): `env_file = app/backend/src/.env`,
`extra="ignore"` (ENV-4 — unknown `.env`-FILE keys don't crash boot). Instantiated as a
module-level singleton `settings = Settings()` (`config.py:95`); `get_settings()` returns it (`config.py:98-100`).

| Field | Type | Default | Line | Prod notes |
|---|---|---|---|---|
| `ENVIRONMENT` | `Literal["development","production","test"]` | `"production"` | 21 | **Secure-by-default.** Gates the destructive recreate (§1), SQL echo (`db.py`), cookie `Secure` flag (`api/auth.py`), SSO-unconfigured warning. Leave unset → `"production"`. |
| `LOG_LEVEL` | `str` | `"INFO"` | 22 | Feeds structlog level (`core/logging.py:93`). Safe. |
| `DB_RECREATE_ON_STARTUP` | `bool` | `False` | 28 | Fail-closed opt-in for drop/create. Default `False` is prod-safe; `.env.example` sets `"true"` for dev. |
| `ESI_BASE_URL` | `str` | `"https://esi.evetech.net"` | 31 | Safe default. |
| `ESI_USER_AGENT` | `str` | **REQUIRED (no default)** — `Field(...)` | 32 | Backend refuses to start without it. Must be provisioned in prod. |
| `ESI_TIMEOUT` | `float` | `20.0` | 33 | Safe. |
| `ESI_CLIENT_ID` | `str` | `""` | 36 | Empty ⇒ SSO login/callback 503. Prod must set to enable auth. |
| `ESI_CLIENT_SECRET` | `SecretStr` | `SecretStr("")` | 37 | Secret. Must be provisioned; keep out of logs/CLI. |
| `ESI_SSO_AUTHORIZE_URL` | `str` | login.eveonline.com/v2/oauth/authorize | 38 | Safe default. |
| `ESI_SSO_TOKEN_URL` | `str` | login.eveonline.com/v2/oauth/token | 39 | Safe default. |
| `ESI_SSO_JWKS_URI` | `str` | login.eveonline.com/oauth/jwks | 40 | Safe default. |
| `ESI_SSO_CALLBACK_URL` | `str` | `https://localhost:5173/api/v1/auth/sso/callback` | 43 | **Dev-only value.** Must match the EVE dev-portal registration char-for-char; **prod requires the real public callback URL** and a matching portal registration. |
| `FRONTEND_ORIGIN` | `str` | `https://localhost:5173` | 44 | **Dev-only value.** Prod must set the real origin (used for post-login redirects). |
| `SESSION_COOKIE_NAME` | `str` | `"hb_session"` | 47 | Safe. |
| `SESSION_IDLE_TTL_SECONDS` | `int` | `604_800` (7d) | 48 | Safe. |
| `SESSION_ABSOLUTE_TTL_SECONDS` | `int` | `2_592_000` (30d) | 49 | Safe. |
| `TOKEN_CIPHER_KEYS` | `SecretStr` | `SecretStr("")` | 50 | **Fernet keyring, comma-separated (first=primary).** Empty ⇒ SSO 503. Prod must provision; **rotating/losing this breaks decryption of all stored ESI tokens** (undecryptable vault → forced reauth). |
| `AGGREGATION_SCHEDULER_INTERVAL_SECONDS` | `int` | `3600` | 53 | Safe. |
| `AGGREGATION_REGION_IDS` | `List[int]` | `[10000002]` (The Forge) | 54 | **ENV-1 complex field** — see below. |
| `AGGREGATION_DEV_CONTRACT_LIMIT` | `int \| None` | `100` | 55 | **NOT env-gated;** prod must set `None`/`0` to disable the cap (§1). |
| `DATABASE_URL` | `str` | **REQUIRED (no default)** — `Field(...)` | 61 | asyncpg DSN. Must be provisioned; secret (embeds password). |
| `CACHE_URL` | `str` | **REQUIRED (no default)** — `Field(...)` | 62 | Valkey/Redis DSN. Must be provisioned; used by BOTH cache AND the APScheduler `RedisJobStore` (§3). |
| `DATABASE_URL_TESTS` | `Optional[PostgresDsn]` | `None` | 63 | Test-only (conftest requires it). |
| `CACHE_URL_TESTS` | `Optional[AnyUrl]` | `None` | 64 | Test-only. |

**Required-with-no-default (boot fails if absent):** `ESI_USER_AGENT`, `DATABASE_URL`, `CACHE_URL` (all `Field(...)`). Everything else has a default.

### ENV-1 implication for prod env-var provisioning

`AGGREGATION_REGION_IDS` is a `List[int]` and pydantic-settings **JSON-decodes complex fields before**
the `mode="before"` validator runs (`config.py:66-86`, ENV-1). Through real env-var/dotenv sources
**only the JSON-list form works** — `AGGREGATION_REGION_IDS=[10000002]`. A bare int or comma-separated
string reaches the field only on direct Python construction (tests), not via env. **Any prod deployment
that sets this via an env var MUST use the JSON-array string form** or boot crashes. The `.env` file already
uses the correct form (`app/backend/src/.env:7`).

---

## 3. Scheduler + ingestion concurrency — `core/scheduler.py` + `services/background_aggregation.py`

### How the scheduler starts

- `create_scheduler` (`core/scheduler.py:17-30`) builds an `AsyncIOScheduler` whose **jobstore is a Redis-backed `RedisJobStore`** parsed from `CACHE_URL` (host/port/db/password via `urlparse`, `scheduler.py:19-27`). So job state is shared across any process pointing at the same Valkey.
- `add_aggregation_job` (`scheduler.py:33-48`) registers **one** job: `id="aggregate_public_contracts"`, `trigger="interval"`, `seconds=AGGREGATION_SCHEDULER_INTERVAL_SECONDS`, `replace_existing=True`, `misfire_grace_time=300`, `next_run_time=datetime.now()` (fires immediately on boot). The job callable is `run_aggregation_job(aggregation_service)` (`services/scheduled_jobs.py:13-25`), which calls `aggregation_service.run_aggregation()` and swallows exceptions with a log.

### Two-instance / deploy-overlap behavior — there IS a lock, at the run level

`ContractAggregationService.run_aggregation` wraps its work in `self._concurrency_lock()`
(`services/background_aggregation.py:141`), a Redis-backed distributed lock — **this is the real
cross-instance guard, not APScheduler:**

- Lock key `"hangar-bay:aggregation:lock"`, TTL `1800s` (30 min) (`background_aggregation.py:26-28`).
- Acquire: `redis_client.set(KEY, lock_token, nx=True, ex=1800)` — atomic SET NX (`background_aggregation.py:93-95`). A **unique fencing token** `uuid.uuid4().hex` identifies this runner (`background_aggregation.py:88-90`).
- If not acquired: logs `"Contract aggregation job is already running. Skipping this run."` and raises `ConcurrencyLockError`, caught upstream as a clean skip (`background_aggregation.py:96-102,194-196`).
- Release: **compare-and-delete via Lua** — only deletes if the stored value still equals this runner's token (`_RELEASE_LOCK_LUA`, `background_aggregation.py:34,107-120`). Guards against a TTL expiry mid-run causing one runner to drop another's lock.

**So: if two backend instances run concurrently (rolling deploy overlap, multiple replicas), they do NOT
double-ingest.** The first to `SET NX` wins the run; the others log "already running" and skip cleanly.
The lock is TTL-bounded (self-heals after 30 min if a holder crashes) and fencing-tokened (per ENV-3, hardened since commit `d16d145`).

**Caveats the M4 designer must weigh:**
- **The 30-min TTL is a hard ceiling on run length.** A run exceeding 1800s loses its lock and a second runner can start; the token-mismatch release path handles it but concurrent runs become possible. Full-region prod ingestion (no `AGGREGATION_DEV_CONTRACT_LIMIT` cap) could plausibly exceed 30 min — needs validation.
- **Every replica boots with `next_run_time=datetime.now()`**, so every new instance attempts an immediate run on startup; the lock reduces this to one actual run, but N replicas = N lock-contention attempts at every deploy.
- **`RedisJobStore` is shared across replicas** — all schedulers see the same single job. This is coherent, but there is no leader-election; each scheduler independently fires the interval and relies entirely on the Redis lock for mutual exclusion. Designing for a **single dedicated ingestion worker** (scheduler enabled on one process, disabled on web replicas) would be cleaner than N schedulers racing a lock, but that split does not exist today — the scheduler is unconditionally started in `lifespan` for every process.

---

## 4. How the server is launched — no container image exists

### pdm scripts (`app/backend/pyproject.toml:36-40`)

```
lint           = "flake8 ."
format         = "black ."
dev            = "uvicorn fastapi_app.main:app --reload --host 0.0.0.0 --port 8000 --app-dir src"
export-openapi = "python src/export_openapi.py"
```

- **The only server launch command is `dev`** — single-process uvicorn with `--reload`, port 8000, `--app-dir src`. **There is NO production launch script, no gunicorn, no `--workers`, no uvicorn worker config anywhere.** `uvicorn[standard]>=0.34.3` is a dependency (`pyproject.toml:8`) but only invoked via the dev script. `requires-python = ">=3.14"`.
- No `pdm run start`/`prod`/`serve`. A prod deploy must supply its own process manager / worker model. **Note the multi-worker interaction with §3:** running uvicorn/gunicorn with `--workers N` would start N schedulers (one per worker process), each racing the aggregation lock — the same replica-contention concern applies within a single host.

### Dockerfile — NONE

`find -iname "Dockerfile*"` across the repo (excluding node_modules) returns **zero results.** There is
no container image for the backend (or frontend) anywhere. Building/packaging the app for deployment is a
**genuine M4 gap** the designer must fill.

### compose files — dev/observability only, NOT an app deployment

`app/backend/docker/` contains three compose files, none of which define the FastAPI app service:

- **`compose.yml`** (`compose.yml:35-46`) — defines **only three bridge networks** (`hb-public-net`, `hb-data-tier-net`, `hb-monitoring-net`) for Zero-Trust microsegmentation. **No services.** The header comments describe an intended topology where the FastAPI container bridges all three networks, but that container is never defined in any compose file.
- **`compose.dependencies.yml`** — the data tier:
  - `postgres_db`: image `postgres:16-alpine`, container `hangar_bay_postgres`, port `5432:5432`, healthcheck `pg_isready -U hangar_bay_user -d hangar_bay_dev` (interval 10s/timeout 5s/retries 5), named volume `postgres_data`, `restart: unless-stopped`, on `hb-data-tier-net` (`compose.dependencies.yml:29-48`).
  - `valkey_cache`: image `valkey/valkey:7.2-alpine`, container `hangar_bay_valkey`, port `6379:6379`, healthcheck `valkey-cli ping`, named volume `valkey_data`, `restart: unless-stopped`, on `hb-data-tier-net` (`compose.dependencies.yml:50-64`).
  - **Credentials are hardcoded dev defaults** (`POSTGRES_USER: hangar_bay_user`, `POSTGRES_PASSWORD: hangar_bay_password`, `POSTGRES_DB: hangar_bay_dev`) with inline `# IMPORTANT: Change these...` / `# TODO: Consider using Docker secrets or .env for production-like setup` comments (`compose.dependencies.yml:35-38`). **Dev-only; not prod-usable as-is.**
- **`compose.observability.yml`** — `prometheus:v3.4.2` (port 9090, config-file mount) + `grafana:12.0.2` (port 3000), on `hb-monitoring-net` (`compose.observability.yml:17-41`). Grafana has no admin-password config. Dev-only.

**Assessment:** pinned image versions and healthchecks are good building blocks, but these compose files
are explicitly local-dev scaffolding (headers say "for local development", "Change these default credentials",
"For production: More robust volume management, backup strategies, and security hardening"). **There is no
prod-usable app container, no app service definition, and secrets are hardcoded.** M4 needs to author the app
image + a prod-grade compose/orchestration story from scratch.

---

## 5. Documented env contract — `.env.example` vs actual `.env`

`app/backend/.env.example` (note: lives at `app/backend/`, but the app LOADS from `app/backend/src/.env`
per `config.py:89` and ENV-1 — the example and the real file are in **different directories**). Contents:

- `ENVIRONMENT="development"`, `LOG_LEVEL="INFO"`, `DB_RECREATE_ON_STARTUP="true"` (dev workflow).
- Required-no-default trio documented: `DATABASE_URL`, `CACHE_URL`, `ESI_USER_AGENT` (`.env.example:12-15`).
- Test DSNs: `DATABASE_URL_TESTS`, `CACHE_URL_TESTS`.
- EVE SSO block: `ESI_CLIENT_ID`, `ESI_CLIENT_SECRET`, `TOKEN_CIPHER_KEYS` — all empty, with a documented key-gen recipe (`.env.example:21-31`).

The actual dev `app/backend/src/.env` (`src/.env:1-9`) sets `ENVIRONMENT=development`,
`AGGREGATION_REGION_IDS=[10000002]` (JSON form — ENV-1), `AGGREGATION_DEV_CONTRACT_LIMIT=1000`, and
**does NOT set** `DB_RECREATE_ON_STARTUP`, `ESI_CLIENT_ID`, `ESI_CLIENT_SECRET`, or `TOKEN_CIPHER_KEYS`
(so SSO is 503 and the destructive recreate is OFF in this particular checkout despite ENVIRONMENT=development).

**Prod contract gap:** `.env.example` documents no `ESI_SSO_CALLBACK_URL`/`FRONTEND_ORIGIN` overrides,
no `AGGREGATION_DEV_CONTRACT_LIMIT` disable line, and no production-shaped example. The designer should
produce a prod env template covering: the real callback/origin, the token keyring, ingestion cap disabled,
`ENVIRONMENT` explicit-or-omitted decision, and secret-injection mechanism (files/secret-store, never CLI flags per the universal no-secrets-in-flags rule).

---

## 6. Relevant pitfalls — verbatim (short)

From `docs/pitfalls/implementation-pitfalls.md`:

**ENV-1** (`:118-122`): "A `List[int]` settings field only accepts a JSON list
(`AGGREGATION_REGION_IDS=[10000002]`). A bare int or comma-separated string crashes at startup even if a
field validator claims to handle it — pydantic-settings JSON-decodes complex types first." Also: "the
backend loads env from `app/backend/src/.env` (not next to `.env.example`) and requires `ESI_USER_AGENT`."

**ENV-2** (`:126-130`): "`main.py` drops and recreates all tables on every startup and immediately re-runs
aggregation (dev limit: 100 contracts from configured regions). Real data appears minutes after boot, not
instantly." Lesson: don't diagnose an empty contract list as a frontend bug until ingestion has run.

**ENV-3** (`:134-140`): "Every backend source edit triggers a reload, which drops/recreates all tables
(ENV-2) and starts a fresh aggregation run; killing a run mid-flight ... can strand the Valkey lock so the
NEXT startup run logs 'already running' and silently skips." Fix: clear the lock
(`valkey-cli DEL "hangar-bay:aggregation:lock"`), `touch main.py`, one clean cycle. **"The lock is
TTL-bounded (30 min) and fencing-tokened since `d16d145`, so production self-heals; this is purely a
dev-loop trap."**

**ENV-4** (`:144-152`): "Without `extra="ignore"` in `model_config`, any key present in `.env` that is NOT
a declared field aborts construction at import — crashing boot. ... unknown ENV VARS are ignored ..., but
unknown `.env`-FILE keys are not — this trap is `.env`-file-specific." Fix: keep `extra="ignore"`; new
config always adds the field AND documents it in `.env.example`.

**PROXY-1** (`:70-75`): "The backend mounts routes bare (e.g. `/contracts/`) and the dev proxy adds/strips
`/api/v1`. Requesting `/contracts` (no slash) triggers a 307 whose `Location` lacks the proxy prefix, so
the redirect escapes to the SPA origin and fails." Fix: "Clients call schema paths verbatim, including
trailing slashes; the openapi-fetch client's `baseUrl` owns the `/api/v1` prefix." **M4 relevance: the
`/api/v1` prefix and trailing-slash handling belong to the deploy edge / reverse proxy — the production
edge must replicate what the Vite dev proxy does today (strip `/api/v1`, preserve trailing slashes), or
routing breaks. There is no CORS config; frontend and backend are same-origin through that proxy/edge.**

(ENV-5 is SUPERSEDED — backend is now on Python 3.14 / FastAPI 0.139. ESI-1: all ESI routes pin explicit
versions; upstream-status/readiness work is deferred, spec'd in observability-spec.md §2.5.)

---

## Quick-reference: production-readiness gaps surfaced

| Area | State today | Gap for M4 |
|---|---|---|
| Destructive drop/create | Fail-closed gated on `ENVIRONMENT==development` AND `DB_RECREATE_ON_STARTUP` (`main.py:140`) | **Safe.** But no migration system for durable prod schema (Alembic is stale — see m3-recon §6). |
| Server launch | Only `pdm run dev` (uvicorn `--reload`, 1 proc) | **No prod launch cmd, no workers, no gunicorn.** |
| Container image | **None** (`find Dockerfile` = 0) | Author backend (and frontend) images. |
| Compose | Networks + Postgres/Valkey/Prometheus/Grafana, all dev-only, hardcoded creds | No app service; not prod-usable. |
| Health check | Static `{"status":"ok"}` (`main.py:123-125`) | No DB/cache probe; real readiness/liveness spec'd but unbuilt (observability-spec §2.5). |
| Ingestion in prod | Scheduler + immediate run unconditionally started in `lifespan`; Redis lock prevents double-ingest | No leader election; 30-min lock TTL caps run length; `AGGREGATION_DEV_CONTRACT_LIMIT=100` not env-gated. |
| Secrets | `ESI_CLIENT_SECRET`, `TOKEN_CIPHER_KEYS`, DB/cache DSNs all via env/`.env` | Need prod secret-injection story (files/store, not CLI flags). |
| Dev endpoints | `/cache-test` (marked CASCADE-PROD-CHECK) + unauth `/metrics` ship in the app object | Remove/guard `/cache-test`; decide on `/metrics` exposure/auth. |
| Edge/proxy | `/api/v1` strip + trailing-slash handling owned by Vite dev proxy; no CORS (same-origin) | Prod edge must replicate proxy behavior (PROXY-1). |
