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

**Overall:** 🚧 In progress — Phase 1 (Backend enablement fixes).

| Phase | Status | Ship SHA(s) | Notes |
|---|---|---|---|
| 1 — Backend enablement fixes | 🚧 In progress | — | Claimed on `claude/hangar-bay-frontend-rebuild-2e4fe7`. Task 1 complete (`598dd22`); Tasks 2–3 + group review pending. Ship SHA(s) recorded at the group-review step. |
| 2 — Frontend scaffold | ⬜ Not started | — | — |
| 3 — Acceptance, teardown, docs | ⬜ Not started | — | — |

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

**Execution Status:** ⬜ NOT STARTED

Backend tests need a real Postgres. Before Phase 1:

- [ ] **Step 0.1: Confirm the backend test suite runs at all**

`app/backend/src/.env` must contain a `DATABASE_URL_TESTS` entry pointing at a scratch Postgres database (the test fixture drops/recreates all tables per test — never point it at a database with data you care about), e.g.:

```
DATABASE_URL_TESTS=postgresql+asyncpg://postgres:postgres@localhost:5432/hangar_bay_test
```

Create the database if needed: `createdb hangar_bay_test` (or via docker — see `app/backend/docker/`).

- [ ] **Step 0.2: Run the existing HTTP filter tests as a green baseline**

Run: `cd app/backend && pdm run pytest src/fastapi_app/tests/api/test_contract_filters.py -q`
Expected: all tests PASS. If they fail for environment reasons, fix the environment before touching code — Phase 1's TDD signal depends on a green baseline. If they fail for code reasons, STOP and report; that's a Discovery.

---

## Phase 1 — Backend enablement fixes

**Execution Status:** 🚧 IN PROGRESS — branch `claude/hangar-bay-frontend-rebuild-2e4fe7`. Claim recorded retroactively at 2026-07-11T22:53:24Z (UTC), anchored to the first Phase 1 commit (`598dd22`, Task 1) since the "on phase claim" banner flip was missed when work started. Task 1 is complete; Tasks 2–3 and the Phase 1 group review remain. Per the Living Document Contract, ship SHA(s) are recorded at the Phase 1 group-review step (see "Phase 1 group review" below), not per-task.

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

- [ ] Review Phase 1 commits from ≥3 perspectives (correctness of the SQL change under each `needs_item_join` trigger; regression-test rigor per TEST-1/TEST-4; spec fidelity — no feature work smuggled in). Minimum 3 rounds; continue until a round finds nothing.
- [ ] Update the Phase 1 banner and Execution Status table.

---

## Phase 2 — Frontend scaffold

**Execution Status:** ⬜ NOT STARTED

All commands run from `app/frontend/web/` unless stated otherwise. Node ≥ 20.19 required (`node --version`).

### Task 4: Scaffold the Vite app with pinned deps and tooling

**Files:**
- Create: `app/frontend/web/` (Vite react-ts template), `.npmrc`, `vite.config.ts`, `eslint.config.js`, `.prettierrc.json`, `.prettierignore`, `src/test/setup.ts`
- Modify: `package.json` (scripts, exact pins, TS 5.x, drop oxlint), `src/index.css`, `tsconfig.app.json` (enable strict)

**Context:** CONTRIBUTING.md mandates exactly-pinned frontend dependency versions (no `^`/`~`). `.npmrc` with `save-exact=true` enforces that for every future install; the template's own generated ranges get pinned from the lockfile. Tailwind v4 is Vite-plugin based (no tailwind.config.js needed). The TanStack Router plugin must precede the React plugin in the plugins array. Delete the template's demo content — this scaffold ships no design opinions (that's /impeccable's phase).

- [ ] **Step 4.1: Generate the app and enforce exact pins**

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

- [ ] **Step 4.2: Install the stack (exact pins are automatic via .npmrc)**

The current create-vite template pins `typescript@~6.0.x`, but `openapi-typescript` declares a `typescript@^5.x` peer — installing without downgrading first ERESOLVEs and halts. Do NOT reach for `--legacy-peer-deps`/`--force` (they undermine the exact-pin reproducibility policy); pin TypeScript 5.x first:

```bash
npm install -D typescript@5.9.3
npm install tailwindcss @tailwindcss/vite @tanstack/react-router @tanstack/react-query openapi-fetch
npm install -D @tanstack/router-plugin openapi-typescript vitest jsdom @testing-library/react @testing-library/jest-dom @testing-library/user-event
npm install -D eslint @eslint/js typescript-eslint eslint-plugin-react-hooks globals eslint-plugin-jsx-a11y prettier eslint-config-prettier
npm uninstall oxlint
```

