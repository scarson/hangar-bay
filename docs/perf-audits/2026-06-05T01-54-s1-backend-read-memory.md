# Performance Audit — Backend Read Path — Dimension: Memory & Allocation

Scope: `GET /contracts/` read path and supporting modules.
Lens: superpowers-plus/performance-audit profile-pack `python.md` (memory/allocation + Runtime notes).
Verification: STATIC-ONLY (complexity/structural arguments). No measured numbers.

---

### [MAJOR impact] Join fan-out materialized in Python before `.unique()` dedup on the paged data query
**Location:** `app/backend/src/fastapi_app/services/contract_service.py:79-82`, `167-177`
**Problem:** When any item-related filter or `sort_by=ship_name` is active, the base query gets `query.outerjoin(ContractItem)` (line 82). The data query then applies `.order_by().offset().limit(size).options(selectinload(Contract.items))` (lines 167-173) and is collected with `result.scalars().unique().all()` (line 177). Because the primary SELECT is over a `Contract LEFT OUTER JOIN contract_items`, the DB returns **one row per (contract, matching item) pair** — the classic join fan-out. SQLAlchemy must construct a `Contract` identity-map entry / row tuple for every one of those rows and then `.unique()` discards the duplicates in Python. The `selectinload` does NOT prevent this: `selectinload` issues a *separate* IN query for items, but the primary joined query still emits the fan-out rows. So for a page where each contract has N items, up to `size × N` rows are pulled into the Python driver and deduped, rather than `size` rows.
**Impact:** Per-request peak allocation on the data query scales with `size × avg_items_per_contract` (row tuples + transient duplicate-resolution) instead of `size`. For contracts with many items this is a multiplicative blow-up of the row-buffer churn for every interactive browse request that filters on items or sorts by ship name (a common case for a ship-contract browser). The materialized count of `Contract` instances after dedup is still `size`, but the discarded intermediate rows are pure allocation waste on the hot path.
**Confidence:** Strong-static (SQLAlchemy emits a flat join; `.unique()` is post-fetch Python dedup — its presence is itself the evidence that the result is known to contain duplicate Contract rows).
**Effort:** Contained — the structural fix is to make the primary data query select only distinct contract IDs / contract rows (e.g. resolve the filtered-and-paged set of `contract_id`s via a distinct subquery, then `select(Contract).where(contract_id.in_(...)).options(selectinload(...))`), so the entity-loading query never carries the fan-out. Interacts with the LIMIT-on-fan-out correctness issue below, so the two should be fixed together.
**Verification plan:** Structural: confirm `.unique()` on line 177 is only required because the join duplicates rows; once the entity query keys off distinct contract IDs the dedup (and its intermediate rows) disappears. Correctness guard: a test with one contract having multiple matching items asserting (a) the page contains the contract exactly once and (b) `len(page) == min(size, distinct_matches)` — protects against regressions from the rewrite.

---

### [MAJOR impact] Count subquery wraps the entire fan-out query, forcing a large DB-side intermediate
**Location:** `app/backend/src/fastapi_app/services/contract_service.py:131-135`
**Problem:** `count_subquery = select(query.subquery().c.contract_id).distinct().subquery()` then `select(func.count()).select_from(count_subquery)`. `query` at this point is the full filtered `Contract OUTER JOIN contract_items` select. So the count path tells the DB to: produce the entire filtered fan-out rowset, project `contract_id`, DISTINCT it, then count. The DISTINCT must buffer/hash every fan-out row of the *entire matching set* (not just one page) before collapsing. For large regions (tens of thousands of contracts, each 0..N items) the pre-distinct intermediate scales with `total_matching_contracts × avg_items`.
**Impact:** Peak intermediate memory of the count step scales with the full filtered fan-out, not with the page. While this is primarily DB-side (asyncpg streams the single scalar back, so Python-side allocation is small), it is the largest memory amplifier on the request and is incurred on *every* page request because `total` is recomputed each call. This sits squarely in "reading/building a large intermediate collection then discarding it" — here the collection is the DISTINCT hash set inside the DB driven by the Python query construction.
**Confidence:** Strong-static (the query shape is explicit; DISTINCT over a join cannot be evaluated without materializing the join keys).
**Effort:** Contained — count distinct contract IDs directly off the filtered set without the entity join when item filters are absent, or use `COUNT(DISTINCT contracts.contract_id)` over the filtered join (lets the planner avoid a separate DISTINCT-then-count materialization). The Python-side change is small; the win is bounding the DB intermediate.
**Verification plan:** Structural: `EXPLAIN` shape comparison (HashAggregate over full join vs. COUNT(DISTINCT)) — argue the intermediate cardinality difference without timing it. Correctness guard: test that `total` equals the distinct contract count under item-filter fan-out (a contract with 3 matching items must count as 1).

---

