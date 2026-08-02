# Feature Spec: Type-Aware Contract Browsing

**Feature ID:** F008
**Creation Date:** 2026-08-01
**Last Updated:** 2026-08-01
**Status:** Draft

## 0. Authoritative ESI & EVE SSO References (Required Reading for ESI/SSO Integration)
*   **EVE Online API (ESI) Swagger UI / OpenAPI Spec:** [https://esi.evetech.net/ui/](https://esi.evetech.net/ui/) - *Primary source for all ESI endpoint definitions, request/response schemas, and parameters.*
*   **ESI published OpenAPI document:** [https://esi.evetech.net/meta/openapi.json](https://esi.evetech.net/meta/openapi.json) - *The machine-readable spec. Every ESI field claim in this document was verified against it, not against prose documentation.*
*   **EVE Online Developers - ESI Best Practices:** [https://developers.eveonline.com/docs/services/esi/best-practices/](https://developers.eveonline.com/docs/services/esi/best-practices/)

---

## 1. Feature Overview (Required)

Hangar Bay ingests, enriches, and stores the entire public-contract corpus of The Forge — approximately 34,000 live contracts — and displays roughly 1.2% of it. The remaining contracts are reachable only through an unlabelled `ships_only` checkbox that produces a table whose columns describe ships, applied to rows that are mostly not ships.

This feature makes the non-ship corpus a designed product surface rather than a shipped side effect. It covers the data work that makes the corpus describable (persisting a taxonomy and the per-type fields currently discarded at ingestion) and the presentation work that makes it browsable (contract-type segmentation and type-appropriate summary rows).

The motivating analysis, including competitive evidence and the measured composition of the hidden corpus, is [`docs/superpowers/specs/2026-08-01-contract-coverage-gap-analysis.md`](../../docs/superpowers/specs/2026-08-01-contract-coverage-gap-analysis.md). Its recommendation §6 sequences this work; this spec is that recommendation's phases 2 and 3.

**What this feature does not change:** the ships-only default. `PRODUCT.md` states that non-ship contracts are reachable by explicit toggle and are "never the default noise." That decision stands. This feature makes the non-default view real; it does not promote it.

## 2. User Stories (Required)

*   Story 1: As a buyer, I want to browse contracts by type (item exchange, auction, courier), so that I see rows whose columns describe what I am looking at.
*   Story 2: As a blueprint buyer, I want to see runs, material efficiency, and time efficiency as first-class columns and filters, so that I can evaluate a blueprint copy without opening every contract.
*   Story 3: As a buyer of any item class, I want to filter by item category and group (e.g. Ship → Frigate, Module → Shield Booster), so that I can narrow a 34,000-row corpus to the class of thing I want.
*   Story 4: As an auction participant, I want to see the buyout price alongside the starting bid, so that I can tell whether an auction is worth watching.
*   Story 5: As a hauler, I want to browse courier contracts with route, reward, collateral, volume, deadline, and reward-per-jump, so that I can find jobs worth taking — a capability no tool in the EVE ecosystem currently offers.
*   Story 6: As a user looking at a multi-item contract, I want a compact composition summary in the row, so that I can judge a mixed lot without opening it.
*   Story 7: As a user, I want to know how fresh a row is and what the view does not cover, so that I can trust what I am seeing and correctly interpret an empty result.
*   Story 8: As a seller browsing want-to-buy contracts, I want items requested and items offered shown distinctly, so that I do not mistake one for the other.

## 3. Acceptance Criteria (Required)

**Story 1 — contract-type segmentation**
*   Criterion 1.1: The contracts view presents contract-type segmentation with a live result count per segment.
*   Criterion 1.2: Selecting a segment updates the list and is reflected in the URL, so the view is shareable and restorable.
*   Criterion 1.3: The default view remains ships-only, consistent with F002 Criterion 1.1 and `PRODUCT.md`.
*   Criterion 1.4: Courier contracts are excluded from the ships-only view by construction, because ESI returns no items for them and the ship flag is derived from items.
*   Criterion 1.5: `ships_only` and contract-type selection MUST NOT be independently settable into a combination that can never match. Ships-only combined with the courier segment is empty by construction (Criterion 1.4), so the UI must make that state unreachable — selecting the courier segment clears `ships_only`, and the change is visible to the user rather than silent. A guaranteed-empty result reachable by ordinary interaction is the same silent-filter-no-op defect Criterion 7.2 prohibits; this feature must not ship the defect it forbids.

**Story 2 — blueprint copy display and filtering**
*   Criterion 2.1: `runs`, `material_efficiency`, and `time_efficiency` are persisted from the ESI items payload.
*   Criterion 2.2: BPC rows display runs, ME, and TE.
*   Criterion 2.3: The existing `min_runs`/`max_runs` filter family operates against `runs` rather than `raw_quantity`, which cannot be populated from public ESI and is why the filter currently matches nothing. **Verifiable form:** given a seeded contract whose item has `runs = 10`, a request with `min_runs=5&max_runs=15` returns that contract, and `min_runs=11` does not. A test asserting only HTTP 200 and an empty list satisfies neither and must not be accepted as evidence — that is precisely the assertion shape that passed against this bug for its entire lifetime.
*   Criterion 2.4: A blueprint **original** is distinguishable from a copy. Per pitfall ESI-3, the public route omits `runs` entirely for originals rather than sending `-1`; absence must not be read as zero.

**Story 3 — taxonomy filtering**
*   Criterion 3.1: Item `category_id` and `group_id` are persisted.
*   Criterion 3.2: The filter rail offers a cascading category → group filter, where group options are scoped to the selected category.
*   Criterion 3.3: Group selection supports type-ahead, because some categories contain hundreds of groups.
*   Criterion 3.4: Both filters are URL-addressable.
*   Criterion 3.5: The filter's option list — which categories and groups exist, with display names — is served by the API, derived from the taxonomy actually present in the corpus. It is not hard-coded in the frontend and not assembled by the client. F002's market-group filter was deferred indefinitely because its option-source endpoint did not exist; this feature must not reproduce that hole while superseding it.

**Story 4 — auctions**
*   Criterion 4.1: Contract `buyout` is persisted and returned.
*   Criterion 4.2: Auction rows display starting bid and buyout, with buyout distinguished from a fixed price.
*   Criterion 4.3: Where no buyout is set, the row says so rather than rendering zero or blank.

**Story 5 — courier browsing**
*   Criterion 5.1: Contract `days_to_complete` is persisted.
*   Criterion 5.2: `end_location_name` is returned by the API. It is resolved at ingestion today but not served, so a destination currently reaches the client as a bare integer.
*   Criterion 5.3: Courier rows display origin → destination, reward, collateral, volume, and deadline.
*   Criterion 5.4: Reward per m³ is displayed and sortable.
*   Criterion 5.5: Jump counts are computed for all three ESI route preferences and stored.
*   Criterion 5.6: The user selects a route preference; the selection drives both the jumps column and the reward-per-jump sort.
*   Criterion 5.7: No unqualified "Jumps" label is ever rendered. The active preference is always visible.
*   Criterion 5.8: Contracts whose jump count cannot be determined are visibly distinct from contracts with a low reward-per-jump, in both display and sort order.
*   Criterion 5.9: The courier view states its coverage: origins within The Forge only.

**Story 6 — multi-item composition**
*   Criterion 6.1: A contract with more than one item displays a composition summary (counts by category) and total volume rather than a single item name.
*   Criterion 6.2: Single-item contracts continue to lead with the item.

**Story 7 — freshness and coverage honesty**
*   Criterion 7.1: `last_seen_at` is surfaced in the UI.
*   Criterion 7.2: A filter combination that cannot match — most importantly a region other than The Forge — produces an explanatory state distinguishing "not covered" from "nothing matched." This is the empty-state-or-explain invariant proposed in the gap analysis §2.2.

**Story 8 — want-to-buy symmetry**
*   Criterion 8.1: Items requested (`is_included = false`) and items offered are rendered distinctly and never merged into one list.

## 4. Scope (Required)

### 4.1. In Scope

**Data layer**
*   Persist item `category_id` and `group_id`. Both are already resolved during enrichment at `services/background_aggregation.py:783` and discarded at `:787`, where they are collapsed into a ship/not-ship string. This costs no additional ESI calls.
*   Persist item `runs`, `material_efficiency`, `time_efficiency`, and `item_id`.
*   Persist contract `buyout` and `days_to_complete`.
*   Persist `end_location_system_id`, and a `system_route_jumps` table keyed by (origin system, destination system, preference).

**API**
*   A `contract_type` filter and per-type counts.
*   Cascading `category_id` / `group_id` filters.
*   Serve `end_location_name`, `buyout`, `days_to_complete`, `runs`, ME, TE, jumps, and the derived ratios.
*   Make the `min_runs`/`max_runs`, ME, and TE filter families functional.

**Presentation**
*   Contract-type segmentation with counts.
*   Type-aware summary rows for five shapes: single-item exchange, multi-item, BPC, auction, courier.
*   Want-to-buy symmetry, `last_seen_at` surfacing, and coverage-honest empty states.

**Instrumentation**
*   Server-side logging of filter dimensions (contract type, category, group) on the existing contracts endpoint, via the structlog pipeline already shipping to Grafana Cloud. Dimensions only; no PII.

### 4.2. Out of Scope

Each exclusion carries its reason, so that a later reader can tell a decision from an oversight.

*   **Abyssal / mutated module display.** Committed near-future work with its own spec and plan. `item_id` is persisted in this feature specifically so that the follow-on requires no re-ingestion of the corpus. Abyssal items render as ordinary modules until then, which is honest; a partially-built roll-quality score would not be.
*   **Valuation and appraisal.** Parked per [`2026-07-26-m5-direction-options.md`](../../docs/superpowers/specs/2026-07-26-m5-direction-options.md). The gap analysis §3.2 is its display contract when it lands. No row in this feature asserts whether a price is good.
*   **"Jumps from my current location."** Requires a full solar-system route graph. The courier spike ([`2026-08-01-courier-route-jumps-spike.md`](../../docs/superpowers/specs/2026-08-01-courier-route-jumps-spike.md)) establishes that reward-per-jump does **not** need one, but this contextual column does — 8,490 possible origins rather than a bounded set of contract endpoints.
*   **Multi-region ingestion.** An explicit M5 non-goal. This feature states coverage honestly rather than lifting the limit.
*   **Market-group navigation tree.** Not foreclosed. See §15 for the measurement that would justify revisiting it.
*   **Changing the ships-only default.** `PRODUCT.md` stands.
*   **An MCP surface.** Downstream of M5 trust work per the gap analysis §7.

## 5. Key Data Structures / Models

New and changed columns. All new columns are nullable, because ESI omits most of them for contracts to which they do not apply, and absence must remain distinguishable from zero.

**`ContractItem`**

| Column | Type | Notes |
|---|---|---|
| `category_id` | int, nullable | Dogma category. Already resolved during enrichment; currently discarded. |
| `group_id` | int, nullable | Dogma group. Same. |
| `runs` | int, nullable | Present only on blueprint copies. Absent on originals — see ESI-3. |
| `material_efficiency` | int, nullable | Blueprints only. |
| `time_efficiency` | int, nullable | Blueprints only. |
| `item_id` | bigint, nullable | Join key to `/dogma/dynamic/items/{type_id}/{item_id}`. Written but unread until the abyssal follow-on. Requires `BigInteger`. |

**`Contract`**

| Column | Type | Notes |
|---|---|---|
| `buyout` | numeric, nullable | Auctions only. |
| `days_to_complete` | int, nullable | Couriers. Present on 115/115 sampled Forge couriers. |
| `end_location_system_id` | bigint, nullable | Mirrors the existing start-location resolution. |
| `jumps_shortest`, `jumps_secure`, `jumps_insecure` | int, nullable | Denormalized from `system_route_jumps` for sortability. NULL where an endpoint is a player structure. |

**`system_route_jumps`** (new)

| Column | Type | Notes |
|---|---|---|
| `origin_system_id` | bigint | Composite PK with the two below. |
| `destination_system_id` | bigint | |
| `preference` | enum/text | `shortest` \| `secure` \| `insecure`. |
| `jumps` | int | |
| `computed_at` | timestamptz | Route geography is static; this exists for auditability, not expiry. |

**Retained but unused columns.** `status`, `date_completed`, `raw_quantity`, and `is_singleton` remain, and this feature adds no filter or display that reads them. They can only ever be NULL under public ingestion, and are exactly what the authenticated character and corporation contract routes return. The reasoning is recorded in the gap analysis §4.2 and is not reopened here. Likewise `ContractItem.market_group_id` and `EsiMarketGroupCache` are retained but are not the taxonomy axis (§15).

## 6. API Endpoints Involved

### 6.1. Consumed ESI API Endpoints

| Endpoint | Use | Notes |
|---|---|---|
| `GET /contracts/public/{region_id}` | Existing | Source of `buyout`, `days_to_complete`. |
| `GET /contracts/public/items/{contract_id}` | Existing | Source of `runs`, ME, TE, `item_id`. |
| `GET /universe/groups/{group_id}` | Existing | Already called; `category_id` read and discarded. |
| `GET /universe/categories/{category_id}` | New | For display names. Small, bounded, permanently cacheable. |
| `GET /universe/stations/{station_id}` | Existing | Extended to end locations. |
| `GET /route/{origin}/{destination}?flag=` | **New — see the compatibility-date constraint below** | Jump counts. |

**`/route/` and ESI-4 — a hard constraint, not a note.**

Hangar Bay sends no `X-Compatibility-Date` header and therefore receives the oldest published date, `2020-01-01` (pitfall ESI-4). At that date `/route/` is a `GET` returning a bare array. At compatibility date `2025-09-30` and later it becomes a **`POST`** with a JSON body, renamed preference values (`Shorter` / `Safer` / `LessSecure`), an object response envelope, and no server-side cache. The old shape returns **HTTP 404** at the newer date. This was verified live by the courier spike.

Consequences this spec requires:
1. This feature ships correctly today at the current floor, using the `GET` form. No header change is needed to build it.
2. `/route/` **must** be added to the ESI drift-monitor manifest (`app/backend/tools/esi_spec_monitor/manifest.py`). This is not optional. Without it, the day the floor moves is the day couriers 404 in production.
3. The separate ESI-4 pinning work and this feature are coupled. Whichever lands second must handle both `/route/` shapes or pin below `2025-09-30`. The implementation plan must state which.
4. `security_penalty` (available only on the newer shape) must never be sent. Measured behaviour is non-monotonic — 0 → 45 jumps, 5–20 → 11, 25+ → 45 — and the spec documents it only as "strictness of the path preference." Pin to default; never expose it.

### 6.2. Exposed Hangar Bay API Endpoints

Extensions to `GET /contracts/`, not a new endpoint. Routers mount bare; the `/api/v1` prefix belongs to the proxy and edge (pitfall PROXY-1).

New query parameters: `contract_type`, `category_id`, `group_id`, `route_preference`.
New response fields: `end_location_name`, `buyout`, `days_to_complete`, `jumps` (resolved for the active preference), `reward_per_jump`, `reward_per_volume`, per-item `runs` / `material_efficiency` / `time_efficiency` / `category_id` / `group_id`.
New sortable fields: `reward_per_jump`, `reward_per_volume`, `days_to_complete`, `buyout`.

**Per-type counts.** Segment labels carry counts, and those counts MUST reflect every other active filter — a count that ignores the search box or the price range is a lie in a numeral, worse than no count. The requirement is therefore: one round trip returns the page plus all segment counts under the active filter set, not one query per segment and not an unfiltered total. A grouped aggregate over the filtered set, returned in the list envelope, satisfies this; the plan may choose otherwise but must meet the same bar and must state the query shape it settled on.

**Taxonomy option list.** A companion endpoint returns the categories and groups present in the corpus with their display names, for Criterion 3.5. Names come from `/universe/categories/{id}` and the group records already fetched during enrichment, cached rather than re-resolved per request.

After any change here: `pdm run export-openapi`, then `npm run generate:api`, both regenerated artifacts committed in the same PR.

## 7. Workflow / Logic Flow

**Ingestion.** Unchanged in shape. Enrichment additionally writes the taxonomy and blueprint fields it already holds. Location resolution extends to end locations. A route-resolution step then runs over the distinct (origin system, destination system) pairs present in courier rows: pairs already in `system_route_jumps` are skipped, and only genuinely new pairs reach ESI. Measured, The Forge's 115 couriers collapse to 39 distinct system pairs — 117 route calls across three preferences, 8.4 seconds cold including station resolution, and zero calls in steady state.

**Backfill of existing rows.** New columns land NULL on the ~34,000 contracts already stored, and nothing in normal operation revisits an already-enriched contract. The mechanism for this exists and must be used: `ENRICHMENT_VERSION` in `background_aggregation.py` is documented as "bump to re-queue every contract for re-enrichment after an enrichment-logic fix." This feature MUST bump it, for a reason beyond tidiness — §4.2 promises that persisting `item_id` spares the abyssal follow-on a corpus re-ingest, and without a backfill that promise is false for every contract already in the database.

The bump carries a documented operational cost, recorded here so it is planned rather than discovered: the next run becomes a one-off full-corpus resweep taking roughly 80 minutes at a ~46,000-contract corpus. That outlives the aggregation lock TTL, so the `Aggregation lock token mismatch on release` warning at its end is **expected on that run** and is not a concurrency incident. The runbook at the constant's definition governs; the deploy must not be repeated while the resweep is in flight.

**Query.** `contract_type` and taxonomy filters compose with the existing filter set. Derived ratios are computed in SQL for sortability.

**Render.** The active contract-type segment selects a column set; the row renderer is shared. Column definitions live in their own module rather than inside `ContractTable.tsx`, which today hard-codes a five-column array and would otherwise become the file that does too much.

## 8. UI/UX Considerations

*   **Type-aware rows, shared frame.** One table component, five column sets. Adding the abyssal shape later must not require touching the frame.
*   **Cascading taxonomy filter.** Category first, then group scoped to that category with type-ahead. A flat group list is not viable: the Module category alone contains hundreds of groups.
*   **Route preference is a visible control**, not a hidden default. The measured spread justifies this: Jita → Amarr is 11 / 45 / 40 jumps by preference, a 4.1× range; across real Forge couriers, 32% have `secure` at ≥ 2× `shortest`, and 3 of the top-10 reward-per-jump leaders reorder when the preference changes.
*   **Label `secure` as "Prefer high-sec", never "Safe".** Verified: to a null-sec destination, `secure` returned an 81-jump route still crossing 23 low/null systems. "Safe" would be a false claim.
*   **Unknown is not zero.** Roughly 9–10% of couriers have a player-structure endpoint that cannot be resolved without ACL-scoped tokens. Those rows must read as "unknown" and must not silently sort as if they were poor value.
*   **Full ISK figures and relative expiry are retained** — both are existing advantages over the surveyed competition.
*   **Coverage statements over silent empty results.** Selecting an uningested region must explain, not return an empty table.

## 9. Error Handling & Edge Cases (Required)

*   **Divide by zero on jumps.** A courier between two stations in the same system has zero jumps. Zero same-system couriers appeared across 250 sampled contracts, but nothing prevents one. Reward per jump must guard.
*   **Divide by zero on volume.** Same guard for reward per m³.
*   **Blueprint originals.** `runs` is absent, not `-1`, on the public route (ESI-3). Filters and display must treat absence as "not a copy," never as zero runs.
*   **`is_blueprint_copy` absence.** ESI omits the flag for non-copies; the filter must treat NULL as not-a-copy. Fixed previously; the taxonomy work must not regress it.
*   **Response-shape mismatch in the ESI client.** `_get_esi_object` raises on any non-dict response, and the legacy `GET /route/` returns a bare array. The paginated helper is also unusable — it flattens a dict into its keys. A third, list-shaped helper is required; neither existing helper can be reused.
*   **Unresolvable locations.** Player structures stay NULL end-to-end and surface as "unknown."
*   **Partial enrichment.** The existing `ENRICHMENT_INCOMPLETE` semantics extend to the new fields: a contract whose taxonomy failed to resolve must not be stamped `COMPLETED`.
*   **Serialization strictness.** A non-optional schema field over a nullable column fails the entire page, not one row, because `PaginatedResponse` validates every item. Every new field is optional in the response schema unless it is provably non-null for every row.

## 10. Security Considerations

*   No new authentication surface. All consumed endpoints are public and unauthenticated.
*   No PII in instrumentation. Filter dimensions only — no user identifiers, no free-text search contents.
*   New filter parameters are typed and bounded by Pydantic, reaching the database only through the ORM.
*   The route-resolution fan-out reuses the existing bounded-concurrency helper and the NPC-station-ID guard that avoids spending ESI error budget on requests guaranteed to 401.

## 11. Performance Considerations

*   Route resolution is bounded by distinct system pairs, not contract count, and is cached permanently. Steady state is zero ESI calls. The `/route/` rate limit is 3,600 per 15 minutes; the working set uses well under 1% of it.
*   Jump counts are denormalized onto contract rows so that reward-per-jump sorts in SQL rather than in the application.
*   New filter columns (`contract_type`, `category_id`, `group_id`) require indexes; the plan specifies which, informed by the existing index set.
*   Per-type counts must not degenerate into one query per segment.

## 12. Accessibility Considerations

*   Contract-type segmentation must be keyboard-navigable and expose its selected state to assistive technology.
*   The cascading filter must announce that changing category changes the available groups.
*   "Unknown jumps" must be conveyed textually, not by colour or a dash alone.
*   Existing a11y tests (`components/a11y.test.tsx`) extend to the new controls.

## 13. Internationalization Considerations

**The frontend has no internationalization today** — no i18n library, no message catalogue, no externalized strings anywhere in `app/frontend/web/src/`. This was checked rather than assumed.

Consequently this feature introduces literal English strings, consistent with every existing view. It does not introduce an i18n framework, which would be a project-wide decision far outside this scope. What it does do is avoid making a future migration worse: user-facing strings stay in the component layer rather than being embedded in the new column-definition modules, so a later extraction has one place to look. ESI-sourced names (categories, groups, stations) are served in English by ESI and would not be translated in any case.

## 14. Dependencies

*   **F001** — the ingestion pipeline this feature extends.
*   **F002** — the browsing surface this feature extends, and whose market-group mechanism it supersedes (§15).
*   **ESI-4 / `/route/`** — the compatibility-date coupling in §6.1.
*   **No dependency on M5, appraisal, or multi-region ingestion.** This feature is buildable today.

## 15. Notes / Open Questions

### 15.1. Reconciliation: the F002 market-group conflict

F002 §221 and criteria 4.3–4.5 place a market-group category filter in MVP scope, backed by a `GET /ships/market_groups` endpoint sourced from ESI `/v1/markets/groups/`. The M1 frontend design deferred it, correctly, because that endpoint does not exist. The conflict was never resolved.

**Resolution: F008 supersedes the mechanism and preserves the requirement.** F002 asks to filter by "broad ship market groups/categories (e.g. Frigate, Cruiser)." Those are dogma **group** names under the Ship category — the same group records enrichment already fetches in order to compute the ship flag. The user-facing requirement is met; the mechanism changes from market groups to dogma category/group.

**The deciding reason is the abyssal follow-on.** Abyssal and mutated items are off-market by construction and therefore have no market group at all. A taxonomy built on market groups would require a second taxonomy, or would leave the largest non-ship cluster unfilterable, exactly when the follow-on lands. Dogma category/group is the only axis that spans both this feature and its committed successor.

**What the market-group axis would genuinely have been better at**, recorded so the trade-off is not lost: it is a browsing hierarchy CCP built for buyers, with real depth (`EsiMarketGroupCache.parent_group_id` exists for it), whereas dogma gives two levels with a very wide second level. The cascading filter in §8 is the mitigation.

**A measurement the plan should take, because it could partially reopen this.** The 87%-NULL market-group figure in the gap analysis §4.1 was measured across all non-ship items, a population dominated by abyssal items — the cluster this feature defers. Coverage among the items this feature actually displays (blueprints, ordinary modules, injectors, containers) may be far higher. If it is, that does **not** change the filter axis, for the reason above; but it would make a market-group navigation tree a legitimate later enhancement layered on top. The measurement is cheap and should be recorded either way.

**Action on F002 itself:** a pointer is added to F002 noting that criteria 4.3–4.5 are superseded here, with a link. Leaving F002 silently false is the failure mode this avoids.

### 15.2. Policy: courier contracts

No courier policy exists anywhere in the repository. Their exclusion from item fetching is an implementation artifact — ESI returns no items for couriers — never a decision. This section is that decision.

**Couriers are a first-class contract type in this feature**, with their own columns and their own sorts. They are not purchases: a courier contract is a job offer, and its audience is haulers rather than buyers. Nothing in the surveyed ecosystem browses them, which makes this the most differentiated surface in the feature and the least validated.

**Three limits are accepted deliberately:**
1. **Coverage is stated, not hidden.** Only The Forge is ingested, so this is "couriers originating in The Forge" — 115 contracts. That is a thin tab, and it is a thin tab honestly labelled rather than an implied national market.
2. **No unqualified jump count**, for the measured reasons in §8.
3. **No "jumps from my location"**, which needs the route graph (§4.2).

**Open question, non-blocking:** the recommended default route preference is `secure`, on the reasoning that couriers carry collateral the hauler forfeits on loss, so the risk-adjusted figure is the actionable one. The supporting evidence that established freight services quote ISK per jump *segmented by security band* comes from a web-search summary rather than a primary rate card, and is the weakest-sourced claim in the spike. It is a one-line default and does not block implementation; one confirming look at a live freight rate page before ship would settle it.

### 15.3. On the evidence base

The case for this feature is supply-side: the data is already fetched, enriched, and stored, and the competitive field is empty. There is no demand evidence — no user request for BPC or courier browsing, no traffic data, no search terms. The application has one user today and has not been advertised, so no adoption metric could produce signal at this stage.

This is recorded rather than resolved. The instrumentation in §4.1 exists so that the question becomes answerable later; it is deliberately not framed as a success criterion now.

## 16. AI Implementation Guidance

### 16.1. Read before implementing

`docs/pitfalls/implementation-pitfalls.md` and `docs/pitfalls/testing-pitfalls.md` in full. Directly load-bearing here: **ESI-3** (originals omit `runs`), **ESI-4** (compatibility date and `/route/`), **FASTAPI-1** (`Annotated[Model, Query()]`, never bare `Depends`, for GET filter models), **PROXY-1** (no `/api/v1` in FastAPI), **SQLA-1**, **ENV-2/ENV-3** (every backend `.py` save under reload wipes the database — batch edits), **TEST-14** (`tests/api/test_contracts.py` carries a file-level `pytest.mark.vcr`; new tests there replay cassettes and can pass with the behaviour deleted — use `test_contract_filters.py`).

### 16.2. Critical logic points

*   Taxonomy persistence is an eight-line change at the point where `category_id` is already in scope (`background_aggregation.py:783`). Resist the urge to add an ESI call.
*   The route-resolution step keys on distinct system pairs. Keying on contracts would multiply calls by roughly 3× for no benefit.
*   A new list-shaped ESI helper is required for `/route/` (§9). Do not widen `_get_esi_object` to accept lists — its dict assertion protects every other caller.
*   Every new response field is optional unless provably non-null for all rows (§9).

### 16.3. Testing focus

TDD is mandatory for all production code here. Specific traps this feature is prone to:

*   **Fixtures must carry the production data shape.** Backend fixtures previously hand-wrote three columns ingestion never writes, which gave dead filters green tests. Any fixture asserting on `runs`, `is_blueprint_copy`, or taxonomy must reflect what ESI actually sends — including omitting `runs` on originals.
*   **Assert the filters return rows.** The defect class this feature is fixing is filters that match nothing. A test asserting a 200 and an empty list would have passed against every one of those bugs.
*   **Do not write new tests into `tests/api/test_contracts.py`** (TEST-14).
*   **No assertions inside `if data["items"]:`** without seeding a fixture — a previously shipped test never executed its assertion block.
*   **Mutation-check the load-bearing tests.** Break the behaviour, confirm the test goes red, revert. A test that stays green under mutation is a finding, not a formality — restore from a file copy rather than `git checkout --`, which would discard uncommitted work and produce false evidence.
*   Frontend fixtures must not carry absolute past expiry dates; the future-clock lane exists because an entire suite silently rendered "Expired" and nothing failed.
