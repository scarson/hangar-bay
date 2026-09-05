<!-- ABOUTME: Execution checklist and evidence for the remaining Wave 5 frontend coverage. -->
<!-- ABOUTME: Records scope decisions, verification, review findings, and integration status. -->

# Frontend coverage continuation — September 5, 2026

Work order: [latest coverage handoff](../../superpowers/handoffs/2026-08-10-wave-5-backend-closed-frontend-started-handoff.md), backed by the [living remediation table](../../test-coverage-reports/2026-08-09-f008-remediation-test-coverage-review.md#remediation-status-living--update-per-wave).

- [x] Read latest plans, handoffs, registers, and relevant pitfalls; verify remote state.
- [x] Create isolated worktree from `origin/dev` at `29adc11`; baseline 455 Vitest tests pass.
- [x] Close frontend-logic N-9 and N-10, plus shared expiry N-11.
- [x] Cover component page/detail rows N1–N12 and pagination N16 (N8 browser duplication stays residual).
- [x] Cover filter-control rows N13–N15.
- [x] Mutation-check load-bearing assertions and restore production files: 67/67 caught.
- [x] Run eslint, TypeScript, Vitest, future-clock, and existing Playwright lanes.
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
- Column membership: 11 tests passed (six independent segment snapshots plus existing invariants); focused eslint passed.
- Page/detail authoring: 145 tests passed. Filter authoring: 18 tests passed. Combined baseline after formatting cleanup: all 174 tests in the three changed files passed.
- Existing Playwright baseline: 146 passed, 7 skipped. The three opt-in live-smoke cases and four viewport-inapplicable cases account for all skips. Initial output contained a Node color-variable warning; final verification will remove the conflicting `NO_COLOR` variable from the command environment.
- Browser verification with the conflicting environment variable removed and normal process permissions: 146 passed, 7 expected skips, exit 0 in 29.9 seconds, no warnings or errors.
- Full final lanes: eslint and `tsc -b` exit 0 with no output; Vitest 509/509; future-clock 509/509 at `2027-10-10T10:19:27.096Z`; existing Playwright 146 passed and 7 expected skips. Production source and dependency manifests are unchanged.

## Environment findings

The sandboxed Playwright invocation completed every test but waited indefinitely for its Vite child during teardown. Installed Playwright's Windows launcher invokes `taskkill /pid ... /T /F` and waits for process closure; the task-owned npm/Vite tree remained alive after all workers exited. Read-only process inspection also returned Access denied inside the sandbox. After validating all four child process IDs and the Vite command's worktree path, an elevated `Stop-Process -Force` stopped only that server tree and the original test runner immediately reported 146 passed, 7 skipped, exit 0. A first stop without `-Force` failed inside PowerShell with an object-reference error. Run the final browser lane outside the process-restricted sandbox so it can tear down its own child tree normally; do not change application code or test timeouts for this environment issue.

Vitest renders substituted string labels with quotes in parameterized test titles. The mutation harness rejected a selector that matched zero tests and restored source without recording a kill. All 67 selectors were then checked against the actual names in a passing JSON test report; quoted titles were resolved to those names before resuming. A report path with four parent traversals landed one directory above the intended worktree; the report was moved to the verified absolute task path. Mutation snapshots and subsequent reports use absolute paths.

## Review ledger

- Preliminary column review: CONVERGED, no claim-level findings; [focused review](columns-review.md).
- Parent review expanded history coverage from Search alone to all nine text/numeric inputs, added sole-filter category and both blueprint-flag cases, and required awaiting final request values rather than a first-keystroke request count. These findings were fixed before the mutation round.
- Final independent Codex review pending complete mutation and suite evidence.
