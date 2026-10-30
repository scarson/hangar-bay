<!-- ABOUTME: Holistic correctness audit of contract browsing and saved-search replay at d43da7c. -->
<!-- ABOUTME: Records source-backed findings, verification limits, and previously accepted concerns. -->

# Contract search and saved-search replay: holistic bug hunt

## Scope and method

Audit date: September 5, 2026. Frozen source: `d43da7c9313de7ce19aa9de21242b07949da4364`, verified in the isolated `bug-hunt-contract-search-2026-09-05` worktree. This report uses repository-relative paths and one-based source lines at that revision.

Applied the holistic hunter's read-everything-then-reason method. Read the complete primary implementation before analyzing the composed flows: backend contract and saved-search routers, services, contract schemas/models and saved-search portions of account schemas/models; frontend contracts and saved-searches feature implementation, both contract routes, API client, application QueryClient configuration, debounce helper, and current-user hook. Read adjacent ingestion code for region stamps, enrichment version, and completion semantics. Inspected existing parser, hook, component, account-schema, and saved-search API tests after forming the implementation model. Source was first read in the root checkout at the same frozen revision, then findings were checked in the isolated worktree.

Design references reviewed: [Product principles, including restorable URL state](../../PRODUCT.md), [F008 type-aware browsing specification](../../design/features/F008-Type-Aware-Contract-Browsing.md), [F008 implementation decisions](../superpowers/plans/2026-08-06-f008-decision-log.md), [overnight follow-up decisions](../superpowers/plans/2026-08-08-overnight-followups-decision-log.md), [M3 account-feature design](../superpowers/specs/2026-07-17-m3-account-features-design.md), [F005 saved-search feature requirements](../../design/features/F005-Saved-Searches.md), [implementation pitfalls](../pitfalls/implementation-pitfalls.md), and [testing pitfalls](../pitfalls/testing-pitfalls.md). Prior findings were checked against the [August 8 consolidated F008 bug hunt](2026-08-08-f008-prerelease-consolidated.md), [living coverage register](../test-coverage-reports/2026-08-09-f008-remediation-test-coverage-review.md), and [September 5 coverage handoff](../superpowers/handoffs/2026-09-05-frontend-coverage-handoff.md).

No application source changes, dependency installs, server launches, git mutations, database operations, or database-touching tests were performed by this hunter. The only executable probe used the already-installed TanStack Query core in memory, described under H4. Findings H1-H3 are source-established and await the consolidator's component/schema cross-validation; this report does not claim browser or database reproduction. Existing test failures were not observed because this hunter did not run the application test suites. The only file written is this report.

## Bugs

### H1. Pagination correction overwrites a restored URL using another search's result count

**Severity:** significant (P2). **Verification:** source trace; dynamic component confirmation requested from consolidator.

**Location:** `app/frontend/web/src/features/contracts/components/ContractsPage.tsx:159-165`; interacting code at `app/frontend/web/src/features/contracts/hooks/useContracts.ts:57-72,117,128` and `ContractsPage.tsx:127-131`.

**Reachable scenario:** Open a broad search on page 5 with 1,000 matches. Change a discrete filter, which pushes a page-1 history entry. Type search text into that filtered view, which replaces the current history entry, and let its 30-match result settle. Press Back. The router restores the earlier broad search and page 5, while its changed search text starts the 300 ms debounce. `useContracts` freezes the entire effective query at the narrow search until that debounce settles. The visible `data.total` therefore remains 30 while live `search.page` is 5. This scenario does not require the broad result to have expired from the query cache: the frozen effective query prevents selection of its cache key during the debounce.

**Expected:** Restore page 5 and the earlier filters. Correct the page only after the response belongs to the restored effective search and proves page 5 is out of range.

**Actual:** `pageCount` is computed as 1 from the narrow result, `pageOutOfRange` compares that against the restored page 5, and the effect replaces the history entry with page 1. When the correct broad query finally settles, the user's restored page has already been lost. `keepPreviousData` exposes the same mismatch on uncached non-text query transitions. This is a persisted navigation side effect, beyond merely showing a stale count during a refresh.

