<!-- ABOUTME: Adversarial product-completeness/YAGNI/spec-fidelity review of the M3 account-features design spec. -->
<!-- ABOUTME: Walks every F005/F006/F007 story + acceptance criterion against the design and the verified 2026-07-17 codebase. -->

# M3 Design Review — Product Completeness / YAGNI / Spec Fidelity

**Reviewer lens:** product completeness + YAGNI + spec fidelity.
**Spec under review:** `docs/superpowers/specs/2026-07-17-m3-account-features-design.md`
**Feature authority:** F005-Saved-Searches, F006-Watchlists, F007-Alerts-Notifications.
**Verified against:** `app/backend/src/fastapi_app/schemas/contracts.py`, `app/frontend/web/src/features/contracts/filters.ts`, `ContractDetailPage.tsx`, `schemas/common.py`, auth feature tree.

**Verdict: sound-with-fixes.** The zero-scope framing is correct and well-justified; the apply-saved-search round-trip is clean; every story is satisfiable or explicitly deferred. Findings are one substantive product/reasoning gap in F006 and three smaller fidelity items.

---

## Attack results (what survived, what I refuted)

### Refuted (design holds — recorded so the next reviewer doesn't re-litigate)

- **Apply-saved-search round-trip is symmetric and lossless.** I compared `SavedSearchParameters` (spec §4.5) field-by-field against the frontend `ContractSearch` (`filters.ts`) and the backend `SortableContractFields` enum (`schemas/contracts.py`). `ContractSearch` = {search, min_price, max_price, region_ids, is_bpc, ships_only, page, size, sort_by, sort_direction}. `SavedSearchParameters` = the same set minus `page`. `sort_by`'s enum (`SortableContractFields`) has exactly the 6 values the frontend `SortField` union has (`date_issued, date_expired, price, collateral, ship_name, volume`) — **no mismatch**, so a search sorted by `ship_name`/`collateral`/`volume` saves and 422s nowhere. No field the saved payload can express is un-expressible by the `/contracts` URL, and vice versa. The one dropped field (`page`) is intentional. This round-trip is a non-issue.
- **Zero-scope framing is factually correct.** Enumerated each feature's data needs: F005 = HB rows only; F006 type validation needs `published` + `category_id==6`, both from public/unauthenticated ESI already wrapped by `ESIClient`; F007 matches local `contracts`/`contract_items`. No F005/F006/F007 requirement — including a future type-ahead ship search, which hits public `universe/types` — needs an ESI scope. The design's YAGNI rejection of requesting the first scope is sound.
- **No-individual-GET deviation is safe.** F005 §7 explicitly permits applying "or uses already loaded data"; the design applies from the loaded list. `GET /me/*/{id}` has no consumer. Correctly deferred (§8), not a silent drop.
- **Rename-only PUT** matches F005 Story 5 / Criterion 5.3 (criteria-update explicitly deferred by the feature spec). Correct.
- **Bell-as-link** satisfies F007 Criterion 3.4 ("dedicated UI element (e.g., a notification bell/panel)") and Story 4 (list, mark-read, contract links). The dropdown was an "e.g." No story becomes unsatisfiable.
- **Notification-settings-as-one-checkbox** satisfies F007 Criterion 3.1; 3.2/3.3 are feature-tagged future. Fine.
- **PaginatedResponse.total exists** (`schemas/common.py`) so the unread-badge-via-`size=1`-reading-`total` trick is buildable. `HeaderIdentity`, `useCurrentUser`, and `Input`/`Checkbox`/`Badge`/`Button` all exist — the "no new overlay primitives" claim holds.

---

## Findings

### 1. [MAJOR] F006 watchlist-add is reachable only for ships currently in a viewed contract — the chosen UI reintroduces the exact limitation the design used to reject its alternative, and §10 claims full F006 coverage anyway

**Where:** spec §3.2, §5 ("Watchlist add (F006): on the contract detail page (F003), each included ship item row gains a … Watch button"), §8 (type-ahead deferral), §10 (item 1).

**The gap.** The *only* frontend entry point for adding a watchlist item is a Watch button on a **contract detail page**, gated on `category === 'ship'`. To reach that page a user must open a contract that currently exists in the dataset and contains that ship. Therefore a user can only ever watch a ship that is **currently listed in some contract**. A ship with zero current listings cannot be added to the watchlist through any UI.

**Why this is more than a deferral.** The design's §3.2 rejects alternative (b) — "only allow adds from contract context" — with this exact rationale: *"users can't watch ships not currently listed, which is the core use case of a watchlist. Rejected."* The chosen backend (option a, ESI resolution) was picked specifically so *any* ship could be added — but the chosen **frontend** exposes no way to exercise that, so at the product level the shipped behavior has the identical limitation the design just called disqualifying. Then §8 defers the type-ahead search with the rationale *"adds-from-contract-context covers the browsing-driven flow,"* which directly contradicts §3.2(b)'s own analysis that browsing-context-only adds fail the core use case.

**Concrete failure scenario.** User wants a Caracal for ≤ 10M ISK. Right now there are zero Caracal contracts (or only ones far above 10M that still appear — fine). The pure "none listed at all" case: the user has no contract detail page to open, so there is no Watch button anywhere, so the ship cannot be added, so no future-availability notification will ever fire. The watchlist's headline value proposition ("be alerted when a ship you want but that isn't available becomes available") is unreachable for exactly the ships a user most wants to watch.

