# Whole-Repo Performance Audit — Reviewed Slice Plan

**Planning SHA:** `68925a0`  ·  **Date:** 2026-06-05 (UTC)  ·  **Method:**
`performance-audit-cycle` → `whole-repo-scoping.md` (full method, review-gated).
**Verification mode:** static-only (dynamic deferred — no running PG/Valkey/dataset; see decision log §5).

## Scope summary

**Hangar Bay** — an EVE Online public-contract marketplace (ship sales). Backend aggregates public
contracts from the EVE ESI API on a schedule into PostgreSQL (SQLite for dev), caches via
Valkey/Redis, and serves a filtered/paginated read API to an Angular SPA.

**Realistic load (for Impact calibration):**
- **Read path (S1):** user-driven HTTP `GET /contracts/` — paginated (size ≤ 100), filter + sort +
  full-text-ish search. Frequency = request rate (interactive browsing). Data size = the `contracts`
  table for the aggregated regions (The Forge etc. → tens of thousands of live contracts plausible).
- **Ingestion path (S2):** scheduled every **900 s** (15 min). Per run: fetch public contracts for N
  regions (paginated), resolve issuer/corp/location IDs to names (batched), fetch **items per
  contract**, bulk-upsert. Frequency = cron cadence; per-occurrence cost dominated by ESI round-trips
  scaling with contract count.
- **Frontend (S3):** would be per-interaction render, **but routes are unwired today** (latent).

## Survey table (production LOC)

| Unit | Language | Prod LOC | Purpose |
|---|---|---:|---|
| `app/backend/src/fastapi_app` (read path) | Python / FastAPI | ~700 | serve filtered/paginated contracts |
| `app/backend/src/fastapi_app` (ingestion) | Python / asyncio+httpx | ~650 | ESI aggregation → DB |
| `app/backend/src/fastapi_app` (shared: models/config/logging/main) | Python | ~660 | schema, settings, wiring |
| `app/frontend/angular/src` | TypeScript / Angular 20 | ~506 | SPA (signals, zoneless) — **latent (no routes)** |

Excluded from sizing: `tests/`, `alembic/` migrations, `__pycache__`, `*.spec.ts`, `node_modules`,
`check_alembic_version.py`.

## Stack profile (Phase 0 detection)

- **Backend:** Python ≥3.11; FastAPI ≥0.115.12; SQLAlchemy[asyncio] 2.0.41; asyncpg 0.30;
  redis(.asyncio) 6.2 (Valkey); Alembic; httpx 0.28; APScheduler 3.11; structlog 25; Pydantic v2 /
  pydantic-settings 2.9; prometheus-fastapi-instrumentator 7.
  - **Profile packs:** `python.md` + modules `python/orm-database.md`, `python/async-asyncio.md`,
    `python/web-frameworks.md`; **SQL companion** `sql.md` + `sql/postgres.md` (the read path emits a
    hand-shaped DISTINCT-count-over-join + ORM SQL; schema/DDL in scope via `models/contracts.py`);
    version index `version-indexes/python.md`.
- **Frontend:** Angular 20, `@angular/cdk` 20, RxJS 7.8, TypeScript 5.8; **zoneless** change
  detection + signals; `provideHttpClient(withFetch())`.
  - **Profile packs:** `javascript-typescript.md` + `javascript-typescript/angular.md` +
    `javascript-typescript/bundling-build.md`; version index `version-indexes/javascript-typescript.md`.

## Hot-path & reachability map (cheap, structural)

Workload shape: **IO-bound service** (S1, S2) + a **latent SPA** (S3). So "hot" = DB round-trips,
N+1/unbatched queries, missing indexes, external-call fan-out, serialization — **not** CPU inner loops.

- **HOT — S1 read path:** `contract_service.get_contracts` (DISTINCT count over an outer join;
  leading-wildcard `ILIKE`; `selectinload` items; per-row Pydantic validation; **no cache-aside**
  despite the perf-spec mandating it). On every list request.
- **HOT — S2 ingestion:** `background_aggregation._process_contracts` — **serial `await
  get_contract_items()` per contract** (network N+1) and **serial per-region** fetches;
  `esi_client_class.get_esi_data_with_etag_caching` (sequential pagination); `bulk_upsert` (items
  batched at 50). Every 15 min, cost scaling with contract count.
