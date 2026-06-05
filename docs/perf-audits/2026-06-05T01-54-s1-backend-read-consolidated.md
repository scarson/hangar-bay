---
run_schema_version: 1
run_id: 2026-06-05T01-54-s1-backend-read
date: 2026-06-05T01:54:00Z
scope: "Backend read/request pipeline (GET /contracts/) — slice S1 of whole-repo audit"
methodology:
  skill: performance-audit
  plugin_version: superpowers-plus@0.2.0
dispatch:
  model_requested: "latest-opus (Agent-tool subagents)"
  reasoning_effort: "default (harness exposes no knob)"
  overridden_by_user: false
stack:
  - { ecosystem: pypi, framework: fastapi, version: ">=0.115.12" }
  - { ecosystem: pypi, framework: sqlalchemy, version: "2.0.41" }
  - { ecosystem: pypi, framework: asyncpg, version: "0.30" }
  - { ecosystem: pypi, framework: pydantic, version: "2.x" }
  - { ecosystem: pypi, framework: redis, version: "6.2" }
currency_briefs:
  - { framework: python-stack, researched_on: 2026-06-03, status: "version-index only (covered_through Py3.13/SQLAlchemy2.0); no live brief" }
lanes_run: [algorithmic, memory, data-access, concurrency, idiom-currency, cost-map]
lanes_skipped: { payload-startup: "backend, no payload/startup surface", dynamic: "deferred — no running PG/Valkey/dataset; static-only run" }
finding_counts:
  by_impact: { critical: 2, major: 7, minor: 5 }
  by_lane: { algorithmic: 2, memory: 3, data-access: 8, concurrency: 3, idiom-currency: 3 }
  suspected_bugs: 8
regression:
  prev_run_id: null
  new: 14
  persisting: 0
  resolved: 0
---

# Performance Audit — Backend Read / Request Pipeline (S1)

**Date:** 2026-06-05 01:54 UTC   **Scope:** `GET /contracts/` read path (slice S1 of whole-repo)
**Stack:** FastAPI ≥0.115 / SQLAlchemy[asyncio] 2.0.41 / asyncpg / Pydantic v2 / redis(Valkey)
**Currency brief:** version-index `python.md` (covered_through Py3.13 / SQLAlchemy 2.0, built 2026-06-03); no live brief (offline currency for redis/httpx noted per-finding).
**Lanes run:** algorithmic, memory, data-access, concurrency, idiom-currency, cost-map. *(payload-startup N/A; dynamic deferred — static-only.)*
**Dispatch:** 6 independent **blind** subagents, lane-reads-own-pack. **Blind discovery result:** the lanes independently reconstructed the entire hot-path map (the fan-out join, the DISTINCT count, the missing cache, the pool ceiling) with no findings pre-seeded — and the `concurrency` lane correctly *refused* a tempting-but-unsafe parallelization (see False Positives).
**Regression vs none:** 14 new (first run for this scope).

## Critical Findings

### P1. Read endpoint never uses the cache — every list request recomputes count + data + serialization from Postgres
**Lanes:** data-access, cost-map (agreement ×2)   **Location:** `services/contract_service.py:35-208`, `api/contracts.py:25-36` (Redis available via `core/cache.py` + `core/dependencies.py:get_cache`, never referenced)
**Fingerprint:** `data-access:contract_service.py:get_contracts:no-cache-aside`   **Status:** new
**Problem:** Valkey/Redis is fully wired (`app.state.redis`, `get_cache`) but the listing path makes zero cache calls (grep-confirmed). Every request — including the universally-shared default landing query (no filters, `date_issued DESC`, page 1) — runs both a count query and a data query against Postgres and re-serializes. The project's own `performance-spec.md` §3.1 mandates cache-aside for "frequently accessed, slowly changing" data; contract data changes only every 900 s (the aggregation cadence), so it is the textbook cache-aside candidate.
**Impact:** reachability = 100% of read traffic; frequency = every browse; per-occurrence = 2 DB round-trips + DISTINCT-count + page serialization. Caching the hot default queries short-circuits nearly every other S1 finding for the common case.
**Confidence:** Strong-static   **On cost map:** yes
**Effort:** Contained (a cache-aside wrapper around `get_contracts` keyed on the filter set; invalidate-on-aggregation or short TTL).
**Verification plan:** measure cache hit-ratio + P95 on the default query before/after under a warm cache; correctness guard = a test asserting cached and uncached responses are byte-identical for a fixed filter set, and that a new aggregation run invalidates/expires the entry. **Design decision for the user:** acceptable staleness window (TTL vs event invalidation) — see Design Decisions.

