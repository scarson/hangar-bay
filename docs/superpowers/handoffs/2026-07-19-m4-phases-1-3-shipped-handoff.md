# M4 Handoff — Phases 1+3 Shipped (2026-07-19)

ABOUTME: End-of-session handoff for the M4 execution session — phases 1 and 3 merged to dev, Phase 0 spike still pending (now agent-runnable), what the continuation session does and in what order.
ABOUTME: Authoritative state lives in the plan (2026-07-18-m4-production-readiness.md, Living Document) and the audit dirs; this file is orientation + the continuation prompt, not a second source of truth.

## Headline state

- **dev @ `e80103a`** (= closeout PR [#63](https://github.com/scarson/hangar-bay/pull/63)). **main still pre-M2** — the dev→main release PR has NOT been opened; it will carry M2+M3+M4 phases 1+3 (a large publication PR per `docs/git-strategy.md` §Release branch).
- **Merged this session:** Phase 1 (PR [#56](https://github.com/scarson/hangar-bay/pull/56), merge `6885b67`), Phase 3 (PR [#60](https://github.com/scarson/hangar-bay/pull/60), merge `86a56c6`), plan closeout (PR #63, `e80103a`).
- **Open PR not ours:** [#62](https://github.com/scarson/hangar-bay/pull/62) `claude/c901-run-aggregation` — another session's refactor of `run_aggregation` complexity. **Seam:** our merged freshness recording rewired exactly that function (counters, `_record_run_outcome`, lock-context yield); #62 predates it and MUST rebase over our changes. That's the other session's job per git-strategy; do not merge #62 for them, but if asked, the freshness semantics they must preserve are pinned by `test_freshness_*` in `tests/services/test_background_aggregation.py`.
- **No live worktrees from this session** (phase-1/phase-3/closeout all removed; branches deleted after merge). The handoff branch `claude/m4-handoff` carries this doc + plan/pitfalls updates.
- **Local scratch cleaned:** spike Docker image removed, scratch test DBs dropped, dev Valkey lock cleared after the one prod-shaped boot smoke.

## What shipped (pointers, not narrative)

- Plan (Living Document, all banners current): `docs/superpowers/plans/2026-07-18-m4-production-readiness.md` — Execution Status table has per-phase ship SHAs; Deviations D-1..D-10; Discoveries (cp314 wheel gap, boot-time Valkey/`scheduler.start()` crash posture, stale-citation note).
- Phase 1 review record: `docs/audits/m4-phase1-review/` (3 lenses + codex round; 7+2 confirmed findings, all applied).
- Phase 3 review record: `docs/audits/m4-phase3-review/summary.md` (3 lenses + two default-model codex rounds + the delegated **codex 5.6-Sol high merge gate: PASS**).
- Docs-based Render verification (the Phase 0 substitute): `docs/audits/m4-recon/render-docs-verification-2026-07-18.md` + `render-docs-verification/` lane files. `docs/audits/m4-recon/render-spike-results.md` is **reserved for the real spike** — do not write it from docs.
- New pitfalls: DEPLOY-1, DEPLOY-2, ENV-8 (`docs/pitfalls/implementation-pitfalls.md`).

## Decisions made late in the session (easy to lose)

1. **Sam removes `:443` from the prod EVE callback** (portal edit, his action) → at 2b, `ESI_SSO_CALLBACK_URL` is the clean `https://hangarbay.app/api/v1/auth/sso/callback`. Verify the portal edit actually landed before the value is entered (plan Deviation D-3, resolved).
2. **`RENDER_API_KEY` location:** the MAIN checkout's gitignored root `.env` (`/Users/sam/Code/hangar-bay/.env`, 1Password Environments export). Worktrees never have it (pitfall ENV-8). The Phase 0 spike is therefore **agent-runnable now** via the curl+API patterns with per-Bash-call sourcing; the Render MCP additionally needs the export at Claude Code launch.
3. **Merge-authority delegation (Phase 3 only, consumed):** Sam delegated the Phase 3 merge to a codex 5.6-Sol high gate + green CI. That delegation was for PR #60 and is DONE — it does not automatically extend to the release PR or future PRs; default merge authority reverts to `docs/git-strategy.md` §Merge authority unless Sam says otherwise.

## Operational guardrails learned this session (persisted, listed for orientation)

- `codex review` rejects `-m`; override the model with `-c model="gpt-5.6-sol"`. Sol at high needs **>9 min** on repo-size diffs — run it detached (`nohup … &` + a Monitor on the PID), not under Bash's 600 s cap.
- A `CONFLICTING` PR gets **no** `pull_request` CI runs at all (GitHub can't build the test-merge commit). Silent missing checks ⇒ rebase, don't wait on Actions.
- dev moves fast when parallel sessions are active (four PRs landed mid-flight this session): after CI goes green, merge immediately; expect rebases and re-run full gates after each (both of ours were keep-both resolutions).
- Workflow-tool runs: check the `<failures>` block before trusting an empty result — a spend-limit or classifier outage can error every subagent and return `{confirmed: []}` that looks like a clean review.
- Backend suite: serialize runs (shared test DB) and give each worktree its own `DATABASE_URL_TESTS` database name. Local compose creds are `hangar_bay_user`/`hangar_bay_password`/db `hangar_bay_dev` (committed dev defaults, not secrets).
- ENV-3 hygiene after any dev-DB-touching boot (e.g. the Docker smoke): `docker exec hangar_bay_valkey valkey-cli DEL "hangar-bay:aggregation:lock"`.

## Priority queue for the continuation session

1. **Phase 0 empirical spike** (plan Task 0.1, probes P1–P6) — agent-runnable now; gates 2b. Verdict decides Topology A (shipped render.yaml) vs Appendix B (in-container Caddy, fully specified). P2b also records the real assigned onrender.com hostname for the rewrite destination.
2. **If the verdict is B** (or the hostname differs): branch → fix `render.yaml` (+ Dockerfile for B) → PR to dev (Routine) BEFORE the release PR.
3. **dev→main release PR** (git-strategy §Release branch). Expect deploy.yml's first `workflow_run` firing on main to fail at the deploy step (no service-ID secrets yet) — by design, don't chase it (plan Phase 4 Step 0).
4. **Support Sam through 2b** (blueprint apply; secrets generated BEFORE the flow; hostname check; DNS; service-ID Actions secrets) and confirm the GH Actions secret `RENDER_API_KEY` + repo variable `PROD_ORIGIN` exist.
5. **Phase 4 Steps 1–2, 4** (workflow_dispatch deploy, `/api/v1/ready` verification, rollback drill). **Step 3 (live SSO login on prod) is Sam's — the M4 exit criterion.**

Blocked-on-Sam at time of writing: portal `:443` edit; GH secrets/variable; 2b itself; Phase 4 Step 3. Everything else above is agent work.

## Continuation prompt (paste-ready)

```
You are continuing the M4 production-readiness execution for Hangar Bay
(FastAPI + React → Render). Phases 1 and 3 are MERGED to dev; your mission is
the remainder: empirical spike → (topology fix if needed) → release PR →
2b/Phase-4 support. Read CLAUDE.md and docs/pitfalls/ first (ENV-8, DEPLOY-1/2
are new); skill routing is mandatory — superpowers:executing-plans for plan
execution, superpowers:test-driven-development for ANY production-code change,
superpowers:verification-before-completion before claiming anything done.

AUTHORITATIVE DOCUMENTS (priority order):
- Plan (LIVING DOCUMENT — maintain its banners/table/Deviations/Discoveries as
  you work): docs/superpowers/plans/2026-07-18-m4-production-readiness.md
- Spec: docs/superpowers/specs/2026-07-18-m4-production-readiness-design.md
  (§4 topology, §5 migration rules, §8.2 freshness semantics are binding)
- Handoff (orientation + seams):
  docs/superpowers/handoffs/2026-07-19-m4-phases-1-3-shipped-handoff.md
- Docs-based Render verification (what the spike must still prove empirically —
  P1 POST pass-through and P2 trailing-slash are UNDOCUMENTED, docs could not
  settle them): docs/audits/m4-recon/render-docs-verification-2026-07-18.md

ULTRACODE + MODEL ROUTING (standing): ultracode
Use the Workflow tool for substantive multi-agent work (adversarial reviews,
multi-lens verification, doc sweeps); tens of agents max; persist every
analysis/review subagent's findings per ORCH-1 (docs/git-strategy.md §Output
persistence) with ABSOLUTE paths, committed wave-by-wave. Routing: you (Fable)
hold the main loop and correctness-critical review rounds; default Opus for
execution/review subagents; Sonnet for mechanical tasks (codegen, formatting).
Check the Workflow result's <failures> block before trusting an empty result.
Repo policy: meaningful PRs get a codex adversarial review before merge
(model_reasoning_effort=high — xhigh times out; `codex review` takes the model
via -c model="..." not -m; gpt-5.6-sol at high needs >9 min, run detached).

CREDENTIALS (pitfall ENV-8): RENDER_API_KEY is in the MAIN checkout's
gitignored root .env (/Users/sam/Code/hangar-bay/.env — 1Password Environments
export; worktrees NEVER have it). For curl against api.render.com, source it
inside EACH Bash call: `set -a; . /Users/sam/Code/hangar-bay/.env; set +a`.
NEVER cat/echo/print that file or variable, never copy it anywhere, never
commit it. If this session was launched with the export, the Render MCP works
too — prefer it for reads; the key is ACCOUNT-wide and the MCP can do
destructive ops: create only free-tier spike resources, never touch billing,
tear the spike down when done (plan Deviation D-2 authorizes Sam's real
account for the spike).

YOUR MISSION, in order:
1. Phase 0 spike — plan Task 0.1 exactly (probe app in a scratch dir OUTSIDE
   the repo, throwaway GitHub repo, free-tier web service + static site +
   free Postgres, probes P1–P6, teardown). Write
   docs/audits/m4-recon/render-spike-results.md with the TOPOLOGY verdict
   (A if P1 AND P2 pass exactly, else B) and commit it. Record the actual
   assigned onrender.com hostname (P2b).
2. If verdict is B: implement Appendix B (in-container Caddy — fully specified
   in the plan) on a branch, PR to dev (Routine, codex-reviewed, auto-merge on
   green). If A but the hostname differs from render.yaml's rewrite
   destination: fix the destination the same way. Update plan Deviations.
3. Open the dev→main release PR per docs/git-strategy.md §Release branch
   (publication PR carrying M2+M3+M4 phases 1+3 — main is still pre-M2).
   Follow that section's merge-authority rules; deploy.yml's first firing on
   main FAILS at the deploy step by design (no service-ID secrets yet).
4. Surface to Sam, in plain session text (NEVER AskUserQuestion dialogs — his
   client hides surrounding text): the 2b checklist (plan Phase 2b; secrets
   generated BEFORE the blueprint flow; verify the EVE portal :443 removal
   landed; hostname check; DNS; RENDER_API_SERVICE_ID/RENDER_STATIC_SERVICE_ID
   Actions secrets; GH secret RENDER_API_KEY + variable PROD_ORIGIN).
5. After 2b: Phase 4 Steps 1-2 and 4 (workflow_dispatch deploy of the released
   SHA, /api/v1/ready verification, rollback drill). Step 3 (Sam's live SSO
   login on the prod origin) is the M4 exit criterion — record his results in
   the plan and close the milestone.

CONSTRAINTS: work in your own worktree (git fetch origin dev; git worktree add
.claude/worktrees/<slug> -b claude/<slug> origin/dev). Conventional Commits
every commit; commit audit artifacts wave-by-wave. NEVER run `pdm run dev`
(ENV-2/ENV-3: every boot wipes and re-ingests the dev DB; pdm run pytest is
safe but SERIALIZE runs and use a dedicated DATABASE_URL_TESTS db name —
shared-DB contention). uvicorn stays --workers 1 everywhere (in-process
scheduler, DEPLOY-2). No secrets in argv/chat/logs/git. Check `gh pr list`
before any merge (one-writer rule); PR #62 (run_aggregation C901 refactor,
another session) must rebase over the merged freshness recording — theirs to
handle, but don't collide with it. A CONFLICTING PR gets no pull_request CI
runs — silent missing checks mean rebase. If a spike probe or API shape
contradicts the plan, follow reality, record a Deviation, keep going; STOP
only for genuine scope forks or anything requiring Sam's accounts/billing/
portal beyond what D-2 authorizes.
```

## Adversarial review of this handoff

- **Round 1 — naive fresh agent (3 findings applied):** added the glossary-free framing (spelled out 2b, P1/P2, Topology A/B inline where first used); added compose dev creds + test-DB-name guidance; made the #62 seam self-contained (what it is, whose job, which tests pin our semantics).
- **Round 2 — recency-bias audit (2 applied):** surfaced the mid-session merge-authority delegation as consumed-and-not-standing (it would otherwise read as a standing rule); restored the boot-time `scheduler.start()` crash posture pointer (Discovery in the plan) which only late-session context carried.
- **Round 3 — seam auditor (3 applied):** PR #62 vs freshness recording; release PR carrying M2+M3+M4 (main is pre-M2 — a fresh agent would otherwise assume a small diff); render.yaml's placeholder hostname vs P2b/2b verification chain.
- **Round 4 — operational guardrails (2 applied):** persisted the codex model-override/Sol-timing and conflicted-PR-CI rules into the guardrails section AND the continuation prompt (they were only in session learnings); confirmed ENV-8 landed in pitfalls with the full checklist rather than living here alone.
- **Round 5 — loss-averse audit (2 applied):** the `/metrics` constant-time-compare hardening idea (refuted-as-immaterial this round, parked — recorded in the phase-3 review summary's refuted list, referenced from the plan's M5-adjacent notes); `postgresMajorVersion "17"` vs available 18 flip-at-2b note (lives in the docs-verification file; now also in the 2b support step framing).
- **Round 6 — credential-handling auditor (session-specific; 2 applied):** this session's defining failure was a credential-location trap, and the continuation prompt hands a live account-wide key to an autonomous agent. Verified the prompt (a) never instructs reading/printing the file, sources per-call only, and scopes Render actions to free-tier spike resources + teardown per D-2; (b) states the MCP-only-at-launch limitation so the agent doesn't burn time "fixing" a dead MCP mid-session. Tightened both wordings.
- **Round 7 — holistic top-to-bottom re-read (1 applied):** confirmed doc order tells one story (state → decisions → guardrails → queue → prompt); deduplicated the `:443` decision (was stated three times, now decision-section + prompt only). Final pass through rounds 1–7 after fixes: zero material findings.
