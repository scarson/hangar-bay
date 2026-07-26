# Adversarial Review — M5 Trust & Shareability Design

ABOUTME: Adversarial design review of `docs/superpowers/specs/2026-07-26-m5-trust-shareability-design.md`, checked against the live codebase in this worktree.
ABOUTME: Findings ranked BLOCKER / MAJOR / MINOR; every code claim was verified against actual files, not taken on faith.

Reviewed 2026-07-26. Files checked: `contract_service.py`, `api/contracts.py`, `api/ops.py`, `schemas/contracts.py`, `schemas/common.py`, `models/contracts.py`, `services/watchlist_matcher.py`, `services/saved_search_service.py`, `services/background_aggregation.py`, `render.yaml`, `routes/index.tsx`, `index.html`, `ContractsPage.tsx`, `Pagination.tsx`, `format.ts`, `filters.ts`, `e2e/fixtures/contracts.ts`, both pitfalls docs, F002.

---

## BLOCKER

### B-1. The `/contracts*` rewrite collides with the existing JSON API at the backend's bare paths — the spec never mentions it

The backend already mounts a JSON router at bare `/contracts` (`api/contracts.py`: `APIRouter(prefix="/contracts")`, with `GET /contracts/` = list and `GET /contracts/{contract_id}` = detail). The existing rewrite `source: /api/v1/*` → `destination: https://hangar-bay-api.onrender.com/*` strips the prefix, so the SPA's API call `GET /api/v1/contracts/123` arrives at the backend as `GET /contracts/123`.

The spec's proposed rewrite sends apex `GET /contracts/123` (a document navigation) to the backend, and its own sentence — "The backend serves these routes at bare paths, per PROXY-1 — the handler must not assume an `/api/v1` prefix" — mandates that the HTML handler live at `/contracts/{id}`. **That is the exact path the JSON detail endpoint already occupies.** Both request classes arrive at one origin, one path, indistinguishable except by headers. Concrete failures, pick one:

- If the JSON route wins route matching, Discord's crawler receives JSON. Stage 1 is dead on arrival.
- If the HTML route wins, every SPA detail-page API call receives an HTML document and the detail page breaks site-wide.
- Bonus: apex `/contracts/` (trailing slash) maps to backend `/contracts/`, the JSON **list** endpoint — a user reloading a trailing-slash URL gets a raw JSON dump as their page. FastAPI's `redirect_slashes` makes bare `/contracts` reachable the same way.

The fix is not hard — mount the document handler under a distinct backend prefix (e.g. `/pages/contracts/*`) and write the rewrite destination to target it — but the spec must specify it, because it contradicts the spec's own "bare paths per PROXY-1" instruction as written, and PROXY-1's "keep paths verbatim" framing needs a deliberate, documented carve-out for document routes. Content-negotiating on `Accept` inside one route is the wrong answer (FastAPI doesn't route on headers; crawler Accept headers are unreliable). This is the single largest omission in the design and it invalidates the Stage 1 section as specified.

### B-2. Unverified Render glob: `/contracts*` (no slash) as a rewrite source

Every existing rule uses segment-style globs (`/api/v1/*`, `/*`). Whether Render accepts a mid-segment suffix glob `/contracts*`, and whether it matches the bare path `/contracts`, `/contracts/123`, and (undesirably) `/contractsanything`, is asserted, not verified. The spike verified Render's docs for the *absence* of header matching but not this. If `/contracts*` is invalid or matches only literally, the routing design silently doesn't cover the list page or covers wrong paths. Cheap to settle; must be settled before the spec's routing section can be trusted. (This interacts with M-2: `/contracts/*` vs `/contracts` + `/contracts/*` is also the scoping lever for excluding the list page.)

---

## MAJOR

### M-1. Availability coupling is understated: recreate deploys make it a *routine* outage, not a tail risk

`render.yaml`'s disk pin exists "ONLY to pin max-1-instance + **recreate deploys**". Recreate strategy means every backend deploy has a stop-start window. Today that window costs nothing on the document path — the CDN keeps serving the shell. After Stage 1, **every backend deploy takes down document serving for `/contracts*`** — which, given `/` is just a client-side redirect to `/contracts`, is effectively every reload, bookmark, and shared link on the site. The risk section frames coupling as "a hard process-down is accepted" — an exceptional event — when the design actually converts each merge-to-main into a small scheduled document outage. Either accept that explicitly (with the deploy frequency named), serve a static fallback from the edge on 5xx (Render rewrites don't do failover — so probably not available), or scope the rewrite smaller (M-2).

