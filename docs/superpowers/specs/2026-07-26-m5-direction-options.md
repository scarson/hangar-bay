# M5 Direction Options

ABOUTME: Candidate directions for M5 with the evidence behind each, the chosen starting point, and the reasoning that ordered them — written before any M5 design exists.
ABOUTME: This is a direction/options record, NOT a design spec; the chosen direction gets its own dated design under `docs/superpowers/specs/` before any plan is written.

**Status:** Direction chosen, no design written yet. Current start: **trust & shareability polish**, with **coverage expansion** as the intended follow-on. The other three directions are parked here so they are not rediscovered from scratch.

**Provenance:** Generated 2026-07-26, immediately after M4 closed out its last engineering residual (the watchlist matcher lock TTL, PR [#82](https://github.com/scarson/hangar-bay/pull/82)). At that moment all seven feature specs (`design/features/` F001–F007) were built and no product direction past M4 existed in the repo.

---

## Where M4 left things

Four verified facts shaped every option below. Each was confirmed against the code, not inferred.

1. **Coverage is one region.** `render.yaml` sets `AGGREGATION_REGION_IDS = "[10000002]"` — The Forge (Jita) only, ~51k contracts. `PRODUCT.md` promises "the right hull at the right price **in the right place**"; today there is one place.

2. **There is no price context of any kind.** No market-price ingestion, no appraisal logic anywhere in `app/backend/src/`. The product displays what a contract *asks* and never what its contents are *worth*. The user question `PRODUCT.md` names — "is this Rokh cheap enough to fly it back?" — is the question the app cannot currently answer.

3. **`status` is `"unknown"` on every public contract.** `services/background_aggregation.py:108` defaults it, because ESI's *public* contracts endpoint does not return a status field (that exists only on character/corp contract routes). A column shipped to a "trust the numbers" audience carries no information on any row.

4. **Alerts have no delivery path off the site.** No webhook, email, or push anywhere in the backend — the only `email` import is `email.utils` for ESI date parsing in `core/esi_client_class.py`. The watchlist/notification features (F006/F007) terminate in an in-app list, for an audience `PRODUCT.md` describes as alt-tabbed out of the game.

---

## The candidate directions

### Trust & shareability polish — *small*

Finish what M4 deliberately parked and make the product honest about itself: the user-facing data-staleness indicator (parked in the M4 design spec `2026-07-18-m4-production-readiness-design.md` §"parked to M5", with the data already exposed by `/ready`), resolution or removal of the meaningless `status` column, and link-unfurl (Open Graph) previews so a shared filtered URL renders properly when pasted into Discord.

Serves two of the three success criteria `PRODUCT.md` states outright — "trusts the numbers" and "shares a filtered URL with a corpmate". The staleness indicator gained urgency from the Jul 23–26 production incident, where the site served 3.6-day-old data with no signal a user could see (incident record: M4 plan Deviation D-15).

### Coverage expansion — *medium-large, infrastructure-dominated*

Ingest beyond The Forge: the other trade hubs (Amarr, Dodixie, Rens, Hek), then high-sec more broadly.

**This is where M4's residual engineering queue stops being housekeeping.** A single-region run already takes ~77 minutes (measured 2026-07-26: deploy completed 18:46:44Z, first completed ingest 20:03:21Z). The scheduler split, ingestion observability, the ETag-eviction and instance-sizing posture, and the ESI 403 audit — all listed as loose residuals in the M4 close handoff — are **prerequisites** for multi-region ingestion, not a competing track. Choosing this direction converts that queue into the work.

### Market appraisal — *large*

Value contract contents against market prices, show the delta against the asking price, and let users sort and filter by underpricing. This is the difference between a browsable list and a deal-finder, and it is the job third-party EVE appraisal tools exist to do.

Highest differentiation of any direction here, and the only one that answers the product's own stated user question. Requires a market-price source (ESI `/markets/prices/` for adjusted/average values, or regional order books for real bid/ask), an explicit valuation policy for bundles, and honest treatment of items that cannot be priced meaningfully (blueprint copies, abyssal modules, fitted rigs). **Principal risk:** valuation is opinionated, and a wrong number destroys exactly the trust the product is trying to earn — worse than showing no number.

### Alert delivery channels — *small-medium*

Deliver watchlist hits where the audience actually is: Discord webhooks first (EVE communities run on Discord), possibly EVE in-game mail; richer triggers than price-under-threshold.

Highest leverage per unit of effort for retention, and it makes the existing watchlist and notification features load-bearing rather than merely present.

### Closed trial, then public launch — *small*

Two distinct steps that were initially conflated:

- **Closed trial** — put it in front of the friend (and possibly their corp) whose idea prompted the app. Cheap, and it does **not** require the product to be differentiated first, because the participants already want the thing to exist.
- **Public launch** — broad EVE-community exposure. **Gated on differentiation.** Today a public audience would correctly read Hangar Bay as a basic ship-contract aggregator that does nothing existing marketplace sites do not; there is no reason for them to look until something like market appraisal exists.

---

## Current direction and why

**Start with trust & shareability polish. Coverage expansion as the intended follow-on.**

The starting choice is small, finishes M4's parked work, and makes the product presentable to the closed-trial participants — who are the realistic first audience. Coverage expansion follows because it is foundational: appraisal and alerting both get more valuable as coverage grows, and its prerequisites are already enumerated as residuals.

Market appraisal is the strongest differentiator and remains the most likely eventual headline feature, but it is the largest build and the one most improved by real user input first. Public launch is explicitly sequenced *after* differentiation rather than before it.

### Reasoning chain, including what was reconsidered

- **A "launch and learn" step was proposed first as public exposure (EVE subreddit, community Discords) and was rejected on accurate grounds:** the product currently does nothing existing marketplace sites do, so a public audience has no reason to engage, and their verdict would measure differentiation rather than the questions worth asking. Reframing it as a closed trial with an already-interested friend preserves the cheap-feedback benefit and drops the differentiation precondition. The public step survives, but moved behind appraisal.
- **The initial recommendation was polish + launch as a fast pair, then let feedback choose between appraisal and coverage.** The adopted direction keeps the polish-first half and replaces the "let feedback decide" half with a deliberate bet on coverage as foundational work. The difference is a judgment about whether early feedback from a small trial group is decisive enough to re-order a foundational investment; it likely is not.
- **The "M5 is a queue of ops chores competing with product work" framing was wrong** and is corrected above: under coverage expansion those residuals are the critical path. This was the single most useful analytical result of the session and is the reason coverage is ranked as foundational rather than deferred.
- **One assumed driver evaporated during the survey.** The M4 plan's Discovery that a boot-time Valkey outage crashes the process at `scheduler.start()` was premised on APScheduler's `RedisJobStore` writing synchronously at start; the Jul 26 incident fix replaced it with an in-memory jobstore, and `init_cache` swallows a failed connect rather than raising. The scheduler-split work therefore retains only its single-worker driver (pitfall DEPLOY-2). Recorded in the M4 plan (PR [#83](https://github.com/scarson/hangar-bay/pull/83)); repeated here because it changes how coverage expansion should be scoped.

### What would change this ordering

- **If the closed trial surfaces a specific unmet need**, that need outranks the plan above — the trial exists to be listened to.
- **If appraisal turns out to be cheaper than assumed** (for example, if ESI's aggregate price endpoints prove good enough without order-book ingestion), it moves ahead of coverage: differentiation before scale is the better trade when differentiation is affordable.
- **If ingestion cost per region proves worse than linear**, coverage expansion needs its own design pass before commitment rather than being treated as configuration plus hardening.

### Open questions

- **What "trust" gap do the trial participants actually feel?** The polish direction is currently scoped from the product's stated principles and one incident, not from a user complaint. The closed trial should test this rather than assume it.
- **Should the `status` column be resolved or removed?** ESI's public route cannot populate it; the choice is between deriving a display status from `date_expired`/`date_completed` (which the watchlist matcher already does for its own query) and dropping the column. This is a design decision for the polish direction, not a settled one.
- **How many regions is "enough"?** Trade hubs cover most real demand at a fraction of all-of-high-sec's ingestion cost. The stopping point is a product decision, not a technical one.
