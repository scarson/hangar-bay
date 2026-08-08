# Feature Spec: Type-Aware Contract Browsing

**Feature ID:** F008
**Creation Date:** 2026-08-01
**Last Updated:** 2026-08-08 (§3.1/§16.3 range-family branch semantics ratified)
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

The motivating analysis, including competitive evidence and the measured composition of the hidden corpus, is [`docs/superpowers/specs/2026-08-01-contract-coverage-gap-analysis.md`](../../docs/superpowers/specs/2026-08-01-contract-coverage-gap-analysis.md). Its recommendation §6 sequences this work; this spec is that recommendation's phase 2 and **most of** phase 3. Two pieces of that phase 3 are deferred here and carry their own plans: abyssal/mutated display and courier reward-per-jump (§4.2).

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
*   Criterion 1.1: The accepted `contract_type` values are enumerated explicitly and cover **every** value ESI can emit, not only the three with designed row shapes. The full set, confirmed against the committed ESI spec snapshot, is `item_exchange`, `auction`, `courier`, `loan`, `unknown`. A corpus contract whose type is outside the designed set MUST remain reachable and counted — silently dropping it would contradict §1's claim that this feature makes the whole corpus browsable. **Decided: `loan` and `unknown` are valid `contract_type` values and appear in `segment_counts` (§17.5), but get no segment control of their own.** They are reachable by URL and counted honestly; they do not occupy screen space for a population that is empty or near-empty in The Forge. If a later region makes them common, promoting them to segments is additive and breaks nothing.
*   Criterion 1.2: `loan` and `unknown` contracts are **item-less by construction, exactly like couriers**, and inherit the same handling. Ingestion skips item fetching for every type outside `item_exchange` and `auction` (`background_aggregation.py:637`), so these contracts never enter `processed_contract_ids`, remain `PENDING_ITEMS`, and keep `enrichment_version = 0` indefinitely. Two consequences the plan must handle rather than trip over: they are excluded from the ships-only view by the same construction as couriers (Criterion 1.6), and §7 step 4's "verified non-NULL rate on item-level columns" can never cover them, so the verification query must scope to types that actually receive items.
*   Criterion 1.3: The contracts view presents contract-type segmentation with a live result count per segment. **Counts are of distinct contracts**, not of joined item rows — a multi-item contract counts once. A fixture with at least one multi-item contract is required to make this assertion meaningful.
*   Criterion 1.4: Selecting a segment updates the list and is reflected in the URL, so the view is shareable and restorable.
*   Criterion 1.5: The default view remains ships-only, consistent with F002 Criterion 1.1 and `PRODUCT.md`.
*   Criterion 1.6: Courier contracts — and `loan` and `unknown` contracts, per Criterion 1.2 — are excluded from the ships-only view by construction, because ESI returns no items for them and the ship flag is derived from items.
*   Criterion 1.7: `ships_only` and contract-type selection MUST NOT be independently settable into a combination that can never match. This applies to **every item-less segment** — courier, and `loan` and `unknown` if Criterion 1.1 gives them a segment — not to courier alone; each is empty under ships-only by the same construction (Criterion 1.6). Selecting any such segment clears `ships_only`, visibly rather than silently. A guaranteed-empty result reachable by ordinary interaction is the same silent-filter-no-op defect Criterion 7.2 prohibits; this feature must not ship the defect it forbids.
*   Criterion 1.8: **Decided: while `ships_only` is active, an item-less segment's count is computed with `ships_only` lifted as well as `contract_type`.** The courier tab reads its true total, not 0. Criterion 1.7 makes the combined state unreachable, so the count's only job is to advertise what switching would reveal — and a `Courier (0)` label that becomes `Courier (115)` the instant you click it is the silent-no-op defect wearing a numeral.
*   Criterion 1.9: **Returning from an item-less segment restores `ships_only` to its default (on).** Criterion 1.7 clears it on the way in; without a stated rule for the way back, two implementers ship opposite behavior — the same defect 1.8 exists to prevent, one interaction later. Because `filters.ts:77` reads `ships_only: raw.ships_only !== false`, "cleared" is written into the URL as an explicit `false`, and restoring means removing that parameter rather than setting it true.

**Story 2 — blueprint copy display and filtering**
*   Criterion 2.1: `runs`, `material_efficiency`, and `time_efficiency` are persisted from the ESI items payload.
*   Criterion 2.2: BPC rows display runs, ME, and TE.
*   Criterion 2.3: The existing `min_runs`/`max_runs` filter family operates against `runs` rather than `raw_quantity`, which cannot be populated from public ESI and is why the filter currently matches nothing.

    **Semantics and verifiable form: see §3.1**, which defines the contract-level predicate for every item-level range filter and the correct three-way assertion. Do not reason about this criterion without it — the obvious reading produces a test that cannot pass.
