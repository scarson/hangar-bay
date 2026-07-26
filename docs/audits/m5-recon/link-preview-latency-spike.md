# Link-Preview Routing — Latency Spike

ABOUTME: Measured cost of routing contract-detail page loads through the backend (needed for per-URL link previews) against today's CDN-served SPA shell.
ABOUTME: Read-only production measurements taken 2026-07-26; informs the routing decision in the trust & shareability design.

## Why this spike ran

Per-URL Open Graph previews require server-rendered meta tags — Discord's crawler does not execute JavaScript, and `app/frontend/web/index.html` carries no `og:*` tags at all. Render static sites cannot run server-side code and their route rules match **path only** (verified against Render's redirects/rewrites documentation: rules support `source` and `destination`, no header or User-Agent conditions), so a crawler-vs-human split cannot happen at Render's edge.

That leaves approaches which route some traffic through a server. The objection to all of them was latency, on a product whose stated principles include "Fast is a feature." This spike measured that cost instead of assuming it.

## Method

Read-only GETs against production (`hangarbay.app`), 12 samples per target, plus real browser navigation timing via the Performance API on a live contract page. No code deployed. Contract detail page used: a live contract ID sampled from `/api/v1/contracts/`.

## Results

### Transport-level (curl, median TTFB)

| Path | TTFB median | p90 | Notes |
|---|---|---|---|
| SPA shell via CDN (today) | **51.7 ms** | 68.5 ms | `cf-cache-status: HIT`, `age: 243` |
| `index.html` via CDN | 55.1 ms | 82.8 ms | same object |
| API via apex (`/api/v1/*` rewrite → backend) | **251.3 ms** | 398.7 ms | `cf-cache-status: BYPASS` |
| API direct to backend origin (bare path, PROXY-1) | **90.3 ms** | 142.0 ms | — |

**The external-rewrite hop costs ~161 ms median.** Confirmed independently on `/ready` (apex 0.31–0.57 s vs direct 0.13–0.22 s across 5 paired samples), so it is not an artifact of one endpoint.

**Root cause is not a misconfiguration.** Both paths are Cloudflare-fronted (Render's own edge is Cloudflare — consistent with M4 Deviation D-12's note that proxying our DNS would stack a *second* such layer). The shell is an edge-cache HIT served near the client; the API is `BYPASS` and travels to the ohio origin every request. The gap is edge-hit versus origin round-trip — distance, not waste.

### Page-level (browser Performance API, contract detail page)

Cold load (empty cache):

| Milestone | Time |
|---|---|
| Document TTFB | 65 ms |
| DOMContentLoaded | 822 ms |
| First data request issued | **3003 ms** |
| First Contentful Paint | **3592 ms** |

Warm load (assets HTTP-cached — the returning-user case). **Four samples, because the first one turned out to be the worst and was initially quoted as typical:**

| Sample | Assets done | First API request | Bootstrap gap | Time-to-content |
|---|---|---|---|---|
| 1 | 130 ms | 850 ms | 720 ms | 1265 ms |
| 2 | ~44 ms | 887 ms | ~840 ms | 1091 ms |
| 3 | 66 ms | 364 ms | **298 ms** | **711 ms** |
| 4 | 46 ms | 299 ms | **253 ms** | **628 ms** |

> **SUPERSEDED (2026-07-26, same day): every one of those four samples was contaminated.** Re-measured in a freshly opened browser tab, the bootstrap gap is **≈ 0** — three clean samples gave **2 ms, 10 ms and −12 ms** (negative because the API request fires *before* the last cached asset finishes; they overlap). Time-to-content was **~457 ms**, with FCP at 100–304 ms.
>
> The four samples below were taken in a tab that had been open across many navigations and heavy `Runtime.evaluate` calls. **The "bootstrap gap" was contention in the measuring environment, not work the application does.** Sample 2's two *cache-hit* modules reporting 825 ms durations was the tell, and it was misread as evidence of app cost rather than as evidence that the whole tab was stalled.
>
> **Corrected figures: warm time-to-content ~450–500 ms, of which the document is ~35–50 ms and the API call ~270 ms. There is no meaningful client-bootstrap term.**
>
> Original contaminated table preserved below, because the sequence of wrong numbers is the useful part.

**Contaminated range (superseded): a 253–840 ms bootstrap gap and 628–1265 ms time-to-content.** Samples 3 and 4 ran clean *relative to the others*; samples 1 and 2 show heavy contention.