(The template lints with oxlint and ships no ESLint at all; the spec mandates ESLint flat config + jsx-a11y, so ESLint and its config chain are installed explicitly and oxlint is removed. If `npm uninstall oxlint` reports it wasn't installed, that's fine — template contents shift between releases.)

- [ ] **Step 4.3: Write vite.config.ts (proxy, plugins, vitest)**

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

- [ ] **Step 4.4: Tailwind, lint, format, scripts, template cleanup**

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

- [ ] **Step 4.5: Verify the scaffold is green**

Run: `npm run build` — Expected: tsc + vite build succeed.
Run: `npm run lint` — Expected: exit 0.
Run: `npm run test` — Expected: "No test files found" exit 0 (or configure `passWithNoTests: true` in the vitest block if it exits non-zero; tests arrive in Task 5).

- [ ] **Step 4.6: Commit**

```bash
git add app/frontend/web
git commit -m "feat(frontend): scaffold React 19 + Vite + TS + Tailwind v4 app with pinned deps"
```

### Task 5: Router + Query providers and route skeleton

**Files:**
- Create: `src/routes/__root.tsx`, `src/routes/index.tsx`, `src/routes/contracts.index.tsx`, `src/routes/contracts.$contractId.tsx`, `src/test/renderApp.tsx`, `src/routes.test.tsx`
- Modify: `src/main.tsx`

