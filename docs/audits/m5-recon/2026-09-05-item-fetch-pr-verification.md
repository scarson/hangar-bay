ABOUTME: Verifies the amended item-fetch plan and its preparation handoff against repository sources.
ABOUTME: Records the accepted monitoring finding's disposition, six handoff lenses and artifact hashes.

# Contract item fetch preparation verification

**Result: zero substantive issues remain in this review. Raw new-finding count: 0.** This is verification of the preparation documents, not implementation verification. Both production tasks remain unstarted.

## Exact reviewed artifacts

| Artifact | SHA256 |
|---|---|
| [Contract item fetch integrity implementation plan](../../plans/2026-09-05-ingestion-item-fetch-integrity-plan.md) | `334C2AE026A8C910E6E0F4A90B2BD5E5EB8A13CB6628AE51BDF2D19339383A9A` |
| [Preparation handoff](../../superpowers/handoffs/2026-09-05-contract-item-fetch-integrity-handoff.md) | `CD34F7CD02E2DEF8BB5771A87A5CB216376E6779555C020511DEA5455EC89D1A` |

The plan hash includes the preparation-review scope amendment in its Deviations section. The handoff remains byte-identical to the previously reviewed artifact.

## Original finding disposition

The P2 finding, **Required item-page header is outside the drift monitor's coverage**, was accepted and addressed in the plan. The [as-raised final PR review](2026-09-05-item-fetch-pr-final-review.md) remains unchanged. Task 1 now assigns the header dependency, projection, comparison, reporting, regression tests and generated snapshot to its execution scope. This resolves the missing planning seam; it does not assert that the monitoring code has already been implemented.

## Source-backed amendment verification

| Check | Verification |
|---|---|
| Dependency registration and scope | Plan line 165 names seven distinct Task 1 files: the client, two application test modules, monitor manifest, monitor implementation, monitor tests and generated snapshot. Line 309 stages those seven. Task 2 retains its separate three-file scope and runs after Task 1's review and commit. The scope amendment is also recorded at line 116. |
| Bounded header projection | Plan lines 292–294 register only the item endpoint's consumed `200 X-Pages`. The existing `Endpoint` at `app/backend/tools/esi_spec_monitor/manifest.py:50` has body-field declarations; the prescribed separate header declaration avoids confusing request parameters or body fields with response headers. The qualified subject `response-header:200:x-pages` and case-insensitive matching preserve header identity. Undeclared headers, descriptions, 204 headers and endpoints with no header declarations remain outside the added projection. |
| References and schema descriptors | `monitor.py:95` supplies `_resolve`, including explicit errors for broken or cyclic local references; lines 116 and 126 supply scalar and array descriptors. The plan names Response Object, Header Object and schema-reference resolution, retains those errors, and requires equivalent-reference and unresolved-reference tests. This can be implemented without changing unrelated body projection behavior. |
| Upstream optionality | The plan retains the source observation that `X-Pages` is not declared required. The header descriptor takes `required` from the upstream Header Object, defaults it to false, and tests both omitted and explicit requiredness. The client independently rejects a missing header. The amendment expressly distinguishes published-schema monitoring from runtime header presence. |
| Comparison, severity and attribution | `monitor.py:376` already supports keyed descriptor comparison and `removed_severity=None`; line 417 supplies the type/format/enum/requiredness rules. `_Context.add` at line 330 makes newest-view findings informational. The plan routes the qualified header subject through these existing mechanisms and the consumer map, and retains reporting via `format_report` at line 600. Its pinned/newest/both-view assertions match the current comparison model. |
| Manifest consistency and duplicate suppression | `_diff_manifest_consistency` at `monitor.py:485` excludes subjects already explained by field findings. The plan computes body and header misses separately before combining them, preventing same-named body fields or request parameters from satisfying the response-header dependency. It requires ordinary header removal to produce only `FIELD_REMOVED`, a newly undocumented dependency to produce `MANIFEST_FIELD_UNDOCUMENTED`, and restoration to remain informational. |
| Test reach and independence | The complete existing `tools/esi_spec_monitor/tests/test_monitor.py` was read. Its fixtures call `project`, `build_snapshot`, `compare_snapshots` and `format_report` directly and distinguish pinned-only mutations from changes at both dates. The amendment follows those boundaries, requires red evidence before implementation, exact descriptors/findings/consumer attribution, independent schema mutations and quiet unchanged/unrelated inputs. It also checks the actual manifest so fixture-only declarations cannot masquerade as registered production coverage. |
| Snapshot exception and commands | The global constraint at plan line 141 permits only this generated snapshot and prohibits hand editing or API/frontend regeneration. `pyproject.toml` defines `esi-spec-monitor` with `PYTHONPATH=tools`; `monitor.py:674` accepts `--update` and uses default invocation for checking, with no `--check` argument. `fetch_specs` at line 643 retrieves pinned and newest metadata views. The plan's commands agree with those mechanisms, require inspecting the generated diff, prohibit manufacturing a snapshot after retrieval failure, and require a subsequent no-drift exit 0. Unrelated live drift must be investigated rather than silently accepted. |
| Suite inclusion and dependency boundaries | `pyproject.toml` sets `testpaths` to both application tests and `tools`, with both source directories in `pythonpath`. The plan therefore correctly includes the monitor module in the full backend run without a workflow, package, dependency, or configuration change. Its PDM invocation also agrees with the handoff's recorded Windows launcher limitation. |
| Retry-count repair | Plan line 288 expects five item requests: `[1, 2, 3, 3, 3]`. The existing `_get_with_transient_retry` sets `max_retries = 3` and `backoff_factor = 0.5`, logs each `ConnectError`, and sleeps only before another attempt. Two successful pages plus three failing page-3 attempts therefore give five requests and waits `[0.5, 1.0]`. The final network error has status 0 through `ESIRequestFailedError` and no explicit chained cause, matching the plan's message and exception assertions. |

