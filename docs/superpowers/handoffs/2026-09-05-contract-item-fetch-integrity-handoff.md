ABOUTME: Hands off the reviewed contract item fetch integrity plan at the preparation checkpoint.
ABOUTME: Records observed state, verification, coordination boundaries and the next executor's grounding steps.

# Contract item fetch integrity handoff

Sam requested the next natural stopping point, a handoff, and a PR after resetting usage. This checkpoint delivers the reviewed plan. **Neither production task was started.** The next implementation is Task 1 of the [contract item fetch integrity plan](../../plans/2026-09-05-ingestion-item-fetch-integrity-plan.md), followed sequentially by Task 2.

## Observed publication state

Observed at **2026-09-05T19:45:49Z**, before publishing this handoff:

| Surface | Reading |
|---|---|
| Repository | `C:/Users/Sam/Code/hangar-bay`, remote `https://github.com/scarson/hangar-bay.git` |
| Root checkout | `dev` was at `a2ac558f1fbb0689ff1a91ccfcbc7249816eeb24`. The separate root status check at 2026-09-05T19:49:27Z showed only the pre-existing untracked `.codex/`. |
| Preparation worktree | `.claude/worktrees/ingestion-pipeline-plan`, branch `codex/ingestion-pipeline-plan`, tip `fd29e6d2dfc4e573d5d2d3bc2bbc1b8b9fc7dbf9`. Only the continuation note and two report files were pending before this handoff was written. |
| Preparation publication | No remote branch or PR for `codex/ingestion-pipeline-plan` was found. This session was preparing a documentation-only PR; its number and later checks were not yet available in this reading. |
| Separate contract-search work | `.claude/worktrees/bug-hunt-contract-search-2026-09-05` was at `24d4a311f44b852e054d89bc969d28373c7103e5`; [PR 193 — contract-search audit and remediation plan](https://github.com/scarson/hangar-bay/pull/193) was open. Its checks were not inspected for this handoff. |

At the timestamped 2026-09-05T19:49:27Z forge check, PRs 187–192 were merged and GitHub returned no open Dependabot alerts. These historical completions are recorded in the [continuation record](../../audits/m5-recon/2026-09-05-continuation.md) and the [frontend coverage handoff](2026-09-05-frontend-coverage-handoff.md); do not repeat those changes. The verified root configuration digest appears once under operational guardrails.

## Ready plan and verification

- Certification commit: `6b420dad0192e05a57ea26f9bca8a9d8f10ce99e`. The five-round review ended with a cold GPT-6 Astra high pass raising zero substantive findings. A Claude Opus 5 high round provided the required cross-provider review. The complete round table and all dispositions are in the continuation record; no findings were rejected.
- Editorial commit: `fd29e6d2dfc4e573d5d2d3bc2bbc1b8b9fc7dbf9`. One editor candidate produced 12 changed hunks. The verifier approved 11; the coordinator restored the remaining hunk exactly from the certified baseline because its rewrite dropped the no-op-recorder condition on a header requirement. [Editorial verdicts](../../audits/m5-recon/2026-09-05-item-fetch-editorial-review.md) preserve the result.
- The isolated unchanged backend passed **184 focused tests**, **822 full backend tests**, and `flake8 .` with pristine final output. The baseline is evidence about the inspected source, not verification of an implementation that has not been written.
- The final plan reviewer could not independently retrieve the upstream OpenAPI document. The plan distinguishes the coordinator's dated observations from its deliberate fail-closed client policy; see the [final review's limit](../../audits/m5-recon/2026-09-05-item-fetch-plan-final-review.md).

The plan's acceptance criteria are authoritative. Task 1 makes item reads uncached and rejects incomplete advertised page walks while preserving existing stored items, ship flags and enrichment versions on failure. Task 2 replaces tests that manufacture the unreachable `ESINotModifiedError` with real client responses at controlled HTTP/Redis boundaries, then removes that dead exception and its handlers. The broader request governor, scheduler and queue redesign are outside this slice.

## Successor actions and seams

