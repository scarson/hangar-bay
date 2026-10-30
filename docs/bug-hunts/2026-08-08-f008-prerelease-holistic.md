# Bug Hunt Report — F008 pre-release (holistic)

**Date:** 2026-08-08
**Method:** bug-hunter-holistic — read every in-scope source file into context, then reason about
contract violations, sibling-pattern breaks, silent data loss, and error propagation.
**Tree:** worktree `pr-147-handoff-beaace` at `b442dc5` (F008 complete on dev, release pending).

## Scope

Backend: `services/contract_service.py`, `services/background_aggregation.py`, `services/db_upsert.py`,
`api/contracts.py`, `schemas/contracts.py`, `schemas/account.py` (SavedSearchParameters), `schemas/common.py`,
`models/contracts.py`, `core/esi_client_class.py` (the 304/ETag path the ingestion findings depend on).
Frontend: `features/contracts/**` (filters.ts, columns.tsx, format.ts, regions.ts, all components, all hooks),
`lib/api/client.ts`, `routes/contracts.index.tsx`, `routes/contracts.$contractId.tsx`.
Intent sources consulted before flagging anything: the F008 spec (all of §3, §3.1, §8, §17),
`docs/pitfalls/implementation-pitfalls.md` (full), decision logs D1–D13 and OD1–OD6.
Several surprising-looking behaviors were checked against those logs and are **not** flagged
(the OD4 honest-zero segment counts, the D13 readiness capture + `enabled` gate + key mechanism,
the D11 sort reconciliation, the D8 range-family branch semantics, the D10/SQLA-5 `preserve_on_null`
name columns, the Criterion 1.8/1.9 ships-only lift/restore).

Two claims were verified empirically rather than by reading: the committed ESI spec snapshot's
`required` flags for `GET /contracts/public/{region_id}` (via `tools/esi_spec_monitor/snapshot.json`),
and pydantic v2's rejection of non-integral values for `Optional[int]` (via the project venv).

## Bugs

### 1. `Contract.price` is NOT NULL over an ESI-optional field with no ingestion default — one price-less contract aborts every aggregation run

**Location:** `app/backend/src/fastapi_app/models/contracts.py:60` (`price: Mapped[float] = mapped_column(Numeric, nullable=False)`) and `app/backend/src/fastapi_app/services/background_aggregation.py:261` (`"price": c.get("price")`)
**Severity:** significant (latent — spec-licensed, not yet observed in production)
**Evidence:** The committed ESI spec snapshot records `[].price` as `required: false` on
`GET /contracts/public/{region_id}` (verified in `tools/esi_spec_monitor/snapshot.json`; the only
required fields are `contract_id`, `date_expired`, `date_issued`, `issuer_corporation_id`, `issuer_id`,
`type`). Every other optional field in `_build_contract_rows` is handled: `collateral` gets a `0.0`
default (`:262`), `for_corporation` gets `False` (`:257`), and `reward`/`volume`/`buyout`/
`days_to_complete`/`title`/locations sit over nullable columns. `price` alone maps `c.get("price")`
— None when absent — into a `nullable=False` column. This violates the FASTAPI-3 chain rule
("each link at least as permissive as the one above; enforce at INGESTION") at the one field the
F008 field audit didn't touch.
**Impact:** ESI expresses absence by omission (ESI-3), and a courier/loan with no price is exactly
the shape it licenses. If one such contract ever appears, the 500-row batch's single
`INSERT ... ON CONFLICT` raises `IntegrityError`, `_process_contracts` has no per-batch isolation,
the run's single end-of-run commit never happens, and `run_aggregation` records a failed run — for
**every** run, for as long as that contract stays listed (up to two weeks). That is a total,
repeating ingestion outage across all regions triggered by one upstream row, with staleness the only
user-visible symptom. Fix shape: default at ingestion (`c.get("price", 0.0)`) or make the
column/response chain nullable — decided deliberately, since `price` is sortable/filterable.

### 2. The URL parser passes non-integer blueprint-range bounds through to the API, 422ing the whole list view

