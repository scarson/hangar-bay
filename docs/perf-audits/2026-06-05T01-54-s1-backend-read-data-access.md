# Performance Audit — Backend Read Path: Data Access & I/O

Scope: `GET /contracts/` read path. Dimension: data access & I/O (SQL/query shape & indexing).
Static-only analysis; no measured numbers. Stack: FastAPI + SQLAlchemy 2.0 asyncio + asyncpg (Postgres prod / SQLite dev) + redis/Valkey.

Files examined:
- `app/backend/src/fastapi_app/api/contracts.py`
- `app/backend/src/fastapi_app/services/contract_service.py`
- `app/backend/src/fastapi_app/models/contracts.py`
- `app/backend/src/fastapi_app/db.py`
- `app/backend/src/fastapi_app/core/dependencies.py`
- `app/backend/src/fastapi_app/core/cache.py`
- `app/backend/src/fastapi_app/schemas/contracts.py`

---

### [CRITICAL impact] Mandated cache-aside is entirely absent from the contracts read path
**Location:** `services/contract_service.py:35-208` (get_contracts) and `api/contracts.py:25-36` (list endpoint); cache infra exists at `core/cache.py:26-66` and `core/dependencies.py:11-22`
**Problem:** The project spec mandates cache-aside for frequently-read data, and a Redis/Valkey client is fully wired up (`get_cache` dependency, `app.state.redis`). But `contract_service.py` never imports or touches the cache (import block `:1-20` has no cache reference; verified no `get_cache`/`redis` symbol in the file). Every interactive browse request therefore executes BOTH the count query and the data query against Postgres unconditionally — there is no read-through, no result memoization, no short-TTL cache of hot first-page/default-sort results. The list endpoint (`api/contracts.py:26-29`) does not even inject the cache dependency.
**Impact:** 2 DB round-trips per request (count + data), 100% of read traffic, zero cache offload. The default landing query (`sort_by=date_issued desc`, `page=1`, no filters) is identical across all users and is the single hottest query shape — a prime cache-aside candidate that currently hits the DB every time. Under interactive browsing this is the dominant, repeated cost and the largest gap versus the P95 < 200 ms / common < 50 ms targets.
**Confidence:** Strong-static (cache wired but provably unreferenced on this path).
**Effort:** Contained — add cache-aside around `get_contracts` keyed on the normalized filter set; invalidation can be coarse (short TTL) given append-mostly contract data. Cross-cutting only if precise invalidation on ingest is required.
**Verification plan:** Confirm by grep that `contract_service.py` / `api/contracts.py` contain no `redis`/`get_cache` reference (done). Add a cache layer keyed on a canonical serialization of `ContractFilters`; guard test: identical filter sets return byte-identical paginated payloads on hit vs miss, and a mutation/ingest invalidates (or TTL-expires) the entry.

---

### [CRITICAL impact] Substring search uses leading-wildcard ILIKE — cannot use any btree index, forces sequential scan
**Location:** `services/contract_service.py:88-96` (`search_term = f"%{filters.search}%"`, `Contract.title.ilike(...)`, `ContractItem.type_name.ilike(...)`)
**Problem:** The search builds a `%term%` pattern (leading wildcard) and applies it with `ILIKE` across `contracts.title` and `contract_items.type_name`. A leading-wildcard `ILIKE` is non-sargable — a plain btree index (the only kind declared: `ix_contracts_title` at `models/contracts.py:73`; `type_name` has no index at all) cannot be used for a `%x%` match. Postgres must sequentially scan and apply the pattern per row. Because the predicate is `OR`-ed across a column in `contracts` AND a column in the joined `contract_items` (`:91-96`), it also forces the outer join (`:79-82`) to materialize before filtering.
**Impact:** Seq Scan over `contracts` (tens of thousands of rows for large regions) plus the joined `contract_items` fan-out on every search request; `Rows Removed by Filter` will be large. Index `ix_contracts_title` is dead weight for this predicate (never used by `%x%`), and `type_name` is unindexed regardless. Scales linearly with contract + item row counts; this is the slowest interactive operation and will blow the 200 ms P95 on large regions.
**Confidence:** Strong-static (leading-wildcard ILIKE is categorically non-btree-sargable; index inventory confirmed).
**Effort:** Contained — replace with Postgres trigram GIN indexes (`pg_trgm`: `CREATE INDEX ... USING gin (title gin_trgm_ops)` and same on `type_name`), which accelerate `ILIKE '%x%'`; or move to full-text (`tsvector` + GIN). Dev runs SQLite so the index strategy must be Postgres-conditional.
**Verification plan:** `EXPLAIN (ANALYZE, BUFFERS) SELECT ... WHERE title ILIKE '%foo%' OR ct.type_name ILIKE '%foo%'` — expect Seq Scan + high `Rows Removed by Filter` before, Bitmap Index Scan on the trigram GIN after. Correctness guard: same result set pre/post index for representative search terms.

