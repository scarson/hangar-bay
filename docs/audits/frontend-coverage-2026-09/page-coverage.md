<!-- ABOUTME: Maps the bounded contracts page/detail coverage work to the frontend coverage register. -->
<!-- ABOUTME: Records targeted verification, residual browser scope, and isolated mutations for coordination. -->

# Contracts page and detail coverage

Scope is limited to `app/frontend/web/src/features/contracts/components/pages.test.tsx` and this report. No production source, E2E fixture/spec, shared test helper, register, or git state was changed.

## Register mapping

| Row | Test coverage | Result and scope note |
|---|---|---|
| N1 | `keeps the out-of-range redirect transient state visibly loading` | Pins the automatic correction render through the real router and query stack. A real memory-history blocker holds the effect's `REPLACE` long enough to observe the otherwise one-commit state; no hook or router module is mocked. |
| N2 | `uses the default page size when a defensive response omits size` | Pins both last-page correction and pagination rendering with the 50-row fallback. This is explicitly a defensive impossible-wire fixture: the current API schema requires `size`. |
| N3 | `makes no courier-origin claim when the coverage list is empty` | Pins suppression of the courier coverage sentence when no ingested region exists. |
| N4 | `shows the disclosure glyph that matches the filter rail state` | Pins `+`, `−`, `+` across closed, open, closed transitions alongside `aria-expanded`. |
| N5 | `$label text changes replace history entries` | Parameterizes Search, both price bounds, and all six blueprint bounds through the real controls. Each case asserts its literal URL value and that memory history still cannot go back. Any pushed keystroke creates a back entry and fails the assertion. |
| N6 | `names an unknown-segment deep link and sends its type without ships-only` | Pins heading, document title, rendered row, and request URL for the control-less `unknown` segment. |
| N7 | `renders zero for a defensively missing segment-count key` | Pins the missing-key `0` fallback and its effect on All. This is explicitly a defensive impossible-wire fixture: the current backend zero-fills every enum key. |
| N8 | `suppresses ships-only counts while an item-less segment request is in flight` | Covers the requested ships-only → courier component transition with the old rows/counts held by React Query. The opposite widened → item-less and item-less → item-bearing directions were already covered. Browser duplication remains residual because current AGENTS.md forbids adding E2E mocks. |
| N9 | `keeps nonsortable headers inert and renders the active sort-direction glyph` | Pins the nonsortable Type header's lack of a button plus descending and ascending glyphs on a real sortable header. |
| N10 | `dims held rows only while their replacement request is in flight` | Pins `opacity-60` during a held sort request and its removal after the response lands, while the real prior row stays rendered. |
| N11 | `warns only on an expired list cell` | Pins `text-warn` without `text-ink-dim` on the expired row and the inverse on a live control row. This single two-sided test also closes frontend-logic N-11. |
| N12 | `rejects the non-positive contract id %s before fetching it`; `suppresses zero collateral instead of presenting it as hauler risk`; `renders the $label detail volume explicitly`; `renders For corporation = $expected`; `falls back to issuer and corporation ids when names are absent`; `does not repeat a seller title that equals the primary label`; `retries a failed detail request and renders the recovered contract` | Covers zero and negative IDs, zero collateral, present/null volume, both corporation booleans, both ID fallbacks, title dedupe, and retry recovery after the hook exhausts its initial retry. Existing tests retain the positive collateral, distinct/blank titles, and nonnumeric-ID arms. |
| N16 | `clamps an empty result to one page and uses the supplied unit label` | Renders the real generic Pagination component and pins the zero-total clamp, custom unit label, and both disabled boundaries. |
| Frontend-logic N-10 | `leaves one missing figure blank on a single-copy blueprint row` | Pins a single-copy row with a null material-efficiency figure as `['10', '', '8']`, distinct from the multi-copy and no-copy blank cases. |

## Verification

- `npm test -- src/features/contracts/components/pages.test.tsx` — 1 file, 145 tests passed, 0 failed; clean Vitest output after the final test edit.
- `npx eslint src/features/contracts/components/pages.test.tsx` — exit 0, no output.
- `npx prettier --check src/features/contracts/components/pages.test.tsx` — all matched files use Prettier style.
- `git diff --check -- app/frontend/web/src/features/contracts/components/pages.test.tsx` — exit 0; Git emitted only its configured LF-to-CRLF working-copy notice.

No mutation was run because the parent owns the coordinated mutation round while all workers share production source. The machine-readable cases are in `.cache/frontend-coverage/page-cases.json`.
Its 29 cases parse as JSON and every `old` snippet was read-only validated against the named production source with the declared exact count.

## Suggested isolated mutations

Apply and restore each edit independently, run only the named test, and preserve the source snapshot in a `finally` as required by TEST-12.

