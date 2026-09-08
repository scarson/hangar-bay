<!-- ABOUTME: Differential correctness audit of contract browsing and saved-search state. -->
<!-- ABOUTME: Records paired invariants, verified findings, accepted semantics, and verification limits. -->

# Bug Hunt Report — Differential

## Scope

Audit revision: `d43da7c`. Backend contracts and saved-search API, services, schemas and models; frontend contracts and saved-searches production features and contracts routes. Supporting router/API/debounce code and associated tests are consulted only to resolve paired invariants. No production, config, or test edits; no servers, database operations, external acquisition, or security reproduction.

## Relationships Examined

- **URL parse / request serialization:** URL values accepted as filters must serialize into valid, semantically equivalent contract queries. **Held for examined supported input classes; D2 affects saving.**
- **Browse state / saved-search serialize / server validate / stored replay:** saving a valid browse state preserves its effective filters and sorting; applying resets only pagination plus explicitly ratified parser normalization. **Violated at the D2 price ceiling; otherwise held.**
- **Fetched response / page clamping:** a response can correct only the pagination of the search that produced it, never a different navigation whose response has not arrived. **Violated: D1.**
- **List membership / segment counts:** distinct contract totals and segment counts agree with the list predicates, allowing the documented item-less ships-filter lift. **Held by predicate construction; no database snapshot test performed.**
- **SQL sorting / row summaries:** a named sort and its displayed field must express the documented relationship. **Held for scalar fields; name representative remains C1.**
- **Offered-item classification / list and detail summaries:** copy classification, composition and primary labels agree with offered/requested semantics. **Held.**
- **Taxonomy options / selected filters:** available option data and filter serialization retain the selected criteria under the documented coverage restrictions. **Held under accepted cascade/readiness semantics; existing limitations accounted for below.**

## Bugs

Two findings are confirmed below: one significant pagination-state mismatch and one minor price-validation mismatch.

### D1 — Page correction overwrites a different search restored through browser history

**Location:** `app/frontend/web/src/features/contracts/components/ContractsPage.tsx:159-165`; paired with `app/frontend/web/src/features/contracts/hooks/useContracts.ts:57-72,117,128` and `app/frontend/web/src/lib/useDebouncedValue.ts:6-11`.

**Severity:** significant.

**Invariant violated:** a fetched response may correct only the pagination of the search that produced it. Restoring another valid search must preserve that search's page while its effective query changes.

**Evidence:** `useContracts` deliberately freezes the complete effective search for 300 ms while search text settles, and retains previous responses during query changes. `ContractsPage` nevertheless compares live `search.page` against the held response's `total / size` and issues a replacing navigation. The response already carries `countsSearch`, but correction does not compare it with live search.

**Reachable expected/actual:** Start with a multipage Tristan search, advance from page 3 to page 4, replace the text with Rifter and wait for its 10-result page 1, then go Back. The previous history entry restores Tristan page 3. During debounce, the Rifter response still supplies one page; correction replaces the restored URL with Tristan page 1. Expected: Tristan page 3 remains selected and loads. Actual: both settled UI and URL land on page 1. No result drift or network error is needed. This is persistent state loss, beyond the explicitly accepted temporary chrome/rows mismatch during debounce.

**Verification:** source proof plus independent parent runtime confirmation using the actual `renderApp` in the existing Vitest environment, communicated during this audit. Parent reports four clean observation checks including this navigation sequence; durable observation source: `docs/bug-hunts/2026-09-05-contract-search-runtime-observations.tsx.txt` (parent-authored observation archive). This hunter's separate standalone in-memory JSDOM harness did not produce a valid reproduction; it encountered missing browser globals and Node conditional exports and stopped after three setup attempts. Those attempts are not counted as validation.

**Design evidence:** `PRODUCT.md` principle 2 promises shareable/restorable filters, sorts and pages. Implementation pitfall WEB-1 requires row-describing decisions to use the fetched state. `useContracts.ts:63-69` accepts only temporary visual divergence, not replacing restored URL state. This defect is not among the accepted August 8 consolidated findings.

**History:** blame places the correction in `ba9aaf8c` (July 11), and the effective-search freeze in `e65c6727` (August 8). The correction predates the temporal semantics it must now respect.

**Verified test gap:** `components/pages.test.tsx:283-350` checks cold invalid pages and a same-population pending correction, not back-navigation between different search totals. An identity check only for `isPlaceholderData` is insufficient: debounce keeps the previous query active, so its data can be an ordinary successful result.

**Smallest fix / blast radius:** gate correction on agreement between the response's captured search and live state, including debounce-sensitive text and page. Recheck that agreement at the navigation updater before rewriting a newer state. Scope is the contracts page plus focused transition assertions; retain legitimate cold invalid-page correction. No API or storage change is required.

### D2 — Browse price bounds above the saved-search ceiling cannot be saved

