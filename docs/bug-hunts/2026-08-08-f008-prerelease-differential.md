# Bug Hunt Report — Differential

Hunt date: 2026-08-08. Scope: F008 "Type-Aware Contract Browsing" pre-release, analyzed on
`claude/pr-147-handoff-beaace` (HEAD `b442dc5`). Method: enumerate pairs/sets of functions that
must agree (round-trip, plan/apply, producer/consumer, inclusion/exclusion), state each pair's
invariant, and check it against both sides. Intent sources consulted before flagging:
`design/features/F008-Type-Aware-Contract-Browsing.md` (Criteria 1.1–1.9, 7.2), the F008 decision
log (`docs/superpowers/plans/2026-08-06-f008-decision-log.md`, D1/D10/D11/D13), the overnight
followups log (`docs/superpowers/plans/2026-08-08-overnight-followups-decision-log.md`, OD4), and
the committed ESI spec snapshot (`app/backend/tools/esi_spec_monitor/snapshot.json`).

## Scope

Backend: `app/backend/src/fastapi_app/services/contract_service.py`,
`services/background_aggregation.py`, `services/db_upsert.py`, `api/contracts.py`,
`schemas/contracts.py`, `models/contracts.py`, `tools/esi_spec_monitor/snapshot.json`.
Frontend: `app/frontend/web/src/features/contracts/**` (filters.ts, columns.tsx, format.ts,
components/SegmentTabs.tsx, FilterRail.tsx, TaxonomyFilter.tsx, BlueprintFilter.tsx,
ContractsPage.tsx, ContractTable.tsx, Pagination.tsx, hooks/useContracts.ts, useTaxonomy.ts,
useContract.ts), `src/lib/api/schema.d.ts`, `e2e/fixtures/contracts.ts`.

## Relationships Examined

- **parseContractSearch ↔ toApiQuery ↔ backend ContractFilters** (URL → state → wire round trip):
  every ContractSearch the parser emits must compile to a request the backend accepts (the
  parser's own documented junk-tolerance contract) — **VIOLATED** (Bug 2).
- **Segment count label ↔ what clicking the segment serves** (`_segment_counts_and_total` +
  `SegmentTabs` counts vs `segmentPatch` destination + parser restore): "the number a segment
  shows is the number selecting it delivers" (Criterion 1.8's rationale, restated in the
  SegmentTabs comment) — **VIOLATED** for item-bearing segments while an item-less segment is
  active (Bug 1). The item-less-under-item-filter zero and the hidden All numeral are ratified
  decisions (OD4, D11) and are NOT flagged.
- **ESI public-contracts payload (per committed spec snapshot) ↔ `_build_contract_rows` ↔
  Contract model constraints**: every payload the spec permits must produce a storable row —
  **VIOLATED** for `price` (Bug 3).
- **ContractFilters ↔ `_apply_contract_filters`/`_apply_item_filters` completeness**: every filter
  field must flow through the two shared helpers so `_segment_counts_and_total` and
  `_count_unknown_system_excluded` (which rebuild queries through them) stay in sync with the
  page — held. All 22 filter fields route through the helpers; both count paths rebuild via them.
- **Empty-page short-circuit ↔ normal-path `ContractListResponse` construction**
  (contract_service.py:1091–1104 vs 1125–1133): both sites carry the same envelope fields
  (total/page/size/items/unknown_system_excluded/segment_counts/coverage) — held.
- **`total` ↔ page predicate under type folding**: membership for `total` judged on the folded
  segment; the page predicate adds `type NOT IN (known)` when `unknown` is selected — the two
  partition identically — held.
- **`_needs_item_join` ↔ the filters that require a join**: search/type_ids/ship_name-sort join;
  the EXISTS families (is_bpc, runs/ME/TE, taxonomy) deliberately don't — held, and the
  conditional DISTINCT in `_segment_counts_and_total` keys off the same flag — held.
- **is_bpc filter ↔ served `is_blueprint_copy_contract` flag** (`_has_blueprint_copy_item` vs
  `_contract_fields`): both offered-items-only, both `is True` — agree by construction — held.
- **`_reward_per_volume` (Python, served value) ↔ SORT_MAP's SQL ratio**
  (`reward / nullif(volume, 0)`): identical NULL classes (reward NULL, volume NULL/0) — held.
- **Ingestion writers ↔ columns the API reads** (TEST-18 direction): every column
  `_contract_fields`/`ContractItemSchema` serializes and every column the filters read
  (runs/ME/TE, category_id/group_id, buyout, days_to_complete, end_location_*) is written by
  `_build_contract_rows` or `_fetch_item_rows`/`_enrich_items_and_find_ships` — held.
