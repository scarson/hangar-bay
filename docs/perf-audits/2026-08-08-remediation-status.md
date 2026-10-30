<!-- ABOUTME: Disposition of every task and finding in the 2026-06-05 whole-repo performance-audit -->
<!-- ABOUTME: remediation plan against the code as it stands on 2026-08-08, plus what is still worth doing. -->

# Remediation status of the 2026-06-05 performance audit (as of 2026-08-08)

**Plan under review:** `docs/plans/2026-06-05-whole-repo-perf-audit-remediation-plan.md` (status DRAFT,
never signed off, never executed as a plan).
**Method:** every finding ID re-checked against current source, current Alembic migrations, and
`git log`. No production access, so anything needing a live `EXPLAIN` or instance metrics is marked
PRODUCTION-BLOCKED rather than guessed at.

**Headline:** the plan was never executed *as a plan*, but roughly half its findings were fixed
incidentally by two months of feature work — the frontend rebuild (Angular deleted in `657e804`,
2026-07-11), the M4 production-readiness pass (`eaec803`, 2026-07-18), the F008 query work, and the
2026-08-02 watermark investigation (`420e7cf`). The whole frontend slice (Tasks 7 and 8) is obsolete
because its target no longer exists. The ingestion slice (Tasks 1 and 5) is almost entirely untouched.

| Task | Findings | Disposition |
|---|---|---|
| 0 | Measurability | STILL OPEN (partial) |
| 1 | SP1, SP4, SP5, SP6 | STILL OPEN (SP1 materially mitigated) |
| 2 | P1 | STILL OPEN |
| 3 | P2–P6, SB1 | MIXED: SB1 + P4 remediated, P3/P5 partial, P2/P6 open |
| 4 | SP3, SP7 | SP3 REMEDIATED, SP7 STILL OPEN |
| 5 | SP2, SP8, SP10, SP11 | STILL OPEN |
| 6 | P7–P10 | P7 REMEDIATED, P8/P9/P10 STILL OPEN |
| 7 | FP1, FP2, FP3 | OBSOLETE (Angular deleted) |
| 8 | FP7, FP8, FP9 | OBSOLETE / superseded |
| 9 | P12, SP14–SP17 | SP13/SP17 closed, P12/SP14/SP15/SP16 STILL OPEN |

---

## Task 0 — Stand up the measurability the rest of the plan depends on

**Disposition: STILL OPEN (partial).**

What exists today:

- `app/backend/src/fastapi_app/core/metrics.py` holds exactly one instrument —
  `hangar_bay_last_ingest_success_timestamp`, a Gauge. That is the whole module (8 lines).
- `main.py:139-148` configures `prometheus_fastapi_instrumentator`, which yields per-route request
  count/latency/in-progress. `/metrics` is bearer-gated at `main.py:151-158`.
- `contract_service.get_contracts` emits a structured `contract_search_executed` event carrying
  `duration_ms` (`contract_service.py:1123`, `1136-1157`). This is not a metric, but it is what the
  2026-08-02 investigation actually used to establish the 6-second regression — so the *read-path*
  measurability gap is smaller in practice than the plan assumed.

What the plan asked for and is still missing:

- **No per-query DB-time instrument.** Nothing times the count query separately from the page query,
  which is exactly the split that mattered in the 2026-08-02 root cause (COUNT 6,022 ms vs PAGE 0.5 ms).
- **No cache hit/miss counters** — there is no read-path cache to count (see Task 2).
- **No ingestion run-duration, ESI-round-trip, or items-fetched counters.** `run_aggregation` logs
  free-text `logger.info` lines (`background_aggregation.py:546`, `567-570`, `589`) and writes a JSON
  freshness record to `INGEST_LAST_RUN_KEY` (`_record_run_outcome`, line 487) holding
  `{finished_at, outcome, regions_ok, regions_failed, last_success_at}` — no duration, no round-trip
  count, no item count. `/ops/ready` reads that record (`api/ops.py:58`).

The gap is real and it is the gap that would let Tasks 1 and 5 be verified rather than argued.

---

## Task 1 — Bound the ESI fan-out: concurrency-cap the per-contract item fetch

### SP1 — serial per-contract item fetch — **STILL OPEN, materially mitigated**

`_fetch_item_rows` (`background_aggregation.py:704-756`) is still a plain `for contract in contracts`
loop `await`ing `get_contract_items` one at a time (line 723). No semaphore, no `gather`.

The mitigation, which changes the operational picture substantially: `_select_already_enriched`
(line 680-702) reads back `item_processing_status == 'COMPLETED' AND enrichment_version ==
ENRICHMENT_VERSION` and line 719 skips those contracts entirely. Its own docstring states the intent —
"This is what turns a corpus-sized run into a churn-sized one." So the serial loop now runs over the
run's *new/failed* contracts, not the whole corpus. The 900 s-interval overrun the plan warned about is
therefore a cold-start / `ENRICHMENT_VERSION`-bump problem, not a steady-state one — and the
`ENRICHMENT_VERSION` comment at line 65-72 confirms it, documenting a resweep as "~80 min at a ~46k
corpus, which outlives the aggregation lock TTL."

