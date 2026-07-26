# M5 Trust & Shareability — Design

ABOUTME: Design for the first M5 milestone — make Hangar Bay's data honest about itself and make its links worth pasting into Discord, ahead of a private trial with a friendly EVE corporation.
ABOUTME: Chosen direction from `2026-07-26-m5-direction-options.md`; evidence in `docs/audits/m5-recon/`; awaiting Sam's approval before an implementation plan is written.

**Status:** DRAFT — awaiting Sam's review. Written 2026-07-26 while Sam was away, per his instruction to drive the brainstorm as far as reasonable. Design sections were not individually approved, which the normal brainstorming flow requires; treat the whole document as one approval gate.

**Revision note:** this is the second draft. A blind adversarial review (`docs/audits/m5-recon/spec-review-fable.md`) found a blocker that would have broken the JSON API in production, and a substantive gap — sold contracts — that the first draft missed entirely. Both are fixed here, and the headline recommendation changed as a result.

**Goal:** A trial user from a Discord-native corporation opens the site, believes the numbers, finds live contracts rather than dead ones, and pastes links that unfurl into something worth clicking.

**Non-goal:** Market appraisal, multi-region coverage, and alert delivery channels are separate directions (see the options record).

---

## Recommendation up front

**Ship the small, high-certainty things now; give per-URL link previews their own design pass.**

In M5: site-wide static OG tags, dead-contract filtering (expired *and* sold), the freshness surface, and retiring the `status` field. All are small, independently valuable, and carry no architectural risk.

**Defer per-URL previews** to a follow-on with its own design. This defers the headline Discord feature, which is a real cost and Sam may well overrule it — but the routing work grew a route collision, a deploy-outage regression, and a shell-fetch dependency once reviewed, and the milestone's whole purpose was to be small and trial-ready. Static tags already move every link from "unfurls as nothing" to "unfurls as something," which captures most of the trial value at roughly an hour of work.

---

## What we found

Method and numbers in `docs/audits/m5-recon/`.

**1. Dead contracts are shown as live, in two distinct ways.**

*Expired* (`expired-contracts-finding.md`): nothing prunes contracts and the list query never filters on expiry — `date_expired` appears in `contract_service.py` only as a *sortable* field.

The first draft measured this across all 51,365 contracts (~6,200 expired, ~12%). **That was the wrong population.** The frontend defaults to ships-only (`filters.ts`), which is 622 contracts. Re-measured in the view users actually get: **~53 of 622 expired, ~8.5%**. The headline is sharper, not weaker — the list page size is 50, so **sorting by "Time left" ascending fills the entire first page with dead contracts**, and `ContractsPage.tsx`'s `DEFAULT_DIRECTION` maps `date_expired: 'asc'`, making that the one-click default for anyone asking "what's expiring soonest?"

*Sold or delisted* — **the larger half, and it does not show up in any expiry measurement.** A contract that is accepted disappears from ESI's public list, but nothing tracks absence: `Contract` has **no `last_seen_at` or `updated_at` column** (verified against `models/contracts.py`), the public route never populates `date_completed`, and ingestion never deletes. A ship sold five minutes after ingestion keeps showing as available for the remainder of its contract duration — up to two weeks. An expiry filter removes none of these.

The watchlist matcher already gets this right for its own query, filtering both `date_expired > now()` and `date_completed IS NULL` (`watchlist_matcher.py`) — precedent worth citing, though `date_completed` alone cannot catch sold public contracts either.

**2. Link previews are impossible today, and the latency objection was aimed at the wrong term — though by a narrower margin than first reported** (`link-preview-latency-spike.md`). `index.html` carries no `og:*` tags, and Render static sites cannot run server code or match routes on User-Agent.

Routing a path to the backend costs ~161 ms. **Corrected 2026-07-26 after re-measuring in a clean browser tab:** warm time-to-content is **~450–500 ms** — document ~35–50 ms, API call ~270 ms — and the "client bootstrap gap" this design twice leaned on **does not exist**. Measured at 2 ms, 10 ms and −12 ms in a fresh tab; the earlier 253–840 ms figures were contention in a long-lived measuring tab, not work the app does.