*   Criterion 2.4: A blueprint **original** is distinguishable from a copy. Per pitfall ESI-3, the public route omits `runs` entirely for originals rather than sending `-1`; absence must not be read as zero.
*   Criterion 2.5: The `min_me` / `max_me` / `min_te` / `max_te` filter families operate against `material_efficiency` and `time_efficiency`. All four are inert today (`schemas/contracts.py:165-200`), not only the minimums. **These fail more dangerously than the runs filter and need the harsher test.** Measured against live production on 2026-08-01: `min_me=10` returns **15,592 contracts — the identical count to the same query with no ME filter at all**. The filter is not merely inert, it is invisible: it returns a large, plausible, wrong result set that reads as a successful answer, where `min_runs=5` at least returns zero and looks broken. **Semantics and verifiable form: see §3.1.** Additionally, and specific to this criterion: assert the filtered count is **strictly less** than the unfiltered count for the same query. That single assertion is what catches the live defect, where `min_me=10` returns the entire result set unchanged. A test asserting only "returns some rows" passes against the defect and must not be accepted.

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

    **This is a breaking change to shipped behavior, not a description of it.** Items are eager-loaded on both list paths (`contract_service.py:272` in `_fetch_page_grouped`, `:294` in `_fetch_page_simple`) and on the detail path (`api/contracts.py:52`), and the frontend list row genuinely depends on them: `contractIsBpc` iterates `contract.items` (`ContractTable.tsx:36`) and `primaryLabel` reads `items[].type_name` / `category` / `is_included` (`format.ts:78`). Dropping `items` from the list response requires the two replacement fields named in §4.1 plus the composition summary of 6.1, landed before or with the removal, with the client chain regenerated.

    **The response model must be split, and this is the part an implementer will get wrong.** `ContractSchema` is the single model for both endpoints — `ContractListResponse[ContractSchema]` at `api/contracts.py:27` and bare `ContractSchema` at `:41` — and its `items` field already defaults to `[]` (`schemas/contracts.py:73`). So dropping the `selectinload` on the list path alone *appears* to satisfy this criterion while leaving the generated TypeScript still declaring `items: ContractItemSchema[]` on list rows, which would now always arrive empty. That is a schema that lies rather than a field that was removed, and it is strictly worse than the status quo. Satisfying 6.4 requires a distinct list-row model whose type says what the payload contains.

**Story 7 — freshness and coverage honesty**
*   Criterion 7.1: `last_seen_at` is surfaced in the UI, which requires adding it to the response schema — it is computed today and returned by nothing.
*   Criterion 7.2: A filter combination that cannot match — most importantly a region other than The Forge — produces an explanatory state distinguishing "not covered" from "nothing matched." This is the empty-state-or-explain invariant proposed in the gap analysis §2.2.
*   Criterion 7.3: **Coverage is data, not a hard-coded constant.** The API exposes which regions are actually covered; the client does not embed "The Forge" as a literal. Without this the implementation must either hard-code the region (which silently becomes wrong the day coverage expands) or infer coverage from an empty result (which misclassifies a genuinely empty covered region as uncovered). Both failure modes are the defect Criterion 7.2 exists to prevent, reintroduced one layer down.
*   Criterion 7.4: **Decided: coverage reports observed reality, not configured intent.** `Settings.AGGREGATION_REGION_IDS` (`core/config.py:61`) states what we mean to ingest; `SELECT DISTINCT start_location_region_id` states what we actually have. They diverge for the whole ingestion window after a coverage change, and during that window the configured value would tell a user a region is covered when it holds nothing — the exact failure Criterion 7.3 exists to prevent. Region display names come from the static `regions.ts` map the frontend already ships. Wire shape in §17.7.

**Story 8 — want-to-buy symmetry**
*   Criterion 8.1: Items requested (`is_included = false`) and items offered are rendered distinctly and never merged into one list.

### 3.1. Item-level filter semantics — canonical statement

**Every filter over an item column needs a contract-level predicate, and this subsection defines it once for all of them.** Criteria 2.3, 2.5, and 3.2 all refer here. The list endpoint returns contracts, but `runs`, `material_efficiency`, `time_efficiency`, `category_id`, and `group_id` live on items, and a contract may hold many items with different values. Without a stated rule, three readings are equally consistent with "filter by ME ≥ 10" and they return different result sets.

**The rule: existential over offered items.** A contract matches an item-level filter when **at least one item with `is_included = true` satisfies the predicate**. Requested items never make a contract match — they are the counterparty's side of the trade, and Criterion 8.1 exists because conflating them misleads. This is the same rule the `is_bpc` fix settled on, extended to ranges.

**Range filters compose per item, not per contract.** `min_me=10&max_me=20` matches a contract holding one item with ME 15. It does **not** match a contract holding an ME-5 item and an ME-25 item, because no single item satisfies both bounds. Bounds within a family apply to the same item; that is what a range means.

**The assertion is a three-way identity, not a two-way partition.** Two complementary bounds do **not** sum to the unfiltered total, for two independent reasons: range bounds leave gaps (`max_me=5` and `min_me=10` exclude ME 6–9), and NULL-valued items fall outside both (blueprint originals omit `runs` entirely per ESI-3, and non-blueprint items have no ME at all). A test demanding a two-way sum cannot pass under any correct implementation. Assert instead:

```
count(branch_a) + count(branch_b) - count(both) + count(neither) == count(unfiltered)
```

where **`neither`** is contracts with no offered item satisfying either bound — including every contract holding no blueprint at all — and **`both`** is contracts holding offered items on each side of the boundary. Choose the two branches to be genuinely complementary over the *non-NULL* population (`max_runs=10` and `min_runs=11`), and state the expected `neither` and `both` counts explicitly in the fixture rather than deriving them.