That 80-minute resweep is the residual cost SP1 was about.

### SP5 — per-region fetches sequential — **STILL OPEN, currently inert**

`_fetch_regions` (`background_aggregation.py:384-415`) is still a sequential `for region_id in
region_ids` loop. Production configures a single region (`AGGREGATION_REGION_IDS` defaults to
`[10000002]`), so the fan-out is 1 today. It becomes live the moment coverage expands.

### SP6 — ID-resolution chunks sequential — **STILL OPEN**

`ESIClient.resolve_ids_to_names` (`core/esi_client_class.py:482-505`) still walks `for i in range(0,
len(unique_ids), chunk_size)` issuing one `POST /v3/universe/names/` per 1,000-id chunk serially.

### SP4 — httpx default pool limits — **STILL OPEN**

Neither client sets `httpx.Limits`:
- `core/http_client.py:17-21` — `httpx.AsyncClient(base_url=..., headers=..., timeout=15.0)`.
- `core/esi_client_class.py:174-178` — `httpx.AsyncClient(base_url=..., headers=..., timeout=...)`.

Both take httpx's default `max_connections=100`. Harmless while every call site is serial; it is the
thing that must be pinned to `C` before any of SP1/SP5/SP6 is fixed.

### Partial credit worth recording

A bounded fan-out *was* introduced for a different loop the audit did not name:
`_resolve_esi_objects` (`background_aggregation.py:115-147`) runs single-object type/group/category/
station lookups under `asyncio.Semaphore(ENRICHMENT_CONCURRENCY)` with `ENRICHMENT_CONCURRENCY = 8`
(line 55), with per-id `try/except` so `gather` never sees an exception. Its docstring gives the same
rationale the plan gives for SP1 ("minutes of added runtime that can also push a run past the lock
TTL"). This is a working, tested precedent for the exact shape SP1 needs — including the "never an
unbounded gather" constraint — which reduces the design risk of Task 1 considerably. The
**[DECISION] on `C`** is effectively pre-answered at 8 for the enrichment fan-out; it still needs an
explicit settings key and a matching `httpx.Limits`.

---

## Task 2 — Add cache-aside to the contract read path [P1]

**Disposition: STILL OPEN.**

`get_contracts` (`contract_service.py:1005-1182`) goes straight to Postgres on every request. There is
no Valkey read in the module — `grep` for `redis`/`cache` in `services/contract_service.py` and
`api/contracts.py` returns only docstring prose about the *taxonomy name cache* (a DB table,
`EsiTaxonomyCache`) and `_category_names` (`contract_service.py:658-671`), which is a per-request
`SELECT`, not a cache. `app.state.redis` exists (`core/cache.py:79`) and is used by `/ops/ready` and
by the aggregation lock, never by the read path.

The invalidation hook the plan wanted has meanwhile been built for a different purpose:
`_record_run_outcome` (`background_aggregation.py:487`) already runs at the end of every aggregation
and already writes to Valkey inside the lock. Bumping a cache-version key there is a two-line addition.

**Cost has changed since the audit, in the direction that makes this more valuable.** A single list
request now issues, at minimum: the grouped segment/total aggregate (`_segment_counts_and_total`,
line 441), the `_observed_coverage` recursive CTE (line 553), the page query, the `selectinload(items)`
follow-up, and `_category_names` — plus `_count_unknown_system_excluded` when `system_ids` is set.
That is 5–6 round trips per request against a `basic_256mb` instance, all of it identical for every
anonymous visitor loading the default view.

---

## Task 3 — Rewrite the one-to-many read query and add the missing indexes

### SB1 (LIMIT-before-dedup short pages) — **REMEDIATED**

`_fetch_page_joined` (`contract_service.py:596-635`) paginates over distinct contract ids first — it
projects `with_only_columns(Contract.contract_id)`, `.group_by(Contract.contract_id)`, orders by an
aggregate of the sort column (`func.max`/`func.min` chosen by direction) with `contract_id` as
tiebreaker, then `.offset().limit()` — and only then loads that page's contracts with
`selectinload(Contract.items)`, restoring page order in Python (lines 632-634). The comment at lines
602-610 states the failure it prevents. A full page now returns `size` distinct contracts by
construction.

### P4 (COUNT over SELECT DISTINCT over the fan-out) — **REMEDIATED on the hot path**

The page total no longer comes from `_count_distinct_contracts` at all. `_segment_counts_and_total`
(`contract_service.py:441-531`) derives `total` from the *same grouped statement* that produces the
segment labels, and applies DISTINCT conditionally:

```python
matched = (
    func.count(func.distinct(Contract.contract_id))
    if needs_item_join
    else func.count(Contract.contract_id)
)
```

with the comment "the DISTINCT sort is pure cost on the unjoined path every default request takes."
This is precisely the fix the 2026-08-02 audit's §9 asked for.

**Residual:** `_count_distinct_contracts` (lines 390-400) still wraps unconditionally in
`select(...).distinct().subquery()`. It survives as the counter for
`_count_unknown_system_excluded` only — a path taken solely when `system_ids` is set. Low value, but
it is the same no-op DISTINCT on the no-join path.

### P5 / P14 (item filters via outer join where EXISTS fits) — **PARTIALLY REMEDIATED**

Remediated: every filter family added since the audit uses a correlated `EXISTS` rather than a join —
`_has_blueprint_copy_item` (line 183), `_offered_item_range_exists` (line 214) for runs/ME/TE, and
the category/group clause in `_apply_item_filters` (lines 371-385). `_needs_item_join` (line 75)
carries an explicit comment recording *why* those families are deliberately absent from the join
condition.

Still open: `_needs_item_join` still returns True for `filters.search`, `filters.type_ids`, and
`sort_by == ship_name`, and `get_contracts:1049` still issues `query.outerjoin(ContractItem)` for
them. The text search predicate at lines 268-276 is an `OR` across `Contract.title` and
`ContractItem.type_name`, which is the one that genuinely needs either a join or a rewritten
`EXISTS`; `type_ids` is a pure "does this contract hold such an item" question and is the clearest
remaining EXISTS candidate.

P14 (join transports item columns that `selectinload` then re-fetches) is resolved for the joined
page path, which projects only `contract_id` (line 616).

### P2 (leading-wildcard ILIKE, no pg_trgm) — **STILL OPEN**

`contract_service.py:269` still builds `search_term = f"%{filters.search}%"` and applies
`.ilike(search_term)` to both columns. No `pg_trgm` extension and no GIN index exists: the six
migrations under `app/backend/src/alembic/versions/` (`3aca702a74e3` baseline, `b1c4d7e9f204`,
`c7e2a9b41d36`, `d5f83b17c0ae`, `ea2491c47a9f`, `685dab7d6df5`) contain no `CREATE EXTENSION` and no
`postgresql_using='gin'`. `ix_contracts_title` is a plain btree, useless to a leading wildcard.

### P3 (location filter columns unindexed) — **PARTIALLY REMEDIATED**

- `start_location_region_id`: **indexed**, as the leading column of
  `ix_contracts_region_last_seen('start_location_region_id', 'last_seen_at')` —
  `models/contracts.py:129`, shipped by migration
  `c7e2a9b41d36_contracts_last_seen_at.py:42` in commit `4548802` (2026-07-26). It was added for the
  watermark, but a region-only predicate uses it as a prefix.
- `start_location_system_id`: **still unindexed.** Filtered at `_apply_location_filters:332` and, more
  expensively, scanned by `_count_unknown_system_excluded:592` (`.is_(None)`).
- `start_location_id`: **still unindexed.** Filtered at `_apply_location_filters:334`. The 2026-08-02
  audit used this column's *lack* of an index as its scan-cost control experiment (§2, third bullet).

### P6 (no composite filter+sort index) — **STILL OPEN**

The only composite indexes on `contracts` are `ix_contracts_type_status(type, status)` and
`ix_contracts_region_last_seen(region, last_seen_at)`. Everything else is single-column
(`models/contracts.py:117-134`). The plan's recommended `(start_location_region_id, date_issued DESC)`
does not exist.

The **[DECISION] on which columns** should now be re-derived rather than answered as written: the real
default request is `is_ship_contract = true AND date_expired > now() AND <watermark> ORDER BY
date_issued DESC LIMIT 50`, with no region filter at all — the region filter is optional and F008
made the *unfiltered* list the primary surface. A composite chosen for region+date_issued would serve
a query that is no longer dominant. This needs a fresh `EXPLAIN` against production before anyone
picks columns.

---

## Task 4 — Narrow the upsert ON CONFLICT SET and raise the item batch size

### SP3 (ON CONFLICT rewrites every column) — **REMEDIATED**

`services/db_upsert.py:43`:

```python
supplied_cols = [name for name in values[0] if name not in primary_key_cols]
```

with the comment at lines 39-42 recording exactly the mechanism: "`stmt.excluded` enumerates EVERY
table column, so building set_ from it wholesale clobbers omitted columns with their defaults on
conflict." Shipped in `733e398` (2026-07-11), extended in `3b61078` (2026-08-07) with the
`preserve_on_null` COALESCE path for the four denormalized name columns.

The plan's **[DECISION] on ingestion-owned vs derived columns** is also answered, in code and in
prose: `_build_contract_rows` (`background_aggregation.py:226-282`) deliberately omits
`is_ship_contract`, `item_processing_status`, and `enrichment_version` from the row dict, with a
comment (lines 273-279) explaining that including them "decayed ship flags to False whenever items
were ETag-304'd" and "would likewise reset a stamped enrichment_version to 0 on every re-sighting,
re-queueing the corpus forever." That is the state machine the decision asked about, settled by a
live incident.

Note this arrived as a **correctness** fix, not a performance one — but it delivers SP3's write-
amplification win as a side effect.

### SP7 (item upsert batch 50 → 500) — **STILL OPEN**

`background_aggregation.py:584`: `BATCH_SIZE = 50`. Unchanged.

The contract upsert next to it *does* use 500 (`batch_size = 500`, line 544), so the asymmetry is
now visible in one function. Raising the item batch is a one-token change with a well-understood
ceiling (asyncpg's 32,767 bind parameters; `UPDATE_ID_CHUNK_SIZE = 1000` at line 50 shows the
project already reasons about that limit). `ContractItem` rows carry ~17 supplied columns, so 500 rows
≈ 8,500 parameters — comfortably inside the cap.

---

## Task 5 — Stream the ingestion to bound peak memory

**Disposition: STILL OPEN, entirely.**

- **SP8** — `ESIClient.get_esi_data_with_etag_caching` (`core/esi_client_class.py:192-243`) is still
  a coroutine returning `List[Dict]`. It initializes `full_data = []` (line 199) and `extend`s every
  page (lines 224, 235) before returning the whole thing (line 243). Not a generator.
- **SP2** — `_fetch_regions` accumulates `all_contracts_data` across every region
  (`background_aggregation.py:391, 404`) and returns it whole; `run_aggregation:447` holds it, and
  `_fetch_item_rows` accumulates `all_items` across every contract in the run (lines 714, 750)
  before any upsert happens (line 582). Peak memory is still proportional to the whole run.
- **SP11** — `_build_contract_rows` (line 226) transforms the entire contract list into a second
  full-size list (`contract_values`, line 542) which coexists with `all_contracts_data`. Peak is
  still doubled.
- **SP10** — `_store_page_cache` (line 290-308) writes `response.content` at line 308, while the
  caller already materialized `response.json()` at line 232 and extended `full_data` with it. Both
  representations of the same page are live simultaneously.

Nothing here has changed. The plan's sequencing advice (do Task 1 first, both touch the same
orchestration) still holds; note that `_select_already_enriched` has since been threaded through
`_fetch_item_rows`, so a streaming refactor must preserve the skip semantics and the
`processed_contract_ids` set that `_update_item_processing_status` keys off.

