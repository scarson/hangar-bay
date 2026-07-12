# Frontend Rebuild Milestone 1 — Public Contract Browsing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the abandoned Angular frontend with a working React SPA foundation that renders real contract data end-to-end, after fixing the two backend bugs that make the existing API unusable from a browser.

**Architecture:** Vite SPA (React 19, TypeScript strict, Tailwind CSS v4) at `app/frontend/web/`, talking to the existing FastAPI backend through a `/api/v1`-stripping dev proxy. TanStack Router (file-based) holds all filter/sort/pagination state in typed URL search params; TanStack Query owns all server state; API types are generated from the backend's OpenAPI schema. Two surgical backend bugfixes (query-param binding for ID-list filters; pagination over distinct contract IDs) with HTTP-level regression tests precede the frontend work.

**Tech Stack:** FastAPI 0.115 / SQLAlchemy 2 / pytest + pytest-asyncio (backend); React 19, Vite, TypeScript, Tailwind CSS v4, @tanstack/react-router + router-plugin, @tanstack/react-query, openapi-typescript + openapi-fetch, Vitest + React Testing Library, ESLint flat + eslint-plugin-jsx-a11y + Prettier (frontend).

**Spec:** `docs/superpowers/specs/2026-07-11-frontend-rebuild-milestone-1-design.md` — the authoritative scope statement. Where this plan and the spec disagree, the spec wins; record the discrepancy as a Deviation.

**Branch/worktree:** execute on `claude/hangar-bay-frontend-rebuild-2e4fe7` (this worktree). Tasks are sequential — 1→11 — unless a banner says otherwise. Task 3 depends on Task 1; Task 6 depends on Task 3; Tasks 7–9 depend on 4–6.

---

## Living Document Contract

This plan is a living document. Every executing agent MUST update it as
execution progresses, not only at completion.

- **On phase claim:** the executor MUST flip the banner to 🚧 IN PROGRESS
  with a claim timestamp (ISO 8601 UTC) and the active branch name. The
  banner MUST NOT include an expected-completion estimate — agents cannot
  reliably estimate their own wall-clock, and a fabricated duration
  becomes a stale anchor that misleads future readers. Followers
  encountering a 🚧 banner determine liveness by observable signals (PR
  existence, recent branch commits), not by arithmetic on expected times.
  See Step 5's stale-claim reclaim protocol.
- **On phase ship:** the executor MUST update that phase's **Execution
  Status** banner with the shipped commit SHA(s) and date. If a PR is
  open, the PR number and URL MUST appear in the top-of-plan Execution
  Status table.
- **On phase defer:** the executor MUST update the banner with ⏸ status
  AND a prose description of the unblock condition + a link to the
  likely-unblocker artifact (plan page, task, or PR whose own Execution
  Status banner will signal completion). Prose + link is durable across
  paraphrases and scope edits; exact-string coordination between agents
  is not.
- **On PR merge:** the executor MUST record the merge SHA in the banner
  + the top-of-plan Execution Status table.
- **On deviation from the written plan** (scope edits, structural
  refactors, dropped tasks, reordered phases): the executor MUST
  inline-document the deviation in the affected task AND summarize it
  in the top-of-plan Execution Status as a "Deviations" subsection.
  Deviation state MUST NOT live only in PR notes or status reports.
- **On discovery** (pre-existing drift surfaced during execution, new
  bugs found, architectural issues noted): the executor MUST add a
  "Discoveries" subsection at the top of the plan with pointers to the
  files/lines affected. Follow-up dispatches read this subsection to
  avoid duplicate discovery work.

The plan SHOULD reflect reality at the end of every session that touches
it. Anything worth putting in a status report to the user is worth
putting in the plan.

Rationale: `/writing-plans-enhanced` Step 5. Writing at ship time is
cheap; reconstruction by downstream readers is expensive, compounds
across dispatches, and fails silently when state is split across PR
notes and commit messages.

---

## Execution Status

**Overall:** ✅ All three phases shipped and gate-reviewed; milestone exit (superpowers:finishing-a-development-branch) is the only remaining step. The follow-on phase is `/impeccable`.

| Phase | Status | Ship SHA(s) | Notes |
|---|---|---|---|
| 1 — Backend enablement fixes | ✅ Shipped | `598dd22`, `c854668`, `31f4a37`, `e10b109`, `c051add` | Tasks 1–3 shipped on `claude/hangar-bay-frontend-rebuild-2e4fe7`. Group review complete (≥3 rounds); 3 minor findings (plan bookkeeping staleness, TEST-1 system/station/is_bpc coverage gap, FASTAPI-2 inert-param schema markers) remediated in the follow-up `fix(task-gate)` commit `c051add` (inert-param schema markers, 5 new HTTP/pagination tests, re-exported `openapi.json`). |
| 2 — Frontend scaffold | ✅ Shipped | `b17b24c`, `ec07568`, `7420c77`, `c9d1d2d`, `58a9df5`, `448dc53`, `528ca95`, `ecaf2fa`, `4fa9438` | Tasks 4–8 shipped; Fable gate approved after 3 fix rounds (negative-price URL sanitization, NaN-id no-request test, plan bookkeeping). Final: 29 frontend tests, lint + strict build green. |
| 3 — Acceptance, teardown, docs | ✅ Shipped | `afbd1bf`, `54956dd`, `1e6c763`, `657e804`, `662a0ba`, `8f82036`, `d8a737a`, `7882b8d`, `b708fe6` | Tasks 9–11 shipped 2026-07-12. Task 9 acceptance PASSED against live data (fixes `afbd1bf` region stamp + `54956dd` blank-title label; record `1e6c763`). Task 10 Angular teardown (`657e804`, review fix `662a0ba`). Task 11 docs (`8f82036`, review fix `d8a737a`). Group review complete (this gate); round-1 findings remediated in `7882b8d` (which also shipped CONTRIBUTING.md content fixes — env block + eight repointed links), round-2 findings (detail-page blank-title fix, Discovery undercount, this backfill) in `b708fe6`; round 3 clean (nits only). Final verification at milestone exit: backend 38 passed, frontend 31 passed, lint + strict build green. |

### Discoveries

