# Routing review — Discord unfurls for contract pages (independent opinion, Fable)

Reviewer: Claude (Fable 5), 2026-07-26. Independent architectural read; the requester
deliberately withheld their preference. Grounded against the repo (`render.yaml`, frontend
route tree, `index.html`) and the measurements supplied in the brief.

## Verdict

**Option 1 — backend owns the contract routes — staged in three pieces, with a
15-minute edge-cache probe run first.** Option 2 is disqualified by the stated
requirements, not by taste. Option 3 is the technically cleverest answer and the wrong
one for this project at this moment.

One repo fact that strengthens Option 1 considerably: the frontend route tree is
`contracts.index.tsx` (filtered search at `/contracts`) and `contracts.$contractId.tsx`
(detail at `/contracts/:id`). **A single `/contracts*` rewrite covers both the primary
and the secondary case.** The search page is not at `/`, so the blast radius of handing
this prefix to the backend is exactly the two pages that need unfurls — nothing else.

---

## 1. Why Option 1

### Option 2 is eliminated by the requirements, full stop

Users copy URLs from the address bar. `/s/c/:id` links only exist if someone clicks a
Share button, so the primary flow — paste `hangarbay.app/contracts/123` into Discord —
produces no preview. The brief itself states this constraint; Option 2 fails it by
construction. It also proliferates two URL shapes for the same resource, and the
human-bounce page (JS or meta-refresh redirect) is visible jank for anyone who does
click a share link. No implementation quality rescues a design that misses the main
use case. Eliminated.

### Option 1 vs Option 3 — the real contest

Both satisfy the address-bar constraint. The decision turns on four axes:

**Operational surface.** Option 1 adds zero services, zero deploy pipelines, zero
credential sets. The route handler lives in `fastapi_app/api/`, is tested with the
existing pytest suite under the existing TDD discipline, ships through the existing CD,
and logs through the existing structlog → Alloy → Grafana Cloud path. Option 3 adds a
Cloudflare Worker: wrangler tooling, a CF API token in CI, a third deploy pipeline the
existing CD knows nothing about, and observability in a separate console. For a repo
run by one person plus agents, whose entire prod stack is currently "two Render
services and a database," a third platform for one HTML `<head>` is a poor trade —
especially for a milestone explicitly framed as small polish before a trial.

