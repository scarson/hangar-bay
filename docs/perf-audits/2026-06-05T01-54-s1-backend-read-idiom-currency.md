# Backend Read-Path Audit — Dimension: Framework-Idiom Currency

**Lane:** backend-read-idiom-currency
**Run:** 2026-06-05T01-54-s1
**Scope:** STATIC-ONLY. Read path for the contracts list/detail endpoints + supporting config/db/cache modules.
**Index relied on:** `version-indexes/python.md`, `covered_through: "Python 3.13 / Django 5.0 / SQLAlchemy 2.0 / pandas 2.x / NumPy 2.0"` (built 2026-06-03). No live currency brief this run — version-specific claims grounded in that index; anything ungrounded is marked LOW.

**Stack confirmed in scope:** FastAPI + Starlette, SQLAlchemy[asyncio] 2.0.41 (`AsyncSession`/`AsyncEngine`, `future=True`), asyncpg, Pydantic v2 (`ConfigDict(from_attributes=True)`, `model_validate`). Async driver under AsyncSession is the current-correct path (orm-database lens, "Async ORM correctness-as-performance") — no event-loop-blocking sync-driver issue found.

---

### [MAJOR impact] Double Pydantic validation on the contracts list response: service `model_validate`s every row, then FastAPI `response_model` re-validates the whole page again
**Location:** `services/contract_service.py:186` (`items=[ContractSchema.model_validate(c) for c in contracts]`) feeding the endpoint at `api/contracts.py:25` (`@router.get("/", response_model=PaginatedResponse[ContractSchema])`).
**Problem:** The service already converts every ORM `Contract` (plus its nested `items`) into a fully-validated `ContractSchema` via `model_validate`, then wraps them in a `PaginatedResponse[ContractSchema]`. FastAPI sees `response_model=PaginatedResponse[ContractSchema]` and runs the entire object through a second validation+serialization pass before encoding. The web-frameworks lens ("FastAPI `response_model` re-validation on every response", lines 65–73) names exactly this: when "the returned object is already a validated pydantic model," the `response_model` pass is redundant. Here it is strictly redundant because the items are already `ContractSchema` instances — the second pass re-walks every field of every contract and every nested item.
**Impact:** Two full validation passes over the page instead of one. For `size` up to 100 contracts, each with a nested `items` list, the per-row field-walk (date coercion, optional handling, nested list validation) runs twice. Pydantic v2's core is Rust-accelerated so each pass is cheaper than v1 would be, but the second pass is pure waste — it scales with page size × (contract fields + Σ item fields) on every list request. The fix is to do it once: either return ORM objects and let `response_model` do the single conversion (drop the comprehension), or keep the explicit conversion and bypass the response_model pass (`response_model=None` + return an `ORJSONResponse`, or `model_dump`).
**Confidence:** Strong-static (both passes are visible in scope; redundancy is structural, not inferred). The *magnitude* relative to total request cost is Heuristic without a benchmark.
**Effort:** Localized — either delete the `[model_validate(...)]` comprehension and pass ORM objects through (relying on `from_attributes=True`, already set in `schemas/contracts.py:22,49`), or set `response_model=None` and return a pre-serialized response. One-site change, but pick one direction and keep the detail endpoint consistent.
**Verification plan:** Benchmark `GET /contracts/?size=100` p50/p95 with (a) current double-pass, (b) ORM-objects-through-response_model single pass, (c) explicit `model_dump` + `ORJSONResponse` with `response_model=None`. Correctness guard: snapshot-compare the JSON body across all three to confirm identical field set, alias mapping, and null handling (especially the nested `items` and the `Optional[...]` fields).

---

### [MINOR impact] Per-row `model_validate` in a list comprehension instead of the v2 list fast path (`TypeAdapter(list[...]).validate_python`)
**Location:** `services/contract_service.py:186`.
**Problem:** The index entry under Pydantic v2 idioms calls out `TypeAdapter` for validating lists as the v2 fast path versus per-element `model_validate` in a Python loop (Pydantic v2 serialization fast paths: "`model_validate`/`model_dump` … TypeAdapter for lists"). The code runs `ContractSchema.model_validate(c)` once per contract inside a Python-level comprehension. A `TypeAdapter(list[ContractSchema]).validate_python(contracts)` drives the whole list through one Rust-side call, amortizing the Python/Rust boundary crossing across the page instead of paying it per row.
**Impact:** One FFI boundary crossing + Python loop iteration per contract (up to `size`=100) versus a single batched call. Per-occurrence cost is small (the heavy field-walk happens either way), so this is bounded-small-n in isolation. Listed as MINOR and only worth doing if the page conversion stays in the service at all — note this is **subsumed by the MAJOR finding above**: if you drop the explicit conversion entirely (let `response_model` do the single pass) this site disappears. Do not implement both fixes independently.
**Confidence:** Heuristic — the TypeAdapter-for-lists fast path is index-grounded, but the win is allocation/boundary overhead that is small relative to the field-walk and only matters at the top of the `size` range.
**Effort:** Localized.
**Verification plan:** Microbenchmark `[Model.model_validate(x) for x in rows]` vs `TypeAdapter(list[Model]).validate_python(rows)` at n=100 with the real nested shape. Only pursue if the MAJOR finding's resolution keeps conversion in the service. Correctness guard: assert equal output lists.

