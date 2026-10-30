<!-- ABOUTME: Records the saved-search write/read and frontend validation boundary investigation. -->
<!-- ABOUTME: Defines implementation and test requirements that preserve stored text and saved-price policy. -->

# Contract-search boundary planning evidence

Date: 2026-09-05. Status: DONE_WITH_CONCERNS; planning investigation only. Sam approved keeping existing overlong saved text readable, rejecting overlong creation, and presenting local validation on Apply without truncation. The saved-price ceiling remains 1,000,000,000,000,000 ISK. This report supports the overlong-text and actionable-save-feedback findings in the [consolidated contract-search report](2026-09-05-contract-search-consolidated.md); its earlier pending-decision labels predate the parent task's approval. No production edits, external installations, database writes, or backend runtime tests occurred in this investigation.

## Investigation checklist

- [x] Inspect request models, response models, service writes, and persistence representation.
- [x] Trace raw URL/input through debounce, API serialization, save creation, and Apply.
- [x] Identify validation ownership, Unicode semantics, error handling, and cross-fix interactions.
- [x] Specify failing tests, regeneration, checks, and unresolved execution requirements.

## Backend: separate creation parameters from stored parameters

The exact shared boundary is `app/backend/src/fastapi_app/schemas/account.py`: `SavedSearchParameters.search` at line 25 has `min_length=3` and no maximum; `SavedSearchCreate.search_parameters` at line 55 and `SavedSearchSchema.search_parameters` at line 69 both refer to it. `SavedSearchUpdate` only contains `name`. `api/saved_searches.py` uses `SavedSearchSchema` for GET list, POST response, and PUT response. In `services/saved_search_service.py`, creation calls `payload.search_parameters.model_dump()` and stores that dictionary in the `SavedSearch.search_parameters` JSON column; list returns owned ORM rows, rename changes only `row.name`, and delete does not validate parameters.

The smallest explicit schema separation is:

```python
class SavedSearchCreateParameters(SavedSearchParameters):
    search: Optional[str] = Field(default=None, min_length=3, max_length=100)
```

Declare that class after `SavedSearchParameters` and before `SavedSearchCreate`; change only `SavedSearchCreate.search_parameters` to the creation model. Keep the existing `SavedSearchParameters` class as the stored/response type. The inherited fields retain the same defaults, `extra="forbid"`, price ceiling, finite-number constraints, taxonomy fields, and sort policy. POST continues returning the read model; accepting narrower requests than responses is deliberate. No service, router signature, database schema, data migration, rename contract, or delete behavior needs changing.

`schemas/contracts.py:351-358` already provides the browse minimum and maximum. Do not broaden that endpoint or replace its existing raw-string validation. A parent-model validator attached only to `SavedSearchCreate` could reject overlong text with fewer lines, but it would hide the nested field maximum from generated OpenAPI. The small subclass makes the difference explicit to API clients and gives a natural field location in 422 validation errors. Copying all parameter fields into two unrelated models would create avoidable drift. Narrowing `SavedSearchParameters` itself breaks the approved preservation policy.

Retain both model names in generated output. A schema regression test should resolve `SavedSearchCreate.search_parameters` to the creation schema and `SavedSearchSchema.search_parameters` to the stored schema, check maximum 100 only on the creation search field, and check that both reject extra properties. Optional string fields use `anyOf`; inspect the string member instead of assuming `maxLength` is on the outer property.

## Text semantics and shared frontend ownership

`features/contracts/filters.ts` owns route parsing and `toApiQuery`. The parser at line 273 intentionally preserves a nonempty raw string, including surrounding spaces. Existing tests explicitly require that preservation. The serializer at line 327 trims and omits terms shorter than three characters. `SaveSearchControl.tsx` independently repeats that trim/minimum logic at lines 15 and 38. `SavedSearchesPage.tsx:122-129` applies a saved blob through `parseContractSearch` and navigates to `/contracts`; `routes/contracts.index.tsx` uses the same parser as `validateSearch`.

Keep raw text in input and route state exactly as supplied. Do not truncate, drop an overlong term, normalize Unicode, or add HTML `maxLength=100`. Introduce a small shared text helper in `filters.ts`, used by both serializers and validation consumers, which computes the existing JavaScript `trim()` result and counts Unicode code points with `Array.from(trimmed).length` (or equivalent string iteration). Export the 100-character limit beside `MIN_SEARCH_LENGTH`. Code-point counting must also replace the minimum check so a pair of astral characters does not pass the JavaScript minimum while failing Python validation.

The helper should distinguish these states without silently converting an invalid long term into an absent filter:

| Effective text after existing trim | Serialized text | Query/save behavior |
| --- | --- | --- |
| Absent, blank, or fewer than three code points | Omitted | Preserve the existing mid-typing behavior and permit other criteria |
| Three through 100 code points | Full trimmed text | Permit browsing and saving, subject to save-specific price constraints |
| More than 100 code points | Retain the entire text as invalid state | Show correction guidance and prevent dispatch; never send a widened request without the term |

A compact implementation can return `{ text, error }`, retaining full overlong `text` and supplying a validation message. Both serializers can use `text`; dispatch owners must check `error`. That keeps serialization mechanical and avoids throwing during render, since `useContracts` constructs its query key on every render. A discriminated valid/invalid result is also sound, but all callers must handle it explicitly; do not bolt an exception onto the current render-time serializer without redesigning those call sites.

The backend currently does not trim search terms. Keep that behavior: server request constraints measure the actual raw JSON/query string; the frontend trims before sending, as it already does. A direct saved-create body with 101 characters including padding is rejected; a frontend input with 100 characters plus padding sends the trimmed 100-character payload. Existing saved raw text containing padding remains visible; if its trimmed effective term is within range, it remains queryable. No Python `.strip()` change or attempt to equate Python and ECMAScript whitespace sets is needed.

Unicode semantics are code points, not grapheme clusters or UTF-16 code units. Combining marks each count; do not add NFC normalization or `Intl.Segmenter`. A local Node probe confirmed: two rocket emoji have four UTF-16 units but two code points; 100 rocket emoji have 200 units but 100 code points; padded 100-character ASCII has 104 raw units but 100 trimmed code points; `e` plus a combining acute accent has two code points. Backend Unicode HTTP tests are still required; the probe is not a Pydantic runtime result.

## Prevent requests and misleading cached presentation

`useContracts.ts:57-73` debounces only search text and freezes the whole effective search at the last settled state. Its query key and fetch-time metadata use that effective search. Its existing `enabled` gate at line 128 only waits for taxonomy readiness. This means live input and effective request text can disagree in both directions during correction.

Use the shared validation result for both the live `search` and `effectiveSearch`. Enable list fetching only when readiness is known and both texts are valid. Invalid live text must close the gate immediately, before debounce settles; corrected live text must not reopen it while the effective text remains invalid. Keep readiness, query keys, and the existing debounce behavior otherwise intact.

Add a check before `api.GET` inside `queryFn` as well. The installed TanStack Query source at `node_modules/@tanstack/query-core/src/queryObserver.ts:297-346` sends `refetch()` through `fetch()` to the query's fetch operation without an `enabled` check; `enabled:false` is not an absolute request prohibition. The guard must reject locally before network dispatch if its captured effective search is invalid. If the implementation exposes a live-state refetch guard too, test it; avoid inventing successful empty query data to satisfy the query function. No URL, text, or cache mutation should be used to repair invalid input.

At `ContractsPage`, give local text validation priority over the pending/error/data branches. A cold disabled query remains pending, so retaining the current `isPending ? skeleton` branch first would display an endless loading state. A previously failed or completed query can retain its error/data after disabling; rendering generic service failure with Retry, cached matching counts, or stale pagination would misdescribe the invalid current input.

Recommended local state: keep heading, filter controls, and Save search disclosure reachable; render a visible results-area message such as "Search must be 100 characters or fewer. Shorten the search text to load contracts." Suppress result count, freshness stamp, segment counts, rows, pagination, coverage/empty-result explanations, and the matching-results live announcement while invalid. Keep the actual query cache untouched. A matching local explanation should take precedence over stale server errors. Clear filters and editing the text remain recovery actions.

The results-area message is necessary because FilterRail is hidden behind the Filters disclosure below the desktop breakpoint. Add `aria-invalid` and `aria-describedby` to the Search input; its description should identify the length restriction. Avoid announcing two separate alerts for one error: use the results-area alert/status for the announcement and descriptive input help for association. The current input remains controlled by raw URL text, so applying a saved overlong term requires no alternate Apply code path or storage mutation.

Guard response-driven page correction while local input is invalid. Coordinate with the pagination-ownership fix: it must additionally require matching captured search and recheck the navigation updater, because merely checking length does not fix stale page correction during ordinary valid-text debounce. Coordinate with the readiness fix in `useContracts`: text validity composes with readiness and must not replace its corrected success/coverage predicate. All existing fetch-time metadata continues to describe actual rows.

Requests already started under valid criteria may finish while the input becomes invalid. Retaining their valid cache entries is safe; the invalid presentation branch must not display them as current matches. This change does not require cancellation or a query-cache redesign.

## Save-specific validation and actionable errors