That removes the argument that document delivery is negligible: the ~200 ms routing penalty is **~40%+ of the real baseline**, not the ~16% first claimed or the ~30% of the first correction. Each successive measurement made the change look worse, which is the direction that should have been assumed.

**Dismissed after investigation:** `search` and ship filtering work correctly (`is_ship_contract=true` → 622; `search` covers `Contract.title` OR `ContractItem.type_name` via the items join). An apparent "`ship_name` is always null" finding was an artifact of probing for a response field that does not exist.

---

## Workstream A — Dead-contract filtering

Two mechanisms, because the two failure modes are different.

**A1 — Expiry filter (small).** Add `Contract.date_expired > now()` to the list query. It belongs in `_apply_contract_filters`, so it reaches both `_count_distinct_contracts` and both fetch paths — a predicate applied to only one of them makes `total` disagree with the pages, which is the SQLA-1 failure this codebase has already paid for once. Use the database clock (`func.now()`), not a Python-side timestamp, so the predicate and any index agree and no timezone conversion sits between them.

Needs an index on `date_expired` and therefore an Alembic migration; the migration is the schema-change step class the repo already has conventions for.

**A2 — Delisted detection (medium — this is the real work).** Add `last_seen_at` to `Contract`, stamped on every upsert. Filter the list to contracts seen in the most recent *complete* ingest run.

The correctness hinge is "complete." Aggregation already counts `regions_ok`/`regions_failed` and derives an outcome of success / partial / failure. Only a **success** may advance the watermark — a partial run must not, or every contract in the failed region is wrongly judged delisted and vanishes from the site. This is the sharp edge of A2 and deserves its own test.

Non-destructive by choice: mark, do not delete. Deletion loses history and interacts with saved searches and notifications that reference those contracts.

**Detail pages keep serving dead contracts, clearly marked.** Never 404 them. Shared links outlive contracts, and a 404 for a link posted this morning reads as a broken site rather than an expired deal.

**Open question for Sam:** should an "include dead contracts" toggle exist? Precedent exists (ships-only has one, F002 Criterion 1.1). Recommendation: ship without it; let the trial ask.

---

## Workstream B — Data freshness surface

The user-facing staleness indicator parked in the M4 design. Its justification is the Jul 23–26 incident: production served 3.6-day-old data with no signal any user could see, while `/ready` correctly reported `data_stale`.

**Mechanism:** add `data_as_of` (ISO 8601, last successful ingest) **and** `data_stale` (boolean) to the contracts list envelope. Both, not just the timestamp — the frontend cannot compute staleness itself, because the threshold derives from `AGGREGATION_SCHEDULER_INTERVAL_SECONDS`, a server-side setting the SPA has no access to. The server owns the judgement; the client owns the presentation.

Values come from the same Valkey record `/ready` reads (`INGEST_LAST_RUN_KEY`), cached in-process with a 30-second TTL so the hot path takes at most one cache read per 30 s. Thirty seconds is far below the hourly cadence, so the displayed age is never misleading.

**Valkey-down behavior is specified, not left to chance:** the freshness read is wrapped so that an unreachable or uninitialized cache yields `data_as_of: null` and `data_stale: true`, never an exception. The list endpoint is the product's core read path and must not acquire a hard dependency on an evictable cache — the key is explicitly evictable under `allkeys-lru` (DEPLOY-3). A null renders as no freshness line rather than an invented one.

**Envelope caution:** `PaginatedResponse` is generic and also serves notifications. The new fields must not become required on every paginated payload — add them to the contracts response specifically, or as optional fields defaulting to null.

**Display:** extend the existing count line in `Pagination.tsx` (`Page 1 of 13 · 622 contracts`) with `· updated 12 min ago`. The stale state escalates to explicit wording naming the age. Per `accessibility-spec.md`, staleness is never signalled by color alone — the escalated state changes the *text*.

---

## Workstream C — Site-wide link previews (Stage 0)

Add `og:title`, `og:description`, `og:image`, `og:site_name`, and `twitter:card` to `index.html`. No routing changes, no backend work, roughly an hour. Today every link unfurls as nothing; after this, every link unfurls as the product.

