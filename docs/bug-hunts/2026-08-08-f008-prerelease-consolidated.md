<!-- ABOUTME: Consolidated findings of the 2026-08-08 pre-release bug hunt over the F008 surface — -->
<!-- ABOUTME: four parallel hunter methodologies, cross-validated, with test-gap analysis appended. -->

# F008 Pre-Release Bug Hunt — Consolidated Findings

**Date:** 2026-08-08
**Scope:** The F008 Type-Aware Contract Browsing surface ahead of the dev→main release — backend
`services/contract_service.py`, `services/background_aggregation.py`, `services/db_upsert.py`,
`api/contracts.py`, `schemas/contracts.py`, `models/contracts.py`; frontend
`src/features/contracts/**` and `src/lib/api/**`.
**Hunters:** Exploratory, Holistic, Multipass, Differential (reports beside this file, same date-slug).
**Cross-validation:** every load-bearing claim below re-verified against source by the consolidator;
classification shifts from the hunters' own labels are noted where they occur.

---

## Confirmed Bugs

### B1. Item-bearing segment numerals advertise a population their click cannot deliver while an item-less segment is active
**Consensus:** Exploratory, Multipass, Differential (3/4); verified by consolidation.
**Location:** `SegmentTabs.tsx:118-123` (raw `counts[segment.type]`), `segmentPatch` `:77-82`
(click restores `ships_only`), `contract_service.py:504-511` (item-bearing counts computed under
`filters.is_ship_contract`, which is None on an item-less-segment request).
**Evidence:** Standing on Courier, `ships_only` was cleared (Criterion 1.7), so the envelope's
item-exchange/auction counts are ships-lifted; clicking either button restores ships-only
(Criterion 1.9), so the delivered population is the ships-only subset (~411 delivered vs ~33,800
advertised at spec magnitudes). The comment at `SegmentTabs.tsx:114-116` ("the number a segment
shows is the number selecting it delivers") is false in exactly this state. Decision-log D11 fixed
this same defect for the **All** control ("No numeral beats a wrong one") and recorded
serve-the-mirror-counts as a follow-up; the typed buttons were missed.
**Second manifestation (Exploratory):** during the courier→All transition, `leavingItemLess` flips
immediately (live URL) while the displayed counts are still the captured lifted envelope
(`keepPreviousData`), so the All numeral transiently reappears wrong — the WEB-1 shape
(interpreting captured data with live-URL flags).
**Impact:** Criterion 1.8's "silent-no-op defect wearing a numeral," mirror direction; user-visible
on every item-less-segment visit under default settings.
**Blast radius:** Frontend-only for the D11-precedent fix (hide typed numerals in that state, as All
already does). The full fix (serve ships-respecting mirror counts) is a backend envelope change —
recorded as design decision D-b below.
**Fix approach:** Apply the D11 precedent now — typed item-bearing numerals hidden while
`leavingItemLess`, pinned by tests; keep D-b as the recorded upgrade path.

### B2. A spec-conformant contract without `price` poisons the entire aggregation run, recurring every tick
**Consensus:** ALL FOUR hunters; verified by consolidation.
**Location:** `models/contracts.py:60` (`price … nullable=False`) vs `background_aggregation.py:261`
(`"price": c.get("price")` — bare, while `collateral` gets `0.0` one line down); committed ESI spec
snapshot marks `[].price` `required: false` on `/v1/contracts/public/{region_id}/`.
**Evidence:** A price-less payload writes NULL into a NOT NULL column; the batch upsert raises
`IntegrityError` inside the run-wide transaction; the whole run rolls back, and re-fails every run
for as long as the contract stays listed.
**Impact:** Total, self-renewing ingestion outage from one row. Latent (production evidence says ESI
sends `price: 0` today), spec-licensed, pre-existing (not F008-introduced) — but F008's backfill
rebuilds the row every run, so there is no skip to route around it.
**Blast radius:** Migration (price → nullable) + `NULLABLE_SORTS` must gain `price` (the non-null
premise recorded in its comment becomes false) + ingestion test omitting the field (TEST-22, added
this hunt) + **the watchlist matcher** (plan-review P1: `_render_message` at
`watchlist_matcher.py:54` formats a NULL price and aborts the run — a no-`max_price` watchlist
admits NULL-priced matches at `:173`) + the detail page's unconditional ` ISK` suffix
(`ContractDetailPage.tsx:190`). The wire schema is already `Optional[float]`
(`schemas/contracts.py:115`) and the generated `schema.d.ts` already types it nullable, so no
API-contract change. Defending with a
`0.0` default instead was REJECTED: ESI-3 / the project's absence-≠-zero principle — a missing
price is not "free," and the corpus must not publish a value it does not have.
**Fix approach:** Nullable migration, `NULLABLE_SORTS` extension, spec-minimal ingestion test,
frontend null-price rendering check. Classification: `Review — database schema`.

### B3. The URL parser passes non-integer blueprint bounds the backend 422s — the whole list view collapses
**Consensus:** Holistic, Differential (2/4); verified by consolidation (`toNonNegativeNumber` at
`filters.ts:187-190` lacks the `Number.isInteger` guard its siblings `toBoundedInt`/`toIdArray`
apply; all six bounds are `Optional[int]` server-side, and pydantic rejects `2.5`).
**Evidence:** `min_me=5.5` — typeable into the ME box (`BlueprintFilter.tsx` passes `Number(raw)`
through) or carried by a shared URL — survives parsing, is sent, 422s, and the core view degrades
to the "Failed to load contracts" error card with Retry re-422ing forever.
**Impact:** Violates the parser's own documented junk-tolerance contract ("a value that would 422
is never sent") for six user-reachable params.
**Blast radius:** One predicate in `filters.ts`; parser tests.
**Fix approach:** Integer guard in `toNonNegativeNumber` (or a dedicated integer variant for the six
bounds — `min_price`/`max_price` legitimately accept decimals and MUST keep doing so).

### B4. `formatComposition` naive pluralization garbles real dogma category names
**Consensus:** Multipass, Holistic, Exploratory (3/4); verified (`format.ts:167` appends `s`
unconditionally).
**Evidence/Impact:** "3 Commoditys", "2 Accessoriess", "2 SKINss" in the Criterion-6.1 composition
line — real categories, user-visible.
**Fix approach:** Minimal English rules sufficient for the dogma category namespace: no suffix when
the name already ends in `s`; `-y` → `-ies`; else `+s`. Pinned against the real names.

### B5. Courier segment's default sort direction contradicts the column's own default
**Consensus:** Multipass + Holistic flagged as a design concern; **promoted to confirmed minor bug
by consolidation** after verifying the mechanism.
**Location:** `filters.ts:260-262` (absent `sort_direction` falls back to a flat `'desc'`) vs
`ContractsPage.tsx:17-19` (`DEFAULT_DIRECTION[date_expired] = 'asc'` — the direction a header click
gives that column).
**Evidence:** Entering Courier with no sort in the URL reconciles the sort to `date_expired` (no
Issued column) but the direction to `'desc'` — longest-remaining-first — while clicking the same
Time-left header defaults to expiring-soonest-first. Same column, two defaults, chosen by entry
path.
**Impact:** Internal inconsistency; couriers is exactly the segment where Time-left ordering
carries the domain meaning.
**Fix approach:** Single-source the per-field default direction (move `DEFAULT_DIRECTION` into
`filters.ts`; parser fallback uses `DEFAULT_DIRECTION[resolved sort_by]`; `ContractsPage` imports
it). Default view is unchanged by construction (`date_issued` maps to `desc`).

### B6. `contractTypeLabel` block comment contradicts its code
**Consensus:** Multipass; to be re-verified at fix time.
**Location:** `format.ts:93-95` — comment says unrecognised types keep "Exchange"; code correctly
returns `'Unknown'`.
**Impact:** A provably-false comment inviting a regression that would desync the badge from the
unknown segment. Comment-only fix.

### B7. Duplicated `contract_type` values in a URL defeat segment detection
**Consensus:** Holistic (as design concern); **promoted to confirmed minor bug by consolidation** —
the parser's junk-tolerance contract owns URL junk. Mechanism (corrected by the plan review):
`?contract_type=courier&contract_type=courier` parses to a length-2 array; the ships-only widening
and `isItemLessSelection` use `.every()` and are unaffected, but `activeSegment` (`filters.ts:105`)
requires exactly one type, so single-segment identity breaks — no pressed button, fallback title,
no segment-scoped column set.
**Fix approach:** Dedupe in the parser, beside the validation it already does.

---

## Design Decisions Requiring Input (documented, not implemented)

### D-a. `search` and `type_ids` predate §3.1 and follow different semantics than every F008 filter
**Found by:** Exploratory, Holistic, Multipass (independently).
**The concern:** Both read *requested* items as well as offered (Story 8 conflation: a want-to-buy
contract matches a ship search), both apply per-joined-row rather than as the correlated EXISTS
§3.1 mandates for the F008 families, and they compose same-row with each other. Pre-existing,
deliberate at the time; now philosophically inconsistent within one function.
**Options:** (1) leave as-is, document; (2) migrate both to offered-only EXISTS (behavior change —
WTB contracts stop matching searches; needs a product call and probably a spec amendment).
**Recommendation:** Take (2) in a dedicated post-release follow-up — it also closes the perf
audit's P5 remainder (EXISTS for `type_ids`, rewritten search predicate). Not release-blocking.

### D-b. Serve ships-respecting mirror segment counts on item-less-segment requests
**The concern:** B1's full fix. D11 already records it as the follow-up; hiding numerals (shipped
now) is the precedent-consistent stopgap.
**Why a decision:** envelope/API change (`Review — public API contract`), extra count aggregation
cost per item-less request.

