<!-- ABOUTME: Depth-first correctness audit of contract-search URL state, query readiness, and saved-search replay. -->
<!-- ABOUTME: Records source evidence, reachable failures, accepted decisions, and verification limits at d43da7c. -->

# Contract search exploratory bug hunt

## Scope and method

Frozen application revision: `d43da7c` (September 5, 2026). This report follows the exploratory hunter's depth-first methodology. File listings identified the highest-risk coordination points first: `useContracts` and `ContractsPage` combine live URL state, a delayed query, cached responses, and navigation side effects; saved-search Apply crosses server validation and the route parser; readiness coordinates two independent API queries.

Deep reads covered frontend contract filter parsing, list/query state, segmentation, taxonomy and blueprint controls, pagination, detail navigation, saved-search serialization/components/hooks, backend contract querying/counts/pagination/readiness, saved-search CRUD and schemas, related model fields, router bindings, and relevant existing tests. Adjacent reads included API error handling, QueryClient defaults, debounce behavior, and ingestion liveness semantics. The highest-risk threads were followed through callers, callees, tests, and decisions before moving on.

Design calibration included PRODUCT.md; implementation and testing pitfalls; F008's item-filter, segment, readiness, and URL semantics; the F008 decision log (including the reversed readiness decision); the overnight offered-filter decision; M3 account design; F005 error handling; the August 8 consolidated hunt; the September 5 coverage handoff and page-coverage report; and the living coverage remediation register. Existing coverage counts are historical evidence only, not a fresh test result.

Source paths below are repository relative. They refer to the frozen revision and resolve under the audit worktree at `C:/Users/Sam/Code/hangar-bay/.claude/worktrees/bug-hunt-contract-search-2026-09-05`.

## Bugs

### E1 — Back navigation can replace a valid restored page with another search's last page

**Severity:** significant (P2).  
**Location:** `app/frontend/web/src/features/contracts/components/ContractsPage.tsx:159-165`. Supporting mechanism: `app/frontend/web/src/features/contracts/hooks/useContracts.ts:57-73`; URL updates at `ContractsPage.tsx:127-130`; search field history replacement at `components/FilterRail.tsx:77-85`.

**Reachable scenario:** A search for Tristan has at least four pages. Browse through pages 3 and 4. Type Rifter, which resets page to 1 and replaces the current history entry, and let its smaller nonzero result (for example, 10 contracts at size 50) settle. Press browser Back. The prior history entry correctly restores Tristan/page 3.

**Expected:** The restored Tristan/page 3 remains in the URL and is queried or served from its matching cache. Automatic page correction uses Tristan's own result.

**Actual and evidence:** The changed search text starts the 300ms debounce. `effectiveSearch` remains the last settled Rifter/page 1 during that interval, so `data.total` still describes 10 Rifter results. The page component computes `pageCount=1`, compares the live `search.page=3` against it, and its effect replaces the URL with Tristan/page 1. This runs before Tristan settles, even when the requested Tristan/page 3 is cached: the hook has not switched to that key yet. The original, valid history entry is overwritten. The same defect also exists with `keepPreviousData` after a non-text query transition, but the text/history sequence establishes reachability without relying on cache eviction.

**Root cause:** Navigation correction combines live request state and results from another request. The data already carries `countsSearch`, but the correction ignores it.

**Design evidence:** PRODUCT.md principle 2 requires filters, sorts, and pages to be restorable from the URL. The implementation-pitfalls WEB-1 rule says claims about held rows must use the request they belong to. The debounce's accepted residual at `useContracts.ts:63-69` permits temporary chrome disagreement; it does not permit rewriting a different search's history. The September 5 page-coverage report pins genuine out-of-range correction and independent text replacement, not their composition.

**Test gap:** Existing `pages.test.tsx` cases at lines 283 and 303 start with a truly invalid page or hold its redirect. Hook debounce tests pin frozen requests. Neither proves that Back to a higher valid page survives a changed-text debounce.

**Smallest fix recommendation:** Gate out-of-range correction on the returned search matching the live search by value, including the requested page, so both frozen-query and placeholder states stand down. Preserve correction for a settled matching response that proves the page invalid. Add a real-router component regression combining navigation history, a changed search string, a smaller result, and Back; assert the restored page and the returned rows, not only network-call counts.

**Verification:** Confirmed by source/control-flow trace. This worker did not execute a browser/component reproduction; coordinator validation is pending.