---

## Task 6 — Trim per-request read overhead

### P7 (no pool config) — **REMEDIATED**

`db.py:11-23` now sets `pool_pre_ping=True`, `pool_size=5`, `max_overflow=5`, with a comment naming
the constraint ("Render Basic's connection budget is small; scheduler + API share it"). Commit
`eaec803` (2026-07-18). The **[DECISION]** on deploy budget was answered by the deploy target rather
than by the audit's ~10–20/worker guess — deliberately smaller, and correctly so for the instance.

Also picked up in the same commit: `hide_parameters=True`, which the read path leans on at
`_error_without_bound_parameters` (`contract_service.py:982-1002`).

### P8 (sync structlog render + stdout write on the event loop) — **STILL OPEN**

`core/logging.py:91-102` attaches a plain `logging.StreamHandler(sys.stdout)` and, when `LOG_FILE`
is set, a plain `logging.FileHandler`. No `QueueHandler`, no `QueueListener` — `grep` for
`QueueHandler` across `app/backend/src` returns nothing.

This got *worse* since the audit, not better: `get_contracts` now emits two large JSON log records
per request (the "Starting contract search" record at line 1021 and the `contract_search_executed`
record at line 1136), each carrying a nested `search_terms` dict of ~11 fields, both rendered and
written synchronously on the event loop. The `LOG_FILE` sink adds a second synchronous write per
record where configured.

