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

Hangar Bay ingests, enriches, and stores the entire public-contract corpus of The Forge and displays a small fraction of it. **The measured figures, with their populations stated** — because two different denominators are in circulation and mixing them produces a wrong percentage: the *live* Forge corpus is ~33,900 contracts, of which ~411 are ship-flagged (~1.2%); the *stored* table is larger (~46,000–51,000, including contracts no longer live) and the ships-only default view returns ~622 rows against it. Any single percentage quoted without saying which population it is over is unreliable, and the plan should re-measure rather than inherit these.

The non-ship remainder is reachable only by clearing the "Ships only" checkbox, which yields the same six-column table (`Ship / Contract`, `Type`, `Price`, `Location`, `Time left`, `Issued`) applied to rows that are mostly not ships. The control is labelled; what is missing is any design for what it reveals.

This feature makes the non-ship corpus a designed product surface rather than a shipped side effect. It covers the data work that makes the corpus describable (persisting a taxonomy and the per-type fields currently discarded at ingestion) and the presentation work that makes it browsable (contract-type segmentation and type-appropriate summary rows).

The motivating analysis, including competitive evidence and the measured composition of the hidden corpus, is [`docs/superpowers/specs/2026-08-01-contract-coverage-gap-analysis.md`](../../docs/superpowers/specs/2026-08-01-contract-coverage-gap-analysis.md). Its recommendation §6 sequences this work; this spec is that recommendation's phases 2 and 3.

**What this feature does not change:** the ships-only default. `PRODUCT.md` states that non-ship contracts are reachable by explicit toggle and are "never the default noise." That decision stands. This feature makes the non-default view real; it does not promote it.

## 2. User Stories (Required)

*   Story 1: As a buyer, I want to browse contracts by type (item exchange, auction, courier), so that I see rows whose columns describe what I am looking at.
*   Story 2: As a blueprint buyer, I want to see runs, material efficiency, and time efficiency as first-class columns and filters, so that I can evaluate a blueprint copy without opening every contract.
*   Story 3: As a buyer of any item class, I want to filter by item category and group (e.g. Ship → Frigate, Module → Shield Booster), so that I can narrow a corpus of tens of thousands of contracts to the class of thing I want.
*   Story 4: As an auction participant, I want to see the buyout price alongside the starting bid, so that I can tell whether an auction is worth watching.
*   Story 5: As a hauler, I want to browse courier contracts with route, reward, collateral, volume, deadline, and reward per m³, so that I can find jobs worth taking — a capability no tool in the EVE ecosystem currently offers. (Reward *per jump*, the other ratio haulers sort on, is deferred to the follow-on in §4.2.)
*   Story 6: As a user looking at a multi-item contract, I want a compact composition summary in the row, so that I can judge a mixed lot without opening it.
*   Story 7: As a user, I want to know how fresh a row is and what the view does not cover, so that I can trust what I am seeing and correctly interpret an empty result.
*   Story 8: As a seller browsing want-to-buy contracts, I want items requested and items offered shown distinctly, so that I do not mistake one for the other.

## 3. Acceptance Criteria (Required)

**Story 1 — contract-type segmentation**
*   Criterion 1.1: The accepted `contract_type` values are enumerated explicitly and cover **every** value ESI can emit, not only the three with designed row shapes. The full set, confirmed against the committed ESI spec snapshot, is `item_exchange`, `auction`, `courier`, `loan`, `unknown`. A corpus contract whose type is outside the designed set MUST remain reachable and counted — silently dropping it would contradict §1's claim that this feature makes the whole corpus browsable. The plan states whether the extras get their own segment, fold into an "other" segment, or appear only when no type filter is active; it may not leave them unhandled.
*   Criterion 1.2: `loan` and `unknown` contracts are **item-less by construction, exactly like couriers**, and inherit the same handling. Ingestion skips item fetching for every type outside `item_exchange` and `auction` (`background_aggregation.py:637`), so these contracts never enter `processed_contract_ids`, remain `PENDING_ITEMS`, and keep `enrichment_version = 0` indefinitely. Two consequences the plan must handle rather than trip over: they are excluded from the ships-only view by the same construction as couriers (Criterion 1.6), and §7 step 4's "verified non-NULL rate on item-level columns" can never cover them, so the verification query must scope to types that actually receive items.
*   Criterion 1.3: The contracts view presents contract-type segmentation with a live result count per segment. **Counts are of distinct contracts**, not of joined item rows — a multi-item contract counts once. A fixture with at least one multi-item contract is required to make this assertion meaningful.
*   Criterion 1.4: Selecting a segment updates the list and is reflected in the URL, so the view is shareable and restorable.
*   Criterion 1.5: The default view remains ships-only, consistent with F002 Criterion 1.1 and `PRODUCT.md`.
*   Criterion 1.6: Courier contracts — and `loan` and `unknown` contracts, per Criterion 1.2 — are excluded from the ships-only view by construction, because ESI returns no items for them and the ship flag is derived from items.
*   Criterion 1.7: `ships_only` and contract-type selection MUST NOT be independently settable into a combination that can never match. Ships-only combined with the courier segment is empty by construction (Criterion 1.6), so the UI must make that state unreachable — selecting the courier segment clears `ships_only`, and the change is visible to the user rather than silent. A guaranteed-empty result reachable by ordinary interaction is the same silent-filter-no-op defect Criterion 7.2 prohibits; this feature must not ship the defect it forbids.
*   Criterion 1.8: **What a segment count reads while `ships_only` is active is specified, not left to the implementer.** Because ships-only excludes item-less types entirely, the courier segment's count under that filter is either 0 (the filter honestly applied) or its unfiltered total (the count answering "what is behind this tab"). Both are defensible and they are visibly different; two implementers will otherwise ship opposite behavior. The plan picks one and states it. Given Criterion 1.7 makes the combined state unreachable anyway, the count's job here is to advertise what switching would reveal.