### E2 — Rename and delete failures on saved searches produce no user feedback

**Severity:** minor (P2 user-flow defect).  
**Location:** `app/frontend/web/src/features/saved-searches/components/SavedSearchesPage.tsx:131-177`, especially rename submission at 135 and delete submission at 167. Supporting hooks: `features/saved-searches/hooks/useSavedSearches.ts:43-70`; duplicate rename mapping in `app/backend/src/fastapi_app/services/saved_search_service.py:74-91`.

**Reachable scenario:** Create two saved searches with different names, then rename the first to the second's name. The backend returns the documented 409. Separately, confirm deletion during a network/server failure, or after another tab has already deleted that row.

**Expected:** The row or form reports a clear duplicate-name, deletion, or connection error and permits correction/retry.

**Actual and evidence:** The hooks throw on non-success, so React Query records an error. The row reads only `rename.isPending` and `remove.isPending`; it renders neither mutation's error. Rename's success callback never closes the form on 409, leaving the same text and buttons with no explanation. A failed delete keeps the row, and the five-second timer may simply return the button to Delete. The always-mounted empty live region on the list does not receive any mutation message. There is no global mutation error callback in `main.tsx`.

**Root cause:** Mutation failure state stops at the hook/component boundary. The create-search control already has explicit error rendering, but the manage-row operations do not.

**Design evidence:** F005 section 9 expressly requires clear duplicate-name and user-friendly API-error messages. The M3 account design section 5 calls for inline feedback and accessible save/delete feedback.

**Test gap:** The saved-search hooks test error results, while `SavedSearchesPage.test.tsx` checks list failure and successful rename/delete requests. Those layers do not prove that a row communicates an unsuccessful mutation.

**Smallest fix recommendation:** Render row-scoped accessible mutation errors, distinguish 409 on rename, and clear obsolete feedback when retrying/canceling/opening an edit. Preserve the typed name after a failed rename. Test duplicate rename and failed delete through the real component and fetch seam, asserting visible feedback and that no success state is claimed.

**Verification:** Confirmed by complete read of the row render, hook failure paths, backend mapping, and QueryClient setup. No mutation request or database operation was executed.

### E3 — A failed readiness refresh leaves a previously complete item surface enabled

**Severity:** significant (P2, conditional on a readiness endpoint failure after a prior complete answer).  
**Location:** `app/frontend/web/src/features/contracts/hooks/useTaxonomy.ts:79-80` and `app/frontend/web/src/features/contracts/hooks/useContracts.ts:99-103`. Poll/error mechanism: `useTaxonomy.ts:32-59`.

**Reachable scenario:** An open tab first receives `coverage=complete`. A later scheduled readiness poll returns 500 or times out while the list endpoint remains usable. This can coincide with a backend enrichment-version change, when the readiness gate is specifically intended to close until the resweep finishes. The reader changes an item filter or page after the failed probe.

**Expected:** A failed readiness answer degrades live controls to not-ready; newly fetched rows carry false readiness and the existing incomplete-results warning where applicable. Held rows keep their own captured description until their replacement arrives.

**Actual and evidence:** Query caches retain prior successful data on a refetch error. Both readiness consumers inspect only `data?.coverage === 'complete'`, ignoring `isError`/successful status. Thus the failed poll leaves both predicates true, does not change the list query's readiness key, and later list requests continue capturing true. The controls and incomplete-results warning treat the prior success as current for as long as probes fail.

**Root cause:** Presence of cached successful data is treated as success of the latest readiness check. This is distinct from the intended five-minute interval: the interval actually runs, and its failed result is ignored.

**Design evidence:** The F008 decision log's readiness section specifies that an unreachable endpoint degrades to not-ready. `useTaxonomy.ts:69-73` states the same rule. The data-driven gate decision requires an open tab to degrade automatically across later enrichment-version resweeps. No inspected decision accepts keeping the surface ready after an errored refresh.

**Test gap:** `hooks.test.tsx:166-213` covers successful partial-to-complete and complete-to-partial transitions. The timeout test starts cold without cached successful data. Neither reaches a refetch failure with prior complete data.

**Smallest fix recommendation:** Derive readiness from successful query status and complete coverage in both consumers (prefer one shared predicate). Keep a pending ordinary refetch's known answer until it fails, then close the live gate and let the readiness-key mechanism fetch appropriately described replacement rows. Test complete, failed refetch, new list request, and later recovery as one state sequence.

