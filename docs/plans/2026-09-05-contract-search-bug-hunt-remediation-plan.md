<!-- ABOUTME: Specifies the approved contract-search and saved-search correctness repairs. -->
<!-- ABOUTME: Tracks implementation, regression evidence, and review gates for the September 5 hunt. -->

# Contract search bug-hunt remediation plan

> **For agentic workers:** Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement the checked steps. Every delegated agent MUST use GPT-6 Astra; use high reasoning effort for independent reviews.

**Goal:** Preserve the requested contract view across history, readiness failures and saved-search replay, explain failed operations, and sort by the displayed headline.

**Architecture:** Keep URL state and fetch-time result metadata separate. Narrow saved creation through a request-only parameter subclass while preserving stored reads. Compute the existing displayed headline as a SQL sort key before pagination. Keep the public `ship_name` sort parameter.

**Tech Stack:** Python 3.14+, FastAPI, Pydantic, SQLAlchemy async/PostgreSQL; React 19, TanStack Query/Router, TypeScript, Vitest/Testing Library; unchanged PDM/npm dependency locks.

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

**Plan review:** ✅ COMPLETED 2026-09-05 — 6 rounds, terminating round independent (cold read, GPT-6 Astra/high); cross-provider review omitted under Sam's Astra-only constraint
**Overall:** 0/6 phases shipped; 0 deferred. Implementation has not started.

| Phase | Status | Ship SHA(s) | Notes |
| --- | --- | --- | --- |
| 1 — Restore trustworthy fixtures | ⬜ NOT STARTED | — | O1 |
| 2 — Keep results attached to their requests | ⬜ NOT STARTED | — | B1, B3 |
| 3 — Validate saved-search boundaries | ⬜ NOT STARTED | — | B2, B6; approved stored-text policy |
| 4 — Explain saved-row operations and criteria | ⬜ NOT STARTED | — | B4, B5 |
| 5 — Order displayed headlines | ⬜ NOT STARTED | — | Approved Name-sort semantics |
| 6 — Verify and integrate | ⬜ NOT STARTED | — | All findings |

### Deviations

- _None yet._

### Discoveries

- _None yet._

## Sources and approved scope

The [consolidated findings and test-gap analysis](../bug-hunts/2026-09-05-contract-search-consolidated.md) is the source specification. Sam explicitly approved both stored-text compatibility and displayed-headline sorting on September 5, 2026. Implement all six confirmed findings and the fixture repair O1, included under Sam's delegated choice of scope. No confirmed finding is deferred. The [boundary investigation](../bug-hunts/2026-09-05-contract-search-boundary-planning.md) and [headline SQL investigation](../bug-hunts/2026-09-05-contract-search-sort-planning.md) explain source mechanisms and selected approaches. Their proposed runtime checks remain to be executed.

Audited production base: `d43da7c9313de7ce19aa9de21242b07949da4364`. Reports landed in `74667ca` and `2d19d06`. Recheck source drift against freshly fetched `origin/dev` before implementation, following [repository git and merge authority](../git-strategy.md). Concurrent project work owns other branches and the root checkout. Coordinate before any merge or root-dev update. Keep the unrelated root `.codex/config.toml` untouched. Continue in this isolated worktree or a dedicated `.claude/worktrees/` worktree. Never commit on local `dev`.

Use one implementation branch/PR with the phase order below. Several phases touch `ContractsPage`, its tests, or saved-search UI, so do not dispatch simultaneous writers to those files. Record a completed task in branch notes. A phase remains IN PROGRESS until its commits are integrated. Later phases can start after their task dependencies pass while the preceding phase's branch is observably live. Mark SHIPPED only when its commits are reachable on `origin/dev`. Then record the merge and banner in a subsequent documentation commit. The eventual implementation PR is **Review — public API validation and contract ordering semantics**. Sam retains merge authority even though the design is approved.

## Global execution constraints

