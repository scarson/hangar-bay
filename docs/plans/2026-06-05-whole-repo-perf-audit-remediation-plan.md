# Performance Audit Remediation Plan — Whole Repo (2026-06-05)

**Source findings:** `docs/perf-audits/2026-06-05-s1-backend-read-validated.md`,
`…-s2-backend-ingest-validated.md`, `…-s3-frontend-validated.md`, and the
`…-WHOLE-REPO-ROLLUP.md`.
**Status:** **DRAFT — awaiting operator sign-off on the flagged design decisions before execution.**

> **Why this is a draft, not an executed plan.** The `performance-audit-cycle` Phase 5 requires
> presenting findings to the user and collecting design-decision answers + opt-outs *before* the fix
> plan is finalized, and Phase 7 requires running `plan-review-cycle` on it. The operator is offline
> (in transit) and could not be prompted, and **executing remediation was not requested** — this run's
> deliverable is the audit. So this plan: (a) schedules **all** confirmed findings per the
> no-severity-deferral discipline; (b) surfaces the design decisions inline as **[DECISION]** blocks
> for the operator to resolve on landing; (c) is **not** yet subagent-proofed via
> `writing-plans-enhanced` nor reviewed via `plan-review-cycle` — both should run once the decisions
> are answered. Nothing in the codebase was changed.

## Disposition discipline (per `finding-model.md`)
Every confirmed finding's default disposition is **FIX**. None is deferred on severity/effort grounds.
The only items not scheduled for immediate work are: (a) those gated on an operator **[DECISION]**, and
(b) the frontend data-layer items, which are legitimately gated on **reachability** (the feature is
latent) — scheduled as part of "wire the contracts feature," not deferred to no one. See the Deferred
appendix for the precise, named reasons.

## Verification gate (applies to EVERY task)
Each task MUST capture: a **baseline** before the change (a measurement where the env allows, else an
explicit complexity/round-trip/allocation argument); a **post-change demonstration** of improvement
(same); and a **correctness guard** (existing tests pass + a test pinning the behavior the optimization
must preserve). **If a change doesn't demonstrably improve, revert it.** No fabricated numbers — this
repo had no running PG/Valkey/ESI/dataset at audit time, so several baselines are complexity arguments
until a perf environment exists (see Task 0).

---

## Task 0 — Stand up the measurability the rest of the plan depends on
**What/where/why:** add the metrics the audit found missing so the later tasks have real before/after
numbers instead of arguments — per-query DB-time + cache hit/miss counters on the read path, and
run-duration + ESI-round-trip + items-fetched counters on the ingestion job. *(Roll-up Theme D;
S1 Measurability; S2 Measurability.)*
**Verification:** the new metrics appear on `/metrics`; a local run shows non-zero values. Guard: metrics
don't alter response/job behavior.
**Do not touch:** the existing Prometheus instrumentator config beyond adding counters.

## Task 1 — Bound the ESI fan-out: concurrency-cap the per-contract item fetch (and region/id-chunk fetches) [perf S2 SP1, SP4, SP5, SP6]
**What/where/why:** in `services/background_aggregation.py` the per-item-bearing-contract
`get_contract_items` loop, the per-region `get_public_contracts` loop, and the per-chunk
`resolve_ids_to_names` loop issue independent ESI requests **serially**; at realistic volumes the item
loop alone can exceed the 900 s interval. Run the **network fetches** under a single
`asyncio.Semaphore(C)` + `gather`, set `httpx.Limits(max_connections=C, max_keepalive=...)` on both
ESI clients (`core/esi_client_class.py`, `core/http_client.py`) to the **same** cap, and **keep
`bulk_upsert` serial on the one `AsyncSession`** (it is not concurrency-safe).
**[DECISION] ESI concurrency cap `C`:** set by ESI's error-rate budget, not us. *Recommend:* a
settings-driven `C` starting ~10–20, tuned against ESI `X-ESI-Error-Limit-*` headers. Operator to
confirm the value / settings key. **Never an unbounded `gather`.**
**Verification:** baseline = serial round-trip count argument (≈ M sequential); after = wall-time ≈
`ceil(M/C)`×latency, confirmed by the Task-0 run-duration metric on a recorded ESI fixture. Guard: a
test asserting the resulting `all_items`/contracts multiset equals the serial path's on a fixture; a
test that no more than `C` concurrent ESI sockets open.
**Do not touch:** the DB upsert serialization; the ETag/lock semantics.

