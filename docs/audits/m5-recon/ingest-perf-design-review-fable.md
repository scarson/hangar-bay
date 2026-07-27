# ABOUTME: Adversarial design review (Fable) of the M5 ingest-performance proposal
# ABOUTME: (error-limit awareness + concurrent _fetch_item_rows). Findings ranked BLOCKER/MAJOR/MINOR.

# M5 ingest-perf design review — adversarial (Fable)

Reviewed against: `app/backend/src/fastapi_app/services/background_aggregation.py`,
`core/esi_client_class.py`, `core/scheduler.py`, `core/config.py`, `api/ops.py`,
`docs/pitfalls/implementation-pitfalls.md` (DEPLOY-2/3, ESI-1), `render.yaml`, open PR #91,
and current ESI docs (error limiting + the Oct–Dec 2025 token-bucket rate-limit rollout).

**Verdict in one line:** the diagnosis (sequential loop = bottleneck) is arithmetically
verified and correct, and "error-limit awareness first" is the right ordering — but the
design optimizes the wrong variable. Contract items are immutable per `contract_id`, and
the run refetches ~45k already-known contracts every cycle. Skip-known-contracts is the
dominant fix (~20–40× fewer requests at concurrency 1); concurrency is the *secondary*
fix for cold start. And claim 4 ("nothing survives a short run") is false for the cache
and only conditionally true for the lock.

---

## Verification of the observed facts (attack question 1)

**Does `get_contract_items` hit the network every call?** Yes — verified in
`get_esi_data_with_etag_caching`: it reads the ETag from Valkey, then *unconditionally*
calls `_get_with_transient_retry` (a conditional GET). There is no cache-only path. A 304
saves bandwidth and JSON parse, never the round trip. So cache eviction does NOT dominate
the runtime; per-request latency does. The sequential-loop diagnosis stands.

**Arithmetic.** ~51,365 Forge contracts, item_exchange/auction subset ≈ 45–47k. Measured
77 min ≈ 4,620 s ⇒ ~95–100 ms per sequential round trip. That is exactly one
Ohio→ESI HTTP RTT including TLS-keepalive'd request/response — fully consistent. At
concurrency 20: 46k / 20 workers × ~95 ms ≈ 3.6 min. The ~4-min expectation is sound
*arithmetic*, contingent on ESI tolerating the request rate (~190 req/s — see BLOCKER-2).

**Unverified decomposition.** 77 min also contains: list pagination (~52 pages, trivial),
`resolve_ids_to_names` (tens of POSTs, trivial), enrichment fan-out (10–15k unique types at
concurrency 8 ≈ 2–4 min when the object cache has been LRU-evicted — which it will have
been, see MAJOR-3), and ~3,000 sequential item-upsert statements (BATCH_SIZE=50 for ~150k
rows ≈ 15–60 s of DB round trips). No per-phase timing exists anywhere, so the "item loop
is ~73 of the 77 minutes" claim is inference, not measurement (MAJOR-6).

---

## BLOCKER findings

### BLOCKER-1: The design misses the dominant optimization — contract items are immutable, and ~45k of the ~46k fetches per run are refetches of data we already hold

EVE contracts cannot be edited after issuance (editing means delete + recreate = new
`contract_id`); auction *bids* change but bids are a different endpoint and are not
fetched. Therefore `/v1/contracts/public/items/{contract_id}/` has exactly one useful
fetch per contract, ever. The code (`_fetch_item_rows`) iterates every listed contract
every run with no check against the DB — and the DB already carries the needed state:
`item_processing_status` (`COMPLETED` / `ENRICHMENT_INCOMPLETE` / NULL).

**The fix shape:** before the loop, one SELECT of contract_ids with
`item_processing_status = 'COMPLETED'`; fetch items only for contracts not in that set
(new, NULL, or `ENRICHMENT_INCOMPLETE`). Steady-state Forge churn (new contracts/hour) is
on the order of 1–2k, not 46k — a ~20–40× reduction that:

- works at **concurrency 1** (a ~2–4 min run with zero new failure modes);
- is immune to the error limit (2 orders of magnitude fewer chances to err);
- is the only shape that survives ESI's **ongoing token-bucket rate-limit rollout**
  (see BLOCKER-2): if the contracts group ever gets a budget like the docs' example
  ("150/15m" at 2 tokens per 2xx ≈ 75 requests/15 min), per-contract refetch-everything
  dies at *any* concurrency;
- eliminates ~1.1M requests/day of ESI load that the concurrent-refetch design would
  otherwise institutionalize (hourly 46k-fetch runs) — an ESI-citizenship problem the
  design never weighs.

