# Performance Audit — Backend ESI Ingestion: Algorithmic Complexity & Data Structures

**Slice:** superpowers-plus/performance-audit — ESI ingestion / background aggregation path
**Dimension:** algorithmic complexity & data-structure choice (STATIC-ONLY)
**Date:** 2026-06-05
**Scope:** `services/background_aggregation.py`, `core/esi_client_class.py`, `services/db_upsert.py`, `services/scheduled_jobs.py`, `core/scheduler.py`, `core/http_client.py`

---

## Orientation (what the data structures actually do)

Per scheduled run (every 900 s), `_process_contracts` receives a flat `List[dict]` of
all contracts across all regions (thousands → tens of thousands). It then:

1. Builds four `set` comprehensions of unique IDs, unions them, filters them, and resolves
   them to names via a batched POST.
2. Builds one `id_to_name_map` dict (resolve), then a transform comprehension that does O(1)
   dict lookups per contract.
3. Slices contract rows into 500-row batches for upsert.
4. Per item-bearing contract, fetches items, accumulates into `all_items`, slices into
   50-row batches for upsert.

The **container choices for the ID-resolution path are correct**: sets for de-dup, a dict for
the name map, O(1) lookups in the transform. There is **no accidental quadratic** over the
growing contract/item collections in this slice — every pass over `contracts`/`all_items` is a
single linear traversal, and the batch-slicing loops are O(N) total. The structural cost in this
path is dominated by I/O fan-out (per-contract item fetches) and DB round-trips, which belong to
the concurrency and data-access lanes audited elsewhere.

The findings below are the genuine algorithmic/data-structure items, all MINOR — there is no
CRITICAL or MAJOR algorithmic-complexity defect in this slice.

---

### [MINOR impact] Redundant re-de-duplication and full sort of an already-unique ID set on every run

**Location:** `core/esi_client_class.py:199` (`resolve_ids_to_names`), reached from
`services/background_aggregation.py:211`

**Problem:** The caller has *already* produced a de-duplicated collection: lines 188–195 build
four sets and union them (`issuer_ids.union(corporation_ids).union(...)`), then line 200–202
filters that to a `list`. `resolve_ids_to_names` then immediately recomputes
`unique_ids = sorted(list(set(ids)))` (line 199) — re-building a set from an already-unique list
(O(M)) and, more notably, **sorting** the whole ID collection (O(M log M)) for no functional
reason. The chunking at line 202 only needs *some* partition of the IDs into ≤1000-element
groups; ordering is irrelevant to correctness because the ESI `/universe/names/` response is
keyed back by `item['id']` (line 208), not by position. The sort is pure recomputed work on the
hot path.

**Impact:** O(M log M) sort + O(M) re-set on every run, M = unique resolvable IDs (issuers +
corps + locations). Under realistic load M is in the thousands–tens-of-thousands range, so this
is a real-but-modest per-run cost, not a scaling cliff. The de-dup is also doubled work: it is
computed once by the caller's set union and again here.

**Confidence:** Strong-static — the sort output is consumed only by positional slicing into
chunks; no downstream code depends on ID order.

**Effort:** Localized — replace `sorted(list(set(ids)))` with `list(set(ids))` (or, if the caller
guarantees uniqueness, iterate `ids` directly). The set is still useful as a defensive de-dup if
`resolve_ids_to_names` may be called from paths that do not pre-dedupe; the *sort* is the part to
drop.

**Verification plan:** Complexity argument — chunking + dict-keyed response assembly are
order-independent, so removing the sort changes O(M log M) → O(M) with identical output set.
Correctness guard: a test passing IDs in shuffled order and asserting the returned
`{id: name}` map is identical with and without the sort.

---

### [MINOR impact] Chained `set.union(...)` allocates three throwaway intermediate sets

**Location:** `services/background_aggregation.py:193–195`

**Problem:** `issuer_ids.union(corporation_ids).union(start_location_ids).union(end_location_ids)`
builds the combined set by creating a fresh intermediate set at each `.union()` call: the first
`.union` allocates a set holding issuers+corps, the second copies that *plus* start-locations
into another new set, the third copies *all of that again* plus end-locations. The final result
is correct and the total work is still linear in the number of IDs, but the constant factor is
~3× the necessary copying because each chained `union` re-materializes the accumulated set.
`set().union(a, b, c, d)` or `a | b | c | d` collapses this, and `set().union(*iterables)` or a
single comprehension over `itertools.chain` avoids the intermediates entirely.

