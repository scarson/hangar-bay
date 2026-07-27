# ESI Ingestion & Alerting — Clean-Sheet Design

ABOUTME: From-first-principles redesign of contract ingestion and alert delivery, driven by the requirement that an alert user isn't late to a deal.
ABOUTME: Proposal — not implemented. Rewritten at round 3 of an alternating adversarial review; supersedes the "add concurrency" plan and the patched drafts before it.

## The requirement

> A user who sets up alerts in Hangar Bay isn't late to landing a great deal when one appears.

EVE contracts are first-come-first-served, so this is a race.

**The promise is narrow, and should be stated plainly: the user is never late *because of us*.** It does not promise the user wins. Every serious ESI-based tool can play the same scheduling game described below, so this buys **parity with other tools, not advantage over them** — and against semi-automated snipers watching extreme Jita mispricings, or a player sitting in the in-game contract window, we lose regardless. ESI is 0–30 minutes behind reality by design and no client-side choice changes that.

What we control is the ~140 minutes we currently add on top.

## A discipline this document is under

Three review rounds found the same failure repeatedly: **asserting end-to-end properties from whichever component was in focus, backed by single-point measurements promoted into constants.** Concurrency-first; "speed dissolves the lock/cache/staleness problems"; "discovery cadence is what users feel"; one `Expires` sample becoming "the floor"; one 384-contract sample becoming "latent"; one churn sample becoming a rate.

Three rules apply throughout:

1. Every **"by construction"** claim names the mechanism enforcing it *and* the test pinning it.
2. Every **measurement carries its sample scope** where it is used, not only where it was taken.
3. Every **latency claim walks the whole chain**, including systems that aren't ours — CCP's lazily-regenerated cache, Discord, and the user's spaceship.

## The observation the design turns on

**Public contracts are immutable; the public contract *list* is not.**

Items are fixed at issuance — editing produces a new `contract_id`, and auction bids live on a separate endpoint. So items need fetching **exactly once, ever**. What changes is only which contracts exist.

The current pipeline conflates these, and every problem below follows:

| | Discovery (which contracts exist) | Enrichment (what's inside one) |
|---|---|---|
| Mutability | changes constantly | immutable once fetched |
| Cost | fixed per region (34 pages for The Forge, 2–3 for other hubs — one sample, 2026-07-27) | 1 request per *new* contract |
| Steady-state volume | constant | proportional to churn |
| Caching | validators are the right tool | validators are pointless — read-once |
| Freshness meaning | **this is what "current" means** | backlog depth, not currency |

Conflating them makes corpus size, rather than churn rate, set the cost of every cycle.

## Design

### Stage 1 — Discovery

Fetch each region's paginated public contract list; upsert rows; stamp `last_seen_at` (PR #91's mechanism). Presence *and absence* both come from here, and **absence requires a complete sweep** — a contract is only known gone once every page of its region has been read, so pages can never be skipped to save requests.

**Scheduling comes from `Expires`, not a fixed interval.** ESI's cache is server-side and shared, so every consumer sees a new generation at the same instant; the race between tools is decided by poll phase. Measured across five trade hubs (2026-07-27): TTL uniformly **1800 s**, but **expiry phase differs per region** — four hubs regenerated within a 95-second window, Amarr 28 minutes later. So scheduling is per region.

Regeneration appears **lazy** — triggered by the first request after expiry rather than a clock. Two consequences:
- Poll at `Expires + ε`, never before. Polling early re-reads the stale body; there is nothing to be early to.
- We plausibly become the trigger, which is as good as this race gets.

**Nothing about the TTL is hard-coded.** We measured 1800 s; the swagger documents up to 3600 s. The design survives that discrepancy precisely because it reads the header. Skew is corrected via `Expires − Date` rather than local time, and the computed delay is floored and capped.

**Generation shear is the hazard this scheduling creates**, and it is why the watermark can hurt. A 34-page sweep starting at `Expires + ε` can straddle a lazy regeneration and mix generations; page boundaries shift; a live contract can be skipped. PR #91's watermark would then read that contract as delisted and hide it for a full cycle — **a user-visible false delisting.**

Enforcement, with pinning tests:
- Every page's `Last-Modified` must equal page 1's; a mismatch aborts and restarts the sweep.
- **The watermark is stamped only from a consistent, complete sweep.** An inconsistent sweep may still upsert contract data; it may not conclude anything about absence.
- Test: a fixture serving a mid-sweep `Last-Modified` change must not advance the watermark.
- Opposite edge: a poll returning the *previous* generation triggers a short bounded re-poll rather than accepting it — otherwise the scheduler silently concedes the race it exists to win, one cycle at a time.

### Stage 2 — Enrichment

The queue is a **query, not a data structure**: contracts whose items have never been successfully fetched. `item_processing_status` already models this and is written but never read back.