**Why it survived refutation.** For popular hulls some contract usually exists, so add-while-listed → set-max-price-later mostly works, which is why this is MAJOR not blocker. But it is disclosed inconsistently (deferral rationale contradicts the design's own reasoning) and §10 item 1 asserts "F006 Stories 1–5 … criteria met," overstating coverage of Story 1.

**Proposed fix.** Either (a) pull the deferred type-ahead ship-search add flow into M3 scope (the backend already resolves arbitrary `type_id` via ESI, so this is a frontend-only add path plus the public `universe/types` search — still zero-scope), or (b) keep it deferred but rewrite §3.2/§8/§10 to state honestly that M3 watchlists can only track currently-listed ships, drop the self-contradictory "covers the browsing-driven flow" claim, and soften §10's "criteria met" to "Story 1 partially met (adds limited to listed ships)."

---

### 2. [MINOR] F006 Criterion 2.1 (max-price input "when adding a ship") is not met — max price is a separate post-add step, yet §10 claims all F006 criteria are met

**Where:** spec §5 ("Optional max-price entry happens on the watchlist page after adding (keeps the detail-page control one-click)"); §10 item 1.

**The gap.** F006 Criterion 2.1 is explicit: *"When adding a ship, an optional input field for 'maximum price' is available."* The design makes add one-click with no price field and relocates max-price entry to the watchlist page afterward. The user *can* set a max price (Story 2's intent survives), but the criterion as worded — a price field *at add time* — is not satisfied. §10 item 1 nonetheless asserts F006 Stories 1–5 criteria are "met," which is inaccurate for 2.1.

**Concrete failure scenario.** An acceptance test written literally against Criterion 2.1 ("adding a ship exposes a max-price input") fails against the built UI; a reviewer trusting §10 would not expect that.

**Proposed fix.** Either add an optional inline max-price field to the detail-page Watch control (keeps 2.1 literally satisfied), or amend §10 to note Criterion 2.1 is intentionally deviated (add sets no price; price is set on the watchlist page) with the one-click rationale — turning a silent deviation into a recorded one.

---

### 3. [MINOR] Save Search 422s on a 1–2-character search term that is a valid `/contracts` URL state

**Where:** spec §4.5 (`SavedSearchParameters.search: str|None (min_length=3)`), §5 ("The persisted object is `search` minus `page`"), verified against `filters.ts` `parseContractSearch` (keeps `search` when `length > 0`) and `toApiQuery` (drops it when `< 3`).

**The gap.** The frontend treats a 1–2-char search as a legitimate `ContractSearch` state: `parseContractSearch` retains `search: "ab"` in URL state (the user is mid-typing / shared a URL), while `toApiQuery` omits it from the contracts request. So the user is validly "viewing results" (unfiltered by the short term) with `search: "ab"` live in state. If they click Save Search, the design persists `search` minus `page` — including `search: "ab"` — and `SavedSearchParameters.search`'s `min_length=3` rejects it with a 422 ("422 invalid params" per §4.5).

**Concrete failure scenario.** URL `/contracts?search=ab` → results render → authed user clicks Save Search → POST body `{search: "ab", …}` → 422. From the user's view, "I'm looking at results but can't save them," with an opaque validation error.

**Why it survived refutation.** It is reachable purely through documented frontend behavior (short search stays in URL by design), and the design specifies no client-side normalization of `search` before POST. Low frequency, hence MINOR.

**Proposed fix.** Have the Save Search control apply the same gate as `toApiQuery` — drop `search` (send `undefined`) when the trimmed term is `< MIN_SEARCH_LENGTH` — so a saved search never carries a term the backend will reject. Document this in §5.

---

### 4. [NIT] Per-user caps override F005's explicit "no hard limit for MVP" decision

**Where:** spec §3.5 / §4.3 (`MAX_SAVED_SEARCHES_PER_USER=100`, `MAX_WATCHLIST_ITEMS_PER_USER=200`, cap breach → 400) vs F005 §15 ("Max number of saved searches per user: No hard limit for MVP, but may be considered post-MVP based on usage").

**The gap.** F005 made an explicit MVP decision — no hard cap. The design imposes one now. It is disclosed (§3.5, appendix "still uncertain (1)") and flagged as a gut number, and 100/200 are generous enough that real users almost never hit them, so functional impact is negligible. But it is a direct override of a stated feature-spec decision and should be surfaced to Sam as such rather than framed only as a testing-discipline convenience.

**Proposed fix.** Keep the caps (they serve the bounded-growth testing discipline) but note in §8/§10 that they override F005 §15's "no hard limit for MVP," so the deviation is on the record for Sam's sign-off.

---

## Coverage matrix (every story/criterion)

| Feature | Story / Criterion | Design disposition |
|---|---|---|
| F005 | Stories 1–5, all criteria | Satisfied (save control, list, apply-via-navigate, two-step delete, rename PUT). ✓ |
| F006 | Story 1 (1.1, 1.2) | Satisfied only for currently-listed ships — **Finding 1**. |
| F006 | Story 2 (2.1, 2.2) | Price stored, but not entered "when adding" — **Finding 2**. |
| F006 | Story 3 (3.1–3.3) | Satisfied (watchlist page; live-market-data correctly out of scope). ✓ |
| F006 | Story 4, Story 5 | Satisfied (two-step remove; inline price/notes edit). ✓ |
| F007 | Story 1 (1.1, 1.2) | Satisfied (matcher, date-gated, `price <= max_price` or null). ✓ |
| F007 | Story 1 (1.3 re-notify/cooldown) | "may" — deferred with unblock condition (§8). ✓ |
| F007 | Story 2 | Feature-tagged future; deferred. ✓ |
| F007 | Story 3 (3.1, 3.4) | Satisfied (checkbox; bell + page). 3.2/3.3 future. ✓ |
| F007 | Story 4 (4.1–4.3) | Satisfied (page, mark-read single/all, contract deep-link). ✓ |

No **silent** drops found — every narrowed/deferred item appears in §2, §3, or §8, though Findings 1 and 2 are disclosed inconsistently with §10's coverage claim.
