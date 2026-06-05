# Performance Audit — Memory & Allocation Dimension

**Slice:** ESI ingestion / background aggregation
**Date:** 2026-06-05
**Dimension:** memory & allocation (STATIC-ONLY; structural/allocation arguments)
**Stack:** Python 3.11+ asyncio, httpx, SQLAlchemy[asyncio] 2.0 + asyncpg, redis.asyncio, APScheduler

Scope read in full:
- `app/backend/src/fastapi_app/services/background_aggregation.py`
- `app/backend/src/fastapi_app/core/esi_client_class.py`
- `app/backend/src/fastapi_app/services/db_upsert.py`
- `app/backend/src/fastapi_app/core/http_client.py`

---

### [CRITICAL impact] Every region's full contract set accumulated into one in-memory list before any processing

**Location:** `services/background_aggregation.py:127-151` (`run_aggregation`); accumulation at line 133, handed off at 151

**Problem:** `all_contracts_data` is a single `List[dict]` that `extend()`s the *entire* paginated contract result of *every* region in `current_region_ids` before `_process_contracts` is ever called. Each region's `get_public_contracts` already fully materializes all pages internally (see the ETag-helper finding below), so peak holds the raw parsed dict for every contract across every region simultaneously. The realistic load is thousands to tens of thousands of contracts per run, each a JSON object with ~17 fields. Nothing here is bounded or streamed; the list lives for the whole run and is only sliced down in DEV mode (line 149), which does not apply in production.

The natural structural fix is per-region (or per-page) processing: drive `_process_contracts` for one region's contracts at a time so peak is bounded by the largest single region rather than the sum of all regions. The DB upsert is already batched (line 247), so downstream does not require the full list — only the cross-cutting collect-then-process shape forces full materialization.

**Impact:** peak memory scales with **total contracts across all regions per run** (Σ regions), instead of max(region). Linear, unbounded by design.

**Confidence:** Strong-static

**Effort:** Contained — restructure `run_aggregation` to loop region→`_process_contracts`, but `_process_contracts` currently computes a cross-contract `id_to_name_map` and a cross-contract item pass, so the name-resolution batching and item batching would need to be scoped per region (or kept as a second bounded pass). Touches one method's control flow plus the helper's assumptions.

**Verification plan:** Allocation argument — `all_contracts_data` retains every region's contract dict for the lifetime of the run; converting to per-region processing reduces the retained set to one region at a time. Correctness guard: cross-contract ID dedup currently spans all regions (line 188-195); per-region scoping means IDs shared across regions get resolved once per region instead of once globally — acceptable for correctness (names are idempotent) but verify the resolve count does not balloon (could regress the data-access lane); a region-spanning dedup set kept separately preserves the single-resolve property without holding contract dicts.

---

### [CRITICAL impact] `all_items` accumulates every item of every contract across the whole run before upserting

**Location:** `services/background_aggregation.py:255-289` (`all_items` built at 255, extended at 276, drained at 282-289)