### P9 (double Pydantic validation of the list response) — **STILL OPEN**

`api/contracts.py:33` declares `@router.get("/", response_model=ContractListResponse)` and the
service already returns a fully constructed `ContractListResponse` (`contract_service.py:1125-1133`,
built from `_list_item` → `ContractListItemSchema(**_contract_fields(...))` per row at line 1129).
FastAPI re-validates the whole page. Same shape at `contracts.py:49` (taxonomy) and `:60` (detail).

The per-row cost has grown since the audit: each list row now also carries a nested
`CompositionSummary` with a `CompositionCategory` list and a `BlueprintSummary`
(`_contract_fields:828-829`), so the duplicated validation walks more objects than it did.

### P10 (COMMIT on every read request) — **STILL OPEN**

`db.py:38-51`, `get_db` still calls `await session.commit()` unconditionally on every request that
did not raise (line 46).

---

## Task 7 — Consolidate the frontend data layer and align it to the backend contract

**Disposition: OBSOLETE.** The Angular SPA the task targets was deleted wholesale in `657e804`
("chore: remove abandoned Angular frontend and Angular-specific design docs", 2026-07-11).
`app/frontend/angular/` does not exist. The paths the task and the S3 appendix name —
`ContractSearch`, `ContractApi`, `contract.models.ts`, `contract.model.ts`,
`app/frontend/angular/src/app/features/contracts/**` — are all gone.

