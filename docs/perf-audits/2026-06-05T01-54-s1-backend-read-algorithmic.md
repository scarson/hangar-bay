# Performance Audit — Backend Read Pipeline — Dimension: Algorithmic Complexity & Data Structures

Scope: `GET /contracts/` request path and supporting modules. Static-only verification.
Lens applied as a prior, not a checklist. Query/index specifics are deferred to the `data-access`
lane; this report covers Python-side algorithmic cost and structural work that scales with
result-set size or filter-list size.

---

### [MAJOR impact] Python-side `.unique()` deduplication over join-fanned-out rows scales with items-per-contract
**Location:** `app/backend/src/fastapi_app/services/contract_service.py:79-82` (`outerjoin(ContractItem)`), `:167-177` (data query + `result.scalars().unique().all()`)

**Problem:** When any item-scoped filter/sort is active (`search`, `type_ids`, `is_bpc`, `min_runs`, `max_runs`, or `sort_by == ship_name`), the query does `outerjoin(ContractItem)`. A contract with N items produces N joined rows. The data query applies `order_by/offset/limit` and then SQLAlchemy collapses the duplicated parent rows back to distinct `Contract` objects in Python via `result.scalars().unique().all()`. `.unique()` builds a hash/identity set over **every returned row**, not over the distinct contracts. So the Python-side dedup work is O(rows_returned) = O(distinct_contracts × avg_items_per_contract), and the result-assembly cost grows with the join fan-out factor rather than with the page size the caller asked for.

For ship contracts (the headline use case) item counts are frequently in the tens, so a search-filtered page does materially more Python row-handling than the `size ≤ 100` page size suggests. This is pure-Python per-row work (hashing + set membership + list build) on the hot interactive-browse path.

**Impact:** Reachability: every search/type/bpc/ship-sort request (a primary, frequent filter combination). Frequency: interactive browsing — high. Per-occurrence cost: O(distinct × items_per_contract) Python row dedup + the extra rows the driver must decode/transport, versus O(distinct) for an un-fanned result. Aggregate cost scales with the items-per-contract distribution, which is unbounded by the page size.

**Confidence:** Strong-static (the `outerjoin` + `.unique()` pattern provably produces and then dedups fan-out rows; exact fan-out factor depends on data).

**Effort:** Contained — restructure the data query so the parent page is selected without the item fan-out (e.g. select distinct contract IDs / use the filter join only to constrain a `Contract.contract_id.in_(...)` subquery, then load the page + `selectinload(items)`), within `get_contracts` and its query-building block. Coordinate with the `data-access` lane, which owns the join/DISTINCT query shape.

**Verification plan:** Structural argument — count rows emitted by the data query under a `search` filter for contracts with K items each: current shape returns up to K× the distinct-contract count before `.unique()` collapses them; a contract-only page query returns exactly the distinct count. Confirm `.unique()` is operating over fanned rows by logging `len(result.all())` pre-unique vs post-unique on a seeded multi-item dataset. Correctness guard: a test seeding contracts with multiple matching items asserts the returned page contains each contract exactly once and in the requested sort order (pins dedup + ordering behavior across the refactor).

---

### [MINOR impact] Redundant materialization of filter-only joined items, then re-fetch via `selectinload`
**Location:** `app/backend/src/fastapi_app/services/contract_service.py:82` (`outerjoin(ContractItem)`) together with `:172` (`.options(selectinload(Contract.items))`)

**Problem:** The `outerjoin(ContractItem)` exists only to *filter/sort* on item attributes; its joined item columns are never read into the response. The response items are loaded separately by `selectinload(Contract.items)` (a second `IN (...)` round trip). So for the page, item rows are pulled through the join (inflating the primary result set, feeding the `.unique()` dedup in the finding above) **and** fetched again by selectinload. The join's item payload is pure wasted transport/decode work on the read path. The selectinload itself is the correct collection-loading strategy; the waste is that the filter join also drags item columns that are discarded.

**Impact:** Reachability: same item-filtered requests as above. Frequency: high. Per-occurrence cost: extra column decode for the discarded joined item rows; small relative to the dedup cost but on the same hot path and same root cause. Mostly a structural duplication rather than a complexity blowup.

**Confidence:** Strong-static.

**Effort:** Contained — folds into the same refactor as the MAJOR finding (constrain by an item-existence subquery / `EXISTS` rather than a fan-out join that also selects item columns). Owned jointly with `data-access`.

**Verification plan:** Structural — show the joined item columns are never projected into `ContractSchema` (response items come from `selectinload`), so the join's item payload is dead. Guard: existing filter tests must still return identical contract sets after switching the filter join to an `EXISTS`/`IN` subquery.

---

## Other items examined and deliberately NOT reported

- `[ContractSchema.model_validate(c) for c in contracts]` (`contract_service.py:186`) and the nested `items` validation: bounded by `size ≤ 100` contracts × their items. Pydantic v2 validation is C-backed; this is bounded per-request work and not an accidental quadratic. Volume of nested item validation is a consequence of the fan-out/over-fetch above, not an independent algorithmic defect — no separate finding.
- `SORT_MAP.get(...)` (`contract_service.py:24-32, 157`): dict lookup, O(1). Correct container choice.
- `.in_(filters.region_ids / system_ids / station_ids / type_ids)` (`contract_service.py:109-118`): these are pushed to SQL `IN`; Python side just passes the list. Filter lists are user-supplied and small; no Python-side linear scan. Not a finding.
- Two near-identical log-context dict builds per request (`contract_service.py:49-61` and `:190-206`): bounded constant-size dicts, cold relative to the DB round trips. The structlog/JSON render cost is a `serialization`/`idiom-currency` concern, not algorithmic — out of lane.
- `core/logging.py`, `core/cache.py`, `core/dependencies.py`, `db.py`, `schemas/*`, `main.py`: no per-request Python loops over request- or dataset-sized input; no wrong-container or recomputed-pure-value patterns in this dimension. (`main.py:128-137` `drop_all`/`create_all` on startup is a destructive correctness/startup concern, not algorithmic — see Suspected Bugs.)

---

## Suspected Bugs (for follow-up)

- **`contract_service.py:167-177` — pagination `LIMIT` applied to fan-out rows.** The data query applies `.offset()/.limit()` to the item-joined (non-distinct) result, but `.unique()` then collapses duplicate parent rows in Python. With multi-item contracts a page can therefore return **fewer than `size` distinct contracts** (some of the `size` raw rows are duplicates of the same contract), and page boundaries can split a contract's item-rows across pages, yielding unstable/duplicated pagination. The count query (`:131-132`) correctly counts `distinct contract_id`, so `total` and the per-page distinct count disagree. Likely a correctness defect; flagged here, not chased.
- **`contract_service.py:131` — `select(query.subquery().c.contract_id).distinct().subquery()` then `count()`** wraps the full filtered (joined) query as a subquery for distinct counting. Correctness looks intended, but the double-subquery DISTINCT shape is worth a `data-access` lane review for whether the planner materializes the whole join before de-duplicating.
- **`db.py:30-41` — `get_db_session_factory` defined twice** (identical). Second definition shadows the first; harmless but indicates a copy-paste error. `Base = declarative_base()` is also defined twice (`db.py:6` and `:27`); the second rebind creates a distinct `Base`, but models import `Base` from this module so behavior depends on import timing — worth confirming models bind to the intended `Base`.
- **`main.py:128-137` — `create_db_tables` runs `drop_all`+`create_all` in `lifespan` startup**, destroying all data on every app start. Marked in-code as dev-only but unconditional; not a perf issue, flagged for follow-up.
