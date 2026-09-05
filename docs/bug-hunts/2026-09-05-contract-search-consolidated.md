<!-- ABOUTME: Consolidates the contract-search bug hunt with source and runtime evidence. -->
<!-- ABOUTME: Reconciles every hunter candidate, testing gap, and unresolved remediation decision. -->

# Contract search bug hunt — consolidated findings

**Date:** 2026-09-05
**Audited source:** `d43da7c9313de7ce19aa9de21242b07949da4364`, freshly fetched `origin/dev` at scope selection.
**Mode:** Full cycle. The surface joins SQL predicates/counts/pagination, URL normalization and history, delayed and cached requests, readiness, and saved-search persistence/replay. These interactions justify independent methods beyond a small-file snapshot.
**Agents:** Four hunters, two independent verifiers and one report reviewer, all `gpt-6-astra`, reasoning effort `high`. The harness permits three active children, so the differential hunter started after the exploratory hunter finished; the other methods overlapped. Cross-validation accounted for all four completed reports.
**Status:** Findings and test-gap analysis complete; remediation decisions below await Sam. No production fix is claimed. The implementation plan and its review have not run.

Scope is defined in the [audit progress and scope record](2026-09-05-contract-search-progress.md). Primary paths are the backend contract/read and saved-search services, routes and schemas, and frontend contracts/saved-searches features. Ingestion writers, authentication internals, dependency maintenance and reward-per-jump work were adjacent context or excluded work.

## Results

Six confirmed bugs: four P2 behavior failures and two P3 feedback/presentation failures. Two decisions affect the remediation, including how to address a confirmed text-boundary bug without making stored searches unreadable. One additional baseline test-fixture issue is recorded separately. No critical or high-severity production outage was established.

| Finding | Severity | Location | Fix scope |
| --- | --- | --- | --- |
| B1 — Back navigation loses a valid page | P2 | `ContractsPage.tsx:159` | Page correction and transition tests |
| B2 — Overlong text is saved but cannot be queried | P2 | `schemas/account.py:25`, `filters.ts:327` | Input/write/read contract; decision required |
| B3 — Failed readiness refresh keeps the surface ready | P2 | `useTaxonomy.ts:80`, `useContracts.ts:100` | Shared readiness rule and state-sequence tests |
| B4 — Rename/delete failures are invisible | P2 | `SavedSearchesPage.tsx:131` | Row feedback and recovery tests |
| B5 — Saved criteria summaries omit active restrictions | P3 | `SavedSearchesPage.tsx:18` | Pure summary and focused tests |
| B6 — Saved-search restrictions produce retry advice | P3 | `useSavedSearches.ts:31`, `SaveSearchControl.tsx:98` | Error detail and useful recovery message |

## Confirmed bugs

### B1. Back navigation loses a valid page

**Consensus:** All four hunters. **Location:** `app/frontend/web/src/features/contracts/components/ContractsPage.tsx:159-165`, composed with `features/contracts/hooks/useContracts.ts:57-72,117,128`.

**Evidence:** In the actual router/component, start at Tristan/page 3 with 200 results, choose Next, enter Rifter and await its 10-result page 1, then Back. Back should restore Tristan/page 3. It instead settles at Tristan/page 1, including the URL. The search debounce keeps Rifter's effective query active for 300 ms, while the page correction compares the restored page against Rifter's one-page total and replaces history. The same mismatch can happen with placeholder data, but this ordinary history sequence does not require cache eviction or a slow response.

**Impact:** A valid shareable/restorable view is overwritten. This exceeds the documented temporary disagreement between live controls and retained rows. **Blast radius:** ContractsPage and its tests; no API/storage change. **Fix approach:** Only correct pagination when the response's captured search agrees with the currently requested search, including page. Recheck before applying a navigation updater. A check of `isPlaceholderData` alone misses the settled query held during debounce. Retain genuine out-of-range correction once matching data arrives.

### B2. Search text can be saved even though the list rejects it