What replaced it: `app/frontend/web`, a React 19 + TanStack Router/Query + Vite SPA
(`app/frontend/web/package.json`). The specific findings, mapped onto the replacement:

- **FP1 (two overlapping services, divergent shapes/URLs)** — structurally resolved. There is exactly
  one HTTP client, `src/lib/api/client.ts`, and exactly one model source: `src/lib/api/schema.d.ts`
  is *generated* from the backend's own `openapi.json` (`npm run generate:api` →
  `openapi-typescript openapi.json -o src/lib/api/schema.d.ts`). Request params and response shape
  cannot drift from the backend contract by construction — which is the durable form of what FP1 and
  SB-S3-1/2 asked for. `useContracts` (`src/features/contracts/hooks/useContracts.ts:45`) calls
  `api.GET('/contracts/', { params: { query } })` with the generated types.
- **FP3 (`JSON.stringify` distinctUntilChanged)** — obsolete. React Query's structural query-key
  comparison replaces it (`queryKey: ['contracts', 'list', query, itemSurfaceReady]`, line 43).
- **FP4 (no request sharing)** — resolved by React Query's request dedupe + cache; the design
  decision that deferred it is moot.
- **FP5 (Angular resource idiom)** — moot; the framework is gone.
- **FP2 (debounce on the wrong trigger)** — **inverted, and now a live finding.** The rewrite dropped
  debouncing entirely. `FilterRail.tsx:66-68` pushes every keystroke straight into the route
  (`onUpdate({ search: event.target.value || undefined }, { replace: true })`), the route search feeds
  `useContracts`, and the query key changes per keystroke. `grep` for `debounce` across
  `app/frontend/web/src` returns nothing outside tests.
- **FP10 (`size` URL-unbounded)** — resolved server-side: `schemas/contracts.py:456` declares
  `size: int = Field(default=50, ge=1, le=100)`. A hostile `size=100000` is a 422, not a corpus dump.

The reachability gate the plan attached to this task ("currently `routes=[]`") is also gone: the
contracts feature is fully wired and covered by Playwright e2e including a production live-smoke.

---

## Task 8 — Frontend build guard-rails

**Disposition: OBSOLETE / superseded.**

- **FP7 (eager `@angular/localize/init`)** — moot. No Angular, no polyfill.
- **FP8 (no lazy-loading convention)** — **satisfied, better than the plan asked.** The plan wanted a
  *convention* to be adopted before the first feature landed; the replacement enforces it
  automatically. `vite.config.ts` configures `tanstackRouter({ target: 'react', autoCodeSplitting:
  true })`, so every route is code-split by the build rather than by developer discipline.
- **FP9 (loose budgets)** — **the analogous gap is still open, at low value.** There is no bundle-size
  budget in the new stack: `vite.config.ts` sets no `build.chunkSizeWarningLimit` and no
  `manualChunks`, `package.json` has no `size-limit` or equivalent, and `scripts/` holds only
  `generate-regions.mjs`. Vite's default 500 kB chunk warning is advisory and does not fail a build.
  This is the one piece of Task 8 that has a real successor, and it is cheap.

---

## Task 9 — Constant-factor + currency cleanups

### P12 (`sqlalchemy.future` select shim) — **STILL OPEN**

`services/contract_service.py:6`: `from sqlalchemy.future import select`. Also
`tests/services/test_contract_service.py:28`.

Partially fixed elsewhere without the plan: `background_aggregation.py:10` uses
`from sqlalchemy import select, text, update`. So the repo is now inconsistent between its two
largest modules, which is a slightly worse state than uniform-legacy.

### SP14 (`sorted(list(set(ids)))` dead work) — **STILL OPEN**

`core/esi_client_class.py:488`: `unique_ids = sorted(list(set(ids)))`. Unchanged. The sort is dead —
`unique_ids` is only ever chunked and POSTed (lines 491-497), and `chunk[0]` is used solely in a log
message (line 499).

### SP15 (chained `set.union` + 4 passes over contracts) — **STILL OPEN**

`_collect_resolvable_ids` (`background_aggregation.py:92-112`) still makes four separate
comprehensions over `contracts` (lines 94-97) and chains `.union().union().union()` (line 100),
then makes a fifth pass to filter structure ids (lines 106-108).

### SP16 (`.close()` vs `.aclose()` on redis.asyncio) — **STILL OPEN, four sites**

