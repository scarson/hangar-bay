ABOUTME: Specifies complete, uncached public contract item fetching and removal of an unreachable exception model.
ABOUTME: Carries execution gates and regression checks for preserving enrichment state after incomplete reads.

# Contract item fetch integrity implementation plan

> **For agentic workers:** Use `superpowers:subagent-driven-development` to execute the two tasks sequentially, with a fresh implementer and review for each. Use checkbox steps to track execution. Sam has authorized autonomous execution after the plan review; no execution-method question is needed.

**Goal:** An item fetch either returns every advertised page or fails without supplying a prefix that ingestion could mark complete.

**Architecture:** Give `ESIClient.get_contract_items` an uncached paginator that uses the existing transient-retry transport. Keep region-list and single-object caching intact. Replace service tests that manufacture `ESINotModifiedError` with real `ESIClient` calls over controlled HTTP and Redis boundaries. Then remove the unreachable exception and handlers.

**Tech Stack:** Python 3.14, HTTPX, pytest/pytest-asyncio, SQLAlchemy async, PostgreSQL, Valkey. No dependency changes.

## Living Document Contract

This plan is a living document. Every executing agent MUST update it as
execution progresses, not only at completion.

Where this project has no git repository, every reference below to a SHA,
a branch, or a PR means the nearest durable equivalent the project does
offer (a dated revision, a build identifier, a release tag), and where
none exists the banner states that plainly. An invented SHA is worse than
an absent one: it reads as an anchor and sends the next agent looking for
a commit that never existed.

- **Before any phase claim:** no phase may be claimed while the
  **Plan review** line in Execution Status reads ⬜ NOT RUN. An unreviewed
  plan is not executable. Run the review (`plan-review-cycle`) and let its
  completion flip the line, or — if this plan was legitimately exempted by
  the user — record that at the line as ⏭ SKIPPED with the date, so the
  exemption is visible instead of indistinguishable from an omission. A
  line still reading ⬜ at execution time means the gate was skipped
  silently, which is the one state this record exists to make impossible.
- **On phase claim:** before flipping your own banner, the executor MUST
  check the preceding phase's banner against git reality — a ✅ SHIPPED
  banner's recorded SHA reachable on the default branch, a 🚧 banner live
  per the stale-claim signals below. If a banner does not match reality,
  correct it first. A plan's accuracy is checked by the next agent to
  arrive, not by the one who left it; this is the only read-back the
  contract has. Then flip your own banner to 🚧 IN PROGRESS
  with a claim timestamp (ISO 8601 UTC) and the active branch name. The
  banner MUST NOT include an expected-completion estimate — agents cannot
  reliably estimate their own wall-clock, and a fabricated duration
  becomes a stale anchor that misleads future readers. Followers
  encountering a 🚧 banner determine liveness by observable signals (PR
  existence, recent branch commits), not by arithmetic on expected times.
  See `/writing-plans-enhanced` §Plan construction requirements for the
  stale-claim reclaim protocol.
- **On phase ship:** the executor MUST update that phase's **Execution
  Status** banner with the shipped commit SHA(s) and date. If a PR is
  open, the PR number and URL MUST appear in the Execution Status table.
  Recorded SHAs stay resolvable because this project merges with
  `--merge` and preserves per-commit history; under a squash-merge
  workflow, record the squashed commit that landed on the default branch
  instead, or the banner points at a SHA no reader can find.
  **The banner ships in its own commit, after the work.** A commit
  cannot contain its own hash, so the banner naming a SHA cannot ride
  in the commit that SHA identifies. Commit the work with a pathspec
  that excludes this plan, read the SHA back from git, then commit the
  banner and table update on top. Amending is not a way out — it
  rewrites the SHA you just recorded. Where the phase ships through a
  PR, **On PR merge** below is a second such update for the same
  reason, and lands after the merge.
- **On phase defer:** the executor MUST update the banner with ⏸ status
  AND a prose description of the unblock condition + a link to the
  likely-unblocker artifact (plan page, task, or PR whose own Execution
  Status banner will signal completion). Prose + link is durable across
  paraphrases and scope edits; exact-string coordination between agents
  is not.
- **On PR merge:** the executor MUST record the merge SHA in the banner
  + the Execution Status table.
- **On deviation from the written plan** (scope edits, structural
  refactors, dropped tasks, reordered phases): the executor MUST
  inline-document the deviation in the affected task AND summarize it
  in the Execution Status section's "Deviations" subsection.
  Deviation state MUST NOT live only in PR notes or status reports.
