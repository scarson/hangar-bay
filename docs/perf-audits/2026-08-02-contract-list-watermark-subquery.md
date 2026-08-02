<!-- ABOUTME: Root-cause investigation of the 6-second unfiltered contract list in production, -->
<!-- ABOUTME: the five candidate rewrites measured against the live database, and the design chosen. -->

# The unfiltered contract list takes 6 seconds (2026-08-02)

**Status:** root cause confirmed against production; design chosen; awaiting review.

**Symptom that surfaced it:** the post-deploy live smoke against production failed on
`e2e/live-smoke.spec.ts:71` — "pagination crosses a real page boundary when the dataset has
one" — in Deploy run
[30735956450](https://github.com/scarson/hangar-bay/actions/runs/30735956450). The
assertion that timed out is `announcedTotal()`, which waits 5 s for the polite live region
to publish "N contracts match". The region only fills once the list query resolves, so the
failure is a latency failure wearing an assertion's clothes.

## 1. What is actually slow

The `/contracts/` list endpoint issues two queries per request: an exact `total` count over
every matching row, and a page fetch of 50 rows. Measured on the production database
(`dpg-d9fj14btqb8s73d71r10-a`, plan `basic_256mb`, PostgreSQL 18) with `EXPLAIN (ANALYZE)`:

| Query | Unfiltered ("All Contracts") | Ships-only (the default view) |
|---|---|---|
| COUNT | **6,022 ms** | 8.4 ms |
| PAGE | 0.5 ms | 60.6 ms |

The count is the entire problem, and only on the unfiltered path. Within that count plan,
the cost is one node:

```
SubPlan 2 -> ... Index Only Scan Backward using ix_contracts_region_last_seen
             (actual time=0.075..0.075 rows=1 loops=61874)
             Index Searches: 61874
```

61,874 executions × 0.081 ms ≈ **5.0 s of the 6.0 s**. That subplan is the per-region
watermark in `still_listed_by_esi()` — `last_seen_at >= (SELECT max(last_seen_at) FROM
contracts WHERE region = outer.region)` — which PostgreSQL evaluates once per candidate
row because it is correlated.

Production currently ingests exactly one region (`AGGREGATION_REGION_IDS` defaults to
`[10000002]`, The Forge), so those 61,874 executions all recompute **the same single
value**.

### Why the ships-only path is fine

`is_ship_contract = true` selects 426 of 34,116 live contracts through
`ix_contracts_is_ship_contract`, so only ~424 rows ever reach the subplan. The cost of the
predicate is proportional to the number of rows that reach it, not to the corpus.

## 2. What it is not

Three plausible explanations were tested and eliminated, each with direct evidence:

- **Not the network, the proxy, or serialization.** The `duration_ms` that
  `contract_search_executed` logs is measured inside `get_contracts()`, and it tracks the
  wall-clock TTFB (6,469 ms logged against a 6.5 s curl). `size=1` is as slow as `size=50`.
- **Not table bloat.** `pg_stat_user_tables` reports `n_dead_tup = 0` for both `contracts`
  and `contract_items`, a 34 MB heap, and an autovacuum at 06:30:25Z. The count plan shows
  227,590 shared **hits** and zero reads — the working set is entirely in cache. This was
  the leading hypothesis (ingestion restamps `last_seen_at` on every row every few minutes,
  which looks like a bloat generator) and it is wrong.
- **Not scan cost.** Two queries filtering the *unindexed* `start_location_id` force the
  same scan but differ in how many rows survive to the watermark predicate:
  `station_ids=1` (matches nothing) returns in **0.6 s**; `station_ids=60003760` (Jita 4-4,
  30,867 rows) takes **6.1 s**. Same scan, 10× the time, and the only variable is how many
  rows reach the subplan.

## 3. It is a regression, and it crossed the test's threshold today

`still_listed_by_esi()` arrived in `4b9957f` ("fix(api): stop watchlist alerts outliving a
contract's purchase"), which was **not** in the previous production release (`7a95118`) and
shipped in today's. Server-side `duration_ms` for the same unfiltered query, from the
production logs:

| When | Release | Unfiltered count |
|---|---|---|
| 2026-07-27 08:26 | `7a95118` (no watermark predicate) | 4,235 ms / 3,096 ms |
| 2026-08-02 06:07 | `fe43bda` (watermark predicate) | 3,182 ms / 3,045 ms |
| 2026-08-02 06:35+ | `0edea19` (code-identical to `fe43bda`) | 5,338–10,007 ms |

Two things are true at once and both matter:

1. **The unfiltered path was already slow before this release** — 3–4 s — so the watermark
   predicate did not create the problem, it enlarged one that was already one bad day away
   from the 5 s assertion budget.
2. **The corpus grew.** 76,599 rows now, of which 34,116 are live. The predicate's cost is
   linear in rows examined, so this gets worse on its own schedule regardless of releases.

The smoke test passed on 2026-07-27 at 8.4 s of test time and on 2026-08-02 06:07 at 7.2 s.
It is not a flake that started failing; it is a threshold that was always going to be
crossed. Raising the timeout would hide the next crossing rather than the current one.

## 4. Candidates measured against production

Every candidate below was run against the live database with `EXPLAIN (ANALYZE)` and
checked for set equality against the current predicate. **All candidates that returned
selected identically** (34,109–34,111 contracts, varying only because ingestion ran between
measurements).

| Candidate | Unfiltered COUNT | Unfiltered PAGE | Ships COUNT | Ships PAGE |
|---|---|---|---|---|
| **Current** — correlated `max()` per row | 6,022 ms | 0.5 ms | 8.4 ms | 60.6 ms |
| Uncorrelated `(region, last_seen) IN (SELECT region, max(...) GROUP BY region)` | 1,304 ms | 264 ms | 371 ms | 169 ms |
| …same, without the `DISTINCT` wrapper | 663 ms | 264 ms | — | — |
| `LEFT JOIN` to a grouped watermark derived table | 1,259 ms | — | — | — |
| `NOT EXISTS` anti-join ("no newer stamp in my region") | **>5 min** | — | — | — |
| CTE: per-region `max()` driven by `SELECT DISTINCT region` | 1,132 ms | 367 ms | 499 ms | 372 ms |

Two results decide the design.

**Every "compute the watermark once" rewrite regresses the default view.** The ships-only
path goes from 69 ms total to 539 ms (tuple-`IN`) or 871 ms (CTE). The reason is structural:
computing the watermark set costs ~500–600 ms *unconditionally*, because PostgreSQL has to
scan 76,599 index entries to discover which regions exist — `SELECT DISTINCT
start_location_region_id` alone measures **602 ms**, and PostgreSQL 18's btree skip scan
does not kick in here. The correlated form pays per surviving row and so is *cheaper*
whenever the query is selective. Neither shape wins everywhere, and the default view — the
one every real user loads — is the selective one. Trading a 7.8× regression on the default
path for a 6.5× win on a secondary path is a bad trade taken blind.

**A per-region `max()` against a *known* region id is essentially free: 0.073 ms.**

```
SELECT max(last_seen_at) FROM contracts WHERE start_location_region_id = 10000002;
-- Execution Time: 0.073 ms  (index probe on ix_contracts_region_last_seen)
```

So the whole problem reduces to one question: **how do we learn the region ids without
scanning the contracts table?** Everything expensive above is expensive only because it
answers that question by scanning.

The `NOT EXISTS` anti-join deserves its own note: it reads as the most natural rewrite
("no contract in my region carries a newer stamp"), it is semantically identical, and it is
catastrophic — the inequality join defeats hashing and the planner produced something that
had not finished after five minutes. It is recorded here so nobody re-proposes it.

## 5. The design: a maintained per-region watermark

Ingestion already knows the answer. `_build_contract_rows` stamps **one `seen_at` for the
whole run** (its docstring says so explicitly: "a contract is judged present by matching the
newest stamp in its region, which only works if one run writes one value"), and
`_fetch_regions` already tracks which regions succeeded. The read path is recomputing, at
1,000× the cost, a value the write path had in hand.

**Add a `contract_region_watermarks` table** — one row per region, `region_id` primary key,
`last_seen_at` — upserted by the aggregation run inside the same transaction as the contract
upsert, for each region it successfully fetched.

`still_listed_by_esi()` keeps its exact shape and stays a single boolean expression usable
from both call sites (the contract service and the watchlist matcher). Only the source of
the watermark changes: a correlated lookup against a table of ≤5 rows resolved by primary
key, instead of an aggregate over 76,599 rows.

Why this and not the alternatives:

- **vs. any query-time derivation** — it is the only option that is fast on *both* the
  selective and the broad path, because it removes the scan rather than relocating it.
- **vs. reading `AGGREGATION_REGION_IDS` from settings** — that also gives a cheap region
  list, but it couples the read path to a config value that can drift from the data. A
  region dropped from the config leaves its contracts in the table with no watermark; a
  maintained table simply keeps the last one it wrote.
- **vs. caching the watermark in Valkey** — no schema change, but it puts a TTL between the
  data and a *visibility* predicate. Contracts already sold would keep being offered for the
  length of the TTL, and the cache becomes a correctness dependency for a path that has none
  today.
- **vs. upsizing the database** — `basic_256mb` is genuinely small and this would get
  cheaper on a bigger plan, but 61,874 redundant evaluations of a constant is a defect at
  any instance size, and the corpus grows.

### Failure behaviour, chosen deliberately

- **No watermark row for a region ⇒ its contracts are visible.** The predicate must treat a
  missing watermark as "show it", matching the existing rule that a NULL `last_seen_at` is
  visible. The opposite default would blank the site in the window between deploying the
  migration and the first ingestion run.
- **The watermark write shares the contract upsert's transaction**, so the table can never
  be ahead of the rows it describes. A watermark ahead of its contracts would hide every
  contract in the region at once; a watermark behind them merely keeps sold contracts
  visible a little longer, which is the failure this codebase already prefers (see
  `still_listed_by_esi`'s docstring on missed alerts vs. dead listings).
- **The migration backfills** from `SELECT region, max(last_seen_at) ... GROUP BY region` so
  there is no window with an empty table. That backfill costs ~600 ms, once.

### What this does not fix

Even with the predicate free, the unfiltered count still scans and de-duplicates ~34,000
rows, which measured **663 ms** in the closest equivalent shape. That is acceptable and
under the assertion budget, but it is not fast, and it is the number that will grow with the
corpus. Two follow-ups are worth their own decisions, neither taken here:

1. **The `DISTINCT` wrapper in `_count_distinct_contracts` is a no-op on the no-join path**
   and measurably expensive (1,304 ms → 663 ms in the tuple-`IN` shape; ~100 ms in the
   current shape). `contract_id` is the primary key, so without an item join no duplicates
   are possible. Removing it conditionally is safe but is a separate change with its own
   test obligations.
2. **F008 makes this the main path.** Type-aware browsing is precisely about making the
   ~98.8% of contracts that are not ships a designed surface, which turns today's secondary
   6-second path into the primary one. Whatever is decided about exact counts at corpus
   scale — cached totals, approximate counts above a threshold, or keyset pagination —
   belongs in the F008 plan rather than here.

## 6. Reproduction

The production measurements need the requesting IP on the database's allow list. A local
scale model that reproduces the *plan shape* (though not the absolute timings — a laptop is
~100× faster than `basic_256mb` here) is:

```bash
docker exec hangar_bay_postgres psql -U hangar_bay_user -d postgres -c "CREATE DATABASE hangar_bay_perf"
# seed 34k live + 17k expired contracts in 5 regions, then compare plans
```

The trap worth recording: seeding the corpus with two separate `INSERT` statements gives the
two batches **different `now()` values**, because `now()` is transaction time. Every live row
then fails the watermark predicate, all the plans short-circuit to zero rows, and the
measurements are meaningless while looking plausible. Normalize `last_seen_at` to a single
literal after seeding.

## 7. Evidence index

- Failing CI run: Deploy [30735956450](https://github.com/scarson/hangar-bay/actions/runs/30735956450), job `smoke`.
- Passing prior run on the code-identical predecessor: Deploy [30735261942](https://github.com/scarson/hangar-bay/actions/runs/30735261942) (pagination test 7.2 s).
- Predicate introduced in `4b9957f`; first reached production in the `0.2.0` release.
- Production plans, equivalence checks, and per-candidate timings: §1 and §4 above, all from
  `EXPLAIN (ANALYZE)` against `dpg-d9fj14btqb8s73d71r10-a` on 2026-08-02.
