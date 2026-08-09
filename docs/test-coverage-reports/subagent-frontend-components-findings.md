# Frontend components + e2e — test coverage review

ABOUTME: Systematic path-level coverage review of the contracts feature components
ABOUTME: (ContractsPage family) and the Playwright e2e layer, incl. four queued prior-review inputs.

Reviewed on branch `claude/pr-147-handoff-beaace` (2026-08-08). All paths are relative to
`app/frontend/web/` unless prefixed. Intent sources: F008 spec §3/§8
(`design/features/F008-Type-Aware-Contract-Browsing.md`), `docs/pitfalls/testing-pitfalls.md`
(TEST-2/3/4/5/6/7/17), and the 2026-08-08 pre-release bug-hunt remediation plan
(`docs/superpowers/plans/2026-08-08-f008-prerelease-bug-hunt-remediation-plan.md`).

Severity vocabulary per task: **security-critical / correctness / nice-to-have**.
Verdict summary: **0 security-critical, 10 correctness, 18 nice-to-have.**

---

## 1. Queued inputs from prior reviews — current status

### O1a — `WirePage` omits `unknown_system_excluded` — **STILL OPEN**

- `e2e/fixtures/contracts.ts:153-160` — `WirePage` carries `total/page/size/items/segment_counts/coverage` and nothing else.
- The real envelope always carries `unknown_system_excluded` (nullable): `src/lib/api/schema.d.ts:618`, pinned backend-side at `app/backend/src/fastapi_app/tests/test_export_openapi.py:36`.
- The fixture file's own header (`e2e/fixtures/contracts.ts:1-8`) claims "feed the app exactly what the backend would send" — the claim is currently false by one field.
- Impact today is latent (no component under `src/features/contracts/` reads the field), but the fixture lane cannot exercise any future consumer, and the drift is exactly what the wire-mirror discipline exists to prevent.
- **Severity: correctness** (test-infrastructure drift, no user-visible bug yet).

### O1b — fixture composition tiebreak `localeCompare` vs Python ordinal — **STILL OPEN**

- Fixture: `e2e/fixtures/contracts.ts:293-298` — `(a.name ?? '').localeCompare(b.name ?? '')`.
- Backend: `app/backend/src/fastapi_app/services/contract_service.py:758-764` — tuple key `(-item_row_count, name is None, name or "")`, i.e. Python code-point comparison.
- `localeCompare` is ICU/locale-collation (case-insensitive-ish, `'a' < 'Z'`); Python ordinal is code-point (`'Z' < 'a'`). They agree only while names are same-case ASCII with distinct leading letters — true of today's `CATEGORY_NAMES` (`e2e/fixtures/contracts.ts:67-73`), so no assertion is currently wrong, but any future category set with mixed case or non-ASCII (EVE has none today in categories, but the map is hand-maintained) silently diverges the fixture's "derives the summaries the same way the service does" contract.
- Cheap fix when taken: replace with the ordinal comparator `(a.name ?? '') < (b.name ?? '') ? -1 : …` or a code-point compare.
- **Severity: correctness** (test-infrastructure; benign on current data by luck, not by construction).

### O2 — item-less/item-bearing partition stated in four places — **PARTIALLY ADDRESSED**

The four statements and their current pinning:

| Location | Form | Pinned? |
|---|---|---|
| `src/features/contracts/filters.ts:58` (`ITEM_LESS_TYPES`) | literal | **Yes** — `src/features/contracts/filters.test.ts:66` |
| `src/features/contracts/filters.ts:66` (`ITEM_BEARING_TYPES`) | literal | **Yes** — `filters.test.ts:67`, and **union = enum** at `filters.test.ts:70` (`[...ITEM_BEARING_TYPES, ...ITEM_LESS_TYPES].sort() === [...CONTRACT_TYPES].sort()`) |
| `app/backend/src/fastapi_app/services/contract_service.py:409-420` | `_ITEMLESS_CONTRACT_TYPES` literal; `_ITEM_BEARING_CONTRACT_TYPES` **derived as the enum complement** | Partition holds **by construction** (complement), no test needed for the union |
| `app/backend/src/fastapi_app/services/background_aggregation.py:720` | `if contract["type"] not in ["item_exchange", "auction"]: continue` — **hard-coded literal**, not `_ITEM_BEARING_CONTRACT_TYPES` | **NO** — no backend test references `_ITEMLESS_CONTRACT_TYPES`/`_ITEM_BEARING_CONTRACT_TYPES` (grep over `app/backend/src/fastapi_app/tests` finds none), and nothing pins the `_fetch_item_rows` literal against the enum |

So: the TypeScript half of the queued gap is now closed (a sixth type fails the build via
`UnmirroredContractTypes` at `filters.ts:49-51` and then fails `filters.test.ts:70` until
classified). The Python half is half-closed: `contract_service` derives its complement, but
**`_fetch_item_rows` still restates the item-bearing set as a literal with no pin** — a sixth
item-bearing contract type would be counted, filtered and columned correctly everywhere else and
*silently never have its items ingested*. Also note there is still no **cross-language** pin: the
TS partition and the Python partition are each internally consistent but nothing compares them
(e.g. an exported constant in the OpenAPI schema, or a wire-level test).

