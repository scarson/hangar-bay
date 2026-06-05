---
run_schema_version: 1
run_id: 2026-06-05T02-05-s3-frontend
date: 2026-06-05T02:05:00Z
scope: "Frontend Angular SPA (latent — routes=[]) — slice S3 of whole-repo audit"
methodology:
  skill: performance-audit
  plugin_version: superpowers-plus@0.2.0
dispatch:
  model_requested: "latest-opus (Agent-tool subagents)"
  reasoning_effort: "default (harness exposes no knob)"
  overridden_by_user: false
stack:
  - { ecosystem: npm, framework: angular, version: "20" }
  - { ecosystem: npm, framework: "@angular/cdk", version: "20" }
  - { ecosystem: npm, framework: rxjs, version: "7.8" }
  - { ecosystem: npm, framework: typescript, version: "5.8" }
currency_briefs:
  - { framework: angular, researched_on: 2026-06-04, status: "version-index covered_through Angular 19 (zoneless GA in 21); Angular-20 resource APIs uncovered → Heuristic/manual-check" }
lanes_run: [data-access, idiom-currency, payload-startup, memory, cost-map]
lanes_skipped: { algorithmic: "examined — no dataset-sized loops/quadratics in the SPA; REDUCED-tier omit", concurrency: "N/A — single-threaded RxJS; no shared-state parallelism surface", dynamic: "deferred — static-only" }
finding_counts:
  by_impact: { critical: 0, major: 1, minor: 9 }
  by_lane: { data-access: 5, idiom-currency: 3, payload-startup: 3, memory: 2 }
  suspected_bugs: 8
regression:
  prev_run_id: null
  new: 10
  persisting: 0
  resolved: 0
---

# Performance Audit — Frontend Angular SPA (S3, **latent**)

**Date:** 2026-06-05 02:05 UTC   **Scope:** Angular 20 SPA — slice S3 of whole-repo
**Stack:** Angular 20 (zoneless + signals) / @angular/cdk 20 / RxJS 7.8 / TS 5.8 / `@angular/build`
**Currency brief:** version-index `javascript-typescript.md` (covered_through **Angular 19**, zoneless "GA in 21"; built 2026-06-04). The app targets Angular **20** (one major ahead), so resource-API recommendations are Heuristic + flagged for manual currency check; no live brief.
**Lanes run:** data-access, idiom-currency, payload-startup, memory, cost-map. **Reduced tier** (WARM-latent): `algorithmic` and `concurrency` examined and omitted as no-surface (recorded above), per the whole-repo method's REDUCED depth. dynamic deferred.
**Reachability (the defining fact):** `app/app.routes.ts` exports `routes = []` — grep-confirmed that **no template/component injects** `ContractSearch`/`ContractApi`/the pipes. The feature code is **latent (reachability ≈ 0 today)**; findings are ranked by what they'd cost **once wired** and are tagged accordingly. Only the bootstrap path is reachable now.
**Anti-padding result (this slice was the deliberate stress test):** the lanes did **not** manufacture findings over unreachable code. The `memory` lane explicitly declined to call the root-singleton subscription a leak and warned against the naive `pure:false` "fix"; the `payload-startup` lane returned "no CRITICAL/MAJOR, here's the posture"; `cdk`/`material` were grep-confirmed unimported and **not** charged to the bundle. All 10 findings are MINOR except one MAJOR-once-wired. **Calibration held.**
**Regression vs none:** 10 new.

## Major Findings