**Consensus:** Holistic and multipass; boundary verifier independently confirmed. **Location:** `app/backend/src/fastapi_app/schemas/contracts.py:351-358` versus `schemas/account.py:25`; frontend `features/contracts/filters.ts:273,327`, `components/FilterRail.tsx:63-70`, and `features/saved-searches/components/SaveSearchControl.tsx:38`.

**Evidence:** The API caps search text at 100 characters. The search input, parser, API serializer and saved serializer admit longer text; the saved model only has a minimum. The executed frontend observation retained 101 characters in both payloads and verified the generated API maximum of 100. Backend `test_contracts.py:243-251` already asserts the intended maximum. The saved service dumps validated parameters into JSON without another text bound, so an otherwise valid creation can persist an unreplayable query. This backend acceptance follows directly from the write path; no live save/database operation was performed.

**Impact:** A normal paste or shared URL produces a generic list failure; Retry repeats it. Saving can make the failure persistent on Apply. **Blast radius:** Frontend input/serialization/replay and backend saved-write validation; generated API artifacts if request schema changes. **Fix approach:** Keep the approved API limit, reject invalid new saves, and give accurate local validation without silently truncating or dropping the search. First resolve Q1: adding the maximum to the shared stored/response model can make existing overlong rows break the entire saved-search list and rename response. No production prevalence is claimed.

### B3. Failed readiness refresh keeps later results marked ready

**Consensus:** Exploratory, holistic and multipass. **Location:** `app/frontend/web/src/features/contracts/hooks/useTaxonomy.ts:79-80` and `hooks/useContracts.ts:99-103,122`.

**Evidence:** After taxonomy succeeds with complete coverage, fail its refresh with HTTP 500 and change an item filter. In the actual hooks/component, taxonomy has `status:error` and retains its complete data; the subsequent list response still captures `itemSurfaceReady:true`. An independent in-memory query-core probe confirmed the retained-data state. Both application consumers check coverage alone.

**Impact:** During an enrichment resweep with a failing taxonomy probe, controls remain available and newly fetched partial results lack the intended indexing warning. Repeated errors can prolong this beyond the ordinary five-minute polling window. **Blast radius:** Both readiness consumers and their state-sequence tests. **Fix approach:** Share a predicate requiring a successful query result and complete coverage. Preserve fetch-time metadata and the readiness key; an ordinary in-flight refetch may use the last successful answer, but an errored refresh must close the gate and recovery must reopen it. Existing code comments and the approved readiness decision already require this behavior.

### B4. Saved-search rename and delete failures are invisible

**Consensus:** Exploratory, holistic and multipass; independent saved-UI verifier confirmed. **Location:** `app/frontend/web/src/features/saved-searches/components/SavedSearchesPage.tsx:105-177`.

**Evidence:** The hooks throw on failed PUT/DELETE, but the row renders neither mutation's error. The real-component observation received a duplicate-name 409, reached mutation error state, retained the attempted name, and rendered no alert. The complete delete branch has the same omission. The list's error state belongs to a separate query; its empty live region cannot announce these failures.

**Impact:** A normal name conflict, failed deletion, or stale-row error gives no explanation or recovery guidance. **Blast radius:** SavedSearchRow and its component tests. **Fix approach:** Show accessible row-scoped errors, distinguish rename conflict, preserve correctable input, and reset stale messages on fresh attempts/cancel/success. F005 error handling and M3 accessibility already require feedback; a new UI architecture or product decision is unnecessary.

### B5. Saved-search summaries omit selected types and exclude-copy filters

**Consensus:** Exploratory, holistic and differential raised a presentation concern; independent cross-validation promotes the narrow omission to a P3 bug. **Location:** `app/frontend/web/src/features/saved-searches/components/SavedSearchesPage.tsx:18-56`.

**Evidence:** Executing the actual summary function produced the identical `All contracts · sorted by date issued desc` for unrestricted, courier-only, auction-only and explicit `is_bpc:false` parameters. The serializer, model and Apply preserve these meaningful restrictions. The visible checkbox emits true/undefined; false is reached through the supported URL/saved state, not simply by unchecking it.

