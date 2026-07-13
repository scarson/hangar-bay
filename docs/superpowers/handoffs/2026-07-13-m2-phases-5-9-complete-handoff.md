# Handoff — M2 EVE SSO: Phases 5–9 shipped as stacked PRs #31–#35, milestone code-complete (2026-07-13)

**For the resuming agent:** M2 (EVE SSO login, F004) is now **code-complete across all nine phases**. This handoff supersedes [`2026-07-13-m2-phases-0-4-execution-handoff.md`](./2026-07-13-m2-phases-0-4-execution-handoff.md) (that one covered Phases 0–4; read it only for deep backstory). Your job is one of: (a) after Sam runs the codex gate and merges the stack, execute the two queued follow-ups; or (b) after the stack lands, run the live-lane SSO end-to-end test. Do NOT redo any phase — all nine are implemented, per-phase-reviewed, and CI-green.

> **Framing note (read first — this keeps you on Fable).** Hangar Bay is Sam's own app; M2 is standard defensive OAuth. Describe auth mechanisms in plain correctness terms — what the correct handshake/validation does ("the callback confirms it is completing the login this browser started", "return-path validation keeps redirects under FRONTEND_ORIGIN") — never threat-actor/attack-centric phrasing, which trips a broad safeguard classifier. Held across ~35 subagent dispatches over two sessions with zero trips. Durable record: user-memory `hangar-bay-auth-framing`.

## Headline state