**Story 2 — blueprint copy display and filtering**
*   Criterion 2.1: `runs`, `material_efficiency`, and `time_efficiency` are persisted from the ESI items payload.
*   Criterion 2.2: BPC rows display runs, ME, and TE.
*   Criterion 2.3: The existing `min_runs`/`max_runs` filter family operates against `runs` rather than `raw_quantity`, which cannot be populated from public ESI and is why the filter currently matches nothing. **Verifiable form:** given a seeded contract whose item has `runs = 10`, a request with `min_runs=5&max_runs=15` returns that contract, and `min_runs=11` does not. A test asserting only HTTP 200 and an empty list satisfies neither and must not be accepted as evidence — that is precisely the assertion shape that passed against this bug for its entire lifetime.
*   Criterion 2.4: A blueprint **original** is distinguishable from a copy. Per pitfall ESI-3, the public route omits `runs` entirely for originals rather than sending `-1`; absence must not be read as zero.
*   Criterion 2.5: The `min_me` / `max_me` / `min_te` / `max_te` filter families operate against `material_efficiency` and `time_efficiency`. All four are inert today (`schemas/contracts.py:165-200`), not only the minimums. **These fail more dangerously than the runs filter and need the harsher test.** Measured against live production on 2026-08-01: `min_me=10` returns **15,592 contracts — the identical count to the same query with no ME filter at all**. The filter is not merely inert, it is invisible: it returns a large, plausible, wrong result set that reads as a successful answer, where `min_runs=5` at least returns zero and looks broken. **Verifiable form:** given seeded items at ME 0 and ME 10, `min_me=10` returns only the latter, and the result count is strictly less than the unfiltered count for the same query. A test that asserts only "returns some rows" passes against the current defect and must not be accepted.

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
*   Criterion 5.5: `end_location_system_id` is resolved and persisted, using the same station-resolution path that already handles start locations. **Nothing in this feature reads it.** It exists so that the reward-per-jump follow-on (§4.2) needs no second full-corpus resweep — the same reasoning that puts `item_id` in this feature for the abyssal follow-on.
*   Criterion 5.6: Reward per m³ is the courier normalization metric in v1, and the view does not display or imply a distance-based metric it cannot yet compute.
*   Criterion 5.7: The courier view states its coverage: origins within The Forge only.

**Story 6 — multi-item composition**
*   Criterion 6.1: A contract with more than one item displays, in place of a single item name: **a per-dogma-category breakdown** (e.g. `3 modules · 1 blueprint · 2 other`) and total volume. The breakdown counts the number of distinct item **rows** per category — not distinct type IDs, and not summed quantities. These produce materially different summaries and the ambiguity must not survive into implementation: a contract of 100 identical drones in one row reads as `1 drone`, not `100 drones`. If summed quantity is wanted it is a separate, separately-labelled figure. A bare `4 items · 12,000 m³` does **not** satisfy this criterion — the category breakdown is the point, because it is what lets a reader judge a mixed lot without opening it.
*   Criterion 6.2: Single-item contracts continue to lead with the item.
*   Criterion 6.3: Composition counts are computed over **offered** items only. Requested items (`is_included = false`) are summarized separately and never merged into the same figure, consistent with Criterion 8.1.
*   Criterion 6.4: The list response stops inlining full item lists, and the detail response bounds its own worst case. Live production contains a single contract row measuring **55.7 KB** serialized, with multi-item contracts of 244 and 143 items in the corpus — a tail two orders of magnitude past the typical row.

    **This is a breaking change to shipped behavior, not a description of it.** `ContractSchema.items` is inlined on *both* list and detail today, eager-loaded at `contract_service.py:272` and `:294`, and the frontend list row genuinely depends on it: `contractIsBpc` iterates `contract.items` (`ContractTable.tsx:36`) and `primaryLabel` reads `items[].type_name` / `category` / `is_included` (`format.ts:78`). Dropping `items` from the list response therefore requires the two replacement fields named in §4.1 — a contract-level blueprint-copy flag and a server-computed primary label — plus the composition summary of 6.1. The plan must land those before or with the removal, must regenerate the client chain, and must treat this as the serialization-contract change it is.

**Story 7 — freshness and coverage honesty**
*   Criterion 7.1: `last_seen_at` is surfaced in the UI, which requires adding it to the response schema — it is computed today and returned by nothing.
*   Criterion 7.2: A filter combination that cannot match — most importantly a region other than The Forge — produces an explanatory state distinguishing "not covered" from "nothing matched." This is the empty-state-or-explain invariant proposed in the gap analysis §2.2.
*   Criterion 7.3: **Coverage is data, not a hard-coded constant.** The API exposes which regions are actually covered; the client does not embed "The Forge" as a literal. Without this the implementation must either hard-code the region (which silently becomes wrong the day coverage expands) or infer coverage from an empty result (which misclassifies a genuinely empty covered region as uncovered). Both failure modes are the defect Criterion 7.2 exists to prevent, reintroduced one layer down.
*   Criterion 7.4: The coverage source is named explicitly, because the two candidates disagree exactly when it matters. `Settings.AGGREGATION_REGION_IDS` (`core/config.py:61`, default `[10000002]`) states **intent**; `SELECT DISTINCT start_location_region_id` states **reality**. They diverge for the entire ingestion window after a coverage change — which is precisely the situation Criterion 7.3 exists for. The plan picks one, or reports both with distinct meanings ("configured" versus "has data"), and must also name a source for region *display names*, which neither candidate provides.

**Story 8 — want-to-buy symmetry**
*   Criterion 8.1: Items requested (`is_included = false`) and items offered are rendered distinctly and never merged into one list.

## 4. Scope (Required)

### 4.1. In Scope

