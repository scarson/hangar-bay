# Handoff — E2E + docs sweep shipped, EVE-cyan rebrand, M2 SSO brainstorm open (2026-07-12, later session)

Supersedes [`2026-07-12-design-phase-handoff.md`](./2026-07-12-design-phase-handoff.md)
(its priority-queue items 2–4 are done; its Runbook `preview_start` note is stale).

## Headline state

- **Branch:** `claude/hangar-bay-frontend-rebuild-2e4fe7`, worktree at
  `.claude/worktrees/hangar-bay-frontend-rebuild-2e4fe7`. Tip `7c19f1e` + this handoff
  commit, **pushed**. Working tree clean apart from this handoff's files at write time.
- **PR #22 is MERGED** ([#22](https://github.com/scarson/hangar-bay/pull/22), merge commit
  `27ec57d`, 2026-07-12 07:18Z, by Sam, true merge): **`main` now contains everything through
  `7c19f1e`** — M1, design phase, EVE-cyan rebrand, E2E suite, docs sweep. GitHub auto-deleted
  the head branch on merge; this handoff's push re-created it carrying only the handoff
  commit(s), which go to main via a small docs PR. **M2 starts from a FRESH branch/worktree
  off `main`** — do not continue feature work on this worktree's branch.
- **Suites at tip:** backend 53 pytest; frontend 47 vitest + **37 Playwright E2E** (fixture
  lane = 64 executions across desktop/mobile projects, green twice consecutively; live lane
  3/3 vs the real stack). `eslint .` and strict `tsc -b`/Vite build green.
- **Dev environment:** a fresh session should assume the uvicorn backend and Vite preview are
  DOWN (they die with the session/app) and re-run the Runbook below. Postgres + Valkey
  containers usually survive. `app/backend/src/.env` (untracked) already carries
  `AGGREGATION_DEV_CONTRACT_LIMIT=1000` — see Discoveries.
- **M2 (EVE SSO, F004) brainstorm is OPEN mid-flight** — resume point in §M2 below.

## What shipped this session (commits, newest last)

| Commit | What |
|---|---|
| `aeaea09` | **EVE-cyan rebrand** (Sam-requested): `--color-brand` family hue 172 → 195.3, anchored to `#5CCBCB` sampled live from eveonline.com's computed styles. One accent again (interim `--color-eve` token removed; wordmark uses `text-brand`). `brand-ink` chroma capped 0.025 (0.03 clips sRGB gamut at hue 195). All pairs re-verified ≥ 9:1. DESIGN.md updated. |
| `fc5784b` | **Playwright E2E suite** — closes the M1 spec §Testing deferral. `app/frontend/web/e2e/`: fixture lane (all API via `page.route` interception, wire-shape builders in `e2e/fixtures/`, helpers in `e2e/helpers/`; desktop 1280×800 + mobile Pixel 7 projects) + opt-in live smoke lane (`E2E_LIVE=1`, structural invariants only). `npm run e2e`. Retries pinned 0 (TEST-2). vitest now excludes `e2e/**` (TEST-6). |
| `7c19f1e` | **Docs residue sweep** — Angular→React across F001–F007 + template + accessibility/design/observability/security specs; CONTRIBUTING + 4 backend test-file headers un-SQLite'd; risks.md PERF-001 (`inflight`) marked resolved; README gains Implementation Status + fresh screenshot (`design/assets/images/progress/frontend-contracts-20260712.png`, 2×, EVE-cyan brand, live data). Recovered from an interrupted agent (its edits survived on disk; verified + finished by the session lead). |

Also this session, uncommitted-until-this-handoff: pitfalls TEST-6/TEST-7, test-spec.md §3.5
E2E row updated to "live", this doc, and the superseded-banner on the prior handoff.