- **Severity: correctness** (residual: `_fetch_item_rows` literal + no cross-language pin).

### PR #156 deferred pin — no e2e fixture assigns `price: null` — **STILL OPEN**

- `e2e/fixtures/contracts.ts:124` types `price: number | null`, but every builder and canned
  dataset assigns a number (`makeContract` default `price: 250_000_000` at line 344; `SEVEN_SHIPS`,
  `BPC_CONTRACTS`, `AUCTION_CONTRACTS`, `COURIER_CONTRACTS` all numeric; grep for `price: null`
  under `e2e/` matches nothing — the only hit is the unrelated `max_price: null` in
  `e2e/fixtures/account.ts:38`).
- Reverting `WireContract.price` to `number` would still typecheck the entire e2e suite, so the
  `number | null` widening is not regression-pinned at this layer.
- The unit layer *does* pin the rendered branch (`pages.test.tsx:339-357`, detail-page bare dash,
  no ISK unit in Economics) — but that test stubs raw JSON, so it would also survive the type
  reversion; it pins the render, not the wire type.
- Cheap fix when taken: one list-row + one detail e2e case built with `makeContract({ price: null })`
  asserting the list cell dash and the detail dash-no-unit.
- **Severity: correctness.**

---

## 2. Per-component branch map (unit/component layer: `pages.test.tsx`, `a11y.test.tsx`, `columns.test.ts`)

