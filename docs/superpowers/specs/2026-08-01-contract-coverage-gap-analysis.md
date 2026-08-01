<!-- ABOUTME: Gap analysis of Hangar Bay vs EVE Workbench's market tool and the wider EVE marketplace-tool ecosystem, -->
<!-- ABOUTME: motivating the decision to display all ingested contract types (not just ships) and sketching an MCP surface. -->

# Contract coverage gap analysis: Hangar Bay vs EVE Workbench and the marketplace-tool ecosystem

**Date:** 2026-08-01
**Status:** Analysis complete; decisions pending Sam
**Prompting question:** "Should we at least display the data for all these other contracts we're ingesting besides plain ships?"

## 0. Method and evidence quality

Five parallel research lanes, run 2026-08-01 (Opus/Sonnet subagents; findings synthesized here):

1. **EVE Workbench live recon** — drove the rendered site (v2.2.0) anonymously; extracted the full Angular route table (62 routes) and grepped the shipped JS bundle for contract features. High confidence.
2. **Hangar Bay code + prod inventory** — file:line-verified pass over ingestion, API, and frontend; prod quantification via the public API (live corpus `total` counts are exact; contract-type/category breakdowns are a 12.7% systematic sample, validated by matching the sampled BPC rate 49.6% against the exact 49.7%). Render MCP was unauthorized, so these are *live visible corpus* numbers, not raw table counts.
3. **Ecosystem recon** — Adam4EVE, MutaMarket, EVE Ref, EVE Tycoon, Fuzzwork, Janice, jita.space, via server-rendered HTML, public API specs, and app bundles. Mostly primary-source; flagged inferences noted inline.
4. **Domain research** — ESI public-contracts schema, player use-cases per contract type, appraisal-source conventions. ESI schema facts verified against the OpenAPI spec.
5. **MCP surface research** — see §7.

A parallel verify-and-fix lane confirmed the defects in §4.4 and is producing a Review-classified PR from branch `claude/contract-filter-bugfixes`.

## 1. Headline findings

1. **We already ingest the whole market and display 1.2% of it.** The live Forge corpus is 33,817 contracts; 411 are ship-flagged. All three contract types are stored; items are fetched for every item_exchange and auction; the ships-only view is purely a client-side default (`ships_only` in `app/frontend/web/src/features/contracts/filters.ts`). The "All Contracts" view already ships behind one checkbox — unlabeled, un-columned, and un-designed for what it contains.
2. **The non-ship market is BPCs and abyssals, not junk.** 49.1% of live contracts contain a blueprint copy (16,609 — ~40× the ship market by count). The top non-ship item types cluster into abyssal/mutated modules and capital-component blueprints, plus skill injectors and containers. These are exactly the item classes that *cannot* trade on the regular market — contracts are their only marketplace.
3. **EVE Workbench has no contracts feature at all.** Confirmed definitively: no contract route among all 62 routes; the word "contract" appears in their bundle only as paste-source instructions for their appraisal/refinery tools. Their market tool is a plain order browser (no charts, stats, or derived metrics).
4. **The competitive void is real and specific.** Across the seven surveyed tools, only Adam4EVE browses public contracts — and it is maintenance-only (© 2013-2021, "not being developed further"), returning `Too many connections` on roughly half of requests. MutaMarket proves the model works but covers only abyssal modules. EVE Tycoon's contract features are personal-history-only behind a paid tier. **Nobody in the ecosystem handles courier contracts.**
5. **We drop, at ingestion, exactly the fields the non-ship market runs on.** BPC `runs`/`material_efficiency`/`time_efficiency` are in the ESI items payload and never persisted; auction `buyout` is never ingested; item `group_id`/`category_id` are fetched during enrichment then discarded (`category` is a ship/not-ship boolean, `app/backend/src/fastapi_app/services/background_aggregation.py:692`). Displaying non-ship contracts well is therefore mostly an **ingestion-fields + taxonomy + presentation** problem, not a pipeline problem.

## 2. Gap analysis vs EVE Workbench's market tool

EVE Workbench's market browser (`/market/:orderType/:regionId/:locationId/:id`) is the tool Sam asked to compare against. It browses **market orders**, which is adjacent to but distinct from our contracts domain; the useful comparison is UX mechanics, not data.

### 2.1 What they have that we lack