- Preserve existing search predicates, segment counts, pagination partitioning, title/primary-label output, saved-price ceiling `1e15`, finite-number checks, ownership/authentication, count-cap concurrency policy and the three-character omission policy. Only the explicitly described validation, feedback, readiness, history and ordering behavior changes.
- Do not truncate stored/input text, migrate/delete existing rows, add a criteria-editing API, loosen price limits, add dependencies, or hand-edit generated API/router files. New files require two ABOUTME header comments. Preserve comments unless their described behavior becomes false. Match surrounding formatting. Avoid repo-wide `pdm run format` (ENV-7).
- Read [implementation pitfalls](../pitfalls/implementation-pitfalls.md) and [testing pitfalls](../pitfalls/testing-pitfalls.md). For every production task, invoke `superpowers:test-driven-development`. Write intended-behavior tests. Run them and observe the relevant assertion failure. Implement minimally, then rerun green. Import/configuration failures are not TDD evidence. O1 is test-only and follows its own warning-reproduction check.
- Use actual application hooks/components/router and stub only HTTP at the existing fetch seam (TEST-5). Backend tests use real PostgreSQL. Add no E2E mocks. Keep unexpected output visible. Fix races with deterministic synchronization, never weaker assertions (TEST-2). Do not copy the archived audit probes into regression tests unchanged: they intentionally assert defects.
- Before each task is marked complete, review its tests against the testing pitfalls. Run the listed checks. Inspect stdout/stderr. Commit exact paths with a Conventional Commit before marking the task complete. Record red/green evidence and any deviation in this plan. For each completed phase, review the batch once from a perspective its individual tasks did not apply. Run further rounds only while material findings continue. Stop after a clean round.

### Runtime and database preflight

Run commands from the cwd named for each lane: `app/frontend/web` for npm and `app/backend` for Python/PDM. On this Windows host `npm.cmd` works and `python -m pdm` is the available PDM invocation. Frontend dependencies were installed from the unchanged lockfile. Backend SQLAlchemy/asyncpg/pytest were absent during planning. Discover existing configured runtimes before installation. Any necessary restoration must use trusted repository manifests/locks and [external-resource safety](../security/external-resource-safety.md). Do not invent package or registry coordinates.

The backend fixture in `src/fastapi_app/tests/conftest.py` **drops/recreates all tables** in `DATABASE_URL_TESTS`. Its full-suite migration fixture also connects to the same server's `postgres` database and forcibly drops/recreates the fixed-name `m4_equiv_check` database. Before any backend test or measurement, verify that its database targets are disposable and distinct from application/production data. Serialize all processes sharing the primary target. Before the full suite, verify disposal authority for `m4_equiv_check`. Also verify exclusive access to that PostgreSQL server's migration-test target. Different `DATABASE_URL_TESTS` names do not isolate concurrent full-suite runs. Use an isolated disposable PostgreSQL instance when exclusivity cannot otherwise be established. If the applicable targets cannot be verified, stop the backend lane. Record the unmet gate. Continue independent frontend work. Do not start the application ingestion lifespan as a way to run tests. Never print credential values. Never copy them into tracked files. Follow ENV-8 and TEST-10/TEST-23.

## Phase 1 — Restore trustworthy fixtures

**Execution Status:** ⬜ NOT STARTED

### Task 1.1 — Give authenticated component tests real response shapes

**Source:** O1 — unread-count warnings in six passing tests. **Depends on:** none. **Produces:** a clean account-adjacent frontend test baseline.

**Modify:** `app/frontend/web/src/features/watchlists/components/WatchButton.test.tsx`, `app/frontend/web/src/features/contracts/components/pages.test.tsx`. **Read:** `src/features/notifications/hooks/useNotifications.ts` (exports `useUnreadCount`), `src/test/http.ts`, and the notification responder in `SavedSearchesPage.test.tsx` (all frontend-relative).

- [ ] Read testing pitfalls §1/§7 and TEST-5/TEST-8. Run `npm.cmd test -- src/features/watchlists/components/WatchButton.test.tsx src/features/contracts/components/pages.test.tsx --reporter=dot`. Reproduce the six `Query data cannot be undefined` warnings before editing.
- [ ] In the three authenticated watch-button tests and three detail watch-button gate tests, route notification requests before their broad contract response. Use the actual notification envelope, preserving the endpoint/method assertions and all existing behavioral assertions:

```ts
if (new URL(url).pathname === '/api/v1/me/notifications/') {
  return jsonResponse({ total: 0, page: 1, size: 1, items: [] })
}
```

- [ ] Keep unexpected endpoints visible. Do not install a global console suppression or change production notification logic. Rerun both files. Require no unexpected stderr. Review against testing pitfalls before completion.
- [ ] Commit: `test(web): preserve watch-button assertions with valid notification fixtures`.

## Phase 2 — Keep results attached to their requests

**Execution Status:** ⬜ NOT STARTED

### Task 2.1 — Protect page correction and readiness transitions

**Source:** B1 and B3. **Depends on:** Task 1.1. **Produces:** shared `isItemSurfaceReady` predicate and response-owned page correction. No API changes.

**Modify:** `app/frontend/web/src/features/contracts/hooks/useTaxonomy.ts`, `hooks/useContracts.ts`, `components/ContractsPage.tsx`, `hooks/hooks.test.tsx`, `components/pages.test.tsx` (the last four paths share the contracts feature prefix).

- [ ] Invoke TDD. Read both pitfalls, especially WEB-1, TEST-2/5/7/8/25/29/30. Write intended-behavior tests in the existing real router/hook harness. Use the [runtime observation source](../bug-hunts/2026-09-05-contract-search-runtime-observations.tsx.txt) as fixture evidence, with expected outcomes corrected.
- [ ] Back regression: serve Tristan with total 200 and Rifter with total 10, reflecting requested page in each row label. Start `/contracts?search=Tristan&page=3`. Click Next, enter Rifter, and await its page 1. Then go Back. Assert final full URL search and visible `Tristan page 3`, never page 1. Separately hold placeholder responses between different populations and assert no clamp before matching data. Seed an out-of-range cached result for `Rifter`. Then navigate to the same page with raw ` Rifter `. After debounce, the shared cached response must still permit valid correction. Cover two different sub-three-character terms that both serialize to absent search. Preserve existing genuine invalid-page and zero-total behavior.

```ts
act(() => router.history.back())
await screen.findByText('Tristan page 3')
expect(router.state.location.search).toMatchObject({ search: 'Tristan', page: 3 })
```

- [ ] Readiness regression: complete taxonomy -> begin ordinary held refetch -> failure with retained complete data -> changed `min_me` -> replacement rows -> successful complete recovery. During the ordinary refetch, the live gate remains open. After error, the controls close. Later rows capture false readiness. Held rows retain their own fetch-time warning state until replaced. Assert cache status, returned metadata, actual warning and control behavior, not call count alone. Keep cold failure/timeout and partial/complete tests.
- [ ] Run `npm.cmd test -- src/features/contracts/hooks/hooks.test.tsx src/features/contracts/components/pages.test.tsx --reporter=dot` and capture failures in intended assertions.
- [ ] Share readiness in `useTaxonomy.ts`. Both `useItemSurfaceReady` and `useContracts` consume it:

```ts
export function isItemSurfaceReady(
  taxonomy: Pick<ReturnType<typeof useTaxonomy>, 'isSuccess' | 'data'>,
): boolean {
  return taxonomy.isSuccess && taxonomy.data?.coverage === 'complete'
}
```

- [ ] Keep readiness in the query key and fetch-time metadata. Keep cold readiness gating. In `ContractsPage`, compare canonical API-query identity using `hashKey` from `@tanstack/react-query` and existing `toApiQuery`. Raw text can differ while sharing the same cached request. Keep `sameSearch` unchanged for debounce state equality. Exclude placeholder responses and recheck canonical identity inside the updater:

```ts
const sameRequest = (a: ContractSearch, b: ContractSearch) =>
  hashKey([toApiQuery(a)]) === hashKey([toApiQuery(b)])
const pageOutOfRange = data !== undefined && !isPlaceholderData && sameRequest(data.countsSearch, search)
  && data.total > 0 && search.page > pageCount
// Inside the guarded effect, with data included in the dependency list:
navigate({
  search: (prev) => sameRequest(data.countsSearch, prev)
    ? { ...prev, page: pageCount }
    : prev,
  replace: true,
})
```

- [ ] Define the pure `sameRequest` helper outside the component. Read `isPlaceholderData` from the existing query result. Narrow `data` explicitly before the callback for TypeScript. Preserve response size fallback and the transient correction loading branch. An `isPlaceholderData` check alone does not cover the settled query held during debounce. Canonical identity alone does not exclude held data during a readiness-key transition.
- [ ] Rerun targeted tests and `npm.cmd run lint`. Use deferred responses/fake-timer advancement with settled React work if a test races. Never remove/relax the URL, metadata or warning assertion. Review pitfalls before completion. Commit `fix(web): preserve requested pages and readiness after refresh errors`.

## Phase 3 — Validate saved-search boundaries

**Execution Status:** ⬜ NOT STARTED

### Task 3.1 — Bound creation while preserving stored reads

**Source:** B2 and approved stored-text compatibility. **Depends on:** database preflight; Task 2.1 before this phase is integrated. **Produces:** `SavedSearchCreateParameters` in OpenAPI. Stored `SavedSearchParameters` remains permissive.

**Modify:** `app/backend/src/fastapi_app/schemas/account.py`, `tests/api/test_account_schemas.py`, `tests/api/test_saved_searches.py`, `tests/api/test_contracts.py` (tests are under `app/backend/src/fastapi_app/`). **Regenerate:** `app/frontend/web/openapi.json`, `app/frontend/web/src/lib/api/schema.d.ts`.

- [ ] Invoke TDD. Read FASTAPI-3, TEST-1/10/18/23/27 and boundary/error-output guidance. Add schema and HTTP tests for 100 accepted/101 rejected search code points, two/three astral-character minimum, 100/101 astral-character maximum, absent text, extra-key rejection and existing `1e15` price limits. Pin raw backend validation without server trimming. Add browse Unicode HTTP checks alongside existing ASCII tests.
- [ ] Through real POST, assert the nested `search_parameters.search` 422 location for rejected input. Assert that rejected input causes no saved-row write. Directly seed one 101-character saved ORM row and an ordinary sibling to represent already-stored data. GET returns both. Rename returns unchanged long parameters. Delete succeeds. Do not use the narrowed create model to arrange that preservation fixture.
- [ ] Test `app.openapi()` creation and response schema references: the request nested string has `maxLength: 100`, response nested string has no maximum, and both forbid extras. Inspect the string member of `anyOf`.
- [ ] Run `python -m pdm run pytest src/fastapi_app/tests/api/test_account_schemas.py src/fastapi_app/tests/api/test_saved_searches.py src/fastapi_app/tests/api/test_contracts.py -q`. Record actual validation/HTTP failures. Then implement only:

```python
class SavedSearchCreateParameters(SavedSearchParameters):
    search: Optional[str] = Field(default=None, min_length=3, max_length=100)


# Within SavedSearchCreate, retaining every other existing field/validator:
search_parameters: SavedSearchCreateParameters
```

- [ ] Keep GET/POST/PUT response models on `SavedSearchParameters`. No database migration or service rewrite is needed. Rerun the targeted backend tests and regenerate using `python -m pdm run export-openapi` from backend, then `npm.cmd run generate:api` from frontend. Inspect the generated diff for creation/read separation. Never patch generated files manually.
- [ ] Review tests against pitfalls. Commit `fix(api): bound saved creation and preserve stored search reads`.

### Task 3.2 — Explain invalid text and save restrictions before dispatch

**Source:** B2 and B6. **Depends on:** Tasks 2.1 and 3.1. **Consumes:** request schema `SavedSearchCreateParameters`, canonical API-query comparison and readiness metadata. **Produces:** `searchText(value)` and actionable saved-create feedback. `useContracts` retains its query fields. It adds `searchError: string | undefined` for live input and `isSearchBlocked: boolean` for either live/effective invalid text.

