# Frontend LOGIC layer — systematic test coverage review (2026-08-08)

ABOUTME: Path-by-path coverage map for the contracts frontend logic layer (filters, format,
ABOUTME: columns, regions, hooks, useDebouncedValue, api client) with per-row severity and gap calls.

Reviewer rules applied: every path mapped with line numbers; a path without a dedicated
assertion is **GAP** (component-level assertions in `pages.test.tsx` count as dedicated when
they pin the exact branch, and the covering file:line is named); each parser field and enum
variant is its own row; boundary values checked explicitly. Severity: **SEC** (input-handling
path that could leak/corrupt requests or state), **CORR** (correctness), **NTH** (nice-to-have).

Intent sources consulted: `docs/pitfalls/testing-pitfalls.md` (TEST-2 never weaken, TEST-17
clock-anchored fixtures — the formatter tests correctly inject `now` and stay literal-vs-literal),
`docs/plans/2026-08-08-f008-prerelease-bug-hunt-remediation-plan.md` (Phase 1: B3 integer
guards, B5 per-field default sort direction, B7 dedupe; Phase 2: B4 pluralization, B6 label
comment; Phase 3: B1 segment numerals), and the F008 criteria referenced inline in the source
(1.1, 1.2, 1.7, 1.9, 2.2, 5.3, 6.1, 7.2, 7.3, §8). Note: the prompt named the plan at
`docs/superpowers/plans/…`; in this worktree it lives at `docs/plans/…`.

Files under review (all paths relative to `app/frontend/web/`):

- `src/features/contracts/filters.ts` / `filters.test.ts`
- `src/features/contracts/format.ts` / `format.test.ts`
- `src/features/contracts/columns.tsx` / `columns.test.ts`
- `src/features/contracts/regions.ts` / `regions.test.ts`
- `src/features/contracts/hooks/useContracts.ts`, `useTaxonomy.ts`, `useContract.ts` / `hooks/hooks.test.tsx`
- `src/lib/useDebouncedValue.ts` (no test file exists)
- `src/lib/api/client.ts` / `client.test.ts`
- Component-level pins cited from `src/features/contracts/components/pages.test.tsx`

## Summary counts

- **Security-critical gaps: 0.** Every input-handling path here either drops junk to
  `undefined` (parser), gates it before the wire (`toApiQuery`), or is validated again
  server-side. No path constructs a request or state from unvalidated input in a way that
  could leak or corrupt — the failure mode of every gap below is a wrong display, a wrong
  default, or a 422, not a leak. Escalation considered for the `page` upper bound
  (`Number.MAX_SAFE_INTEGER` passes through to the API, filters.ts:284) and for the trimmed
  search wire value; both are bounded by backend validation and classified CORR.
- **Correctness gaps: 28**
- **Nice-to-have gaps: 13**

---

## 1. `filters.ts` (343 lines) vs `filters.test.ts`

### Constants / enums

| Path | Lines | Coverage | Verdict |
|---|---|---|---|
| `SORT_FIELDS` membership (9 fields) | 6–16 | filters.test.ts:168–178 pins the exact list | Covered |
| `CONTRACT_TYPES` mirrors server enum, all 5 variants | 30–36 | filters.test.ts:59–65 pins membership; `satisfies`/`Exhausted` close both directions at compile time | Covered |
| `ITEM_LESS_TYPES` = courier, loan, unknown | 58 | filters.test.ts:66 | Covered |
| `ITEM_BEARING_TYPES` = item_exchange, auction; partition property | 66 | filters.test.ts:67, 70 (partition of the enum) | Covered |
| `MIN_SEARCH_LENGTH === 3` | 69 | filters.test.ts:286 | Covered |
| `DEFAULT_PAGE`/`DEFAULT_SIZE`/`MAX_SIZE` values | 70–72 | Used as oracles throughout the test file; `MAX_SIZE=100` itself never observed at its boundary (see size rows) | Partial — see size boundary gap |

### `DEFAULT_DIRECTION` per-field fallback (Phase 1 Task 1.2 / bug B5 — added this cycle)

The parser reaches this map on line 289 whenever `sort_direction` is absent/junk. Each field
is its own row per the review rules. Only two of nine are asserted.

| Field → expected fallback | Lines | Coverage | Verdict |
|---|---|---|---|
| `date_issued` → `desc` | 189 | filters.test.ts:36, 207, 266 | Covered |
| `date_expired` → `asc` | 190 | filters.test.ts:259–261 (courier fallback) | Covered |
| `price` → `asc` | 191 | none — no test parses `{sort_by:'price'}` without a direction | **GAP (CORR)** |
| `collateral` → `asc` | 192 | none | **GAP (CORR)** |
| `ship_name` → `asc` | 193 | none | **GAP (CORR)** |
| `volume` → `desc` | 194 | none | **GAP (CORR)** |
| `reward_per_volume` → `desc` | 197 | none (test :183 asserts the *field* is kept with courier, never the direction) | **GAP (CORR)** |
| `days_to_complete` → `desc` | 198 | none (test :189 same — field only) | **GAP (CORR)** |
| `buyout` → `asc` | 199 | none (test :185 same — field only) | **GAP (CORR)** |