**Impact:** The criteria line fails to identify a saved search's primary type restriction or active exclusion. No storage or replay data loss occurs. Compact summaries need not be unique for every parameter blob; the finding is limited to these omitted locally available criteria. **Blast radius:** Summary function and pure-function tests. **Fix approach:** Name selected contract types and describe explicit false as excluding blueprint copies, not as selecting only originals. No additional lookup or product decision is necessary.

### B6. Saved-search restrictions lose their actionable explanation

**Consensus:** Multipass, confirmed by the boundary verifier and coordinator source inspection; differential identified the price-validation case. **Location:** `app/backend/src/fastapi_app/services/saved_search_service.py:48-52`, `schemas/account.py:26-27`; frontend `features/saved-searches/hooks/useSavedSearches.ts:31-32` and `components/SaveSearchControl.tsx:98-102`.

**Evidence:** The backend returns 400 with a clear per-user limit message. The hook discards the parsed error detail and passes status alone; the form renders only a generic retry instruction. The same form gives generic retry advice when a browse-valid price exceeds the deliberate, tested saved-price ceiling of 1e15. The executed serializer probe preserved `1000000000000001`; the saved schema rejects it. `ApiError`, `extractDetail`, and `raiseApiError` already support error detail, and watchlist creation demonstrates its recovery-message use.

**Impact:** Retry cannot succeed until the user removes a saved search or corrects the unsupported price. **Blast radius:** Saved-create hook/form and focused tests. **Fix approach:** Preserve useful server detail, announce the required recovery, and clearly identify unsupported saved-price bounds. Keep duplicate-name and generic/network cases distinct. The count cap, its best-effort concurrency semantics, and the saved-price ceiling remain unchanged. Existing validation-feedback requirements authorize this correction without a product decision.

## Design decisions requiring Sam

### Q1. Preserve readability of already-saved overlong text

The model used for saved-write validation also validates GET and rename responses. Narrowing it can reject previously accepted stored rows; the [F008 saved-parameter decision](../superpowers/plans/2026-08-06-f008-decision-log.md) explicitly warns about this.

**Recommendation:** Keep existing stored text and permissive reads, impose the 100-character maximum on new creation, and retain invalid text visibly with a local validation message when applied. Users can shorten the term in the contract search and save a replacement. This preserves data and avoids a migration, but keeping stored values readable while narrowing writes is compatibility behavior requiring Sam's explicit approval under AGENTS.md.

**Alternative:** Inventory stored rows first, then choose and review a migration/rollout before narrowing the shared model. No current evidence establishes whether such rows exist. Truncation, deletion and criteria-editing APIs are not authorized defaults. **Decision status:** Asked; no answer received at report writing.

### Saved-price domain — established policy retained

Differential D2 establishes that a finite price just above 1e15 passes browse parsing and both serializers but is rejected by saved validation. The ceiling is deliberate and tested. Saved parameters use JSON, whereas the storage-width rationale directly fits the watchlist's numeric column; this does not authorize removing either guard.

**Disposition:** Preserve the established saved ceiling and clearly explain that restriction when saving under B6, keeping browse semantics unchanged. A common ceiling for browsing and saving, or a different price policy for saved JSON, would change accepted input domains and require a separate product choice. The initial question about those alternatives received no answer; independent report review established that preserving policy and correcting the feedback needs no such decision. Finite-number validation and the watchlist guard remain intact.

### Q3. Define what the Name sort represents

Differential C1 establishes that `contract_service.py:50,600` orders the lowest/highest joined item name by direction, while the shown `primary_label` prefers the first offered ship (`:667-703`). A fitted Rokh can sort before a Rifter because its module name wins; requested items can supply the sort key. Text/type predicates also restrict the joined rows participating in that aggregate (`:273-281,346-347`), so active criteria can change the representative. Existing tests explicitly pin the representative behavior. No inspected specification makes displayed-label sorting an established requirement, so this is not counted as a confirmed bug.

**Recommendation:** Sort by the displayed contract name with one direction-independent key and the existing deterministic contract-ID tie breaker. This aligns the visual column with its ordering, but changes SQL ordering semantics and needs performance and regression checks. **Alternative:** Retain joined-item ordering and describe its meaning clearly in the UI. **Decision status:** Asked; no answer received.