### M-2. Stage 1 routes the *list page* — the effective homepage — through the backend for zero Stage-1 benefit

`/contracts*` covers bare `/contracts`, i.e. the main list view every user lands on and reloads. Stage 1 only injects per-contract tags; list-page tags are Stage 3, "deferrable indefinitely." So from day one the highest-traffic document pays ~200 ms and the new availability coupling (M-1) while receiving nothing until a stage the spec may never ship. The spec sells the wide prefix as "no extra blast radius"; it is precisely extra blast radius. The alternative — rewrite only `/contracts/*` (detail pages), leave bare `/contracts` on the static fallback with Stage 0 tags until Stage 3 exists — is never discussed. It should be, and it is probably the right call for a trial-scale milestone.

### M-3. Sold/delisted contracts are the other half of the trust hole, and the spec doesn't acknowledge the boundary

Contracts leave ESI's public list when accepted (sold), not only when expired. Nothing prunes or flags them locally — no `last_seen` tracking exists in the model, and the public route never populates `date_completed`. A ship sold on day 1 of a 4-week contract remains in list results, apparently live, for 27 more days. The expiry predicate removes **none** of these. The codebase already knows about this class: `watchlist_matcher.py` filters `Contract.date_expired > func.now()` **and** `Contract.date_completed.is_(None)` (lines 147–154). The measured ~12% is therefore a *lower bound* on dead rows, and the milestone's stated goal ("finds live contracts rather than dead ones") is only partially achievable by Workstream B. The spec should either name this as an accepted limitation with a rough size estimate, or add ingest-side last-seen tracking to scope — but silently equating "not expired" with "available" repeats the exact trust failure the milestone exists to fix, one layer down.

### M-4. The evidence for Workstream B was measured against a view users don't see by default