**Context:** File-based routing — the router plugin generates `src/routeTree.gen.ts` during any Vite-driven run (dev, build, and vitest, since vitest loads vite.config.ts). Commit `routeTree.gen.ts` (it's in eslint/prettier ignores). Routes here render mechanical placeholders; Tasks 7–8 fill them in. The `/` route redirects to `/contracts`.

- [ ] **Step 5.1: Write the route files and providers**

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

- [ ] **Step 5.2: Write the routing smoke test (fails until routeTree generates + routes exist)**

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

- [ ] **Step 5.3: Run tests**

Run: `npm run test`
Expected: PASS (2 tests). If `routeTree.gen.ts` is missing, run `npx vite build` (NOT `npm run build` — that runs `tsc -b` first, which fails on the unresolvable `./routeTree.gen` import before the plugin ever gets to generate it), then re-run the tests.

- [ ] **Step 5.4: Verify in the browser**

Run: `npm run dev` — open `http://localhost:5173/`. Expected: URL changes to `/contracts` and the Task 8 placeholder text renders.

- [ ] **Step 5.5: Commit**

```bash
git add app/frontend/web/src
git commit -m "feat(frontend): file-based TanStack Router + Query providers with route skeleton and smoke tests"
```

### Task 6: Generated API client

**Files:**
- Create: `src/lib/api/client.ts`, `src/lib/api/client.test.ts`, `src/test/http.ts`
- Generate: `src/lib/api/schema.d.ts` (via `npm run generate:api`; committed)

**Context:** `openapi.json` was exported in Task 3 (regenerate any time with `cd app/backend && pdm run export-openapi`). openapi-fetch's default query serializer emits repeated array params (`region_ids=1&region_ids=2`) — exactly what FastAPI expects post-Task-1; the test locks that invariant (pitfall TEST-5). The client's `baseUrl` owns the `/api/v1` prefix and all calls use schema paths verbatim including trailing slashes (pitfall PROXY-1).

- [ ] **Step 6.1: Generate types**

Run: `npm run generate:api`
Expected: `src/lib/api/schema.d.ts` created; it contains `'/contracts/'` and `'/contracts/{contract_id}'` path keys and a `PaginatedResponse_ContractSchema_` component.

- [ ] **Step 6.2: Write the failing test**

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

- [ ] **Step 6.3: Run to verify failure**

Run: `npm run test -- src/lib/api`
Expected: FAIL — vitest cannot resolve `./client` (the module doesn't exist until Step 6.4).

- [ ] **Step 6.4: Write the client**

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

- [ ] **Step 6.5: Run tests, typecheck, commit**

Run: `npm run test -- src/lib/api` — Expected: PASS (3 tests).
Run: `npm run build` — Expected: green.

```bash
git add app/frontend/web/src/lib/api app/frontend/web/src/test app/frontend/web/openapi.json
git commit -m "feat(frontend): generated OpenAPI types + typed api client with request-contract tests"
```

### Task 7: URL filter model and query hooks

**Files:**
- Create: `src/features/contracts/filters.ts`, `src/features/contracts/filters.test.ts`, `src/features/contracts/hooks/useContracts.ts`, `src/features/contracts/hooks/useContract.ts`, `src/features/contracts/hooks/hooks.test.tsx`

**Context:** URL search params are the single source of truth for filter state. `parseContractSearch` is the route's `validateSearch` — it must accept arbitrary junk from the address bar and always return a well-formed object (bad values fall back to defaults, never throw). `toApiQuery` gates `search` below the backend's `min_length=3` (a 1–2-char search stays in the URL while the user types, but is never sent — the backend would 422). Hooks live under `features/contracts/hooks/` and must not import any component (mobile-shareable seam, per spec). ME/TE and the other deferred filters are deliberately absent — do NOT add params the M1 UI doesn't ship (spec: "Milestone-1 minimum filter surface").

- [ ] **Step 7.1: Write failing tests for the filter model**

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

- [ ] **Step 7.2: Run to verify failure**

Run: `npm run test -- src/features/contracts/filters`
Expected: FAIL — `./filters` module not found.

- [ ] **Step 7.3: Implement the filter model**

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

- [ ] **Step 7.4: Write failing hook tests**

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

- [ ] **Step 7.5: Implement the hooks**

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

- [ ] **Step 7.6: Run all frontend tests, typecheck, commit**

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

- [ ] **Step 8.1: Generate the static region map**

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

- [ ] **Step 8.2: Write failing page tests**

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

- [ ] **Step 8.3: Implement the pages**

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

- [ ] **Step 8.4: Run the full frontend suite, lint, build**

Run: `npm run test` — Expected: PASS (all files).
Run: `npm run lint` — Expected: exit 0 (jsx-a11y included).
Run: `npm run build` — Expected: green.

- [ ] **Step 8.5: Commit**

```bash
git add app/frontend/web/scripts app/frontend/web/src
git commit -m "feat(frontend): contract list + detail pages end-to-end with static region map

Mechanical scaffold UI proving the full data path (URL filters -> typed
client -> rendered states incl. loading/error/empty/not-found). Visual
design intentionally deferred to the /impeccable phase."
```

### Phase 2 group review

- [ ] Review Phase 2 commits from ≥3 perspectives (URL-state correctness incl. back/forward behavior; test rigor per TEST-5 — outcomes AND request URLs asserted; spec fidelity — M1 minimum surface exactly, no ME/TE, no design investment). Minimum 3 rounds; continue until clean.
- [ ] Update the Phase 2 banner and Execution Status table.

---

## Phase 3 — Acceptance, teardown, documentation

**Execution Status:** ⬜ NOT STARTED

### Task 9: End-to-end acceptance against the real backend

**Files:** none modified — this is a verification gate. Requires the backend dev environment (pitfalls ENV-1, ENV-2).

- [ ] **Step 9.1: Boot the backend**

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

- [ ] **Step 9.2: Boot the frontend and verify the acceptance checklist**

Run: `cd app/frontend/web && npm run dev` — open `http://localhost:5173/`.

Checklist (all must hold):
- [ ] `/` redirects to `/contracts`; a table of real contracts renders.
- [ ] Typing 2 chars in search sends no request with `search`; the 3rd char triggers a filtered request (verify in devtools Network).
- [ ] Selecting a region updates the URL (`?region_ids=...`) and the result set; the URL is shareable (paste into a new tab → same filtered view) and the back button restores the previous filter state.
- [ ] BPC toggle, price bounds, sort field/direction all round-trip through the URL and change results; changing any filter resets to page 1.
- [ ] Pagination: with `size=10` in the URL and >10 total contracts, Next/Previous walk pages with no duplicated or skipped contracts across the boundary (this exercises the Task 2 fix live when a search term is active).
- [ ] Clicking a row opens `/contracts/<id>` with fields + items; a bogus id (`/contracts/999999999`) shows the not-found state; `/contracts/abc` shows not-found, not a crash.
- [ ] Stopping the backend and clicking Retry shows the error state with a working retry once the backend returns.

- [ ] **Step 9.3: Record the gate**

Update this plan: Phase 3 banner, plus a one-line note per checklist item that failed and what was fixed (as Deviations/Discoveries). No commit for this task unless fixes were needed.

### Task 10: Angular teardown

**Files:**
- Delete: `app/frontend/angular/` (entire tree), `design/angular/` (entire tree)

- [ ] **Step 10.1: Delete and verify nothing depends on the removed trees**

```bash
git rm -r --quiet app/frontend/angular design/angular
git grep -n "frontend/angular\|design/angular" -- ':!docs/plans' ':!docs/superpowers' ':!docs/perf-audits'
```

(`git grep` covers every tracked file type — config, TOML, YAML — not just the obvious extensions.)

Expected: roughly 20 hits, ALL in prose/historical documents — `README.md` and `CONTRIBUTING.md` (rewritten in Task 11), `plans/implementation/**` (the 2025 MVP plans), `design/reviews/**`, `design/meta/**` (design-log, memory-index, risks), `design/chat-prompts.txt`. These are historical records: leave every one of them untouched (editing them is scope creep). The pass criterion is: **zero hits in code or config** (anything under `app/`, or any `.json`/`.toml`/`.yml`/`.ts`/`.py` file outside those doc trees). If such a hit appears, resolve it before committing.

- [ ] **Step 10.2: Commit**

```bash
git commit -m "chore: remove abandoned Angular frontend and Angular-specific design docs

Superseded by app/frontend/web (React). Git history preserves the tree."
```

### Task 11: Documentation updates

**Files:**
- Modify: `README.md`, `CONTRIBUTING.md`, `design/specifications/test-spec.md`, `design/specifications/accessibility-spec.md`, `design/specifications/i18n-spec.md`

**Context:** The spec's "Teardown & documentation updates" section is the requirements list. These are prose edits; the content requirements below are exhaustive — do not invent additional policy.

- [ ] **Step 11.1: README.md**

- Core Technologies: replace `**Frontend:** Angular` with `**Frontend:** React 19 (Vite, TypeScript, Tailwind CSS v4, TanStack Router/Query)`.
- Prerequisites: drop the Angular CLI requirement; keep Node ≥ 20.19.
- Replace the "Frontend Setup (Angular)" section with: `cd app/frontend/web`, `npm install`, `npm run dev` (app at `http://localhost:5173`, proxying `/api/v1` to the backend on `:8000`), plus the type-regeneration flow: after backend schema changes run `cd app/backend && pdm run export-openapi` then `cd app/frontend/web && npm run generate:api`.
- Mark the 2025 screenshot as pre-rebuild ("Angular-era screenshot; React rebuild in progress").

- [ ] **Step 11.2: CONTRIBUTING.md**

- Rewrite frontend setup/commands sections for `app/frontend/web` (same commands as README, plus `npm run lint`, `npm run format`, `npm run test`).
- State the dependency policy: exact pins enforced by `.npmrc` (`save-exact=true`); no `^`/`~` in `package.json`.
- Add a "Backend dev prerequisites" subsection with the env-file location (`app/backend/src/.env`), required vars incl. the JSON-list format for `AGGREGATION_REGION_IDS`, the Valkey requirement, the drop/recreate-on-restart + ingestion-delay behavior, and `DATABASE_URL_TESTS` for the test suite (content per pitfalls ENV-1/ENV-2 and Task 9 Step 9.1).

- [ ] **Step 11.3: design/specifications/test-spec.md**

- §4 frontend rows: Karma/Jasmine → Vitest + React Testing Library; Protractor → Playwright (deferred until the /impeccable phase delivers the UI it would smoke-test); `@axe-core/angular` → `eslint-plugin-jsx-a11y` (active) + `vitest-axe` on key views (arrives with /impeccable).
- §6: add that frontend CI build-fail wiring for a11y scans is deferred until frontend CI exists; the M1 posture is lint-time + test-time checks.

- [ ] **Step 11.4: design/specifications/accessibility-spec.md and i18n-spec.md**

- accessibility-spec.md: replace Angular-specific mandatory tooling references with the React equivalents above; the WCAG requirements themselves are framework-agnostic and stay untouched.
- i18n-spec.md: add a status note that M1 ships hardcoded English strings by explicit decision (spec Non-goals), with i18n wiring revisited before feature milestones; replace Angular-specific implementation guidance with a pointer to that note (do not delete the framework-agnostic requirements).

- [ ] **Step 11.5: Verify and commit**

```bash
grep -rn "ng serve\|Angular CLI\|angular" README.md CONTRIBUTING.md design/specifications/ | grep -iv "angular-era\|historical\|previously\|was Angular"
```

Expected: no hits describing Angular as the current stack (mentions framed as history are fine).

```bash
git add README.md CONTRIBUTING.md design/specifications/
git commit -m "docs: update README/CONTRIBUTING/specs for the React frontend

Frontend sections now describe app/frontend/web (React 19 + Vite +
Tailwind v4 + TanStack); test-spec frontend tooling moves to Vitest/RTL
with Playwright and vitest-axe deferred to the /impeccable phase; i18n
spec notes the explicit M1 English-only deferral."
```

### Phase 3 group review

- [ ] Review Phase 3 from ≥3 perspectives (acceptance checklist honesty — every box actually observed; teardown completeness; docs accuracy against what was really built). Minimum 3 rounds; continue until clean.
- [ ] Update all banners and the Execution Status table; fill Deviations/Discoveries.
- [ ] Milestone exit: invoke superpowers:finishing-a-development-branch. The follow-on phase is `/impeccable` (design system + full F002/F003 interface build) per the spec's Process section.