**Design evidence:** Product principle 2 requires view states, including pages, to be shareable and restorable. Implementation pitfall WEB-1 requires data interpretation to follow the response. The pagination code's own comment promises to preserve the user's query instead of destroying it. The accepted debounce residual in `useContracts.ts:63-69` concerns immediate page chrome; it does not authorize writing a different page to history from an unrelated response.

**Why existing tests miss it:** `components/pages.test.tsx:283-351` tests genuinely invalid pages against one result population, including a blocked corrective navigation. Its text/reset test asserts immediate reset to page 1. Neither combines Back restoring a different text and a valid higher page with the still-frozen narrow response. Hook debounce tests verify freezing in isolation, which is correct; the bug is what the page effect does with the frozen data.

**Minimal fix direction:** Gate the corrective navigation on response/request identity, including the live page and effective filter state. The captured `data.countsSearch` is available for this purpose. Checking only `isFetching` or `isPlaceholderData` is insufficient during debounce because the old effective query can be a settled, successful cache hit. Add a component regression covering the actual history sequence and assert both the final restored URL page and matching rows.

### H2. Search text accepted by the UI and saved-search model exceeds the list endpoint's limit

**Severity:** significant (P2). **Verification:** source-established schema mismatch; no HTTP/database reproduction by this hunter.

**Location:** `app/frontend/web/src/features/contracts/filters.ts:273,324-327`; `app/frontend/web/src/features/contracts/components/FilterRail.tsx:61-70`; `app/backend/src/fastapi_app/schemas/contracts.py:350-359`; `app/backend/src/fastapi_app/schemas/account.py:25`; `app/frontend/web/src/features/saved-searches/components/SaveSearchControl.tsx:38`; replay at `app/frontend/web/src/features/saved-searches/components/SavedSearchesPage.tsx:122-129`.

**Reachable scenario:** Paste a contract description or multi-name query containing 101 non-whitespace characters into Search, or open an ordinary shared URL carrying it. The input has no maximum length; the parser preserves any nonempty string; `toApiQuery` checks only the three-character minimum. An authenticated user can additionally save the query: the save mapper also checks only the minimum, and `SavedSearchParameters.search` has no maximum.

**Expected:** The supported search limit is handled coherently in the input/URL path and the persisted-search contract. A saved search must not be accepted as replayable while its exact search text is rejected by the endpoint it replays against.

**Actual:** `ContractFilters.search` rejects the 101-character text because its maximum is 100. The main listing falls to the generic service-unreachable error card, and Retry repeats the same invalid request. Saving can succeed; Apply reproduces the failure later. The account-schema docstring explicitly promises its bounds match `ContractFilters` so saved blobs cannot replay into a 422, which is false for this field.

**Design evidence:** M3 design section 5 requires the saved-search mapper to use the same text gate as `toApiQuery`; F005 story 3 requires saved criteria to re-execute. F008 decision D4 explicitly records matching saved/list filter bounds and warns that narrowing a read-validated stored model can break existing saved rows. The coverage register records the separate list-bound addition in PR #164; this is the downstream alignment omission, not a request to remove that approved bound.

**Why existing tests miss it:** `SaveSearchControl.test.tsx` and `hooks.test.tsx` pin the short-text gate; saved-search schema tests reject two characters and accept typical short text. No inspected test runs the upper boundary through both save and replay. Testing the list endpoint's 100-character rejection alone cannot catch the consumer mismatch.

**Minimal fix direction:** Define and enforce the supported search bound across the parser/input, API-query mapper, and saved-search write validation. Preserve explicit semantics for overlong URL input rather than silently pretending an invalid query was run. Before tightening the shared saved-search response model, inspect existing persisted overlong blobs and choose a migration/read policy: the same model validates list responses, so naively adding `max_length=100` can turn one already-saved row into a failure of the entire saved-search list. Any persisted-data policy belongs in the reviewable remediation design.

### H3. Failed saved-search rename and delete operations give no visible or announced feedback

**Severity:** significant (P2). **Verification:** complete component/hook source trace; dynamic component confirmation requested from consolidator.