- **`_enrich_items_and_find_ships` "could not tell" set ↔ `_update_item_processing_status`
  COMPLETED/ENRICHMENT_INCOMPLETE partition ↔ `_select_already_enriched` skip**: unresolved
  category ⇒ incomplete ⇒ re-fetched; COMPLETED may clear the ship flag — held.
- **`_enrichment_is_current` denominator ↔ ingestion's item-fetch gate**: derived
  `_ITEM_BEARING_CONTRACT_TYPES` = {item_exchange, auction} matches the literal list in
  `_fetch_item_rows` — held today, but stated twice (see Design Concerns).
- **Frontend ITEM_LESS/ITEM_BEARING mirrors ↔ backend `_ITEMLESS_CONTRACT_TYPES`**: same
  partition — held today; unenforced (see Design Concerns).
- **useContracts query key ↔ values captured with the rows** (WEB-1): every captured value
  (segment, regionIds, enrichmentFiltered, itemFilteredItemLessSegment, itemSurfaceReady) is a
  function of `query` or of the key's readiness element — held.
- **`itemFilteredItemLessSegment` (client explanation) ↔ server behavior**: the EXISTS families
  are `is_included`-scoped, so an item-less segment under them genuinely serves 0, and
  `requiresOfferedItem` correctly splits `is_bpc=false` out (satisfied by every item-less
  contract) — held.
- **`hasActiveFilters` ↔ `resetFilters`**: the rail's button-visibility enumeration covers
  exactly the fields reset clears — held.
- **`reconcileSort`/`segmentPatch` ↔ `sortableFieldsFor`/column sets**: blueprint columns carry
  no sortField, so the narrow/wide column-set difference between the two callers cannot diverge
  (pinned by test, per the code) — held.
- **openapi.json/schema.d.ts ↔ live Pydantic schemas**: the generated
  `list_public_contracts_contracts__get` query block and response schemas match ContractFilters
  and the response models field-for-field (spot-checked all F008 additions) — held.
- **e2e fixture derivations ↔ service derivations** (`derivePrimaryLabel`/`deriveComposition`/
  `deriveBlueprintSummary` vs `_primary_label`/`_composition`/`_blueprint_summary`): same offered
  filter, same ship-first headline, same <2-rows null, same copy_count discriminator — held, with
  one sub-ASCII caveat (see Design Concerns).

## Bugs

### 1. Item-bearing segment counts overstate while an item-less segment is active — the label shows a no-ships-filter count but clicking restores ships-only

**Location:** `app/frontend/web/src/features/contracts/components/SegmentTabs.tsx:123`
(`: (counts[segment.type] ?? 0)`), against
`app/frontend/web/src/features/contracts/components/SegmentTabs.tsx:80-82` (`segmentPatch`
leavingItemLess → `ships_only: undefined`) +
`app/frontend/web/src/features/contracts/filters.ts:256` (absence parses as ships-only ON) +
`app/backend/src/fastapi_app/services/contract_service.py:504-511` (item-bearing segments are
counted under `filters.is_ship_contract`, which is None on an item-less-segment request).

**Severity:** significant

**Invariant violated:** "The number a segment shows is the number selecting it delivers" —
Criterion 1.8's stated rationale ("a `Courier (0)` label that becomes `Courier (115)` the instant
you click it is the silent-no-op defect wearing a numeral"), restated verbatim in the SegmentTabs
count comment ("Per-segment counts go out exactly as served … the number a segment shows is the
number selecting it delivers").

**Evidence:** Stand on the Courier segment. Criterion 1.7 cleared `ships_only`, so `toApiQuery`
sends no `is_ship_contract`; `_segment_counts_and_total` therefore computes the item_exchange and
auction counts with **no ships filter** (`_count_under_ships_filter(all, ships, None)` returns
`all_matching`). SegmentTabs displays those raw numbers on the Item exchange and Auction buttons.
But clicking either goes through the `leavingItemLess` branch of `segmentPatch`, which removes the
`ships_only` parameter, and the parser restores it to ON (Criterion 1.9) — so the page served is
ships-only, a strictly smaller population than the numeral advertised (e.g. "Item exchange 5,012"
→ click → 3,187 rows and a header saying "3,187 matching").

D11 identified this exact population mismatch and fixed it **for the All control only**: "The All
control renders without a numeral while an item-less segment is active. The envelope's
item-bearing counts were computed without ships-only, and All's destination restores it — a
population those numbers cannot describe. No numeral beats a wrong one." The individual
item-bearing buttons have the identical destination (ships-only restored via the same
`leavingItemLess` branch) and keep showing the identical wrong numbers. Neither D11's follow-up
("serve Criterion 1.8's mirror — ships-respecting item-bearing counts — on item-less-segment
requests") nor OD4 (which covers the different item-less-under-item-filter case and ratifies the
served zero there) addresses these two buttons.

**Impact:** Wrong numeral on the two most prominent segment controls whenever the reader is on
Courier (or a URL-reached loan/unknown segment) — the count then visibly shrinks the instant the
segment is clicked, which is the exact defect shape (in mirror image) Criterion 1.8 was written
to prevent, and which this project triaged as P1 when Codex found the All-control instance.
Fix options, consistent with D11: hide these numerals in the `leavingItemLess` state as All does,
or implement D11's recorded follow-up (serve ships-respecting item-bearing counts on
item-less-segment requests — the backend already computes both aggregates per type; the choice at
contract_service.py:508 of `None if segment in _ITEMLESS_CONTRACT_TYPES else
filters.is_ship_contract` would instead apply the ships filter to item-bearing segments whenever
the *destination* view carries it).