### [MAJOR impact] LIMIT applied to the fan-out rowset undercounts page contents (memory + correctness coupled)
**Location:** `app/backend/src/fastapi_app/services/contract_service.py:167-177`
**Problem:** `.limit(filters.size)` is applied to the joined query *before* `.unique()` dedups. The DB applies LIMIT to fan-out rows, so a page can return up to `size` *rows* that collapse to **fewer than `size` distinct contracts**. From the memory lens this is the flip side of finding #1: the code fetches a `size`-bounded slice of the wrong (fan-out) population. The allocation argument: even with LIMIT, the row buffer for the page is `size` fan-out rows, and dedup churns transient objects; the page payload then under-fills, so clients paginate more (more requests, more total allocation across the browse session).
**Confidence:** Strong-static for the structural shape (LIMIT-before-dedup over a join). The correctness consequence is recorded below as a bug, not chased.
**Effort:** Contained — same rewrite as finding #1 (page over distinct contract IDs, then load entities) fixes both the dedup waste and the short-page behavior in one change.
**Verification plan:** Covered by the finding #1 guard test (`len(page) == min(size, distinct_matches)`).

---

### [MINOR impact] Per-request structured-log payloads rebuild the same `search_terms` dict 2–3× per call
**Location:** `app/backend/src/fastapi_app/services/contract_service.py:49-61`, `139-151`, `190-206`, `214-228`
**Problem:** `get_contracts` builds a `search_terms` dict literal (and re-reads `filters.sort_by.value`/`sort_direction.value`) at the start (info log), again in the zero-results branch, and again in the success/failure `log_key_event` call — 2 dict allocations per normal request plus enum `.value` lookups. structlog's `JSONRenderer` (logging.py:73) then serializes the merged event dict on every emitted record, allocating the JSON string. This is per-request but bounded and small (a handful of dict/str allocations), so it is a minor allocation cost, not a hot inner-loop issue.
**Impact:** A small constant number of dict + string allocations per request; does not scale with result size.
**Confidence:** Heuristic (small constant overhead; only matters if log volume itself becomes a concern).
**Effort:** Localized — build the `search_terms` dict once and reuse; or rely on structlog binding. Low value, listed only for completeness.
**Verification plan:** Structural: count dict literals per request path. No correctness guard needed (logging-only).

---

### [MINOR impact] Full page of Pydantic models built eagerly via list comprehension
**Location:** `app/backend/src/fastapi_app/services/contract_service.py:186`
**Problem:** `items=[ContractSchema.model_validate(c) for c in contracts]` materializes a list of `ContractSchema` (each nesting a `List[ContractItemSchema]`) for the whole page before the `PaginatedResponse` is built and re-serialized to JSON by FastAPI. This is per-row Pydantic object churn plus a second serialization pass (FastAPI validates the `response_model` again). However, the page is bounded at `size ≤ 100` (schemas/contracts.py:128), so `n` is small and capped — this is bounded-small-n by the calibration rules.
**Impact:** Allocation bounded by `size` (≤100) contracts × their items. Does not grow with table size. The notable inefficiency is the *double* model construction (service builds `ContractSchema`, then FastAPI re-validates against `response_model=PaginatedResponse[ContractSchema]`), doubling Pydantic allocations for the page.
**Confidence:** Heuristic (double-validation is real but bounded; impact depends on items-per-contract).
**Effort:** Localized — return ORM objects and let FastAPI serialize once (the schemas already use `from_attributes=True`), or set `response_model=None` and return the pre-built response to avoid the second validation pass. Bounded payoff.
**Verification plan:** Structural: confirm both the service comprehension and FastAPI response_model validation run (two Pydantic passes over the same page). Correctness guard: response shape/field test unchanged after collapsing to a single validation.

---

## Non-findings (checked, not significant for this dimension)

- `core/cache.py`: Redis client is a singleton created at startup; `decode_responses=True` allocates str per reply but no unbounded accumulation in scope. No in-process cache with eviction concerns on the read path.
- `core/logging.py`: `RequestIDMiddleware` clears + binds contextvars per request (bounded, constant). No accumulating buffer.
- `schemas/*` and `models/contracts.py`: Pydantic v2 models and ORM instances do not declare `__slots__`, but instance counts per request are page-bounded (≤100 contracts + their items); `__slots__` micro-savings fall under bounded-small-n. Not reported.
- No unbounded module-level cache, no `lru_cache` on instance methods, no whole-file reads, no accumulating global buffers found in scope.

---

## Suspected Bugs (for follow-up)

1. **LIMIT-before-dedup returns short pages** (`contract_service.py:167-177`): with an active item filter / `sort_by=ship_name`, `.limit(size)` bounds fan-out rows, so `.unique()` can yield fewer than `size` distinct contracts on a full page — clients see undersized pages and inconsistent pagination. (Coupled to memory finding #3.)
2. **`SORT_MAP.get(filters.sort_by)` can never be `None` as written** (`contract_service.py:157-160`): `sort_by` defaults to and is typed as `SortableContractFields`, and all enum members are mapped, so the `None` fallback branch is dead — but if `ship_name` sort is requested *without* the join being added in some refactor, ordering by `ContractItem.type_name` would be invalid. Note for follow-up; not a memory issue.
3. **`min_me`/`max_me`/`min_te`/`max_te` filters accepted but never applied** (`schemas/contracts.py:97-108` vs service filter block): silently ignored (acknowledged in code comment line 121). Correctness, not memory.
