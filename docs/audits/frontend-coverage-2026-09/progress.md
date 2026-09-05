<!-- ABOUTME: Execution checklist and evidence for the remaining Wave 5 frontend coverage. -->
<!-- ABOUTME: Records scope decisions, verification, review findings, and integration status. -->

# Frontend coverage continuation — September 5, 2026

Work order: [latest coverage handoff](../../superpowers/handoffs/2026-08-10-wave-5-backend-closed-frontend-started-handoff.md), backed by the [living remediation table](../../test-coverage-reports/2026-08-09-f008-remediation-test-coverage-review.md#remediation-status-living--update-per-wave).

- [x] Read latest plans, handoffs, registers, and relevant pitfalls; verify remote state.
- [x] Create isolated worktree from `origin/dev` at `29adc11`; baseline 455 Vitest tests pass.
- [ ] Close frontend-logic N-9 and N-10, plus shared expiry N-11.
- [ ] Cover component page/detail rows N1–N12 and pagination N16.
- [ ] Cover filter-control rows N13–N15.
- [ ] Mutation-check load-bearing assertions and restore production files.
- [ ] Run eslint, TypeScript, Vitest, future-clock, and existing Playwright lanes.
- [ ] Independent adversarial review and any scoped re-review.
- [ ] Update living report and handoff, commit, open Routine PR, gate merge on green CI.

## Scope and preflight decisions

| Work area | Shared interface / consistency check | Outcome |
|---|---|---|
| Logic columns and page tests | Column definitions are read by both; tests live in distinct files | Root owns column tests; page worker owns pages.test.tsx and shared expiry/blueprint rendering cases |
| Page and filter-control tests | Both use real router/query/components and network-boundary fixtures | Filter worker uses a separate test module and existing shared test helpers; no production edits planned |
| Mutation verification | Workers would otherwise mutate shared source during another suite | No concurrent mutations; root coordinates after authoring completes |
| Component rows N2/N7 | Optional-envelope fallbacks are defensive branches; API normally fills those fields | Label omission fixtures as defensive, not representative API responses |
| Component row N8 and N17 browser gaps | Register suggests fixture-lane E2E additions; AGENTS.md forbids implementing E2E mocks | Ruling: add no E2E mocks. Close N8's component assertion, leave its browser duplication and N17 explicit residuals. Cost if wrong: browser duplication waits for Sam's choice of a real-data test setup or an explicit fixture-lane exception |
| Root untracked config | `.codex/config.toml` predates this work and is outside task scope | Ruling: preserve it untouched and work in isolation under Sam's explicit autonomy request. Cost if wrong: no config integration, no user data changed |
| Reward-per-jump and mobile live smoke | Latest handoff holds architecture/licensing and N18 for Sam | Preserve those holds; do not infer approval from autonomous continuation |

## Evidence

- Remote fetch succeeded; `gh pr list` returned no open PRs.
- Baseline: `npm test` — 32 files, 455 tests passed, pristine output.
- Environment: restored unchanged committed npm lockfile with `npm ci`; no dependency changes.

## Review ledger

Pending authoring and verification.