### 2. Parser accepts non-integer blueprint bounds that toApiQuery sends and the backend 422s — the documented junk-tolerance round trip breaks, and it is reachable by typing

**Location:** `app/frontend/web/src/features/contracts/filters.ts:248-253`
(`min_runs`…`max_te` parsed via `toNonNegativeNumber`, which never checks integrality) →
`filters.ts:301-307` (`toApiQuery` forwards them verbatim), against
`app/backend/src/fastapi_app/schemas/contracts.py:351-398` (all six are `Optional[int]` —
a query value of `2.5` fails Pydantic int parsing and 422s the request). Contributing entry
point: `app/frontend/web/src/features/contracts/components/BlueprintFilter.tsx:30-31`
(`Number(raw)` — a typed "2.5" flows into state unrounded).

**Severity:** significant

**Invariant violated:** parseContractSearch's own contract, stated at filters.ts:177-190 and
213-217: URL/state values that "422 the request … fall back to undefined here"; toApiQuery's
header: a value that would 422 "is never sent". Every ContractSearch the parser emits must
compile to a request the backend accepts.

**Evidence:** The parser enforces this contract asymmetrically. `page`/`size` go through
`toBoundedInt` (requires `Number.isInteger`), id lists through `toIdArray` (ditto), and the
tests pin the negative-value half ("drops negative min_price/max_price (backend schema minimum
is 0, would 422)", filters.test.ts:209). But the six blueprint bounds are parsed with
`toNonNegativeNumber`, which accepts any finite non-negative float — and unlike `min_price`/
`max_price` (backend `Optional[float]`, where 2.5 is fine), the backend fields are `int`.
`min_me=2.5` survives the parser, is sent by `toApiQuery`, FastAPI/Pydantic rejects the string
"2.5" for an int (`int_parsing`), the endpoint 422s, `useContracts` throws `ApiError`, and the
whole page renders the "Failed to load contracts" error card.

Reachable two ways: a shared/hand-edited URL (`?min_me=2.5`) — exactly the junk class the parser
exists to absorb — and ordinary typing: the ME/TE/Runs inputs are `type="number"` with no integer
guard in `bound()`, so typing "2.5" into Min ME navigates with `min_me: 2.5` and kills the list.

**Impact:** Instead of the designed graceful fallback, an entire core view degrades to an error
card on input the UI itself accepts. Fix is one predicate: the blueprint bounds need the same
`Number.isInteger` gate the other integer fields already have (parser side, so all routes in —
deep link, saved search, typing — get the identical treatment, matching the project's stated
parser-normalization pattern). A differential round-trip test (parser output → toApiQuery →
backend schema validation) would have caught this; the existing junk-tolerance tests only assert
the negative half of the "would 422" contract.

### 3. `_build_contract_rows` writes `price` bare into a NOT NULL column, while the committed ESI spec marks `price` optional — one spec-conformant payload aborts the whole aggregation run

**Location:** `app/backend/src/fastapi_app/services/background_aggregation.py:261`
(`"price": c.get("price")` — no default, unlike line 262's
`"collateral": c.get("collateral", 0.0)`), against
`app/backend/src/fastapi_app/models/contracts.py:60`
(`price: Mapped[float] = mapped_column(Numeric, nullable=False)`) and
`app/backend/tools/esi_spec_monitor/snapshot.json` (pinned view of
`GET /contracts/public/{region_id}`: `[].price` → `"required": false` — same as collateral,
volume, buyout).

**Severity:** significant (latent — no observed occurrence; probability unknown, blast radius
total)

**Invariant violated:** Every payload the committed ESI spec permits must produce a row the
Contract model can store (the producer/consumer contract the spec-monitor snapshot exists to
police, and the ESI-3 discipline: ESI omits fields rather than sending falsy ones).

