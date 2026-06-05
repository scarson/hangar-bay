# Performance Audit — Concurrency & Parallelization lane

**Slice:** s2-backend-ingest (ESI ingestion / background aggregation)
**Dimension:** concurrency & parallelization (network fan-out)
**Date:** 2026-06-05
**Mode:** STATIC-ONLY. Structural arguments; no measured numbers.

Scope read: `services/background_aggregation.py`, `core/esi_client_class.py`,
`services/db_upsert.py`, `core/scheduler.py`, `core/http_client.py`,
plus `services/scheduled_jobs.py` (job wrapper).

---

### [CRITICAL impact] Per-contract item fetch is a sequential `await` loop over thousands of independent contracts

**Location:** `services/background_aggregation.py:255-281` (loop), each iteration `await self.esi_client.get_contract_items(...)` at `:261`; underlying call `core/esi_client_class.py:187-190`.

**Problem:** `_process_contracts` iterates every `item_exchange`/`auction` contract and `await`s `get_contract_items(contract_id)` one at a time. Per the load brief this loop runs thousands to tens of thousands of times per run. Each `get_contract_items` is a separate external ESI HTTP round-trip (`/v1/contracts/public/items/{id}/`) that is almost entirely network wait. Because the calls are serialized with `await`, total wall-time for this phase is `N × (round-trip latency)` — the event loop sits idle waiting on one socket at a time while it could be servicing many.

The work is independent and safe to overlap on the **fetch** side:
- Each call takes only `contract["contract_id"]` (`:261`) and returns its own list; no iteration reads another iteration's result.
- The only shared mutable state is `all_items.extend(item_values)` (`:276`), a list whose final ordering is irrelevant — it is later re-chunked and upserted by primary key (`:282-289`), and `bulk_upsert` does `on_conflict_do_update` keyed on PK (`db_upsert.py:36-38`), so row order does not affect the result set.
- ETag/data Redis writes inside the fetch (`esi_client_class.py:165-166`) are per-path keys (`etag:{path}`, `data:{path}`); concurrent fetches of distinct contract_ids touch distinct keys, no key collision.

**Critical constraint — the DB write must stay serialized.** The single `AsyncSession` (`background_aggregation.py:125`) is NOT concurrency-safe, and `bulk_upsert` (`:288`) issues statements on it. The correct shape is: fan out only the **network fetch** under a bounded `asyncio.Semaphore`, collect results, then keep the existing sequential `bulk_upsert` batching unchanged. Do not move `bulk_upsert` inside the concurrent region.

**Impact:** Serial: `N` sequential round-trips, wall-time `≈ N × latency`. Bounded-concurrent with cap `C`: `≈ ceil(N/C) × latency`. For `N` in the thousands this is the dominant cost of the entire run and the single highest-value change in the slice.

**Confidence:** Strong-static (independence of fetches verifiable from the code; PK-keyed upsert removes ordering dependence).

**Effort:** Contained — refactor the loop into a semaphore-bounded `gather` of fetch coroutines, then a sequential transform+upsert pass. Must add pool sizing (see the pool-limits finding) and keep DB writes serial.

**Verification plan:**
- Structural: confirm no iteration of the loop reads `all_items` or another contract's result; the only cross-iteration write is the order-independent `extend`.
- Correctness guard: assert the multiset of `(contract_id, record_id)` rows produced concurrently equals the multiset produced by the current serial loop (sort both before compare). Run the existing serial path and the concurrent path against the same fixture; row sets must be identical.
- Concurrency cap: bound with a `Semaphore(C)` where `C` is small (single-digit to low-tens) and set httpx `Limits(max_connections>=C)` so the pool does not become the bottleneck. Keep `C` well under ESI's per-IP error/rate budget; an unbounded `gather(*[...])` over thousands of contracts would open thousands of sockets at once and trip ESI rate limiting / exhaust the pool — that is a regression, not the fix. Preserve per-call timeout/retry (already in `get_esi_data_with_etag_caching`).

---

### [MAJOR impact] Per-region public-contract fetches run sequentially despite being independent

**Location:** `services/background_aggregation.py:129-137`, `await self.esi_client.get_public_contracts(region_id)` at `:131`.

**Problem:** The region loop `await`s each region's paginated contract fetch in series. Each `get_public_contracts` is itself a multi-page sequential ESI fetch (`esi_client_class.py:182-185` → `all_pages=True`). Regions are fully independent: each call takes only `region_id`, results are appended via `all_contracts_data.extend(...)` (`:133`) with no ordering dependency, and ETag/data keys are per-path so distinct regions write distinct Redis keys. The number of regions is the configured `AGGREGATION_REGION_IDS` set — typically modest, but each fetch is a chain of paginated round-trips, so serializing across regions multiplies several independent multi-page chains end-to-end.

**Impact:** Serial: `sum over regions of (pages_r × latency)`. Region-concurrent: `≈ max over regions of (pages_r × latency)` (pagination within a region stays sequential — see below). Smaller absolute win than the per-contract loop because region count is bounded, but a clean, low-risk overlap of multi-page chains.

