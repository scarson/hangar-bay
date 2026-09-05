<!-- ABOUTME: Records component-level coverage added for contract filter controls. -->
<!-- ABOUTME: Maps review rows to tests, verification evidence, and deferred mutation checks. -->

# Contract filter control coverage

Status: **DONE** for test authoring and targeted verification. Production-source mutation checks are deliberately deferred to the coordinating agent because other workers are editing shared frontend files concurrently.

The added suite is [`filter-controls.test.tsx`](../../../app/frontend/web/src/features/contracts/components/filter-controls.test.tsx). It renders the real `/contracts` route through TanStack Router and React Query, stubs only `fetch`, and uses the shared [`http.ts`](../../../app/frontend/web/src/test/http.ts) response helpers plus [`renderApp.tsx`](../../../app/frontend/web/src/test/renderApp.tsx). Its fixtures are an honest empty contract-page envelope and minimal taxonomy envelopes; it does not duplicate contract-row fixtures.

## Review-row mapping

| Authoritative review row                                                                        | Added coverage                                                                                                                                                                                                                                                                                                                                                                                                                                                                                  |
| ----------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| N13 — FilterRail empty region search, last-region removal, active-filter gates, and count chips | Asserts the exact “No region matches” result; unchecks the only selected region and proves both router state and the next list request omit `region_ids`; proves `Clear filters` is present when the sole active state is `region_ids`, `max_price`, `category_id`, either boolean value of `is_bpc`, each of the six blueprint bounds, or `ships_only=false`; proves it disappears after that state is cleared; and reads the literal `2` chip from the Region, Category, and Group fieldsets. |
| N14 — TaxonomyFilter empty and nullable taxonomy states                                         | Asserts the complete-but-empty category message; asserts the query-less scoped-group empty message with an empty type-ahead; and serves a real nullable `category_id` group, proving it is visible while unscoped and is both hidden and removed from URL/request state when the category scope narrows.                                                                                                                                                                                        |
| N15 — Numeric bound removal                                                                     | An eight-case control matrix types and clears minimum/maximum price, runs, material efficiency, and time efficiency. Every case asserts the typed value in router state and the list request, then asserts the key is absent from router state and the next list request after clearing. The six blueprint cases also close the control-to-wire mapping gap recorded as correctness finding C8 in the authoritative frontend component review.                                                  |

The `hasActiveFilters` cases cover the review's remaining top-level disjuncts (`max_price`, `region_ids`, and `!ships_only`) plus every previously unpinned member reached through `hasOfferedItemFilters`: `category_id`, both meaningful `is_bpc` values, and all six blueprint bounds. Existing suites cover search, minimum price, contract type, and group ID.

## Verification

Run from `app/frontend/web`:

```text
npm test -- src/features/contracts/components/filter-controls.test.tsx
Test Files  1 passed (1)
Tests       18 passed (18)
```

The final Vitest run emitted no warnings or error output. Targeted ESLint completed with exit code 0 and no output. `npm exec prettier -- --check src/features/contracts/components/filter-controls.test.tsx` reported that all matched files use Prettier formatting.

## Deferred mutation checks

Run each replacement independently after concurrent frontend authoring finishes, restore from a beside-the-source snapshot in `finally`, verify only the named target test fails where practical, then rerun the restored target suite green. These candidates are exact source-text edits against the current files.