**Verification:** Application source and cache-state reasoning establish the mechanism. After this report was written, the coordinator relayed the holistic hunter's independent query-core probe: a successful complete answer followed by a failed refetch produced status:error with coverage:complete still present. That independently validates the cache-retention premise. This worker did not run that probe, install dependencies, or execute a browser/component reproduction.

## Design concerns

### E4 — Saved-search summaries omit the contract-type restriction and the false blueprint-copy branch

**Location:** `app/frontend/web/src/features/saved-searches/components/SavedSearchesPage.tsx:21-56`.  
**Severity:** minor, nonblocking.

`summarizeSearch` never inspects `contract_type`, and only describes `is_bpc` when true. A courier-only saved search can read “All contracts” in its criteria line; an explicit exclude-copies search reads the same as no copy restriction. Apply preserves these values, so this is not a replay-data-loss bug. The human-readable summary may be intentionally abbreviated, and no inspected spec exhaustively defines it, so this remains a design concern rather than a confirmed functional finding. Consider displaying type selections and the explicit false branch using already available values; no extra API request is needed.

## Rejected candidates and accepted decisions

| ID | Candidate investigated | Disposition and evidence |
|---|---|---|
| E5 | Separate ME/runs/TE families may match different offered items in one contract. | Rejected as a bug. F008 section 3.1 and the ratified range-family decision explicitly choose this. Each family's lower/upper bounds must share one item; different families need not. `contract_service.py:219-250,349-369` follows that contract. |
| E6 | Item-less segment counts stay zero when an offered-item filter is active. | Rejected as a bug. The ratified overnight offered-filter decision preserves those filters on segment entry; zero is the actual destination count. `_segment_counts_and_total` lifts only type and ship flags. |
| E7 | Item-bearing numerals disappear while entering/leaving item-less segments. | Rejected as a bug. This is the accepted mitigation from the August 8 hunt and the sort/count decision; mirror counts are an already-recorded product/API follow-up. `SegmentTabs.tsx:116-164` explicitly suppresses these numerals. |
| E8 | Saved-search Apply can reconcile unsupported segment sorts and the parser drops negative runs bounds. | Not promoted. Sort reconciliation is an explicit F008 URL rule; nonnegative UI bounds are deliberate in `filters.ts:188-211`. API-only negative sentinel searches would expose a broader schema/parser parity question, but this worker found no ordinary UI-produced lost bound and does not reclassify an explicit parser policy as a fresh defect. |
| E9 | Search and type IDs can match requested items as well as offered items. | Existing design question, not a fresh bug claim. The latest backend tests themselves identify offered-only search semantics as still open (`test_contract_filters.py:2806-2813,3075-3087`). No semantics were invented for this audit. |
| E10 | Joined pagination duplicates contract rows, or unknown stored types disappear from totals. | Rejected on source review. The joined path pages grouped IDs with a deterministic contract-ID tie breaker; grouped totals fold unknown types consistently with the row predicate (`contract_service.py:430-519,585-624`). No counterexample was established. |
| E11 | Caps can overshoot under concurrent saved-search creation. | Rejected as a bug for this hunt. M3 section 3 explicitly accepts best-effort count-then-insert caps. Unique names remain backed by the database and a savepoint. |

## Outside-scope findings

None newly confirmed. Existing dependency alerts, deferred route computation, production monitoring, and browser-fixture residuals remain the previously recorded follow-ups. They were not turned into correctness findings here. Security behavior, exploit reproduction, dependency acquisition, and database mutation were outside this worker's authorization.

## Verification limits and testing pitfalls

This was a read-only source audit followed by this report-file write. No application source, test, configuration, dependency, git state, running server, or database was changed by this worker. No tests were run by this worker. The coordinator owns any subsequent runtime validation and report consolidation.

The testing-pitfalls document was reviewed after the hunt as well as during calibration. E1 and E3 warrant state-sequence regressions across independently tested mechanisms; existing TEST-25 already covers why observing real returned/rendered data is essential with caches. E2 needs component-visible error assertions in addition to hook error assertions. No testing-pitfalls file was edited because this worker's write authorization is limited to this report.

Candidate accounting is complete: E1–E3 are source-confirmed bugs with the stated runtime-verification limits; E4 is a design concern; E5–E11 are explicitly rejected or already-accepted/open decisions. The report does not infer bugs from coverage percentages or test omissions.