- **On discovery** (pre-existing drift surfaced during execution, new
  bugs found, architectural issues noted): the executor MUST record it
  in the Execution Status section's "Discoveries" subsection with
  pointers to the files/lines affected. Follow-up dispatches read this
  subsection to avoid duplicate discovery work.

**Layout invariant.** Only the two one-line headers — **Plan review** and
**Overall** — sit above the status table; the table follows them directly.
Deviations and Discoveries are subsections
*below* it and MUST NOT be placed above it — the table is what a reader
needs in the first screen, and it stops being that the moment a growing
narrative sits on top of it. Entries in both subsections are a one-line
summary plus a pointer to where the detail lives (the affected task, the
file:line); they are not the place to tell the story.

The plan SHOULD reflect reality at the end of every session that touches
it. Anything worth putting in a status report to the user is worth
putting in the plan.

Rationale: `/writing-plans-enhanced` §Plan construction requirements.
Writing at ship time is
cheap; reconstruction by downstream readers is expensive, compounds
across dispatches, and fails silently when state is split across PR
notes and commit messages.

## Execution Status
<!-- Plan review and Overall are the only lines above the table. New content goes
     in the Deviations / Discoveries subsections below it — never above the table. -->

**Plan review:** ✅ COMPLETED 2026-09-05 — 5 rounds, terminating round independent (cold read, GPT-6 Astra high)
**Overall:** 0/2 phases shipped; 0 deferred.

| Phase | Status | Ship SHA(s) | Notes |
|---|---|---|---|
| 1 — Complete uncached item reads | ⬜ Not started | — | Task 1 |
| 2 — Actual 304 and failure boundaries | ⬜ Not started | — | Task 2; depends on Task 1 |

### Deviations

- Preparation PR review extended Task 1 to register the consumed `200 X-Pages` header in the ESI drift monitor, test its projection/comparison and regenerate that monitor's snapshot. This keeps the changed ESI dependency covered in the same implementation PR. The two-task sequence and production merge classification are unchanged.

### Discoveries

- _None yet._

## Scope and evidence