**Location:** `app/frontend/web/src/features/contracts/filters.ts:178,208-211,274-275,328-329`; `app/frontend/web/src/features/saved-searches/components/SaveSearchControl.tsx:14-18,76`; paired with `app/backend/src/fastapi_app/schemas/account.py:13,26-27` and `app/backend/src/fastapi_app/schemas/contracts.py:361-362`.

**Severity:** minor.

**Invariant violated:** a valid browse state exposed by the UI must be accepted by the saved-search serializer/validator pair, or the UI must visibly explain the restriction before offering an unfulfillable save.

**Evidence:** browse parsing accepts every finite nonnegative price. The normal price inputs have a minimum but no maximum (`FilterRail.tsx:115-151`). `toApiQuery` forwards the value, and `ContractFilters` has no ceiling. `toSavedSearchParameters` forwards that same price unchanged, but `SavedSearchParameters` rejects values above 1,000,000,000,000,000. The save failure becomes the generic retry suggestion at `SaveSearchControl.tsx:97-101`; retries cannot fix the unchanged payload.

**Reachable expected/actual:** Set maximum price to `1000000000000001`, a finite exactly representable integer. Browsing accepts the criterion. Save the search with any ordinary unique name. Expected: a supported save, or an explicit bound validation explaining why the criterion cannot be saved. Actual: request-schema rejection and an unhelpful retry message. This does not require a contract priced above the ceiling: a high maximum still matches ordinary contracts.

**Verification:** an in-memory Node probe loaded the actual TypeScript parser, API serializer, and save serializer through TypeScript transpilation without changing files. Both outputs retained `max_price:1000000000000001`. Backend rejection is established by the explicit Pydantic `le=PRICE_CEILING` constraint; no backend request or database action was run.

**Design evidence:** M3 account design §4.5 defines stored filters as `ContractSearch` minus page; §5 names the same effective-query normalization on save as browsing. The server ceiling itself is deliberate and must not be removed casually: the gap is that the browse/save boundary never conveys or enforces it consistently.

**History:** blame attributes the stored ceiling to `576647b3` (July 18). The existing browse fields and save serializer do not implement that constraint. The August 8 accepted/rejected candidates do not record this UI mismatch.

**Verified test gap:** backend `tests/api/test_saved_searches.py:157-176` explicitly checks rejection above the cap and acceptance at the cap. Those correct schema tests do not compare the bound against frontend-generated browse/save payloads. This is not a request to weaken the backend constraint.

**Smallest fix / blast radius:** make the browse/save boundary enforce one documented supported price range and show meaningful validation. Prefer sharing the authoritative maximum through the schema/client boundary rather than duplicating an unrelated number. Any change to accepted browse inputs needs deliberate contract consideration; a narrowly scoped save validation message can prevent the misleading retry loop without changing query semantics. Scope is price validation and save UI, with focused boundary contract assertions.

## Design Concerns

### C1 — Ship-name sorting and the displayed primary label use different representatives

**Location / pair:** `contract_service.py:50,600` orders joined item names by direction-dependent minimum/maximum; `_offered_items` and `_primary_label` at `contract_service.py:667-703` choose the first offered ship, then the first offered named item; `columns.tsx:77,99` displays that primary label beneath a `ship_name` sort header.

**Observed mismatch:** a fitted Rokh with an offered `1MN Afterburner` can precede a single Rifter in ascending name order even though the displayed headlines read Rokh, Rifter. Requested items can also supply the ordering representative while never supplying the headline. Search predicates further constrain which joined item names participate in sorting.

**Disposition:** design concern, not a confirmed fresh bug. The aggregate representative is explicitly documented in source, and `tests/api/test_contract_filters.py:2531-2543` pins directional ordering that is not simply reversed. F002's required sorts are price and dates; neither F002 nor the F008 decisions read in this audit explicitly binds `ship_name` to `primary_label`. Changing the representative is therefore a product/ordering decision, not a justified routine correction. If sorted headlines are the intended promise, select one deterministic headline-equivalent key independent of direction; this touches the SQL ordering contract and requires review. Blame: aggregate choice `3d4e61e2` (July 18), server headline choice `61039868` (August 7).

### C2 — Saved-search summaries do not identify contract-type criteria

**Location / pair:** `SaveSearchControl.tsx:20` serializes `contract_type`; `SavedSearchesPage.tsx:18-55` renders the criteria summary without that field, while apply at `SavedSearchesPage.tsx:122-129` restores the full blob through the parser.

**Disposition:** minor presentation/design concern. Distinct searches restricted to exchange versus auction can have identical summaries apart from their user-given names. The stored/replayed selection is preserved. The M3 design asks for a human-readable criteria summary but does not enumerate a mandatory complete summary field set, so this audit does not promote omission alone to data-loss or round-trip failure. An explicit segment label would improve the summary's identification without changing persistence.

## Candidate Accounting and Cleared Relationships