### P2. Substring search uses leading-wildcard `ILIKE '%term%'` — non-sargable, forces sequential scans
**Lanes:** data-access (cost-map corroborates)   **Location:** `services/contract_service.py:88-96`
**Fingerprint:** `data-access:contract_service.py:get_contracts:leading-wildcard-ilike`   **Status:** new
**Problem:** `Contract.title ILIKE '%x%'` OR `ContractItem.type_name ILIKE '%x%'`. A leading `%` makes the existing `ix_contracts_title` btree unusable, and `type_name` is unindexed entirely — so search scans `contracts` (and the joined `contract_items`) linearly. This is the slowest interactive operation on a large region.
**Impact:** reachability = every search request (min_length 3); per-occurrence = full scan over tens of thousands of rows × the join fan-out. Grows with table size.
**Confidence:** Strong-static   **On cost map:** yes
**Effort:** Contained (add `pg_trgm` GIN indexes on `title` and `contract_items.type_name`; the ORM `ILIKE` then uses them on Postgres). Note SQLite dev has no trigram — behavior is dialect-split; guard accordingly.
**Verification plan:** `EXPLAIN ANALYZE` the search query before/after the GIN index (seq scan → bitmap index scan); correctness guard = search-result-set equality test on a fixed fixture.

## Major Findings

### P3. Location filter columns (region/system/station) are unindexed
**Lanes:** data-access   **Location:** `models/contracts.py:48-50` vs filters in `contract_service.py:108-114`
**Fingerprint:** `data-access:models/contracts.py:contracts:missing-location-indexes`   **Status:** new
**Problem:** `start_location_region_id`, `start_location_system_id`, `start_location_id` are filtered with `IN (...)` but carry no index. Region filtering is the *primary* browse axis (the app aggregates by region), so this is a hot, unindexed predicate.
**Impact:** seq scan of `contracts` on the most common filter; scales with table size. **Confidence:** Strong-static. **On cost map:** yes. **Effort:** Localized (add btree indexes; consider composite — see P6).
**Verification plan:** `EXPLAIN ANALYZE` region-filtered query before/after; guard = result-set equality.

### P4. Count query is `COUNT(*)` over `SELECT DISTINCT contract_id` over the full filtered fan-out SELECT
**Lanes:** data-access, algorithmic, memory, cost-map (agreement ×4)   **Location:** `services/contract_service.py:131-135`
**Fingerprint:** `data-access:contract_service.py:get_contracts:distinct-count-over-join`   **Status:** new
**Problem:** When item filters/sort are active the inner query is `Contract OUTER JOIN ContractItem`; the count wraps it in `SELECT DISTINCT contract_id` then `COUNT(*)`, projecting ~25 Contract columns and DISTINCT-ing the entire row-multiplied set on every request before any page is returned.
**Impact:** the heaviest DB region; runs every request; intermediate scales with `total_matching × items_per_contract`. **Confidence:** Strong-static. **On cost map:** yes (High). **Effort:** Contained.
**Verification plan:** rewrite to `COUNT(DISTINCT contracts.contract_id)` or an `EXISTS` semi-join (P5); `EXPLAIN ANALYZE` before/after; guard = the count equals the prior count on fixtures with multi-item contracts.

