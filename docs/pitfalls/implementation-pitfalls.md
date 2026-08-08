# Hangar Bay — Implementation Pitfalls & Review Findings

> **Purpose:** Document implementation traps, design flaws, and corrected decisions that would cause production failures, security vulnerabilities, or data correctness bugs if shipped. This document is the primary code review reference for the Hangar Bay codebase.
>
> **What to implement and why.** Read before starting any task; add entries when a bug's root cause is a reusable trap, not a one-off typo. Each entry follows: **ID — the flaw — why it matters — the fix (do instead) — where it bit us.**
>
> **Relationship to testing-pitfalls.md:** This document specifies *what* to implement and *why*. `docs/pitfalls/testing-pitfalls.md` specifies *how to verify* those implementations work correctly. They are complementary — cross-references are noted inline.
>
> **Last validated against codebase:** 2026-07-12 (replace when you audit against the current code)

---

## How to Use This Document

This document serves three audiences. Start here, then go directly to the section you need.

**If you're implementing code:** Go to the domain section matching your work area. Each entry has a clear *Flaw → Why It Matters → Fix → Where It Bit Us* structure. Follow the Fix. The provenance teaches the generalizable principle so you'll catch the next instance of this pattern.

**If you're reviewing code:** Go to your domain section's **Review Checklist** at the end. Each item is a pass/fail check derived from the pitfalls above it. If a checklist item fails, read the referenced pitfall for context.

**If you're maintaining this document:** Every pitfall discovered during implementation, review, or debugging MUST be added here. See the maintenance sections at the end of this file (Appendix C). Partial updates cause drift.

---

## Table of Contents