**The overlap term is real for range families and empty for the boolean one, and the difference is the existential rule itself.** `is_bpc=false` is the *negation* of `is_bpc=true`, so those branches partition by construction and `both` is always zero. Complementary range bounds are two independent existential questions: a contract offering an ME-5 item and an ME-15 item genuinely satisfies `max_me=9` AND `min_me=10` — each bound by a different offered item — so it legitimately appears under both, and a test demanding it appear under exactly one would reject a correct implementation. (Ratified 2026-08-08 after implementation surfaced the conflict with this section's earlier "exactly one branch" wording; the reasoning record is the build decision log, `docs/superpowers/plans/2026-08-06-f008-decision-log.md`, entry on range-family branch membership.)

**The mixed-child fixture is still required** (TEST-19, SQLA-3), and what it must assert differs by family shape. For the boolean family: seed a contract holding an offered copy alongside an offered non-copy and assert it lands in **exactly one** branch — under a naive per-row predicate it matches both. For a range family: seed the straddling contract described above and assert (a) it appears in **both** single-bound branches (pinning existential semantics), (b) a window whose bounds no single item satisfies excludes it (pinning same-item composition — `min_me=10&max_me=12` must not match the ME-5/ME-15 contract), and (c) the identity above holds with `both` stated. A single-item fixture cannot distinguish the contract-level rule from the per-row one and proves nothing.

## 4. Scope (Required)

### 4.1. In Scope

**Data layer**
*   Persist item `category_id` and `group_id`. **Both values are already in hand during enrichment and neither is stored.** `group_id` arrives on the type payload and is used at `background_aggregation.py:771-775` to fetch group records, then dropped by omission; `category_id` is read off that group record at `:783` purely to compare against `SHIP_CATEGORY_ID`, and `:787` stores only the derived `"ship"`-or-NULL string. Persisting them adds columns and assignments, **not** ESI calls.
*   Persist item `runs`, `material_efficiency`, `time_efficiency`, and `item_id`.
*   Persist contract `buyout` and `days_to_complete`.
*   Persist `end_location_name` (required by Criterion 5.2; the name is already resolved and discarded).
*   Persist `end_location_system_id` (write-only in this feature; see Criterion 5.5). Requires widening two of the three location-resolution paths — **§5.1 is the canonical statement of which and why; do not re-derive it here or anywhere else.**
*   Serve a contract-level blueprint-copy flag and a primary display label, so the list response no longer has to inline every item (Criterion 6.4). **Decided: both are computed per query, not stored columns.** Storing them would put the single largest change in this feature behind the 80-minute resweep in §7 step 4 for no benefit, since both derive from item rows that are present as soon as enrichment writes them. Computed keeps §7's phase assignment stable and avoids two denormalized columns that would need their own invalidation story.

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
*   **Remove the raw search string from those logs.** `contract_service.py` emits `"search": filters.search` — the user's own query text — at four sites (`:317`, `:365`, `:412`, `:436`). §10 forbids that, and a task told only to "add dimensions, no PII" would satisfy the letter of its instruction while leaving the violation in place. Log a boolean or a length instead, at all four.

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
| `end_location_system_id` | int, nullable | Typed `Integer` to match its sibling `start_location_system_id` (`models/contracts.py:56`); solar system IDs fit int32. Written but unread in this feature (Criterion 5.5). NULL where the endpoint is a player structure — measured at **6 of 115 Forge couriers (~5%)** for the end location specifically; the ~9–10% figure in the spike is the *both-endpoints* rate and does not apply to this column alone. Population requires the widening in §5.1. |

### 5.1. Location resolution — canonical statement

**This subsection is the single source of truth for how location data is resolved. Every other section refers here rather than restating it.** Name resolution and system resolution are separate pipelines, and within system resolution the fetch set and the cache read are separate functions. Of the three paths, one already handles end locations and two do not:

| Path | Current scope | Needed for this feature |
|---|---|---|
| `_collect_resolvable_ids` (`background_aggregation.py:97`) | Already unions `end_location_ids` into the **name** set | **No change.** This is why `end_location_name` is nearly free. |
| `_npc_station_ids` (`:150-157`) | `start_location_id` only — its docstring reads "The distinct start locations" | **Widen** to collect end locations, or `end_location_system_id` is never populated. |
| `_select_known_station_systems` (`:575-599`) | Selects `Contract.start_location_id` / `start_location_system_id` only | **Widen.** Skipping this does not fail loudly: a station that only ever appears as a *destination* is absent from `known` on every run and is re-fetched from ESI forever, so the "steady state costs zero station requests" its docstring promises silently becomes false for exactly the locations this feature adds. |

Two consequences that follow from the table and are not restated elsewhere:

*   **Cost.** The marginal cold cost is the end-only stations, which is smaller than the spike's 44-station / 2.2-second figure because that covers start and end together and production already resolves all starts. Steady state returns to zero **only if both widenings land**.
*   **A hazard to preserve.** `_select_known_station_systems`'s docstring records that the upsert copies every supplied column on conflict, so a run that re-resolved from scratch and came back empty would write NULL over systems the site already knew. Neither widening may weaken that property.

### 5.2. Taxonomy name cache

Criterion 3.5 requires a served option list with display *names*, and the ID columns above cannot produce them: group payloads are fetched transiently during enrichment and discarded, and no dogma category or group cache exists. Without a durable name source the companion endpoint in §6.2 has nothing to serve, which is exactly how F002's market-group filter died.

**Decided: a new table, `esi_taxonomy_cache`. Do not repurpose `EsiMarketGroupCache`.** That model's primary key is `market_group_id` and its `raw_esi_response` is `nullable=False` (`models/contracts.py:22-32`); dogma category IDs and market group IDs share an integer space with no discriminator, so reusing it would need a migration and a new key column anyway. Reuse buys nothing and costs a confusing table.

Shape: `(kind, esi_id)` as the composite key where `kind` is `category` or `group`, plus `name`, `parent_category_id` (NULL for categories), and `fetched_at`.

**Population, which is the part the ID-column work does not cover:**

*   **Group names are free.** They ride the group payloads enrichment already fetches at `background_aggregation.py:774-776`.
*   **Category names are not.** They need `GET /universe/categories/{id}`, which means a new `ESIClient` method and a fan-out through the existing `_resolve_esi_objects` helper. This is the **one** ESI call this feature adds, and it is why §4.1's "adds columns and assignments, not ESI calls" is scoped to the ID columns. The set is tiny — a few dozen categories, immutable — so it resolves once and is cached permanently.
*   **Cold-cache behavior is a requirement, not an accident.** The cache fills as enrichment runs, so between the migration and the completion of the resweep the option list is partial. The taxonomy filter is therefore gated with the rest of the item-level surface in §7 step 4, and the option endpoint must report an empty or partial list honestly rather than presenting it as the complete taxonomy.

**Retained but unused columns.** `status`, `date_completed`, `raw_quantity`, and `is_singleton` remain, and this feature adds no filter or display that reads them. **They are not uniformly NULL, and the distinction matters for anyone writing a filter against them:** `status` is `nullable=False` and holds the placeholder `"unknown"`, and `is_singleton` is `nullable=False` and receives `False` from ingestion (`background_aggregation.py:654` supplies `i.get("is_singleton", False)`; the column declares no default of its own). Only `date_completed` and `raw_quantity` are actually NULL. So two of the four hold *values that look real and are meaningless* — a worse trap than NULL, and the reason `is_bpc=false` and `min_runs` both silently matched nothing. All four are exactly what the authenticated character and corporation contract routes return. The reasoning is recorded in the gap analysis §4.2 and is not reopened here. Likewise `ContractItem.market_group_id` and `EsiMarketGroupCache` are retained but are not the taxonomy axis (§15).

## 6. API Endpoints Involved

### 6.1. Consumed ESI API Endpoints

| Endpoint | Use | Notes |
|---|---|---|
| `GET /contracts/public/{region_id}` | Existing | Source of `buyout`, `days_to_complete`. |
| `GET /contracts/public/items/{contract_id}` | Existing | Source of `runs`, ME, TE, `item_id`. |
| `GET /universe/groups/{group_id}` | Existing | Already called; `category_id` read and discarded. |
| `GET /universe/categories/{category_id}` | New | For display names. Small, bounded, permanently cacheable. |
| `GET /universe/stations/{station_id}` | Existing | Extended to end locations, to populate `end_location_system_id`. |

**The ESI drift-monitor manifest MUST be updated in this feature**, in three distinct ways. `app/backend/tools/esi_spec_monitor/manifest.py` records, per endpoint, every field Hangar Bay consumes and who consumes it; that is what makes upstream drift visible before it breaks production. Omitting any of these fails silently — the monitor stays green while watching a field set that no longer matches what we read.

1. **Six genuinely new fields to add:** contract `buyout` and `days_to_complete`; item `runs`, `material_efficiency`, `time_efficiency`, and `item_id`. Verified absent from the `/contracts/public/{region_id}` and `/contracts/public/items/{contract_id}` blocks.
2. **Two existing entries to amend, not add.** `group_id` (`manifest.py:133`) and `category_id` (`:143`) are **already monitored** — consistent with §4.1, which says both are read during enrichment today. Their consumer notes describe them as feeding the ship-flag decision only; both will now also populate `ContractItem` columns, so the notes need widening.
3. **One entry that becomes false.** `manifest.py:114-118` records `raw_quantity` as "read by the min_runs/max_runs filter in contract_service," with the consequence "always NULL, so min_runs/max_runs match zero rows." Criterion 2.3 rewires that filter to `runs`, so both the consumer note and the consequence stop being true. Leaving them turns the monitor into a source of confident misinformation.

Plus one new endpoint block for `/universe/categories/{id}` (§5.2).

**No new ESI endpoint beyond `/universe/categories/{id}` is consumed.** `/route/` belongs to the deferred reward-per-jump work (§4.2), and moving it out is one of the reasons for that deferral: it is the only ESI dependency in the original scope whose *shape* depends on the compatibility date. At the current `2020-01-01` floor it is a `GET` returning a bare array; at `2025-09-30` and later it is a `POST` with a JSON body, renamed preference values, an object envelope, and no server-side cache, and the old shape returns **HTTP 404**. Verified live by the courier spike. Because this feature does not call it, F008 and the open ESI-4 pinning decision can proceed independently — see §15.2 for what the follow-on inherits.

### 6.2. Exposed Hangar Bay API Endpoints

Mostly extensions to `GET /contracts/`, plus two small companion endpoints named below. Routers mount bare; the `/api/v1` prefix belongs to the proxy and edge (pitfall PROXY-1).

New query parameters: `contract_type`, `category_id`, `group_id`. **`contract_type` filters the existing `Contract.type` column** — the model already stores it and already indexes it via `ix_contracts_type_status`. No new column is added; the plan states the parameter-to-column mapping and whether that composite index serves the new access pattern or needs a companion.
New response fields, **stated per response because Criterion 6.4 splits them**: on both list and detail — `end_location_name`, `buyout`, `days_to_complete`, `reward_per_volume`, `last_seen_at`, the contract-level blueprint flag, the primary label, and the composition summary. On the **detail** response only — per-item `runs` / `material_efficiency` / `time_efficiency` / `category_id` / `group_id`, since the list row no longer carries `items` at all.
New sortable fields: `reward_per_volume`, `days_to_complete`, `buyout`. **Each needs its own acceptance evidence** — Criterion 5.4 covers only `reward_per_volume`, and a sort that silently no-ops is the same defect class as a filter that silently no-ops. The plan asserts, for each, that ascending and descending produce different first rows over a fixture with distinct values.

**Per-type counts.** Segment labels carry counts, and those counts MUST reflect every other active filter — a count that ignores the search box or the price range is a lie in a numeral, worse than no count.

**The one exception is load-bearing: segment counts are computed with the `contract_type` predicate itself removed.** Reading "every active filter" literally would make every unselected segment read zero, which is both wrong and useless — the point of the counts is to tell the user what is behind the tabs they are *not* on. So: all other filters applied, type predicate lifted, grouped by type.

Two further requirements that a naive implementation gets wrong: counts are of **distinct contracts** (a grouped aggregate over an item-joined rowset inflates every multi-item contract, and would still satisfy Criterion 1.3 read superficially), and all segment counts plus the page come back in **one round trip**, not one query per segment. Criterion 1.8 governs their behavior under the ships-only default. The plan states the query shape it settled on.

**Taxonomy option list.** A companion endpoint returns the categories and groups present in the corpus with their display names, for Criterion 3.5, served from the name cache in §5 rather than resolved per request.

**Coverage metadata.** An endpoint or envelope field states which regions are actually ingested, for Criterion 7.3. The client must not hard-code this.

After any change here: `pdm run export-openapi`, then `npm run generate:api`, both regenerated artifacts committed in the same PR.

## 7. Workflow / Logic Flow

**Ingestion.** Unchanged in shape. Enrichment additionally writes the taxonomy and blueprint fields it already holds, adding no ESI calls for the ID columns because both were already resolved and thrown away. Location resolution extends to end locations per **§5.1**. Category *names* for the taxonomy cache do need a new ESI call — see §5.2, which is the one place §4.1's "not ESI calls" claim does not reach.

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

### 7.1. Single-writer resources — constraints on how the plan may decompose

The phase gate above orders the work in time. These four resources constrain how it may be split *across parallel tasks*, and violating any of them fails in a way the offending task will not see.

*   **One migration task, front-loaded.** `app/backend/src/alembic/versions/` is a linear chain. The ten new columns split naturally across taxonomy, blueprint, auction, and courier work — and four tasks each writing a migration off the same `down_revision` produce `Multiple head revisions`, which fails `alembic upgrade head`. That command is `render.yaml`'s `preDeployCommand`, so the failure lands on the **production deploy**, not the test run. All schema changes belong to a single migration authored once, before any task that depends on them.
*   **One `ENRICHMENT_VERSION` bump, in the last ingestion task.** Two tasks each writing item-level fields will each bump it. The second bump triggers a second 80-minute production resweep and invalidates the first bump's step-4 verification mid-flight.
*   **Codegen is re-run after rebase, never merged.** Every schema-touching task regenerates `openapi.json` and `schema.d.ts` wholesale, so concurrent branches conflict in generated files that CLAUDE.md forbids hand-editing. The resolution is always `pdm run export-openapi` then `npm run generate:api` on the rebased branch, never a manual merge of the artifacts.
*   **`ContractTable.tsx` is restructured once, before the segments that need it.** Both step 3 (auction, courier) and step 4 (blueprint, composition) edit the same hard-coded `<td>` block at `:112-151`. The per-column cell-renderer refactor is its own task and lands first.

**And the step-3/step-4 boundary needs a mechanism, not just an instruction.** Step 4's entry condition is an ~80-minute production resweep that no subagent can produce or observe, on a repo whose release path is a `dev` → `main` publication PR. The plan must name how step 4 waits: merged to `dev` but held from the release PR, or behind a flag, or a separate release train. "Verify before exposing" is not executable without one.

**State the denominator when verifying those rates.** The stored table includes contracts no longer present in ESI's public list, and both `_build_contract_rows` and `_fetch_item_rows` iterate only the freshly fetched batch — so neither backfill ever revisits a delisted contract and neither rate can approach 100% of the table. Measure against contracts seen in a recent ingestion run, not against `SELECT count(*) FROM contracts`, or the check fails for a reason that has nothing to do with this feature. The same population-mixing warning as §1.

The plan must make step 4 an independently verifiable unit separate from step 2. A single PR that migrates, ingests, and exposes the item-level surface cannot satisfy this, because the resweep takes roughly 80 minutes of production runtime and cannot be verified inside the deploy that triggers it.

**Query.** `contract_type` and taxonomy filters compose with the existing filter set. Derived ratios are computed in SQL for sortability.

**Render.** The active contract-type segment selects a column set; the row renderer is shared. Column definitions move into their own module rather than living inside `ContractTable.tsx`.

**This is a larger change than "extract the array."** The six-entry `COLUMNS` array (`ContractTable.tsx:14-33`) drives only the `<thead>`; the six `<td>`s are hard-coded inline at `:112-151` and are not derived from it. Extracting `COLUMNS` alone yields per-segment *headers* over a fixed body — worse than doing nothing, because the columns would no longer describe the cells. The body must first be restructured into per-column cell renderers so that a column definition carries both its header and its cell. The plan sizes this as a component refactor, not a constant move.

## 8. UI/UX Considerations

*   **Type-aware rows, shared frame.** One table component, per-segment column sets. Adding the abyssal shape later must not require touching the frame.

*   **The five "row shapes" are two orthogonal axes, not five mutually exclusive cases.** This has to be stated because the shapes visibly overlap — an auction can be multi-item and can contain several blueprint copies — and an implementer handed five overlapping labels will invent a precedence rule of their own.

    **Axis 1, the segment, comes from `Contract.type`** and is disjoint by construction: item exchange, auction, courier. It selects the columns that describe the *contract* — price, or current bid and buyout, or route and reward.

    **Axis 2, the row body, comes from item composition** and applies within any item-bearing segment: single item, or multi-item composition summary. Courier has no second axis because ESI returns it no items.

    **Blueprint columns are per-row cell content within the item-exchange and auction segments, not a segment of their own.** The columns are always present in those segments; what varies is whether a given row has values to put in them.

    **The discriminator, stated so it admits one reading:** runs, ME, and TE render when the contract has **exactly one offered item that is a blueprint copy**. Other offered items may be present — a contract holding one BPC and one hull still shows that BPC's values, because there is no ambiguity about which blueprint they describe. A contract holding *two or more* offered blueprint copies has no single ME/TE to report, so those cells read as a count ("3 BPCs") linking to the detail view rather than showing one arbitrary blueprint's numbers. Non-blueprint rows leave the cells empty.

    This satisfies Story 2's "first-class columns" (they are real columns in the segment's column set, sortable and filterable) without inventing a blueprint segment that would fragment the type-based segmentation.

