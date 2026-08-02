<!-- ABOUTME: Bounded research spike on whether courier reward-per-jump belongs in F008 v1, -->
<!-- ABOUTME: covering ESI/SDE adjacency sources, route security preference, and implementation size. -->

# Courier reward-per-jump: does it belong in F008 v1?

**Date:** 2026-08-01
**Status:** Research complete. Recommendation pending Sam's decision.
**Scope:** The "ISK per jump" metric for the courier tab of F008 (the type-aware all-contracts browse view). Everything measured here is against live ESI and the live production API on 2026-08-01/02.

---

## Verdict

**Fold reward/jump into F008 v1.**

**Deciding reason, one sentence:** computing it for the *entire* live courier population does not need a route graph at all — courier endpoints cluster onto ~110 stations forming ~107 distinct origin→destination pairs, so the whole feature is **~320 cached ESI route lookups taking under 10 seconds cold**, and the station→system resolution machinery it depends on already exists in `background_aggregation.py`.

**What was actually wrong with the original exclusion.** The provisional "separate project" call was reasoning about *building a solar-system route graph* — and that judgment is correct: a general graph with EVE-accurate security-weighted pathfinding genuinely is a separate project (see [Option B](#option-b--vendor-an-adjacency-edge-list-and-run-our-own-bfs) below, and the four-disconnected-components trap it carries). The error was assuming reward/jump *requires* one. It does not. Jump counts for a bounded, heavily-repeating set of station pairs are a **lookup**, not a graph problem.

**The honest caveat:** what folds in is *per-pair route lookups*. The route graph stays out. If Hangar Bay later wants "jumps from my current location" — an Adam4EVE-style contextual column, already named as a future direction in the contract-coverage gap analysis (`docs/superpowers/specs/2026-08-01-contract-coverage-gap-analysis.md`) — that is a genuinely different problem (8,490 possible origins, not 107 fixed pairs) and would need the graph. This spike does not clear that.

---

## 1. Measured facts about the courier population

Fetched all public contracts for five regions directly from ESI `/v1/contracts/public/{region_id}/` on 2026-08-01.

| Region | Contracts | Couriers | Courier share | Distinct location pairs |
|---|---:|---:|---:|---:|
| The Forge (10000002) | 33,903 | 115 | 0.34% | 48 |
| Sinq Laison (10000032) | 1,529 | 44 | 2.88% | 30 |
| Metropolis (10000042) | 975 | 42 | 4.31% | 27 |
| Domain (10000043) | 2,699 | 34 | 1.26% | 12 |
| Heimatar (10000030) | 2,047 | 15 | 0.73% | 10 |
| **Union of 5** | **41,153** | **250** | — | **127** |

The decisive numbers:

- **The Forge alone** (the only region Hangar Bay currently ingests): 115 couriers → **12 distinct start locations, 40 distinct end locations, 48 distinct location pairs → 39 distinct *system* pairs.**
- **Across 5 regions:** 250 couriers → 112 distinct NPC stations → **107 route-resolvable pairs.**
- Couriers repeat their endpoints heavily. 115 contracts collapse to 39 route questions — a **~3:1** compression in one region, and it gets better as volume grows because the trade hubs are fixed.

### Endpoint resolvability

Courier jumps need **both** endpoints resolved to systems. Prior work measured ~97.1% coverage on *start* locations across all contract types; couriers are worse, because haulers frequently deliver *to* player-owned structures:

| | The Forge | 5 regions |
|---|---:|---:|
| Couriers with both endpoints NPC-resolvable | 105 / 115 = **91.3%** | 226 / 250 = **90.4%** |
| Blocked by start being a player structure | 4 | — |
| Blocked by end being a player structure | 6 | — |

**~9–10% of couriers will have no jump count**, and that is structural, not fixable: player-owned Upwell structures have no tokenless ESI route (`/universe/structures/` needs `esi-universe.read_structures.v1` and 403s for structures the token's character cannot dock at — as documented in `get_universe_station`'s docstring in `core/esi_client_class.py`). This is the same NULL-honesty problem the codebase already handles for `start_location_system_id`.

---

## 2. End-to-end cost, measured

I ran the complete pipeline against live ESI for The Forge's real courier population — resolve every NPC station to a system, then compute every distinct system pair under all three security preferences:

```
distinct NPC stations to resolve:        44
station->system:  44/44 resolved in 2.2s (44 calls)
distinct SYSTEM pairs:                   39   (0 same-system)
routes: 117 calls (3 preferences x 39 pairs) in 6.2s
TOTAL cold-cache wall time: 8.4s for 161 ESI calls
```

**8.4 seconds and 161 calls, cold, for every courier in the region under every security preference.** Warm, it is zero calls — see the caching analysis below. Across all five sampled regions the cold cost would be 112 station calls + 321 route calls.

### Rate limits (from the published spec, verified live)

`/route/` is the only endpoint here that declares a rate limit:

| Endpoint | Rate limit | Server cache |
|---|---|---|
| `GET /route/{origin}/{destination}` (compat 2020-01-01) | **3,600 / 15m**, group `routes` | `x-server-cache-ttl: 86400` (24h), ETag present |
| `POST /route/{...}` (compat ≥ 2025-09-30) | 3,600 / 15m, group `routes` | **`not-cached`**, no ETag |
| `GET /universe/systems/{id}`, `/universe/stargates/{id}`, `/universe/stations/{id}` | none declared | — |

3,600 per 15 minutes is **345,600/day**. Full-New-Eden courier coverage at three preferences would consume well under 1% of that even with zero caching. Rate limiting is a non-issue.

### Why the cache makes steady state free

Route geography is static — stargates do not move outside rare CCP map changes. A long Valkey TTL is correct and the repo already has the mechanism (`ESIClient._get_esi_object(path, cache_seconds=86_400)`). Better still, the codebase's existing station→system trick applies directly: `_select_known_station_systems` re-reads already-resolved pairs off stored rows so "steady state costs zero station requests." A `system_route_jumps` table does the same for routes, permanently.

---

## 3. Data-source comparison

### Option A — ESI `/route/{origin}/{destination}` (recommended)

Server-computed path; jumps = `len(route) - 1`.

- **Cost:** 1 call per (origin, destination, preference). 39 pairs × 3 = 117 calls for The Forge.
- **Bytes:** trivial (a JSON array of system IDs; a 12-system route is ~150 bytes).
- **Build time:** none. No graph to construct, no data to vendor, nothing to refresh on CCP's build cadence.
- **Refresh cadence:** effectively never. Cache for days.
- **Decisive advantage:** it returns **CCP's own** security-preference semantics. We do not have to reimplement, or guess at, what "secure" means. (Section 4 shows that guessing would be a bad idea.)
- **Cost:** introduces an ESI-4 compatibility-date dependency. See section 6.

### Option B — vendor an adjacency edge list and run our own BFS

Sources for the edge list, all verified by direct fetch:

| Source | What you get | Download |
|---|---|---|
| **Fuzzwork** `dump/latest/csv/mapSolarSystemJumps.csv` | exactly the edge list, 13,978 directed rows | **937 KB** (59 KB gzipped) |
| **CCP SDE** `eve-online-static-data-latest-jsonl.zip` | `mapStargates.jsonl` (502 KB in-zip) inside a 94 MiB bundle | **94 MiB** for a 502 KB file |
| **EVE Ref** reference-data | **no adjacency at all** — verified; its "System jumps" dataset is ESI *traffic telemetry*, not topology | n/a |
| **EVE Ref** SDE mirror | byte-identical mirror of CCP's zip, plus historical builds | 94 MiB |

A minimal edge list (array of ID pairs) is **~51 KB gzipped** — genuinely small enough to vendor into the repo.

**So the data is cheap. The routing is not.** Three specific costs:

1. **Security-weighted pathfinding is the actual work.** Plain BFS gives you `shortest` only. Reproducing CCP's `secure` / `insecure` semantics means reimplementing an algorithm we can only observe as a black box — and section 4 shows its `security_penalty` knob behaves non-monotonically, so "observe and match" is not a short exercise.
2. **The graph is not connected.** It has **four components**: main New Eden (5,228 systems), Pochven (27, gate-isolated, filament-only entry), and two Jove pockets (7 and 6). A naive BFS silently returns "unreachable" for ~40 systems. ESI already handles this.
3. **Refresh burden.** CCP builds ~2–4×/week. A vendored file needs a monitoring/refresh story that the ESI option simply does not have.

**Also a trap worth recording:** the legacy SDE URL `https://eve-static-data-export.s3-eu-west-1.amazonaws.com/tranquility/sde.zip` still returns **HTTP 200** with `Last-Modified: Mon, 07 Jul 2025` — frozen ~13 months and serving stale data without erroring. CCP reworked SDE distribution (the `bsd/` and `universe/` folders are gone; 79 flat per-dataset files now). Anything pointing at the old URL is broken silently.

### Option C — build the graph from ESI `/universe/systems/{id}` + `/universe/stargates/{id}`

`/universe/systems/{id}` returns `stargates[]` as **IDs only**; each must then be resolved to get `destination.system_id`. There is no bulk stargate endpoint.

**Cost: 8,490 + 13,978 = ~22,468 calls.** Verified payload sizes: 1,024 bytes/system, 221 bytes/stargate. This is strictly dominated by Option B (same result, ~22,000 calls instead of one 937 KB GET). **Rejected.**

### Verdict on sourcing

Option A. It is the only one that is *free of build, refresh, and algorithm* cost, and the only one that gives EVE-accurate security preferences. Option B remains the right answer *if and when* "jumps from my location" is built — at that point vendoring Fuzzwork's 937 KB CSV becomes worth it, and shortest-path-only BFS is acceptable for a contextual distance column.

---

## 4. The security-preference problem

**Yes, it is a real problem, and it is much bigger than expected.**

The legacy `flag` parameter takes `shortest` / `secure` / `insecure` (default `shortest`). Live, Jita (30000142) → Amarr (30002187):

| Preference | Jumps |
|---|---:|
| `shortest` | **11** |
| `insecure` | **40** |
| `secure` | **45** |

**A 4.1× spread on one of EVE's most-travelled routes.** I verified this is real geography, not an API artifact, by resolving every system on the shortest path: it threads Ahbazon (security 0.421 — displays as 0.4, low-sec), the well-known chokepoint, while the 45-jump `secure` route detours around it entirely. This is the post-Niarja map; the numbers are consistent with EVE reality.

### How much it matters across the real courier population

Computed for all 105 jump-resolvable Forge couriers:

| Measure | Value |
|---|---|
| `secure` / `shortest` ratio | min **1.00**, median **1.25**, max **4.09** |
| Contracts where `secure` ≥ 2× `shortest` | **34 / 105 = 32%** |
| Contracts where all three preferences agree | **40 / 105 = 38%** |
| Top-10 ISK/jump ranking overlap, `shortest` vs `secure` | **7 / 10** |

Worked example from live data — the same contract, two defensible answers:

| Reward | shortest | secure | ISK/jump (shortest) | ISK/jump (secure) |
|---:|---:|---:|---:|---:|
| 200,000,000 | 11 | 45 | **18,181,818** | **4,444,444** |

**So: no, a single unqualified "jumps" number does not mean anything.** For 38% of contracts it is unambiguous; for a third of them the choice moves the headline metric by more than 2×, and it reorders the top-10 leaderboard — which is precisely the view a hauler uses.

### `secure` is a preference, not a guarantee

Important correctness finding for UI labelling. I audited the security status of every system on returned routes:

| Route | Preference | Jumps | Systems below 0.45 security |
|---|---|---:|---:|
| Jita → Amarr | `shortest` | 11 | 1 (min 0.42) |
| Jita → Amarr | `secure` | 45 | **0** (min 0.46) |
| Jita → 1DQ1-A (null-sec dest) | `shortest` | 42 | 28 |
| Jita → 1DQ1-A (null-sec dest) | `secure` | **81** | **23** |

When an all-high-sec path exists, `secure` delivers it. When it does not, `secure` returns a route that is **nearly twice as long and still runs through 23 low/null systems**. Labelling that "Safe" would be a straightforward lie to the user.

### The `security_penalty` knob — do not use it

The newer compatibility-date contract adds `security_penalty` (0–100, default 50). Measured, Jita → Amarr, `preference: Safer`, three runs per value:

```
sp=0  -> 45 45 45
sp=5  -> 11 11 11
sp=10 -> 11 11 11
sp=15 -> 11 11 11
sp=20 -> 11 11 11
sp=25 -> 45
sp=50 -> 45
sp=100 -> 45
```

Deterministic and reproducible, but **non-monotonic**: 0 gives the safe route, 5–20 give the low-sec route, 25+ give the safe route again. The spec documents it only as "Strictness of the path preference." **Recommendation: never send it; pin to the default.** Exposing a control that behaves like this to users would be indefensible.

### Recommendation for the UI

1. **Compute and store all three preferences.** It costs 3× a trivial number (117 calls instead of 39 for The Forge) and removes the need to ever guess right.
2. **Let the user pick, and make the choice visible and sticky.** A three-way control on the courier tab (`Shortest` / `Prefer high-sec` / `Prefer low-sec`), with the selected preference feeding both the `Jumps` column and the `ISK/jump` sort. Never render a bare "Jumps" header with no stated preference.
3. **Default to `secure` (prefer high-sec).** Two reasons. First, a courier contract carries collateral the hauler forfeits on loss, so the risk-adjusted number is the one they act on; defaulting to `shortest` would flatter every contract whose short path runs through low-sec, which is exactly the misleading direction. Second, the established freight services price this way: EVE's dominant hauling operation runs *segmented* services — a high-sec arm and a separate low/null-sec arm — at different per-jump rates, quoted in **ISK per jump** (order ~0.9–1.0M ISK/jump high-sec, as of a 2023 rate quote). That is direct evidence both that ISK/jump is the metric haulers actually hold in their heads, and that it is **never** quoted without a security band attached. *Sourcing caveat: this came from a web-search summary of forum/wiki material, not a primary rate card — the service's own site did not resolve. Treat the direction as well-supported and the specific rate figure as indicative only.*
4. **Label honestly.** Use "Prefer high-sec", not "Safe". Where the returned route is *not* fully high-sec, mark it — we already have the system list, so the check is a lookup against per-system security for the bounded set of systems on our routes.
5. **Surface the spread.** When `secure` and `shortest` differ materially, that gap *is* the risk signal a hauler wants. Showing both (one as the sort key, the other in a tooltip or secondary cell) is more useful than picking one and hiding the other.

---

## 5. What it would take to implement

Sized against the actual code. The dependencies already exist, which is most of why this is small.

### Already present and directly reusable

- `background_aggregation._resolve_station_systems` — resolves NPC stations to systems, with `_select_known_station_systems` memoizing from stored rows so steady state costs zero requests.
- `background_aggregation._resolve_esi_objects(fetch, ids, kind)` — generic bounded-concurrency fan-out (`ENRICHMENT_CONCURRENCY = 8`) that degrades per-id failures to absent entries.
- `ESIClient._get_esi_object(path, cache_seconds)` — Valkey TTL cache for single-object endpoints.
- `NPC_STATION_ID_MIN/MAX` — the guard that avoids spending ESI error budget on guaranteed-401 structure lookups.
- Alembic migrations at `app/backend/src/alembic/versions/`, applied in production via `preDeployCommand` in `render.yaml`.

### Work required

| # | Change | Where | Size |
|---|---|---|---|
| 1 | Add `end_location_system_id` column; add `system_route_jumps` table (origin, destination, preference) → jumps; add denormalized jump columns on `Contract` | `models/contracts.py` + one migration | S |
| 2 | Extend `_npc_station_ids` to collect **end** locations (it reads only `start_location_id` today) | `background_aggregation.py` | XS |
| 3 | Resolve both endpoints; stamp `end_location_system_id` in `_build_contract_rows` | `background_aggregation.py` | S |
| 4 | `ESIClient.get_route(origin, destination, preference)` | `core/esi_client_class.py` | S |
| 5 | Route-cache read/write + fan-out for uncached pairs; stamp jumps onto contract rows | `background_aggregation.py` | M |
| 6 | Expose `jumps` + `reward_per_jump`; add sort fields to `SortableContractFields`; add a preference query param | `schemas/contracts.py`, `services/contract_service.py` | M |
| 7 | Add `GET /route/{origin}/{destination}` to the drift monitor manifest (**required by ESI-4**) | `tools/esi_spec_monitor/manifest.py` | XS |
| 8 | Tests, TDD (per project mandate) | `tests/` | M |
| 9 | Courier tab: jumps column, ISK/jump sort, preference control | `app/frontend/web/src/` | M |

**Honest estimate: 1–2 days of agent work for the backend, plus the frontend courier tab it feeds into (which F008 is building regardless).** Nothing here is research; it is all wiring against patterns the repo already runs.

### Two concrete traps found while sizing

1. **`_get_esi_object` will reject the route response.** It hard-fails anything that is not a JSON object:
   ```python
   if not isinstance(data, dict):
       raise ESIRequestFailedError(
           message=f"Expected JSON object from {path}, got {type(data).__name__}"
       )
   ```
   The legacy `GET /route/` returns a bare **array**. This needs a list-shaped sibling helper — and note the docstring's warning about why the *paginated* helper cannot be used either (`full_data.extend(page)` flattens a dict into its keys). Neither existing helper fits; a third small one is needed.

2. **Divide-by-zero guard is mandatory.** Across 250 couriers in 5 regions there were **zero** same-location contracts, but nothing prevents a courier between two stations *in the same system*, which is 0 jumps. `reward / jumps` must guard. (Reward is not the risk: zero-reward couriers were 0/115.)

---

## 6. ESI-4 compatibility-date dependency — **this recommendation depends on it**

Per `docs/pitfalls/implementation-pitfalls.md` ESI-4 (omitting `X-Compatibility-Date` pins the client to the oldest published date), Hangar Bay sends no header and therefore gets **2020-01-01**. Verified: `https://esi.evetech.net/meta/openapi.json` responds `x-compatibility-date: 2020-01-01`.

Prior work recorded `/route/` as "renamed" across compatibility dates. **That undersells it.** Verified by fetching the spec at each published date and calling both shapes live:

| | compat **2020-01-01** (what we get today) | compat **≥ 2025-09-30** |
|---|---|---|
| Path | `/route/{origin}/{destination}` | `/route/{origin_system_id}/{destination_system_id}` |
| **Method** | **GET** | **POST** |
| Parameters | query: `flag`, `avoid`, `connections` | JSON body: `preference`, `security_penalty`, `avoid_systems`, `connections` |
| Preference values | `shortest` / `secure` / `insecure` | `Shorter` / `Safer` / `LessSecure` |
| Response | bare array `[30000142, ...]` | object `{"route": [...]}` |
| **Server cache** | **24h TTL + ETag** | **`not-cached`, no ETag** |

Live confirmation of the hard cutover:

```
GET  /route/30000142/30002187?flag=shortest   (compat 2026-07-21)  ->  HTTP 404
POST /route/30000142/30002187 {"preference":"Shorter"}             ->  11 jumps
```

Published compatibility dates today: `2026-07-21, 2026-07-17, 2026-06-09, 2026-05-19, 2025-12-16, 2025-11-06, 2025-09-30, 2025-09-26, 2025-08-26, 2025-04-02, 2025-04-01, 2020-01-01`. The rename lands at **2025-09-30**.

**Which date this recommendation requires:** it works **today, unchanged, at the current 2020-01-01 floor**, using `GET /route/{origin}/{destination}?flag=…`. No header change is needed to ship.

**The dependency to flag:** ESI-4 records that 2020-01-01 is a floor **CCP can raise with notice**. When Hangar Bay adopts a newer compatibility date — for any reason, including the `/meta/status` adoption ESI-1 wants — `/route/` **404s** and must be rewritten as a POST with a body and a different response envelope and different enum spellings. Mitigations:

- Adding `/route/` to the drift monitor manifest (work item 7) is what makes this *visible in advance* rather than a production 404. It is not optional.
- **The lost server-side cache is largely harmless for us** — we cache in Valkey ourselves with our own TTL, so `not-cached` costs us ETag revalidation, not request volume. At 3,600/15m against a ~107-pair working set, this does not bind.
- Both shapes return identical jump counts (verified: 11 / 45 / 40 under both). So the migration is mechanical, not semantic.

---

## 7. What I verified vs. what I inferred

### Verified by direct measurement (live ESI / live production API, 2026-08-01/02)

- Courier counts, endpoint counts, and distinct-pair counts for 5 regions, from `/v1/contracts/public/{region_id}/`.
- 91.3% (Forge) / 90.4% (5 regions) both-endpoint resolvability, and the player-structure cause.
- The full end-to-end run: 44 station lookups + 117 route calls = 161 calls in 8.4s.
- Jita→Amarr = 11 / 45 / 40 jumps by preference, and the per-system security audit confirming Ahbazon on the shortest path.
- The `secure`-is-not-a-guarantee finding (Jita→1DQ1-A, 81 jumps with 23 low/null systems).
- `security_penalty` non-monotonicity, 3 runs per value.
- The GET→POST cutover, the 404 at the newer date, and the `not-cached` change — from the spec at each date *and* live calls.
- 8,490 solar systems (agrees between ESI and SDE); rate limit 3,600/15m group `routes`.
- Payload sizes: 1,024 B/system, 221 B/stargate.
- That `_get_esi_object` rejects non-dict responses, and that `_npc_station_ids` reads only start locations — read from source.
- SDE/Fuzzwork/EVE Ref sizes, the 13,978-stargate count, the 4-component graph, and the stale legacy SDE URL — fetched directly by a research subagent, which reported its own unverified items (below).

### Inferred, labelled as such

- **That ~107 pairs is representative of full New Eden.** 5 regions is a sample. Courier share varied 0.34%–4.31%, and destinations are unbounded (anywhere in New Eden), so a full-coverage pair count could be several hundred to low thousands. *Inference: still ~1% of the rate-limit budget, so the conclusion is robust to being wrong by 10×.*
- **That route geography is static enough for a multi-day TTL.** Well-founded (stargates do not move) but not measured over time.
- **That defaulting to `secure` matches hauler convention.** Supported by freight-service pricing being both per-jump and security-segmented, but that support is a **web-search summary, not a primary rate card** — the service's own domain did not resolve. This remains the weakest-sourced claim in the document and is flagged as an open question. The *structural* point it rests on — that ISK/jump is never quoted without a security band — is corroborated independently by ESI's own API shape, which has no unqualified "jumps" call.
- **The 1–2 day size estimate.** A judgment call from reading the code, not from having built it.

### Explicitly not verified

- Fuzzwork's terms of use — no license page found. The underlying data remains under CCP's developer agreement (limited non-exclusive license to use/display/distribute Game Data within an Application; strictly non-commercial).
- EVE Ref's license position on redistributing its derived data.
- Whether any per-file SDE download URL exists (two guessed paths 403'd; the docs document none).

---

## 8. Open questions and risks

1. ~~**What should the default preference be?**~~ **RESOLVED 2026-08-01, after this spike was written.** A follow-up survey of shipped tools and community sources closed this against primary sources, and also corrected one recommendation in section 4:

   - **The default is confirmed high-security-preferred.** EVE University's *Moving your items* states the convention verbatim — "The payment should assume a fully hisec route if one is available" — and quotes ~900,000–1,000,000 ISK/jump for standard high-sec work. EVE Courier, the only surveyed tool exposing the control, defaults to High-Sec. The weakly-sourced rate-card inference is no longer load-bearing.
   - **Correction to section 4's UI recommendation.** This spike recommended a three-way user-facing preference picker. The survey found that no shipped tool does that except EVE Courier, and that Adam4EVE's pattern is better: auto-pick the route, then disclose per row which security tier it actually achieved (colour-coded, tooltipped — 142 high-sec / 110 low-sec / 23 null-sec on one live page load). F008 adopts per-row disclosure as the honesty mechanism, with a picker demoted to optional refinement.
   - **New correctness caveat on `secure`, not known when section 4 was written.** ESI's `secure` flag does not return the *shortest* high-sec route. Jita → Amarr: ESI returns 45 jumps while a fully high-sec 34-jump route exists; Amarr → Dodixie is 34 vs 25. Short routes agree exactly. ESI appears to weight rather than hard-constrain, so stored `secure` counts are an **upper bound** and can deflate reward-per-jump by up to roughly a third on long routes.
   - **One more framing correction.** Reward-per-jump is a comparison metric, not a quote: PushX bills per *warp* ("number of jumps + 1 in most cases"), with collateral multipliers and a 4.5M ISK floor.
   - **Also worth knowing:** no surveyed tool ships an ISK-per-jump column at all. The metric lives in rate cards and marketing copy, never in a shipped table.
2. **~9–10% of couriers will show no jumps.** Sorting by ISK/jump must decide where NULLs land. Given ESI-3's history in this repo (dead filters returning empty pages that read as "no matches"), the UI must make "unknown, player structure" visibly distinct from "low ISK/jump" — not silently sort them to the bottom.
3. **ESI-4 migration.** Covered in section 6. The mitigation is the manifest entry; without it this becomes a production 404.
4. **Only one region is ingested.** The courier tab ships against **115 contracts**. That is a thin tab. Worth knowing before investing in courier-specific UI — though it is an argument for broader ingestion, not against reward/jump.

---

## 9. Findings that affect F008 beyond reward/jump

Three things surfaced that change the courier tab design independently of this spike's question:

1. **`days_to_complete` is in every ESI courier payload (115/115) and is not stored.** It is absent from `models/contracts.py` entirely. It is a core courier field — the hauler's deadline — and the contract-coverage gap analysis already lists it as needed for courier display. Adding it is one column in the same migration this work needs anyway. **Near-free if done together, a second migration if not.**

2. **reward/m³ — the *other* ratio haulers sort on — is already free.** `volume` and `reward` are both stored on `Contract` today. It needs no ESI calls, no schema change, and no route data. If reward/jump were somehow rejected, **reward/m³ should ship regardless.** The gap analysis names both as "the ratios haulers sort on"; only one of them has any cost at all.

3. **`collateral` is populated on 115/115 couriers** and already stored. Collateral is what determines whether a hauler will touch a contract. It is available for the courier tab at zero cost.

Net: the courier tab's three highest-value columns beyond route are **collateral (free, stored), reward/m³ (free, stored), and days_to_complete (one column)**. Reward/jump is the only one with real cost, and that cost is ~320 cached lookups.
