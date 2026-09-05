ABOUTME: Records an independent final review of the item-fetch plan and preparation handoff.
ABOUTME: Preserves as-raised findings, source checks, artifact hashes and verification limits.

# Contract item fetch integrity final PR review

**Result: 1 substantive finding. Raw raised count: 1.** This record contains the finding as raised, before coordinator disposition. No implementation was performed.

## Reviewed artifacts

| Artifact | SHA256 |
|---|---|
| [Contract item fetch integrity implementation plan](../../plans/2026-09-05-ingestion-item-fetch-integrity-plan.md) | `CE6C02F4C822FF9F1C19843437B3E4F161509A481FE611D8F44A600BC07F4E87` |
| [Preparation handoff](../../superpowers/handoffs/2026-09-05-contract-item-fetch-integrity-handoff.md) | `CD34F7CD02E2DEF8BB5771A87A5CB216376E6779555C020511DEA5455EC89D1A` |

## Finding

### P2 — Required item-page header is outside the drift monitor's coverage

- **Task and quoted span:** Task 1, response-policy table, line 224: “Missing/empty/non-integer/zero/negative `X-Pages`, or total changes on a later page” must “Raise `ESIRequestFailedError(status_code=200)`; never guess a last page.” Task 1's file scope at line 165 includes the client and its two test modules, and its verification step at line 290 retains the compatibility tests as the configuration/monitor guard.
- **Dimension:** Missing context and files; changed external-dependency coverage; implementation-pitfall compliance.
- **Claim:** The plan makes the response header a prerequisite for every successful 200 item fetch without assigning coverage of that dependency to the ESI drift monitor. An upstream spec change removing or changing `X-Pages` can therefore stop item enrichment while the monitor still reports no corresponding contract change. The executor needs this seam resolved or explicitly carried as a monitoring limitation before interpreting the current verification instructions as sufficient coverage of the changed dependency.
- **Source evidence:** `app/backend/tools/esi_spec_monitor/manifest.py:50` defines response-body `consumed_fields`, and the item endpoint at line 104 lists only item fields. `app/backend/tools/esi_spec_monitor/monitor.py:162` extracts the 200 JSON body schema; `_project_endpoint` at line 246 projects response statuses and fields at lines 265–267, with no response headers. Its diff at lines 547 and 558–559 likewise compares body fields and statuses. The compatibility tests in `app/backend/src/fastapi_app/tests/core/test_esi_compatibility_date.py` constrain the configured date and monitor pin, not item response-header declarations.
- **Applicable rule:** [Implementation pitfalls, ESI dependency review checklist](../../pitfalls/implementation-pitfalls.md#4c--review-checklist), line 433, requires a changed ESI dependency to be registered in the monitor in the same PR. The plan's listed files and steps do not account for this changed header requirement.
- **Boundary:** This finding does not challenge the chosen fail-closed policy or assert that upstream requires the header. The plan correctly distinguishes its client policy from the upstream header's optional declaration. The missing piece is monitoring that dependency.

## Checks completed

- Read the complete current plan and handoff, repository `AGENTS.md`, and both testing and implementation pitfall sets. Read the cited ingestion design's enrichment section and Plan B correctness docket as scope authorities.
- Checked task ordering and file overlap. Task 2 follows Task 1's review and commit; both phases remain unstarted and only ship after integration. The handoff separates this preparation PR from the future data-integrity production PR and leaves that production merge to Sam.
- Traced the current cached item paginator, 204/304 handling, empty-page termination, retry transport and exception class. The plan's failure mechanism matches the source, and repository-wide exception references identify the stated five service tests plus the dead handlers/class.
- Traced `_process_contracts`, contract-row construction, `bulk_upsert`, item mapping, completion/version updates and ship-flag clearing. The planned seed/re-sighting/recovery tests observe stored rows and refreshed contract state; they distinguish a rejected fetch from a returned non-ship prefix. The fresh-row and healthy-sibling cases constrain isolation.
- Checked the three-page HTTP boundary, exact returned rows and request paths, no-cache observer, first-versus-late 204/304/empty failures, decoder causes, retry exhaustion and logger evidence against TEST-4/12/18/21/24/25/26/28. Required mapped item fields are supplied while optional-field semantics remain with the existing writer.
- Read the existing cached-region/freshness tests, `db_session` fixture, sessionmaker use and lock double. The plan replaces manufactured 304 exceptions with empty-wire 304 responses and nonempty Redis bodies, seeds region stamps incorrectly on purpose, supplies names/station responses, separates lock/freshness Redis from ESI cache state, and explicitly binds the two committed transactions to `TEST_DATABASE_URL` with cleanup in `finally`.
- Checked the untouched cached-helper, region and object-cache boundaries, no-startup/no-migration/no-version-bump constraints, isolated test environment instructions, generated-file/formatter constraints and the handoff's re-grounding and worktree coordination instructions. No additional substantive finding was identified on these checks.

## Limits

- Static repository review only. No tests, mutations, backend startup, dependency acquisition, production-environment reads or writes, deployment, commits, or edits to the plan/handoff/source were performed. This report is the sole file authored by this reviewer.
- Plan git history and earlier review artifacts were not read. Historical baseline counts, upstream observations, certification/editorial claims and publication observations in the handoff were treated as dated reports, not independently reproduced evidence.
- The upstream OpenAPI document and live ESI responses were not retrieved in this review. The header finding follows from the plan's explicit policy and the local monitor's source, irrespective of whether upstream currently emits the header.
- This review establishes plan and handoff readiness limits; it does not certify an implementation, current production data, complete region discovery, atomic upstream generations, request budgets, corpus repair or the broader ingestion redesign.