---

### [MINOR impact] Legacy transitional import `from sqlalchemy.future import select` instead of the 2.0 canonical `from sqlalchemy import select`
**Location:** `services/contract_service.py:5` (`from sqlalchemy.future import select`). Contrast `api/contracts.py:2` which already uses the canonical `from sqlalchemy import select`.
**Problem:** `sqlalchemy.future` was the 1.4 forward-compatibility shim for the 2.0-style `select()`. Under SQLAlchemy 2.0 (index: "`session.execute(select(Model))` unified API — landed in SQLAlchemy 2.0"), `sqlalchemy.select` *is* the 2.0 construct; `sqlalchemy.future.select` is a now-redundant alias kept for 1.4-migration code. The two endpoints in scope import `select` from different modules, which is also an internal-consistency smell.
**Impact:** No runtime perf difference — `future.select` resolves to the same construct. This is flagged because it is a superseded-idiom currency marker (the lens asks for "patterns the index marks superseded that the code still uses"), not because it costs cycles. Style-adjacent; included only because it is a concrete version-currency signal, not a taste preference.
**Confidence:** Strong-static (import path is superseded per the 2.0 migration; zero perf delta is certain).
**Effort:** Localized — change the import line.
**Verification plan:** None needed beyond import swap + existing test suite green; behavior is identical by construction.

---

## Items checked and explicitly NOT flagged (idiom-currency dimension)

- **`selectinload(Contract.items)`** (`contract_service.py:172`, `api/contracts.py:50`): this *is* the current-recommended 2.0 loader for one-to-many collections at this cardinality (orm-database lens: "`selectinload` issues a separate SELECT … WHERE id IN (…) and scales better for large collections"). Not a superseded idiom. No finding.
- **`AsyncSession` / `async_sessionmaker` / `create_async_engine(future=True)`** (`db.py`): current 2.0 async idioms. `expire_on_commit=False` and `autoflush=False` are set — these are the perf-favorable settings the orm-database lens recommends, not defaults being fought. No finding.
- **`ConfigDict(from_attributes=True)` + `model_validate`** (`schemas/contracts.py`): current Pydantic v2 idiom (the v1 `class Config`/`from_orm` path is the superseded one; this code does NOT use it). No finding.
- **`PaginatedResponse(BaseModel, Generic[T])`** (`schemas/common.py`): standard v2 generic-model idiom; not superseded.
- **`model_validator` / `field_validator`** (`config.py`, `core/config.py`): current v2 validator decorators (not v1 `@validator`/`@root_validator`). No idiom-currency finding. (See Suspected Bugs re: two divergent `Settings`.)
- **`db.execute(...).scalars().unique().all()`** (`contract_service.py:177`): `.all()` materializes the page, but the page is bounded by `limit(size)` ≤ 100 — the streaming/`yield_per` guidance (orm-database lens "Streaming large result sets") targets tens-of-thousands-row scans, not a bounded page. NOT flagged (bounded-small-n; out of dimension anyway).
- **`redis.asyncio` client + `from_url`** (`core/cache.py`): current async-redis idiom for redis-py 4.2+/6.2. No superseded-pattern finding.

## Support-track note
No upgrade is recommended by any finding above, so the runtime LTS gate does not bind here. All three findings are lateral idiom swaps within the already-pinned versions (SQLAlchemy 2.0.41, Pydantic v2) — no Python/runtime version bump implied.

---

## Suspected Bugs (for follow-up)
*(Out of dimension — flagged for the correctness lane, not chased here.)*

1. **Two divergent `Settings` classes / duplicate config modules.** `config.py` and `core/config.py` each define a `Settings` BaseSettings with different fields, defaults, and `env_file` paths (`config.py` → `../.env`; `core/config.py` → `src/.env`). `main.py:18` imports from `core.config`; `db.py:8` imports from `.config`. Two separate `Settings()` instances are constructed at import time with different `AGGREGATION_REGION_IDS` defaults (`core/config.py` has a default_factory; `config.py` makes it required). Likely-unintended config drift between the DB layer and the app layer.
2. **`get_db_session_factory` defined twice, identically** (`db.py:30` and `db.py:37`) — the second shadows the first. Dead/duplicate definition.
3. **`Base = declarative_base()` called twice** (`db.py:6` and `db.py:27`). The second `Base` replaces the first in `db.py`'s namespace; models import `Base` from `..db`, so they bind to the second instance. Harmless only by luck of import ordering — fragile.
4. **`create_db_tables()` does `drop_all` + `create_all` on every startup** (`main.py:128–137`) — destructive on each boot; the docstring admits it is dev-only but it runs unconditionally in `lifespan`.
5. **Leftover debug `print()` statements at import time** in `config.py` (lines 44, 52, 55, 59, 67, 70, 109, 110), `core/config.py` (lines 46, 60, 64, 71, 80, 86, 100–104), and `main.py:9` — not a perf finding at request time, but noise that runs on every process start / every settings validation.
