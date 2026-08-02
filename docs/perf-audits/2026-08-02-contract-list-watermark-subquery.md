<!-- ABOUTME: Root-cause investigation of the 6-second unfiltered contract list in production, -->
<!-- ABOUTME: the five candidate rewrites measured against the live database, and the design chosen. -->

# The unfiltered contract list takes 6 seconds (2026-08-02)

**Status:** root cause confirmed against production; **first design proposed here was rejected
by review and replaced** (§5); replacement implemented and measured. See §8 for what the
reviews changed, and §9 for what remains open.

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

61,874 executions × 0.075 ms ≈ **4.6 s of the 6.0 s**. That subplan is the per-region
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
  which looks like a bloat generator) and the evidence does not support it. Stated
  precisely, since review pushed back on the original wording: `n_dead_tup` is an estimate
  of *currently* dead tuples and buffer hits prove residency rather than compactness, so
  this rules bloat out as the *dominant* cost — which the third bullet establishes
  independently — rather than proving the heap is perfectly compact.
- **Not scan cost.** Two queries filtering the *unindexed* `start_location_id` force the
  same scan but differ in how many rows survive to the watermark predicate:
  `station_ids=1` (matches nothing) returns in **0.6 s**; `station_ids=60003760` (Jita 4-4,
  30,867 rows) takes **6.1 s**. Same scan, 10× the time, and the only variable is how many
  rows reach the subplan.

## 3. It got worse over time and crossed the test's threshold today

