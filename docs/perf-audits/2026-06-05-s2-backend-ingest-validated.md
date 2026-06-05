# S2 — Backend ESI Ingestion · Cross-Validated Findings (cycle Phase 3)

**Source:** `2026-06-05T01-58-s2-backend-ingest-consolidated.md` + 6 raw lane reports.
**Validation:** every finding re-checked against source by the runner (read directly during scoping);
hot-path reachability re-confirmed under the realistic load (scheduled every 900 s, M item-bearing
contracts dominating); checked against `performance-spec.md`. Static-only (no fabricated numbers).

**Completeness:** 17 unique findings (SP1–SP17) + 7 suspected bugs. All dispositioned below.

## Confirmed (default: FIX)

| ID | Title | Impact | Effort | Blast radius |
|----|-------|--------|--------|--------------|
| SP1 | Serial per-contract ESI item fetch (network N+1) | CRITICAL | Contained | network fan-out; **couple with SP4 cap + keep DB upserts serial**; guard result multiset |
| SP2 | Whole-run in-memory accumulation of contracts + items | CRITICAL | Contained | streaming refactor; depends on SP8 generator |
| SP3 | ON CONFLICT rewrites every column → write amplification | CRITICAL | Contained | narrow SET; verify unchanged-row updates 0 cols; co-located with SB-S2-2/3 |
| SP4 | httpx default pool limits (fan-out hazard + bottleneck) | MAJOR | Localized | **gates SP1/SP5/SP6** — set `Limits == semaphore cap` |
| SP5 | Per-region fetches sequential | MAJOR | Contained | bounded-concurrent under the global cap; keep error isolation |
| SP6 | ID-resolution chunks sequential | MAJOR | Localized | bounded gather |
| SP7 | Item upsert batch 50 vs 500 | MAJOR | Localized | raise batch; pure win |
| SP8 | ETag helper materializes all pages (root cause of SP2) | MAJOR | Cross-cutting | changes return contract at 3 call sites — verify aggregate data equal |
| SP9 | Per-call Redis client where pooled shared client fits | MAJOR | Contained | inject shared client; lock semantics unchanged |
| SP10 | `response.json()` + `response.content` both held | MINOR | Localized | folds into ETag refactor |
| SP11 | `contract_values` doubles contract peak | MINOR | Localized | per-batch transform (folds into SP2) |
| SP12 | Uncoalesced Redis round-trips in ETag path | MINOR | Localized | pipeline/MGET |
| SP13 | Fresh engine per run | MINOR | Localized | pin pool params **when** fan-out added |
| SP14 | Redundant `sorted(set(ids))` dead work | MINOR | Localized | drop sort |
| SP15 | Chained `set.union` + 4 passes over contracts | MINOR | Localized | one pass, `a|b|c|d` |
| SP16 | `.close()` vs `.aclose()` on redis.asyncio | MINOR (LOW conf) | Localized | currency — manual check (redis-py not in index) |
| SP17 | Hand-rolled retry vs httpx transport retries | MINOR (LOW conf) | Localized | partial — 5xx retry can't delegate; borderline |

**Disposition discipline:** nothing deferred on severity/effort grounds. SP16/SP17 are LOW-confidence
(ungrounded by the version index — no live currency brief for redis-py/httpx) and tagged for a manual
currency check rather than dropped. The MINORs (SP10–SP15) are grouped into the SP2/SP8 streaming
refactor and a single "cheap constant-factor cleanups" task — grouped, not dropped.

## Design decisions needing user input (recommendations attached)
1. **ESI concurrency cap `C` (SP1/SP4/SP5/SP6).** The right cap is set by ESI's error-rate budget,
   not by us. *Recommendation:* a conservative, **settings-driven** cap (start ~10–20 concurrent ESI
   requests) with the httpx `Limits(max_connections=C)` pinned to the same value; tune against ESI's
   `X-ESI-Error-Limit-*` headers. Never an unbounded `gather`.
2. **Streaming refactor scope (SP2/SP8).** Converting the ETag helper to an async generator is
   Cross-cutting (3 call sites). *Recommendation:* do it — it unlocks both the memory fix and
   incremental upserts — but as its own task with the result-equality guard, sequenced before the
   per-batch flush changes.
3. **ON CONFLICT semantics (SP3).** *Recommendation:* narrow the SET to genuinely-mutable columns and
   stop clobbering `item_processing_status`; coordinate with the ingestion state machine (this also
   resolves SB-S2-2/3). Needs a quick confirm of which columns are "ingestion-owned" vs "derived."

## False positives / correctly rejected (no action)
- **Fan-out of ESI pagination within one call** — declined (page count known only after page 1).
- **Fresh-engine-per-run as a major cost** — correctly MINOR.
- **The upsert idiom itself (`insertmanyvalues`)** — not stale; only the batch *size* (SP7) is real.
- **`algorithmic` lane: no critical/major** — honest non-finding (anti-padding held).

## Out-of-scope / pre-existing
- All suspected bugs (SB-S2-1…7) are correctness, handed to `bug-hunt-cycle`. **SB-S2-1** (item pages
  >1 dropped) and **SB-S2-4** (`record_id` PK collision across contracts) are the highest-value and
  should be triaged first — both cause silent data loss/clobber independent of performance.
- The `contracts`/`contract_items` **schema + indexes** are audited in S1 (shared substrate); S2's
  write amplification (SP3) is calibrated against those 9 secondary indexes.

## Blast-radius summary
The throughput cluster (SP1+SP4+SP5+SP6) is **one coordinated change** — a global semaphore + matching
httpx limits, DB upserts left serial — shippable behind a settings flag. The memory cluster (SP2+SP8+
SP10/SP11) is a second coordinated change (the generator refactor). SP3 and SP7 are independent,
low-risk DB-write wins. None changes a public API; the ingestion is a background job, so no
user-facing latency contract is touched — but SP1's fix is what keeps a run from exceeding its 900 s
interval, which *is* the operational contract.
