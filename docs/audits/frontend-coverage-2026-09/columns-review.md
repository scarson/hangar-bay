<!-- ABOUTME: Reviews the frontend-logic N-9 literal sort-field snapshots against their register claim. -->
<!-- ABOUTME: Records whether plausible source edits can violate that claim while the focused tests pass. -->

# Frontend-logic N-9 focused review

**Verdict: CONVERGED.** No claim-level findings.

The literal table covers every segment accepted by `columnsFor`: no selection, item exchange,
auction, courier, loan, and unknown. For each segment it constrains both relevant memberships:

- `columnsFor(segment, false)` is flattened directly and compared with the handwritten literal, so
  the readiness-closed set has an independent oracle.
- `sortableFieldsFor(segment)` is compared with the same literal. Its source contract computes the
  segment's widest set through `columnsFor(segment, true)`, so additions or removals of sortable
  fields in the readiness-open set change the public result and fail the snapshot.

Within frontend-logic N-9's claim, plausible source-only edits are constrained: deleting, adding,
renaming, or swapping a base column's `sortField`; routing a segment to the wrong column set; or
adding a sortable readiness-gated blueprint column changes at least one literal comparison. Merely
changing `sortableFieldsFor` to inspect the closed set would not change current behavior because
the gated columns have no sort fields; it would violate the implementation rationale only after a
separate edit added such a field. Treating that coordinated pair as a current test gap would expand
the row beyond its per-segment membership claim.

## Plausible missed edits within the claim

None.

Sources reviewed:

- [`app/frontend/web/src/features/contracts/columns.test.ts`](../../../app/frontend/web/src/features/contracts/columns.test.ts)
  current working-tree delta for the N-9 snapshot.
- [`app/frontend/web/src/features/contracts/columns.tsx`](../../../app/frontend/web/src/features/contracts/columns.tsx)
  `columnsFor` and `sortableFieldsFor` behavior.
- [`docs/test-coverage-reports/subagent-frontend-logic-findings.md`](../../test-coverage-reports/subagent-frontend-logic-findings.md)
  §3 and nice-to-have row N-9: replace the self-referential consistency assertion with direct
  per-segment membership snapshots.
- [`docs/test-coverage-reports/2026-08-09-f008-remediation-test-coverage-review.md`](../../test-coverage-reports/2026-08-09-f008-remediation-test-coverage-review.md)
  §Wave 5 sweep: the exact remaining N-9 claim.