| EVE Workbench feature | Hangar Bay today | Assessment |
|---|---|---|
| Hierarchical market-group tree with in-place search that preserves ancestor paths | Free-text search only; no taxonomy UI at all | **Adopt** — needs persisted `group_id`/`category_id` (§4.1). Best-in-survey pattern for "where do things live" |
| Scope-preserving links (item links carry active region/station scope) | Filters live in the URL (good) but no equivalent cross-navigation | Adopt where taxonomy navigation lands |
| Sell/Buy tabs with live counts in the label | Single list; no count-bearing segmentation | Adopt for contract-type segmentation (exchange/auction/courier tabs with counts) |
| Location scoping to station level, security-status chips on stations | Region filter only (and only one region has data — §4.3); no security display | Adopt security chips; station scoping already has an unused `station_ids` API filter |
| "My current location" → contextual sortable `Jumps` column | Nothing | Adopt eventually — Adam4EVE proves the contract-market version (jumps + route-security tooltip) |
| `remaining / total` quantity in one cell | n/a (contracts don't partial-fill) | n/a |
| Deep-linkable, server-rendered first paint (SEO/sharing) | SPA | Relevant to the M5 trust/shareability theme (see `docs/superpowers/specs/2026-07-26-m5-trust-shareability-design.md`) |
| Item info modal (dogma attributes, description, variations) | Type names only | Cheap alternative: deep-link item rows to everef.net/types/{id} instead of building an item encyclopedia |

### 2.2 What they get wrong (traps to avoid)

- **Abbreviated-only prices** (`4.72M`, no exact figure anywhere) — unusable for margin decisions. We show full ISK; keep it.
- **Absolute-only expiry timestamps** on the one table where time pressure matters. Contracts need relative countdowns with urgency treatment (we already render time-left).
- **No summary statistics of any kind** — no median/spread/history. Their market tool is a raw dump; the LP Store's `ISK/LP` default-sort is the only derived metric on the site, and it's their best page. Lesson: **a computed profitability metric as the default sort is the product** (maps to the parked appraisal direction, `docs/superpowers/specs/2026-07-26-m5-direction-options.md`).
- **Silent filter no-ops** — "PLEX in Aridia" renders Jita orders because CCP's global PLEX pseudo-region ignores the region scope, and the UI asserts a scope it didn't apply. We have the same defect class live today (`system_ids` matches zero rows, §4.4) — an empty-state-or-explain rule should be a product invariant.
- **No error states** (failed backend call → infinite spinner) and **`Unknown Structure` at security `-0.5`** for unresolvable player structures — dishonest fallbacks.

### 2.3 What we already do better

Full ISK prices, relative expiry, honest empty states, liveness watermarking (`last_seen_at` per region), typed OpenAPI client, and a contracts domain they don't touch at all. EVE Workbench's strength is breadth of adjacent tools (fits, appraisal, refinery, LP store) and anonymous-friendly personalization — not market UX depth.

## 3. What the wider ecosystem teaches about displaying non-ship contracts

Full per-tool detail lives in the recon lane's report; this section keeps what changes our decisions.

### 3.1 Type-specific summary rows, not one universal table

The consistent lesson across MutaMarket, Adam4EVE, and EVE Tycoon: browse rows lead with a **compact, type-aware summary**; itemization is the detail view's job.

| Contract shape | Row leads with | Distinctive fields | Valuation display |
|---|---|---|---|
| Single-item exchange | the item | quantity | ask vs market price, margin % |
| Multi-item ("loot pile") | composition counts (MutaMarket pattern: e.g. `3 modules · 1 BPC · 2 other`) + total m³ | priced-vs-unpriced coverage (Adam4EVE `NoP` column) | ask vs buy-side AND sell-side totals; optionally reprocess value (Fuzzwork) |
| BPC | name + **ME / TE / Runs as first-class columns** | BPO-vs-BPC flag | never silently price at type market price — either refuse-and-flag (EVE Tycoon) or price per (type, ME, TE, runs) tuple (Adam4EVE) |
| Abyssal/mutated | base module + mutaplasmid | roll-quality score; per-attribute value + signed delta | estimate with error bars + sample count, or explicit "no estimate" (MutaMarket). Note: rolled stats are NOT in ESI public-contract data; parity with MutaMarket needs another source |
| Courier | route (origin → destination), jumps | reward, collateral, volume, days_to_complete | reward/jump and reward/m³ — the ratios haulers sort on |
| Auction | current-bid + countdown | bid count, buyout | requires ingesting `buyout` (§4.2) and the bids endpoint (bidder identity is not public) |

### 3.2 Valuation display conventions (unanimous across serious tools)

Recorded here because appraisal is the parked headline feature; these are the table stakes when it lands:

1. **Never a single price** — buy-side and sell-side (or buy/split/sell à la Janice) always shown together.
2. **Medians beside spot prices** (Janice: 5-day and 30-day) — contract items are disproportionately thin-market.
3. **Reject outliers and publish the rejection** (EVE Tycoon returns thresholds + excluded-order counts) — contract markets are scam-rich.
4. **Coverage/provenance as a visible, filterable column** — Adam4EVE's `NoP`/`NMkt?` columns; EVE Tycoon's per-row tinted `Appraisal Method`. The single most transferable idea in the survey.

### 3.3 Cheap differentiators nobody (or almost nobody) does

- **"Open in EVE client" via ESI `POST /ui/openwindow/contract/`** — only Adam4EVE has it; we already have EVE SSO from M2, making this nearly free and closing the browse→buy loop.
- **Symmetric want-to-buy handling** — render "items received" and "items to deliver" as twin tables (`is_included=false` items); expose want-to-buy as a filter. We already store `is_included`.
- **Courier browsing at all** — a wholly unoccupied niche; we already store ~173 live couriers (with zero item rows, correctly — couriers have no items).
- **`last_seen_at` as a user-facing column and filter** — the only staleness signal an ESI ingester has; we compute it and never show it.

## 4. The internal gap: ingested-but-invisible, dropped-at-ingestion, and defects

### 4.1 Fetched-then-discarded taxonomy (the enabling gap)

Enrichment already resolves each item's `group_id` and `category_id` from ESI and keeps only a ship/not-ship boolean (`background_aggregation.py:683-695`). `EsiMarketGroupCache` is an unused empty-shell model. Persisting group/category unlocks every category-filter promise in `design/features/F002-Ship-Browsing-Advanced-Search-Filtering.md` and the type-aware rows in §3.1. **Caveat measured in prod:** `market_group_id` is ~87% NULL on sampled non-ship items (abyssal items are off-market), so the taxonomy must be dogma category/group based, not market-group based.

### 4.2 Dropped ESI fields

| Field | ESI has it | We store | Blocks |
|---|---|---|---|
| item `runs`, `material_efficiency`, `time_efficiency` | yes (items endpoint) | no | real ME/TE/runs filters (currently inert per pitfall FASTAPI-2; runs filter mis-wired to `raw_quantity`), honest BPC display for 49% of the corpus |
| contract `buyout` | yes | no | any meaningful auction display (~527 live auctions show only starting bid) |
| contract `days_to_complete` | yes | no | courier display |
| auction bids (`/contracts/public/bids/`) | yes (no bidder identity) | not fetched | current-bid display |

### 4.3 Region coverage

One region ingested (The Forge) while the frontend offers a 70-region filter — 69 of which can never match. Multi-region is an explicit M5 non-goal (`2026-07-26-m5-trust-shareability-design.md`); noted here because several ecosystem patterns (jumps-from-my-location, route security) only pay off with broader coverage.

### 4.4 Defects (verification + fixes in flight on `claude/contract-filter-bugfixes`)

1. `is_bpc=false` matches zero rows (`is_blueprint_copy` is True-or-NULL; empirically `total: 0` in prod).
2. `system_ids` filter matches zero rows (`start_location_system_id` never populated by ingestion).
3. Courier contracts render as "Exchange" in both table and detail views (two-way badge assumes exchange/auction).
4. Courier serialization 500 risk: `ContractSchema.start_location_id` non-optional over a nullable column, reachable via the shipped `ships_only=false` view.
5. `collateral` is filterable and sortable but absent from every response schema.
6. `min_runs`/`max_runs` filters `raw_quantity`, which is not a run count (deferred to the product plan — the correct fix is ingesting `runs`, §4.2).
7. `status` is always the literal `"unknown"` and `date_completed` always NULL (fields don't exist in public ESI data); `date_completed` is used as an always-true liveness predicate in the watchlist matcher (dead-code class, report-only).

## 5. Where the specs already stand

- The ships-only **default** is decided (PRODUCT.md: non-ship reachable by explicit toggle, "never the default noise") — this analysis does not challenge it. What's absent is any spec for what the non-ship view *is*: it's defended as a shipped non-regression in the M5 ingestion designs yet has no product spec, no design treatment, and no name.
- Contract-type filtering was promised (F002 Story 7/Criterion 6.1) then explicitly deferred in the M1 design ("no such filter param exists"). Two spec conflicts need reconciling: F002's market-group filter is simultaneously MVP-scoped (F002) and deferred-no-backing-API (M1 design); courier handling has no written policy at all.
- Appraisal is formally parked as the likely headline feature with a named re-ordering trigger (`2026-07-26-m5-direction-options.md`). §3.2 above is the display contract for when it lands.

## 6. Recommendation

**Yes — display what we ingest.** The data is already paid for (fetched, enriched, stored); the audience (BPC and abyssal buyers) has no living alternative; the incumbent-shaped competitor (Adam4EVE) is decaying; and EVE Workbench — the strongest general EVE tools site — has left contracts entirely unoccupied. The risk is not building it; the risk is shipping the current unlabeled "All Contracts" checkbox view as if it were the feature.

Sequenced shape (sizes are relative; a plan would firm these up):

1. **Now / small — stop being wrong.** Land the defect fixes (§4.4, PR in flight). Cost: already spent.
2. **Foundation / medium — ingest what we throw away.** Persist item `category_id`/`group_id`; ingest `runs`/ME/TE, `buyout`, `days_to_complete`. Schema migrations + enrichment changes + client regeneration. This unblocks everything else and makes three inert filter families real.
3. **Presentation / medium-large — the type-aware browse view.** Contract-type tabs with counts; type-specific summary rows per §3.1; courier columns (route, reward, collateral); BPC columns (ME/TE/runs); want-to-buy symmetry; `last_seen_at` surfaced. This is the actual "display the data" milestone and needs its own feature spec (an F008) reconciling the F002-vs-M1 conflicts.
4. **Later / large — valuation.** Unchanged from the M5 direction doc, but §3.2's conventions become requirements, and Adam4EVE's per-(type, ME, TE, runs) BPC pricing plus MutaMarket's published-error-bars model are the reference implementations.

Abyssal roll-stats (MutaMarket parity) are explicitly out: ESI public-contract data doesn't carry rolled attributes, so that's a different-data-source product decision, not a display gap.

## 7. MCP surface for Hangar Bay's final form

*(Pending — a research lane on MCP prior art, consumer personas, proposed tool surface, and hosting/auth considerations is in flight; this section will be filled in when it reports.)*

## Appendix A. Reasoning notes and uncertainties

**Why the comparison target shifted.** The prompting question named EVE Workbench's market tool, but recon established it browses market *orders* and has zero contract features — so a feature-parity comparison would answer the wrong question. The analysis therefore treats EVE Workbench as a UX-mechanics reference (§2) and the real gap analysis as Hangar Bay vs the contract-tool ecosystem (§3) plus Hangar Bay vs its own ingested data (§4). That reframing is the load-bearing judgment call in this doc.

**What I'm still uncertain about.**
- Adam4EVE's per-commodity contract price-history methodology (single-item contracts only?) is inferred from page shape; its explanation is an image we couldn't OCR-verify. Confirm before building per-type BPC price history on the same model.
- Prod numbers are live-visible-corpus counts via the public API, not raw SQL (Render MCP unauthorized this session); type/category breakdowns are a validated 12.7% sample. Directionally solid; not a census.
- EVE Workbench's logged-in surface (developer applications, personal access tokens) was unreachable anonymously — they may expose a third-party API whose shape we haven't seen.

**Considered and set aside.**
- *Matching EVE Workbench's market-order browsing* (i.e., adding a market-orders view to Hangar Bay): rejected — crowded space (Fuzzwork, EVE Tycoon, Adam4EVE, jita.space all do it), zero differentiation, and orthogonal to our ingestion asset.
- *Market-group-based taxonomy* for the category filter: rejected on measurement — ~87% NULL coverage precisely where non-ship volume concentrates; dogma category/group is the viable axis.
- *Changing the ships-only default*: not proposed — PRODUCT.md's default stands; this analysis argues for making the non-default view real, not for changing the default.

**Things almost missed.** The `system_ids`/`is_bpc=false` dead filters surfaced only because the inventory lane checked filter columns against ingestion writes rather than trusting the API schema — the same defect class (silent filter no-op) then showed up independently in EVE Workbench's PLEX/region behavior, which is what promoted "empty-state-or-explain" from a bug fix to a proposed product invariant.
