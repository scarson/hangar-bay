# ABOUTME: Round-2 adversarial review (Fable) of the M5 ingestion clean-sheet design
# ABOUTME: after the chaining/Expires/two-lane/Discord revisions. Findings ranked BLOCKER/MAJOR/MINOR.

# Clean-sheet design review — round 2 (Fable)

Scope: the revised design (user story, measured ESI facts, Expires scheduling, chained
lanes, Discord delivery, job topology). Round-1 items verified as applied; not re-litigated.

**Verdict in one line:** the ingestion half is now close to sound — the remaining defects
cluster in the *chain*: the fast lane welds a third-party delivery dependency into the
discovery job under discovery's lock (recreating the exact lock-TTL-versus-run-duration
defect this design was born to kill), Expires-phase polling maximizes exposure to a
mid-sweep generation shear that the watermark converts into false delistings, and the
Discord half has an SSRF hole and no delivery semantics.

---

## Q1 — Does chaining hold up?

Inline-after-discovery is right for enrichment and matching: both are cheap (~12 s + a
few queries), both are ours, and a queue between them only adds latency. Delivery is
where the chain breaks.

### BLOCKER-1: The chain puts Discord inside discovery's lock — "inherits discovery's TTL" recreates the original sin one layer up

The topology table gives the fast lane a lock that "inherits discovery's," where
discovery's TTL was derived from a seconds-scale budget. But the chain now appends:
enrichment (ESI-governed — a `Retry-After` pause legitimately extends it), matching
(fine), and **delivery — HTTP calls to a third party with its own rate limits and
outages, retried with backoff per the delivery section**. Worst case: Discord is down or
rate-limiting, N users matched this cycle, "retry with backoff" runs inline → the chain
outlives a lock sized for a different job. That is precisely the 65-minute-lock /
77-minute-run defect, reintroduced at the design's newest layer. Two concrete failures:
the next Expires-scheduled discovery tick skips on a held lock (discovery freshness now
*coupled to Discord availability* — the fast lane damaging the very latency it exists to
protect), or the lock expires mid-chain and the mutual-exclusion claim is fiction again.

**Fix (keeps the latency win):** the chain's lock TTL is the *sum* of its stages'
budgets + margin, and delivery gets a hard, small budget (~10 s) for **first attempts
only**. Matches are already persisted (the notifications table + SQLA-2 dedup index is
the delivery queue you were asking whether you need — it already exists). Undelivered
rows are picked up by a small retry tick. The design's objection — "an independent
delivery tick re-introduces latency" — is wrong for retries: first attempts stay
chained (latency unchanged); only *failed* deliveries wait for the tick, and a failed
delivery is already late by definition. Note the retry tick is *required* by the
design's own text: "failures retry with backoff" is unimplementable in a chained-only
model, because nothing runs between discovery ticks to perform the retry.

### MAJOR-6: Contracts that miss the fast lane fall out of the alert path entirely

If the fast-lane budget exhausts (governor pause, transient 5xx burst), the unfinished
new contracts correctly fall to the backfill lane — but the chained matcher only matches
"the contracts just enriched" *by the fast lane*. Backfill-enriched contracts are then
matched only by the matcher's "periodic full pass," whose interval the design no longer
specifies (it was 15 min; the text now says "retains a periodic full pass" for watchlist
edits). If that pass slows or is removed, a rate-limited cycle's contracts silently take
hours to alert. Fix: chain matching after *every* enrichment batch regardless of lane
(the dedup index makes double-matching free), and state the periodic pass's interval as
the alert-path safety net, not just the watchlist-edit catch-up.

Also state chain failure isolation: a matcher/delivery exception must not mark
*discovery* failed — freshness derives from Stage 1's own outcome, which succeeded.

---

## Q2 — Expires-driven scheduling: sound in principle, naive in four mechanics

The idea is right and self-tuning (see Q3). The mechanics as written are not:

### MAJOR-3: Polling at the regeneration boundary maximizes mid-sweep generation shear, and the watermark converts shear into false delistings

A sweep is 34 sequential page fetches over several seconds, each page carrying its own
headers. ESI's cache is lazy per page — the "new generation" of page 20 may be
materialized by *our* request. Polling at `Expires`+ε lands the sweep exactly on the
boundary, so pages can come from **different generations mid-sweep**. New contracts
shift page boundaries between generations, so a boundary-spanning sweep can *skip*
contracts entirely. Today's pipeline rarely spans a boundary (34 pages in ~seconds at a
random phase ≈ low odds); Expires-phase polling makes spanning the *common case*. The
consequence is not cosmetic: PR #91's per-region watermark treats "absent from a
complete sweep" as delisted, so a shear-skipped live contract is **hidden from the site
for a full cycle (~30 min)** and re-appears next sweep — user-visible flicker, plus
noise in the delisting data. Fix, cheap: record page 1's `Last-Modified`; if any later
page's `Last-Modified` disagrees, the sweep is generation-inconsistent — restart it
(bounded retries), and **never stamp the watermark from an inconsistent sweep**.

**The stale-poll race (same family, opposite edge):** polling at `Expires`+ε can still
return the *old* generation (clock slop, CDN edge). As written, the scheduler would
accept it, upsert nothing new, and sleep another 1800 s — silently losing the exact race
the feature exists to win, one cycle at a time. Fix: compare `Last-Modified` to the
previous sweep's; if unchanged, short backoff (5–15 s) and re-poll, bounded, before
conceding the cycle.

### MINOR-7: Scheduler header hygiene (each item small, all needed)

- **Clock skew:** compute the delay as `Expires − Date` (both from the response — same
  clock), never `Expires − local_now`.
- **Floor and cap** the computed delay: a stale/garbage `Expires` must not busy-loop
  (floor ~30 s) or park discovery forever (cap at the configured fallback interval).
- Page 1's headers govern the region's schedule; per-region independence is right and
  currently trivial (one region).
- Thundering herd against CCP is a non-issue at our scale — jitter's real job is the
  +ε boundary offset, not politeness; say so to prevent someone "fixing" it later.

---

## Q3 — The 30-minute floor claim

**The claim's robustness comes from the mechanism, not the measurement — lean on that.**
You measured 1800 s once; the swagger documents "up to 3600 s" for this endpoint. That
discrepancy is exactly why the design should never hard-code 30 minutes anywhere
(including the "~30–40 min" results table — footnote it as "at the measured 1800 s
window"): the Expires-driven scheduler doesn't care what the number is, and if CCP
changes it per-region or per-load, the design self-adjusts. To the specific questions:
`Last-Modified` is the generation marker ESI actually maintains — use it for both the
shear check and the stale-poll check (MAJOR-3), which also makes it empirically
self-verifying: if ESI regenerated more often than `Expires` implies, your own sweep
logs would show it. Polling *before* `Expires` is strictly useless — the shared cache
serves the old body until expiry, full stop; there is nothing to be early *to*. The one
nuance worth keeping: regeneration is lazy, so the earliest instant the new data exists
is the first request *after* expiry — with +ε polling and the stale-retry loop, that
request is plausibly ours, which is as good as the race can be played.

---

## Q4 — Two lanes: real, with two specifics missing

No preemption is needed at these scales — in one asyncio process, "discovery draws
first" means at worst draining in-flight requests (~1–2 s) before discovery's ~34
acquisitions proceed. What priority classes *cannot* do is conjure budget that backfill
already burned:

- **MINOR-8a:** the discovery reservation must be on the *budgets* (error-limit
  headroom, and tokens when the rollout reaches this group), not just acquisition order:
  backfill stops when projected headroom < discovery's per-cycle need (~40 requests'
  worth, with 4xx priced at 5). The current text says "reserve headroom" and "draws
  first" in the same breath — specify that these are two different mechanisms and both
  are needed.