**Modify:** frontend `src/features/contracts/filters.ts`, `filters.test.ts`, `hooks/useContracts.ts`, `hooks/hooks.test.tsx`, `components/FilterRail.tsx`, `components/filter-controls.test.tsx`, `components/ContractsPage.tsx`, `components/pages.test.tsx`; `src/features/saved-searches/components/SaveSearchControl.tsx`, its `.test.tsx`, `components/SavedSearchesPage.test.tsx`, `hooks/useSavedSearches.ts`, its `.test.tsx`. **Read:** API `extractDetail`/`raiseApiError` and Input prop forwarding. Do not change the global API error contract.

- [ ] Invoke TDD. Read WEB-1, FASTAPI-3, TEST-1/2/5/25/30 and Unicode/boundary/error-path guidance. Add pure tests for raw URL preservation, trimming, absent/blank/two/three code points, 100/101 ASCII and astral code points, combining characters and padded 100-character text. Count code points, not UTF-16 units/graphemes. Preserve existing ECMAScript trim. Do not normalize Unicode or impose an HTML `maxLength`.
- [ ] Add real router tests: cold overlong URL; warm valid rows -> overlong paste -> correction; correction while the debounced effective text is still invalid; non-text changes and manual hook refetch while invalid; Apply of a stored overlong row with other criteria preserved. Explicitly finish debounce/readiness work before asserting absence of a list request. On invalid state, assert no list request and no stale rows/counts/pagination/status. Assert no generic Retry or permanent skeleton. Assert a visible correction message even when mobile filters are collapsed. Correction restores normal rows and payload.
- [ ] Add save tests for each price bound at `1e15` and `1000000000000001`, invalid text, disabled Save plus direct form submission, retained name and recovery. Browsing above the saved ceiling remains allowed. Add hook/form tests for count-limit 400 with detail, duplicate 409, 422 validation arrays for both a 101-character saved-search name and unsupported criteria, malformed error body, 500, network failure, 401 auth invalidation and success-only saved-list invalidation. Unknown 422 guidance must cover the name and criteria without falsely diagnosing a price limit. Retain the name so it can be corrected.
- [ ] Run `npm.cmd test -- src/features/contracts/filters.test.ts src/features/contracts/hooks/hooks.test.tsx src/features/contracts/components/filter-controls.test.tsx src/features/contracts/components/pages.test.tsx src/features/saved-searches --reporter=dot`. Capture the relevant failing assertions before implementing.
- [ ] Export this helper from `filters.ts` beside the bounds. Both serializers consume its `text`. Overlong text remains identifiable and is never silently omitted. Keep the serializer safe during render:

```ts
export const MAX_SEARCH_LENGTH = 100
export function searchText(value: string | undefined): {
  text: string | undefined; error: string | undefined
} {
  const text = value?.trim()
  const length = text === undefined ? 0 : Array.from(text).length
  return {
    text: length < MIN_SEARCH_LENGTH ? undefined : text,
    error: length > MAX_SEARCH_LENGTH ? 'Search must be 100 characters or fewer.' : undefined,
  }
}
```

