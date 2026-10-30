<!-- ABOUTME: Five-pass correctness audit of contract search and saved-search replay at d43da7c. -->
<!-- ABOUTME: Records source evidence, candidate dispositions, and verification limits for consolidation. -->

# Contract search and saved-search replay: multipass hunt

## Scope and method

Frozen revision: `d43da7c9313de7ce19aa9de21242b07949da4364`. Source root: `C:/Users/Sam/Code/hangar-bay/.claude/worktrees/bug-hunt-contract-search-2026-09-05`.

Primary source: backend contracts/saved-search routers, services, schemas and models; frontend contract filter parsing, hooks, filter controls, segments, columns, formatting, list/detail pages, pagination, saved-search serialization/hooks/manage page and both contract routes. Adjacent source: API client, query defaults, debounce, identity hook, DB session configuration, and ingestion watermark writer. Generated files are excluded from correctness analysis.

Design evidence: PRODUCT.md; F008 Type-Aware Contract Browsing; F005 Saved Searches; M3 account design; F008 decision log; implementation/testing pitfalls; the August 8 consolidated F008 hunt; September 5 frontend coverage handoff and its coverage register. Historical dispositions take precedence over rediscoveries. No test source was read, per the multipass skill. Regression suggestions below describe desired verification, not a claim that an existing test is missing. The parent owns test-gap inspection and dynamic validation.

Source gathering began read-only in the root checkout while report-directory authorization was pending. The isolated checkout was then verified at the same frozen revision before recording pass 1. No source modifications, database operations, dependency acquisition, servers, or Git changes were performed by this hunter.

## Pass progress

- [x] Pass 1: contract violations.
- [x] Pass 2: cross-sibling pattern violations.
- [x] Pass 3: failure modes.
- [x] Pass 4: concurrency.
- [x] Pass 5: error propagation.

## Bugs

### M1. Search text accepted by the UI and saved-search API exceeds the list endpoint's maximum

**Location:** `app/backend/src/fastapi_app/schemas/contracts.py:351-358`; `app/backend/src/fastapi_app/schemas/account.py:25`; `app/frontend/web/src/features/contracts/components/FilterRail.tsx:63-70`; `app/frontend/web/src/features/contracts/filters.ts:273,327`; `app/frontend/web/src/features/saved-searches/components/SaveSearchControl.tsx:38`.

**Severity:** significant (P2). **Found in:** Pass 1, contract violations. **Status:** source-confirmed; no runtime HTTP request made.

**Expected:** ordinary search input has a clear, consistent accepted length, and successfully stored search parameters replay into a valid list request. The saved-search model explicitly promises bounds matching `ContractFilters` so replay cannot produce a 422 (`schemas/account.py:15-21`). F005 criteria 1.3 and 3.2 require storing and re-executing the criteria.

**Actual and reachability:** the list model limits search to 100 characters. The search box has no maximum, the URL parser preserves any nonempty string, and `toApiQuery` gates only the minimum trimmed length. A normal paste of a longer ship/contract description therefore becomes an invalid list request; the UI presents the generic market-service failure message and retry repeats it. Saving that same view succeeds because both `toSavedSearchParameters` and `SavedSearchParameters.search` lack the upper bound. Applying it later preserves the overlong text and repeats the failure. No malformed wire request is necessary: every step is reachable from the ordinary controls.

**Minimal fix:** make the search-length contract consistent at input, URL validation/API serialization, and saved-search creation. Explain or normalize overlong text according to the existing junk-tolerant URL policy. Preserve read access to any already-stored longer values when tightening write validation: the same `SavedSearchParameters` model validates list responses, so blindly adding `max_length` there can make one existing row break the whole saved-search list. The parent should flag that persistence choice for review.

**Regression check:** exercise 100-character and 101-character input through parser, request mapping, save, and apply; verify the invalid boundary does not produce a generic service outage or create an unreplayable search. Also verify listing any pre-existing longer blob under the chosen remediation.

### M2. Saved-search rename and delete failures never reach the user

**Location:** `app/frontend/web/src/features/saved-searches/components/SavedSearchesPage.tsx:106-183` (mutation state and complete row renderer), especially `:135,149,166-167`; `app/frontend/web/src/features/saved-searches/hooks/useSavedSearches.ts:47,61`; `app/backend/src/fastapi_app/services/saved_search_service.py:81-85`. Successful sibling error rendering is `SaveSearchControl.tsx:94-102`.

**Severity:** significant (P2). **Found in:** Pass 2, cross-sibling patterns; traced through failure and error propagation in later passes. **Status:** source-confirmed.

**Expected:** failed saved-search mutations provide a clear user-facing reason or recovery message. F005 section 9 explicitly requires user-friendly API error messages; duplicate names return 409 with a choose-another-name message. Section 12 requires feedback to reach screen readers.

