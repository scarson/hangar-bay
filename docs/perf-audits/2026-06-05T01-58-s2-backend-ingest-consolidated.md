---
run_schema_version: 1
run_id: 2026-06-05T01-58-s2-backend-ingest
date: 2026-06-05T01:58:00Z
scope: "Backend ESI ingestion & background aggregation (scheduled job) — slice S2 of whole-repo audit"
methodology:
  skill: performance-audit
  plugin_version: superpowers-plus@0.2.0
dispatch:
  model_requested: "latest-opus (Agent-tool subagents)"
  reasoning_effort: "default (harness exposes no knob)"
  overridden_by_user: false
stack:
  - { ecosystem: pypi, framework: httpx, version: "0.28" }
  - { ecosystem: pypi, framework: sqlalchemy, version: "2.0.41" }
  - { ecosystem: pypi, framework: asyncpg, version: "0.30" }
  - { ecosystem: pypi, framework: redis, version: "6.2" }
  - { ecosystem: pypi, framework: apscheduler, version: "3.11" }
currency_briefs:
  - { framework: python-stack, researched_on: 2026-06-03, status: "version-index only (no redis/httpx/apscheduler entry); LOW for those" }
lanes_run: [algorithmic, memory, data-access, concurrency, idiom-currency, cost-map]
lanes_skipped: { payload-startup: "backend job, no payload/startup surface", dynamic: "deferred — no running ESI/PG/dataset; static-only" }
finding_counts:
  by_impact: { critical: 3, major: 7, minor: 7 }
  by_lane: { algorithmic: 3, memory: 5, data-access: 6, concurrency: 6, idiom-currency: 4 }
  suspected_bugs: 7
regression:
  prev_run_id: null
  new: 17
  persisting: 0
  resolved: 0
---

# Performance Audit — Backend ESI Ingestion & Aggregation (S2)

**Date:** 2026-06-05 01:58 UTC   **Scope:** the scheduled aggregation job (every 900 s) — slice S2 of whole-repo
**Stack:** httpx 0.28 / SQLAlchemy[asyncio] 2.0.41 + asyncpg / redis 6.2 / APScheduler 3.11
**Currency brief:** version-index `python.md` (covered_through 2026-06-03; **no** redis/httpx/APScheduler entries → those findings LOW/Heuristic, flagged for manual currency check).
**Lanes run:** all six core. *(payload-startup N/A; dynamic deferred — static-only.)*
**Dispatch:** 6 blind subagents, lane-reads-own-pack. **Blind discovery:** three independent lanes (data-access, concurrency, cost-map) converged on the same dominant finding — the serial per-contract ESI fetch — from different framings; the `algorithmic` lane honestly returned "no critical/major" (no quadratic), the anti-padding discipline holding.
**Regression vs none:** 17 new (first run for this scope).

## The run's time budget (from the cost-map lane)
For R regions, P pages/region, N contracts, M item-bearing contracts, the run **serially** issues
≈ `Σ P` (contract pages) + `ceil(unique_ids/1000)` (name POSTs) + **`M`** (item GETs) ESI round-trips,
plus `ceil(N/500)` + `ceil(items/50)` DB upserts. **M dominates by 1–2 orders of magnitude** and is
fully serialized → e.g. 100 ms × 10k contracts ≈ 1000 s, which *exceeds the 900 s interval*. The
per-contract item fetch IS the run.

## Critical Findings

### SP1. Per-contract item fetch is a serial `await` loop — a network N+1 over thousands of contracts
**Lanes:** concurrency, data-access, cost-map (agreement ×3)   **Location:** `services/background_aggregation.py:255-281` (await `:261`)
**Fingerprint:** `concurrency:background_aggregation.py:process_contracts:serial-item-fetch-n-plus-1`   **Status:** new
**Problem:** For every item-bearing contract the code `await`s `get_contract_items(contract_id)` one at a time. The fetches are independent (only input is `contract_id`; `all_items.extend` is order-irrelevant; ETag keys are per-path), so wall-time is `Σ` of per-call latency instead of `max`. This is the dominant cost of the entire job.
**Impact:** M sequential WAN round-trips/run (thousands–tens of thousands); at realistic M the run can exceed its own 900 s interval. **Confidence:** Strong-static. **On cost map:** yes (High). **Effort:** Contained.
**Verification plan:** bound the *network* fetch with an `asyncio.Semaphore(C)` + `gather`; **keep `bulk_upsert` serial on the single `AsyncSession`** (not concurrency-safe) and **set the httpx pool limit = C** (see SP4) so the fan-out can't trip ESI rate limits. Guard = the resulting `all_items` multiset equals the serial path's on a fixture; cap `C` conservatively (see Design Decisions).

