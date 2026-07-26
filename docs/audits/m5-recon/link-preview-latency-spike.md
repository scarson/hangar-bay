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

**Honest range: a 253–840 ms bootstrap gap and 628–1265 ms time-to-content.** Samples 3 and 4 ran clean; samples 1 and 2 show contention. Sample 2 is instructive — two *cache-hit* modules (`format-*.js`, `useWatchlist-*.js`, both `transferSize === 0`) reported 825 ms durations, which reads as main-thread blocking or cache-read stalling rather than real work.

**What the gap is, and is not.** It is not asset downloading: every JS/CSS file was a cache hit in every sample. It is the interval after the bundles are in hand and before `useQuery` issues its request — main-bundle execution, React mount, TanStack Router resolving the route, the route component rendering. The breakdown *within* that window was not instrumented (no `longtask` entries were captured), so no attribution between JS execution, framework init, and application logic is claimed here.

Measured on a 10-core / 16 GB machine in an automated browser. A real user's Chrome may show less contention; the clean samples are probably closer to reality than the slow ones.

## What this means for the routing decision

1. **Document delivery is the smallest component of time-to-content**, not the largest. Against a clean warm baseline of ~630–710 ms, the document is ~35–48 ms. Optimizing document delivery to protect "fast is a feature" was aiming at the wrong term. This conclusion survives the corrected numbers — but by a smaller margin than the first draft claimed.

2. **Routing contract pages through the backend costs ~200 ms of document delivery** (edge HIT → origin BYPASS). Against the originally-quoted 1265 ms baseline that is ~16%; against the clean ~650 ms baseline it is **closer to ~30%**. The first framing understated it, because it compared against the slowest observed sample.

3. **Inlining contract data into the server-rendered shell removes the client's separate API call (~414 ms).** Net effect is roughly **300 ms faster than today**, not slower. This inverts the original objection. The backend already holds the data in-process for the OG tags, so inlining costs one query it was already making — unlike a Cloudflare Worker, which would need a second network fetch to get it.

4. **Consequence for scoping.** Shipping tags without inlining costs entry loads ~200 ms — about 30% of a clean baseline. That is a real regression rather than a rounding error, though not obviously a blocking one; whether to couple the stages is a judgement call, and the corrected numbers make coupling more defensible than the first draft concluded.

5. **Two larger performance findings fall out of this spike and are out of scope here**, recorded so they are not lost:
   - **The bootstrap gap (253–840 ms) is the largest single term in warm time-to-content**, larger than the API call in the clean samples and far larger than document delivery. It has nothing to do with link previews and is the biggest available lever on page speed.
   - **Every SPA API call pays the ~161 ms origin penalty**, site-wide, on every page.

## Open question this spike could not resolve

**Can backend-rendered contract HTML be edge-cached?** The API path returns `cache-control: max-age=0` and shows `cf-cache-status: BYPASS`. If a backend HTML response carrying a short `s-maxage` (contract data changes about hourly, so 60–300 s is defensible) is honored by Render's edge, repeat views of the same contract return to ~50 ms and crawlers are served from cache — which would erase objection 2 entirely. It is unknown whether Render's edge caches rewrite-destination responses at all, or forces BYPASS regardless of origin headers.

This is cheap to settle but **requires deploying a response header and observing `cf-cache-status`** — it cannot be answered from outside. It should be the first task of any implementation, because a positive result simplifies the design and a negative one does not block it.

## Reproducing

`curl -w '%{time_starttransfer}'` against the four targets above; browser timings via `performance.getEntriesByType('navigation'|'resource'|'paint')` on a loaded contract page. The measurement script used is not committed — it is 40 lines of `curl` invocations and is faster to rewrite than to maintain.
