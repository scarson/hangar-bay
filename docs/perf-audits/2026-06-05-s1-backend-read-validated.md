# S1 — Backend Read Pipeline · Cross-Validated Findings (cycle Phase 3)

**Source:** `2026-06-05T01-54-s1-backend-read-consolidated.md` + the 6 raw lane reports.
**Validation method:** every finding re-checked against the actual source by the runner (the runner
read all S1 files directly during scoping); hot-path reachability re-confirmed under the realistic
load; checked against `performance-spec.md`; blast radius assessed. Verification mode = static-only
(dynamic deferred — no running PG/Valkey/dataset; no fabricated numbers).

**Completeness:** 14 unique findings (P1–P14) + 8 suspected bugs surfaced across the 6 lanes. Every
one is dispositioned below as **Confirmed / Design decision / False positive / Out-of-scope**. Count:
12 confirmed (2 of which, P13/P14, are confirmed-but-subsumed), 3 flagged for a user design call,
1 false-positive class recorded, 8 suspected bugs handed off.

## Confirmed (default disposition: FIX — scheduled in the plan)

| ID | Title (self-contained) | Impact | On cost map | Effort | Blast radius |
|----|------------------------|--------|-------------|--------|--------------|
| P1 | Read endpoint never uses the cache — recomputes count+data+serialize every request | CRITICAL | yes | Contained | Adds a cache layer + invalidation on aggregation; touches read path only; correctness risk = stale reads (bounded by TTL) |
| P2 | Leading-wildcard `ILIKE '%term%'` search is non-sargable | CRITICAL | yes | Contained | New `pg_trgm` GIN indexes (migration); dialect-split (no trigram on SQLite dev) — guard behavior |
| P4 | `COUNT(*)` over `SELECT DISTINCT contract_id` over the fan-out SELECT | MAJOR | yes | Contained | Query rewrite; **must keep count value identical** — pin with tests; couples to P5 |
| P5 | Item filters via outer join + Python `.unique()` where `EXISTS` semi-join fits | MAJOR | yes | Contained | Query-shape change; fixes SB1 too; verify result-set + count equality on multi-item fixtures |
| P3 | Location filter columns (region/system/station) unindexed | MAJOR | yes | Localized | Add indexes (migration); pure win |
| P6 | No composite (filter+sort) index; all single-column | MAJOR | yes | Localized | Add composite index (migration); choose columns vs real query mix |
| P7 | Async engine has no pool config — ~15-conn ceiling | MAJOR | yes | Localized | Engine config; **needs deploy context** for exact sizing (also a design decision) |
| P8 | Sync structlog render + stdout write on the event loop | MAJOR | yes | Contained | Logging infra change (QueueHandler/Listener); app-wide, affects all routes — verify log output unchanged |
| P9 | Double Pydantic validation of the list response | MAJOR | yes | Localized | Response construction change; verify response JSON byte-identical |
| P10 | `COMMIT` on every read request | MINOR | (low) | Localized | Touch `get_db`; ensure write paths still commit |
| P11 | `Numeric`→Decimal marshaling on price/collateral | MINOR | no | Contained | Type choice has **money-correctness** implications — see Design Decisions |
| P12 | Legacy `sqlalchemy.future` select shim | MINOR | no | Localized | Import swap; zero behavior change |
| P13 | Per-row `model_validate` vs v2 list fast path | MINOR | no | Localized | **Subsumed by P9** — do not implement separately |
| P14 | Filter-only join transports item cols `selectinload` re-fetches | MINOR | yes | — | **Subsumed by P5** — same refactor |

**Disposition discipline:** none of P1–P14 is deferred. P11 (Numeric) and the cache TTL choice are
routed to the user as *design decisions*, not severity-deferred — they are scheduled pending that
input. P13/P14 are confirmed real but explicitly folded into P9/P5 (grouping ≠ dropping).

## Design decisions needing user input (recommendations attached)
1. **Cache staleness window (P1).** Data refreshes every 900 s. *Recommendation:* cache the hot,
   filter-light queries (especially the default landing page) with a TTL ≤ the aggregation interval,
   and/or bump a cache-version key at the end of each successful aggregation run for event-style
   invalidation. Low staleness risk; very high hit-ratio on the shared default query.
2. **Connection-pool sizing (P7).** Needs `Postgres max_connections` ÷ (workers × any other
   consumers, incl. the aggregation job's own engine). *Recommendation:* set explicit
   `pool_size`/`max_overflow` once that budget is known; until then, raising `pool_size` to ~10–20
   per worker is a safe interim if Postgres allows.
3. **`Numeric` vs `float` for price/collateral (P11).** *Recommendation:* **keep `Numeric`** — ISK
   amounts are money and float rounding is a correctness hazard; the marshaling cost is minor and the
   right tradeoff. Documented here so it is a *decision*, not an un-owned finding.

## False positives / correctly rejected (no action)
- **Parallelizing the count and data queries with `asyncio.gather`** — REJECTED by the `concurrency`
  lane itself: the count gates the `total==0` early-return (data dependency) and both share one
  `AsyncSession` (asyncpg sessions are not concurrency-safe). Would be a correctness regression.
  Recorded so a future run doesn't "rediscover" it as a missed optimization.
- **`selectinload(items)` as N+1** — not a finding; intended single-extra-query eager load.

## Out-of-scope / pre-existing (documented, not fixed here)
- `item_processing_status` index serves the **ingestion** path (S2), not reads — its write-tax on
  reads is noted but owned by S2.
- The Suspected Bugs (SB1–SB8) are **out-of-scope for a performance audit by definition** (audit
  records bugs, never chases them). SB1 and SB8 are *co-located* with perf findings P5/P4 and the
  ship_name sort — the eventual P4/P5 remediation task will touch that exact code, so SB1/SB8 should
  be resolved alongside it, but they are handed to `bug-hunt-cycle`, not fixed in the perf plan. See
  the bug-hunt kickoff. SB3 (unconditional `drop_all`/`create_all` on startup) is the highest-severity
  correctness/operational issue found and is flagged prominently for the operator.

## Blast-radius summary
The two highest-impact fixes (P1 cache, P4+P5 query rewrite) are **read-path-local** and independently
shippable. P2/P3/P6 are additive index migrations (low risk). P8 (logging) is the only app-wide
change and needs a log-output regression guard. Nothing here changes a public API signature, so no
frontend contract is affected — *except* that fixing SB4 (the `start_location_id` nullability
mismatch) would change response behavior for courier contracts and should be coordinated with the
frontend `contract.model.ts` consumers.