- [ ] In `useContracts`, validate live and effective text. Require both to be valid in `enabled`. Repeat the validation guard immediately before `api.GET` in `queryFn` because manual `refetch` bypasses `enabled`. Return the query fields plus `searchError` from live validation and `isSearchBlocked` from either validation. Preserve Task 2.1's captured metadata and query key. Throw a normal validation Error before transport if manually invoked while invalid. UI validation has priority over the query error.
- [ ] `ContractsPage` renders `searchError` first. Next, it renders a loading state when `isSearchBlocked` remains true after correction. Ordinary query pending/error/data branches follow. Throughout `isSearchBlocked`, hide stale response-derived rows, counts, segments, stamps, warnings and live-region text. Disable page correction throughout `isSearchBlocked`. Associate the input using `aria-invalid`/`aria-describedby`. Provide a results-area message outside the collapsed FilterRail and a way to reveal the field. Keep raw text and other criteria in the URL. Existing Saved Searches Apply navigation requires no persistence rewrite.
- [ ] `SaveSearchControl` uses `SavedSearchCreate['search_parameters']` for the outgoing serializer type and `searchText` for text. Compute local save error from invalid text or either non-finite/negative/above-`1e15` price. Render which bound needs correction. Disable submit. Repeat the guard in `submit` before serialization/mutation. Preserve the entered name while criteria are corrected. Reset stale server feedback on a fresh attempt or cancellation.
- [ ] In the create hook, destructure parsed `error`. Pass `extractDetail(error)` into existing `raiseApiError`. Keep shared `extractDetail` intentionally string-only. In the form, map server 400 count detail to “Remove a saved search before saving another”. Preserve 409 conflict wording. Map 422 to “The search name or criteria are invalid. Use a name of 100 characters or fewer, review the criteria, and save again”. Other failures keep retry guidance. Do not dump validation arrays or user input. Local validation supplies specific text/min/max-price guidance. The fallback also covers server rejection of an overlong saved-search name.
- [ ] Rerun targeted tests, `npm.cmd run lint`, and `npm.cmd run build`. Inspect generated code for only intended output. Use deterministic timer/response fences rather than weaker assertions. Review pitfalls. Commit `fix(web): validate search boundaries and explain save restrictions`.

## Phase 4 — Explain saved-row operations and criteria

**Execution Status:** ⬜ NOT STARTED

### Task 4.1 — Render row failures and active summary restrictions

**Source:** B4 and B5. **Depends on:** Task 3.2 (shared saved-page tests). **Produces:** accessible row recovery without API changes.

**Modify:** `app/frontend/web/src/features/saved-searches/components/SavedSearchesPage.tsx`, `SavedSearchesPage.test.tsx`, `SavedSearchesPage.a11y.test.tsx` in the same directory. **Read:** `useSavedSearches.ts` error/invalidation behavior and existing `ApiError`.

- [ ] Invoke TDD. Read TEST-2/5/7/8 and error/negative-property guidance. Real-row tests must cover rename 409, generic/network rename error, failed deletion, preserved row/input, error isolation between two rows, cancellation, fresh attempt and successful recovery. Preserve delete confirmation/blur/five-second disarm and pending protection. Include failure after disarm so the error remains visible outside the confirmation-only button branch. Auth expiration continues through existing hooks.
- [ ] Pure summary tests cover each of the five contract types, multiple types, explicit `is_bpc:true`, false and absence. Expected examples include `Types: courier, auction` and `Excludes blueprint copies`. A false value must not imply originals only. Preserve ranges, taxonomy/region compactness and default sorting for partial stored blobs.
- [ ] Run `npm.cmd test -- src/features/saved-searches/components/SavedSearchesPage.test.tsx src/features/saved-searches/components/SavedSearchesPage.a11y.test.tsx --reporter=dot` and observe relevant failing assertions.
- [ ] Render row-scoped `role="alert"` errors with actionable rename conflict/delete retry text. Read the actual mutation error. Keep the entered name. Retain the failed-delete row. Permit retry. Clear relevant mutation error with `reset()` on fresh interaction/attempt, cancel or success. Keep error output outside markup hidden by rename/delete mode. Do not confuse list query failure with mutation failure.
- [ ] Add the local summary fragments without changing saved data or Apply:

```ts
if (p.contract_type?.length) {
  parts.push(`Types: ${p.contract_type.map(type => type.replaceAll('_', ' ')).join(', ')}`)
}
if (p.is_bpc === true) parts.push('BPC only')
else if (p.is_bpc === false) parts.push('Excludes blueprint copies')
```

- [ ] Rerun targeted tests and accessibility cases. Inspect errors and retained state. Review pitfalls, then commit `fix(web): explain saved-row failures and active restrictions`.

## Phase 5 — Order displayed headlines

