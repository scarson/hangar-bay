# Frontend Data Access & I/O Audit (HTTP + RxJS dataflow)

Lane: **frontend-data-access** — superpowers-plus/performance-audit, STATIC-ONLY.
Stack: Angular 20 (zoneless + signals), RxJS 7.8, TS 5.8, `provideHttpClient(withFetch())`.

## Reachability calibration (read first)

`app/app.routes.ts` exports `routes = []` (confirmed, line 3). No routes are wired, so the
router never resolves `contractFilterResolver`, never lazy-loads a contracts feature, and no
component injects `ContractSearch` or `ContractApi`. A repo-wide grep for `ContractSearch`,
`ContractApi`, `updateFilters`, and `getContracts` matches only the two service files, the
resolver, the models file, and `*.spec.ts` / `*.bak` files — **no template or component
consumer exists**. Both services are `providedIn: 'root'` but are tree-shaken / never
instantiated because nothing injects them.

Therefore **runtime reachability ≈ 0 today**. Findings below are ranked by what they WOULD cost
**once a contracts route + search component are wired in** and rendering up to ~100
contracts/page. Every finding carries the latent caveat. Bootstrap/config (`app.config.ts`,
`main.ts`, `environments/*`) is already reachable and is assessed without the caveat.

---

### [MAJOR impact] Two overlapping HTTP services both `GET` the contracts endpoint with divergent contracts

**Location:** `app/features/contracts/contract-search.ts:49,81` (`/api/v1/contracts/`) and
`app/features/contracts/contract.api.ts:62,64-65` (`${environment.apiUrl}/contracts/`)

**Problem:** Two independent root-provided services target the same backend collection
`GET /contracts/`. `ContractSearch` is the signal+RxJS pipeline (debounce/switchMap, paginated
browse). `ContractApi` is a second imperative service doing the same fetch with a different
state shape and a **different, hardcoded-vs-env base URL**: `ContractSearch` hardcodes the
relative `'/api/v1/contracts/'` (relies on a dev proxy / same-origin), while `ContractApi`
builds `environment.apiUrl + '/contracts/'` (`http://localhost:8000/api/v1/contracts/` in dev,
the prod domain in prod). They also consume **different response shapes** from the same
endpoint — see the response-shape finding below. Once a feature is wired, whichever service a
component reaches for determines both base URL and response contract; the duplication invites a
screen that mounts both (e.g. a list using one, a count/summary using the other), doubling
requests-per-interaction (2 calls per filter change instead of 1) and splitting cache/sharing so
identical queries never dedupe. There is no `shareReplay`/dedup layer on either path.

**Impact:** Latent (reachability ≈ 0 now). Once wired: structural risk of 2 requests per
interaction for the same data plus a maintenance fork where the two diverge further. No
stale-render risk from this item itself; the risk is duplicate/overlapping fetches and no shared
cache.

**Confidence:** Strong-static (both files read; same endpoint path confirmed; no consumer
chooses between them yet).

**Effort:** Contained — collapse to one service (keep the `ContractSearch` pipeline, delete
`ContractApi` or make it a thin facade), unify on `environment.apiUrl`, pick one response shape.
Touches the two service files, their specs, and the eventual consumer.

**Verification plan:** Grep confirms no consumer today. Argue from the endpoint string match
(`/contracts/` in both). Correctness guard: when consolidating, assert via a unit test that the
surviving service uses `environment.apiUrl` (so prod points at the real domain, not a relative
path that 404s under a CDN/origin split) and that exactly one HTTP call fires per `updateFilters`.

---

### [MAJOR impact] `switchMap` over a 300ms-debounced trigger is correct for cancellation, but `updateFilters` fires the trigger on *every* partial filter mutation including pagination

**Location:** `app/features/contracts/contract-search.ts:56-63,102-105`

