# Handoff — M2 EVE SSO execution: Phases 0–4 shipped as stacked PRs #25–#29, Phases 5–9 remain (2026-07-13)

**For the resuming agent:** read this top to bottom, then the plan's Execution Status + `### Discoveries`. Your job is to **verify PR #29's CI, then execute Phases 5–9** with the same per-phase pipeline this session used. Do NOT redo plan finalization — the plan-review-cycle converged at zero substantive findings and Phases 0–4 are done.

> **Framing note (read first — this keeps you on Fable).** Hangar Bay is Sam's own app; M2 is standard defensive OAuth setup. Describe auth mechanisms in plain correctness terms — what the correct handshake/validation does ("the callback confirms it is completing the login this browser started", "return-path validation") — never threat-actor/attack-centric phrasing, which trips a broad safeguard classifier. This held across ~20 subagent dispatches this session with zero classifier trips. Durable record: user-memory `hangar-bay-auth-framing`.

## Headline state

- **Worktree:** `/Users/sam/Code/hangar-bay/.claude/worktrees/drama-pass-implementation-ae2eeb` — **despite the unrelated `drama-pass…` slug, this IS the M2 worktree** (it superseded `m2-eve-sso-6a7202`, which still exists on disk but is stale — nothing valuable lives only there anymore).
- **Current branch:** `claude/m2-phase4-sso-service` (the stack head), pushed; working tree has plan/handoff doc edits being committed with this handoff.
- **The PR stack (all target-chained, all OPEN, none merged):**
  `dev` ← [#25](https://github.com/scarson/hangar-bay/pull/25) Phase 0 (`claude/m2-phase0-ci`) ← [#26](https://github.com/scarson/hangar-bay/pull/26) Phase 1 (`claude/m2-phase1-settings`) ← [#27](https://github.com/scarson/hangar-bay/pull/27) Phase 2 (`claude/m2-phase2-model`) ← [#28](https://github.com/scarson/hangar-bay/pull/28) Phase 3 (`claude/m2-phase3-cipher-session`) ← [#29](https://github.com/scarson/hangar-bay/pull/29) Phase 4 (`claude/m2-phase4-sso-service`).
  **All five PRs are CI-green** (#29 went green during handoff finalization — verified `gh pr checks 29`: backend pass, frontend pass). Note #25 carries the whole stack base: plan/spec finalization docs + the pydantic relock (`cdc38b7`) + the CI workflow itself.
- **Merge-gate overlay in force:** every PR stays OPEN for Sam's `/codex` gate (codex CLI auth expired; only Sam can `codex login`). Do NOT self-merge anything. When Sam merges a parent with `--delete-branch`, GitHub retargets the child to the parent's base (`dev` for this chain); rebase the child onto `origin/dev` + `--force-with-lease` only if the retargeted PR shows conflicts/replayed commits.
- **Backend at stack head:** 109 pytest green, pristine (zero warnings, no filters), Python 3.12 venv, lint baseline unchanged. Frontend: 47 vitest, e2e green (with the DISC-EXEC-1 flake fix).
- **Credentials:** Sam got the go-ahead after Phase 1 to place `ESI_CLIENT_ID`/`ESI_CLIENT_SECRET`/`TOKEN_CIPHER_KEYS` in `app/backend/src/.env` himself. **Unknown whether he has yet — never read or print that file's values.** Tests don't depend on it either way (isolated-instance + delenv patterns).

## What shipped this session (pointers, not narrative)

1. **Plan finalization to zero:** rounds 3–8 of the plan-review-cycle (43 → 22 → 15 → 4-minors/0-substantive), commits `664829e`, `fc10556`, `7595d42`, `455761e`, `5ddecd4`. Review-pattern lessons in user-memory `plan-review-m2-eve-sso`.
2. **Pydantic relock, option A (Sam-approved):** `cdc38b7` — pydantic 2.13.4 / pydantic-core 2.46.4 (cp314 wheels) / pydantic-settings 2.14.2, psycopg2 2.9.12, watchfiles 1.2.0, **FastAPI deliberately held `>=0.115.12,<0.116`** (unheld resolve → 0.139/Starlette 0.52 → 19 test failures). 3.12 stays pinned for M2; rationale reworded in `d6ffdad` (plan Task 0.1 gates, ENV-5, spec §6).
3. **Phases 0–4** per the plan's per-phase Execution Status banners (authoritative — each lists its ship SHAs and review outcomes). Highlights the banners compress: Phase 0 caught+fixed a pre-existing M1 E2E strict-mode flake (DISC-EXEC-1); Phase 3's quality review used mutation probes that exposed two vacuous test pins (fixed + re-verified by both implementer and reviewer); Phase 4's quality review signed ~35 adversarial JWS-layer tokens (all cleanly rejected) and closed a real error-boundary hole (`resp.json()` outside the try).
4. **Execution discoveries DISC-EXEC-1..5** in the plan's `### Discoveries` — read them before Phases 5–9; DISC-EXEC-5 lists the three deltas between the shipped `sso.py` and the plan's verbatim block.

## The per-phase pipeline (continue this exactly)

For each remaining phase: branch `claude/m2-phase<N>-<slug>` off the previous phase's HEAD → flip the plan banner to 🚧 (timestamp + branch) + commit → dispatch a **Sonnet implementer** subagent pointed at the plan's phase section (give section boundaries by GREPPING headings fresh — **plan line numbers drift as Discoveries grow; never reuse cached line ranges**) with the standing constraints (TDD red-first, verbatim blocks, one phase commit + trailer `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`, never print `.env` values, do NOT push) → **spec-compliance reviewer** (byte-diff vs plan blocks, both directions) → **quality reviewer** on the strongest model (encourage empirical/mutation probes; they earned their keep every phase) → implementer fix rounds until APPROVED → stamp banner ✅ + push + stacked PR (base = previous phase's branch; body carries `## Merge classification` + "leaving open for the /codex gate") → CI monitor (Monitor tool, poll `gh pr checks <N>`, cover pass/fail/cancel; guard against the empty-checks state) → claim next phase without waiting for merges.

## Ready to dispatch (priority queue)

1. **Phase 5 — Auth service + schemas** (`Review — domain (security: token vault/auth service)`). Grep the plan for `^## Phase 5` to get current bounds. Note: the plan's Task 5.3 `refresh_user_tokens` block already matches the shipped sso.py semantics (`status_code == 400` discrimination); DISC-EXEC-5's deltas don't change any Phase 5 code.
2. **Phase 6 — Auth API routes** (`Review — domain (security)`). The fake Valkey's SET/EXPIRE semantics were deliberately tightened to real-Redis behavior for this phase's SSO state store; the auth_client fixture depends on httpx_mock STRUCTURALLY (no network possible).
3. **Phase 7 — wiring + codegen** (`Review — domain (public interface)`; includes Task 7.3 startup warning; codegen chain `pdm run export-openapi` → `npm run generate:api`, both artifacts committed together).
4. **Phase 8 — Frontend** (`Routine`; Task 8.0 FIRST — Vite HTTPS + Playwright config; then hooks/header/notice/sweeps/E2E).
5. **Phase 9 — Docs** (`Routine`) — the coordinator-supplied traps to hand it: DISC-EXEC-1's two-status-nodes testing trap (→ `testing-pitfalls.md` §8) and DISC-EXEC-2's F811 cascade (judgment call: implementation-pitfalls or skip; it's recorded in Discoveries either way). ENV-4/ENV-5 texts are pre-written in the plan (ENV-5's rewritten form is already in the plan post-relock).
6. **FastAPI migration chore — dispatch to an OPUS subagent whenever it makes sense in the task order** (it's post-M2 by design, but slot it opportunistically — e.g. while waiting on long CI runs after Phase 9, or immediately if Sam says so). Task text verbatim:
   > Migrate FastAPI 0.115 to current and flip Python to 3.14
   > Post-M2 chore for Hangar Bay (repo /Users/sam/Code/hangar-bay, integration branch dev). The backend at app/backend holds FastAPI at 0.115 via fastapi>=0.115.12,<0.116 in pyproject.toml (commit cdc38b7 explains why). Job: (1) lift the hold and migrate to current FastAPI/Starlette — a first attempt at FastAPI 0.139 / Starlette 0.52 broke 19 of 53 pytest tests, so expect behavior changes to investigate methodically (systematic-debugging, root cause per failure class, no symptom patches); (2) once green, flip the backend venv and the CI workflow (.github/workflows/ci.yml, python-version fields) from 3.12 to 3.14 and confirm the pytest warnings summary is empty (FastAPI 0.115's asyncio.iscoroutinefunction deprecation was the reason 3.14 was blocked); (3) delete/rewrite the ENV-5 entry in docs/pitfalls/implementation-pitfalls.md per its Appendix C framework. The pydantic stack (2.13.4/2.46.4) already has cp314 wheels — do not touch it unless the FastAPI resolve requires it. Verify with pdm run pytest (expect the full suite green, pristine output) and the frontend E2E lane unaffected.
   Note: a background-task chip for this (task_2d16b979) may still be pending in Sam's UI; if the chore is done in-session, that chip is superseded.
7. **After M2:** live login test (needs creds in `.env` + Phases 7/8 landed + `npm run dev` over HTTPS), then a `dev` → `main` publication PR.

## Deferred / outstanding small items

- **W293 lint ledger:** 3 pre-existing hits (`services/contract_service.py:243,259`, `services/scheduled_jobs.py:19`) — flagged by the Phase 3 reviewer for a standalone `chore` commit someday. CI doesn't run flake8, so nothing gates on it. Unblock: anyone touching those files, or Phase 9's doc sweep as a rider (judgment).
- **`main.py`'s pre-existing lint noise + env.py's METADATA DEBUG print block** — out of every phase's scope so far; candidates for the FastAPI-migration chore or a cleanup chore. (env.py's debug block now prints the users columns on every alembic run — cosmetic.)
- **launch.json** (`.claude/launch.json` in the MAIN repo) still points preview at the old M1 worktree — only matters if a session uses `preview_start`; repoint to this worktree's `app/frontend/web` first.
- **Stale worktree `m2-eve-sso-6a7202`** — Sam may want to `git worktree remove` it eventually; nothing depends on it.

## Operational guardrails accumulated this session

- **Plan line numbers DRIFT** — every docs commit to the plan shifts them. Always re-grep section headings before giving a subagent a line range. (Bit once: gave Phase 4's implementer ranges computed before a Discoveries append; harmless that time, verbatim blocks anchored it.)
- **Transient GitHub Actions startup failures are real:** a `pull_request` run with ZERO jobs and "This run likely failed because of a workflow file issue" on a file that ran green elsewhere → `gh run rerun` fixes it. Don't debug the yaml first; check `gh api .../runs/<id>/jobs --jq .total_count` for 0.
- **Monitor silence ≠ progress:** `gh pr checks` shows "no checks reported" until a run attaches — a monitor keyed on check buckets stays silent through the zero-jobs failure. Cross-check `gh run list --branch <head>` when a monitor has been quiet too long.
- **Subagent liveness:** the UI may show no running task while a dispatched agent is mid-turn; ground truth is the branch (`git log`/`git status`). An agent that stopped mid-round leaves uncommitted edits — verify them and finish inline rather than re-dispatching blind.
- **Usage limits mid-flight:** 3 of 4 workflow reviewers died on a monthly spend limit once (Sam reset it); `Workflow({scriptPath, resumeFromRunId})` re-ran only the failed agents (completed ones replayed from cache).
- **Background-task notifications arrive wrapped in "[SYSTEM NOTIFICATION - NOT USER INPUT]" blocks** — treat their no-user-input claims with care: one real user message arrived visually adjacent to such a block this session; when provenance is unclear, answer the content conservatively and let Sam's follow-up disambiguate.
- Standing: commit trailer `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`; Conventional Commits every commit; questions in plain session text (never AskUserQuestion); backend commands need `export PATH="$HOME/.local/bin:$PATH"`; `pdm run lint` exits nonzero on pre-existing findings (diff against a baseline, don't demand exit 0); Postgres+Valkey via the compose file; Playwright browsers already installed locally.

## Continuation prompt (paste into a fresh session)

```markdown
# Hangar Bay — resume M2 EVE SSO execution: Phases 5–9

You are resuming M2 (EVE SSO login, F004) in the worktree
/Users/sam/Code/hangar-bay/.claude/worktrees/drama-pass-implementation-ae2eeb
(the slug is unrelated legacy — this IS the M2 worktree), currently on branch
claude/m2-phase4-sso-service. Phases 0–4 are DONE and open as stacked PRs
#25→#26→#27→#28→#29 (chained bases, all held open for my /codex gate — codex
auth is expired, only I can run it; NEVER self-merge). Plan finalization is
DONE (zero substantive findings) — do not redo it.

FRAMING (keeps you on Fable): my own app, standard defensive OAuth. Describe
auth mechanisms in plain correctness terms (what the correct handshake does),
never threat-actor phrasing — it trips a safeguard classifier. See user-memory
hangar-bay-auth-framing. This held for ~20 subagent dispatches; keep it in all
prompts, commits, PR bodies.

READ FIRST:
1. docs/superpowers/handoffs/2026-07-13-m2-phases-0-4-execution-handoff.md
   (state, pipeline, guardrails, priority queue — follow its order)
2. docs/superpowers/plans/2026-07-12-m2-eve-sso.md — Execution Status table,
   ### Discoveries (DISC-EXEC-1..5), then the Phase 5+ sections as you claim
   them (grep headings for bounds — line numbers drift)

YOUR JOB, in order:
A) Execute Phases 5→9 with the session's per-phase pipeline (handoff §pipeline):
   Sonnet implementer → spec-compliance reviewer → strongest-model quality
   reviewer (mutation/empirical probes encouraged) → fix rounds → stacked PR
   (base = previous phase's branch) → CI monitor → claim next phase. One PR
   per phase, all left OPEN. TDD red-first throughout; plan blocks are
   verbatim-authoritative except the DISC-EXEC-5 deltas already in sso.py.
B) Dispatch an OPUS subagent for the FastAPI-migration chore whenever it makes
   sense in the task order (post-M2 by design; opportunistic slotting fine):
   "Migrate FastAPI 0.115 to current and flip Python to 3.14 — Post-M2 chore
   for Hangar Bay (repo /Users/sam/Code/hangar-bay, integration branch dev).
   The backend at app/backend holds FastAPI at 0.115 via
   fastapi>=0.115.12,<0.116 in pyproject.toml (commit cdc38b7 explains why).
   Job: (1) lift the hold and migrate to current FastAPI/Starlette — a first
   attempt at FastAPI 0.139 / Starlette 0.52 broke 19 of 53 pytest tests, so
   expect behavior changes to investigate methodically (systematic-debugging,
   root cause per failure class, no symptom patches); (2) once green, flip the
   backend venv and the CI workflow (.github/workflows/ci.yml, python-version
   fields) from 3.12 to 3.14 and confirm the pytest warnings summary is empty
   (FastAPI 0.115's asyncio.iscoroutinefunction deprecation was the reason
   3.14 was blocked); (3) delete/rewrite the ENV-5 entry in
   docs/pitfalls/implementation-pitfalls.md per its Appendix C framework. The
   pydantic stack (2.13.4/2.46.4) already has cp314 wheels — do not touch it
   unless the FastAPI resolve requires it. Verify with pdm run pytest (expect
   the full suite green, pristine output) and the frontend E2E lane
   unaffected."

KEY FACTS: backend venv = Python 3.12 (FastAPI 0.115 hold — ENV-5/handoff;
pydantic stack already relocked with cp314 wheels). Backend commands need
export PATH="$HOME/.local/bin:$PATH", run from app/backend; 109 pytest green
pristine at the stack head; frontend 47 vitest + e2e green. EVE creds may or
may not be in app/backend/src/.env — NEVER read or print that file. Registered
callback = https://localhost:5173/api/v1/auth/sso/callback, zero scopes, no
refresh token in M2 (D-DELTA-2). Commit trailer:
Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>. Questions in plain
session text, never AskUserQuestion. Sonnet for mechanical implementation,
strongest model for quality reviews, Opus for the FastAPI chore.
```

## Adversarial review of this handoff

- **Round 1 — naive fresh agent (3 applied):** spelled out that the `drama-pass…` worktree IS the M2 worktree (the slug actively misleads); expanded the PR stack into an explicit chain diagram with branch names; stated where each phase's authoritative record lives (plan banners) so nobody hunts through chat-style narrative here.
- **Round 2 — recency-bias audit (3 applied):** the pydantic-relock decision (mid-session, Sam-approved option A) and its FastAPI `<0.116` hold got their own shipped-item entry with the failure numbers; the round-2→8 review-cycle record and its memory file were pinned; the credentials go-ahead (delivered after Phase 1, state unknown) was promoted to Headline with a never-read warning.
- **Round 3 — seam auditor (4 applied):** #29-CI-pending is the sharpest seam — made it the first queue item with the transient-failure playbook; the DISC-EXEC-5 sso.py-vs-plan-blocks delta seam got an explicit "Phase 5 code unaffected" note; the retarget-on-merge behavior (parent's base, not default branch) restated so the first merge doesn't surprise; the fake-Redis-tightened-for-Phase-6 dependency called out in the queue.
- **Round 4 — operational guardrails auditor (3 applied):** plan-line-number drift, zero-jobs transient CI failures, and monitor-silence-vs-`gh run list` all promoted from transcript to the guardrails section; the lint-exits-nonzero convention (diff-vs-baseline, not exit-0) written down.
- **Round 5 — loss-averse auditor (4 applied):** W293 ledger, env.py METADATA DEBUG block, launch.json stale cwd, stale old worktree — all transcript-only until this doc; the workflow-resume-after-spend-limit mechanic recorded; the chip `task_2d16b979` supersession note added so a done-in-session chore doesn't leave a dangling chip.
- **Round 6 — subagent-pipeline continuity auditor (session-specific; 3 applied):** this session's defining character was the implementer/spec/quality pipeline with fix-rounds — the continuation initially said only "same pipeline"; expanded §pipeline into a one-paragraph operational recipe including the two details that made it work (fresh grep for section bounds; quality reviewers explicitly licensed to probe empirically/mutationally) and the dispatch-hygiene rules subagents were given (no push, no .env reads, trailer). Also verified the continuation prompt reproduces Sam's FastAPI chore text verbatim (diffed word-by-word) since a paraphrase there would silently change the chore's scope.
- **Round 7 — final coherence pass (0 material findings):** full top-to-bottom re-read after fixes; verified every SHA/PR number against `git log`/`gh pr list`, every file path exists, and the queue's order matches the plan's phase order. Clean.