Live sanity pass (no commit): first-ever dataset with `is_blueprint_copy` verified in the UI —
BPC badges on 402 contracts, ships-only default showing 7 flagged hulls, filters/sort/
pagination/detail/URL-restore/history-back all correct. One expected fallback observed:
player-structure locations render as raw IDs (`Location 10425…`) until authed ESI exists
(that's an M2+ payoff).

## M2 EVE SSO (F004) — brainstorm state and resume point

Running the repo process: brainstorm → spec → Sam review → **adversarial spec review (Fable
subagent)** → `/writing-plans-enhanced` → plan-review-cycle → execution.
Currently INSIDE the superpowers:brainstorming flow (re-invoke that skill on resume):

- ✅ Context explored (findings below).
- ✅ Clarifying question 1 — **client-state: DECIDED (a)** — HTTPOnly cookie session +
  `GET /api/v1/me` + a `useCurrentUser` TanStack Query hook. No tokens in the browser, no
  client auth store; 401 = anonymous → Login button, 200 → character name + logout. Sam
  chose (a) explicitly.
- ✅ F004's `[DECIDED]` items accepted as baseline (Sam offered the chance to reopen;
  didn't): no ESI scopes in F004 itself; identity from ID-token JWT via JWKS; confidential
  client + `state` CSRF; Valkey-backed server-side sessions, secure HTTPOnly cookie ~7 days;
  tokens encrypted at rest; owner-hash transfer handling; refresh on demand only.
- ⬜ Remaining clarifying questions (ask ONE AT A TIME, plain session text):
  1. **EVE developer application** — only Sam can register it (his EVE credentials) at
     developers.eveonline.com. Needs: app created, dev callback URL registered (recommend
     `http://localhost:8000/auth/sso/callback`), and `ESI_CLIENT_ID`/`ESI_CLIENT_SECRET`
     placed in `app/backend/src/.env` by Sam himself — never via chat, never committed.
     This gates live testing but NOT implementation (mock SSO in tests).
  2. **Milestone success criteria / UI scope** — is M2 done at header identity
     (login button → character name + logout)? Is a portrait in scope? Is the
     structure-name-resolution payoff (raw `Location <id>` → real names via authed ESI)
     in M2 or deferred to M3? (It needs the `esi-universe.read_structures.v1` scope, which
     contradicts F004's "no scopes" — if wanted, it's a scope-bearing follow-up, not F004.)
  3. **Session duration semantics** — fixed 7-day expiry vs sliding renewal on activity.
- ⬜ Then: 2–3 approaches (main open axes: session library — hand-rolled Valkey session
  dependency vs `starlette-session`-style middleware; OAuth client — hand-rolled httpx flow
  vs Authlib; token-encryption keying — Fernet key in env), design sections for approval,
  spec at `docs/superpowers/specs/2026-07-12-m2-eve-sso-design.md`, self-review, Sam's
  review gate, Fable adversarial spec review, `/writing-plans-enhanced`.

### Context findings a fresh agent needs (verified this session)

- **Legacy `User` model must be replaced** —
  `app/backend/src/fastapi_app/models/common_models.py`: non-null unique `email`,
  `hashed_password`, `UserType.LOCAL`, `is_admin`, and `eve_character_id` as 32-bit
  `Integer` (modern EVE character IDs exceed 2^31 → must be `BigInteger`). F004 §5 has the
  target model. Dev drops/recreates tables on every boot (ENV-2), so the swap is cheap in
  dev; check whether Alembic exists at all before assuming a migration is needed (unverified).
- **Two divergent Settings classes are BOTH live:** `main.py` imports
  `core/config.py:settings`; `db.py`, `core/cache.py`, `core/http_client.py` import the
  legacy `config.py:get_settings` — and the legacy one already holds `ESI_CLIENT_ID`/
  `ESI_CLIENT_SECRET` stubs (`config.py:33`). M2 must pick the SSO config's home
  deliberately; consolidating the two classes is a candidate targeted improvement inside
  M2's design (it directly serves the work).
- **Dev cookie topology works:** SPA on `localhost:5173`, backend on `localhost:8000` —
  cookies are host-scoped (port-ignored), and all `/api/v1` calls ride the Vite proxy
  (same-origin), so an HTTPOnly session cookie set during the callback flows to API calls.
  The callback endpoint lives on :8000 and must redirect back to the SPA origin (dev:
  `http://localhost:5173/...`) after establishing the session.
- **Auth E2E strategy:** Playwright cannot drive real EVE SSO. Fixture lane: intercept
  `/api/v1/me` (401 vs 200 fixtures) for UI states. The OAuth callback flow itself gets
  backend HTTP-level tests (TEST-1 discipline; mock the EVE token/JWKS endpoints — the
  ESI-seam lesson says use real-shaped responses, not dict-returning mocks).
- `/api/v1/me` and `/auth/sso/*` paths are already sketched in F004 §6.2, and the
  frontend README + F004 already reference `useCurrentUser` (docs sweep aligned them).

## Deferred / not started (unblock condition + pointer)

- **Closing-gate nits (all pre-existing, none block):** singular "1 contracts" live region
  (`ContractsPage.tsx`; E2E deliberately matches `/contracts? match/` loosely so a fix won't
  break it); price Min/Max 14px-vs-13px drift; aggregation-lock TTL watchdog; theoretical
  out-of-range-redirect edge. Authority: prior handoff §Closing-gate nits.
- **`start_location_system_id` ingestion gap** — needed before system filters ship.
  Authority: M1 plan §Discoveries.
- **Backend hygiene:** Settings consolidation (may fold into M2 — see above); debug
  `print()` noise; flake8 red (C901 ETag helper, E261) — pytest is the enforced gate.
- **Frontend CI** — doesn't exist (`.github/` absent). E2E and a11y build-fail wiring both
  wait on it. E2E is local/manual until then.
- **i18n** — deferred by M1 spec Non-goals; feature specs now say "to be defined for the
  React stack".
- **Structure-name resolution** — needs authed ESI + a scope; scope-bearing follow-up to
  M2 (see M2 question 2).

## Operational guardrails accumulated this session (durable homes noted)

- **TEST-6** (vitest glob swallows Playwright specs) and **TEST-7** (QueryClient retry:1
  means error-state stubs must fail twice) → `docs/pitfalls/testing-pitfalls.md`.
- **`preview_start` reads the MAIN repo's `.claude/launch.json`**, not the worktree's — a
  root-level one now exists pointing `hangar-bay-web` into this worktree
  (`cwd: .claude/worktrees/…/app/frontend/web`, port 5173). If the worktree changes, update it.
- **Any backend `.py` edit — even comments — triggers reload → DB wipe → re-ingest**
  (ENV-3 reaffirmed; comment-only header edits did it this session). Batch, then one clean
  cycle; first run after wipe is fast (~1 min) with warm Valkey ETag caches.
- **User interruptions (Esc / rejecting a tool call) kill in-flight background workflows AND
  agents.** Workflows: relaunch with `Workflow({scriptPath, resumeFromRunId})` — completed
  `agent()` calls replay from cache (check `journal.jsonl`; zero completions = clean rerun).
  Agents killed by the user CANNOT be resumed (harness refuses) — but their on-disk edits
  survive; verify and finish the work directly instead of spawning a duplicate.
- **E2E house rules** (enforced in the suite): role/label selectors only (no test-ids);
  retries 0; every wire-visible behavior asserts request params AND render; `Badge` DOM text
  is title-case (`Ship`, `Exchange`) — CSS uppercases visually; the Issued column is
  `max-sm:hidden` so mobile assertions use `th[aria-sort]` attributes, not visible roles;
  live-region text is always-plural — match loosely.
- **Brand color provenance:** EVE cyan `#5CCBCB` = `oklch(0.778 0.101 195.3)` sampled from
  eveonline.com's PLAY FREE button/stat numerals (computed styles, 2026-07-12). DESIGN.md
  is authoritative.
- Standing conventions: questions in plain session text (never AskUserQuestion); plan
  reviewers EXECUTE scaffolding steps; commit trailer
  `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`.

## Priority queue (suggested)

1. Merge the small docs PR carrying this handoff into `main` (Sam's click), so the next
   session reads it from `main`.
2. Resume M2 brainstorm — on a fresh worktree/branch off `main` (≥ `27ec57d`) — at §M2's
   remaining questions → approaches → design → spec → Sam review → Fable adversarial spec
   review → `/writing-plans-enhanced` → plan-review-cycle → execute.
3. During M2 backend work, batch in: Settings consolidation (if the design adopts it),
   the four closing-gate nits worth doing, debug-print cleanup.
4. After M2: F005+ (scope-bearing features), frontend CI (unlocks E2E + a11y gating),
   `start_location_system_id` gap before system filters.

## Runbook (fresh session, cold machine)

Post-merge note: run this from whatever checkout hosts the work (for M2, the NEW worktree
off `main`). The main-repo `.claude/launch.json`'s `cwd` points at the OLD M1 worktree —
**update it to the new worktree's `app/frontend/web` before `preview_start`**.

```bash
cd <your-worktree>   # M1 archive: .claude/worktrees/hangar-bay-frontend-rebuild-2e4fe7
docker compose -f app/backend/docker/compose.yml -f app/backend/docker/compose.dependencies.yml up -d --wait postgres_db valkey_cache
export PATH="$HOME/.local/bin:$PATH"      # pdm lives here (uv tool install)
docker exec hangar_bay_valkey valkey-cli DEL "hangar-bay:aggregation:lock"
(cd app/backend && pdm run dev)            # tracked background task; wipes+re-ingests on boot
# ready when: curl -s "localhost:8000/contracts/?is_ship_contract=true&size=1" → total > 0
#   (~1-4 min; .env already has AGGREGATION_DEV_CONTRACT_LIMIT=1000 → ~7 ships / 402 BPCs)
# frontend: preview_start name=hangar-bay-web (reads the MAIN repo's .claude/launch.json) → :5173
# E2E: (cd app/frontend/web && npx playwright test)            # fixture lane, no backend needed
#      (cd app/frontend/web && E2E_LIVE=1 npx playwright test --project=live-smoke)  # needs backend
```

Backend env: `app/backend/src/.env` (untracked; ENV-1 format rules). Test DB
`hangar_bay_test` via `DATABASE_URL_TESTS` (present).

## Continuation prompt (paste into a fresh session)

```markdown
# Hangar Bay — start M2 EVE SSO from main (post-merge of PR #22)

PR #22 is MERGED (true merge `27ec57d`): `main` contains M1, the design phase, the EVE-cyan
rebrand, the Playwright E2E suite, and the docs sweep. Start by pulling `main` in
`/Users/sam/Code/hangar-bay` (the local checkout may be behind), then create a FRESH worktree
+ branch off `main` for M2 (superpowers:using-git-worktrees; e.g. `claude/m2-eve-sso-<suffix>`).
Do not reuse the old M1 worktree branch (`claude/hangar-bay-frontend-rebuild-2e4fe7`) for
feature work.

**Read first (in order, paths relative to your checkout):**
1. `docs/superpowers/handoffs/2026-07-12-e2e-docs-m2-kickoff-handoff.md` — full state,
   M2 brainstorm resume point, discoveries, guardrails, runbook (if it's not on main yet,
   it's on the old branch / its docs PR)
2. `design/features/F004-User-Authentication-SSO.md` — the SSO feature spec (most decisions
   pre-made and marked [DECIDED])
3. `PRODUCT.md` + `DESIGN.md` — product register + token rules (brand is now EVE cyan #5CCBCB)
4. `docs/pitfalls/implementation-pitfalls.md` (ENV-1/2/3) and `docs/pitfalls/testing-pitfalls.md`
   (esp. TEST-1, TEST-6, TEST-7)

**Context:** Suites at main: 47 vitest + 37 Playwright frontend (`npx playwright test`;
live lane `E2E_LIVE=1 … --project=live-smoke`), 53 pytest backend; lint + strict build green.
The dev environment is likely DOWN (session-bound processes); the handoff's Runbook has the
exact bring-up. Two machine-local gotchas: the untracked `app/backend/src/.env` already sets
AGGREGATION_DEV_CONTRACT_LIMIT=1000 (the default 100 samples zero ships — oldest-first ESI
page), and the main repo's `.claude/launch.json` `cwd` still points at the OLD M1 worktree —
repoint it at your new worktree's `app/frontend/web` before using preview_start.

**Task: resume the M2 (EVE SSO, F004) brainstorm mid-flight** — re-invoke
superpowers:brainstorming and pick up at clarifying questions. Already settled (do not re-ask):
- Client-state = cookie session + GET /api/v1/me + a useCurrentUser TanStack Query hook.
  No tokens in the browser, no client auth store. (My explicit choice.)
- F004's [DECIDED] baseline stands: no ESI scopes in F004; identity via ID-token JWT (JWKS);
  confidential client + state CSRF; Valkey-backed server-side sessions, HTTPOnly cookie
  ~7 days; tokens encrypted at rest; owner-hash transfer handling; refresh on demand.

Remaining clarifying questions (one at a time, PLAIN SESSION TEXT):
(1) EVE developer app registration — I must create it and put ESI_CLIENT_ID/SECRET into
app/backend/src/.env myself; propose the dev callback URL. (2) M2 success criteria — header
identity only, or more? Structure-name resolution needs a scope → likely M3. (3) Session
duration semantics (fixed vs sliding). Then: 2-3 approaches (session mechanism, OAuth client
library, token-encryption keying), sectioned design for my approval, spec at
docs/superpowers/specs/2026-07-12-m2-eve-sso-design.md, spec self-review, my review gate,
adversarial spec review (Fable subagent), /writing-plans-enhanced, plan-review-cycle,
then workflow execution — same shape as M1.

**M2 design facts already verified (in the handoff §Context findings):** the legacy User
model stub must be replaced (Integer character_id overflows — BigInteger; drop
email/password/UserType); TWO Settings classes are both live and the legacy one holds the
ESI client stubs — pick the SSO config home deliberately (consolidation is a candidate
targeted improvement); dev cookie topology works via the Vite proxy; auth E2E = fixture-lane
/api/v1/me interception + backend HTTP-level OAuth tests with real-shaped SSO mocks.

**Conventions that bit us (don't relearn):** ask questions in plain session text (never
AskUserQuestion); plan reviewers must EXECUTE scaffolding steps, not read them; commit trailer
`Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`; backend .py edits (even comments)
trigger reload+DB-wipe — batch them, then one clean lock-clear + ingestion cycle, hands off
until it finishes; user interruptions kill background workflows/agents — workflows resume via
resumeFromRunId, killed agents don't (but their disk edits survive — verify and finish inline).

Ultracode is enabled - don't go crazy - tens of agents are okay, hundreds are not. Be deliberate about model routing - Opus default, Fable when the task benefits from the uplift, Sonnet for mechanical tasks.
```

## Adversarial review of this handoff

- Round 1 — naive fresh agent: 3 findings applied (spelled out the brainstorming-skill
  re-invocation in the continuation prompt — a fresh agent wouldn't know the flow state
  machine; added the `useCurrentUser` naming so the hook name stays consistent with the
  docs-sweep prose; runbook now names the E2E commands).
- Round 2 — recency bias: 3 findings applied (the sanity-pass structure-ID fallback and its
  M2 relevance were only in chat; the interrupted-workflow/agent recovery semantics were
  only in chat; the launch.json root-location discovery predated everything else and was
  nearly lost).
- Round 3 — seam auditor: 3 findings applied (PR #22 description doesn't yet mention this
  session's commits — PR comment queued as part of this handoff's commit step; the
  structure-name payoff contradicts F004's no-scopes decision — made the contradiction
  explicit in M2 question 2 so the spec doesn't absorb it silently; superseded-banner added
  to the prior handoff pointing here).
- Round 4 — guardrails auditor: 2 findings applied (TEST-6/TEST-7 written into
  testing-pitfalls.md rather than living here; the interruption-kills-background-work rule
  generalized and recorded under guardrails, not just narrated).
- Round 5 — loss-averse: 3 findings applied (Badge title-case DOM text and the
  `max-sm:hidden` aria-sort selector constraint were only in an agent's report; the
  brand-color provenance line — future designers need WHERE #5CCBCB came from; Alembic
  status explicitly marked unverified instead of asserted).
- Round 6 — **auth-security reviewer** (session-specific: this handoff launches an OAuth
  implementation): 3 findings applied (continuation prompt now states Sam himself puts
  client credentials in .env — never via chat, never committed; dev cookie topology
  documented so the design doesn't invent a token-in-JS workaround for a non-problem;
  test guidance pins real-shaped SSO endpoint mocks per the M1 ESI-seam lesson, so the
  callback flow isn't "verified" against dict-shaped fantasies).
- Round 7 — **fresh-eyes holistic top-to-bottom read** (lens: overall coherence after six
  rounds of point fixes): 2 findings applied (deduplicated the Settings-consolidation item
  which appeared in three sections with drifting wording — now §Context findings owns the
  detail and other sections point at it; fixed the continuation prompt's read-order to put
  the handoff first, F004 second — it had drifted during edits).
- Round 8 — **post-merge reality check** (session-specific: Sam merged PR #22 *between this
  doc's first commit and its push* — the push's `[new branch]` output was the tell): 6
  findings applied (headline PR bullet rewritten to merged state + fresh-branch-off-main
  directive; "PR #22 merge" removed from Deferred; priority queue re-anchored on the docs
  PR + fresh M2 worktree; continuation prompt rewritten — pull main, new worktree, stale
  `launch.json` cwd warning, "do not merge" instruction deleted; runbook gained the
  which-checkout note; memory files updated to merged state). Lesson recorded here: verify
  remote/PR state at handoff time, not from session memory — the world moves mid-session.
- Final full pass (all eight rounds re-run): zero material findings.
