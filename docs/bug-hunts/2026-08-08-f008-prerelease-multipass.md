<!-- ABOUTME: Multi-pass bug hunt report for the F008 pre-release audit (2026-08-08) — five focused
     analysis passes (contract violations, cross-sibling patterns, failure modes, concurrency, error
     propagation) over the F008 backend and frontend surface. -->

# Bug Hunt Report — F008 pre-release, multi-pass methodology

## Scope

Analyzed (source only; no test files read, per methodology):

- **Backend:** `app/backend/src/fastapi_app/services/contract_service.py`, `services/background_aggregation.py`, `services/db_upsert.py`, `api/contracts.py`, `schemas/contracts.py`, `schemas/common.py`, `models/contracts.py`, `core/esi_client_class.py` (ETag/304 mechanics only), `tools/esi_spec_monitor/snapshot.json` (required-field arrays only).
- **Frontend:** `app/frontend/web/src/features/contracts/` — `filters.ts`, `columns.tsx`, `format.ts`, `regions.ts`, `components/{ContractsPage,SegmentTabs,ContractTable,FilterRail,TaxonomyFilter,BlueprintFilter,ContractDetailPage,Pagination}.tsx`, `hooks/{useContracts,useTaxonomy,useContract}.ts`; `lib/api/client.ts`.
- **Intent sources consulted before flagging:** `design/features/F008-Type-Aware-Contract-Browsing.md` (spec, incl. §3.1/§17), `docs/pitfalls/implementation-pitfalls.md`, `docs/superpowers/plans/2026-08-06-f008-decision-log.md` (D1–D13), `docs/superpowers/plans/2026-08-08-overnight-followups-decision-log.md` (OD1–OD6).

All five passes performed: (1) contract violations, (2) cross-sibling pattern violations, (3) failure-mode reasoning, (4) concurrency reasoning, (5) error propagation.

## Bugs

### Item-bearing segment tab counts advertise a population the click cannot deliver while an item-less segment is active
**Location:** `app/frontend/web/src/features/contracts/components/SegmentTabs.tsx:123` (numeral), `:77-82` (`segmentPatch` ships-only restore); server side `app/backend/src/fastapi_app/services/contract_service.py:504-511` (`_segment_counts_and_total`)
**Severity:** significant
**Evidence:** Standing on the Courier segment (`/contracts?contract_type=courier`), the parser has cleared `ships_only` (Criterion 1.7, `filters.ts:256`), so the request carries no `is_ship_contract` and the served `segment_counts["item_exchange"]` / `["auction"]` are computed over **all** matching contracts — not the ships-only subset. `SegmentTabs.tsx:123` renders those numerals as-is (`counts[segment.type] ?? 0`). But clicking Item exchange or Auction from an item-less segment goes through `segmentPatch` with `leavingItemLess=true`, which sets `ships_only: undefined` — restoring the ships-only default (Criterion 1.9). The delivered page's total is the ships-only count; the advertised numeral was the lifted one. At the spec's own measured magnitudes (§1: ~411 ship-flagged of ~33,900 live), the label and the landing total disagree by roughly two orders of magnitude.

Decision log D11 identified this exact mechanism for the **All** control and fixed it there by hiding the numeral ("No numeral beats a wrong one"), explicitly noting the missing mirror data as a follow-up ("serve Criterion 1.8's mirror — ships-respecting item-bearing counts — on item-less-segment requests"). The typed item-bearing tabs have the identical defect and were left showing the raw numerals. The comment at `SegmentTabs.tsx:114-116` ("the number a segment shows is the number selecting it delivers") is false in precisely this state — the ships-only restore on the way out is what breaks it.
**Impact:** On the Courier (or URL-reached loan/unknown) segment, the Item exchange and Auction tabs read e.g. "Item exchange 15,000"; clicking lands on a page totalling ~400. This is the "silent-filter-no-op defect wearing a numeral" that Criterion 1.8 exists to prevent, in the mirror direction. Fix options, consistent with D11: hide the item-bearing numerals while `leavingItemLess` (as All already does), or serve the ships-respecting mirror counts on item-less-segment requests.
**Found in:** Pass 2 — cross-sibling pattern violations (the All control is the sibling that got the fix), confirmed in Pass 1 against the comment's stated contract.