Mutation check (thought experiment, per TEST-12): flipping `volume: 'desc'` to `'asc'` in the
map fails **zero** tests today. For a fix that exists *because* B5 was a flat-`desc` bug, seven
of nine map entries being unpinned is the headline parser gap.

### `activeSegment` (105–107)

| Path | Coverage | Verdict |
|---|---|---|
| Exactly one selected type → that type | filters.test.ts:272 (via dedupe test); pages.test.tsx segment suites exercise it end-to-end | Covered |
| `contract_type === undefined` → `undefined` | no assertion anywhere calls `activeSegment` on a no-selection search | **GAP (CORR)** |
| Multi-type selection → `undefined` | no assertion (`?.length === 1` false branch) | **GAP (CORR)** |

### Helper predicates (118–168)

| Path | Lines | Coverage | Verdict |
|---|---|---|---|
| `hasEnrichmentDependentFilters`: any of the 8 keys defined → true; all undefined → false | 129–131 | No unit test. Component pins: pages.test.tsx:1534 ("warns only when a filter that reads the new item columns is in play") asserts min_price does NOT trigger and a taxonomy filter does; :1478 the deep-link warning; :1525 drop-once-enriched | Covered (component-level, both branches pinned) |
| `hasOfferedItemFilters` (adds `is_bpc` to the eight) | 139–143 | Grep finds no caller outside filters.ts and no test importing it. `requiresOfferedItem` does not call it — it uses `hasEnrichmentDependentFilters || is_bpc === true`. **This export appears entirely unused and untested** | **GAP (NTH)** — dead-export check; if a consumer exists it is untested, if none exists it is YAGNI |
| `requiresOfferedItem`: enrichment-dependent branch | 156–158 | pages.test.tsx:1805 (empty item-less segment explained under an item filter) | Covered (component) |
| `requiresOfferedItem`: `is_bpc === true` branch | 157 | pages.test.tsx:1791–1842 suite exercises item-filter-on-item-less explanations | Covered (component) |
| `requiresOfferedItem`: `is_bpc === false` must NOT trigger | 157 | pages.test.tsx:1824 ("does not claim an item-less mismatch for is_bpc=false") — a dedicated assertion of exactly this split | Covered (component) |
| `isItemLessSelection`: undefined → false; all-item-less → true; mixed → false | 165–168 | Composed behavior pinned via parser widening tests (filters.test.ts:85–97, 138–147) and pages.test.tsx:1791+; no direct unit call, but every branch has a behavioral assertion | Covered (composed) |
| `isItemLessSelection` on an empty array → **vacuously true** (`[].every` ⇒ true) | 167 | Unreachable from the parser (`toContractTypes` returns `undefined`, never `[]`), but the function is exported and a future caller handing it a hand-built search hits the wrong answer silently. No test documents the contract | **GAP (NTH)** |

### Parser fields — `parseContractSearch` (244–291)

Each field: junk / valid / absent are separate paths.