*   **One live semantic disagreement must be resolved, not inherited.** Two blueprint-copy predicates already exist in the codebase and they disagree: the backend's `_has_blueprint_copy_item()` ignores `is_included` (`contract_service.py:91-112`), while the frontend's `contractIsBpc` requires it (`ContractTable.tsx:36`). §3.1 settles it — **offered items only** — and the contract-level flag §4.1 adds must use that rule. Left unreconciled, the served flag would silently disagree with the `is_bpc` filter that selected the rows it appears on, and it would disagree specifically on want-to-buy contracts, which is what Story 8 is about. The backend predicate is the one that changes.
*   **Cascading taxonomy filter.** Category first, then group scoped to that category with type-ahead. A flat group list is not viable: the Module category alone contains hundreds of groups.
*   **No distance figure of any kind on the courier row in this feature.** Reward per m³ is the normalization; jumps, reward per jump, and route-security tiers all belong to the deferred work (§4.2), and the design rules that govern them are recorded in §15.2 so they are not re-derived. A row must not imply a distance it cannot compute — an unlabelled "route" column reading `Jita → Amarr` is fine; anything that reads as *near* or *far* is not.
*   **Unknown is not blank.** Player structures cannot be resolved without ACL-scoped tokens, so some courier endpoints have no name. Measured across 115 Forge couriers: about **9–10% have at least one** unresolvable endpoint, of which **~5% (6 of 115) are the destination** and ~3% the origin. Those cells must read as "unknown structure" — not blank, not an ID, and not a fabricated placeholder that reads like a real station. This is the same honesty rule §2.2 of the gap analysis criticized a competitor for breaking by rendering `Unknown Structure` at a fake security rating.
*   **Full ISK figures and relative expiry are retained** — both are existing advantages over the surveyed competition.
*   **Coverage statements over silent empty results.** Selecting an uningested region must explain, not return an empty table.