## Task 2 — Add cache-aside to the contract read path [perf S1 P1]
**What/where/why:** `services/contract_service.get_contracts` hits Postgres on every request; wrap it in
cache-aside keyed on the normalized filter set, storing the serialized page in Valkey. Invalidate by
bumping a cache-version key at the end of each successful aggregation run (`run_aggregation`).
**[DECISION] staleness window:** *Recommend* TTL ≤ the 900 s aggregation interval **and/or**
version-key invalidation on aggregation completion. Operator to confirm acceptable staleness.
**Verification:** baseline = Task-0 shows 0% cache hits; after = high hit-ratio on the default query +
lower P95. Guard: a test that cached and uncached responses are byte-identical for a fixed filter set,
and that an aggregation run invalidates the entry.
**Do not touch:** the query logic itself (Task 3 owns that) — cache around it first.

## Task 3 — Rewrite the one-to-many read query and add the missing indexes [perf S1 P2, P3, P4, P5, P6; fixes SB1]
**What/where/why:** replace the item-attribute `OUTER JOIN` + Python `.unique()` with an `EXISTS`
semi-join so contract rows don't multiply; count via `COUNT(DISTINCT contracts.contract_id)` (or over
`contracts` alone); keep `selectinload(items)` purely for display. Add a migration with: `pg_trgm` GIN
indexes on `contracts.title` + `contract_items.type_name` (P2); btree indexes on
`start_location_region_id`/`system_id`/`start_location_id` (P3); a composite e.g.
`(start_location_region_id, date_issued DESC)` chosen against the real query mix (P6). This also fixes
the LIMIT-before-dedup short-page bug (SB1) because rows no longer fan out.
**[DECISION] composite index columns:** depends on the dominant real filter+sort combination. *Recommend*
region+date_issued; operator to confirm against expected usage.
**Verification:** `EXPLAIN ANALYZE` before/after (seq scan → index scan; sort node removed; DISTINCT
gone) on a production-like dataset. Guard: result-set + count equality on multi-item fixtures; a
pagination test that a full page returns `size` distinct contracts.
**Do not touch:** SQLite-dev behavior — `pg_trgm` is Postgres-only; guard the dialect split.

## Task 4 — Narrow the upsert `ON CONFLICT` SET and raise the item batch size [perf S2 SP3, SP7]
**What/where/why:** in `services/db_upsert.py` the `ON CONFLICT DO UPDATE` rewrites **all** non-PK
columns every run, churning all 9 `contracts` indexes (defeats HOT updates, bloats) and clobbering
`item_processing_status`; narrow the SET to genuinely-mutable, supplied columns. In
`background_aggregation.py` raise the item upsert batch from 50 → 500 (param ceiling is not binding).
**[DECISION] which columns are "ingestion-owned" vs derived** (so the SET doesn't reset
`item_processing_status`/`items_last_fetched_at`): operator to confirm the ingestion state machine.
**Verification:** baseline = ~2000 item statements/run + all-index dirtying argument; after = ~200
statements + only-changed-columns updated (a second unchanged run updates 0 rows). Guard: upsert
idempotency test.
**Do not touch:** the PK conflict target (the `record_id` PK question is correctness — SB-S2-4, bug-hunt).

## Task 5 — Stream the ingestion to bound peak memory [perf S2 SP2, SP8, SP10, SP11]
**What/where/why:** convert `esi_client_class.get_esi_data_with_etag_caching` to an async generator
yielding pages (SP8), and process/upsert per region/per batch instead of accumulating
`all_contracts_data` + `all_items` run-wide (SP2); transform per-batch (SP11); avoid holding
`response.json()` + `response.content` simultaneously (SP10).
**Verification:** baseline = peak ∝ total contracts+items argument; after = peak bounded to one batch.
Guard: same rows upserted as the accumulate-then-flush version on a fixture. **Sequence after Task 1**
(both touch the same orchestration) to minimize conflict.
**Do not touch:** the ETag/304 caching semantics.

## Task 6 — Trim per-request read overhead [perf S1 P7, P8, P9, P10]
**What/where/why:** explicit connection-pool sizing on `db.py:async_engine` (P7); route structlog
through `QueueHandler`/`QueueListener` so the event loop only enqueues (P8); build the response with a
single Pydantic pass — `response_model=None` + return, or pass ORM objects through (P9); stop
committing on read-only requests in `get_db` (P10).
**[DECISION] pool size (P7):** needs `Postgres max_connections` ÷ (workers + the aggregation engine).
Operator to provide deploy budget; interim ~10–20/worker if Postgres allows.
**Verification:** P8/P9 via micro-bench + the Task-0 metric under concurrency; P7 via a concurrent-read
load test moving the ceiling. Guard: log-output equality (P8); response JSON byte-equality (P9); write
paths still persist (P10).
**Do not touch:** the structured-log *schema* (only the handler/transport).