Legend: ✔ = directly asserted; **GAP** = no direct assertion anywhere (per rules, "covered
indirectly" is recorded as GAP).

### 2.1 ContractsPage.tsx (`src/features/contracts/components/ContractsPage.tsx`)

| Branch (lines) | Status | Evidence / gap severity |
|---|---|---|
| EmptyResults: item-filtered item-less segment card (40-59) | ✔ | `pages.test.tsx:1805-1822`; negative case `is_bpc=false` `1824-1840`; e2e `taxonomy.spec.ts:170-174` |
| EmptyResults: nothing-ingested + nothing-selected card (61-75) | ✔ | `pages.test.tsx:1293-1308` |
| EmptyResults: uncovered-region heading, singular arm (79-94) | ✔ | `pages.test.tsx:1236-1250`; a11y `a11y.test.tsx:133-142`; e2e `states.spec.ts:118-137` |
| EmptyResults: uncovered-region plural arm (85-92) | ✔ | `pages.test.tsx:1252-1264` |
| EmptyResults: covered set empty inside uncovered card ("No region has been ingested yet") (85-87) | ✔ | `pages.test.tsx:1335-1352` |
| EmptyResults: mixed covered+uncovered selection sentence (90-92) | ✔ | `pages.test.tsx:1323-1333` |
| EmptyResults: ordinary covered-empty "Loosen a price bound" (95-103) | ✔ | `pages.test.tsx:1310-1321`; e2e `states.spec.ts:98-116` |
| sr-only status: count, singular wording (197-199) | ✔ | `pages.test.tsx:164-176` ("1 contract matches", aria-live=polite) |
| sr-only status: zero + no coverage suffix (203-204) | ✔ | `pages.test.tsx:1306-1307` |
| sr-only status: zero + uncovered-selection suffix (205-207) | ✔ | `pages.test.tsx:1266-1279` |
| "Data as of" shown / suppressed on null `as_of` (222-224) | ✔ | `pages.test.tsx:1209-1218` / `1220-1234`; e2e `states.spec.ts:139-149` |
| SegmentTabs mounted only with data (231-233) | ✔ | every segment test waits on data; held-response tests keep tabs mounted (`pages.test.tsx:829-866`) |
| enrichment-filtered incomplete notice (247-251), incl. WEB-1 held-response direction and drop-when-complete | ✔ | `pages.test.tsx:1478-1547` |
| isPending skeleton (253-254) | ✔ | `pages.test.tsx:1758-1789`; e2e `states.spec.ts:65-96` |
| isError alert + Retry (255-264) | ✔ | `pages.test.tsx:232-239`; a11y `165-176`; e2e retry-recovers `states.spec.ts:151-182` |
| pageOutOfRange → redirect to last page (159-165) | ✔ | `pages.test.tsx:282-300`; e2e `pagination.spec.ts:124-144` |
| pageOutOfRange → transient skeleton render (265-267) | **GAP** | never asserted (redirect end-state only). *nice-to-have* |
| `data.size ?? DEFAULT_SIZE` fallback in pageCount (159) | **GAP** | every fixture envelope carries `size`. *nice-to-have* |
| courier origin line shown on courier segment (276-280), incl. empty courier view | ✔ | `pages.test.tsx:1281-1291, 1385-1393`; negative outside courier `1395-1404`; e2e `segments.spec.ts:238-240` |
| courier origin line suppressed when `ingested_region_ids` is empty (276) | **GAP** | the `.length > 0` guard's false arm never rendered. *nice-to-have* |
| Filters disclosure button aria-expanded/aria-controls (172-183) | ✔ (e2e) | `responsive.spec.ts:32-101` (mobile project) — no unit assertion; the `+`/`−` glyph swap (180-182) asserted nowhere. *glyph: nice-to-have* |
| text inputs navigate with `{ replace: true }` (122-128; also FilterRail/BlueprintFilter call sites) | **GAP** | no test anywhere asserts history-entry behavior (per-keystroke back-button walk would regress green). *nice-to-have* |
| `resetFilters` preserves size/sort, drops the rest (132-141) | ✔ | e2e `filters.spec.ts:170-241` (exhaustive param sweep incl. sort-preservation); unit `pages.test.tsx:777-797` |
| `handleSort` flip / DEFAULT_DIRECTION on new field (143-152) | ✔ | e2e `sorting.spec.ts:177-242` |

### 2.2 SegmentTabs.tsx

| Branch (lines) | Status | Evidence / gap severity |
|---|---|---|
| `listTitle`: Ship/All fallback pair (41-45) | ✔ | `pages.test.tsx:123, 63-75` (e2e default-view) |
| `listTitle`: typed titles — item_exchange/auction/courier/loan (28-34) | ✔ | courier `pages.test.tsx:671-672`; loan `971`; auction via `filters.spec` detour |
| `listTitle`: `'Unknown Contracts'` (33) | **GAP** | the `unknown` segment is URL-reachable exactly like `loan`, but no test renders it (loan has a dedicated wire test at `pages.test.tsx:961-979`; unknown has none). *nice-to-have* |
| `segmentPatch`: sort survives / resets by destination column set (75-76) | ✔ | `pages.test.tsx:707-757, 906-928` |
| `segmentPatch`: item-less entry sets `ships_only:false` (77-79) | ✔ | `pages.test.tsx:649-679`; e2e `segments.spec.ts:100-137`; (the belt-and-braces half is documented mutation-unobservable at lines 60-63 — accepted) |
| `segmentPatch`: leaving item-less REMOVES `ships_only` (80-82) | ✔ | `pages.test.tsx:681-705`; e2e `segments.spec.ts:139-168` |
| Numeral suppression — settled item-less selection: All count-less + typed item-bearing count-less + item-less own numeral stays (149-156) | ✔ | `pages.test.tsx:799-810, 812-827`; e2e `segments.spec.ts:80-98, 151-153, 250-253` |
| Numeral suppression — transition direction A (item-less → item-bearing, held response: numerals stay off until new envelope) (109-124) | ✔ (unit only) | `pages.test.tsx:829-866`. **E2E: absent** — no e2e spec holds a response across a segment click; the gate technique exists in `states.spec.ts:24-31` but is not applied here. *nice-to-have (unit pin is strong; e2e duplication low-value)* |
| Numeral suppression — transition direction B (widened → item-less click, live-URL side poisons) (124, `leavingItemLess`) | ✔ (unit only) | `pages.test.tsx:868-904`. E2E absent — same note as above. *nice-to-have* |
| Numeral suppression — ships-only → item-less click (the documented "hidden-though-honest" residual window, comment 110-123) | **GAP** | `pages.test.tsx:868` starts from `ships_only=false`; no test starts the transition from the ships-only default and asserts the in-flight suppression. The accepted residual is documented (D11 / 2026-08-08 bug-hunt) but not pinned, so a regression that *shows* numerals in that window (or breaks suppression generally from this start state) is untested. *nice-to-have* |
| All sums ITEM_BEARING under ships-only / CONTRACT_TYPES when widened (129, 151-153) | ✔ | `pages.test.tsx:617-637, 639-647`; e2e `segments.spec.ts:59-78, 170-181` |
| `counts[segment.type] ?? 0` missing-key fallback (156) | **GAP** | every fixture serves all five keys (deliberately, per `listPage` docs), so the `?? 0` arm never runs. *nice-to-have* |
| aria-pressed active/inactive on plain buttons (162-164) | ✔ | `pages.test.tsx:625-627, 666-669, 974`; a11y `a11y.test.tsx:122-131`; e2e throughout |
| loan/unknown get no control (20-25) | ✔ | `pages.test.tsx:635-636, 972`; e2e `segments.spec.ts:76-77` |

### 2.3 ContractTable.tsx

| Branch (lines) | Status | Evidence / gap severity |
|---|---|---|
| aria-sort ascending/descending/absent, exactly one active (47-53) | ✔ | `pages.test.tsx:752-757, 771-775`; e2e `sorting.spec.ts:105, 127-130, 159-164, 230-234` |
| Sortable header button + glyph (58-69) vs non-sortable span (70-71) | **GAP** (span arm) | sortable arm exercised by every sort click; no negative assertion that unsortable headers (Type, Route, Location…) expose no sort button. The ▲/▼ glyph direction itself is stripped by `headerNames()` (`pages.test.tsx:86-88`) and asserted nowhere (aria-sort carries the a11y contract, glyph is sighted-only). *nice-to-have* |
| Column sets per segment (via `columnsFor`) | ✔ | header-name sweeps `pages.test.tsx:930-959, 1034-1104, 1133-1183`; e2e `segments.spec.ts:183-241`; set invariants `columns.test.ts:16-63` |
| `hiddenClass` responsive column hiding — Location `max-lg:hidden` (columns.tsx:127), Issued `max-sm:hidden` (columns.tsx:151), courier Collateral/Volume `max-lg:hidden` (columns.tsx:280, 288) | **GAP** | asserted **nowhere at any layer**. JSDOM can't do it (fair), but the mobile Playwright project (Pixel 7, 412px) runs every spec and never asserts a hidden column `toBeHidden()` / a kept column `toBeVisible()` — `sorting.spec.ts:102-105` explicitly *works around* the hiding instead of pinning it. The two deliberate keeps ARE pinned: Deadline (`segments.spec.ts:218-223`, both projects) and the blueprint trio (`columns.test.ts:46-52` pins `hiddenClass === undefined`; `items.spec.ts:64-74` renders on both projects). But dropping `max-lg:hidden` from Location, or adding a hidden class to Price/Time-left, ships green. **correctness** |
| `cellClass` function arm (5-8; Expired `text-warn` at columns.tsx:141-143, buyout-less faint at columns.tsx:243-244) | partial | buyout-less styling's *text* pinned (`pages.test.tsx:1058-1069`, e2e `segments.spec.ts:200`); the Expired `text-warn` arm never renders in any test (list rows are always future-dated per TEST-17; the keepPreviousData drift case that can show an expired row is unexercised). *nice-to-have* |
| `isRefreshing` opacity dim (34-36) | **GAP** | never asserted. *nice-to-have* |
| Sticky header intent guard (56) | ✔ | `pages.test.tsx:125-126` (className contains `sticky`) |
| ContractTableSkeleton role/status/name (107-127) | ✔ | `states.spec.ts:76-95`; `pages.test.tsx:1781` |

### 2.4 ContractDetailPage.tsx

| Branch (lines) | Status | Evidence / gap severity |
|---|---|---|
| notFound: non-integer id, no request leaves (124-131) | ✔ | `pages.test.tsx:414-429` |
| notFound: `contractId <= 0` arm (126) | **GAP** | `/contracts/-5` or `/contracts/0` parses to a valid integer and takes a *different* guard arm than NaN; untested. *nice-to-have* |
| notFound: 404 (127, 144) + title | ✔ | `pages.test.tsx:405-412`; e2e `detail.spec.ts:167-182` |
| isPending skeleton (133-142) | ✔ | e2e `states.spec.ts:209-230` |
| isError non-404 alert + Retry (143-157) | ✔ (render) | `states.spec.ts:232-244` asserts alert+button; the detail Retry is never *clicked* to recovery (list retry is, `states.spec.ts:170-181`). *nice-to-have* |
| Price null → bare dash, no unit (189-191) | ✔ (unit) | `pages.test.tsx:339-357`. E2E: **absent** — see queued input 4. *correctness (counted there)* |
| Reward row: rendered when `reward != null && reward > 0`, suppressed otherwise (193-195) | **GAP** | the courier detail test (`pages.test.tsx:548-558`) asserts Collateral only; no test asserts the Reward row renders (COURIER fixture has `reward: 80_000_000` but it is never read back), nor that an exchange contract (no reward key) suppresses the row. A courier's headline pay could disappear or render for `0` and every suite stays green. **correctness** |
| Collateral row: `> 0` render (199-201) ✔ / `=== 0` suppression | ✔ / **GAP** | render `pages.test.tsx:555-557`; suppression (exchange CONTRACT has `collateral: 0`) never asserted. *nice-to-have* |
| Volume row dash on null (202-204) | **GAP** | courier volume renders in the LIST; the detail Volume row (both arms) is never asserted. *nice-to-have* |
| `for_corporation` Yes/No (205-207) | **GAP** | *nice-to-have* |
| Issuer/corp name fallback to `Character ${id}` / `Corporation ${id}` (216-221) | **GAP** | `pages.test.tsx` ROW carries no `issuer_name`, so the fallback renders in every detail test yet is never asserted (and the named arm only via a11y fixture). *nice-to-have* |
| Location label + null start location (222-224) | ✔ | `pages.test.tsx:560-570` |
| Issued/Expires + expiry parenthetical / Expired badge, both arms (171-174, 225-231) | ✔ | `pages.test.tsx:383-403` |
| Last seen shown / row omitted on null (237-239) | ✔ | `pages.test.tsx:463-486`; e2e positive `detail.spec.ts:106-110` |
| Seller-title quoted subtitle: distinct title ✔ / blank ✔ / `title === primary_label` dedupe arm (178-180) | **GAP** (dedupe) | distinct `pages.test.tsx:330`; blank `359-381`; the third arm (courier fixtures hit it silently) never asserted. *nice-to-have* |
| Empty items → "No item data recorded" Contents card (244-252) | **GAP** | the only render of this branch in any suite is incidental (COURIER detail, `items: []`) and never asserted; live-smoke asserts a `Contents` region exists (`live-smoke.spec.ts:63`) against arbitrary data. This is a real, common state (every courier/loan detail). **correctness** |
| Offered/Requested split, each side conditional (77-79, 262-264) | ✔ | `pages.test.tsx:2071-2095`; a11y `105-120`; e2e `detail.spec.ts:93-101, 184-205` |
| Item `Type ${id}` fallback (101) | ✔ | `pages.test.tsx:2097-2111` |
| Ship badge / BPC badge / per-copy terms (103-105) | ✔ | e2e `detail.spec.ts:97-101`; terms `pages.test.tsx:2113-2131`, e2e `detail.spec.ts:207-229` |
| WatchButton gate: `is_included && category === 'ship'` (106-110) | **GAP** | neither the positive render (offered ship shows a watch control) nor the negatives (requested ship / non-ship item shows none) is asserted in `pages.test.tsx`, `a11y.test.tsx`, `detail.spec.ts`, or `watchlist.spec.ts` (which covers the /watchlist page only, per its test list). If the watchlists feature's own unit tests cover the button in isolation, the *gate on this page* is still unpinned. **correctness** |
| BackLink button (history) vs link (cold) (25-44) | ✔ | `pages.test.tsx:431-461, 488-498`; e2e `detail.spec.ts:118-165` incl. negative assertions on the other control's absence |

### 2.5 FilterRail.tsx

| Branch (lines) | Status | Evidence / gap severity |
|---|---|---|
| Search input + MIN_SEARCH_LENGTH hint (60-73) | ✔ | debounce `pages.test.tsx:2134-2194`; gate e2e `filters.spec.ts:26-62` |
| item-less: "Show" scope sentence + Ships-only disabled, is_bpc enabled (75-99) | ✔ | e2e `taxonomy.spec.ts:182-200`; unit sentence `pages.test.tsx:1791-1803` |
| Price min/max set (102-141) | ✔ | e2e `filters.spec.ts:64-86` |
| Price/blueprint bound cleared back to `''` → param removed (115, 133) | **GAP** | inputs are only ever filled, never cleared, in every suite (Clear-filters resets via navigation, not via the input path). *nice-to-have* |
| Region count chip (146-150) | **GAP** | never asserted. *nice-to-have* |
| Region type-ahead narrows (152-160) ✔ / "No region matches" empty message (166-167) | ✔ / **GAP** | e2e `filters.spec.ts:101-105`; empty-message arm untested. *nice-to-have* |
| toggleRegion check→sorted ascending wire (51-56) ✔ / uncheck-to-last → param removed | ✔ / **GAP** | e2e `filters.spec.ts:107-121`; uncheck path untested. *nice-to-have* |
| `hasActiveFilters` disjuncts (42-49) | partial | exercised for search+min_price+segment (e2e `filters.spec.ts:182-212`), `group_id` deep link (`pages.test.tsx:1876-1887`); the remaining disjuncts (`max_price`, `region_ids`, `!ships_only`, each blueprint bound) never individually gate the button. A dropped disjunct = deep-linked filter with no Clear button. *nice-to-have (boilable lake)* |
| itemSurfaceReady gate open/closed + "still indexing" line (192-208) | ✔ | `pages.test.tsx:1430-1547, 1748-1789`; e2e `taxonomy.spec.ts:128-142`, `items.spec.ts:90-104` |
| item-less sentence above the (open) item filters (199-203) | ✔ | `pages.test.tsx:1791-1803`; e2e `taxonomy.spec.ts:196-199` |

### 2.6 TaxonomyFilter.tsx

| Branch (lines) | Status | Evidence / gap severity |
|---|---|---|
| Scoping: empty selection = whole taxonomy / scoped groups (70-76) | ✔ | `pages.test.tsx:1569-1587`; e2e `taxonomy.spec.ts:33-56` |
| toggleCategory prune-in-one-navigation / widen-keeps-all (78-98) | ✔ | `pages.test.tsx:1622-1655`; e2e `taxonomy.spec.ts:102-126` |
| toggleGroup add/remove (100-105) | ✔ | e2e `taxonomy.spec.ts:58-83` |
| Group type-ahead + "No group matches “q”" (74-76, 153-156) | ✔ | `pages.test.tsx:1589-1605` |
| "No group in the selected categories" (query-less empty arm, 155) | **GAP** | only the query arm of the ternary is asserted. *nice-to-have* |
| "No category in the corpus yet" (111-112) | **GAP** | every ready-taxonomy fixture has categories. *nice-to-have* |
| Null-`category_id` group: reachable only unscoped; dropped from `survivingGroups` on narrow (70-71, 92) | **GAP** | `WireTaxonomyGroup.category_id` is nullable (`e2e/fixtures/contracts.ts:167-171`) and the code comments call the case out, but no fixture serves one. *nice-to-have* |
| Live-region scope description, both wordings + count + aria-live (126-141, IdFieldset 33-41) | ✔ | `pages.test.tsx:1657-1694`; a11y described-by resolution `a11y.test.tsx:144-163` |
| Selected-count chips (27-31) | ✔ (via described-by tests' selected states) — chip numeral itself unasserted. *nice-to-have (folded into region chip row above)* |

### 2.7 BlueprintFilter.tsx

| Branch (lines) | Status | Evidence / gap severity |
|---|---|---|
| ME min bound → URL + wire (35-64, family 2) | ✔ | e2e `filters.spec.ts:148-168`; deep-link `pages.test.tsx:1478-1532` |
| **Runs min/max, ME max, TE min/max — the other five bounds** (FAMILIES 13-17) | **GAP** | no suite ever types into or deep-links `min_runs`/`max_runs`/`max_me`/`min_te`/`max_te` through the *controls* (the parser is covered in `filters.test.ts`, the wire in backend tests). `FAMILIES` is data: a swapped key (`max: 'max_me'` on the TE row) would produce a wrong wire param with everything green. The e2e Clear-filters sweep (`filters.spec.ts:237-240`) asserts their *absence* after reset only. **correctness** (five-case lake, minutes to boil) |
| Empty string → `undefined` (bound removal, 30-31) | **GAP** | same fill-only pattern as price. *nice-to-have* |
| sr-only Min/Max labels per family noun (40, 54) | partial | 'Minimum material efficiency' exercised; the other five labels unqueried. (folded into the row above) |

### 2.8 Pagination.tsx

| Branch (lines) | Status | Evidence / gap severity |
|---|---|---|
| Prev disabled on 1 / Next disabled on last (19, 25) | ✔ | e2e `pagination.spec.ts:81-97` |
| Label "Page N of M · T contracts" (22-24) | ✔ | e2e `pagination.spec.ts:56, 139, 158`; boundary walk `29-79` (TEST-4) |
| `Math.max(1, …)` clamp when `total === 0` (16) | **GAP** | unreachable from ContractsPage (EmptyResults replaces the table at `ContractsPage.tsx:281-287`), but the component is generic (`unitLabel` prop, line 8) and any other caller hits the clamp; never asserted. *nice-to-have* |
| `unitLabel` non-default arm (8, 23) | **GAP** | *nice-to-have* |

---

## 3. Per-e2e-spec journey map (desktop + mobile projects unless noted)

`playwright.config.ts:25-55`: `desktop` (1280×800) and `mobile` (Pixel 7, 412px) both run every
spec except `live-smoke`, which runs desktop-shaped only (`live-smoke` + optional
`live-smoke-prod`). Retries 0 throughout (TEST-2).

| Spec | Journeys pinned | Journeys absent (rows) |
|---|---|---|
| `default-view.spec.ts` | root→/contracts redirect; ships-only default wire (`is_ship_contract=true`, PROXY-1 path, page/size/sort defaults); widen toggle drops the param | — |
| `segments.spec.ts` | control set + honest counts; settled numeral suppression (item-bearing count-less while courier active); courier select clears ships-only + URL shape + reload-restores; All restore removes both params; widened All full sum; auction column split + "No buyout"; courier columns + unknown-structure + rate + Deadline + origin statement; shared courier URL | in-flight numeral suppression (both held-response directions — unit-only, `pages.test.tsx:829-904`); `loan`/`unknown` reachable-by-URL journey (unit-only, `pages.test.tsx:961-979`) — *nice-to-have each* |
| `filters.spec.ts` | 3-char search gate incl. never-sent proof; price bounds; region type-ahead + 2-region repeated-key wire; is_bpc; min_me; Clear-filters exhaustive URL sweep + sort preservation; filter resets page to 1 | clearing an individual input back to empty (param removal) — *nice-to-have* |
| `sorting.spec.ts` | default issued-desc; price sort + page reset + server-order render; direction flip; column-switch direction reset; deep-link sort; courier rate sort both directions + segment travels; courier sortless-entry reconcile to date_expired asc | **Deadline (`days_to_complete`) header click — untested in every suite** (only the parser accepts it, `filters.test.ts:189-190`, and the header renders; the header→wire→aria-sort journey for the one column comment-flagged "the server sorts on it so the header must disclose it", `columns.tsx:308-312`, is unpinned) — **correctness**. Buyout and Time-left header clicks e2e-absent (unit covers buyout `pages.test.tsx:1071-1084`; Time-left click covered nowhere as a click, only as reconcile target) — *nice-to-have* |
| `pagination.spec.ts` | 3-page boundary walk, union/no-dup (TEST-4); disabled endpoints; scroll-to-top on page; out-of-range rewrite to last page; middle-page deep link without page-1 fetch | — |
| `states.spec.ts` | held-response loading skeleton; empty card + zero announcement; uncovered-region card; freshness stamp; error alert + retry recovery (retry-exhaustion aware, TEST-7); live-region count update on filter; detail loading; detail error | "No data ingested yet" empty-corpus card (unit-only `pages.test.tsx:1293-1308`); mixed covered/uncovered selection (unit-only `1323-1333`); enrichment "results may be incomplete" notice (unit-only `1478-1547`) — *nice-to-have each* |
| `taxonomy.spec.ts` | category scopes groups + wire; type-ahead + group beside category; shared two-param URL; prune-in-one-navigation; partial-coverage gate closed + message; filter survives item-less round trip + mismatch card; ships-only disabled on item-less | — |
| `items.spec.ts` | three blueprint row states (values / "3 BPCs" link / nothing) on both viewports; gated columns absent under partial; mixed-lot composition line | composition unnamed-category "+N more" fallback (unit-only `pages.test.tsx:2032-2051`) — *nice-to-have* |
| `detail.spec.ts` | row→detail full render (badges, regions, ISK unit, Last seen); history-back button restores filtered URL; cold deep link renders + link control + no stray requests; 404 + back; WTB two-sided split; per-copy terms; document title | **null-price detail (queued input 4)**; expired badge/countdown drop (unit-only `pages.test.tsx:383-403`); Last-seen-null omission (unit-only `476-486`); empty-items Contents card — *counted in §2.4* |
| `responsive.spec.ts` | mobile: disclosure closed by default + hidden single-instance rail; open→filter end-to-end→close; filter survives collapse; desktop: no button + permanent rail; both: row→detail→browser-back | **responsive column visibility (Location/Issued/Collateral/Volume hides at 412px; Price/Time-left keeps)** — the one viewport-sensitive table behavior, unpinned anywhere — **correctness** (counted in §2.3) |
| `live-smoke.spec.ts` | real-proxy 200 + PROXY-1 pathname; announced-total XOR structure; detail round trip + history back; real page-boundary no-dup (SQLA-1 guard) | mobile live-smoke project does not exist (config) — *nice-to-have*; no live structural probe of `segment_counts`/coverage block shape |
| `auth.spec.ts` / `notifications.spec.ts` / `saved-searches.spec.ts` / `watchlist.spec.ts` | header identity (anon login link w/ next, authed portrait+logout, single logout POST, ?sso=denied notice); bell unread count, list + mark-all-read, anon prompt; save-search POST payload minus page, apply, header nav; watchlist anon prompt, add-by-name payload, two-step remove | outside this review's component scope; noted for the journey inventory. WatchButton-on-detail gate belongs to §2.4's GAP, not covered here either |

---

## 4. Findings ledger

### Security-critical — 0

None. The reviewed surface renders server-derived text through React (no `dangerouslySetInnerHTML`
found in the components reviewed), and no auth/secret handling lives in this layer.

### Correctness — 10

| # | Finding | Where |
|---|---|---|
| C1 | O1a: `WirePage` still omits `unknown_system_excluded`; fixture lane's wire-mirror claim is false by one field | `e2e/fixtures/contracts.ts:153-160` vs `src/lib/api/schema.d.ts:618` |
| C2 | O1b: fixture composition tiebreak `localeCompare` vs backend Python ordinal — agrees only over same-case ASCII | `e2e/fixtures/contracts.ts:297` vs `app/backend/src/fastapi_app/services/contract_service.py:758-764` |
| C3 | O2 residual: `_fetch_item_rows` hard-codes `["item_exchange", "auction"]` with no test pinning it to the enum/partition; a sixth item-bearing type would silently never get items ingested. Frontend union now pinned (`filters.test.ts:70`); no cross-language pin exists | `app/backend/src/fastapi_app/services/background_aggregation.py:720` |
| C4 | PR #156 deferral stands: no e2e fixture assigns `price: null`; reverting `WireContract.price` to `number` still typechecks; e2e list/detail null-price journey absent | `e2e/fixtures/contracts.ts:124` |
| C5 | Responsive column visibility (`hiddenClass` — Location `max-lg:hidden`, Issued `max-sm:hidden`, courier Collateral/Volume `max-lg:hidden`) asserted at no layer, despite the mobile project running every spec; only the deliberate keeps (Deadline, blueprint trio) are pinned | `src/features/contracts/columns.tsx:127, 151, 280, 288`; workaround at `e2e/sorting.spec.ts:102-105` |
| C6 | Detail Reward row (`reward != null && reward > 0`) — neither render (courier) nor suppression (zero/absent) is asserted anywhere | `src/features/contracts/components/ContractDetailPage.tsx:193-195` |
| C7 | Detail empty-items "No item data recorded" Contents card never asserted — the standard courier/loan detail state | `ContractDetailPage.tsx:244-252` |
| C8 | BlueprintFilter: five of six bounds (min/max runs, max ME, min/max TE) never exercised through the controls; a swapped key in the `FAMILIES` table ships green | `src/features/contracts/components/BlueprintFilter.tsx:13-17` |
| C9 | Deadline (`days_to_complete`) header sort click untested in unit and e2e — the header discloses a server sort (per its own comment) whose click→wire→aria-sort journey is unpinned | `src/features/contracts/columns.tsx:303-316` |
| C10 | WatchButton gate on detail items (`is_included && category === 'ship'`) — positive and negative arms unasserted in this layer | `ContractDetailPage.tsx:106-110` |

### Nice-to-have — 18

| # | Finding | Where |
|---|---|---|
| N1 | pageOutOfRange transient skeleton arm unasserted | `ContractsPage.tsx:265-267` |
| N2 | `data.size ?? DEFAULT_SIZE` fallback unexercised | `ContractsPage.tsx:159` |
| N3 | Courier origin line suppression when coverage is empty | `ContractsPage.tsx:276` |
| N4 | Filters button `+`/`−` glyph swap unasserted (aria-expanded is pinned) | `ContractsPage.tsx:180-182` |
| N5 | `{ replace: true }` history semantics for text inputs untested (per-keystroke history regression invisible) | `ContractsPage.tsx:122-128` |
| N6 | `'Unknown Contracts'` title / unknown-segment-by-URL journey (loan has one; unknown doesn't) | `SegmentTabs.tsx:33` |
| N7 | `counts[type] ?? 0` missing-key fallback | `SegmentTabs.tsx:156` |
| N8 | ships-only → item-less in-flight suppression window (documented residual) unpinned; e2e has no in-flight numeral tests in either direction | `SegmentTabs.tsx:109-124` |
| N9 | Non-sortable header span arm — no negative sort-button assertion; ▲/▼ glyph direction unasserted | `ContractTable.tsx:58-71` |
| N10 | `isRefreshing` opacity dim | `ContractTable.tsx:34-36` |
| N11 | Expired-row `text-warn` cellClass arm never rendered | `columns.tsx:141-143` |
| N12 | Detail: negative/zero id guard arm; collateral-0 suppression; Volume row both arms; `for_corporation`; issuer/corp id fallbacks; title-dedupe arm; detail Retry never clicked to recovery | `ContractDetailPage.tsx:126, 199-207, 216-221, 178-180, 143-157` |
| N13 | FilterRail: "No region matches" arm; region uncheck-to-removal; input clear-to-removal; remaining `hasActiveFilters` disjuncts; count chips | `FilterRail.tsx:42-49, 115, 133, 146-150, 166-167` |
| N14 | TaxonomyFilter: "No category in the corpus yet"; "No group in the selected categories" (query-less arm); null-`category_id` group scoping | `TaxonomyFilter.tsx:70-71, 92, 111-112, 155` |
| N15 | BlueprintFilter/price empty-string bound removal path | `BlueprintFilter.tsx:30-31`, `FilterRail.tsx:115, 133` |
| N16 | Pagination `total===0` clamp arm and `unitLabel` arm | `Pagination.tsx:8, 16` |
| N17 | E2E gaps that are unit-pinned: no-data-ingested card, mixed region selection, enrichment incomplete notice, unnamed-composition fallback, expired-badge detail, last-seen-null | see §3 states/items/detail rows |
| N18 | No mobile live-smoke project | `playwright.config.ts:36-40` |

---

## 5. Review notes (method + uncertainties)

- **Method.** Read all eight components plus `columns.tsx`/`filters.ts` end-to-end; mapped every
  conditional against `pages.test.tsx` (2,195 lines), `a11y.test.tsx`, `columns.test.ts`,
  `filters.test.ts` (targeted), all 16 e2e specs, both helpers, all three fixture files, and the
  Playwright config. Backend files read only where a queued input required verification
  (`contract_service.py`, `background_aggregation.py`, backend test greps).
- **Boundary with the logic-layer reviewer.** `format.ts`/`filters.ts`/hooks internals
  (`useContracts`, debounce) are the sibling subagent's scope; rows here reference them only where
  a component-layer journey depends on them (e.g. Deadline sort).
- **Uncertainty flagged rather than assumed.** C10 (WatchButton): the watchlists feature may carry
  its own component tests for the button in isolation — I verified only that the *gate on the
  detail page* is unasserted in the files in this review's scope plus `watchlist.spec.ts`.
- **What I'd add with more time.** A pass over `src/features/watchlists`/`saved-searches`
  component tests to close the C10 uncertainty, and a check of whether any Vitest test renders
  `Pagination` outside ContractsPage (would retire N16's clamp row).
- **Almost missed.** The frontend partition pin at `filters.test.ts:70` — the queued O2 wording
  ("no test pinning … in either language") is now stale for TypeScript; only the Python
  `_fetch_item_rows` literal remains unpinned. Report the residual, not the original claim.
