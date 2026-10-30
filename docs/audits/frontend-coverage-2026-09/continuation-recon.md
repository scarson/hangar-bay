<!-- ABOUTME: Identifies the highest-priority executable continuation after the 2026-08-10 coverage handoff. -->
<!-- ABOUTME: Separates the remaining frontend coverage queue from work that requires Sam's decisions. -->

# Frontend coverage continuation reconnaissance

## Recommendation

Continue Wave 5 frontend coverage in the order recorded by the latest handoff: close frontend-logic
N-9 and N-10, then close frontend-components N-1 through N-17. Close the shared expired-row gap
once during the component work; it is frontend-logic N-11 and frontend-components N-11.

This is the most important currently executable thread because the latest handoff makes it the
first item in its queue, and the campaign's living remediation table identifies it as the only
in-progress coverage slice not held for a decision. The backend-read register is closed 10/10,
backend-write is closed 18/18, frontend correctness is closed 28/28 logic plus 10/10 components
and 3/3 e2e pins, and the first
10 of 13 frontend-logic nice-to-have rows are closed. Re-running those sweeps would duplicate
completed work.

## Authoritative sources

- [`docs/superpowers/handoffs/2026-08-10-wave-5-backend-closed-frontend-started-handoff.md`](../../superpowers/handoffs/2026-08-10-wave-5-backend-closed-frontend-started-handoff.md)
  §§0-3 and §7: superseding handoff, ordered queue, remaining logic rows, reward-per-jump state,
  and work held for Sam.
- [`docs/test-coverage-reports/2026-08-09-f008-remediation-test-coverage-review.md`](../../test-coverage-reports/2026-08-09-f008-remediation-test-coverage-review.md)
  §Remediation status and §Wave 5 sweep: living campaign source of truth, completed work, duplicate
  row reconciliation, and the configuration change excluded from the test-only wave.
- [`docs/test-coverage-reports/subagent-frontend-logic-findings.md`](../../test-coverage-reports/subagent-frontend-logic-findings.md)
  §Gap register: original frontend-logic findings. Its prose is evidence; the later living wave
  table and superseding handoff determine current status.
- [`docs/test-coverage-reports/subagent-frontend-components-findings.md`](../../test-coverage-reports/subagent-frontend-components-findings.md)
  §4: original component nice-to-have rows.
- [`docs/superpowers/plans/2026-08-10-reward-per-jump.md`](../../superpowers/plans/2026-08-10-reward-per-jump.md)
  Phase 0 Task 0.2: executable ranking-inversion measurement; Phases 1-4 are blocked.
- [`docs/superpowers/specs/2026-08-10-reward-per-jump-spec.md`](../../superpowers/specs/2026-08-10-reward-per-jump-spec.md)
  §2 and its appendix: architectural denominator decision and unresolved licensing evidence.

## Executable queue

1. **Frontend-logic N-9 — sortable-field membership.** Replace the self-referential
   `sortableFieldsFor` expectation with handwritten per-segment membership snapshots.
2. **Frontend-logic N-10 — blueprint list cell.** Assert that one blueprint copy with one null
   figure renders a blank list-level cell.
3. **Frontend-components N-1 through N-17.** Cover the page-out-of-range skeleton; size fallback;
   courier-origin suppression; filter glyph state; replace-history semantics; unknown-contract
   title and journey; missing count fallback; item-less in-flight suppression; non-sortable header
   and direction glyphs; refresh opacity; expired-row warning class; detail guards, suppression,
   fallbacks, and retry; FilterRail empty/removal/disjunct/count-chip paths; taxonomy empty/scoping
   paths; empty-string bound removal; pagination zero/unit-label paths; and e2e journeys already
   pinned at unit level.
4. **Shared expired-row gap.** Component N-11 renders the same `EXPIRES_COLUMN` `text-warn` branch
   named by logic N-11. One test closes both rows.

Frontend-components N-18 is outside this executable test-only queue. It changes
`playwright.config.ts` to add a mobile live-smoke lane, so the living sweep flags it for Sam.

Reward-per-jump Phase 0 Task 0.2 is independently executable after the frontend queue. It takes one
live courier snapshot, compares ESI `secure` counts with true shortest all-high-sec BFS counts, and
reports ranking inversions, top-10 overlap, and the maximum ratio difference against the plan's
predeclared threshold. It does not authorize Phase 1 or later.

## Work held for Sam

- Reward-per-jump source selection: licensing for onward redistribution of the Fuzzwork graph data
  is unresolved. Do not implement Phases 1-4 until Sam answers the architectural decision.
- The Grafana Cloud alert rules for last successful ingestion and malformed-date skips.
- The remaining mocked-behavior hazard: delete the unsupported-dialect fallback, rename its test to
  describe dialect dispatch, or accept the documented residual.
- The production database allow rule `198.37.143.189/32` and the dev-to-main release.
- The eleven F008 pre-release product and architecture choices covering search semantics, segment
  counts, dead ESI handlers, ingestion truncation, taxonomy composition, auction blueprint
  display, integer widths, transient filter visibility, sort disclosure, taxonomy read
  consistency, and the `min_runs` sentinel rationale. They are enumerated in
  [`docs/bug-hunts/2026-08-08-f008-prerelease-consolidated.md`](../../bug-hunts/2026-08-08-f008-prerelease-consolidated.md)
  under §Design Decisions Requiring Input.
- Ratification or reversal of treating backend-write N-11's `"a contract"` fallback as
  defense-in-depth.
- Frontend-components N-18, because it changes the live-smoke lane configuration.

## Repository state at continuation

Fresh `origin/dev` is `29adc11` with zero open pull requests. The continuation worktree is
`.claude/worktrees/coverage-frontend` on `codex/coverage-frontend`. The root checkout's untracked
`.codex/config.toml` remains untouched and outside this work.