---

### [MAJOR impact] Count query wraps the filtered statement in DISTINCT-over-subquery — sort/hash on the full fan-out every request
**Location:** `services/contract_service.py:127-135`
**Problem:** To count distinct contracts despite the one-to-many join, the code does `select(query.subquery().c.contract_id).distinct().subquery()` then `select(func.count())` over it (`:131-132`). When `needs_item_join` is true (any search / type_ids / is_bpc / runs / ship_name sort — `:69-77`), the inner query joins `contract_items`, producing one row per matching item; the `DISTINCT` must then de-duplicate the entire fan-out via a sort or hash-aggregate over all matched item rows before counting. This count query runs on EVERY request (`:134`), in addition to the data query.
**Impact:** 1 of the 2 round-trips/request is this count; with the join active it processes the full item-level fan-out (N items per contract) through a DISTINCT node, not just the contract rows. With no covering/composite index for the filter+`contract_id` projection, the de-dup spills toward `work_mem` limits as matched rows grow. Even when no join is needed, it still wraps a subquery and counts the full filtered set on every page — `COUNT` over a large table per paginated response is the classic pagination tax.
**Confidence:** Strong-static (query shape is explicit; DISTINCT-over-join cost is inherent).
**Effort:** Contained — when no item filter/sort is active, count directly on `contracts` (no subquery, no DISTINCT). When the join is required, prefer `COUNT(DISTINCT contract_id)` pushed down, or restructure so the item predicate becomes an `EXISTS` correlated/anti-join (one contract row per match, no fan-out, no DISTINCT). Consider caching the count for the default unfiltered query (ties into the cache finding).
**Verification plan:** `EXPLAIN (ANALYZE, BUFFERS)` the current count subquery vs an `EXISTS`-rewrite for a search filter — compare for HashAggregate/Sort node, `temp written`, and actual rows processed. Guard: total count must match for filtered and unfiltered cases including contracts with zero items.

---

### [MAJOR impact] Item filters via outer JOIN + DISTINCT instead of EXISTS — row multiplication on hot filters
**Location:** `services/contract_service.py:79-82` (outerjoin) and `:117-125` (type_ids / is_bpc / min_runs / max_runs on `ContractItem`), with `.unique()` at `:177`
**Problem:** Filtering on item attributes (`type_id IN`, `is_blueprint_copy`, `raw_quantity` range) is done by `outerjoin(ContractItem)` then `WHERE` on item columns. This multiplies contract rows by their item count, then forces application-side de-dup (`result.scalars().unique().all()`, `:177`) and the DISTINCT count above. An `OR`-ed `ILIKE` across the joined table compounds it (search finding). For an equality/`IN`/boolean membership test on items, a semi-join (`EXISTS (SELECT 1 FROM contract_items ...)`) returns each contract once with no fan-out.
**Impact:** Every item-filtered request inflates intermediate rows by the average items-per-contract factor before `LIMIT`, doing redundant work the join then collapses. The fan-out also interacts badly with `OFFSET`/`LIMIT` ordering (the sort at `:169` operates over duplicated rows). Scales with items-per-contract × matched contracts.
**Confidence:** Strong-static for the query shape; Heuristic on the magnitude (depends on items-per-contract distribution, stated as 0..N).
**Effort:** Contained — convert item-attribute filters to `EXISTS` subqueries; drop the outer join for the filter case. Keeps `selectinload(Contract.items)` for the projection (that part is already correct).
**Verification plan:** `EXPLAIN (ANALYZE, BUFFERS)` join+DISTINCT vs `EXISTS` for `type_ids=[...]` — expect fewer actual rows and no de-dup node in the EXISTS plan. Guard: identical contract set and ordering both ways.

---