**Confidence:** Strong-static.

**Effort:** Localized — wrap the region fetches in a bounded `gather` (cap = region count is already small, but still cap it and share the pool), then `extend` results. The `try/except ESINotModifiedError/Exception` per region must be preserved per-task (use `return_exceptions` or per-coro try) so one region's failure does not cancel the others.

**Verification plan:**
- Structural: confirm `all_contracts_data` order is never depended upon downstream — `_process_contracts` builds sets/maps and upserts by PK, so order is irrelevant.
- Correctness guard: assert the set of `contract_id`s collected concurrently equals the serial set; assert per-region error handling still isolates failures (inject a failing region, confirm others still ingest).
- Concurrency cap: cap at region count under a shared semaphore/pool; do not let region fan-out plus contract fan-out (above) jointly exceed the chosen pool/rate budget — they should share one global semaphore or be phased so the combined in-flight count stays bounded.

---

### [MAJOR impact] ID-resolution chunks POSTed sequentially though each chunk is an independent request

**Location:** `core/esi_client_class.py:192-216`, loop `:202-214`, `await self.http_client.post("/v3/universe/names/", json=chunk)` at `:205`.

**Problem:** `resolve_ids_to_names` splits unique IDs into 1000-id chunks and `await`s each `POST /v3/universe/names/` in series, merging into `resolved_names` (`:208`). Each chunk POST is an independent ESI round-trip; the only shared state is the `resolved_names` dict, written under distinct `item['id']` keys (`:208`) so concurrent merges do not collide. With tens of thousands of contracts the unique issuer/corp/location ID set can span multiple chunks, each a full network round-trip serialized behind the previous.

**Impact:** Serial: `ceil(unique_ids / 1000) × latency`. Bounded-concurrent: `≈ ceil(chunks / C) × latency`. Magnitude scales with distinct entity count; secondary to the per-contract loop but on the same critical path (runs before item fetch at `:211`).

**Confidence:** Strong-static.

**Effort:** Localized — `gather` the chunk POSTs under a small cap, then merge results. Per-chunk `try/except` (`:209-214`) must remain per-task so one failed chunk does not abort the rest (current `continue` semantics → use `return_exceptions` and skip failures).

**Verification plan:**
- Structural: dict writes are keyed by resolved `id`; chunk membership is disjoint by construction (`unique_ids[i:i+chunk_size]`), so no key is written by two chunks.
- Correctness guard: assert the concurrent `resolved_names` dict equals the serial dict for the same input ID list; assert a single failing chunk leaves the other chunks' names present (same as current `continue` behavior).
- Concurrency cap: small cap (chunks are large; few of them). Counts against the same ESI rate budget as the other lanes — keep it inside the global bound.

---

### [MAJOR impact] httpx clients use default connection-pool limits, capping any fan-out and risking pool starvation

**Location:** `core/esi_client_class.py:65-69` (managed client, the one used by the background job) and `core/http_client.py:16-20` (request-path client). Neither passes `limits=httpx.Limits(...)`.

**Problem:** Both `httpx.AsyncClient` instances are constructed without a `Limits` object, so they use httpx defaults (`max_connections=100`, `max_keepalive_connections=20`). Today the ingestion path is fully serial, so this is latent. But it is a hard prerequisite/interaction for every parallelization above: if fetches are fanned out without raising/aligning the pool limit, the pool itself becomes the bottleneck or blocks tasks waiting for a free connection. Conversely, the default of 100 is large enough that a naive unbounded `gather` over thousands of contracts would happily open up to 100 simultaneous ESI connections — likely tripping ESI's per-IP rate/error budget. The pool limit and the application-level semaphore cap must be chosen together.

**Impact:** Determines whether the concurrency wins above are realizable and bounded. Without explicit `Limits`, fan-out is implicitly bounded at the wrong number (100) for the ESI rate budget.

**Confidence:** Strong-static (no `Limits`/`max_connections` anywhere in `src` — grep returned no matches).

**Effort:** Localized — add `limits=httpx.Limits(max_connections=C, max_keepalive_connections=C)` to the background-job client at `esi_client_class.py:65`, with `C` matching the global ingestion semaphore cap.

**Verification plan:**
- Structural: confirm the managed client (`:64-69`) is the one used during `async with self.esi_client` in `run_aggregation` (`background_aggregation.py:110`). Set `max_connections == semaphore cap` so neither layer silently over- or under-bounds the other.
- Correctness guard: none needed (config only); verify no behavioral change on the serial path.
- Concurrency cap: choose `C` conservatively relative to ESI's documented per-IP limits; the semaphore is the authority on in-flight requests, the pool limit is the safety net at exactly the same value.

---

### [MINOR impact] On-demand Redis client created per lock acquisition and per ESIClient context, and engine created per run

**Location:** Redis-per-lock at `background_aggregation.py:67` (`aioredis.from_url` inside `_concurrency_lock`); Redis-per-context at `esi_client_class.py:71` (`__aenter__`); engine-per-run at `background_aggregation.py:118` (`create_async_engine`) disposed at `:172`.