1. **Resolve the preparation PR by branch.** If it is open, finish its applicable CI and review, then merge under the repository's Routine policy before creating the production branch. If merged, use the integrated plan. If closed without merge, compare `origin/dev` contents before recreating anything; the plan may have arrived another way. Missing remote branches are normal after merge. This documentation PR does not ship either production phase.
2. **Execute Task 1, then Task 2**, with a fresh implementer and task review for each. Read the plan's review line and phase banners against git before claiming work. Preserve the TDD and mutation evidence prescribed there. Record production commits separately from plan-status commits. Keep phases in progress until production integration.
3. **Publish the implementation as `Review — data-integrity paths`.** That future production PR had not been created at this checkpoint. Complete its tests and independent review, wait for green CI, and leave its merge decision to Sam. The permission to auto-merge this preparation's Routine documentation PR does not authorize the future data-integrity merge.
4. **Coordinate with the separate contract-search task** before root checkout writes. Its task title was “Run GPT-6 Astra bug hunt”, ID `01a0712e-dcf5-7522-ab7e-e3e9d943e535`. It owned the audit and planned saved-search validation/name-ordering work. If PR 193 is open, leave integration with its owner; if merged, account for its contents; if closed unmerged, check contents before assuming its work is missing. Do not edit its worktree or run tests against its database.

Use the existing preparation worktree only while its branch remains a valid unmerged work unit. After a Routine merge and cleanup, create a dedicated `codex/` implementation branch/worktree from freshly fetched `origin/dev`. Do not preserve a merged preparation branch as an undeclared production branch.

## Verification environment and operational guardrails

The baseline setup used Python 3.14.3 in this worktree's `app/backend/.venv`, a dedicated PostgreSQL database `hb_item_fetch_integrity_20260905a`, and Valkey DB 12. Its ignored settings and tool caches were local to that worktree and may disappear during cleanup. The runbook was `app/backend/.cache/item-fetch-baseline/runbook.md`; the execution ledger was `.superpowers/sdd/2026-09-05-ingestion-item-fetch-integrity-plan/progress.md`. Recheck their existence and database isolation before use; if absent, provision from the tracked configuration and frozen lock. Do not print credentials or run the destructive backend startup command.

The plan carries portable test commands. On this Windows host, pytest required a worktree-local `--basetemp`; omitting it caused six setup errors. The corrected full run passed. Temporary PDM and uv artifacts were moved beneath `.cache/.venv/` so the existing lint exclusion covered external code. PDM was verified through `.cache/.venv/pdm-tool/Scripts/python.exe -m pdm`; its relocated launcher should not be used. No lint configuration was weakened. Git for Windows skill scripts required `/usr/bin` in their shell PATH. Resolve installed executable paths; this host's PowerShell came from the Codex runtime.

The root configuration was deliberately preserved. Its verified SHA256 was `2AD8A9B68075E810D91D7FB4A1144063CB649DF7F21D364034495BA757342182`. Use per-command `safe.directory` for the exact worktree if the sandbox account differs from the file owner; do not change global git configuration.

An initial external review launch was rejected by automatic approval review. After verifying the repository was public and owned by Sam, a fixed public-source text bundle with tools/MCP disabled was approved and completed. A later text-only editorial invocation returned an unusable terminal transcript despite exit code zero. It was rejected as evidence; a fresh comparison using the mechanical diff returned all required verdicts. Judge the actual review artifact, not merely process success. No review process needed to continue at this checkpoint.

## Later work and deferrals