- **Ingestion never persisted region IDs** (found in Task 9, fixed at `afbd1bf`): the aggregation
  loop fetches contracts per region but never wrote `start_location_region_id`, so the column was
  NULL for ALL real ingested data and the region filter matched nothing in production — while
  every fixture-based test passed (fixtures set the column by hand; the TEST-1 trap one layer
  down: the gap only appears when the real pipeline, not a fixture, writes the row). Fixed by
  stamping the fetch region onto each ESI payload (`_hb_region_id`) and mapping it in
  `_process_contracts`; first-ever tests added for the aggregation mapping. **Still open:**
  `start_location_system_id` has the same gap (needs station→system resolution, which the
  pipeline doesn't do) — acceptable for M1 since system filters are deferred, but it must be
  fixed before any milestone exposes system filtering.
- **`primaryLabel` renders an empty link for contracts with `title: ""`** (found in Task 9):
  real ESI data carries empty-string titles (not null), which `??` doesn't catch, and non-ship
  contracts often have no resolvable item `type_name`. Fixed during Task 9 (see its notes).
- **Real-data nuance:** ingested contracts include non-ship contracts (`is_ship_contract: false`)
  and items with unresolved `type_name`; the M1 UI displays them as-is. Worth a product decision
  (default ship-only filter?) during the /impeccable phase — F001/F002 center on ship contracts.
- **Residual Angular-as-current guidance survives across five specs the pre-/impeccable
  follow-up docs pass must cover** (found during the Phase 3 gate; extended at the round-2 gate
  after the prescribed case-insensitive scan turned up two more files the original list of three
  undercounted). Three are wholly outside Task 11's file scope; security-spec.md is likewise
  outside it; accessibility-spec.md was in the docs-pass scope (the milestone's pass was scoped by
  the M1 spec's Teardown list to only test/accessibility/i18n-spec.md and got its §3.4/§3.5
  React-idiom note), yet two Angular residuals inside it survived — Task 11 Deviation 4 logged
  them as "incidental phrasing", which understates a full Angular Forms code block. Run the
  case-insensitive `grep -rin '\bangular\b'` across all of `design/specifications/` to confirm the
  full list before the /impeccable phase leans on any of them:
  - `design/specifications/design-spec.md` — presents Angular as the current frontend framework at
    lines ~57, 121, 156–157, 164, 167, 256, 263, 269, 327, 339 (`@angular/localize`,
    Angular Material/CDK, RxJS, "Leverage Angular's Capabilities"). **Closed 2026-07-12 by this
    commit** — all ten sites rewritten to the shipped React 19/Vite/Tailwind v4/TanStack stack
    (mirroring README's Core Technologies); the original Angular choice retained as a past-tense
    History note; frontend i18n stated as deferred per the M1 spec's Non-goals (no library invented).
  - `design/specifications/performance-spec.md` — §2.2 (Frontend Load & Interaction Times
    (Angular)), §3.2 (Frontend (Angular): lazy-loaded Angular modules, Angular CLI build
    optimizations, `@angular/cdk/scrolling`, Angular Material), and the checklist line ~165
    ("When generating Angular components, use `OnPush`, `trackBy`…"). **Closed 2026-07-12 by this
    commit** — §2.2 relabeled for React (targets untouched), §3.2 rewritten to the shipped build
    reality (Vite production build: tree-shaking/minification via Rollup + esbuild; route-level
    code splitting already active via TanStack Router `autoCodeSplitting`), the virtualization
    requirement kept with library selection explicitly deferred to the /impeccable design phase,
    and the §6 anti-patterns + §7 checklist converted to React equivalents.
  - `design/specifications/observability-spec.md` — §frontend metrics/tracing at lines 43, 59, 62,
    66, 76, 104 (Angular `HttpClient`/OpenTelemetry instrumentation patterns). **This file was
    missed by the plan's Step 11.5 grep even when run repo-wide** because that grep is
    case-sensitive (`ng serve\|Angular CLI\|angular`) and observability-spec.md carries only
    capital-A `Angular` tokens with no lowercase `angular`/"Angular CLI" match. A follow-up docs
    pass should use a case-insensitive scan (`grep -rin '\bangular\b'`) across all of
    `design/specifications/`.
  - `design/specifications/security-spec.md` — presents Angular as the current frontend at §3.2
    "Output Encoding (Frontend - Angular)" (lines 163–169, `DomSanitizer`/`bypassSecurityTrustHtml`
    patterns), the Angular `ErrorHandler` pattern (lines 211–212), and the `npm/Angular` dependency
    bullets (lines 225–237, `npm audit` framed as the Angular toolchain). Flagged by the prescribed
    case-insensitive scan; outside the M1 spec's Teardown scope, so left unedited this milestone.
  - `design/specifications/accessibility-spec.md` — retains a literal Angular Forms code sample at
    §3.3 "AI Implementation Pattern (Input Assistance - Angular Forms)" (lines 100–105, with
    `*ngIf`/`[formControl]`/`[attr.aria-*]`) and Angular i18n AI-guidance at §3.5 (lines 116, 118,
    `i18n-aria-label`/"Angular's localization"). Task 11 Deviation 4 recorded these as "incidental
    phrasing", understating a full code block CONTRIBUTING.md tells AI agents to "pay close
    attention to". Outside the M1 spec's Teardown scope for code-sample rewrites — the /impeccable
    docs pass must replace them with React patterns.
- **Angular-as-current residue also survives in `design/features/`** (found 2026-07-12 by the
  design/performance-spec follow-up's broader `git grep -n "@angular"` verification): the feature
  specs still give `@angular/localize`/Angular-pipe i18n guidance as current AI instruction —
  `00-feature-spec-template.md` (~lines 195, 218), `F002` (~196, 236–237, incl.
  `@angular/cdk/collections`), `F003` (~131, 162), `F004` (~246, 274, 321). Outside that
  follow-up's authorized scope (design-spec/performance-spec/test-spec only), so left unedited;
  the /impeccable docs pass or the pre-i18n-milestone pass should update them alongside the
  observability/security/accessibility residues above.

---

## Universal task requirements

Every task below inherits these blocks. They are not repeated verbatim in each task to keep the plan readable, but they are **mandatory**:

**BEFORE starting any task:**
1. Invoke /superpowers:test-driven-development
2. Read `docs/pitfalls/testing-pitfalls.md` and `docs/pitfalls/implementation-pitfalls.md`
Follow TDD: write failing test → implement → verify green.

**BEFORE marking any task complete:**
1. Review tests against `docs/pitfalls/testing-pitfalls.md`
2. Verify test coverage (error paths? edge cases?)
3. Run tests and confirm green

**Assertion rigor (applies to every task that writes tests, especially Tasks 2, 7, 8):**
If any test assertion races, flakes, or fails nondeterministically, the fix is deterministic synchronization or deterministic fixture data (see TEST-2/TEST-3) — NOT assertion removal or weakening. If synchronization cannot make the assertion pass reliably, STOP and raise to the dispatching agent. Do not ship a weaker test. Weakened assertions rationalized as "CI stability fixes" are the exact pattern this rule prevents. Prefer mechanism assertions over symptom assertions; when racing forces a choice, fix the synchronization rather than dropping the mechanism assertion. Commit subjects touching test assertions state what happened to them ("add", "strengthen", "preserve", or explicitly "weaken" with rationale).

**After completing each phase (group review):**
Review the phase's batch of commits from multiple perspectives (correctness, test rigor, spec fidelity). Minimum 3 review rounds. If round 3 still finds issues, keep going until clean.

---

## Phase 0 prerequisite — backend test environment

**Execution Status:** ✅ DONE — executed out-of-band by the workflow harness. The test environment (Postgres + Valkey in Docker, `app/backend/src/.env` with `DATABASE_URL_TESTS` → `hangar_bay_test`) was provisioned before Phase 1, and the green baseline (24 passed) was run prior to any Phase 1 code change. Steps 0.1/0.2 below are checked to reflect that; no separate Phase 0 commit exists because the harness owns provisioning.

Backend tests need a real Postgres. Before Phase 1:

- [x] **Step 0.1: Confirm the backend test suite runs at all**

`app/backend/src/.env` must contain a `DATABASE_URL_TESTS` entry pointing at a scratch Postgres database (the test fixture drops/recreates all tables per test — never point it at a database with data you care about), e.g.:

```
DATABASE_URL_TESTS=postgresql+asyncpg://postgres:postgres@localhost:5432/hangar_bay_test
```

Create the database if needed: `createdb hangar_bay_test` (or via docker — see `app/backend/docker/`).

- [x] **Step 0.2: Run the existing HTTP filter tests as a green baseline**

Run: `cd app/backend && pdm run pytest src/fastapi_app/tests/api/test_contract_filters.py -q`
Expected: all tests PASS. If they fail for environment reasons, fix the environment before touching code — Phase 1's TDD signal depends on a green baseline. If they fail for code reasons, STOP and report; that's a Discovery.

---

## Phase 1 — Backend enablement fixes

**Execution Status:** ✅ SHIPPED — branch `claude/hangar-bay-frontend-rebuild-2e4fe7`. Tasks 1–3 shipped: Task 1 (`598dd22`, + review fixups `c854668`), Task 2 (`31f4a37`), Task 3 (`e10b109`). Group review complete (≥3 rounds); it surfaced 3 minor findings — stale plan bookkeeping, a TEST-1 HTTP-coverage gap on `system_ids`/`station_ids` and page-boundary pagination under the `is_bpc` trigger, and FASTAPI-2 inert-param (`min_me`/`max_me`/`min_te`/`max_te`) schema markers — all remediated in the follow-up `fix(task-gate): address review findings` commit `c051add` (which also re-exported `app/frontend/web/openapi.json`). No code-behavior regressions found; the SQL pagination change was verified correct under each `needs_item_join` trigger.

Two contract-preserving bugfixes + the OpenAPI export script. All backend work happens in `app/backend/`; run all pytest commands from that directory.

### Task 1: Bind the four ID-list filters as repeated query params

**Files:**
- Modify: `app/backend/src/fastapi_app/api/contracts.py:26-28`
- Modify: `app/backend/src/fastapi_app/schemas/contracts.py:109` (comment only)
- Test: `app/backend/src/fastapi_app/tests/api/test_contract_filters.py`

**Context:** `ContractFilters` is injected via `Depends(ContractFilters)`. FastAPI binds its scalar fields to query params but the four `Optional[List[int]]` fields (`region_ids`, `system_ids`, `station_ids`, `type_ids`) to the GET **request body** — repeated query params are silently ignored, and browsers can't send a GET body (pitfall FASTAPI-1). FastAPI 0.115+ supports query-param models via `Annotated[Model, Query()]`, which binds ALL fields — including lists — as query params. The service layer (`contract_service.py`) already handles the lists correctly; only the HTTP binding is broken, which is why only HTTP-level tests can cover this (pitfall TEST-1).

Do NOT add per-field `Query()` defaults inside the Pydantic model, and do NOT change any filter semantics — the fix is the endpoint annotation only.

- [x] **Step 1.1: Write the failing tests**

Append to `app/backend/src/fastapi_app/tests/api/test_contract_filters.py` (module already has `pytestmark = pytest.mark.asyncio`; the `setup_contracts` fixture in `conftest.py` creates contracts 101/102/104 in region 10000002 and contract 103 in region 10000020, with a Venture item `type_id=17480` only on 103):

```python
async def test_filter_by_region_ids_repeated_query_params(
    client: AsyncClient, setup_contracts
):
    """Regression (FASTAPI-1): list filters must bind as repeated query params."""
    response = await client.get("/contracts/?region_ids=10000020")

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert [c["contract_id"] for c in data["items"]] == [103]


async def test_filter_by_multiple_region_ids(client: AsyncClient, setup_contracts):
    response = await client.get("/contracts/?region_ids=10000002&region_ids=10000020")

    assert response.status_code == 200
    assert response.json()["total"] == 4


async def test_filter_by_type_ids_repeated_query_params(
    client: AsyncClient, setup_contracts
):
    response = await client.get("/contracts/?type_ids=17480")

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["contract_id"] == 103


async def test_id_list_filters_are_query_params_in_openapi_schema():
    """The generated schema must expose the ID lists where browser clients can use them."""
    from fastapi_app.main import app

    schema = app.openapi()
    operation = schema["paths"]["/contracts/"]["get"]

    assert "requestBody" not in operation
    param_names = {p["name"] for p in operation["parameters"]}
    assert {"region_ids", "system_ids", "station_ids", "type_ids"} <= param_names
```

- [x] **Step 1.2: Run them to verify they fail for the right reason**

Run: `pdm run pytest src/fastapi_app/tests/api/test_contract_filters.py -q -k "region_ids or type_ids or openapi_schema"`
Expected: `test_filter_by_region_ids_repeated_query_params` and `test_filter_by_type_ids_repeated_query_params` FAIL on the `total` assertions (filter silently ignored → all 4 contracts returned where 1 expected); the schema test FAILS on `requestBody not in operation`. `test_filter_by_multiple_region_ids` PASSES even before the fix (both regions together cover all 4 fixture contracts — it exists to guard against over-filtering after the fix, not to detect the bug). If the failures look different (e.g. 422s), STOP and investigate before proceeding.

- [x] **Step 1.3: Implement the fix**

In `app/backend/src/fastapi_app/api/contracts.py`, change the import line and the endpoint signature:

```python
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
```

```python
@router.get("/", response_model=PaginatedResponse[ContractSchema])
async def list_public_contracts(
    filters: Annotated[ContractFilters, Query()],
    db: AsyncSession = Depends(get_db),
):
```

(The `filters` parameter has no default, so it must come before `db`. Everything else in the endpoint body stays as-is.)

In `app/backend/src/fastapi_app/schemas/contracts.py`, replace the false comment on line 109 (`# ID lists - FastAPI handles string-to-list conversion for query params`) with:

```python
    # ID lists — bound as repeated query params via Annotated[ContractFilters, Query()]
    # in the endpoint (see pitfall FASTAPI-1: bare Depends() sends lists to the GET body).
```

- [x] **Step 1.4: Run the new tests, then the full backend suite**

Run: `pdm run pytest src/fastapi_app/tests/api/test_contract_filters.py -q`
Expected: PASS (all, including pre-existing tests — the annotation change must not alter scalar-param behavior).
Run: `pdm run pytest -q`
Expected: PASS. (`test_contracts.py` tests marked `esi_live`/`vcr` replay from cassettes; if any fail for cassette reasons unrelated to this change, note it as a Discovery — do not "fix" cassettes in this task.)

- [x] **Step 1.5: Commit**

```bash
git add app/backend/src/fastapi_app/api/contracts.py app/backend/src/fastapi_app/schemas/contracts.py app/backend/src/fastapi_app/tests/api/test_contract_filters.py
git commit -m "fix(api): bind ID-list filters as repeated query params, add HTTP regression tests

Bare Depends(ContractFilters) sent Optional[List[int]] fields to the GET
request body; repeated query params were silently ignored and browsers
cannot send a GET body. Annotated[ContractFilters, Query()] (FastAPI
0.115+ query-param models) binds every field as a query param."
```

### Task 2: Paginate over distinct contract IDs when the item join is active

**Files:**
- Modify: `app/backend/src/fastapi_app/services/contract_service.py:154-177`
- Test: `app/backend/src/fastapi_app/tests/api/test_contract_filters.py`

**Context:** When `needs_item_join` is true (`search`, `type_ids`, `is_bpc`, `min/max_runs`, or `sort_by=ship_name`), the service outer-joins `contract_items` and applies `offset/limit` to the joined rows, de-duplicating only afterwards with `.unique()` (`contract_service.py:167-177`). A contract with N matching items occupies N joined rows, so pages come up short and contracts can be skipped or duplicated across page boundaries, while the count query (lines 131-135, which is correct — leave it alone) reports distinct totals (pitfalls SQLA-1, TEST-4). Fix: when the join is active, first select the page of **distinct contract IDs** (grouped, ordered by an aggregate of the sort column, with `contract_id` as a deterministic tiebreaker), then load those contracts with their items and restore the page order. The no-join path keeps plain offset/limit (it was never broken) plus the same tiebreaker for deterministic ordering.

Do NOT touch the count query, the filter section, logging, or the exception handling. Do NOT change the response shape.

- [x] **Step 2.1: Write the failing test**

Append to `test_contract_filters.py`. The fixture makes every contract match the search term via TWO items each (guaranteeing joined-row duplication), with strictly ordered prices and IDs so ordering assertions are deterministic (pitfall TEST-3):

```python
from datetime import datetime, timedelta, timezone

from fastapi_app.models import Contract, ContractItem


async def test_pagination_with_search_returns_full_distinct_pages(
    client: AsyncClient, db_session: AsyncSession
):
    """Regression (SQLA-1/TEST-4): offset/limit must apply to distinct contracts,
    not joined rows. Three contracts x two matching items each; size=2 must give
    pages of [2, 1] contracts with no overlap."""
    now = datetime.now(timezone.utc)
    for n, cid in enumerate((201, 202, 203)):
        db_session.add(
            Contract(
                contract_id=cid, title=f"Grid Pack {cid}", price=(n + 1) * 1_000_000,
                collateral=0.0, status="outstanding", type="item_exchange",
                issuer_id=1, issuer_corporation_id=1, for_corporation=False,
                is_ship_contract=True, start_location_id=60003760,
                date_issued=now, date_expired=now + timedelta(days=7),
                items=[
                    ContractItem(
                        record_id=cid * 10 + 1, type_id=587,
                        type_name="Gridrunner Alpha", quantity=1,
                        is_included=True, is_singleton=False,
                    ),
                    ContractItem(
                        record_id=cid * 10 + 2, type_id=588,
                        type_name="Gridrunner Beta", quantity=1,
                        is_included=True, is_singleton=False,
                    ),
                ],
            )
        )
    await db_session.flush()

    base = "/contracts/?search=Gridrunner&size=2&sort_by=price&sort_direction=asc"
    page1 = (await client.get(f"{base}&page=1")).json()
    page2 = (await client.get(f"{base}&page=2")).json()

    assert page1["total"] == 3
    assert page2["total"] == 3
    ids1 = [c["contract_id"] for c in page1["items"]]
    ids2 = [c["contract_id"] for c in page2["items"]]
    assert len(ids1) == 2, f"page 1 short: {ids1}"
    assert len(ids2) == 1, f"page 2 wrong length: {ids2}"
    assert set(ids1) & set(ids2) == set(), "contract duplicated across pages"
    assert set(ids1) | set(ids2) == {201, 202, 203}, "contract skipped"
    assert ids1 == [201, 202], "price-asc order violated"


async def test_pagination_sorted_by_ship_name_no_duplicates(
    client: AsyncClient, db_session: AsyncSession
):
    """ship_name sort forces the item join even without filters; same invariants,
    with contract_id as the tiebreaker when the aggregate sort key ties."""
    now = datetime.now(timezone.utc)
    for cid in (301, 302, 303):
        db_session.add(
            Contract(
                contract_id=cid, title=f"Hull Lot {cid}", price=1_000_000,
                collateral=0.0, status="outstanding", type="item_exchange",
                issuer_id=1, issuer_corporation_id=1, for_corporation=False,
                is_ship_contract=True, start_location_id=60003760,
                date_issued=now, date_expired=now + timedelta(days=7),
                items=[
                    ContractItem(
                        record_id=cid * 10 + 1, type_id=587,
                        type_name="Atron", quantity=1,
                        is_included=True, is_singleton=False,
                    ),
                    ContractItem(
                        record_id=cid * 10 + 2, type_id=588,
                        type_name="Breacher", quantity=1,
                        is_included=True, is_singleton=False,
                    ),
                ],
            )
        )
    await db_session.flush()

    base = "/contracts/?sort_by=ship_name&sort_direction=asc&size=2"
    ids1 = [c["contract_id"] for c in (await client.get(f"{base}&page=1")).json()["items"]]
    ids2 = [c["contract_id"] for c in (await client.get(f"{base}&page=2")).json()["items"]]

    assert ids1 == [301, 302]
    assert ids2 == [303]
```

(Check the file's existing imports first: `AsyncClient` is already imported; add `from sqlalchemy.ext.asyncio import AsyncSession` plus the `datetime`/model imports shown above only if not already present.)

- [x] **Step 2.2: Run to verify failure**

Run: `pdm run pytest src/fastapi_app/tests/api/test_contract_filters.py -q -k pagination`
Expected: both tests FAIL. The search test fails with a short page 1 (joined-row pagination), e.g. `page 1 short: [201]`. The ship_name test's pre-fix failure shape is nondeterministic (its joined sort key is fully tied, so the database's row order decides which assertion trips — it may fail on page-2 contents, e.g. `ids2 == [303, 301]`, rather than a short page). Either shape is the expected bug signature; only a PASS here would be surprising.

- [x] **Step 2.3: Implement the fix**

In `contract_service.py`, replace the `--- Data Query ---` block (lines 154-177, from `sort_column = SORT_MAP.get(...)` through `contracts = result.scalars().unique().all()`) with:

```python
        # --- Data Query ---
        # Apply sorting and pagination to get the specific page of results.
        sort_column = SORT_MAP.get(filters.sort_by)
        if sort_column is None:
            # Fallback to default or raise an error for an unsupported sort key
            sort_column = Contract.date_issued

        descending = filters.sort_direction == SortDirection.desc

        if needs_item_join:
            # Paginating the joined query directly would offset/limit over
            # joined (duplicated) rows, producing short pages and contracts
            # skipped or repeated across page boundaries. Paginate over
            # distinct contract IDs first, then load that page's contracts.
            # Ordering uses an aggregate of the sort column (min/max picks
            # the sort-direction-appropriate representative when a contract
            # has multiple items) with contract_id as a deterministic
            # tiebreaker.
            sort_aggregate = func.max(sort_column) if descending else func.min(sort_column)
            order_expr = sort_aggregate.desc() if descending else sort_aggregate.asc()
            id_query = (
                query.with_only_columns(Contract.contract_id)
                .group_by(Contract.contract_id)
                .order_by(order_expr, Contract.contract_id.asc())
                .offset((filters.page - 1) * filters.size)
                .limit(filters.size)
            )
            id_result = await db.execute(id_query)
            page_ids = [row[0] for row in id_result.all()]

            data_query = (
                select(Contract)
                .where(Contract.contract_id.in_(page_ids))
                .options(selectinload(Contract.items))
            )
            result = await db.execute(data_query)
            contracts = list(result.scalars().unique().all())
            # Restore the page order computed by id_query.
            position = {cid: index for index, cid in enumerate(page_ids)}
            contracts.sort(key=lambda contract: position[contract.contract_id])
        else:
            order_expr = sort_column.desc() if descending else sort_column.asc()
            data_query = (
                query.order_by(order_expr, Contract.contract_id.asc())
                .offset((filters.page - 1) * filters.size)
                .limit(filters.size)
                .options(selectinload(Contract.items))
            )
            result = await db.execute(data_query)
            contracts = result.scalars().unique().all()
```

Notes: `query.with_only_columns(...)` (SQLAlchemy 2.0) keeps the accumulated joins and WHERE clauses while swapping the selected columns. An out-of-range page yields `page_ids == []` and `in_([])` correctly returns no rows. `func` and `select` are already imported in this module.

- [x] **Step 2.4: Run the new tests, then the full suite**

Run: `pdm run pytest src/fastapi_app/tests/api/test_contract_filters.py -q`
Expected: PASS — including the pre-existing sort tests (`test_sort_by_price_asc` etc.), which must survive the added `contract_id` tiebreaker. If a pre-existing ordering test fails, the fixture likely has tied sort keys — per TEST-2/TEST-3, fix by making the assertion account for the documented tiebreaker, never by deleting the assertion.
Run: `pdm run pytest -q`
Expected: PASS.

- [x] **Step 2.5: Commit**

```bash
git add app/backend/src/fastapi_app/services/contract_service.py app/backend/src/fastapi_app/tests/api/test_contract_filters.py
git commit -m "fix(service): paginate distinct contracts under item join, add page-boundary regression tests

offset/limit previously applied to joined contract_items rows: pages came
up short and contracts were skipped/duplicated across boundaries whenever
search/type_ids/is_bpc/runs filters or ship_name sort were active. Now
pages of distinct contract IDs are selected first (grouped, aggregate-
ordered, contract_id tiebreaker), then hydrated. Count query unchanged."
```

### Task 3: OpenAPI export script for frontend codegen

**Files:**
- Create: `app/backend/src/export_openapi.py`
- Modify: `app/backend/pyproject.toml` (add pdm script)
- Test: `app/backend/src/fastapi_app/tests/test_export_openapi.py`

**Context:** Frontend codegen needs the OpenAPI schema as a file, without requiring a running server. Importing `fastapi_app.main` requires env vars (pitfall ENV-1), so the script provides safe dummy defaults via `os.environ.setdefault` — real env, when present, always wins. Output goes to `app/frontend/web/openapi.json` (committed, so frontend builds never need a Python environment). Depends on Task 1 — the exported schema must contain the fixed query params.

- [x] **Step 3.1: Write the failing test**

Create `app/backend/src/fastapi_app/tests/test_export_openapi.py`:

```python
import json
import subprocess
import sys
from pathlib import Path

BACKEND_SRC = Path(__file__).resolve().parents[2]  # .../app/backend/src
SCRIPT = BACKEND_SRC / "export_openapi.py"


def test_export_openapi_writes_usable_schema(tmp_path):
    out = tmp_path / "openapi.json"

    result = subprocess.run(
        [sys.executable, str(SCRIPT), str(out)],
        capture_output=True, text=True, cwd=str(BACKEND_SRC),
    )

    assert result.returncode == 0, result.stderr
    schema = json.loads(out.read_text())
    assert "/contracts/" in schema["paths"]
    assert "/contracts/{contract_id}" in schema["paths"]

    list_op = schema["paths"]["/contracts/"]["get"]
    # Regression guard on Task 1: a requestBody here means the ID-list
    # filters regressed to GET-body binding (pitfall FASTAPI-1).
    assert "requestBody" not in list_op
    param_names = {p["name"] for p in list_op["parameters"]}
    assert {"region_ids", "system_ids", "station_ids", "type_ids"} <= param_names
    assert "PaginatedResponse_ContractSchema_" in schema["components"]["schemas"]
```

- [x] **Step 3.2: Run to verify failure**

Run: `pdm run pytest src/fastapi_app/tests/test_export_openapi.py -q`
Expected: FAIL — `result.returncode == 0` assertion fails because the script doesn't exist (`No such file or directory` in stderr).

- [x] **Step 3.3: Implement the script**

Create `app/backend/src/export_openapi.py`:

```python
"""Export the FastAPI OpenAPI schema to a JSON file for frontend codegen.

Usage: python src/export_openapi.py [output_path]
Default output: ../frontend/web/openapi.json (relative to app/backend/).

Importing fastapi_app.main requires environment configuration; this script
provides safe dummy defaults so codegen works in any environment. Real env
vars, when set, always take precedence (setdefault). The dummy values are
never used to open connections — only the schema is generated.
"""

import json
import os
import sys

_ENV_DEFAULTS = {
    "ESI_USER_AGENT": "hangar-bay-openapi-export (build tooling)",
    "AGGREGATION_REGION_IDS": "[10000002]",
    "DATABASE_URL": "postgresql+asyncpg://export:export@localhost:5432/export_dummy",
    "CACHE_URL": "redis://localhost:6379/15",
}
for _key, _value in _ENV_DEFAULTS.items():
    os.environ.setdefault(_key, _value)

from fastapi_app.main import app  # noqa: E402


def main() -> None:
    out_path = sys.argv[1] if len(sys.argv) > 1 else "../frontend/web/openapi.json"
    schema = app.openapi()
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(schema, f, indent=2, sort_keys=True)
        f.write("\n")
    print(f"OpenAPI schema written to {out_path} ({len(schema['paths'])} paths)")


if __name__ == "__main__":
    main()
```

If the import still fails on a missing required setting, add that variable to `_ENV_DEFAULTS` with an obviously-fake value — do NOT relax the app's config classes.

Add to `[tool.pdm.scripts]` in `app/backend/pyproject.toml`:

```toml
export-openapi = "python src/export_openapi.py"
```

- [x] **Step 3.4: Run the test, then the script for real**

Run: `pdm run pytest src/fastapi_app/tests/test_export_openapi.py -q`
Expected: PASS.
Run: `mkdir -p ../frontend/web && pdm run export-openapi`
Expected: `OpenAPI schema written to ../frontend/web/openapi.json (N paths)` and the file exists at `app/frontend/web/openapi.json`. (The directory won't exist until Task 4 scaffolds the app; `mkdir -p` makes this order-independent.)

- [x] **Step 3.5: Commit**

```bash
git add app/backend/src/export_openapi.py app/backend/pyproject.toml app/backend/src/fastapi_app/tests/test_export_openapi.py app/frontend/web/openapi.json
git commit -m "feat(backend): add OpenAPI export script for frontend codegen"
```

### Phase 1 group review

- [x] Review Phase 1 commits from ≥3 perspectives (correctness of the SQL change under each `needs_item_join` trigger; regression-test rigor per TEST-1/TEST-4; spec fidelity — no feature work smuggled in). Minimum 3 rounds; continue until a round finds nothing. **Outcome:** the SQL pagination change is correct under every trigger (`search`/`type_ids`/`is_bpc`/`min_runs`/`max_runs`/`ship_name`), the count query was left untouched, and no feature work was smuggled in. Three minor findings were raised and fixed (see below); a final round found nothing further.
- [x] Update the Phase 1 banner and Execution Status table. *(Done in the `fix(task-gate)` remediation commit.)*
- [x] **Finding remediation (`fix(task-gate)` commit):**
  - Plan bookkeeping (this finding): Phase 0 banner flipped to ✅ DONE and Steps 0.1/0.2 checked (env provisioned out-of-band by the harness); Phase 1 banner + top-of-plan Execution Status table flipped to ✅ Shipped with SHAs `598dd22`/`c854668`/`31f4a37`/`e10b109`.
  - TEST-1 coverage gap: added HTTP-level behavioral tests for `system_ids` and `station_ids` (plus over-filter guards) and a page-boundary pagination test under the `is_bpc` trigger (`test_pagination_with_is_bpc_returns_full_distinct_pages`, 3×2-item BPC fixture, size=2, TEST-4 union/intersection/page-length invariants) in `app/backend/src/fastapi_app/tests/api/test_contract_filters.py`.
  - FASTAPI-2: appended "(NOT IMPLEMENTED — accepted but ignored by the service; do not expose in clients)" to the `min_me`/`max_me`/`min_te`/`max_te` `Field` descriptions in `app/backend/src/fastapi_app/schemas/contracts.py` and re-ran `pdm run export-openapi` to refresh the committed `app/frontend/web/openapi.json`.

---

## Phase 2 — Frontend scaffold

**Execution Status:** ✅ SHIPPED 2026-07-12 — branch `claude/hangar-bay-frontend-rebuild-2e4fe7`. Tasks 4–8 shipped: Task 4 scaffold (`b17b24c`, + review fixups `ec07568`), Task 5 router + Query providers (`7420c77`), Task 6 generated API client (`c9d1d2d`), Task 7 URL filter model + query hooks (`58a9df5`), Task 8 static region map + list/detail pages (`448dc53`). Group review complete (≥3 rounds); it surfaced 3 minor findings — stale plan bookkeeping, a TEST-5 multi-value URL round-trip coverage gap, and back/forward history granularity on text inputs — all remediated in the follow-up `fix(task-gate): address review findings` commits `528ca95`/`ecaf2fa`/`4fa9438`. Final: 29 frontend tests, lint + strict build green.

All commands run from `app/frontend/web/` unless stated otherwise. Node ≥ 20.19 required (`node --version`).

### Task 4: Scaffold the Vite app with pinned deps and tooling

**Files:**
- Create: `app/frontend/web/` (Vite react-ts template), `.npmrc`, `vite.config.ts`, `eslint.config.js`, `.prettierrc.json`, `.prettierignore`, `src/test/setup.ts`
- Modify: `package.json` (scripts, exact pins, TS 5.x, drop oxlint), `src/index.css`, `tsconfig.app.json` (enable strict)

**Context:** CONTRIBUTING.md mandates exactly-pinned frontend dependency versions (no `^`/`~`). `.npmrc` with `save-exact=true` enforces that for every future install; the template's own generated ranges get pinned from the lockfile. Tailwind v4 is Vite-plugin based (no tailwind.config.js needed). The TanStack Router plugin must precede the React plugin in the plugins array. Delete the template's demo content — this scaffold ships no design opinions (that's /impeccable's phase).

- [x] **Step 4.1: Generate the app and enforce exact pins**

Task 3 already committed `app/frontend/web/openapi.json`, and `npm create vite` prompts interactively when the target directory is non-empty (which would hang an unattended run). Move the file aside first. From `app/frontend/`:

```bash
mv web/openapi.json ./openapi.json.keep && rmdir web
npm create vite@latest web -- --template react-ts
mv ./openapi.json.keep web/openapi.json
cd web
printf 'save-exact=true\n' > .npmrc
npm install
node -e "
const fs = require('fs');
const pkg = JSON.parse(fs.readFileSync('package.json'));
const lock = JSON.parse(fs.readFileSync('package-lock.json'));
for (const section of ['dependencies', 'devDependencies']) {
  for (const dep of Object.keys(pkg[section] || {})) {
    pkg[section][dep] = lock.packages['node_modules/' + dep].version;
  }
}
fs.writeFileSync('package.json', JSON.stringify(pkg, null, 2) + '\n');
"
```

Verify: `grep -E '"[\^~]' package.json` → no output (no range specifiers remain).

- [x] **Step 4.2: Install the stack (exact pins are automatic via .npmrc)**

> **Deviation (ESLint 10 ERESOLVE, forced by reality):** After the plan's review, `eslint@10.7.0` and `@eslint/js@10.0.1` were published. The unversioned `npm install -D eslint @eslint/js ...` floated to ESLint 10, which ERESOLVEd against `eslint-plugin-jsx-a11y@6.10.2` (peer caps at `^9`). Per the plan's own no-`--force`/`--legacy-peer-deps` policy and its "pin the compatible major first" approach to the TypeScript ERESOLVE, the fix was to pin `eslint@9` and `@eslint/js@9` (the ESLint major the whole flat-config chain supports). Resolved cleanly; installed `eslint@9.39.5`, `@eslint/js@9.39.5`, `eslint-plugin-react-hooks@7.1.1`, `typescript-eslint@8.63.0`, `eslint-plugin-jsx-a11y@6.10.2`. TypeScript landed at exactly `5.9.3` as named. All deps exact-pinned via `.npmrc`.

The current create-vite template pins `typescript@~6.0.x`, but `openapi-typescript` declares a `typescript@^5.x` peer — installing without downgrading first ERESOLVEs and halts. Do NOT reach for `--legacy-peer-deps`/`--force` (they undermine the exact-pin reproducibility policy); pin TypeScript 5.x first:

```bash
npm install -D typescript@5.9.3
npm install tailwindcss @tailwindcss/vite @tanstack/react-router @tanstack/react-query openapi-fetch
npm install -D @tanstack/router-plugin openapi-typescript vitest jsdom @testing-library/react @testing-library/jest-dom @testing-library/user-event
npm install -D eslint @eslint/js typescript-eslint eslint-plugin-react-hooks globals eslint-plugin-jsx-a11y prettier eslint-config-prettier
npm uninstall oxlint
```

(The template lints with oxlint and ships no ESLint at all; the spec mandates ESLint flat config + jsx-a11y, so ESLint and its config chain are installed explicitly and oxlint is removed. If `npm uninstall oxlint` reports it wasn't installed, that's fine — template contents shift between releases.)

- [x] **Step 4.3: Write vite.config.ts (proxy, plugins, vitest)**

Replace `vite.config.ts` with:

```ts
/// <reference types="vitest/config" />
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { tanstackRouter } from '@tanstack/router-plugin/vite'

export default defineConfig({
  // Router plugin must come before the React plugin.
  plugins: [tanstackRouter({ target: 'react', autoCodeSplitting: true }), react(), tailwindcss()],
  server: {
    proxy: {
      // Mirrors the deployment contract: the SPA calls /api/v1/*, the backend
      // mounts routes bare (see app/backend/src/fastapi_app/main.py:165).
      '/api/v1': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api\/v1/, ''),
      },
    },
  },
  test: {
    environment: 'jsdom',
    setupFiles: './src/test/setup.ts',
  },
})
```

Create `src/test/setup.ts`:

```ts
import '@testing-library/jest-dom/vitest'
```

- [x] **Step 4.4: Tailwind, lint, format, scripts, template cleanup**

> **Deviation (minor, template drift):** The current create-vite template ships more demo assets than the plan enumerates — `src/assets/` contained `react.svg` **plus** `hero.png` and `vite.svg`. Since `main.tsx` no longer imports `App` or any asset, the whole `src/assets/` directory is unreferenced, so it was deleted in full (`rm -rf src/assets`) rather than just `react.svg`. The template also ships `public/icons.svg` — an unreferenced brand-icon sprite from the demo `App.tsx`; it was removed too (in the `fix(task-4)` review-fix commit) so the scaffold ships no demo content. `public/favicon.svg` is kept — `index.html` references it. (For the `eslint-plugin-react-hooks` flat-config key, the config uses `reactHooks.configs.flat['recommended-latest']`, not the plan's verbatim `configs['recommended-latest']`; this adaptation is documented in the Step 4.5 note #1 below.)

Replace `src/index.css` entirely with:

```css
@import 'tailwindcss';
```

Delete template demo files: `src/App.tsx`, `src/App.css`, `src/assets/react.svg`, and the logo/counter references (`src/main.tsx` gets fully replaced in Task 5; leave it broken-but-present until then is NOT acceptable — instead reduce it to rendering an empty `<div />` so the build stays green:

```tsx
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'

createRoot(document.getElementById('root')!).render(<StrictMode />)
```

**Create** `eslint.config.js` (the template ships none — it uses oxlint, removed in Step 4.2). If the template left an oxlint config file (e.g. `.oxlintrc.json`), delete it:

```js
import js from '@eslint/js'
import globals from 'globals'
import tseslint from 'typescript-eslint'
import reactHooks from 'eslint-plugin-react-hooks'
import jsxA11y from 'eslint-plugin-jsx-a11y'
import prettier from 'eslint-config-prettier'

export default tseslint.config(
  { ignores: ['dist', 'src/routeTree.gen.ts', 'src/lib/api/schema.d.ts'] },
  {
    files: ['**/*.{ts,tsx}'],
    extends: [
      js.configs.recommended,
      ...tseslint.configs.recommended,
      reactHooks.configs['recommended-latest'],
      jsxA11y.flatConfigs.recommended,
      prettier, // last, so it disables conflicting stylistic rules
    ],
    languageOptions: {
      globals: globals.browser,
    },
  },
)
```

(If the installed eslint-plugin-react-hooks version names its flat config differently — some versions expose `configs.flat.recommended` instead of `configs['recommended-latest']` — use the documented flat recommended config for that version; do not drop the plugin.)

**Enable strict TypeScript** — the template does NOT set it, the spec mandates it ("TypeScript (strict)"), and TanStack Router's `createRouter` intentionally fails compilation without `strictNullChecks` (you'd hit a cryptic `error TS2345: ... '"strictNullChecks must be enabled in tsconfig.json"'` at Task 6's build otherwise). Add to `compilerOptions` in `tsconfig.app.json`:

```json
"strict": true
```

Verify: `grep -n '"strict"' tsconfig.app.json` → one hit, value `true`.

Create `.prettierrc.json`:

```json
{
  "semi": false,
  "singleQuote": true,
  "printWidth": 100
}
```

Create `.prettierignore`:

```
dist
src/routeTree.gen.ts
src/lib/api/schema.d.ts
openapi.json
package-lock.json
```

Set `package.json` scripts (merge with template's existing `dev`/`build`/`preview`):

```json
{
  "dev": "vite",
  "build": "tsc -b && vite build",
  "preview": "vite preview",
  "lint": "eslint .",
  "format": "prettier --write .",
  "test": "vitest run",
  "generate:api": "openapi-typescript openapi.json -o src/lib/api/schema.d.ts"
}
```

- [x] **Step 4.5: Verify the scaffold is green**

> **Deviation/adaptation notes (Step 4.5):**
> 1. **react-hooks flat config key (version adaptation, plan-anticipated):** `eslint-plugin-react-hooks@7.1.1` exposes `configs['recommended-latest']` as the **legacy** eslintrc shape (`plugins: ['react-hooks']` array-of-strings), which flat config rejects. The flat config lives at `configs.flat['recommended-latest']` (plugins as an object). Per the plan's own contingency note, `eslint.config.js` uses `reactHooks.configs.flat['recommended-latest']`. Plugin not dropped; `npm run lint` exits 0.
> 2. **`passWithNoTests: true` (plan-prescribed, since removed):** vitest 4.1.10 exits 1 on "No test files found"; the plan's Step 4.5 explicitly authorizes adding `passWithNoTests: true` to the vitest block. Added; `npm run test` then exited 0. **Removed in the `fix(task-gate)` commit `528ca95`** once Task 5 onward populated the suite with real tests — the stopgap was a no-op by then, and leaving a "pass with no tests" escape hatch in a suite that now has tests could mask a future accidental test-collection gap. `vite.config.ts` no longer contains the option (per the Living Document Contract, recording the removal so a reader does not expect a vitest option that is gone).
> 3. **Benign build/test stderr (observation, not a deviation):** `npm run build` and `npm run test` both print a non-fatal `ENOENT ... scandir '.../src/routes'` from `@tanstack/router-generator` because `src/routes` does not exist until Task 5. Both commands still exit 0 and produce correct output (dist built; tests pass-with-none). The message disappears once Task 5 creates `src/routes`.

Run: `npm run build` — Expected: tsc + vite build succeed.
Run: `npm run lint` — Expected: exit 0.
Run: `npm run test` — Expected: "No test files found" exit 0 (or configure `passWithNoTests: true` in the vitest block if it exits non-zero; tests arrive in Task 5).

- [x] **Step 4.6: Commit**

```bash
git add app/frontend/web
git commit -m "feat(frontend): scaffold React 19 + Vite + TS + Tailwind v4 app with pinned deps"
```

### Task 5: Router + Query providers and route skeleton

**Files:**
- Create: `src/routes/__root.tsx`, `src/routes/index.tsx`, `src/routes/contracts.index.tsx`, `src/routes/contracts.$contractId.tsx`, `src/test/renderApp.tsx`, `src/routes.test.tsx`
- Modify: `src/main.tsx`

**Context:** File-based routing — the router plugin generates `src/routeTree.gen.ts` during any Vite-driven run (dev, build, and vitest, since vitest loads vite.config.ts). Commit `routeTree.gen.ts` (it's in eslint/prettier ignores). Routes here render mechanical placeholders; Tasks 7–8 fill them in. The `/` route redirects to `/contracts`.

- [x] **Step 5.1: Write the route files and providers**

`src/routes/__root.tsx`:

```tsx
import { createRootRoute, Outlet } from '@tanstack/react-router'

export const Route = createRootRoute({
  component: () => <Outlet />,
})
```

`src/routes/index.tsx`:

```tsx
import { createFileRoute, redirect } from '@tanstack/react-router'

export const Route = createFileRoute('/')({
  beforeLoad: () => {
    throw redirect({ to: '/contracts' })
  },
})
```

`src/routes/contracts.index.tsx` (placeholder; replaced in Task 8):

```tsx
import { createFileRoute } from '@tanstack/react-router'

export const Route = createFileRoute('/contracts/')({
  component: () => <main className="p-4">Contract browsing arrives in Task 8.</main>,
})
```

`src/routes/contracts.$contractId.tsx` (placeholder; replaced in Task 8):

```tsx
import { createFileRoute } from '@tanstack/react-router'

export const Route = createFileRoute('/contracts/$contractId')({
  component: () => <main className="p-4">Contract detail arrives in Task 8.</main>,
})
```

Replace `src/main.tsx`:

```tsx
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { createRouter, RouterProvider } from '@tanstack/react-router'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { routeTree } from './routeTree.gen'
import './index.css'

const queryClient = new QueryClient({
  defaultOptions: { queries: { staleTime: 30_000, retry: 1 } },
})

const router = createRouter({ routeTree })

declare module '@tanstack/react-router' {
  interface Register {
    router: typeof router
  }
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>
  </StrictMode>,
)
```

- [x] **Step 5.2: Write the routing smoke test (fails until routeTree generates + routes exist)**

`src/test/renderApp.tsx` — shared test harness used by all route/component tests:

```tsx
import { render } from '@testing-library/react'
import { createMemoryHistory, createRouter, RouterProvider } from '@tanstack/react-router'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { routeTree } from '../routeTree.gen'

export function renderApp(initialUrl: string) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  const router = createRouter({
    routeTree,
    history: createMemoryHistory({ initialEntries: [initialUrl] }),
  })
  return {
    router,
    ...render(
      <QueryClientProvider client={queryClient}>
        <RouterProvider router={router} />
      </QueryClientProvider>,
    ),
  }
}
```

`src/routes.test.tsx`:

```tsx
import { describe, expect, it } from 'vitest'
import { screen } from '@testing-library/react'
import { renderApp } from './test/renderApp'

describe('route skeleton', () => {
  it('redirects / to /contracts', async () => {
    const { router } = renderApp('/')
    await screen.findByText(/Task 8/)
    expect(router.state.location.pathname).toBe('/contracts')
  })

  it('renders the contract detail route', async () => {
    renderApp('/contracts/12345')
    await screen.findByText(/detail/i)
  })
})
```

- [x] **Step 5.3: Run tests**

Run: `npm run test`
Expected: PASS (2 tests). If `routeTree.gen.ts` is missing, run `npx vite build` (NOT `npm run build` — that runs `tsc -b` first, which fails on the unresolvable `./routeTree.gen` import before the plugin ever gets to generate it), then re-run the tests.

> **Execution note:** Confirmed `src/routeTree.gen.ts` was absent before the run (red precondition). `npm run test` → 2 passed; the vitest run (loading `vite.config.ts`) triggered the router plugin to generate `src/routeTree.gen.ts` with all four routes — the `npx vite build` fallback was not needed. As additional verification `npm run build` (tsc + vite build) and `npm run lint` both pass. The `Not implemented: Window's scrollTo()` lines are benign jsdom warnings from TanStack Router scroll restoration, not failures.

- [x] **Step 5.4: Verify in the browser**

Run: `npm run dev` — open `http://localhost:5173/`. Expected: URL changes to `/contracts` and the Task 8 placeholder text renders.

> **Deviation (execution environment — no live dev server):** The live `npm run dev` browser check was not performed. This task was executed by the unattended workflow harness under an explicit "Do NOT start servers" directive (Phase 2 needs no running backend/db — all tests stub the network). The exact behavior this step verifies — `/` redirecting to `/contracts` and the Task 8 placeholder rendering — is asserted programmatically by the Step 5.3 smoke test `src/routes.test.tsx` (`redirects / to /contracts` asserts `router.state.location.pathname === '/contracts'` after finding the `/Task 8/` placeholder text; `renders the contract detail route` finds the `/detail/i` text at `/contracts/12345`). Both passed. No manual browser step is load-bearing beyond what the automated smoke test already covers.

- [x] **Step 5.5: Commit**

```bash
git add app/frontend/web/src
git commit -m "feat(frontend): file-based TanStack Router + Query providers with route skeleton and smoke tests"
```

### Task 6: Generated API client

**Files:**
- Create: `src/lib/api/client.ts`, `src/lib/api/client.test.ts`, `src/test/http.ts`
- Generate: `src/lib/api/schema.d.ts` (via `npm run generate:api`; committed)

**Context:** `openapi.json` was exported in Task 3 (regenerate any time with `cd app/backend && pdm run export-openapi`). openapi-fetch's default query serializer emits repeated array params (`region_ids=1&region_ids=2`) — exactly what FastAPI expects post-Task-1; the test locks that invariant (pitfall TEST-5). The client's `baseUrl` owns the `/api/v1` prefix and all calls use schema paths verbatim including trailing slashes (pitfall PROXY-1).

- [x] **Step 6.1: Generate types**

Run: `npm run generate:api`
Expected: `src/lib/api/schema.d.ts` created; it contains `'/contracts/'` and `'/contracts/{contract_id}'` path keys and a `PaginatedResponse_ContractSchema_` component.

- [x] **Step 6.2: Write the failing test**

`src/lib/api/client.test.ts`:

```ts
import { describe, expect, it } from 'vitest'
import createClient from 'openapi-fetch'
import type { paths } from './schema'
import { ApiError } from './client'
import { jsonResponse } from '../../test/http'

const EMPTY_PAGE = { total: 0, page: 1, size: 50, items: [] }

function clientWithRecorder(calls: string[]) {
  const recordingFetch: typeof fetch = async (input) => {
    const url =
      typeof input === 'string' ? input : input instanceof URL ? input.toString() : input.url
    calls.push(url)
    return jsonResponse(EMPTY_PAGE)
  }
  return createClient<paths>({ baseUrl: 'http://test/api/v1', fetch: recordingFetch })
}

describe('api client request contract', () => {
  it('serializes ID arrays as repeated query params (FastAPI form/explode)', async () => {
    const calls: string[] = []
    const client = clientWithRecorder(calls)

    await client.GET('/contracts/', {
      params: { query: { region_ids: [10000002, 10000020], page: 1, size: 50 } },
    })

    expect(calls[0]).toContain('region_ids=10000002&region_ids=10000020')
  })

  it('hits the trailing-slash list path under the /api/v1 base (PROXY-1)', async () => {
    const calls: string[] = []
    const client = clientWithRecorder(calls)

    await client.GET('/contracts/', { params: { query: { page: 1, size: 50 } } })

    expect(calls[0].startsWith('http://test/api/v1/contracts/?')).toBe(true)
  })

  it('omits undefined query params entirely', async () => {
    const calls: string[] = []
    const client = clientWithRecorder(calls)

    await client.GET('/contracts/', {
      params: { query: { search: undefined, page: 1, size: 50 } },
    })

    expect(calls[0]).not.toContain('search')
  })
})

describe('ApiError', () => {
  it('carries the HTTP status and is an Error', () => {
    const error = new ApiError(404)
    expect(error.status).toBe(404)
    expect(error).toBeInstanceOf(Error)
    expect(error.message).toContain('404')
  })
})
```

`src/test/http.ts` (shared by the hook/page tests in Tasks 7–8 — the `.test.helpers` naming convention is deliberately avoided so nothing under `src/test/` ever matches vitest's `*.test.*` collection glob):

```ts
export function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}
```

- [x] **Step 6.3: Run to verify failure**

Run: `npm run test -- src/lib/api`
Expected: FAIL — vitest cannot resolve `./client` (the module doesn't exist until Step 6.4).

> **Execution note:** Confirmed — vitest failed with `Failed to resolve import "./client" from "src/lib/api/client.test.ts". Does the file exist?`, exactly the stated reason.

- [x] **Step 6.4: Write the client**

`src/lib/api/client.ts`:

```ts
import createClient from 'openapi-fetch'
import type { components, paths } from './schema'

export type Contract = components['schemas']['ContractSchema']
export type ContractItem = components['schemas']['ContractItemSchema']
export type PaginatedContracts = components['schemas']['PaginatedResponse_ContractSchema_']

export class ApiError extends Error {
  constructor(public status: number) {
    super(`API request failed with status ${status}`)
    this.name = 'ApiError'
  }
}

// baseUrl owns the /api/v1 prefix (dev proxy strips it — see vite.config.ts).
// All calls use schema paths verbatim, INCLUDING trailing slashes: /contracts
// without the slash triggers a 307 that escapes the rewriting proxy (PROXY-1).
//
// Two testability constraints shape this call (do NOT "simplify" them away):
// - openapi-fetch builds `new Request(url)` internally; a bare relative
//   baseUrl throws "Invalid URL" under Node/jsdom (browsers resolve it,
//   test environments don't). Prefixing location.origin keeps requests
//   same-origin (still routed through the Vite proxy) and test-runnable.
// - openapi-fetch captures fetch at createClient() time; delegating at
//   call time keeps vi.stubGlobal('fetch', ...) effective in tests.
export const api = createClient<paths>({
  baseUrl: (typeof location !== 'undefined' ? location.origin : '') + '/api/v1',
  fetch: (request) => globalThis.fetch(request),
})
```

> **Deviation (TS toolchain, forced by reality):** The current create-vite template's `tsconfig.app.json` (already present from Task 4) sets `"erasableSyntaxOnly": true`, a TypeScript 5.8+ flag not anticipated by the plan. It rejects parameter-property constructor shorthand (`constructor(public status: number)`) with `error TS1294: This syntax is not allowed when 'erasableSyntaxOnly' is enabled.` — confirmed via `npm run build`. Fixed by expanding to an explicit field declaration + assignment, identical runtime behavior and public API (`error.status` still works, verified by the `ApiError` test):
> ```ts
> export class ApiError extends Error {
>   status: number
>
>   constructor(status: number) {
>     super(`API request failed with status ${status}`)
>     this.name = 'ApiError'
>     this.status = status
>   }
> }
> ```
> The baseUrl/fetch construction below the class was transcribed verbatim, comments included, per the task guardrail — this deviation is scoped only to the constructor syntax, not that block.

- [x] **Step 6.5: Run tests, typecheck, commit**

Run: `npm run test -- src/lib/api` — Expected: PASS (3 tests).
Run: `npm run build` — Expected: green.

> **Execution note:** The test file as written contains 4 `it(...)` cases (3 under `describe('api client request contract')` + 1 under `describe('ApiError')`), so the actual passing count is 4, not the 3 the plan's expected-output line states — a plan documentation miscount, not a test change. All 4 passed on the first run after the `ApiError` deviation fix above; no assertion was altered or weakened. Full suite (`npm run test`): 2 files, 6 tests, all green. `npm run build` and `npm run lint` both exit 0.

```bash
git add app/frontend/web/src/lib/api app/frontend/web/src/test app/frontend/web/openapi.json
git commit -m "feat(frontend): generated OpenAPI types + typed api client with request-contract tests"
```

### Task 7: URL filter model and query hooks

**Files:**
- Create: `src/features/contracts/filters.ts`, `src/features/contracts/filters.test.ts`, `src/features/contracts/hooks/useContracts.ts`, `src/features/contracts/hooks/useContract.ts`, `src/features/contracts/hooks/hooks.test.tsx`

**Context:** URL search params are the single source of truth for filter state. `parseContractSearch` is the route's `validateSearch` — it must accept arbitrary junk from the address bar and always return a well-formed object (bad values fall back to defaults, never throw). `toApiQuery` gates `search` below the backend's `min_length=3` (a 1–2-char search stays in the URL while the user types, but is never sent — the backend would 422). Hooks live under `features/contracts/hooks/` and must not import any component (mobile-shareable seam, per spec). ME/TE and the other deferred filters are deliberately absent — do NOT add params the M1 UI doesn't ship (spec: "Milestone-1 minimum filter surface").

- [x] **Step 7.1: Write failing tests for the filter model**

`src/features/contracts/filters.test.ts`:

```ts
import { describe, expect, it } from 'vitest'
import {
  DEFAULT_PAGE,
  DEFAULT_SIZE,
  MIN_SEARCH_LENGTH,
  parseContractSearch,
  toApiQuery,
} from './filters'

describe('parseContractSearch', () => {
  it('returns defaults for an empty search object', () => {
    expect(parseContractSearch({})).toEqual({
      search: undefined,
      min_price: undefined,
      max_price: undefined,
      region_ids: undefined,
      is_bpc: undefined,
      page: DEFAULT_PAGE,
      size: DEFAULT_SIZE,
      sort_by: 'date_issued',
      sort_direction: 'desc',
    })
  })

  it('coerces a lone region id into an array and drops junk entries', () => {
    expect(parseContractSearch({ region_ids: 10000002 }).region_ids).toEqual([10000002])
    expect(parseContractSearch({ region_ids: ['10000002', 'abc', -5] }).region_ids).toEqual([
      10000002,
    ])
    expect(parseContractSearch({ region_ids: 'abc' }).region_ids).toBeUndefined()
  })

  it('falls back to defaults on invalid page/size/sort values instead of throwing', () => {
    const parsed = parseContractSearch({
      page: 'x',
      size: 9999,
      sort_by: 'DROP TABLE',
      sort_direction: 'sideways',
    })
    expect(parsed.page).toBe(DEFAULT_PAGE)
    expect(parsed.size).toBe(DEFAULT_SIZE)
    expect(parsed.sort_by).toBe('date_issued')
    expect(parsed.sort_direction).toBe('desc')
  })

  it('keeps valid values', () => {
    const parsed = parseContractSearch({
      search: 'Tristan',
      min_price: '1000000',
      is_bpc: true,
      page: 3,
      size: 25,
      sort_by: 'price',
      sort_direction: 'asc',
    })
    expect(parsed).toMatchObject({
      search: 'Tristan',
      min_price: 1_000_000,
      is_bpc: true,
      page: 3,
      size: 25,
      sort_by: 'price',
      sort_direction: 'asc',
    })
  })
})

describe('toApiQuery', () => {
  it('gates search below the backend min_length of 3', () => {
    expect(MIN_SEARCH_LENGTH).toBe(3)
    const base = parseContractSearch({})
    expect(toApiQuery({ ...base, search: 'ab' }).search).toBeUndefined()
    expect(toApiQuery({ ...base, search: '  ab  ' }).search).toBeUndefined()
    expect(toApiQuery({ ...base, search: 'abc' }).search).toBe('abc')
  })

  it('passes filters through and keeps pagination/sort always present', () => {
    const query = toApiQuery(parseContractSearch({ region_ids: [10000002], page: 2 }))
    expect(query.region_ids).toEqual([10000002])
    expect(query.page).toBe(2)
    expect(query.size).toBe(DEFAULT_SIZE)
    expect(query.sort_by).toBe('date_issued')
    expect(query.sort_direction).toBe('desc')
  })
})
```

- [x] **Step 7.2: Run to verify failure**

Run: `npm run test -- src/features/contracts/filters`
Expected: FAIL — `./filters` module not found.

- [x] **Step 7.3: Implement the filter model**

`src/features/contracts/filters.ts`:

```ts
export const SORT_FIELDS = [
  'date_issued',
  'date_expired',
  'price',
  'collateral',
  'ship_name',
  'volume',
] as const
export type SortField = (typeof SORT_FIELDS)[number]

export const SORT_DIRECTIONS = ['asc', 'desc'] as const
export type SortDirection = (typeof SORT_DIRECTIONS)[number]

/** Backend ContractFilters.search has min_length=3; shorter values 422. */
export const MIN_SEARCH_LENGTH = 3
export const DEFAULT_PAGE = 1
export const DEFAULT_SIZE = 50
export const MAX_SIZE = 100

export interface ContractSearch {
  search?: string
  min_price?: number
  max_price?: number
  region_ids?: number[]
  is_bpc?: boolean
  page: number
  size: number
  sort_by: SortField
  sort_direction: SortDirection
}

function toNumber(value: unknown): number | undefined {
  const n =
    typeof value === 'number' ? value : typeof value === 'string' && value !== '' ? Number(value) : NaN
  return Number.isFinite(n) ? n : undefined
}

function toBoundedInt(value: unknown, min: number, max: number, fallback: number): number {
  const n = toNumber(value)
  return n !== undefined && Number.isInteger(n) && n >= min && n <= max ? n : fallback
}

function toIdArray(value: unknown): number[] | undefined {
  const raw = Array.isArray(value) ? value : value === undefined ? [] : [value]
  const ids = raw
    .map(toNumber)
    .filter((n): n is number => n !== undefined && Number.isInteger(n) && n > 0)
  return ids.length > 0 ? ids : undefined
}

/**
 * validateSearch for the /contracts route. Accepts arbitrary address-bar
 * input and always returns a well-formed ContractSearch — invalid values
 * fall back to defaults rather than throwing.
 */
export function parseContractSearch(raw: Record<string, unknown>): ContractSearch {
  return {
    search: typeof raw.search === 'string' && raw.search.length > 0 ? raw.search : undefined,
    min_price: toNumber(raw.min_price),
    max_price: toNumber(raw.max_price),
    region_ids: toIdArray(raw.region_ids),
    is_bpc: typeof raw.is_bpc === 'boolean' ? raw.is_bpc : undefined,
    page: toBoundedInt(raw.page, 1, Number.MAX_SAFE_INTEGER, DEFAULT_PAGE),
    size: toBoundedInt(raw.size, 1, MAX_SIZE, DEFAULT_SIZE),
    sort_by: SORT_FIELDS.includes(raw.sort_by as SortField)
      ? (raw.sort_by as SortField)
      : 'date_issued',
    sort_direction: SORT_DIRECTIONS.includes(raw.sort_direction as SortDirection)
      ? (raw.sort_direction as SortDirection)
      : 'desc',
  }
}

/**
 * URL state → API query object. Gates `search` below MIN_SEARCH_LENGTH:
 * a 1–2-char value stays in the URL (the user is mid-typing) but is never
 * sent — the backend would reject it with a 422.
 */
export function toApiQuery(s: ContractSearch) {
  const trimmed = s.search?.trim()
  return {
    search: trimmed !== undefined && trimmed.length >= MIN_SEARCH_LENGTH ? trimmed : undefined,
    min_price: s.min_price,
    max_price: s.max_price,
    region_ids: s.region_ids,
    is_bpc: s.is_bpc,
    page: s.page,
    size: s.size,
    sort_by: s.sort_by,
    sort_direction: s.sort_direction,
  }
}
```

Run: `npm run test -- src/features/contracts/filters` — Expected: PASS.

- [x] **Step 7.4: Write failing hook tests**

`src/features/contracts/hooks/hooks.test.tsx` — stubs global fetch (pitfall TEST-5); asserts rendered outcome AND the request URL:

```tsx
import { afterEach, describe, expect, it, vi } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import type { ReactNode } from 'react'
import { jsonResponse } from '../../../test/http'
import { parseContractSearch } from '../filters'
import { useContracts } from './useContracts'
import { useContract } from './useContract'

const PAGE = {
  total: 1,
  page: 1,
  size: 50,
  items: [
    {
      contract_id: 101,
      issuer_id: 1,
      issuer_corporation_id: 101,
      start_location_id: 60003760,
      type: 'item_exchange',
      status: 'outstanding',
      title: 'Tristan for Sale',
      for_corporation: false,
      date_issued: '2026-07-01T00:00:00Z',
      date_expired: '2026-07-08T00:00:00Z',
      price: 1000000,
      is_ship_contract: true,
      items: [],
    },
  ],
}

function stubFetch(handler: (url: string) => Response) {
  const calls: string[] = []
  vi.stubGlobal('fetch', async (input: RequestInfo | URL) => {
    const url =
      typeof input === 'string' ? input : input instanceof URL ? input.toString() : input.url
    calls.push(url)
    return handler(url)
  })
  return calls
}

function wrapper({ children }: { children: ReactNode }) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('useContracts', () => {
  it('fetches a page and exposes the data', async () => {
    const calls = stubFetch(() => jsonResponse(PAGE))

    const { result } = renderHook(() => useContracts(parseContractSearch({})), { wrapper })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(result.current.data?.total).toBe(1)
    expect(result.current.data?.items[0]?.contract_id).toBe(101)
    expect(calls[0]).toContain('/api/v1/contracts/?')
  })

  it('never sends a sub-3-char search', async () => {
    const calls = stubFetch(() => jsonResponse(PAGE))

    const { result } = renderHook(
      () => useContracts(parseContractSearch({ search: 'ab' })),
      { wrapper },
    )

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(calls[0]).not.toContain('search')
  })

  it('surfaces server errors as isError', async () => {
    stubFetch(() => jsonResponse({ detail: 'boom' }, 500))

    const { result } = renderHook(() => useContracts(parseContractSearch({})), { wrapper })

    await waitFor(() => expect(result.current.isError).toBe(true))
  })
})

describe('useContract', () => {
  it('fetches a single contract by id', async () => {
    const calls = stubFetch(() => jsonResponse(PAGE.items[0]))

    const { result } = renderHook(() => useContract(101), { wrapper })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(result.current.data?.contract_id).toBe(101)
    expect(calls[0]).toContain('/api/v1/contracts/101')
  })

  it('exposes a 404 as an ApiError without retrying', async () => {
    const calls = stubFetch(() => jsonResponse({ detail: 'Contract not found' }, 404))

    const { result } = renderHook(() => useContract(999), { wrapper })

    await waitFor(() => expect(result.current.isError).toBe(true))
    expect(calls).toHaveLength(1)
  })
})
```

Run: `npm run test -- src/features/contracts/hooks` — Expected: FAIL (hook modules not found).

- [x] **Step 7.5: Implement the hooks**

`src/features/contracts/hooks/useContracts.ts`:

```ts
import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { api, ApiError } from '../../../lib/api/client'
import { toApiQuery, type ContractSearch } from '../filters'

export function useContracts(search: ContractSearch) {
  const query = toApiQuery(search)
  return useQuery({
    queryKey: ['contracts', 'list', query],
    queryFn: async () => {
      const { data, response } = await api.GET('/contracts/', { params: { query } })
      if (data === undefined) throw new ApiError(response.status)
      return data
    },
    placeholderData: keepPreviousData,
  })
}
```

`src/features/contracts/hooks/useContract.ts`:

```ts
import { useQuery } from '@tanstack/react-query'
import { api, ApiError } from '../../../lib/api/client'

export function useContract(contractId: number) {
  return useQuery({
    queryKey: ['contracts', 'detail', contractId],
    enabled: Number.isInteger(contractId) && contractId > 0,
    retry: (failureCount, error) =>
      !(error instanceof ApiError && error.status === 404) && failureCount < 1,
    queryFn: async () => {
      const { data, response } = await api.GET('/contracts/{contract_id}', {
        params: { path: { contract_id: contractId } },
      })
      if (data === undefined) throw new ApiError(response.status)
      return data
    },
  })
}
```

- [x] **Step 7.6: Run all frontend tests, typecheck, commit**

Run: `npm run test` — Expected: PASS (routes + client + filters + hooks).
Run: `npm run build` — Expected: green.

```bash
git add app/frontend/web/src/features
git commit -m "feat(frontend): URL filter model with search gate + contract query hooks, full test coverage"
```

### Task 8: Static region map and the end-to-end contract pages

**Files:**
- Create: `scripts/generate-regions.mjs`, `src/features/contracts/regions.ts` (generated then committed), `src/features/contracts/regions.test.ts`, `src/features/contracts/components/ContractsPage.tsx`, `src/features/contracts/components/ContractDetailPage.tsx`, `src/features/contracts/components/pages.test.tsx`
- Modify: `src/routes/contracts.index.tsx`, `src/routes/contracts.$contractId.tsx`, `src/routes.test.tsx`

**Context:** These pages are the milestone's mechanical end-to-end proof — correct data flow, working filters-in-URL, explicit loading/error/empty branches. Presentation is deliberately bare-bones Tailwind; /impeccable redesigns it next phase. Do NOT invest in visual design, do NOT add filters beyond the spec's M1 minimum surface (search, price range, region multi-select, BPC toggle, sort, pagination), and do NOT add ME/TE controls (backend-inert — pitfall FASTAPI-2). The region selector uses a bundled static map generated once from ESI (public API, no auth); the generator script is committed for future refresh.

- [x] **Step 8.1: Generate the static region map**

Create `scripts/generate-regions.mjs`:

```js
// Regenerates src/features/contracts/regions.ts from ESI (public, no auth).
// Run: node scripts/generate-regions.mjs
const ESI = 'https://esi.evetech.net/latest'

const ids = await (await fetch(`${ESI}/universe/regions/`)).json()
// K-space regions only: wormhole (11xxxxxx) and abyssal (12xxxxxx+) regions
// never host public contracts a marketplace user can reach.
const kspace = ids.filter((id) => id < 11000000)
const regions = await Promise.all(
  kspace.map(async (id) => {
    const region = await (await fetch(`${ESI}/universe/regions/${id}/`)).json()
    return { id, name: region.name }
  }),
)
regions.sort((a, b) => a.name.localeCompare(b.name))

const lines = regions.map((r) => `  { id: ${r.id}, name: ${JSON.stringify(r.name)} },`)
const content = `// GENERATED by scripts/generate-regions.mjs — do not edit by hand.
// EVE region IDs are stable static data; regenerate only if CCP adds regions.
export const REGIONS = [
${lines.join('\n')}
] as const

export type Region = (typeof REGIONS)[number]
`
await (await import('node:fs/promises')).writeFile('src/features/contracts/regions.ts', content)
console.log(`Wrote ${regions.length} regions`)
```

Run: `node scripts/generate-regions.mjs`
Expected: `Wrote N regions` (N ≈ 70) and `src/features/contracts/regions.ts` exists. If ESI is unreachable, STOP and note it — do not hand-write region IDs from memory.

`src/features/contracts/regions.test.ts` (locks known-stable invariants):

```ts
import { describe, expect, it } from 'vitest'
import { REGIONS } from './regions'

describe('static region map', () => {
  it('contains The Forge with its canonical id', () => {
    expect(REGIONS.find((r) => r.name === 'The Forge')?.id).toBe(10000002)
  })

  it('is sorted by name and k-space only', () => {
    const names = REGIONS.map((r) => r.name)
    expect(names).toEqual([...names].sort((a, b) => a.localeCompare(b)))
    expect(REGIONS.every((r) => r.id < 11000000)).toBe(true)
  })
})
```

- [x] **Step 8.2: Write failing page tests**

`src/features/contracts/components/pages.test.tsx` — uses the route-level harness so URL↔filter wiring is exercised, not mocked (pitfall TEST-5):

```tsx
import { afterEach, describe, expect, it, vi } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { jsonResponse } from '../../../test/http'
import { renderApp } from '../../../test/renderApp'

const CONTRACT = {
  contract_id: 101,
  issuer_id: 1,
  issuer_corporation_id: 101,
  start_location_id: 60003760,
  type: 'item_exchange',
  status: 'outstanding',
  title: 'Tristan for Sale',
  for_corporation: false,
  date_issued: '2026-07-01T00:00:00Z',
  date_expired: '2026-07-08T00:00:00Z',
  price: 1000000,
  start_location_name: 'Jita IV - Moon 4 - Caldari Navy Assembly Plant',
  is_ship_contract: true,
  items: [
    {
      record_id: 1011,
      type_id: 587,
      quantity: 1,
      is_included: true,
      is_singleton: false,
      type_name: 'Tristan',
    },
  ],
}

function stubFetch(handler: (url: string) => Response) {
  const calls: string[] = []
  vi.stubGlobal('fetch', async (input: RequestInfo | URL) => {
    const url =
      typeof input === 'string' ? input : input instanceof URL ? input.toString() : input.url
    calls.push(url)
    return handler(url)
  })
  return calls
}

afterEach(() => vi.unstubAllGlobals())

describe('ContractsPage', () => {
  it('renders fetched contracts in the table', async () => {
    stubFetch(() => jsonResponse({ total: 1, page: 1, size: 50, items: [CONTRACT] }))

    renderApp('/contracts')

    expect(await screen.findByText('Tristan')).toBeInTheDocument()
    expect(screen.getByText(/1,000,000/)).toBeInTheDocument()
  })

  it('shows the empty state for zero results', async () => {
    stubFetch(() => jsonResponse({ total: 0, page: 1, size: 50, items: [] }))

    renderApp('/contracts')

    expect(await screen.findByText(/no contracts match/i)).toBeInTheDocument()
  })

  it('shows the error state with a retry control on failure', async () => {
    stubFetch(() => jsonResponse({ detail: 'boom' }, 500))

    renderApp('/contracts')

    expect(await screen.findByRole('alert')).toHaveTextContent(/failed to load/i)
    expect(screen.getByRole('button', { name: /retry/i })).toBeInTheDocument()
  })

  it('reads filters from the URL and sends them to the API', async () => {
    const calls = stubFetch(() =>
      jsonResponse({ total: 0, page: 1, size: 50, items: [] }),
    )

    renderApp('/contracts?region_ids=10000002&is_bpc=true&sort_by=price&sort_direction=asc')

    await screen.findByText(/no contracts match/i)
    expect(calls[0]).toContain('region_ids=10000002')
    expect(calls[0]).toContain('is_bpc=true')
    expect(calls[0]).toContain('sort_by=price')
  })

  it('resets to page 1 when a filter changes', async () => {
    const calls = stubFetch(() =>
      jsonResponse({ total: 200, page: 3, size: 50, items: [CONTRACT] }),
    )

    const { router } = renderApp('/contracts?page=3')
    await screen.findByText('Tristan')

    await userEvent.click(screen.getByLabelText(/blueprint copies only/i))

    await waitFor(() => expect(router.state.location.search).toMatchObject({ page: 1 }))
    // Router state updates before TanStack Query issues the refetch — the
    // request assertions must also wait (TEST-2: fix the sync, never weaken).
    await waitFor(() => {
      expect(calls.at(-1)).toContain('is_bpc=true')
      expect(calls.at(-1)).toContain('page=1')
    })
  })
})

describe('ContractDetailPage', () => {
  it('renders a contract with its items', async () => {
    stubFetch(() => jsonResponse(CONTRACT))

    renderApp('/contracts/101')

    expect(await screen.findByText('Tristan for Sale')).toBeInTheDocument()
    // The list item renders as "1× Tristan" across text nodes — match the
    // full normalized text, not the bare name (which also appears in the h1).
    expect(screen.getByText(/1× Tristan/)).toBeInTheDocument()
    expect(screen.getByText(/jita/i)).toBeInTheDocument()
  })

  it('shows not-found for a 404', async () => {
    stubFetch(() => jsonResponse({ detail: 'Contract not found' }, 404))

    renderApp('/contracts/999')

    expect(await screen.findByText(/not found/i)).toBeInTheDocument()
  })
})
```

Update `src/routes.test.tsx`, whose placeholder-text assertions become stale once the real pages land. Add the same `stubFetch`/`afterEach` helpers to that file, then: in the redirect test, stub `jsonResponse({ total: 0, page: 1, size: 50, items: [] })` and replace `await screen.findByText(/Task 8/)` with `await screen.findByRole('heading', { name: /ship contracts/i })`; in the detail-route test, stub `jsonResponse({ detail: 'Contract not found' }, 404)` and replace the placeholder assertion with `await screen.findByText(/not found/i)`.

Run: `npm run test -- src/features/contracts/components`
Expected: FAIL — component modules not found.

> **Deviation (minor, expected-failure phrasing — no code change):** Step 8.2's stated red reason ("component modules not found") did not manifest literally, because `pages.test.tsx` reaches the pages through the route harness (`renderApp`) rather than importing `ContractsPage`/`ContractDetailPage` directly. The RED run failed all 7 tests with `TestingLibraryElementError: Unable to find …` — the routes still rendered the "arrives in Task 8" placeholders, so the assertions for real page content (Tristan, empty/error/not-found states) could not match. Same conceptual cause the step intends (pages not yet implemented); the tests were transcribed verbatim and no assertion was weakened.

- [x] **Step 8.3: Implement the pages**

`src/features/contracts/components/ContractsPage.tsx`:

```tsx
// Mechanical scaffold UI: correct data flow and states only.
// Presentation is redesigned wholesale in the /impeccable phase.
import { Link, useNavigate } from '@tanstack/react-router'
import type { Contract } from '../../../lib/api/client'
import { MIN_SEARCH_LENGTH, SORT_FIELDS, type ContractSearch } from '../filters'
import { REGIONS } from '../regions'
import { useContracts } from '../hooks/useContracts'

export function ContractsPage({
  search,
  from,
}: {
  search: ContractSearch
  from: '/contracts/'
}) {
  const navigate = useNavigate({ from })
  const { data, isPending, isError, refetch } = useContracts(search)

  const update = (patch: Partial<ContractSearch>) =>
    navigate({ search: (prev) => ({ ...prev, page: 1, ...patch }) })

  return (
    <main className="p-4">
      <h1 className="text-xl font-bold">Hangar Bay — Ship Contracts</h1>

      <form
        role="search"
        onSubmit={(event) => event.preventDefault()}
        className="my-4 flex flex-wrap items-end gap-4"
      >
        <label className="flex flex-col">
          Search (min {MIN_SEARCH_LENGTH} chars)
          <input
            type="search"
            className="border p-1"
            value={search.search ?? ''}
            onChange={(e) => update({ search: e.target.value || undefined })}
          />
        </label>
        <label className="flex flex-col">
          Min price
          <input
            type="number"
            min="0"
            className="border p-1"
            value={search.min_price ?? ''}
            onChange={(e) =>
              update({ min_price: e.target.value === '' ? undefined : Number(e.target.value) })
            }
          />
        </label>
        <label className="flex flex-col">
          Max price
          <input
            type="number"
            min="0"
            className="border p-1"
            value={search.max_price ?? ''}
            onChange={(e) =>
              update({ max_price: e.target.value === '' ? undefined : Number(e.target.value) })
            }
          />
        </label>
        <label className="flex flex-col">
          Regions
          <select
            multiple
            className="border p-1"
            size={4}
            value={(search.region_ids ?? []).map(String)}
            onChange={(e) => {
              const ids = Array.from(e.target.selectedOptions, (o) => Number(o.value))
              update({ region_ids: ids.length > 0 ? ids : undefined })
            }}
          >
            {REGIONS.map((region) => (
              <option key={region.id} value={region.id}>
                {region.name}
              </option>
            ))}
          </select>
        </label>
        <label className="flex items-center gap-1">
          <input
            type="checkbox"
            checked={search.is_bpc === true}
            onChange={(e) => update({ is_bpc: e.target.checked ? true : undefined })}
          />
          Blueprint copies only
        </label>
        <label className="flex flex-col">
          Sort by
          <select
            className="border p-1"
            value={search.sort_by}
            onChange={(e) => update({ sort_by: e.target.value as ContractSearch['sort_by'] })}
          >
            {SORT_FIELDS.map((field) => (
              <option key={field} value={field}>
                {field}
              </option>
            ))}
          </select>
        </label>
        <label className="flex flex-col">
          Direction
          <select
            className="border p-1"
            value={search.sort_direction}
            onChange={(e) =>
              update({ sort_direction: e.target.value as ContractSearch['sort_direction'] })
            }
          >
            <option value="desc">desc</option>
            <option value="asc">asc</option>
          </select>
        </label>
      </form>

      {isPending ? (
        <p>Loading contracts…</p>
      ) : isError ? (
        <p role="alert">
          Failed to load contracts.{' '}
          <button className="underline" onClick={() => refetch()}>
            Retry
          </button>
        </p>
      ) : data.items.length === 0 ? (
        <p>No contracts match these filters.</p>
      ) : (
        <>
          <table className="w-full border-collapse text-left">
            <thead>
              <tr className="border-b">
                <th className="p-2">Ship / Title</th>
                <th className="p-2">Type</th>
                <th className="p-2">Price (ISK)</th>
                <th className="p-2">Location</th>
                <th className="p-2">Issued</th>
              </tr>
            </thead>
            <tbody>
              {data.items.map((contract) => (
                <tr key={contract.contract_id} className="border-b">
                  <td className="p-2">
                    <Link
                      to="/contracts/$contractId"
                      params={{ contractId: String(contract.contract_id) }}
                      className="underline"
                    >
                      {primaryLabel(contract)}
                    </Link>
                  </td>
                  <td className="p-2">{contract.type}</td>
                  <td className="p-2">
                    {/* Fixed locale: M1 is explicitly English-only (spec Non-goals),
                        and tests assert the formatted value (pitfall TEST-3). */}
                    {contract.price != null ? contract.price.toLocaleString('en-US') : '—'}
                  </td>
                  <td className="p-2">
                    {contract.start_location_name ?? contract.start_location_id}
                  </td>
                  <td className="p-2">{new Date(contract.date_issued).toLocaleDateString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <nav aria-label="Pagination" className="my-4 flex items-center gap-4">
            <button
              className="border px-2 disabled:opacity-50"
              disabled={search.page <= 1}
              onClick={() => navigate({ search: (prev) => ({ ...prev, page: search.page - 1 }) })}
            >
              Previous
            </button>
            <span>
              Page {data.page} of {Math.max(1, Math.ceil(data.total / data.size))} ({data.total}{' '}
              contracts)
            </span>
            <button
              className="border px-2 disabled:opacity-50"
              disabled={search.page * data.size >= data.total}
              onClick={() => navigate({ search: (prev) => ({ ...prev, page: search.page + 1 }) })}
            >
              Next
            </button>
          </nav>
        </>
      )}
    </main>
  )
}

function primaryLabel(contract: Contract): string {
  const included = contract.items.find((item) => item.is_included && item.type_name)
  return included?.type_name ?? contract.title ?? `Contract ${contract.contract_id}`
}
```

`src/features/contracts/components/ContractDetailPage.tsx`:

```tsx
// Mechanical scaffold UI — redesigned in the /impeccable phase.
import { Link } from '@tanstack/react-router'
import { ApiError } from '../../../lib/api/client'
import { useContract } from '../hooks/useContract'

export function ContractDetailPage({ contractId }: { contractId: number }) {
  const { data, isPending, isError, error, refetch } = useContract(contractId)

  if (!Number.isInteger(contractId) || contractId <= 0) {
    return <NotFound />
  }
  if (isPending) {
    return <main className="p-4">Loading contract…</main>
  }
  if (isError) {
    if (error instanceof ApiError && error.status === 404) return <NotFound />
    return (
      <main className="p-4">
        <p role="alert">
          Failed to load this contract.{' '}
          <button className="underline" onClick={() => refetch()}>
            Retry
          </button>
        </p>
      </main>
    )
  }

  return (
    <main className="p-4">
      <Link to="/contracts" className="underline">
        ← All contracts
      </Link>
      <h1 className="my-2 text-xl font-bold">{data.title ?? `Contract ${data.contract_id}`}</h1>
      <dl className="grid max-w-xl grid-cols-2 gap-1">
        <dt className="font-semibold">Type</dt>
        <dd>{data.type}</dd>
        <dt className="font-semibold">Status</dt>
        <dd>{data.status}</dd>
        <dt className="font-semibold">Price (ISK)</dt>
        <dd>{data.price != null ? data.price.toLocaleString('en-US') : '—'}</dd>
        <dt className="font-semibold">Location</dt>
        <dd>{data.start_location_name ?? data.start_location_id}</dd>
        <dt className="font-semibold">Issuer</dt>
        <dd>{data.issuer_name ?? data.issuer_id}</dd>
        <dt className="font-semibold">Issued</dt>
        <dd>{new Date(data.date_issued).toLocaleString()}</dd>
        <dt className="font-semibold">Expires</dt>
        <dd>{new Date(data.date_expired).toLocaleString()}</dd>
      </dl>
      <h2 className="mt-4 font-semibold">Items</h2>
      <ul className="list-disc pl-6">
        {data.items.map((item) => (
          <li key={item.record_id}>
            {item.quantity}× {item.type_name ?? `Type ${item.type_id}`}
            {item.is_blueprint_copy ? ' (BPC)' : ''}
            {item.is_included ? '' : ' — asked for, not included'}
          </li>
        ))}
      </ul>
    </main>
  )
}

function NotFound() {
  return (
    <main className="p-4">
      <p>Contract not found.</p>
      <Link to="/contracts" className="underline">
        ← All contracts
      </Link>
    </main>
  )
}
```

Replace `src/routes/contracts.index.tsx`:

```tsx
import { createFileRoute } from '@tanstack/react-router'
import { ContractsPage } from '../features/contracts/components/ContractsPage'
import { parseContractSearch } from '../features/contracts/filters'

export const Route = createFileRoute('/contracts/')({
  validateSearch: parseContractSearch,
  component: () => <ContractsPage search={Route.useSearch()} from={Route.fullPath} />,
})
```

Replace `src/routes/contracts.$contractId.tsx`:

```tsx
import { createFileRoute } from '@tanstack/react-router'
import { ContractDetailPage } from '../features/contracts/components/ContractDetailPage'

export const Route = createFileRoute('/contracts/$contractId')({
  component: () => {
    const { contractId } = Route.useParams()
    return <ContractDetailPage contractId={Number(contractId)} />
  },
})
```

- [x] **Step 8.4: Run the full frontend suite, lint, build**

Run: `npm run test` — Expected: PASS (all files).
Run: `npm run lint` — Expected: exit 0 (jsx-a11y included).
Run: `npm run build` — Expected: green.

> **Deviations (Step 8.3/8.4, all forced by reality — no assertion touched, no runtime behavior changed):**
> 1. **RTL cleanup (`src/test/setup.ts`, a Task 4 file):** the plan's Task 4 `vite.config.ts` sets no `globals: true`, so `@testing-library/react@16.3.2` never auto-registers `cleanup()` (it only does when `afterEach` is a global). The five `ContractsPage` renders in `pages.test.tsx` accumulated in the DOM, so `getByLabelText(/blueprint copies only/i)` and `getByText(/jita/i)` failed with "Found multiple elements". Fix: the canonical RTL-without-globals pattern — `import { cleanup } from '@testing-library/react'; afterEach(() => cleanup())` in the shared `setup.ts`. Deterministic; weakens nothing (TEST-2 compliant). Earlier tasks' tests never queried accumulating text, which is why this stayed latent until Task 8.
> 2. **Named route components (`contracts.index.tsx`, `contracts.$contractId.tsx`):** `eslint-plugin-react-hooks@7.1.1`'s stricter rules-of-hooks flags `Route.useSearch()` / `Route.useParams()` inside the plan's anonymous `component: () => …` arrow ("neither a React component nor a hook"). Fix: extract each route's `component` into a named uppercase `RouteComponent` function (TanStack Router's own documented pattern). Identical runtime behavior; `npm run lint` → exit 0.
> 3. **`SearchSchemaInput` marker (`contracts.index.tsx`):** wiring `validateSearch: parseContractSearch` (which returns a `ContractSearch` with required `page`/`size`/`sort_by`/`sort_direction`) made `/contracts` search params *required for navigation*, so `tsc -b` rejected the plan's own bare `redirect({ to: '/contracts' })` (Task 5 `index.tsx`) and `<Link to="/contracts">` (Task 8 detail page) with TS2741/TS2345. Fix: give the route's inline `validateSearch` the input type `Record<string, unknown> & SearchSchemaInput` (delegating to `parseContractSearch`), the documented TanStack idiom that makes defaulted search params optional for navigation while `useSearch()` keeps the full `ContractSearch`. Localized to this one route file — `filters.ts` (Task 7) and every direct `parseContractSearch({…})` test call stay verbatim (adding the required phantom marker to `parseContractSearch`'s own signature would have broken those direct calls). `npm run build` → exit 0.

- [x] **Step 8.5: Commit**

```bash
git add app/frontend/web/scripts app/frontend/web/src
git commit -m "feat(frontend): contract list + detail pages end-to-end with static region map

Mechanical scaffold UI proving the full data path (URL filters -> typed
client -> rendered states incl. loading/error/empty/not-found). Visual
design intentionally deferred to the /impeccable phase."
```

### Phase 2 group review

- [x] Review Phase 2 commits from ≥3 perspectives (URL-state correctness incl. back/forward behavior; test rigor per TEST-5 — outcomes AND request URLs asserted; spec fidelity — M1 minimum surface exactly, no ME/TE, no design investment). Minimum 3 rounds; continue until clean. **Outcome:** URL-as-source-of-truth is correct including multi-value params; spec surface is the M1 minimum with no ME/TE and no design investment. Three minor findings were raised and fixed (see remediation below); a final round found nothing further.
- [x] Update the Phase 2 banner and Execution Status table. *(Done in the `fix(task-gate)` remediation commit — banner flipped to ✅ SHIPPED, top table row already ✅ Shipped.)*
- **Finding remediation (`fix(task-gate)` commit — three minor findings):**
  - Plan bookkeeping (finding 1): Step 4.5 deviation note #2 now records that `passWithNoTests: true` was removed from `vite.config.ts` in commit `528ca95` once the suite had real tests, per the Living Document Contract (previously the note still described the option as present).
  - TEST-5 coverage gap (finding 2): added `pages.test.tsx` route-level test "carries a repeated region_ids URL through to repeated API params" — renders `/contracts?region_ids=10000002&region_ids=10000020` and asserts `calls[0]` contains `region_ids=10000002&region_ids=10000020`, exercising the full multi-value inbound seam (TanStack Router qss decode → `parseContractSearch` array coercion → `toApiQuery` → openapi-fetch repeated-array serializer) that prior single-value tests left uncovered. Pure addition; no existing assertion weakened.
  - Back/forward granularity (finding 3, **runtime-behavior deviation** from Step 8.3's verbatim `ContractsPage.tsx`): the `update` helper (`src/features/contracts/components/ContractsPage.tsx`) now takes an optional `{ replace?: boolean }` and the three text inputs (search, min_price, max_price) navigate with `{ replace: true }`; the discrete controls (region multi-select, BPC toggle, sort field/direction) and pagination keep the default push. This collapses the per-keystroke history entries so the back button restores prior discrete filter states rather than walking the search box character-by-character (addresses Task 9 Step 9.2's "working back button" acceptance item). URL-as-source-of-truth is unchanged; no test assertion was altered (no existing test drives text-input history depth).

---

## Phase 3 — Acceptance, teardown, documentation

**Execution Status:** ✅ SHIPPED 2026-07-12 — branch `claude/hangar-bay-frontend-rebuild-2e4fe7`. All three tasks executed and committed: Task 9 acceptance PASSED against live ESI data, requiring two fixes shipped during acceptance (`afbd1bf` ingestion region stamp, `54956dd` blank-title row label — both in Discoveries) plus the acceptance record (`1e6c763`); Task 10 Angular teardown (`657e804`, review fix `662a0ba`); Task 11 documentation (`8f82036`, review fix `d8a737a`). Full ship SHAs: `afbd1bf`, `54956dd`, `1e6c763`, `657e804`, `662a0ba`, `8f82036`, `d8a737a`, `7882b8d`, `b708fe6`. Group review complete (this gate) across three rounds: round-1's five findings landed in `7882b8d` (`fix(task-gate)`, which also shipped CONTRIBUTING.md content fixes — env block + eight repointed links); round-2's three findings (ContractDetailPage blank-title `??` fix + regression test, the residual-Angular Discovery undercount, and this SHA backfill) landed in `b708fe6`; round 3 was clean (nits only). Final verification at milestone exit: backend 38 passed, frontend 31 passed (6 files), lint exit 0, strict build green. Milestone complete; integration (merge/PR) is the user's call per superpowers:finishing-a-development-branch.

### Task 9: End-to-end acceptance against the real backend

**Files:** none modified — this is a verification gate. Requires the backend dev environment (pitfalls ENV-1, ENV-2).

- [x] **Step 9.1: Boot the backend**

Ensure `app/backend/src/.env` contains (values per your environment):

```
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/hangar_bay
DATABASE_URL_TESTS=postgresql+asyncpg://postgres:postgres@localhost:5432/hangar_bay_test
CACHE_URL=redis://localhost:6379/0
ESI_USER_AGENT=hangar-bay-dev (your-email@example.com)
AGGREGATION_REGION_IDS=[10000002]
```

`AGGREGATION_REGION_IDS` must be a JSON list — a bare int or comma-separated string crashes at startup (ENV-1). Postgres and Valkey must be running (see `app/backend/docker/`). Then:

Run: `cd app/backend && pdm run dev`
Expected: startup completes; note that startup **drops and recreates all tables** and immediately runs aggregation — real data appears after a few minutes (ENV-2; dev limit is 100 contracts from The Forge). Verify data exists before judging the frontend: `curl -s "http://localhost:8000/contracts/?size=1" | head -c 400` returns `"total": <nonzero>`.

- [x] **Step 9.2: Boot the frontend and verify the acceptance checklist**

Run: `cd app/frontend/web && npm run dev` — open `http://localhost:5173/`.

Checklist (all must hold):
- [x] `/` redirects to `/contracts`; a table of real contracts renders. *(100 live Forge contracts.)*
- [x] Typing 2 chars in search sends no request with `search`; the 3rd char triggers a filtered request (verify in devtools Network). *(Network-verified: only `search=ven` ever left the browser.)*
- [x] Selecting a region updates the URL (`?region_ids=...`) and the result set; the URL is shareable (paste into a new tab → same filtered view) and the back button restores the previous filter state. *(Required the `afbd1bf` ingestion fix — see Discoveries. Hand-written repeated-param URLs are also accepted; the router normalizes to its JSON array encoding.)*
- [x] BPC toggle, price bounds, sort field/direction all round-trip through the URL and change results; changing any filter resets to page 1. *(Sort-direction change from page 3 → page 1 verified. BPC toggle round-trips; this 100-contract sample happened to contain zero BPCs, so its result-set effect was verified as the correct empty state.)*
- [x] Pagination: with `size=10` in the URL and >10 total contracts, Next/Previous walk pages with no duplicated or skipped contracts across the boundary (this exercises the Task 2 fix live when a search term is active). *(`search=blueprint`, 21 matches via the item join: pages [10, 10, 1], 21 unique, Next disabled on last page.)*
- [x] Clicking a row opens `/contracts/<id>` with fields + items; a bogus id (`/contracts/999999999`) shows the not-found state; `/contracts/abc` shows not-found, not a crash.
- [x] Stopping the backend and clicking Retry shows the error state with a working retry once the backend returns. *(One live-verification caveat: TanStack Query pauses retries while the tab is unfocused, so the error state needed a simulated `visibilitychange` in the headless pane — correct production behavior, jsdom tests cover the state directly.)*

- [x] **Step 9.3: Record the gate**

Update this plan: Phase 3 banner, plus a one-line note per checklist item that failed and what was fixed (as Deviations/Discoveries). No commit for this task unless fixes were needed.

**Acceptance record (2026-07-12, orchestrator-driven):** all items pass against live ESI data.
Fixes required and shipped during acceptance: `afbd1bf` (ingestion region stamp) and `54956dd`
(blank-title row label) — both in Discoveries. Dev-experience note: killing the backend
mid-ingestion (e.g. uvicorn `--reload`) leaves the Valkey aggregation lock held until its TTL
expires, so the next startup run logs "already running" and skips; remedy during development is
`docker exec hangar_bay_valkey valkey-cli DEL "hangar-bay:aggregation:lock"`. The lock is
TTL-bounded, so this self-heals in production.

### Task 10: Angular teardown

**Files:**
- Delete: `app/frontend/angular/` (entire tree), `design/angular/` (entire tree)

- [x] **Step 10.1: Delete and verify nothing depends on the removed trees**

```bash
git rm -r --quiet app/frontend/angular design/angular
git grep -n "frontend/angular\|design/angular" -- ':!docs/plans' ':!docs/superpowers' ':!docs/perf-audits'
```

(`git grep` covers every tracked file type — config, TOML, YAML — not just the obvious extensions.)

Expected: roughly 20 hits, ALL in prose/historical documents — `README.md` and `CONTRIBUTING.md` (rewritten in Task 11), `plans/implementation/**` (the 2025 MVP plans), `design/reviews/**`, `design/meta/**` (design-log, memory-index, risks), `design/chat-prompts.txt`. These are historical records: leave every one of them untouched (editing them is scope creep). The pass criterion is: **zero hits in code or config** (anything under `app/`, or any `.json`/`.toml`/`.yml`/`.ts`/`.py` file outside those doc trees). If such a hit appears, resolve it before committing.

> **Deviation (hit-count estimate, not the pass criterion):** actual count was 126 hits, not "roughly 20" — but every one of the 23 matching files falls exactly within the plan's named categories (`README.md`, `CONTRIBUTING.md`, `plans/implementation/**`, `design/reviews/**` (pre-mortems + post-mortems + the perf-audit slice plan), `design/meta/{design-log,memory-index,risks}.md`, `design/chat-prompts.txt`). All are `.md`/`.txt` prose/historical records; none are under `app/` or `.json`/`.toml`/`.yml`/`.ts`/`.py`. A repo-wide follow-up check (`git grep` restricted to `app/` plus `*.json|*.toml|*.yml|*.yaml|*.ts|*.py` globs, no doc-tree exclusions) reused the same path-only pattern (`frontend/angular|design/angular`) and returned zero matches — but that pattern only detects the removed *paths*, not free-text mentions of "Angular" in prose/comments, so on its own it does not establish "zero hits in code or config" in the fully general sense the pass criterion states. A stale prose reference did in fact survive it: `app/backend/docker/compose.yml`'s network-purpose comment described the frontend container as "(Angular)" (harmless — the `networks:` block defines no Angular-specific config — and pre-existing rather than introduced by this commit, but it made the "pass criterion holds" claim literally false). Corrected in the `fix(task-10)` review-remediation commit to say "(React)". Left every doc-tree hit untouched per the instruction not to edit historical records (Task 11 handles README.md/CONTRIBUTING.md separately).

- [x] **Step 10.2: Commit**

```bash
git commit -m "chore: remove abandoned Angular frontend and Angular-specific design docs

Superseded by app/frontend/web (React). Git history preserves the tree."
```

### Task 11: Documentation updates

**Files:**
- Modify: `README.md`, `CONTRIBUTING.md`, `design/specifications/test-spec.md`, `design/specifications/accessibility-spec.md`, `design/specifications/i18n-spec.md`

**Context:** The spec's "Teardown & documentation updates" section is the requirements list. These are prose edits; the content requirements below are exhaustive — do not invent additional policy.

> **Deviations (Task 11 execution, 2026-07-12):**
> 1. **Frontend `app/frontend/web/README.md` already rewritten in Phase 2 (`ec07568`).** The dispatch guardrail expected this file to still be the stale create-vite/Oxlint template deferred to Task 11, but the Phase-2 Task-4 review fix `ec07568` already replaced it with a stack-accurate stub (Vite + React 19 + TS strict + Tailwind v4 + ESLint flat/jsx-a11y + Vitest; all seven npm scripts; the `.npmrc save-exact` note). Verified accurate against the shipped toolchain — no further change needed in Task 11, so it is not in this task's commit.
> 2. **Additional framework-name corrections beyond the three literal bullets.** To honor the "docs MUST describe what was actually built" mandate, CONTRIBUTING.md's AI-guidance stack declarations were also corrected (Core Technologies (AI Focus), the `TypeScript/React` Coding-Standards bullet, the `React (Frontend)` Key-Technologies block, the Development-Workflow frontend line, and the accessibility/i18n/performance spec one-line descriptions). These are factual stack statements, not new policy.
> 3. **test-spec.md scope.** Step 11.3's §4 tooling swap was additionally applied to the §3.6 accessibility-test example (it carried a lowercase `@axe-core/angular` token that would otherwise fail the Step 11.5 gate and read as stale). The deeper AI-implementation-pattern prose in §3.1/§3.2/§3.4 (Jasmine/Karma/`TestBed` patterns) was **left as-is** — outside the plan's named §4/§6 scope, it is capital-`Angular` (does not trip the gate), and rewriting it into React/Vitest patterns would fabricate patterns not yet established (deferred to `/impeccable` + a later docs pass). Flagged as residual below. **Update (review remediation, `fix(task-11)`):** this residual was closed within Task 11's file scope after all — the §3.1/§3.2 patterns were converted to Vitest + React Testing Library, and the §3.4 perf-area label and the §7 `npm audit` example were relabeled for React. The patterns turned out to be already established in the shipped frontend (30 passing Vitest/RTL tests using exactly `render`/`renderHook`/`QueryClientProvider`/`user-event`/`vi.stubGlobal`/the `renderApp` helper), so describing them is factual, not fabrication. test-spec.md now contains zero any-case `angular`/`jasmine`/`karma`/`testbed` tokens. **Re-verified 2026-07-12** during the design/performance-spec residue sweep: still zero tokens; §3.1/§3.2/§3.4/§7 remain consistent with §4 and the shipped test patterns — no further edits needed.
> 4. **accessibility-spec.md scope.** §4 (Angular Material/CDK tooling) was replaced with React idioms and §5's automated-tool line was swapped to jsx-a11y + vitest-axe, per the bullet. The incidental "custom Angular components" phrasing inside the §3 WCAG-requirement prose was left untouched per the bullet's explicit "WCAG requirements … stay untouched" (capital-`Angular`; does not trip the gate).
> 5. **Step 11.5 grep — in-scope clean, out-of-scope residual (Discovery).** Restricted to Task 11's five named files the grep is clean (exit 1). Run against the whole `design/specifications/` directory as the plan's command literally does, it still flags **`design-spec.md`** (lines ~164/167/327) and **`performance-spec.md`** (lines ~81/83), which carry pre-existing Angular-as-current-stack references (`@angular/localize`, `@angular/cdk/scrolling`, "Angular CLI build optimizations"). Those two specs are **outside** Task 11's named file scope (the spec's Teardown list and this task both name only test/accessibility/i18n-spec), so they were not edited. The plan's Step 11.5 verification command is broader than its edit scope — a plan-internal inconsistency; a follow-up is needed to update those two specs. **Update (2026-07-12): closed by this commit** — the tracked follow-up swept `design-spec.md` and `performance-spec.md` (stack statements updated to the shipped React/Vite reality; i18n and virtualization library choices stated as deferred rather than invented; framework-agnostic requirements untouched). The observability/security/accessibility residues remain tracked in the top-of-plan Discoveries for the /impeccable docs pass.
> 6. **Commit scope.** The plan's Step 11.5 `git add` names only `README.md CONTRIBUTING.md design/specifications/`; this commit also stages this plan file (Task 11 checkbox ticks + these notes), per the dispatch instruction to include plan edits in the task commit.

- [x] **Step 11.1: README.md**

- Core Technologies: replace `**Frontend:** Angular` with `**Frontend:** React 19 (Vite, TypeScript, Tailwind CSS v4, TanStack Router/Query)`.
- Prerequisites: drop the Angular CLI requirement; keep Node ≥ 20.19.
- Replace the "Frontend Setup (Angular)" section with: `cd app/frontend/web`, `npm install`, `npm run dev` (app at `http://localhost:5173`, proxying `/api/v1` to the backend on `:8000`), plus the type-regeneration flow: after backend schema changes run `cd app/backend && pdm run export-openapi` then `cd app/frontend/web && npm run generate:api`.
- Mark the 2025 screenshot as pre-rebuild ("Angular-era screenshot; React rebuild in progress").

- [x] **Step 11.2: CONTRIBUTING.md**

- Rewrite frontend setup/commands sections for `app/frontend/web` (same commands as README, plus `npm run lint`, `npm run format`, `npm run test`).
- State the dependency policy: exact pins enforced by `.npmrc` (`save-exact=true`); no `^`/`~` in `package.json`.
- Add a "Backend dev prerequisites" subsection with the env-file location (`app/backend/src/.env`), required vars incl. the JSON-list format for `AGGREGATION_REGION_IDS`, the Valkey requirement, the drop/recreate-on-restart + ingestion-delay behavior, and `DATABASE_URL_TESTS` for the test suite (content per pitfalls ENV-1/ENV-2 and Task 9 Step 9.1).

- [x] **Step 11.3: design/specifications/test-spec.md**

- §4 frontend rows: Karma/Jasmine → Vitest + React Testing Library; Protractor → Playwright (deferred until the /impeccable phase delivers the UI it would smoke-test); `@axe-core/angular` → `eslint-plugin-jsx-a11y` (active) + `vitest-axe` on key views (arrives with /impeccable).
- §6: add that frontend CI build-fail wiring for a11y scans is deferred until frontend CI exists; the M1 posture is lint-time + test-time checks.

- [x] **Step 11.4: design/specifications/accessibility-spec.md and i18n-spec.md**

- accessibility-spec.md: replace Angular-specific mandatory tooling references with the React equivalents above; the WCAG requirements themselves are framework-agnostic and stay untouched.
- i18n-spec.md: add a status note that M1 ships hardcoded English strings by explicit decision (spec Non-goals), with i18n wiring revisited before feature milestones; replace Angular-specific implementation guidance with a pointer to that note (do not delete the framework-agnostic requirements).

- [x] **Step 11.5: Verify and commit**

```bash
grep -rn "ng serve\|Angular CLI\|angular" README.md CONTRIBUTING.md design/specifications/ | grep -iv "angular-era\|historical\|previously\|was Angular"
```

Expected: no hits describing Angular as the current stack (mentions framed as history are fine).

> **Result:** across Task 11's five named files (`README.md`, `CONTRIBUTING.md`, `test-spec.md`, `accessibility-spec.md`, `i18n-spec.md`) the grep is clean. Run against the whole `design/specifications/` directory it still flags `design-spec.md` and `performance-spec.md`, which are out of Task 11's scope (see Deviation 5 above). `git add` also includes this plan file (see Deviation 6).

```bash
git add README.md CONTRIBUTING.md design/specifications/
git commit -m "docs: update README/CONTRIBUTING/specs for the React frontend

Frontend sections now describe app/frontend/web (React 19 + Vite +
Tailwind v4 + TanStack); test-spec frontend tooling moves to Vitest/RTL
with Playwright and vitest-axe deferred to the /impeccable phase; i18n
spec notes the explicit M1 English-only deferral."
```

### Phase 3 group review

- [x] Review Phase 3 from ≥3 perspectives (acceptance checklist honesty — every box actually observed; teardown completeness; docs accuracy against what was really built). Minimum 3 rounds; continue until clean. **Outcome:** the Task 9 acceptance record is honest (each box carries the live observation that backed it, including the two real-data fixes it forced); the Angular teardown is complete (zero code/config hits; the one stale prose comment corrected in `662a0ba`); the docs were audited against what shipped. Five findings were raised and fixed in the `fix(task-gate)` commit below — two major plan-bookkeeping (Phase 2/3 banners + table + checkboxes stale despite the work being done) and three minor docs-accuracy items (a top-of-plan Discovery for the residual Angular specs, and CONTRIBUTING.md env-var/Docker + design-doc link-path corrections). A final round found nothing further.
- [x] Update all banners and the Execution Status table; fill Deviations/Discoveries. *(Done in the `fix(task-gate)` remediation commit — Phase 2 and Phase 3 banners flipped to ✅ SHIPPED, the Overall line and Phase 3 table row updated, and the residual-Angular-specs Discovery added.)*
- [ ] Milestone exit: invoke superpowers:finishing-a-development-branch. **Pending — the one remaining step after this gate;** the orchestrator runs it once the `fix(task-gate)` commit lands. Left unticked deliberately: the ritual has not been invoked yet, and a ticked box here would falsely tell followers the branch was already merged/PR'd. The follow-on phase is `/impeccable` (design system + full F002/F003 interface build) per the spec's Process section.