The frontend defaults to ships-only (`filters.ts:77` — `ships_only: raw.ships_only !== false`, mapped to `is_ship_contract=true`; F002 Criterion 1.1). The default trial-user view is ~622 ship contracts, not 51,365. Both headline measurements — "~12% expired," "20 of 20 dead on the Time-left sort" — were taken via the raw API without `is_ship_contract=true` (the finding's method section confirms it). The expired share *within the ships-only view* is unmeasured; with ~75 expected expired ship contracts against a 50-row page the 20/20 result plausibly still holds, but it is an inference, not the verified fact the spec presents. Also Workstream C's "today `Page 1 of 514 · 51,365 contracts`" describes the non-default all-contracts view. Re-measure scoped to the default view, or restate the claims accurately. The recommendation almost certainly survives; the evidence as quoted doesn't.

### M-5. Freshness couples the core list endpoint to Valkey with unspecified failure behavior

The contracts list endpoint currently never touches Valkey. Workstream C adds a per-request (30s-amortized) read of `INGEST_LAST_RUN_KEY`. The spec specifies behavior for *key absent* but not for *Valkey unreachable* or *client never initialized* (`app.state.redis` is `None` when startup init failed — `ops.py`'s `_probe_cache` handles exactly this with a reinit attempt and a catch-all). If the implementer naively awaits a cache call, a Valkey outage 500s the product's core endpoint — an availability *regression* delivered by the trust milestone. Must specify: any cache failure → `data_as_of: null`, never an error; and whether the failure result is itself cached for the TTL. Additionally, the record is JSON (`{last_success_at, outcome, ...}`), not a bare timestamp — `data_as_of` is `last_success_at`, parsed with the same corrupt-record tolerance `_freshness_fields` shows. Finally, an in-process TTL cache is module/global state — a known test-isolation defect class in this repo's plan reviews (global-state fixture leaks); the spec should mandate a reset seam.

### M-6. Stale-threshold computation location is unspecified, and the frontend can't compute it

"Reusing `/ready`'s existing threshold of more than twice `AGGREGATION_SCHEDULER_INTERVAL_SECONDS`" — the frontend has no access to that setting. Two reasonable implementations diverge: (a) server adds `data_stale: bool` (or the threshold) to the envelope; (b) frontend hardcodes 7200s. (b) drifts silently the day the interval changes. The spec must pick (a) and say so — it also keeps the staleness semantics in one place (`ops.py` already owns them).

### M-7. The og:image fallback chain implies a per-request probe of an external CDN, unaddressed

`render → icon → site-wide` sounds declarative, but a meta tag holds one URL; knowing that `render` 400s for a type requires an HTTP probe of `images.evetech.net`. Where does that happen? A naive implementation adds a serial outbound HTTP call to every document request — external-service latency and failure coupling on the page hot path, exactly the kind of cost this spec elsewhere measures to the millisecond. Options the spec must choose among: always emit `render` for `category == 'ship'` items (ships have renders; verified only by three samples), a cached/async probe, or a static category rule with `icon` for non-ships. Two engineers guess differently and one of the guesses is a hot-path regression.

### M-8. Shell-fetch mechanics are underspecified, including a loop hazard the spec itself weaponized against the rejected alternative

Stage 1's handler "fetches the built shell (ETag-revalidated)". From where? Apex (`hangarbay.app/index.html`) re-enters Cloudflare and works only because `/index.html` doesn't match the `/contracts*` rewrite — the same class of self-reference loop the spec cites as a strike against the Cloudflare Worker ("a Worker fetching the apex for the shell re-enters the very rewrite that invoked it"). The constraint (the shell-fetch path must never match the handler's own rewrite source) is real for the chosen design too and is stated nowhere. Also unspecified: fetching the static site's `onrender.com` hostname directly instead (skips the edge; different caching behavior); behavior when the shell fetch fails and no cached copy exists (cold start after backend deploy + static site incident → what response?); timeout budget for the revalidation call.

### M-9. Testing gaps — what passes while the behavior is broken

The listed tests are decent for Workstream B but miss the failure modes above:

- **Nothing asserts the JSON API survives Stage 1.** Given B-1, the highest-value test in the milestone is: after the document routes exist, `GET /contracts/123` (bare, as the proxy delivers API traffic) still returns JSON with the contract schema, and the document route returns HTML. Absent this, a route-ordering change ships a site-wide breakage that every listed test passes through.
- **No Valkey-down test for the list endpoint** (M-5): list returns 200 with `data_as_of: null` when the cache client raises / is `None`.
- **No test for the placement invariant of the expiry predicate.** Concretely: the predicate belongs in `_apply_contract_filters` (`contract_service.py:50`), which flows into both `_count_distinct_contracts` and both fetch paths. A mutation that moves it into only `_fetch_page_simple` leaves `total` overcounting and pagination walking phantom pages — the listed "total reflects the filtered count" test catches this **only if** the fixture's expired rows are numerous enough to change the page count, and only if it's run against *both* the joined and simple fetch paths (an item-filter in the fixture query forces the joined path; no item-filter forces the simple one). The spec's test list doesn't require exercising both paths; SQLA-1 history says it must.
- **No boundary-semantics test**: `date_expired == now()` exactly — `>` vs `>=` (and `func.now()` per-statement timing) should be pinned, trivially.
- **No cache-header test** for whatever `Cache-Control` the document handler emits — load-bearing given the edge-cache spike is the milestone's first task.
- The escaping test should include `'` (attribute context) alongside `<>"&`.

Existing strengths acknowledged: TEST-4 page-boundary crossing is cited, TEST-12 mutation-verification is mandated, the real-shell no-mock rule is right.

---

## MINOR

- **m-1. Envelope is shared.** `PaginatedResponse` is generic (`schemas/common.py`) and used by notifications (`api/notifications.py:27`). Adding `data_as_of` to it pollutes notifications with an ingest-freshness field. Needs a contracts-specific response model (subclass or new model); spec doesn't say. Also: Workstreams B (no schema change), C, *and* D all touch the OpenAPI surface, but the regen chain (`pdm run export-openapi` → `npm run generate:api`) is mentioned only under D.
- **m-2. No index on `date_expired`, and the spec is silent.** `models/contracts.py` indexes price/date_issued/collateral/volume — not `date_expired`, despite it now being both a filter on every list query and an existing sort column. Fine at 51k rows; the spec's own admission of unbounded growth makes it worth a sentence either way, and any index is an Alembic migration in prod (`DB_RECREATE_ON_STARTUP=false`, `preDeployCommand` runs alembic) — a step class the spec never mentions.
- **m-3. `now()` is ambiguous.** DB clock (`func.now()`, the existing `watchlist_matcher.py:151` pattern) vs Python `datetime.now(timezone.utc)`. Column is `DateTime(timezone=True)` so `func.now()` compares cleanly; the spec should name `func.now()` and cite the matcher as the in-repo precedent — which, oddly, the spec never mentions at all despite it being proof the predicate is already load-bearing elsewhere (including the notification-prune "no-resurrection" guard at line 199, which is *consistent* with, not endangered by, Workstream B).
- **m-4. Workstream D ripples into e2e fixtures.** `e2e/fixtures/contracts.ts` declares `status: string` (line 35) and sets `'unknown'` (line 100). "The frontend never reads it" is true of app code (verified: all `.status` hits are HTTP statuses) but the fixture type breaks on regen. Small, but the spec's task list for D is incomplete.
- **m-5. Discord caches embeds at post time; the EXPIRED prefix only covers links posted after death.** A link posted while live keeps its "available" embed after the contract dies — the crawl happened at post time. The spec's rationale ("previews will frequently describe contracts that have since died") claims more coverage than server-side tags can deliver. The controllable mitigation: put the *absolute* expiry timestamp in the description (not, or in addition to, relative "time remaining," which freezes misleadingly in a cached embed). The detail page remains the honest layer for the click-later case — the spec has that part right.
- **m-6. Stage 0's og:image must be a stable-pathed asset.** Vite hashes `/assets/*` and old hashes vanish on the next deploy (`immutable` header notwithstanding — the file is gone), breaking the image in every previously posted embed. The image belongs in `public/` under a stable name, and `og:image` must be an absolute URL. One sentence in the spec prevents a silent regression that only manifests in week-old Discord messages.
- **m-7. Client-clock skew on "updated 12 min ago"** can render negative ages. Clamp at zero. `format.ts`'s injectable-`now` pattern is the template.
- **m-8. "Roughly fifteen minutes" for the edge-cache spike** ignores that the deploy rides CD to production (merge → deploy → observe). Closer to an hour of wall clock. Harmless but sets the wrong expectation for "it goes first."
- **m-9. Unverifiable production observations** (`cf-cache-status: HIT/BYPASS`, `age: 243`, `max-age=0`, the 400-for-non-ship image probe, 622 ship contracts) — accepted as spike-attested; nothing in the repo contradicts them. All *repo* claims in the spec checked out: `DEFAULT_DIRECTION` maps `date_expired: 'asc'` (`ContractsPage.tsx:15`), `timeRemaining` returns `'Expired'` (`format.ts:28`), `index.html` has zero `og:*` tags, `render.yaml`'s ORDER MATTERS comment and literal-`/index.html` no-cache scoping are as described, `status` defaults via `c.get("status", "unknown")` in `background_aggregation.py`, `INGEST_LAST_RUN_KEY`/2×-interval threshold in `ops.py:97`, and every cited pitfall tag (SQLA-1, TEST-4/5/9/12, DEPLOY-3) exists as characterized. The `/` → `/contracts` redirect exists but is **client-side** (`routes/index.tsx` `beforeLoad`), a nuance the routing section elides — a visit to `/` itself never fetches a `/contracts` document, but every subsequent reload does.

---

## Scope realism

The milestone is *mostly* honest about being small, and the staging is its best feature. Calibrated sizes:

- **Genuinely small, pre-trial, ship them:** Stage 0 (hours), Workstream B (a predicate + tests — with M-3 named as a limitation), Workstream C (a day, once M-5/M-6 are specified), Workstream D (small; include m-4).
- **Secretly the big one:** Stage 1. Once B-1 (new routing namespace + PROXY-1 carve-out), M-7 (image strategy), M-8 (shell-fetch subsystem), and M-1 (deploy-window behavior) are accounted for, this is a multi-day chunk with the milestone's only real architectural risk. It should be its own gated unit of work, after the trial-critical items above, and scoped to `/contracts/*` detail pages only (M-2).
- **Cut from M5 outright:** Stage 2. TanStack Query dehydration into a non-SSR Vite SPA is a real subsystem (hydration boundary, query-key serialization matching the client's exact key shape, staleness semantics vs. any edge caching). "Fast-follow, skippable" is the right instinct — make it explicit: not in this milestone.
- Stage 3: already correctly deferred.

## Where the design is sound

The Cloudflare Worker rejection is well-argued and correct. No-404-for-expired-detail is the right call and correctly identified as load-bearing for previews. Keeping the `status` DB column while dropping the API field is right. Escaping treated as an injection concern with a hostile-input test is right. Fallback-to-generic-tags-with-200 on lookup failure is right. The edge-cache question genuinely belongs first. The "reasoning worth preserving" section is a model of the repo's thinking-documentation discipline.

## Top three actions before this spec is implementable

1. Resolve B-1: specify the backend document-route prefix, the exact rewrite `source`/`destination` pair, and the PROXY-1 carve-out. Add the JSON-survives regression test to the test list.
2. Verify B-2 (Render glob semantics) alongside the edge-cache spike — same deployed experiment, and decide M-2 (detail-only rewrite) with the result.
3. Specify M-5/M-6/M-7 (freshness failure mode + threshold location + image strategy) so two engineers implement the same design.