**Cache correctness by construction.** Option 1 serves the *same* HTML to every
User-Agent. There is nothing UA-variant anywhere, so no `Vary: User-Agent` problem, no
"crawler page cached and served to a human" failure class, and edge caching (if
available — see §3c) is a pure win. Option 3's whole mechanism is UA-variant responses
threaded through **three** cache layers (Render's edge on the rewrite, Cloudflare's
cache on the Worker route, the Worker's subrequest to the shell). `Vary: User-Agent`
is notoriously unreliable at CDNs; the only safe posture is `no-store` on everything
the Worker emits, which forfeits edge caching entirely and still leaves you auditing
whether Render's edge caches rewrite-destination responses regardless. Option 1 has no
such audit to do.

**Latency honesty.** Option 3's headline advantage — "humans keep CDN latency" — is
partly unverified. The measured ~161 ms external-rewrite penalty is Render-edge proxy
overhead *plus* the edge→ohio leg, in unknown proportion. Option 3's human path is
Render edge → CF Worker → shell fetch; if a meaningful share of the 161 ms is Render's
proxy overhead itself, Option 3 humans pay much of the penalty anyway, while inheriting
all the new complexity. Nobody has measured a Render rewrite to a nearby Cloudflare
destination. Option 3's central benefit is a hypothesis; Option 1's central cost
(~200 ms median on entry-load documents) is measured and bounded.

**Where the cost lands vs where the benefit lands.** The ~200 ms document penalty
applies **only to full document loads** — pasted links, refreshes, first entry.
In-app navigations are TanStack Router client-side transitions with no document request
at all: unchanged. And the entry-load visitor is *exactly* the Discord-link-clicker
this milestone serves — the same person who, once data inlining ships (§below), gets
the ~300 ms net *improvement*. The cost and the compensating win land on the same
request class. That symmetry is what makes Option 1 coherent rather than merely
tolerable.

### The staged shape (this is the recommendation, not an option-1 monolith)

- **Stage 0 (an hour, ship immediately):** add *static* site-wide OG tags to
  `app/frontend/web/index.html` — `og:site_name`, `og:title`, `og:description`,
  `og:image` (a branded card), `twitter:card`. Today the file has none. Every pasted
  link — homepage, watchlist, anything — gets a branded unfurl right away, and pages
  the dynamic work never covers stay covered forever. This is the true minimum polish
  and it de-risks the trial even if everything below slips.
- **Probe (15 minutes, before committing to perf posture):** the edge-cache experiment
  in §3c. Its outcome sets Stage 1's cache headers, nothing else — Stage 1 proceeds
  either way.
- **Stage 1 (the milestone's core):** Render rewrite `/contracts*` → FastAPI (rules
  *before* the SPA catch-all — same ORDER-MATTERS pattern already commented in
  `render.yaml`). FastAPI fetches the built shell from the static origin
  (`hangar-bay-web`'s `.onrender.com` hostname, **not** the apex — see §2, loop
  hazard), holds it in a process-global cache, revalidates with `If-None-Match` per
  request (ohio → CF edge conditional GET is tens of ms; a 304 costs almost nothing),
  and keeps the last-known-good copy as stale-if-error. It injects escaped
  `og:title` / `og:description` / `og:image` (EVE image CDN by type ID, absolute URL)
  into `<head>` and returns the shell to *everyone* — no UA sniffing.
- **Stage 2 (fast-follow, measured before/after):** inline dehydrated contract data
  (one `<script>` with the query payload; frontend seeds TanStack Query from it).
  This converts the entry-load penalty into the measured ~300 ms net win. Its benign
  failure mode — query-key mismatch — degrades to today's behavior (client refetches).
- **Stage 3 (optional, still same architecture):** the filtered-search secondary case.
  Same rewrite already routes `/contracts?type=...`; backend maps filter params to a
  summary string and a count. Count needs a query per crawler hit — cache it in Valkey
  keyed by normalized filter, short TTL. Defer freely; no new decisions required.

---

## 2. Risks and failure modes, per option

### Option 1 (chosen — these must be engineered for, not hand-waved)

1. **Deploy-skew / stale-shell 404s — the 3am scenario.** Frontend deploys new hashed
   assets; a backend-cached stale shell references bundles the static origin no longer
   serves → white page on contract routes. Mitigation is the per-request
   `If-None-Match` revalidation above. Note the repo's *existing* exposure: the
   `Cache-Control: no-cache` header rule in `render.yaml` matches only the literal
   path `/index.html`; SPA-fallback documents on deep links ride Render's default
   `s-maxage=300` (which is exactly why the brief measured a `cf-cache-status: HIT`
   shell). So the site already tolerates a ≤5-minute stale-shell window after every
   frontend deploy. The bar for Stage 1: **no worse than that window**; ETag
   revalidation beats it.
2. **Availability coupling.** Today a dead backend still serves the shell; the SPA
   renders its own error state. After Stage 1, `/contracts*` documents fail entirely
   when FastAPI is down (Render rewrites have no fallback rule). Partial mitigation:
   the handler serves the cached shell with *generic* tags when the DB/lookup fails —
   so only a fully-down FastAPI process takes the pages out. Accept for a friendly-corp
   trial; monitor; note that `healthCheckPath: /ready` already gates deploys for
   zero-downtime.
3. **XSS via contract data.** Contract titles are player-authored text going into
   meta-tag attribute values. Escape with quoting (`html.escape(quote=True)`);
   integer-validate the type ID before building the image URL. This is the one
   security-review item in the milestone.
4. **Single-instance backend absorbs document traffic.** The API is deliberately
   pinned to one instance (scheduler disk pin, starter plan) and also runs ingestion.
   Corp-trial page traffic is trivial; flag it as a capacity note for later, not a
   blocker now.
5. **Render route-matching details to verify at apply time:** (a) whether
   `source: /contracts/*` matches bare `/contracts` — if not, add both rules;
   (b) the API hostname is flagged in `render.yaml` as a placeholder
   ("Render suffixes service hostnames when a name is taken") — use the verified
   actual hostname; (c) query strings must pass through the rewrite (they do for
   `/api/v1/*` today, but confirm on the new rule).
6. **404 / expired contracts.** Serve the shell with generic tags (and ideally a real
   404 status) so dead links unfurl as "Hangar Bay" rather than a stale ship. Cheap;
   do it in Stage 1.
7. **Discord caches unfurls server-side** for a long time per URL. Price edits won't
   refresh an already-posted embed. Not a bug in any option — set expectations with
   the corp.

### Option 2

Already eliminated (§1). Additional notes for completeness: two URL shapes for one
resource leak into bookmarks and chat history; the human bounce is either a JS redirect
(blank flash, breaks no-JS) or meta-refresh (slow, ugly); and it quietly teaches users
that "real" links don't unfurl, which is the opposite of the goal.

### Option 3

1. **UA-variant responses across three cache layers** — the dominant correctness risk,
   detailed in §1. Safe posture is `no-store` everywhere, which deletes the option's
   performance rationale and still requires verifying Render's edge behavior on
   rewrite responses.
2. **Request loop.** The Worker must fetch the shell from the static site's
   `.onrender.com` hostname. Fetching `hangarbay.app/contracts/...` re-enters the
   `/contracts/*` rewrite → Worker → repeat. Trivial to avoid, catastrophic to miss,
   and easy to reintroduce in a refactor ("just use the canonical domain").
3. **UA allowlist rot.** Discordbot is stable, but the corp will eventually paste
   links into Slack, Telegram, forums. Each unfurler has its own UA; misses are
   *silent* (no preview, no error, nothing in logs you're watching). An allowlist is
   permanent gardening.
4. **Third deploy surface.** Wrangler config, CF API token in CI, Worker versioning,
   a separate dashboard for logs/errors. The 3am debugging session spans Render's
   edge, Cloudflare's cache, and the Worker console to answer "which layer mangled
   this response?"
5. **Unmeasured human-path latency** (§1) — the option's core benefit is unverified.
6. **Policy erosion.** The apex was kept DNS-only *deliberately* to avoid stacking
   Cloudflare on Render's Cloudflare. Option 3 re-stacks them for one path through a
   side door: Render-CF-edge → CF Worker → Render-CF-edge (shell fetch). It doesn't
   violate the letter of the earlier decision, but it recreates exactly the
   multi-layer cache/purge topology that decision existed to avoid.

Option 3 is the right architecture in a different context: a team already running
Workers, or a scale where human CDN latency on entry loads is sacred and measured to
survive the rewrite hop. Neither holds here.

---

## 3. Scrutiny of the reasoning in the brief

### (a) "Inlining data makes pages net faster despite the ~200 ms document penalty" — **arithmetically sound, with three caveats**

Warm-cache arithmetic: today content lands ~1265 ms (doc 48 → bootstrap gap to ~850 →
API to ~1265). With the document served from ohio (~250 ms median) carrying inlined
data: ~250 + ~720 bootstrap ≈ **~970-1000 ms, no API wait — ~265-300 ms net faster**.
Cold loads are dominated by JS download, but inlining still removes the serial
~400-600 ms data leg for a smaller relative win. Caveats:

1. **Both penalty and benefit apply only to entry loads.** Client-side navigations
   never request a document — unchanged either way. This *narrows* the claim but also
   targets it perfectly: the Discord-link visitor is an entry load.
2. **p90 is thinner.** Doc p90 through the rewrite is ~399 ms; the p90 win shrinks and
   could occasionally invert against today's p90 tail. Median case is solidly positive.
3. **The gain is conditional on hydration actually matching** the client's query keys
   and serialization. The failure mode is benign (client refetches; you keep the
   penalty, lose the win) but *silent* — Stage 2 needs an e2e assertion that no
   contract API request fires on a hard load of a contract page.

Also note the ~720 ms bootstrap gap is the single largest number on the warm path and
belongs on a perf backlog independent of this milestone — no routing option touches it.

### (b) "OG tags and inlining must ship together or the change is a net regression" — **overstated; reject the coupling**

OG-only (Stage 1) costs ~200 ms median (~330 ms p90) on entry-load documents for
`/contracts*` — against a ~1.3 s warm time-to-content and ~3.6 s cold FCP — and buys
the milestone's entire stated goal. Calling that "a net regression" prices the feature
at zero; it isn't a regression, it's a purchase, and a cheap one. Meanwhile "must ship
together" bundles HTML serving + shell caching + tag injection + dehydration +
frontend hydration + e2e verification into one atomic change — larger blast radius,
harder rollback, exactly what a small milestone shouldn't do. Ship Stage 1, measure,
ship Stage 2 within days. (The claim is also falsified in general by Option 3's
existence, which decouples the two entirely — but that's not why to reject it here.)

### (c) "Would Render's edge honor `s-maxage` on a rewrite destination?" — **unknown; weak positive evidence; 15-minute empirical answer**

The measured API responses show `cf-cache-status: BYPASS`, not `DYNAMIC`. In
Cloudflare vocabulary BYPASS means the *origin response's headers* (no-store /
no-cache / private / Set-Cookie) suppressed caching — i.e. the edge looked at the
headers and obeyed them — whereas DYNAMIC means "not cache-eligible, didn't even
consider it." BYPASS is therefore weak evidence the edge *would* cache a permissive
response. But Render's zone config is theirs, undocumented for this case, and could
change without notice. The test: add a trivial endpoint (or header on one) returning
`Cache-Control: public, s-maxage=60` plus a timestamp; hit it through the apex rewrite
several times; if the timestamp freezes and `cf-cache-status` flips to HIT, it's
honored. Two follow-ups regardless of outcome: **only Option 1 can safely exploit
this** (UA-invariant responses; Option 3 would be caching UA-variant HTML), and even
if honored, treat it as an optimization with a short TTL, never a correctness
dependency — it's Render's internal behavior, not a contract.

### One more framing error worth naming

The brief presents Option 1's shell-fetch coupling as novel risk. It's actually the
*same* staleness class the site already lives with (the `s-maxage=300` deep-link shell,
per §2.1) — Stage 1 with ETag revalidation makes the window smaller than today's, not
larger. Risk assessments should be measured against the existing baseline, not against
an imagined zero-staleness world.

---

## 4. Scope judgment

The staged Option 1 fits a small polish milestone **because it's severable**:

- **Stage 0** (static OG tags) is an hour and worth doing even if the milestone ended
  there — it's the floor for "links look intentional in Discord."
- **Stage 1** is the milestone's real body: one Render route rule + one FastAPI
  endpoint + shell cache with ETag revalidation + escaped tag injection + tests. A
  bounded lake — every edge case (404, expired contract, escaping, shell-fetch
  failure, revalidation) is enumerable and testable in pytest. Days, not weeks.
- **Stage 2** (inlining) is the piece that flirts with "architecture project." Keep it
  a fast-follow with its own PR and its own before/after measurement; if the trial
  date arrives first, ship without it — the trial needs unfurls, not 300 ms.
- **Stage 3** (search summaries) is deferrable indefinitely without foreclosing
  anything; the routing already carries it.

What does *not* fit the milestone: Option 3 in any form (new platform for a polish
milestone), and any attempt to fix the 720 ms bootstrap gap "while we're in there."

**Do not skip Stage 0 in the excitement over Stage 1.** It's the highest
value-per-hour line item in this document.

---

## Summary of verify-at-apply checklist (Stage 1)

1. Run the §3c edge-cache probe; set Stage 1 `Cache-Control` accordingly
   (`no-cache` if unhonored/uncertain; `public, s-maxage=30-60` if honored).
2. Confirm `source: /contracts/*` matches bare `/contracts`; add a second rule if not.
3. Use the API service's *actual* assigned hostname (render.yaml flags the placeholder).
4. Backend fetches the shell from the static site's `.onrender.com` hostname, never
   the apex.
5. Rewrite rules ordered before the `/*` SPA fallback (existing PROXY-1 pattern).
6. `html.escape(..., quote=True)` on all injected tag content; integer-validate type
   IDs in image URLs.
7. pytest: tags present and escaped for a real contract; generic tags on unknown ID;
   shell served from stale cache when the static origin errors.
8. After Stage 2 only: e2e asserting zero contract-API requests on a hard load of a
   hydrated contract page.
