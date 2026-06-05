# Whole-Repo Performance Audit — Cross-Slice Roll-Up

**Date:** 2026-06-05 (UTC)   **Repo:** Hangar Bay (EVE Online public-contract marketplace)
**Method:** `performance-audit-cycle` → `whole-repo-scoping.md`, 3 reviewed slices, static-only.
**Inputs:** `runs.jsonl` (3 runs) + the S1/S2/S3 consolidated + validated reports.
**Why this exists:** the request was a **posture question** ("perf audit the whole repo"), so the
roll-up is REQUIRED. It synthesizes themes that are invisible in any single slice. Single-level
(one backend deployable + one SPA — not a service monorepo).

## Heat map (slice × tier × severity)

| Slice | Tier | Critical | Major | Minor | Suspected bugs |
|-------|------|:---:|:---:|:---:|:---:|
| S1 — backend read pipeline | FULL (HOT) | 2 | 7 | 5 | 8 |
| S2 — backend ESI ingestion | FULL (HOT) | 3 | 7 | 7 | 7 |
| S3 — frontend SPA | REDUCED (latent) | 0 | 1 | 9 | 8 |
| **Total** | | **5** | **15** | **21** | **23** |

The mass is in the **backend** (both hot paths); the frontend is honestly low-yield because it's
latent. No finding shipped top-ranked on an unverified assumption — the cross-slice frequency
calibration produced **no `frequency-unresolved — assume-hot` findings** (the read and write paths are
independent; the one shared substrate, the schema/indexes, was calibrated to the hotter read caller).
There is nothing here for the operator to "confirm reachability" on after the fact.

## Cross-slice themes (the point of the roll-up)

### Theme A — The one-to-many `contracts ↔ contract_items` is mishandled on BOTH sides
This is the repo's defining performance shape, and **no single slice sees the whole of it**:
- **Read (S1):** item-attribute filters/sort are done via `OUTER JOIN` → row fan-out → `DISTINCT`
  count (P4) + Python `.unique()` dedup (P5) + a LIMIT-before-dedup short-page bug (SB1).
