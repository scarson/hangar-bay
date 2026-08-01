<!-- ABOUTME: Design-space research for a Hangar Bay MCP server — prior art, consumer personas, a proposed seven-tool -->
<!-- ABOUTME: surface, auth/rate-limit/hosting considerations, and CCP-license constraints. Companion to the 2026-08-01 gap analysis. -->

# Hangar Bay MCP surface — design-space research

**Date:** 2026-08-01
**Status:** Research; no decisions taken. Companion to `2026-08-01-contract-coverage-gap-analysis.md` (§7 there summarizes this doc).
**Provenance:** Opus research agent output, lightly edited for formatting. All claims were verified by the agent against primary sources (spec pages, GitHub repos, the CCP license, and this repo); unverified items are flagged inline.

**Biggest single finding up front:** the MCP spec revision changed on **2026-07-28 — days before this research** ([versioning](https://modelcontextprotocol.io/specification/versioning)). It carries breaking changes (the initialize handshake is replaced by per-request `_meta` version negotiation plus a `server/discover` RPC; server-initiated requests are replaced by the Multi Round-Trip Requests pattern). Any MCP design written from 2025-era knowledge is now wrong in structural ways; treat every "current MCP practice" claim — including from recent blogs — as suspect until checked against `2026-07-28`.

---

## 1. Prior art: what good public-data / marketplace MCP servers look like in 2026

### 1a. The registry and governance landscape

The official registry (`github.com/modelcontextprotocol/registry`) is still **preview, not GA**, with an API freeze at v0.1 since 2025-10-24; publishing requires namespace ownership proof via GitHub OAuth/OIDC or DNS/HTTP domain verification ([repo](https://github.com/modelcontextprotocol/registry)). Secondary sources claim 10,000+ public servers and ~97M SDK downloads/month as of March 2026 — **unverified marketing-adjacent stats**.

### 1b. The single best structural analog: Shopify Storefront Catalog MCP

The closest prior art to what Hangar Bay would build ([shopify.dev/docs/agents/catalog/storefront-catalog](https://shopify.dev/docs/agents/catalog/storefront-catalog)). Three tools, not thirty:

| Tool | Params | Shape |
|---|---|---|
| `search_catalog` | `query` (free text), `context` (buyer signals), `filters` (category, price range), `pagination` (cursor + limit) | product summaries + cursor |
| `lookup_catalog` | `ids` (array, **max 10**) | bulk resolve, with explicit `not_found` entries |
| `get_product` | `id`, `selected` (option selections) | full detail |

Notable conventions: opaque cursor pagination with `limit` min 1 / default 10 / max 250, an explicit `has_next_page` signal, prices in minor units, and a `context` object separating *buyer situation* from *filters*. It implements the [UCP Catalog capability](https://ucp.dev/latest/specification/catalog/mcp/) (Google's Universal Commerce Protocol, 2026-04-08). Whether UCP survives as a standard is unknowable; the *tool shape* is good regardless.

The lesson: **default limit 10, not 50.** Shopify's human storefront paginates at 24–48; their agent-facing tool defaults to 10.

### 1c. Financial / market-data MCPs: the anti-pattern

Polygon.io's official MCP server "exposes all Polygon.io API endpoints as MCP tools" — 35+ tools ([PulseMCP](https://www.pulsemcp.com/servers/polygon)). This endpoint-mirroring approach is exactly what Anthropic and FastMCP's maintainer both argue against (§4d). Popular because it is cheap to generate, not because it works well.

### 1d. EVE Online MCP servers — they exist, and none of them do contracts

A cluster, essentially all from one author (`kongyo2`), all thin ESI/third-party-API wrappers, all tiny (4–8 stars):

- [`kongyo2/eve-online-mcp`](https://github.com/kongyo2/eve-online-mcp) — market data via ESI (`get-market-prices`, `get-market-orders`, `get-market-history`, `get-market-groups`, `get-structure-orders`, …). TypeScript, MIT, 8 stars. **No contracts.**
- [`kongyo2/evetycoon-mcp-server`](https://github.com/kongyo2/evetycoon-mcp-server) — wraps evetycoon.com's API rather than ESI. The closest structural precedent for "an EVE site exposes itself via MCP." 4 stars.
- [`kongyo2/eve-online-traffic-mcp`](https://github.com/kongyo2/eve-online-traffic-mcp), [`kongyo2/eve-online-osint-mcp`](https://github.com/kongyo2/eve-online-osint-mcp), and an "ask-eve" PI server on LobeHub.

Separately, [EVE AI Agent](https://developers.eveonline.com/docs/community/eve-ai-agent/) is a community LLM chat assistant featured **on CCP's own developer docs site** — it does not use MCP, but CCP linking to an LLM-powered ESI consumer is a meaningful posture signal (§5).

**The gap is a moat, not just a hole.** ESI's public-contract surface is `/contracts/public/{region_id}/` (paged, no filtering) plus one items call per contract. An ESI-wrapping MCP server **structurally cannot** answer "find me a cheap fitted Ishtar near Jita": it would have to page an entire region and issue ~33,800 item fetches. Hangar Bay's ingestion + index turns that into one SQL query. No cleverness closes that gap on the ESI side.

### 1e. Extracted patterns from well-regarded servers

- **Few fat tools beat many thin ones.** Anthropic: build "a few thoughtful tools targeting specific high-impact workflows"; consolidate ([Writing effective tools for AI agents](https://www.anthropic.com/engineering/writing-tools-for-agents)).
- **Namespace by service and resource** (`asana_search`, `asana_projects_search`).
- **Return names, not IDs**; offer a `response_format` enum (`"concise"`/`"detailed"`) when IDs are unavoidable.
- **Token efficiency is a design parameter**: pagination, filtering, truncation with sensible defaults, and truncation messages that steer the agent toward "many small targeted searches instead of a single broad search."
- **Errors are prompts.** Tool-execution errors go in the result with `isError: true` and must communicate "specific and actionable improvements, rather than opaque error codes" ([spec §Error Handling](https://modelcontextprotocol.io/specification/2026-07-28/server/tools)).
- **Structured output is first-class** (`outputSchema` + `structuredContent`, JSON echoed in a text block for compatibility). How widely clients actually consume `structuredContent` in practice is a **real, unmeasured uncertainty**.

---

## 2. Consumer personas, derived from concrete queries

### P1 — The player's chat assistant (dominant persona; ~80% of value)

| Utterance | Tool need |
|---|---|
| "Find me a well-priced fitted Ishtar near Jita" | free-text search + ship semantics + location scoping + price sort; name→type_id resolution; station/system proximity, not just region |
| "What's the cheapest Gila on contract right now?" | same, ranked, small N — **one call returning ~5 rows, not 50** |
| "Is this contract a good deal?" (pastes a URL/ID) | contract detail **plus** appraisal; URL→id parsing |
| "Any cheap Gila BPCs?" | `is_bpc` + type filter; runs/ME/TE don't exist yet (gap analysis §4.2) |
| "Watch for a Loki under 400m and tell me" | authenticated write, or more natively an MCP resource subscription (§3f) |
| "What ships are for sale in Amarr?" | **currently unanswerable — coverage is The Forge only.** An MCP surface makes this failure louder: an empty list reads to an agent as "no ships in Amarr." |

### P2 — The hauling / logistics assistant

"Price a Jita→Amarr courier for 340k m³, 2bn collateral." Wants **aggregates, not rows** ("going ISK/m³ and ISK/jump on this lane?") — a statistics tool, and a strong argument for one aggregation tool in v1 (§3d).

### P3 — The market-analysis / industry agent

"How are capital BPC prices trending?" Given the corpus shape (49% BPC, big abyssal clusters), already well-served by the data, completely unserved by the UI. Wants faceted counts and distributions; the persona most likely to abuse the endpoint (§4a).

### P4 — The corp/alliance Discord bot

Scheduled saved queries; wants stable, cheap, cursor-paginated access and a freshness stamp. Where "free backend for someone else's product" risk lives (§5).

**Persona-derived conclusion:** P1 dominates, and P1's queries are almost all "give me the best few, with enough context to judge." That is a **ranked-shortlist API**, not a paginated list-browsing API. Designing the MCP surface as a mirror of the contract list would serve the least important persona best.

---

## 3. Proposed first-draft tool surface

### 3a. Naming and shape

Namespace everything `hangarbay_*`. Seven tools for v1, three optional:

```
hangarbay_search_contracts     ← the workhorse
hangarbay_get_contract         ← detail + items
hangarbay_resolve_names        ← type/region/system/station name ⇄ id
hangarbay_market_summary       ← aggregates (P2/P3)
hangarbay_appraise_contract    ← post-appraisal only
hangarbay_data_status          ← freshness/coverage (candidate for deletion, 3e)
hangarbay_watch_type           ← authenticated; defer (3g)
```

### 3b. `hangarbay_search_contracts`

```jsonc
{
  "name": "hangarbay_search_contracts",
  "description": "Search live EVE Online public contracts aggregated by Hangar Bay. \
Covers <REGIONS> (currently The Forge / Jita only). Data refreshes hourly; every \
result carries the timestamp it was observed. Contracts already sold or expired are \
excluded. Use a small limit and a narrow query; prefer several targeted searches \
over one broad one.",
  "inputSchema": {
    "query":            "string  — free text over contract title and item names, min 3 chars",
    "ship_type_ids":    "int[]   — resolve names first with hangarbay_resolve_names",
    "region_ids":       "int[]",
    "system_ids":       "int[]",
    "station_ids":      "int[]",
    "contract_type":    "enum: item_exchange | auction | courier | any  (default any)",
    "ships_only":       "bool    — default true; mirrors the site default",
    "is_bpc":           "bool",
    "min_price":        "number  (ISK)",
    "max_price":        "number",
    "min_collateral":   "number",
    "max_collateral":   "number",
    "expires_after":    "string  (ISO 8601) — 'still available in N hours'",
    "sort_by":          "enum: price | date_issued | time_left | volume | collateral (default price)",
    "sort_direction":   "enum: asc | desc",
    "limit":            "int 1..50, default 10",
    "cursor":           "string  — opaque; from a previous response",
    "response_format":  "enum: concise | detailed  (default concise)"
  }
}
```

Returns `structuredContent`:

```jsonc
{
  "data_as_of": "2026-08-01T14:03:00Z",
  "data_stale": false,
  "coverage": ["The Forge"],
  "total_matching": 47,
  "returned": 10,
  "next_cursor": "eyJvIjoxMH0",
  "contracts": [{
    "contract_id": 219000000, "url": "https://hangarbay…/contracts/219000000",
    "type": "item_exchange", "title": "Ishtar, fitted",
    "price_isk": 285000000, "collateral_isk": 0,
    "location": "Jita IV - Moon 4 - Caldari Navy Assembly Plant",
    "system": "Jita", "region": "The Forge",
    "expires_in_hours": 71, "issued": "2026-07-29T00:00:00Z",
    "item_count": 14,
    "headline_items": ["Ishtar", "Heavy Assault Missile Launcher II ×5"],
    "is_bpc_contract": false, "is_ship_contract": true
  }]
}
```

Design points, each earned from the repo:

- **`concise` must NOT return `items`.** Today `ContractSchema` always carries the full `items` array and `contract_service.py` eager-loads it on both fetch paths (`selectinload(Contract.items)` in `_fetch_page_joined` and `_fetch_page_simple`). A 50-row page of fitted ships is thousands of item rows — fine for a table, a token bomb in an MCP result. **The MCP search tool needs its own projection — do not reuse `ContractSchema`.** `headline_items` + `item_count` is the concise shape; `detailed` may include items but should force `limit ≤ 5`.
- **Names, not IDs, in the output.** The DB already denormalizes `start_location_name`; region/system names need a small reference table or cached ESI resolve (3c).
- **`contract_type` is new.** The REST API has no type filter even though `Contract.type` is stored and indexed (`ix_contracts_type_status`). Cheap to add; unlocks the hauling persona.
- **Cursor, not `page`.** MCP's pagination utility is opaque-cursor (clients MUST NOT parse cursors). It formally covers only list operations, but matching the convention is right — and the 2026-07-28 [Stateful Tools](https://modelcontextprotocol.io/specification/2026-07-28/server/tools) guidance specifies how: opaque high-entropy handle, bounded lifetime, retention policy in the tool description, actionable error on expiry. A base64 offset+filter-digest cursor over the existing offset pagination needs no new state store.

### 3c. `hangarbay_resolve_names` — not optional

```
{ names: string[], kinds?: ("type"|"region"|"system"|"station")[] }
→ { resolved: [{name, id, kind, published, category}], ambiguous: [...], not_found: [...] }
```

Every P1 query starts with a name; every filter takes an id. Today there is **no backend reference surface at all**: regions are a generated static array in the *frontend* (`app/frontend/web/src/features/contracts/regions.ts`), and type-name resolution exists only inside `watchlist_service._resolve_name_to_type_id` (calls ESI). An MCP server needs this promoted into a real, cached backend service. Bulk-in/bulk-out with explicit `ambiguous`/`not_found` buckets follows Shopify's `lookup_catalog`; ambiguity ("Ishtar" vs "Ishtar Blueprint") is the natural elicitation point (3i).

### 3d. `hangarbay_market_summary` — the token-economy tool

```
{ group_by: "ship_type"|"region"|"station"|"contract_type"|"price_bucket",
  <same filters as search>, limit: int }
→ { buckets: [{key, contract_count, min_price, median_price, p25, p75, total_volume}], data_as_of }
```

Makes a 33.8k-row corpus tractable: "what's the going rate for a Gila?" should be **one aggregate call**, not 50 rows the model averages itself. Serves the hauling persona (ISK/m³ by lane) and the analysis persona directly. This belongs in **v1, not v2** — it is what distinguishes a thoughtful MCP surface from a REST mirror.

### 3e. `hangarbay_data_status`

Coverage regions, `data_as_of`, `data_stale`, last ingest outcome, corpus counts. **Self-pushback:** a status tool the model must *remember to call* is worse than freshness embedded in every result. Candidate for deletion; keep only as a cheap diagnostic alongside per-result freshness fields.

### 3f. `hangarbay_appraise_contract` — gate this hard

Only after appraisal ships:

```
{ contract_id: int, basis?: "jita_split"|"jita_buy"|"jita_sell" }
→ { asking_price, appraised_value, delta_isk, delta_pct, basis, priced_at,
    line_items: [{type_name, qty, unit_value, source}],
    unpriceable: [{type_name, qty, reason: "blueprint_copy"|"abyssal_mutated"|"no_market_data"}] }
```

The `unpriceable` array is the whole design. The M5 direction doc's named risk (a wrong valuation destroys trust, worse than no number) is **strictly worse over MCP**: a human sees a caveat next to a number; an LLM launders the number into prose that drops the caveat. Concrete mitigation: never return a bare `appraised_value` when `unpriceable` is non-empty — return `appraised_value_partial` plus `unpriced_item_count`, so the field name itself survives summarization. Given 49% of contracts contain BPCs, *most* of the corpus is partially unpriceable.

Pricing bases: Fuzzwork's aggregates endpoint returns weightedAverage/max/min/median/percentile/volume/orderCount per side — and its author explicitly asks integrators not to hammer it ("Get the data yourself, direct from CCP"). ESI's `/markets/prices/` and regional order books are the first-party route.

### 3g. Authenticated `/me/*` — recommendation: **web-only for v1**

1. **The auth cost is disproportionate** (§4c — an OAuth 2.1 authorization server, not a session-cookie reuse).
2. **The spec pushes human-in-the-loop on writes anyway**, and an all-read-only server is a far easier trust story for an institutionally paranoid community.
3. **The natural MCP form of "watch this" isn't a write tool.** The 2026-07-28 spec has `subscriptions/listen` + `notifications/resources/updated`; a watchlist as a *subscribable resource* (`hangarbay://watch/{type_id}?max_price=…`) also addresses the M5 finding that alerts have no delivery path off the site. Exciting v2, but **client support for subscriptions is unverified**.

If writes do come: `hangarbay_watch_type` maps 1:1 to `WatchlistItemCreate` (already accepts exactly one of `type_id`/`type_name` — agent-friendly); note `SavedSearchParameters` uses `extra="forbid"`, so an MCP tool must not pass through filter keys saved searches reject.

### 3h. Resources vs tools

**Tools for everything in v1.** Resources are application-driven (the spec's illustration is a resource-picker UI) — wrong model for searching 33k contracts. Defensible resource uses: a few static context docs (`hangarbay://reference/regions`, `hangarbay://about/coverage-and-freshness`; `resources/read` now supports `ttlMs`/`cacheScope`), and **resource links from tool results** (`{"type": "resource_link", "uri": "https://hangarbay…/contracts/…"}`) — the clean way to hand the user a shareable URL, which is PRODUCT.md's "the URL is the interface" principle.

### 3i. Elicitation / Multi Round-Trip Requests

The 2026-07-28 spec replaced server-initiated requests with [MRTR](https://modelcontextprotocol.io/specification/2026-07-28/basic/patterns/mrtr): a tool returns `resultType: "input_required"` with `inputRequests` and an opaque `requestState`; the client gathers input and retries. Good fit for name ambiguity. Hard constraints: servers MUST NOT send elicitation to clients without the capability and MUST NOT assume a retry ever comes — so tools must still work by returning an `ambiguous` array. `requestState` is attacker-controlled: integrity-protect (HMAC/AEAD), principal-bind, TTL.

---

## 4. Design considerations

### 4a. Rate limiting — a from-scratch build

**There is no API-level rate limiting anywhere in the backend today** (grep: the only rate-limit code is ESI *outbound* error-limit handling; `security-spec.md` has no throttling section). The MCP spec says servers MUST rate-limit tool invocations. Agent traffic breaks human-calibrated limits by construction. Posture:

- **Three keys**: per-caller, per-tool, global. Token bucket with burst, **weighted by tool cost** (`resolve_names` cache hit ≠ `market_summary` aggregate scan ≠ `appraise_contract` external data).
- **Informative 429s** as tool-execution errors (`isError: true`) — which limit, wait time, quota — so the model self-corrects instead of blind-retrying.
- **Unauthenticated access still needs a caller key of some kind** (free, self-service, no-PII), or the only key is IP — worthless against a hosted agent fleet.
- **Amplification asymmetry:** appraisal calls consume external market data. Uncapped agent traffic on Hangar Bay becomes uncapped Hangar Bay traffic on Fuzzwork/ESI, and ESI bans for cache circumvention. **Cache appraisals aggressively; never proxy live.**

### 4b. Freshness signaling — the repo is ahead of the requirement

M5 Workstream B already specifies `data_as_of` + `data_stale` on the list envelope, sourced from the ingest-run record, with the right philosophy: *the server owns the judgement, the client owns the presentation* (the staleness threshold derives from the scheduler interval no client can see). For MCP, three rules:

1. **`data_as_of` + `data_stale` in every tool result** — models drop context between calls; a payload field survives.
2. **Escalate in text, not just a boolean.** A model will summarize away `true`; it will not summarize away "⚠ Data is 3.6 days old; these contracts may no longer exist."
3. **Same for coverage:** `coverage: ["The Forge"]` in every result, and an explicit "no data for <region>" error rather than an empty list. **An empty list is a lie to an agent.**

M5's liveness filtering (expiry + per-region `last_seen_at` watermark for sold/delisted contracts) is a **prerequisite** for MCP: an agent confidently recommending a sold contract is this surface's single worst failure mode.

### 4c. Auth — the spec forecloses the easy path

Current auth is an opaque Valkey session cookie (`core/current_user.py`); no bearer/PAT path exists. The [2026-07-28 authorization spec](https://modelcontextprotocol.io/specification/2026-07-28/basic/authorization): the MCP server is an OAuth 2.1 Resource Server, MUST implement RFC 9728 Protected Resource Metadata; clients MUST use RFC 8707 resource indicators; and — the killer — clients MUST NOT send tokens other than ones issued by the MCP server's own authorization server, and servers MUST NOT accept or transit any other tokens. **You cannot hand an EVE SSO token to the MCP server.** EVE SSO would sit *upstream* of an authorization server Hangar Bay operates or rents (AuthKit/Auth0/Stytch/Descope), issuing Hangar-Bay-audience tokens after federating to CCP — plus PKCE, discovery, RFC 9207, Client ID Metadata Documents (Dynamic Client Registration is now *deprecated*). **That is a milestone, not a task** — the strongest argument for a read-only public v1. Authorization is OPTIONAL in the spec; a fully public server is conformant.

### 4d. Hosting, and the auto-generation question

**Auto-generating from OpenAPI: the consensus is settled and it is "don't."** FastMCP's own docs recommend the FastAPI integration "for bootstrapping and prototyping, not for mirroring your API to LLM clients" ([gofastmcp.com/integrations/fastapi](https://gofastmcp.com/integrations/fastapi)); the maintainer's essay [Stop Converting Your REST APIs to MCP](https://jlowin.dev/blog/stop-converting-rest-apis-to-mcp) makes the argument at length; Anthropic's guidance points the same way. Hangar Bay is a textbook case: auto-generation would emit ME/TE parameters that are accepted-and-ignored (FASTAPI-2), a runs filter wired to `raw_quantity` (−1 BPO / −2 BPC, not a run count) so `min_runs=5` matches nothing, and a response schema dragging full `items` into every row. **Four inert parameters, two semantically wrong ones, and a token bomb — all correctly generated.**

**Library state (verified 2026-08-01 by the spec/hosting lane — Part 2 below):** the recommendation flipped on 2026-07-28. The **official Python SDK v2.0.0** shipped that day with stable `2026-07-28` support and "serves every earlier revision from the same server"; it renamed `FastMCP` → `MCPServer` (decorator API unchanged) and ships middleware, caching, pagination, and OpenTelemetry pages of its own. **FastMCP 3.4.5** (stable) tops out at spec `2025-11-25` (hard `mcp<2.0` pin); `2026-07-28` support exists only in its 4.0.0b1 prerelease. `tadata-org/fastapi_mcp` is **dead** (last real commit 2025-08-10, unbounded `mcp>=1.12.0` pin that likely breaks on fresh installs against SDK v2). **Use the official SDK v2.**

**Same app or sidecar?** Sidecar-in-the-same-process: mount the MCP ASGI app inside the existing FastAPI app (`mcp.streamable_http_app()` mounted in Starlette/FastAPI), sharing DB engine, Valkey, settings, structlog — but keep the tool layer **hand-written against `services/`, never against the HTTP routes**. Two project gotchas: PROXY-1 (an MCP mount needs an edge decision — likely its own hostname, e.g. `mcp.hangarbay…`, which also gives a clean RFC 8707 canonical resource URI and a separate rate-limit domain), and the single-worker/scheduler-split posture noted in the M5 options doc (check before assuming co-hosting is free).

---

## 5. What "final form" unlocks — and the strategic risks

**From website to substrate.** An MCP surface changes the unit of competition from *presentation* to *the index itself*. The item-enriched, name-resolved, freshness-stamped contract corpus is the asset, and §1d establishes it is genuinely unreachable from ESI — every existing EVE MCP server is a thin ESI wrapper and none do contracts, because contracts are the one ESI dataset you cannot query without ingesting all of it. Hangar Bay is the only entity in this ecosystem that has already paid that cost. Infrastructure compounds where a website does not: every corp Discord bot and hauling assistant that integrates becomes a reason the pipeline must keep running well.

**It changes what the product owes its users.** A website gets away with a stale row and a small-type caveat; an agent laundering that row into confident prose does not. M5's trust work (dead-contract filtering, freshness surface, retiring the always-`"unknown"` status column) stops being polish and becomes the **precondition** for an MCP surface being ethical to publish. Same for appraisal — over MCP, a wrong number degrades to an agent telling someone a 2-billion-ISK contract is a good deal. And ships-only/one-region scope becomes a load-bearing honesty problem the moment an agent asks about Amarr and gets `[]`. **Honest read: an MCP server should not ship before M5's trust work and coverage expansion land.** It is the right final form, and it is downstream of the current milestone, not parallel to it.

**Risk 1 — becoming a free backend; CCP has already decided this for you.** The [EVE Developer License Agreement](https://developers.eveonline.com/license-agreement) §4.1: developers "may not charge any fee … or otherwise monetize the Application"; §4.4 permits only ISK-gated access, voluntary donations, and general advertising. **Paid tiers are not available as a mitigation.** What remains is operational: required free API keys for attribution and rate-limit keying, per-caller quotas, published fair-use terms. The risk is smaller than it looks — competitors also cannot charge, so nobody can build a *paid* product on your back; the realistic downside is bandwidth and ingestion cost, not revenue capture.

**Risk 2 — ESI redistribution: silence and tolerance, never written permission.** A dedicated license lane (Part 3 below) sharpened this: the Developer License grants distribution of Game Data "within an Application," reserves all other rights (§2.6), contains no sublicense clause, and no CCP statement anywhere addresses third parties consuming your re-served data — the accurate sentence is "CCP has not addressed it; established sites do it openly and CCP indexes them," never "CCP permits it." De-facto precedent is strong and directly on-point: **EVE Ref publishes full ESI public-contract snapshots twice hourly as public CSVs** and is listed in CCP's own community docs; zKillboard, Fuzzwork, and Adam4EVE all redistribute ESI-derived data (note: zKillboard's widely-copied attribution template *asserts* granted permission — that assertion is site-specific; don't copy it). Documented enforcement history targets **ingestion behavior** (cache circumvention, error-limit blowouts, discovery-by-enumeration) and gambling/RMT — zero cases against public-API redistribution. Obligations: CCP proprietary notice (§7.1), identifying User-Agent, respect caching, stay inside error limits. **Assessment: legal risk low but non-zero; resolve by asking the third-party dev channel, not by reading harder.** Mild positive signal: CCP features an LLM-powered ESI consumer on its own docs site, and an ESI MCP tool announced on the official forum drew zero policy attention.

**Risk 3 — building on a protocol that moved days ago.** The 2026-07-28 revision is breaking; SDK support almost certainly lags; deprecated features get a 12-month runway under the [feature lifecycle policy](https://modelcontextprotocol.io/community/feature-lifecycle). Survivable — but it argues for a **small surface**: seven hand-written tools re-implemented against a new revision is a week; a thirty-tool auto-generated mirror is a quarter. The narrow surface is the hedge against protocol churn, not just the token-economy answer.

---

## Part 2 — spec + hosting deep-dive (separate verification lane, same date)

A second research lane verified the protocol and hosting landscape directly against primary sources. Decision-relevant facts, including corrections to Part 1:

### Protocol state

- **Current spec revision is `2026-07-28`** (lineage: 2024-11-05 → 2025-03-26 → 2025-06-18 → 2025-11-25 → 2026-07-28; RC locked 2026-05-21 with a ten-week validation window). Headline breaking changes: `initialize` handshake and protocol sessions **removed** (per-request `_meta` version negotiation; state via server-minted opaque handles passed as tool arguments); `server/discover` is **mandatory** for servers; **MRTR** replaces all server-initiated requests; every result carries `resultType`; `subscriptions/listen` replaces `resources/subscribe`; **Sampling, Roots, and Logging are deprecated** (12-month runway).
- **`ttlMs` + `cacheScope` are now REQUIRED** on list/read/discover results (`"public"` = shareable across auth contexts). A real win for a public read-heavy marketplace — shared intermediaries can cache tool lists and reference resources.
- **Pagination is list-operations only; there is no tool-result pagination in MCP.** Tool-data pagination is convention: `limit`/`cursor` in the tool's own inputSchema, small defaults, `next_cursor` in `structuredContent`.
- **Hard client limits:** Claude.ai/Desktop cap tool results at **~150,000 characters**; Claude Code at **25,000 tokens**; 300s timeout on hosted surfaces. Design responses well under the Claude Code cap.
- **Client adoption lags the spec:** as of 2026-08-01 Claude's connector docs list auth support only through 2025-11-25 ("rolling out soon" for 2026-07-28). **Build for 2026-07-28; the official SDK serves earlier revisions from the same server.** Claude does not support resource subscriptions; ChatGPT supports tools only. **Tools are the only primitive with universal support — design the value in tools.**
- **Elicitation** is active (now via MRTR) but client support is unverifiable — treat as enhancement, never load-bearing; always return an `ambiguous` array as the fallback path.

### Auth — the three-layer architecture is confirmed, with EVE SSO blockers named

**EVE SSO cannot be the MCP Authorization Server** — three independent blockers verified against CCP's SSO docs: no DCR/CIMD (manual portal registration only), no RFC 8707 resource indicators, and wrong audience (`aud = [client_id, "EVE Online"]`, not the MCP server's URI — unfixable without token passthrough, which the spec explicitly forbids). Correct architecture: (1) Hangar Bay MCP server as pure Resource Server (RFC 9728 metadata, audience validation); (2) an Authorization Server Hangar Bay operates or rents (Keycloak is the spec's own tutorial example) issuing MCP-audience tokens, CIMD preferred (DCR now deprecated); (3) EVE SSO federated upstream inside that AS — EVE/ESI tokens stay server-side, never visible to the MCP client.

**Lazy auth is first-class and fits a public marketplace exactly:** "a product catalog can be browsed anonymously; an order history cannot." Anonymous clients call public tools; the server challenges on protected ones. Critical detail: the refusal must be a **transport-level `401` + `WWW-Authenticate`** gated before the JSON-RPC layer — a `200` with `isError: true` produces no auth prompt in Claude.

**Anthropic's connector review criteria are an enforced gate:** a catch-all `api_request` tool with a `method` parameter is rejected; read and write must be separate tools; `readOnlyHint`/`destructiveHint` annotations determine per-call confirmation behavior; oversized responses are grounds for rejection. Pure machine-to-machine `client_credentials` is unsupported — every connection requires user consent.

### Hosting — the recommendation flipped on 2026-07-28

- **Official Python SDK v2.0.0** (released 2026-07-28): stable current-spec support, serves all earlier revisions, `FastMCP` class renamed `MCPServer`, ships provisional middleware (rate limiting/access control), caching, pagination, OpenTelemetry. **The safer choice today.**
- **FastMCP 3.4.5** (stable): pinned `mcp<2.0`, tops out at spec 2025-11-25; current-spec support only in 4.0.0b1. Its genuine advantages over the official SDK: composition, proxying, OpenAPI generation (which we don't want), in-process test client.
- **`tadata-org/fastapi_mcp`: dead.** Last real commit 2025-08-10, 161 open items, alpha classifier, unbounded `mcp>=` pin that likely breaks fresh installs against SDK v2.
- **Two day-one pitfalls for mounting inside FastAPI** (worth `docs/pitfalls/` entries when this is built): (1) the parent app must enter the MCP session manager's lifespan — a mounted sub-app's lifespan never runs; symptom is `RuntimeError: Task group is not initialized` (the single most-reported integration bug); (2) the SDK's transport security accepts only localhost-addressed requests until `transport_security=` is configured with the real hostname — symptom is `421 Misdirected Request` on Render.
- Rate-limit error codes: `-32020..-32099` is now **reserved for the spec**; implementation-defined errors use `-32000..-32019`, or plain HTTP 429.

### Autogeneration verdict, quantified

The empirical record behind "hand-design, don't mirror": GitHub Copilot cut ~40 tools to 13 and gained 2–5pp on SWE-bench across two model families; Anthropic's docs state tool selection degrades past **30–50 tools**; a controlled Pet Store experiment found cliff-edge failure at 107 tools; an academic survey (AutoMCP, arXiv 2507.16044) found hand-written servers expose a **median 19% of available API operations** — curation is the norm, not the exception. No credible non-vendor source argues the opposite; vendors selling generation all ship curation features that concede the point.

## Part 3 — developer-license deep-dive (separate verification lane, same date)

Full detail lives in that lane's report; the durable facts:

- **The licensor rebranded.** CCP Games became **Fenris Creations** on 2026-05-06 (independent from Pearl Abyss; eveonline.com footer now reads "©2026 Fenris Creations"), but the Developer License Agreement still names "CCP hf." throughout and still prescribes the `© 2014 CCP hf.` attribution string. Re-check the license page before writing any attribution string into shipped code; the ecosystem is split (zKillboard switched to Fenris; EVE Ref/Fuzzwork/Adam4EVE have not).
- **Monetization (verified verbatim from the license):** no real-money fees for access (§4.1), no monetizing products incorporating Licensed Materials (§4.3, with an "or by separate written agreement with CCP" escape hatch that has no published process). Permitted: ISK-gated access, voluntary donations "solely to offset Developer's costs" (must not gate features), and non-intrusive general advertising (§4.4).
- **Redistribution is silence, not permission** — see Risk 2 above. The grant is "within an Application"; whether a machine-readable API consumed by other people's software qualifies has never been addressed by CCP in any medium (a 2018 forum thread asking directly was never answered).
- **The real operational risk is ingestion behavior.** Every documented ESI ban targets request patterns: the 2018 `/search/` discovery-by-enumeration ban, cache circumvention, error-limit violations. Bans are permanent and IP-based. Unauthenticated ESI rate-limit buckets key on **source IP** — one backend shares one bucket across all its users. CCP's stated posture on bulk pullers (market-orders rate-limit blog, 2026-02): tolerated, bucketed, and told "please only fetch the data you're actually using."
- **`Expires` is being deprecated.** ESI is migrating routes to event-driven invalidation; on converted routes the `Expires` header "is no longer meaningful" and `Cache-Control` is authoritative. Hangar Bay's ESI client parses `Expires` (`core/esi_client_class.py:191-195`) — flagged as a follow-up task.
- **AI/MCP consumption is entirely unregulated** by CCP policy. The EULA's automation rules target in-game unfair advantage, not out-of-game data processing.
- **Unverified this session:** the support-site policy pages (3rd Party EULA, Third Party Policies, Botting, main EULA) 403 automated fetches; anything quoted from them needs a human read before entering a legal artifact.

## Appendix: repo-grounded facts a plan would need

| Fact | Location |
|---|---|
| List endpoint always eager-loads `items` on both fetch paths | `services/contract_service.py` `_fetch_page_joined`, `_fetch_page_simple` |
| `min_me`/`max_me`/`min_te`/`max_te` accepted but ignored (FASTAPI-2) | `schemas/contracts.py` |
| `min_runs`/`max_runs` filter `raw_quantity` (−1 BPO / −2 BPC), not runs | `services/contract_service.py` `_apply_item_filters` |
| `ContractItem.category` is only `"ship"` or NULL; `group_id`/`category_id` not stored | `models/contracts.py`; `background_aggregation.py` ~692 |
| `Contract.type` stored + indexed but not exposed as a filter | `models/contracts.py` `ix_contracts_type_status` |
| `status` always `"unknown"`; retirement designed in M5 Workstream D | `2026-07-26-m5-trust-shareability-design.md` |
| `data_as_of` / `data_stale` envelope design | same doc, Workstream B |
| Liveness: expiry + per-region `last_seen_at` watermark | `contract_service.py` `_apply_contract_filters` |
| Auth = opaque Valkey session cookie; no bearer/PAT path | `core/current_user.py`, `api/auth.py` |
| No API rate limiting anywhere | grep across `src/`; `security-spec.md` silent |
| No backend reference data; regions are a generated frontend constant | `app/frontend/web/src/features/contracts/regions.ts` |
| Coverage = The Forge only | `render.yaml` `AGGREGATION_REGION_IDS = "[10000002]"` |
| Routers mount bare; `/api/v1` owned by proxy/edge (PROXY-1) | `api/contracts.py` and siblings |

**Unverified items, flagged rather than smoothed over:** FastMCP 3.0 GA status; SDK support for the 2026-07-28 revision; real-world client support for `structuredContent` and resource subscriptions; `fastapi_mcp` maintenance state; registry-scale statistics.