**Data layer**
*   Persist item `category_id` and `group_id`. **Both values are already in hand during enrichment and neither is stored.** `group_id` arrives on the type payload and is used at `background_aggregation.py:771-775` to fetch group records, then dropped by omission; `category_id` is read off that group record at `:783` purely to compare against `SHIP_CATEGORY_ID`, and `:787` stores only the derived `"ship"`-or-NULL string. Persisting them adds columns and assignments, **not** ESI calls.
*   Persist item `runs`, `material_efficiency`, `time_efficiency`, and `item_id`.
*   Persist contract `buyout` and `days_to_complete`.
*   Persist `end_location_name` (required by Criterion 5.2; the name is already resolved and discarded).
*   Persist `end_location_system_id` (write-only in this feature; see Criterion 5.5). This one requires widening `_npc_station_ids` to collect end locations — it reads only start locations today.
*   Serve a contract-level blueprint-copy flag and a primary display label, so the list response no longer has to inline every item (Criterion 6.4).

**API**
*   A `contract_type` filter and per-type counts.
*   Cascading `category_id` / `group_id` filters.
*   Serve `end_location_name`, `buyout`, `days_to_complete`, `runs`, ME, TE, and the derived ratios that need no route data.
*   Make the `min_runs`/`max_runs`, ME, and TE filter families functional.

**Presentation**
*   Contract-type segmentation with counts.
*   Type-aware summary rows, modelled as two orthogonal axes rather than a flat list of shapes — segment (item exchange, auction, courier) crossed with row body (single item, multi-item), with blueprint columns as a refinement of the single-item body. §8 defines this precisely and it is the definition that governs.
*   Want-to-buy symmetry, `last_seen_at` surfacing, and coverage-honest empty states.

**Instrumentation**
*   Server-side logging of filter dimensions (contract type, category, group) on the existing contracts endpoint, via the structlog pipeline already shipping to Grafana Cloud. Dimensions only; no PII.

### 4.2. Out of Scope

Each exclusion carries its reason, so that a later reader can tell a decision from an oversight.