### SP2. Whole-run in-memory accumulation — every region's contracts and every contract's items held before flush
**Lanes:** memory (×2 CRITICAL), cost-map   **Location:** `services/background_aggregation.py:127-151` (contracts), `:255-289` (items)
**Fingerprint:** `memory:background_aggregation.py:process_contracts:whole-run-accumulation`   **Status:** new
**Problem:** `all_contracts_data` extends *every* region's full result before processing; `all_items` collects *every* item of *every* contract (100k+/run) before the (already-batched) upsert drains it — held simultaneously with the `contract_values` transform list. Peak RSS scales with total contracts + total items per run, not with one batch.
**Impact:** peak memory ∝ whole run; OOM risk as regions/contracts grow. **Confidence:** Strong-static. **On cost map:** yes (Medium). **Effort:** Contained (flush per region/per batch while iterating). Root-caused by SP8.
**Verification plan:** structural (peak bounded to one batch after streaming); guard = same rows upserted.

### SP3. `ON CONFLICT DO UPDATE` rewrites every non-PK column every run → index/heap write amplification
**Lanes:** data-access   **Location:** `services/db_upsert.py:33-39` (+ caller `background_aggregation.py:215-241`)
**Fingerprint:** `data-access:db_upsert.py:bulk_upsert:full-column-on-conflict-update`   **Status:** new
**Problem:** The upsert SET is *all* non-PK columns unconditionally. `contracts` carries 9 secondary indexes, so every re-upsert of an unchanged contract dirties all of them, defeats Postgres HOT updates, and generates dead tuples → vacuum pressure — across thousands–tens of thousands of conflicting rows every 900 s. It also references columns absent from the INSERT VALUES and clobbers `item_processing_status` back to `PENDING` (the latter is a co-located correctness bug, SB-S2-2/3).
**Impact:** sustained write amplification + bloat on the busiest table on a 900 s cadence. **Confidence:** Strong-static. **On cost map:** yes. **Effort:** Contained (narrow SET to the columns actually supplied + those that legitimately change; consider `WHERE` clause / `DO NOTHING` when unchanged).
**Verification plan:** compare heap/index writes + dead-tuple counts before/after on a fixture re-run; guard = a test that an unchanged second run updates 0 rows (or only intended columns).

## Major Findings

### SP4. httpx clients use default pool limits — both a fan-out bottleneck and a rate-limit hazard
**Lanes:** concurrency   **Location:** `core/esi_client_class.py:65-69`, `core/http_client.py:16-20` (no `httpx.Limits` anywhere — grep-confirmed)
**Fingerprint:** `concurrency:esi_client_class.py:http-client:default-pool-limits`   **Status:** new
**Problem:** Default `max_connections=100`. Today (serial) it's a latent bottleneck; the moment SP1/SP2 fan-out is added, an unbounded `gather` would blast ~100 ESI connections and trip rate limiting. The pool limit MUST be set equal to the application semaphore cap.
**Impact:** gates the SP1/SP2/SP3-region fixes; safety-critical for the fan-out. **Confidence:** Strong-static. **Effort:** Localized. **Verification:** set `httpx.Limits(max_connections=C)`; guard = no >C concurrent ESI sockets under load.

### SP5. Per-region public-contract fetches run sequentially despite independence
**Lanes:** concurrency, data-access, cost-map (agreement ×3)   **Location:** `services/background_aggregation.py:129-137` (await `:131`)
**Fingerprint:** `concurrency:background_aggregation.py:run_aggregation:serial-region-fetch`   **Status:** new
**Problem:** Each region is an independent multi-page chain; serializing them makes run-time the sum, not the max. **Impact:** wall-time ∝ region count. **Confidence:** Strong-static. **On cost map:** yes. **Effort:** Contained (bounded-concurrent regions under the same global cap; preserve per-region error isolation).
**Verification:** structural; guard = same contracts collected per region.

### SP6. ID-resolution chunks POSTed sequentially
**Lanes:** concurrency   **Location:** `core/esi_client_class.py:202-214` (await `:205`)
**Fingerprint:** `concurrency:esi_client_class.py:resolve_ids_to_names:serial-id-chunks`   **Status:** new
**Problem:** Each 1000-id chunk POST is independent (merges keyed by disjoint IDs) but awaited serially; on the critical path before item fetch. **Impact:** `ceil(unique/1000)` serial round-trips. **Confidence:** Strong-static. **Effort:** Localized (bounded gather under the cap). **Verification:** guard = same name map.