**Location:** `app/frontend/web/src/features/contracts/filters.ts:187-190` (`toNonNegativeNumber`, used for `min_runs`/`max_runs`/`min_me`/`max_me`/`min_te`/`max_te` at `:248-253`); reachable from `components/BlueprintFilter.tsx:30-31` (`Number(raw)` from a `type="number"` input)
**Severity:** minor
**Evidence:** `parseContractSearch`'s contract is documented at `:214-217`: "Accepts arbitrary
address-bar input and always returns a well-formed ContractSearch — invalid values fall back to
defaults rather than throwing," and the sibling coercers honor it (`toBoundedInt` and `toIdArray`
both require `Number.isInteger`). `toNonNegativeNumber` checks only finite-and-≥0, so `min_me=5.5`
— typed into the ME box (the input's implicit `step=1` flags it but does not block the value) or
carried in a shared/hand-edited URL — survives parsing and is sent to the API. The backend fields
are `Optional[int]` (`schemas/contracts.py:351-398`), and pydantic v2 rejects `"5.5"` and `5.5`
for `int` (verified against the project venv: both raise `ValidationError`), so the request 422s.
**Impact:** The core list view collapses to the "Failed to load contracts. The market data service
may be unreachable." error card — a misdiagnosis; the service is fine — and Retry re-issues the
same 422 forever while the junk value sits in the URL. The user must find and clear the offending
bound (or Clear filters) to recover. This is the exact silent-junk class the parser exists to
absorb, broken for six of its parameters. Fix shape: require `Number.isInteger` in the coercer for
the six int-typed bounds (or floor in `BlueprintFilter`'s `bound`).

### 3. `formatComposition` pluralizes category names by appending `s`, misspelling real dogma categories

**Location:** `app/frontend/web/src/features/contracts/format.ts:167` (`${category.item_row_count} ${category.name}${category.item_row_count === 1 ? '' : 's'}`)
**Severity:** minor (cosmetic, user-visible on real data)
**Evidence:** Category display names come from ESI verbatim, and the dogma set includes names for
which naive `+s` is wrong: `Commodity` → "3 Commoditys" (category 17 — PLEX and mission commodities
are common in mixed lots), `Accessories` → "2 Accessoriess" (category 5), `Entity` → "Entitys",
`Apparel` → "Apparels". `Ancient Relics` and `Special Edition Assets` double their plural. The
composition line is Criterion 6.1's headline deliverable, so these strings land in the most-read
cell of the multi-item row.
**Impact:** Confidently misspelled English in the product's signature summary line. Fix shape:
pluralize only known-safe names, use `Intl.PluralRules` with a small irregular map, or drop the
suffix entirely ("Commodity × 3").

## Design Concerns

These are risk patterns, not spec violations; each was checked against the spec/decision logs and
none is contradicted by a recorded decision.

1. **`search` and `type_ids` still use the per-joined-row form and compose on the same row,
   contradicting §3.1's family semantics one filter over.** `_apply_contract_filters` matches
   `ContractItem.type_name.ilike(...)` and `_apply_item_filters` matches
   `ContractItem.type_id.in_(...)` as predicates on the same joined row
   (`contract_service.py:271-276, 341-342`). Two consequences, both pre-existing but now
   inconsistent with the F008-established rules: (a) search matches **requested** items — searching
   "Rifter" surfaces want-to-buy ads asking for Rifters, the conflation Story 8/§3.1 excludes for
   every other item predicate; (b) `search` + `type_ids` together demand the SAME item satisfy both
   (row-level AND), where §3.1's rule for separate families is "may be satisfied by different
   items" — a contract offering a Rifter whose title matches nothing and an Ishtar whose name
   matches the search is excluded from `type_ids=<Rifter>&search=Ishtar`. The `ship_name` sort
   aggregate similarly ranges over requested items, so a WTB contract sorts under a name its row
   never displays. Worth an explicit decision (extend §3.1 to these two, or record the exemption).

2. **A Valkey-evicted page body silently truncates a region walk and makes later-page contracts
   read as delisted.** `_read_etag_cached_page` returns `[]` for a 304 whose cached body was
   evicted (`esi_client_class.py:245-254`), and `_last_page_reached` treats the empty page as the
   end of the walk (`:319-322`). If pages 1..k of a region serve and page k+1's body was evicted
   (etag surviving, body gone — routine under `allkeys-lru`, DEPLOY-3), the run restamps only pages
   1..k, the region's watermark advances, and every contract on the later pages fails
   `still_listed_by_esi` — vanishing from the site as "delisted" until the etag TTL expires
   (~30–60 min). No error is logged anywhere on this path. Same shape on the items route is benign
   (the zero-item guard keeps the contract un-COMPLETED), but the region walk has no equivalent
   guard.

3. **`ESINotModifiedError` is never raised by production code; the tests that exercise the "304
   counts as CHECKED OK" accounting mock a behavior the real client does not have.**
   `get_esi_data_with_etag_caching` serves 304s from cache and never raises; the handlers at
   `background_aggregation.py:406` and `:751` are reachable only from test mocks
   (`test_background_aggregation.py:257, 1394, 1495, 1591` construct it by hand). The real
   304-path accounting differs from what those tests pin (a real all-304 region returns its cached
   contracts and takes the normal path). Dead handler + mocked-behavior tests — the class
   CLAUDE.md's testing rules ask to be surfaced.

4. **While the item surface is not ready, an active taxonomy/blueprint filter has no visible
   control.** `FilterRail.tsx:192-209` replaces the whole item-level control block with "Item
   filters are still indexing." even when the URL carries `min_me=5` — the exact objection the
   adjacent comment raises for the item-less case ("hiding a control whose parameter is set hides
   an ACTIVE filter"). Mitigated by the page-level "results may be incomplete" notice and the
   Clear-filters button, but the specific value is invisible and individually unclearable for the
   duration of a resweep.

5. **Entering the Courier segment defaults to Time-left descending, against the app's own
   direction convention.** `reconcileSort` falls back to `date_expired` with the parser's blanket
   `desc` default (`filters.ts:259-262, 284`), while `DEFAULT_DIRECTION` (`ContractsPage.tsx:20`)
   deliberately sets `date_expired: 'asc'` ("soonest first"). So a fresh courier tab orders
   longest-remaining-first, but clicking its own Time-left header fresh gives soonest-first.
   Internal inconsistency, one line to align if the soonest-first reading is preferred.

6. **A duplicated `contract_type` value in a hand-edited URL defeats segment detection.**
   `toContractTypes` does not dedupe, so `?contract_type=courier&contract_type=courier` yields a
   length-2 array, `activeSegment` returns undefined, and courier rows render under the default
   (sale) columns while the request itself is fine. Junk-input polish only.

## Testing-pitfalls follow-up

Added TEST-22 to `docs/pitfalls/testing-pitfalls.md`: ingestion-mapping tests never omit
upstream-optional fields, which is why Bug 1 survived every suite — all payload fixtures carry
`price`, so the NOT NULL column's absence path has never executed. (Mirror of TEST-18: that entry
reconciles fixtures against the writer; this one reconciles the writer against the upstream
`required` array.)