Keep the save-specific price ceiling out of `parseContractSearch` and `toApiQuery`; browsing still accepts finite nonnegative values above 1e15. In the save feature, use one small criteria-validation function that combines the shared text error with save price validation, preserving absent/null price semantics and identifying minimum price, maximum price, or both. The UI should say that saved searches require those prices to be at most 1,000,000,000,000,000 ISK, and ask the user to lower or clear the relevant bound before saving. No clamping or dropping a supplied bound is acceptable. Keep non-finite protection on the server; frontend malformed/non-finite values are already removed by the route parser, and a defensive save validator may reject them when called with a programmatically constructed state.

`SaveSearchControl` should derive current criteria validation on every render, show it in the open form, disable Save for invalid criteria, and repeat the guard in `submit` before `create.mutate`. A disabled button alone does not protect a form submit. Keep the disclosure available so users can discover the reason, preserve the entered name on failure, and clear validation automatically when criteria become valid. Opening, canceling, successful save, and a fresh submission should reset stale mutation feedback consistently. Use `SavedSearchCreate['search_parameters']` as the serializer return type after generation, instead of the read-response parameter alias; `SavedSearchesPage` and its summary keep the permissive read alias.

Creation hook handling should follow the working watchlist sibling: destructure `{ data, error, response }`, then call `raiseApiError(queryClient, response.status, extractDetail(error))` for failed responses. This preserves the existing 401 invalidation and success-only saved-list invalidation. `extractDetail` intentionally accepts only a string and discards a 422 validation array, so forwarding it alone fixes the count-cap explanation but does not describe field validation failures.

Use a save-specific error message mapper, with distinct outcomes:

| Condition | Recovery guidance |
| --- | --- |
| Local text validation | Shorten Search to 100 characters; no POST |
| Local saved-price validation | Lower or clear the named price bounds to the saved ceiling; no POST |
| 400 with saved-search limit detail | Remove a saved search before saving another; retain server detail/configured maximum when useful |
| 409 | A saved search already has that name; choose another name |
| 422 with known nested search or price validation | Explain the actual offending field and its applicable limit |
| Other/malformed 422 | Check the name and search criteria before trying again; do not falsely assert that price caused it |
| Network failure or 5xx | Generic retry guidance |
| 401 | Preserve existing session invalidation/sign-in transition |

If structured 422 detail is surfaced, implement a narrow helper in the saved-search feature that first preserves string detail, then safely inspects validation array entries for recognized `loc` paths such as `['body', 'search_parameters', 'min_price']` and known constraint types. Format application-owned field messages rather than printing arbitrary validation input. Feed the resulting string to the existing `ApiError.detail`; do not broaden the global error class solely for this fix. Recognize overlong `search`, saved-price upper bounds, and name validation separately, or fall back honestly for unrecognized validation. A generic 422 must never be labeled a price ceiling failure just because that is one known cause. Local prevention handles normal UI use; structured response handling covers server-side rejection and callers outside that form.

The server count limit and its best-effort concurrency semantics remain untouched. Do not prefetch all saved searches to predict capacity; the server is the authority. Showing a link to the existing Saved Searches page can make removal recovery convenient, but no criteria-editing API or alternate save workflow is needed.

## Failing tests to add before production changes

Backend tests belong in `tests/api/test_account_schemas.py` and `tests/api/test_saved_searches.py`; preserve `test_contracts.py:243-251`, which already pins the browse ASCII boundary.

1. Creation schema accepts exactly 100 ASCII/code-point characters and rejects 101. Include 100/101 astral characters and two/three astral characters to pin minimum and maximum. Keep `None`, omitted text, extras rejection, finite-price checks, and the existing saved ceiling assertions.
2. POST through the real FastAPI client returns 201/422 at 100/101; rejected requests leave the saved list unchanged. Assert the nested field location in the real 422 response, not just the status. Add browse HTTP Unicode minimum/maximum checks so frontend fixtures use confirmed wire behavior.
3. Insert an overlong saved blob directly using the existing real `db_session` and `SavedSearch` ORM model to represent previously accepted storage. Include an ordinary sibling. GET must return both with the overlong text intact; PUT rename must return 200 with unchanged parameters; DELETE must still work. Bypass creation only for arranging previously stored data, not for proving writer rejection.
4. Verify OpenAPI creation/read separation and max-only-on-create as described in the backend section. Retain existing 400/401/409 route error declarations.
5. Preserve price tests at exactly 1e15 and add the representable value 1e15+1 for each bound. No change to browse price acceptance is intended.

Frontend tests belong in existing `filters.test.ts`, `hooks/hooks.test.tsx`, `components/filter-controls.test.tsx`, `components/pages.test.tsx`, `SaveSearchControl.test.tsx`, `useSavedSearches.test.tsx`, and `SavedSearchesPage.test.tsx` as relevant. Use actual hooks/components/router with fetch stubs, not mocked application hooks.