**Evidence:** The spec snapshot the repo pins — the project's own authority for what ESI may
send — marks `price` not-required, exactly like `collateral`. The row builder defends
`collateral` with a `0.0` default because the model column is NOT NULL; `price` shares the same
NOT NULL constraint but gets `c.get("price")`, which is `None` for an omitted field. A single
price-less contract then fails the batch upsert (insert path and on-conflict `DO UPDATE
price=excluded.price` alike violate NOT NULL), the exception propagates out of
`_process_contracts`, and `run_aggregation` records the entire run failed — every region, and
recurring every subsequent run for as long as that contract stays in ESI's public list (up to
weeks), during which the whole corpus goes stale. The served schema deepens the disagreement:
`ContractListItemSchema.price` is `Optional[float]` (schemas/contracts.py:115), i.e. the API
layer already models a NULL price the storage layer forbids.

Production has ingested couriers (whose in-game price is 0) without incident, so ESI evidently
sends `price: 0` today rather than omitting it — which is why this is latent rather than live.
But the repo's stated posture (ESI-3; the spec monitor) is that optionality in the pinned spec is
load-bearing. Either give `price` the same treatment `collateral` already has (a default at the
row builder), or make the column nullable to match the served schema — the current three-way
state (spec: optional; API: optional; storage: required; writer: unguarded) is internally
inconsistent whichever intent is right.

**Impact:** A single spec-conformant contract poisons every aggregation run until it delists —
silent corpus-wide staleness with only the ingest-failure log to show for it.

## Design Concerns

Fragile informal invariants — not bugs today, but relationships nothing enforces:

- **The item-less/item-bearing partition is stated four times, enforced once.** Backend:
  `_ITEMLESS_CONTRACT_TYPES` (contract_service.py:406) with `_ITEM_BEARING_CONTRACT_TYPES`
  derived as its complement — good; but ingestion's item-fetch gate restates it as a literal
  (`background_aggregation.py:717`: `not in ["item_exchange", "auction"]`), and the readiness
  denominator (`_live_item_bearing_contracts`) only agrees with the fetch gate because the two
  independent statements happen to match. Frontend: `ITEM_LESS_TYPES` and `ITEM_BEARING_TYPES`
  (filters.ts:58,66) are two more independent statements. The `Exhausted<>` device forces
  `CONTRACT_TYPES` to track the server enum, but nothing forces
  `ITEM_LESS_TYPES ∪ ITEM_BEARING_TYPES = CONTRACT_TYPES`: a sixth contract type added later
  would compile after a `CONTRACT_TYPES` edit while `sumCounts(counts, CONTRACT_TYPES |
  ITEM_BEARING_TYPES)` (SegmentTabs.tsx:122) silently omitted it from the All numeral. A
  `satisfies`-level partition check (or deriving one list from the other, as the backend does)
  would close it.
- **Fixture composition ordering matches the service only over ASCII, uniformly-capitalized
  names.** `_composition` tiebreaks with Python ordinal sort (`entry.name or ""`,
  contract_service.py:755-761); the e2e builder tiebreaks with `localeCompare`
  (e2e/fixtures/contracts.ts:293-298). For today's EVE category names ("Ship", "Module", …) the
  two agree; a name differing only in case or diacritics would order differently, letting an
  ordering assertion pass against fixtures and fail live. Worth one ordinal-compare line in the
  fixture if category names ever widen.
- **`WirePage` omits `unknown_system_excluded`.** The real envelope always carries it (null when
  system_ids wasn't applied). No frontend consumer reads it today, so nothing breaks — but the
  fixture header promises "exactly what the backend would send", and the first consumer of that
  field will find the fixture lane silently green.

## Non-findings (checked and cleared, recorded to save the next hunter the trip)

- Item-less segment counts reading 0 under taxonomy/blueprint/is_bpc filters: ratified
  working-as-designed (OD4 — the served zero is honest because those filters survive the
  segment switch).
- The hidden All numeral on item-less segments: D11, deliberate.
- `ships_only` not surviving a courier round trip when it was explicitly false beforehand:
  Criterion 1.9 defines return as restore-the-default, deliberate.
- Item-level filters NOT dropped by the parser on item-less selections: deliberate, documented
  at filters.ts:229-239 (an earlier revision did drop them and was reverted).
- `min_runs` ge=-1 on the wire vs the parser stripping negatives: deliberate
  (filters.ts:181-186).
- `watchlist_matcher` hand-writing its own item predicates: deliberate per the task scoping.
- `is_singleton`/`raw_quantity`/`status`/`date_completed` absent from wire schemas while
  present as columns: deliberate (ESI-3, authenticated-route fields).

## Testing-pitfalls note

Bug 2 is the one finding a *differential* test class would have caught: a round-trip property
test asserting that every `parseContractSearch` output, compiled through `toApiQuery`, validates
against the backend's `ContractFilters` schema (the existing junk-tolerance tests assert only
hand-picked halves of that contract — negatives but not non-integers). Per the hunt protocol the
testing-pitfalls doc was not modified (this run is analysis-only); if the fix lands, that is the
natural PR to add the pitfall entry in.
