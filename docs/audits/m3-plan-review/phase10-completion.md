<!-- ABOUTME: Completion record for Phase 10 (docs, gates, PR) of the M3 account-features plan. -->
<!-- ABOUTME: Captures the real gate numbers, per-task commit SHAs, the PR, and deviations from the plan-as-written. -->

# Phase 10 completion — M3 account features (F005 / F006 / F007)

**Date:** 2026-07-18
**Branch:** `claude/m3-account-features` (worktree `.claude/worktrees/m3-account-features`)
**Plan:** `docs/superpowers/plans/2026-07-17-m3-account-features.md` §Phase 10
**Starting HEAD:** `1386fe9` (Phase 9 tip, clean tree)

Phase 10 delivers the docs updates (two pitfall entries, README/feature-index/per-feature deviation notes), the full local gate run, and the single unmerged PR to `dev`. No production code changed in this phase.

## Per-task commit SHAs

| Task | Subject | SHA |
|------|---------|-----|
| 10.1 | `docs(pitfalls): add SQLA-2 (partial-index ON CONFLICT) and TEST-11 (chunk-boundary insert)` | `46e6f5a` |
| 10.2 | `docs: mark F005/F006/F007 implemented with recorded M3 deviations` | `70592e8` |
| 10.3 | (gates + PR; no code commit) — plan marked complete in `docs(m3): mark phase 10 complete` | see final commit |

## Gate results (Task 10.3 — real numbers)

Dependencies: `postgres_db` + `valkey_cache` up and healthy via compose.

| # | Gate | Command | Result |
|---|------|---------|--------|
| 1 | Backend pytest | `cd app/backend && pdm run pytest -q` | **320 passed** in 17.59s, output pristine (no warnings/errors) |
| 2 | Frontend lint | `cd app/frontend/web && npx eslint .` | **clean** (exit 0, no output) |
| 3 | Frontend typecheck | `npx tsc -b` | **clean** (exit 0) |
| 4 | Frontend unit/component | `npm run test` (vitest run) | **135 passed** (26 files), exit 0 |
| 5 | E2E fixture lane | `npm run e2e` | **90 passed, 7 skipped**, retries 0, 0 failures — desktop 44 passed / 3 skipped, mobile 46 passed / 1 skipped, live-smoke 3 skipped |
| 6 | Codegen artifacts | `git status --porcelain` on `openapi.json`, `schema.d.ts`, `routeTree.gen.ts` | **clean** — no regen diff |
| 7 | Push | `git push origin claude/m3-account-features` | pushed `1386fe9..70592e8` (branch already tracked `origin`) |
| 8 | Open PR | `gh pr create --base dev` | **PR #46** — https://github.com/scarson/hangar-bay/pull/46 |
| 9 | Confirm open/unmerged | `gh pr view 46` | `state: OPEN`, base `dev`, head `claude/m3-account-features` — **not merged** |

### E2E skip accounting (7 expected skips)

- 3 desktop skips — the 3 mobile-only tests skipped on the desktop project.
- 1 mobile skip — the 1 desktop-only responsive test (`responsive.spec.ts:127`) skipped on the mobile project.
- 3 live-smoke skips — the live-smoke lane auto-skips without `E2E_LIVE=1` and a real backend.

## PR

- **#46** — feat: M3 account features (F005 saved searches, F006 watchlists, F007 notifications)
- URL: https://github.com/scarson/hangar-bay/pull/46
- Base `dev`, head `claude/m3-account-features`, state **OPEN**.
- Merge classification: **Review — database schema + per-user data authorization** (both Domain triggers). **Sam merges.** `/codex review` to be recorded before merge. **NOT merged by this session** — the plan ends at an open PR.

## Deviations from the plan-as-written

1. **Task 10.1 completeness followed the doc's full Appendix C checklist, not just the plan's abbreviated Step-4 list.** The plan's Step 4 enumerates five completeness items and asserts they are "exactly the Completeness Checklist in Appendix C." The live Appendix C checklist actually has **eight** items. Per the parent instruction ("checklist completeness per the doc's own Appendix C rules"), the two extra items were also satisfied:
   - **Grep for other instances:** searched the backend for other `on_conflict` / partial-index sites. The only partial-index `ON CONFLICT` target is `services/watchlist_matcher.py` (already restates `index_where`); `services/auth_service.py` and `services/db_upsert.py` target full unique constraints / primary keys, so SQLA-2 does not apply to them. No remediation needed.
   - **Appendix A changelog:** added a dated `2026-07-18 — SQLA-2 added` entry recording the source and the grep result.
   These additions are within Task 10.1's file (`implementation-pitfalls.md`) and were included in commit `46e6f5a`.

2. **README M2 paragraph's stale trailing sentence was corrected.** The Milestone 2 paragraph ended with "…(F005 … F006 … F007 …) remain deferred, gated on Milestone 3," which M3 now falsifies. It was changed to "…are delivered in Milestone 3, below," and a new **Milestone 3 (account features) — implemented** paragraph was added in the surrounding style. This is a truthful correction of a now-false statement, consistent with the plan's Step-2 intent ("mark F005/F006/F007 as implemented … matching the surrounding style").

3. **PR-body test-evidence parentheticals removed.** The plan's body template carried meta-instructions like "(fill from gate Step 1)". These were replaced with the real numbers and dropped from the published body (they were authoring instructions, not body content). The Merge classification block and "Sam merges" were kept verbatim as instructed.

No other deviations. No gate required more than one attempt; nothing was weakened.

## Notes / non-blocking observations

- `mergeStateStatus` on PR #46 reports `UNSTABLE`. The project has no CI yet (CLAUDE.md: "CI/CD: none yet"), so this reflects pending/absent required checks rather than a real merge problem. The PR is OPEN and unmerged as required.
- Frontend vitest emits jsdom "Not implemented: Window's scrollTo()" / "HTMLCanvasElement's getContext()" console lines. These are known jsdom environment limitations (not test failures) and were present at the Phase 8 baseline that recorded 135 passing; not a regression.
- Backend `pdm run lint` (flake8) is NOT one of Task 10.3's gates and remains non-clean repo-wide (pre-existing debt, CI does not run it); left untouched per the parent instruction.