## 9. Error Handling & Edge Cases (Required)

*   **Divide by zero on volume.** Reward per m³ must guard against a zero or missing `volume`.
*   **Blueprint originals.** `runs` is absent, not `-1`, on the public route (ESI-3). Filters and display must treat absence as "not a copy," never as zero runs.
*   **`is_blueprint_copy` absence.** ESI omits the flag for non-copies; the filter must treat NULL as not-a-copy. Fixed previously; the taxonomy work must not regress it.
*   **Unresolvable locations.** Player structures cannot be resolved without ACL-scoped tokens, so `end_location_system_id` stays NULL for **about 5% of couriers** (6 of 115 measured) and the destination surfaces as "unknown" rather than blank or zero. The ~9–10% figure that appears in the spike is the *both-endpoints* rate; do not attach it to this column.
*   **Partial enrichment, and a narrow scope mismatch this feature creates.** The existing `ENRICHMENT_INCOMPLETE` semantics extend to the new fields: a contract whose taxonomy failed to resolve must not be stamped `COMPLETED`. The completion predicate has two halves and **only one is narrowed**: the `type_name is None` half already covers excluded items, while the *category* half is scoped to included items via `unresolved_category_contract_ids` (`background_aggregation.py:796-799`), because the only thing it gated was the ship flag, which only offered items decide. Criterion 8.1 renders requested items and Criterion 6.3 summarizes them by category — so a contract whose *requested* item failed **category** resolution would be stamped `COMPLETED`, excluded from every future re-fetch, and display a permanently blank want-to-buy side with no route back. Widening the category half is a small, specific change; the plan must state that it made it.
*   **Serialization strictness.** A non-optional schema field over a nullable column fails the entire page, not one row, because `PaginatedResponse` validates every item. Every new field is optional in the response schema unless it is provably non-null for every row.