| Field & branch | Lines | Coverage | Verdict |
|---|---|---|---|
| `search` valid non-empty string → kept | 268 | filters.test.ts:219, 228 | Covered |
| `search` absent → undefined | 268 | filters.test.ts:17 (defaults) | Covered |
| `search` **empty string** `''` → undefined (`length > 0` guard) | 268 | none — no test parses `{search: ''}` | **GAP (CORR)** |
| `search` **non-string junk** (number/array) → undefined | 268 | none | **GAP (CORR)** |
| `min_price` valid (int, decimal, numeric string, 0) | 269 | filters.test.ts:214–215, 250–252 | Covered |
| `min_price` negative (number and string) → undefined | 269 | filters.test.ts:211, 213 | Covered |
| `min_price`/`max_price` **non-numeric junk** (`'abc'`, `''`, `Infinity`) → undefined | 170–174, 202–205 | tested only through the blueprint-bounds path (:161); never through a price field | **GAP (NTH)** — shared helper, but per-field rule applies |
| `max_price` negative → undefined; valid decimal kept | 270 | filters.test.ts:212, 215, 252 | Covered |
| `region_ids` lone scalar → array; junk entries dropped (string-number kept, `'abc'`, −5 dropped); all-junk → undefined | 271, 220–226 | filters.test.ts:48–54 | Covered |
| `region_ids` **empty array** `[]` → undefined | 221, 225 | none — the `value === undefined ? [] : [value]` vs `Array.isArray` distinction with a literal `[]` input is never exercised for this field | **GAP (CORR)** — boundary named in review scope |
| `region_ids` non-integer (1.5) / zero → dropped | 224 | zero pinned only via `group_id` (:151); 1.5 nowhere | **GAP (NTH)** (folded into the shared-helper row below) |
| `contract_type` valid single / valid array / mixed valid+junk / all junk → undefined | 272, 228–237 | filters.test.ts:73–83 | Covered |
| `contract_type` duplicate values → deduped (Phase 1 Task 1.3 / B7) | 235 | filters.test.ts:269–273 incl. `activeSegment` identity | Covered |
| `contract_type` **empty array** `[]` → undefined | 229, 236 | none | **GAP (CORR)** |
| `category_id` valid scalar/array, junk dropped, all-junk → undefined | 273 | filters.test.ts:149–153 | Covered |
| `category_id` **empty array** → undefined | 220–226 | none | **GAP (CORR)** |
| `group_id` valid/junk incl. 0 dropped | 274 | filters.test.ts:151 | Covered |
| `group_id` **empty array** → undefined | 220–226 | none | **GAP (CORR)** |
| Six blueprint bounds (`min_runs`…`max_te`): negative → undefined, `'abc'` → undefined, 0 kept, `'10'` kept | 275–280 | filters.test.ts:155–165 loops all six | Covered |
| Six blueprint bounds: **non-integer** (2.5, `'2.5'`) → undefined; `'0'` kept (Phase 1 Task 1.1 / B3) | 210–213 | filters.test.ts:239–247 loops all six | Covered |
| `is_bpc` boolean true / false kept | 281 | filters.test.ts:116+127 (true), 130–136 (false) | Covered |
| `is_bpc` absent → undefined | 281 | filters.test.ts:17 | Covered |
| `is_bpc` **non-boolean junk** (`'true'`, 1) → undefined | 281 | none — the only parser field whose junk branch has no test at all | **GAP (CORR)** |
| `ships_only` default true / explicit true / explicit false / string-junk `'false'` → true | 283 | filters.test.ts:40–46 | Covered |
| `ships_only` item-less widening (single, explicit-true override, multi item-less) | 252–253, 283 | filters.test.ts:85–97 | Covered |
| `ships_only` untouched for mixed / item-bearing / junk-only selection | 283 | filters.test.ts:138–147 | Covered |
| Item-level filters preserved through an item-less selection (incl. `is_bpc=false`) | 254–265 | filters.test.ts:99–136 | Covered |
| `page` junk (`'x'`) → DEFAULT_PAGE | 284 | filters.test.ts:198–204 | Covered |
| `page` **bounds**: 0 → fallback, 1 kept (min boundary), negative, non-integer 1.5 → fallback | 215–218, 284 | none — only string junk tested; valid page 3 kept (:223, :232) | **GAP (CORR)** |
| `size` out-of-range high (9999) → DEFAULT_SIZE | 285 | filters.test.ts:200, 205 | Covered |
| `size` **bounds**: exactly `MAX_SIZE` (100) kept, 101 → fallback, 0 → fallback, 1 kept | 285 | none — the exact 100/101 edge is unpinned; a clamp-vs-fallback regression at the boundary is invisible | **GAP (CORR)** |
| `sort_by` junk (`'DROP TABLE'`) → date_issued | 305–307 | filters.test.ts:201, 206 | Covered |
| `reconcileSort`: valid + disclosed by segment → kept (reward_per_volume/courier, buyout/auction, days_to_complete/courier) | 301–312 | filters.test.ts:182–190 | Covered |
| `reconcileSort`: valid but undisclosed, date_issued expressible → date_issued (buyout, no segment) | 311 | filters.test.ts:191 | Covered |
| `reconcileSort`: valid but undisclosed, date_issued NOT expressible → date_expired (ship_name/courier) | 311 | filters.test.ts:192–194 | Covered |
| `reconcileSort` **per multi-type selection**: `contractTypes.length !== 1` → segment undefined → default column set governs (e.g. `buyout` + `['auction','courier']` must reconcile to date_issued) | 308 | none — every reconcile test uses zero or one type | **GAP (CORR)** |
| `sort_direction` valid kept (asc :226/235, explicit desc override :263–264) | 287–289 | Covered |
| `sort_direction` junk → `DEFAULT_DIRECTION[sortBy]` | 289 | filters.test.ts:202, 207 (date_issued only) — per-field rows above | Covered for the branch; per-field gaps counted above |

### `toApiQuery` (319–342)