### `Contract.price` is NOT NULL over an upstream-optional field with no ingestion default — one price-less contract halts all ingestion persistently
**Location:** `app/backend/src/fastapi_app/services/background_aggregation.py:261` (`"price": c.get("price")`), `models/contracts.py:60` (`price: Mapped[float] = mapped_column(Numeric, nullable=False)`); upstream: `tools/esi_spec_monitor/snapshot.json` `GetContractsPublicRegionId` `[].price` `required: false`
**Severity:** significant (latent — no known production occurrence)
**Evidence:** The committed ESI spec snapshot records `price` as **optional** on `GET /contracts/public/{region_id}`. `_build_contract_rows` maps it with a bare `.get()` (no default, unlike `collateral`'s `c.get("collateral", 0.0)` one line below and `for_corporation`'s default), and the column is `nullable=False`. This is the FASTAPI-3 three-link chain (upstream `required` → model `nullable=` → response `Optional`) broken at the upstream→model link: each link MUST be at least as permissive as the one above, and here the model is stricter than the spec. ESI-3 documents that ESI's public routes omit falsy fields rather than sending them, so a zero-price contract (courier, loan) omitting the key is exactly the shape the upstream contract permits.
**Impact:** A single contract arriving without `price` makes its batch's `bulk_upsert` raise `IntegrityError`, which aborts the run's single shared transaction (`_process_contracts` commits once at the end) — no contracts, items, or restamps land for **any** region that run. Because the offending contract stays in ESI's public list, every subsequent run fails identically until it delists: a persistent, total ingestion outage triggered by one upstream row. Fix is one of: default at ingestion (as `collateral` does), or make the column nullable and the response field already-`Optional[float]` absorbs it. Pre-existing (predates F008), but F008's spec verification pass surfaced the `required` array this violates, and F008's contract-level backfill guarantees `_build_contract_rows` runs over every fetched contract every run — there is no skip that could route around the row.
**Found in:** Pass 3 — failure mode reasoning ("what happens if this row lacks the field?"), cross-checked against the spec snapshot.