### P5. Item-attribute filters use an outer join + Python `.unique()` dedup where an `EXISTS` semi-join avoids the fan-out
**Lanes:** algorithmic, memory, data-access, cost-map (agreement ×4)   **Location:** `services/contract_service.py:79-125, 167-177`
**Fingerprint:** `algorithmic:contract_service.py:get_contracts:join-fanout-dedup`   **Status:** new
**Problem:** `outerjoin(ContractItem)` multiplies each contract into one row per item; `result.scalars().unique().all()` dedups in Python (work ∝ rows-after-join, not page size); the data query also drags item columns it never reads (items are separately `selectinload`-ed). An `EXISTS (SELECT 1 FROM contract_items WHERE …)` semi-join filters without multiplying rows.
**Impact:** inflates both the count (P4) and data queries, and the Python-side dedup, on every item-filtered/ship-name-sorted browse. **Confidence:** Strong-static. **On cost map:** yes (High). **Effort:** Contained (collides constructively with P4 — same rewrite).
**Verification plan:** semi-join rewrite; guard = result-set + count equality on multi-item fixtures; **note correctness coupling to SB1** (LIMIT-before-dedup) — the rewrite should fix both.

### P6. No composite (filter + sort) index — all `contracts` indexes are single-column
**Lanes:** data-access   **Location:** `models/contracts.py:70-80`
**Fingerprint:** `data-access:models/contracts.py:contracts:no-composite-index`   **Status:** new
**Problem:** The dominant query shape — "filter by region + `ORDER BY date_issued DESC LIMIT size`" — cannot be served by an index-ordered scan with only single-column indexes; Postgres must sort after filtering.
**Impact:** a sort node on every page of the common browse; grows with matched rows. **Confidence:** Strong-static. **On cost map:** yes. **Effort:** Localized (a composite e.g. `(start_location_region_id, date_issued DESC)`; choose columns against real query mix).
**Verification plan:** `EXPLAIN ANALYZE` shows sort removed / index-ordered scan; guard = ordering test.

### P7. Async engine has no pool configuration — defaults cap concurrency at ~15 connections/worker
**Lanes:** concurrency, data-access (agreement ×2)   **Location:** `db.py:12-18`
**Fingerprint:** `concurrency:db.py:async_engine:pool-defaults`   **Status:** new
**Problem:** `create_async_engine` sets only `echo`/`future`; `QueuePool` defaults `pool_size=5` + `max_overflow=10` = 15. Each request holds a connection across the count + data (+ selectinload) round-trips, so beyond ~15 concurrent requests the surplus serialize on checkout (`pool_timeout=30s`) and eventually 500. Invisible until concurrent load.
**Impact:** hard concurrency ceiling for an IO-bound read service. **Confidence:** Strong-static. **On cost map:** yes. **Effort:** Localized (set `pool_size`/`max_overflow`/`pool_recycle`/`pool_timeout` against Postgres `max_connections` ÷ worker count). **Design decision:** exact sizing needs deployment context — see Design Decisions.
**Verification plan:** load test concurrent reads to confirm the ceiling moves; guard = none (config).

### P8. Per-request synchronous structlog render + stdout write runs on the event loop
**Lanes:** concurrency, cost-map (agreement ×2)   **Location:** `core/logging.py:58-90`; emitters `contract_service.py:49, 139, 190`
**Fingerprint:** `concurrency:logging.py:setup_logging:sync-logging-on-loop`   **Status:** new
**Problem:** A sync `StreamHandler(sys.stdout)` + `JSONRenderer` runs the 7-processor chain and the blocking `write()` on the loop thread; the read path emits 2+ records/request. JSON encode + a backpressured stdout pipe stall *all* concurrently-waiting coroutines.
**Impact:** per-request loop-time tax that worsens tail latency under concurrency. **Confidence:** Strong-static. **On cost map:** yes. **Effort:** Contained (`QueueHandler`/`QueueListener` so the loop only enqueues; add an `isEnabledFor`/level guard).
**Verification plan:** structural (off-loop handoff) + a concurrency latency test; guard = log-output equality.

