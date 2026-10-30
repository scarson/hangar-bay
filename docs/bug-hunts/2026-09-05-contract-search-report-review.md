<!-- ABOUTME: Independently reviews the consolidated contract-search audit against its raw reports and source evidence. -->
<!-- ABOUTME: Records report corrections, candidate reconciliation, and the limits of this document-only review. -->

# Consolidated contract-search report review

Status: DONE_WITH_CONCERNS. Reviewed the consolidated report as present on September 5, 2026, against application source at `d43da7c`, all four sibling hunter reports, both independent verification reports, and the archived runtime observation source. This review did not inspect git history or prior conversation, run tests or probes, access a database, launch servers, or change application code. Only this review file was written. Line spans below identify the reviewed report text before coordinator corrections.

## Findings

### 1. Separate the already-required price-error feedback from the optional price-domain decision

**Priority:** P2, report/actionability. **Report span:** `2026-09-05-contract-search-consolidated.md:87-91`, Q2, and its reconciliation disposition at line 185.

Q2 places its recommended remedy under “Design decisions requiring Sam” and records it as awaiting an answer, even though the recommendation preserves both accepted numeric domains and merely explains the existing saved ceiling. The alternative domain changes require a choice; this behavior-preserving feedback remedy does not. Leaving the entire candidate at a decision gate obscures an actionable part of differential D2 and can unnecessarily block completing the known failure feedback.

**Evidence:** `design/features/F005-Saved-Searches.md:170-173` already requires user-friendly API failure messages. The current ceiling is explicit at `app/backend/src/fastapi_app/schemas/account.py:13,26-27`. `app/frontend/web/src/features/saved-searches/components/SaveSearchControl.tsx:98-100` tells every non-conflict failure to retry, including a deterministic over-ceiling rejection. The boundary verifier's “Price ceiling asymmetry” section explicitly identifies clear save validation for the established ceiling as a smaller behavior-preserving remedy and says changing the numeric ceiling is unnecessary for that improvement. This is the same distinction the consolidated report correctly makes for B6's deterministic capacity error.

**Correction:** Reconcile D2's unhelpful validation feedback as routine remediation, either as a separately counted narrow feedback finding or explicitly within the saved-create feedback scope. Keep Q2 solely for an optional change to the numeric domains, and state that such a change is unnecessary to fix the feedback. Update the results/count and decision wording to agree with the chosen grouping. This does not authorize changing either API domain. Q1's explicit compatibility-approval requirement remains applicable; this finding does not remove it.

### 2. The baseline count is tests, not assertions

**Priority:** P3, evidence precision. **Report span:** `2026-09-05-contract-search-consolidated.md:107`, first paragraph under O1.

The paragraph says the frontend suite completed “509 assertions.” The verification evidence section identifies the same result as 509 tests across 33 files. Vitest's test count is not an assertion count, and individual tests in the inspected suite contain multiple expectations. No assertion-count measurement is archived or claimed elsewhere.

**Correction:** Change “509 assertions” to “509 tests.” Keep the exit-zero result and the six-warning qualification. This review confirms the fixture mechanism in source, but did not independently rerun or recount the coordinator's recorded runtime output.

## Reconciliation and evidence checks

Every labelled entry from exploratory E1-E11, holistic H1-H4, multipass M1-M4/MC1, and differential D1-D2/C1-C2/R1-R11 appears once in the reconciliation table. The unnumbered accepted concerns and cleared source paths in those reports also have descriptive dispositions. No additional orphaned candidate was found. The D2 disposition needs the feedback/domain separation described in finding 1; the candidate itself was not omitted.

The six B1-B6 verdicts and their severity split are supported at the claimed level. B1's actual-router history sequence matches the archived observation exactly; its dependence on debounce-held ordinary query data explains why a placeholder-only guard is insufficient. B2 carefully distinguishes frontend execution from backend write-path inference and does not claim existing overlong production rows. B3's warm-cache failure capture is actually asserted in the archive; its conditional resweep impact follows from source, rather than from a measured production resweep. B4's runtime observation covers rename; deletion remains correctly identified through the complete source branch. B5's summary observations preserve the distinction between explicit false and the checkbox's true/undefined behavior. B6 is a source-established message-loss defect with an existing sibling implementation.

The readiness recommendation respects the final decision in `docs/superpowers/plans/2026-08-06-f008-decision-log.md:189-197`: although that document retains a contrary historical heading, the decision was reversed and shipped readiness sequencing, fetch-time capture, and readiness in the query key. The consolidated report preserves these mechanisms. Its instruction to close the live gate after an errored refresh must not be read as relabelling held rows before their replacement response arrives; the report's preservation of fetch-time metadata is consistent with that requirement.

Q3 correctly remains a product/ordering concern: `contract_service.py:600` deliberately picks a direction-dependent aggregate, while `_primary_label` picks the first named offered ship. One useful optional clarification for Sam is that text/type predicates also restrict the joined rows participating in that aggregate (`contract_service.py:273-281,346-347`), as the differential report already notes. Thus the existing representative can depend on active search predicates as well as sort direction. This is additional decision context, not a newly discovered bug or a reason to change the verdict.

O1's source explanation matches the three authenticated WatchButton responders and the three detail watch-button gate cases: their broad response handlers can return a contract body to the unread-count request, whose real hook reads `data.total`. The report does not mistake that fixture issue for a production notification defect and does not claim pristine baseline output.

The recorded install count, elapsed runtimes, exit status, and six-warning execution count are coordinator observations. The archive supports the four observation cases' assertions, not an independent rerun by this reviewer. No history attribution was independently checked, and no missing production-fix or implementation-plan verification is hidden: the report explicitly says neither has been completed.

## Resolution verification

**Final review status: DONE.** Re-read the coordinator's corrected consolidated report and progress record. Both findings are resolved: B6 now explicitly includes actionable count-cap and saved-price validation feedback while preserving existing domains; D2 and R1 reconcile to that scope; only stored-text compatibility and Name-sort semantics remain pending decisions. O1 consistently reports 509 tests. The optional predicate-dependent Name-sort context is also present. No unresolved report correction remains from this bounded review. These are document corrections; application remediation, its tests, and the outstanding decisions remain uncompleted as the report states.
