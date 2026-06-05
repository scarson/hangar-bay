# Performance Audit — Backend ESI Ingestion / Background Aggregation
## Dimension: Data Access & I/O (DB writes + external HTTP)

Slice: `superpowers-plus/performance-audit`, ESI ingestion / background aggregation lane.
Method: STATIC-ONLY. Round-trip-shape reasoning; no fabricated latency numbers. Load context: every 900 s; thousands–tens of thousands of contracts/run; 100k+ items/run; per item-bearing contract one ESI items fetch.

Scope read:
- `services/background_aggregation.py`
- `core/esi_client_class.py`
- `services/db_upsert.py`
- `core/http_client.py`
- `models/contracts.py` (adjacent — PK/index reference)

---

### [CRITICAL impact] Per-contract item fetch is a serial HTTP N+1 — one ESI round-trip per item-bearing contract, fully sequential
**Location:** `services/background_aggregation.py:255-281` (the `for contract in contracts:` loop, `await self.esi_client.get_contract_items(...)` at :261)
**Problem:** Items are fetched one contract at a time with a blocking `await` inside a Python `for` loop. There is no concurrency (no `asyncio.gather`, no bounded `Semaphore` fan-out) and no coalescing. Every `item_exchange`/`auction` contract = exactly one ESI HTTP GET to `/v1/contracts/public/items/{contract_id}/`. With "thousands to tens of thousands" of contracts per run and the majority being item-bearing, this is the dominant I/O cost of the entire run, and because the calls are serialized, total wall time = Σ per-request latency (including ESI's per-endpoint latency + retry backoff on any 5xx). The shared `httpx.AsyncClient` and the asyncio event loop are designed to run many of these in flight at once; here they run strictly one-at-a-time.
**Impact:** **HTTP round-trips per run = (number of item-bearing contracts)**, i.e. thousands–tens of thousands, scaling linearly with item-bearing contract count. Latency scales linearly (serial), so a 10k-contract run pays ~10k × single-request RTT end-to-end. This is the single largest round-trip multiplier in the slice. ESI itself rate-limits/error-limits, so naive unbounded parallelism is wrong — the fix is *bounded* concurrency (e.g. `asyncio.Semaphore(N)` + `gather`), which collapses wall time by ~N× while respecting the error-limit budget. ETag caching in `get_contract_items` reduces *bytes* on a 304 but does NOT reduce round-trips: a request is still issued per contract every run.
**Confidence:** Strong-static (loop structure and per-call `await` are explicit).
**Effort:** Contained — introduce a bounded `gather` over `get_contract_items`, collect results, then batch-upsert. Must add a concurrency cap to stay under ESI error limits and must preserve per-contract error isolation (currently each contract's failure is caught independently).
**Verification plan:** Count round-trips: instrument/log one HTTP GET per item-bearing contract per run and confirm count == item-bearing contract count. Confirm serialization by observing wall time ≈ N × RTT before fix. After fix, assert wall time ≈ (N / concurrency) × RTT and that total ESI requests is unchanged (same round-trip count, parallelized — not reduced). Guard ESI error-limit headers (`X-ESI-Error-Limit-Remain`) to size the semaphore.

---

### [MAJOR impact] Item upsert batch size of 50 issues ~10× more INSERT…ON CONFLICT statements than the contract path (500)
**Location:** `services/background_aggregation.py:284-288` (`BATCH_SIZE = 50`) vs the contract path `batch_size = 500` at :243
**Problem:** Items are upserted in batches of 50 rows per `INSERT … ON CONFLICT DO UPDATE`, while contracts use 500. With 100k+ items per run that is **100000 / 50 = ~2000 DB round-trips** for items alone. The `contract_items` row is narrow (7 inserted columns), so PostgreSQL's bound-parameter ceiling (~65 535 params/statement) is nowhere near binding: 7 cols × 500 rows = 3500 params, × 1000 rows = 7000 params — both far under the limit. Batch 50 is leaving an order of magnitude of round-trip reduction on the table for no parameter-limit reason. Each statement is a separate `await db.execute(...)` → one network round-trip to Postgres (asyncpg) plus per-statement parse/plan overhead.
**Impact:** **DB round-trips for items per run ≈ ceil(item_count / 50)** — ~2000 at 100k items, scaling linearly with item count. Raising the batch to 500 cuts this to ~200 (10×); to 1000, ~100 (20×). Statements/run is the metric; the reduction is pure round-trip + parse-overhead savings. (The contract path's 500 is already reasonable: ~20 cols × 500 = ~10k params, still under the ceiling.)
**Confidence:** Strong-static (constant is literal; param math from `models/contracts.py` column count).
**Effort:** Localized — change one constant; optionally compute it from a target param budget (`floor(65535 / cols_per_row)` with margin).
**Verification plan:** Round-trip count argument: log `ceil(len(all_items)/BATCH_SIZE)` executes/run before and after. Param-limit guard: assert `cols_per_row × batch ≤ ~60000`. EXPLAIN/timing on a representative batch to confirm no plan regression at the larger row count.

---

### [MAJOR impact] ON CONFLICT DO UPDATE rewrites every non-PK column every run — including unprovided and indexed columns — inflating write + index-maintenance cost
**Location:** `services/db_upsert.py:33-39` (and the SQLite branch :42-48); `set_` built from `{c.name: c for c in stmt.excluded if c.name not in primary_key_cols}`
**Problem:** The update set is *every* non-PK column of the table, unconditionally, on every conflicting row. Two consequences for the Contract upsert (run with thousands–tens of thousands of conflicting rows each cycle, since the same contracts reappear region-over-region across runs):
1. **Indexed-column churn.** `contracts` carries 9 secondary indexes (`type_status`, `start_location_name`, `title`, `is_ship_contract`, `price`, `date_issued`, `collateral`, `volume`, `item_processing_status`). Updating a column that participates in an index dirties that index even when the value is unchanged. On Postgres a non-HOT update (any indexed column in the SET) writes a new heap tuple version + new index entries for *all* indexes and creates dead tuples → autovacuum pressure (see postgres.md MVCC/HOT bullet). Touching `price/collateral/volume/date_issued/title/...` every run defeats HOT.
2. **`item_processing_status` clobber + correctness coupling.** The contract values dict (`background_aggregation.py:238`) sets `item_processing_status = "PENDING_ITEMS"` on every run, and the upsert SET includes it — so every existing contract's item-processing progress is reset to PENDING on every aggregation cycle. This is both a write the run shouldn't make and a logic reset (the column is indexed, line 64). Also note `stmt.excluded` enumerates *table* columns not present in the INSERT VALUES (e.g. `start_location_system_id`, `start_location_region_id`, `items_last_fetched_at`, `contract_esi_etag`); including those in `set_` references the EXCLUDED pseudo-row's value for a column that was never supplied — at minimum redundant, and risks overwriting independently-maintained columns (`items_last_fetched_at`, `contract_esi_etag`) back to their insert-defaults/NULL. Flagged for correctness below.
**Impact:** DB *write amplification* per run scales with (conflicting-row count × indexes touched). For the contract path that is thousands–tens of thousands of rows × up-to-9 indexes of avoidable index maintenance + dead-tuple generation each 900 s cycle. Narrowing the SET to genuinely-mutable columns (and excluding PK-stable + independently-owned columns) restores HOT-update eligibility for rows whose indexed columns didn't change and stops the PENDING reset.
**Confidence:** Strong-static for the "updates all non-PK columns" shape and the index list; Heuristic on the magnitude of HOT/vacuum savings (depends on real change rate, which needs `pg_stat_user_tables`).
**Effort:** Contained — `bulk_upsert` is generic; either pass an explicit updatable-column allowlist per call site, or derive the SET from the keys actually present in `values` (cheap, removes the unprovided-column bug) and let call sites exclude progress/etag columns.
**Verification plan:** Read generated SQL (`stmt.compile()`) to confirm current SET column list. `EXPLAIN (ANALYZE, BUFFERS)` an upsert batch and inspect heap/index buffer writes + `n_tup_hot_upd` vs `n_tup_upd` in `pg_stat_user_tables` before/after narrowing. Correctness guard: assert `item_processing_status`, `items_last_fetched_at`, `contract_esi_etag` are no longer in the SET.

---

### [MAJOR impact] Regions fetched sequentially — all-pages contract pagination per region runs one region at a time
**Location:** `services/background_aggregation.py:129-138` (`for region_id in current_region_ids:` with `await self.esi_client.get_public_contracts(region_id)`), feeding `get_esi_data_with_etag_caching(..., all_pages=True)` at `esi_client_class.py:95-180`
**Problem:** Each region's contracts are fetched (all pages, serial page-walk inside `get_esi_data_with_etag_caching`) before the next region starts. Region fetches are independent and could run with bounded concurrency. Within a region the page loop is necessarily sequential only because `X-Pages` is read from page 1's response — but ESI returns `X-Pages` on page 1, so pages 2..N for a region could also be fetched concurrently once page count is known. As-is, total contract-fetch wall time = Σ over regions of (Σ pages × RTT).
**Impact:** **HTTP round-trips per run = Σ_region (pages_in_region)** (unchanged by parallelizing — same count), but wall time is currently the *sum* of all of them serially. Parallelizing regions (and optionally pages 2..N within a region) cuts contract-fetch latency by up to (#regions × avg-pages)× subject to a concurrency cap. Scales with region count × pages/region.
**Confidence:** Strong-static (serial loop; page loop increments `page` with blocking await).
**Effort:** Contained — `gather` regions under a semaphore; within `get_esi_data_with_etag_caching`, optionally fetch page 1, read `X-Pages`, then `gather` the remainder. The page-walk refactor touches retry/ETag bookkeeping, so keep it bounded.
**Verification plan:** Count round-trips (Σ pages) and confirm unchanged after parallelization; measure wall-time drop. Preserve per-region `ESINotModifiedError`/exception isolation that the current loop provides.

---

### [MINOR impact] ETag path issues serial, uncoalesced Redis round-trips per page (2 GET + up to 2 SET)
**Location:** `esi_client_class.py:100` (`get(etag_key)`), `:138` (`get(data_key)` on 304), `:165-166` (two separate `set(...)` calls)
**Problem:** Per page the code does a Redis `GET etag_key`, and on a 304 a second `GET data_key`; on a fresh 200 it does two sequential `SET`s (etag, then data). These are independent keys that could be pipelined (`MGET` / a single pipeline round-trip) instead of separate awaited calls. Redis is local/fast, so per-call cost is small, but the page count across the whole run is large: it scales with (Σ region pages) + (item-bearing contracts), i.e. thousands–tens of thousands of pages, each paying 2–3 serial Redis RTTs.
**Impact:** **Redis round-trips per run ≈ 2–4 × (total ESI pages fetched)** — thousands–tens of thousands of serial Redis RTTs, scaling with page/contract count. Pipelining the GET pair and the SET pair roughly halves Redis round-trips on the hot path. Low per-call cost keeps this MINOR, but it compounds with the item N+1's page count.
**Confidence:** Strong-static.
**Effort:** Localized — combine the etag/data GETs and the two SETs into pipeline calls.
**Verification plan:** Count Redis ops/run before/after (expect ~2× reduction on cache-hit and write paths). Confirm correctness of MGET decode for the absent-key case.

---

### [MINOR impact] Fresh async engine created and disposed every run — connection pool never reused across cycles
**Location:** `services/background_aggregation.py:113-123` (`create_async_engine(...)` per run) and `:169-173` (`engine.dispose()` in `finally`)
**Problem:** A brand-new `AsyncEngine` (and its connection pool) is built at the start of every aggregation run and disposed at the end. Because runs are 900 s apart and each run is long-lived, the pool *is* reused within a run, so the per-run connection-establishment cost (one TCP+auth to Postgres) is paid once per cycle, not per query — this is why it's MINOR, not MAJOR. The cost is a single cold connection setup every 900 s plus loss of any cross-run prepared-statement/plan caching. The reference pack flags zero-lifetime pools as a per-request tax; here the lifetime is per-run, which bounds the damage. Additionally the engine is created with all-default pool parameters (no `pool_size`/`pool_recycle`/`pool_pre_ping`) — acceptable for a single-session batch job but worth pinning if item-fetch concurrency (Critical finding) later drives concurrent sessions.
**Impact:** ~1 extra Postgres connection-establishment per run (per 900 s); negligible per-query impact since the session is reused within the run. Does not scale with contract/item count.
**Confidence:** Strong-static.
**Effort:** Contained — hoist a module/app-level engine and reuse across runs; but weigh against the deliberate "picklable standalone background job" design (the code comments suggest on-demand client creation is intentional for APScheduler).
**Verification plan:** Confirm one connection-open per run via `pg_stat_activity`/connection logs; verify no per-batch reconnect. Only worth acting on if/when concurrent sessions are introduced.

---

## Suspected Bugs (for follow-up)

1. **`get_contract_items` drops item pages (no `all_pages=True`).** `esi_client_class.py:187-190` calls `get_esi_data_with_etag_caching(path)` with `all_pages` defaulting to `False` (`:84`). The method `break`s after page 1 (`:168-169`). Any contract whose items span more than one ESI page (`X-Pages > 1`) silently loses items beyond page 1. Per audit rules: recorded, not chased. Fix is `all_pages=True` (mirrors `get_public_contracts` at :185), but note this *increases* HTTP round-trips for multi-page contracts.

2. **`item_processing_status` reset to `PENDING_ITEMS` every run via the upsert SET.** `background_aggregation.py:238` always sets the value and `db_upsert.py:33-39` includes it in `set_`, so every existing contract's item-processing state is overwritten each cycle (also an indexed column — `models/contracts.py:64`). Likely unintended progress clobber. (Detailed in the MAJOR ON CONFLICT finding.)

3. **ON CONFLICT `set_` references columns absent from the INSERT VALUES.** `db_upsert.py` builds `set_` from `stmt.excluded` (all table columns), but `values` supplies only a subset. Columns like `items_last_fetched_at`, `contract_esi_etag`, `start_location_system_id`, `start_location_region_id` are set to the EXCLUDED pseudo-row's value for a column that was never provided — risk of overwriting independently-maintained columns back to insert-default/NULL on every upsert. Needs verification of SQLAlchemy's EXCLUDED behavior for unsupplied columns, then narrow the SET to keys present in `values`.
