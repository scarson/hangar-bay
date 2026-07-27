# ESI Ingestion — Clean-Sheet Design

ABOUTME: A from-first-principles redesign of contract ingestion, written after ESI's 2025 rate-limit changes invalidated the assumptions the current pipeline was built on.
ABOUTME: Proposal for review — not implemented. Supersedes the incremental "add concurrency" plan, which optimized the wrong axis.

## Why start over rather than patch

Three separate investigations in one session each moved the target: the 77-minute run turned out to be ~46,000 sequential per-contract fetches; the fix for that turned out to be *not fetching* rather than fetching faster; and ESI's per-group token buckets (rolled out Oct–Dec 2025, keyed for public routes by source IP) changed what "faster" is even allowed to mean. A design patched across three reversals is not a design anyone would have chosen deliberately.

## The observation the whole design turns on

**Public contracts are immutable; the public contract *list* is not.**

A contract's items are fixed at issuance — editing means a new `contract_id`, and auction bids live on a different endpoint. So a contract's items need fetching **exactly once, ever**. What changes over time is only which contracts *exist*.

The current pipeline conflates these into one loop, and every consequence below follows from that:

| | Discovery (which contracts exist) | Enrichment (what's inside one) |
|---|---|---|
| Mutability | changes constantly | immutable once fetched |
| Cost | ~51 paginated requests per region | 1 request per *new* contract |
| Steady-state volume | constant | proportional to churn, not to corpus |
| Caching | ETag validators are the right tool | validators are pointless — read-once |
| Failure meaning | region unavailable | one contract unknown |
| Freshness meaning | **this is what "current" means** | backlog depth, not currency |

Conflating them forces the fast, cheap, mutable half to run at the speed of the slow, expensive, immutable half — and makes the corpus size, rather than the churn rate, set the cost of every cycle.

## The design

### Stage 1 — Discovery (every cycle, seconds)

Fetch each region's paginated public contract list. Upsert contract rows and stamp `last_seen_at` (the mechanism already in PR #91). Presence and absence both come from here: a contract missing from a complete region sweep is delisted.

ETag validators genuinely belong here — a list page either changed or it didn't. But **a 304 whose cached body is missing must re-request without `If-None-Match`**, never return an empty page. The corpus is ~51 pages per region; correctness costs one extra request in the rare miss.

Freshness and staleness are measured **from this stage**, because this stage is what determines whether the listing is current. Today they are measured from a run that also drags 46,000 item fetches behind it, which is why the staleness threshold keeps tripping.

### Stage 2 — Enrichment (budgeted, resumable, incremental)

The work queue is a **query, not a data structure**: contracts whose items have never been successfully fetched. `item_processing_status` already models exactly this and is currently written but never read back.

- **Fetch once, ever.** A successfully enriched contract is never re-fetched. Steady state drops from the corpus (~46,000) to the churn (new contracts since the last cycle).
- **Do not ETag-cache item pages.** A validator on immutable read-once data buys nothing and costs cache pressure in a 25 MB instance that cannot hold it. This deletes the silent-empty-page failure entirely rather than fixing it.
- **Budgeted per cycle** — wall-clock first, plus caps on requests and error budget. This is what makes run duration *bounded by construction*.
- **Resumable.** The queue lives in the database, so an interrupted, rate-limited, or redeployed run loses no work; the next cycle resumes.
- **Ordered by contract volume, descending.** Under a budget, ordering decides what you get first — and hulls are the product's headline. This is where volume belongs: as a **priority**, never as the filter that was rejected for foreclosing non-ship item data.

### Stage 3 — Derived flags

`is_ship_contract` is computed when enrichment lands, from items — unchanged in substance, but now it happens once per contract rather than being recomputed against refetched data every cycle.

### The rate-limit governor

A **single shared limiter** in front of every ESI call, because both ESI limits are keyed by source IP and we have exactly one egress IP. Per-request backoff cannot help: twenty workers each backing off independently still collectively exceed one bucket.

It must:
- Track `X-Esi-Error-Limit-Remain` / `-Reset` and the token-bucket headers, and slow the *whole* pipeline as headroom shrinks rather than reacting after a breach.
- Treat 420 and 429 as first-class, honoring `Retry-After`. The current client's `< 500 == success` predicate makes both invisible — they skip retry and degrade into per-contract "failures."
- Price 4xx correctly (5 tokens under the new scheme), so an error storm throttles itself.
- **Fail the run as degraded, not successful,** when it pauses on a limit. Today a limit breach would record a successful run over missing data.

### Failure taxonomy

The current code has one bucket ("fetch failed"). Three behaviors are needed:

- **Transient** (5xx, timeout, 420/429): stays queued, bounded retries with backoff. Not an error about the contract.
- **Gone** (403/404): almost certainly the contract was accepted or withdrawn between the list fetch and the item fetch. This is a **delisting signal, not an error** — it should feed Stage 1's absence handling. I suspect this is the entire explanation for the unattributed 403s in the Jul 23 logs.
- **Poisoned** (repeated failures beyond a threshold): dead-lettered so it stops consuming error budget every cycle, and stays visible in metrics.

And one invariant worth enforcing loudly: **an `item_exchange`/`auction` contract with zero items is impossible.** An empty result is an error, never a `COMPLETED`. Today it is silently recorded as success — measured at 3.1% of sampled contracts in production.

### Locking and cadence

Two jobs, two locks, each with a TTL derived from that job's own bounded budget. This replaces the current arrangement, where a 65-minute lock TTL guards a 77-minute run and is saved only by tick alignment. Bounded duration is a structural fix; a lock heartbeat would be a patch on an unbounded run.

Discovery can then run far more often than enrichment, because it is cheap — which is what users actually feel.

### Observability

None exists today; the 77-minute decomposition is inference. Minimum: per-stage duration and counts, error-budget headroom, and — the key operational metric — **enrichment queue depth**. A growing queue is the single number that says "falling behind," and nothing currently reports it.

## What this buys

| Problem | How it dissolves |
|---|---|
| 77-minute runs | Steady state becomes churn-sized, not corpus-sized |
| Lock TTL < run duration | Runs are bounded by budget, by construction |
| Staleness threshold tripping | Freshness measured from the cheap stage |
| Cache oversubscription | Item pages stop being cached at all |
| Silent empty pages | Deleted, not fixed — no validator, and empty ≠ success |
| Unattributed 403s | Reclassified as delisting signals |
| Coverage expansion | Discovery scales with regions; enrichment with churn |

The last row is the strategic point: the current design makes each new region cost another full corpus sweep every cycle. This one makes a new region a one-time backfill plus its share of churn — which is the difference between coverage being affordable and not.

## Migration from the current state

1. **Repair before optimizing.** Contracts marked `COMPLETED` with zero items must be re-queued *before* skip-known is enabled, or the ~3% currently missing items become permanently invisible. One-time query.
2. Land the failure taxonomy and the invariant, so the repair cannot silently recur.
3. Enable skip-known. This alone collapses the steady-state workload.
4. Add the governor before any concurrency.
5. Add bounded concurrency, scoped to cold start and backfill.

## Deliberately not proposed

- **A separate worker process.** The DB-backed queue makes splitting enrichment into its own service a deployment decision rather than a redesign, so it costs nothing to defer — and on Render it costs money to adopt.
- **Bulk item fetching.** ESI exposes no batch endpoint for contract items; per-contract is forced.
- **Dropping non-ship enrichment.** Rejected earlier and still rejected: it regresses the shipped `is_ship_contract=false` view, which carries item data today.

## Open questions

- **Churn rate is unmeasured.** The entire steady-state argument rests on new-contracts-per-cycle being small relative to 46,000. Plausible, unverified, and it should be measured before committing.
- **Token-bucket parameters** for public contract routes are not established here — the governor's shape is right regardless, but its tuning needs the real numbers.
- **Backfill duration** for a cold start (or a newly added region) under a correct governor is unknown, and it sets how long coverage expansion takes to become useful.
