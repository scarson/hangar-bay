<!-- ABOUTME: Records isolated mutation failures and successful source-restoration checks. -->
<!-- ABOUTME: Preserves exact edits and test selectors for the frontend coverage continuation. -->

# Frontend coverage mutation verification

**67 of 67 isolated mutations were caught. Every source restoration was followed by a passing targeted test run.**

The [generated mutation manifest](mutation-cases.json) preserves each exact source edit, target test file, and validated runtime selector. Each mutant ran alone. The harness saved a beside-the-source byte snapshot, verified exact replacement counts, restored in `finally`, compared restored bytes, and checked git status after each case. No production edit remains.

A passing three-file baseline contained 174 tests. A selector that matched zero tests stopped the harness and was never counted as a kill. Runtime-expanded quoted labels were resolved against that passing JSON report before resuming. Each successful mutation below produced assertion-level failures, not merely a nonzero process exit.

To reproduce a case, use the unchanged frontend lockfile, apply its manifest edit to the named source file, and run `node node_modules/vitest/vitest.mjs run <test_file> -t <test_pattern>` from `app/frontend/web`; restore source in `finally` and require the same selection to pass.

| Mutation | Failed tests | Restored passes | Failure excerpt |
|---|---:|---:|---|
| sort-membership | 5 | 6 | AssertionError: expected [ 'date_expired', 'date_issued', …(1) ] to deeply equal [ 'date_expired', 'date_issued', …(2) ] |
| blueprint-sort-membership | 3 | 6 | AssertionError: expected [ 'date_expired', 'date_issued', …(3) ] to deeply equal [ 'date_expired', 'date_issued', …(2) ] |
| page-out-of-range-skeleton | 1 | 1 | TestingLibraryElementError: Unable to find an accessible element with the role "status" and name "Loading contracts" |
| default-size-page-count | 1 | 1 | Error: Unable to find an element with the text: Tristan. This could be because the text is broken up by multiple elements. In this case, you can provide a function for yo |
| default-size-pagination | 1 | 1 | Error: Unable to find an element with the text: Page 2 of 2 · 51 contracts. This could be because the text is broken up by multiple elements. In this case, you can provid |
| courier-origin-empty-coverage | 1 | 1 | Error: expect(element).not.toBeInTheDocument() |
| filter-disclosure-glyph | 1 | 1 | Error: expect(element).toHaveTextContent() |
| search-history-replace | 1 | 1 | AssertionError: expected true to be false // Object.is equality |
| minimum-price-history-replace | 1 | 1 | AssertionError: expected true to be false // Object.is equality |
| maximum-price-history-replace | 1 | 1 | AssertionError: expected true to be false // Object.is equality |
| blueprint-history-replace | 6 | 6 | AssertionError: expected true to be false // Object.is equality |
| unknown-segment-title | 1 | 1 | Error: Unable to find role="heading" and name "Unknown Contracts" |
| missing-segment-count-fallback | 1 | 1 | Error: Unable to find role="button" and name '/^Auction 0$/' |
| ships-only-itemless-inflight-counts | 1 | 1 | TestingLibraryElementError: Unable to find an accessible element with the role "button" and name '/^All$/' |
| nonsortable-header-control | 1 | 1 | Error: expect(element).not.toBeInTheDocument() |
| sort-direction-glyph | 1 | 1 | Error: expect(element).toHaveTextContent() |
| refresh-opacity | 1 | 1 | Error: expect(element).toHaveClass("opacity-60") |
| expired-cell-warning | 1 | 1 | Error: expect(element).toHaveClass("text-warn") |
| live-cell-not-warning | 1 | 1 | Error: expect(element).toHaveClass("text-ink-dim") |
| nonpositive-contract-render-guard | 2 | 2 | Error: Unable to find an element with the text: /Contract not found/i. This could be because the text is broken up by multiple elements. In this case, you can provide a f |
| zero-collateral-suppression | 1 | 1 | Error: expect(element).not.toBeInTheDocument() |
| recorded-detail-volume | 1 | 1 | TestingLibraryElementError: Unable to find an element with the text: 12,345 m³. This could be because the text is broken up by multiple elements. In this case, you can pr |
| missing-detail-volume | 1 | 1 | TestingLibraryElementError: Unable to find an element with the text: —. This could be because the text is broken up by multiple elements. In this case, you can provide a  |
| corporation-audience-label | 2 | 2 | TestingLibraryElementError: Unable to find an element with the text: Yes. This could be because the text is broken up by multiple elements. In this case, you can provide  |
| issuer-id-fallback | 1 | 1 | TestingLibraryElementError: Unable to find an element with the text: Character 1. This could be because the text is broken up by multiple elements. In this case, you can  |
| corporation-id-fallback | 1 | 1 | TestingLibraryElementError: Unable to find an element with the text: Corporation 101. This could be because the text is broken up by multiple elements. In this case, you  |
| seller-title-deduplication | 1 | 1 | Error: expect(element).not.toBeInTheDocument() |
| detail-retry-control | 1 | 1 | Error: Unable to find role="heading" and name "Tristan" |
| pagination-empty-clamp | 1 | 1 | TestingLibraryElementError: Unable to find an element with the text: Page 1 of 1 · 0 results. This could be because the text is broken up by multiple elements. In this ca |
| pagination-unit-label | 1 | 1 | TestingLibraryElementError: Unable to find an element with the text: Page 1 of 1 · 0 results. This could be because the text is broken up by multiple elements. In this ca |
| single-blueprint-missing-figure | 1 | 1 | AssertionError: expected [ '10', '0', '8' ] to deeply equal [ '10', '', '8' ] |
| filter-region-no-matches | 1 | 1 | TestingLibraryElementError: Unable to find an element with the text: No region matches “not-a-region”. This could be because the text is broken up by multiple elements. I |
| filter-last-region-uncheck | 1 | 1 | AssertionError: expected { region_ids: [ 10000002 ], …(5) } to not have property "region_ids" |
| filter-min-price-mapping | 1 | 1 | AssertionError: expected { ships_only: true, page: 1, …(4) } to have property "min_price" with value 7 |
| filter-max-price-mapping | 1 | 1 | AssertionError: expected { ships_only: true, page: 1, …(4) } to have property "max_price" with value 8 |
| filter-min-price-clear | 1 | 1 | AssertionError: expected { ships_only: true, page: 1, …(4) } to not have property "min_price" |
| filter-max-price-clear | 1 | 1 | AssertionError: expected { ships_only: true, page: 1, …(4) } to not have property "max_price" |
| filter-max-price-active | 1 | 1 | TestingLibraryElementError: Unable to find an accessible element with the role "button" and name "Clear filters" |
| filter-region-active | 1 | 1 | TestingLibraryElementError: Unable to find an accessible element with the role "button" and name "Clear filters" |
| filter-ships-only-active | 1 | 1 | TestingLibraryElementError: Unable to find an accessible element with the role "button" and name "Clear filters" |
| filter-region-count-chip | 1 | 1 | TestingLibraryElementError: Unable to find an element with the text: 2. This could be because the text is broken up by multiple elements. In this case, you can provide a  |
| taxonomy-selected-count-chip | 1 | 1 | TestingLibraryElementError: Unable to find an element with the text: 2. This could be because the text is broken up by multiple elements. In this case, you can provide a  |
| taxonomy-empty-category-corpus | 1 | 1 | Error: Unable to find an element with the text: No category in the corpus yet. This could be because the text is broken up by multiple elements. In this case, you can pro |
| taxonomy-queryless-empty-groups | 1 | 1 | Error: Unable to find an element with the text: No group in the selected categories. This could be because the text is broken up by multiple elements. In this case, you c |
| taxonomy-null-group-scoping | 1 | 1 | Error: expect(element).not.toBeInTheDocument() |
| taxonomy-null-group-pruning | 1 | 1 | AssertionError: expected { group_id: [ 999 ], …(6) } to not have property "group_id" |
| blueprint-min-runs-clear | 1 | 1 | AssertionError: expected { ships_only: true, page: 1, …(4) } to not have property "min_runs" |
| blueprint-max-runs-clear | 1 | 1 | AssertionError: expected { ships_only: true, page: 1, …(4) } to not have property "max_runs" |
| blueprint-min-me-clear | 1 | 1 | AssertionError: expected { ships_only: true, page: 1, …(4) } to not have property "min_me" |
| blueprint-max-me-clear | 1 | 1 | AssertionError: expected { ships_only: true, page: 1, …(4) } to not have property "max_me" |
| blueprint-min-te-clear | 1 | 1 | AssertionError: expected { ships_only: true, page: 1, …(4) } to not have property "min_te" |
| blueprint-max-te-clear | 1 | 1 | AssertionError: expected { ships_only: true, page: 1, …(4) } to not have property "max_te" |
| blueprint-min-runs-mapping | 1 | 1 | AssertionError: expected { ships_only: true, page: 1, …(4) } to have property "min_runs" with value 9 |
| blueprint-max-runs-mapping | 1 | 1 | AssertionError: expected { ships_only: true, page: 1, …(4) } to have property "max_runs" with value 10 |
| blueprint-min-me-mapping | 1 | 1 | AssertionError: expected { ships_only: true, page: 1, …(4) } to have property "min_me" with value 11 |
| blueprint-max-me-mapping | 1 | 1 | AssertionError: expected { ships_only: true, page: 1, …(4) } to have property "max_me" with value 12 |
| blueprint-min-te-mapping | 1 | 1 | AssertionError: expected { ships_only: true, page: 1, …(4) } to have property "min_te" with value 13 |
| blueprint-max-te-mapping | 1 | 1 | AssertionError: expected { ships_only: true, page: 1, …(4) } to have property "max_te" with value 14 |
| enrichment-category-member | 1 | 1 | Error: Unable to find role="button" and name "Clear filters" |
| offered-item-is-bpc-member | 2 | 2 | Error: Unable to find role="button" and name "Clear filters" |
| enrichment-group-member | 1 | 1 | TestingLibraryElementError: Unable to find an accessible element with the role "button" and name "Clear filters" |
| enrichment-min-runs-member | 1 | 1 | TestingLibraryElementError: Unable to find an accessible element with the role "button" and name "Clear filters" |
| enrichment-max-runs-member | 1 | 1 | TestingLibraryElementError: Unable to find an accessible element with the role "button" and name "Clear filters" |
| enrichment-min-me-member | 1 | 1 | TestingLibraryElementError: Unable to find an accessible element with the role "button" and name "Clear filters" |
| enrichment-max-me-member | 1 | 1 | TestingLibraryElementError: Unable to find an accessible element with the role "button" and name "Clear filters" |
| enrichment-min-te-member | 1 | 1 | TestingLibraryElementError: Unable to find an accessible element with the role "button" and name "Clear filters" |
| enrichment-max-te-member | 1 | 1 | TestingLibraryElementError: Unable to find an accessible element with the role "button" and name "Clear filters" |