## 10. Security Considerations

*   No new authentication surface. All consumed endpoints are public and unauthenticated.
*   No PII in instrumentation. Filter dimensions only — no user identifiers, no free-text search contents. **This is currently violated by code this feature extends** (`contract_service.py:314-326`, `:405`, `:429` log `filters.search` verbatim); §4.1 makes fixing it part of the instrumentation work rather than leaving a task to add clean fields next to dirty ones.
*   New filter parameters are typed and bounded by Pydantic, reaching the database only through the ORM.
*   End-location resolution reuses the existing bounded-concurrency helper and the NPC-station-ID guard that avoids spending ESI error budget on requests guaranteed to 401.

## 11. Performance Considerations

*   End-location station resolution is bounded by distinct stations, not contract count, and its steady-state cost depends on the widening in §5.1.
*   Derived ratios (reward per m³) are computed in SQL so they sort without loading the page into the application.
*   Filtering on contract type reuses `Contract.type`, already covered by the composite `ix_contracts_type_status`. The plan verifies whether that composite serves a type-only predicate or whether a companion index is warranted — it does not assume either. New taxonomy columns (`category_id`, `group_id`) do need indexes; the plan specifies which, informed by the existing set.
*   **Adding a sortable field touches five places, not one.** `reward_per_volume` needs a `SORT_MAP` entry (`contract_service.py:27-34`), a new `SortableContractFields` member — which `SavedSearchParameters.sort_by` also consumes (§14) — a matching entry in the frontend's duplicated `SORT_FIELDS` (`features/contracts/filters.ts:1-9`), regenerated client types, and it must work through the grouped-subquery pagination path that SQLA-1 governs. A sort on a computed ratio is not a one-line addition.
*   The `ENRICHMENT_VERSION` bump (§7) triggers a one-off full-corpus resweep of roughly 80 minutes. It is a planned deploy-time cost, not a steady-state one.
*   Per-type counts must not degenerate into one query per segment.

## 12. Accessibility Considerations

*   Contract-type segmentation must be keyboard-navigable and expose its selected state to assistive technology.
*   The cascading filter must announce that changing category changes the available groups.
*   An unknown courier destination must be conveyed textually, not by colour or a dash alone.
*   Existing a11y tests (`src/features/contracts/components/a11y.test.tsx`) extend to the new controls.

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

F002's criteria 4.3–4.5 and its §15 implementation note place a market-group category filter in MVP scope, backed by a `GET /ships/market_groups` endpoint sourced from ESI `/v1/markets/groups/`. The M1 frontend design deferred it, correctly, because that endpoint does not exist. The conflict was never resolved.

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

