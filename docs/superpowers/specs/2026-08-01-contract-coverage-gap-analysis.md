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

A parallel verify-and-fix lane independently confirmed all §4.4 defects (correcting recon's causal story on two) and produced the Review-classified [PR #98](https://github.com/scarson/hangar-bay/pull/98). A sixth lane researched the MCP protocol/hosting landscape (§7 and companion doc).

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

### 4.4 Defects — independently verified; four fixed in [PR #98](https://github.com/scarson/hangar-bay/pull/98) (Review — serialization contract; awaiting Sam)

| # | Defect | Verdict | Action |
|---|---|---|---|
| 1 | `is_bpc=false` matches zero rows | Confirmed | **Fixed** (filter treats NULL as not-a-BPC) |
| 2 | `system_ids` matches zero rows (column never populated) | Confirmed | Deferred — needs a location→system cache (see below) |
| 3 | Courier serialization 500 (`start_location_id` non-optional over nullable column) | Confirmed, **worse than reported** — one null row 500s the whole page of 50, since `PaginatedResponse` validates every item | **Fixed** |
| 4 | Courier renders as "Exchange" | Confirmed | **Fixed** (renders "Courier") |
| 5 | `collateral` filterable/sortable but never returned | Confirmed | **Fixed** (added to response schema; client chain regenerated) |
| 6 | `min_runs`/`max_runs` wired to `raw_quantity` | Confirmed, **cause corrected** — `raw_quantity` doesn't exist on the *public* items route at all (authenticated routes only), so the column is permanently NULL | Deferred to the §6 phase-2 plan (ingest `runs`) |
| 7 | `status` always `"unknown"`, `date_completed` always NULL | Confirmed; one real behavioral gap found (below) | Reported |

Verification corrections and new findings from the fix lane (full evidence in the PR):

- **Defect 1's cause was mis-diagnosed by recon:** ingestion *does* map `is_blueprint_copy`; ESI simply omits the flag for non-copies (live sample of 1,658 public item rows: `true` 1,396×, absent 262×, `false` never). The bug was purely the filter's `col == False` NULL semantics.
- **ESI public-vs-authenticated schema split matters for §4.2:** `runs` is public (present on exactly the BPC rows), but the documented `runs == -1` for originals **never occurs on the public route** — originals omit the field. A naive implementation of the runs filter would be wrong; recorded as a pitfall (ESI-2) in PR #98 alongside FASTAPI-3, TEST-17, TEST-18.
- **Root cause behind three false-passing tests:** the backend test fixture hand-wrote three columns ingestion never writes (`is_blueprint_copy=False`, `raw_quantity`, `start_location_system_id`) — a data shape ESI cannot produce — so the dead filters had green tests. The fixture now carries the production shape and documents what it still fakes.
- **New: watchlist notifications outlive purchase.** The watchlist matcher filters on expiry plus the always-true `date_completed IS NULL`, and does *not* use the per-region `last_seen_at` watermark the list view uses — so an already-accepted contract keeps generating notifications until its expiry date (up to two weeks). Deferred because the fix changes notification semantics; recommended fix is reusing the watermark predicate.
- **`system_ids` sizing:** ESI's public payload has no system id; `/v1/universe/stations/` resolution covers 97.1% of sampled start locations (player structures need ACL-scoped tokens and would stay NULL); only 160 distinct locations across 7,292 contracts, so a location→system cache table is tiny. Deferred as a design decision, param left in place.
- The lane also fixed a **pre-existing red test on `origin/dev`** (a hard-coded 2026-07-31 expiry under a liveness predicate — detonated on 2026-08-01, before this work started).

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

Full research in the companion doc `2026-08-01-mcp-surface-research.md` (prior art, personas, tool sketches, auth/hosting/license analysis). The decision-relevant summary:

- **The gap is a moat, not just a hole.** Every existing EVE MCP server is a thin ESI wrapper and none touch contracts — because ESI's public-contract surface structurally cannot answer "find me a cheap fitted Ishtar near Jita" without first ingesting an entire region (one items call per contract, ~33.8k calls). Hangar Bay is the only party that has already paid that cost; an MCP surface converts a differentiated website into differentiated infrastructure.
- **Small, hand-designed, read-only v1.** Roughly five to seven `hangarbay_*` tools — contract search (ranked shortlist, default limit 10, concise projection without full item lists), contract detail, name⇄id resolution, an aggregation/summary tool, and (only after appraisal ships) an appraise tool whose schema makes partial valuations impossible to launder into confident prose. Explicitly **not** OpenAPI auto-generation, which would faithfully reproduce our inert ME/TE params, the broken runs filter, and a token-bomb response schema — and which Anthropic's connector review criteria and the empirical record both reject.
- **Authenticated `/me/*` stays web-only for now.** The MCP auth spec requires an OAuth 2.1 authorization server that Hangar Bay operates; EVE SSO cannot fill that role (no dynamic client registration, no RFC 8707, wrong token audience) and would sit federated *behind* our AS. That is a milestone of its own; a read-only public server is fully spec-conformant without it.
- **Sequencing: downstream of M5, not parallel.** Freshness (`data_as_of`/`data_stale` in every payload, escalated in words, not just booleans), sold/delisted liveness filtering, and honest coverage signaling ("no data for Amarr", never an empty list) are *preconditions* for an agent-facing surface — an agent laundering a stale row into confident prose is this surface's worst failure mode. API rate limiting is net-new mandatory work (none exists today).
- **License shapes the strategy:** the CCP developer license forbids monetization, so "free backend" risk is managed operationally (free API keys for attribution/quota), and nobody else can build a paid product on our back either. ESI-data redistribution is unaddressed-but-precedented (EVE Ref, zKillboard, Fuzzwork); a short question to CCP's third-party dev channel is cheap insurance.
- **Timing note:** the MCP spec had a breaking revision on 2026-07-28; the official Python SDK v2 supports it (and serves older clients) as of the same day, while Claude-side client support is still rolling out. A deliberately small tool surface is also the hedge against further protocol churn.

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