## False positives and already-recorded decisions

No substantive newly alleged defect was dismissed without an explanation. The reconciliation records deliberate semantics, cleared query shapes and prior open concerns separately from confirmed bugs. Existing requested-item search semantics, mirror counts, hidden controls during indexing, category/group composition, auction BPC presentation, missing sort columns, sentinel bounds, liveness/coverage policy, and best-effort caps are not reopened by this audit. Their authority remains the [August 8 consolidated findings](2026-08-08-f008-prerelease-consolidated.md), F008 decisions and M3 design.

## Baseline issue outside the primary product findings

### O1. Six passing tests emit invalid-query-data warnings

The unchanged frontend suite completed 509 tests across 33 files with exit 0, but six cases emitted `Query data cannot be undefined` for notification unread-count queries. Three are in `features/watchlists/components/WatchButton.test.tsx`; three are contract-detail watch-button gate cases in `features/contracts/components/pages.test.tsx`.

**Root cause:** Their broad authenticated fetch responders hand the contract detail fixture to the notification endpoint. `useUnreadCount` returns that body's missing `total`, producing undefined query data. This is a fixture wire-shape failure, not evidence that real notification responses omit total. The normal saved-page fixtures route notifications to a proper pagination envelope and demonstrate the correction.

**Impact:** Test output violates the project's pristine-output requirement and weakens confidence in account-adjacent setup. **Recommendation:** Include the two test-file fixture repairs as supporting remediation scope under Sam's delegated scope choice; return a valid notification envelope and keep unexpected requests visible. No E2E mocks or warning suppression are needed. These six fixture cases were not changed in this audit; the baseline is not reported as pristine.

## Test-gap analysis

| Bug | Why the existing tests missed it | Catch test and pitfall follow-through |
| --- | --- | --- |
| B1 — History page overwrite | Genuine out-of-range correction and debounce/history behavior were tested independently. | Real router: broad page 3 → page 4 → narrower text/page 1 → Back. Assert restored page and actual rows; hold response and debounce transitions independently. Retain cold invalid-page correction. Follow WEB-1 and TEST-5, TEST-25, TEST-30. |
| B2 — Unreplayable overlong text | The list API maximum test exists; save/parser tests exercise the minimum and ordinary terms. | Cross-check 100/101 characters at input, URL, save write and Apply; assert visible validation and whether a request was sent. Include whitespace and non-BMP Unicode to match backend character counting. Verify existing stored rows under Q1's chosen policy. Follow TEST-1, TEST-5 and boundary validation guidance. |
| B3 — Cached complete after error | Readiness tests cover cold failure and successful complete/partial transitions. | Complete → failed refresh → changed item filter → response capture/warning → recovery. Observe data and rendered warning, not fetch count alone. Follow TEST-25 and TEST-29. |
| B4 — Invisible row errors | Hook/backend tests check rejection; page tests check successful mutations and list failure. | Real row: rename 409, delete failure, retained input/row, clear message, successful recovery. Follow TEST-5, TEST-8 and error-message/side-effect guidance. |
| B5 — Missing summary criteria | Pure summary cases cover ranges/taxonomy but not type or false boolean. | Assert single/multiple types and true/false/absent copy state, preserving compact region/taxonomy summaries. Follow the negative-input/absence guidance. |
| B6 — Save restriction detail lost | Backend tests assert count/price limits; frontend only pins duplicate status/feedback. | Return the real 400 count-cap detail and saved-price validation failure at fetch seam; assert meaningful recovery for each. Cover prices at and above 1e15 while preserving browse behavior. Preserve generic failure and failed-mutation invalidation checks. Follow TEST-5 and error-message guidance. |

**Testing-pitfall updates:** TEST-29 requires warm-cache failure sequences; TEST-30 requires request ownership for response-driven navigation. These are specific reusable gaps. Existing error-path and boundary guidance already covers the other findings and is not duplicated.

