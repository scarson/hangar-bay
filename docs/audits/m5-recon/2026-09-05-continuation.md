ABOUTME: Records the resumed ingestion work and its boundaries against the remaining project plans.
ABOUTME: Preserves verified prerequisites, queued work, and operational constraints for the next executor.

# Ingestion continuation — 2026-09-05

- [x] Reconcile latest handoffs and shipped work against `origin/dev` at `f457acb`.
- [x] Check whether the courier ranking study can acquire its required live snapshot.
- [x] Identify an independently verifiable ingestion prerequisite.
- [x] Write and independently review the item-fetch integrity implementation plan.
- [ ] Implement and verify its tasks, subject to the plan's execution gates.
- [ ] Publish the production implementation and record its integration state.
- [ ] Publish the reviewed plan and session handoff at Sam's requested stopping point.

## Current scope

The [ingestion clean-sheet design](ingestion-clean-sheet-design.md) spans shared request governance, discovery scheduling, queue claims, matching, and delivery. Its [Plan B handoff](../../superpowers/handoffs/2026-07-27-plan-b-handoff.md) carries an independently actionable correctness prerequisite: remove item-page ETag caching and its unreachable `ESINotModifiedError` model. That prerequisite is the selected continuation. The pipeline's remaining architecture is not represented as implemented or executable by this slice.

At the inspected base, `core/esi_client_class.py` calls the cached paginator from `get_contract_items`. `_read_etag_cached_page` returns an empty list when a 304's body is absent; `_last_page_reached` terminates on that empty list before consulting `X-Pages`. A non-empty prefix can therefore reach `_update_item_processing_status` as a completed result. These paths are under `app/backend/src/fastapi_app/`. No production request was made to reproduce this failure.

The other carried items remain queued: a shared governor covering GET and POST, discrimination between 420 reset headers and 429 Retry-After, a cumulative request wait budget, deadline-derived lock lifetimes before scheduler changes, and queue scans using existing indexes unless measurement justifies another. The current cache helper already prefers Cache-Control over Expires; the design's polling assumption must be revalidated under [the cache-lifetime pitfall](../../pitfalls/implementation-pitfalls.md#esi-2-expires-is-being-deprecated-read-cache-control-for-cache-lifetimes).

## Courier study access constraint

The [reward-per-jump plan](../../superpowers/plans/2026-08-10-reward-per-jump.md), Task 0.2 (measure ranking changes), requires one frozen population across the deployment's configured ingestion regions, including endpoint system resolution. Task 0.1 already has evidence in the [reward-per-jump specification](../../superpowers/specs/2026-08-10-reward-per-jump-spec.md); it should not be repeated.

On 2026-09-05, GitHub's `PROD_ORIGIN` repository variable confirmed `https://hangarbay.app`. One ordinary list request with `contract_type=courier`, `size=100`, and `page=1` returned HTTP 200, total 34,287 and 100 items. That deployed response lacked coverage metadata and `end_location_system_id`. The response alone does not establish that the deployed API supports the requested type filter. Neither the complete courier population nor runtime `AGGREGATION_REGION_IDS` can be inferred from it.

No Render API key or database connection was available in the process or the expected root/backend environment files. The production database access rule remains held. The study needs a read-only, consistent export containing contract ID, reward, both endpoint system IDs, relevant eligibility fields, the extraction time, and the deployed configured region list. Paginating a changing public listing is not evidence of the plan's single-instant snapshot. No inversion numbers or routing recommendation were manufactured.

## Coordination

The separate contract-search bug-hunt task owns saved-search validation and SQL name ordering. Its worktree is untouched. Dependency and production-smoke workflow work are separate branches; the coordinating task alone performs merges and root `dev` synchronization. The pre-existing untracked root `.codex/` configuration is unrelated and remains untouched under Sam's autonomous continuation instruction.

## Completed parallel follow-ups

