<!-- ABOUTME: Cross-validates saved-search mutation feedback and criteria-summary correctness against source, design, and tests. -->
<!-- ABOUTME: Records independent verdicts, reachable scenarios, evidence limits, and minimal remedies for the September 5 contract-search audit. -->

# Saved-search UI cross-validation

Status: DONE. Scope: the saved-search UI at audit source revision `d43da7c`, in the `bug-hunt-contract-search-2026-09-05` worktree. No application source edits, git mutations, server launches, database operations, dependency acquisition, or security testing were performed. This report is the only file written by this verifier.

| Finding | Verdict | Severity | Product decision required |
| --- | --- | --- | --- |
| Failed rename/delete operations provide no feedback | Confirmed correctness bug | P2: normal management failures are invisible | No |
| Criteria summary omits contract type and explicit exclusion of blueprint copies | Confirmed presentation correctness bug | P3: misleading/incomplete description; Apply remains correct | No |

## Failed rename/delete operations provide no feedback

The independently discovered mutation-feedback candidates describe one shared omission in `app/frontend/web/src/features/saved-searches/components/SavedSearchesPage.tsx:106`: the row obtains both mutation results, but only consumes their pending state and rename's success callback. Its complete render does not read either mutation's error state. The list-level `isError` at line 73 belongs to the list query and cannot represent a rejected rename or deletion. The empty live region at line 77 is never populated with an outcome.

### Expected behavior and reachability

- `design/features/F005-Saved-Searches.md:170` (required error handling) requires user-friendly API error messages; line 172 requires clear duplicate-name feedback. The rename endpoint's contract in section 6.2 explicitly includes 409. Section 12, line 193, requires feedback to reach screen readers.
- `docs/superpowers/specs/2026-07-17-m3-account-features-design.md:215` specifies inline rename and two-step delete. Its accessibility requirement at line 220 includes live save/delete feedback. The same design's deferral of toast/modal primitives does not defer messages: line 214 explicitly uses an inline conflict message for creation.
- A signed-in user with searches named A and B can rename B to A through the existing controls. `app/backend/src/fastapi_app/services/saved_search_service.py:72` implements rename inside a savepoint and maps the unique-name rejection to 409. `app/backend/src/fastapi_app/tests/api/test_saved_searches.py`, test `test_rename_to_existing_name_409`, asserts this response and that both names remain intact.
- A delete can fail through an ordinary network/server failure or a stale row already deleted in another tab. `_get_owned` at service line 24 returns 404 for a missing row; deletion at line 90 calls it. The row remains displayed because only successful mutation invalidates the list.
- The rename field also accepts more than the backend's 100-character maximum (`schemas/account.py:60`), yielding another ordinary validation-failure path. This is supporting reachability, not a separately inflated finding.

### Mechanism and observable consequence

`app/frontend/web/src/features/saved-searches/hooks/useSavedSearches.ts:39` and line 54 send PUT and DELETE, respectively. Each non-success HTTP response calls `raiseApiError`; invalidation is success-only. `app/frontend/web/src/lib/api/client.ts:50` throws an `ApiError`; it is not a UI notifier. `app/frontend/web/src/main.tsx:13` configures query defaults without a global mutation-error renderer. Network exceptions likewise enter the mutation's error state.

After rejected rename, the form remains open with the attempted name and the Save button enabled again, but no explanation of the conflict or failure. After rejected deletion, the row remains and the confirmation eventually disarms without explanation. A 401 can invalidate identity and cause the account UI to become a sign-in prompt; that special recovery does not resolve silent 409, 404, 422, 5xx, or network failures.

The parent separately reported a real component/fetch-seam duplicate-name reproduction with mutation error state and no alert. This verifier did not repeat that execution and does not present it as an independently executed test. Independent evidence here is the complete source trace, backend contract, intended UI behavior, and coverage inspection.

### Test gaps and minimal remedy

`SavedSearchesPage.test.tsx:66` tests list-load failure; lines 88 and 108 test successful rename/delete dispatch. Neither exercises row-level failure feedback. Hook tests for failed rename/delete assert mutation error state and absence of list invalidation, which is necessary but does not assert what the user sees. The existing axe tests cover an authenticated list and an anonymous prompt, not failed mutations. The Playwright saved-search spec covers navigation, creation payload, listing, and Apply, not rejected rename/delete.

Render an accessible row-scoped error from each existing mutation result. Distinguish rename conflict from a generic failure; retain the attempted name so the user can correct it. Clear obsolete feedback when starting/cancelling a fresh interaction and on successful recovery. `SaveSearchControl.tsx:63` and lines 93-103 supply an existing same-feature inline-error pattern; no UI architecture or new primitive is necessary.