### `formatComposition` naive pluralization mangles real dogma category names
**Location:** `app/frontend/web/src/features/contracts/format.ts:167` (`${category.name}${category.item_row_count === 1 ? '' : 's'}`)
**Severity:** minor
**Evidence:** The composition line appends a bare `s` for counts above one. Real dogma category names in the contract corpus include "Commodity" (category 17 — PLEX and other commodities are a routine multi-item-contract filler), "Accessories" (5), "Apparel" (30), and "SKINs" (91). These render as "3 Commoditys", "2 Accessoriess", "4 SKINss".
**Impact:** Visible misspellings in the list row's composition summary — the row surface Criterion 6.1 makes a headline feature — for common mixed-lot contents. Needs either an irregular-plural map, no pluralization (`3 × Commodity`), or `Intl.PluralRules`-style handling with the category name kept invariant.
**Found in:** Pass 1 — contract violations (the function's promise is a readable per-category breakdown; it silently emits non-words for valid inputs).

### `contractTypeLabel`'s block comment asserts the opposite of what the code does
**Location:** `app/frontend/web/src/features/contracts/format.ts:93-95` vs `:108-112`
**Severity:** minor
**Evidence:** The comment above `TYPE_LABELS` reads "Anything unrecognised keeps the historical 'Exchange' reading rather than surfacing a raw wire value." The function returns `TYPE_LABELS[type] ?? 'Unknown'`, and its own inline comment says the label "must say so rather than masquerade as an exchange" — i.e. the exact opposite policy, which is the correct one (a stored type outside the enum is served under the unknown segment, `contract_service.py:494-501`).
**Impact:** The stale comment invites a future editor to "fix" the fallback back to `'Exchange'`, which would mislabel out-of-enum types and desynchronize the badge from the unknown segment that serves those rows. Comment-only fix.
**Found in:** Pass 1 — contract violations (comment/code disagreement).

## Design Concerns

These are not defects against any spec or decision-log ruling I could find, but each is a pattern that raises bug risk. None are coverage observations.

1. **`type_ids` and `search` are the two item-level filters exempt from §3.1's offered-only existential rule.** `_apply_item_filters` (`contract_service.py:341-342`) applies `type_ids` as a per-row predicate on the joined items with no `is_included` restriction, and the `search` predicate (`:271-276`) matches `ContractItem.type_name` on both sides of the trade. Every F008 family (is_bpc, runs/ME/TE, taxonomy) is a correlated EXISTS over **offered** items; these two pre-F008 filters classify contracts via **requested** items too — a want-to-buy ad asking for a Vindicator matches `type_ids=<Vindicator>`. Because both filters are positive-only (no negation offered) the join+DISTINCT form is semantically existential, so there is no SQLA-3 overlap defect — but the sibling deviation is exactly the shape §3.1 warns "will fail the same way" if a negative branch or bound is ever added, and the requested-side matching is a Story-8-adjacent surprise that nothing documents as chosen.

2. **The `volume` and `collateral` sorts are dead UI capabilities that the parser actively strips.** No column in any segment's set carries `sortField: 'volume'` or `'collateral'` (verified across `columns.tsx`), so `reconcileSort` (`filters.ts:274-285`) rewrites any URL or saved search carrying them to the fallback. They remain valid API parameters and full members of `SORT_FIELDS`/`DEFAULT_DIRECTION`. OD3's rationale for extending `NULLABLE_SORTS` ("the UI now offers all five sorts side by side") overstates this — `volume` is offered nowhere. Risk: a future column addition that names one of these sortFields silently resurrects a sort whose direction defaults were never exercised; conversely today's dead entries are maintenance surface that misleads readers about what the UI can express.

3. **`ESINotModifiedError` is caught but can no longer be raised.** `_fetch_regions` (`background_aggregation.py:406`) and `_fetch_item_rows` (`:751`) both handle it, and the freshness accounting comment says "a 304 region counts as CHECKED OK" via that path — but `get_esi_data_with_etag_caching` (`esi_client_class.py:221-224`) handles 304 internally by serving the Valkey-cached body and never raises the exception. The handlers are dead code and the comments describe an accounting path that cannot occur. Harmless today (the cache-serving path restamps contracts, which is strictly better), but the dead branches invite reasoning about a mechanism that does not exist.

4. **A 304 whose cached body was evicted silently reads as an empty region for up to one ETag TTL.** `_read_etag_cached_page` (`esi_client_class.py:245-254`) returns `[]` and pagination stops, by documented decision ("does not fall back to a live fetch"). ETag key and data key share a TTL but Valkey's `allkeys-lru` (DEPLOY-3) can evict them independently — etag surviving, body gone yields a 304 answered with nothing. The per-region watermark keeps rows visible and the zero-item guard keeps contracts out of COMPLETED, so the blast radius is bounded staleness — but the run is recorded `regions_ok`/`success` in the freshness record for a region that was not actually checked, which slightly overstates health in exactly the degraded state the record exists to expose.

5. **Courier segment's default sort direction contradicts the app's own direction convention for that field.** Entering Courier resets the sort to `date_expired` (D11's fallback — the set has no Issued column) with the parser's blanket `desc` default (`filters.ts:260-262`), i.e. longest-time-left-first, while `DEFAULT_DIRECTION` (`ContractsPage.tsx:17-29`) declares `date_expired: 'asc'` ("soonest for dates"). A user's first click on the Time left header then toggles to `asc` rather than establishing it. Cosmetic ordering inconsistency on the segment's cold view.

6. **The BPC badge is invisible on the Auction segment.** `AUCTION_COLUMNS` drops `TYPE_COLUMN` (correct — every row is an auction), but that column is also the only carrier of the `is_blueprint_copy_contract` badge. Before readiness the blueprint columns are omitted too, so a BPC auction is indistinguishable from any other auction on its own segment while the default segment shows the badge for the same row.

7. **`filters.ts:183-185`'s rationale for the backend's `min_runs ge=-1` bound repeats a claim ESI-3 refutes.** The comment says "the backend accepts `min_runs=-1` because ESI publishes it as a sentinel"; pitfall ESI-3 establishes the `-1` sentinel never occurs on any data Hangar Bay ingests (public route omits `runs` instead). Harmless permissiveness, stale rationale on both sides of the wire (`schemas/contracts.py:351-366` carries `ge=-1` with no stated reason).

8. **`_taxonomy_coverage` reads its two conditions in separate statements** (`contract_service.py:932-936`) under READ COMMITTED, so an ingestion commit landing between them can produce one transiently inconsistent partial/complete verdict. Self-corrects on the next request; noted only because the value gates the whole item surface.

## Methodology note

Findings were not cross-checked against the test suites or e2e specs (methodology forbids reading test files), so a finding pinned as intended behavior by a test I could not read would need that evidence surfaced at consolidation. Intent sources (spec, pitfalls, both decision logs) were checked for every finding above; none ratify the flagged behaviors.

`docs/pitfalls/testing-pitfalls.md` was reviewed and deliberately left unedited: the two substantive bugs found are a UI state-transition honesty defect and an ingestion NOT-NULL chain violation — the second is already fully covered in kind by implementation-pitfalls FASTAPI-3 (the doc's three-link chain rule; this instance breaks the upstream→model link it names), and this hunt is one of several running in parallel, so pitfall edits belong to the consolidation step rather than to one hunter's branch.