- [Production-smoke failure diagnostics, PR 190](https://github.com/scarson/hangar-bay/pull/190), merged at `b37c18a3e81ac2b9bcb59dd113e77b6db147d9b8`: `.github/workflows/deploy.yml` preserves existing Playwright failure traces for seven days. Full CI, all four CodeQL analyses, and independent review passed before merge. No deployment was triggered by this task.
- [Browserslist dependency remediation, PR 189](https://github.com/scarson/hangar-bay/pull/189), merged at `0172ae18d18da0c7fbedcb05fe45b9287ec6eb53`: clean install, build, lint, generation, 509 unit tests, 509 future-clock tests, and 146 browser checks passed (7 expected skips). Both independent reviews found no actionable defects. GitHub alerts 10 and 11 became fixed at `2026-09-05T12:17:06Z`; the installed frontend audit reported zero vulnerabilities. The PR links the final hosted checks and the dependency verification record carries the detailed evidence.
- [Dependency verification record, PR 191](https://github.com/scarson/hangar-bay/pull/191), merged at `4f1226134d61b254301bb93bcd1c5452fe6a57eb`: preserves the dependency checks and alert closure, and reconciles the frontend coverage handoff. All applicable checks passed.
- [Reward-per-jump status correction, PR 192](https://github.com/scarson/hangar-bay/pull/192), merged at `a2ac558f1fbb0689ff1a91ccfcbc7249816eeb24`: records the already-completed edge-list findings and the remaining snapshot-access prerequisite. Independent review and all applicable checks passed.

## Item-fetch plan review and preparation

The [item-fetch integrity implementation plan](../../plans/2026-09-05-ingestion-item-fetch-integrity-plan.md) contains two sequential tasks. Its review record is the execution gate; this continuation does not authorize skipping it.

| Round | Reviewer | Raised | Fixed | Rejected |
|---|---|---:|---:|---:|
| 1 | Author self-review, with coordinator verification | 4 | 4 | 0 |
| 2 | GPT-6 Astra high, cold independent | 1 | 1 | 0 |
| 3 | Claude Opus 5 high, cold independent | 5 | 5 | 0 |
| 4 | Coordinator self-review of the complete repair wave | 0 | 0 | 0 |
| 5 | GPT-6 Astra high, cold independent | 0 | 0 | 0 |

Notes: the transport-exception finding appears in both independent rounds and shares one fix. The opening round comprises three author findings and one distinct coordinator finding. The required cross-provider review ran successfully; both pitfalls documents were available. The [final independent review](2026-09-05-item-fetch-plan-final-review.md) raised zero findings. It checked actual sources but could not independently retrieve the upstream OpenAPI document; the coordinator's dated observations remain the stated evidence for that document. No rejection awaits concurrence.

The opening review corrected a nonexistent test name, supplied the concrete response decoder, required SQL read-back after bulk writes, and separated no-cache instrumentation from late-failure fixtures. The [GPT review](2026-09-05-item-fetch-plan-gpt-review.md) and [Claude review](2026-09-05-item-fetch-plan-claude-review.md) preserve their exact findings. Their accepted repair wave replaces the impossible transport-cause assertion with the logged exception's actual class/status/message, binds committed aggregation tests to the dedicated test database, supplies real names/station HTTP fixtures with courier contracts, seeds region stamps with a sentinel, and verifies application headers on every item request. The coordinator read the complete repair diff and checked it against the response and persistence contracts. Production code is unchanged at this preparation stage.

Pattern: `plan-review-item-fetch-integrity`. Tests must reach the failing page before claiming to detect an incomplete result. Fixture defaults can satisfy region-stamp assertions without exercising the writer. A real client in an integration test also requires every adjacent HTTP boundary and an explicit test-database session factory; otherwise swallowed setup failures can hide the mechanism being tested.

The isolated baseline passed 184 focused tests and 822 full backend tests with pristine output. The initial full run had six temporary-directory setup errors; a worktree-local pytest `--basetemp` resolved the host permission issue without source changes. The full passing run is recorded in the ignored verification directory and execution ledger. Git for Windows skill scripts require `/usr/bin` in their shell PATH on this host. A denied external review attempt was replaced, after verifying public repository ownership, with a fixed text bundle and a tool-disabled reviewer; the approved run completed without permission denials.

The unchanged backend also passed flake8 . after moving the temporary PDM environment and uv dependency cache under the existing .venv exclusion. The first lint attempt still encountered uv's extracted third-party packages; inspection identified that second cache tree before relocation. The project lint configuration and production source were unchanged. The ignored runbook records the relocated PDM module invocation and UV_CACHE_DIR.

## Requested checkpoint

After resetting usage, Sam requested the next natural stopping point, followed by a handoff and PR. The selected boundary is the reviewed implementation plan; both production tasks remain unstarted. Certification is 6b420dad0192e05a57ea26f9bca8a9d8f10ce99e; editorial commit fd29e6d2dfc4e573d5d2d3bc2bbc1b8b9fc7dbf9 accepted 11 verified hunks and restored one baseline hunk. The [editorial verifier report](2026-09-05-item-fetch-editorial-review.md) preserves the comparison. The first verifier response lacked verdicts and was rejected; a fresh tool-disabled Claude Opus 5 high comparison returned the required 12 hunk verdicts. An exit code of zero alone does not certify a model's review output.

The [bounded maintenance follow-up assessment](2026-09-05-next-maintenance-action.md) found ingestion metrics and queued logging unimplemented but without dedicated reviewed plans. It was saved before its agent hit a usage limit; the coordinator read the complete report and verified the instrument declarations, logging setup and implementation absence. Ingestion metrics is the smaller later planning task; its source overlap makes it follow the item-fetch production change, not this documentation PR.