**From research spikes, single-source, and some of it IS in scope:** the courier population counts and endpoint-resolvability rates are load-bearing here — they set the ~5% NULL rate in §5 and §9, the station-resolution cost in §7 and §11, and the "115 contracts, a thin tab" honesty statement in §15.2. Treat them as measurements to confirm, not as settled facts. The ESI route divergences and the Adam4EVE, PushX, and EVE University observations govern deferred work only, and nothing in this feature's implementation rests on those.

**Sampled, not census:** the 87%-NULL market-group figure (§15.1), which §15.1 already schedules for re-measurement.

### 15.4. On the evidence base

The case for this feature is supply-side: the data is already fetched, enriched, and stored, and the competitive field is empty. There is no demand evidence — no user request for BPC or courier browsing, no traffic data, no search terms. The application has one user today and has not been advertised, so no adoption metric could produce signal at this stage.

This is recorded rather than resolved. The instrumentation in §4.1 exists so that the question becomes answerable later; it is deliberately not framed as a success criterion now.

## 16. AI Implementation Guidance

### 16.1. Read before implementing

`docs/pitfalls/implementation-pitfalls.md` and `docs/pitfalls/testing-pitfalls.md` in full.

**Read SQLA-3 and TEST-19 first, before anything else.** SQLA-3 — "a per-row predicate over a one-to-many join cannot classify the parent" — is not a general caution here, it describes **every item-level filter this feature touches**: the category/group filter (Criterion 3.2), the runs filter (2.3), the ME/TE filters (2.5), the offered-only composition counts (6.3), and the want-to-buy split (8.1). The runs filter is *already written* in this shape (`contract_service.py:197-200`), so making it functional without changing its shape ports the `is_bpc` defect onto a new column rather than fixing it. The `is_bpc` filter is the worked example: a contract bundling a blueprint copy with a hull matched both `is_bpc=true` *and* `is_bpc=false`, returning under a filter and its own negation, with totals quietly exceeding the corpus. Every filter listed above is the same shape and will fail the same way unless written against **§3.1**, which defines the contract-level predicate they all share.

Also directly load-bearing: **ESI-3** (originals omit `runs`), **FASTAPI-1** (`Annotated[Model, Query()]`, never bare `Depends`, for GET filter models), **FASTAPI-2** (the inert ME/TE params — Criterion 2.5), **FASTAPI-3** (a response field stricter than its column 500s the whole page, not one row — governs every new optional field in §9), **PROXY-1** (no `/api/v1` in FastAPI), **SQLA-1** (pagination over joins, which the new sort field must pass through), **SQLA-2**, **ENV-2/ENV-3** (every backend `.py` save under reload wipes the database — batch edits), **TEST-14** (never pair `pytest.mark.vcr` with an app-client fixture), **TEST-19**, **TEST-20** (assertions inside `if data["items"]:` never run). **ESI-4** matters to the deferred route work, not to any call this feature makes.

### 16.2. Critical logic points

*   Taxonomy persistence happens where both values are already in scope: `group_id` at `background_aggregation.py:771-775`, `category_id` on the group record read at `:783`. Resist the urge to add an ESI call for either.
*   Location resolution: follow **§5.1** exactly. Two of three paths need widening, and the one that is easy to miss is the cache read, not the fetch — skipping it costs nothing at first and then costs an ESI call per destination station on every run forever.
*   The response-model split in Criterion 6.4 is the change most likely to be done wrong. Dropping the eager-load without splitting the model leaves a schema that advertises a field it no longer sends.
*   Every new response field is optional unless provably non-null for all rows (§9).
*   Nothing in this feature calls `/route/`. If you find yourself needing an ESI route call, you have wandered into the deferred work in §4.2.

### 16.3. Testing focus

TDD is mandatory for all production code here. Specific traps this feature is prone to:

*   **Every item-level filter test needs a mixed-child parent (TEST-19)** — taxonomy, runs, ME, and TE alike, not taxonomy alone. A fixture whose contract holds exactly one item passes identically whether the query classifies the *contract* or the *row*; the readings diverge only when one contract holds children of both kinds. So for each filter: seed a contract holding both a matching and a non-matching offered item. What it must assert differs by family — the boolean `is_bpc` fixture lands in exactly one branch (negation-derived complements); a range family's straddling fixture appears in both single-bound branches and is excluded by a same-item window, per §3.1. **The assertion form is §3.1's identity — `branch_a + branch_b - both + neither == unfiltered`, with the expected `neither` and `both` counts stated in the fixture.** A two-way sum is wrong for every filter in this feature except the boolean `is_bpc`. Coverage built from single-item contracts says nothing about the semantics that matter.
*   **Fixtures must carry the production data shape.** Backend fixtures previously hand-wrote three columns ingestion never writes, which gave dead filters green tests. Any fixture asserting on `runs`, `is_blueprint_copy`, or taxonomy must reflect what ESI actually sends — including omitting `runs` on originals, and leaving `status` at its `"unknown"` placeholder rather than inventing a value.
*   **Assert the filters return rows.** The defect class this feature is fixing is filters that match nothing. A test asserting a 200 and an empty list would have passed against every one of those bugs.
*   **Both `tests/api/test_contracts.py` and `tests/api/test_contract_filters.py` are safe to write into.** Their `pytestmark` is `asyncio` only. The VCR markers and all five cassettes were removed on 2026-08-01 after the cassettes were found to have recorded the app talking to itself; `tests/marker_guards.py` now aborts collection if any test pairs the `vcr` marker with an app-client fixture. **Do not reinstate a `vcr` marker on either module** — that is what TEST-14 forbids, and it is enforced rather than merely documented.
*   **No assertions inside `if data["items"]:`** without seeding a fixture — a previously shipped test never executed its assertion block.
*   **Mutation-check the load-bearing tests.** Break the behaviour, confirm the test goes red, revert. A test that stays green under mutation is a finding, not a formality — restore from a file copy rather than `git checkout --`, which would discard uncommitted work and produce false evidence.
*   Frontend fixtures must not carry absolute past expiry dates; the future-clock lane exists because an entire suite silently rendered "Expired" and nothing failed.