- `core/cache.py:57` — `await self.redis_client.close()`
- `core/esi_client_class.py:190` — `await self._managed_redis_client.close()`
- `services/background_aggregation.py:362` — `await redis_client.close()`
- `services/watchlist_matcher.py:109` — `await redis_client.close()`

The httpx counterpart *was* fixed — `esi_client_class.py:188` and `core/http_client.py:30` both use
`aclose()`. The plan tagged SP16 LOW-confidence pending a currency check against redis-py; that check
is still owed and is the actual work here.

### SP17 (hand-rolled retry vs httpx transport retries) — **CLOSED as correctly rejected**

The plan said "evaluate"; the current code answers it. `_get_with_transient_retry`
(`core/esi_client_class.py:367-417`) now retries on 5xx *and* on ESI's 420/429 rate-limit statuses
(`RATE_LIMIT_STATUSES`, line 19), honors `Retry-After` through `_rate_limit_wait` (line 81) with a
`RATE_LIMIT_SLEEP_CEILING` clamp against `float('inf')`, and carries a per-client
`rate_limit_wait_budget` so request-scoped callers fail fast while ingestion keeps full patience
(lines 118, 125-133). httpx's transport-level `retries` covers connection failures only — it cannot
express any of this. Delegating would be a regression. Record it as evaluated-and-kept.

### SP13 (fresh engine per run) — **REMEDIATED**

`run_aggregation` now opens `async with AsyncSessionLocal() as db_session`
(`background_aggregation.py:444`), sharing the single configured engine from `db.py:11` rather than
building its own. The pool params the finding said should be pinned "when fan-out is added" are the
ones now set at `db.py:16-17`.

### SP9 (per-call Redis client where a pooled shared client fits) — **MOSTLY MITIGATED**

Two `aioredis.from_url` sites remain outside the shared `CacheManager`:
`background_aggregation.py:324` (`_concurrency_lock`) and `watchlist_matcher.py:86`. Both create one
client per *job run*, not per call, and both are background jobs whose lifecycle deliberately does not
depend on `app.state`. `ESIClient.__aenter__:180` likewise creates one managed client per context
entry. The per-call pattern the finding described is gone; what remains is defensible.

---

## The 2026-08-02 contract-list watermark audit: what shipped

`docs/perf-audits/2026-08-02-contract-list-watermark-subquery.md`

### §5 — configured regions as an optimization hint — **IMPLEMENTED, verbatim**

`still_listed_by_esi()` (`contract_service.py:93-165`) is exactly the shipped design:

- `_newest_in(region_id)` (lines 168-180) builds the **uncorrelated** per-region scalar subquery over
  an `aliased(Contract)`, so PostgreSQL hoists it to an InitPlan.
- `at_a_known_regions_watermark` (lines 147-155) ORs one `and_(region == r, last_seen_at >=
  _newest_in(r))` per configured region.
- The `case` at lines 158-164 falls back to the original correlated `newest_in_region` for any region
  not in `AGGREGATION_REGION_IDS`, preserving the "hint, never a semantic input" property.
- `if not ingested_region_ids: return unstamped_or_current` (lines 143-145) keeps the empty-config
  case on the original predicate.
- The docstring (lines 118-131) carries the mechanism, the 61,874-probe figure, and a back-reference
  to the audit document.

Shipped in `420e7cf` ("perf(api): evaluate the region watermark once per query, not once per row",
2026-08-02). `ix_contracts_region_last_seen` — the index the fast path probes — was already in place
from `4548802` (2026-07-26).

The predicate is also reused rather than restated: `_live_item_bearing_contracts`
(`contract_service.py:853-867`) calls `still_listed_by_esi()`, so the readiness queries get the fast
path for free, and there is still one definition of "still on offer."

### §9 item 2 — drop the DISTINCT wrapper on the no-join count path — **IMPLEMENTED**

Done in `_segment_counts_and_total` (`contract_service.py:479-483`), conditional on `needs_item_join`,
with the SQLA-1 rationale in the comment. The follow-up's own condition ("it needs its own test that
the joined path still de-duplicates") appears satisfied by the conditional itself.

Residual: `_count_distinct_contracts` (line 396) still wraps unconditionally, but is now reachable
only from `_count_unknown_system_excluded`.

### §9 item 3 — look at `_count_unknown_system_excluded` — **STILL OPEN, unchanged**

`_count_unknown_system_excluded` (`contract_service.py:572-593`) still:
1. rebuilds the full filter set including `still_listed_by_esi()` — a **third** application of the
   watermark predicate in one request (after `_segment_counts_and_total` and the page query);
2. adds `Contract.start_location_system_id.is_(None)` over a column with **no index** (confirmed
   absent from `models/contracts.py:117-134` and from every migration);
3. and is called at `get_contracts:1066-1070`, **before** the `if total == 0` short-circuit at line
   1076 — exactly the ordering the audit flagged.