- **Fetch once, ever.** Steady state drops from the corpus (~46,000) to churn — measured **~230 new contracts/hour** against a 45,441 corpus (300-contract sample spanning 78.4 minutes of `date_issued`; single sample, and **churn is diurnal**, so treat it as an order of magnitude rather than a rate — the budget below absorbs the variance).
- **Do not ETag-cache item pages.** A validator on immutable read-once data buys nothing and costs pressure in a 25 MB instance that cannot hold it. This deletes the silent-empty-page failure rather than fixing it.
- **Budgeted per cycle** — wall-clock first, plus request and error-budget caps. Enforced by clipping every governor sleep to `min(governor_deadline, cycle_deadline)`. Pinned by a test asserting a long `Retry-After` cannot extend a cycle past its deadline.
- **Retry scheduling, not counting.** `next_attempt_at` per row; never-attempted contracts sort ahead of retries, so failing heavy contracts cannot park at the queue head.
- **Rows are claimed**, not merely selected, so the two lanes cannot double-fetch the same contract.
- **Resumable.** The queue is a DB query, so interruption, rate-limiting or redeploy loses no work.
- **Ordered by volume descending** — under a budget, ordering decides what arrives first, and hulls are the headline. Volume as *priority*, never the filter rejected earlier for foreclosing non-ship item data.

### Stage 3 — Matching

Matching runs **chained after every enrichment batch, in either lane** — not only the fast lane. A contract that falls to backfill must not thereby exit the alert path.

A periodic full pass remains, because watchlist *entries* change independently of contracts: a user adding a watch item must eventually match against contracts already in the corpus. Its interval is a stated setting, not an accident.

### Stage 4 — Delivery

**Delivery is not in the chain.** The chain performs a **first attempt only, under a ~10 s budget**; everything else runs on a separate tick. In order of severity:

1. An inline retrying HTTP call to a third party un-bounds the chain's duration — the same 65-minute-lock/77-minute-run defect this design exists to eliminate, re-derived one layer up.
2. It couples discovery freshness to Discord's availability: an outage would hold the lock past the next `Expires` tick.
3. "Retry with backoff" is *unimplementable* in a chained-only model, because nothing runs between discovery ticks.

**The notifications table is already the delivery queue** — it needs `delivered_at` and `attempts`, not a new queue.

**Delivery is at-least-once, explicitly.** The SQLA-2 partial index dedups notification *creation*, not delivery; a crash between POST and commit re-sends. That is the accepted semantic, and a duplicate alert is the acceptable failure.

### Delivery security — a user-supplied URL is an SSRF primitive

The backend POSTs to a URL the user supplies, from inside Render's private network. Encryption at rest was the wrong frame; confidentiality is the lesser problem.

Non-negotiable:
- **Strict host allowlist** — Discord's webhook surface only. Not a blocklist, not a scheme check.
- **Redirects refused**, never followed.
- **~5 s timeout**, and no response body interpreted beyond status.
- Stored encrypted via the existing `TOKEN_CIPHER_KEYS` mechanism, never logged.

Also required: a **per-webhook rate limiter separate from the ESI governor** (Discord's limits are Discord's), **embed batching** (10 per message) with a digest cap so a backfill cannot flood a channel, a **test message on save** so a wrong paste fails immediately and visibly, and a **re-enable path** for auto-disabled hooks.

Alerts carry an embed we build directly — hull, price, location, time remaining, link — so delivery does not depend on crawler unfurling and is unaffected by per-URL previews being deferred.

## The rate-limit governor

A **single shared limiter** in front of every ESI call, because both ESI limits are keyed by source IP and we have one egress IP. Per-request backoff cannot help: twenty workers each backing off independently still collectively exceed one bucket.

- Tracks `X-Esi-Error-Limit-Remain` / `-Reset` and any token-bucket headers, slowing the whole pipeline as headroom shrinks rather than reacting after a breach.
- Treats 420 and 429 as first-class with `Retry-After`. Today's `< 500 == success` predicate makes both invisible — they skip retry and degrade into per-contract "failures."
- **Fails open on absent headers.** No `X-Ratelimit-*` appeared on a live public-contracts response (2026-07-27), so that rollout has not reached this group; the governor must not stall when expected headers are missing.
- **Reserves budget, not merely draw order, for discovery.** Priority cannot conjure back budget a backfill has already burned, so the reservation binds the error and token budgets themselves.
- **Records a degraded run, not a successful one,** when it pauses on a limit.

## Failure taxonomy

- **Transient** (5xx, timeout, 420/429): stays queued, bounded retries with backoff.
- **Gone** (403/404): the contract was accepted or withdrawn between list and item fetch — expected in volume, since the list is up to 30 minutes stale. **Drop from the queue, write nothing.** Discovery remains the sole authority on existence; making 403 a delisting signal would bet existence on an undocumented "Forbidden" to buy at most one cycle over what the watermark already gives.
- **Poisoned** (repeated failures past a threshold): dead-lettered with a metric, so it stops consuming error budget every cycle.