**Problem:** `all_items: List[dict]` collects the transformed item rows for *every* eligible contract in the run before the batched upsert loop starts at line 285. Per the realistic load, items can reach 100k+ across a run, each a 7-key dict. The per-contract `item_values` list comprehension (264-275) is itself fine, but `all_items.extend(item_values)` retains all of them until the very end. Because the upsert is already batched at `BATCH_SIZE = 50` (line 284-288), there is no downstream reason to hold the full set — items could be flushed to `bulk_upsert` as they cross a batch threshold while iterating contracts, bounding peak to one batch (plus the current contract's items) instead of the run-wide total.

This is the single largest peak contributor in the slice: items dwarf contracts in count, and the entire `all_items` list coexists in memory with `all_contracts_data`, `contract_values`, and `id_to_name_map` (all still referenced in the same `_process_contracts` frame).

**Impact:** peak memory scales with **total items across all contracts per run** (potentially 100k+ dicts), held simultaneously with the contracts list and the transformed contract list.

**Confidence:** Strong-static

**Effort:** Contained — introduce a running buffer that flushes via `bulk_upsert` whenever it reaches `BATCH_SIZE`, with a final flush after the loop. Localized to the item loop, but interacts with transaction boundaries (currently one commit at `run_aggregation:153`), so verify partial-flush semantics under the single outer transaction.

**Verification plan:** Allocation argument — replacing run-wide accumulation with a fixed-size buffer caps retained item dicts at `BATCH_SIZE + |current contract's items|`. Correctness guard: all flushes must occur inside the same session/transaction so the existing single `commit()` still covers them; confirm no contract's items are split incorrectly across the `ContractItem` PK (`record_id`) and that the final remainder buffer is flushed.

---

### [MAJOR impact] ETag helper materializes all pages into `full_data` instead of yielding per page

**Location:** `core/esi_client_class.py:90` (`full_data = []`), 141 / 152 (`full_data.extend(page_data)`), 180 (`return full_data`)

**Problem:** `get_esi_data_with_etag_caching` accumulates every page of a paginated endpoint into one `full_data` list and returns it whole. For `get_public_contracts` (called with `all_pages=True`) a large region can be many pages; the entire region's contract set is built here before being returned to `run_aggregation`, which then `extend()`s it into `all_contracts_data` — so the full region payload exists twice transiently (the returned list and the accumulator) at the hand-off point. Converting this to an async generator (`yield page_data` per page) would let the caller consume page-by-page and bound peak to a single page, and directly enables the per-region/per-page streaming the CRITICAL findings above need.

This is the structural root that forces the two CRITICAL accumulations: callers cannot stream because the producer only offers a fully-materialized list.

**Impact:** peak memory scales with **one region's full contract set** (all pages) per call; combined with the caller's accumulator it doubles transiently at the `extend` boundary.

**Confidence:** Strong-static

**Effort:** Cross-cutting — changing the return contract from `List[dict]` to an async iterator touches all three call sites (`get_public_contracts:185`, `get_contract_items:190`, `resolve_ids_to_names` is unaffected) and both consumers in `_process_contracts`. The retry/ETag/pagination logic stays intact; only the yield boundary changes.

**Verification plan:** Structural argument — a generator defers allocation to one page at a time; the `while True` pagination loop already processes page-by-page, so `yield page_data` is a mechanical transform. Correctness guard: 304/204/404 break conditions and `X-Pages` termination must still fire identically; ensure ETag writes (165-166) still happen per page before yield.

---

### [MAJOR impact] Redundant materialization: `response.json()` parses the body while `response.content` is cached separately

**Location:** `core/esi_client_class.py:149` (`page_data = response.json()`) and `166` (`self.redis_client.set(data_key, response.content, ...)`)

**Problem:** On a 200 response the body is materialized twice in distinct representations that coexist: `response.json()` (line 149) builds the full parsed Python object graph (list of dicts), and `response.content` (line 166) holds the full raw bytes — both alive in the same scope because the cache write at 166 happens after the parse at 149 within the same iteration. httpx also retains the decoded buffer internally once `.content`/`.json()` is accessed. So for each page, peak transiently holds: raw bytes (`response.content`) + parsed object (`page_data`) + the growing `full_data`. For large contract pages this is a meaningful multiplier on per-page peak.

The cache stores raw bytes (167) but the 304 read path re-parses with `json.loads(cached_data)` (140) — so the cached form is bytes by design. The redundancy is that the *fresh* path keeps both the bytes and the parsed form live simultaneously rather than, e.g., parsing from the already-cached bytes or releasing one before extending `full_data`.

**Impact:** per-page transient peak ≈ raw bytes + parsed object graph held together; scales with **page payload size**, multiplied across pages for the largest regions.

**Confidence:** Heuristic — httpx's internal buffer retention and the exact GC timing of `response` between iterations are implementation-dependent; the double-representation at lines 149+166 is static fact, the magnitude depends on payload size.

**Effort:** Localized — reorder so the raw bytes are released promptly, or parse `page_data` from the cached bytes; confined to the 200-branch.

**Verification plan:** Allocation argument — two full-body representations of the same page are simultaneously reachable across lines 149-166. Correctness guard: the cache must still store the exact bytes ESI returned (so the 304 replay at 140 stays byte-identical); do not substitute a re-serialized `json.dumps(page_data)` which could differ from the original ETag'd bytes.

---

### [MINOR impact] `contract_values` builds a second full-size transformed list, doubling the contracts peak

**Location:** `services/background_aggregation.py:215-241` (`contract_values` comprehension)

**Problem:** `_process_contracts` receives `contracts` (the full `all_contracts_data`) and builds `contract_values`, a same-length list of transformed dicts, while the original `contracts` list is still referenced (it is iterated again at line 256 for items and used for the ID sets at 188-191). So both the raw contract list and the transformed contract list are fully live simultaneously — peak holds ~2× the contract dict count. The upsert loop at 247 only ever needs one 500-row slice at a time, so the full `contract_values` materialization is not required by the sink; a generator feeding `bulk_upsert` per batch, or transforming within the batch loop, would avoid the second full list.

Rated MINOR relative to the item accumulation because contracts are the smaller collection and the original `contracts` list must persist anyway for the item pass — so only the *duplicate* transformed copy is the avoidable cost, not the original.

**Impact:** peak memory holds **2× the contract dicts** (raw + transformed) for the contract-upsert phase; scales with contracts per run.

**Confidence:** Strong-static

**Effort:** Localized — move the transform into the `range(0, total, batch_size)` loop (transform each 500-slice on demand) so only one batch of transformed dicts exists at a time. `total_contracts` count would come from `len(contracts)` instead.

**Verification plan:** Allocation argument — transforming per-batch caps the transformed-dict count at `batch_size` (500) instead of the full run. Correctness guard: `id_to_name_map` lookups (234-236) must still be available inside the loop (it is computed before, so fine); ensure batch boundaries and count logging stay correct.

---

## Suspected Bugs (for follow-up)

None.