- **Write (S2):** the same relationship drives the **serial per-contract item fetch N+1** (SP1, the
  #1 throughput issue) and the item upsert batching (SP7).
- **Shared substrate:** the `contracts`/`contract_items` schema carries 9 single-column indexes but
  misses the columns the read path filters/sorts on (P3 location, P6 composite, P2 trigram) — and the
  full-column `ON CONFLICT` write (SP3) churns all 9 every 900 s.
- **Systemic fix:** treat the one-to-many as one design problem — `EXISTS` semi-join on read, bounded
  fetch + wider batch + narrowed upsert on write, and an index set chosen for the *actual* read query
  mix. Done piecemeal per slice you'd miss that P4/P5/SP1/SP3 share a root.

### Theme B — Valkey/Redis is invested in but under-leveraged on the hottest path
- **Read (S1):** the hottest, most-shared query (the default contract listing) hits Postgres every
  request — **cache-aside is entirely absent** (P1) despite the spec mandating it and a Redis layer
  being wired.
- **Write (S2):** Redis *is* used (ETag cache, lock) but inefficiently — per-page uncoalesced
  round-trips (SP12) and a per-call client (SP9).
- **Systemic fix:** a deliberate caching strategy — cache-aside on read keyed by filter set + the
  background job bumping a cache-version on each successful run (the 900 s cadence makes staleness
  bounded and the hit-ratio high). This single change sits in front of the entire S1 query+serialize
  stack for the common case.

### Theme C — Serial I/O where bounded concurrency fits (and where it correctly doesn't)
- **S2** defaults to serial `await`s over independent work (regions SP5, items SP1, id chunks SP6) —
  the dominant ingestion cost. The fix is one **global semaphore + matching `httpx.Limits`** (SP4),
  DB upserts kept serial on the single session.
- **S1** correctly does **not** parallelize (count gates the early-return; one async session) — the
  `concurrency` lane rejected it. The theme isn't "parallelize everything"; it's "the ingestion path
  leaves free concurrency on the table, the read path doesn't."

### Theme D — Instrumented for request counts, blind to the costs the audit found
Prometheus + structured logs exist, but there is **no** per-query DB-time, cache hit/miss, or
ingestion run-duration / ESI-call-count metric — so **none of the top findings are measurable in
production today** (and the synchronous logging is itself S1 P8). Before/after proof for P1/P4/SP1
requires *adding* the metric first. Cross-slice measurability gap: close it (DB-time + cache-ratio +
run-duration counters) as a prerequisite to the remediation's verification gates.

### Theme E — Frontend↔backend API contract drift (cross-slice correctness blocking perf)
S3's two highest-value issues are **mismatches against the S1 backend contract**: the frontend reads
`total_items`/`total_pages` (backend returns `total`/`items`) and sends `sort_order` (backend expects
`sort_direction`). The frontend's findings are *latent precisely because* the feature is half-wired —
and wiring it requires aligning these contracts. This is a seam only the whole-repo view exposes:
fix the backend `ContractSchema` nullability (SB4) and the frontend request/response model **together**.

### Theme F — Pervasive half-built / duplicate scaffolding (hand off to health-review + bug-hunt)
Duplicate `Base`/`get_db_session_factory` and two `Settings` classes (S1), two contract services + two
model files + `.bak` files compiled (S3), import-time debug `print()`s (S1/S2), the unconditional
`drop_all`/`create_all` on startup (S1 SB3). Not performance per se, but a repo-wide signal that this
is early-stage scaffolding — `project-health-review` and the per-slice `bug-hunt` kickoffs should sweep it.

## Prioritized cross-slice fix list (repo-wide ranking)

Ordered by Impact × Confidence, low-effort-first within a band. IDs trace to slice reports.

1. **Bound the ESI fan-out** — concurrency-cap the per-contract item fetch + per-region + id-chunk
   fetches under one semaphore, with `httpx.Limits` = the cap, DB upserts serial. *(S2 SP1+SP4+SP5+SP6;
   keeps a run under its 900 s interval.)* **Top throughput win.**
2. **Cache-aside the read path** — cache the hot/default contract queries; invalidate on aggregation.
   *(S1 P1.)* **Top read-latency win.**
3. **Rewrite the one-to-many read query + add the right indexes** — `EXISTS` semi-join, `COUNT(DISTINCT)`,
   location + composite + `pg_trgm` indexes; fixes the short-page bug too. *(S1 P2+P3+P4+P5+P6, SB1.)*
4. **Narrow `ON CONFLICT` + raise item batch size** — stop rewriting all 9 indexed columns; batch items
   at 500. *(S2 SP3+SP7; resolves the status-clobber bugs.)*
5. **Stream the ingestion (generator refactor)** — cap peak memory to one batch. *(S2 SP2+SP8.)*
6. **Per-request overhead cluster** — off-loop logging, single Pydantic pass, explicit pool sizing,
   no commit-on-read. *(S1 P7+P8+P9+P10.)*
7. **Align + consolidate the frontend data layer** — one service/model, request/response contract
   matched to the backend. *(S3 FP1 + SB-S3-1/2; cross-slice with S1.)*
8. **Frontend build guard-rails (do now, cheap)** — budgets, lazy-loading convention, drop the unused
   `@angular/localize` polyfill. *(S3 FP7+FP8+FP9.)*
9. **Close the measurability gap** — DB-time + cache hit/miss + run-duration/ESI-call metrics (prereq
   for verifying 1–4). *(Theme D.)*
10. **The cheap constant-factor + currency cleanups** — drop dead `sorted(set())`, collapse set unions,
    `aclose()`, legacy `select` import, etc. *(S1 P12, S2 SP14/SP15/SP16/SP17.)*

## Correctness work (separate track — `bug-hunt-cycle`, NOT this audit)
23 suspected bugs were recorded across the slices (kickoffs written per slice). The ones that cause
**silent data loss/incorrectness** and should be triaged first, independent of performance:
unconditional `drop_all`/`create_all` on startup (S1 SB3); `get_contract_items` dropping item pages
>1 (S2 SB-S2-1); `record_id` PK collision across contracts (S2 SB-S2-4); the frontend reading the
wrong response fields + ignoring sort (S3 SB-S3-1/2). The perf remediation for P4/P5/SP3 will *touch*
the same code as SB1/SB-S2-2/3, so coordinate — but the audit records bugs, it does not fix them.

## Verdict (posture)
The architecture choices are sound (async FastAPI, SQLAlchemy 2.0, Valkey available, Angular 20
zoneless+signals). The performance gaps are **concentrated and fixable**, not architectural: two
hot paths each have a clear #1 (ESI fan-out serialization; missing read cache), both rooted in the
same one-to-many relationship being handled naïvely on read and write. The frontend is sound but
latent. There is real, well-calibrated, high-leverage performance work here — see the remediation plan
at `docs/plans/2026-06-05-whole-repo-perf-audit-remediation-plan.md`.