**Actual and reachability:** create renders both duplicate-name and generic errors, but the manage-page row reads only the rename/delete mutations' pending states. Rename returns 409 whenever the user chooses another saved search's existing name; the hook throws `ApiError`, React Query records failure, and no branch displays it. The Save button becomes enabled with the form still open and no explanation. Delete behaves similarly on an ordinary network/server failure or a stale row already deleted elsewhere. The parent list's `isError` belongs to the list query, so it does not catch mutation errors. Its empty live region at `SavedSearchesPage.tsx:78` never receives outcome text.

**Minimal fix:** render per-row rename and delete error states, distinguishing rename conflicts from retryable failures; reset errors when opening/cancelling a fresh interaction. Keep the entered rename so the user can correct it. Populate the intended accessible feedback surface rather than leaving it permanently empty.

**Regression check:** rename one existing search to another search's name and verify a visible/announced conflict while both rows remain intact; reject a delete request and verify a retryable error and preserved row; retry successfully and verify stale feedback clears. Parent to determine existing test coverage.

### M3. Pagination repair rewrites a valid restored page using another search's count

**Location:** `app/frontend/web/src/features/contracts/components/ContractsPage.tsx:159-165`; `app/frontend/web/src/features/contracts/hooks/useContracts.ts:57-72,117,128`; navigation semantics at `ContractsPage.tsx:122-130`.

**Severity:** significant (P2). **Found in:** Pass 4, concurrency/asynchronous transitions. **Status:** source-confirmed transition; parent to run a component reproduction.

**Expected:** Back restores the URL's filter/sort/page state, and out-of-range repair uses a count for that requested search. PRODUCT principle 2 makes URL restoration an explicit product contract. The repair comment itself says it should handle pages that actually exceed the result's last page.

**Actual:** `pageCount` comes from the current hook data but `pageOutOfRange` compares it with the live URL's page. The hook deliberately retains another search's data both during text debounce (`effectiveSearch = lastSettled`) and through `keepPreviousData`. The effect immediately replaces the requested page with the other search's last page. When the correct query later settles, its larger total cannot restore the original page because the URL was already overwritten.

**Reachability:** browse search A on page 4 with at least four pages; toggle a discrete filter (pushes an entry and resets to page 1), then type narrower search B (replaces that current entry) whose settled results have one nonempty page. Back restores A/page 4. For the next 300 ms, `useContracts` still serves settled B/page 1. The effect interprets A's page 4 against B's one-page total and rewrites A to page 1. This debounce case does not depend on whether A is cached, and `isPlaceholderData` need not be true because the hook is still observing B's real query. A corresponding stale-data window exists when returning to an evicted query without a text change.

**Minimal fix:** authorize repair only when the data describes the currently requested search and page; use the captured `countsSearch`/effective request identity or an explicit settled-response state. Guarding only `!isPlaceholderData` misses the debounce mechanism. Continue clamping genuine out-of-range responses after a matching result arrives.

**Regression check:** the exact browser-history transition above, holding the debounce interval and incoming response independently, must preserve page 4 until A answers. Also verify a genuinely overlarge matching page still repairs to the last valid page and that placeholder data from a different query cannot trigger navigation. Parent to assess current test coverage.

### M4. Failed taxonomy refreshes keep reporting a prior complete readiness result

**Location:** `app/frontend/web/src/features/contracts/hooks/useTaxonomy.ts:40-54,71-80`; `app/frontend/web/src/features/contracts/hooks/useContracts.ts:99-103,122`; consequence at `app/frontend/web/src/features/contracts/components/ContractsPage.tsx:247-251`.

**Severity:** significant (P2), conditional on a failed refresh after an earlier complete result. **Found in:** Pass 5, error propagation. **Status:** source-confirmed against application code and the installed query library's error-state reducer; parent to dynamically validate.

**Expected:** an unsuccessful readiness probe degrades to not-ready while normal contract browsing continues. This is explicit in `useTaxonomy.ts:54` and its readiness helper contract at `:71-74`, and matches F008 decision D13's error fallback. Freshly fetched filtered rows must carry the appropriate incomplete-index warning.

**Actual and reachability:** first fetch succeeds with `coverage: complete`; a subsequent five-minute poll, refocus fetch, or remount fetch times out or fails. The taxonomy hook throws, but TanStack Query retains its last successful `data`. The installed implementation confirms this: `app/frontend/web/node_modules/@tanstack/query-core/src/query.ts:670-684` spreads prior state into the error state without clearing `data`. Both consumers look only at `data.coverage`, so controls remain open and list queries continue capturing `itemSurfaceReady: true`. If a resweep has begun while the taxonomy route is unavailable, taxonomy/blueprint-filtered rows can be incomplete without the warning. This lasts until a successful probe, rather than the bounded five-minute normal stale window.

