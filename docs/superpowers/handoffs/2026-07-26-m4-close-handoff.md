# M4 Close Handoff — Production Live, CD Green, One Exit Criterion Open (2026-07-26)

ABOUTME: End-of-session handoff for the M4 continuation sessions (2026-07-21 and 2026-07-26) — production shipped and verified, the Jul 23-26 scheduler incident fixed, and the single remaining M4 item plus the M5-candidate queue for a fresh session.
ABOUTME: Authoritative state lives in the plan (2026-07-18-m4-production-readiness.md, Living Document, D-11..D-15) and docs/pitfalls/; this file is orientation + the continuation prompt, not a second source of truth.

## Headline state

- **Production LIVE and healthy:** `https://hangarbay.app` — Render **ohio**, Docker web service (starter) + static site + **Postgres 18** (basic-256mb) + Key Value (free, allkeys-lru), custom domain + certs, SSO enabled (302 → EVE verified). Serving 40k+ contracts; ingestion healthy post-incident-fix.
- **`main` @ `5b403dc9`** (release PR [#79](https://github.com/scarson/hangar-bay/pull/79), 2026-07-26). Pipeline run **30215356899 was the first fully-green CD run** (deploy job: pinned deploy + Alembic pre-deploy + release verification; smoke job: 3/3 against prod). Three releases total this campaign: #66 (Jul 19), #74 (Jul 21), #79 (Jul 26).
- **`dev` @ `6205607`** = origin/dev: one unreleased change, PR [#80](https://github.com/scarson/hangar-bay/pull/80) (region-filter viewport sizing) — rides the next publication PR.
- **No live worktrees or branches from these sessions.** Four STALE worktrees from OLDER sessions exist under `.claude/worktrees/` (`amazing-tu-4fac04`, `drama-pass-implementation-ae2eeb`, `hangar-bay-frontend-rebuild-2e4fe7` — detached HEADs — and `m3-account-features`); per git-strategy §Red flags, investigate for uncommitted work before removing. Not this campaign's state.
- **M4 is one item from closed:** Phase 4 Step 3, Sam's live SSO login (see Deferred).

## What shipped (pointers, not narrative)

- **Plan** (all banners/Deviations current through D-15): `docs/superpowers/plans/2026-07-18-m4-production-readiness.md`. Phase 0 ✅ (Topology A), Phase 2 ✅ (2b via API — D-12/D-13), Phase 4 Steps 0/1/2/4 ✅ with drill durations, Step 3 partial.
- **Spike record:** `docs/audits/m4-recon/render-spike-results.md` (P1–P6 raw outputs; 201/202 deploy-API semantics; `deactivated` = also superseded; newest-first list). PG18 assessment: `docs/audits/m4-recon/postgres-18-upgrade-assessment.md`.
- **Jul 23-26 incident** (scheduler silently dead 3.6 days): full record in plan **D-15**. Root cause: APScheduler's RedisJobStore keys evicted by the `allkeys-lru` Key Value under ETag-cache memory pressure. Fixes shipped in release #79: PR [#76](https://github.com/scarson/hangar-bay/pull/76) (MemoryJobStore; aggregation lock TTL = scheduler interval + 300 s margin; mutation-verified tests) and PR [#77](https://github.com/scarson/hangar-bay/pull/77) (CD smoke pagination spec raced `keepPreviousData` placeholder rows — deterministic sync per TEST-2).
- **New pitfalls:** DEPLOY-3 (never colocate durable coordination state with an evicting cache), TEST-13 (Playwright testMatch regexes match full paths — worktree names can hijack them), plus Jul-21-era DEPLOY entries. `docs/pitfalls/`.
- **Infra facts of record:** service IDs and the Render API landmines (preDeployCommand is create-time-only; its executor mangles quotes AND `-c` flags → use `python -m alembic upgrade head` + `ALEMBIC_CONFIG` env var) — plan D-12/D-14. render.yaml is documentation-of-record (blueprint never applied; keep it synced manually with API/dashboard changes).

## Deferred items (unblock condition + owner)

1. **M4 exit criterion — live SSO (Sam).** Unblocks when Sam creates an EVE character (free Alpha account; creation happens in the game client, not the web) and runs the spec §9.3 flow on `https://hangarbay.app`: login → consent → callback → character in header → `/me` 200 → logout, plus one consent-denial (`?sso=denied`, no session). His 2026-07-21 attempt verified everything up to EVE's character-selection gate. Record results in plan Phase 4 Step 3 and close the milestone.
2. **Watchlist lock TTL (Sam decision).** `WATCHLIST_MATCH_LOCK_TTL_SECONDS` (900) equals its interval — same defect shape as the fixed aggregation lock, low exposure. Flagged in PR #76's body; widen or accept.
3. **Release PR #80's region-filter fix.** Unblocks with the next dev→main publication PR (any future release carries it; not urgent alone).
4. **Spike-repo deletion (Sam).** `gh auth refresh -h github.com -s delete_repo && gh repo delete scarson/hb-render-spike-m4 --yes` — the session token lacks the scope.

## Operational guardrails accumulated (persisted; listed for orientation)

- **1Password root `.env` empties when its read-approval prompt is dismissed** — reads trigger the 1P prompt; a dismissed prompt yields a 0-byte read that mimics a revoked `RENDER_API_KEY` (Render returns bare 400s on an empty bearer). Ask Sam to approve, then batch API calls into the approval window. (Also in memory.)
- **Bash cwd resets between tool calls** (especially after worktree removals) — use `git -C <path>` / explicit `cd` in EVERY call; a stray commit landed on local `dev` once and only GitHub branch protection stopped the push (recovered via cherry-pick + reset).
- Don't name worktrees with substrings matching Playwright `testMatch` regexes (TEST-13; the regexes are now anchored to `e2e\/live-smoke`, but the principle stands).
- `status` is a read-only zsh variable — don't use it in monitor scripts.
- deploy.yml's smoke job uploads no artifacts on failure — diagnosis needed local reproduction; adding an artifact-upload step is a cheap improvement (M5-adjacent, queued below).
- Local dev compose: the `postgres_db` volume holds pre-18 data — postgres 18 refuses it; drop the volume once (dev data is disposable, ENV-2).
- Don't run prod-lane smokes (or dispatch drills) while a deploy is in flight — restarts race the specs; serialize.
- Rolling back to a pre-#79 SHA revives the UNFIXED smoke spec in that checkout — a rollback's smoke job may fail spuriously even though the deploy+verification are sound (the spec fix lives in the repo at the deployed SHA, not on the service).
- `METRICS_TOKEN` (and any service env value) is recoverable via `GET /v1/services/{id}/env-vars` — values, not just keys; treat that endpoint's output as secret-bearing and never print it raw.

## M5 candidate queue (scoped-but-unstarted, from this campaign's residuals)

1. Scheduler split (standing M5 thread; the boot-time Valkey/`scheduler.start()` crash posture Discovery and the in-process-scheduler single-worker constraint both point here).
2. Ingestion observability (C901-campaign residual, sharpened by D-15: per-run progress/duration metrics, run-in-progress visibility — `/ready` can't distinguish "running" from "dead" between commits).
3. ESI 403 handling audit: Jul 23 logs show per-contract item fetches failing 403 (caught and logged per contract, run still succeeds). Are these expired contracts? Rate/ban signals? Worth understanding before they scale.
4. Uncapped-run resource posture: first runs take ~70 min (155k items) on a 512 MB starter instance; ETag caching makes steady-state cheap, but the Key Value free tier WILL keep evicting ETags under pressure (sessions/ETags evictable = accepted; scheduler state now safe). Revisit sizing when usage grows.
5. deploy.yml: upload Playwright artifacts on smoke failure.

## Priority queue for a fresh session

1. Whatever Sam brings (M5 kickoff, feature work, or the SSO close-out when his character exists).
2. If touching the backend: read `docs/pitfalls/` first — DEPLOY-1/2/3 and TEST-13 are new since the last handoff's snapshot.
3. Next release: bundle #80 + whatever ships next; publication PRs per git-strategy §Release branch (Review — publication, Sam merges, `--delete-branch=false`).

## Continuation prompt (paste-ready)

```
You are picking up Hangar Bay (FastAPI + React → Render) after the M4
production-readiness campaign. Production is LIVE at https://hangarbay.app
(Render ohio: docker web service + static site + Postgres 18 + Key Value;
SSO enabled; CD fully proven — first all-green pipeline run 30215356899 on
release 5b403dc9). Read CLAUDE.md and docs/pitfalls/ first (DEPLOY-1/2/3,
TEST-13, ENV-8 are recent); skill routing is mandatory.

AUTHORITATIVE STATE (priority order):
- Plan (Living Document; Deviations D-11..D-15 carry the 2b-via-API record,
  the Render API landmines, and the Jul 23-26 scheduler incident):
  docs/superpowers/plans/2026-07-18-m4-production-readiness.md
- Handoff (orientation + guardrails + M5 queue):
  docs/superpowers/handoffs/2026-07-26-m4-close-handoff.md
- Session memory: m4-remaining-on-sam (auto-loaded).

OPEN ITEMS: M4 closes on Sam's live SSO login (needs an EVE character —
game client, free); watchlist lock TTL decision (PR #76 body); PR #80's
region-filter fix awaits the next release; Sam deletes the spike repo.

CREDENTIALS (ENV-8 + new): RENDER_API_KEY lives in the MAIN checkout's root
.env (1Password Environments). Reading it triggers a 1P approval prompt on
Sam's Mac; a DISMISSED prompt yields an empty file (Render then 400s on the
empty bearer). Source per Bash call (set -a; . /Users/sam/Code/hangar-bay/.env;
set +a), never print values, batch calls into the approval window. render.yaml
is documentation-of-record — the blueprint was never applied; mirror any
infra change into it manually.

CONSTRAINTS: work in worktrees off origin/dev (never name one with a
Playwright testMatch substring — TEST-13); explicit git -C/cd every call
(cwd resets); never `pdm run dev`; serialize pytest with a dedicated
DATABASE_URL_TESTS db; uvicorn --workers 1 (DEPLOY-2); no secrets in
argv/chat/logs/git; Conventional Commits; publication PRs are Review-class
(Sam merges, --delete-branch=false); don't run prod smokes mid-deploy;
rollbacks to pre-#79 SHAs fail their smoke job spuriously (old spec) —
judge rollbacks by the deploy job + /ready commit.
```

## Adversarial review of this handoff

- **Round 1 — naive fresh agent (3 applied):** spelled out D-15/2b/Topology A inline at first use; added the game-client detail to the SSO deferral; expanded the stale-worktrees list with the investigate-first rule.
- **Round 2 — recency-bias audit (3 applied):** restored Jul-21-era items that late-session incident work had crowded out — the Render API landmines summary, the P2b un-suffixed-hostname result, and the local compose postgres-volume note (originally only in D-14).
- **Round 3 — seam auditor (3 applied):** #80-on-dev vs prod-release seam; the rollback-to-pre-#79-SHA smoke seam (old spec rides old SHAs); render.yaml-as-documentation-of-record drift seam (API changes must be mirrored manually).
- **Round 4 — operational guardrails auditor (2 applied):** promoted the zsh `status` variable trap and the don't-smoke-mid-deploy rule from transcript-only to the guardrails list; confirmed DEPLOY-3/TEST-13 live in pitfalls, not just here.
- **Round 5 — loss-averse audit (2 applied):** the ESI-403 open question and the deploy.yml artifact-upload improvement existed only in session text — both now in the M5 queue; METRICS_TOKEN recoverability (and its secret-handling caveat) captured.
- **Round 6 — production-operations auditor (session-specific; 2 applied):** this session uniquely operated LIVE production. Reviewed the handoff for operator-shaped gaps: added the explicit "judge rollbacks by deploy job + /ready commit" rule to the continuation prompt (an operator seeing a red smoke on a rollback would otherwise chase it), and verified every resource ID a future operator needs is reachable via plan D-12/D-13 rather than only in transcript.
- **Round 7 — holistic top-to-bottom re-read (1 applied):** tightened the headline so the one-open-item status is unmissable; confirmed doc order tells one story (state → shipped → deferred → guardrails → queue → prompt). Final full pass after fixes: zero material findings.