**Execution Status:** ⬜ NOT STARTED

### Task 5.1 — Use the displayed label before pagination

**Source:** approved Name-sort decision in the consolidated report. **Depends on:** database preflight and earlier phases before integration. **Produces:** one non-null contract-level SQL key for both sort directions. Public sort spelling and displayed labels stay unchanged.

**Modify:** `app/backend/src/fastapi_app/services/contract_service.py`, `tests/services/test_contract_service.py`, `tests/api/test_contract_filters.py` (tests under the same `fastapi_app` directory). **Temporary measurement file:** `app/backend/src/fastapi_app/tests/services/test_contract_sort_performance.py`, created only for the measurement step and archived outside the regression suite afterward. **Archive:** `docs/bug-hunts/2026-09-05-contract-search-sort-performance.md` and exact diagnostic source beside it, created by this task.

- [ ] Invoke TDD. Read SQLA-1/3, WEB-1, TEST-1/2/3/4/12/18/23/25/27 and the complete [headline SQL design and fixture expectations](../bug-hunts/2026-09-05-contract-search-sort-planning.md). Its SQLAlchemy expression is the selected implementation, with runtime PostgreSQL validation required.
- [ ] Add `test_primary_label_sort_key_matches_displayed_headline` with literal labels and real DB key results compared to unchanged `_primary_label`. Cover named offered ship priority, record-order versus lexical-order conflict, requested distractors, missing/empty/whitespace names, category string versus ID disagreement, title fallback, every courier destination branch, loan/unknown and large valid IDs. Batch all 29 Python whitespace characters and non-whitespace U+200B/U+FEFF in `test_primary_label_sort_key_matches_python_title_whitespace`. Assert bound btrim output matches literal labels/Python stripping without normalizing item/destination names.
- [ ] Add API `test_name_sort_uses_displayed_headlines`, `test_name_sort_paginates_equal_headlines_in_both_directions`, `test_name_sort_orders_fallbacks_with_named_items`, and `test_name_sort_preserves_database_collation`. Exercise Name alone and search/type-triggered joined pagination, requested/module matching rows that differ from offered headlines, both directions, ID-ascending equal-key ties, at least two pages, full ID partition, totals and segment counts. Use literal ASCII expectations. For locale-sensitive labels, compare with PostgreSQL ordering an independently declared literal reference relation, not Python sorting or the production key.
- [ ] Update the two deliberate conflicting test groups specified in the planning evidence. Replace `test_ship_name_sorts_both_ways_and_leaves_item_less_contracts_last` with headline expectations while retaining volume checks. Remove `ship_name` from `ITEM_BEARING_JOINED_SORTS`' nullable matrix. Add a separate headline ordering test on that same corpus. Preserve nullable-sort exhaustiveness and all other sort cases. Name the replacement tests with `name_sort` for focused selection.
- [ ] Establish TDD red through the API expectations first: `python -m pdm run pytest src/fastapi_app/tests/api/test_contract_filters.py -k name_sort -q`. Those tests use existing interfaces and must fail on returned ordering, not an import of the proposed helper. Then add the helper/parity tests as the implementation proceeds. Run the service/filter files with `-k "primary_label_sort_key or name_sort"` for green. Establish the baseline performance measurements described in the measurement step before the production change.
- [ ] Implement `_primary_label_sort_key` exactly from the selected SQL design. Explicitly alias offered named items. Order by category `ship` priority then record ID. Correlate only to Contract. Coalesce to Python-equivalent trimmed title, courier text, contract ID fallback. Bind the explicit 29-character whitespace set. Test it independently. Map `ship_name` to this expression. Remove it from nullable sorts and join triggers. Preserve filter-induced joins. In grouped-ID pagination order the contract-level key directly rather than wrapping it in per-joined-item min/max. Keep min/max for every other joined sort. Keep ascending ID ties unchanged. Keep page-only entity loading.
- [ ] Verify grouped SQL by execution on PostgreSQL, including correlated subquery functional dependency. Compilation alone is insufficient. Keep display helpers unchanged. Preserve database collation. Add no migration/index/schema change based on speculation.
- [ ] Run the bounded baseline/candidate diagnostic from the planning evidence: disposable corpora of 1,000 and 10,000 contracts with 1/8/32-item fanout, both directions/pages/filter paths, five post-warmup samples, unchanged date sort control. Capture real page/count queries with their bind parameters, `EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON)`, and service times with a session-local timeout. Do not perform test DDL on a live snapshot. Investigate full item-table scans per parent, headline subplans multiplied by joined fanout, material slowdowns or timeouts before proceeding. Archive exact measured results and diagnostic source. Report synthetic evidence's limits rather than inventing a performance pass threshold. Broader indexes or architecture require Sam's decision if measurements demand them.
- [ ] Rerun the three service/filter/contract API files. Inspect clean output and preservation checks. Review pitfalls, then commit `fix(api): order contracts by their displayed headlines`. Commit the measurement evidence separately if needed. Do not leave temporary measurement tests in normal discovery.

