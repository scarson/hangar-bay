ABOUTME: Records the resumed ingestion work and its boundaries against the remaining project plans.
ABOUTME: Preserves verified prerequisites, queued work, and operational constraints for the next executor.

# Ingestion continuation — 2026-09-05

- [x] Reconcile latest handoffs and shipped work against `origin/dev` at `f457acb`.
- [x] Check whether the courier ranking study can acquire its required live snapshot.
- [x] Identify an independently verifiable ingestion prerequisite.
- [ ] Write and independently review the item-fetch integrity implementation plan.
- [ ] Implement and verify its tasks, subject to the plan's execution gates.
- [ ] Publish the reviewed result and record its integration state.

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