**Impact:** O(total IDs) work with a ~3× constant-factor on set construction; allocation churn
proportional to the union size. Cold-ish (once per run) and linear, so MINOR — flagged because
it is a clear data-structure-construction inefficiency in the named ID-union path, not because it
threatens scaling.

**Confidence:** Strong-static.

**Effort:** Localized — single-line change to `issuer_ids | corporation_ids | start_location_ids
| end_location_ids` (or build one set directly from a `chain` of the source comprehensions).

**Verification plan:** Complexity argument — the multi-arg union / `|` produces one result set in
a single pass versus three cascading copies; assert resulting set equality against the current
chained expression on a fixed contract fixture.

---

### [MINOR impact] ID sets are built by four independent full passes over the contracts list

**Location:** `services/background_aggregation.py:188–191`

**Problem:** Lines 188–191 iterate the full `contracts` list **four separate times** — one
comprehension each for `issuer_ids`, `corporation_ids`, `start_location_ids`, and
`end_location_ids`. Each pass re-incurs Python-level iteration and per-element dict
`__getitem__`/`.get()` over the same N dicts. A single pass that appends into four sets (or one
loop populating all four) does the same work in 1×N iterations instead of 4×N. CPython's
per-iteration bytecode + dict-access cost is the sharpest edge in the cost model (Runtime notes),
so collapsing four passes into one is a real constant-factor win on a list of thousands–tens-of-
thousands of dicts.

**Impact:** 4×N Python-level dict accesses → N; constant-factor (~4×) reduction on the
ID-collection phase. Linear, once per run — MINOR.

**Confidence:** Strong-static.

**Effort:** Localized — replace the four comprehensions with one `for c in contracts:` loop
that updates the four sets (with the same `start_location_id`/`end_location_id` truthiness
guards preserved).

**Verification plan:** Complexity argument — one traversal yields the identical four sets;
assert the four sets are equal to the current comprehensions' output on a fixed fixture
(including contracts with missing/`None` location IDs to preserve the filtering semantics).

---

## Notes on candidates explicitly *not* reported (calibration)

- **Per-contract sequential item fetch (`background_aggregation.py:256–281`)** — this is an
  O(item-bearing-contracts) chain of sequential `await` round-trips. That is a real and likely
  dominant cost, but it is a **concurrency / data-access** issue (sequential awaits that want
  `gather`/bounded fan-out; per-row remote fetch), not algorithmic complexity. Out of this lane.

- **Batch-slice loops (`:247` contracts, `:285` items)** — `range(0, n, batch)` + `lst[i:i+batch]`
  is O(N) total with O(N) extra slice allocation; correct container/algorithm for chunking.
  Not a finding (bounded, linear, idiomatic). `itertools.batched` would avoid the slice
  allocations but that is a micro-opt below threshold.

- **`id_to_name_map.get(...)` per contract (`:234–236`)** — dict, O(1) lookups, correct
  structure. No finding.

- **`bulk_upsert` `update_cols` dict comprehension (`db_upsert.py:33–34, 42–43`)** — iterates
  `stmt.excluded`, which is bounded by **column count**, not row count; rebuilt per batch but
  O(columns). Below threshold.

- **`all_contracts_data.extend(...)` per region (`:133`) and `full_data.extend(...)` per page
  (`esi_client_class.py:141, 152`)** — amortized O(1) appends building the working list; correct.
  This is unbounded in-memory accumulation (a *memory* lane concern), not an algorithmic-
  complexity defect. Out of lane.

---

## Suspected Bugs (for follow-up)

- **`ContractItem.record_id` upsert-on-conflict semantics (`models/contracts.py:89` vs
  `background_aggregation.py:266` + `db_upsert.py:28,36`).** `record_id` is declared
  `primary_key=True, autoincrement=True`, but the ingestion path supplies ESI's `record_id` as
  the value and `bulk_upsert` keys the `ON CONFLICT` on the primary key. ESI `record_id` is only
  unique *within a contract*, so the same `record_id` can recur across different contracts —
  meaning two different (`contract_id`, `record_id`) rows could collide on the PK and clobber each
  other, or the autoincrement assumption fights the supplied value. This is a correctness concern
  (data structure / key model), not a performance finding; flagging for follow-up.
