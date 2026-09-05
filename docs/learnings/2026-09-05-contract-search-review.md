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

## Construction editorial pass

The first editorial pass certified all 29 changed hunks as preserving meaning, with no drift or baseline notes. It used separate GPT-6 Astra/high editor and verifier contexts and committed only the plan at `debc63f237468cc7edcce02c73be87fc944f2590`, directly atop the construction certification at `26a76bd7d0bdad07c31cabf62db219cd6eff6a9e`. See the [complete first editorial verification](../bug-hunts/2026-09-05-contract-search-editorial-1-verification.md).

## Final bug-hunt plan review

| Round | Reviewer | Findings raised | Fixed | Rejected |
| --- | --- | --- | --- | --- |
| 1 | Author self-review | 0 | 0 | 0 |
| 2 | Independent cold GPT-6 Astra/high | 1 | 1 | 0 |
| 3 | Author self-review | 0 | 0 | 0 |
| 4 | Independent cold GPT-6 Astra/high | 0 | 0 | 0 |

The author reviewed the polished plan across ambiguity, context gaps, interpretation latitude, dependencies and both pitfall dimensions. The source-grounded construction checks and complete polished text were checked together; no substantive gap was found in round 1.

The [round-two independent findings](../bug-hunts/2026-09-05-contract-search-plan-review-2-round-2.md) identified one coverage-preservation gap: the empty joined-ID pagination test selects its path through Name sorting alone. Task 5.1 now includes `type_ids=587`, matching both fixture rows while retaining the join after the Name-sort change, and preserves the response assertions. Source checks verified `_needs_item_join`, `_apply_item_filters`, the fixture's type IDs and the existing test. Round 3 checked the repair and all six review dimensions without another substantive finding.

The [round-four independent review](../bug-hunts/2026-09-05-contract-search-plan-review-2-round-4.md) raised zero substantive findings, completing the final review after four rounds. The single finding was fixed and independently re-reviewed; no rejection or unverified repair remains. The most recent plan-review line records this four-round cycle separately from construction review.

Notes: all reviewers remain GPT-6 Astra/high under Sam's explicit constraint. Cross-provider review is omitted under that constraint. No rejection awaits concurrence.

## Final editorial pass

The [complete final editorial verification](../bug-hunts/2026-09-05-contract-search-editorial-2-verification.md) marks all 25 zero-context Git diff hunks PRESERVED, with no drift or baseline notes. Separate fresh GPT-6 Astra/high editor and verifier contexts were used; cross-provider review was omitted under Sam's constraint. The complete candidate was accepted without manual patching.

editorial-pass: attempts 1 · hunks rewritten 25, reverted 0 · certified `18f2a3a5c7f56c12a392fd00d069de1858af0546` → `838b6bda4ab36df61749eed0f8615ce1046b946f` · prompts v1.

The polish commit contains only the plan and is directly atop certification. The initial hunk-count cross-check used Python's diff segmentation and counted 24; repeating it with the verifier's zero-context Git diff confirmed all 25 report entries before acceptance. No plan bytes were changed by the failed cross-check.

## Reusable observations

- Query `enabled` does not constrain manual `refetch`. Validation needs both dispatch gating and an explicit UI state that accounts for live versus debounced input.
- A display-derived SQL key must reproduce the entire fallback chain, including whitespace and direction-independent item selection, while filter joins continue to select the contract population independently.
- A helper that does not exist yet cannot furnish useful red-test evidence through an import error. First pin the externally observable failure with existing interfaces, then add helper-level parity checks.
- Full-suite database isolation must follow derived fixture targets, not only the configured test database. The migration equivalence fixture uses a fixed database name on the same server.
- Request ownership follows canonical cache identity. A raw URL comparator can reject a response that the cache correctly treats as belonging to the requested wire query.
- Changing a query-path trigger can leave existing tests green while removing the path coverage their names claim. Preserve the trigger through another supported input and keep the response assertions.

## Operational record

The worktree remains isolated from concurrent root-checkout work. Initial file guesses for a notification hook and router helper were corrected using file discovery; the plan names the verified files. Installed frontend query-core source and Python Unicode enumeration informed planning, but neither substitutes for the required HTTP/PostgreSQL tests.

At the completed-review phase boundary, the clean campaign branch was rebased onto freshly fetched `origin/dev` at `4f12261`. The audited production source, regression tests and selected plan/design bytes did not change across the rebase. Upstream changes covered dependency maintenance, deployment diagnostics and handoff evidence. The local tag `audit/contract-search-2026-09-05-review-history` retains the complete pre-rebase history at `c4fae6494c87665e74d77cc6b1e31e97dc6cd8cf`, preserving the historical certification and editorial commit references in this record. The rebased final-review certification is `18f2a3a5c7f56c12a392fd00d069de1858af0546`.

The second editorial pass's initial byte check aborted because Git checkout converted LF to CRLF. A raw-byte comparison proved checkout conversion was the only difference. A command-scoped `core.autocrlf=false` checkout restored the exact certified blob; the repeated check passed before dispatch. No global Git setting or plan substance changed. The pitfall-ID census after rebase found no duplicates, and the shared-pitfall diff contains only the two intended additions.