## Task 7 — Consolidate the frontend data layer and align it to the backend contract [perf S3 FP1, FP2, FP3; resolves SB-S3-1/2; gated on wiring]
**What/where/why:** collapse `ContractSearch` + `ContractApi` (and `contract.models.ts` +
`contract.model.ts`) into one service + one model whose request params (`sort_direction`, `type_ids`)
and response shape (`total`/`items`) **match the backend** (S1). Split the debounce so only text-search
debounces (FP2); replace the `JSON.stringify` `distinctUntilChanged` with a field comparator (FP3).
**[DECISION] adopt the Angular 20 resource idiom (`httpResource`/`rxResource`) (FP5)?** Verify stability
in the project's exact Angular 20.x (our version index only covers through Angular 19) before adopting.
**Reachability gate:** this is scheduled **as part of wiring the contracts feature** (currently
`routes=[]`), not before — it has no runtime effect until then.
**Verification:** one request per interaction; renders real backend data (not `undefined`); sort works.
Guard: a component test against a mocked backend response in the real shape.

## Task 8 — Frontend build guard-rails (do now — cheap, no reachability gate) [perf S3 FP7, FP8, FP9]
**What/where/why:** remove the eager `@angular/localize/init` polyfill until i18n begins (FP7); add a
`loadComponent`/`loadChildren` lazy-loading convention before the first feature is wired (FP8); tighten
`angular.json` budgets — warning headroom on `initial`, add a per-lazy-chunk (~200 kB) budget (FP9).
**Verification:** `ng build --configuration production` — initial bundle drops (FP7) and budgets enforce
the stated targets. Guard: app still bootstraps; no `$localize` usage exists (grep).
**Do not touch:** the otherwise-sound default Angular 20 build config.

## Task 9 — Constant-factor + currency cleanups (batch) [perf S1 P12; S2 SP14, SP15, SP16, SP17]
**What/where/why:** one small task — drop the dead `sorted(list(set(ids)))` (SP14); collapse the chained
`set.union` + 4 passes into one (SP15); `aclose()` not `close()` on `redis.asyncio` (SP16); evaluate
httpx transport retries vs the hand-rolled loop (SP17); `from sqlalchemy import select` not the
`.future` shim (S1 P12). Grouped (not dropped) per the disposition discipline.
**Verification:** complexity argument (each removes provable dead/duplicate work); guard: existing
behavior unchanged. **Confirm SP16/SP17 against current redis-py/httpx docs first** (LOW-confidence,
ungrounded by the version index — no live currency brief this run).

---

## Counter over-optimization
Each task names the minimum change and what NOT to touch. Performance work tempts wholesale rewrites —
e.g. Task 3 is a targeted query + index change, **not** an ORM-to-raw-SQL migration; Task 1 is a bounded
semaphore, **not** a queue/worker rearchitecture.

## Advisory
After remediation, run the auto-generated **bug-hunt kickoffs** (per slice) over the diff — performance
changes are a classic bug source, and several perf tasks touch code co-located with recorded suspected
bugs (Task 3 ↔ SB1; Task 4 ↔ SB-S2-2/3; Task 7 ↔ SB-S3-1/2).

## Appendix: Findings identified but not fixed in this cycle
*(Per the discipline, only items with a named, substantive reason or a reachability gate appear here —
nothing is severity-deferred.)*

### Frontend data-layer items (FP1, FP2, FP3, FP5, FP10)  (S3)
**Impact:** MAJOR/MINOR once wired   **Location:** `app/frontend/angular/src/app/features/contracts/**`
**Why gated (not deferred):** the contracts feature is **latent** (`routes=[]`) — these have zero
runtime effect until the feature is wired, so they are scheduled **inside Task 7** ("wire the feature"),
not as standalone pre-work. Reachability is the named mechanism, not severity.
**Recommended approach:** Task 7 + Task 8.

### Suspected bugs (all 23)  (S1/S2/S3)
**Why not here:** out of scope by definition — a performance audit records correctness bugs and hands
them to `bug-hunt-cycle`; it does not fix them. **Recommended approach:** run the three bug-hunt
kickoffs under `docs/perf-audits/2026-06-05-*-bug-hunt-kickoff.md`, prioritizing the silent-data-loss
ones (startup `drop_all`; dropped item pages; `record_id` PK collision; frontend contract mismatch).