**Concrete failure the current design causes:** you ship 20× concurrency, runs drop to
~4 min, the scheduler now completes every hour, and you have *increased* total ESI request
volume ~2× (77-min runs previously fit only ~12 runs/day; 4-min runs fit 24) while leaving
the 45k-refetch waste untouched. First time ESI extends rate limiting to the contracts
group, ingestion breaks outright.

Concurrency is still wanted — for **cold start** (fresh DB / new region: 46k genuinely
new contracts) and backfill of `ENRICHMENT_INCOMPLETE`. The correct plan is
skip-known **first**, bounded concurrency **second**, sized for the cold-start case.

### BLOCKER-2: "Read the error-limit headers" is not a design; and the plan is silent on ESI's *second* limiter (429/Retry-After token buckets), which the client currently treats as success

Verified against ESI docs:

- **Error limiting** (live since 2018): any 4xx/5xx counts; documented default budget is
  100 errors per rolling 60 s window; breach ⇒ **420** on *every* endpoint for the rest of
  the window, and requests made while limited also fail. Headers:
  `X-Esi-Error-Limit-Remain` / `X-Esi-Error-Limit-Reset`.
- **Rate limiting** (rolled out Oct 7 – Dec 4, 2025, group by group; "not active on all
  routes yet — check response headers"): token buckets per rate-limit-group + user, where
  *public* requests are keyed by **source IP** — i.e., the single Render egress IP.
  Costs: 2xx = 2 tokens, 3xx = 1, **4xx = 5**, 5xx = 0. Breach ⇒ **429 + Retry-After**.
  Headers: `X-Ratelimit-Limit/-Remaining/-Used/-Group`.

The current client is blind to both, and worse than blind:
`_get_with_transient_retry` treats **any status < 500 as success** (esi_client_class.py,
`if response.status_code < 500: break`). A 420 or 429 therefore skips retry/backoff
entirely, flows to `raise_for_status()`, and becomes a per-contract "failure" that
`_fetch_item_rows` logs with a stack trace and moves past. Under 20× concurrency, tripping
the limit converts the remaining ~40k contracts into a ~3-minute firehose of guaranteed-420
requests — each one both extending your penalty and (under the new system) burning 5 tokens
apiece — plus ~40k `exc_info=True` ERROR lines shipped to Grafana Cloud (billed log volume).
The run then "completes" and records a **success/partial** outcome, because item-fetch
failures never touch the `regions_ok/failed` counters.

What the design must actually specify (currently missing entirely):

1. A **shared limiter object** across all workers (a semaphore does not coordinate a
   global pause): track worst-case `Remain`/`Reset` monotonically across racing responses;
   when `Remain` drops below a floor (e.g. 10), *all* workers sleep until `Reset`.
2. **420 and 429 are global pause-and-retry signals, never per-contract failures**; honor
   `Retry-After`. This requires changing the `< 500` success predicate — a behavior change
   to a shared client that every other ESI caller (enrichment, name resolution) rides.
3. **Budget arithmetic as an acceptance criterion:** at ~190 req/s, the 100-per-60 s error
   window tolerates a sustained error fraction of ~0.87%. The observed per-contract 403s
   are currently unquantified (see MAJOR-5); if they exceed ~1% of item fetches, naive
   20× concurrency error-limits itself *by design*. Sequentially (~10 req/s) the same 403
   rate was harmlessly under budget — which is precisely why this hasn't bitten yet.
4. A retry cap + terminal state so the same permanently-403 contract doesn't re-burn error
   budget every run forever (interacts with BLOCKER-1's skip set).

The design's *ordering* (error-limit work before concurrency) is correct; its *content* is
a header name, and that is not enough to build from.

---

## MAJOR findings

### MAJOR-3: Claim 4 is false for the cache: cache-sizing fully survives a short run — and the shared 25 MB `allkeys-lru` Valkey is collateral damage of every run, fast or slow

Cache pressure is a function of *volume written*, not run duration. Every run writes
~46k ETag keys + ~46k body keys (`_store_page_cache`) into the free-tier Key Value
instance (~25 MB, `allkeys-lru` per render.yaml) that also holds: **user sessions**
(render.yaml already concedes "sessions evictable under pressure"), the **enrichment
object cache** (whose eviction is why enrichment goes cold every run), the
**`INGEST_LAST_RUN_KEY` freshness record** (written with *no TTL* and read rarely — a
prime LRU victim, silently breaking the §8.2 freshness signal), and the **aggregation
lock itself** (SET once, never touched again → LRU-cold; DEPLOY-3 tolerates lock eviction,
but it's worth naming that a write-heavy run actively pushes its own lock toward
eviction). Making the run 4 min instead of 77 changes none of this; it only compresses
the churn into a shorter window.

Additional latent correctness wart the design should fix in passing: on a 304 whose
cached body was evicted, `_read_etag_cached_page` returns `[]` — the contract is added to
`processed_contract_ids` with zero items and `_update_item_processing_status` marks it
`COMPLETED`. Today this is mostly masked because DB rows persist and upserts never
delete, but it makes `COMPLETED` a lie in exactly the eviction regime the instance runs in.

**The clean resolution follows from BLOCKER-1:** once items are fetched once-per-contract,
**stop ETag-caching item pages at all** — caching an immutable, read-once payload in a
25 MB LRU is pure churn. That, not run speed, is what actually retires the cache-sizing
question (and stops evicting sessions every ingest).

### MAJOR-4: The lock-TTL problem is not "collapsed" — it is violated in production today, and speed is a mitigation, not a fix

TTL = 3600 + 300 = 65 min < 77-min runs: the mutual-exclusion window expires mid-run
*every run right now*; the Lua compare-and-delete then correctly declines to release
(the "token mismatch" warning in DEPLOY-3's incident log is this firing). Practical risk
is currently low — APScheduler `max_instances=1` prevents in-process overlap, and the
disk-pinned single instance (render.yaml `scheduler-pin`) forces recreate deploys, so a
second *process* holding the window is rare — but the design's own centerpiece can
reopen it: an error-limit/429 pause (BLOCKER-2) makes a "4-minute" run arbitrarily long
again (a 60 s error window is short, but repeated trips or a long `Retry-After` are not
bounded by anything on our side).

Fix honestly rather than by speed: either **renew the lock mid-run** (heartbeat EXPIRE
every few minutes from the run loop) or, at minimum, log/alert when run duration exceeds
`interval/2` so TTL-vs-runtime drift is seen before it matters. DEPLOY-3's "TTL derives
from interval + margin" rule is necessary but not sufficient when runtime is
upstream-controlled.

### MAJOR-5: The unexplained 403s must be quantified and root-caused *before* concurrency ships — they are the error-budget denominator

Most plausible mechanism: the contract was accepted/deleted between the list fetch and its
item fetch — a race whose window is the run duration itself. A 77-min run gives up to 77
minutes for listed contracts to die mid-run; both proposed fixes shrink the window
(fast run) or the exposed set (skip-known fetches only fresh contracts, which are the
least likely to have died). But this is a hypothesis; the design treats the 403s as a
footnote when they are the load-bearing input to BLOCKER-2's budget math, and under the
new rate limiting each 403 costs 5 tokens (2.5× a success). Required: one production run's
count of 403s by contract age, and a decision on terminal-state handling for repeat
offenders. Note `_fetch_item_rows` only iterates currently-listed contracts, so these are
within-run races, not zombie DB rows.

### MAJOR-6: No instrumentation exists to verify either the diagnosis or the win

There is no run-duration metric, no per-phase timing, no fetch/error counters — the
77-min figure came from deploy-log archaeology. Shipping a performance fix with no
before/after measurement violates the project's own verification discipline. Add (cheap):
per-phase `logger.info` timings + a `run_duration_seconds` metric next to
`last_ingest_success_timestamp`, and counters for item fetches attempted/304/4xx. This
also pins the decomposition assumption in the arithmetic above. While in there: item
upsert `BATCH_SIZE = 50` for ~150k rows is ~3,000 sequential statements; ~8 params/row
means ~1,500–2,000 rows/statement fits comfortably under asyncpg's 32,767-param cap —
a free order-of-magnitude on the DB phase.

---

## MINOR findings

### MINOR-7: Concurrency limit has no defensible basis yet — and `ENRICHMENT_CONCURRENCY = 8` is not a precedent, it's an unjustified constant that happened to work

There is no documented ESI concurrency ceiling; the governing constraints are the two
limiters in BLOCKER-2. So the number must be (a) a `Settings` field, not a module
constant, (b) calibrated against observed `X-Esi-Error-Limit-Remain` /
`X-Ratelimit-Remaining` headers from real runs, and (c) ≤ httpx's default
`max_keepalive_connections` (20) unless pool limits are raised explicitly — above 20 you
churn connections instead of reusing them. Start 10–20 for cold start; with BLOCKER-1's
skip in place, steady-state barely needs it.

### MINOR-8: Concurrency refactor mechanics (mostly sound, three constraints to state)

Mirroring the enrichment pattern is the right shape *if* workers return rows and the
gather site aggregates — do not have workers mutate `all_items` / `processed_contract_ids`
mid-flight (current code appends after the await, which would be safe, but returning
values is the pattern already proven in `_enrich_items_and_find_ships`). Two hard
constraints: the `AsyncSession` must stay out of the workers (it is not
concurrency-safe; all DB writes remain after the gather — the current design implies this,
say it explicitly), and per-contract ordering is genuinely irrelevant downstream
(record_id-keyed upserts; ship-flag set union) — confirmed, no ordering dependency.
Also cap the failure-path logging: `logger.error(..., exc_info=True)` per contract is
fine at 10 failures, not at 10,000 (Grafana Cloud ingest is billed).

### MINOR-9: Downstream-cadence effects are mostly fine — verified individually

- `data_stale` (`api/ops.py`): threshold is `2 × interval` = 2 h; hourly 4-min runs keep
  age well under it. Sound.
- PR #91 watermark: stamped at contract-list upsert, not item fetch, so item-fetch
  concurrency/failures don't touch it; per-region failure isolation already covers a
  420-poisoned region (the whole region raises out of `get_public_contracts` pagination
  → no stamp → contracts persist). One real interaction to test: a 420/429 *global* pause
  striking mid-`_fetch_regions` fails *subsequent* regions while earlier ones stamped —
  exactly the per-region case #91's mutation tests cover. Sound, but add it to the test
  matrix when both land. Sequencing note in #91 ("later release") is unaffected.
- Faster runs mean the whole-run DB transaction shrinks from 77 min (an autovacuum and
  lock-horizon problem on a 256 MB Postgres) to ~4 min — an unclaimed *benefit* the
  design could name.
- ETag TTLs: derived from ESI `Expires` (`_cache_ttl_seconds`, default 600 s) — hourly
  runs will mostly find them expired *or evicted*; irrelevant once BLOCKER-1 +
  MAJOR-3's stop-caching-items land.

### MINOR-10: The volume-filter rejection is correct, but for one reason, not two — and ordering has a value the design undersells

Rejecting *exclusion* is right on the first ground alone: the `is_ship_contract=false`
view is a shipped feature; a filter that stops populating non-ship items breaks it.
That argument is sufficient and verifiable. The "market appraisal needs the long tail"
argument is speculative product direction doing rhetorical work it doesn't need to do —
drop it from the rationale before someone later "refutes" the speculation and takes the
sound conclusion down with it. Steelman worth keeping: volume-**ordering** (likely-ship
first) is cheap failure-resilience — if a run dies or gets rate-limit-paused midway, the
~573 ship contracts (the flagship view) are already fresh. With skip-known in place this
matters mainly on cold start, which is exactly when runs are longest and most likely to
be interrupted. Order the cold-start fetch queue by volume descending; never exclude.

---

## What the recommended plan looks like (delta from the proposed design)

1. **Instrument first** (MAJOR-6): per-phase timings + fetch/error counters. One
   production run of data also answers MAJOR-5's 403 question.
2. **Limiter correctness** (BLOCKER-2): shared error-limit + rate-limit awareness in
   `ESIClient`; 420/429 = global pause + retry honoring `Retry-After`; fix the `< 500`
   success predicate; budget floor; retry caps.
3. **Skip known contracts** (BLOCKER-1): fetch items only where `item_processing_status`
   is not `COMPLETED`; stop ETag-caching item pages (MAJOR-3); fix the 304-evicted-body
   `COMPLETED` lie.
4. **Bounded concurrency for cold start** (design point 3, demoted): configurable,
   default 10–20, workers-return-rows shape, volume-descending order.
5. **Lock heartbeat or duration alarm** (MAJOR-4) — do not let speed stand in for the
   mutual-exclusion invariant.

Steps 1–3 deliver ~95% of the win with strictly less risk than the proposed
concurrency-first plan; step 4 covers the only case (cold start) where concurrency earns
its complexity.

## Sources

- [ESI Error Rate Limiting Goes Live On Monday — EVE: Developers](https://developers.eveonline.com/blog/esi-error-rate-limiting-goes-live-on-monday)
- [Best Practices for ESI — EVE Developer Documentation](https://developers.eveonline.com/docs/services/esi/best-practices/)
- [Rate Limiting — EVE Developer Documentation](https://developers.eveonline.com/docs/services/esi/rate-limiting/)
- [Hold your horses: introducing rate limiting to ESI — EVE: Developers](https://developers.eveonline.com/blog/hold-your-horses-introducing-rate-limiting-to-esi)