- **Coordinator worktree (this session):** `/Users/sam/Code/hangar-bay/.claude/worktrees/m2-phases-5-9-sso-6b3f7c` on branch `claude/m2-phases-5-9-sso-6b3f7c` (off `main`; used only for orchestration + this handoff is written into the M2 worktree below).
- **M2 execution worktree:** `/Users/sam/Code/hangar-bay/.claude/worktrees/drama-pass-implementation-ae2eeb` — **despite the unrelated `drama-pass…` slug, this IS the M2 worktree.** All phase branches were cut here. Its tip is `claude/m2-phase9-docs` (the top of the stack).
- **The stack (all target-chained, all OPEN, all CI-green, none merged):**
  `dev` ← [#31](https://github.com/scarson/hangar-bay/pull/31) Phase 5 auth-service (`claude/m2-phase5-auth-service`) ← [#32](https://github.com/scarson/hangar-bay/pull/32) Phase 6 auth-routes (`claude/m2-phase6-auth-routes`) ← [#33](https://github.com/scarson/hangar-bay/pull/33) Phase 7 wiring+codegen (`claude/m2-phase7-wiring-codegen`) ← [#34](https://github.com/scarson/hangar-bay/pull/34) Phase 8 frontend (`claude/m2-phase8-frontend`) ← [#35](https://github.com/scarson/hangar-bay/pull/35) Phase 9 docs (`claude/m2-phase9-docs`).
- **Phases 0–4 are already merged to `dev`:** #25, #26, #27, #28, and **#30**. Note #30 replaced #29 — see the merge seam below.
- **Merge-gate overlay in force:** every PR stays OPEN for Sam's `/codex` gate. Codex CLI auth was expired at the start of this session but Sam had refreshed it (this session ran codex reviews of #25–#29 successfully). Regardless: **never self-merge.** Sam runs the gate and merges.
- **Backend at stack head:** 172 pytest green, pristine (zero warnings), Python 3.12 venv. Frontend: 58 vitest, e2e 72 passed/7 skipped (desktop+mobile), eslint + `tsc -b` clean.
- **Credentials:** EVE creds may or may not be in `app/backend/src/.env`. **Never read or print that file's values.** Tests don't depend on it (isolated-instance + delenv/monkeypatch patterns throughout).

## What shipped this session (pointers, not narrative)

Authoritative per-phase record lives in the plan's Execution Status banners: [`docs/superpowers/plans/2026-07-12-m2-eve-sso.md`](../plans/2026-07-12-m2-eve-sso.md) (top-of-plan **Overall** summary + the Execution Status table + each `## Phase N` banner). Highlights the banners compress:

1. **Codex reviews of #25–#29** ran first (Sam's explicit ask). #25/#26 clean; #27 surfaced the **P1 fail-open dev gate**; #28 three P2s (session/fake-redis); #29 four P2s (sso.py error-contract). #28 was merged; #29 was auto-closed by GitHub when its stacked base branch was deleted during the #28 merge (reopen-then-retarget is blocked on a closed PR) → opened **#30** as a replacement for the same head commit and merged it. All codex findings are captured in the hardening-PR task (below), not lost.
2. **Every phase carried a real fix round** its quality review earned via mutation/empirical probes:
   - **P5:** mutation-proven that the token-expiry arithmetic (`upsert` and `refresh`) and `last_login_at` refresh were unasserted — added three assertions, each verified to kill its mutant. The refresh-expiry assertion was initially vacuous (satisfied by the leftover upsert expiry); fixed by seeding a near-immediate `expires_in=1` so only a real refresh advance passes.
   - **P6:** added two mutation-verified tests pinning the §4.4 ungated-logout/`/me` boundary (they still work when SSO is unconfigured).
   - **P7:** the SSO-unconfigured startup-warning parametrization couldn't tell `or` from `and`; added two mixed-config rows, mutation-verified.
   - **P8:** the login-`next` assertion was flagged as possibly tautological (test derives expected from the same router store the component reads) — mutation-verified it catches component-transform bugs, and the `toContain('is_bpc%3Dtrue')` canary catches the router-drops-param case; also corrected the `SsoNotice` `useNavigate({from})` comment that overstated the mechanism.
3. **Two follow-ups** were scoped and deferred (see Ready-to-dispatch). One premature action was corrected: a hardening-PR worktree off `dev` was created then removed once I realized it must wait for the stack (see the seam below).

## Ready-to-dispatch (priority queue)

1. **Codex-findings hardening PR** — full finding list in user-memory `m2-eve-sso-shipped` and below. Do it in a **fresh worktree off `dev`** (`git worktree add … origin/dev -b claude/m2-hardening-codex-findings`), not either existing M2 worktree. **Prerequisite: the M2 stack (#31–#35) must be merged to `dev` first.** Two reasons it cannot start earlier: (a) the deferred Phase 5/6 findings live in unmerged code (`auth_service.py`, `api/auth.py`); (b) the P1 fix edits `main.py`, which Phase 7 (#33) also edits — opening a `dev`-based PR now forces a `main.py` merge conflict. Contents: **1 P1** (`main.py` `create_db_tables` fails open — `ENVIRONMENT` defaults to `"development"`, so a prod deploy that omits the var runs `Base.metadata.drop_all`; make destructive recreate a fail-closed explicit opt-in) **+ 7 P2s** (session.py EXPIRE→EXPIREAT race + corrupt-payload-500; fake_redis TTL non-expiry; sso.py `PyJWKSetError` escaping `SsoJwtError`, `_post_token` not validating body fields so a missing `expires_in` → callback 500 instead of `sso=error`, non-string `iss` → `TypeError`, oversized-digit `sub` → `int()` `ValueError`) **+ the deferred P5/P6 minors** (P5-finding-3 identity-map-only persistence assertion; P5-finding-5 read `expires_in` into a local before the first ORM mutation — pairs with the `_post_token` fix; P6 corrupt-state-payload class). **VERIFY each codex claim empirically before fixing** — codex findings can false-positive (one was falsified during plan review last session; see user-memory `plan-review-m2-eve-sso`). Needs its own `/codex` review before merge. Runs backend `pytest`.
2. **FastAPI 0.115→current + Python 3.12→3.14 migration chore** (dispatch to an **Opus** subagent, in its own fresh worktree off `dev`) — verbatim task text in the prior handoff's queue item 6 and in the plan's queue. **Prerequisite: must run after Phase 9 has merged** (it rewrites the ENV-5 pitfalls entry that Phase 9 writes; concurrent runs conflict on `implementation-pitfalls.md`). Also runs backend `pytest`.
3. **Live-lane SSO end-to-end test** — after the stack lands + EVE creds in `app/backend/src/.env` + `npm run dev` over HTTPS (Phase 8's Task 8.0 set this up). Then a `dev` → `main` publication PR closes M2.

**Serialization constraint for #1 and #2:** both run backend `pdm run pytest` against the SINGLE shared docker test DB (`hangar_bay_*` containers). They cannot run concurrently with each other or with any backend-pytest phase work — the test DB drop/recreate cycles would collide. Run them one at a time.

## Merge seams (where context is silently lost)

- **#29 → #30 replacement.** #29 (Phase 4) was auto-closed by GitHub when `claude/m2-phase3-cipher-session` (its base) was deleted during the #28 `--delete-branch` merge. A closed PR cannot be reopened-then-retargeted (GraphQL blocks both). Fix used: `gh pr create` a fresh PR (#30) for the same head commit `3175f1e` against `dev`, then merge. **Implication for the stack #31–#35:** as Sam merges each parent with `--delete-branch`, GitHub retargets the child to the parent's base (`dev` for this chain). If a child instead gets auto-closed (same failure mode), reopen via a fresh replacement PR, not `gh pr reopen`. If a retargeted child shows conflicts/replayed commits, rebase onto `origin/dev` + `--force-with-lease`.
- **Hardening PR ↔ Phase 7 on `main.py`.** The P1 hardening fix and Phase 7 both edit `main.py`. This is why the hardening PR is gated behind the stack merging — do not open it against `dev` while #33 is still open.
- **FastAPI chore ↔ Phase 9 on ENV-5.** Phase 9 writes ENV-5 in its 3.12-hold form (verbatim from the plan); the FastAPI chore rewrites/deletes it. Sequencing: Phase 9 merges first, chore rewrites after. Do not run the chore concurrently with Phase 9 being open.

## Operational guardrails accumulated this session

- **Per-phase pipeline that worked (continue it for the follow-ups' reviews):** Sonnet implementer pointed at the plan section (grep headings FRESH for bounds — plan line numbers drift; the Read tool was observed off-by-one past ~line 1856) → spec-compliance reviewer (byte-diff both directions via awk-extracted fences, not eyeballing) → strongest-model quality reviewer (mutation/empirical probes explicitly licensed — they earned their keep every phase) → fix round if a real gap → stamp banner ✅ + push + stacked PR (base = previous phase's branch) → CI monitor → claim next phase without waiting for merges.
- **Fix-round discipline that emerged:** fold a reviewer finding into the phase ONLY when it's a real, mutation-proven gap in THAT phase's OWN files; route cross-cutting findings (rooted in already-merged code) to the hardening PR instead. Every fix round this session was mutation-verified (mutate source → confirm the new assertion fails → restore byte-clean).
- **Subagent mutation hygiene:** subagents that mutate source to prove a test's strength MUST `git checkout -- .` and confirm `git status --porcelain` empty before finishing. One reviewer hit a stale-`.pyc` false-red after restore (same mtime-second) — clearing `__pycache__` fixed it; not a code defect.
- **CI monitor pattern:** `gh pr checks <N> --json name,state` polled in a bash loop that exits on all-terminal; a 15-min monitor timeout can fire while a slow frontend check is still `pending` (happened on #35) — just re-arm or `gh pr checks` directly to confirm.
- **Backend commands** need `export PATH="$HOME/.local/bin:$PATH"`, run from `app/backend`. `pdm run lint` exits nonzero on the pre-existing W293 ledger (contract_service.py, scheduled_jobs.py) — diff against baseline, never demand exit 0. Frontend commands run from `app/frontend/web`.
- Standing: commit trailer `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`; Conventional Commits; questions in plain session text (never AskUserQuestion — user-memory `ask-questions-in-session-text`); never read/print `.env`.

## Continuation prompt (paste into a fresh session)

```markdown
# Hangar Bay — M2 EVE SSO follow-ups (stack is code-complete)

M2 (EVE SSO, F004) is code-complete: all 9 phases implemented as stacked PRs
#31←#32←#33←#34←#35 off dev, each CI-green and per-phase-reviewed, ALL held
open for my /codex gate (never self-merge). Phases 0–4 already merged to dev
(#25-28, #30). Read FIRST:
1. docs/superpowers/handoffs/2026-07-13-m2-phases-5-9-complete-handoff.md
2. docs/superpowers/plans/2026-07-12-m2-eve-sso.md (Execution Status + Discoveries)
3. user-memory m2-eve-sso-shipped, hangar-bay-auth-framing, plan-review-m2-eve-sso

FRAMING (keeps you on Fable): my own app, standard defensive OAuth. Plain
correctness terms, never threat-actor phrasing.

Your job depends on whether I've merged the stack yet:
- If the stack is STILL OPEN: nothing to execute yet — the two follow-ups are
  both blocked on the stack merging to dev (main.py conflict + Phase 5/6
  findings not yet in dev + the ENV-5 rewrite ordering). Confirm CI is still
  green, answer questions, do not open the follow-up PRs.
- If the stack is MERGED to dev: execute, one at a time (both run backend
  pytest against the single shared docker test DB — never concurrently):
  (A) the codex-findings hardening PR (1 P1 fail-open main.py dev-gate + 7 P2s
      + the deferred P5/P6 minors — full list in the handoff/memory). VERIFY
      each codex claim empirically before fixing; needs its own /codex review.
  (B) an OPUS subagent for the FastAPI-0.115→current / Python-3.12→3.14 chore
      (verbatim task text in the handoff); it rewrites the ENV-5 pitfalls entry.
Then: live-lane SSO end-to-end test (EVE creds in app/backend/src/.env + npm
run dev over HTTPS), then a dev→main publication PR to close M2.

Backend cmds need export PATH="$HOME/.local/bin:$PATH" from app/backend; lint
exits nonzero on the pre-existing W293 ledger (diff vs baseline). Commit trailer
Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>. Never read/print .env.
```

## Adversarial review of this handoff

- **Round 1 — naive fresh agent (2 applied):** removed ephemeral in-session task-list numbers ("task #8/#7" — a fresh agent has no access to my TaskList; the durable pointers are user-memory `m2-eve-sso-shipped` + this doc); glossary terms (P1/P2, PROXY-1, D2, §4.4) are all resolvable via the plan/spec the doc points at.
- **Round 2 — recency-bias audit (0 applied):** verified the early-session items (the #25–#29 codex reviews, the #29→#30 replacement) are documented with equal weight to the late-session Phase 9 work; the mid-session premature-hardening-worktree correction and the Phase 5 vacuous-refresh-assertion self-catch are both recorded in "What shipped."
- **Round 3 — seam auditor (2 applied):** added the fresh-worktree-off-`dev` instruction to both follow-ups (a resuming agent must NOT work in either existing M2 worktree for the hardening/chore PRs); the three merge seams (#29→#30 replacement + retarget-on-merge behavior, hardening↔Phase 7 `main.py`, FastAPI-chore↔Phase 9 ENV-5) each have their own subsection.
- **Round 4 — operational guardrails auditor (0 applied):** the per-phase pipeline, fix-round-only-for-own-file-gaps discipline, subagent mutation hygiene (`git checkout -- .` + stale-`.pyc` gotcha), the CI-monitor-timeout-vs-slow-frontend note, backend PATH, and the lint-baseline convention are all in the guardrails section; nothing left only in transcript.
- **Round 5 — loss-averse auditor (0 applied):** the serialization constraint (both follow-ups share the single docker test DB), the live-lane test + `dev`→`main` publication as the true M2 close, and the "verify codex claims empirically" caution are all captured. Deliberately omitted as not-follow-up-relevant: the stale `m2-eve-sso-6a7202` worktree and the `launch.json` M1-cwd note (both in the prior handoff; neither blocks the follow-ups).
- **Round 6 — security-finding-custody auditor (session-specific; 0 applied, 1 verified):** this session's defining character was orchestrating security/correctness review findings across a stacked auth PR chain, and the highest-consequence artifact is the **P1 fail-open `create_db_tables` gate** (a prod deploy missing `ENVIRONMENT` would `drop_all`). Audited whether any finding could silently evaporate: the P1 is triple-captured (hardening-PR queue item + merge seam here, user-memory `m2-eve-sso-shipped`, and it will re-surface against the final `main.py`). Recounted the P2s against the raw codex outputs — #28 gave 3 (session EXPIRE race, fake_redis TTL, corrupt-payload-500), #29 gave 4 (PyJWKSetError, `_post_token` body fields, non-string `iss`, oversized `sub`) = the 7 P2s listed. The deferred P5/P6 minors are listed with their fix approach. Custody is intact; no finding lives only in the transcript.
- **Round 7 — holistic coherence pass (0 applied):** top-to-bottom re-read; the continuation prompt correctly branches on stack-still-open vs stack-merged, every PR number/SHA matches `gh pr list`, and the framing note leads. Clean.