- In `FilterRail.tsx`, replace `visibleRegions.length === 0` with `false`. Expected failure: `says when the region type-ahead has no matches`.
- In `FilterRail.tsx`, delete `else next.delete(id)`. Expected failure: `removes the region from the URL and request when the last selection is unchecked`.
- In `FilterRail.tsx`, replace `{ min_price: event.target.value === '' ? undefined : Number(event.target.value) }` with `{ min_price: Number(event.target.value) }`. Expected failure: matrix case `sets and clears min_price through its labelled input`.
- In `FilterRail.tsx`, replace `{ max_price: event.target.value === '' ? undefined : Number(event.target.value) }` with `{ max_price: Number(event.target.value) }`. Expected failure: matrix case `sets and clears max_price through its labelled input`.
- In `FilterRail.tsx`, delete `search.max_price !== undefined ||` from `hasActiveFilters`. Expected failure: the `max_price` matrix case at the post-type `Clear filters` assertion.
- In `FilterRail.tsx`, delete `search.region_ids !== undefined ||` from `hasActiveFilters`. Expected failure: `removes the region from the URL and request when the last selection is unchecked` at the initial `Clear filters` assertion.
- In `FilterRail.tsx`, replace `!search.ships_only` with `false` in `hasActiveFilters`. Expected failure: `offers Clear filters when ships-only is the sole changed setting`.
- In `FilterRail.tsx`, replace `{selectedRegions.size}` with `{1}`. Expected failure: `shows the selected counts in the region, category, and group legends` at the Region chip assertion.
- In `TaxonomyFilter.tsx`, replace `{selectedCount}` with `{1}`. Expected failure: `shows the selected counts in the region, category, and group legends` at the Category and Group chip assertions.
- In `TaxonomyFilter.tsx`, replace `categories.length === 0` with `false`. Expected failure: `states when a complete corpus has no categories`.
- In `TaxonomyFilter.tsx`, replace `query ?` with `true ?` in the empty-group message. Expected failure: `states when the selected categories contain no groups without requiring a query`.
- In `TaxonomyFilter.tsx`, replace `selectedCategories.size === 0 || (categoryId != null && selectedCategories.has(categoryId))` with `selectedCategories.size === 0 || categoryId == null || selectedCategories.has(categoryId)`. Expected failure: `offers a category-less group only while unscoped and prunes it when the scope narrows` at the post-narrow visibility assertion.
- In `TaxonomyFilter.tsx`, replace `.filter((group) => group.category_id != null && next.has(group.category_id))` with `.filter((group) => group.category_id == null || next.has(group.category_id))`. Expected failure: the same nullable-group test at the router and request `group_id` removal assertions.
- In `BlueprintFilter.tsx`, replace `raw === '' ? undefined : Number(raw)` with `Number(raw)`. Expected failure: all six blueprint-bound matrix cases at the clear-state and request-removal assertions.

For the six blueprint control mappings, mutate one member at a time in the `FAMILIES` table: `min_runs` → `max_runs`, `max_runs` → `min_runs`, `min_me` → `max_me`, `max_me` → `min_me`, `min_te` → `max_te`, and `max_te` → `min_te`. The matching matrix case must fail at both its router-state and request-parameter assertions.

For every enrichment-dependent contribution to `hasActiveFilters`, delete one literal at a time from `ENRICHMENT_DEPENDENT_FILTERS` in [`filters.ts`](../../../app/frontend/web/src/features/contracts/filters.ts). The `category_id` sole-filter case, existing `group_id` sole-filter case, and matching six blueprint matrix cases must each fail at their `Clear filters` assertion. Separately remove `'is_bpc'` from `OFFERED_ITEM_FILTERS`; both boolean sole-filter cases must fail. This observes each compound-predicate member directly rather than deriving expectations from the production list.

The bound matrix waits for the latest list request itself to carry the final typed value, then waits for a later request itself to omit the cleared parameter. Call-count increases remain asserted in both directions. This ordering matters for multi-digit values because router state updates before React Query necessarily issues the matching refetch.

No production mutation was executed in this worker. The current worktree also contains changes owned by the column/page workers and the generated route tree; this worker did not edit those files.

## Coordinated verification

The parent completed the isolated mutation round: all 67 campaign mutations were caught and every restored selection passed. The [durable mutation record](mutations.md) and its generated manifest supersede the worker’s scratch manifests and pending-mutation notes. Scratch files are reclaimed with the worktree. The combined changed-file baseline passed all 174 tests.