`still_listed_by_esi()` arrived in `4b9957f` ("fix(api): stop watchlist alerts outliving a
contract's purchase"), which was **not** in the previous production release (`7a95118`) and
shipped in today's. Server-side `duration_ms` for the same unfiltered query, from the
production logs:

| When | Release | Unfiltered count |
|---|---|---|
| 2026-07-27 08:26 | `7a95118` (no watermark predicate) | 4,235 ms / 3,096 ms |
| 2026-08-02 06:07 | `fe43bda` (watermark predicate) | 3,182 ms / 3,045 ms |
| 2026-08-02 06:35+ | `0edea19` (code-identical to `fe43bda`) | 5,338–10,007 ms |

**Do not read that table as proof the release caused it.** Review was right to flag the
original wording here. The predicate-bearing code logged 3.0–3.2 s at 06:07 and the
*code-identical* commit logged 5.3–10.0 s half an hour later, so something other than the
predicate moved between those rows — corpus growth and a 06:30:25Z autovacuum/analyze are
both candidates, and no controlled with/without comparison on one snapshot was ever run. The
honest claims are narrower:

1. **The unfiltered path was already slow before this release** — 3–4 s — so the watermark
   predicate did not create the problem.
2. **The predicate is nonetheless the dominant cost now**, which §1 and §2 establish
   directly from the plan rather than from the history.
3. **The cost is linear in rows examined**, and the corpus is at 76,599 rows / 34,116 live,
   so it worsens on its own schedule regardless of releases.

The smoke test passed on 2026-07-27 at 8.4 s of test time and on 2026-08-02 06:07 at 7.2 s.
It is not a flake that started failing; it is a threshold that was always going to be
crossed. Raising the timeout would hide the next crossing rather than the current one.

## 4. Candidates measured against production

Every candidate below was run against the live database with `EXPLAIN (ANALYZE)` and
checked for set equality against the current predicate. All of them selected identically
(34,101–34,111 contracts, varying between runs only because ingestion kept committing).

**Those equality checks are weaker evidence than they look**, and review said so: they are
two counts taken seconds apart on a moving dataset, not a set comparison. Only the chosen
design (§5) is backed by a both-way `EXCEPT` inside a single snapshot. Treat this table as
a *performance* comparison; the correctness argument lives in §5.

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
scanning the contracts table?** Every *candidate rewrite* above is expensive only because it
answers that question by scanning. (Note the precise claim: the **current** query is slow
because it repeats a cheap one-row probe 61,874 times, not because anything scans to
discover regions. Those are two different costs and an earlier draft of this document
conflated them.)

The `NOT EXISTS` anti-join deserves its own note: it reads as the most natural rewrite
("no contract in my region carries a newer stamp"), it is semantically identical, and it is
catastrophic — the inequality join defeats hashing and the planner produced something that
had not finished after five minutes. It is recorded here so nobody re-proposes it.

## 5. The design: configured regions as an optimization hint

**This replaces an earlier proposal in this document — a maintained `contract_region_watermarks`
table written by ingestion — which two independent reviews rejected and a measurement
confirmed was also slower. §8 records why, because the reasons generalize.**

The shipped change keeps `still_listed_by_esi()` a standalone boolean expression and changes
nothing about what it means. It only changes *how PostgreSQL is asked to compute it*:

```python
case(
    (Contract.start_location_region_id.in_(ingested_region_ids),
     # fast path: one UNCORRELATED subquery per configured region, hoisted to an
     # InitPlan and evaluated once for the whole query
     or_(*[and_(Contract.start_location_region_id == r,
                Contract.last_seen_at >= _newest_in(r)) for r in ingested_region_ids])),
    # fallback: exactly today's correlated predicate, for any other region
    else_=Contract.last_seen_at >= newest_in_region,
)
```

`AGGREGATION_REGION_IDS` is an **optimization hint, never a semantic input.** The `case`
guarantees that a row whose region is not configured is judged by precisely the predicate
that judges it today. Configuration drift changes which rows take the fast path; it cannot
change which rows are visible.

That property is the whole point, and it is what makes this safe to ship without a
behaviour decision. It was verified against the production corpus, not argued:

```
-- both-way EXCEPT, single snapshot, correct config
current_rows | new_rows | lost | gained
      34,100 |   34,100 |    0 |      0

-- same, with a DELIBERATELY WRONG config (the real region omitted)
drift_hidden | drift_shown
           0 |           0
```

### Measured on production

| Path | Before | After |
|---|---|---|
| Unfiltered COUNT | 6,022 ms | **1,565 ms** |
| Unfiltered PAGE | 0.5 ms | **0.155 ms** |
| Ships-only COUNT | 8.4 ms | 64 ms |
| Ships-only PAGE | 60.6 ms | ~63 ms |

The unfiltered list — the path that failed the smoke test and the path F008 turns into the
main one — goes from ~6.0 s to ~1.6 s, roughly a quarter of the 5 s assertion budget. The
page query keeps its early exit, which every "compute once" candidate in §4 destroyed
(0.5 ms → 264–372 ms). The default ships-only view moves by tens of milliseconds inside a
request that is ~400 ms end to end; the numbers on this instance vary by more than that
between runs.

### Why not the alternatives

- **vs. the rejected watermark table** — measured *slower* (1,270 ms vs 1,565 ms is within
  noise, but the table's correlated PK lookup still re-executes ~61,874 times, which is the
  very mechanism being fixed), and it costs a migration, an ingestion write, a second source
  of truth, and the failure modes in §8.
- **vs. using the uncorrelated form only for the broad count** (codex's first suggestion) —
  it works, but it makes the liveness rule two expressions that must be kept in agreement.
  The hint-with-fallback shape gets the same win with one expression.
- **vs. "unconfigured region ⇒ visible"** — a simpler predicate, measured at 861 ms, but it
  makes configuration a *semantic* input: dropping a region from the config would change
  visibility. Rejected for that reason alone, despite being the faster option.
- **vs. upsizing the database** — `basic_256mb` is genuinely small and everything here would
  get cheaper on a bigger plan. Still worth considering (§9), but 61,874 redundant
  evaluations of a constant is a defect at any instance size.

### What this does not fix

The unfiltered count still scans and de-duplicates ~34,000 rows. Two follow-ups, neither
taken here:

1. **The `DISTINCT` wrapper in `_count_distinct_contracts` is a no-op on the no-join path.**
   `contract_id` is the primary key, so without an item join no duplicates are possible.
   Both reviews independently said to do it, and one argued for doing it in this change.
   It is deferred only to keep this diff to a single mechanism; it needs its own test that
   the joined path still de-duplicates (SQLA-1).
2. **`_count_unknown_system_excluded` applies the same predicate a third time.** When
   `system_ids` is set, the endpoint pays the count twice — once for the user's filter and
   once for a residual over an *unindexed* column — and it runs before the `total == 0`
   short-circuit. Neither review's author nor this document's original draft spotted this;
   it means "All Contracts + a system filter" was roughly double the headline 6 s. The fast
   path helps it equally, but it deserves its own look.

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

## 8. What the reviews changed

The design in §5 is the second one. The first — a `contract_region_watermarks` table
(`region_id` PK, `last_seen_at`) upserted by ingestion in the contract-upsert transaction and
read through a correlated primary-key lookup — was reviewed independently by an Opus agent
and by codex, and both rejected it. Recorded because the failure modes generalize to any
"denormalize a derived value into a side table" proposal in this codebase.

**Two ways it would have taken the site down.**

1. **"Write a watermark for each region successfully fetched" is not the same set as
   "regions whose contracts were restamped."** `get_public_contracts` returns an empty list
   *without raising* for a 404, a 204, and — the reachable one — a 304 whose cached body has
   been evicted from Valkey. That cache is `allkeys-lru` by design (DEPLOY-3), so eviction is
   expected. `_fetch_regions` counts all of those as `regions_ok`. Advancing a watermark for
   a region where nothing was restamped hides **every contract in that region**; with a
   single configured region, that is the whole site, silently.
2. **"The predicate keeps its exact shape" contradicts "a missing watermark row means
   visible."** A correlated scalar subquery over a table with no matching row returns SQL
   NULL, and `last_seen_at >= NULL` is NULL, which `WHERE` rejects. Missing watermark would
   have meant *hidden* — the exact inverse of the stated intent, and reachable on every dev
   boot, since the dev startup path drops and recreates all tables (ENV-2/ENV-3).

**A claim in the first draft was simply false.** It asserted `_fetch_regions` "already tracks
which regions succeeded"; it returns `tuple[List[dict], int, int]` — a flattened contract
list and two counters. Both reviewers caught it independently. The lesson is the one already
in this repo's memory: open the function before writing "X already does Y" into a durable
artifact.

**And the proposal was never measured.** Both reviews noted the projected win was
extrapolated from a *different* plan shape. Measuring it (`C5` in the working notes) put the
correlated PK lookup at **1,270 ms** — no better than the far simpler §5 change, because it
still re-executes ~61,874 times. The mechanism being fixed is the repetition, not the cost of
each probe, and a smaller table does not remove repetition.

**The chosen design came out of the reviews, not the original analysis.** Both independently
proposed some form of "use the configured regions without letting configuration decide
visibility"; codex's phrasing — configured region ids as an optimization hint with the
existing predicate as the `ELSE` fallback — is what shipped. The original document had
dismissed the config-based option in a single line about coupling; that dismissal was wrong,
because the coupling it feared is exactly what the `case` fallback removes.

**Other findings applied to this document:** the equality checks in §4 were counts on a
moving dataset rather than set comparisons (§4 now says so, and §5 carries a real `EXCEPT`);
the release-regression claim was overstated (§3 rewritten); the `n_dead_tup` argument proved
less than claimed (§2 narrowed); the arithmetic used 0.081 ms where the plan says 0.075 ms
(§1 corrected); and `_count_unknown_system_excluded` is a third application of the predicate
that nothing in the original draft mentioned (§5, "What this does not fix").

## 9. Open items

- **Remove the temporary IP allow rule** on `hangar-bay-db` — `198.37.143.189/32`,
  described "temp troubleshooting 2026-08-02 - REMOVE". It was added with explicit
  authorization to run the production `EXPLAIN`s above, and the Render API key stopped
  authenticating before it could be reverted. The allow list was empty before.
- **Drop the `DISTINCT` wrapper on the no-join count path** (§5). Safe, measured, and both
  reviews asked for it.
- **Look at `_count_unknown_system_excluded`** — a third execution of the predicate, over an
  unindexed column, ahead of the `total == 0` short-circuit.
- **Decide whether `basic_256mb` is the right plan.** A per-execution cost of 0.075 ms for a
  fully-cached three-level index probe is CPU starvation, not a query defect. Everything here
  is ~100× slower than the same shapes on a laptop.
- **Exact counts at corpus scale belong to the F008 plan.** F008 makes the unfiltered list
  the primary surface, so cached totals, approximate counts above a threshold, or keyset
  pagination should be decided there rather than bolted on here.