### P9. Double Pydantic validation of the list response
**Lanes:** idiom-currency, memory, cost-map (agreement ×3)   **Location:** `services/contract_service.py:186` + `api/contracts.py:25`
**Fingerprint:** `idiom-currency:contract_service.py:get_contracts:double-pydantic-validation`   **Status:** new
**Problem:** The service `model_validate`s every ORM row into `ContractSchema` (with nested items), then the endpoint's `response_model=PaginatedResponse[ContractSchema]` makes FastAPI re-validate the already-validated page a second time. Two full Pydantic passes per request, scaling with page size × (fields + nested items).
**Impact:** redundant CPU on every list request. **Confidence:** Strong-static. **On cost map:** yes. **Effort:** Localized (convert once — pass ORM objects through `response_model` relying on `from_attributes`, or set `response_model=None` and return an `ORJSONResponse`). Subsumes the per-row `TypeAdapter` micro-finding.
**Verification plan:** micro-bench the response build before/after; guard = response JSON equality.

## Minor Findings

### P10. `get_db` issues `COMMIT` on every request, including read-only ones
**Lane:** cost-map/data-access   **Location:** `db.py:44-57`   **Fingerprint:** `data-access:db.py:get_db:commit-on-read`   **Status:** new
**Problem/Impact:** an extra transaction round-trip per read with nothing to flush. **Confidence:** Strong-static. **Effort:** Localized (commit only when the session is dirty, or use an explicit write dependency). **Verification:** round-trip count; guard = write paths still persist.

### P11. `price`/`collateral` typed `Numeric` → Decimal marshaling at the ORM boundary
**Lane:** data-access   **Location:** `models/contracts.py:42-43`   **Fingerprint:** `data-access:models/contracts.py:contracts:numeric-decimal-overhead`   **Status:** new
**Problem/Impact:** Decimal conversion on range filters + serialization. Real but small; **kept** (severity ranks attention, not inclusion). **Confidence:** Heuristic. **Effort:** Contained (only if profiling shows it; type choice has correctness implications for money — likely a deliberate tradeoff, see Design Decisions).

### P12. Legacy `from sqlalchemy.future import select` shim
**Lane:** idiom-currency   **Location:** `contract_service.py:5`   **Fingerprint:** `idiom-currency:contract_service.py:imports:legacy-future-select`   **Status:** new
**Problem/Impact:** the 1.4 forward-compat shim; under 2.0 the canonical import is `from sqlalchemy import select` (already used in `api/contracts.py:2` — internal inconsistency). Zero perf delta; currency-marker only. **Effort:** Localized.

### P13. Per-row `model_validate` comprehension vs the Pydantic v2 list fast path
**Lane:** idiom-currency   **Location:** `contract_service.py:186`   **Status:** new — **subsumed by P9** (do not implement separately).

### P14. Filter-only join transports item columns that `selectinload` re-fetches
**Lane:** algorithmic, cost-map   **Location:** `contract_service.py:82, 172`   **Status:** new — **subsumed by P5** (same refactor).

## Cross-Cutting Themes

1. **The one-to-many filtered via JOIN is the root cause of P4 + P5 (+ SB1, P14).** Switching item-attribute filters to an `EXISTS` semi-join, counting `DISTINCT contract_id` (or over `contracts` alone), and keeping `selectinload` purely for display collapses the count, the data query, the Python dedup, and the short-page bug into one coherent rewrite.
2. **Caching (P1) is the highest-leverage single change** — it sits *in front of* the entire query+serialize stack for the common, shared queries.
3. **Indexing gaps (P2, P3, P6)** are a cluster: the model has 9 single-column indexes but misses the columns the read path actually filters/sorts on most (location, trigram search, composite sort).
4. **Per-request fixed overhead (P8 logging, P9 double-validation, P10 commit-on-read)** is a second cluster — none individually huge, collectively a measurable per-request tax independent of result size.