**Location:** `app/frontend/web/src/features/saved-searches/components/SavedSearchesPage.tsx:131-177`; `app/frontend/web/src/features/saved-searches/hooks/useSavedSearches.ts:39-63`; backend expected duplicate-name behavior at `app/backend/src/fastapi_app/services/saved_search_service.py:73-91`.

**Reachable scenario:** Save searches named A and B, then rename B to A. The backend returns the intended 409. Alternatively, rename with a name over 100 characters (422), or confirm Delete while the request fails or the row was already deleted in another tab (404).

**Expected:** Keep the recoverable edit or row in place and state why the operation did not finish, with accessible feedback and an appropriate retry/edit path. For duplicate names, ask the user to choose another name.

**Actual:** The hooks correctly throw `ApiError`, but `SavedSearchRow` reads neither `rename.isError`/`rename.error` nor `remove.isError`/`remove.error`. Only pending state and success handlers affect the render. A rejected rename leaves the input open and Save enabled without an explanation; a failed deletion leaves the row and eventually resets the confirmation button without an explanation. The always-mounted live region at `SavedSearchesPage.tsx:77` is empty and never receives mutation outcomes.

**Design evidence:** M3 section 5 explicitly requires `aria-live` on save/delete feedback, and the feature's rename/delete actions are in scope. `SaveSearchControl.tsx:93-103` provides the working sibling pattern: duplicate names and generic failures are rendered inline. No prior consolidated F008 finding or reviewed coverage handoff accepts silent saved-search write failures.

**Why existing tests miss it:** `SavedSearchesPage.test.tsx` exercises successful rename/delete and list-load failure. Hook tests exercise rejected mutations below the component boundary. Backend `test_rename_to_existing_name_409` establishes the real, routine conflict outcome, but no inspected page test checks what the person sees when that outcome reaches the row.

**Minimal fix direction:** Render per-row rename/delete error feedback from the existing mutation state, with duplicate-name wording and general failure wording. Reset stale feedback when starting/canceling an operation. Add component tests for duplicate rename and failed delete using the fetch seam; assert the message, retained data, and recovery rather than merely observing the rejected request.

### H4. A failed taxonomy refresh keeps the item-filter surface falsely marked ready

**Severity:** significant (P2). **Verification:** actual installed TanStack Query cache behavior confirmed in an in-memory probe; application consequences traced in source.

**Location:** `app/frontend/web/src/features/contracts/hooks/useContracts.ts:99-103,122`; `app/frontend/web/src/features/contracts/hooks/useTaxonomy.ts:53-59,69-80`; the resulting warning condition is `app/frontend/web/src/features/contracts/components/ContractsPage.tsx:247`.

**Reachable scenario:** The taxonomy endpoint first returns `coverage: complete`, opening the item-level filters. A later five-minute poll times out or returns an error, for example during a deployment/enrichment resweep or a taxonomy-specific failure. The contracts endpoint remains available and the user runs a taxonomy/blueprint-filtered search.

**Expected:** After a failed readiness probe, the surface is treated as not ready as the hook and approved design describe. New list responses carry false readiness and show the indexing/incomplete-results warning when such filters apply. Previously displayed rows keep their own captured semantics until the replacement response arrives.

**Actual:** TanStack Query retains the successful `data` when a refetch fails. Both consumers check only `data.coverage === complete`; neither checks the query's error state. They therefore keep the controls open, preserve the true-readiness list key, and label newly fetched results ready. If enrichment has actually become partial during the outage, short results are shown without the intended warning. Repeated failures can retain that claim indefinitely rather than merely for one scheduled polling interval.

**Executable evidence:** An in-memory `QueryClient` was seeded at `['contracts','taxonomy']` with `{coverage:'complete'}`. A `fetchQuery` on that key used a rejecting function and `retry:false`; the caught failure left `{status:'error', coverage:'complete', itemSurfaceReady:true}`. This used the already-installed `@tanstack/query-core`; it created no server, file, network request, or database connection.