**The invariant that makes fetch-once safe: enrichment succeeds only when the result is non-empty AND every page was fetched.** Violated two ways today:
- An `item_exchange`/`auction` contract with zero items is impossible; an empty result is an error, never `COMPLETED`. Currently recorded as success — **3.1% of a 384-contract sample** (2026-07-27).
- `get_contract_items` passes the default `all_pages=False` while `get_public_contracts` passes `True`, truncating any contract past 1,000 items. **Latent in that same sample** (max 422 items, p99 16, none at 1,000) — but fetch-once makes truncation permanent, so it is fixed before, not after.

## What fetch-once destroys, and how to give it back

The refetch-everything loop is accidental **self-healing**, and this repo has cashed that cheque twice: `is_ship_contract` never being set, and `is_blueprint_copy` never being mapped, were both repaired by the next full sweep. Fetch-once makes the *next* enrichment bug a hand-written production migration instead of a no-op.

An **`enrichment_version` stamp** replaces it: bumping a constant re-queues the corpus through the same budgeted, governed machinery — a deliberate, observable backfill rather than an accident that worked.

## Job topology

| Job | Trigger | Budget | Lock TTL |
|---|---|---|---|
| **Discovery** (per region) | that region's `Expires + ε`, skew-corrected | seconds | its budget + margin |
| **Fast lane**: enrich-new → match | chained inline after a consistent sweep | small, wall-clock bounded | **sum of stage budgets + margin** |
| **Backfill enrichment → match** | short periodic tick while a backlog exists | small, wall-clock bounded | its budget + margin |
| **Delivery retries** | periodic tick | small | its budget + margin |
| **Full watchlist pass** | stated interval | small | its budget + margin |

No lock inherits another's TTL. `run_aggregation` splits along the seam it already contains: `_fetch_regions` → discovery, `_fetch_item_rows` → enrichment, `_process_contracts` divided between them.

## The latency chain, end to end

| Hop | Today | This design | Whose |
|---|---|---|---|
| EVE issue → ESI generation | 0–30 min | 0–30 min | **CCP's** |
| ESI → our discovery | up to 125 min | seconds (poll at `Expires + ε`) | ours |
| Discovery → ship flag set | up to 77 min | ~12 s, sequential | ours |
| Ship flag → matched | up to 15 min | seconds (chained) | ours |
| Matched → delivered to Discord | **never** | seconds (first attempt inline) | ours + Discord's |
| Delivered → user acts | unbounded | unbounded | **the user's** |

Ours falls from ~140 minutes to under one. The first and last rows are not ours and do not move.

## What this buys

| Problem | How it dissolves |
|---|---|
| 77-minute runs | Steady state becomes churn-sized, not corpus-sized |
| Lock TTL < run duration | Every job's TTL derives from its own bounded budget |
| Staleness threshold tripping | Freshness measured from the cheap stage |
| Cache oversubscription | Item pages stop being cached |
| Silent empty pages | Deleted, not fixed — no validator, and empty ≠ success |
| Unattributed 403s | Classified *gone*; never an existence authority |
| Alerts nobody sees | Delivery to where the corp actually is |
| Coverage expansion | Discovery fixed per region; enrichment scales with churn |

## Migration

Each step is independently deployable; recreate deploys prevent dual-writer overlap.

1. **Success invariant + repair, in one release.** Repair-first leaves a window where the old pipeline re-mints zero-item `COMPLETED` rows. Predicate: zero-item `COMPLETED` contracts, plus item counts at exact multiples of 1,000. Log the distribution — 3.1% is measured, but the 304-with-evicted-body *mechanism* is still inferred, and this is the cheap chance to confirm it.
2. **`enrichment_version`** — replace self-healing before removing it.
3. **Skip-known.** Collapses the steady-state workload; the single largest win.
4. **Governor**, before any concurrency.
5. **Discovery/enrichment split**, with sweep-consistency checks and per-job locks. `/ready`'s freshness source rewires to discovery here.
6. **`Expires` scheduling**, replacing the fixed interval.
7. **Delivery**: schema, SSRF-safe sender, retry tick, then chaining.
8. **Bounded concurrency**, scoped to backfill.

Steps 1–3 deliver most of the latency win and are independent of the rest.

## Deliberately not proposed

- **A separate worker process.** A DB-backed queue makes that a deployment decision, not a redesign — and on Render it costs money.
- **Bulk item fetching.** ESI exposes no batch endpoint; per-contract is forced.
- **Dropping non-ship enrichment.** Regresses the shipped `is_ship_contract=false` view.
- **Preemption between lanes.** Draining in-flight requests costs ~1–2 s at these scales; budget reservation suffices.

## Open questions

- **Delivery-side latency and Discord's rate limits** are uncharacterised and sit on the critical path.
- **Token-bucket parameters** for public contract routes are unestablished; the governor's shape is right regardless, but tuning needs real numbers.
- **Backfill duration** for a cold start or a new region, under a correct governor, is unknown — and it sets how long coverage takes to become useful.
- **Churn is diurnal** and measured once; the budget absorbs variance, but a sustained-peak measurement would firm up sizing.
- **A backlog lever on the human hop:** ESI's authenticated `POST /ui/openwindow/contract/` (`esi-ui.open_window` scope) can open a contract directly in the user's game client from an alert. That attacks the one hop this design otherwise concedes entirely.