### D-c. `ESINotModifiedError` handlers are dead code, and the tests covering them mock behavior the client does not have
**Found by:** Multipass, Holistic.
**The concern:** The real ESI client's 304 path serves cache and never raises; the two handlers in
`background_aggregation.py` are unreachable, and tests asserting "304 counts as CHECKED OK" mock the
raise. **CLAUDE.md's testing rules require flagging mocked-behavior tests to Sam — this is that
flag.** Needs its own verification pass, then either the handlers become real (if a raise path
should exist) or handlers + tests go.

### D-d. A Valkey-evicted page body silently truncates a region walk mid-pagination
**Found by:** Holistic, Multipass.
**The concern:** Later-page contracts read as delisted for the etag TTL; the watermark advances on
earlier pages; no log line marks it. Ingestion-semantics fix (treat as failed region? log?) needs
sign-off.

### D-e. Multi-select taxonomy: a category with no selected group contributes nothing
**Found by:** Exploratory. The single same-item EXISTS means category A + group-of-category-B drops
category-A-only contracts; the in-code claim that the rail cannot produce this pairing is false
under multi-select. Semantics decision (per-family OR vs the current shape).

### D-f. BPC badge is invisible on the Auction segment
**Found by:** Multipass. Auctions can carry blueprint copies; the column set hides the badge there.
Product call.

