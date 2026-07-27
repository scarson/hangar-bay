# M5 Handoff — Plan A Shipped and Released, Plan B Ready to Plan (2026-07-27)

ABOUTME: End-of-session handoff for the Plan A execution session of 2026-07-27 — six tasks + two codex-driven fixes merged in PR #94, published to production in PR #95, deploy verified live.
ABOUTME: Authoritative state lives in the Plan A plan's Execution Status/Deviations/Discoveries and docs/pitfalls/; this file is orientation, seams, the deploy record, and the Plan B continuation prompt.

## Headline state

- **Production LIVE** at `https://hangarbay.app`, `main` @ **`7a95118`** (release PR [#95](https://github.com/scarson/hangar-bay/pull/95): #91 delisted detection + #93 fileConfig fix + #94 Plan A). All three migrations applied in one pre-deploy transaction; deploy + smoke green at 08:26Z.
- **Post-deploy acceptance: PENDING at handoff-write time.** The boot-time ingestion run died in 3s on a transient Valkey connection refusal (`Error 111`, before Valkey accepted connections; lock released cleanly, scheduler intact). First real run on new code: **09:25:00Z tick**. Verify with: `/ready` (`last_ingest_outcome: success`, `data_stale: false`, run duration = stamp time − 09:25:00Z, expect **under ~5 min**) and the Render log line `Fetched items for N contracts (M skipped as already enriched)` — expect N in the hundreds-to-~1,800 (churn + persistent-failure set; that band is the retry loop working, NOT skip-known failing), M ≈ 44k. The pre-deploy `[requeue]` counts (zero-item vs 1000-multiple split) are in the 08:26Z deploy's pre-deploy logs on the Render dashboard — the first real read on the zero-item mechanism; record them here when read.
- **`dev` @ `56dc96f`** (the #94 merge). No open PRs beyond this handoff's own docs PR; no unmerged work branches.
- Plan A is **fully executed and released**: `docs/superpowers/plans/2026-07-27-ingestion-correctness-and-cost.md`. Read its **Execution Status, Deviations (3), and Discoveries (10)** before touching ingestion — they are the authoritative record of what shipped differently from the written plan and why.

## What shipped this session (pointers, not narrative)

| Artifact | Where |
|---|---|
| Plan A implementation (6 tasks, 3 phases, ~25 recorded mutations) | PR [#94](https://github.com/scarson/hangar-bay/pull/94), merged `56dc96f` |
| Codex-driven fixes: ship-flag clear w/ unresolved-category exclusion; unresolved category ⇒ ENRICHMENT_INCOMPLETE | same PR (final commits); codex disposition table is a PR comment |
| fileConfig caplog fix (ordered-run hazard) | PR [#93](https://github.com/scarson/hangar-bay/pull/93) |
| Release + deploy record | PR [#95](https://github.com/scarson/hangar-bay/pull/95); deploy saga in this doc §Operational guardrails |
| Plan A living record (Deviations/Discoveries/status) | the plan doc, top section |
| Session memory | `~/.claude/projects/-Users-sam-Code-hangar-bay/memory/plan-a-executed-pr94.md` |

## Plan B — designed, NOT planned. What it now carries

Plan B = pipeline restructure: **discovery/enrichment split, `Expires`-driven scheduling, shared rate-limit governor**. Design: `docs/audits/m5-recon/ingestion-clean-sheet-design.md` (3 adversarial review rounds; still authoritative). Plan A execution ADDED six items to Plan B's docket — all recorded in Plan A's Deviations/Discoveries; summary:

1. **ETag-cache removal on item pages now carries CORRECTNESS weight, not just cost.** The 304-evicted-body mid-walk truncation can silently truncate a multi-page fetch — and post-ship-flag-work, that path can **actively clear a correct ship flag** (page-1-only read, ship on page 2 → flag False, COMPLETED, stamped, skip-frozen — i.e. COMPLETED at the current version, so skip-known never re-fetches it). Interim mitigation candidate if Plan B slips: treat "ETag present, cached body absent" as a cache miss in `_read_etag_cached_page`.
2. **The governor must read `X-Esi-Error-Limit-Reset` for 420** — 420 carries no Retry-After (only 429 does); today every 420 takes the 0.5s/1.0s fallback schedule inside a ≤60s window (a rate reduction, not the final answer). A user-facing client arguably shouldn't retry 420 at all — needs 420/429 discrimination, explicitly governor-phase.
3. **Dead-code cleanup:** `ESINotModifiedError` is raised nowhere in production (real 304s resolve inside `get_esi_data_with_etag_caching`); tests stubbing it model a shape the client never produces. Clean up with the ETag decision.
4. **Per-request wait budget** (the shipped budget is per-wait): a 420 under the 1.0s request-scoped budget still sleeps ~1.5s per ESI call.
5. **If Plan B changes the scheduler interval** (Expires-driven scheduling will): re-derive the lock-TTL / `max_instances` math first — the runbook comment on `ENRICHMENT_VERSION` in `services/background_aggregation.py` documents that `max_instances=1` (now explicit and test-pinned) is what actually serializes runs, safe only while a run stays under 2× the interval.
6. **Queue scans need no new index** — a `PENDING_ITEMS` discovery scan is served by the baseline single-column status index; the measured evidence for dropping the composite is in the plan's Deviations.

## Not Plan B but adjacent (unowned)

- **Plan C — Discord alert delivery** (SSRF constraints designed): the other half of the alert user story. Do Plan C first if the corp-trial date is near (the prospective EVE corp evaluating Hangar Bay — see the trust & shareability design) — delivery is the binding constraint on the alert story.
- **Freshness surface** (`data_as_of`/`data_stale` in the UI): design changed underneath it; the freshness record still lives in an evicting cache pending the `volatile-lru` decision (below). Today's boot illustrated the adjacent failure: a run that dies before writing the record leaves `/ready` at `null`/`stale` until the next tick.
- **Retiring the always-`"unknown"` `status` field**: small, independent, unblocked.
- Minor recorded-not-fixed (all in plan Discoveries or code comments): partial group payload (`{"name": ...}`, no `category_id`) reads as resolved-non-ship (unreachable per ESI's contract); excluded-item categories can stay NULL on COMPLETED contracts (cosmetic; comment documents it); the ENRICHMENT_INCOMPLETE log doesn't split type vs category failures and has no metric.

## Deferred items with unblock conditions

1. **Sam's live SSO login** — M4's last exit criterion. Needs an EVE character; nothing agent-side.
2. **Key Value `maxmemoryPolicy` → `volatile-lru`** — needs Sam in the Render dashboard; unblocks the freshness-record eviction fix (`render.yaml` is documentation-of-record and must be mirrored manually). Analysis: `docs/superpowers/handoffs/2026-07-27-m5-ingestion-handoff.md` §Deferred item 2 (volatile-lru vs move-to-Postgres, with the recommendation).
3. **Spike-repo deletion** (`scarson/hb-render-spike-m4`) — needs a gh token scope Sam has.
4. **After any future `ENRICHMENT_VERSION` bump:** expect one ~80-min resweep run and the end-of-run "Aggregation lock token mismatch on release" warning (expected then, not an incident) — runbook on the constant.
5. ~~Discord embed check~~ — **DONE** (Sam's screenshot 2026-07-27: preview renders fully; Cloudflare is not blocking Discordbot).

## Operational guardrails accumulated this session

**Deploy mechanics (learned live during the #95 release):**
- **Production deploys are triggered by the CD workflow** (`.github/workflows/deploy.yml`, `workflow_run` on CI@main) calling the Render API — Render autoDeploy is not the path. **Redeploy/rollback without a new commit:** `gh workflow run deploy.yml --ref main -f sha=<full-sha>` (the `workflow_dispatch` input exists exactly for this).
- **A pre-deploy failure against an in-flight ingestion run looks like:** `pre_deploy_failed` ~38s after `pre_deploy_started` (30s `lock_timeout` + overhead), deploy aborts, old code keeps serving. The fix is timing, not code: wait for the run to end and redeploy. Confirmed empirically — the same migrations applied cleanly on the idle-window retry.
- **Timing the window:** poll `/ready` `last_ingest_age_seconds`; a fresh stamp (< ~10 min) opens the idle window. Pre-Plan-A cadence: runs start every ~120 min and take ~77+ (observed: a run ran ~124 min this morning — the ~77-min figure is an average, not a bound). Post-Plan-A runs are minutes, so the window is nearly always open; this matters again mainly for version-bump resweeps.
- **A boot-time ingestion run can die on Valkey not yet accepting connections** (`Error 111` in `_fetch_regions` ~3s after start). Harmless: lock releases, APScheduler keeps the schedule, next tick runs it — but `/ready` shows `null`/`data_stale: true` until then, and the failed run writes no freshness record (the write needs the same dead connection). Don't diagnose this as the DEPLOY-3 jobstore outage — the scheduler is alive; check for the next tick line.

**Credentials / API (ENV-8 extensions):**
- **The 1Password-managed root `.env` can transiently empty MID-SESSION** and later repopulate. A sourced var of length 0 does not mean the key is gone — before concluding, check the file: `awk -F= '/^[A-Z]/ {print $1, length(substr($0, index($0,"=")+1))}' .env` (names and lengths only, never values). Retry after a minute.
- **The Render logs API requires `ownerId`** (`GET /v1/logs?ownerId=tea-…&resource=srv-…`); without it you get empty results that look like "no logs", not an error — a TEST-15 instrument-blindness shape. Get ownerId from the service object. Pre-deploy command output is NOT under the service resource (deploy events at `/v1/services/{id}/events` give status + timing; the command's stdout is dashboard-only).
- **The Render MCP needs launch-time env** (ENV-8); in a session launched without it, the REST API with per-call sourcing works fine.
- **Render resource ids** (stable, save the lookup): backend web service `srv-d9fippfavr4c73cbi1d0`, static site `srv-d9fi26favr4c73ca2qa0`, owner `tea-d9dvc8t7vvec73eq2ktg`.

**Test/infra (from the execution phase):**
- **A fresh scratch test DB must be `CREATE DATABASE`d before first use** — nothing in the suite creates it; missing DB produces ~14 misleading `InvalidCatalogNameError` setup errors on top of real failures.
- **Parallel agents need disjoint scratch DBs AND disjoint Valkey DB numbers** (e.g. `CACHE_URL_TESTS=redis://localhost:6379/3` for a second agent).
- **`gh pr merge --delete-branch` from a worktree fails its LOCAL cleanup** when the base branch is checked out elsewhere; the remote merge still succeeds — verify with `gh pr view --json state`, don't retry.
- **BSD mktemp needs trailing Xs** — `mktemp foo-XXXXXX.txt` creates the literal filename once, then fails "File exists".
- **codex on this repo:** `high` timed out twice on a ~1,200-line diff; `medium` completed. Bound the diff (exclude docs) and expect to drop effort.
- **Rebasing an execution branch rewrites the SHAs in the plan's Execution Status table** — remap by commit subject after rebasing; prose references to pre-rebase SHAs stay as historical records.

## Process notes that earned their keep (for the next plan execution)

- **Two-stage per-task review + 3-round phase batch reviews found real defects at every altitude:** a plan-mandated index that measurement proved useless; the 3.1%→3.9% arithmetic slip; a hardcoded-literal mutation surviving 464 tests; the unclamped `float(Retry-After)` sleep.
- **Ask implementers to VERIFY the stated safety argument, not just apply the fix.** The coordinator-specified naive ship-flag clear was empirically refuted by the implementer (it would have cleared genuine flags on a transient group blip and skip-frozen them); the correct fix exposed the deeper COMPLETED-despite-unresolved-category gap.
- **Codex disposition pattern:** 4 of 5 findings were already-recorded decisions; the value was the 5th. Cross-model review pays at the margin, not the median.

## Priority queue

1. **Read the post-deploy acceptance numbers** (if not yet recorded here): `/ready` outcome + run duration after the next tick; `Fetched items for N (M skipped)` and the `[requeue]` counts from Render logs/dashboard. Update this doc's Headline.
2. **Plan B planning**: `/superpowers-plus:writing-plans-enhanced` from the clean-sheet design + the six carried items above, then `/superpowers-plus:plan-review-cycle` before executing. Decide Plan B vs Plan C order by trial-date proximity.
3. Plan C planning (or first, per above).
4. Sam: SSO login, `volatile-lru`, spike-repo deletion.

## Adversarial review of this handoff

- **Round 1 — naive fresh agent (4 applied):** file-pathed the volatile-lru analysis reference (two handoffs now share the 2026-07-27 date); glossed "skip-frozen" and "the corp trial" at first use; confirmed pitfall IDs are named with enough context to route a reader who hasn't memorized them.
- **Round 2 — recency-bias audit (1 applied):** the read-side chunk-boundary lesson (a `break`-after-first-chunk mutation survived the whole suite) lived only in commit messages and a plan Discovery — promoted into testing-pitfalls TEST-11 as an explicit reads-too extension.
- **Round 3 — seam auditor (3 applied):** verified the merged `claude/m5-plan-a-ingestion` remote branch was already deleted; refreshed the stale session-memory file (still said "#94 awaiting merge"); verified the plan⇄handoff acceptance cross-reference points both ways consistently (plan says results land here; here says tick the plan's last two Verification items).
- **Round 4 — operational guardrails auditor (2 applied):** the deploy-collision mechanics were transcript+handoff-only — promoted to implementation-pitfalls **DEPLOY-4** (with the ~38s signature and the `workflow_dispatch` redeploy path, full completeness checklist); ENV-8 extended with the transient-empty `.env` mode and the names/lengths-only inspection command.
- **Round 5 — loss-averse auditor (1 applied):** Render resource ids (backend service, static site, owner) existed only in the transcript — recorded in §Operational guardrails.
- **Round 6 — session-specific: release-under-interruption auditor (2 applied).** This session's character: a live release where the human merged early, credentials died mid-flight, and acceptance spans the handoff boundary — so the failure mode is freezing a MOVING target into prose. Audited every time-sensitive claim for either a timestamp or a self-verification path: reworded "no open PRs" (false the moment this doc's own PR opens); confirmed the PENDING acceptance block carries its own verification recipe and the continuation prompt's FIRST step re-checks it rather than trusting this doc.
- **Round 7 — holistic top-to-bottom re-read (2 applied):** confirmed the Headline's acceptance bullet states the expected-band framing ("~1,800 is the retry loop working, not skip-known failing") where the number will be read, not only in the continuation prompt; un-froze "dev @ 56dc96f" in the continuation prompt (stale the moment this doc's own PR merges). Full re-pass after all fixes: zero material findings.

## Continuation prompt

```
You are picking up Hangar Bay (FastAPI + React → Render) post-Plan-A. Production
is LIVE at https://hangarbay.app, main @ 7a95118 (release PR #95 = #91 delisted
detection + #93 fileConfig + #94 Plan A ingestion correctness/cost). dev is at
or just past 56dc96f (the #94 merge; this handoff's own docs PR merges on top).
No unmerged work branches.
Read CLAUDE.md and docs/pitfalls/ first. Skill routing is mandatory.

AUTHORITATIVE STATE (priority order):
- Plan A plan (Execution Status, 3 Deviations, 10 Discoveries — the record of
  what shipped differently and why):
  docs/superpowers/plans/2026-07-27-ingestion-correctness-and-cost.md
- This handoff (orientation, deploy mechanics, Plan B docket):
  docs/superpowers/handoffs/2026-07-27-plan-b-handoff.md
- Ingestion design (authoritative for Plan B):
  docs/audits/m5-recon/ingestion-clean-sheet-design.md

FIRST: check post-deploy acceptance if this handoff's Headline still says
PENDING — /ready should show last_ingest_outcome success with runs taking
minutes; the "Fetched items for N contracts (M skipped)" Render log line should
show N in the hundreds-to-~1,800 (churn + persistent-failure retry set — that
band is the retry loop working, NOT skip-known failing) and M ≈ 44k. Record the
numbers in the handoff Headline and tick the last two Verification items in the
Plan A plan.

NEXT: plan Plan B via /superpowers-plus:writing-plans-enhanced from the
clean-sheet design PLUS the six carried items in this handoff §Plan B (ETag
removal now correctness-weighted; governor reads X-Esi-Error-Limit-Reset for
420; ESINotModifiedError cleanup; per-request budget option; re-derive
lock-TTL/max_instances math before changing the scheduler interval; no new
queue index needed). Then /superpowers-plus:plan-review-cycle before executing.
Consider Plan C (Discord alert delivery — designed, SSRF constraints in the
design) FIRST if the trial date is near: delivery is the binding constraint on
the alert story.

CONSTRAINTS: work in worktrees off origin/dev; explicit git -C / cd every call
(cwd resets); never `pdm run dev`; each pytest agent needs its OWN
DATABASE_URL_TESTS scratch DB (CREATE DATABASE it first) and its own Valkey DB
number; inline env vars, never `env $VARS cmd` (zsh doesn't word-split);
uvicorn --workers 1 (DEPLOY-2); no secrets in argv/chat/logs; Conventional
Commits; publication PRs omit --delete-branch (head is dev); time deploys just
after an ingestion run completes (pre-deploy migrations, 30s lock_timeout) —
redeploy without a commit via
`gh workflow run deploy.yml --ref main -f sha=<full-sha>`; verify migration
chains with `alembic heads`, never by listing filenames.

FACTS (don't re-derive): ESI public contract lists carry 1800s TTL, lazy
regeneration; X-Pages 34 Jita / 2-3 other hubs; churn ~230/hour, diurnal;
per-contract item fetch ~95-100ms; ESI enforces BOTH 100-errors/60s (420, no
Retry-After) and per-group token buckets keyed by source IP (429, Retry-After).
Zero-item rate: 15/384 ≈ 3.9% (the older "3.1%" in review-record docs was an
arithmetic slip). 420/429 are retried with waits clamped to 60s; request-scoped
clients carry a 1.0s per-wait budget. ENRICHMENT_VERSION bump = deliberate
corpus resweep (~80 min; expected token-mismatch warning at its end; runbook on
the constant).

STILL SAM'S: live SSO login (M4 exit criterion), Render Key Value
maxmemoryPolicy volatile-lru, spike-repo deletion.
```