| Row | Isolated production mutation | Test expected to fail |
|---|---|---|
| N1 | In `ContractsPage.tsx`, replace the `pageOutOfRange` branch's `<ContractTableSkeleton />` with `null`. | `keeps the out-of-range redirect transient state visibly loading` |
| N2 | In `ContractsPage.tsx`, change the page-count denominator from `(data.size ?? DEFAULT_SIZE)` to `(data.size ?? 1)`; restore, then separately change Pagination's `size` prop from `data.size ?? DEFAULT_SIZE` to `data.size ?? 1`. | `uses the default page size when a defensive response omits size` in both runs |
| N3 | In `ContractsPage.tsx`, remove `&& data.coverage.ingested_region_ids.length > 0` from the courier-origin condition. | `makes no courier-origin claim when the coverage list is empty` |
| N4 | In `ContractsPage.tsx`, replace `{filtersOpen ? '−' : '+'}` with `'+'`. | `shows the disclosure glyph that matches the filter rail state` |
| N5 | In `FilterRail.tsx`, remove `{ replace: true }` independently from Search, minimum price, and maximum price; in `BlueprintFilter.tsx`, remove it from the shared bound updater. | The matching `$label text changes replace history entries` case(s) |
| N6 | In `SegmentTabs.tsx`, change the `unknown` title value to `'Loan Contracts'`. | `names an unknown-segment deep link and sends its type without ships-only` |
| N7 | In `SegmentTabs.tsx`, replace `(counts[segment.type] ?? 0)` with `counts[segment.type]`. | `renders zero for a defensively missing segment-count key` |
| N8 | In `SegmentTabs.tsx`, replace `countsFromItemLess || leavingItemLess` with `countsFromItemLess`. | `suppresses ships-only counts while an item-less segment request is in flight` |
| N9 | In `ContractTable.tsx`, replace `column.sortField ? (` with `true ? (`; restore, then separately swap the `'▲'` and `'▼'` string literals. | `keeps nonsortable headers inert and renders the active sort-direction glyph` in both runs |
| N10 | In `ContractTable.tsx`, replace `isRefreshing ? 'opacity-60' : ''` with `''`. | `dims held rows only while their replacement request is in flight` |
| N11 | In `columns.tsx`, force the expiry-class predicate false; restore, then force it true. | `warns only on an expired list cell` in both runs |
| N12: ID | In `ContractDetailPage.tsx`, remove `contractId <= 0` from the rendered NotFound guard. | `rejects the non-positive contract id %s before fetching it` |
| N12: collateral | Change `data.collateral > 0` to `data.collateral >= 0`. | `suppresses zero collateral instead of presenting it as hauler risk` |
| N12: volume | Replace the present-volume expression with the literal `'—'`; restore, then replace the null arm with `'0 m³'`. | `renders the $label detail volume explicitly`, with the recorded and missing cases failing respectively |
| N12: corporation | Swap the `'Yes'` and `'No'` ternary arms. | `renders For corporation = $expected` |
| N12: identity | Replace the issuer fallback with an empty string; restore, then do the same for the corporation fallback. | `falls back to issuer and corporation ids when names are absent` in both runs |
| N12: title | Remove `data.title.trim() !== data.primary_label` from the subtitle condition. | `does not repeat a seller title that equals the primary label` |
| N12: retry | Replace the Retry button's `onClick={() => refetch()}` with `onClick={() => undefined}`. | `retries a failed detail request and renders the recovered contract` |
| N16 | In `Pagination.tsx`, remove `Math.max(1, ...)`; restore, then replace `{unitLabel}` with the literal `contracts`. | `clamps an empty result to one page and uses the supplied unit label` in both runs |
| Frontend-logic N-10 | In `columns.tsx::blueprintColumn`, replace `value == null ? null : value` with `value ?? 0`. | `leaves one missing figure blank on a single-copy blueprint row` |

## Residuals and concerns

- N8's browser duplication remains open by explicit scope ruling. A real-data browser setup or Sam's explicit exception to the E2E-mock prohibition is required before adding that lane.
- N2 and N7 are defensive branches exercised with response shapes the current backend schema cannot emit. The tests describe that limitation in place so they are not mistaken for integration evidence.
- The `notFound` title predicate's separate `contractId <= 0` clause is not independently observable because the earlier render guard returns the same NotFound page first. The manifest mutates the render guard and does not manufacture an invalid combined mutant to claim otherwise.
- Mutation evidence is pending the parent-coordinated isolated round; the table above gives exact edits and discriminating test names.

## Coordinated verification

The parent completed the isolated mutation round: all 67 campaign mutations were caught and every restored selection passed. The [durable mutation record](mutations.md) and its generated manifest supersede the worker’s scratch manifests and pending-mutation notes. Scratch files are reclaimed with the worktree. The combined changed-file baseline passed all 174 tests.