**Minimal fix:** derive readiness from both the query's successful status and coverage in one shared rule, preserving the fetch-time capture/key mechanism for row descriptions. Keep cached option data if useful, but do not treat its continued existence as proof that the latest readiness probe succeeded.

**Regression check:** seed a successful complete probe, fail a later refresh, and assert the control gate closes and a subsequently fetched item-filtered list captures not-ready; verify recovery restores readiness and that the first-load error still unblocks the list. This differs from testing a cold initial error with no cached data.

## Design concerns

### MC1. Saved-search creation discards the actionable cap failure

`saved_search_service.py:48-52` returns a clear 400 explaining the per-user maximum. `useSavedSearches.ts:31-32` discards the parsed response error and builds an `ApiError` from status alone, even though `lib/api/client.ts:35-44` supplies `extractDetail` for this purpose. `SaveSearchControl.tsx:98-100` consequently says only to try again. At the configured cap, retry cannot succeed until the user deletes a search. This is a minor recovery-message defect; the cap behavior itself is deliberate and the save remains correctly rejected. It is recorded separately from M2 because an error message is visible here and the impact is narrower. Minimal follow-through is to preserve and render the cap detail with a deletion/recovery hint. No runtime cap setup was performed.

### Pass 3 disposition

The save/create, rename/savepoint, delete/flush, and read/serialize pipelines were traced step by step. Assigning the rename inside `begin_nested()` correctly protects its unique-constraint failure; refresh loads response defaults before serialization, and the session dependency rolls back/rethrows on failure. No additional source-confirmed transaction bug was established. M1's use of the stored validation model on response reads remains a remediation hazard, not evidence that today's saved-search list already fails. M2's UI error omission survives the complete service-to-component trace.

### Pass 4 disposition

M3 is distinct from the accepted brief live-chrome/held-row mismatch documented in `useContracts`: this path mutates navigation permanently rather than merely painting transient stale data. Search/count/page SQL statements also execute separately while ingestion may commit, so cross-statement snapshots deserve consideration if strict per-response consistency becomes a requirement. No database interleaving was executed and this is not promoted to a confirmed bug; the analogous taxonomy two-statement concern is already documented in the August 8 hunt. Saved-search uniqueness is database-backed; the cap race remains explicitly accepted.

### Pass 5 disposition and testing-pitfalls review

Contract-service exceptions are logged and rethrown, so no silent success response was found there. Anonymous identity fallback is explicitly designed to return null on any failure and is not reported as an error-swallowing bug. The saved-search hooks throw on unsuccessful requests, locating M2 at the rendering layer rather than the API transport. Taxonomy first-load failure handling works; M4 is the distinct cached-success-to-error transition.

Reviewed `docs/pitfalls/testing-pitfalls.md` after completing the hunt. Its error-path, oversized-input, asynchronous-transition, and timeout guidance already describes the general defect families. No generic advice or source edits were added. M3 suggests a focused future addition to WEB-1/testing guidance: automatic navigation derived from response metadata must wait for metadata belonging to the requested URL, and debounce-held data can be non-placeholder data. The parent owns any shared pitfalls edits.

## Bugs outside primary scope

None newly established. Previously recorded ingestion/name-cache, requested-item search semantics, dependency alerts, and test-mock concerns were left in their authoritative existing records.

## Completion

All five passes completed and persisted incrementally. Four source-confirmed bugs (M1-M4) and one minor recovery-message concern (MC1) are submitted for independent consolidation. Audit status: DONE_WITH_CONCERNS because runtime verification and test-gap conclusions belong to the parent and have not been claimed here.

## Rejected and previously documented candidates

- The best-effort saved-search cap can overshoot with concurrent creates. Explicitly accepted in M3 account design section 3.5; not a new bug.
- Search and `type_ids` include requested items and use joined-row semantics. Already recorded as a product decision in the August 8 hunt, design concern D-a; not reflagged.
- Separate blueprint families can match different offered items; both bounds within one family match the same item. F008 section 3.1 and its ratified decision explicitly require this.
- `is_bpc=false` correctly includes item-less contracts through negated EXISTS. Dropping this filter on segment change would alter saved-search meaning.
- Sort reconciliation, missing volume/collateral headers, item filters hidden during a resweep, suppressed segment numerals, and two-read taxonomy consistency are previously documented decisions/concerns in the August 8 hunt.

## Verification limitations

This report is a static correctness audit. No existing tests were read or run, no browser interaction was performed, and no database or production endpoint was contacted. Source-confirmed findings still require the parent's independent validation and test-gap assessment. Scope does not include security assessment or exploit reproduction.