### SP7. Item upsert batch size 50 (vs 500 for contracts) → ~10–20× more DB statements
**Lanes:** data-access   **Location:** `services/background_aggregation.py:284-288`
**Fingerprint:** `data-access:background_aggregation.py:process_contracts:item-batch-size-50`   **Status:** new
**Problem:** 100k items / 50 = ~2000 INSERT…ON CONFLICT statements/run; the row is 7 columns so the Postgres ~65k-param ceiling is nowhere near binding (7×500=3500). Raising to 500–1000 cuts DB round-trips 10–20×. **Impact:** DB round-trips/run. **Confidence:** Strong-static. **On cost map:** yes. **Effort:** Localized. **Verification:** statement count before/after; guard = same rows.

### SP8. ETag helper materializes all pages into one list instead of yielding (root cause of SP2)
**Lanes:** memory   **Location:** `core/esi_client_class.py:90, 141, 152, 180`
**Fingerprint:** `memory:esi_client_class.py:get_esi_data:full-materialization`   **Status:** new
**Problem:** `get_esi_data_with_etag_caching` accumulates the whole region's paged result into `full_data` and returns it whole; callers re-extend it, doubling the region payload transiently. Converting to an async generator (`yield page_data`) is what unlocks the SP2 streaming fixes. **Impact:** forces the whole-run accumulation. **Confidence:** Strong-static. **Effort:** Cross-cutting (changes the return contract at 3 call sites). **Verification:** structural; guard = same aggregate data.

### SP9. Per-call Redis client built/torn-down per run where the pooled shared client is the fast path
**Lanes:** idiom-currency, concurrency   **Location:** `services/background_aggregation.py:67` (`_concurrency_lock`), `core/esi_client_class.py:71`
**Fingerprint:** `idiom-currency:background_aggregation.py:concurrency_lock:per-call-redis-client`   **Status:** new
**Problem:** `_concurrency_lock` does `aioredis.from_url(...)` + `.close()` every run to run just a lock set/delete; the pooled `get_cache` client is imported but unused (the constructor comment shows it was deliberately removed). **Impact:** per-run pool build/teardown (×2 commands). **Confidence:** Strong-static (Heuristic magnitude). **Effort:** Contained (inject the shared client). **Verification:** structural; guard = lock semantics unchanged.

