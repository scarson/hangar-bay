# ABOUTME: Adversarial review (Fable) of the M5 ingestion clean-sheet design
# ABOUTME: (docs/audits/m5-recon/ingestion-clean-sheet-design.md). Findings ranked BLOCKER/MAJOR/MINOR.

# Clean-sheet ingestion design review — adversarial (Fable)

Reviewed against: the clean-sheet design doc, `services/background_aggregation.py`,
`core/esi_client_class.py`, `core/config.py`, `api/ops.py`, `core/scheduler.py`,
`render.yaml`, PR #91, and the live ESI swagger for both contract endpoints
(fetched this session — two load-bearing facts below come from it).

**Verdict in one line:** the discovery/enrichment split is the right architecture and
most of the dissolution table holds — but "fetch once, ever" has a hole the current code
makes real (the items endpoint paginates and we only ever fetch page 1), fetch-once-forever
deletes the accidental self-healing that has already rescued this codebase twice, and the
"discovery runs far more often" freshness claim is capped at one hour by ESI itself.

---

## Q1 — Is the immutability premise airtight?

**The content premise is airtight; the observation premise is not.**

Content: EVE contracts cannot be edited after issuance (edit = delete + recreate = new
`contract_id`); auction bids live on `/contracts/public/bids/`, not items; contracts do
not move regions (locations fixed at issuance); "edited before first observation" is
impossible because there is no edit. No counterexample exists for *the items changing
under a stable contract_id*. Sound.

What is NOT airtight is the implicit second premise: **"our first fetch = the complete
truth."** Two concrete failure modes:

### BLOCKER-1: The items endpoint paginates, and the current fetch reads only page 1 — fetch-once makes the truncation permanent

Verified against the ESI spec: `/v1/contracts/public/items/{contract_id}/` takes a
`page` parameter, returns `X-Pages`, and serves **max 1,000 items per page**.
`get_contract_items` calls `get_esi_data_with_etag_caching(path)` with `all_pages`
defaulted to **False** — it never reads `X-Pages`. Any contract with >1,000 item rows
(large clearance/freighter-load contracts are a real listing type) is silently truncated
to its first 1,000 items *today*. Under the current refetch-everything loop this is a
persistent but at least re-fixable bug; under fetch-once-ever it becomes **permanently
wrong data that no future run will correct**, and the appraisal product direction would
misprice exactly the highest-value contracts. The enrichment fetch must walk all pages,
and "success" must mean *all pages fetched* — a mid-pagination failure must not record
partial items as `COMPLETED`. The migration repair (Q7) must also re-queue existing
suspects: any `COMPLETED` contract whose item count is an exact multiple of 1,000.

### BLOCKER-2: Fetch-once-forever deletes self-healing, and this codebase's own history proves it will be needed (this is my main Q6 answer)

The refetch-everything loop is wasteful, but it is also an accidental repair mechanism:
every enrichment bug ever shipped was retroactively healed one cycle after its fix.
This has already happened **twice** — `is_ship_contract` was never set ("will be updated
later" never happened) and `is_blueprint_copy` was never mapped (column stayed NULL, the
is_bpc filter dead on real data); both are documented in the code's own comments, and
both fixes worked *only because the next run refetched everything*. Under fetch-once,
each would have required ad-hoc production data surgery. Enrichment bugs are empirically
a recurring class here, so the design needs a **designed re-enrichment lever**, not an
accident: an `enrichment_version` (or equivalent) stamped on success, so bumping a
constant re-queues the corpus through the normal budgeted machinery — cost: one column
and one WHERE clause. Without it, the third enrichment bug (BLOCKER-1 is arguably it)
turns into a manual migration every time.

---

## Q2 — Is the split clean? Can delisting come from discovery alone?