| Path | Lines | Coverage | Verdict |
|---|---|---|---|
| Search gate: 2 chars → undefined (below boundary) | 322 | filters.test.ts:288 | Covered |
| Search gate: whitespace-padded 2 chars (`'  ab  '`) → undefined (trim before measuring) | 321–322 | filters.test.ts:289 | Covered |
| Search gate: exactly 3 chars → sent (boundary) | 322 | filters.test.ts:290 | Covered |
| Search **trimmed value is what's sent** (`'  abc  '` → `'abc'`, not the raw string) | 321–322 | none — every ≥3 test uses an already-trimmed string, so a regression to `s.search` (raw) passes the suite while sending padded text the backend matches differently | **GAP (CORR)** |
| `ships_only: true` → `is_ship_contract: true`; false → undefined | 336 | filters.test.ts:302–305 | Covered |
| Widened item-less selection → no `is_ship_contract` on the wire | 336 | filters.test.ts:307–314 | Covered |
| Filter pass-throughs (type, taxonomy, blueprint bounds, prices, regions) + pagination/sort always present | 323–340 | filters.test.ts:277–300, 316–341 | Covered |
| `is_bpc` pass-through | 335 | none — the pass-through test omits it | **GAP (NTH)** |
| Junk-dropped field stays absent on the wire | — | filters.test.ts:277–283; client.test.ts:41–50 (undefined params omitted from the URL) | Covered |

---

## 2. `format.ts` (213 lines) vs `format.test.ts`

TEST-17 compliance noted: `timeRemaining` tests inject `now` and assert literal-vs-literal —
the sanctioned pattern; fixtures elsewhere use `daysFromNow()` helpers.

| Path | Lines | Coverage | Verdict |
|---|---|---|---|
| `formatIsk` value → grouped; null → '—' | 30–32 | format.test.ts:91–92 | Covered |
| `formatIsk(undefined)` → '—' | 31 | none (signature accepts it; couriers/auctions call it with possibly-absent fields, and Phase 4 makes `price` nullable) | **GAP (NTH)** |
| `formatIsk(0)` → `'0'` (courier price is genuinely 0) | 31 | none directly (pages.test.tsx courier suites render price 0 rows but never assert the price cell text) | **GAP (NTH)** |
| `formatVolume` null / undefined → '—' | 54 | format.test.ts:353–356 | Covered |
| `formatVolume(0)` → `'0'` (measured zero keeps its numeral) | 55 | format.test.ts:349–350 | Covered |
| `formatVolume` < 0.005 → `'<0.01'` | 55 | format.test.ts:348 | Covered |
| `formatVolume` **exactly 0.005** (boundary: not `<`, so formatted) | 55 | none | **GAP (NTH)** |
| `formatVolume` < 100 → two decimals; float-noise flattening | 56 | format.test.ts:330–331, 337–338 | Covered |
| `formatVolume` **just below 100** (99.99 → `'99.99'`) — threshold's other side | 56 | none (:342 pins exactly 100 → `'100'`; the sub-threshold side is only pinned far away at 0.02–0.2) | **GAP (NTH)** |
| `formatVolume` ≥ 100 → whole, grouped, rounded | 56–57 | format.test.ts:342–344 | Covered |
| `formatRewardPerVolume` decimals kept / whole grouped / null / undefined | 61–63 | format.test.ts:131–136 | Covered |
| `formatDeadline` value / 0 / null / undefined | 66–68 | format.test.ts:171–177 | Covered |
| `formatDate` valid → UTC day; garbage → '—' | 70–73 | format.test.ts:101–102 | Covered |
| `timeRemaining` NaN → '—' | 81 | format.test.ts:51 | Covered |
| `timeRemaining` exact instant + past → 'Expired' (`<=` not `<`) | 82 | format.test.ts:54–59 | Covered |
| `timeRemaining` sub-minute clamp to '1m' | 89 | format.test.ts:62–68 | Covered |
| `timeRemaining` bucket boundaries (59m59s / 1h / 23h59m / 1d / 1d23h) + unit dropping | 83–88 | format.test.ts:71–86 | Covered |
| `contractTypeLabel` all five enum variants (Phase 2 B6 pinned the courier label) | 95–112 | format.test.ts:108–117 — each variant its own assertion | Covered |
| `contractTypeLabel` out-of-map → 'Unknown' | 111 | format.test.ts:119–123 | Covered |
| `routeLabel` both named / null destination / null origin / both null, never the id | 120–131 | format.test.ts:141–166 | Covered |
| `regionNames` 1/2/3-name prose; unknown id keeps `Region <id>`; empty list → `''` | 143–145 | format.test.ts:181–202 | Covered |
| `pluralize` four shapes: count 1; already-plural `/s$/i`; consonant-y → -ies; default +s (Phase 2 Task 2.1 / B4) | 152–156 | format.test.ts:230–253 (Commodities, Accessories, SKINs, Decoys, singular) | Covered |
| `formatComposition` two named + other bucket; row counts not quantities; unnamed → other; volume present; volume null omitted; sub-1 m³ | 171–184 | format.test.ts:215–320 | Covered |
| `formatComposition` **`total_volume === 0`** → appends `'0 m³'` (`!= null` passes 0; formatVolume(0) → '0') | 182 | none — the zero-volume composition branch has no assertion, and the docstring at :180–181 makes a claim about it ("a measured zero is a real reading") that nothing pins | **GAP (CORR)** |
| `formatComposition` **empty categories list** → `''` (or volume-only string) | 172–183 | none — guarded upstream by `total_item_rows > 1` (columns.tsx:69) but the function's own contract is unpinned | **GAP (NTH)** |
| `formatBlueprintTerms` all three / runs-null+ME 0 / all null → '' / singular run | 194–200 | format.test.ts:360–382 | Covered |
| `locationLabel` name / id fallback / both null | 207–212 | format.test.ts:385–392 | Covered |