### D-g. `issuer_id` / `issuer_corporation_id` are int32 under spec-int64 fields
**Found by:** Exploratory. Same poisoning shape as B2 if CCP ever allocates above 2^31.
**Recommendation:** fold a BigInteger widening into the next schema migration wave, not B2's
(keep B2 minimal and reviewable).

### D-h. During a resweep, an active URL-carried blueprint filter has no visible control
**Found by:** Holistic. FilterRail hides the whole block while coverage is `partial` — the same
objection its own comment raises for the item-less case. Transient-state UX call.

### D-i. `reconcileSort` strips `volume`/`collateral` sorts on segments whose column sets lack those headers
**Found by:** Multipass, framed as "dead UI capabilities" and an OD3 overstatement. Consolidation
note: this is `reconcileSort` working as designed (a sort no header can disclose is invisible), and
OD3's fix matters regardless because the sorts stay URL-reachable; but whether `volume` deserves a
column (and hence a sort) on more segments is a product question.

### D-j. `_taxonomy_coverage`'s two-statement read can transiently disagree across an ingestion commit
**Found by:** Multipass. Read-consistency nit; five-minute poll self-heals. Fix only if cheap.

### D-k. Stale `-1` sentinel rationale on both sides of the `min_runs` bound
**Found by:** Multipass. Comment cleanup candidate; verify against the current wire contract first.