**Delisting: yes — the watermark alone is sufficient and should be the *only* writer of
delist state** (see Q4 for why the 403 coupling should be inverted). A contract that
vanishes between list fetch and item fetch is simply absent from the next complete sweep;
per-region all-or-nothing stamping (a failed page aborts the region's stamp) already
protects against partial sweeps. Sound.

**But the split leaks in the other direction — visibility:**

### MAJOR-3: Discovery-then-enrichment breaks the atomic visibility the current design gets right, and the design doesn't decide what pending contracts look like

Today the entire run commits in **one transaction**: a contract becomes visible with its
items and its ship flag simultaneously. The clean sheet commits discovery first, so
"listed, zero items, `is_ship_contract=false`, status pending" becomes a *persistent,
user-visible* state: new ship contracts sit in the non-ship view (flag not yet computed)
showing no items — indistinguishable from the 3.1% zero-item bug you just measured.
On cold start / new-region backfill this state lasts hours for most of the corpus.
The design must pick one: exclude `item_processing_status`-pending contracts from list
views (cleanest — the ships-default view already effectively does this since unflagged
contracts don't match), surface the pending state in the API/UI, or accept and document
the eventual consistency. Silence here ships a regression that will be reported as
"contracts have no items again."

Also under-specified across the split: the freshness record and `/ready` currently
describe *one* job; two jobs need two outcomes (discovery freshness + enrichment health),
or `data_stale` will claim health while enrichment is completely broken. The design's
queue-depth metric is the right signal but only if `/ready`/ops actually consume it.

---

## Q3 — The governor

**Single shared limiter: right shape, one line.** One egress IP, one process
(DEPLOY-2 pins `--workers 1`; the disk pin forces recreate deploys, so no dual-process
window) — per-worker backoff provably can't coordinate one bucket. Sound.

**"Slow down as headroom shrinks": implementable, not wishful**, with two mechanics the
design should state: (a) headers from concurrent responses race, so merge monotonically —
track min(`Remain`) and convert `Reset`/`Retry-After` to an absolute monotonic deadline,
never re-read them as relative later; (b) a simple threshold-pause (Remain < N ⇒ all
callers sleep until deadline) is sufficient — proportional slowdown is optional polish.
Note the token-bucket headers only appear on routes where rate limiting is active; the
governor must tolerate their absence.

**Empty bucket at cycle start:** correct behavior is one probe request, read the
deadline, sleep **clipped to the cycle's wall-clock deadline** (see MAJOR-6), and if the
budget expires first, end the cycle having done zero enrichment with a *degraded* outcome.
That is correct precisely because the queue is a DB query — nothing is lost. What the
design misses:

### MAJOR-7: The governor needs priority classes — discovery and enrichment share one bucket

Freshness is measured from discovery, but an enrichment backfill can drain the shared
bucket right before the discovery tick, starving the stage the design declares
"what current means." Give discovery priority or reserved headroom in the governor
(it needs ~51 requests/region/cycle — trivial to reserve), and let enrichment consume
the remainder.

---

## Q4 — Failure taxonomy: is 403-means-gone right?

### MAJOR-5: Invert the coupling — 403 should never write delist state; the watermark already owns delisting

The evidence does support 403 ≈ dead contract: the spec documents 404 as "Contract not
found" and 403 as bare "Forbidden" on this public endpoint, the region list is cached
up to 3600 s (verified), so every run necessarily fetches items for contracts that died
up to an hour before the list was even assembled — a steady 403 trickle is *expected*,
which matches the unattributed Jul 23 logs. But "almost certainly gone" is doing
load-bearing work over an undocumented status code, and the failure mode of being wrong
is silently deleting live contracts. The design gets at most **one cycle of latency**
from treating 403 as a delisting signal — the watermark hides the same contract at the
next sweep anyway. That is a terrible risk/reward trade. Invert it:

- 403/404 ⇒ drop from this cycle's queue, write nothing to delist state.
- If the contract is absent from the next discovery sweep (the normal case), the
  watermark delists it and the queue query never selects it again — self-resolving.
- If it is *still listed* next sweep, re-attempt; N consecutive 403-while-listed ⇒
  dead-letter + metric (this is the genuinely anomalous case worth seeing).

This keeps Stage 1 the sole authority on existence (the clean split the design claims),
makes the unknown 403 causes — new-contract propagation races included — harmless, and
costs one cycle of latency on a signal that was only ever an optimization.

Transient and poisoned classes: sound as specified, with the retry-scheduling caveat in
MAJOR-6. The zero-items invariant is sound — an `item_exchange`/`auction` contract
requires ≥1 item at creation (requested items still appear with `is_included=false`),
so empty = error, always. Extend it per BLOCKER-1: success = ≥1 item AND all pages.

---

## Q5 — The budget mechanism

### MAJOR-6: "Bounded by construction" is only true if the governor yields to the deadline — and the retry/ordering interplay has a real starvation path

Two specific holes:

1. **Deadline clipping.** A governor pause (`Retry-After`, error-window reset) that
   naively sleeps past the cycle's wall-clock deadline un-bounds the run and the
   lock-TTL-safe-by-construction claim collapses. Invariant to state and test: every
   governor sleep is `min(governor_deadline, cycle_deadline)`; hitting the cycle deadline
   ends the cycle. With that, TTL = budget + margin conforms to DEPLOY-3 (pin it with the
   interval-reconfiguration test the pitfall mandates).
2. **Starvation.** Volume-descending ordering + a retryable failure class puts the same
   failing heavy contracts at the head of every cycle's queue. A dozen ~poisoned
   high-volume contracts, each burning bounded retries and 5-token 4xx costs, can consume
   every cycle's budget while the never-attempted tail starves. Required: a
   `next_attempt_at` (backoff schedule) on failures, ordering = never-attempted-first
   (by volume desc), then due-retries; dead-letter threshold as designed. With that,
   starvation requires churn itself to exceed capacity — which the queue-depth metric
   catches, and the capacity math should be stated in the doc: e.g. a 4-minute budget at
   ~20 req/s ≈ 4,800 fetches/cycle vs. plausible Forge churn of low thousands/hour
   (unmeasured — the doc rightly flags this), and cold start ≈ 46k/4,800 ≈ 10 cycles.

---

## Q6 — What does this design get wrong that the current one gets right?

Three things, two already covered: **self-healing via refetch** (BLOCKER-2 — the big
one), **atomic contract+items visibility** (MAJOR-3), and one more:

### MAJOR-4: "Discovery can run far more often — which is what users actually feel" over-promises: ESI caps list freshness at one hour, and the watermark makes sweeps DB-expensive

Verified: `/v1/contracts/public/{region_id}/` is server-side cached **up to 3600 s**.
Sub-hourly discovery re-reads the same cached list (304s or byte-identical bodies) —
the freshness floor is ESI's, not ours. And each sweep is cheap only in ESI requests:
the PR #91 watermark requires restamping `last_seen_at` on **every listed contract every
sweep** (a 304'd page's contracts must still be stamped or they appear delisted), i.e.
~51k row-writes (~103 bulk statements) per sweep against the 256 MB Postgres — fine
hourly, MVCC/vacuum churn at 5-minute cadence for zero freshness gain. The honest claim:
effective cadence improves ~125 min → 60 min and data lands minutes after the tick
instead of 77 — a real, bounded win. The doc's "staleness threshold keeps tripping"
row dissolves correctly ( `data_stale` = 2 × interval = 2 h, comfortably cleared);
just don't sell sub-hourly discovery as a user-visible improvement, because CCP's cache
makes it a no-op. Corollary worth stating instead: since enrichment is resumable, run
*enrichment* on a short interval (5–10 min) with a small budget — that's the cadence
users feel through the ship flag (MAJOR-3), and the design currently leaves it open.

---

## Q7 — Sequencing and migration

### MINOR-8: The repair/invariant ordering is inverted, and the repair predicate is incomplete

As written, step 1 (repair zero-item `COMPLETED` rows) precedes step 2 (invariant that
stops minting them) — the still-running old pipeline can re-mint zero-item `COMPLETED`
rows between the two. Land invariant + repair in the same release (repair as a data
migration riding the invariant deploy), then skip-known. The repair predicate must also
include BLOCKER-1's truncation suspects (item count ≡ 0 mod 1000) and
`ENRICHMENT_INCOMPLETE` rows (already in the queue query — confirm). While repairing,
log the age/ETag distribution of the zero-item rows — 3.1% is measured but the *mechanism*
(304-evicted-body vs. anything else) is still inferred, and the repair is the one chance
to confirm it cheaply.

Otherwise the migration is genuinely incremental-safe: prod DB persists (no recreate;
`DB_RECREATE_ON_STARTUP=false`), recreate deploys prevent old/new dual-writer overlap,
and each step is independently deployable. Two explicit dependencies to write down:
PR #91's watermark must be live before 403-invert/delisting reasoning applies, and #91
itself is sequenced behind #90's deploy per its own PR note. Dev loop: fetch-once +
dev's DB-recreate startup means every dev boot is a cold backfill — the existing
`AGGREGATION_DEV_CONTRACT_LIMIT=100` already covers it; one line, no action.

### Sound sections, one line each

- Stage 1 ETag handling (304-with-missing-body ⇒ refetch without `If-None-Match`): correct, and cheap as claimed.
- Not caching item pages: correct; kills the cache-oversubscription and empty-page rows of the table for the right reason.
- Stage 3 derived flags: sound, given BLOCKER-2's version stamp.
- Two jobs / two locks / TTL from budget: conforms to DEPLOY-3 *given* MAJOR-6's deadline clipping; pin with the interval-reconfiguring test.
- Observability section: right metrics; queue depth is indeed the number that matters — wire it into ops/alerting, not just Prometheus.
- "Deliberately not proposed" (no worker split, no bulk endpoint — confirmed none exists, keep non-ship enrichment): all correct calls.
- Open questions self-assessment: honest; churn measurement should happen in step 0 alongside the instrumentation, since MAJOR-6's capacity math needs it.

---

## Summary table

| # | Rank | Finding | Concrete failure |
|---|------|---------|-----------------|
| 1 | BLOCKER | Items endpoint paginates (1,000/page, `X-Pages`); code fetches page 1 only; fetch-once makes truncation permanent | Highest-value multi-item contracts permanently missing items; unfixable without manual surgery |
| 2 | BLOCKER | No designed re-enrichment lever; fetch-once deletes the self-healing that already rescued two shipped enrichment bugs | Every future enrichment bug = production data migration |
| 3 | MAJOR | Pending-enrichment contracts are user-visible with zero items; atomic visibility of the single-transaction design lost | "Contracts have no items" regression, worst on cold start/backfill |
| 4 | MAJOR | ESI caches the region list 3600 s; sub-hourly discovery is a no-op while watermark stamping costs ~51k row-writes/sweep | Freshness over-promise; DB churn for zero gain if cadence is raised |
| 5 | MAJOR | 403-as-delisting couples enrichment into existence-authority for a one-cycle gain over an undocumented status code | Wrong-cause 403 silently hides live contracts; invert to drop-and-let-watermark-decide |
| 6 | MAJOR | Budget bound is fiction unless governor sleeps clip to the cycle deadline; volume-desc + retries starves the queue head | Lock TTL violated again; backlog never drains despite green runs |
| 7 | MAJOR | Governor lacks priority classes; enrichment can drain the shared bucket ahead of discovery | The stage freshness is measured from starves first |
| 8 | MINOR | Repair-before-invariant ordering re-mints bad rows; repair predicate misses 1000-multiple truncation suspects | 3.1% repair silently regresses between releases |