**The image must live in `public/`, not `/assets/`.** Vite content-hashes `/assets/*` filenames on every build, and `render.yaml` serves them `immutable` for a year. Discord caches embeds by URL at post time, so a hashed image URL breaks every previously-posted embed on the next frontend deploy. A stable `public/` path does not change.

---

## Workstream D — Retire the `status` field

`Contract.status` is always the literal `"unknown"` (ESI's public route returns no status; `background_aggregation.py:108` defaults it). Verified across a 100-contract production sample; the frontend never reads it.

Remove it from the API response and regenerate the typed client (`pdm run export-openapi` → `npm run generate:api`). Keep the DB column and its index — dropping them is a migration with no benefit at this size, and the column becomes meaningful if character/corp contracts are ever ingested.

**`e2e/fixtures/contracts.ts` declares `status`** and must be updated in the same change, or the fixture lane drifts from the wire shape it exists to pin.

---

## Deferred: per-URL link previews

Recorded here so the follow-on design starts from what this review established rather than rediscovering it.

**The routing approach that survives scrutiny is the backend rendering the shell**, not a Cloudflare Worker. The Worker option serves different HTML per User-Agent, which is a `Vary: User-Agent` cache hazard forcing `no-store` and deleting its own performance rationale; its central benefit is unverified, since a rewrite to a Cloudflare destination has never been measured; it re-creates the stacked-CDN topology the DNS-only apex decision (M4 D-12) exists to avoid; and a Worker fetching the apex for the shell re-enters the rewrite that invoked it.

**Three constraints the follow-on must satisfy — all found by review, none obvious:**

1. **The backend already owns `/contracts` at a bare path.** `api/contracts.py` mounts `APIRouter(prefix="/contracts")` with `@router.get("/{contract_id}")`, and the `/api/v1/*` rewrite strips the prefix, so SPA API calls arrive at exactly `/contracts/123` — verified live (`200 application/json` on the origin). A naive `/contracts*` document rewrite lands the HTML handler on the JSON endpoint: either crawlers get JSON or the SPA's detail page breaks. The document handler needs a **distinct backend prefix** with the rewrite supplying it as the destination path, plus a regression test asserting the JSON API still returns JSON.

2. **Backend deploys are recreate deploys.** `render.yaml` pins a disk to keep the scheduler single-instance, which forces recreate rather than rolling deploys. Routing documents through the backend therefore makes **every backend deploy a brief site-wide document outage**, since `/` redirects to `/contracts`. That is a routine operational cost, not the tail risk the first draft described.

3. **Scope it to `/contracts/*` detail pages only.** Routing the list page — the effective homepage — through the backend buys nothing until search summaries exist, and doubles the blast radius.

**Also unverified:** whether Render's route globs accept the suffix form `/contracts*` at all. Every existing rule is segment-style (`/api/v1/*`).

**Data inlining is cut from M5 entirely**, but the follow-on should treat it as **coupled to per-URL tags, not optional**. Against the true ~450–500 ms baseline, shipping tags alone costs ~40%+, and inlining is what repays it by removing the client's ~270 ms API call. On these numbers the original "both or neither" instinct was closer to right than the review that talked me out of it — the review's arithmetic was sound, but it was fed an inflated baseline. Dehydrating TanStack Query state into a non-SSR SPA is real engineering — which is precisely why it belongs in the same design pass as the routing work, not as a "fast-follow" that can quietly never arrive.

**Preview content, when it is built:** hull name and price as title, with **absolute expiry in the description** — Discord caches embeds at post time, so a relative "expires in 3h" or an `EXPIRED` prefix is frozen at the moment of posting and misleads later readers. Image from `https://images.evetech.net/types/{type_id}/render?size=512`, verified 200 `image/jpeg` for real hulls, falling back to `icon` (verified 200 for a type whose `render` 400s) and then to the Stage 0 image. The fallback chain must be resolved from stored data, not a per-request probe of an external CDN. All interpolated values HTML-escaped — contract titles are player-authored free text, and this is an injection concern with an explicit hostile-input test.

**Settle the edge-cache question first.** The backend sets no `Cache-Control` anywhere, yet every response through the rewrite carries `cache-control: max-age=0` with `cf-cache-status: BYPASS` — so that header comes from the edge, and today's `BYPASS` is uninformative rather than evidence either way. The open question is whether an explicit origin `s-maxage` is passed through or overwritten. Probe: an endpoint returning `Cache-Control: public, s-maxage=60` plus a timestamp; request repeatedly; watch for `HIT` and a frozen timestamp.

---

## Testing

Every item is written test-first, and characterization tests are mutation-verified (TEST-12) — a filter test that passes with the predicate deleted is not evidence.

- **Expiry filter:** fixtures spanning the expiry boundary; expired contracts absent from results; `total` reflects the filtered count. Must cross a page boundary (TEST-4) and must exercise **both** the joined and simple fetch paths, since the predicate's placement determines whether count and pages agree (SQLA-1).
- **Delisted detection:** a contract absent from a later complete run is filtered; and — the one that matters — **a contract absent from a *partial* run is NOT filtered**, so a failed region cannot erase the site.
- **Detail page:** expired and delisted contracts return 200 with their state, not 404.
- **Freshness:** `data_as_of` and `data_stale` present and correct; the threshold flips at more than twice the scheduler interval; **Valkey unreachable yields nulls and a 200, never a 500**; the stale state is distinguishable without color.
- **Status removal:** the field is gone from the schema, the regenerated client compiles, and the e2e fixture matches the new wire shape.
- **Frontend:** stub at the fetch seam (TEST-5); every fixture-lane spec intercepts `GET /me` (TEST-9).

---

## Risks

**A2's watermark is the one that can take the site down.** If a partial run advances it, every contract in a failed region is judged delisted at once. The mitigation is a test, not care.

**Migrations.** A1 and A2 both add schema. Two migrations on a live database with a pre-deploy `alembic upgrade head` — the M4 machinery handles this, but it is the step class where DEPLOY-1's URL-scheme trap lives.

**Scope.** A2 is the item most likely to grow. If it does, A1 alone still ships a real improvement and A2 can follow.

---

## Reasoning worth preserving

**The same number was wrong three times, in the same direction.** Time-to-content was quoted as 1265 ms (one sample, the slowest of four), then ~650 ms (four samples, all from a contaminated tab), then finally ~450–500 ms (clean tab). Each figure made routing through the backend look cheaper than it is: 16%, then 30%, then 40%+. The "720 ms client bootstrap" that justified dismissing document latency was never real — it was contention in the measuring environment, and it survived a re-measurement because the re-measurement reused the same dirty tab.

The lesson is not "measure" — that was done. It is **take more than one sample before a number becomes load-bearing**, especially in an automated browser where contention is invisible in the result. One sample is an anecdote wearing a decimal point. The same mistake in a different guise appears below in the population error.

**Measuring the wrong population nearly shipped a wrong headline.** The first draft's "12% of contracts are expired" was true of the whole dataset and irrelevant to users, who see a ships-only default of 622. Corrected, the number fell to ~8.5% and the finding got *sharper* — 53 dead contracts against a 50-row page means the entire first page of the most natural sort is dead. Always measure the view the user actually gets.

**The biggest gap was invisible from the outside.** Expiry is measurable through the public API; sold-but-still-listed is not, because the record looks identical to a live one. It surfaced only from reading the model and noticing no `last_seen_at` existed. Absence of a column is not something an API probe can find.

**The route collision would have reached production.** The first draft said "the backend serves these routes at bare paths, per PROXY-1" — correctly citing the pitfall while walking into it, because the backend already serves JSON at that exact bare path. Citing a pitfall is not the same as checking it.

**The cheapest win was nearly missed.** Static site-wide OG tags cost about an hour and change every link on the site. They surfaced only under review by someone uninvested in the routing question, which had absorbed all the attention.

**Still uncertain:** whether the trial corporation shares contract links or search links (assumed contracts); whether Render's edge honors origin `s-maxage` on rewrites; whether an "include dead" toggle is wanted; and whether deferring per-URL previews is the right call, which is Sam's to make.