### [MAJOR impact] No index supports the location IN-list filters (region/system/station)
**Location:** `services/contract_service.py:109-114` (`start_location_region_id.in_`, `start_location_system_id.in_`, `start_location_id.in_`) vs `models/contracts.py:70-80` index list
**Problem:** The realistic load filters heavily on `region_ids` / `system_ids` / `station_ids` (IN lists). None of `start_location_region_id`, `start_location_system_id`, `start_location_id` is indexed — the declared indexes (`:70-80`) cover `type,status`, `start_location_name`, `title`, `is_ship_contract`, `price`, `date_issued`, `collateral`, `volume`. The single most common geographic filter (browse a region) hits unindexed columns, forcing a Seq Scan to evaluate the IN predicate, then the `ORDER BY date_issued` sort, then `LIMIT`.
**Impact:** A region browse (the canonical use case) scans the whole `contracts` table to satisfy `region_id IN (...)` — no index seek possible. Combined with the per-request count query this is two full scans. Directly contradicts the spec's mandate to index all WHERE columns. Scales linearly with table size.
**Confidence:** Strong-static (explicit cross-reference: filtered columns absent from the index inventory).
**Effort:** Localized — add btree indexes on `start_location_region_id`, `start_location_system_id`, `start_location_id`. Better: composite `(start_location_region_id, date_issued)` to serve the region-filter-then-date-sort path as an index-ordered scan (equality column first, then ORDER BY column — see composite ordering guidance).
**Verification plan:** `EXPLAIN (ANALYZE, BUFFERS) ... WHERE start_location_region_id IN (...) ORDER BY date_issued DESC LIMIT 50` before/after. Expect Seq Scan + Sort before; Index Scan / Bitmap before sort (or index-ordered, no Sort node) after.

---

### [MAJOR impact] Sort columns price/collateral/volume indexed singly, but never composite with the region filter — sort node survives
**Location:** `services/contract_service.py:157-173` (ORDER BY from SORT_MAP `:24-32`) vs single-column indexes `models/contracts.py:76-79`
**Problem:** Sorts on `date_issued`, `price`, `collateral`, `volume` each have a standalone single-column index (`:76-79`). But the common request shape is *filter by location/price range, then sort* — e.g. `region_id IN (...) ORDER BY price`. A single-column index on `price` cannot serve a query that first filters on `region_id` (or filters on a price range and sorts by a different column); the planner picks the more selective filter (which is currently unindexed per the finding above) and then performs an explicit Sort. The standalone sort indexes only help the *unfiltered* full-table sort, which is the least useful case.
**Impact:** Filtered-and-sorted browses (the norm) incur a Sort node over the filtered set every request; the single-column sort indexes go largely unused whenever a filter is present. The `ship_name` sort (`:31`, maps to `ContractItem.type_name`) additionally requires the join and sorts over the item fan-out, and `type_name` is unindexed.
**Confidence:** Heuristic — depends on the planner's selectivity choice; the shape (filter + different-column sort) reliably defeats single-column sort indexes.
**Effort:** Contained — design composite indexes for the real filter+sort pairs (e.g. `(start_location_region_id, date_issued DESC)`, `(start_location_region_id, price)`); accept that not every filter/sort combination can be covered and index the highest-frequency ones. Weigh added write cost on ingest.
**Verification plan:** `EXPLAIN (ANALYZE, BUFFERS)` the filter+sort combos; look for a `Sort` node and whether it spills (`Sort Method: external merge Disk`). A matching composite index removes the Sort (index returns rows pre-ordered).

---

### [MAJOR impact] No connection-pool configuration on the async engine — defaults under concurrent browse load
**Location:** `db.py:12-18` (`create_async_engine` with only `echo` and `future`)
**Problem:** The async engine sets no pool parameters — no `pool_size`, `max_overflow`, `pool_timeout`, `pool_recycle`, or `pool_pre_ping`. SQLAlchemy's async engine defaults to a small `QueuePool` (size 5 / overflow 10). Each request issues two sequential DB round-trips (count then data, `:134` and `:175`) holding a connection for both; the `get_db` dependency also commits on every read request (`db.py:52`) even though the path is read-only. Under interactive browsing concurrency, 15 in-flight requests exhaust the pool and subsequent requests block up to `pool_timeout` (30 s default). No `pool_recycle`/`pre_ping` means stale sockets behind a proxy/Valkey-adjacent infra surface as errors.
**Impact:** Throughput ceiling at ~15 concurrent DB-using requests before queueing; each request's 2 serialized round-trips double connection hold time versus a single query. Affects all read traffic at concurrency. No measured numbers — query-shape/concurrency argument only.
**Confidence:** Strong-static for the missing config; Heuristic on where the concurrency ceiling actually binds.
**Effort:** Localized — set the four pool params + `pool_pre_ping` explicitly on `create_async_engine` for the Postgres path. Note: `asyncpg`/`AsyncAdaptedQueuePool` defaults still warrant explicit tuning. Behind PgBouncer transaction mode, disable driver statement caching (see orm-database pack).
**Verification plan:** Load-test concurrent `GET /contracts/` beyond 15 in-flight and observe pool-timeout errors / latency cliff; confirm the engine's pool class and size via `async_engine.pool.status()`.