### FP1. Two overlapping HTTP services both GET `/contracts/` — divergent base URLs and response shapes
**Lanes:** data-access, idiom-currency, memory, cost-map (agreement ×4)   **Location:** `features/contracts/contract-search.ts:49,81` (`/api/v1/contracts/`) vs `features/contracts/contract.api.ts:62,64` (`environment.apiUrl + /contracts/`)
**Fingerprint:** `data-access:features/contracts:duplicate-contract-services`   **Status:** new
**Problem:** Two `providedIn:'root'` services hit the same backend collection with different base-URL strategies (hardcoded relative vs env-based) and different response models (`PaginatedContractsResponse{total,page,size,items}` vs `PaginatedShipContractsResponse{items,total_items,total_pages}`). Once a screen wires both, it doubles requests/interaction and splits any caching so identical queries never dedupe.
**Impact:** reachability **latent**; once wired = 2× requests + no request sharing on the primary data path. **Confidence:** Strong-static. **Effort:** Contained (collapse to one service + one model). **Verification plan:** one service, asserted single request per interaction; guard = the consuming component renders identical data. *(Also resolves suspected bugs SB-S3-1/3/4.)*

## Minor Findings (all latent-once-wired unless noted)

- **FP2. 300 ms debounce applied to discrete actions, not just text search.** `data-access`. `contract-search.ts:56-63,102-105` — `updateFilters` funnels page/size/sort through the same `debounceTime(300)`→`switchMap`, so pagination/sort pays a 300 ms tax and rapid paging can skip an intermediate page. (The debounce+switchMap is *correct* for type-ahead search — no stale render.) Effort Localized (split the trigger).
- **FP3. `JSON.stringify`-based `distinctUntilChanged`.** `data-access`, `memory`, `cost-map`. `contract-search.ts:61` — key-order-sensitive; can mis-dedupe a resolver-set filter and refetch. CPU trivial (≤6 scalars). Effort Localized (field comparator).
- **FP4. No request sharing/cache; no `withHttpTransferCache()`.** `data-access`. Re-navigating to a viewed page refetches. Effort Contained. *(Design call — freshness.)*
- **FP5. Hand-rolled `Subject`+`switchMap`→signal vs the Angular 20 resource idiom.** `idiom-currency`. `contract-search.ts:53-94` (+ `contract.api.ts:44-94`) — current zoneless+signals idiom for "filters → async → {data,loading,error}" is `rxResource`/`httpResource`/`toSignal` (index line 81). Currency/maintenance, not hot-path. **Heuristic** (replacement-API stability is past the index's `covered_through`). Effort Contained.
- **FP6. `timeLeft` pure pipe reads a moving clock → renders a frozen snapshot.** `idiom-currency`, `memory`, `cost-map`. `shared/pipes/time-left.ts:14`. As a pure pipe it's churn-free (good) but the countdown never ticks. **Perf-relevant guidance:** do **not** convert to `pure:false` (that re-runs `new Date()`+arithmetic per row per CD pass — real churn); use a shared interval `signal`/`computed` clock. The staleness itself is a correctness bug (SB-S3-6). Effort Localized.
- **FP7. `@angular/localize/init` polyfill ships eagerly with zero `$localize` usage.** `payload-startup`. `angular.json:37-39` (also dup'd in `test` builder) — ~10–15 kB (heuristic) of dead weight in an otherwise framework-only initial bundle; grep finds no i18n usage. Effort Localized (re-add when i18n begins).
- **FP8. No lazy-loading / code-splitting convention established.** `payload-startup`. `app.routes.ts:3` empty while an un-routed `features/contracts/` already exists — risk the first feature is wired eagerly and pulls its full graph into the initial bundle instead of a `loadComponent`/`loadChildren` < 200 kB chunk. **Latent.** Effort Contained (set the convention now). **Heuristic.**
- **FP9. Budget has no warning headroom and no lazy-chunk budget.** `payload-startup`. `angular.json:43-54` — `initial` warns at 500 kB (= the target, so no early warning), errors at 1 MB (2× target); no per-lazy-chunk budget, so the documented "lazy < 200 kB" target is unenforced. Effort Localized.
- **FP10. Per-row pipe cost on list render once wired; page `size` is URL-unbounded → consider CDK virtual scroll.** `cost-map`, `memory`. With up to ~100 rows/page (and the resolver parses `size` from the URL without clamping — `contract-filter.resolver.ts:19`), the first render is O(rows × pure pipes); `Isk.transform`'s `toLocaleString` and `TimeLeft`'s 2 `Date` allocations are the priciest. `@angular/cdk` is already a dependency. **Latent.** Effort Contained (virtual scroll + `track contract_id` when the list template lands; clamp `size`).

## Cross-Cutting Themes
1. **The feature is duplicated and half-wired** (FP1 + two model files + the resolver dropping filters) — consolidating to one service/model/contract is the single highest-value frontend change and resolves four suspected bugs at once.
2. **The build posture is sound but un-guard-railed for growth** (FP8 + FP9 + FP7) — set lazy-loading + budgets + drop the unused i18n polyfill *before* features land, while it's cheap.
3. **Zoneless + signals + pure pipes is the favorable baseline** — steady-state CD is near-free; cost concentrates on the first render of each result page (FP10), not CD breadth. The architecture is well-chosen.

## Measurability
Nothing is measurable at runtime today (latent). Once wired, the relevant signals are Lighthouse/Web-Vitals (FCP/LCP/TTI/INP — the project's stated targets) and `ng build --configuration production` bundle/budget output (for FP7/FP8/FP9, measurable **now** via a build). The payload findings have a concrete, runnable verification (`ng build` + the analyzer) that was **not** executed this static-only run.

## Execution Cost Map (highlights)
> Full map: `2026-06-05T02-05-s3-frontend-cost-map.md`. Most regions are **latent-once-wired**.
- **Reachable now:** app bootstrap/provider graph (one-shot, bounded).
- **Latent-once-wired, High:** first-render per-row pipe evaluation across the list (FP10).
- **Latent-once-wired, Medium:** the debounce→switchMap→HTTP search path (network-bound); signal/computed propagation on each settle (targeted, not tree-wide — zoneless).
- **Architecture note:** pure pipes + zoneless mean the classic tree-wide CD cost center does not apply; `track contract_id` and clamping `size` are the levers once the `@for` list exists.

## Suspected Bugs (for follow-up — NOT addressed here)
> Recorded, not chased. Kickoff: `docs/perf-audits/2026-06-05-s3-frontend-bug-hunt-kickoff.md`.
- **SB-S3-1.** Response-shape mismatch: `ContractApi` reads `response.total_items`/`total_pages` (`contract.api.ts:71-73`) but the backend returns `total`/`page`/`size`/`items` — these fields are always `undefined`.
- **SB-S3-2.** Param-name mismatch: `ContractSearch` sends `sort_order` (`contract-search.ts:76-78`) but the backend expects `sort_direction`; sort is silently ignored.
- **SB-S3-3.** Two divergent model files (`contract.model.ts` vs `contract.models.ts`) for one endpoint.
- **SB-S3-4.** Base-URL inconsistency (relative `/api/v1/...` vs `environment.apiUrl`) → 404 risk under a prod origin/CDN split.
- **SB-S3-5.** Resolver parses only page/size/search (`contract-filter.resolver.ts:18-26`), dropping `type`/`sort_by`/`sort_order` on deep-link load.
- **SB-S3-6.** `timeLeft` never updates after first render (pure pipe over a wall-clock value) — fix preserving purity via a shared ticking timebase.
- **SB-S3-7.** `.bak` files included in `tsconfig.app.json:13` compilation `include`, plus stray `.bak` files in `src` — build hygiene.
- **SB-S3-8.** Error path leaves stale `data` and the `null` from `catchError` is silently dropped by the truthy guard (`contract-search.ts:84,90-94`).

## False positives / correctly-rejected (anti-padding wins, recorded)
- **Root-singleton subscription as a leak** — explicitly NOT flagged; a `providedIn:'root'` service lives for the app lifetime and `switchMap` cancels in-flight HTTP. (`memory` lane.)
- **`pure:false` as the `timeLeft` "fix"** — explicitly warned against (would create per-row/per-CD churn).
- **`@angular/cdk`/`@angular/material` bundle cost** — grep-confirmed unimported; not charged to the bundle despite being a declared dependency.
- **No render nits manufactured** over the latent `@for`/list code that doesn't exist yet — forward expectations only.