| § | Section | You're working on... | Entries | Checklist |
|---|---------|---------------------|---------|-----------|
| 1 | [API & Request Binding](#section-1-api--request-binding) | FastAPI request/query binding, filter params, dev-proxy routing | FASTAPI-1, FASTAPI-2, FASTAPI-3, PROXY-1 | §1.C |
| 2 | [Data & Persistence](#section-2-data--persistence) | SQLAlchemy queries, pagination over joins | SQLA-1, SQLA-2, SQLA-3, SQLA-4, SQLA-5 | §2.C |
| 3 | [Environment & Dev Loop](#section-3-environment--dev-loop) | Settings/env loading, startup ingestion, dev-server hygiene | ENV-1, ENV-2, ENV-3, ENV-4, ENV-5, ENV-6, ENV-7, ENV-8, ENV-9, ENV-10 | §3.C |
| 4 | [External Integrations (ESI)](#section-4-external-integrations-esi) | Calling EVE's ESI API — route versions, deprecations, caching headers, upstream status, spec drift | ESI-1, ESI-2, ESI-3, ESI-4 | §4.C |
| 5 | [Deployment & Platform](#section-5-deployment--platform) | Production config, managed-platform URLs, process topology | DEPLOY-1, DEPLOY-2, DEPLOY-3, DEPLOY-4, DEPLOY-5, DEPLOY-6 | §5.C |
| 6 | [Frontend State & Rendering](#section-6-frontend-state--rendering) | React SPA — URL state vs cached server data, and what the screen claims while they disagree | WEB-1 | §6.C |
| — | [Orchestration](#orchestration) | Parallel subagent dispatch and output persistence | ORCH-1 | §Orchestration.C |
| A | [Historical Changelog](#appendix-a-historical-changelog) | Provenance, validation dates, review process meta-observations | — | — |
| B | [Unified Summary Table](#appendix-b-unified-summary-table) | All pitfalls at a glance, with severity and status | — | — |
| C | [Document Maintenance Guide](#appendix-c-document-maintenance-guide) | How to add, update, and supersede entries | — | — |

---

# Section 1: API & Request Binding

> **Reader context:** I'm building or reviewing FastAPI request handling — query-parameter binding, filter models, and how the SPA/dev-proxy reaches backend routes.
>
> These traps share a theme: a filter or route can look correct at every layer above HTTP (schema, generated client, service) while being silently unreachable or inert over the wire.

---

### FASTAPI-1: `Depends(Model)` sends list fields to the GET request body

**The Flaw:** A Pydantic model used via `Depends(Model)` binds scalar fields to query params but any non-scalar field (e.g. `Optional[List[int]]`) to the **request body** — silently.

**Why It Matters:** Repeated query params are ignored (200 OK, unfiltered), and browsers cannot send a GET body at all — so the filter is unreachable from any browser client while every server-side layer still looks healthy.

**The Fix:** Declare query-param models as `Annotated[Model, Query()]` (FastAPI ≥ 0.115).

**Where It Bit Us:** `region_ids`/`system_ids`/`station_ids`/`type_ids` in `ContractFilters` were unusable from any browser client (found by 2026-07-11 adversarial spec review). See testing-pitfalls.md TEST-1.

---

### FASTAPI-2: Declared-but-unimplemented filter params ship dead controls

**The Flaw:** A filter param that the schema accepts but the service never applies looks functional to every layer above it (API docs, generated clients, UI).

**The Fix:** Before exposing any filter in a client, verify the service layer actually applies it. Mark known-inert params in the schema description.

**Where It Bit Us:** `min_me`/`max_me`/`min_te`/`max_te` were accepted and silently ignored for as long as ME/TE were absent from the model, and `min_runs`/`max_runs` filtered `raw_quantity`, a column public ingestion never fills — three controls a client could offer that could only disappoint. Since fixed (F008): ingestion writes `runs`/`material_efficiency`/`time_efficiency`, and `_apply_item_filters` applies all three families as correlated EXISTS over offered items.

---

### PROXY-1: FastAPI trailing-slash 307 escapes a prefix-rewriting proxy

**The Flaw:** The backend mounts routes bare (e.g. `/contracts/`) and the dev proxy adds/strips `/api/v1`. Requesting `/contracts` (no slash) triggers a 307 whose `Location` lacks the proxy prefix, so the redirect escapes to the SPA origin and fails.

**The Fix:** Clients call schema paths verbatim, including trailing slashes; the openapi-fetch client's `baseUrl` owns the `/api/v1` prefix.

---

### FASTAPI-3: A response schema stricter than its own column 500s the whole page

**The Flaw:** A Pydantic response field declared non-optional (`start_location_id: int`) sitting over a model column declared `nullable=True`. Nothing rejects the row on the way in; the mismatch fires only when a NULL actually reaches serialization.

**Why It Matters:** The blast radius is the *page*, not the row. `PaginatedResponse` validates every item, so one NULL-bearing contract raises `ValidationError` inside the endpoint and returns 500 for a page that also held 49 perfectly good rows — and the same row 500s its detail endpoint. It stays invisible until real data supplies the NULL, which for an upstream-optional field can be long after the code ships.

**The Fix:** Read optionality as a three-link chain and check all of it whenever you touch any link: upstream `required` array → model `nullable=` → response schema `Optional[...]`. Each link MUST be at least as permissive as the one above it. Where a field is genuinely required for the UI to make sense, enforce it at INGESTION (reject or default the row) rather than at serialization, where the failure lands on a reader who did nothing wrong.

**Where It Bit Us:** `ContractSchema.start_location_id` was a bare `int` over a nullable column fed by an ESI field absent from the public-contracts `required` array (2026-08-01). Pinned by `test_serializes_a_contract_esi_sent_without_a_start_location`, which 500s on the pre-fix schema. Pairs with ESI-3 and testing-pitfalls TEST-18.

---

### §1.C — Review Checklist

- [ ] **Query-param models use `Annotated[Model, Query()]`, not `Depends(Model)`** — confirm non-scalar fields (e.g. `List[int]`) bind to query params, not the GET body (FASTAPI-1)
- [ ] **Every filter param the schema accepts is actually applied by the service layer** — known-inert params are explicitly marked in the schema description (FASTAPI-2)
- [ ] **Clients call schema paths verbatim, including trailing slashes** — the openapi-fetch `baseUrl` owns the `/api/v1` prefix; no bare-path request 307-escapes the proxy (PROXY-1)
- [ ] **Response-schema optionality is at least as permissive as the column, which is at least as permissive as the upstream `required` array** — a stricter response field 500s the entire page a NULL lands on, not just its row (FASTAPI-3)

---

# Section 2: Data & Persistence

> **Reader context:** I'm writing or reviewing SQLAlchemy queries — especially anything that paginates, sorts, or joins one-to-many relationships.

---

### SQLA-1: Paginating a joined query paginates joined rows, not parent entities

**The Flaw:** `offset/limit` applied to a query that joins a one-to-many child table operates on the duplicated joined rows.

**Why It Matters:** De-duplicating afterwards (`.unique()`) yields short pages, and parents can be skipped or duplicated across page boundaries while the distinct count query disagrees.

**The Fix:** Paginate over distinct parent IDs (grouped subquery with aggregate-based ordering), then load the page's entities and restore the ID order.

**Where It Bit Us:** `get_contracts` pagination under `search`/`is_bpc`/`type_ids`/`ship_name` sort. See testing-pitfalls.md TEST-4.

---

### SQLA-2: `ON CONFLICT` against a partial unique index must restate the index predicate

**The Flaw:** `INSERT … ON CONFLICT DO NOTHING` / `DO UPDATE` targeting a **partial** unique index (`CREATE UNIQUE INDEX … WHERE <predicate>`) will not infer the index from `index_elements` alone. Postgres raises `no unique or exclusion constraint matching the ON CONFLICT specification` at runtime — every insert fails, not just conflicting ones.

**Why It Matters:** The failure is runtime-only (schema and query both look valid), so it surfaces on the first real insert, not at review or migration time. For a scheduled writer (the watchlist matcher) that means every run raises and zero notifications are ever created.

**The Fix:** Restate the partial-index predicate in the conflict clause as a **literal identical to the index DDL**. SQLAlchemy: `insert(...).on_conflict_do_nothing(index_elements=["user_id", "contract_id", "watch_type_id"], index_where=text("type = 'watchlist_match'"))`. Use `text(...)`, not the ORM comparison `Notification.type == "watchlist_match"` — the latter compiles to a parameterized `type = $1`, which Postgres's partial-index implication check cannot match against the index's literal predicate, so inference can fail. Also populate **every** column in the index — Postgres treats NULLs as distinct in a unique index, so a NULL-bearing dedup column would never conflict and hollow out the guarantee.

**Where It Bit Us:** Pre-empted in the M3 watchlist-matcher design (`docs/superpowers/specs/2026-07-17-m3-account-features-design.md` §4.4); the partial index `uq_notifications_watchlist_dedup` on `(user_id, contract_id, watch_type_id) WHERE type='watchlist_match'` requires the `index_where` restatement or the matcher's core insert raises on every run. See testing-pitfalls.md TEST-11.

---

### SQLA-3: A per-row predicate over a one-to-many join cannot classify the parent

**The Flaw:** A filter that classifies a PARENT entity ("is this a blueprint-copy contract?") applied as a predicate on a JOINED CHILD row. The join emits one row per child, so the predicate answers a question about *an item*, not *the contract*. Both a condition and its apparent negation are then satisfiable by the same parent — a contract bundling a copy with an ordinary item has one item matching each — so the two branches OVERLAP instead of partitioning.

**Why It Matters:** The failure is quiet and only visible on mixed children. Single-item contracts behave perfectly, which is most fixture data and most casual testing. At scale the same contract appears under `is_bpc=true` AND `is_bpc=false`, the two totals sum to more than the corpus, and a user paging both filters sees duplicates with no error anywhere. A test built on single-item fixtures cannot detect it.

**The Fix:** Express parent-level classification as a **correlated EXISTS over the children**, and derive the negative branch by negating that same expression rather than writing a second predicate:

```python
has_copy = (
    select(ContractItem.record_id)
    .where(ContractItem.contract_id == Contract.contract_id,
           ContractItem.is_blueprint_copy.is_(True))
    .correlate(Contract).exists()
)
query = query.filter(has_copy if filters.is_bpc else ~has_copy)
```

One expression negated makes the branches exact complements *by construction*, instead of two hand-written predicates that must be kept in agreement. It also drops the join for that filter entirely, so the SQLA-1 pagination hazard does not arise. Test it with a parent holding BOTH kinds of child and assert the two branch totals sum to the unfiltered total — a single-child fixture passes either way.

**Where It Bit Us:** `is_bpc` (2026-08-01). A first fix corrected the NULL half (ESI-3) but kept the per-item form, so a contract bundling a BPC with a hull matched both filter values; caught in adversarial review of PR #98 before merge and re-fixed as a contract-level EXISTS. Pairs with SQLA-1 (both are "the join changed what the query is about") and testing-pitfalls TEST-19.

---

### SQLA-4: A SQLAlchemy error carries the failed statement's bind values into `str()`

**The Flaw:** Scrubbing a sensitive value out of a log payload while the same log record renders the exception with `str(e)`. Every `StatementError` (and so every `DBAPIError` — statement timeout, dropped connection, deadlock) appends `[SQL: ...]\n[parameters: {...}]` to its message. The SQL carries placeholders, but the parameters carry the **values**, and the statement that failed is the one holding the user's input as a bind.

**Why It Matters:** It defeats the scrub completely and silently, on exactly the path nobody exercises. The success path logs the redacted dimension; the failure path re-publishes the raw value one key over, in the same record. Nothing looks wrong in review, and a test that injects a plain `RuntimeError` — the obvious way to simulate a DB failure — cannot see it, because a non-SQLAlchemy exception's `str()` has no parameters to leak. The value also escapes past the service: a re-raised exception reaches whatever global handler logs `str(exc)` and the traceback.

**The Fix:** Hide at the source — `create_async_engine(..., hide_parameters=True)` — so SQLAlchemy substitutes `[SQL parameters hidden due to hide_parameters=True]` in every error the engine raises, in the service's log, in the global handler's, and in the traceback alike. Where a log site must hold the guarantee for a session built elsewhere, render through the same flag rather than dropping the message (the driver's diagnosis is why the field exists):

```python
def _error_without_bound_parameters(exc: BaseException) -> str:
    if not isinstance(exc, StatementError):
        return str(exc)
    previously_hidden = exc.hide_parameters
    exc.hide_parameters = True
    try:
        return str(exc)
    finally:
        exc.hide_parameters = previously_hidden
```

Test it by injecting a real `StatementError` constructed with the sensitive value as a bind, and assert against the WHOLE log record, not the payload key you scrubbed.

**Where It Bit Us:** F008 Task B10 (2026-08-07). The four `search_terms` payloads were changed to report `search_len` instead of the user's raw query text, and the commit claimed the text "never lands in a log line" — but the failure site's `error_message=str(e)` sat in the same record, and the failing statement is the one carrying the `ILIKE '%<search text>%'` bind. Caught in review; the test that shipped with the scrub injected `RuntimeError("simulated db failure")` and was structurally unable to see it. Pairs with the universal "no PII in audit/debug logs" rule and testing-pitfalls TEST-21.

---

### SQLA-5: An upsert that copies supplied columns on conflict decays enrichment-derived values

**The Flaw:** `bulk_upsert` copies every supplied column from the incoming row on conflict. A column whose value comes from a fallible enrichment step (external name resolution, item fetching) carries NULL or a default whenever that step degrades — and the on-conflict copy writes it over the good value already stored, for every re-sighted row in the batch.

**Why It Matters:** The decay is silent: no error is raised anywhere, because the degraded step already handled its own failure (a swallowed per-chunk error, an ETag-304 skip). One transient upstream outage blanks previously-correct data corpus-wide, and it stays blank until the next fully-successful run — or forever, when the value is never re-derived. Three variants have bitten this one function: `is_ship_contract` decayed to False whenever items were ETag-304'd past re-enrichment; a station outage would have written NULL over every known `start/end_location_system_id`; and a partial `/universe/names` map blanked all four denormalized name columns for every re-sighted contract.

**The Fix:** Decide per column what an absent-or-NULL value means at conflict time, and encode that decision in the row shape or the upsert call:

- **Maintained by a different writer** (`is_ship_contract`, `item_processing_status`, `enrichment_version`): keep the column **absent from the row dict entirely** — `bulk_upsert` only updates supplied columns, and the uniform-keys invariant makes one row's omission everyone's.
- **Re-derived every run, where NULL means "unknown this run"** (the four name columns): pass the column in `bulk_upsert`'s `preserve_on_null` set, which compiles the on-conflict assignment to `COALESCE(excluded.col, table.col)` — NULL keeps the stored value, a real value still overwrites.
- **Legitimately clearable** (a title the issuer deleted): plain copy semantics are correct; do neither.

A durable-cache read-back (as `_select_known_station_systems` does for station→system pairs) is the stronger alternative when the value is static and worth never re-fetching — but it protects only its own columns; new enrichment-derived columns need one of the three choices above.

**Where It Bit Us:** The four contract name columns (F008 decision log D10, flagged by codex in the PR-A review; fixed in PR #142, 2026-08-07). The `is_ship_contract` decay and the station-system hazard were each fixed earlier in their own shapes — the comment blocks in `_build_contract_rows` and `_select_known_station_systems` (`services/background_aggregation.py`) carry those stories.

---

### §2.C — Review Checklist

- [ ] **Pagination over a one-to-many join paginates distinct parent IDs, not duplicated joined rows** — grouped subquery with aggregate-based ordering; page entities re-loaded and restored to the ID order (SQLA-1)
- [ ] **Parent-level classification uses a correlated EXISTS, not a predicate on a joined child row** — the negative branch negates the same expression, and a mixed-child fixture proves the branches are complements (SQLA-3)
- [ ] **`ON CONFLICT` against a partial unique index restates the index predicate** — `index_where=` matches the index's `WHERE`, and every indexed column is non-NULL on insert (Postgres NULLs never conflict) (SQLA-2)
- [ ] **No log site renders a SQLAlchemy exception with an unscrubbed `str()`** — the engine sets `hide_parameters=True`, and any redaction claim is tested against the whole record with a real `StatementError` carrying the value as a bind (SQLA-4)
- [ ] **Every enrichment-derived column in an upsert row decides what NULL means on conflict** — maintained-elsewhere columns are absent from the row, re-derived-each-run columns are in `preserve_on_null` (COALESCE keeps the stored value), and only genuinely clearable columns keep plain copy semantics (SQLA-5)

---

# Section 3: Environment & Dev Loop

> **Reader context:** I'm configuring settings/env, or debugging why the backend has no data / behaves oddly in the dev loop.
>
> Several of these are not shipped-code bugs but dev-loop traps that repeatedly cost debugging sessions — an empty database that *looks* like a frontend or data bug is almost always one of these.

---

### ENV-1: pydantic-settings JSON-decodes complex env fields before validators run

**The Flaw:** A `List[int]` settings field only accepts a JSON list (`AGGREGATION_REGION_IDS=[10000002]`). A bare int or comma-separated string crashes at startup even if a field validator claims to handle it — pydantic-settings JSON-decodes complex types first.

**Also note:** the backend loads env from `app/backend/src/.env` (not next to `.env.example`) and requires `ESI_USER_AGENT`. (Prior to the M2 settings consolidation there were two divergent Settings classes — `fastapi_app/config.py` and `fastapi_app/core/config.py` — that setup docs had to satisfy both; M2 consolidated them into the single `core/config.py` Settings, so this is now a single-class concern. See ENV-4 for the consolidated class's `extra="ignore"` requirement.)

---

### ENV-2: Backend restart wipes and re-ingests all data

**The Flaw:** `main.py` drops and recreates all tables on every startup and immediately re-runs aggregation (dev limit: 100 contracts from configured regions). Real data appears minutes after boot, not instantly.

**The Lesson:** Don't diagnose an empty contract list as a frontend bug until ingestion has had time to run.

---

### ENV-3: uvicorn --reload + startup ingestion + the Valkey lock interact badly in dev

**The Flaw:** Every backend source edit triggers a reload, which drops/recreates all tables (ENV-2) and starts a fresh aggregation run; killing a run mid-flight (reload, pkill, app restart) can strand the Valkey lock so the NEXT startup run logs "already running" and silently skips — leaving an empty database that looks like a data bug.

**The Fix:** Finish all backend edits first, then run one clean cycle: `docker exec hangar_bay_valkey valkey-cli DEL "hangar-bay:aggregation:lock"`, `touch app/backend/src/fastapi_app/main.py`, then hand off the backend until ingestion completes (first run ~2-7 min; ESI ETag/TTL caches in Valkey make repeats much faster). The lock is TTL-bounded (30 min) and fencing-tokened since `d16d145`, so production self-heals; this is purely a dev-loop trap.

**Also:** run dev servers as tracked background tasks with visible logs — a detached server logging to `/dev/null` cost a debugging session when stale logs from a dead process were mistaken for live state.

---

### ENV-4: pydantic-settings rejects unknown .env keys unless extra="ignore"

**The Flaw:** The consolidated `Settings` reads the whole `app/backend/src/.env` file. Without `extra="ignore"` in `model_config`, any key present in `.env` that is NOT a declared field aborts construction at import — crashing boot.

**Why It Matters:** During M2, adding `TOKEN_CIPHER_KEYS` to `.env` before the field existed on the class crashed the baseline app at startup. Unknown ENV VARS are ignored (pydantic-settings only reads env vars matching fields), but unknown `.env`-FILE keys are not — this trap is `.env`-file-specific.

**The Fix:** Keep `extra="ignore"` on the consolidated `Settings.model_config` (`core/config.py`). New config always adds the field AND documents it in `.env.example`.

**Where It Bit Us:** M2 settings consolidation (2026-07-12).

---

### ENV-5: The backend venv/CI pin Python 3.12 until the FastAPI 0.115 hold lifts

> **SUPERSEDED (2026-07-13):** Hold lifted — no longer applicable. The FastAPI-current / Python-3.14 chore migrated the backend to FastAPI 0.139 / Starlette 1.3.1 and moved the venv and both CI `python-version` pins to 3.14. FastAPI 0.139 precomputes `Dependant.is_coroutine_callable` at route registration and no longer calls the 3.14-deprecated `asyncio.iscoroutinefunction`, so the 16 DeprecationWarnings are gone at the source (never a filter mask). The spike that "broke 19 tests" traced to `prometheus-fastapi-instrumentator` 7.1.0, whose middleware crashes in `_get_route_name` against Starlette 0.52.x despite its `starlette<1.0` pin; reaching current Starlette required bumping it to 8.0.2 (`starlette>=1.0`). The pydantic-relock context below stays true; original content preserved for history.

**The Flaw:** The default machine `python3` is CPython 3.14. The pydantic stack is relocked with cp314 wheels (pydantic 2.13 / pydantic-core 2.46), so 3.14 installs and passes — but FastAPI is deliberately held at 0.115 (`fastapi>=0.115.12,<0.116` in pyproject): its internals call `asyncio.iscoroutinefunction`, which 3.14 deprecates, emitting a DeprecationWarning block in every test run and violating the pristine-test-output gate. The unheld resolve (FastAPI 0.139 / Starlette 0.52) broke 19 tests on first contact — a real migration, not a version bump.

**The Fix:** Keep the backend venv and CI on Python 3.12 (`actions/setup-python` + `setup-pdm` with `python-version: '3.12'`) until a dedicated FastAPI/Starlette migration lands; then flip the pins to 3.14 and delete this entry. Never mask the warnings with a filter, and do not "fix" application code for other interpreter versions.

**Where It Bit Us:** M2 CI bring-up + the pydantic relock spike (2026-07-12).

---

### ENV-6: F811 cascade when removing debug prints/functions

**The Flaw:** The repo's flake8 config ignores `F401` (unused import) but NOT `F811` (redefinition). Deleting a debug print/function whose sole job consumed a module-level `settings` import leaves that import orphaned — invisible under the F401 ignore — and any same-named function parameter (e.g. a `settings` argument on some other function in the same module) then trips a live `F811` ("redefinition of unused `settings`").

**Why It Matters:** Because F401 is silenced project-wide, an agent removing debug scaffolding gets no signal that the import is now dead; the failure only surfaces as an unrelated-looking F811 on a different function elsewhere in the file, which reads like a pre-existing lint bug rather than a consequence of the deletion just made.

**The Fix:** When deleting a debug print/function, always check whether it was the last consumer of any module-level import it referenced, and drop the now-orphaned import (and any comment that falsified it) in the same edit — don't rely on flake8 to catch it, since F401 is ignored here.

**Where It Bit Us:** M2 Phase 1 settings consolidation, twice (DISC-EXEC-2, 2026-07-12).

---

### ENV-7: `pdm run format` is repo-wide `black .` on a non-black-formatted codebase

**The Flaw:** The `format` pdm script runs `black .` across the whole backend, but the codebase was never black-formatted — the 2026-07-18 lint-debt cleanup (PR #47) used targeted autopep8 + hand fixes and explicitly REJECTED a full black run (60 files / 8.6k-line diff). Running `pdm run format` reformats ~64 files and re-exposes suppressed lint findings: black moves/reflows lines carrying `# noqa: C901` markers and introduces one-line `def` styling that trips E704, so `pdm run lint` goes red on files you never touched.

**Why It Matters:** An agent following a "format then lint" step churns the entire tree in one command; the resulting diff buries the real change, breaks `git blame`, and the re-exposed C901/E704 findings look like pre-existing lint debt rather than a consequence of the command just run.

**The Fix:** Never run `pdm run format` repo-wide. Format NEW files individually: `.venv/bin/black <file>` (verify with `.venv/bin/black --check <file>` + `.venv/bin/flake8 <file>`). Recovery if run by accident: `git restore app/backend/src` (untracked new files keep their formatting). Adopting black repo-wide remains a separate decision for Sam.

**Where It Bit Us:** Grafana Cloud migration Phase 3 (2026-07-18) — the plan's original "run `pdm run format`" step churned 64 files; fully reverted before commit.

---

### ENV-8: Gitignored credential files exist only in the main checkout — worktrees start without them

**The Flaw:** The 1Password-Environments-exported root `.env` (and every other gitignored credential file) lives only in `/Users/sam/Code/hangar-bay` — `git worktree add` copies tracked files, so agent worktrees under `.claude/worktrees/` never contain it. Compounding it, `.mcp.json`'s `${RENDER_API_KEY}` expansion happens once, at Claude Code LAUNCH, from the launching process's environment — a session started without the export has a dead Render MCP for its whole lifetime.

**Why It Matters:** The failure is silent and looks like an auth problem, not a file-location problem: the MCP answers `unauthorized`, `$RENDER_API_KEY` is empty in every Bash shell, and nothing points at the main checkout. It cost the M4 execution session its entire Phase 0 spike (2026-07-19).

**The Fix:** For the MCP: launch Claude Code from a shell that exported the env first (e.g. `set -a; . /Users/sam/Code/hangar-bay/.env; set +a` before `claude`). For curl/CLI use from ANY worktree: source the main checkout's file inside each Bash invocation that needs it (shell state does not persist across tool calls) — `set -a; . /Users/sam/Code/hangar-bay/.env; set +a` — then reference `$RENDER_API_KEY`. NEVER cat/echo/print the file or the variable, never copy it into a worktree, never commit it. **The 1Password-managed file can also transiently EMPTY mid-session and later repopulate** (observed 2026-07-27: a var that sourced fine minutes earlier came back length 0, then recovered): before concluding a key is gone, inspect names and value lengths only — `awk -F= '/^[A-Z]/ {print $1, length(substr($0, index($0,"=")+1))}' .env` — and retry after a minute.

**Where It Bit Us:** M4 execution session (2026-07-18/19): the Phase 0 Render spike was blocked all session and substituted with a docs-based verification (plan Deviation D-1) because the session ran from a worktree with no launch-time export.

---

### ENV-9: Postgres 18 moved PGDATA — a volume at `/var/lib/postgresql/data` blocks startup

**The Flaw:** Postgres 18 images store data in a major-version-specific subdirectory (`PGDATA=/var/lib/postgresql/18/docker`) and expect a single volume mounted one level up, at `/var/lib/postgresql`. The pre-18 convention — mounting at `/var/lib/postgresql/data` — is now actively rejected: the entrypoint treats a volume at that path as un-upgraded data from an older major and **refuses to start**, even when the volume is completely empty. Bumping the image pin without moving the mount is therefore a breaking change, not a version bump.

**Why It Matters:** Two distinct failures, and the second is the dangerous one. First, the container crash-loops with an error that reads like a data-migration problem ("this is usually the result of upgrading the Docker image without upgrading the underlying database"), sending you toward `pg_upgrade` when the actual fix is a one-line mount path. Second — and silently — if the container *did* start, the image's own `VOLUME /var/lib/postgresql` declaration means PGDATA lands in an **anonymous** volume while your named volume sits unused at the old path: data would not persist across `docker compose down`, and nothing would say so. The named-volume mount looks correct in `compose.yml` the whole time.

**The Fix:** Mount the parent: `- postgres_data:/var/lib/postgresql`. Verify with `docker inspect <container> --format '{{range .Mounts}}{{.Name}} -> {{.Destination}}{{"\n"}}{{end}}'` — the named volume must be the mount at `/var/lib/postgresql`, and `docker exec <container> sh -c 'echo $PGDATA; ls /var/lib/postgresql'` should show the major-version directory inside it. Existing data from an older major cannot be carried across by remounting; it needs `pg_upgrade` or, for disposable dev data, recreation (ENV-2 means the dev database is rebuilt on every backend start anyway).

**Where It Bit Us:** `7dce47f build(deploy): unify postgres at 18` changed the dev compose pin from `postgres:16-alpine` to `postgres:18-alpine` without moving the mount. It went unnoticed because CI runs Postgres as an ephemeral GitHub Actions service container with no volume mount at all, so CI stayed green while local dev was broken for anyone who recreated the volume. It surfaced on 2026-08-01 when the crash-looping container blocked local backend tests for a whole multi-agent session; the pre-existing volume also held PG 16 data, which masked the mount bug behind a genuine major-version mismatch.

---

### ENV-10: A container created from a worktree dies when that worktree is removed

**The Flaw:** `docker compose up` resolves relative bind-mount paths against the compose file's directory, so a container started from `.claude/worktrees/<slug>/app/backend/docker/` records **absolute** host paths into that worktree. Reclaiming the worktree after its PR merges — the normal, encouraged end of the workflow (see `docs/git-strategy.md`) — deletes the mount sources out from under a container that is still registered and still set to `restart: unless-stopped`.

**Why It Matters:** The container does not fail where you would look for it. It exits **127**, which reads as "command not found" and sends you hunting for a broken image or entrypoint; the real message is buried in `docker inspect`'s `.State.Error`, naming a path that no longer exists. Worse, the failure is deferred: the container runs fine for days or weeks and only dies at the next restart — the Docker daemon restarting, a Colima stop/start, a machine reboot — long after the worktree removal that caused it, so the two events are never associated. If the mount was a **gitignored credential file** (ENV-8), removing the worktree also destroyed the only copy, and recreating the container is blocked until it is regenerated from 1Password.

**The Fix:** Start long-lived dependency containers from the **main checkout**, never from a worktree — `docker compose -f /Users/sam/Code/hangar-bay/app/backend/docker/compose.yml ... up -d`. Before reclaiming a worktree, check nothing is bound to it: `docker ps -a --format '{{.Names}}' | xargs -I{} sh -c 'docker inspect {} --format "{{{{.Name}}}} {{{{range .Mounts}}}}{{{{.Source}}}} {{{{end}}}}"' | grep worktrees`. When you meet an exit-127 container, read `docker inspect <name> --format '{{.State.Error}}'` before anything else — it distinguishes a missing mount source from a genuinely missing binary.

**Where It Bit Us:** The `alloy` telemetry container was created from `.claude/worktrees/grafana-cloud-migration-5a5464/` during the Grafana Cloud migration (2026-07-19). The worktree was reclaimed when that work merged; alloy kept running until its next restart, then exited 127 and stayed dead for ~11 days unnoticed, silently ending local telemetry shipping. Discovered 2026-08-01. Recovery is blocked on regenerating `app/backend/docker/grafana-cloud.env` in the main checkout, since that gitignored file existed only inside the deleted worktree.

---

### §3.C — Review Checklist

- [ ] **Complex settings fields (e.g. `List[int]`) are supplied as JSON** — `AGGREGATION_REGION_IDS=[...]`; env is loaded from `app/backend/src/.env`; `ESI_USER_AGENT` is set; the single consolidated `core/config.py` Settings class is satisfied (ENV-1)
- [ ] **Empty data after a backend (re)start is not diagnosed as a frontend bug** — startup drops/recreates tables and re-ingests; give ingestion time before concluding a data bug (ENV-2)
- [ ] **After backend edits, run one clean cycle** — clear the Valkey aggregation lock, `touch main.py` once, hand off until ingestion completes; run dev servers as tracked background tasks with visible logs (ENV-3)
- [ ] **`Settings.model_config` keeps `extra="ignore"`** — any new config field is also documented in `.env.example` (ENV-4)
- [ ] **Backend venv/CI run Python 3.14** — the FastAPI 0.115 / Python-3.12 hold is resolved (ENV-5, superseded); keep the two CI `python-version` pins in sync and never mask interpreter warnings with a filter (migrate off the deprecated API instead)
- [ ] **Deleting a debug print/function also drops any module-level import it orphaned** — flake8 ignores F401 here so it won't catch it, but F811 will trip on an unrelated function (ENV-6)
- [ ] **No repo-wide `pdm run format`** — the codebase is not black-formatted; format new files individually with `.venv/bin/black <file>` (ENV-7)
- [ ] **Sessions needing platform credentials source the MAIN checkout's root `.env` per Bash call (worktrees lack it), and MCP servers with `${VAR}` config get the export at launch** — never print or copy the values (ENV-8)
- [ ] **A Postgres major-version bump moves the volume mount too — 18+ mounts at `/var/lib/postgresql`, not `/var/lib/postgresql/data`** (ENV-9)
- [ ] **Long-lived dependency containers are started from the MAIN checkout, and nothing is bind-mounted to a worktree before that worktree is reclaimed** (ENV-10)

---

# Section 4: External Integrations (ESI)

> **Reader context:** I'm adding or changing a call to EVE Online's ESI API — a data route, the SSO/JWT path, or an upstream health check.
>
> ESI removes legacy and unversioned routes on published dates. Code that names a specific version survives these removals; code that leans on `/latest` or legacy meta-routes breaks on the removal date with no change on our side.

---

### ESI-1: Pin explicit ESI route versions; avoid removed legacy/meta routes

**The Flaw:** ESI periodically retires unversioned and legacy routes. The "Spring Cleaning" removal (24 March 2026) dropped `/status.json`, `/swagger.json` (plus `/dev/`, `/_dev/`, `/legacy/`, `/_legacy/` variants), `/diff`, `/versions`, and `/headers`, and began redirecting `/verify` to `https://login.eveonline.com/v2/oauth/verify` (the redirect itself removed 28 April 2026). The `/latest/*` alias is soft-deprecated — its `swagger.json` is frozen and new routes appear only in the OpenAPI specs.

**Why It Matters:** A request built on any of these routes keeps working until the removal date, then fails with no code change on our side — the hardest kind of breakage to anticipate.

**The Fix:**
*   Pin an explicit version prefix on every ESI request (`/v1`, `/v3`, …), matching the `ESIClient` convention (`core/esi_client_class.py`). Never `/latest`.
*   For upstream health, use `/meta/status` (values `OK` / `Degraded` / `Down` / `Recovering`) — never the removed `/status.json`. See `design/specifications/observability-spec.md` §2.5.
*   Validate SSO JWTs offline against JWKS (`services/sso.py`), not by calling `/verify`.
*   Consume ESI data from the OpenAPI specs, not the removed legacy `swagger.json`.

**Where It Stands:** The backend already complies — every data route pins `/v1`/`/v3` and JWTs are validated offline, so Hangar Bay was unaffected by the 24 March 2026 removals. The lone `/latest` usage, the `generate-regions.mjs` build script, was pinned to `/v1`. References: "Spring Cleaning: legacy routes removed 24 March 2026" (https://developers.eveonline.com/blog/spring-cleaning-legacy-routes-removed-24-march-2026) and "A better view on status: improving ESI health monitoring" (https://developers.eveonline.com/blog/a-better-view-on-status-improving-esi-health-monitoring).

### ESI-2: `Expires` is being deprecated; read `Cache-Control` for cache lifetimes

**The Flaw:** ESI is converting routes from time-based expiry to **event-driven invalidation**. On a converted route the cache no longer turns over on a clock, so `Expires` "is no longer meaningful" — it is still emitted, but only for backward compatibility. Code that derives a cache TTL or a poll schedule from `Expires` keeps parsing a header that has quietly stopped describing anything.

**Why It Matters:** This fails silently and asymmetrically. Nothing errors; a wrong-but-plausible number comes out. Too long and we sit on a stale generation past the moment it changed; too short and we re-request needlessly, burning the error budget the 420 limiter meters. Worse, the failure arrives on **CCP's** schedule rather than ours — a route we already consume can convert between deploys, with no change on our side.

**The Fix:**
*   Prefer `Cache-Control: max-age` when the response states one; fall back to `Expires` only when it does not. This is both RFC 9111's precedence rule and ESI's stated direction.
*   Subtract `Age` from `max-age` — `max-age` is the response's total lifetime, not its remaining one, and ESI serves these through a shared cache that can hand over a response most of the way through it.
*   Treat an invalid `max-age` (unparseable, valueless, negative) as *absent* rather than as zero, so it falls back instead of collapsing the TTL.
*   `no-store` means do not store. `no-cache` does **not** — it requires revalidation before reuse, which a conditional-request cache already does; dropping storage for it forfeits the 304 savings for nothing.
*   Do not hard-code a TTL from a measured sample. The observed 1800 s on public contracts is one generation of one route, and the swagger documents up to 3600 s.

**Where It Bit Us:** Not yet, and the live headers say why (probed 2026-08-01). The routes Hangar Bay consumes have **not** converted: `/v1/contracts/public/{region}/`, `/v3/universe/types/{id}/` and `/v1/universe/groups/{id}/` all send a bare `Cache-Control: public` carrying no lifetime at all, alongside a real `Expires`. So `Expires` is still authoritative there and their TTLs are unchanged. `/v1/sovereignty/map/` shows the shape we are heading for — `cache-control: public, max-age=3600, must-revalidate, stale-if-error=900`, with `Expires` merely restating `Date + max-age`. `core/esi_client_class.py` (`_cache_ttl_seconds`) now reads Cache-Control first and falls back to Expires, so the conversion is a no-op for us whenever it lands. Reference: "Smarter caching: when events drive invalidation" (https://developers.eveonline.com/blog/smarter-caching-when-events-drive-invalidation), 2026-01-27, which converted `/characters/{id}/skills` and `/characters/{id}/skillqueue` first and states more routes follow "over the next few months".

> **Design consequence, unresolved:** the ingestion clean-sheet design (`docs/audits/m5-recon/ingestion-clean-sheet-design.md`) schedules discovery at each region's `Expires + ε`. That rests entirely on `Expires` staying meaningful on `/v1/contracts/public/{region}/`. It does today — that route is unconverted and regenerates lazily on a 1800 s cycle — but a conversion would remove the signal the scheduler is built on, not merely change its value. Re-check the live headers before implementing `Expires`-driven scheduling, and prefer deriving the poll instant from whichever header actually carries the lifetime.

---

### ESI-3: ESI omits fields instead of sending falsy values, so `== False` and range filters match nothing

**The Flaw:** ESI's public routes express "no" by *leaving the key out*, not by sending `false`/`0`. `is_blueprint_copy` arrives `true` on copies and is absent on everything else — it is never `false`. `for_corporation` is likewise present-and-`true` or absent. A `.get()` mapping therefore writes True-or-NULL into a nullable column, and the natural filter `column == False` matches **zero rows**, because SQL `NULL = FALSE` is NULL, not TRUE. The same shape hides a second trap: the PUBLIC and AUTHENTICATED contract-item routes are near mirror images, so a field copied from the wrong one is silently always-NULL.

**Why It Matters:** Both failures are *silent and total*. The filter returns HTTP 200 with an empty list, which reads as "no contracts match" rather than "this control is broken"; every layer above (schema, generated client, UI control) looks healthy. A filter reading an always-NULL column is worse still — it has no working branch at all, and a fixture that populates the column by hand makes the test suite agree that it works (testing-pitfalls TEST-18).

**The Fix:**
* Treat a nullable column fed by an optional ESI field as **tri-state**, and decide explicitly what NULL means. For a present-when-true flag, NULL means false — so `col == False` is always wrong. Note that `or_(col.is_(False), col.is_(None))` fixes only the NULL half; when the flag classifies a PARENT entity across a one-to-many join, that per-row form is still wrong for a second reason, and SQLA-3 gives the correct shape.
* Before filtering on any ingested column, confirm the route you actually call populates it. The public item route (`/v1/contracts/public/items/{id}/`) carries `is_blueprint_copy`, `runs`, `material_efficiency`, `time_efficiency`. The authenticated character/corporation item routes carry `raw_quantity` and `is_singleton` and **not** those four. `raw_quantity`'s documented `-1`/`-2` blueprint markers therefore do not exist on any data Hangar Bay ingests. Four such columns are kept on purpose — `contracts.status`, `contracts.date_completed`, `contract_items.is_singleton`, `contract_items.raw_quantity`: the authenticated routes populate all four, so **keep the column, and refuse to read it** until the writer that fills it exists. Each carries a model-level comment saying so; `docs/superpowers/specs/2026-08-01-contract-coverage-gap-analysis.md` §4.2 ("Keep them, don't drop them") records why dropping them was approved and then reversed.
* Verify against the retrieved spec plus a live sample, not from memory — the spec's prose is unreliable here (`collateral` is documented "for Couriers only" yet is present on every item_exchange contract, and `runs`'s documented `-1` for originals never occurs publicly; originals simply omit the field).

**Where It Bit Us:** `is_bpc=false` returned `total: 0` in production for the entire life of the filter (fixed 2026-08-01: `contract_service._has_blueprint_copy_item`, applied in `_apply_contract_filters`). The neighbouring `min_runs`/`max_runs` filter reads `ContractItem.raw_quantity`, a column no public payload can ever populate, and is inert for the same family of reasons. Verified against `https://esi.evetech.net/meta/openapi.json` and a live sample of 7,292 contracts / 1,658 item rows: `is_blueprint_copy` was `true` 1,396 times and absent 262 times — never once `false`.

### ESI-4: Omitting `X-Compatibility-Date` pins the client to the OLDEST published date

**The Flaw:** ESI replaced route versioning with a date header. A request that omits `X-Compatibility-Date` is not served "the current shape" — it is served the **oldest** date ESI still publishes, today `2020-01-01`. Hangar Bay sends no such header, so every call the `ESIClient` makes is answered from a five-year-old contract, chosen for us by default rather than by decision. CCP can raise that floor with notice, and the day they do, our routes change shape with no commit on our side.

**Why It Matters:** It is an unmanaged, invisible dependency in the exact shape of the traps this section already catalogues — nothing in the codebase names the date, nothing fails when it moves, and the effect lands at ingestion where a missing field becomes a NULL column rather than an error (ESI-3). It also silently withholds routes: `/meta/status`, which ESI-1 tells us to use for upstream health, **does not exist at `2020-01-01`**. It first appears at a later compatibility date, so adopting it requires sending the header, not just changing a URL. The same date range removes `/sovereignty/map` and renames `/route/{origin}/{destination}` — proof that the date dimension moves real routes, not just field descriptions.

**The Fix:**
*   **Send the header.** `Settings.ESI_COMPATIBILITY_DATE` is the one place the date is named, and `ESIClient.default_headers()` puts it on every request. Bumping it changes the shape of every ESI response, so treat a bump as its own reviewed change and read the monitor's diff first — never as a rider on unrelated work.
*   **Keep the sender and the watcher in lockstep.** The monitor duplicates the date as `PINNED_COMPATIBILITY_DATE` in `tools/esi_spec_monitor/monitor.py`, because that tool is standard-library only by design and cannot import `Settings`. `tests/core/test_esi_compatibility_date.py` fails if the two disagree. **A monitor watching a date the application does not request reports a safety it cannot see, which is worse than no monitor** — that test is the only thing preventing it, so do not weaken it to make a bump easier.
*   Treat the served date as a tracked value, not an accident. `app/backend/tools/esi_spec_monitor/` fetches `https://esi.evetech.net/meta/openapi.json` on a schedule, projects it down to the routes and fields we consume, and diffs that projection against a committed snapshot. The snapshot records the shape at the date we send and the shape at the newest published date, so "what changes if we adopt a newer date" is answerable without a spike — and a newly published date shows up as a diff in the newest view. Run it locally with `pdm run esi-spec-monitor` from `app/backend`; `--update` rewrites the snapshot, and that update belongs in a PR with a reason, like a lockfile bump.
*   Before adopting a route that is absent from the spec you are reading, check `https://esi.evetech.net/meta/compatibility-dates` and re-fetch the spec with the header set. An "ESI does not have that route" conclusion drawn from a header-less fetch is a conclusion about 2020, not about ESI.
*   Diff the **shape**, never the prose. The spec's `description` strings are unreliable (ESI-3: `collateral` is documented "for Couriers only" but ships on every item_exchange contract; `runs`'s documented `-1` for originals never occurs). The machine-readable `properties`, `required`, `security` and `x-server-cache-mode` fields have been accurate every time we have checked them against live payloads.
*   Diff a **projection**, not the whole document. The spec is 182 paths and churns constantly in areas we never call; a whole-spec diff produces noise, noise gets ignored, and an ignored monitor rots. The manifest at `tools/esi_spec_monitor/manifest.py` names the nine operations we consume and the fields each one feeds, so a failure can say which function breaks.

**Where It Stands:** **Resolved.** Hangar Bay sends `X-Compatibility-Date: 2026-07-21`, the newest published date, chosen deliberately rather than inherited. Nothing broke in the move: every route we consume was byte-identical from the old `2020-01-01` floor through `2026-07-21`, and all nine are unauthenticated. The pin unblocks `/meta/status`, which does not exist at the old floor and which ESI-1 wants for upstream health. One consequence to carry forward: `/route/{origin}/{destination}` is a hard cutover at `2025-09-30` — `GET` with query parameters below it, `POST` with a JSON body, renamed preference values and an object envelope at or above it, with the old shape returning 404. Any future work that calls `/route/` must use the POST form. The monitor exists so that the *next* date question does not require a spike. It replaces a set of VCR cassettes that were deleted in PR #110 — they had been intended to catch this class of drift and could not, because they recorded our own app talking to itself (testing-pitfalls TEST-14) and because a live sample can only reveal drift the sample happens to contain.

### §4.C — Review Checklist

- [ ] **Every ESI request names an explicit version prefix** (`/v1`, `/v3`, …), not `/latest` (ESI-1)
- [ ] **Upstream status checks target `/meta/status`, not the removed `/status.json`** (ESI-1)
- [ ] **SSO JWT validation is offline against JWKS, not a `/verify` round-trip** (ESI-1)
- [ ] **Cache lifetimes read `Cache-Control: max-age` first (less `Age`), with `Expires` only as fallback** (ESI-2)
- [ ] **No cache TTL or poll interval is hard-coded from a measured sample** (ESI-2)
- [ ] **Any new `Expires`-derived scheduling is checked against the live headers for that route first** (ESI-2)
- [ ] **Filters over ESI-fed nullable columns treat NULL explicitly** — a present-when-true flag is never sent as false, so `col == False` matches zero rows (ESI-3)
- [ ] **Every filtered column is actually populated by the route ingestion calls** — the public and authenticated contract-item routes carry disjoint field sets; `raw_quantity` is authenticated-only (ESI-3)
- [ ] **No response field is served that the ingesting route cannot populate** — a wire field that is always NULL or always a placeholder publishes information the corpus does not have, and every client that reads it inherits the lie. Drop it from the response schema; keep the COLUMN when a known future ingestion path would fill it (ESI-3)
- [ ] **A new or changed ESI dependency is added to `tools/esi_spec_monitor/manifest.py` in the same PR** — an endpoint or field outside the manifest is outside the drift monitor's lens (ESI-4)
- [ ] **A conclusion about what ESI does or does not offer is drawn from a spec fetched with an explicit `X-Compatibility-Date`** — a header-less fetch answers for the oldest published date, currently 2020-01-01 (ESI-4)
- [ ] **A snapshot update in `tools/esi_spec_monitor/snapshot.json` comes with a stated reason** — it is a lockfile-shaped artifact; re-generating it to silence a red run defeats the monitor (ESI-4)

---

# Section 5: Deployment & Platform

> **Reader context:** I'm wiring production configuration — platform-injected env vars, process topology, launch commands — for a managed host (Render or similar).

---

### DEPLOY-1: Managed platforms inject `postgresql://` URLs; the async stack needs `postgresql+asyncpg://`

**The Flaw:** Render (and most managed platforms) injects `DATABASE_URL` with the plain `postgresql://` scheme, but `create_async_engine` — both the app engine (`db.py`) and Alembic's CLI path (`alembic/env.py`) — requires the driver-qualified `postgresql+asyncpg://` scheme.

**Why It Matters:** The very first production boot (and the pre-deploy `alembic upgrade head`) dies on `sqlalchemy.exc.InvalidRequestError` before serving a request — a deploy that cannot come up at all, discovered only on the platform.

**The Fix:** Normalize in `Settings` — a `mode="before"` field validator on `DATABASE_URL` rewrites `postgresql://` → `postgresql+asyncpg://` (`core/config.py`). Never hand-edit platform-injected URLs; blueprint references stay untouched (I-5).

**Where It Bit Us:** M4 codex design review (pre-deploy, 2026-07-18) — caught before the first deploy; the spike-substitute docs verification confirmed Render's documented format is `postgresql://user:password@host:port/database`.

---

### DEPLOY-2: uvicorn stays `--workers 1` — the scheduler runs in-process

**The Flaw:** The APScheduler ingestion job runs inside the FastAPI process. N uvicorn workers = N schedulers racing the Valkey ingestion lock every tick.

**Why It Matters:** The fencing-tokened lock makes overlap a wasted-tick problem rather than data corruption, but N−1 workers burn every tick contending, logs fill with skip warnings, and the "single scheduler" operational invariant (I-3) silently becomes a lie that masks real double-scheduling bugs.

**The Fix:** Every production launch command pins `--workers 1` (Dockerfile CMD, any future Procfile). Scale reads by splitting the scheduler out into its own process/service — never by adding workers.

**Where It Bit Us:** Pre-empted in the M4 design (spec §2); the Dockerfile carries the constraint as an inline comment.

---

### DEPLOY-3: Durable coordination state must not live in an evicting cache (`allkeys-lru`)

**The Flaw:** APScheduler's job records lived in a `RedisJobStore` pointed at the production Valkey instance — the same instance configured `maxmemoryPolicy: allkeys-lru` (render.yaml; free tier ~25 MB) that absorbs the ESI ETag cache. State the system needs to KEEP was colocated with a cache explicitly licensed to delete any key under memory pressure.

**Why It Matters:** Eviction of jobstore keys is a *silent, total* scheduler outage: missing keys mean "no due jobs", so nothing fires and nothing errors. On 2026-07-23 an uncapped aggregation run ETag-cached 155k+ contract items, drove the instance into LRU eviction, and the jobstore keys were evicted with the rest — last scheduler tick `01:34:45Z Jul 23`, zero jobs fired for 3.6 days, zero error lines, stale data served while `/ready` correctly reported `data_stale`. Restarts revive it only because the lifespan re-registers jobs at boot.

**The Fix:** The scheduler uses an in-memory jobstore (`core/scheduler.py`; pinned by `tests/core/test_scheduler.py`): every job is re-registered on boot with `replace_existing=True`, so cache-backed persistence bought nothing while exposing scheduler state to eviction. The general rule: state whose loss is silent and must outlive cache pressure (job stores, durable queues, registries) never goes into an `allkeys-lru` instance — keep it in-process or in the database. Cross-run locks are the tolerable exception: they self-expire by design, and eviction merely widens a concurrency window the TTL already bounds — provided the TTL actually covers a real run. Every scheduled job's lock TTL therefore derives from that job's own interval plus a fixed margin, never a standalone constant: `services/background_aggregation.py` and `services/watchlist_matcher.py` each expose a `_lock_ttl_seconds()` doing exactly this. A TTL *equal* to the interval is the same defect in slow motion — it expires precisely as the next tick fires, so any run slower than one interval hands the lock to a concurrent runner. Pin it with a test that reconfigures the interval and asserts the TTL follows (a constant merely raised above today's interval passes a naive "TTL > interval" check and silently re-opens the gap when the interval grows).

**Where It Bit Us:** Production Render deployment, diagnosed 2026-07-26 from live logs: last tick logged `01:34:45Z` Jul 23, then 3.6 days of silence with the app serving stale data. The same logs surfaced the companion lock finding — a ~70-minute run overran the then-fixed 1800s lock TTL ("Aggregation lock token mismatch on release: the 1800s lock TTL likely expired mid-run…"), meaning the mutual-exclusion window was shorter than real run durations.

---

### DEPLOY-4: Pre-deploy migrations collide with in-flight ingestion; redeploy via the CD workflow, not a new commit

**The Flaw:** Migrations run as Render's pre-deploy command while the outgoing instance may hold a long ingestion transaction on `contracts`. A deploy triggered mid-run fails `pre_deploy_failed` ~38s after `pre_deploy_started` — the migration's `SET lock_timeout = '30s'` firing plus overhead — and the deploy aborts with the old code still serving.

**Why It Matters:** The failure looks alarming (a failed production deploy with `nonZeroExit: 1`) but is the *designed* outcome; the wrong responses are re-merging, reverting, or debugging the migration. The right response is pure timing. Conversely, a deploy that must not wait for a human needs a redeploy path that doesn't mint a new commit.

**The Fix:** Time deploys into the post-run idle window: poll `/ready` and treat a fresh `last_ingest_age_seconds` (< ~10 min) as the window opening. To redeploy the SAME commit (retry or rollback), use the CD workflow's dispatch input — `gh workflow run deploy.yml --ref main -f sha=<full-sha>` — production deploys are triggered by `.github/workflows/deploy.yml` calling the Render API, not by Render autoDeploy. The ~38s failure signature distinguishes lock collision from a real migration bug (which fails in seconds or with a stack trace in the pre-deploy logs). Note the ingestion run can also lose: a deadlock may pick the run as victim, which is acceptable — it retries next tick.

**Where It Bit Us:** Release PR #95 (2026-07-27): merged mid-run, `pre_deploy_failed` at 08:05:39Z (38s signature); the identical migrations applied cleanly on the idle-window redeploy at 08:26Z — confirming the mechanism empirically.

---

### DEPLOY-5: Two tasks each authoring a migration leave two heads, and `alembic upgrade head` refuses to run

**The Flaw:** `alembic/versions/` is a **linear chain** — every revision names the `down_revision` it was generated against. Two branches that each add a migration against the same parent both claim that parent, so once both are merged the chain has two heads and `alembic upgrade head` aborts with `Multiple head revisions are present for given argument 'head'`.

**Why It Matters:** This is a production failure, not a test failure, and it appears only *after* both branches are merged and green. `alembic upgrade head` is `render.yaml`'s `preDeployCommand`, so the next deploy aborts before the new code starts, leaving the old code serving. Neither branch's CI can catch it: each has exactly one head in isolation. The parallel decomposition that makes a feature fast to build is precisely what produces it.

**The Fix:** **All schema changes for one body of work are ONE migration, authored once, up front** — before the tasks that depend on it are dispatched. Treat `alembic/versions/` as a single-writer resource in any plan that fans work out to parallel agents. If a second head does land, do not hand-edit `down_revision` on a revision that has already been applied anywhere; generate a merge revision (`alembic merge -m "<why>" <head1> <head2>`). Confirm `alembic heads` prints exactly one line before merging anything that touches the directory.

**Where It Bit Us:** Not yet — recorded pre-emptively, which is the point: the first occurrence would be a failed production deploy. Identified while decomposing F008 Type-Aware Contract Browsing, whose natural four-way task split has each task writing its own migration; `design/features/F008-Type-Aware-Contract-Browsing.md` §7.1 ("Single-writer resources — constraints on how the plan may decompose") lists `alembic/versions/` first for this reason. The hazard is general to any multi-task schema work, which is why it belongs here and not only in that spec.

---

### DEPLOY-6: Dependabot does not index `pdm.lock` — zero backend alerts is silence, not health

GitHub's Dependabot alerts cover `app/frontend/web/package-lock.json` but not the backend's `pdm.lock`, so the repo's security tab can show zero Python alerts while the lock holds vulnerable pins. On 2026-08-06 a direct OSV audit found nine vulnerable locked versions — four in production scope, including the `cryptography` build backing pyjwt's EVE SSO token validation — none of them surfaced by GitHub. When triaging security posture, audit the backend lock directly: `pdm export -f requirements --without-hashes -o reqs.txt`, then batch-query the OSV API (or run `pip-audit -r`) against the pins. Treat "no Dependabot alerts" as a statement about the npm tree only.

---

### §5.C — Review Checklist

- [ ] **`DATABASE_URL` reaches the engine driver-qualified** — the Settings validator normalizes `postgresql://`; no code assumes the platform sends `+asyncpg` (DEPLOY-1)
- [ ] **Every production launch command pins `--workers 1`** — scaling proposals split the scheduler out instead of raising the worker count (DEPLOY-2)
- [ ] **Nothing the app must retain lives in the evicting Valkey** — job stores and other silent-loss durable state stay out of `allkeys-lru` instances; every cross-run lock TTL derives from that job's own interval plus a margin (never equal to the interval, never a standalone constant) and is pinned by a test that reconfigures the interval and asserts the TTL follows (DEPLOY-3)
- [ ] **Deploys are timed into the post-ingestion idle window, and same-commit redeploys go through the CD workflow's `workflow_dispatch` `sha` input** — a `pre_deploy_failed` ~38s in is the lock_timeout collision signature, not a migration bug (DEPLOY-4)
- [ ] **`alembic heads` prints exactly one revision** — work split across parallel tasks authored its schema changes as a single migration up front, rather than one per task (DEPLOY-5)
- [ ] **The backend lock was audited directly (OSV or pip-audit over a `pdm export`), not inferred clean from Dependabot** — Dependabot does not index `pdm.lock`, so its silence covers only the npm tree (DEPLOY-6)

---

# Section 6: Frontend State & Rendering

> **Reader context:** I'm building or reviewing the React SPA — how URL state, cached server data, and what the user actually sees line up.
>
> The theme here is a mismatch in TIME: URL state changes on click, server data changes when the request lands, and anything derived from the wrong one of those describes the screen wrongly for the whole gap between them.

---

### WEB-1: A view shape read from live URL state describes rows fetched under the previous one

**The Flaw:** The query layer holds the previous response on screen while the next one loads (`placeholderData: keepPreviousData`), but the component derives what the rows MEAN — the column set, the units, the labels, the empty-state copy — from the live URL/filter state. The URL changes on click; the rows change when the response lands. In between, the rows are described under rules that were never true of them.

**Why It Matters:** This does not render as "loading" or as missing data — it renders as confident, specific falsehood, and it lasts as long as the request does (this app's unfiltered list has measured multi-second production latency; the refresh treatment is a 60% opacity fade, not a blanked table). Every honesty rule the view has can be inverted at once: a value under the wrong column header is a wrong *number*, and a placeholder like `Unknown structure` — reserved for a real field that genuinely could not be resolved — becomes a fabrication about a row that has no such field at all. Nothing in the component looks wrong in review, because each half is individually correct, and no test sees it unless a test deliberately holds a response open.

**The Fix:** Derive the view key inside the query function, so it is cached with the rows it selected and travels with them through every placeholder, refetch, and cache hit. The key must be a function of the query key (which the request params already fix), or it will drift on its own:

```ts
const segment = activeSegment(search)          // a pure function of the search
return useQuery({
  queryKey: ['contracts', 'list', query],
  queryFn: async () => ({ ...(await fetchPage(query)), segment }),
  placeholderData: keepPreviousData,
})
// consumers read data.segment, never activeSegment(search)
```

`select` is NOT a fix: it runs against placeholder data with the current options closure, so it re-applies the incoming shape to the outgoing rows — the same bug. Controls that express the user's own *selection* (a toggle's pressed state, the heading, the document title) SHOULD keep reading the live URL: those must answer the click immediately. The rule is narrower than "never read the URL" — it is that anything **describing the rows** follows the rows.

**Where It Bit Us:** F008 Task C4 (2026-08-07). Per-segment column sets landed while the page still chose them with `columnsFor(activeSegment(search))`. Before C4 the column set was segment-invariant, so reading it from the URL had been harmless for the life of the component — the defect was introduced by the feature that made the derived value vary, not by the line that was changed. Caught in review; the reproduction is a component test that never resolves the courier response and asserts the header set over the previous rows.

---

### §6.C — Review Checklist

- [ ] **Anything that describes the rows is derived from the response, not from live URL state** — column sets, units, labels, and empty-state copy come off the query result; only the user's own selection state reads the URL (WEB-1)
- [ ] **A newly-varying derived value was audited at its existing read sites** — a value that used to be constant has read sites nobody checked, because until now they could not be wrong (WEB-1)
- [ ] **The in-flight window has a test** — one lane holds a response open across the transition rather than asserting only the settled states on either side (WEB-1)

---

## Orchestration

Pitfalls that arise when a session dispatches parallel subagents and consolidates their output. The canonical rules live in `docs/git-strategy.md` → §Multi-agent coordination → Output persistence. This section is the discovery hook for plan writers who arrive here via the `writing-plans-enhanced` (or equivalent) mandated-read path — it does NOT restate the rules in full.

### ORCH-1: Analysis Dispatches Must Persist Findings Before Returning

**Trigger:** Your plan dispatches parallel subagents (bug hunts, audits, phased analysis, parallel investigations) whose findings would be expensive to regenerate if lost.

**What you need to do:** Every such dispatched subagent MUST write its complete report to a persistent file BEFORE returning; the response message is not the sole record.

**Read the full rule:** `docs/git-strategy.md` → §Multi-agent coordination → Output persistence. That section carries the copy-pasteable prompt block (with `<PERSISTENCE_PATH>` substitution), file-path conventions, orchestrator commit cadence, and the cases where the rule doesn't apply.

**Why this is in implementation-pitfalls:** because the plan-writing skill mandates reading this file, and this rule has to be noticed at plan-write time (when the dispatch prompts are being drafted), not at execution time (when it's too late). The failure mode — orchestrator context compacting mid-consolidation and lossily dropping findings — is predictable and preventable if the plan author builds persistence into the dispatch prompts from the start.

### §Orchestration.C — Review Checklist

- [ ] **Dispatch prompts include the mandatory-persistence block** — copy from `docs/git-strategy.md` §Output persistence; substitute `<PERSISTENCE_PATH>` with a durable per-subagent path (ORCH-1)
- [ ] **Plan specifies exact persistence paths, not "write somewhere useful"** — ambiguous paths default to `/tmp` under pressure, which doesn't survive (ORCH-1)
- [ ] **Orchestrator commits subagent artifacts wave-by-wave** — committed files land on the campaign branch before consolidation begins (ORCH-1)

---

# Appendix A: Historical Changelog

## 2026-08-07 — SQLA-5 added: on-conflict copy decays enrichment-derived values

- Added SQLA-5 (an upsert that copies supplied columns on conflict writes a degraded run's NULLs over previously-stored enrichment values). Third variant of the same trap in one function: after the `is_ship_contract` ETag-304 decay (fixed by omitting maintained columns) and the station-system read-back, a partial `/universe/names` map blanked all four denormalized name columns for every re-sighted contract (F008 decision log D10, flagged by codex in the PR-A review, deferred there, fixed in PR #142 with `preserve_on_null`/COALESCE semantics in `bulk_upsert`).

## 2026-08-07 — Section 6 opened with WEB-1: view shape must follow the rows, not the URL

- Added Section 6 (Frontend State & Rendering) and WEB-1. Found in review of F008 Task C4: per-segment column sets shipped while the page still chose them from the live URL, so `keepPreviousData` rendered the previous segment's rows under the incoming segment's columns for the length of the request — reporting a sale's price as a hauling reward and inventing an unresolvable destination for a contract with no route.
- The general shape is the reason it earned a section rather than a footnote: the read site had been correct for the life of the component and was falsified by a *different* change making the derived value vary. Phase D adds more per-segment surface against the same hook.

## 2026-08-07 — SQLA-4 added: SQLAlchemy errors carry bind values into `str()`

- Added SQLA-4. Found in review of F008 Task B10: the four contract-search log sites had just been changed to report the search string's LENGTH instead of its text, and the commit claimed the text never reaches a log line — but the failure site's `error_message=str(e)` sat in the same record, and a `StatementError`'s `str()` appends `[parameters: {...}]` from the statement holding that very text as an `ILIKE` bind. Closed at the source with `hide_parameters=True` on the application engine (which also covers `main.py`'s global handler and the traceback it logs) plus a render-time scrub at the log site.
- Paired with testing-pitfalls TEST-21, the reason the shipped test could not see it: the injected failure was a `RuntimeError`, whose `str()` has no parameters to leak.

## 2026-08-06 — DEPLOY-6 added: Dependabot does not index pdm.lock

- Added DEPLOY-6. Triage of five open Dependabot alerts (all npm, all undici) included a due-diligence OSV audit of the backend lock, which found nine vulnerable pins Dependabot had never surfaced — four in production scope, including the cryptography build backing EVE SSO token validation. All but a plugin-capped pytest advisory were fixed in the same PR; the entry records the blind spot so future triage never reads GitHub's zero as a backend result.

## 2026-08-02 — DEPLOY-5 added: parallel tasks each authoring a migration break the deploy

- Added DEPLOY-5. Recorded pre-emptively rather than after an incident: the failure mode is a `preDeployCommand` abort in production, and the first occurrence would already be a failed deploy with the old code still serving.
- Surfaced while decomposing F008, where the natural four-way task split has each task generating its own migration against the same parent. F008's decomposition-constraints section already listed `alembic/versions/` as a single-writer resource; the hazard is general to any multi-task schema work, so it is lifted here where a reviewer meets it on the normal path.

## 2026-08-01 — ESI-3's response-schema rule applied at the item level

- No new entry. `ContractItemSchema` still served `is_singleton` and `raw_quantity` after the contract-level pair (`status`, `date_completed`) was removed — the same always-empty wire fields one level down, violating the §4.C checklist bullet sitting beside them. Both are gone from the response schema; the columns and their model-level comments stay, per the keep-the-column-refuse-to-read-it decision in the ESI-3 fix.
- Nothing read either field: no frontend component, only four unit-test mocks and the e2e wire fixture, all moved with the wire shape. `min_runs`/`max_runs` still filter on `ContractItem.raw_quantity` — a query concern, unaffected — so `test_filter_by_bpc_runs` now asserts the matched contract rather than a field the response no longer carries.

## 2026-08-01 — ENV-10 added: containers bind-mounted to reclaimed worktrees

- Added ENV-10. The `alloy` telemetry container was created from the `grafana-cloud-migration-5a5464` worktree; reclaiming that worktree removed its bind-mount sources, and alloy exited 127 at its next restart and stayed dead ~11 days unnoticed. Exit 127 reads as "command not found"; the real cause is only in `docker inspect`'s `.State.Error`. Recovery is blocked on regenerating the gitignored `grafana-cloud.env` in the main checkout (ENV-8).

## 2026-08-01 — ENV-9 added: Postgres 18 volume mount path

- Added ENV-9. `7dce47f` bumped the dev compose pin from `postgres:16-alpine` to `postgres:18-alpine` without moving the volume mount; Postgres 18 stores data at `PGDATA=/var/lib/postgresql/18/docker` and refuses to start when a volume is mounted at the pre-18 `/var/lib/postgresql/data`, even an empty one. `compose.dependencies.yml` now mounts the parent. CI was unaffected throughout (ephemeral service container, no volume), which is why it stayed green while local dev was broken.

## 2026-08-01 — ESI-4 added: the compatibility-date floor, and a monitor for spec drift

- Added ESI-4. Building a drift monitor surfaced that omitting `X-Compatibility-Date` is not "no opinion" — it pins the client to the OLDEST published date (`2020-01-01`), a floor CCP can raise with notice. It also explains a puzzle in ESI-1: `/meta/status` is absent from a header-less spec fetch and appears only at a later date, so adopting it needs the header, not just the URL.
- Landed `app/backend/tools/esi_spec_monitor/` — a manifest of the nine operations we consume, a projection of the published spec down to those, a committed snapshot, and a daily GitHub Actions job that diffs them and files a self-closing issue. The comparison logic carries 35 unit tests against constructed fixture specs, mutation-verified.
- Deliberately NOT a live-ESI test lane. The VCR cassettes deleted in PR #110 were the previous attempt at this and failed twice over (testing-pitfalls TEST-14); beyond that, detecting a spec lie live requires the sample to contain the case, which is inherently flaky, and flaky monitors get muted.
- The monitor's manifest records five fields our ingestion reads that no public ESI route documents: `status` and `date_completed` on contracts, `raw_quantity` and `is_singleton` on contract items (`runs` remains unimplemented). Recorded as known-absent rather than fixed — see the ESI-3 note above on `raw_quantity`.

## 2026-08-01 — SQLA-3 added; ESI-3's prescribed fix corrected

- Added SQLA-3 (a per-row predicate over a one-to-many join classifies the CHILD, not the parent, so a condition and its negation can both match the same parent). Found by adversarial review of PR #98: the first `is_bpc=false` fix corrected the NULL half but kept the per-item form, so a contract bundling a BPC with a hull matched `is_bpc=true` AND `is_bpc=false`. Re-fixed as a correlated EXISTS negated for the false branch, which also removes the filter's join and with it the SQLA-1 pagination hazard.
- Corrected ESI-3's prescribed fix: it recommended `or_(col.is_(False), col.is_(None))`, which repairs only the NULL half and is still wrong for a parent-classifying flag. It now points at SQLA-3 for that case.
- Added testing-pitfalls TEST-19 (single-child fixtures cannot detect parent-vs-child predicate errors).

## 2026-08-01 — ESI-2 added: `Expires` deprecated by event-driven invalidation

- Added ESI-2 from CCP's 2026-01-27 caching dev blog: on converted routes `Expires` survives only for backward compatibility and `Cache-Control` is authoritative. `_cache_ttl_seconds` in `core/esi_client_class.py` now reads `max-age` (less `Age`) first and falls back to `Expires`, with `no-store` suppressing storage and `no-cache` deliberately not doing so.
- Live header probe (2026-08-01) recorded in the entry: none of the routes we consume have converted — they send a bare `Cache-Control: public` with no lifetime — so the change is a no-op today and arms us for the conversion. `/v1/sovereignty/map/` already shows the post-conversion shape.
- Flagged the consequence for the ingestion clean-sheet design, whose per-region discovery scheduling is built on `Expires` for `/v1/contracts/public/{region}/`.

## 2026-08-01 — ESI-3 and FASTAPI-3 added: optional-field shapes and over-strict response schemas

- Added ESI-3 (ESI omits fields instead of sending falsy values, so `col == False` matches zero rows; and the public vs authenticated contract-item routes carry disjoint field sets) after `is_bpc=false` was found returning `total: 0` in production for the whole life of the filter. Fixed in `services/contract_service.py`; verified against the retrieved `meta/openapi.json` plus a live sample of 7,292 contracts / 1,658 item rows in which `is_blueprint_copy` was never once `false`. Numbered ESI-3 because ESI-2 was concurrently taken by the Cache-Control migration (PR #101).
- Added FASTAPI-3 (a response field stricter than its own nullable column 500s the entire page, not just the row) from `ContractSchema.start_location_id`, a bare `int` over a nullable column fed by an ESI field that is not in the public-contracts `required` array.
- Recorded the same root cause on the verification side as testing-pitfalls TEST-18 (fixtures that write columns ingestion never writes). The absolute-future-date trap found alongside it was already recorded on dev as TEST-17, so it is not duplicated here.
- Grepped for further instances of the ESI-3 shape: `min_runs`/`max_runs` read `ContractItem.raw_quantity`, which no public ESI payload can populate — left inert and reported rather than fixed, since populating it needs the `runs` field ingested (schema + migration).

## 2026-07-27 — DEPLOY-4 added; ENV-8 extended with the transient-empty .env mode

- Added DEPLOY-4 (pre-deploy migration vs in-flight ingestion collision; the ~38s `pre_deploy_failed` signature; same-commit redeploy via the CD workflow's `workflow_dispatch` `sha` input) from the PR #95 release: first attempt failed exactly as designed, idle-window redeploy applied the same migrations cleanly.
- Extended ENV-8: the 1Password-managed root `.env` can transiently empty mid-session and repopulate — check names/value-lengths (never values) before concluding a credential is gone.

## 2026-07-26 — DEPLOY-3 added: jobstore keys evicted by the allkeys-lru Valkey

- Added DEPLOY-3 (durable coordination state must not share an `allkeys-lru` cache) from the Jul 23–26 production incident: LRU eviction deleted the `RedisJobStore` keys and the scheduler went silent for 3.6 days with zero errors. Fix shipped in the same PR: in-memory jobstore (`core/scheduler.py`) + aggregation lock TTL derived from the scheduler interval (`services/background_aggregation.py`), both TDD-pinned.
- Generalized DEPLOY-3's lock-TTL rule from the aggregation lock to every scheduled job, and sharpened it: a TTL *equal* to the interval is the same defect (it expires exactly as the next tick fires), and the pinning test must reconfigure the interval — a constant raised above today's interval passes a naive "TTL > interval" assertion. Applied to the watchlist matcher, whose TTL equalled its interval (`services/watchlist_matcher.py` `_lock_ttl_seconds()`; the standalone `WATCHLIST_MATCH_LOCK_TTL_SECONDS` setting was removed as dead config).

## 2026-07-19 — ENV-8 added: worktrees lack gitignored credential files

- Added ENV-8 (gitignored credential files exist only in the main checkout; `${VAR}` MCP expansion is launch-time-only) from the M4 execution session, where it silently blocked the Phase 0 Render spike for the whole session. Fix pattern: launch-time export for MCP, per-Bash-call sourcing of `/Users/sam/Code/hangar-bay/.env` for CLI use, never printing values.

## 2026-07-19 — DEPLOY-1/DEPLOY-2 added: managed-platform URL scheme + single-worker topology

- Added Section 5 (Deployment & Platform) with DEPLOY-1 (`postgresql://` → `postgresql+asyncpg://` normalization in Settings) and DEPLOY-2 (uvicorn `--workers 1`; in-process scheduler) from M4 Phase 3 (plan Task 3.12). DEPLOY-1's fix is implemented and tested (`core/config.py` validator, `test_config.py`); DEPLOY-2 is carried by the production Dockerfile CMD.

## 2026-07-18 — ENV-7 added: repo-wide `pdm run format` trap

- Added ENV-7 from the Grafana Cloud observability migration (`docs/superpowers/plans/2026-07-18-grafana-cloud-observability.md`): `pdm run format` = `black .` churns ~64 files on this non-black codebase and re-exposes noqa'd C901s plus E704. Cross-referenced from the migration plan's Deviations and session memory.

## 2026-07-18 — SQLA-2 added: partial-index ON CONFLICT needs index_where

- Added SQLA-2 (`ON CONFLICT` against a partial unique index must restate the index predicate) from the M3 account-features work (Phase 10, Task 10.1). Pre-empted in the watchlist-matcher design (`docs/superpowers/specs/2026-07-17-m3-account-features-design.md` §4.4); pairs with testing-pitfalls.md TEST-11.
- Grepped the backend for other `on_conflict` sites: the only partial-index target is `services/watchlist_matcher.py` (already restates `index_where`); `services/auth_service.py` and `services/db_upsert.py` target full unique constraints / primary keys, so SQLA-2 does not apply to them.

## 2026-07-13 — ENV-5 superseded: FastAPI-current / Python-3.14 migration

- Lifted the FastAPI 0.115 hold: migrated the backend to FastAPI 0.139 / Starlette 1.3.1 (+ `prometheus-fastapi-instrumentator` 8.0.2, required for Starlette ≥1.0 — its 7.1.0 middleware crashes against Starlette 0.52.x despite a `starlette<1.0` pin). FastAPI 0.139 precomputes the dependant coroutine flag and no longer calls the 3.14-deprecated `asyncio.iscoroutinefunction`, eliminating the 16 DeprecationWarnings at the source (no filter mask). Flipped the backend venv and both CI `python-version` pins 3.12 → 3.14.
- Marked ENV-5 `SUPERSEDED` (kept its original body + the pydantic-relock context as history); rewrote the §3.C checklist item to the current 3.14 invariant and updated the Appendix B status row.

## 2026-07-12 — M2 additions: ENV-4, ENV-5, ENV-6; ENV-1 two-Settings text retired

- Added ENV-4 (pydantic-settings rejects unknown `.env` keys unless `extra="ignore"`) and ENV-5 (backend venv/CI pin Python 3.12 until the FastAPI 0.115 hold lifts) from the M2 EVE SSO plan (Phase 9, Task 9.2).
- Added ENV-6 (F811 cascade when removing debug prints/functions whose sole job consumed a module-level import) — a trap discovered twice during M2 Phase 1 settings consolidation (DISC-EXEC-2).
- Retired ENV-1's "two divergent Settings classes" claim (its "Also note" paragraph and the §3.C checklist line): M2 Phase 1 consolidated `fastapi_app/config.py` and `fastapi_app/core/config.py` into the single `core/config.py` Settings, so the setup-docs-must-satisfy-both text was false. ENV-1's JSON-decode trap itself is unchanged and remains live.

## 2026-07-12 — Restructured to the pitfalls-docs template

- Migrated this file to the standard template shape: added §How to Use, Table of Contents, per-section Review Checklists, the Orchestration §ORCH-1 universal entry, and Appendices A/B/C (summary table + maintenance framework).
- **Preserved all existing project entries with their IDs and facts:** FASTAPI-1, SQLA-1, FASTAPI-2, PROXY-1, ENV-1, ENV-2, ENV-3. Entries were regrouped into domain sections (API & Request Binding; Data & Persistence; Environment & Dev Loop) and reformatted into the Flaw → Why → Fix → Where-It-Bit-Us shape without dropping content or renumbering.

## 2026-07-12 — Testing infra & dev-loop traps recorded

- ENV-3 hardened with the Valkey-lock clean-cycle procedure after a detached-server / stale-log debugging session.

## 2026-07-11 — Adversarial spec review

- FASTAPI-1 discovered: ID-list `ContractFilters` params were GET-body-bound and unreachable from browser clients.

---

# Appendix B: Unified Summary Table

| ID | Title | Severity | Status | Domain |
|----|-------|----------|--------|--------|
| FASTAPI-1 | `Depends(Model)` sends list fields to the GET body | HIGH | VALIDATED | API & Request Binding |
| FASTAPI-2 | Declared-but-unimplemented filter params ship dead controls | MEDIUM | UNIMPLEMENTED | API & Request Binding |
| FASTAPI-3 | Response schema stricter than its column 500s the whole page | HIGH | VALIDATED | API & Request Binding |
| PROXY-1 | Trailing-slash 307 escapes a prefix-rewriting proxy | MEDIUM | VALIDATED | API & Request Binding |
| SQLA-1 | Paginating a joined query paginates joined rows | HIGH | VALIDATED | Data & Persistence |
| SQLA-2 | ON CONFLICT vs a partial unique index needs index_where | HIGH | VALIDATED | Data & Persistence |
| SQLA-3 | A per-row predicate over a one-to-many join cannot classify the parent | HIGH | VALIDATED | Data & Persistence |
| SQLA-4 | A SQLAlchemy error carries the failed statement's bind values into `str()` | HIGH | VALIDATED | Data & Persistence |
| SQLA-5 | An on-conflict copy decays enrichment-derived values on degraded runs | HIGH | VALIDATED | Data & Persistence |
| ENV-1 | pydantic-settings JSON-decodes complex env fields early | MEDIUM | VALIDATED | Environment & Dev Loop |
| ENV-2 | Backend restart wipes and re-ingests all data | LOW | VALIDATED | Environment & Dev Loop |
| ENV-3 | --reload + ingestion + Valkey lock interact badly in dev | MEDIUM | VALIDATED | Environment & Dev Loop |
| ENV-4 | pydantic-settings rejects unknown .env keys unless extra="ignore" | MEDIUM | VALIDATED | Environment & Dev Loop |
| ENV-5 | FastAPI 0.115 / Python-3.12 hold (resolved 2026-07-13: FastAPI 0.139 + Python 3.14) | LOW | SUPERSEDED | Environment & Dev Loop |
| ENV-6 | F811 cascade when removing debug prints/functions | LOW | VALIDATED | Environment & Dev Loop |
| ENV-7 | `pdm run format` is repo-wide black on a non-black codebase | LOW | VALIDATED | Environment & Dev Loop |
| ENV-8 | Gitignored credential files exist only in the main checkout | MEDIUM | VALIDATED | Environment & Dev Loop |
| ENV-9 | Postgres 18 moved PGDATA; volume must mount at /var/lib/postgresql | MEDIUM | VALIDATED | Environment & Dev Loop |
| ENV-10 | Container bind-mounted to a worktree dies (exit 127) when it is reclaimed | MEDIUM | VALIDATED | Environment & Dev Loop |
| ESI-1 | Pin ESI route versions; avoid removed legacy/meta routes | LOW | VALIDATED | External Integrations (ESI) |
| ESI-2 | `Expires` deprecated by event-driven invalidation; read `Cache-Control` | MEDIUM | VALIDATED | External Integrations (ESI) |
| ESI-3 | ESI omits fields rather than sending falsy values; `== False` matches nothing | HIGH | VALIDATED | External Integrations (ESI) |
| ESI-4 | No `X-Compatibility-Date` pins the client to the oldest published date | MEDIUM | VALIDATED | External Integrations (ESI) |
| DEPLOY-1 | Managed platforms inject postgresql:// URLs; async stack needs +asyncpg | HIGH | VALIDATED | Deployment & Platform |
| DEPLOY-2 | uvicorn stays --workers 1 (in-process scheduler) | MEDIUM | VALIDATED | Deployment & Platform |
| DEPLOY-3 | Durable coordination state must not live in an evicting cache | HIGH | VALIDATED | Deployment & Platform |
| DEPLOY-4 | Pre-deploy migrations collide with in-flight ingestion; redeploy via CD dispatch | MEDIUM | VALIDATED | Deployment & Platform |
| DEPLOY-5 | Parallel tasks each authoring a migration leave two alembic heads; `upgrade head` aborts the deploy | HIGH | UNIMPLEMENTED | Deployment & Platform |
| DEPLOY-6 | Dependabot does not index pdm.lock; backend deps need a direct OSV/pip-audit pass | MEDIUM | VALIDATED | Deployment & Platform |
| WEB-1 | A view shape read from live URL state describes rows fetched under the previous one | HIGH | VALIDATED | Frontend State & Rendering |
| ORCH-1 | Analysis Dispatches Must Persist Findings | HIGH | VALIDATED | Orchestration |

Severity levels: `CRITICAL` (production data loss / security), `HIGH` (correctness bug under predictable conditions), `MEDIUM` (correctness bug under edge cases), `LOW` (cleanliness / clarity / dev-loop hazard).

Status values: `VALIDATED` (prescribed fix is implemented and tested), `UNIMPLEMENTED` (pitfall documented but fix not yet in code), `SUPERSEDED` (replaced by another entry or no longer applicable).

> **Note:** Severity and status above were inferred from each entry's text during the 2026-07-12 restructure (FASTAPI-2 is marked `UNIMPLEMENTED` because its inert `min/max_me/te` params still ship). Adjust when you next audit against the code.

---

# Appendix C: Document Maintenance Guide

## When to Update This Document

Update this document when any of the following occur:

| Trigger | Action |
|---------|--------|
| Bug hunt finds a generalizable pattern | Add a pitfall to the appropriate domain section |
| Health review flags a cross-cutting issue | Add or strengthen a pitfall |
| Implementation reveals a prescribed fix was wrong | Update the existing pitfall to match reality — the code is the source of truth |
| Code review catches a pitfall already documented here | Strengthen the entry with the new example |
| A pitfall's prescribed fix is implemented | Update the entry's status in Appendix B |
| A feature is removed or an approach abandoned | Mark the pitfall as SUPERSEDED with a note explaining why |
| testing-pitfalls.md adds a new section | Check if a cross-reference should be added here |

**Do NOT update this document for:**

- One-off implementation bugs that don't generalize to a pattern
- Code style preferences or formatting choices
- Performance optimizations without correctness implications

---

## How to Add a Pitfall

### Step 1: Choose the domain section

If the pitfall spans two domains, place it where the reader is most likely to look when they encounter the bug. Add a "See Also" cross-reference in the other section.

### Step 2: Assign the next ID

IDs are sequential within each section's prefix (`FASTAPI-3`, `ENV-4`, etc.). Check the last entry with that prefix and increment. Use a short prefix that matches the domain (2-7 letters, uppercase, descriptive). Existing IDs are load-bearing — they are referenced from handoff docs, CLAUDE.md, and session memory. Never renumber an existing entry.

### Step 3: Write the entry

**For complex findings** (non-obvious failure mode or architectural fix):

```markdown
### PREFIX-N: Title

**The Flaw:** What the code does wrong or what's missing.
**Why It Matters:** The production failure mode — what breaks, for whom, and why it's hard to detect.
**The Fix:** The specific code change or pattern to apply. Include a code example when the fix is non-trivial.
**Where It Bit Us:** The concrete incident and its provenance (date / review), if any.
```

**For simple findings** (one-line pattern substitution, self-evident why):

```markdown
### PREFIX-N: Title
[One paragraph: what's wrong, what to do instead, and why. No code example needed.]
```

**Use the right heuristic:** If an implementing agent could correctly apply the fix from just a one-line description without understanding the failure mode, use the condensed format. If they'd need to understand WHY to apply it correctly, use the full format.

### Step 4: Update the review checklist

Add a checkbox item to the section's review checklist (§X.C) that captures the key check for this pitfall.

### Step 5: Update the Table of Contents

Update the entry list in the TOC table (e.g., `FASTAPI-1, FASTAPI-2` becomes `FASTAPI-1, FASTAPI-2, FASTAPI-3`).

### Step 6: Update the Summary Table

Add a row to Appendix B with the pitfall ID, title, severity, status, and domain.

### Step 7: Check for cross-references

- Does testing-pitfalls.md need a corresponding test guidance entry?
- Does another domain section need a "See Also" pointer?
- Does the same pattern exist elsewhere in the codebase? Grep for other instances.

---

## How to Update an Existing Pitfall

1. **Read the current entry** and understand its intent
2. **Check the code** to see what actually changed
3. **Update the entry** to reflect reality — never preserve a prescription that contradicts the code
4. **Update Appendix B** status if it changed (e.g., `UNIMPLEMENTED` → `VALIDATED`)
5. **Check Appendix A** — add a changelog line noting the update date and reason

---

## How to Mark a Pitfall as Superseded

Do NOT delete pitfall entries. Mark them:

```markdown
### PREFIX-N: Title

> **SUPERSEDED (YYYY-MM-DD):** [Reason — e.g., "Feature removed in Phase 12" or "Replaced by PREFIX-M which covers the broader pattern"]

[Original content preserved below for historical context]
```

Update Appendix B status to `SUPERSEDED`.

---

## Completeness Checklist

**A pitfall update is not complete until ALL of these are done.** Partial updates are how this document drifts — and a drifted document is worse than no document, because it creates false confidence in protections that don't exist.

- [ ] Entry written in the correct domain section with the correct format
- [ ] Entry has the next sequential ID for its prefix (existing IDs never renumbered)
- [ ] TOC entry list updated
- [ ] Appendix B summary table row added/updated
- [ ] Review checklist (§X.C) updated with the corresponding check item
- [ ] Cross-references checked: testing-pitfalls.md, other domain sections, See Also block
- [ ] If the pattern could exist elsewhere in the codebase: grepped for other instances
- [ ] Appendix A changelog updated with date and source

**If you skip any of these steps, the next agent to read this document will not find your pitfall.** The TOC is the routing table — without it, your entry is invisible. The summary table is the audit trail — without it, the next health review won't know your finding was addressed.

---

## Voice and Style Reference

This document uses persuasion principles to ensure agents follow critical practices:

- **Authority** for bright-line rules: "MUST", "Never", "Always", "No exceptions"
- **Implementation intentions** for triggers: "When writing a query-param model, ALWAYS use `Annotated[Model, Query()]`"
- **Social proof via failure modes**: "Without this, the ID-list filters are unreachable from any browser client — every time"
- **Commitment** via checklists: the review checklists at the end of each section

When writing pitfall entries, apply these principles. A pitfall that says "consider using X" will be ignored under pressure. A pitfall that says "MUST use X — without it, Y happens every time" will be followed.

Reference: the `superpowers:writing-skills` skill (or equivalent in your skill library) carries the full persuasion-principles framework if you want to go deeper.