---

### [MINOR impact] `price`/`collateral` are `Numeric` — arithmetic-heavy range filters slower than float, and ORM↔Python Decimal marshaling at the boundary
**Location:** `models/contracts.py:42-43` (`price`, `collateral` as `Numeric`) vs range filters `services/contract_service.py:99-106`
**Problem:** `price` and `collateral` are `Numeric` (arbitrary-precision). Range comparisons (`>= / <=`, `:99-106`) and sorts on these columns are slower than `bigint`/`double precision` in Postgres, and asyncpg returns `Decimal` objects that Pydantic then coerces to `float` in `ContractSchema` (`schemas/contracts.py:41-42` declare `float`) — per-row Decimal→float marshaling on every returned row. `volume`/`reward` are already `Float`, so the type choice is inconsistent.
**Impact:** Minor per-row serialization overhead at the DB boundary (≤ size=100 rows/page) plus modestly slower numeric range/sort. Bounded by page size, so aggregate impact is small relative to the scan/index findings.
**Confidence:** Heuristic — real but small; EVE ISK values may intentionally need precision, so this is a tradeoff not a clear defect.
**Effort:** Contained — if precision beyond float is not required, switch to `Numeric(scale=2)` at minimum (bounded width) or `BigInteger` cents; otherwise leave and accept the cost. Schema currently already downcasts to float, suggesting precision isn't being preserved end-to-end anyway.
**Verification plan:** Compare sort/range `EXPLAIN ANALYZE` cost on a `numeric` vs `double precision` column at representative row counts; confirm whether downstream consumers rely on sub-float precision before changing the type.

---

### [MINOR impact] `item_processing_status` has an index never used by the read path
**Location:** `models/contracts.py:64` (`index=True` on `item_processing_status`)
**Problem:** `item_processing_status` carries a btree index but the contracts read path (`get_contracts`) never filters or sorts on it — it is an ingest/background concern. Likewise `ix_contracts_is_ship_contract` (`:74`) and `ix_contracts_type_status` (`:71`) are not exercised by any filter in `ContractFilters`/`get_contracts`. Every such index is write tax on contract ingest with no read-path benefit here.
**Impact:** No read-path cost; pure write/storage overhead on ingest. Flagged for completeness of the index cross-reference, not a hot-path issue. (Some may serve the ingest pipeline — out of this lane's scope to confirm.)
**Confidence:** Heuristic — read path provably doesn't use them, but other code paths might.
**Effort:** Localized — audit non-read usages before dropping; not actionable from the read path alone.
**Verification plan:** `pg_stat_user_indexes.idx_scan` in production to confirm zero/low scans before removing any index.

---

## Suspected Bugs (for follow-up)

- **Duplicate `get_db_session_factory` definition and duplicate `Base = declarative_base()`** — `db.py:30-34` and `:37-41` define the same function twice; `Base` is assigned at `:6` and re-assigned at `:27`, discarding the first `Base` (any model importing the earlier `Base` would mismatch the engine's metadata). Correctness, not perf — flagging per instructions.
- **`ship_name` sort silently degrades without the item join guarantee** — `SORT_MAP[ship_name]` maps to `ContractItem.type_name` (`contract_service.py:31`); the join is only added when `needs_item_join` includes the ship_name sort condition (`:76`), which is correct, but sorting by an outer-joined nullable `type_name` over a fan-out yields nondeterministic which-item-wins ordering per contract. Behavioral, not this lane.
- **`start_location_id` typed `Optional` in model (`models/contracts.py:48`) but `int` (required) in `ContractSchema` (`schemas/contracts.py:31`)** — a contract with null `start_location_id` would fail response validation. Correctness, follow-up.
