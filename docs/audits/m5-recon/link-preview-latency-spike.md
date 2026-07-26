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

Warm load (assets HTTP-cached — the returning-user case):

| Phase | Window |
|---|---|
| Document + all cached JS/CSS | 48 → **130 ms** |
| Client bootstrap before any data request | 130 → **850 ms** (~720 ms) |
| Contract API call | 851 → **1265 ms** (~414 ms) |

Measured on a 10-core / 16 GB machine, so the bootstrap gap is not weak-hardware noise — but it *was* measured in an automated browser, and absolute values on a real user's Chrome may differ. The **relative** comparison between routing approaches is unaffected, since client bootstrap is constant across them.

## What this means for the routing decision

1. **Document delivery is the smallest component of time-to-content**, not the largest. Warm time-to-content is ~1265 ms, of which the document is ~48 ms. Optimizing document delivery to protect "fast is a feature" was aiming at the wrong term.

2. **Routing contract pages through the backend costs ~200 ms of document delivery** (edge HIT → origin BYPASS) — real, but recoverable, see next point.

3. **Inlining contract data into the server-rendered shell removes the client's separate API call (~414 ms).** Net effect is roughly **300 ms faster than today**, not slower. This inverts the original objection. The backend already holds the data in-process for the OG tags, so inlining costs one query it was already making — unlike a Cloudflare Worker, which would need a second network fetch to get it.

4. **Consequence for scoping, and it is a hard one:** OG tags and data inlining must ship *together*. Routing contract pages to the backend for tags alone, without inlining, ships a measurable ~200 ms regression. Either both, or neither.

5. **Two larger performance findings fall out of this spike and are out of scope here**, recorded so they are not lost:
   - **~720 ms of client bootstrap before the first data request** dominates warm time-to-content. This is the single largest lever on page speed and has nothing to do with link previews.
   - **Every SPA API call pays the ~161 ms origin penalty**, site-wide, on every page.

## Open question this spike could not resolve

**Can backend-rendered contract HTML be edge-cached?** The API path returns `cache-control: max-age=0` and shows `cf-cache-status: BYPASS`. If a backend HTML response carrying a short `s-maxage` (contract data changes about hourly, so 60–300 s is defensible) is honored by Render's edge, repeat views of the same contract return to ~50 ms and crawlers are served from cache — which would erase objection 2 entirely. It is unknown whether Render's edge caches rewrite-destination responses at all, or forces BYPASS regardless of origin headers.

This is cheap to settle but **requires deploying a response header and observing `cf-cache-status`** — it cannot be answered from outside. It should be the first task of any implementation, because a positive result simplifies the design and a negative one does not block it.

## Reproducing

`curl -w '%{time_starttransfer}'` against the four targets above; browser timings via `performance.getEntriesByType('navigation'|'resource'|'paint')` on a loaded contract page. The measurement script used is not committed — it is 40 lines of `curl` invocations and is faster to rewrite than to maintain.