*   **Abyssal / mutated module display.** Committed near-future work with its own spec and plan. `item_id` is persisted in this feature specifically so that the follow-on requires no re-ingestion of the corpus. Abyssal items render as ordinary modules until then, which is honest; a partially-built roll-quality score would not be.
*   **Valuation and appraisal.** Parked per [`2026-07-26-m5-direction-options.md`](../../docs/superpowers/specs/2026-07-26-m5-direction-options.md). The gap analysis §3.2 is its display contract when it lands. No row in this feature asserts whether a price is good.
*   **Courier reward-per-jump, and the jumps column it sorts on.** Committed near-future work with its own plan, alongside the abyssal follow-on. It is deferred *despite* being cheap in isolation — the courier spike ([`2026-08-01-courier-route-jumps-spike.md`](../../docs/superpowers/specs/2026-08-01-courier-route-jumps-spike.md)) measured the entire live Forge courier population at 161 ESI calls and 8.4 seconds cold, needing per-pair route lookups rather than a route graph.

    Three reasons it is still not in v1. It is the largest block of net-new machinery in the feature (a route-cache table, a list-shaped ESI client helper that neither existing helper can substitute for, denormalized sort columns, and per-system security resolution for tier disclosure) while serving 115 contracts, 0.34% of the corpus. It is the **only** part of this feature that depends on the ESI compatibility date — `GET /route/` becomes a `POST` and the old shape 404s at `2025-09-30`, so keeping it here would force F008 and the open ESI-4 pinning decision to be sequenced against each other for no benefit. And its honesty requirements (per-row security-tier disclosure, an unqualified "Jumps" label being forbidden, ESI's `secure` being an upper bound rather than the true high-sec distance) are substantial enough to deserve their own review rather than riding in as a subsection.

    **The seam is deliberate.** Everything ingestion-side stays in v1: `end_location_system_id` is resolved and stored now (Criterion 5.5), so the follow-on is purely route lookups plus presentation and needs no second full-corpus resweep. What the follow-on must additionally do — including adding `GET /route/` to the ESI drift-monitor manifest — is recorded in §15.2 and in the spike.

*   **"Jumps from my current location."** A genuinely different problem from reward-per-jump, and out of scope for both this feature and its follow-on. It needs a full solar-system route graph: 8,490 possible origins rather than a bounded set of fixed contract endpoints.
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
| `end_location_name` | text, nullable | **Genuinely cheap — one column and one mapping line.** `start_location_name` is a stored column (`models/contracts.py:67`) populated from the resolved-name map at `background_aggregation.py:200`, and the end location is already in that map: `_collect_resolvable_ids` unions `end_location_ids` into the name-resolution set at `background_aggregation.py:97`. The name is resolved today and simply never written. |
| `end_location_system_id` | int, nullable | **Not cheap in the same way, and the two must not be conflated.** System resolution runs through a *different* function from name resolution: `_npc_station_ids` (`background_aggregation.py:150-158`) reads **only** `start_location_id` — its docstring says so outright. It must be widened to collect end locations before this column can be populated. Typed `Integer` to match its sibling `start_location_system_id` (`models/contracts.py:56`); solar system IDs fit int32. Written but unread in this feature (Criterion 5.5). NULL where the endpoint is a player structure — measured at **6 of 115 Forge couriers (~5%)** for the end location specifically; the ~9–10% figure in the spike is the *both-endpoints* rate and does not apply to this column alone. |

**A taxonomy name cache** (new, or `EsiMarketGroupCache` repurposed — the plan chooses and states which). Criterion 3.5 requires a served option list with display *names*, and §5's ID columns alone cannot produce them: group payloads are fetched transiently during enrichment and discarded, and no dogma category or group cache exists. Without a durable name source the companion endpoint in §6.2 has nothing to serve, which is exactly how F002's market-group filter died. Category names come from `/universe/categories/{id}`; group names from the group records enrichment already fetches.

**Retained but unused columns.** `status`, `date_completed`, `raw_quantity`, and `is_singleton` remain, and this feature adds no filter or display that reads them. **They are not uniformly NULL, and the distinction matters for anyone writing a filter against them:** `status` is `nullable=False` and holds the placeholder `"unknown"`, and `is_singleton` is `nullable=False` and takes its mapping default of `False`. Only `date_completed` and `raw_quantity` are actually NULL. So two of the four hold *values that look real and are meaningless* — a worse trap than NULL, and the reason `is_bpc=false` and `min_runs` both silently matched nothing. All four are exactly what the authenticated character and corporation contract routes return. The reasoning is recorded in the gap analysis §4.2 and is not reopened here. Likewise `ContractItem.market_group_id` and `EsiMarketGroupCache` are retained but are not the taxonomy axis (§15).

## 6. API Endpoints Involved

### 6.1. Consumed ESI API Endpoints

| Endpoint | Use | Notes |
|---|---|---|
| `GET /contracts/public/{region_id}` | Existing | Source of `buyout`, `days_to_complete`. |
| `GET /contracts/public/items/{contract_id}` | Existing | Source of `runs`, ME, TE, `item_id`. |
| `GET /universe/groups/{group_id}` | Existing | Already called; `category_id` read and discarded. |
| `GET /universe/categories/{category_id}` | New | For display names. Small, bounded, permanently cacheable. |
| `GET /universe/stations/{station_id}` | Existing | Extended to end locations, to populate `end_location_system_id`. |

**No new ESI endpoint is consumed by this feature.** `/route/` belongs to the deferred reward-per-jump work (§4.2), and moving it out is one of the reasons for that deferral: it is the only ESI dependency in the original scope whose *shape* depends on the compatibility date. At the current `2020-01-01` floor it is a `GET` returning a bare array; at `2025-09-30` and later it is a `POST` with a JSON body, renamed preference values, an object envelope, and no server-side cache, and the old shape returns **HTTP 404**. Verified live by the courier spike. Because this feature does not call it, F008 and the open ESI-4 pinning decision can proceed independently — see §15.2 for what the follow-on inherits.

### 6.2. Exposed Hangar Bay API Endpoints

Mostly extensions to `GET /contracts/`, plus two small companion endpoints named below. Routers mount bare; the `/api/v1` prefix belongs to the proxy and edge (pitfall PROXY-1).

New query parameters: `contract_type`, `category_id`, `group_id`. **`contract_type` filters the existing `Contract.type` column** — the model already stores it and already indexes it via `ix_contracts_type_status`. No new column is added; the plan states the parameter-to-column mapping and whether that composite index serves the new access pattern or needs a companion.
New response fields: `end_location_name`, `buyout`, `days_to_complete`, `reward_per_volume`, `last_seen_at`, per-item `runs` / `material_efficiency` / `time_efficiency` / `category_id` / `group_id`.
New sortable fields: `reward_per_volume`, `days_to_complete`, `buyout`.

**Per-type counts.** Segment labels carry counts, and those counts MUST reflect every other active filter — a count that ignores the search box or the price range is a lie in a numeral, worse than no count.

**The one exception is load-bearing: segment counts are computed with the `contract_type` predicate itself removed.** Reading "every active filter" literally would make every unselected segment read zero, which is both wrong and useless — the point of the counts is to tell the user what is behind the tabs they are *not* on. So: all other filters applied, type predicate lifted, grouped by type.

Two further requirements that a naive implementation gets wrong: counts are of **distinct contracts** (a grouped aggregate over an item-joined rowset inflates every multi-item contract, and would still satisfy Criterion 1.3 read superficially), and all segment counts plus the page come back in **one round trip**, not one query per segment. Criterion 1.8 governs their behavior under the ships-only default. The plan states the query shape it settled on.

**Taxonomy option list.** A companion endpoint returns the categories and groups present in the corpus with their display names, for Criterion 3.5, served from the name cache in §5 rather than resolved per request.

**Coverage metadata.** An endpoint or envelope field states which regions are actually ingested, for Criterion 7.3. The client must not hard-code this.

After any change here: `pdm run export-openapi`, then `npm run generate:api`, both regenerated artifacts committed in the same PR.

## 7. Workflow / Logic Flow

**Ingestion.** Unchanged in shape. Enrichment additionally writes the taxonomy and blueprint fields it already holds — no new ESI calls, because both were already resolved and thrown away. Location resolution extends to end locations via a widened `_npc_station_ids`, which adds station lookups. The spike measured 44 distinct NPC stations resolving in ~2.2 seconds cold across The Forge's courier population, but that figure covers **start and end stations together** and production already resolves all start locations — so the *marginal* cost here is smaller than 44 stations and 2.2 seconds, and steady state is zero because `_select_known_station_systems` reads already-resolved pairs off stored rows. Treat the spike number as a ceiling, not the increment.

**Backfill of existing rows — and the two halves backfill differently.** This distinction decides the phase boundary, so it must not be glossed.

**Contract-level columns backfill for free.** `_build_contract_rows` and `bulk_upsert` run over *every* fetched contract on *every* ordinary run (`background_aggregation.py:470-486`), and the `_select_already_enriched` skip is applied afterwards and gates only `_fetch_item_rows`. So `buyout`, `days_to_complete`, `end_location_name`, and `end_location_system_id` populate on the next normal ingestion cycle with no version bump and no resweep.

**Item-level columns do not.** `category_id`, `group_id`, `runs`, `material_efficiency`, `time_efficiency`, and `item_id` are written only during item enrichment, which the skip does suppress for already-enriched contracts. These need `ENRICHMENT_VERSION` in `background_aggregation.py` bumped — documented as "bump to re-queue every contract for re-enrichment after an enrichment-logic fix." This feature MUST bump it, for a reason beyond tidiness: §4.2 promises that persisting `item_id` spares the abyssal follow-on a corpus re-ingest, and without a backfill that promise is false for every contract already in the database.

The bump carries a documented operational cost, recorded here so it is planned rather than discovered: the next run becomes a one-off full-corpus resweep taking roughly 80 minutes at a ~46,000-contract corpus. That outlives the aggregation lock TTL, so the `Aggregation lock token mismatch on release` warning at its end is **expected on that run** and is not a concurrency incident. The runbook at the constant's definition governs; the deploy must not be repeated while the resweep is in flight.

**Item-dependent presentation is gated on the resweep. Contract-dependent presentation is not.** Shipping taxonomy filters, ME/TE columns, or composition summaries before the resweep completes means rendering blanks across most of the corpus, which a user cannot distinguish from a broken feature. But gating *everything* on it needlessly blocks the auction and courier work (Stories 4 and 5), whose columns are all contract-level.

The required order is:

1. Migration applied (all new columns exist, all NULL).
2. Ingestion changes deployed, `ENRICHMENT_VERSION` bumped.
3. **Unblocked immediately after the next ordinary run:** auction and courier presentation — `buyout`, `days_to_complete`, `end_location_name`, reward per m³ — verified against a non-NULL rate on the contract-level columns.
4. **Blocked until the resweep is observed to completion**, with a verified non-NULL rate on the *item-level* columns and not merely "the job finished": taxonomy filters, blueprint columns, composition summaries.

The plan must make step 4 an independently verifiable unit separate from step 2. A single PR that migrates, ingests, and exposes the item-level surface cannot satisfy this, because the resweep takes roughly 80 minutes of production runtime and cannot be verified inside the deploy that triggers it.

**Query.** `contract_type` and taxonomy filters compose with the existing filter set. Derived ratios are computed in SQL for sortability.

**Render.** The active contract-type segment selects a column set; the row renderer is shared. Column definitions move into their own module rather than living inside `ContractTable.tsx`.

**This is a larger change than "extract the array."** The six-entry `COLUMNS` array (`ContractTable.tsx:14-33`) drives only the `<thead>`; the six `<td>`s are hard-coded inline at `:112-151` and are not derived from it. Extracting `COLUMNS` alone yields per-segment *headers* over a fixed body — worse than doing nothing, because the columns would no longer describe the cells. The body must first be restructured into per-column cell renderers so that a column definition carries both its header and its cell. The plan sizes this as a component refactor, not a constant move.

## 8. UI/UX Considerations

*   **Type-aware rows, shared frame.** One table component, per-segment column sets. Adding the abyssal shape later must not require touching the frame.

*   **The five "row shapes" are two orthogonal axes, not five mutually exclusive cases.** This has to be stated because the shapes visibly overlap — an auction can be multi-item and can contain several blueprint copies — and an implementer handed five overlapping labels will invent a precedence rule of their own.

    **Axis 1, the segment, comes from `Contract.type`** and is disjoint by construction: item exchange, auction, courier. It selects the columns that describe the *contract* — price, or current bid and buyout, or route and reward.

    **Axis 2, the row body, comes from item composition** and applies within any item-bearing segment: single item, or multi-item composition summary. Courier has no second axis because ESI returns it no items.

    **Blueprint columns are a refinement of the single-item body, not a sixth shape.** Runs, ME, and TE appear when the contract's offered items comprise exactly one blueprint copy. A contract with several blueprint copies has no single ME/TE to report, so it renders as multi-item composition and defers per-blueprint detail to the detail view. This resolves the "which blueprint supplies ME/TE" ambiguity by removing the case rather than picking arbitrarily.
*   **Cascading taxonomy filter.** Category first, then group scoped to that category with type-ahead. A flat group list is not viable: the Module category alone contains hundreds of groups.
*   **No distance figure of any kind on the courier row in this feature.** Reward per m³ is the normalization; jumps, reward per jump, and route-security tiers all belong to the deferred work (§4.2), and the design rules that govern them are recorded in §15.2 so they are not re-derived. A row must not imply a distance it cannot compute — an unlabelled "route" column reading `Jita → Amarr` is fine; anything that reads as *near* or *far* is not.
*   **Unknown is not zero.** Roughly 9–10% of couriers have a player-structure endpoint that cannot be resolved without ACL-scoped tokens. Those rows must read as "unknown" and must not silently sort as if they were poor value.
*   **Full ISK figures and relative expiry are retained** — both are existing advantages over the surveyed competition.
*   **Coverage statements over silent empty results.** Selecting an uningested region must explain, not return an empty table.

## 9. Error Handling & Edge Cases (Required)

*   **Divide by zero on volume.** Reward per m³ must guard against a zero or missing `volume`.
*   **Blueprint originals.** `runs` is absent, not `-1`, on the public route (ESI-3). Filters and display must treat absence as "not a copy," never as zero runs.
*   **`is_blueprint_copy` absence.** ESI omits the flag for non-copies; the filter must treat NULL as not-a-copy. Fixed previously; the taxonomy work must not regress it.
*   **Unresolvable locations.** Player structures cannot be resolved without ACL-scoped tokens, so `end_location_system_id` stays NULL for roughly 9–10% of couriers and the destination surfaces as "unknown" rather than blank or zero.
*   **Partial enrichment, and a narrow scope mismatch this feature creates.** The existing `ENRICHMENT_INCOMPLETE` semantics extend to the new fields: a contract whose taxonomy failed to resolve must not be stamped `COMPLETED`. The completion predicate has two halves and **only one is narrowed**: the `type_name is None` half already covers excluded items, while the *category* half is scoped to included items via `unresolved_category_contract_ids` (`background_aggregation.py:796-799`), because the only thing it gated was the ship flag, which only offered items decide. Criterion 8.1 renders requested items and Criterion 6.3 summarizes them by category — so a contract whose *requested* item failed **category** resolution would be stamped `COMPLETED`, excluded from every future re-fetch, and display a permanently blank want-to-buy side with no route back. Widening the category half is a small, specific change; the plan must state that it made it.
*   **Serialization strictness.** A non-optional schema field over a nullable column fails the entire page, not one row, because `PaginatedResponse` validates every item. Every new field is optional in the response schema unless it is provably non-null for every row.

## 10. Security Considerations

*   No new authentication surface. All consumed endpoints are public and unauthenticated.
*   No PII in instrumentation. Filter dimensions only — no user identifiers, no free-text search contents.
*   New filter parameters are typed and bounded by Pydantic, reaching the database only through the ORM.
*   End-location resolution reuses the existing bounded-concurrency helper and the NPC-station-ID guard that avoids spending ESI error budget on requests guaranteed to 401.

## 11. Performance Considerations

*   End-location station resolution is bounded by distinct stations, not contract count, and memoizes from stored rows — 44 distinct stations across the courier population, then zero.
*   Derived ratios (reward per m³) are computed in SQL so they sort without loading the page into the application.
*   Filtering on contract type reuses `Contract.type`, already covered by the composite `ix_contracts_type_status`. The plan verifies whether that composite serves a type-only predicate or whether a companion index is warranted — it does not assume either. New taxonomy columns (`category_id`, `group_id`) do need indexes; the plan specifies which, informed by the existing set.
*   **Adding a sortable field touches five places, not one.** `reward_per_volume` needs a `SORT_MAP` entry (`contract_service.py:27-34`), a new `SortableContractFields` member — which `SavedSearchParameters.sort_by` also consumes (§14) — a matching entry in the frontend's duplicated `SORT_FIELDS` (`features/contracts/filters.ts:1-9`), regenerated client types, and it must work through the grouped-subquery pagination path that SQLA-1 governs. A sort on a computed ratio is not a one-line addition.
*   The `ENRICHMENT_VERSION` bump (§7) triggers a one-off full-corpus resweep of roughly 80 minutes. It is a planned deploy-time cost, not a steady-state one.
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
*   **F005 (Saved Searches) — a hard collision that must be resolved in this feature, not discovered during it.** `SavedSearchParameters` (`schemas/account.py:16-31`) is `extra="forbid"` and its docstring states it deliberately *rejects* the inert ME/TE params under FASTAPI-2. Two tests pin that rejection: `tests/api/test_saved_searches.py:125` asserts `min_me=5` returns 422, and `tests/api/test_account_schemas.py:57` asserts the schema-level equivalent. Criterion 2.5 makes those params real, and this feature additionally introduces `contract_type`, `category_id`, and `group_id`, none of which a saved search can currently hold.

    So an implementing agent will hit a passing test asserting the exact inverse of a criterion they were told to satisfy. The plan must decide explicitly: widen `SavedSearchParameters` to accept the now-functional params and update both tests, or leave saved searches on the narrower set and say why. **What it must not do is treat the red test as a bug in the test.** Whichever way it goes, the sort-field coupling in §11 applies too — `SavedSearchParameters.sort_by` consumes the same `SortableContractFields` enum this feature extends.
*   **ESI-4 / `/route/`** — the compatibility-date coupling in §6.1.
*   **No dependency on M5, appraisal, or multi-region ingestion.** This feature is buildable today.

## 15. Notes / Open Questions

### 15.1. Reconciliation: the F002 market-group conflict

F002 §221 and criteria 4.3–4.5 place a market-group category filter in MVP scope, backed by a `GET /ships/market_groups` endpoint sourced from ESI `/v1/markets/groups/`. The M1 frontend design deferred it, correctly, because that endpoint does not exist. The conflict was never resolved.

**Resolution: F008 supersedes the mechanism and preserves the requirement.** F002 asks to filter by "broad ship market groups/categories (e.g. Frigate, Cruiser)." Those are dogma **group** names under the Ship category — the same group records enrichment already fetches in order to compute the ship flag. The user-facing requirement is met; the mechanism changes from market groups to dogma category/group.

**The deciding reason is the abyssal follow-on.** Abyssal and mutated items are off-market by construction and therefore have no market group at all. A taxonomy built on market groups would require a second taxonomy, or would leave the largest non-ship cluster unfilterable, exactly when the follow-on lands. Dogma category/group is the only axis that spans both this feature and its committed successor.

**What the market-group axis would genuinely have been better at**, recorded so the trade-off is not lost: it is a browsing hierarchy CCP built for buyers, with real depth (`EsiMarketGroupCache.parent_group_id` exists for it), whereas dogma gives two levels with a very wide second level. The cascading filter in §8 is the mitigation.

**A measurement the plan should take, because it could partially reopen this.** The 87%-NULL market-group figure comes from the gap analysis §4.1 and is itself a sample, not a census; it was measured across all non-ship items, a population dominated by abyssal items — the cluster this feature defers. Coverage among the items this feature actually displays (blueprints, ordinary modules, injectors, containers) may be far higher. If it is, that does **not** change the filter axis, for the reason above; but it would make a market-group navigation tree a legitimate later enhancement layered on top. The measurement is cheap and should be recorded either way.

**Action on F002 itself: already done, not pending work.** F002 carries the supersession pointer at its criteria 4.3–4.5 and again in its §15 notes, both linking here. No further edit to F002 is needed and the plan should not make one.

### 15.2. Policy: courier contracts

No courier policy exists anywhere in the repository. Their exclusion from item fetching is an implementation artifact — ESI returns no items for couriers — never a decision. This section is that decision.

**Couriers are a first-class contract type in this feature**, with their own columns and their own sorts. They are not purchases: a courier contract is a job offer, and its audience is haulers rather than buyers. Nothing in the surveyed ecosystem browses them, which makes this the most differentiated surface in the feature and the least validated.

**Three limits are accepted deliberately:**
1. **Coverage is stated, not hidden.** Only The Forge is ingested, so this is "couriers originating in The Forge" — 115 contracts. That is a thin tab, and it is a thin tab honestly labelled rather than an implied national market.
2. **No distance metric in v1.** Reward per m³ is the normalization; reward per jump follows in its own plan (§4.2). The view must not display or imply a distance figure it cannot compute.
3. **No "jumps from my location"**, ever in this line of work — it needs the full route graph and is a different problem (§4.2).

**What the reward-per-jump follow-on inherits, recorded here so it is not re-derived.** The spike measured and verified all of the following; the follow-on plan starts from them rather than from scratch.

*   **Cost is settled:** 39 distinct system pairs across The Forge's 115 couriers, 117 route calls for all three preferences, 161 ESI calls and 8.4 seconds cold including station resolution, zero in steady state. The rate limit is 3,600 per 15 minutes, so the working set uses well under 1%.
*   **The default is high-security-preferred**, on stated convention rather than inference: EVE University's *Moving your items* — "The payment should assume a fully hisec route if one is available" — and EVE Courier, the only surveyed tool exposing the control, defaults the same way.
*   **Disclosure beats a mode picker.** Adam4EVE is the only shipped precedent: auto-pick the route, then have each row state which security tier it actually achieved, colour-coded and tooltipped (142 high-sec / 110 low-sec / 23 null-sec on one live page load). Per-row disclosure is how the honesty requirement is met; a user-facing preference control is at most a secondary refinement.
*   **Three correctness traps.** ESI's `secure` flag is an *upper bound*, not the shortest high-sec route — Jita → Amarr returns 45 jumps when a fully high-sec 34-jump route exists, diverging by up to about a third on long routes while agreeing exactly on short ones. `secure` is also never a guarantee and emits no signal when no high-sec route exists (Jita → 1DQ1-A: 81 jumps still crossing 23 low/null systems), so "does a high-sec route exist?" must be answered from the returned system list, not the flag. And `security_penalty` on the newer API shape is measurably non-monotonic (0 → 45 jumps, 5–20 → 11, 25+ → 45); pin it to default and never expose it.
*   **Two implementation traps.** `_get_esi_object` raises on any non-dict response and the legacy `GET /route/` returns a bare array; the paginated helper is also unusable because it flattens a dict into its keys. A third, list-shaped helper is required. And reward-per-jump needs a divide-by-zero guard: no same-system couriers appeared across 250 sampled contracts, but nothing prevents one, and zero jumps must resolve to a defined display rather than an exception or an infinity.
*   **Two display rules the follow-on must decide explicitly, because "visibly distinct" admits opposite implementations.** Where unknown-jump rows sort under ascending *and* descending reward-per-jump (they must not silently occupy the "best value" end in either direction), and what the jumps cell reads when the count is unknown versus when it is genuinely zero.
*   **Two required steps.** Adding `GET /route/` to the ESI drift-monitor manifest is not optional — without it, the day the compatibility floor moves is the day couriers 404 in production. And the follow-on must resolve the ESI-4 interaction explicitly: either handle both `/route/` shapes, or pin below `2025-09-30`.
*   **One framing constraint.** Reward per jump is a comparison metric, not a quote. Real services bill per *warp* ("jumps + 1 in most cases" — PushX), with collateral multipliers and a floor. The UI must not imply it is what a hauler would charge.
*   **Worth knowing before investing:** no surveyed tool ships an ISK-per-jump column at all. The metric lives in rate cards and marketing copy, never in a shipped table. That is consistent with an unoccupied niche and is also a mild warning that the number may be harder to make honest than it looks.

**The default-preference question is now settled** — it was the weakest-sourced claim in the spike and has since been confirmed against primary sources. EVE University's *Moving your items* states the convention verbatim: "The payment should assume a fully hisec route if one is available," and quotes the established services at roughly 900,000–1,000,000 ISK per jump for standard high-security work. Independently, EVE Courier — the only surveyed tool that exposes a route-preference control — defaults it to High-Sec. High-security-preferred is therefore the default on convention, not on inference.

**What the same survey found that is worth recording.** No tool in the ecosystem ships an ISK-per-jump *column*; the metric appears in marketing copy and rate cards, never in a shipped table. That is consistent with this being an unoccupied niche, and it is also a mild warning worth naming rather than burying: it is possible nobody ships it because the number is harder to make honest than it looks — which is precisely why the follow-on's disclosure rules below are written as hard requirements rather than preferences.

**A related distinction, since it is easy to conflate.** CCP declined to add distance sorting to the in-game contract browser, stating it is "a user-specific pathfinding search that is simply too expensive for the server." That constraint does not apply here and the difference is the whole reason this is feasible: our jump counts are between *fixed contract endpoints*, computed once and cached, not between a contract and wherever a given user happens to be standing. The user-relative version is exactly the "jumps from my location" case §4.2 puts out of scope.

### 15.3. Provenance of the numbers in this spec

Several figures here come from live production probes and research spikes, not from anything checkable in the repository. They are load-bearing in different degrees, and an implementing agent should know which is which rather than treating them all as facts of the codebase.

**Verified against source, and safe to rely on:** every file:line citation, the column types and index names, `ENRICHMENT_VERSION`'s existence and semantics, the `_npc_station_ids` start-only scope, the `_build_contract_rows`-before-skip ordering, `selectinload` on both list and detail, the `SavedSearchParameters` rejection and its two tests, and the ESI contract-type enum (from the committed spec snapshot).

**Measured against live production on 2026-08-01, not re-checkable from the repo:** the ~33,900 live corpus, ~411 ship-flagged, ~622 default-view rows; `min_me=10` returning 15,592 identical to unfiltered; the 55.7 KB maximum row and the 244- and 143-item contracts; the ~46,000-contract corpus and ~80-minute resweep behind §7's phase split. **The plan should re-measure any of these it depends on**, particularly the resweep duration, since it is the sole justification for separating steps 3 and 4. The *mechanisms* behind them are all verified in source; only the magnitudes are point-in-time.

**From research spikes, single-source:** the courier population counts and endpoint-resolvability rates; the ESI route divergences; the Adam4EVE, PushX, and EVE University observations in §15.2. These govern deferred work, so nothing in this feature's implementation rests on them.

**Sampled, not census:** the 87%-NULL market-group figure (§15.1), which §15.1 already schedules for re-measurement.

### 15.4. On the evidence base

The case for this feature is supply-side: the data is already fetched, enriched, and stored, and the competitive field is empty. There is no demand evidence — no user request for BPC or courier browsing, no traffic data, no search terms. The application has one user today and has not been advertised, so no adoption metric could produce signal at this stage.

This is recorded rather than resolved. The instrumentation in §4.1 exists so that the question becomes answerable later; it is deliberately not framed as a success criterion now.

## 16. AI Implementation Guidance

### 16.1. Read before implementing

`docs/pitfalls/implementation-pitfalls.md` and `docs/pitfalls/testing-pitfalls.md` in full.

**Read SQLA-3 and TEST-19 first, before anything else.** SQLA-3 — "a per-row predicate over a one-to-many join cannot classify the parent" — is not a general caution here, it is a description of the central filter this feature adds. Criterion 3.2 asks "contracts containing an item in category X," which is parent classification over item children, and so are the offered-only composition counts in 6.4 and the want-to-buy split in 8.1. The only prior instance of this bug in the repo was `is_bpc`, found in adversarial review on **2026-08-01 — the day before this spec was written**: a contract bundling a blueprint copy with a hull matched both `is_bpc=true` *and* `is_bpc=false`, returning under a filter and its own negation with totals quietly exceeding the corpus. The category filter is the same shape and will fail the same way unless written deliberately.

Also directly load-bearing: **ESI-3** (originals omit `runs`), **FASTAPI-1** (`Annotated[Model, Query()]`, never bare `Depends`, for GET filter models), **FASTAPI-2** (the inert ME/TE params — Criterion 2.5), **FASTAPI-3** (a response field stricter than its column 500s the whole page, not one row — governs every new optional field in §9), **PROXY-1** (no `/api/v1` in FastAPI), **SQLA-1** (pagination over joins, which the new sort field must pass through), **SQLA-2**, **ENV-2/ENV-3** (every backend `.py` save under reload wipes the database — batch edits), **TEST-14** (never pair `pytest.mark.vcr` with an app-client fixture), **TEST-19**, **TEST-20** (assertions inside `if data["items"]:` never run). **ESI-4** matters to the deferred route work, not to any call this feature makes.

### 16.2. Critical logic points

*   Taxonomy persistence happens where both values are already in scope: `group_id` at `background_aggregation.py:771-775`, `category_id` on the group record read at `:783`. Resist the urge to add an ESI call for either.
*   Widening `_npc_station_ids` to collect end locations is required for `end_location_system_id` and is easy to miss, because the *name* map already covers end locations through a different function. Resolving the name and resolving the system are two separate paths.
*   Every new response field is optional unless provably non-null for all rows (§9).
*   Nothing in this feature calls `/route/`. If you find yourself needing an ESI route call, you have wandered into the deferred work in §4.2.

### 16.3. Testing focus

TDD is mandatory for all production code here. Specific traps this feature is prone to:

*   **Every taxonomy-filter test needs a mixed-child parent (TEST-19).** A fixture whose contract holds exactly one item passes identically whether the query classifies the *contract* or the *row* — the readings diverge only when one contract holds children of both kinds. So: seed a contract holding both a ship and a module, assert it appears under exactly one branch of a category filter, and assert the two branch totals sum to the unfiltered total. **"These two branches partition the set" is the property under test, and it is not implied by either branch being individually correct.** Coverage built from single-item contracts says nothing about the semantics that matter.
*   **Fixtures must carry the production data shape.** Backend fixtures previously hand-wrote three columns ingestion never writes, which gave dead filters green tests. Any fixture asserting on `runs`, `is_blueprint_copy`, or taxonomy must reflect what ESI actually sends — including omitting `runs` on originals, and leaving `status` at its `"unknown"` placeholder rather than inventing a value.
*   **Assert the filters return rows.** The defect class this feature is fixing is filters that match nothing. A test asserting a 200 and an empty list would have passed against every one of those bugs.
*   **Both `tests/api/test_contracts.py` and `tests/api/test_contract_filters.py` are safe to write into.** Their `pytestmark` is `asyncio` only. The VCR markers and all five cassettes were removed on 2026-08-01 after the cassettes were found to have recorded the app talking to itself; `tests/marker_guards.py` now aborts collection if any test pairs the `vcr` marker with an app-client fixture. **Do not reinstate a `vcr` marker on either module** — that is what TEST-14 forbids, and it is enforced rather than merely documented.
*   **No assertions inside `if data["items"]:`** without seeding a fixture — a previously shipped test never executed its assertion block.
*   **Mutation-check the load-bearing tests.** Break the behaviour, confirm the test goes red, revert. A test that stays green under mutation is a finding, not a formality — restore from a file copy rather than `git checkout --`, which would discard uncommitted work and produce false evidence.
*   Frontend fixtures must not carry absolute past expiry dates; the future-clock lane exists because an entire suite silently rendered "Expired" and nothing failed.