- **Ingestion metrics:** the [bounded maintenance assessment](../../audits/m5-recon/2026-09-05-next-maintenance-action.md) found the requested run-duration, request-count and item-count measurements absent, but no dedicated reviewed implementation plan. It is the smaller later planning task, after the item-fetch production change integrates. Its counting semantics and source overlap must be resolved before implementation.
- **Queued logging:** the same assessment found no QueueHandler/QueueListener implementation. Queue limits, overflow, drain/shutdown, context capture and rendering ownership need design decisions and a separate plan.
- **Courier reward-per-jump study:** Task 0.1 already shipped in PR 185. [Task 0.2's snapshot requirement](../plans/2026-08-10-reward-per-jump.md#task-02-measure-whether-the-denominator-choice-actually-reorders-anything) remains the gate for the study: one consistent read-only population plus configured ingestion regions and endpoint systems. The public listing observed during this session could not supply that evidence. Keep the production access-rule and routing-data decisions held until the documented prerequisites are met.
- **Other Plan B prerequisites:** request governance, 420/429 header treatment, total wait budgets, scheduler-derived lock lifetimes and measured queue indexing remain in the [ingestion design](../../audits/m5-recon/ingestion-clean-sheet-design.md) and [Plan B handoff](2026-07-27-plan-b-handoff.md). This plan does not stand in for the full pipeline design.

## Handoff review

The author applied all six lenses, then rechecked the repaired spans. The independent reviewer will write the [final handoff review](../../audits/m5-recon/2026-09-05-item-fetch-handoff-review.md) before publication; that record was absent when this draft was first written.

| Perspective | Material findings applied |
|---|---:|
| Naive fresh agent | 1 — removed a duplicate incorrect configuration digest |
| Recency bias | 0 |
| Work-unit seams | 1 — distinguished the future production PR from this documentation PR in the maintenance assessment |
| Operational guardrails | 1 — replaced inferred observation times with timestamped readings |
| Loss of hot context | 0 |
| Plan readiness versus production completion | 0 |

### Round 6 — Plan readiness versus production completion — 0 findings

This session produced an implementation plan, code examples, a working test environment and passing baseline tests. The sixth lens checked that none was presented as implemented or verified production behavior. Both phase banners remained not started, and the successor actions separated the Routine preparation PR from the future Review-class production PR.

## Continuation prompt

```text
# Contract item fetch integrity

0. Ground first. The preparation was observed at 2026-09-05T19:45:49Z. Check checkout, status, tips, remote containment, worktrees, associated PR states and checks. An empty result or error is information; a missing branch often means it merged. Live state wins. Moved state usually means work already landed, not work to redo. Commit non-ancestry is not proof the work is absent; a PR's state settles only that PR's merge, so target contents win when they disagree. Check contents before recreating closed-unmerged work. Stop and ask about unfamiliar divergence rather than overwriting it.
   Repository: C:/Users/Sam/Code/hangar-bay, origin https://github.com/scarson/hangar-bay.git; root dev was a2ac558f1fbb0689ff1a91ccfcbc7249816eeb24 with only pre-existing untracked .codex/.
   Preparation: .claude/worktrees/ingestion-pipeline-plan, branch codex/ingestion-pipeline-plan, tip fd29e6d2dfc4e573d5d2d3bc2bbc1b8b9fc7dbf9; documentation was pending, with no remote branch or associated PR yet found. Recheck the PR by head branch because publication followed this reading.
   Parallel work: .claude/worktrees/bug-hunt-contract-search-2026-09-05 was 24d4a311f44b852e054d89bc969d28373c7103e5; scarson/hangar-bay PR193 was open. Root status and PRs187-192 were rechecked at 19:49:27 UTC: only .codex/ was untracked, those PRs were merged, and open Dependabot alerts were empty. The isolated backend environment/runbook may have been removed during cleanup; recheck before use.
1. Read docs/superpowers/handoffs/2026-09-05-contract-item-fetch-integrity-handoff.md and docs/plans/2026-09-05-ingestion-item-fetch-integrity-plan.md. Both production tasks were unstarted. Resolve the preparation PR: open means finish its Routine checks/review and merge; merged means use the integrated plan; closed-unmerged means inspect origin/dev contents before restoring missing work.
2. Use a dedicated codex/ implementation worktree from current origin/dev after preparation integration. Execute Task1 and then Task2 with TDD, the prescribed failure-preservation/mutation checks, and independent reviews. Preserve unrelated .codex/ files and coordinate root writes with the contract-search task; do not touch its worktree or database.
3. Publish the production change only after verification as Review — data-integrity paths, leaving its merge to Sam. Do not confuse the documentation PR with production delivery. Keep the courier snapshot gate and broader ingestion redesign deferred as documented.
```
