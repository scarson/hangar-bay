<!-- ABOUTME: Hands off the reviewed contract-search bug hunt and remediation plan. -->
<!-- ABOUTME: Preserves PR state, approved decisions, verification limits, and execution order. -->

# Contract-search remediation — September 5, 2026

## Headline state

Observed at `8bb282e869eea38d408ce63daee3e7af2762a500` / 2026-09-05T19:41:41Z:

- The clean worktree `C:/Users/Sam/Code/hangar-bay/.claude/worktrees/bug-hunt-contract-search-2026-09-05` was on `codex/bug-hunt-contract-search-2026-09-05`, tracking the identically named origin branch. It was nine commits ahead of `origin/dev` and zero behind after rebasing onto `a2ac558f1fbb0689ff1a91ccfcbc7249816eeb24`.
- [PR #193 — audit contract search and plan remediation](https://github.com/scarson/hangar-bay/pull/193) was open, mergeable and classified `Review — public API and ordering semantics`. Its documentation-only CI path had passed; four CodeQL language jobs were running and the aggregate CodeQL job was queued. Sam owns the merge decision.
- The root checkout was on `dev` at `a2ac558f1fbb0689ff1a91ccfcbc7249816eeb24` with the pre-existing untracked `.codex/` directory. This campaign never touched it.
- The separate ingestion worktree was on `codex/ingestion-pipeline-plan` at `6b420dad0192e05a57ea26f9bca8a9d8f10ce99e`, four commits ahead of its tracked `origin/dev`, with untracked `docs/audits/m5-recon/2026-09-05-next-maintenance-action.md`. That state belongs to the other task and must not be changed here.

The handoff commit necessarily follows the observed tip above. Its SHA is not invented inside this file; read the latest branch commit after grounding.

## Delivered scope

- The [consolidated bug hunt](../../bug-hunts/2026-09-05-contract-search-consolidated.md) records six confirmed bugs: response-owned pagination, warm-cache readiness, saved-text boundary disagreement, invisible row mutation failures, incomplete saved criteria summaries and discarded actionable save errors. It separately records six non-pristine notification-fixture warnings and the approved Name-sort design change.
- Four independent hunter methods, two focused verifiers and a report reviewer produced source and runtime evidence. All dispatched agents used GPT-6 Astra with high reasoning effort, as Sam required.
- The [reviewed remediation plan](../../plans/2026-09-05-contract-search-bug-hunt-remediation-plan.md) contains six phases and seven sequential tasks. Construction review ended after six rounds with an independent zero-finding round; the final bug-hunt review ended after four rounds with another independent zero-finding round.
- Independent editorial passes accepted 29 and 25 changed hunks with no drift or baseline notes. The [review record](../../learnings/2026-09-05-contract-search-review.md) preserves every repair, certification and verification limit.
- `docs/pitfalls/testing-pitfalls.md` adds TEST-29 for failure after cached success and TEST-30 for response-driven navigation across request populations.
- The final mechanical pass checked 21 audit/planning artifacts, all local links and ABOUTME headers, every one of 35 labelled reconciliation entries, the verbatim Living Document Contract, six NOT STARTED phase banners and seven tasks. The PR contains documentation only.

No production fix was implemented or claimed.

## Approved decisions

Sam explicitly approved both decisions on September 5, 2026:

1. Preserve existing overlong saved text and permissive reads. Reject new saved terms above 100 Unicode code points, keep invalid input visible and show local validation on Apply. Do not truncate or migrate stored values.
2. Sort Name by the displayed contract headline. Use a direction-independent headline key and ascending contract-ID ties in both directions.

The existing saved-price ceiling of `1e15` remains. The plan improves feedback without changing that domain.

## Verification evidence and limits

- Frontend baseline: 509 Vitest tests passed across 33 files, with six unexpected unread-notification query warnings. Those warnings are the documented fixture issue and mean the baseline output was not pristine.
- Four actual React/router/hook probes confirmed the page overwrite, invisible rename error, retained readiness after failed refresh and 101-character frontend/API disagreement. The final observation run passed 4/4 with clean output. The archived probes describe defects and are not intended-behavior regression tests.
- Frontend dependencies were restored from the unchanged trusted lockfile. No manifest or lockfile changed.
- Backend dependencies were unavailable during the hunt. No backend suite, PostgreSQL execution, production data inventory, live ESI access or browser E2E run was performed. The plan keeps these as implementation gates rather than treating source inspection as runtime proof.
- PR #193's documentation path skipped backend, frontend and OpenAPI jobs by design. CodeQL state is volatile and must be re-read.

## Seam with concurrent work

PR #192 advanced `origin/dev` after this campaign's first publication. The audit branch was rebased again and force-pushed with lease; its only upstream addition was the reward-per-jump plan, so the audit artifacts did not conflict or change meaning. No root reset or merge was performed by this task.

The ingestion task owns `.claude/worktrees/ingestion-pipeline-plan` and its untracked maintenance-action report. Coordinate before any future `gh pr merge` or root `dev` reset because the repository permits only one root writer at a time. Isolated implementation work may proceed without writing root `dev` once PR #193's disposition and Sam's implementation instruction are known.

The local-only tag `audit/contract-search-2026-09-05-review-history` retains the pre-rebase review history at `c4fae6494c87665e74d77cc6b1e31e97dc6cd8cf`. It is an archaeology aid, not a remote delivery mechanism; the PR branch contains the rebased audit artifacts and is authoritative for review.

## Ready to dispatch

The remediation plan is executable sequentially with fresh GPT-6 Astra agents. Tasks share frontend files and the generated frontend API contract depends on the backend request-model split, so parallel implementation would create avoidable conflicts and stale generated output.

PR-state outcomes:

- If PR #193 merged, verify the audit artifacts are present on `origin/dev`; do not recreate them. Remove the merged audit worktree and branch under the repository cleanup rules when it is safe to take the root-writer window. Start implementation only when Sam asks to execute the plan.
- If PR #193 remains open, inspect all checks. Investigate a failed check within this branch, but leave the Review-class merge to Sam.
- If PR #193 is closed without merge, inspect `origin/dev` contents before recreating anything. If the artifacts landed through another route, treat them as shipped. If they are absent, report the closed disposition to Sam before deciding whether to republish.

## Not yet started

All plan phases remain `⬜ NOT STARTED`:

1. Repair authenticated frontend test fixtures so passing output is pristine.
2. Make page correction and taxonomy readiness belong to the current request.
3. Split saved-search creation validation from permissive stored reads, regenerate the API contract and give invalid input actionable feedback.
4. Render row-scoped rename/delete errors and complete saved criteria summaries.
5. Sort by the displayed headline through a PostgreSQL-verified contract-level key and run the bounded performance diagnostic.
6. Run composed frontend/backend/schema verification and prepare the implementation Review PR.

## Operational guardrails

- Read `AGENTS.md`, both pitfall documents, the consolidated report and the whole plan before production work.
- Follow TDD for every production fix: intended-behavior failure first, then the smallest implementation and green proof. Do not turn the archived defect observations into passing regression expectations.
- Before backend tests, prove both `DATABASE_URL_TESTS` and the session-scoped `m4_equiv_check` database are disposable and exclusively owned. Use an isolated disposable PostgreSQL instance if exclusivity is uncertain. Never run destructive database fixtures against development or production data.
- Never hand-edit `openapi.json`, `schema.d.ts` or `routeTree.gen.ts`; regenerate them from their authoritative source.
- Do not add E2E mocks. Keep error output pristine and never weaken assertions to settle timing races.
- Preserve raw URL state while comparing canonical wire-query identity for response ownership. Manual query refetch bypasses `enabled`, so invalid text must also be blocked inside the query function.
- Preserve already-stored overlong saved text through GET, rename and delete. Narrow only the creation request model.
- The Name-sort SQL must match every `_primary_label` fallback, keep ascending contract-ID ties for both directions and retain joined-pagination coverage through another real join trigger after Name stops triggering the join.
- Treat PostgreSQL execution and the 1,000/10,000-contract performance diagnostic as required gates. Do not infer an index or architecture change from source inspection.
- Use only GPT-6 Astra agents for delegated continuation work, preserving Sam's model constraint.

## Handoff review

### Round 1 — Naive fresh agent — 3 findings applied

Clarified that the PR is documentation-only, implementation is not authorized merely by merge, and each open/merged/closed-unmerged outcome has a concrete next action.

### Round 2 — Recency-bias audit — 3 findings applied

Restored the early baseline warnings, actual runtime probes and backend verification limits that the final review/PR work could otherwise overshadow.

### Round 3 — Seam auditor — 3 findings applied

Captured PR #192's second rebase, the other task's dirty ingestion worktree and the single-root-writer coordination requirement.

### Round 4 — Operational guardrails auditor — 5 findings applied

Made the database preflight, generated-code rules, TDD boundary, E2E-mock prohibition and Review-class merge ownership explicit.

### Round 5 — Loss-averse auditor — 3 findings applied

Preserved the unrelated root `.codex/` directory, the local audit-history tag context and the distinction between defect-observation probes and future regression tests.

### Round 6 — Cross-layer contract executor — 4 findings applied

Checked the handoff specifically for the search flow's frontend/backend/SQL seams. Added manual-refetch gating, permissive read/request-only validation, joined-path test preservation and measured PostgreSQL performance requirements.

### Final full sweep — 0 findings

Re-ran all six perspectives after applying their findings. The prompt and PR-state branches remained self-contained, the volatile claims were observational and each implementation boundary pointed to its authority.

## Priority queue

1. Re-ground PR #193 and repository/worktree state.
2. If PR #193 is open, monitor checks and report its Review disposition to Sam. Do not merge it for Sam.
3. If Sam requests implementation after the audit artifacts are present on `origin/dev`, create a fresh dedicated worktree from fetched `origin/dev` and execute the remediation plan sequentially.
4. Update the plan's Living Document banners and evidence after every phase; create the final implementation PR as `Review — public API and ordering semantics`.

## Continuation prompt

```text
# Hangar Bay contract-search remediation

0. Ground yourself before doing anything else. The state described below was
   observed at 2026-09-05T19:41:41Z, at audit tip
   8bb282e869eea38d408ce63daee3e7af2762a500. The world may have moved since;
   finding that it did is normal.

   Answer these before acting, using the tools available in your environment.
   An error or empty result is information, not a malfunction.
   - For each repository/worktree below: what is checked out, is it clean, what
     is its tip, is the handed-off work on a remote, and do the named branch and
     worktree still exist?
   - For PR #193: is it open, merged or closed-unmerged; if merged, at what
     commit; and what do its checks report?
   - Has another task taken the root-writer window or changed the ingestion
     worktree?

   A squash or rebase merge can rewrite commits, so absence of the exact audit
   tip from dev does not prove the work is absent. PR state settles only whether
   that PR merged; work may land by cherry-pick, manual application or a
   superseding PR. When PR state and target-branch contents disagree, contents
   win. Confirm absence before recreating work.

   Live state beats this frozen reading. State moving usually means pending work
   landed and is not a reason to redo it. If live state diverged in an unaccounted
   way, including unfamiliar commits, a force-push or someone else's in-flight
   work, stop and ask Sam rather than improvising reconciliation.

   Observed manifest:
   repo C:/Users/Sam/Code/hangar-bay (origin https://github.com/scarson/hangar-bay.git) branch dev tip a2ac558f1fbb0689ff1a91ccfcbc7249816eeb24 — clean except pre-existing untracked .codex/
   repo C:/Users/Sam/Code/hangar-bay/.claude/worktrees/bug-hunt-contract-search-2026-09-05 branch codex/bug-hunt-contract-search-2026-09-05 tip 8bb282e869eea38d408ce63daee3e7af2762a500 — clean and pushed
   repo C:/Users/Sam/Code/hangar-bay/.claude/worktrees/ingestion-pipeline-plan branch codex/ingestion-pipeline-plan tip 6b420dad0192e05a57ea26f9bca8a9d8f10ce99e — untracked maintenance-action report owned by another task
   PR 193 in scarson/hangar-bay — open and mergeable; docs CI passed; CodeQL running/queued; Review-class, Sam merges

1. Read AGENTS.md, both docs/pitfalls files, the consolidated report at
   docs/bug-hunts/2026-09-05-contract-search-consolidated.md, the review record
   at docs/learnings/2026-09-05-contract-search-review.md, and the complete plan
   at docs/plans/2026-09-05-contract-search-bug-hunt-remediation-plan.md.

2. Resolve PR #193 before implementation. If merged, verify the artifacts on
   origin/dev and do not recreate them. If open, inspect checks, investigate any
   failure and leave the Review-class merge to Sam. If closed without merge,
   inspect origin/dev contents first; report to Sam if the work is genuinely
   absent. Coordinate before any root dev reset or gh pr merge.

3. Do not infer production-fix authorization from the audit PR merging. When Sam
   requests plan execution, fetch origin/dev, create a fresh dedicated worktree
   and run all six phases/seven tasks sequentially with fresh GPT-6 Astra agents.
   Follow TDD and update every Living Document banner as work ships.

4. Preserve the approved contracts: existing overlong saved text stays readable;
   new saved text over 100 Unicode code points is rejected with visible local
   feedback; Name sorts by displayed headline with a direction-independent key
   and ascending contract-ID ties. Keep the saved-price ceiling at 1e15.

5. Treat database safety, PostgreSQL SQL execution, generated API regeneration,
   joined-pagination preservation and the bounded sort-performance diagnostic as
   completion gates. Never hand-edit generated files or add E2E mocks. The prior
   hunt did not run backend, PostgreSQL or browser E2E checks.

6. Prepare the implementation PR as Review — public API and ordering semantics.
   Keep root .codex/ and the ingestion worktree untouched, and coordinate the
   single root-writer window before merge or root reset.
```