- **R1 — Parse / API / save round-trip:** held for the supported ordinary fields, including false booleans, zero integer blueprint bounds, scalar/list ID input normalization, contract-type deduplication, all eight F008 taxonomy/range fields, and trimmed search length gating. D2 is the confirmed price-domain mismatch. Page is deliberately absent from saved blobs and returns to the default on apply.
- **R2 — Stored runs sentinel versus frontend normalization:** rejected as a fresh bug. `SavedSearchParameters` and `ContractFilters` allow -1; the frontend deliberately drops all negative blueprint bounds. `filters.ts:186-190` documents that narrower URL contract, and the August 8 consolidated report expressly acknowledges this asymmetry. This is an accepted policy rather than silently newly lost ordinary UI state.
- **R3 — Item-less type / ships flag / segment counts:** held under the ratified semantics. The parser forces ships off only for exclusively item-less selection. Item-level filters survive and may intentionally produce honest zeroes; `is_bpc=false` is the complementary NOT EXISTS branch and remains satisfiable. Segment controls restore ships-only when leaving item-less types, and hide item-bearing numerals under the documented mirror-count limitation. See F008 criteria 1.7–1.9, decision log D11, and August 8 consolidated decisions on counts and filter retention.
- **R4 — Per-family item predicates / result counts:** held by source construction within one population snapshot. Each blueprint family's bounds share one offered-item EXISTS; separate families may match different offered rows. Taxonomy's category/group conjunction shares one offered-item EXISTS. Both counts and fetch paths use the same predicate builders. Counts use distinct contract IDs when a join can multiply rows. Unknown stored type values fold into the unknown count and are included by the matching unknown list predicate.
- **R5 — Text/type search versus offered-only F008 predicates:** not a fresh finding. Requested-side text/type matches and joined-row composition are the August 8 consolidated report's deferred search/type semantics decision. No change was inferred from the recent coverage campaign.
- **R6 — Taxonomy multi-selection / group cascade:** backend same-item category/group conjunction and UI pruning match current code. The case where a selected category contributes no contracts because only another selected category has a selected group is the already recorded August 8 taxonomy semantics concern, not rediscovered as a fix-ready bug. Hidden active controls during partial enrichment are likewise already recorded there.
- **R7 — Summary / detail / classification:** held. Offered items are record-ID ordered; list and detail share `_contract_fields`; composition counts offered item rows rather than quantities; requested items remain separate on detail; blueprint copy flag and filter use offered true-copy membership; one-copy summary carries terms, multi-copy summary carries count only. SQL reward/NULLIF(volume,0) and the Python served ratio both treat absent operands and zero volume as unknown for the documented nonnegative domain.
- **R8 — Saved CRUD / model semantics:** held by source inspection. JSON stores the validated blob, all listed fields serialize through the response model, rename changes only the name, and uniqueness is backed by `(user_id, name)` with savepoint-protected writes. Creation-cap races are an explicitly accepted best-effort policy in M3 §3.5, not an atomicity bug. No database behavior was independently executed.
- **R9 — Sort normalization / column membership:** held under F008 decision log D11. A sort unsupported by the target segment falls back to a visible field. Per-field default direction is shared, including courier expiry ascending. Volume/collateral loss from parser reconciliation and auction BPC-badge omission are existing August 8 presentation decisions. C1 describes the separate, unresolved representative issue.
- **R10 — Response state / pagination:** violated by D1. Other inspected row-shaping values (segment columns, coverage explanation, item-filter explanation and enrichment warning) are captured with query results as intended. The pagination correction is the state-changing exception.
- **R11 — Saved-filter summary / replay:** criteria replay is complete for ordinary UI state; C2 notes that its human summary is not complete. No round-trip data loss was inferred merely from summary brevity.

## Verification Limits and Completion

**Status: DONE_WITH_CONCERNS.** Two findings: D1 significant, D2 minor; two separately labelled design concerns. No implementation was requested or performed. No security finding or exploit reproduction was attempted. No servers, database reads/writes, installs, test edits, or configuration changes were performed by this hunter. Read-only blame was used to check both sides' history; the parent owns all commits.

The supplied latest coverage handoff establishes that the recent campaign changed tests rather than production behavior; this audit does not assign either finding to that campaign. This is a differential audit of relationships, not a coverage review or an exhaustive proof over live data. D1 has parent-reported runtime evidence using the actual test environment. D2 has an executed frontend serializer probe and static backend validation evidence. SQL population agreement and summary arithmetic were checked against source and accepted design semantics without querying a database.

Reviewed the testing-pitfalls guidance after the hunt. No pitfalls file was edited because this assignment authorizes report-only persistence. D1 is a concrete application of existing WEB-1 plus history restoration, and D2 merits a browse/save schema-boundary assertion. These are tied to the findings, not general coverage advice. A remediation test for D1 must cross search populations with different page counts while text debounce is active; checking only an out-of-range cold URL or only placeholder-data state misses the mechanism.