---

## 3. `columns.tsx` (368 lines) vs `columns.test.ts` (+ pages.test.tsx pins)

| Path | Lines | Coverage | Verdict |
|---|---|---|---|
| `columnsFor('courier')` → courier set (route/reward/collateral/volume/rate/deadline/expires) | 350 | pages.test.tsx:1086–1115 asserts the header list; :1174–1179 again | Covered (component) |
| `columnsFor('auction')` → starting bid + buyout split | 351 | pages.test.tsx:1035–1056 | Covered (component) |
| `columnsFor(undefined)` and `'item_exchange'` → default set | 351 | pages.test.tsx:930 | Covered (component) |
| `columnsFor('loan'/'unknown')` → default set | 351 | columns.test.ts:34–44 pins keys equal closed set; pages.test.tsx:961 (loan by URL), :1995 (no blueprint columns) | Covered |
| Blueprint columns inserted before Location, only when ready AND item-bearing | 352–353, 324–327 | columns.test.ts:29–44 (all 6 segments × both readiness states); pages.test.tsx:1967, 1978, 1995 | Covered |
| Pinned invariant: gated columns add no `sortField` | 17–27 (test) | columns.test.ts:17–27 | Covered |
| Pinned invariant: blueprint columns never breakpoint-hidden | 46–52 (test) | columns.test.ts:46–52 | Covered |
| Pinned invariant: unique keys per set × readiness | 54–63 (test) | columns.test.ts:54–63 | Covered |
| `sortableFieldsFor` **per-segment membership** | 363–367 | Only *consistency* with the closed set is asserted (columns.test.ts:17–27 — both sides derive from `columnsFor`, so deleting `sortField: 'days_to_complete'` from the Deadline column passes it). Membership is partially pinned from the outside: filters.test.ts:182–194 (courier has days_to_complete/reward_per_volume/date_expired, lacks ship_name and date_issued; auction has buyout; default lacks buyout) and pages.test.tsx:707–798, 1071, 1185–1201. Unpinned: default/loan/unknown full membership, courier's full set as a set | **GAP (NTH)** — a direct membership snapshot per segment would make the reconcile oracle mutation-proof |
| `rowContext` computes expiry once + carries readiness | 55–57 | pages.test.tsx:136 (per-row countdowns across buckets) | Covered (component) |
| `labelCell`: composition shown when ready; `+N more` fallback when not; nothing for single-row | 64–94 | pages.test.tsx:196–218 (`+2 more`), 2007–2030 (breakdown when ready, `+3 more` absent), 2032–2050 (fallback while unnamed) | Covered (component) |
| `EXPIRES_COLUMN` cellClass: `text-warn` when the row's countdown reads Expired | 141–143 | none — the class fork has no assertion (list fixtures are clock-anchored live per TEST-17; the detail-page expired badge test :383 is a different code path) | **GAP (NTH)** |
| Buyout cell: null → 'No buyout' + de-emphasized class; value → ISK | 243–245 | pages.test.tsx:1058–1069 (text pinned; class not) | Covered (text) |
| `blueprintColumn`: no summary → blank | 186 | pages.test.tsx:1956 | Covered (component) |
| `blueprintColumn`: single copy → runs/ME/TE values | 199–200 | pages.test.tsx:1930 | Covered (component) |
| `blueprintColumn`: multi-copy → 'N BPCs' link in Runs, ME/TE blank | 187–197 | pages.test.tsx:1942–1953 (`['3 BPCs', '', '']`) | Covered (component) |
| `blueprintColumn`: single copy with a **null figure** → that cell blank (`value == null`) | 199–200 | none at the list level (format.test.ts:366–375 pins the detail formatter, not this cell) | **GAP (NTH)** |

---

## 4. `regions.ts` vs `regions.test.ts`

| Path | Coverage | Verdict |
|---|---|---|
| The Forge pinned to 10000002 | regions.test.ts:5–7 | Covered |
| Sorted by name; k-space only (id < 11000000) | regions.test.ts:9–13 | Covered |
| **Id uniqueness** (a duplicated id would silently shadow a map entry in format.ts:28) | none | **GAP (NTH)** |