## Phase 6 — Verify and integrate

**Execution Status:** ⬜ NOT STARTED

### Task 6.1 — Prove the composed flow and prepare the Review PR

**Source:** B1–B6, O1 and approved Name ordering. **Depends on:** Tasks 1.1–5.1. **Files:** this plan, consolidated report and an execution evidence note `docs/bug-hunts/2026-09-05-contract-search-remediation-verification.md` (created here); source edits only if a verified in-scope failure requires correction through TDD.

- [ ] Read both pitfalls. Invoke `superpowers:verification-before-completion`. Confirm each finding has intended-behavior red/green evidence. For any timing-dependent assertion that flakes, use deterministic synchronization. Stop and raise if that cannot make the original assertion reliable.
- [ ] From frontend run `npm.cmd test -- --reporter=dot`, `npm.cmd run test:future-clock`, `npm.cmd run lint`, and `npm.cmd run build`. Require no unexpected stderr or assertion weakening. After the full-suite database preflight covers both `DATABASE_URL_TESTS` and exclusive disposable `m4_equiv_check`, run backend `python -m pdm run lint`, `python -m pdm run pytest`, and the schema export. Run frontend API generation again. Verify no unexplained generated diff. Compare skips and warnings with recorded expectations. Missing database checks remain a failed completion gate.
- [ ] Trace the real UI/API path for search correction, Back, saved creation/Apply/rename/delete and ascending/descending Name sorting on an already-authorized disposable environment. Use real APIs/data for any E2E verification. Add no new network-intercept E2E fixtures. Preserve backend HTTP and real-router tests as automated evidence. Record exactly what ran and any unavailable manual/E2E surface. Do not describe source inspection as browser execution.
- [ ] Review the combined diff once for URL/request ownership, stored response permissiveness, notification fixture shapes and unchanged count/filter domains. Run further review only while material findings remain. Ensure no temporary probes, credential files, dependency changes or unrelated work entered the diff.
- [ ] Update this plan and consolidated report with verification and unresolved concerns. Commit exact paths. Create a PR to `dev` with `## Merge classification` set to `Review — public API validation and contract ordering semantics`. Include concrete behavior and test evidence. Coordinate concurrent project work before merge/root operations. Wait for CI through a dedicated monitoring tool. Sam merges this Review PR. Do not use `--auto` as a gate, squash, or rebase-merge.
- [ ] After an authorized merge, verify actual reachable commits. Update phase banners/status and merge references in their own documentation commit. Report DONE only for executed and verified work. Report environmental or performance gaps explicitly if they remain.

## Execution recommendation

Use fresh GPT-6 Astra agents sequentially under subagent-driven development, with review after each task. The plan is self-contained for a fresh implementation context, but shared frontend files and the read/write schema dependency make concurrent writers wasteful. A separate task using executing-plans is suitable if Sam wants independent scheduling. Parallel agents are useful only for read-only review or a carefully isolated SQL investigation. The present bug-hunt cycle produces this reviewed plan. Implementation status remains NOT STARTED until execution begins.