The entire current plan was reread for interactions with these amendments. The uncached walk still rejects a late empty/204/304 result without returning a prefix, preserves the ordinary cached helpers and retry policy, and leaves row-field mapping with ingestion. The planned writer-driven seed/re-sighting/recovery tests, refreshed ORM state, healthy sibling, fresh failed row, real cached-region bodies, explicit test-database binding and commit-failure freshness checks retain the observations required by the testing and implementation pitfall sets. No additional ambiguity, file/context gap, interpretation drift or task conflict was identified.

## Six handoff lenses

| Lens | Raw new findings | Result against the updated linked plan |
|---|---:|---|
| Naive fresh agent | 0 | The opening names the checkpoint and next task. The linked plan is explicitly authoritative, so its seven-file Task 1 scope and monitoring step are discoverable without reproducing that implementation detail in the handoff. The continuation prompt requires reading both documents before execution. |
| Recency | 0 | Checkout, PR, baseline, certification and editorial statements are dated observations. The handoff directs successors to current target contents and the integrated plan, rather than treating the observed preparation tip as the implementation starting point. The historical certification statements do not claim the monitoring amendment was implemented. |
| Work-unit seams | 0 | The preparation PR is separated from the later production PR; Task 1 and Task 2 remain sequential. A fresh implementation worktree follows preparation integration, root operations remain coordinated with the contract-search task, and the production merge stays with Sam. The monitoring work remains within Task 1 and introduces no competing writer. |
| Operational guardrails | 0 | Dedicated database/cache isolation, absent-after-cleanup environment files, no credential printing, no destructive startup and the relocated PDM launcher caveat are preserved. These instructions agree with the updated plan's monitor invocation and sole generated-snapshot exception. |
| Loss of hot context | 0 | The handoff provides repository/worktree/task identities, branch-state recovery guidance, durable plan links, the session-local runbook's absence condition and later-work boundaries. The linked plan itself records the monitoring scope amendment, so that decision does not depend on remembering this review conversation. |
| Plan readiness versus production completion | 0 | The handoff states that neither production task started and that the 184/822 test counts describe unchanged source. Both plan phase banners remain not started. The added monitoring tests and snapshot regeneration are future execution steps, and neither document presents them as completed evidence. |

**Handoff total: 0 raw new findings across all six lenses.**

## Limits

- Static review of the complete current plan, unchanged handoff and relevant repository source/test files. No tests, mutations, monitor invocation, upstream retrieval, database/cache access, backend startup, dependency acquisition, snapshot generation, production operation, Git operation or commit was performed in this verification pass.
- Only this verification report was authored. The earlier as-raised report, plan, handoff, source, test environment and snapshot were not changed by this reviewer.
- Historical test results, upstream observations, review-history statements and forge state remain attributed observations. No prior review-history sweep was performed. The coordinator owns documentation-link and publication-state checks.
- The finding is resolved at the plan level. Actual implementation must still earn the prescribed TDD, regression, mutation, lint, full-suite, live metadata/snapshot and independent-review evidence. Published-schema coverage cannot establish runtime header availability, atomic upstream generations or the correctness of deferred ingestion redesign work.
