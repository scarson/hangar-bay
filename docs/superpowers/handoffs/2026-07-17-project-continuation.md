<!-- ABOUTME: Fresh-session continuation prompt + state handoff for Hangar Bay after the ESI spring-cleaning assessment (PR #40). -->
<!-- ABOUTME: Captures release seam (dev 152 ahead of main), next-milestone decision (M3 vs release vs live-SSO verify), deferred items, and guardrails. -->

# Hangar Bay — project continuation handoff (2026-07-17)

Written at the end of the ESI spring-cleaning-assessment session. The paste-ready
starting prompt for a fresh session is at the bottom (§Continuation prompt); the
sections above it are the durable state that prompt refers to.

## Headline state

- **Integration branch `dev` tip:** `5a8c3cc` (origin/dev), pushed. This is where all feature/fix/docs PRs land.
- **Release branch `main` tip:** `15a7195` (origin/main) — Milestone 1 (public marketplace) release.
- **Release seam:** `dev` is **152 commits ahead of `main`**. Everything after M1 — M2 EVE SSO, the M2 hardening PRs, the FastAPI 0.139 / Python 3.14 chore, and this session's ESI work — is on `dev` and **not yet released to `main`**. See §Priority queue item 1.
- **Open PRs:** none.
- **Worktrees live:** main repo at `/Users/sam/Code/hangar-bay` (on local `dev`, currently at `f4ea829` — **behind** origin/dev, needs realign; see §Guardrails). Three ephemeral worktrees under `.claude/worktrees/` (see §Housekeeping) — all on merged/dead branches, cleanup candidates.
- **CI:** GitHub Actions runs frontend + backend on PRs (backend on Python 3.14). No CD yet.

## What shipped this session (PR #40, merged to `dev`, `5a8c3cc`)

Impact assessment of two ESI dev-blog posts against the codebase, plus a one-line fix and persistent documentation of follow-ups:

1. **Assessment: the 24 March 2026 ESI legacy-route removals have zero breaking impact on Hangar Bay.** Every ESI data route is version-pinned (`/v1`, `/v3`); SSO validates JWTs offline via JWKS (no `/verify` round-trip); nothing consumes ESI's `/status.json`, `/swagger.json`, `/diff`, `/versions`, or `/headers`. Verified route-by-route against source, not just an agent summary.
2. **Fix (`6a8e426`):** pinned the one non-pinned caller — `app/frontend/web/scripts/generate-regions.mjs` — from `/latest` to `/v1` (`/v1/universe/regions/`). Build-time script producing committed static `regions.ts`; endpoints re-verified live (HTTP 200), output unchanged.
3. **Docs (`7b7f163`):** recorded the ESI status-monitoring follow-ups and the route-pinning rule persistently (see §Deferred items for the anchors).

## Current milestone / feature state

Source of truth: `README.md` §Implementation Status and `design/features/feature-index.md`.

- **M1 — public marketplace (released to `main`):**
  - **F001** Public Contract Aggregation & Display — ESI→PostgreSQL ingestion pipeline. ✅ implemented.
  - **F002** Ship Browsing & Advanced Search/Filtering — contract list with URL-driven filtering, sorting, pagination. ✅ implemented. **(Not "next work" — already shipped.)**
  - **F003** Detailed Ship/Contract View — per-contract detail view. ✅ implemented.
- **M2 — EVE SSO (on `dev`, unreleased):**
  - **F004** User Authentication (EVE SSO) — header login/identity, Valkey-backed server-side sessions, encrypted token vault, CI coverage. ✅ implemented across 9 phases + two hardening PRs (#36 frontend, #37 backend). Plan: `docs/superpowers/plans/2026-07-12-m2-eve-sso.md`; design: `docs/superpowers/specs/2026-07-12-m2-eve-sso-design.md`.
  - **Deferred within M2:** the **live-lane SSO login test** (a real EVE SSO round trip) — gated on EVE credentials landing in the local `.env` plus a live end-to-end verification pass.
- **M3 — not started, no plan/spec yet.** The account features are all `Refined` in the feature index but unbuilt, and the M2 docs repeatedly mark them **gated on M3**:
  - **F005** Saved Searches, **F006** Watchlists, **F007** Alerts/Notifications.
  - M3 is also where the M2 design deferred a cluster of scope-bearing and token-using work (see §Deferred items).

## The next-work decision (for the fresh session to settle with Sam first)

There is no single pre-decided "next task." Three legitimate directions, each pickable independently. **Confirm the direction with Sam before diving in** — this is a genuine multiple-valid-approaches choice, not an obvious default.

1. **Cut a `dev` → `main` release** (recommended to at least *raise* first). 152 commits of shipped, CI-green, codex-reviewed work sit unreleased. Per `docs/git-strategy.md` §Release branch, `main` advances only via a `dev` → `main` publication PR. Low-risk, high-clarity, unblocks nothing technical but keeps the release branch honest. Open question for Sam: is main intentionally batched, or has the release just not been cut? Don't assume — ask.
2. **Kick off M3** (the next feature milestone). This is *new creative/design work* → start with `superpowers:brainstorming`, not code (skill routing is mandatory here). First substantive question to resolve in brainstorming: **what is M3's actual scope** — are F005/F006/F007 buildable on the *existing* zero-scope SSO identity (they are user-preference features stored in Hangar Bay's own DB), or does M3 genuinely require requesting the first ESI scope (which the M2 docs assume)? The M2 design treats "M3 = first ESI scope + token-using caller"; the account features may not actually need scopes. Resolve that framing before writing a plan.
3. **Complete live SSO verification** (finish M2's one deferred thread). Needs EVE SSO credentials in the backend `.env` and a manual live end-to-end login pass, then flip the `README`/plan note. Small, concrete, but blocked on Sam providing credentials.

My recommendation: surface (1) to Sam immediately (it's a one-question decision), and treat (2) as the main forward direction pending Sam's scope steer. (3) is opportunistic whenever credentials are available.

## Deferred items (each with unblock condition + authoritative link)

- **ESI upstream health via `/meta/status` + meaningful readiness probe + data-staleness indicator.**
  - Unblock condition: a real production deployment exists *and* the ingestion-freshness surface (last-successful-ingest timestamp) is built first. Then `/meta/status` becomes a cheap enhancement (scheduler pre-flight + staleness data source).
  - Authoritative artifacts: `design/specifications/observability-spec.md` §2.5 (three enhancements, value-ordered, with the "MUST target `/meta/status`, never `/status.json`" constraint) and pitfall **ESI-1** in `docs/pitfalls/implementation-pitfalls.md`.
- **M3 scope-bearing / token-using work deferred by the M2 design** (all live-unexercised foundations already coded + tested in M2):
  - First ESI scope + structure-name resolution — its own feature spec + an EVE app consent change. Unblock: M3 kickoff decides to request a scope.
  - Refresh-token flow (`services/sso.refresh_token_pair` / `auth_service.refresh_user_tokens`) — banked but unexercised because zero-scope logins issue no refresh token. Unblock: M3 requests a scope, so refresh tokens start flowing.
  - Per-user session invalidation on refresh-failure — not buildable on M2's `sid`-keyed store (no user→sid index); M2 nulls only the `esi_*` token columns. Unblock: M3's token-using caller enforces re-auth per request.
  - Authoritative artifacts: `docs/superpowers/specs/2026-07-12-m2-eve-sso-design.md` §2.7 / §4.3 / Appendix B, and the recorded deviation notes in `design/features/F004-User-Authentication-SSO.md`.
  - There is also a commit-level note of "deferred M3 concurrency/discrimination gaps" (`ffe7b83`) — fold these into M3 brainstorming.

## Operational guardrails (accumulated / reinforced — don't re-discover)

These are in durable docs already (CLAUDE.md, `docs/pitfalls/`, `docs/git-strategy.md`); repeated here so a fresh agent has them before the first action:

- **Realign local `dev` with fetch + reset, never merge/pull.** The main worktree's local `dev` is currently behind origin/dev (the `gh pr merge` couldn't fast-forward it because `dev` is checked out there). Correct sequence: `git fetch origin dev && git reset --hard origin/dev` from the main worktree. Never "Sync"/`git pull` on `dev`. (git-strategy §Keeping a clean git graph.)
- **Worktrees live at `.claude/worktrees/<slug>` inside the repo** (gitignored), created with `git worktree add .claude/worktrees/<slug> -b <branch>`. Agent branches use the `claude/*` namespace.
- **Merge discipline:** agents auto-merge Routine PRs on green CI via `gh pr merge --merge --delete-branch` (never `--squash`/`--rebase`). Security-sensitive / architecture / data-integrity changes are `Review — domain`; put a `## Merge classification` heading in every PR body. Wait on CI with the Monitor tool, not bash sleep-poll. Known quirk: `gh pr merge --delete-branch` prints a benign `fatal: 'dev' is already used by worktree` error (it's trying to update the local `dev` ref) — the merge still succeeds; delete the remote branch manually with `git push origin --delete <branch>` if it lingers.
- **Conventional Commits on every commit** (no squash — full per-commit history is preserved and bisect-visible).
- **Backend `.py` edits under `--reload` are DESTRUCTIVE** — every save drops+recreates all tables and re-ingests (ENV-2/ENV-3). Batch backend edits, then one clean reload. An empty contract list right after startup is expected.
- **Never add `/api/v1` in FastAPI** — routers mount bare; the prefix belongs to the Vite proxy / deploy edge (PROXY-1).
- **Keep ESI routes version-pinned** (`/v1`, `/v3`…), never `/latest` or the removed legacy/meta routes (ESI-1). Regenerate the client chain after any backend schema change: `pdm run export-openapi` → `npm run generate:api`.
- **Auth/SSO work is framed in correctness terms** (token-handling correctness, offline JWKS validation), not threat/vulnerability language — a project convention.
- **Read `docs/pitfalls/` before coding** (FASTAPI-*, ENV-*, PROXY-1, SQLA-1, TEST-*, ESI-1).

## Priority queue

1. **Raise the `dev` → `main` release question with Sam** (one decision; if yes, cut the publication PR per git-strategy §Release branch).
2. **M3 kickoff** — `superpowers:brainstorming` to settle M3 scope (do F005/F006/F007 need an ESI scope, or build on existing identity?), then `superpowers-plus:writing-plans-enhanced` + `plan-review-cycle`.
3. **Live SSO verification** — whenever EVE credentials are available for the local `.env`.
4. **(Parked, deploy-gated)** readiness probe + staleness indicator + `/meta/status` (observability-spec §2.5 / ESI-1).
5. **(Housekeeping)** prune stale worktrees; realign local `dev`.

## Housekeeping

Stale worktrees (all on merged/dead branches — safe to `git worktree remove` after confirming nothing uncommitted):
- `.claude/worktrees/eve-api-changes-impact-9d17b1` — this session's worktree; branch `claude/eve-api-changes-impact-9d17b1` merged (PR #40) and deleted on remote.
- `.claude/worktrees/drama-pass-implementation-ae2eeb` — detached at `bfeaeac`.
- `.claude/worktrees/hangar-bay-frontend-rebuild-2e4fe7` — detached at `bd3f205`.

---

## Continuation prompt

> Paste the block below into a fresh session. It is self-contained.

```
You are picking up work on Hangar Bay, a FastAPI + React app that aggregates EVE Online public ship contracts into a filterable marketplace. Read CLAUDE.md and docs/pitfalls/ before touching code; skill routing is mandatory (new features → superpowers:brainstorming first).

CURRENT STATE (as of 2026-07-17, handoff: docs/superpowers/handoffs/2026-07-17-project-continuation.md):
- Milestone 1 (public marketplace: F001 aggregation, F002 browsing/search/filter, F003 detail view) is IMPLEMENTED and RELEASED to `main` (origin/main tip 15a7195). Do not treat F002/F003 as unbuilt — they shipped.
- Milestone 2 (F004 EVE SSO: header identity, Valkey server-side sessions, encrypted token vault, CI) is IMPLEMENTED and on `dev`, but NOT yet released to `main`. One thread deferred: the live-lane SSO login test (needs EVE credentials in the backend `.env` + a manual live end-to-end pass).
- `dev` (tip 5a8c3cc) is 152 commits AHEAD of `main`. That whole backlog (M2 SSO + hardening + FastAPI 0.139/Python 3.14 chore + the ESI spring-cleaning assessment) is unreleased.
- No open PRs.

FIRST, realign the main worktree's local `dev`: `git fetch origin dev && git reset --hard origin/dev` (it's behind; never pull/merge on dev — git-strategy).

THEN pick a direction WITH SAM (genuine choice — ask, don't assume):
1. Cut a `dev` → `main` release PR (152 commits shipped/CI-green/reviewed sit unreleased; git-strategy §Release branch governs). Ask Sam whether main is intentionally batched or the release just hasn't been cut.
2. Kick off Milestone 3 — the auth-gated account features F005 Saved Searches / F006 Watchlists / F007 Alerts (all `Refined` in design/features/feature-index.md, no plan yet). Start with superpowers:brainstorming. The first thing to settle: does M3 actually need the first ESI *scope* (the M2 design assumes so), or are these preference features buildable on the existing zero-scope SSO identity? Resolve that framing before writing a plan.
3. Finish live SSO verification (needs EVE creds in `.env`).

Deferred / parked (don't start unprompted; details + unblock conditions in the handoff doc): ESI `/meta/status` health + readiness probe + data-staleness indicator (observability-spec §2.5, pitfall ESI-1, deploy-gated); M3 scope/token-using work deferred by the M2 design (spec §2.7/§4.3/Appendix B).

Guardrails: backend `.py` edits under --reload wipe+re-ingest the DB (ENV-2/3) — batch them; never add `/api/v1` in FastAPI (PROXY-1); keep ESI routes version-pinned, never `/latest` (ESI-1); auth work is framed as correctness, not threat/vuln language; after any backend schema change run `pdm run export-openapi` then `npm run generate:api`; agents auto-merge Routine PRs on green CI (`gh pr merge --merge --delete-branch`, put a `## Merge classification` in the PR body).

Recommendation: raise option 1 with Sam right away (one-question decision), and treat option 2 as the main forward direction pending Sam's scope steer.
```

---

## Adversarial review log

Six rounds run on this handoff per the handoff skill; loop re-run after fixes until a clean pass.

- **Round 1 — Naive fresh agent.** Added explicit "F002/F003 already shipped, not next work" callout (the feature-index lists them as `Refined`, which a cold agent could misread as unbuilt); spelled out branch roles (`dev` = integration, `main` = release) rather than assuming; gave the exact local-dev realign command.
- **Round 2 — Recency-bias audit.** This session was short, so recency risk is low — but pulled forward the mid-session-persisted artifacts (observability §2.5, ESI-1) into §Deferred items with exact anchors so they aren't lost behind the more recent merge/cleanup actions.
- **Round 3 — Seam auditor.** The dominant seam is the 152-commit `dev`↔`main` gap; promoted it to Headline + Priority 1. Second seam: the `gh pr merge` local-`dev`-behind quirk — documented as a guardrail with the exact remedy so the next agent doesn't misread the benign error as a failed merge.
- **Round 4 — Operational guardrails auditor.** Confirmed each guardrail traces to a durable doc (CLAUDE.md / pitfalls / git-strategy) rather than living only here; this section restates, doesn't originate. Added the merge-classification + auto-merge mechanics and the ESI route-pinning rule.
- **Round 5 — Loss-averse auditor.** Captured the three stale worktrees (only visible in `git worktree list` this session) into §Housekeeping; captured the "deferred M3 concurrency/discrimination gaps" commit note (`ffe7b83`) so it folds into M3 brainstorming instead of being rediscovered.
- **Round 6 — Roadmap-integrity auditor (session-specific).** This session's defining character is *roadmap/state reconciliation* (figuring out what's actually built vs. deferred across three milestones). The failure mode is a wrong milestone claim sending the next session to rebuild shipped work or mis-scope M3. Findings applied: corrected the initial mis-read that F002/F003 were unbuilt (README §Implementation Status is authoritative — they're shipped); flagged the genuine M3-scope ambiguity (account features may not need ESI scopes despite the M2 design's assumption) as a brainstorming question rather than a settled fact, so the next session interrogates it instead of inheriting an unverified premise.
