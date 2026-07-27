# M5 Handoff — Trust & Shareability Shipped, Ingestion Redesigned (2026-07-27)

ABOUTME: End-of-session handoff for the M5 session of 2026-07-26/27 — four PRs shipped and released to production, plus a fully-reviewed ingestion redesign and its first implementation plan, ready to execute.
ABOUTME: Authoritative state lives in the linked design/plan docs and `docs/pitfalls/`; this file is orientation, seams, and the continuation prompt — not a second source of truth.

## Headline state

- **Production LIVE and verified** at `https://hangarbay.app`, `main` @ **`fd9d1f2`** (release PR [#90](https://github.com/scarson/hangar-bay/pull/90)). Deploy + smoke both green; the release carried the first schema migration since the baseline.
- **`dev` @ `e5c5b59`** — **one unreleased commit**: PR [#91](https://github.com/scarson/hangar-bay/pull/91) (sold/delisted contract detection, migration `c7e2a9b41d36`). Merged by Sam 00:58Z; **not yet in production**.
- **Branch `claude/m5-ingest-perf`** carries the ingestion redesign, its three review rounds, and Plan A. Pushed, rebased onto current dev, **no PR opened yet** — docs only, 1,749 insertions.
- **No open PRs.** Everything else this session merged.

## What shipped and reached production

Four user-visible changes, all released in #90 and verified live:

| PR | Change | Verified in production |
|---|---|---|
| [#86](https://github.com/scarson/hangar-bay/pull/86) | Open Graph link previews + 1200×630 card | 9 `og:` tags served, `og-card.png` 200 `image/png`, `og:url` correctly absent |
| [#87](https://github.com/scarson/hangar-bay/pull/87) | Expired contracts excluded from the list | "Time left" ascending returns **0 expired on page 1**; total 622 → 573 |
| [#82](https://github.com/scarson/hangar-bay/pull/82) | Watchlist matcher lock TTL derived from its interval | — |
| [#80](https://github.com/scarson/hangar-bay/pull/80) | Region filter viewport sizing | — |

Docs merged: [#84](https://github.com/scarson/hangar-bay/pull/84) M5 direction options, [#85](https://github.com/scarson/hangar-bay/pull/85) trust & shareability design + recon, [#88](https://github.com/scarson/hangar-bay/pull/88) pitfall TEST-14, [#89](https://github.com/scarson/hangar-bay/pull/89) latency-measurement correction.

## Ready to dispatch

**Plan A — `docs/superpowers/plans/2026-07-27-ingestion-correctness-and-cost.md`** (on `claude/m5-ingest-perf`). Six tasks, three phases, subagent-proofed with full code in every step. Takes a steady-state ingestion run from **~77 minutes to seconds**.

Prerequisites are satisfied: #91 is merged, so Task 3's `down_revision` (`c7e2a9b41d36`) is correct on dev.

**Recommended execution:** subagent-driven, one fresh subagent per task, **in a new session** — the plan is deliberately self-contained so it needs none of this session's context.

## Not yet started

- **Plan B** — pipeline restructure: discovery/enrichment split, `Expires`-driven scheduling, the shared rate-limit governor. Designed, not planned.
- **Plan C** — Discord alert delivery. Designed (including its SSRF constraints), not planned. **This is the other half of the alert user story**; the pipeline work alone does not satisfy it.
- **Freshness surface** (`data_as_of` + `data_stale`) — specced in the trust & shareability design, but **the design changed underneath it**: freshness should be measured from discovery, and the freshness record currently lives in an evicting cache (see Deferred).
- **Retiring the always-`"unknown"` `status` field** — small, independent, unblocked.

## Deferred, each with its unblock condition

1. **PR #91's delisted detection reaching production** — unblocks with the next `dev` → `main` publication PR. Should not be rushed: give #90's migration a healthy interval first.
2. **Freshness record eviction.** `/ready` reported `last_ingest_age_seconds: null` **four minutes after a successful ingest wrote that key** — the DEPLOY-3 pattern, milder consequence. Two options analysed: switch the Key Value `maxmemoryPolicy` from `allkeys-lru` to **`volatile-lru`** (one config line; every cache-like key already carries a TTL — ESI bodies, sessions, locks — so the protected set is one ~200-byte key), or move the record to Postgres. **Recommendation: `volatile-lru`.** Needs Sam's Render credentials; `render.yaml` is documentation-of-record and must be mirrored manually.
3. **Scheduler cadence vs run duration — LIVE IN PRODUCTION.** The aggregation lock TTL is `interval + margin` = **65 minutes** while runs take **~77 minutes**, so the lock expires ~12 minutes before a run ends. Today it is saved only by tick alignment (ticks at T+60 and T+120 never land in the T+65→T+77 window), which fails once runs exceed ~120 minutes. Plan A's skip-known dissolves this by making runs short; until then it is a live latent hazard. Checkable: every run should be logging `Aggregation lock token mismatch on release`.
4. **The 3.1% zero-item contracts — LIVE IN PRODUCTION.** Measured: 15 of 384 sampled `item_exchange` contracts serve zero items, which is impossible legitimately. Plan A Tasks 2–3 fix and repair it.
5. **Sam's live SSO login** — still the M4 exit criterion. Needs an EVE character.
6. **Spike-repo deletion** — `gh repo delete scarson/hb-render-spike-m4` needs a token scope this session lacked.
7. ~~Fable's Plan A review pending~~ — **landed and fully applied.** Two blockers and five
   majors, at `docs/audits/m5-recon/plan-a-review-fable.md`. Worth knowing what it caught,
   because all of it would have hit a subagent immediately: Tasks 1 and 6 used pytest fixtures
   that **do not exist** in `tests/core/test_esi_client.py` (its idiom is `_etag_response` /
   `_etag_client` doubles); Task 4's migration template omitted the `revision`/`down_revision`
   module attributes Alembic reads; Task 5 called `select()` without the import; Task 3's
   verification ran against an empty database and exercised nothing; and the acceptance
   criterion said "seconds" when steady state still performs a 34-page sweep and a 46k-row
   upsert — a literal executor would have reported false failure. The reviewer's *first*
   blocker (a missing migration) was **stale**, from reading the branch before its rebase onto
   post-#91 dev; its advice was adopted anyway — verify migration chains with
   `alembic heads`, never by listing filenames.

## Open questions for Sam

- Whether to defer per-URL link previews (the corrected latency numbers now argue tags and data inlining should ship **together**, reversing an earlier call).
- Whether an "include dead contracts" toggle is wanted.
- Whether the trial corp shares contract links or search links.
- **Paste a Hangar Bay link into Discord** — the only check no local test can make; Cloudflare fronts production and could block Discordbot.

## Operational guardrails accumulated this session

- **`git checkout -- <file>` between mutation tests discards an *uncommitted* fix**, producing fake "the mutation killed it" evidence. Use a `cp` snapshot, and always end with a restore-and-rerun that must be green.
- **`tests/api/test_contracts.py` has a file-level `pytest.mark.vcr`** — a test added there replays a cassette and passes with the behavior deleted. Use `test_contract_filters.py`. Now pitfall **TEST-14**; an unexpected new file under `tests/api/cassettes/` is the tell.
- **zsh does not word-split unquoted variables**, so `env $VARS pytest` passes everything as one argument and only the first pair survives. Use inline `VAR=x VAR2=y cmd`.
- **zsh glob-expands `--include=*.py`** before grep sees it, yielding "no matches found" rather than a search. Quote it.
- **`gh pr merge` on a publication PR must omit `--delete-branch`** — the head branch is `dev`.
- **`gh pr merge` fails its local cleanup** when `dev` is checked out in another worktree; the merge still succeeds on GitHub. Verify with `gh pr view --json state`, don't retry.
- **`preview_start` resolves `launch.json`'s `cwd` against the session's worktree**, not the branch's — the dev server won't start from a different worktree without deps installed there.
- **Time deploys for just after an ingestion run completes.** Migrations run as a pre-deploy command with `lock_timeout='30s'`; an overlapping run's transaction on `contracts` can collide. `/ready`'s freshness age tells you where you are in the cycle.
- **Every backend test run needs a dedicated scratch database.** Scratch DBs left behind: `hangar_bay_test_wlttl`, `hb_migrate_check`, `hb_migrate_check2`, `hb_mig3`. Harmless; drop at will.

## Measured facts worth not re-deriving

| Fact | Value | Scope |
|---|---|---|
| ESI public-contract list cache TTL | **1800 s**, uniform | 5 trade hubs, 2026-07-27 |
| Cache regeneration | appears **lazy** (first request after expiry), phase differs per region | same sample |
| `X-Pages` | Jita **34**; Amarr 3; Dodixie/Rens/Hek **2** each | same sample |
| Contract churn | **~230/hour** against a 45,441 corpus | 300-contract sample; **diurnal** |
| Per-contract ESI fetch | ~95–100 ms | derived from a 77-min run over ~46k contracts |
| Zero-item `item_exchange` contracts | **3.1%** | 384-contract sample |
| Warm page time-to-content | **~450–500 ms** (document ~35–50 ms, API ~270 ms) | clean browser tab; earlier 1265 ms and ~650 ms figures were contaminated |
| Apex-rewrite hop cost | **~161 ms** (edge cache HIT vs ohio origin) | 12 samples/target |

## Priority queue

1. **Open a PR for `claude/m5-ingest-perf`** (docs only, Routine) so the design and plan reach dev.
2. **Execute Plan A** — subagent-driven, fresh session. Its review is applied; no pre-work needed.
3. **Publication PR** for #91 + Plan A's output.
4. Plan B, then Plan C — or Plan C first if the trial date is near, since delivery is the binding constraint on the alert story.
5. Sam: SSO login, Discord embed check, Render `volatile-lru`, spike-repo deletion.

## Adversarial review of this handoff

- **Round 1 — naive fresh agent (3 applied):** spelled out DEPLOY-3, TEST-14 and "skip-known" at first use; added the production SHA and dev/main divergence to the headline; made the `claude/m5-ingest-perf` branch's unmerged status explicit rather than implied.
- **Round 2 — recency-bias audit (4 applied):** the session's *first* hour was nearly lost entirely — the 88-hour staleness investigation that turned out to be expected recovery lag, PR #82's merge, and #83's plan correction. Added the measured-facts table so mid-session measurements survive independently of the narrative that produced them.
- **Round 3 — seam auditor (3 applied):** #91 merged *during* the handoff write and changed Plan A's prerequisite from "blocked" to "satisfied" — corrected. The `claude/m5-ingest-perf` branch was created before #91 and would have shown its code as deletions in a PR; rebased. Flagged that Fable's plan review may land after this doc is written and where it will appear.
- **Round 4 — operational guardrails auditor (5 applied):** promoted the zsh word-splitting and glob traps, the `gh pr merge` publication-PR and worktree-cleanup behaviours, and the deploy-timing rule from transcript-only into the guardrails list.
- **Round 5 — loss-averse auditor (4 applied):** three things existed only in chat — the `volatile-lru` analysis and its recommendation, the live lock-TTL hazard with its checkable log signature, and the ESI `/ui/openwindow/contract/` idea for the human hop (now in the design's open questions). Added the scratch-database list so cleanup isn't archaeology.
- **Round 6 — reversal auditor (session-specific; 3 applied).** This session's defining character was that its conclusions *reversed repeatedly* — concurrency-first became fetch-once; "tags and inlining can ship separately" became "they should ship together"; three successive latency baselines each made a change look worse. A handoff that states only final conclusions would let a future agent re-derive a superseded one and think it new. Applied: recorded *which* conclusions reversed and why, kept the contaminated measurements visible beside the corrected ones rather than deleting them, and noted in the open questions that the per-URL preview call was reversed by better numbers.
- **Round 7 — holistic top-to-bottom re-read (1 applied):** tightened the headline so "shipped and verified in production" is unmissable and separated from "designed but not built." Final full pass through all rounds: zero material findings.

## Continuation prompt

```
You are picking up Hangar Bay (FastAPI + React → Render) mid-M5. Production is
LIVE and healthy at https://hangarbay.app, main @ fd9d1f2, carrying link
previews and expired-contract filtering, both verified in production. dev @
e5c5b59 has ONE unreleased commit: PR #91 (sold/delisted contract detection).
Read CLAUDE.md and docs/pitfalls/ first — TEST-12 and TEST-14/15/16 are recent
and were all earned the hard way this session. Skill routing is mandatory.

AUTHORITATIVE STATE (priority order):
- Handoff (orientation, seams, guardrails, measured facts):
  docs/superpowers/handoffs/2026-07-27-m5-ingestion-handoff.md
- Ingestion design (3 adversarial review rounds; supersedes all earlier
  ingestion thinking): docs/audits/m5-recon/ingestion-clean-sheet-design.md
- Plan A, ready to execute:
  docs/superpowers/plans/2026-07-27-ingestion-correctness-and-cost.md
- Session memory: component-focus-error-class (auto-loaded) — read it before
  making any end-to-end performance claim.

These last three live on branch `claude/m5-ingest-perf` (pushed, rebased onto
dev, NO PR yet). Open a docs PR for it early so they reach dev.

NEXT: (1) read docs/audits/m5-recon/plan-a-review-fable.md if it exists and
apply its findings; (2) PR the branch; (3) execute Plan A via
superpowers:subagent-driven-development — six tasks, full code in every step,
takes a steady-state ingestion run from ~77 minutes to seconds.

TWO LIVE PRODUCTION HAZARDS, both fixed by Plan A: the aggregation lock TTL is
65 min against ~77-min runs (saved today only by tick alignment), and 3.1% of
item_exchange contracts serve zero items, which is impossible legitimately.

CONSTRAINTS: work in worktrees off origin/dev; explicit git -C / cd every call
(cwd resets); never `pdm run dev`; serialize pytest with a dedicated
DATABASE_URL_TESTS database; inline env vars, never `env $VARS cmd` (zsh does
not word-split); uvicorn --workers 1 (DEPLOY-2); no secrets in argv/chat/logs;
Conventional Commits; publication PRs omit --delete-branch (head is dev); time
deploys just after an ingestion run completes, since migrations run pre-deploy
with a 30s lock_timeout and can collide with an in-flight run.

ESI FACTS (measured 2026-07-27, don't re-derive): public contract lists carry a
1800s cache TTL, regenerated lazily per region; X-Pages is 34 for Jita and 2-3
for other hubs; churn is ~230 contracts/hour and is diurnal; a per-contract item
fetch costs ~95-100ms. ESI enforces BOTH a 100-errors/60s limit and per-group
token buckets keyed by source IP.
```