**Problem:** The pipeline is structurally sound for search-as-you-type: `debounceTime(300)` then
`switchMap` (line 63) cancels the in-flight request when a newer filter arrives, so stale
responses cannot render for rapid sequential typing — good. The cost is in the trigger surface:
`updateFilters()` (line 102) calls `filterTrigger$.next()` for *any* partial change — page
change, size change, sort toggle, and free-text search all funnel through the same 300ms debounce.
For discrete actions (clicking "next page", toggling sort) the 300ms delay is latency the user
feels for no benefit (those are not high-frequency input streams), while for the text `search`
field the debounce is appropriate. Mixing both through one un-parameterized debounce means either
discrete actions are needlessly delayed (current behavior) or, if the debounce were removed,
typing would become chatty. The result once wired: every keystroke that survives the debounce is
1 request (acceptable), but pagination/sort also pay the 300ms tax and share the same cancellation
window — a fast "next page, next page" double-click collapses to a single request via `switchMap`,
which is *usually* desired but means an intermediate page is silently skipped.

**Impact:** Latent (reachability ≈ 0). Once wired and rendering ~100/page: ~1 request per settled
interaction (good), but 300ms added latency on every discrete pagination/sort action, and
possible skipped intermediate page on rapid paging. Stale-render risk is *low* because
`switchMap` cancels — this is the correct operator choice for search; flagged for the
undifferentiated trigger, not for a cancellation bug.

**Confidence:** Strong-static.

**Effort:** Localized — split the trigger: debounce only the text-search path (e.g. a separate
subject or `debounce(t => isTextChange ? timer(300) : timer(0))`), let pagination/sort fire
immediately. Single-file change in `contract-search.ts`.

**Verification plan:** Trace `updateFilters` → `next()` → debounce → switchMap. Correctness guard:
marble/unit test that a text change waits ~300ms and is cancellable, while a page change fires
without the 300ms delay and that no two pages render out of order.

---

### [MINOR impact] `JSON.stringify`-based `distinctUntilChanged` in the request hot path

**Location:** `app/features/contracts/contract-search.ts:61`

**Problem:** `distinctUntilChanged((prev, curr) => JSON.stringify(prev) === JSON.stringify(curr))`
serializes the entire filter object twice on every trigger emission to detect duplicates. The
filter object is tiny (≤6 scalar fields: page, size, search, type, sort_by, sort_order), so the
per-call cost is negligible. Two correctness hazards outweigh the micro-cost: (1) `JSON.stringify`
key order is insertion-order-dependent — `{page,size,search}` vs `{search,page,size}` serialize
differently and would be treated as *changed* even when semantically equal, causing a redundant
fetch; `updateFilters` spreads `{...current, ...newFilters}` (line 103) which preserves key order
so this is latent, but `setInitialFilters` (line 113) replaces the whole object and the resolver
builds it with a different key order (`page,size,search`), so the first post-resolver
`updateFilters` could see a key-order-only "change" and refetch. (2) `undefined` fields are dropped
by `JSON.stringify`, so toggling a field to `undefined` vs deleting it compares equal — generally
fine here but a subtle trap.

**Impact:** Latent (reachability ≈ 0). Once wired: at most a small number of redundant fetches on
key-order mismatch (1 extra request on first interaction after resolver-set filters); per-call CPU
is trivial at this object size. Stale-render risk: none.

**Confidence:** Strong-static (object size and serialization semantics are determinate).

**Effort:** Localized — replace with an explicit field comparator
(`prev.page===curr.page && prev.size===curr.size && prev.search===curr.search && …`), which is
both faster and order-insensitive. Single-line change.

**Verification plan:** Unit test that two filter objects with identical values but different key
order compare equal (no refetch). Guard: ensure the comparator lists every field the request
sends, so a real filter change still triggers a fetch.

---

### [MINOR impact] No request sharing / cache across identical filter states (re-navigation refetches)

**Location:** `app/features/contracts/contract-search.ts:81-88` (no `shareReplay`/cache layer);
`contract.api.ts:64-94` (same)

**Problem:** Neither service memoizes responses by filter key. The `distinctUntilChanged` only
suppresses *consecutive* identical triggers within one subscription; it does not cache results.
Once wired, navigating away and back to the same page/filter, or returning to a previously-viewed
page during paging, re-issues the full `GET` every time. For a public, slowly-changing contracts
list this is avoidable chattiness. There is no `withHttpTransferCache()` / HTTP caching configured
in `app.config.ts` either, and `withFetch()` alone does not add app-level response caching.

**Impact:** Latent (reachability ≈ 0). Once wired and paging back-and-forth: 1 redundant request
per re-visit of an already-fetched filter state. Stale-render risk: none (refetch returns fresh
data). Aggregate cost low for a browse UI but grows with paging depth.