## Verification evidence and limits

- `npm.cmd ci --no-audit --no-fund` restored the unchanged committed frontend dependency graph; 480 packages installed. No dependency manifest or lockfile changed.
- Baseline `npm.cmd test -- --reporter=dot`: 33 files, 509 tests passed, six unexpected stderr warnings as O1 records. No assertion failure; not a pristine suite result. Runtime 46.14 seconds.
- Four actual frontend observation probes ran with the existing Vitest/React/router setup: Back-page overwrite, rename-error invisibility, complete→failed-readiness→later-list capture, and 101-character payload/API-limit disagreement. Final run: 4/4 passed, clean output, 3.22 seconds.
- The first observation run had three successful observations and one helper failure because a disabled cache entry had no data. The helper was corrected to inspect populated entries and the full four-case observation rerun passed. That failure is not attributed to production code.
- [Exact runtime observation source](2026-09-05-contract-search-runtime-observations.tsx.txt) is archived outside the regression suite. It was executed as `app/frontend/web/src/test/contract-search-audit.test.tsx`. Its assertions deliberately capture defects at the audited revision; they are evidence, not future regression expectations. Remediation must write intended-behavior tests and establish red/green.
- The independent summary verifier executed the actual summary function; the boundary and query verifiers checked source and installed-library behavior. [Saved-UI verification](2026-09-05-contract-search-verify-saved-ui.md) and [boundary verification](2026-09-05-contract-search-verify-boundaries.md) specify their exact limits.
- Backend dependencies were unavailable. No backend suite, production database inventory, live ESI access, database lifecycle, or browser E2E run was performed. Source/schema evidence is explicitly distinguished from executed checks.

## Reconciliation

Before final consolidation, every labelled raw entry was enumerated: exploratory E1–E11; holistic H1–H4; multipass M1–M4 and MC1; differential D1–D2, C1–C2 and R1–R11. Unlabelled concerns/cleared candidates are identified by their own descriptive text in the table. A duplicate retains its confirmed or design disposition through the named target; no finding is discarded for being minor.