## Measurability

Most of these are **observable today**: the app already exposes Prometheus metrics (`/metrics`) and structured request logs with `duration_ms` (`contract_service.py` `log_key_event`). Post-fix wins for P1/P4/P5/P6 are directly visible as P95/P99 read latency and DB time. **Gaps:** there is no per-query DB-time metric or slow-query log wired, and no cache hit/miss counter (needed to confirm P1) — adding those is a prerequisite to *measuring* (not just arguing) the cache and index wins. Index-scan confirmation requires `EXPLAIN ANALYZE` against a production-like dataset (deferred — static-only run).

## Execution Cost Map (highlights)
> Architectural awareness, not a to-do list. Full map: `2026-06-05T01-54-s1-backend-read-cost-map.md`.
- **High:** the DISTINCT-count-over-join (P4); the fan-out data query + `selectinload` (P5).
- **Medium:** per-row Pydantic serialization (P9); the 2–3 sequential DB round-trips/request; per-request structured logging (P8).
- **Low (map-only, inherent/fine):** RequestID + Prometheus middleware hops; `ContractFilters` parsing; the `commit()` on read (P10).
- **Architecture note:** a Redis layer exists but the list endpoint never touches it (P1) — caching short-circuits the whole map for the common case.

## Suspected Bugs (for follow-up — NOT addressed here)
> Correctness issues noticed during the audit. Recorded, not chased. A ready bug-hunt kickoff is at `docs/perf-audits/2026-06-05-s1-backend-read-bug-hunt-kickoff.md`.

- **SB1.** `LIMIT` applied to fan-out rows *before* Python `.unique()` collapses duplicates (`contract_service.py:167-177`) → a "full" page can return fewer than `size` distinct contracts, and pagination can split/duplicate contracts across pages; disagrees with the DISTINCT count. *(Co-located with P5 — fix alongside, but it is a correctness bug, recorded not chased.)*
- **SB2.** `db.py`: `Base = declarative_base()` defined twice (`:6`, `:27` — the second discards the first, import-order sensitive) and `get_db_session_factory` defined twice (`:30`, `:37`).
- **SB3.** `create_db_tables()` runs `drop_all` + `create_all` **unconditionally on every startup** (`main.py:128-137, 45`) — destructive/data-loss on any non-empty DB.
- **SB4.** `ContractSchema.start_location_id` is required `int` (`schemas/contracts.py:31`) but the model column is nullable (`models/contracts.py:48`) — courier contracts (null start location) would fail response validation (500).
- **SB5.** Two divergent `Settings` classes (`config.py` vs `core/config.py`) imported by different layers (`cache.py`/`db.py` vs `main.py`/`dependencies.py`) — config drift risk.
- **SB6.** `min_me/max_me/min_te/max_te` filters are accepted and validated but never applied (acknowledged in a code comment) — silent no-op filters.
- **SB7.** Leftover import-time debug `print()` statements (`config.py`, `core/config.py`, `main.py:9`).
- **SB8.** `sort_by=ship_name` orders on an outer-joined **nullable** item column over the fan-out → nondeterministic page contents (a contract has N candidate sort values).

## False Positives / correctly-rejected (recorded for the validated report)
- **Parallelizing the count and data queries** — the `concurrency` lane *considered and rejected* it: the count gates the `total == 0` early return (data dependency) **and** both run on the same `AsyncSession` (asyncpg sessions are not concurrency-safe). `asyncio.gather` here would be a correctness regression. **Good anti-false-positive.**
- **`selectinload(items)` as an N+1** — not flagged; it is the intended single-extra-query eager load.
- The `SORT_MAP.get() is None` fallback being "dead" and `__slots__`-style micro-allocs were examined and **not** manufactured into findings (anti-padding held).