- **MINOR-8b:** two lanes, one queue ⇒ claim rows (`in_progress` status or
  `FOR UPDATE SKIP LOCKED`) so a fast-lane contract isn't double-fetched by a
  concurrently ticking backfill. Trivial in one process, but only if stated.

Also (observed fact worth locking in): no `X-Ratelimit-*` headers on the contracts
route means the token-bucket rollout hasn't reached this group — the governor must
**fail open on absent headers** (no rate limit ≠ no headroom) and adapt automatically
when they appear. The error window is the only binding limit today.

---

## Q5 — Alert delivery: the sketch has one security hole and no semantics

### BLOCKER-2: A user-pasted webhook URL is an SSRF primitive, not just a credential

The design treats the URL's sensitivity as confidentiality (encrypt at rest — good) but
misses the other direction: the backend will POST to an **arbitrary user-supplied URL
from inside Render's private network**. That is server-side request forgery by
construction — internal service endpoints, metadata services, the Valkey/Postgres
private hosts. Required, non-negotiable: validate at save time and at send time that the
URL's host is exactly Discord's webhook surface (`discord.com` / `ptb.` / `canary.`
paths under `/api/webhooks/`), refuse redirects on the POST, short connect/read timeout
(~5 s), and never fetch anything else with it. With the allowlist this collapses to a
one-function check; without it, delivery is a hole.

### MAJOR-5: Delivery semantics are undesigned — five decisions that will bite in order

1. **Exactly-once is not on offer — choose at-least-once and say so.** Creation-side
   dedup (the SQLA-2 partial index) does not cover delivery: a crash between a
   successful Discord POST and the DB commit recording it re-sends on restart. Add
   `delivered_at` + attempt count to the notification row, mark after send
   (at-least-once, rare duplicate ping — harmless); the reverse order silently *loses*
   alerts, which violates the user story.
2. **Discord's own rate limits** (per-webhook, roughly a handful of requests per couple
   of seconds; 429s with `Retry-After`) need their **own limiter, separate from the ESI
   governor** — different domain, different bucket, different key (per webhook URL).
3. **Batching:** one cycle can match many contracts for one user; webhooks accept up to
   10 embeds per message — batch per user per cycle, and above a cap send a digest
   ("14 matches — view in Hangar Bay") instead of machine-gunning their channel into a
   rate limit.
4. **Verification UX:** POST a test embed on save — catches wrong-paste immediately,
   which is also the moment the allowlist check runs.
5. **Auto-disable needs a re-enable path** and the disabled state surfaced in the UI
   with its reason; otherwise "we stopped delivering and told a log file" — the
   unbounded-latency problem the section exists to fix, reintroduced quietly.

The open-questions list already flags Discord round-trip/rate limits as uncharacterized —
correct; characterize before sizing the delivery budget in BLOCKER-1.

---

## Q6 — Does this satisfy the user story, or a proxy?

**It satisfies "the user is never late because of us." It cannot satisfy "the user wins
the race," and the doc should say which one it's promising.** Walk the timeline for a
genuinely great deal in The Forge:

1. Issue → cache flip: 0–30 min, CCP's, shared by everyone. Parity.
2. Cache flip → our alert: ~ε + 12 s + seconds. But every serious EVE market tool plays
   the same Expires-phase game — this buys **parity with the best ESI consumers, not
   advantage over them**. The design's own consequence #1 already concedes this; the
   headline table should not imply otherwise.
3. Alert → user acts: Discord ping (seconds) → open the game → **travel and buy**. For
   extreme mispricings in Jita, semi-automated snipers with pre-positioned capital win
   inside the first minute after cache flip; a human reading Discord loses that race
   every time regardless of our pipeline. For moderately good deals — the realistic
   product promise — minutes matter and this design delivers them.
4. The one lever left on the human hop, noted for the backlog, not this design: ESI's
   authenticated UI endpoint can open a contract window **in the game client**
   (`POST /ui/openwindow/contract/`, `esi-ui.open_window` scope — version-pin per
   ESI-1). An "open in game" action on the alert removes the search-for-the-contract
   fumble, which is often longer than our entire pipeline latency.