| Hunter | Raw finding | Merged into | Disposition |
| --- | --- | --- | --- |
| exploratory | E1 — Back page overwrite | B1 | confirmed bug |
| exploratory | E2 — invisible rename/delete failures | B4 | confirmed bug |
| exploratory | E3 — readiness after failed refresh | B3 | confirmed bug |
| exploratory | E4 — missing type/exclude-copy summary | B5 | confirmed presentation bug after independent verification |
| exploratory | E5 — different items satisfy different range families | — | false positive; ratified per-family semantics |
| exploratory | E6 — offered filters leave item-less counts zero | — | false positive; honest destination counts |
| exploratory | E7 — suppressed item-bearing numerals | — | documented mitigation; mirror counts already tracked |
| exploratory | E8 — sort reconciliation and negative runs normalization | — | documented URL policy |
| exploratory | E9 — requested-side text/type matches | — | prior open design decision, not reopened |
| exploratory | E10 — joined page duplicates or lost unknown totals | — | false positive; grouped IDs and consistent folding |
| exploratory | E11 — concurrent cap overshoot | — | false positive; explicit best-effort policy |
| holistic | H1 — Back page overwrite | B1 | duplicate confirmed bug |
| holistic | H2 — overlong stored search | B2 / Q1 | confirmed bug; remediation decision |
| holistic | H3 — invisible mutation errors | B4 | duplicate confirmed bug |
| holistic | H4 — retained complete readiness | B3 | duplicate confirmed bug |
| holistic | summary omission concern | B5 | duplicate; promoted on independent verification |
| holistic | requested-side search and type joins | — | prior open design decision |
| holistic | suppressed numerals and mirror counts | — | accepted mitigation/prior follow-up |
| holistic | hidden active filters during partial coverage | — | prior UX concern |
| holistic | category/group multi-selection | — | prior design concern |
| holistic | auction copy-badge absence | — | prior presentation concern |
| holistic | volume/collateral sort reconciliation | — | documented reconciliation; prior column decision |
| holistic | negative runs sentinel versus UI | — | documented narrower UI policy |
| holistic | best-effort cap overshoot | — | false positive under approved policy |
| holistic | surviving item filters and honest zeroes | — | ratified filter-retention behavior |
| holistic | independent offered range families | — | ratified per-family behavior |
| holistic | unknown type folding and distinct joined pages | — | source-cleared query shapes |
| holistic | expired detail, regional liveness, observed coverage | — | documented behavior |
| holistic | ingestion cache eviction and mocked 304 handlers | — | outside scope and already tracked |
| multipass | M1 — overlong stored search | B2 / Q1 | duplicate confirmed bug; remediation decision |
| multipass | M2 — invisible mutation failures | B4 | duplicate confirmed bug |
| multipass | M3 — stale-count history rewrite | B1 | duplicate confirmed bug |
| multipass | M4 — ready after failed poll | B3 | duplicate confirmed bug |
| multipass | MC1 — cap detail discarded | B6 | confirmed feedback bug |
| multipass | pass 3 savepoint/refresh/rollback pipeline | — | source-cleared; strict-read risk belongs to Q1 |
| multipass | pass 4 multiple SQL snapshots | — | unconfirmed concern; analogous prior taxonomy decision; no strict-snapshot requirement established |
| multipass | pass 5 contract errors rethrown and identity fallback | — | source-cleared/documented fallback |
| multipass | concurrent creation cap overshoot | — | false positive; accepted best-effort cap |
| multipass | requested-side text/type semantics | — | prior open design decision |
| multipass | separate blueprint range families | — | ratified behavior |
| multipass | false copy filter on item-less contracts | — | correct negated-EXISTS behavior |
| multipass | reconciliation, absent headers, hidden controls, numerals, taxonomy reads | — | prior decisions/concerns, no fresh defect claimed |
| differential | D1 — pagination response ownership | B1 | duplicate confirmed bug |
| differential | D2 — browse/save price ceiling mismatch | B6 | confirmed feedback bug; differing input domains are established policy |
| differential | C1 — sorted item name versus displayed headline | Q3 | design decision |
| differential | C2 — type omitted from saved summary | B5 | duplicate; promoted on independent verification |
| differential | R1 — ordinary parser/API/save round trip | B2 / B6 | limited source-cleared set; overlong text and price exceptions separately accounted |
| differential | R2 — negative runs bound normalization | — | documented policy |
| differential | R3 — item-less flags/counts/filter retention | — | ratified behavior and existing mirror-count limitation |
| differential | R4 — range families, totals, unknown folding | — | source-cleared within one population snapshot |
| differential | R5 — requested-side search | — | prior open design decision |
| differential | R6 — taxonomy multi-select/cascade and hidden controls | — | prior design concerns |
| differential | R7 — offered summaries/detail/ratio | — | source-cleared for documented domain |
| differential | R8 — saved CRUD and best-effort cap | — | source-cleared/accepted semantics |
| differential | R9 — sort normalization and absent columns/badge | Q3 | normalization documented; representative issue stays a design decision |
| differential | R10 — response/pagination ownership | B1 / B3 | duplicate B1; general readiness claim refined by B3's failed-refresh counterexample |
| differential | R11 — summary versus replay | B5 | duplicate presentation bug; replay itself preserved |

## Audit observations and continuation

The principal pattern is agreement within tested functions but disagreement between them over time or across validation boundaries. All four methods found the page-rewrite interaction; three found the warm-cache readiness failure and invisible row errors. Independent verification promoted narrow summary/cap-feedback concerns rather than treating every presentation choice as subjective. Most rejected candidates were already documented intentional behavior, which made reading decision records valuable.

The first three hunter reports and observation source are committed in `74667ca`. The [independent report review](2026-09-05-contract-search-report-review.md) confirmed the evidence and reconciliation; its corrections are incorporated here. Continue with the bug-hunt skill's decision phase, then write the remediation plan and run its required independent review. No implementation plan is represented as reviewed or executable. The unresolved decisions are stored-text compatibility and Name-sort semantics; silence is not approval.
