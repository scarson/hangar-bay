# M5 Trust & Shareability — Design

ABOUTME: Design for the first M5 milestone — make Hangar Bay's data honest about itself and make its links worth pasting into Discord, ahead of a private trial with a friendly EVE corporation.
ABOUTME: Chosen direction from `2026-07-26-m5-direction-options.md`; evidence in `docs/audits/m5-recon/`; awaiting Sam's approval before an implementation plan is written.

**Status:** DRAFT — awaiting Sam's review. Written 2026-07-26 while Sam was away, per his instruction to drive the brainstorm as far as reasonable. Design sections were not individually approved, which the normal brainstorming flow would require; treat the whole document as one approval gate.

**Goal:** A trial user from a Discord-native corporation opens the site, believes the numbers, finds live contracts rather than dead ones, and pastes links that unfurl into something worth clicking.

**Non-goal:** Market appraisal, multi-region coverage, and alert delivery channels are separate directions (see the options record). Nothing here tries to differentiate Hangar Bay from existing marketplace sites — that is the appraisal direction's job.

---

## What we found

Two production measurements drove this design. Full method and numbers in `docs/audits/m5-recon/`.

**1. ~12% of served contracts have already expired** (`expired-contracts-finding.md`). Nothing prunes contracts, and the list query never filters on expiry — `date_expired` appears in `contract_service.py` only as a *sortable* field. Measured live: ~6,200 of 51,365 contracts already expired, the oldest five days stale. The UI does label rows `Expired` (via `format.ts`'s `timeRemaining()`), so this is a relevance problem rather than a deceptive one — but `ContractsPage.tsx`'s `DEFAULT_DIRECTION` maps `date_expired: 'asc'`, so **clicking "Time left" — the obvious "what's expiring soonest?" move — returns a page of nothing but dead contracts** (verified: 20 of 20).

**2. Link previews are impossible today, and the latency objection to fixing them was aimed at the wrong term** (`link-preview-latency-spike.md`). `index.html` carries no `og:*` tags at all, and Render static sites cannot run server code or match routes on User-Agent, so a crawler/human split cannot happen at Render's edge. Routing a path to the backend costs ~161 ms — but document delivery is ~48 ms of a ~1265 ms warm time-to-content. The dominant cost is ~720 ms of client bootstrap before the first data request, which no routing choice affects.

A third item was investigated and **dismissed**: `search` and ship filtering work correctly. `is_ship_contract=true` returns 622 contracts, item `category: 'ship'` is populated, and `search` filters across `Contract.title` OR `ContractItem.type_name` via the items join. An apparent "`ship_name` is always null" finding was an artifact of probing for a response field that does not exist — the frontend derives the hull label from ship-category items by design.

---

## Workstream A — Link previews

### Routing decision

**Chosen: the backend owns `/contracts*`.** A Render rewrite sends `/contracts*` to FastAPI, which returns the SPA shell with per-URL `og:*` tags injected. Because `/` redirects to `/contracts` (`routes/index.tsx`), this single prefix covers both contract detail and filtered search with no extra blast radius.

**Route ordering is load-bearing.** `render.yaml`'s existing comment on the `routes:` block already warns `ORDER MATTERS: prefix-strip rule before SPA fallback (PROXY-1)`. The new `/contracts*` rule must sit **after** `/api/v1/*` and **before** the `/*` SPA fallback. Placed after the fallback it never matches; placed before `/api/v1/*` it is harmless today but invites a future `/contracts`-prefixed API path to be swallowed. The backend serves these routes at bare paths, per PROXY-1 — the handler must not assume an `/api/v1` prefix.

Rejected alternatives:

- **A dedicated share-link prefix** (`/s/c/:id` produced by a Share button) is disqualified by observed behavior, not by implementation quality: the trial corporation copies URLs from the address bar, so most shared links would carry no preview.
- **A Cloudflare-proxied subdomain running a User-Agent-splitting Worker** was seriously considered and rejected on three grounds. It serves different HTML per User-Agent, which is a `Vary: User-Agent` cache hazard forcing `no-store` and deleting its own performance rationale; its central benefit (humans keep CDN latency) is unverified, since the measured ~161 ms is Render proxy overhead plus the ohio leg in unknown proportion and a rewrite to a Cloudflare destination has never been measured; and it re-creates the stacked-CDN topology that the DNS-only apex decision (M4 Deviation D-12) exists to avoid. It also carries a loop hazard: a Worker fetching the apex for the shell re-enters the very rewrite that invoked it.

The decisive argument for the backend is that it adds **no new platform**. The handler lives in the existing FastAPI service, is tested with pytest under the repo's TDD discipline, ships through existing CD, and is observed through existing Grafana. It is also cache-correct by construction — the same HTML goes to every User-Agent.

**The shell-staleness concern that originally argued against this approach does not survive inspection.** `render.yaml`'s `Cache-Control: no-cache` rule is scoped to the literal path `/index.html` and does not match `/contracts/123`, so deep-link shells already ride the default `s-maxage=300` — verified live (`cf-cache-status: HIT`, `age: 243`). A stale shell window already exists today. Fetching the shell with `If-None-Match` revalidation makes that window *smaller* than the status quo.

### Staging

Each stage ships independently and is separately valuable.

**Stage 0 — site-wide static tags.** Add `og:title`, `og:description`, `og:image`, `og:site_name`, `twitter:card` to `index.html`. No routing changes, no backend work. Today every Hangar Bay link unfurls as nothing; after this, every link unfurls as *something*. This is the highest value-per-hour item in the milestone and should ship first, on its own.

**Stage 1 — per-URL tags for contract pages.** The rewrite plus a FastAPI handler that fetches the built shell (ETag-revalidated), injects per-URL tags, and returns it.

**Stage 2 — data inlining.** The handler additionally inlines the contract payload (dehydrated TanStack Query state) so the client skips its own API call. Measured as a fast-follow; skippable if the trial date arrives first.

**Stage 3 — filtered-search summaries.** Deferrable indefinitely.

Stage 1 costs entry loads ~200 ms of document latency and Stage 2 repays roughly 414 ms. Shipping Stage 1 alone is a **purchase, not a regression** — ~200 ms against a 1265 ms baseline — and coupling the stages would enlarge the blast radius for no safety gain. The caveat worth holding: that cost lands precisely on the Discord-link visitor this milestone exists to serve, so Stage 2 should not drift indefinitely.

### Preview content

**Contract detail.** Title is the hull name with price — `Armageddon Navy Issue — 450,000,000 ISK`. Description carries location, time remaining, contract type, and item count. Image is the EVE render CDN, verified live: `https://images.evetech.net/types/{type_id}/render?size=512` returns 200 `image/jpeg` (~25–43 KB) for real hulls (checked against Armageddon Navy Issue, Nightmare, Ark). The hull's `type_id` comes from the contract's included item with `category == 'ship'`, matching how the frontend already derives its label.

Fallback chain, because `render` is **not** available for every type — verified 400 for a non-ship type: `render` → `icon` (200 `image/png`, confirmed for the same type that 400'd) → the site-wide Stage 0 image.

**Expired contracts.** The title must lead with expiry — `EXPIRED — Armageddon Navy Issue`. This is load-bearing rather than cosmetic: a Discord link routinely gets clicked hours after posting, so previews will frequently describe contracts that have since died. A preview that presents a dead contract as available is the exact trust failure this milestone exists to prevent.

**Filtered search (Stage 3).** A summary of filters and result count — `14 battleships under 200M ISK in The Forge`. Region and type IDs resolve to names; the count reuses the existing filter path.

**Escaping.** Contract titles are player-authored free text (a real one in production: `1976.48GJ, est. 473m`). Every interpolated value is HTML-escaped before injection. This is a correctness *and* injection concern and gets an explicit test with hostile input.

**Failure behavior.** A lookup failure or unknown contract returns the Stage 0 generic tags with a 200, never an error page and never a partial tag set. Crawlers get something valid; humans get the SPA, which renders its existing not-found state.

---

## Workstream B — Expiry honesty

**Exclude expired contracts from list results by default.** Add a `Contract.date_expired > now()` predicate to the list query. This corrects `total` as a side effect, so the displayed count stops overstating what is available.

**Keep serving expired contracts on the detail page, clearly marked.** Do not 404 them. Shared links outlive contracts, and a 404 for a link posted this morning reads as a broken site rather than an expired deal. The page states expiry prominently; the preview says `EXPIRED`.

**Deliberately not doing:** deleting expired rows. Filtering fixes correctness without losing history, and deletion interacts with saved searches and notifications that reference those contracts. Unbounded table growth is real (51k rows in roughly a week, on `basic-256mb`) but is a retention-policy decision of its own — there is precedent in `NOTIFICATION_RETENTION_DAYS`.

**Open question for Sam:** should an "include expired" toggle exist? There is precedent — the ships-only default has an explicit toggle (F002 Criterion 1.1). The YAGNI answer is no toggle until someone asks. Recommendation: ship without it, and let the trial decide.

---

## Workstream C — Data freshness surface

This is the user-facing staleness indicator parked in the M4 design, and the Jul 23–26 incident is its justification: production served 3.6-day-old data with no signal any user could see, while `/ready` correctly reported `data_stale`.

**Mechanism:** add `data_as_of` (ISO 8601 timestamp of the last successful ingest) to the contracts list response envelope, which is currently `{total, page, size, items}`. The value comes from the same Valkey freshness record `/ready` reads (`INGEST_LAST_RUN_KEY`), cached in-process with a **30-second TTL** so the hot path does not take a cache round-trip per request. Thirty seconds is far below the hourly ingest cadence, so the displayed age is never misleading, while a burst of list requests costs at most one Valkey read. If the freshness record is absent — the key is evictable, and `allkeys-lru` may drop it (DEPLOY-3) — `data_as_of` is `null` and the UI shows no freshness line rather than inventing one.

Putting freshness *in the data envelope* rather than behind a separate endpoint means the timestamp always travels with the numbers it describes, and costs no extra request.

**Display:** extend the existing count line in `Pagination.tsx` (today `Page 1 of 514 · 51,365 contracts`) with `· updated 12 min ago`. When the data is stale — reusing `/ready`'s existing threshold of more than twice `AGGREGATION_SCHEDULER_INTERVAL_SECONDS` — the indicator escalates to an explicit warning naming the age.

**Accessibility:** the stale state must not be signalled by color alone (PRODUCT.md, and `accessibility-spec.md`'s color-blind-safe rule). The escalated state changes the *text*, not just the hue.

---

## Workstream D — Retire the `status` field

`Contract.status` is always the literal `"unknown"` — ESI's public contracts route returns no status, and `background_aggregation.py:108` defaults it. Verified across a 100-contract production sample. The frontend never reads it.

Remove it from the API response and regenerate the typed client (`pdm run export-openapi` → `npm run generate:api`). The DB column and the `ix_contracts_type_status` index are left alone; dropping them is a migration with no benefit at this size, and the column becomes meaningful if character/corp contracts are ever ingested.

---

## First implementation task: settle the edge-cache question

**Can backend-rendered HTML be edge-cached by Render's CDN?** If a response carrying `s-maxage=60` is honored on a rewrite destination, repeat views of a contract return to ~50 ms and crawlers are served from cache — which erases the Stage 1 latency cost entirely. If not, Stage 1 still ships; nothing blocks.

Narrowed, but not settled, without deploying: **the backend sets no `Cache-Control` header anywhere** (grep across `fastapi_app/` finds none), yet every response through the rewrite carries `cache-control: max-age=0` — `/ready`, `/contracts/`, `/openapi.json`, and `/docs` alike, all `cf-cache-status: BYPASS`. That header therefore originates at the edge, not the application.

Which means today's `BYPASS` is uninformative: the origin sends nothing to honor, so the edge defaulting to `max-age=0` is exactly what one would expect either way. The open question is specifically **whether an explicit origin `s-maxage` is passed through or overwritten** by that edge default. Only a deployed response carrying its own cache header can distinguish those.

The probe: an endpoint returning `Cache-Control: public, s-maxage=60` plus a request timestamp in the body; request it repeatedly and watch whether `cf-cache-status` ever reports `HIT` and whether the timestamp freezes. Roughly fifteen minutes.

This cannot be answered from outside and needs a deployed response header plus repeated requests watching `cf-cache-status` — roughly fifteen minutes. It goes **first**, because a positive result simplifies everything after it.

---

## Testing

Per the repo's TDD mandate, every item below is written test-first, and characterization tests are mutation-verified (TEST-12) — a preview test that passes with the tag-injection deleted is not evidence.

- **Expiry filtering:** a fixture set spanning the expiry boundary asserting expired contracts are absent from list results and that `total` reflects the filtered count. Must cross a page boundary (TEST-4).
- **Detail page serves expired:** an expired contract returns 200 with its expiry state, not 404.
- **Tag injection:** HTTP-level tests asserting real `og:*` tags in the response body for a live contract, an expired contract, and an unknown ID (generic fallback, 200).
- **Escaping:** a contract title containing `<`, `>`, `"`, and `&` must not break out of the meta tag. Hostile input, asserted explicitly.
- **Image fallback:** a type with no render falls back to icon, then to the site-wide image.
- **Freshness:** `data_as_of` present and correct; the stale threshold flips at more than twice the scheduler interval; the stale state is distinguishable without color.
- **Frontend:** stub at the fetch seam (TEST-5); every fixture-lane spec intercepts `GET /me` (TEST-9).
- **Not mocked:** the shell fetch is exercised against a real static response in at least one test, since a mocked shell would test the mock (the repo's rule against testing mocked behavior).

---

## Risks

**Deploy skew.** Between a frontend deploy and the backend's next shell revalidation, the injected shell may reference asset URLs that no longer exist, producing a broken page. Mitigated by per-request `If-None-Match` revalidation, which makes the window smaller than today's `s-maxage=300` baseline. Worth a pitfalls entry once the behavior is observed in practice.

**Availability coupling.** With `/contracts*` routed to the backend, a backend outage takes down contract *documents*, where today the CDN would serve a shell that then fails to fetch data. The degradation is from "shell plus error state" to "no page." Mitigated for lookup failures by falling back to generic tags; a hard process-down is accepted for a trial-scale product, and noted here so the choice is deliberate.

**Scope creep.** This milestone is meant to be small. Stage 3 and the retention policy are explicitly deferred, and the appraisal and coverage directions are out of scope entirely.

---

## Reasoning worth preserving

**The original latency objection was aimed at the wrong term.** The instinct — "routing pages through the backend costs 200 ms, and this product's principles say fast is a feature" — was correct in isolation and wrong in proportion. Measuring first showed document delivery is ~48 ms of ~1265 ms, and that ~720 ms of client bootstrap dwarfs everything the routing decision touches. The spike changed the decision.

**"OG tags and data inlining must ship together" was overstated and is rejected.** The claim was that Stage 1 alone ships a regression. An independent review argued that ~200 ms against a 1265 ms baseline is a purchase rather than a regression, and that coupling the stages enlarges blast radius for no safety gain. That is correct and is adopted, with the caveat recorded above that the cost lands on the target user.

**The Cloudflare Worker option was more attractive than it deserved.** It appeared to give a clean crawler/human split at low cost. The `Vary: User-Agent` cache hazard, the unmeasured assumption that a Cloudflare-destination rewrite is cheaper than a Render-origin one, and the apex-refetch loop hazard only surfaced under adversarial review. The lesson generalizes: an option whose benefit rests on an unmeasured latency assumption should not beat one whose benefit rests on a measured fact.

**The biggest win was the cheapest and was nearly missed.** Static site-wide OG tags cost about an hour and change every link on the site from unfurling as nothing to unfurling as something. It surfaced only when the routing analysis was reviewed by someone not invested in the routing question. Staging exists in this design because of it.

**Still uncertain:** whether the trial corporation shares contract links or search links (assumed contracts, cheaply revisable); whether Render's edge caches rewrite responses (first task); and whether an "include expired" toggle is wanted (deliberately left to the trial).