**What the gap was, and was not.** Not asset downloading — every JS/CSS file was a cache hit in every sample. It was assumed to be main-bundle execution, React mount, TanStack Router route resolution and render. **That assumption was wrong**: in a clean tab the interval is ~0, so there is no app-side bootstrap cost to attribute.

**How that was settled, and a trap in the instrument.** `performance.getEntriesByType('longtask')` always returns empty — long tasks are only reachable through a `PerformanceObserver`. A first attempt with `observe({type:'longtask', buffered:true})` returned zero entries and was nearly reported as "no main-thread blocking". It was a **false negative**: validating the instrument by deliberately blocking the main thread for 220 ms and re-querying returned zero as well. Chrome keeps **no buffer for `longtask`**, so `buffered: true` retrieves nothing retroactively, even though it works for `paint` (verified — it returns `first-paint`/`first-contentful-paint`).

What does work:
- **Live observation** — register the observer *before* the work; the 220 ms synthetic block was caught correctly.
- **`long-animation-frame`** (LoAF) is supported here and is the right modern tool: it carries per-script attribution (`sourceURL`, `sourceFunctionName`, `invoker`) plus a style/layout breakdown. It also needs pre-load registration.

**So instrumenting load-time attribution requires registering an observer before the app boots — a code change** (an inline script in `index.html`, or `performance.mark()` calls at module-eval, mount, route-resolve and query-issue boundaries, with `performance.measure()` between them). That work was **not** done, because the re-measurement removed the thing it would have explained: there is no gap left to attribute.

**Never trust a zero from an unvalidated instrument.** Prove the instrument can see the thing before concluding the thing is absent.

Measured on a 10-core / 16 GB machine in an automated browser. A real user's Chrome may show less contention; the clean samples are probably closer to reality than the slow ones.

## What this means for the routing decision

1. **Document delivery is a real term, and the conclusion that it was negligible does NOT survive.** Against the corrected clean baseline of ~450–500 ms, the document is ~35–50 ms and the API call ~270 ms. With the imagined bootstrap gap gone, there is no large term for document delivery to hide behind.

2. **Routing contract pages through the backend costs ~200 ms of document delivery** (edge HIT → origin BYPASS). That is ~16% of the originally-quoted 1265 ms, ~30% of the once-corrected ~650 ms, and **~40%+ of the true ~450–500 ms baseline**. The estimate got worse at every re-measurement; each earlier figure flattered the change.

3. **Inlining contract data into the server-rendered shell removes the client's separate API call (~270 ms).** Tags plus inlining lands around ~250–300 ms against today's ~450–500 ms — still **net faster**, by roughly 150–200 ms rather than the ~300 ms first estimated. The backend already holds the data in-process for the OG tags, so inlining costs one query it was already making — unlike a Cloudflare Worker, which would need a second network fetch to get it.

4. **Consequence for scoping.** Shipping tags without inlining costs entry loads ~200 ms — **~40%+ of the true baseline**, and it is the *only* stage that is pure cost. Tags-alone is a regression users would feel; tags-plus-inlining is an improvement. On the corrected numbers these should ship together, which is where this spike started before two inflated baselines argued otherwise.

5. **Two larger performance findings fall out of this spike and are out of scope here**, recorded so they are not lost:
   - ~~The bootstrap gap is the largest single term~~ — **withdrawn**. There is no bootstrap gap; it was measurement contention. The largest term is the API call (~270 ms), most of which is the origin penalty below.
   - **Every SPA API call pays the ~161 ms origin penalty**, site-wide, on every page.

## Open question this spike could not resolve

**Can backend-rendered contract HTML be edge-cached?** The API path returns `cache-control: max-age=0` and shows `cf-cache-status: BYPASS`. If a backend HTML response carrying a short `s-maxage` (contract data changes about hourly, so 60–300 s is defensible) is honored by Render's edge, repeat views of the same contract return to ~50 ms and crawlers are served from cache — which would erase objection 2 entirely. It is unknown whether Render's edge caches rewrite-destination responses at all, or forces BYPASS regardless of origin headers.

This is cheap to settle but **requires deploying a response header and observing `cf-cache-status`** — it cannot be answered from outside. It should be the first task of any implementation, because a positive result simplifies the design and a negative one does not block it.

## Reproducing

`curl -w '%{time_starttransfer}'` against the four targets above; browser timings via `performance.getEntriesByType('navigation'|'resource'|'paint')` on a loaded contract page. The measurement script used is not committed — it is 40 lines of `curl` invocations and is faster to rewrite than to maintain.