Add component checks at the real fetch seam for rename 409 and rejected DELETE, assert visible/announced message and preserved row/input, then correct/retry successfully and assert recovery. Include network failure and validation failure where their message treatment differs. `docs/pitfalls/testing-pitfalls.md:44` requires error-message and side-effect assertions; TEST-5 at line 118 requires real hooks and fetch-seam interception; TEST-8 at line 124 requires synchronizing on skeleton removal before ambiguous status queries. TEST-7's query retry concern applies to the initial list setup, not an assumed retry policy for these mutations.

No product decision is needed to provide the already-required feedback. Selecting concise copy consistent with the creation form is routine implementation.

## Criteria summary omits contract type and explicit exclusion of blueprint copies

`SavedSearchesPage.tsx:18` defines `summarizeSearch`. It never inspects `contract_type`; line 22 checks `if (p.is_bpc)`, collapsing explicit `false` and absence. The row displays the resulting string at line 155.

### Independent executable evidence

The verifier read the actual function source, extracted the function declaration without changing its body, transpiled it in memory using the already-installed TypeScript package, and executed these inputs with Node. No price input was supplied, so the imported price formatter was never needed. No React component or network stub was involved in this pure-function probe.

| Input parameters | Actual summary |
| --- | --- |
| `{ships_only:false}` | `All contracts · sorted by date issued desc` |
| `{ships_only:false, contract_type:['courier']}` | `All contracts · sorted by date issued desc` |
| `{ships_only:false, contract_type:['auction']}` | `All contracts · sorted by date issued desc` |
| `{ships_only:false, is_bpc:false}` | `All contracts · sorted by date issued desc` |
| `{ships_only:false, is_bpc:true}` | `All contracts · BPC only · sorted by date issued desc` |

### Intended behavior, reachability, and limits

M3's frontend design at line 215 explicitly requires a human-readable criteria summary derived from the parameters. `PRODUCT.md` establishes fast selection and clarity as product goals. The existing function's own blueprint-window comment at lines 39-40 explains why meaningful criteria must distinguish saved searches before Apply, and `SavedSearchesPage.test.tsx:150` explicitly tests that purpose for taxonomy/blueprint ranges.

The summary is intentionally compact: region and taxonomy IDs are counted rather than resolved to names. Therefore this report does **not** claim that every distinct parameter blob must have a unique summary, nor that every parameter requires exhaustive serialization. The narrower defect is that the primary contract-type restriction and an active boolean exclusion receive no description at all even though their local values need no lookup. Courier-only and auction-only entries consequently give no indication of their segment, and exclusion of blueprint copies disappears while inclusion is named.

The Save search control persists both fields (`SaveSearchControl.tsx:20` and line 33); the server explicitly accepts them (`schemas/account.py:29` and line 39). Existing creation tests at `SaveSearchControl.test.tsx:60` prove the courier segment is a supported saved state. Apply re-parses these same parameters at `SavedSearchesPage.tsx:128`; `filters.ts:277` and line 286 retain type and explicit boolean state. The backend applies contract type at `services/contract_service.py:299` and tests `is_bpc is not None` at line 315, using the negated offered-copy predicate for false. These are meaningful restrictions, not unsupported or ignored fields.

The explicit false state is reachable through a shared/typed URL or saved parameters. The visible checkbox at `FilterRail.tsx:92` only sets true or undefined, so simply unchecking it is **not** a valid reproduction of false. A signed-in user can open `/contracts?ships_only=false&is_bpc=false`, save the supported state, and encounter this omission on the saved-search page. Contract-type selection is reachable through normal segment controls.

The original exploratory and holistic reports conservatively called summary completeness a design concern. The executable collision and existing summary requirement support a narrower P3 display bug: accurate descriptions of the selected segment and explicit boolean exclusion. No loss or corruption of stored criteria or Apply behavior was established, and no high severity is justified.

### Test gaps, minimal remedy, and tracking

The three current summary tests cover taxonomy/ranges, absence of blueprint ranges, and missing sort defaults. None supplies contract type or an explicit false blueprint flag. Add compact assertions for supported type selections, multiple selected types, false/true/absent blueprint state, and the distinction from an unrestricted search. Describe each selected contract type using existing domain vocabulary and add a phrase such as “Excludes blueprint copies” for explicit false. Avoid wording such as “Blueprint originals only”: the false predicate also includes ordinary non-blueprint contracts and item-less contracts.

This needs no product decision or data/API change. Exact compact wording is routine presentation work; requiring a new design approval would invent a gate. Searches of prior bug-hunt reports, relevant M3 review material, the F008 decision log, and the pitfalls did not establish a prior accepted decision to omit these two restrictions or an existing tracked fix. Both findings fall directly inside the delegated saved-search UI scope.

## Verification boundaries

The pure summary probe exited successfully and printed the tabled outputs. The application test suites and backend tests were inspected but not executed by this verifier. The only incorrect-path reads were corrected with source discovery; no external content was acquired. Findings are bounded to frontend observability and summary fidelity, with the parent responsible for any subsequent implementation, regression tests, and integration.