**Confidence:** Heuristic — whether caching is desirable depends on data-freshness requirements
(public contracts can go stale), so this is a design call, not a clear defect.

**Effort:** Contained — add a small keyed cache (Map of filter-key → `shareReplay(1)` observable
with a TTL/eviction) or adopt `withHttpTransferCache()` for SSR paths; touches the chosen service.

**Verification plan:** Confirm no cache exists (read both services). If adopting caching, guard
with a TTL test so stale public-contract data cannot render indefinitely, and assert a cache hit
issues 0 network calls.

---

### [MINOR impact] Bootstrap config is lean; one already-reachable I/O-adjacent note

**Location:** `app/app.config.ts:11-18`, `main.ts:8-15`, `environments/*`

**Problem:** `app.config.ts` provides `provideHttpClient(withFetch())` with **no
interceptors, no `withHttpTransferCache()`, and no retry/timeout policy**. This is reachable
today (it bootstraps regardless of routes). For the intended public-read browse workload that is
acceptable as-is, but two data-access gaps will matter the moment a feature is wired: (1) no
`withHttpTransferCache()` means if SSR is ever added, the first contracts fetch double-fetches
(server then client); (2) no centralized error/retry interceptor means each service hand-rolls
its own `catchError` (which both already do, divergently — see `contract-search.ts:82` vs
`contract.api.ts:76`). `main.ts` correctly guards a misconfigured prod `apiUrl` (lines 9-14),
which is a useful fail-fast and not a perf issue. `ContractSearch` ignoring `environment.apiUrl`
in favor of a hardcoded relative path (line 49) is the prod-vs-dev base-URL split already called
out in the duplicate-services finding.

**Impact:** Reachable now (bootstrap), but the data-access consequences are latent until a
feature mounts. No measurable cost today. Once wired with SSR: a double-fetch waterfall on first
load absent transfer-cache.

**Confidence:** Strong-static (config read directly).

**Effort:** Localized — add `withHttpTransferCache()` if/when SSR lands; optionally a shared HTTP
interceptor to unify error handling. Single-file change in `app.config.ts`.

**Verification plan:** Confirm provider list (read). If SSR is in scope, guard with a test/manual
check that the contracts request fires once across server+client (transfer-cache hit), not twice.

---

## Suspected Bugs (for follow-up)

These are correctness mismatches (not perf); recorded, not chased:

1. **Response-shape mismatch between the two services for the same endpoint.**
   `ContractSearch` expects `PaginatedContractsResponse = { total, page, size, items }`
   (`contract.models.ts:46-51`). `ContractApi` expects
   `PaginatedShipContractsResponse = { items, total_items, total_pages, page, size }`
   (`contract.model.ts:34-40`) and reads `response.total_items` / `response.total_pages`
   (`contract.api.ts:71-73`). The same `GET /contracts/` cannot satisfy both shapes — at least
   one is wrong against the backend contract, and the consumer would have to rework the response
   (`total` vs `total_items`/`total_pages`). Confirm which matches the FastAPI schema.

2. **Two divergent model files for the same domain.** `contract.models.ts` (`Contract` /
   `ContractItem`, generic public contract) vs `contract.model.ts` (`ShipContract`, ship-specific,
   different fields entirely: `ship_type_id`, `is_blueprint_copy`, `runs`, `material_efficiency`).
   These describe different payloads from ostensibly one endpoint; resolve which the backend
   returns before wiring a component.

3. **Base-URL inconsistency.** `ContractSearch` uses relative `'/api/v1/contracts/'`
   (`contract-search.ts:49`, no env), `ContractApi` uses `environment.apiUrl + '/contracts/'`
   (`contract.api.ts:62`). Under a production origin/CDN split the relative path may resolve to
   the wrong host or 404. Pick one strategy.

4. **Resolver drops filters the pipeline supports.** `contractFilterResolver`
   (`contract-filter.resolver.ts:18-26`) parses only `page`, `size`, `search` from query params,
   but `ContractSearchFilters` also supports `type`, `sort_by`, `sort_order`
   (`contract.models.ts:61-63`). Deep-linking a sorted/filtered URL would silently lose those
   params on initial load. Functional gap, not perf.
