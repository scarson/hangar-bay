# ESI Ingestion — Clean-Sheet Design

ABOUTME: A from-first-principles redesign of contract ingestion, written after ESI's 2025 rate-limit changes invalidated the assumptions the current pipeline was built on.
ABOUTME: Proposal for review — not implemented. Supersedes the incremental "add concurrency" plan, which optimized the wrong axis.

## Why start over rather than patch

Three separate investigations in one session each moved the target: the 77-minute run turned out to be ~46,000 sequential per-contract fetches; the fix for that turned out to be *not fetching* rather than fetching faster; and ESI's per-group token buckets (rolled out Oct–Dec 2025, keyed for public routes by source IP) changed what "faster" is even allowed to mean. A design patched across three reversals is not a design anyone would have chosen deliberately.

## The requirement this is judged against

> A user who sets up alerts in Hangar Bay isn't late to landing a great deal when one appears.

EVE contracts are first-come-first-served, so this is a race, not a comfort target. Decomposed
end to end, with measured numbers:

| Stage | Today | Floor |
|---|---|---|
| EVE issue → ESI publishes | 0–30 min | **CCP's cache. Unavoidable.** |
| ESI → our discovery | up to 125 min | seconds |
| Discovery → enrichment sets the ship flag | up to 77 min | ~12 s (≈115 new contracts/cycle) |
| Enrichment → watchlist matcher runs | up to 15 min | seconds |
| Matcher → **the user actually learns** | **unbounded — in-app only** | seconds |

**We currently add ~140 minutes on top of ESI's 30. This design adds under one.**

Three consequences, and the third is the one that matters most:

1. **We can never beat a player watching the in-game contract window.** ESI is 0–30 minutes
   behind reality by design. The achievable goal is to be even with every other ESI consumer,
   and first among them.
2. **The race between ESI consumers is decided by poll phase.** ESI's cache is server-side and
   shared, so every tool sees a new contract at the same instant — when the cache regenerates.
   A fixed 30-minute poll that is 25 minutes out of phase loses by 25 minutes to an otherwise
   identical competitor.
3. **The binding constraint is delivery, not computation.** Notifications are in-app only —
   there is no webhook, email, or push anywhere in the backend. A perfect pipeline notifying a
   browser tab nobody is watching does not win deals. See "The other half" below.

## The observation the whole design turns on

**Public contracts are immutable; the public contract *list* is not.**

A contract's items are fixed at issuance — editing means a new `contract_id`, and auction bids live on a different endpoint. So a contract's items need fetching **exactly once, ever**. What changes over time is only which contracts *exist*.

The current pipeline conflates these into one loop, and every consequence below follows from that:

| | Discovery (which contracts exist) | Enrichment (what's inside one) |
|---|---|---|
| Mutability | changes constantly | immutable once fetched |
| Cost | 34 paginated requests per region (measured `X-Pages`) | 1 request per *new* contract |
| Steady-state volume | constant | proportional to churn, not to corpus |
| Caching | ETag validators are the right tool | validators are pointless — read-once |
| Failure meaning | region unavailable | one contract unknown |
| Freshness meaning | **this is what "current" means** | backlog depth, not currency |

Conflating them forces the fast, cheap, mutable half to run at the speed of the slow, expensive, immutable half — and makes the corpus size, rather than the churn rate, set the cost of every cycle.

## The design

### Stage 1 — Discovery (every cycle, seconds)

Fetch each region's paginated public contract list. Upsert contract rows and stamp `last_seen_at` (the mechanism already in PR #91). Presence and absence both come from here: a contract missing from a complete region sweep is delisted.

ETag validators genuinely belong here — a list page either changed or it didn't. But **a 304 whose cached body is missing must re-request without `If-None-Match`**, never return an empty page. The Forge is 34 pages (measured); correctness costs one extra request in the rare miss.

Note that **absence requires a complete sweep**: a contract is only known to be gone once every
page of its region has been read. Pages cannot be skipped to save requests, which is why
discovery cost is fixed per region rather than proportional to change.

Freshness and staleness are measured **from this stage**, because this stage is what determines
whether the listing is current. Today they are measured from a run that also drags 46,000 item
fetches behind it, which is why the staleness threshold keeps tripping.

**Scheduling comes from the `Expires` header, not from a fixed interval.** ESI states exactly
when the next version of a list becomes available (measured: `Expires` − `Last-Modified` =
1800 s; `X-Pages: 34` for The Forge). Polling at that moment — plus a small jitter, and per
region, since regions expire independently — puts us within seconds of the earliest instant the
data can exist. A fixed interval is strictly worse at every cadence: faster only collects 304s,
slower loses the race by however far it drifts out of phase. A missing or unparseable header
falls back to a configured default.

### Stage 2 — Enrichment (budgeted, resumable, incremental)

The work queue is a **query, not a data structure**: contracts whose items have never been successfully fetched. `item_processing_status` already models exactly this and is currently written but never read back.

- **Fetch once, ever.** A successfully enriched contract is never re-fetched. Steady state drops from the corpus (~46,000) to the churn (new contracts since the last cycle).
- **Do not ETag-cache item pages.** A validator on immutable read-once data buys nothing and costs cache pressure in a 25 MB instance that cannot hold it. This deletes the silent-empty-page failure entirely rather than fixing it.
- **Budgeted per cycle** — wall-clock first, plus caps on requests and error budget. This is
  what makes run duration *bounded by construction*, and it only holds under an explicit
  invariant: **every governor sleep is `min(governor_deadline, cycle_deadline)`.** Without that
  clipping, a single long `Retry-After` un-bounds the run and the lock-TTL guarantee collapses.
- **Retry scheduling, not just retry counting.** Volume-descending order plus retryable failures
  would otherwise park the same heavy failing contracts at the queue head every cycle and starve
  everything behind them. Each queued contract carries a `next_attempt_at`, and
  never-attempted contracts sort ahead of retries.
- **Resumable.** The queue lives in the database, so an interrupted, rate-limited, or redeployed run loses no work; the next cycle resumes.
- **Ordered by contract volume, descending.** Under a budget, ordering decides what you get first — and hulls are the product's headline. This is where volume belongs: as a **priority**, never as the filter that was rejected for foreclosing non-ship item data.

### Two lanes, chained rather than independently scheduled

Three stages on three independent schedules stack their worst cases (125 + 77 + 15 minutes).
Chaining them on the *delta* collapses that to the work itself:

**Fast lane — the deal-alert path.** Discovery completes → enrich only the contracts it just
discovered → match only those contracts → deliver. Small budget, highest governor priority,
runs on every discovery tick. At ~230 new contracts/hour that is ~115 per 30-minute cycle,
about 12 seconds of enrichment. This lane exists to satisfy the user story and nothing else.

**Backfill lane — everything that is not time-critical.** Cold start, newly added regions,
`enrichment_version` bumps, and retries of previously failed contracts. Budgeted, lowest
priority, and it yields to the fast lane through the governor's priority classes so a
multi-cycle backfill can never delay an alert.

The two lanes share one queue (the same DB query, differently ordered and bounded) and one
governor. Splitting them by *priority* rather than by *process* keeps the deployment single-
service, while leaving the eventual scheduler split a deployment decision rather than a rewrite.

### What fetch-once destroys, and how to give it back

The refetch-everything loop is an accidental **self-healing mechanism**, and this codebase has
already cashed that cheque twice: `is_ship_contract` never being set, and `is_blueprint_copy`
never being mapped, were both repaired by the next full sweep after the fix landed. Fetch-once
removes that safety net, so the *next* enrichment bug becomes a hand-written production
migration instead of a no-op.

The cheap replacement is an **`enrichment_version` stamp** on each contract. Bumping a
constant re-queues the corpus through exactly the same budgeted, governed machinery — a
deliberate, observable, rate-limited backfill rather than an accident that happened to work.
This is what makes fetch-once safe to adopt rather than merely fast.

### Stage 3 — Derived flags

`is_ship_contract` is computed when enrichment lands, from items — unchanged in substance, but now it happens once per contract rather than being recomputed against refetched data every cycle.

### A state the split creates, which must be decided rather than discovered

Today contracts, items and derived flags commit in one transaction, so a contract is never
visible without its items. Splitting the stages makes **"listed, zero items, enrichment
pending"** a real, persistent, user-visible state — and indistinguishable from the 3.1% bug
unless it is modelled deliberately.

Decision: **un-enriched contracts are excluded from filtered list views.** `is_ship_contract`
is genuinely *unknown* until items land, and answering "not a ship" is a lie that puts hulls in
the wrong bucket. They remain reachable by direct link, consistent with the expired-contract
treatment already shipped.

### The rate-limit governor

A **single shared limiter** in front of every ESI call, because both ESI limits are keyed by source IP and we have exactly one egress IP. Per-request backoff cannot help: twenty workers each backing off independently still collectively exceed one bucket.

It must:
- Track `X-Esi-Error-Limit-Remain` / `-Reset` and the token-bucket headers, and slow the *whole* pipeline as headroom shrinks rather than reacting after a breach.
- Treat 420 and 429 as first-class, honoring `Retry-After`. The current client's `< 500 == success` predicate makes both invisible — they skip retry and degrade into per-contract "failures."
- Price 4xx correctly (5 tokens under the new scheme), so an error storm throttles itself.
- **Fail the run as degraded, not successful,** when it pauses on a limit. Today a limit breach
  would record a successful run over missing data.
- **Reserve headroom for discovery.** Both stages share one bucket because both share one egress
  IP, so an enrichment backfill can otherwise starve the very stage that freshness is measured
  from. The governor needs priority classes: discovery draws first.

### Failure taxonomy

The current code has one bucket ("fetch failed"). Three behaviors are needed:

- **Transient** (5xx, timeout, 420/429): stays queued, bounded retries with backoff. Not an error about the contract.
- **Gone** (403/404): the contract was almost certainly accepted or withdrawn between the list
  fetch and the item fetch — expected in volume, since the list is served from a cache up to
  30 minutes old. **Drop it from the queue and write nothing.** An earlier draft made 403 a
  delisting signal; that is wrong. It would bet existence-authority on an undocumented
  "Forbidden" to buy at most one cycle of latency over what the discovery watermark already
  provides. **Stage 1 remains the sole authority on existence.** A contract still listed on the
  next sweep that 403s repeatedly is dead-lettered with a metric.
- **Poisoned** (repeated failures beyond a threshold): dead-lettered so it stops consuming error budget every cycle, and stays visible in metrics.

And the invariant that makes fetch-once safe at all. **Enrichment succeeds only when the
result is non-empty AND every page was fetched.** Two ways that is violated today:

- **An `item_exchange`/`auction` contract with zero items is impossible.** An empty result is
  an error, never `COMPLETED`. Currently recorded as success — measured at 3.1% of sampled
  production contracts.
- **`get_contract_items` requests only page 1.** It calls the ETag helper with the default
  `all_pages=False`, while its sibling `get_public_contracts` correctly passes `all_pages=True`
  — so any contract with >1,000 items is silently truncated. Latent rather than active today
  (sampled max 422 items, p99 16, none at 1,000), but fetch-once would make that truncation
  permanent and unrepairable. Fix before, not after.

### Latency: what is actually achievable

**Measured against live ESI, not assumed.** A region's public contract list returns
`Expires` − `Last-Modified` = **1800 s**; the swagger documents up to 3600 s. `X-Pages` is
**34** for The Forge at 1,000/page.

So **discovery cannot beat ~30 minutes** — CCP's cache is the floor, and polling faster only
buys 304s. "New contracts within minutes" is not reachable for discovery at any cadence.

What *is* reachable, and what users actually feel, is the second half. A contract only enters
the default view once enrichment sets `is_ship_contract`, and today that is welded to a
77-minute run. Chained to discovery, that gap becomes the work itself — roughly 12 seconds for
a cycle's worth of new contracts, sequentially, with no concurrency at all.

An independent enrichment tick would add nothing for *new* contracts, since new work only
exists when discovery has just run. A short periodic tick is useful only for the backfill lane,
which always has work while a backlog exists.

| | today | this design |
|---|---|---|
| Newest contract in the database | **129 min old** (measured) | ~30–40 min |
| Discovery → visible in the ships view | up to 77 min | ~12 s (chained) |
| Floor set by | our pipeline | CCP's 30-min cache |

The honest headline: 129 minutes → ~30–40, with the remainder being CCP's, not ours.

### Job topology, and what happens to `run_aggregation`

Today's single `run_aggregation` job becomes **two scheduled jobs and one chain**:

| Job | Trigger | Budget | Lock TTL |
|---|---|---|---|
| **Discovery** (per region) | `Expires` of that region's last response, + jitter | seconds | minutes |
| **Backfill enrichment** | short periodic tick, only while a backlog exists | small, wall-clock bounded | budget + margin |
| *Fast-lane enrichment → match → deliver* | **chained**, not scheduled: runs inline at the end of each discovery sweep | small, wall-clock bounded | inherits discovery's |

The **watchlist matcher stops being an independent 15-minute interval job** for new contracts.
It runs chained, against only the contracts just enriched — which is what removes its worst-case
15 minutes from the alert path. It retains a periodic full pass, because watchlist *entries*
change independently of contracts and a user adding a watch item must eventually match against
contracts already in the corpus.

`run_aggregation` is not deleted so much as split along the seam it already contains:
`_fetch_regions` becomes discovery, `_fetch_item_rows` becomes enrichment, and
`_process_contracts` is divided between them.

### Locking and cadence

Each job carries a lock whose TTL derives from that job's own bounded budget. This replaces the current arrangement, where a 65-minute lock TTL guards a 77-minute run and is saved only by tick alignment. Bounded duration is a structural fix; a lock heartbeat would be a patch on an unbounded run.

Discovery cadence is **not** a free lever: it is pinned to CCP's 30-minute cache, and polling
faster only collects 304s while forcing a full `last_seen_at` sweep over ~45k rows on a
256 MB Postgres each time. The lever that users feel is enrichment *latency after* discovery,
which the chained fast lane makes near-zero.

### Observability

None exists today; the 77-minute decomposition is inference. Minimum: per-stage duration and counts, error-budget headroom, and — the key operational metric — **enrichment queue depth**. A growing queue is the single number that says "falling behind," and nothing currently reports it.

## The other half: alert delivery

The pipeline work above makes an alert *correct and timely*. It does not make it *arrive*.
Notifications terminate in an in-app list today, for an audience `PRODUCT.md` describes as
alt-tabbed out of the game. Against the stated user story, that is the single largest source of
latency — and it is unbounded, because it depends on when someone next opens a tab.

**Discord webhooks**, for a corporation that already lives there. Design decisions worth fixing
now:

- **Per-user webhook URL, pasted by the user.** This covers the corp-channel case too (paste a
  channel's webhook) without modelling corporations, which we do not otherwise need.
- **The URL is a credential.** Anyone holding it can post to that channel, so it is encrypted at
  rest with the existing `TOKEN_CIPHER_KEYS` mechanism already used for ESI tokens — not stored
  in plaintext, and never logged.
- **Delivery is chained to matching, not separately scheduled.** Re-introducing an independent
  delivery tick would re-introduce the latency the fast lane just removed.
- **Delivery failure is isolated.** A dead or rate-limited webhook must never fail the matcher
  or block other users' notifications; failures retry with backoff and then disable the hook
  with a visible reason rather than retrying forever.
- **Build the embed directly.** Discord webhooks accept rich embeds, so the alert carries hull,
  price, location, time remaining and a link without depending on crawler unfurling. That also
  makes it immune to the per-URL preview work being deferred.
- **Dedup already exists.** The partial unique index on notifications (SQLA-2) prevents
  re-alerting the same user about the same contract; delivery inherits it.

This is a distinct workstream from the ingestion pipeline, and it is deliberately named here
because the user story is not satisfied by either half alone.

## What this buys

| Problem | How it dissolves |
|---|---|
| 77-minute runs | Steady state becomes churn-sized, not corpus-sized |
| Lock TTL < run duration | Runs are bounded by budget, by construction |
| Staleness threshold tripping | Freshness measured from the cheap stage |
| Cache oversubscription | Item pages stop being cached at all |
| Silent empty pages | Deleted, not fixed — no validator, and empty ≠ success |
| Unattributed 403s | Classified as *gone*: dropped from the queue, never treated as existence authority |
| Coverage expansion | Discovery scales with regions; enrichment with churn |
| **Alert latency** | **~140 min of our own latency → under 1 min; the rest is CCP's** |

The last row is the strategic point: the current design makes each new region cost another full corpus sweep every cycle. This one makes a new region a one-time backfill plus its share of churn — which is the difference between coverage being affordable and not.

## Migration from the current state

1. **Land the success invariant and the repair in the same release.** Repairing first leaves a
   window in which the old pipeline re-mints zero-item `COMPLETED` rows between deploys. The
   repair predicate covers zero-item `COMPLETED` contracts *and* item counts that are an exact
   multiple of 1,000 (the truncation signature — currently expected to match nothing, which is
   itself worth confirming). Log the distribution of what it finds: 3.1% is measured, but the
   304-with-evicted-body *mechanism* behind it is still inferred, and the repair is the one
   cheap opportunity to confirm it.
2. Add `enrichment_version`, so the self-healing property is replaced before it is removed.
3. Enable skip-known. This alone collapses the steady-state workload.
4. Add the governor before any concurrency.
5. Add bounded concurrency, scoped to cold start and backfill.

## Deliberately not proposed

- **A separate worker process.** The DB-backed queue makes splitting enrichment into its own service a deployment decision rather than a redesign, so it costs nothing to defer — and on Render it costs money to adopt.
- **Bulk item fetching.** ESI exposes no batch endpoint for contract items; per-contract is forced.
- **Dropping non-ship enrichment.** Rejected earlier and still rejected: it regresses the shipped `is_ship_contract=false` view, which carries item data today.

## Open questions

- ~~Churn rate is unmeasured~~ — **measured: ~230 new contracts/hour** (300 contracts spanning
  78.4 min of `date_issued`), against a 45,441 corpus. A ~197× ratio, which is what the
  steady-state argument rests on. Cross-check: 230/hr over a 45k corpus implies ~8 days average
  contract lifetime, consistent with EVE's common 3-day/1-week/2-week durations.
- **Delivery-side latency is unmeasured.** Discord webhook round-trip and its rate limits are
  not characterised, and they sit on the critical path of the user story.
- **Token-bucket parameters** for public contract routes are not established here — the governor's shape is right regardless, but its tuning needs the real numbers.
- **Backfill duration** for a cold start (or a newly added region) under a correct governor is unknown, and it sets how long coverage expansion takes to become useful.