## 17. Normative API contract

Everything in this section is binding. It exists because the backend and frontend halves of this feature will be built by different tasks, and without named models and exact field lists each side invents its own contract. Field names below are the field names; where a shape is given, it is the shape.

### 17.1. Response models

Criterion 6.4 splits the single `ContractSchema` that today serves both endpoints. Two models replace it:

**`ContractListItemSchema`** — the list row. Carries **no** `items` array.

| Field | Type | Notes |
|---|---|---|
| `contract_id`, `type`, `title`, `price`, `collateral`, `reward`, `volume`, `date_issued`, `date_expired`, `issuer_id`, `for_corporation`, `start_location_id`, `end_location_id` | as today | Unchanged from the current `ContractSchema`. |
| `start_location_name`, `end_location_name` | `str \| None` | `end_location_name` is new. |
| `buyout`, `days_to_complete` | `float \| None`, `int \| None` | New. |
| `reward_per_volume` | `float \| None` | Computed. NULL when `volume` is 0 or NULL (§9). |
| `last_seen_at` | `datetime \| None` | New; Criterion 7.1. |
| `is_blueprint_copy_contract` | `bool` | Contract-level flag, computed, offered items only (§3.1). |
| `primary_label` | `str` | Server-computed; see §17.4. |
| `composition` | `CompositionSummary \| None` | NULL for single-item and item-less contracts; see §17.2. |
| `blueprint_summary` | `BlueprintSummary \| None` | NULL unless exactly one offered BPC; see §17.3. |

**`ContractDetailSchema`** — everything in `ContractListItemSchema`, plus `items: list[ContractItemSchema]`. `ContractItemSchema` gains `runs`, `material_efficiency`, `time_efficiency`, `category_id`, `group_id` (all optional).

`ContractListResponse` becomes `PaginatedResponse[ContractListItemSchema]`.

**The generated TypeScript type changes name**, so every frontend consumer of `Contract = components['schemas']['ContractSchema']` (`lib/api/client.ts:5`, used by `ContractTable.tsx` and `ContractDetailPage.tsx`) moves in the same change. This is a single mechanical rename, but it must be planned as one unit rather than discovered.

### 17.2. `CompositionSummary`

Structured, not a pre-rendered string — the client formats it, so pluralization and truncation stay with the presentation layer.

```
{ "categories": [ { "category_id": 7, "name": "Module", "item_row_count": 3 }, ... ],
  "total_item_rows": 6,
  "total_volume": 12000.0 }
```

`categories` is sorted by `item_row_count` descending, then `name` ascending for stability. Counts are **item rows**, not summed quantities (Criterion 6.1), and cover **offered items only** (Criterion 6.3). The server does not truncate; the client decides how many to show and buckets the rest as "other".

### 17.3. `BlueprintSummary`

```
{ "runs": 10, "material_efficiency": 8, "time_efficiency": 14, "copy_count": 1 }
```

Present only when the contract has one or more offered blueprint copies. When `copy_count > 1` the three value fields are NULL and the client renders the count instead (§8).

### 17.4. `primary_label`

Server-computed, replacing the client-side `primaryLabel` in `format.ts:77-83`, which is deleted rather than kept as a fallback. The chain, in order:

1. The `type_name` of the first offered item in the Ship category, if any offered item is a ship. (This preserves the existing client-side preference; it is a move, not a redesign.)
2. The first offered item's `type_name`.
3. The contract's `title`, trimmed, if non-empty.
4. `"Courier to {end_location_name}"` for couriers, or `"Courier"` when the destination is unresolved.
5. `"Contract {contract_id}"`.

### 17.5. Segment counts

An envelope field on the list response, following the `unknown_system_excluded` precedent already on `ContractListResponse`:

```
"segment_counts": { "item_exchange": 402, "auction": 27, "courier": 115, "loan": 0, "unknown": 0 }
```

Every ESI contract type appears as a key, including zero-valued ones, so the client renders a stable set of segments. Counts are distinct contracts, computed with the `contract_type` predicate lifted and all other filters applied (§6.2). **"One round trip" means one HTTP response, not one SQL statement** — a separate grouped query alongside the existing count and page queries is correct and expected.

### 17.6. Taxonomy options endpoint

`GET /contracts/taxonomy` — flat, not nested, so the client filters the group list locally without a refetch on category change.

```
{ "categories": [ { "category_id": 6, "name": "Ship" }, ... ],
  "groups": [ { "group_id": 25, "category_id": 6, "name": "Frigate" }, ... ],
  "coverage": "partial" | "complete" }
```

`coverage` is `"partial"` while the taxonomy cache is still filling (§5.2), and the client must surface that rather than presenting a partial list as the whole taxonomy.

### 17.7. Coverage metadata

An envelope field on the list response, not a second endpoint — it is needed on every render of the filter rail and a separate query would double the request count for no benefit.

```
"coverage": { "ingested_region_ids": [10000002], "as_of": "2026-08-02T11:04:00Z" }
```

Sourced from **observed reality** (`SELECT DISTINCT start_location_region_id`), not from `Settings.AGGREGATION_REGION_IDS`, per Criterion 7.4 — configured-but-not-yet-ingested is exactly the state that would mislead. Region display names come from the static `regions.ts` map the frontend already ships.

### 17.8. `contract_type` parameter shape

`Optional[List[str]]` bound via `Annotated[ContractFilters, Query()]` per FASTAPI-1, matching the existing `region_ids` pattern, and **typed as an enum so an unknown value returns 422** rather than silently matching nothing. A bare `str` would reintroduce the exact defect class this feature exists to remove. The segmentation UI sends a single value; the list shape leaves multi-select available without an API change.