**Problem:** Each run constructs a fresh Redis connection for the lock, a second fresh Redis connection inside the ESIClient context, and a fresh async engine (new asyncpg pool, paying connection setup). These are creation-cost items on a path that runs every 900 s, not a hot per-item path, so the absolute cost is bounded and amortized across a multi-minute run. Flagged for completeness as a connection-reuse defect, not a high-value win: the per-run fixed cost is dwarfed by the thousands of ESI round-trips this lane is really about.

**Impact:** Small per-run fixed setup/teardown cost; does not scale with contract count.

**Confidence:** Strong-static.

**Effort:** Contained — would require threading a shared Redis client and a shared/long-lived engine into the service rather than minting them per run; touches DI wiring.

**Verification plan:** Structural only (resource-reuse); no result-set guard needed. Note this is below the calibration bar relative to the network-fan-out findings — listed so it is not mistaken for an oversight.

---

### [MINOR impact] Sequential pagination inside a single ESI resource is effectively non-parallelizable as written

**Location:** `core/esi_client_class.py:95-180`, page loop; `page += 1` at `:178`, `X-Pages` checked at `:174-176`.

**Problem:** The brief lists "sequential pagination" as a candidate. Structurally it is NOT a safe fan-out target as currently written: the loop only learns the total page count from the `X-Pages` response header of a fetched page (`:174`), and each page's ETag/data is read/written before deciding whether to continue (`:100-166`). You cannot fan out pages 2..N until page 1 returns `X-Pages`. A correct parallelization would require a two-phase change (fetch page 1, read `X-Pages`, then bounded-`gather` pages 2..N) — but per-region page counts are typically small and the big win is across contracts/regions, not within one resource's pages. Reporting as MINOR so the lane is complete and to record the independence caveat.

**Impact:** Low; per-resource page counts are small and the across-resource lanes dominate.

**Confidence:** Heuristic (depends on typical `X-Pages` per region, not statically known).

**Effort:** Contained — requires restructuring `get_esi_data_with_etag_caching` into a page-1-then-fan-out shape; not worth it ahead of the across-contract lane.

**Verification plan:** If pursued: fetch page 1, capture `X-Pages`, bounded-`gather` remaining pages, concat in page order; guard that the concatenated result equals the serial `full_data`. Keep within the global ESI semaphore.

---

### [MINOR impact] APScheduler job allows overlapping runs only via Redis lock; default `max_instances=1` plus `misfire_grace_time` interaction

**Location:** `core/scheduler.py:35-44` (`add_job`, no `max_instances`/`coalesce`), Redis lock at `background_aggregation.py:62-87`, lock TTL `AGGREGATION_LOCK_TIMEOUT = 1800` at `:29`.

**Problem:** Concurrency-control observations relevant to the fan-out work:
- `add_job` does not set `max_instances` (defaults to 1) or `coalesce`, with `misfire_grace_time=300` (`scheduler.py:42`). If a run exceeds the 900 s interval, APScheduler will skip/misfire rather than overlap, and the Redis lock (`:70-72`, `nx=True`) is a second guard that makes a concurrent run exit via `ConcurrencyLockError`. This is correctly defensive — important because the parallelized run must still be treated as a single logical run holding one lock and one DB session.
- The lock TTL is 1800 s (`:29`) vs a 900 s interval. After parallelization, run wall-time should drop, so the TTL stays safely above run duration. But note the lock is best-effort: if a run ever exceeds 1800 s the TTL expires and a second run could start — the parallelization REDUCES this risk by shortening runs, which is the desired direction.

**Impact:** No regression introduced by this code; it bounds run overlap correctly. Flagged so the parallelization work preserves the single-lock/single-session invariant rather than spawning concurrent runs.

**Confidence:** Strong-static (for the structural guards); Heuristic for the TTL-vs-duration margin (duration not measured).

**Effort:** Localized if `max_instances=1`/`coalesce=True` are made explicit for clarity.

**Verification plan:** Structural — confirm the parallelized run still holds exactly one Redis lock and one `AsyncSession` for its whole duration; the bounded fan-out lives *inside* one locked run, never as multiple scheduled instances. No numeric measurement claimed.

---

## Suspected Bugs (for follow-up)

- **`response` possibly unbound on first-iteration network failure** — `core/esi_client_class.py:103,108-126`: `response` is set to `None` then assigned inside the retry loop; control-flow guarantees `last_exception` is raised before `response` is dereferenced at `:128`, but this is fragile. Correctness, not concurrency — flagging only.
- **Per-region/per-contract exceptions are swallowed and counted as "no data"** — `background_aggregation.py:136-137,279-280`: a broad `except Exception` logs and continues, so a partially-failed ESI run silently produces an incomplete upsert with no failure signal. This interacts with any fan-out (`return_exceptions=True` would preserve current swallow-and-continue semantics) but is a pre-existing correctness/observability concern, not in this lane's scope.

These are correctness items, not chased here.