## Minor Findings
- **SP10.** Redundant per-page materialization: `response.json()` + `response.content` both held live (`esi_client_class.py:149, 166`). `memory`. Heuristic. Localized.
- **SP11.** `contract_values` builds a full second transformed list while `contracts` stays referenced — ~2× contract dicts live (`background_aggregation.py:215-241`). `memory`. Folds into SP2's per-batch transform. Localized.
- **SP12.** Uncoalesced Redis round-trips in the ETag path: 2 GET + up to 2 SET per page, separate awaits (`esi_client_class.py:100, 138, 165-166`). `data-access`. Pipeline/MGET. Minor. Localized.
- **SP13.** Fresh async engine created + disposed per run (`background_aggregation.py:113-123, 169-173`). `data-access`, `concurrency`. Bounded (~1 conn setup/900 s); pin pool params **if** fan-out concurrency is added. Localized.
- **SP14.** Redundant `sorted(list(set(ids)))` in `resolve_ids_to_names` (`esi_client_class.py:199`) — caller already de-dups; the O(M log M) sort is dead work (chunking is order-independent). `algorithmic`. Localized.
- **SP15.** Chained `set.union(...)` allocates throwaway intermediates + four separate full passes over `contracts` to build the four ID sets (`background_aggregation.py:188-195`). `algorithmic`. Collapse to `a|b|c|d` in one loop. Localized.
- **SP16.** `redis.asyncio.Redis.close()` instead of the current `aclose()` (`esi_client_class.py:81`, `background_aggregation.py:87`). `idiom-currency`. **LOW** confidence (redis-py not in the version index — manual currency check). Forward-compat, no throughput cost. Localized.
- **SP17.** Hand-rolled retry/backoff loop vs httpx `AsyncHTTPTransport(retries=…)` for connection retries (`esi_client_class.py:106-126`). `idiom-currency`. **LOW** (httpx not in index); partly a style boundary (the 5xx-status-retry half can't delegate to transport retries). Localized.

## Cross-Cutting Themes
1. **The job is network-round-trip-bound and fully serialized.** SP1 + SP5 + SP6 are one theme — independent `await`s issued one at a time — fixed by a **single global `asyncio.Semaphore` + matching `httpx.Limits` (SP4)**, with DB upserts kept serial on the one session. This is the single highest-leverage change in the whole repo for throughput.
2. **Whole-batch (accumulate-then-flush) shape drives both peak memory (SP2) and DB statement count (SP7).** Streaming per-region/per-batch — unlocked by the SP8 generator refactor — addresses memory and lets upserts drain incrementally.
3. **Write amplification (SP3) compounds every 900 s** — narrowing the ON CONFLICT SET is independent of the throughput work and pure win.
4. **Connection-lifecycle nits (SP9, SP13)** — per-run client/engine churn; minor today, but pinning them matters once concurrency is introduced.

## Measurability
The job logs counts (contracts fetched, IDs resolved, batches) but exposes **no run-duration, per-phase
timing, ESI-call-count, or items-fetched-per-second metric**, and the scheduler has no run-history
metric. The dominant SP1 cost is therefore *inferred*, not observed. Adding (a) a per-run wall-time +
ESI-round-trip counter and (b) a "run overran the interval" alert is a prerequisite to *measuring* the
fan-out win — and would itself surface SP1 in production. Dynamic confirmation deferred (no ESI/PG/dataset).

## Execution Cost Map (highlights)
> Full map: `2026-06-05T01-58-s2-backend-ingest-cost-map.md`.
- **High:** the per-contract item-fetch loop (SP1) — the run's wall-clock budget; the cross-region serial page fetch (SP5).
- **Medium:** per-page ETag/JSON/Redis handling; whole-run accumulation (SP2); item upserts at batch-50 (SP7).
- **Map-only / inherent:** ID-resolution batching (the *good* shape — named to show it isn't the problem); per-run engine/client setup.
- **Architecture note:** ETag/304 caching cuts ESI *bytes* and parse cost but does **not** reduce the *number* of serial round-trips — only bounded concurrency does.

## Suspected Bugs (for follow-up — NOT addressed here)
> Recorded, not chased. Kickoff: `docs/perf-audits/2026-06-05-s2-backend-ingest-bug-hunt-kickoff.md`.
- **SB-S2-1.** `get_contract_items` (`esi_client_class.py:187-190`) calls the ETag helper **without `all_pages=True`** → silently drops item pages beyond page 1 for multi-page contracts (data loss). *(High-value: a contract with >1 page of items is under-ingested.)*
- **SB-S2-2 / SB-S2-3.** The ON CONFLICT SET clobbers `item_processing_status` back to `PENDING_ITEMS` every run (an indexed progress column) and references columns absent from the INSERT VALUES (`items_last_fetched_at`, `contract_esi_etag`, `start_location_system_id/region_id`) — risk of overwriting independently-maintained columns to NULL/default each upsert (`db_upsert.py:33-39` + `background_aggregation.py:215-241`). *(Co-located with perf finding SP3 — fix alongside, but recorded as a correctness bug.)*
- **SB-S2-4.** `ContractItem.record_id` is an **autoincrement PK**, but ingestion supplies ESI's `record_id` (unique only *within* a contract) and `bulk_upsert` keys ON CONFLICT on the PK → rows from different contracts sharing a `record_id` can collide/clobber. *(High-value correctness.)*
- **SB-S2-5.** Broad `except Exception` on per-region/per-contract fetches (`background_aggregation.py:136-137, 279-280`) swallows failures and reports "no data" → silent incomplete upserts.
- **SB-S2-6.** `response` possibly-unbound on a first-iteration network failure (`esi_client_class.py:103, 128`).
- **SB-S2-7.** Dead `get_cache` import (`background_aggregation.py:12`).

## False positives / correctly-rejected
- **Parallelizing ESI pagination within a single call** — the `concurrency` lane *considered and declined* it: page count is only known after page 1's `X-Pages`, requiring a two-phase fetch not worth it ahead of the across-contract fan-out. Good calibration.
- **Fresh-engine-per-run as a major cost** — correctly down-ranked to MINOR (bounded ~1 setup/900 s), not inflated.
- **The `algorithmic` lane found no CRITICAL/MAJOR** and said so plainly (the ID-union/resolve path uses correct containers) — anti-padding held; it reported only three honest MINOR constant-factor items.
- **Manual 500/50 batch sizes vs `insertmanyvalues`** — `idiom-currency` declined to flag the upsert idiom itself as stale (it is the correct 2.0 path); only the *size* (SP7) is a finding.