---

## False Positives

None material. All four hunters checked candidate flags against the spec, pitfalls, and both
decision logs before reporting, and each report's "cleared" list names the documented decisions it
declined to flag (OD4 honest zeros, D11 All-numeral, D13 readiness triple, Criterion 1.7/1.8/1.9,
watchlist's separate predicates, `min_runs` wire asymmetry, item filters surviving segment
switches). Consolidation reclassified two hunter "design concerns" *upward* into bugs (B5, B7) and
none downward.

## Bugs Outside Primary Scope

### O1. Fixture wire-mirror drift (e2e)
**Found by:** Differential. `WirePage` omits `unknown_system_excluded` (a field the real envelope
carries); the composition tiebreak uses `localeCompare` where the service uses Python ordinal —
agreeing only over today's ASCII category names.
**Recommendation:** fold into the test-coverage review task, not the fix plan.

### O2. Item-less/item-bearing type partition is stated four times with no partition invariant
**Found by:** Differential. A future sixth contract type would silently drop from the All numeral.
**Recommendation:** invariant test (backend serves the partition or a test pins
`ITEM_LESS ∪ ITEM_BEARING = CONTRACT_TYPES` in both languages); test-coverage review task.

---

## Test Gap Analysis

### B1 (segment numerals)
**Why missed:** D11's tests pin only the All control's hidden numeral; no test renders the typed
buttons in the `leavingItemLess` state and asserts on their numerals.
**Pitfall coverage:** the transient manifestation is WEB-1 not-followed (captured data interpreted
with live-URL flags); the steady-state mismatch is a spec-semantics gap — one-off, noted in the fix
plan.
**Catch test:** render SegmentTabs with a courier-segment search and a lifted-counts envelope;
assert the item-exchange/auction buttons carry no numeral (post-fix contract).

### B2 (price NOT NULL)
**Why missed:** every ingestion fixture carries every field its author ever saw on the wire; the
absence path never executed.
**Pitfall coverage:** **new pitfall TEST-22 added** (this hunt, holistic hunter) — spec-minimal
ingestion payloads for every upstream-optional field.
**Catch test:** feed `_build_contract_rows` + the upsert a payload omitting `price`; assert the row
persists with NULL (post-fix contract).

### B3 (parser integer gap)
**Why missed:** parser junk tests feed decimal junk to `page`/`size` (which have the guard) but
never to the six blueprint bounds.
**Pitfall coverage:** one-off — noted in the fix plan (the parser's own doc comment is the
contract).
**Catch test:** `min_me=5.5` in the URL parses to `undefined`, and `toApiQuery` sends nothing.

### B4 (pluralization)
**Why missed:** format tests used only cleanly-pluralizing names ("Ship" → "Ships").
**Pitfall coverage:** one-off — fixture names must include the awkward real categories
(Accessories, SKINs, Commodity).

### B5 (courier direction)
**Why missed:** no test enters a segment via URL with no sort params and asserts the direction the
list actually requested; direction assertions all follow header clicks.
**Pitfall coverage:** one-off — noted in the fix plan.

### B6/B7
Comment fix (no test) / parser dedupe (same junk-tolerance suite as B3).

### Testing Pitfalls Updates
- TEST-22 added (spec-minimal ingestion payloads vs NOT NULL columns) — committed with this report.