**Design evidence:** F008 decision D13's final mechanism says an error counts as an answer and an unreachable endpoint degrades to not ready. `useTaxonomy.ts:55` says a failed readiness probe means not ready; lines 69-73 make the same claim for callers. Decision D1 requires readiness to degrade automatically across future resweeps. This is distinct from the previously recorded multi-statement taxonomy snapshot concern: the stale true value here survives any number of failed polls.

**Why existing tests miss it:** `hooks.test.tsx:166-213` covers successful partial-to-complete and complete-to-partial responses. The timeout test starts without cached taxonomy data. Neither failure path has a prior successful complete value to retain.

**Minimal fix direction:** Derive readiness from a successful, non-error query result and use that same rule for both the rail and list fetch captures. Keep the existing sequencing and readiness-key mechanism. Add a success-then-error hook/component test and a later recovery test; assert the actual captured readiness and visible warning, not just request counts.

## Design concerns and prior dispositions

These are existing decisions or lower-confidence presentation concerns, not additional newly confirmed bugs:

- Search and `type_ids` still match requested items and compose on joined rows (`contract_service.py:273-281,346-347`), unlike the F008 offered-item families. This is the prior consolidated report's requested-side-search decision, still requiring a product call. It was not counted again.
- Item-bearing segment numerals are intentionally suppressed when an item-less selection makes the available counts unsuitable for the click destination (`SegmentTabs.tsx:120-165`). Mirror counts remain the prior API-envelope follow-up. Accepted temporary stale counts are not H1's persistent history overwrite.
- Active taxonomy/blueprint controls are hidden while readiness is partial (`FilterRail.tsx:190-209`). The earlier report already records the hidden-active-filter UX concern. H4 is about incorrectly retaining ready after a failed refresh, not reopening that policy.
- Category/group multi-selection semantics, auction BPC badge absence, volume/collateral sort reconciliation, and the `min_runs=-1` rationale were already recorded in the prior report. The nonnegative UI parser is an explicit policy, so its difference from the server's -1 bound was not promoted as a fresh replay defect.
- The saved-search summary (`SavedSearchesPage.tsx:18-55`) does not name `contract_type` and labels every ships-disabled search “All contracts,” including courier-only searches. This loses useful meaning and can mislead, but the reviewed design requires a compact human-readable summary without explicitly prescribing every displayed criterion. Treat as a small presentation decision if this area is revised, rather than inflating the confirmed-bug count.

## Rejected candidates and scope boundaries

- Best-effort saved-search cap overshoot is explicitly accepted by M3 section 3.5; it is not a concurrency bug in this audit.
- Item filters surviving item-less segment switches, and honest zero counts for unsatisfiable combinations, are the ratified no-clearing decision in overnight follow-up OD4.
- Separate blueprint filter families may match different offered items; both bounds within one family must match a single item. The implementation follows the ratified F008 semantics. A straddling multi-item contract appearing in both independent single-bound searches is correct.
- Unknown contract types fold into the unknown segment consistently in the count and filter paths. Joined pagination groups distinct contract IDs and restores their order; no new deterministic query-shape disagreement was found.
- Expired contracts remaining readable by detail link, per-region liveness watermarks retaining stale data when ingestion stops, and observed-row region coverage are documented behavior. No live database was consulted to estimate present coverage.
- The prior ingestion cache-body eviction/pagination concern and mocked 304 exception-handler concern are outside this primary read/replay scope and already tracked. No exploit reproduction, authentication investigation, or external-target test was performed.

## Testing-pitfalls review and completion

The testing-pitfalls document was reviewed after the hunt. H1 reuses WEB-1 and TEST-25's requirement to observe returned state across cache/debounce boundaries; H2 is validation agreement across consumers; H3 demonstrates the gap between hook error handling and visible component outcomes; H4 needs a cached-success-before-error fixture. These suggestions are specific to the findings above. No general advice or pitfall edits were made because only this report was assigned for persistence.

**Status: DONE_WITH_CONCERNS.** Primary source analysis and report persistence are complete. Four source-backed bugs are submitted for consolidation, with direct library-state evidence for H4. Browser/component and HTTP/database reproduction were not performed by this hunter; the consolidator owns independent validation and final disposition. No production fix is claimed.