The call is gated on `filters.system_ids` being set, so it does not touch the default path. The
comment at lines 1063-1065 records a deliberate reason for the pre-short-circuit placement ("an empty
page is where the figure matters most"), so this is now a *considered* cost rather than an oversight —
but the unindexed `IS NULL` scan behind it was never addressed.

### §9 item 1 — remove the temporary IP allow rule on `hangar-bay-db` — **PRODUCTION-BLOCKED**

`198.37.143.189/32`, described "temp troubleshooting 2026-08-02 - REMOVE". Not verifiable from the
repo. **This is a security exposure that has now been open for six days.** It should be checked first,
regardless of anything else in this document.

### §9 item 4 — decide whether `basic_256mb` is the right plan — **PRODUCTION-BLOCKED**

Needs instance metrics. The audit's own argument stands: "A per-execution cost of 0.075 ms for a
fully-cached three-level index probe is CPU starvation, not a query defect."

### §9 item 5 — exact counts at corpus scale belong to F008 — **STILL OPEN, and F008 has landed**

F008 shipped (phases A–D complete per `14efc74`, "docs(handoff): F008 complete on dev, release
pending") and it did make the unfiltered list the primary surface, as predicted. The count is still
exact: `_segment_counts_and_total` (line 441) runs a `GROUP BY Contract.type` aggregate over every
matching row on every request. The deferral has expired without the decision being taken — cached
totals, approximate counts above a threshold, and keyset pagination were all deferred *to* F008, and
F008 closed without them.

Two things partly offset it: the grouped statement serves the segment labels *and* the total from one
pass ("running it alongside a grouped count would double the worst path", line 456), and the §5 fast
path cut the per-row cost. But `GROUP BY` on a corpus-scale row set removes the possibility of the
index-only shortcuts a plain `COUNT(*)` might get, so the shape is now harder to optimize than the one
the audit measured at 1,565 ms.

**Note for whoever re-measures:** the 1,565 ms "After" figure in §5 was measured against the *old*
flat count. The current grouped-aggregate-plus-coverage-CTE shape has not been measured against
production at all. That number should not be treated as the current baseline.

---

## Still open, worth doing

Ranked by value ÷ effort. Items 1 and 2 are not perf work but outrank it.

1. **Remove the production DB IP allow rule `198.37.143.189/32`.** Trivial effort, security exposure,
   six days stale, explicitly flagged "REMOVE" by its author. Blocked on Render access only.
   *(2026-08-02 §9)*

2. **Re-measure the contract list against production before optimizing anything else on it.** The
   headline "1,565 ms after" predates F008's grouped segment counts and the `_observed_coverage`
   recursive CTE, both of which now run on every request. Every read-path decision below depends on a
   current `EXPLAIN (ANALYZE)`. Cheap, and it prevents optimizing the wrong node. *(2026-08-02 §9)*

3. **Raise the item upsert batch from 50 to 500.** One line — `background_aggregation.py:584`. ~10×
   fewer statements per enrichment run; the contract upsert beside it already uses 500; the bind-param
   ceiling is not binding at ~17 columns. The single highest value-per-character change in this
   document. *(Task 4 / SP7)*

4. **Cache-aside the contract list in Valkey, invalidated by a version key bumped in
   `_record_run_outcome`.** The default view is identical for every anonymous visitor, costs 5–6 DB
   round trips against a `basic_256mb` instance, and data only changes once per aggregation interval.
   The invalidation hook already exists and already writes to Valkey inside the lock. This is the
   largest available win on the user-facing path. *(Task 2 / P1)*

5. **Index `start_location_system_id` and `start_location_id`.** Two lines in a migration, pure win,
   no dialect split needed. `start_location_id` is the column the 2026-08-02 audit used as its
   *control* for scan cost precisely because it is unindexed; `start_location_system_id` is scanned
   `IS NULL` by `_count_unknown_system_excluded` on every system-filtered request.
   *(Task 3 / P3, remainder)*

6. **Debounce the contract-search text input.** `FilterRail.tsx:66-68` fires a route update per
   keystroke and `useContracts` keys on it, so typing "raven" issues five corpus-scale requests, each
   an unindexed double `ILIKE '%…%'`. The Angular version *had* a debounce (the audit's FP2 complained
   it was on the wrong trigger); the rewrite dropped it entirely. `useDeferredValue` or a small
   debounce hook on the `search` field only — pagination and sort should stay immediate, which is
   exactly what FP2 originally asked for. *(New; FP2 inverted)*

7. **Move `_count_unknown_system_excluded` after the `total == 0` short-circuit, or fold it into the
   grouped aggregate.** A third application of the watermark predicate plus an unindexed `IS NULL`
   scan, run before the cheap exit. Item 5 above defangs the scan; this removes the redundant
   execution. Both reviews of the 2026-08-02 audit missed it, and it is still unaddressed. NOTE: the
   pre-short-circuit placement carries a deliberate comment ("an empty page is where the figure
   matters most") — reordering contradicts a recorded decision and needs sign-off.
   *(2026-08-02 §5/§9)*

8. **Bound the ESI item fan-out with a semaphore + matching `httpx.Limits`.** `_resolve_esi_objects`
   (`background_aggregation.py:115-147`) is a working, tested template with the cap already chosen at
   8 — copy its shape into `_fetch_item_rows`. Steady-state benefit is modest thanks to the
   already-enriched skip, but it turns an `ENRICHMENT_VERSION` bump from an 80-minute
   lock-TTL-violating resweep into a ~10-minute one, which is what makes enrichment fixes safely
   deployable. Must set `httpx.Limits(max_connections=C)` on both clients in the same change.
   *(Task 1 / SP1, SP4)*

9. **Route structlog through `QueueHandler`/`QueueListener`.** Two synchronous JSON renders and
   stdout writes per list request, on the event loop, each carrying an 11-field nested dict — and a
   second synchronous file write wherever `LOG_FILE` is set. Contained change in
   `core/logging.py:91-102`; needs a log-output equality guard, which
   `tests/core/test_logging.py` gives a place to put. *(Task 6 / P8)*

10. **Add `pg_trgm` GIN indexes on `contracts.title` and `contract_items.type_name`.** Real win for
    text search, but genuinely more work than the items above: needs `CREATE EXTENSION`, a dialect
    split (SQLite dev has no trigram), and it interacts with whatever happens to the search join in
    P5. Do item 6 first — debouncing removes 80% of the search queries for free. *(Task 3 / P2)*

11. **Stream the ingestion (async-generator ETag helper, per-batch upsert).** Correct, and it is the
    only fix for peak memory scaling with corpus size. Deferred below the items above only because it
    is the largest single refactor here (3 call sites, changes a return contract) and must preserve
    the `already_enriched` skip and the `processed_contract_ids` bookkeeping that
    `_update_item_processing_status` depends on. Sequence after item 8. *(Task 5 / SP2, SP8, SP10,
    SP11)*

12. **Decide the exact-count strategy for the unfiltered list.** Deferred to F008; F008 has closed
    without deciding. Cached totals, approximate counts above a threshold, or keyset pagination. Needs
    item 2's measurement and a product call on whether "34,116 contracts" may read "about 34,000".
    *(2026-08-02 §9)*

13. **Stand up the ingestion metrics** — run duration, ESI round trips, items fetched — as Prometheus
    instruments beside `last_ingest_success_timestamp`. Cheap, and it is what would let items 3, 8,
    and 11 be *verified* rather than argued. Its value is mostly derivative, which is why it sits
    here rather than at the top. *(Task 0)*

14. **The constant-factor batch.** `from sqlalchemy import select` in `contract_service.py:6` (the
    repo is now inconsistent with `background_aggregation.py`); drop the dead `sorted()` at
    `esi_client_class.py:488`; single-pass `_collect_resolvable_ids`; check redis-py's current
    guidance and switch the four `.close()` calls to `.aclose()` if confirmed. Half an hour total,
    near-zero measurable benefit, non-zero tidiness benefit. Note SP17 needs no work — the
    hand-rolled retry now handles 420/429 and is correctly kept. *(Task 9 / P12, SP14, SP15, SP16)*

15. **Add a bundle-size budget to the web build.** `vite.config.ts` sets no
    `build.chunkSizeWarningLimit` and there is no `size-limit` in `package.json`; Vite's default
    warning does not fail a build. Lowest value here, but it is 3 lines and it is the only surviving
    piece of Task 8. *(Task 8 / FP9, successor)*

16. **Drop the unconditional `commit()` in `get_db`** (`db.py:46`) — measurable only under load, and
    it needs care that write paths still persist. *(Task 6 / P10)*

17. **Single-pass response construction** (`response_model=None` on `api/contracts.py:33`, or pass
    ORM objects through). Real duplicated work that grew with F008's nested composition/blueprint
    objects, but it trades away FastAPI's response-schema enforcement and OpenAPI generation — and
    `openapi.json` is what generates the frontend's types. Do not do this without a JSON
    byte-equality guard and a plan for keeping the schema published. *(Task 6 / P9)*

**Deliberately not listed:** P6 (composite filter+sort index). The plan's recommended
region+date_issued composite targets a query mix that F008 changed — the dominant request now carries
no region filter at all. Re-derive the columns from item 2's measurement before adding an index; a
wrong composite is write-tax for nothing.

**Closed without work, recorded so nobody reopens them:** SP17 (hand-rolled retry — evaluated, kept,
and it now does things httpx transport retries cannot); P11 (`Numeric` for money — decision was
"keep", and the model still does); P13/P14 (subsumed); the S1 false-positive class (parallelizing
count and data queries with `gather` — still a correctness regression, both still share one
`AsyncSession`).