- **WARM/COLD shared:** `models/contracts.py` (index design — fan-in to both paths),
  `db.py` engine/pool config, `core/logging.py` middleware, `main.py` wiring.
- **WARM-latent — S3 frontend:** render/HTTP code that **nothing currently reaches** (`routes = []`).
  Pure pipes (`isk`, `timeLeft`), two divergent API services. Flag "fires once wired in."
- **"No hot CPU loop" is the correct outcome** for this CRUD-shaped app — most cost is I/O, as mapped.

## The partition (reviewed — see decision log §4 for the 3 rounds)

### S1 — Backend read / request pipeline · tier **FULL** · static-only
**Files (homed here):**
`api/contracts.py`, `services/contract_service.py`, `schemas/contracts.py`, `schemas/common.py`,
`db.py`, `core/dependencies.py`, `core/cache.py`, `models/contracts.py` *(shared — audited here)*,
`models/common_models.py`, `core/logging.py`, `main.py`, `config.py`, `core/config.py`.
**Lanes:** algorithmic, memory, data-access (+SQL/postgres sub-lens), concurrency, idiom-currency,
cost-map. *(payload-startup N/A; dynamic deferred.)*

### S2 — Backend ESI ingestion & aggregation · tier **FULL** · static-only
**Files (homed here):**
`services/background_aggregation.py`, `core/esi_client_class.py`, `services/db_upsert.py`,
`services/scheduled_jobs.py`, `core/scheduler.py`, `core/http_client.py`, `core/exceptions.py`.
*(`models/contracts.py` referenced as adjacent context, audited in S1.)*
**Lanes:** algorithmic, memory, data-access (+SQL/postgres for upsert/index), concurrency
(central — async fan-out), idiom-currency, cost-map. *(payload-startup N/A; dynamic deferred.)*

### S3 — Frontend Angular SPA · tier **REDUCED + payload-startup** · static-only · **latent**
**Files (homed here):** all of `app/frontend/angular/src` (components, services, pipes, resolver,
models, config, routes, main, environments).
**Lanes:** algorithmic, memory, data-access (HTTP), idiom-currency, payload-startup, cost-map.
*(concurrency N/A for single-threaded RxJS; dynamic deferred.)* **Anti-padding stress test lives
here:** lanes are expected to report the code as largely latent/structural, not manufacture render nits.

## Coverage ledger (disjoint; reconciled against `find` at planning SHA)

Every production source file is in **exactly one** slice. Shared `models/contracts.py` audited once
(S1), referenced by S2.

| File | Slice |
|---|---|
| api/contracts.py | S1 |
| services/contract_service.py | S1 |
| schemas/contracts.py, schemas/common.py | S1 |
| db.py, core/dependencies.py, core/cache.py | S1 |
| models/contracts.py, models/common_models.py | S1 (shared; S2 refs) |
| core/logging.py, main.py, config.py, core/config.py | S1 |
| services/background_aggregation.py | S2 |
| core/esi_client_class.py, core/http_client.py | S2 |
| services/db_upsert.py, services/scheduled_jobs.py, core/scheduler.py | S2 |
| core/exceptions.py | S2 |
| app/frontend/angular/src/** | S3 |

**Out of scope (declared):** `tests/**`, `alembic/**` migrations, `check_alembic_version.py`,
`*.spec.ts`, `node_modules/**`, `docker/**`, build/config dotfiles. *(Migrations excluded as
generated/operational; the live schema is audited via the ORM models.)*

## Cross-slice frequency calibration

Read path (S1) and write path (S2) are independent — no impl/caller split that under-ranks. The only
fan-in is the **`contracts`/`contract_items` schema + indexes**, bearing on both S1 reads (per
request — hotter) and S2 writes (per interval). Missing-index findings are calibrated to the **S1
per-request** frequency. No formal frequency-map pre-artifact needed at this size (this paragraph is
it).

## Execution order & depth

1. **S1** (hottest, user-facing) → synthesize → cross-validate → commit/push.
2. **S2** (heaviest per-run cost) → synthesize → cross-validate → commit/push.
3. **S3** (latent; anti-padding test) → synthesize → cross-validate → commit/push.
4. **Whole-repo roll-up** (cross-slice themes; the request is a posture question → roll-up REQUIRED).
5. **Field feedback** finalized (running throughout).

Progress + resume point: `02-progress-ledger.md`.