Generated file; deep content assertions are deliberately out of scope (regeneration script owns it).

---

## 5. Hooks — `useContracts.ts`, `useTaxonomy.ts`, `useContract.ts` vs `hooks.test.tsx` (+ pages.test.tsx)

### The debounce + freeze machinery (added this week)

| Path | Lines | Coverage | Verdict |
|---|---|---|---|
| Debounced search: one request per typed word, not per keystroke | useContracts.ts:49–65 | pages.test.tsx:2137–2154 | Covered (component) |
| Whole-query freeze while unsettled: keystroke's page-1 reset does not fire under the OLD text | 62–64 | pages.test.tsx:2156–2182 (exactly one settled request, `search=raven&page=1`) | Covered (component) |
| Cold-load initialization: deep-linked search rides request one, no debounce delay | useDebouncedValue.ts:6; useContracts.ts:49 | pages.test.tsx:2184–2193 | Covered (component) |
| Settled → unsettled → settled transition updates `lastSettled` (adjust-state-during-render) | 62–64 | exercised implicitly by both debounce tests; no assertion observes `lastSettled` staleness directly | Covered (composed) |
| **Non-keystroke control click mid-word folds into the settled request** (the comment's "a sort click mid-word … instead of doubling it", :57–61) | 62–64 | none — both freeze tests change params only via the keystroke's own navigation; an independent sort/segment/Clear click during the 300 ms window has no test | **GAP (CORR)** |
| `sameSearch` scalar branch (Object.is equality/inequality) | 23–35 | never tested directly (module-private, not exported); only survives as "the page doesn't infinite-loop" | **GAP (CORR)** |
| `sameSearch` **array branches**: length mismatch, elementwise mismatch, equal arrays | 28–29 | none — no test varies `region_ids`/`contract_type`/`category_id`/`group_id` mid-debounce; a regression to reference equality (the exact bug the value-comparison comment :53–56 warns about, → render loop) is caught by nothing dedicated | **GAP (CORR)** |
| `sameSearch` **NaN branch** (`Object.is(NaN, NaN)` → true, unlike `===`) | 29, 31 | none — defensive today (the parser strips NaN) but the function's stated contract; one `Object.is` → `===` regression flips it to a permanent not-same → `setLastSettled` on every render | **GAP (CORR)** |
| `sameSearch` array-vs-scalar / array-vs-undefined mixed types → not same | 28–31 | none | folded into the array-branches row above |
| `toApiQuery`/`activeSegment`/predicates computed from **effectiveSearch** (not live search) | 65–71 | pages.test.tsx:2156–2182 pins `toApiQuery` reading the frozen search; the derived predicate values under freeze are untested but share the single `effectiveSearch` binding | Covered (composed) |
| `useDebouncedValue` as a unit: trailing edge fires after delayMs; **timer reset on rapid change**; cleanup on unmount (no set-state-after-unmount); delayMs change | useDebouncedValue.ts:5–12 | **no test file exists for this new module** — coalescing is pinned once at integration level (pages.test.tsx:2137), reset/cleanup/delay-change never | **GAP (CORR)** (reset behavior) + **GAP (NTH)** (unmount cleanup, delayMs change) |

### Readiness / capture machinery

| Path | Lines | Coverage | Verdict |
|---|---|---|---|
| Fetch page + expose data; taxonomy request precedes list (enabled-gate ordering) | 94–121 | hooks.test.tsx:68–80 | Covered |
| Sub-3-char search never on the wire (hook level) | 65 | hooks.test.tsx:82–93 | Covered |
| Server error → isError | 96–98 | hooks.test.tsx:95–101 | Covered |
| Cold load costs ONE list request (readiness in key + enabled gate) | 95, 119 | hooks.test.tsx:165–185 | Covered |
| Readiness flip → new list query, refetch | 95 | hooks.test.tsx:180–184 | Covered |
| In-flight readiness change never lands under the stale value | 95–115 | hooks.test.tsx:187–211 | Covered |
| `itemSurfaceReady` captured at fetch time | 114 | hooks.test.tsx:178, 183, 210; pages.test.tsx:1696 (no blueprint columns over pre-enrichment rows) | Covered |
| `enrichmentFiltered` capture travels with rows (WEB-1) | 67, 112 | pages.test.tsx:1489–1523 ("keeps warning about the rows on screen while an unfiltered page loads over them") | Covered (component) |
| `itemFilteredItemLessSegment` capture | 70–71, 113 | pages.test.tsx:1791–1854 suite incl. the is_bpc=false negative | Covered (component) |
| `segment` capture | 66, 110 | pages.test.tsx:1133 (rows described with their own columns while next segment loads) | Covered (component) |
| `regionIds` capture (`?? []`) | 111 | pages.test.tsx:1354 (result described while next region loads); the `?? []` default via :1293–1335 empty-coverage suites | Covered (component) |
| `countsSearch` capture (Phase 3 / B1 numerals) | 109 | pages.test.tsx:799–905 (numerals held until the segment's own response lands, dropped when leaving item-less) | Covered (component) |
| `keepPreviousData` placeholder behavior | 120 | pages.test.tsx:1133, 1354, 1489 | Covered (component) |
| `enabled: readinessKnown` — error counts as an answer, list unblocks | 93, 119 | hooks.test.tsx:214–258; pages.test.tsx:1458, 1758 | Covered |

### `useTaxonomy` (33–81)

| Path | Lines | Coverage | Verdict |
|---|---|---|---|
| 5s abort on an unanswered probe; bound holds under production retry:1 client | 39–48 | hooks.test.tsx:214–258 (fake timers; also pins `retry: false` — a retry would break the 6 s bound) | Covered |
| Error → ApiError on undefined data | 44 | hooks.test.tsx via the timeout path; pages.test.tsx:1458 (unreachable endpoint degrades to still-indexing, no retry control) | Covered |
| **`refetchInterval: READINESS_POLL_MS` actually re-polls** — the mechanism behind D1's "degrades on its own" (docstring :7–17 says `staleTime` alone would NOT do it) | 54 | none — both readiness-flip tests drive `queryClient.refetchQueries` by hand, bypassing the interval. Deleting `refetchInterval` fails zero tests; the exact bug the docstring documents (a focused tab reporting `complete` for ~80 minutes across a resweep) comes back silently | **GAP (CORR)** |
| `staleTime: READINESS_POLL_MS` | 53 | none (subsumed by the row above — the pair is the mechanism) | **GAP (NTH)** |
| `useItemSurfaceReady`: complete → true; partial/error/loading → false | 79–81 | pages.test.tsx:1440–1458 (rail closed while enriching, open when complete, closed on unreachable endpoint) | Covered (component) |

### `useContract` (4–18)

| Path | Lines | Coverage | Verdict |
|---|---|---|---|
| Fetch by id, success | 10–16 | hooks.test.tsx:105–113 | Covered |
| 404 → no retry (exactly one call) | 8–9 | hooks.test.tsx:115–122 | Covered |
| **Non-404 error retried exactly once** (`failureCount < 1`) | 8–9 | none — no test issues a 500 and counts two calls; TEST-7 makes this policy load-bearing for every error-state test built on it | **GAP (CORR)** |
| `enabled` gate: non-integer / non-positive id issues no request | 7 | pages.test.tsx:414–429 ("not-found for a non-numeric id without issuing a request") | Covered (component) |

---

## 6. `src/lib/api/client.ts` vs `client.test.ts` (+ hook suites)

| Path | Lines | Coverage | Verdict |
|---|---|---|---|
| Repeated array param serialization | 68–71 | client.test.ts:21–30; pages.test.tsx:257 (end-to-end) | Covered |
| Trailing-slash path under /api/v1 (PROXY-1) | 57–63 | client.test.ts:32–39 | Covered |
| Undefined params omitted from URL | — | client.test.ts:41–50 | Covered |
| `ApiError` status/message/detail/absent-detail | 19–32 | client.test.ts:53–71 | Covered |
| `extractDetail` string / 422-array / missing / non-object | 37–43 | client.test.ts:73–84 | Covered |
| `raiseApiError` throws with status + detail | 50–55 | client.test.ts:86–98 | Covered |
| `raiseApiError` 401 → invalidates `['auth','me']` | 51–53 | useWatchlist.test.tsx:58, 91; parallel assertions in useSavedSearches/useNotifications/useLogout suites | Covered |
| `raiseApiError` **non-401 leaves `['auth','me']` alone** (the negative) | 51–53 | client.test.ts:86–98 throws a 400 but never asserts the cache was untouched | **GAP (NTH)** |
| `baseUrl` `location` fallback for non-DOM environments | 69 | untested; trivial ternary exercised implicitly by every jsdom test | Not counted |

---

## Gap register

### Security-critical (0)

None. See summary rationale.

### Correctness (28)

| # | Gap | Where |
|---|---|---|
| 1–7 | `DEFAULT_DIRECTION` fallback unasserted for `price`, `collateral`, `ship_name`, `volume`, `reward_per_volume`, `days_to_complete`, `buyout` (7 rows; Phase 1 Task 1.2 was added precisely because this was wrong) | filters.ts:188–200, 289 |
| 8 | `search: ''` → undefined branch untested | filters.ts:268 |
| 9 | `search` non-string junk → undefined untested | filters.ts:268 |
| 10 | `is_bpc` non-boolean junk → undefined untested (only parser field with zero junk coverage) | filters.ts:281 |
| 11 | `page` bounds: 0 / negative / non-integer → DEFAULT_PAGE; min boundary 1 kept | filters.ts:284, 215–218 |
| 12 | `size` bounds: exactly MAX_SIZE=100 kept, 101 → fallback, 0 → fallback, 1 kept | filters.ts:285 |
| 13 | `region_ids: []` → undefined untested | filters.ts:220–226, 271 |
| 14 | `category_id: []` → undefined untested | filters.ts:273 |
| 15 | `group_id: []` → undefined untested | filters.ts:274 |
| 16 | `contract_type: []` → undefined untested | filters.ts:228–237 |
| 17 | `activeSegment` no-selection → undefined branch unpinned | filters.ts:105–107 |
| 18 | `activeSegment` multi-selection → undefined branch unpinned | filters.ts:105–107 |
| 19 | `reconcileSort` with a multi-type selection (segment undefined, widened sort must reconcile away) untested | filters.ts:308 |
| 20 | `toApiQuery` sends the **trimmed** ≥3-char search value — regression to raw passes today's suite | filters.ts:321–322 |
| 21 | `formatComposition` with `total_volume === 0` → `'0 m³'` branch unpinned despite its docstring claim | format.ts:182 |
| 22 | `sameSearch` scalar Object.is branch — zero direct tests (module-private) | useContracts.ts:23–35 |
| 23 | `sameSearch` array branches (length / element mismatch / equality; array-vs-scalar) — no test varies a list param mid-debounce; reference-equality regression → render loop caught by nothing | useContracts.ts:28–31 |
| 24 | `sameSearch` NaN branch (`Object.is` semantics) unpinned | useContracts.ts:29, 31 |
| 25 | `useDebouncedValue` has **no test file**: timer-reset-on-change (continuous typing extends the window) has no dedicated assertion at any level | src/lib/useDebouncedValue.ts:7–10 |
| 26 | Independent control click (sort/segment/Clear) during the debounce window folding into the settled request — a documented behavior (useContracts.ts:57–61) with no test | useContracts.ts:62–64 |
| 27 | `useTaxonomy` `refetchInterval` re-poll — the D1 "degrades on its own" mechanism — untested; deleting it fails nothing | useTaxonomy.ts:54 |
| 28 | `useContract` non-404 error retried exactly once (`failureCount < 1`) untested | useContract.ts:8–9 |

### Nice-to-have (13)

| # | Gap | Where |
|---|---|---|
| 1 | `hasOfferedItemFilters` appears unused and untested (dead export or missing consumer test) | filters.ts:139–143 |
| 2 | `isItemLessSelection([])` vacuous-true contract undocumented by any test | filters.ts:167 |
| 3 | Price fields' non-numeric junk (`'abc'`, `''`, Infinity) only tested via the blueprint-bounds path | filters.ts:170–174, 269–270 |
| 4 | `toApiQuery` `is_bpc` pass-through unasserted | filters.ts:335 |
| 5 | `formatIsk(undefined)` → '—' | format.ts:31 |
| 6 | `formatIsk(0)` → `'0'` (courier price) | format.ts:31 |
| 7 | `formatVolume` boundaries: exactly 0.005; just-below-100 | format.ts:55–56 |
| 8 | `formatComposition` empty-categories contract | format.ts:172–183 |
| 9 | `sortableFieldsFor` per-segment membership snapshot (current test is self-referential vs `columnsFor`) | columns.tsx:363–367 |
| 10 | Blueprint cell: single copy with one null figure → blank cell at list level | columns.tsx:199–200 |
| 11 | `EXPIRES_COLUMN` `text-warn` class fork on an expired row | columns.tsx:141–143 |
| 12 | `regions.ts` id-uniqueness invariant | regions.ts:3–74; format.ts:28 |
| 13 | `raiseApiError` non-401 leaves `['auth','me']` untouched; `useDebouncedValue` unmount cleanup / delayMs change (grouped) | client.ts:51–53; useDebouncedValue.ts:9 |

---

## Observations for the fixer

- The strongest cluster is exactly the code the remediation plan just touched: Phase 1's B5
  fix (per-field default direction) shipped with 2/9 fields pinned, and the week's debounce/
  freeze machinery has three good integration tests but zero unit coverage of its two pure
  functions (`sameSearch`, `useDebouncedValue`) — `sameSearch` isn't even exported, so its
  edge branches are untestable without either exporting it or driving them through the hook
  with list-param changes mid-debounce.
- Per TEST-12, several of the "Covered" verdicts above rest on component tests; where a fix
  lands for a gap, mutation-verify against the *new* test, not the neighboring page test.
- Per TEST-2, none of the timing-adjacent gaps (debounce reset, refetchInterval) should be
  closed with sleeps — fake timers (`vi.useFakeTimers`, as the taxonomy timeout test already
  does) keep them deterministic.