1. Shared text helper: absent/blank, two/three code points, 100/101 ASCII, 100/101 astral, combining sequences, and padded 100 characters. Parser retains raw text. Valid serializers preserve trimmed text. Invalid text remains identifiable rather than disappearing into an unrestricted serialized query.
2. Cold overlong URL: full input and route text retained; visible actionable validation; no `/contracts/` list request after debounce/readiness; no perpetual skeleton, generic Retry, or matching-results count. Taxonomy/current-user requests are independent and should not be counted as forbidden list requests.
3. Warm valid results -> paste 101-character text -> settle -> shorten to 100 -> settle. Invalid state hides stale results and issues no invalid list request; correction fetches valid text and restores rows. Include non-search control changes, taxonomy refresh, and manual refetch while invalid; assert URL/payload and the absence of a list request. For absence assertions, control debounce timers and complete readiness work explicitly rather than asserting immediately before an asynchronous request could occur.
4. Apply a persisted overlong saved row through the real Saved Searches page: navigation preserves text and other criteria, the contracts page gives visible validation, no list request is dispatched, and shortening restores a normal request. This should also protect the small-screen path where the filter rail starts collapsed.
5. Open save with invalid text or min/max price above the saved ceiling: visible field-specific guidance, disabled submit, programmatic form-submit guard, retained name, and zero POSTs. After correction Save works and the wire payload includes every accepted criterion. Browse with a price above 1e15 still sends that price; saving at exactly 1e15 succeeds. Preserve the established sub-three-character omission test.
6. Hook 400 test asserts server detail survives in `ApiError` and saved-list cache is not invalidated. Component 400 test asserts remove-before-saving guidance and recovery. Preserve 409, network, 401, and success-invalidation cases. Exercise known 422 field arrays, unknown/malformed 422 details, and generic 5xx without mislabeling them. A test that only asserts status would miss the cap defect again.
7. Keep accessible input description/error-state checks and existing page accessibility coverage. Avoid a global warning suppressor: authenticated responders must route notification endpoints to the correct envelope, as the consolidated report's baseline fixture finding requires.

## Implementation commands and verification requirements

The [remediation plan's database preflight](../plans/2026-09-05-contract-search-bug-hunt-remediation-plan.md#runtime-and-database-preflight) governs execution, including the full suite's separate migration-equivalence database and shared-server exclusion.

After the failing tests exist, run targeted backend cases from `app/backend` with the established Python/PDM environment and a verified isolated `DATABASE_URL_TESTS`. The shared fixture drops and recreates tables; do not improvise a database target or start `pdm run dev`, whose lifespan is destructive. This investigation did not establish that dependencies or the test database are available.

```text
pdm run pytest src/fastapi_app/tests/api/test_account_schemas.py src/fastapi_app/tests/api/test_saved_searches.py src/fastapi_app/tests/api/test_contracts.py
pdm run export-openapi
```

Regenerate the frontend contract only after the backend schema change, then use the installed frontend dependencies from `app/frontend/web`:

```text
npm.cmd run generate:api
npm.cmd test -- src/features/contracts/filters.test.ts src/features/contracts/hooks/hooks.test.tsx src/features/contracts/components/filter-controls.test.tsx src/features/contracts/components/pages.test.tsx src/features/saved-searches
npm.cmd run lint
npm.cmd run build
```

Run the full project-required backend/frontend checks after integration with the pagination, readiness, and saved-row fixes. Inspect real stdout/stderr and preserve pristine output. Generate `app/frontend/web/openapi.json` and `src/lib/api/schema.d.ts` through their commands; never hand-edit either. TypeScript generation does not enforce runtime length/price limits, so generated types do not replace frontend validation. No dependency change is needed.

## Decision rationale and limits

The request subclass is recommended because its field maximum is visible in OpenAPI and it leaves every stored-read call site intact. A shared-model maximum violates the approved persisted-data contract. Truncation, dropping text, a migration, a custom criteria-editing endpoint, and a common browse/save price ceiling were considered and excluded because they change data or policy beyond the approved remedy.

The easily missed interactions are disabled queries retaining pending/data/error state, manual refetch bypassing `enabled`, the two opposite debounce transitions, and the hidden mobile filter rail. Each affects whether the user sees an actionable validation state rather than an accidental loading or network-error state. Backend raw-string validation and frontend trimming are intentionally different layers; adding server normalization is unnecessary and would change existing API behavior.

The node character-count probe and installed query-core source inspection succeeded. Backend Unicode/ORM/HTTP tests and the proposed UI transitions were not executed here; runtime implementation verification remains required. Initial git status encountered Windows ownership protection; a command-local `safe.directory` for this known worktree succeeded and showed a clean starting worktree. A Windows `rg` glob and one read issued from the wrong subdirectory failed; corrected discovery/read paths provided the evidence. No failed command is represented as a passing check.
