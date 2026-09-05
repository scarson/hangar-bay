<!-- ABOUTME: Preserves planning and review lessons from the contract-search bug hunt. -->
<!-- ABOUTME: Records review outcomes and verification limits for continuation. -->

# Contract-search planning and review learning

Type: pattern. Key: `plan-review-contract-search`.

The [remediation plan](../plans/2026-09-05-contract-search-bug-hunt-remediation-plan.md) implements the [approved audit findings](../bug-hunts/2026-09-05-contract-search-consolidated.md). Backend runtime verification belongs to implementation; source-derived SQL correctness and synthetic scaling remain explicit gates.

## Plan-construction review

| Round | Reviewer | Findings raised | Fixed | Rejected |
| --- | --- | --- | --- | --- |
| 1 | Author self-review | 3 | 3 | 0 |
| 2 | Independent cold GPT-6 Astra/high | 2 | 2 | 0 |
| 3 | Author self-review | 0 | 0 | 0 |
| 4 | Independent cold GPT-6 Astra/high | 1 | 1 | 0 |
| 5 | Author self-review | 0 | 0 | 0 |
| 6 | Independent cold GPT-6 Astra/high | 0 | 0 | 0 |

Self-review repairs: corrected the notification hook path to `useNotifications.ts`; exposed both live-text error and effective-text blocking state to avoid showing stale query errors during debounce recovery; established Name-sort TDD red using existing HTTP interfaces before adding a helper whose absence would cause only an import failure. Verified the hook export, ContractsPage branches, and backend fixture/test paths against source.

Independent review repairs: database preflight now covers the full suite's derived `m4_equiv_check` target and same-server exclusivity, verified in `blank_migrated_sync_connection`; saved-create 422 fallback now covers name as well as criteria, with a name-field response regression, verified against `SavedSearchCreate.name` and the form. Both raised findings were accepted; no concurrence is pending. See the [complete independent findings](../bug-hunts/2026-09-05-contract-search-plan-review-1-round-2.md).

Round 3 checked all review dimensions and the complete repair wave; no further substantive gap was found. Primary-target serialization remains required alongside full-suite migration-target isolation. A subsequent independent round must verify the repaired plan before certification.

Round 4 found raw URL equality was stricter than query-cache identity. The [complete round-four findings](../bug-hunts/2026-09-05-contract-search-plan-review-1-round-4.md) include an actual-hook probe confirming cached metadata retains untrimmed request provenance. Task 2.1 now compares serialized queries in both correction guards and excludes placeholder responses while preserving raw debounce equality. Verified `toApiQuery` normalization and the installed `hashKey` export; no production comparator was changed during planning.

Round 5 reread the full plan and claim changes across companions; no further substantive finding. The runtime probe's generated route-file rewrite contained no content diff and was restored. Independent verification of the canonical-identity repair remains required.

The [round-six independent review](../bug-hunts/2026-09-05-contract-search-plan-review-1-round-6.md) raised zero substantive findings, completing plan-construction review after six rounds. All six raised findings were fixed and independently re-reviewed; none were rejected. The bug-hunt workflow's final plan-review phase remains separate from this construction gate.

Notes: all dispatched agents are GPT-6 Astra/high under Sam's explicit model constraint. Cross-provider review is omitted to honor that constraint; independent cold contexts still review actual source. Repository output-persistence policy takes precedence over the skill's temporary-review-file convention. Review findings are retained in the audit directory; any rejection-concurrence scratch file remains temporary.

## Reusable observations

- Query `enabled` does not constrain manual `refetch`. Validation needs both dispatch gating and an explicit UI state that accounts for live versus debounced input.
- A display-derived SQL key must reproduce the entire fallback chain, including whitespace and direction-independent item selection, while filter joins continue to select the contract population independently.
- A helper that does not exist yet cannot furnish useful red-test evidence through an import error. First pin the externally observable failure with existing interfaces, then add helper-level parity checks.
- Full-suite database isolation must follow derived fixture targets, not only the configured test database. The migration equivalence fixture uses a fixed database name on the same server.
- Request ownership follows canonical cache identity. A raw URL comparator can reject a response that the cache correctly treats as belonging to the requested wire query.

## Operational record

The worktree remains isolated from concurrent root-checkout work. Initial file guesses for a notification hook and router helper were corrected using file discovery; the plan names the verified files. Installed frontend query-core source and Python Unicode enumeration informed planning, but neither substitutes for the required HTTP/PostgreSQL tests.