**Spec:** [Ingestion clean-sheet design, Stage 2 enrichment](../audits/m5-recon/ingestion-clean-sheet-design.md#stage-2--enrichment) specifies the decision to avoid item-page ETag caching. The [Plan B handoff's correctness docket](../superpowers/handoffs/2026-07-27-plan-b-handoff.md#plan-b--designed-not-planned-what-it-now-carries) pairs this with the unreachable-exception cleanup. This plan implements only those two prerequisites. Governor, request deadlines, concurrency, queue claims, scheduling, discovery-generation consistency, freshness storage and alert delivery remain separate work.

Source paths below are relative to `app/backend/src/fastapi_app/`, inspected on branch `codex/ingestion-pipeline-plan` based on `f457acb2877ff0e33da8ff3419cd3b0d6a4554e9`:

| Source | Mechanism |
|---|---|
| `core/esi_client_class.py:190–253,331–340` | Items use the cached paginator; a 304 with an evicted body reads as `[]`. |
| `core/esi_client_class.py:309–324` | Empty page terminates before checking `X-Pages`, even after a nonempty prefix. |
| `services/background_aggregation.py:848–904,906` | A returned prefix becomes item rows and a processed contract; status computation can stamp it complete and clear a ship flag whose ship was on a later page. |
| `core/exceptions.py:19`, `services/background_aggregation.py:15,510,895` | `ESINotModifiedError` has no production raise site. HTTP 304 resolves inside the cached client. |

The official [ESI OpenAPI document](https://esi.evetech.net/meta/openapi.json) was read on 2026-09-05 with `X-Compatibility-Date: 2026-07-21`. It documents `GET /contracts/public/items/{contract_id}` as follows: 200 returns the item array and integer `X-Pages` (total pages). A 204 means the contract expired or was recently accepted. The document does **not** mark `X-Pages` required. The client policy below deliberately fails closed when completeness cannot be established. It does not claim that the schema makes that header mandatory. A normal public item response for contract `234802718` on that date returned 200, `X-Pages: 1`, and one item. That sample establishes neither a corpus-wide guarantee nor a page-count bound.

### Global constraints

- Preserve `/v1/contracts/public/items/{contract_id}/`, compatibility-date and User-Agent defaults, existing HTTP timeouts and 420/429/5xx/transport retry behavior. Item requests carry no conditional headers. They perform no Redis reads or writes. Production client constructors already supply only application default headers. Do not mutate shared HTTP-client headers.
- Keep `get_esi_data_with_etag_caching`, its missing-body behavior, `_last_page_reached`, region discovery, universe-object caching and retry policy unchanged. This slice does not claim region-list completeness. It does not repair existing completed rows.
- No `ENRICHMENT_VERSION` bump, migration, cache purge, backend startup, production data writes, deployment, or broad formatter run. The only generated artifact changed is the ESI monitor's `snapshot.json`, regenerated by its CLI as specified in Task 1; never hand-edit it or regenerate backend API/frontend artifacts. Existing expired/accepted/zero-item retry semantics stay intact.
- A production PR has `## Merge classification` followed by `Review — data-integrity paths`. Publish with green CI and independent review. Then leave the PR for Sam's merge decision. Do not auto-merge this production change.
- Read [implementation pitfalls](../pitfalls/implementation-pitfalls.md) and [testing pitfalls](../pitfalls/testing-pitfalls.md). Apply ESI-1/4 (route and date), ESI-3 (optional field omissions), SQLA-5 (preserve derived state), TEST-4/11/24/25 (observe every page and returned row), TEST-12 (falsification), TEST-21 (real failure classes) and TEST-26 (re-sighting through the writer).
- There is no concurrent production-code edit in these tasks. Both touch the ESI-client and aggregation tests. Task 2 therefore starts only after Task 1's review and commit. Mark a phase shipped after integration into `dev`. Until then, keep it in progress with its verified implementation commit(s), PR link and task completion count. This preserves the contract's read-back against the integration branch.

### Verification environment

Run from this worktree's `app/backend`. A Python 3.14.3 venv and PDM 2.28.0 tool are installed from the frozen lock. The ignored `src/.env` selects this task's scratch PostgreSQL database `hb_item_fetch_integrity_20260905a` and Valkey DB 12. Do not reuse them concurrently. Do not print/copy credentials. The coordinating task verified the starting state: 184 focused tests and 822 full backend tests passed with pristine output on 2026-09-05. The ignored `.cache/item-fetch-baseline/runbook.md` contains the local setup. It is session-local and may be absent in a future checkout. Future executors provision dedicated test DB/cache settings from the tracked project configuration. They then verify their own baseline.

```powershell
$env:PYTHONUTF8 = '1'
& ./.venv/Scripts/python.exe -m pytest -q --basetemp .cache/item-fetch-verification/pytest-tmp src/fastapi_app/tests/core/test_esi_client.py src/fastapi_app/tests/services/test_background_aggregation.py
& ./.venv/Scripts/python.exe -m flake8 .
& ./.venv/Scripts/python.exe -m pytest -q --basetemp .cache/item-fetch-verification/pytest-tmp
```

The worktree-local `--basetemp` avoids an observed host-temp permissions failure. Do not modify tests to accommodate that host setup. Do not suppress errors to accommodate it. Targeted test selections below use the same executable and `--basetemp` option.

## Phase 1 — Complete uncached item reads

**Execution Status:** ⬜ NOT STARTED

### Task 1: Return complete item pages without a cache dependency

**Files:** Modify `app/backend/src/fastapi_app/core/esi_client_class.py`. Add or strengthen tests in `app/backend/src/fastapi_app/tests/core/test_esi_client.py` and `app/backend/src/fastapi_app/tests/services/test_background_aggregation.py`. Also modify `app/backend/tools/esi_spec_monitor/manifest.py`, `app/backend/tools/esi_spec_monitor/monitor.py`, and `app/backend/tools/esi_spec_monitor/tests/test_monitor.py`; regenerate `app/backend/tools/esi_spec_monitor/snapshot.json`. These seven files are Task 1's scope. Do not alter service persistence logic.

**Interfaces:** Keep `async get_contract_items(self, contract_id: int) -> list[dict[str, Any]]`. Call `_get_with_transient_retry(path, headers=None)` for each page. Add one private response-decoding helper if needed to keep functions within the existing complexity limit of 10. The helper consumes `httpx.Response` and returns `(list[dict[str, Any]], int)` for a valid 200 response.

**Before starting work:** Invoke `superpowers:test-driven-development`. Read `docs/pitfalls/testing-pitfalls.md`. Follow failing test → minimal implementation → green. Include error paths while writing tests.

- [ ] **Write boundary tests against real HTTPX responses.** Use `httpx.MockTransport` with `httpx.AsyncClient`, or the existing `httpx_mock` fixture. Do not stub `get_contract_items`, the cached paginator, or `_get_with_transient_retry` in tests claiming item-fetch correctness. A Redis double whose every accessed operation fails makes the no-cache requirement observable. Keep exact returned rows and request paths as assertions, not just counts.

```python
from fastapi_app.core.config import Settings


async def test_item_pages_do_not_use_conditional_headers_or_redis():
    settings = Settings(
        _env_file=None,
        DATABASE_URL="postgresql+asyncpg://u:p@localhost/x",
        CACHE_URL="redis://localhost:6379/9",
        ESI_USER_AGENT="hangar-bay-tests",
    )
    expected = [{"record_id": n, "type_id": 587} for n in (41, 42, 43)]
    seen = []

    def respond(request):
        seen.append(str(request.url))
        assert "if-none-match" not in request.headers
        assert "if-modified-since" not in request.headers
        assert request.headers["x-compatibility-date"] == settings.ESI_COMPATIBILITY_DATE
        assert request.headers["user-agent"] == settings.ESI_USER_AGENT
        page = int(request.url.params["page"])
        assert page in (1, 2, 3)
        return httpx.Response(200, json=[expected[page - 1]], headers={"X-Pages": "3"})

    class NoCacheAccess:
        def __getattr__(self, name):
            raise AssertionError(f"item fetch accessed Redis: {name}")

    async with httpx.AsyncClient(
        base_url="https://esi.evetech.net",
        headers=ESIClient.default_headers(settings),
        transport=httpx.MockTransport(respond),
    ) as http_client:
        client = ESIClient(settings, http_client, NoCacheAccess())
        assert await client.get_contract_items(999) == expected
    assert seen == [
        "https://esi.evetech.net/v1/contracts/public/items/999/?page=1",
        "https://esi.evetech.net/v1/contracts/public/items/999/?page=2",
        "https://esi.evetech.net/v1/contracts/public/items/999/?page=3",
    ]
```

- [ ] **Add the response-policy cases.** Where applicable, parameterize failures on page 1 and page 3 of an advertised three-page result. On a late failure, assert that the call raises and never returns earlier rows. All expected requests stop at the failed page (plus existing transient retries). These are client policy decisions, not extra upstream promises:

| Response | Required result |
|---|---|
| 200, valid JSON array of objects, consistent positive integer `X-Pages` | Read pages 1 through the first advertised total, in order, then return the concatenation. |
| Page 1: 200, `[]`, `X-Pages: 1` | Return `[]`; ingestion retains its zero-item retry behavior. |
| Page 1: 204 | Return `[]` without requiring JSON or `X-Pages`. |
| Page 2 or later: 204 | Raise `ESIRequestFailedError(status_code=204)`; discard accumulated pages. |
| Unexpected 304 on any page | Raise `ESIRequestFailedError(status_code=304)`; never consult Redis. |
| Missing/empty/non-integer/zero/negative `X-Pages`, or total changes on a later page | Raise `ESIRequestFailedError(status_code=200)`; never guess a last page. An `int()` parsing failure retains its `TypeError`/`ValueError` cause; range and consistency guards have no parser cause to retain. |
| Empty body, invalid JSON, JSON null/object/scalar, or array containing a non-object | Raise `ESIRequestFailedError(status_code=200)` with page context; JSON-decode failures retain their cause. |
| `[]` anywhere in an advertised multipage result, including the final page | Raise `ESIRequestFailedError(status_code=200)`; only the single-page empty result is accepted. |
| Other statuses (including 404 and unexpected success statuses) | Raise `ESIRequestFailedError` carrying that status. Existing transient failures still take the shared retry path before surfacing. |

Do not validate every item field here. The envelope check establishes a list of dictionaries. Required-key mapping and optional-field semantics remain in the existing ingestion mapping. Consistent page counts establish advertised-page completeness. They do not establish an atomic upstream generation or protection against every possible upstream content error.

- [ ] **Run the new tests and record the expected failure.** Select the new item-page cases in `tests/core/test_esi_client.py`. The no-cache test must fail because the current method accesses Redis. For late-page error cases, use a benign Redis boundary that permits the current cached paginator to reach the failing page. Reusing `NoCacheAccess` there would stop at page 1 and hide the prefix defect. Late empty/204 cases must expose a returned prefix. Do not accept unrelated fixture/setup failures as the red evidence.

- [ ] **Implement the uncached walk.** The following shows the intended control flow. Use a small named decoder. Do not expand the generic cached helper or add cache-mode switches:

```python
async def get_contract_items(self, contract_id: int) -> list[dict[str, Any]]:
    path = f"/v1/contracts/public/items/{contract_id}/"
    items = []
    total_pages = None
    page = 1
    while True:
        page_path = f"{path}?page={page}"
        response = await self._get_with_transient_retry(page_path)
        if response.status_code == 204 and page == 1:
            return []
        page_items, response_pages = self._read_contract_item_page(response)
        if total_pages is not None and response_pages != total_pages:
            raise ESIRequestFailedError(200, f"Inconsistent X-Pages for {page_path}")
        total_pages = response_pages
        if not page_items and (page != 1 or total_pages != 1):
            raise ESIRequestFailedError(200, f"Empty item page for {page_path}")
        items.extend(page_items)
        if page == total_pages:
            return items
        page += 1
```

The decoder makes the response contract explicit:

```python
def _read_contract_item_page(
    self, response: httpx.Response
) -> tuple[list[dict[str, Any]], int]:
    path = response.request.url.raw_path.decode("ascii")
    if response.status_code != 200:
        raise ESIRequestFailedError(response.status_code, f"Unexpected item response for {path}")
    try:
        payload = response.json()
    except ValueError as exc:
        raise ESIRequestFailedError(200, f"Invalid item JSON for {path}") from exc
    if not isinstance(payload, list) or any(not isinstance(item, dict) for item in payload):
        raise ESIRequestFailedError(200, f"Invalid item array for {path}")
    try:
        total_pages = int(response.headers.get("X-Pages"))
    except (TypeError, ValueError) as exc:
        raise ESIRequestFailedError(200, f"Invalid X-Pages for {path}") from exc
    if total_pages < 1:
        raise ESIRequestFailedError(200, f"Invalid X-Pages for {path}")
    return payload, total_pages
```

Include the response request path in each message. Do not log bodies. No cache calls, conditional headers, short-page heuristics, compatibility fallback, retry-policy changes or silent catch-and-return-prefix behavior.

- [ ] **Strengthen the database seam and demonstrate failure preservation.** Extend `test_multipage_item_fetch_persists_every_row_and_completes` from two pages to three distinct page payloads over real HTTPX responses. Use non-ship types on the first pages and an included ship on the last. Supply complete required row fields (`record_id`, `type_id`, `quantity`, `is_included`). Supply ordinary location/name/type/group/category boundary responses. Assert the exact stored record-ID set, `is_ship_contract is True`, `item_processing_status == "COMPLETED"`, and the current enrichment version.

  Add `test_incomplete_item_fetch_preserves_enrichment_state`. Seed a complete ship contract through `_process_contracts`. Record its persisted item rows. Then bump `bg_agg.ENRICHMENT_VERSION` **only with monkeypatch in the test** so the contract is fetched again. The second fetch returns non-ship pages 1 and 2 followed by a page-3 failure. Parameterize late 304, 204, empty array and transport failure. Run the real `ESIClient` and `_process_contracts`. Do not patch either method. Read state back from SQL after each run. Refresh any retained ORM object with `await db_session.refresh(contract)` so a stale identity-map instance cannot satisfy preservation assertions. Assert all earlier item rows and the ship flag are unchanged. Assert status stays `COMPLETED` at the previous version. Assert another run with three valid pages reaches the current version. A fresh contract whose page 3 fails must remain `PENDING_ITEMS` with no item rows and no enrichment stamp. Include a succeeding contract in the same batch to prove the failure remains isolated.

  The page-3 transport-failure handler raises `httpx.ConnectError("item transport unavailable", request=request)` on each of its three attempts. Capture the existing sleep boundary to avoid real backoff delays. For this contract's failing fetch, assert five item requests whose ordered URLs contain pages `[1, 2, 3, 3, 3]`, with three page-3 attempts and waits `[0.5, 1.0]`. Scope the request collection to this contract and this fetch, excluding seed/recovery passes, metadata requests and the succeeding contract. Capture each retry warning and the aggregation error by logger, level and complete message. For the failed contract ID `cid`, the aggregation ERROR message must equal `f"Failed to fetch items for contract {cid}: ESI request failed with status 0: Network error for /v1/contracts/public/items/{cid}/?page=3: item transport unavailable"`. Its `LogRecord.exc_info` must contain an `ESIRequestFailedError` with `status_code == 0` and `message == f"Network error for /v1/contracts/public/items/{cid}/?page=3: item transport unavailable"`. The transport helper does not chain a cause. Cause assertions belong to the decoder's JSON/header parsing failures. If fixture wiring is wrong, do not silence unrelated logs or weaken state assertions.

- [ ] **Verify the full focused modules and lint.** Preserve existing cached-paginator tests unchanged, including its missing-body 304 behavior. Preserve the item wrapper's existing 420/429 retry assertions. Verify the no-cache test's request-level User-Agent and compatibility-date assertions on every item page. Keep the existing compatibility tests as the separate configuration/monitor consistency guard. Mutate the new walk to stop after page 1 and to accept a late empty/204 result. Each mutation must fail the relevant row/state assertion. After each mutation, restore source and rerun the guarded tests. Do not commit mutants.

- [ ] **Register and monitor the consumed pagination header.** The [ESI dependency checklist](../pitfalls/implementation-pitfalls.md#4c--review-checklist) requires changed dependencies in the monitor in the same PR. The current monitor projects body fields and statuses, but no response headers. This step covers published schema drift; it cannot guarantee runtime header presence or replace the HTTP boundary tests.

  Add `Endpoint.consumed_response_headers: dict[str, str]` with an empty default, explicitly describing headers of the `200` response. Register only the item endpoint's `X-Pages`, attributed to `core/esi_client_class.py ESIClient.get_contract_items / _read_contract_item_page`. Project declared headers into a separate `response_headers` map, omitted for endpoints with no declarations. Match names case-insensitively and use the subject `response-header:200:x-pages`. Resolve local Response Object, Header Object and schema references with `_resolve`; preserve its errors for unresolved references. Use existing type/format/enum/array-shape descriptors and the upstream Header Object's `required`, defaulting to `false`. Do not infer requiredness from the client's fail-closed policy. Ignore descriptions, undeclared headers and other response statuses.

  Add the qualified header consumer to `consumers`. Compute body misses against body fields and header misses against `response_headers`, then combine them in `consumed_fields_absent_from_spec`. Extend `_diff_endpoint` with `_diff_keyed` over `response_headers`, using `FIELD_ADDED` / `FIELD_REMOVED`, `_diff_field_shape` and `removed_severity=None`. Preserve manifest-consistency deduplication and existing severity rules: consumed removals, type/format/enum changes and required-to-optional changes are breaking in the pinned view; additions and optional-to-required changes are informational; all newest-view findings are informational through `_Context.add`. Keep qualified subjects and consumer attribution in rendered reports. Preserve body, parameter and status behavior.

  Write fixture tests against real `project`, `build_snapshot`, `compare_snapshots` and `format_report` calls, and run them red before implementation. Assert these independent contracts:

  - Exact optional integer header descriptor and consumer; omitted `required` is `false`, explicit `true` is retained. Equivalent local response/header/schema references yield the same header descriptor and consumer; unresolved consumed-header references raise. Case-only spelling changes and key reordering are quiet.
  - Independent removal, type, format, enum and both requiredness mutations yield exact finding kind, subject, consumer and pinned severity. Mutating only the newest view gives its informational finding; mutating both views gives one finding per affected view. The rendered report identifies the item caller and header.
  - Adding an undocumented header dependency yields `MANIFEST_FIELD_UNDOCUMENTED`; ordinary removal yields only header `FIELD_REMOVED`, without a duplicate manifest finding. Restoration is informational. Unchanged projections remain quiet, and body fields or request parameters with similar names cannot satisfy the header dependency.
  - Undeclared 200 headers, 204 `X-Pages`, and descriptions stay outside this projection. Preserve every existing monitor test. Assert the actual manifest declares only the item endpoint's `X-Pages` dependency.

  Run the complete monitor module with `& ./.venv/Scripts/python.exe -m pytest -q --basetemp .cache/item-fetch-verification/pytest-tmp tools/esi_spec_monitor/tests/test_monitor.py`. Then run `pdm run esi-spec-monitor --update`, inspect `git diff -- tools/esi_spec_monitor/snapshot.json`, and run `pdm run esi-spec-monitor` (the default check, with no `--check` flag). Resolve the installed PDM invocation from the environment runbook; on this prepared Windows environment it is `& ./.cache/.venv/pdm-tool/Scripts/python.exe -m pdm`, not its relocated launcher. The script supplies `PYTHONPATH=tools` and retrieves both pinned and newest metadata views. Never hand-edit the snapshot or manufacture it after a fetch failure.

  Verify both views contain the declared header's integer descriptor, upstream optionality, schema format and consumer, with no missing declaration. The dated upstream observation in this plan described `required: false`; investigate any changed declaration before accepting it. Confirm body projections remain intact and the intended diff adds only the item header projection/consumer. Investigate unrelated live drift instead of accepting it to make the check green. Require the check to exit 0 and report no drift. Rerun the focused modules, lint and full backend suite after integrating this step; the full suite already includes `tools` tests. No workflow, dependency, `pyproject.toml`, backend API export or frontend code-generation change belongs to this step.

- [ ] **Review and commit Task 1.** Review tests against the pitfalls. Confirm pristine green results. Obtain fresh spec-compliance and code-quality reviews. Explicitly stage the seven task files. Use `fix(api): preserve complete contract item fetches` for the production commit. Record its SHA under the phase's in-progress banner in a separate plan-status commit. Do not mark it integrated before merge.

## Phase 2 — Actual 304 and failure boundaries

**Execution Status:** ⬜ NOT STARTED

### Task 2: Remove the unreachable exception and preserve real cached-region behavior

**Dependency:** Task 1's code and tests are committed and reviewed on the execution branch. Read that commit and this phase's banner before claiming it. The parent phase remains in progress until the combined PR integrates.

**Files:** Modify `app/backend/src/fastapi_app/core/exceptions.py`, `app/backend/src/fastapi_app/services/background_aggregation.py`, and `app/backend/src/fastapi_app/tests/services/test_background_aggregation.py`. Reuse the existing core-client helpers only where they represent actual HTTP/Redis boundaries. Leave `get_public_contracts` and cached-paginator production logic unchanged.

**Interfaces:** Region 304 responses resolve to cached `list[dict]` values from real `ESIClient.get_public_contracts(region_id)`. `_fetch_regions(region_ids)` still returns `(contracts, regions_ok, regions_failed)`. Cached contracts are region-stamped and processed. Success is recorded after commit. Item transport failures surface as `ESIRequestFailedError`, leaving enrichment retryable through the existing exception-isolation path.

**Before starting work:** Invoke `superpowers:test-driven-development`. Read `docs/pitfalls/testing-pitfalls.md`. Follow failing test → minimal implementation → green. Include the real boundary behavior in tests before removing branches.

- [ ] **Rewrite each impossible service test in place, preserving its purpose and assertions.** The five test functions that import the exception must all remain represented. The last freshness function is parameterized across two Redis failures:

| Existing test | Replacement boundary and retained assertion |
|---|---|
| `test_reingestion_with_unmodified_items_keeps_ship_flag` | Rename to describe item-fetch failure; use real HTTP `ConnectError` → retry exhaustion after a test-only version bump. Preserve observed fetch attempt, ship flag, completed status and previous-version assertions. Task 1's late-page test provides complementary coverage. |
| `test_freshness_success_when_all_regions_304` | Two region HTTP 304s with nonempty cached courier bodies and `X-Pages: 1`; seed every `_hb_region_id` as `-1`. Take `db_session`, bind `bg_agg.AsyncSessionLocal` to a `TEST_DATABASE_URL` sessionmaker through `monkeypatch`, and dispose the engine in `finally`. Run real region fetch and `_process_contracts` through that committed test transaction; assert both contracts persisted with their distinct source regions, success counters 2/0, last-success time and advancing gauge. |
| `test_freshness_recorder_overwrites_a_non_object_prior_record` | Real region HTTP 304 plus cached empty array yields a valid no-op; keep corrupt prior record `[]` and overwrite/type/outcome/timestamp assertions. |
| `test_a_freshness_cache_failure_never_fails_the_run` | For both existing `get`/`set` recorder failures, run a real region HTTP 304 plus cached empty array. Preserve failure capture, absent ingest record, lock release, and proof that the run reached HTTP. |
| `test_fetch_regions_counts_a_304_region_as_ok` | One region HTTP 304 with a nonempty cached courier body; the other HTTP 200 with a courier body. Seed every `_hb_region_id` as `-1`, then assert **both** contract IDs, their actual source-region stamps and counters 2/0. |

  Construct the real `ESIClient` with a controlled HTTP transport and Redis get/set boundary double; do not stub `get_public_contracts`. Every contract fixture in the cached-region cases uses `type="courier"` and `_hb_region_id=-1`, including the other region's 200 body. Courier persistence exercises region stamping without item fetching or committing item/taxonomy rows that could contaminate unscoped enrichment queries. Task 1 owns item enrichment coverage.

  For cached-region tests that run `_process_contracts`, serve real `POST /v3/universe/names/` responses covering the submitted IDs and `GET /v2/universe/stations/60003760/` with a valid `system_id` (for example, `30000142`). These requests must execute through the real client, with the Redis double supporting the station object's get/set cache boundary. Assert no unexpected WARNING/ERROR records on the successful path. Do not let an unserved item, names, station or taxonomy request become a swallowed error while freshness still reports success.

  Cached region keys are `etag:/v1/contracts/public/{region_id}/?page=1` and `data:/v1/contracts/public/{region_id}/?page=1`. Populate data as `json.dumps(body)` and ETag as a real string/bytes value. Send a real 304 with an empty wire body; only Redis contains the contract data. For no-op recorder tests, populate a cached `[]` deliberately and keep `X-Pages: 1` in the HTTP response. Keep the ESI cache double separate from `_FakeLockRedis`, which owns the ingestion lock and freshness record.

```python
# A 304's wire body is empty. The returned contracts must come from Redis.
region_path = "/v1/contracts/public/10000002/?page=1"
cached_contract = {**_ship_contract_dict(920001), "type": "courier", "_hb_region_id": -1}
other_contract = {**_ship_contract_dict(920002), "type": "courier", "_hb_region_id": -1}
cache = {
    f"etag:{region_path}": "region-generation",
    f"data:{region_path}": json.dumps([cached_contract]),
}
# In the transport handler for that exact path:
assert request.headers["if-none-match"] == "region-generation"
response = httpx.Response(304, headers={"X-Pages": "1"})
# The other region's HTTP 200 body is [other_contract], also with X-Pages: 1.
# After the real _fetch_regions over this 304 and the other region's 200:
assert [(c["contract_id"], c["_hb_region_id"]) for c in contracts] == [
    (920001, 10000002), (920002, 10000043),
]
assert (regions_ok, regions_failed) == (2, 0)
```

- [ ] **Run the replacements before deleting production code.** They should already pass through actual current 304 behavior. This is characterization, not a manufactured failing test for dead-code deletion. Task 1 supplies the production bug's red/green evidence. Falsify the region-data assertion by temporarily making cached 304 reads return `[]`. The nonempty cached-region tests must fail. Restore and rerun.

  Add a real-boundary cached-region commit-failure case using cached courier contracts with input region stamps `-1`. Take `db_session`. Bind `bg_agg.AsyncSessionLocal` to a `TEST_DATABASE_URL` sessionmaker through `monkeypatch`. Follow `test_freshness_success_when_all_regions_fetch_ok` for database setup and `test_freshness_failure_when_commit_raises` for the commit failure boundary. Dispose the engine in `finally`, even if an assertion fails. Serve names and station HTTP responses as specified for the successful cached-region case. Assert outcome `failure` with the previous last-success time and gauge preserved. Capture/assert the expected failure log. A successful 304 fetch cannot freshen a failed transaction.

  Both tests that drive a committed `run_aggregation` transaction must use this explicit test-database binding. The module's ordinary `AsyncSessionLocal` comes from `DATABASE_URL`, not `DATABASE_URL_TESTS`:

```python
from fastapi_app.tests.conftest import TEST_DATABASE_URL
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

# The test takes db_session and monkeypatch fixtures. db_session creates and
# tears down the test schema; run_aggregation commits through its own session.
engine = create_async_engine(TEST_DATABASE_URL)
maker = async_sessionmaker(engine, expire_on_commit=False)
monkeypatch.setattr(bg_agg, "AsyncSessionLocal", maker, raising=False)
try:
    with patch.object(bg_agg.aioredis, "from_url", return_value=_FakeLockRedis(store)):
        await service.run_aggregation()
finally:
    await engine.dispose()
```

  In the commit-failure test, inject the failing `commit` on sessions created by this `maker`, as the existing commit-failure test does. Preserve this test-DB binding and cleanup.

- [ ] **Remove only unreachable production code.** Delete the `ESINotModifiedError` class, its import, and the dedicated catches in `_fetch_regions` and `_fetch_item_rows`. Retain their ordinary `Exception` isolation and counter logic. Replace comments asserting that all 304s skip work with accurate descriptions. Cached nonempty bodies are processed and committed. Only empty fetch results take the no-data path. Search the touched tests' section comments and docstrings for the same false model. Preserve comments whose claims remain true. Do not add compatibility aliases or catches for the deleted class.

```powershell
# From repository root; no matches is the expected final source state.
rg -n ESINotModifiedError app/backend/src/fastapi_app
```

- [ ] **Verify and independently review the combined batch.** Using the environment commands, run the focused modules, lint, then the complete backend suite. Confirm all former scenarios remain covered. Confirm all expected error logs are captured/asserted. Confirm existing region ETag and retry tests pass. Confirm there are no new skips or source changes outside the listed files. After completing this group, review once from a perspective the individual tasks did not apply: follow HTTP bytes through page completion, database rows, ship flag/version, region counters, transaction commit and freshness record. Run further rounds only while material findings continue. Stop on a clean independent round. Include a cross-provider review for the data-integrity surface.

- [ ] **Commit and publish.** Explicitly stage the three Task 2 files with `refactor(api): preserve real esi response coverage`. Record the work SHA in a separate plan-status commit. Push the branch. Open one PR to `dev` carrying both tasks, verification and `Review — data-integrity paths`. Wait for green CI. Investigate routine failures within the project's three-attempt limit. Provide Sam the reviewable PR. The coordinator alone performs root operations. Following Sam's eventual merge, record the verified merge SHA and both shipped phase banners in a follow-up documentation commit.