Also trim the absolute: "this design adds under one [minute]" holds for the happy path;
a governor-paused fast lane adds up to its budget, and a stale-poll retry adds seconds.
"Under a minute in the common case, bounded by the fast-lane budget otherwise" is the
defensible sentence.

---

## Q7 — The error class you're repeating

Name: **asserting end-to-end properties from the component currently in focus, backed
by single-point measurements generalized into constants.** Every instance this session
fits it: concurrency-first (optimizing the loop in hand, not the pipeline), "a short run
collapses lock/cache/staleness" (component speed asserted as system property), "discovery
far more often is what users feel" (one stage's cadence asserted as UX, capped by CCP),
one `Expires` sample → "the floor," one 384-contract sample → "latent, matches nothing,"
one churn sample → a constant (churn is diurnal — EU/US prime time plausibly 2–3× your
230/hr; harmless here because capacity headroom is ~20×, but the *pattern* is the point).
And the freshest instance is in this very revision: **the chain's lock "inherits
discovery's" TTL** — unbounded third-party work placed under a lock sized for a
different job is the original 65/77 defect, re-derived one layer up, in the section
written most recently. The mechanical remedies: (a) every "by construction" claim must
name the mechanism that enforces it *and the test that pins it* (deadline clipping has
this; the chain TTL didn't); (b) every measured number carries its sample scope where
it's used, and nothing downstream hard-codes it (the Expires scheduler gets this right —
apply the same standard to churn and the results table); (c) before writing an
end-to-end latency claim, walk the chain including the systems that aren't yours — CCP's
lazy cache, Discord, and the user's spaceship.

---

## Summary table

| # | Rank | Finding | Concrete failure |
|---|------|---------|------------------|
| 1 | BLOCKER | Delivery (third-party, retrying) runs inside discovery's lock; chain TTL "inherits discovery's" | Lock-TTL < run-duration defect recreated; discovery freshness coupled to Discord outages |
| 2 | BLOCKER | User-pasted webhook URL is SSRF from inside Render's network | Backend POSTs to internal endpoints; allowlist + no-redirect + timeout required |
| 3 | MAJOR | Expires-phase polling makes mid-sweep generation shear the common case; watermark turns skipped contracts into 30-min false delistings; stale-poll race concedes whole cycles | Live contracts flicker out of the site; the race the feature exists to win is silently lost |
| 5 | MAJOR | No delivery semantics: at-least-once choice, per-webhook limiter, embed batching/digest, test-on-save, re-enable path | Duplicate or lost alerts; Discord rate-limit storms; silent permanent disablement |
| 6 | MAJOR | Backfill-enriched contracts exit the alert path; periodic matcher pass now unspecified | Rate-limited cycles' contracts alert hours late |
| 7 | MINOR | Scheduler hygiene: skew via `Expires − Date`, floor/cap delay, page-1 governs | Busy-loop or parked discovery on a bad header |
| 8 | MINOR | Lane reservation must bind budgets not just order; queue rows need claiming across lanes | Discovery starved by pre-spent budget; double-fetch |
| — | MINOR | Governor fails open on absent `X-Ratelimit-*` (confirmed absent on this route today); don't hard-code 1800 s or "30–40 min"; migration section not yet updated for the new topology (lock split, freshness/`/ready` rewiring, Expires scheduler, matcher re-chaining) — the same patch-seam class your round-1 self-review caught | Design/migration drift; governor deadlock on missing headers |

Sound, one line each: the discovery/enrichment table and fetch-once core (unchanged,
still right); complete-sweep requirement for absence; pending-contracts-excluded
decision; `enrichment_version`; failure taxonomy incl. the 403 inversion; deadline
clipping; queue-as-query; migration steps 1–5 for the enrichment half; "deliberately not
proposed" all three; churn cross-check method; observability picks.
