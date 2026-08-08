<!-- ABOUTME: Implementation plan for F008 Type-Aware Contract Browsing — four sequential PR phases -->
<!-- ABOUTME: (data layer, API contract, contract-level frontend, gated item-level frontend), TDD throughout. -->

# F008 Type-Aware Contract Browsing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the non-ship contract corpus a designed product surface: persist the per-type fields currently discarded at ingestion, segment browsing by contract type with honest counts, make the dead runs/ME/TE filter families functional, and add taxonomy filtering, auction, courier, blueprint, and composition displays — per the binding contract in `design/features/F008-Type-Aware-Contract-Browsing.md` §17.

**Architecture:** Four sequential PRs. PR-A extends the data layer (one migration, ingestion writes, taxonomy name cache, one `ENRICHMENT_VERSION` bump). PR-B rebuilds the API contract (list/detail model split, grouped single-statement counts, coverage envelope, functional item-level filters as offered-only correlated EXISTS, taxonomy endpoint). PR-C rebuilds the frontend list around per-column cell renderers and adds the contract-level surface (segments, auction/courier columns, coverage-honest states). PR-D adds the item-level surface, activated by the data-driven coverage signal rather than a flag.

**Tech Stack:** FastAPI 0.139 / SQLAlchemy 2.0 async / Alembic / PostgreSQL 18 / Valkey (untouched on the request path) · React 19 / TanStack Router + Query / Tailwind v4 / openapi-typescript · pytest / vitest / Playwright.

**Companion documents:**
- **Spec (binding):** [`design/features/F008-Type-Aware-Contract-Browsing.md`](../../../design/features/F008-Type-Aware-Contract-Browsing.md) — §17 is the normative API contract; §3.1 the filter semantics; §7.1 the decomposition constraints; §8 the row-shape axes.
- **Decision log (why the shapes below were chosen):** [`2026-08-06-f008-decision-log.md`](2026-08-06-f008-decision-log.md) — D1 coverage-signal gating, D2 grouped-count strategy, D3 loose-index-scan coverage, D4 SavedSearch widening, D5 index set, D6 PR train.
- **Perf context:** [`docs/perf-audits/2026-08-02-contract-list-watermark-subquery.md`](../../perf-audits/2026-08-02-contract-list-watermark-subquery.md) — do not re-derive; production DB access is gone.

## Living Document Contract

This plan is a living document. Every executing agent MUST update it as
execution progresses, not only at completion.

- **On phase claim:** the executor MUST flip the banner to 🚧 IN PROGRESS
  with a claim timestamp (ISO 8601 UTC) and the active branch name. The
  banner MUST NOT include an expected-completion estimate — agents cannot
  reliably estimate their own wall-clock, and a fabricated duration
  becomes a stale anchor that misleads future readers. Followers
  encountering a 🚧 banner determine liveness by observable signals (PR
  existence, recent branch commits), not by arithmetic on expected times.
  See Step 5's stale-claim reclaim protocol.
- **On phase ship:** the executor MUST update that phase's **Execution
  Status** banner with the shipped commit SHA(s) and date. If a PR is
  open, the PR number and URL MUST appear in the top-of-plan Execution
  Status table.
- **On phase defer:** the executor MUST update the banner with ⏸ status
  AND a prose description of the unblock condition + a link to the
  likely-unblocker artifact (plan page, task, or PR whose own Execution
  Status banner will signal completion). Prose + link is durable across
  paraphrases and scope edits; exact-string coordination between agents
  is not.
- **On PR merge:** the executor MUST record the merge SHA in the banner
  + the top-of-plan Execution Status table.
- **On deviation from the written plan** (scope edits, structural
  refactors, dropped tasks, reordered phases): the executor MUST
  inline-document the deviation in the affected task AND summarize it
  in the top-of-plan Execution Status as a "Deviations" subsection.
  Deviation state MUST NOT live only in PR notes or status reports.
- **On discovery** (pre-existing drift surfaced during execution, new
  bugs found, architectural issues noted): the executor MUST add a
  "Discoveries" subsection at the top of the plan with pointers to the
  files/lines affected. Follow-up dispatches read this subsection to
  avoid duplicate discovery work.

The plan SHOULD reflect reality at the end of every session that touches
it. Anything worth putting in a status report to the user is worth
putting in the plan.

Rationale: `/writing-plans-enhanced` Step 5. Writing at ship time is
cheap; reconstruction by downstream readers is expensive, compounds
across dispatches, and fails silently when state is split across PR
notes and commit messages.

## Execution Status

**Overall:** Phases A, B, and C MERGED to dev. Phase D (item-level surface) deferred to a follow-up session — see its banner.

| Phase | Status | Ship SHA(s) | Notes |
|---|---|---|---|
| A — Data layer (migration, ingestion, taxonomy cache) | ✅ Shipped | `a7cd7ba`..`c0e3d85` | PR #138 merged at `8303e15` 2026-08-07; migration `685dab7d6df5`; ENRICHMENT_VERSION→2; 582 tests green; codex-reviewed (D10 deferral logged). |
| B — API contract (model split, counts, filters, taxonomy endpoint) | ✅ Shipped | `ecb1352`..`8da5588` | PR #139 merged 2026-08-07; incl. Tasks C1/C2; 669 backend tests, all frontend lanes; codex-reviewed (3 P2s taken). |
| C — Frontend contract-level surface (segments, auction/courier, coverage states) | 🚧 In progress | — | C1/C2 shipped with PR-B; C3-C5 done on `feat/f008-contract-surface` 2026-08-07; C6 gate remains. |
| D — Frontend item-level surface (taxonomy UI, ME/TE/runs, BPC, composition) | 🚧 In progress | — | Claimed 2026-08-08 on `feat/f008-item-surface` off `dev` @ `5cebd4b`. |

### Deviations
- Task C1: the binding `Column` interface gained `cellClass?: string | ((contract, ctx) => string)` and a `rowContext(contract)` helper, and the default set is named `DEFAULT_COLUMNS` (not `COLUMNS`) — the plan's literal interface could not carry the existing per-cell classes; C4 builds per-segment sets beside it.
- Tasks B6/B9: `ContractFilters.category_id/group_id` are `List[int]` (B6's spec block) while `SavedSearchParameters` uses `List[PositiveInt]` (B9's spec block). Deliberate asymmetry kept: ids ≤ 0 do not exist in EVE, the URL layer already drops them, and the stricter blob validation only refuses values the live filter would match nothing on.
- Phase B task order in execution: C2 ran AFTER B10's steps 1–4 (regeneration), not before B10 as the section order reads — the C2 executor correctly refused to take B10's single-writer regeneration step and the dispatch was re-sequenced (see the workflow-ordering memory note).
- **Task B2, test placement.** The plan sent the requested-only-BPC fixture to `test_contract_service.py`; the mixed-bundle partition test it names actually lives in `test_contract_filters.py` (`test_is_bpc_is_a_contract_level_predicate_on_a_mixed_bundle`, region 99999954), so the new contract went there. Noted inline in B2 Step 1.
- **Task B2, one test folded rather than migrated.** `test_item_response_omits_fields_public_ingestion_cannot_populate` asserted that list-row ITEMS omit `is_singleton`/`raw_quantity`. List rows no longer carry items at all, so the assertion has nothing to range over. Its coverage was folded into `test_detail_item_response_omits_fields_public_ingestion_cannot_populate`, which now sweeps all four fixture contracts (previously only 101) across the endpoint that does carry items — net coverage up, not down. Flagged here and in the PR body per Step 4's rule.
- **Task B3, equivalence-corpus regions.** Step 1 called for the equivalence corpus to sit in "two private regions"; it was seeded into `DELISTED_REGION_A`/`DELISTED_REGION_B` (99999911/99999912) instead, because those are the two ids the `liveness_branch` fixture writes into `AGGREGATION_REGION_IDS`. A corpus in any other region takes the correlated fallback under *both* params, which would make the parametrisation vacuous and leave the watermark fast branch uncovered. `db_session` drops and recreates every table per test function, so sharing the ids with the delisting cases is safe. Noted inline in B3 Step 1. **Region 99999963 is untouched and remains Task B5's** (Global Constraint 23) — B3's service-level zero-fill test queries the empty 99999962, B3's own claim.
- **Task B4, region claim and two tests beyond the three the step named.** B4's Files list assigned no private region, so it claims **99999967–99999970** under the plan's 99999960–99999979 allocation (A/B, a configured-but-uningested third, and a fourth whose rows carry no `last_seen_at`). Two tests were added past Step 1's three: one asserting the empty-page short-circuit carries `coverage` (Global Constraint 18 — the field threads through both `ContractListResponse` constructors, and only a non-empty corpus filtered to nothing distinguishes a threaded field from a hardcoded empty one), and one asserting a region whose rows are all unstamped still counts as covered without breaking `as_of` (`last_seen_at` is nullable, and an unguarded `max()` over the rows raises TypeError — mutation-verified). Test-only helper renamed to `_region_contract`: `_coverage_contract` was already taken in that module by the unknown-system residual tests, where "coverage" means location resolution.

- **Task B7, five deviations** (details inline at the end of Task B7): region 99999971 claimed for a test block whose population is the whole table rather than one region; one test past Step 1's seven, pinning that the name-cache condition is scoped to LIVE contracts (the reason it owns its own query instead of reusing ingestion's unscoped sweep); `coverage` typed as a str-enum so the regenerated TypeScript is a two-value union rather than `string`; the name sort run in Python so the served order does not vary with the server's collation; and a vacuous sort fixture of my own that mutation caught before commit — the categories were seeded already in name order, so the sort assertion agreed with the sort without constraining it.

- **Task B6, four deviations** (details inline at the end of Task B6): region 99999965 claimed behind a shared `taxonomy_corpus` fixture; Step 1's seven assertions split across four behavior-named tests; the module's OpenAPI param-enumeration guard extended with `category_id`/`group_id` (outside the step's list, but it is the FASTAPI-1 guard for exactly this filter class); and `_needs_item_join`'s trailing comment widened to name the fourth EXISTS family.

- **Task B10, one test beyond Step 1's and a fix reaching outside the task's Files list** (details inline at the end of Task B10). Step 1 named a single test; `test_full_dimension_logs_carry_the_type_and_taxonomy_filters` was added because Step 3 also *adds* three keys to the two full-dimension payloads, which is production behavior Step 1's test does not constrain. Separately, review found the PII invariant only half-closed — the failure site logged `str(e)`, which for a `StatementError` renders the failed statement's bind values and so re-published the search text `search_terms` had just withheld. Closing it reached `db.py` (`hide_parameters=True`) and added `tests/test_db_engine.py`, both outside the task's Files list, plus pitfalls SQLA-4 / TEST-21 and a decision-log entry.

- **Task B5, four deviations** (details inline at the end of Task B5): a fourth test pinning that the three range families stay independent EXISTS clauses; a repair to `tests/conftest.py::setup_contracts`, outside the task's Files list, where `raw_quantity=10` had to become `runs=10` for `test_filter_by_bpc_runs` to keep meaning anything; past-tense corrections to pitfalls FASTAPI-2 and TEST-18, whose present-tense claims this task falsifies; and an offline re-projection of the ESI monitor snapshot instead of `--update`, to avoid accepting unreviewed live-spec drift while updating one manifest annotation.

- **Task C3, five deviations.**
  1. **The ships-only restore cannot remove the parameter from the URL, and does not need to.** Criterion 1.9 and the task text both describe restoring the default as "REMOVING the key, which TanStack Router drops from the URL". The patch does remove it — but the route's `validateSearch` (`routes/contracts.index.tsx` → `parseContractSearch`) runs before the location is stringified and always returns a boolean `ships_only`, so the URL comes out `ships_only=true`: exactly the shape Clear filters has always produced. `contract_type: undefined` *is* dropped, because the parser returns undefined for it. The patch still passes `undefined` rather than `true` — that expresses "whatever the default is" instead of freezing today's default at the call site — but the assertions pin the restored default (`ships_only=true` present, `ships_only=false` gone, checkbox checked, wire carries `is_ship_contract=true`) rather than the absence of the key.
  2. **Array search params serialize as JSON, not repeated keys.** Selecting a segment writes `contract_type=%5B%22courier%22%5D`, the same form `region_ids` has always used in this app (only the API client emits repeated keys). The e2e asserts the decoded param value and then **reloads the app-written URL** to prove it restores, which is what Criterion 1.4 actually wants and is stronger than pinning an encoding.
  3. **The Criterion-1.7 clearing inside the segment patch is a second layer, not the enforcing one, and no test can observe it.** `parseContractSearch`'s item-less normalization (Task C2, codex round-2 finding 10) widens the selection on every navigation, so deleting `ships_only: false` from the courier patch changes nothing any lane can see — mutation-verified across both vitest lanes and the Playwright lane. Kept per the task's binding behavior and as defense in depth on a must-never-exist combination, with a comment saying so, so a future reader neither deletes it as dead nor writes a test that pretends to cover it. The *restore* half has no such backstop and is mutation-killed by the component test.
  4. **Six files outside the task's Files list changed, all test-side.** `src/test/http.ts` gained `emptyContractPage()`, and the contract-list stubs in `HeaderIdentity.test.tsx`, `SsoNotice.test.tsx`, `AccountNav.test.tsx`, `NotificationBell.test.tsx`, and `SaveSearchControl.test.tsx` now use it. Those stubs returned `{total, page, size, items}` with no `segment_counts` and no `coverage` — a response the API cannot produce since Phase B, which only stayed green because nothing read those fields. The segment control reads `segment_counts`, so all five crashed the list route into its error boundary. The shared builder is the fix that keeps the next envelope field from re-breaking them one at a time.
  5. **Two existing assertions changed, both tightened.** `pages.test.tsx`'s courier-badge test now scopes to the row (`within(getByRole('row', …))`): a page-wide `getByText('Courier')` matches the new Courier control as well as the badge, and the assertion was always about the badge. `filters.spec.ts`'s clear-filters test now selects a segment before clearing, so the `contract_type` entry added to its URL enumeration is a real assertion rather than a checklist entry for a param the test never set.

- **Task C4, eight deviations** (details inline at the end of Task C4): the per-segment sets live in `columns.tsx` per Task C1's deviation rather than the `ContractTable.tsx` the Files list names; two format helpers (`routeLabel`, `formatDeadline`) beyond the one the task names; Reward/Collateral/Volume/Deadline left unsortable per the binding text, **leaving a Deadline column with no sort toggle for a field Task B8 made sortable** — a C6/Phase-D decision; the courier `Contract` column dropping the `ship_name` sort, which for an item-less segment orders on NULL for every row; responsive hiding chosen rather than specified — Collateral and Volume hide below `lg`, Deadline never hides because `days_to_complete` has no other surface in the app; one test past Step 1's list pinning that the default set is unchanged; the Type column leaving the auction set as redundant with the segment control; and the active segment now travelling with the query result instead of being read from the live URL, which `keepPreviousData` made describe the previous segment's rows under the incoming segment's columns (new pitfall WEB-1, and the reason `activeSegment` lives in `filters.ts`).

- **Task C5, eight deviations** (details inline at the end of Task C5): a preparatory pure-refactor commit moving the existing `timeAgo` out of the notifications feature into `src/lib/timeAgo.ts`, so the task ships two commits rather than Step 4's one; the helper named `regionNames` rather than `coverageLabel` (it names the *uncovered* selection at its other call site) and its region `Map` built in `format.ts` because `regions.ts` is generated; `useContracts` carrying the fetched `region_ids` beside `segment` because WEB-1 governs empty-state copy exactly as it governs column sets; a null freshness stamp rendering nothing rather than a dash on both surfaces; two tests past Step 1's two branches (a mixed covered/uncovered selection, and a corpus with nothing ingested); one pre-existing test's fixture — not its assertions — repaired because its selected region 10000020 is uncovered in the shared fixture; e2e reaching into `segments.spec.ts` and `detail.spec.ts` beyond the named `states.spec.ts` addition; and the Criterion-5.7 courier line rendering only above populated rows.

- **Task D1, six deviations** (details inline at the end of Task D1): the readiness gate is read live rather than carried on the list response (decision log D13); the column half of the gate moves to Task D4, where the columns it hides are created; a loading taxonomy reads as not-ready; `is_bpc` is excluded from the deep-link warning's trigger set because it was never enrichment-dependent; the e2e fixture lane gained a per-spec `interceptTaxonomy` in eleven files; and two existing request-contract tests' list-call predicates were repaired for the new sibling path.

- **Task D2 deviations — TWO WERE REVERSED by the codex review of PR #145; read the reversal note below before the inline list.** Withdrawn: the B6 advisory answered in the parser (an all-item-less selection dropping all nine offered-item filters), and the client-side suppression of the resulting zeroed count. What stands: `Ships only` disabled on an item-less selection (closing a dead control that has been there since Task C3); no type-ahead on the short Category list; the group-scope announcement following the state rather than the plan's fixed sentence, and now living in a polite live region; `hasActiveFilters` taking all nine params in one predicate; and a shared `hasOfferedItemFilters`/`isItemLessSelection` pair replacing `SegmentTabs`' private copy.

- **Task D3, five deviations** (details inline at the end of Task D3): three legended min/max pairs rather than one blueprint fieldset, because §3.1 makes the families independent; no invented upper bounds on the inputs; `summarizeSearch` extended outside the Files list so two saved searches differing only in their blueprint window read differently; `SavedSearchesPage.apply()` needing no change because it restores through the parser; and `hasActiveFilters` already covered by Task D2.

- **Task D4 deviations — the first TWO WERE REVERSED by the codex review of PR #145.** Withdrawn: the single `Blueprint` column and its `lg` hiding. §8 asks for three columns always present in the item-bearing segments, and the width argument against them was wrong — three narrow numeric cells are together narrower than one combined cell, so the mobile objection dissolves too. What stands: the composition breakdown replacing rather than joining `+N more`, and only once the categories are named; the offered/requested split deliberately UNGATED, since `is_included` predates the resweep; per-item blueprint terms added to the detail page so the list's "N BPCs" link answers what it raises; a `formatBlueprintTerms` helper beside the named `formatComposition`; a new `columns.test.ts` pinning three set-level invariants; and two `detail.spec.ts` assertions retargeted from the removed `Contents` region.

- **Task D5, three review-round fixes** (details inline at the end of Task D5): the group-scope sentence became a polite live region carrying a count, because Criterion 12 asks for the change to be *announced* and a described-by is read only on focus; the incomplete-results notice moved off the live URL and onto the query result (WEB-1) after review found it withdrawing itself while the rows it described were still on screen; and `formatVolume` replaced the plan's "`formatIsk`-style m³ formatting" after the live corpus rendered `2 Blueprints · 0 m³` for a 0.02 m³ lot — six of the ten composition-bearing dev contracts measured under 1 m³.

### Discoveries
- C5 review: the inline region-name enumerations in both coverage sentences become unbounded lists when ingestion widens past a handful of regions (cap as 'The Forge and N other regions' then); `toIdArray` does not dedupe repeated URL ids (cosmetic, unreachable from the rail). Neither taken now.
- **`FilterRail.hasActiveFilters` does not yet know about the item-level params.** Task C3 added `contract_type` to it; `category_id`, `group_id`, and the six runs/ME/TE bounds have been parseable since Task C2 but are still absent, so a deep link carrying only those renders no "Clear filters" button even though `resetFilters` would correctly drop them. Tasks D2 and D3 add the controls for exactly those params and must extend the predicate in the same commits (`components/FilterRail.tsx`).
- **Criterion 1.8's lift is not applied to the offered-item filters, so an item-less segment's count reads 0 whenever one is active.** `_segment_counts` (`services/contract_service.py`) lifts `ships_only` for the item-less types precisely because nothing item-less can satisfy it; `category_id`, `group_id`, the three blueprint ranges and `is_bpc` are unsatisfiable by an item-less contract for the identical reason, and are not lifted. The client now renders no numeral in that state (Task D2 deviation 2) — correct but strictly less informative than the number Criterion 1.8 asks for. The backend fix is the same `FILTER (WHERE …)` treatment one filter family over; it needs a decision about whether "lifted" means lifting all offered-item filters together or per-family.
- **Two pre-existing sorts are nullable and place NULL inconsistently with the rule Task B8 establishes.** `SortableContractFields.volume` maps to `Contract.volume` (`models/contracts.py`, `nullable=True`) and `ship_name` maps to `ContractItem.type_name`; neither carries `nulls_last()`, so on PostgreSQL a descending sort by volume leads with every volume-less contract and a descending sort by ship name leads with every item-less one. Task B8 deliberately did not touch them — the step directs that the existing sorts stay byte-identical, and changing a live sort's plan is outside an additive task — but the frontend now offers three sorts that put "no value" last beside two that put it first, which reads as a bug to anyone who tries both. Decide in PR-C/D whether to extend `NULLABLE_SORTS` (`services/contract_service.py`) to cover them.

---

## Global Constraints

Every task implicitly includes all of these. Verbatim values are copied from the spec, the pitfalls docs, and the 2026-08-07 code recon (which verified every citation below against `dev` @ `811441c`).

**Process**
1. **TDD is mandatory for all production code.** BEFORE starting any task: invoke `superpowers:test-driven-development` and read `docs/pitfalls/testing-pitfalls.md`. Write the failing test, run it red, implement minimally, run it green, refactor. BEFORE marking any task complete: review tests against testing-pitfalls, verify error paths and edge cases are covered, run the suite green. Docs/config/generated code are exempt (CLAUDE.md §TDD scope).
2. **Never weaken an assertion to fix a flake** (TEST-2). Deterministic synchronization or deterministic fixtures only. Commit subjects touching assertions say what happened to them.
3. **Mutation-verify load-bearing tests** (TEST-12): break the named behavior, confirm red, restore from a `cp` snapshot (never `git checkout --`), finish with a green restore-run.
4. **After each phase group: minimum 3 review rounds from different perspectives**; keep going past 3 if a round still finds substantive issues. Then a backgrounded codex review of the PR (`codex` per the repo's standing settings: model `gpt-5.6-sol`, `model_reasoning_effort=high`, run as a background task — foreground calls time out). Address findings, then merge under Sam's 2026-08-06 merge grant: verify CI green explicitly (no `--auto` — this repo has no required status checks), then `gh pr merge <n> --merge --delete-branch --body ""`.
5. **Merge classification headings stay honest** even though the agent merges: PR-A `Review — database schema`, PR-B `Review — public API contract`, PR-C/D `Routine`. Each PR body notes the merge is under Sam's explicit 2026-08-06 grant.
6. **Consequential decisions made during execution get a decision-log entry** in [`2026-08-06-f008-decision-log.md`](2026-08-06-f008-decision-log.md) (background / alternatives / decision / reversibility), committed with the work.

**Single-writer resources (spec §7.1 / DEPLOY-5) — violating any of these fails in a way the offending task will not see**
7. **One migration, authored once, in Task A1, before anything depends on it.** `alembic/versions/` is a linear chain; current head is `ea2491c47a9f` — **re-verify against `origin/dev` at authoring time** (`cd app/backend/src && ../.venv/bin/python -m alembic heads` must print exactly one line before AND after).
8. **One `ENRICHMENT_VERSION` bump (1 → 2), in Task A8 only** — the last ingestion change of Phase A. No other task touches the constant.
9. **Codegen is regenerated, never merged.** After any backend schema change: `pdm run export-openapi` (in `app/backend`) then `npm run generate:api` (in `app/frontend/web`); commit both artifacts in the same PR. On rebase conflicts in `openapi.json`/`schema.d.ts`: take either side, re-run both commands, commit the result.
10. **`ContractTable.tsx` is restructured exactly once (Task C1), before any task that adds columns.**

**Environment (this worktree)**
11. Backend test runs use this worktree's dedicated scratch DB and MUST be serialized (the suite drops/recreates all tables in one database — parallel runs corrupt each other):
    ```bash
    cd app/backend
    ESI_USER_AGENT="HangarBayApp/0.1.0 (local dev)" \
    DATABASE_URL_TESTS="postgresql+asyncpg://hangar_bay_user:hangar_bay_password@localhost:5432/hangar_bay_test_f008" \
    .venv/bin/pytest -q
    ```
    The copied `src/.env` lacks `ESI_USER_AGENT` and `DATABASE_URL_TESTS`; both come from process env (env beats `.env` in pydantic-settings). The scratch DB `hangar_bay_test_f008` already exists. Note the migration-equivalence fixture additionally creates/drops `m4_equiv_check` on the same server — a second reason not to run two suites at once.
12. Frontend: `npx eslint .` · `npx tsc -b` · `npm run test` · `npm run test:future-clock` · `npm run e2e` (fixture lane) — all green before any frontend commit claims completion. New component tests must pass under BOTH vitest lanes (fixture dates from `src/test/dates.ts`, never literals — TEST-17).
13. Backend lint: `pdm run lint`. Never `pdm run format` repo-wide (ENV-7) — format only new files individually with `.venv/bin/black <file>`.
14. Do not run `pdm run dev` casually: this worktree's `.env` has `DB_RECREATE_ON_STARTUP` unset (defaults False) so it won't wipe, but batch backend edits anyway (ENV-3).

**Pitfalls that govern this feature (read both docs in full first — `docs/pitfalls/implementation-pitfalls.md`, `docs/pitfalls/testing-pitfalls.md`)**
15. **SQLA-3 / TEST-19 are the heart of this feature:** every item-level filter is a contract-level classification and MUST be a correlated EXISTS over offered items, tested with a mixed-child fixture and §3.1's three-way identity (`branch_a + branch_b + neither == unfiltered`, expected `neither` stated in the fixture).
16. FASTAPI-1 (filters bind via `Annotated[ContractFilters, Query()]` — already the case; keep it), FASTAPI-3 (every new response field Optional unless provably non-null for all rows), ESI-3 (absence ≠ zero: `runs` is omitted on originals; `.get()` everywhere), PROXY-1 (no `/api/v1` in FastAPI; schema paths verbatim incl. trailing slash), SQLA-1 (new sorts must survive the grouped-ID pagination), TEST-14 (never add tests to a VCR-marked module — both `tests/api/test_contracts.py` and `test_contract_filters.py` are safe, `pytestmark` asyncio-only), TEST-18 (before writing a fixture column, confirm the ingestion writer assigns it), TEST-20 (no assertions inside `if data[...]:`), WEB-1 (added by Task C4 — anything describing the rows comes off the query result, never off the live URL, because `keepPreviousData` holds the previous rows through every segment switch).
17. **ORCH-1:** any subagent dispatched for analysis (not this plan's implementation tasks — those produce commits, which are the record) must write findings to a durable file under `docs/` before returning, per `docs/git-strategy.md` §Output persistence.

**Cross-file synchronization traps (from recon — these are the ones a task will not discover on its own)**
18. `ContractListResponse` is constructed in **two places** (`contract_service.py:427-433` empty short-circuit, `:452-458` normal path). Every new envelope field threads through both.
19. `_count_unknown_system_excluded` (`contract_service.py:274-295`) **rebuilds the query from scratch** through `_apply_contract_filters` + `_apply_item_filters`. Every new filter MUST be applied inside one of those two helpers — a filter applied anywhere else silently desynchronizes the residual count.
20. `still_listed_by_esi()` has **three call sites** (contracts list; watchlist matcher `_match_and_notify:166` and `_prune:217`). Nothing in this plan changes it; if a task thinks it needs to, STOP and re-read the perf audit first.
21. The watchlist matcher hand-writes its own item predicates (`watchlist_matcher.py:148-168`) and does not flow through `ContractFilters` — F008's filter rework does NOT touch it, deliberately. It also hardcodes `Contract.type.in_(("item_exchange", "auction"))` at `:151`; Task B1 points that literal at the new enum's values without changing behavior.
22. The joined fetch path re-selects page entities **without filters** (`_fetch_page_joined:325-329`), so eager-loaded `contract.items` is always ALL of a contract's items. Derived structures (composition, blueprint summary, primary label) are therefore computed from the full item set — which is what §17 wants (they describe the contract, not the filter match).
23. Fixture region isolation: every self-seeding API test uses a private `start_location_region_id` and filters on it. In use: 99999901–99999905, 99999911/12, 99999951–99999954. **This plan allocates 99999960–99999979; tasks claim them in order and note the claim in the task.**
24. Frontend seams for any new URL param (all seven, from recon): `ContractSearch` interface → `parseContractSearch` → `toApiQuery` → `FilterRail.hasActiveFilters` → `ContractsPage.resetFilters` → `SaveSearchControl.toSavedSearchParameters` → e2e `filters.spec.ts:176-185` clear-filters URL enumeration.
25. `e2e/fixtures/contracts.ts` wire interfaces are hand-maintained mirrors of the OpenAPI shapes. PR-C updates them to the new list-row shape (no `items`, new fields, envelope `segment_counts` + `coverage`) — stale mirrors make every spec assert against a response the real API can no longer produce.

---

# Phase A — Data layer (branch `feat/f008-data-layer`, PR-A, `Review — database schema`)

**Execution Status:** ✅ SHIPPED at `c0e3d85` on 2026-08-07 (PR #138 merged at `8303e15`). Tasks A1–A8: `a7cd7ba`, `fc60be8`, `551704b`, `49b15b8`, `492a7b1`, `699ee3f`+`679b9e8`, `1cb8d40`, `bb95eed`; gate fixes `b7b7bda`, codex dispositions `c0e3d85` (group-name DB-observed retry added; name NULL-overwrite deferred per decision-log D10).

Everything ingestion-side: the single migration, contract-level and item-level writes, end-location resolution, the taxonomy name cache, the completion-predicate widening, the manifest, and the version bump. After this phase merges, an ordinary ingestion run populates every contract-level column and a resweep populates every item-level column. **No API or frontend change in this phase.**

### Task A1: The migration + model changes (single-writer; everything else in A depends on it)

**Files:**
- Modify: `app/backend/src/fastapi_app/models/contracts.py`
- Create: `app/backend/src/alembic/versions/<generated>_f008_type_aware_columns.py`
- Test (existing, drives TDD): `app/backend/src/fastapi_app/tests/test_migrations.py::test_migrated_schema_matches_model_metadata`

**Interfaces — Produces (later tasks rely on these exact names/types):**
- `Contract.buyout: Mapped[Optional[float]]` (Numeric), `Contract.days_to_complete: Mapped[Optional[int]]` (Integer), `Contract.end_location_name: Mapped[Optional[str]]` (String), `Contract.end_location_system_id: Mapped[Optional[int]]` (Integer)
- `ContractItem.category_id / group_id / runs / material_efficiency / time_efficiency: Mapped[Optional[int]]` (Integer), `ContractItem.item_id: Mapped[Optional[int]]` (BigInteger)
- `EsiTaxonomyCache` model: `kind: Mapped[str]` (String, PK part), `esi_id: Mapped[int]` (Integer, PK part), `name: Mapped[str]` (String, non-null), `parent_category_id: Mapped[Optional[int]]`, `fetched_at: Mapped[datetime]` (DateTime(timezone=True), non-null)

- [x] **Step 1: Confirm the chain has one head** — `cd app/backend/src && ../.venv/bin/python -m alembic heads` prints exactly `ea2491c47a9f (head)`. If it prints anything else, STOP: another migration landed; re-anchor `down_revision` before proceeding.
- [x] **Step 2: Make the equivalence test the failing test.** Add all model changes (below), run
  `pytest fastapi_app/tests/test_migrations.py::test_migrated_schema_matches_model_metadata -q` → expect FAIL with a non-empty schema diff (models ahead of migrations). This is the red step.

  Model additions — `Contract`, inserted after `volume` (`models/contracts.py:64`), matching sibling style:
  ```python
      # Auction-only: the price that ends the auction immediately. ESI omits it for
      # non-auctions and for auctions without one; absence must stay distinguishable
      # from zero (ESI-3), so nullable with no default.
      buyout: Mapped[Optional[float]] = mapped_column(Numeric, nullable=True)
      # Courier-only: contracted days to deliver once accepted.
      days_to_complete: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
  ```
  and after `start_location_name` (`:67`):
  ```python
      end_location_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
  ```
  and after `start_location_system_id` (`:56`) — Integer to match its sibling; solar-system ids fit int32:
  ```python
      # NULL where the destination is a player structure (no tokenless resolution
      # route) — measured ~5% of Forge couriers. Written by ingestion for the
      # reward-per-jump follow-on; nothing in F008 reads it.
      end_location_system_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
  ```
  `ContractItem`, after `is_blueprint_copy` (`:118`):
  ```python
      # Dogma taxonomy, resolved during enrichment from the type→group→category chain
      # that already computes the ship flag. Names live in esi_taxonomy_cache.
      category_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
      group_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
      # Blueprint-copy fields from the PUBLIC item route. A blueprint ORIGINAL omits
      # `runs` entirely rather than sending -1 (ESI-3) — absence means original.
      runs: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
      material_efficiency: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
      time_efficiency: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
      # Join key to /dogma/dynamic/items/{type_id}/{item_id} for the abyssal
      # follow-on; written now so that work needs no corpus re-ingest.
      item_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
  ```
  New model, after `EsiMarketGroupCache` (`:35`):
  ```python
  class EsiTaxonomyCache(Base):
      """Dogma category/group display names, keyed (kind, esi_id).

      Criterion 3.5's option list needs names, and the enrichment pipeline only holds
      them transiently. kind is 'category' or 'group'; ids share an integer space with
      market groups, which is why EsiMarketGroupCache is not reused (spec §5.2).
      """
      __tablename__ = 'esi_taxonomy_cache'

      kind: Mapped[str] = mapped_column(String, primary_key=True)
      esi_id: Mapped[int] = mapped_column(Integer, primary_key=True)
      name: Mapped[str] = mapped_column(String, nullable=False)
      # The owning category for kind='group'; NULL for kind='category'.
      parent_category_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
      fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
  ```
  Index additions — `Contract.__table_args__` gains (after the `volume` entry):
  ```python
          Index('ix_contracts_buyout', 'buyout'),
          Index('ix_contracts_days_to_complete', 'days_to_complete'),
  ```
  `ContractItem.__table_args__` gains (after the `raw_quantity` entry; decision-log D5):
  ```python
          # Indexes for the taxonomy and blueprint filter families (correlated EXISTS
          # probes at corpus scale — same rationale as is_blueprint_copy above).
          Index('ix_contract_items_category_id', 'category_id'),
          Index('ix_contract_items_group_id', 'group_id'),
          Index('ix_contract_items_runs', 'runs'),
          Index('ix_contract_items_material_efficiency', 'material_efficiency'),
          Index('ix_contract_items_time_efficiency', 'time_efficiency'),
  ```
- [x] **Step 3: Author the migration** (green step). `pdm run makemigration f008_type_aware_columns` may scaffold it, but hand-verify against house style — required shape (fill the generated revision id; `down_revision = 'ea2491c47a9f'`):
  ```python
  """f008 type-aware columns

  Ten nullable columns for type-aware browsing (auction buyout, courier fields,
  blueprint stats, dogma taxonomy, dynamic-item join key) plus the taxonomy name
  cache. All nullable because ESI omits each for contracts it does not apply to,
  and absence must stay distinguishable from zero (ESI-3). No backfill: contract-
  level columns fill on the next ordinary ingestion run, item-level columns via
  the ENRICHMENT_VERSION resweep (spec §7).

  Revision ID: <generated>
  Revises: ea2491c47a9f
  Create Date: <generated>

  """
  from typing import Sequence, Union

  from alembic import op
  import sqlalchemy as sa


  revision: str = '<generated>'
  down_revision: Union[str, None] = 'ea2491c47a9f'
  branch_labels: Union[str, Sequence[str], None] = None
  depends_on: Union[str, Sequence[str], None] = None


  def upgrade() -> None:
      """Upgrade schema."""
      # Pre-deploy command on a live database; fail fast rather than queue behind
      # the outgoing instance's ingestion transaction.
      op.execute("SET lock_timeout = '30s'")
      op.add_column('contracts', sa.Column('buyout', sa.Numeric(), nullable=True))
      op.add_column('contracts', sa.Column('days_to_complete', sa.Integer(), nullable=True))
      op.add_column('contracts', sa.Column('end_location_name', sa.String(), nullable=True))
      op.add_column('contracts', sa.Column('end_location_system_id', sa.Integer(), nullable=True))
      op.create_index('ix_contracts_buyout', 'contracts', ['buyout'], unique=False)
      op.create_index('ix_contracts_days_to_complete', 'contracts', ['days_to_complete'], unique=False)

      op.add_column('contract_items', sa.Column('category_id', sa.Integer(), nullable=True))
      op.add_column('contract_items', sa.Column('group_id', sa.Integer(), nullable=True))
      op.add_column('contract_items', sa.Column('runs', sa.Integer(), nullable=True))
      op.add_column('contract_items', sa.Column('material_efficiency', sa.Integer(), nullable=True))
      op.add_column('contract_items', sa.Column('time_efficiency', sa.Integer(), nullable=True))
      op.add_column('contract_items', sa.Column('item_id', sa.BigInteger(), nullable=True))
      op.create_index('ix_contract_items_category_id', 'contract_items', ['category_id'], unique=False)
      op.create_index('ix_contract_items_group_id', 'contract_items', ['group_id'], unique=False)
      op.create_index('ix_contract_items_runs', 'contract_items', ['runs'], unique=False)
      op.create_index('ix_contract_items_material_efficiency', 'contract_items', ['material_efficiency'], unique=False)
      op.create_index('ix_contract_items_time_efficiency', 'contract_items', ['time_efficiency'], unique=False)

      op.create_table(
          'esi_taxonomy_cache',
          sa.Column('kind', sa.String(), nullable=False),
          sa.Column('esi_id', sa.Integer(), nullable=False),
          sa.Column('name', sa.String(), nullable=False),
          sa.Column('parent_category_id', sa.Integer(), nullable=True),
          sa.Column('fetched_at', sa.DateTime(timezone=True), nullable=False),
          sa.PrimaryKeyConstraint('kind', 'esi_id'),
      )


  def downgrade() -> None:
      """Downgrade schema."""
      op.drop_table('esi_taxonomy_cache')
      op.drop_index('ix_contract_items_time_efficiency', table_name='contract_items')
      op.drop_index('ix_contract_items_material_efficiency', table_name='contract_items')
      op.drop_index('ix_contract_items_runs', table_name='contract_items')
      op.drop_index('ix_contract_items_group_id', table_name='contract_items')
      op.drop_index('ix_contract_items_category_id', table_name='contract_items')
      op.drop_column('contract_items', 'item_id')
      op.drop_column('contract_items', 'time_efficiency')
      op.drop_column('contract_items', 'material_efficiency')
      op.drop_column('contract_items', 'runs')
      op.drop_column('contract_items', 'group_id')
      op.drop_column('contract_items', 'category_id')
      op.drop_index('ix_contracts_days_to_complete', table_name='contracts')
      op.drop_index('ix_contracts_buyout', table_name='contracts')
      op.drop_column('contracts', 'end_location_system_id')
      op.drop_column('contracts', 'end_location_name')
      op.drop_column('contracts', 'days_to_complete')
      op.drop_column('contracts', 'buyout')
  ```
- [x] **Step 4: Run the equivalence test green**, then the whole migration file lane: `pytest fastapi_app/tests/test_migrations.py -q` → PASS. `alembic heads` → exactly one head (the new revision).
- [x] **Step 5: Do NOT hand-edit `openapi.json`/`schema.d.ts`** — nothing wire-visible changed yet (schemas change in PR-B).
- [x] **Step 6: Commit** — `feat(api): add type-aware contract and item columns with taxonomy name cache`

**Do NOT:** add response-schema fields, filters, or any read path here; touch `ENRICHMENT_VERSION`; add a server_default to any new column (absence must remain NULL); reuse `EsiMarketGroupCache`.

### Task A2: Contract-level ingestion writes (`buyout`, `days_to_complete`, `end_location_name`)

**Files:**
- Modify: `app/backend/src/fastapi_app/services/background_aggregation.py` (`_build_contract_rows`, `:160-212`)
- Test: `app/backend/src/fastapi_app/tests/services/test_background_aggregation.py`

**Interfaces — Consumes:** A1's columns. **Produces:** upsert rows now carry `buyout`, `days_to_complete`, `end_location_name` keys (uniform across every row — the bulk_upsert derives update columns from `values[0]`).

- [x] **Step 1: Write the failing test.** In `test_background_aggregation.py`, next to `test_resolved_location_names_land_on_persisted_contract_rows` (`:900`), following its end-to-end `_process_contracts` pattern:
  ```python
  async def test_type_specific_contract_fields_land_on_persisted_rows(db_session: AsyncSession):
      """buyout / days_to_complete / end_location_name persist from the ESI payload.

      _build_contract_rows is only exercised end-to-end (nothing unit-tests its dict
      literal), so each new key needs a persisted-row assertion or its wiring can
      silently drop (same rationale as the location-names test above).
      """
      service = _make_service()
      contract = _ship_contract_dict(801)
      contract["type"] = "auction"
      contract["buyout"] = 950_000_000.0
      contract["days_to_complete"] = 3          # ESI sends it on couriers; mapping is type-agnostic
      contract["end_location_id"] = 60008494
      service.esi_client.resolve_ids_to_names = AsyncMock(
          return_value={
              60003760: "Jita IV - Moon 4 - Caldari Navy Assembly Plant",
              60008494: "Amarr VIII (Oris) - Emperor Family Academy",
          }
      )
      await service._process_contracts(db_session, [contract])

      row = (await db_session.execute(
          select(Contract).where(Contract.contract_id == 801)
      )).scalar_one()
      assert row.buyout == 950_000_000
      assert row.days_to_complete == 3
      assert row.end_location_name == "Amarr VIII (Oris) - Emperor Family Academy"

      # Absence stays NULL (ESI-3): a payload without the fields must not write zeros.
      bare = _ship_contract_dict(802)
      await service._process_contracts(db_session, [bare])
      bare_row = (await db_session.execute(
          select(Contract).where(Contract.contract_id == 802)
      )).scalar_one()
      assert bare_row.buyout is None and bare_row.days_to_complete is None
  ```
- [x] **Step 2: Run it** — FAIL (`row.buyout is None`).
- [x] **Step 3: Implement.** In `_build_contract_rows`'s dict literal: after `"volume": c.get("volume"),` (`:198`) add
  ```python
              "buyout": c.get("buyout"),
              "days_to_complete": c.get("days_to_complete"),
  ```
  and after `"start_location_name": ...` (`:200`) add
  ```python
              "end_location_name": id_to_name_map.get(c.get("end_location_id")),
  ```
  (End locations are already in the name map — `_collect_resolvable_ids:97` unions them. Do not touch the deliberately-absent-columns comment block at `:203-209`.)
- [x] **Step 4: Run green**, then the full aggregation module: `pytest fastapi_app/tests/services/test_background_aggregation.py -q`.
- [x] **Step 5: Commit** — `feat(api): persist buyout, days_to_complete, and end_location_name at ingestion`

### Task A3: End-location system resolution (widen both start-only paths — spec §5.1 exactly)

**Files:**
- Modify: `app/backend/src/fastapi_app/services/background_aggregation.py` — `_npc_station_ids` (`:150-157`), `_select_known_station_systems` (`:575-598`), `_build_contract_rows`
- Test: `tests/services/test_background_aggregation.py`

**Context (do not re-derive):** §5.1 names exactly two paths to widen. The fetch set (`_npc_station_ids`) is start-only; the DB cache read-back (`_select_known_station_systems`) is start-only — and skipping the read-back does not fail loudly, it just re-fetches destination-only stations from ESI forever. The read-back's docstring hazard must be preserved: the upsert copies every supplied column on conflict, so the read-back must cover the `end_location_*` column pair too or an ESI blip writes NULL over known destinations corpus-wide.

- [x] **Step 1: Failing tests** (three, added near the station-resolution block at `:1379+`):
  ```python
  async def test_courier_end_station_resolves_to_its_solar_system(db_session: AsyncSession):
      """end_location_system_id persists via the same station path as starts (§5.1)."""
      service = _make_service()
      contract = _ship_contract_dict(811)
      contract["type"] = "courier"                     # skips item fetching entirely
      contract["end_location_id"] = 60008494
      service.esi_client.get_universe_station = AsyncMock(
          side_effect=lambda sid: {60003760: {"system_id": 30000142},
                                   60008494: {"system_id": 30002187}}[sid]
      )
      await service._process_contracts(db_session, [contract])
      row = (await db_session.execute(select(Contract).where(Contract.contract_id == 811))).scalar_one()
      assert row.start_location_system_id == 30000142
      assert row.end_location_system_id == 30002187

  async def test_structure_end_location_keeps_null_system_and_is_never_requested(db_session):
      """Player-structure destinations stay NULL and never spend ESI error budget."""
      service = _make_service()
      contract = _ship_contract_dict(812)
      contract["type"] = "courier"
      contract["end_location_id"] = 1_040_000_000_000          # Upwell structure id range
      calls = []
      service.esi_client.get_universe_station = AsyncMock(
          side_effect=lambda sid: calls.append(sid) or {"system_id": 30000142}
      )
      await service._process_contracts(db_session, [contract])
      row = (await db_session.execute(select(Contract).where(Contract.contract_id == 812))).scalar_one()
      assert row.end_location_system_id is None
      assert 1_040_000_000_000 not in calls

  async def test_a_known_end_station_survives_an_esi_outage(db_session):
      """The DB read-back covers END pairs too — without it, an outage run would
      re-resolve from scratch, get nothing, and bulk_upsert would write NULL over
      every known destination (the §5.1 hazard, end-column edition)."""
      service = _make_service()
      first = _ship_contract_dict(813); first["type"] = "courier"; first["end_location_id"] = 60008494
      service.esi_client.get_universe_station = AsyncMock(
          side_effect=lambda sid: {60003760: {"system_id": 30000142},
                                   60008494: {"system_id": 30002187}}[sid]
      )
      await service._process_contracts(db_session, [first])

      # Second sighting: ESI down for stations. The pair must come from the table.
      service.esi_client.get_universe_station = AsyncMock(side_effect=Exception("ESI down"))
      again = _ship_contract_dict(813); again["type"] = "courier"; again["end_location_id"] = 60008494
      await service._process_contracts(db_session, [again])
      row = (await db_session.execute(select(Contract).where(Contract.contract_id == 813))).scalar_one()
      assert row.end_location_system_id == 30002187
  ```
- [x] **Step 2: Run — all three FAIL** (first on NULL end system; third may fail on NULL-overwrite).
- [x] **Step 3: Implement.**
  - `_npc_station_ids`: collect from both roles, updating the docstring truthfully:
    ```python
    def _npc_station_ids(contracts: List[dict]) -> set[int]:
        """The distinct start and end locations /universe/stations/ can answer for."""
        return {
            location_id
            for contract in contracts
            for location_id in (contract.get("start_location_id"), contract.get("end_location_id"))
            if location_id is not None
            and NPC_STATION_ID_MIN <= location_id < NPC_STATION_ID_MAX
        }
    ```
  - `_select_known_station_systems`: union a second SELECT over the end pair into `known` (same chunked loop, `Contract.end_location_id` / `Contract.end_location_system_id`, `is_not(None)`, `.distinct()`), and extend the docstring's hazard sentence to say the read-back covers both roles for exactly that reason.
  - `_build_contract_rows`: next to `start_location_system_id` (`:184`) add
    ```python
            "end_location_system_id": station_to_system.get(c.get("end_location_id")),
    ```
- [x] **Step 4: Run green; run the whole station block** (`pytest -q -k station`), confirming the four existing station tests (`:1379`, `:1398`, `:1425`, `:1484`, `:1531`) still pass — the boundary test pins the id-range logic your comprehension must preserve.
- [x] **Step 5: Commit** — `feat(api): resolve courier end locations to solar systems at ingestion`

### Task A4: Item-level ingestion writes (`runs`, `material_efficiency`, `time_efficiency`, `item_id`, `category_id`, `group_id`)

**Files:**
- Modify: `background_aggregation.py` — `_fetch_item_rows` item mapping (`:647-662`) and `_enrich_items_and_find_ships` (`:780-800`)
- Test: `tests/services/test_background_aggregation.py`

- [x] **Step 1: Failing test** (end-to-end through `_process_contracts`, the enrichment-stubbing idiom from `:133-144`):
  ```python
  async def test_item_level_columns_persist_from_payload_and_enrichment(db_session):
      """runs/ME/TE/item_id come off the item payload; category_id/group_id off the
      type→group chain the ship flag already walks. A blueprint ORIGINAL omits runs
      entirely (ESI-3) and must persist NULL, not zero."""
      service = _make_service()
      contract = _ship_contract_dict(821)
      service.esi_client.get_contract_items = AsyncMock(return_value=[
          {"record_id": 8211, "type_id": 621, "quantity": 1, "is_included": True,
           "is_blueprint_copy": True, "runs": 10, "material_efficiency": 8,
           "time_efficiency": 14, "item_id": 1_000_000_001},
          {"record_id": 8212, "type_id": 621, "quantity": 1, "is_included": True},  # original: runs absent
      ])
      service.esi_client.get_universe_type = AsyncMock(
          return_value={"name": "Caracal Blueprint", "group_id": 105, "market_group_id": 4}
      )
      service.esi_client.get_universe_group = AsyncMock(
          return_value={"name": "Cruiser Blueprint", "category_id": 9}
      )
      await service._process_contracts(db_session, [contract])

      rows = {r.record_id: r for r in (await db_session.execute(
          select(ContractItem).where(ContractItem.contract_id == 821)
      )).scalars()}
      copy, original = rows[8211], rows[8212]
      assert (copy.runs, copy.material_efficiency, copy.time_efficiency) == (10, 8, 14)
      assert copy.item_id == 1_000_000_001
      assert copy.category_id == 9 and copy.group_id == 105
      assert original.runs is None and original.material_efficiency is None
      assert original.category_id == 9          # taxonomy resolves regardless of blueprint fields
  ```
- [x] **Step 2: Run — FAIL.**
- [x] **Step 3: Implement.** In `_fetch_item_rows`'s dict literal (after `"raw_quantity"`):
  ```python
                      "runs": i.get("runs"),
                      "material_efficiency": i.get("material_efficiency"),
                      "time_efficiency": i.get("time_efficiency"),
                      "item_id": i.get("item_id"),
  ```
  In `_enrich_items_and_find_ships`, in the unconditional per-item block (`:785-787`) — both values are already in local scope:
  ```python
              item["group_id"] = info.get("group_id")
              item["category_id"] = group.get("category_id")
  ```
  (Uniform-keys constraint at `:784` is satisfied because the block is unconditional. **No new ESI call** — resist the urge; §16.2.)
- [x] **Step 4: Green; run the enrichment-version tests** (`:573`, `:595`, `:673`, `:706`) to confirm the added keys didn't disturb the upsert's uniform key set.
- [x] **Step 5: Mutation-verify** (TEST-12): `cp` snapshot, delete the `item["category_id"] = ...` line, confirm the new test goes red on `category_id is None`, restore, rerun green.
- [x] **Step 6: Commit** — `feat(api): persist blueprint stats, item_id, and dogma taxonomy ids during enrichment`

### Task A5: Taxonomy name cache population

**Files:**
- Modify: `app/backend/src/fastapi_app/core/esi_client_class.py` (new `get_universe_category`), `background_aggregation.py` (`_enrich_items_and_find_ships` + a new `_upsert_taxonomy_names` helper)
- Test: `tests/services/test_background_aggregation.py`

**Interfaces — Produces:** `EsiTaxonomyCache` rows: `('group', <id>, name, parent_category_id, fetched_at)` from group payloads already in hand; `('category', <id>, name, NULL, fetched_at)` from the one new ESI call. `ESIClient.get_universe_category(category_id: int) -> dict[str, Any]`.

- [x] **Step 1: Failing test:**
  ```python
  async def test_enrichment_fills_the_taxonomy_name_cache(db_session):
      """Group names ride the payloads enrichment already fetches; category names come
      from the one new ESI call (§5.2), cache-first so the tiny immutable set is
      fetched once, ever."""
      service = _make_service()
      contract = _ship_contract_dict(831)
      service.esi_client.get_contract_items = AsyncMock(return_value=[
          {"record_id": 8311, "type_id": 587, "quantity": 1, "is_included": True},
      ])
      service.esi_client.get_universe_type = AsyncMock(
          return_value={"name": "Tristan", "group_id": 25, "market_group_id": 5}
      )
      service.esi_client.get_universe_group = AsyncMock(
          return_value={"name": "Frigate", "category_id": 6}
      )
      service.esi_client.get_universe_category = AsyncMock(return_value={"name": "Ship"})
      await service._process_contracts(db_session, [contract])

      rows = {(r.kind, r.esi_id): r for r in (await db_session.execute(
          select(EsiTaxonomyCache)
      )).scalars()}
      assert rows[("group", 25)].name == "Frigate"
      assert rows[("group", 25)].parent_category_id == 6
      assert rows[("category", 6)].name == "Ship"

      # Second run: category already cached — the ESI call must not repeat.
      service.esi_client.get_universe_category.reset_mock()
      again = _ship_contract_dict(832)
      service.esi_client.get_contract_items = AsyncMock(return_value=[
          {"record_id": 8321, "type_id": 587, "quantity": 1, "is_included": True},
      ])
      await service._process_contracts(db_session, [again])
      service.esi_client.get_universe_category.assert_not_awaited()
  ```
- [x] **Step 2: FAIL** (no `EsiTaxonomyCache` import / no rows).
- [x] **Step 3: Implement.**
  - `ESIClient`, next to `get_universe_group` (`esi_client_class.py:463-465`) — **verify the version prefix against the committed snapshot (`tools/esi_spec_monitor/snapshot.json`), not memory**, then:
    ```python
    async def get_universe_category(self, category_id: int) -> dict[str, Any]:
        """Fetches static dogma category info (name). Immutable set; long TTL."""
        return await self._get_esi_object(f"/v1/universe/categories/{category_id}/")
    ```
    (Object endpoint → `_get_esi_object`, never the list-shaped ETag helper — its docstring records the live incident.)
  - `background_aggregation.py`: at the end of `_enrich_items_and_find_ships` (after the loop, before `return`), gather what the run learned and hand it to a new helper called from `_process_contracts` right after enrichment:
    ```python
    async def _upsert_taxonomy_names(
        self, db_session: AsyncSession, group_info: dict[int, dict]
    ) -> None:
        """Persist dogma names for the option list (spec §5.2, Criterion 3.5).

        Group names ride payloads already fetched. Category names need the one new
        ESI call this feature adds — cache-first, because the set is tiny and
        immutable, so steady state fetches zero categories.
        """
        now = datetime.now(timezone.utc)
        group_rows = [
            {"kind": "group", "esi_id": gid, "name": info["name"],
             "parent_category_id": info.get("category_id"), "fetched_at": now}
            for gid, info in group_info.items()
            if info.get("name") is not None
        ]
        if group_rows:
            await bulk_upsert(db_session, EsiTaxonomyCache, group_rows)

        category_ids = {
            info.get("category_id") for info in group_info.values()
            if info.get("category_id") is not None
        }
        if not category_ids:
            return
        cached = set((await db_session.execute(
            select(EsiTaxonomyCache.esi_id).where(
                EsiTaxonomyCache.kind == "category",
                EsiTaxonomyCache.esi_id.in_(category_ids),
            )
        )).scalars())
        missing = category_ids - cached
        if not missing:
            return
        payloads = await _resolve_esi_objects(
            self.esi_client.get_universe_category, missing, "Category"
        )
        category_rows = [
            {"kind": "category", "esi_id": cid, "name": p["name"],
             "parent_category_id": None, "fetched_at": now}
            for cid, p in payloads.items()
            if p.get("name") is not None
        ]
        if category_rows:
            await bulk_upsert(db_session, EsiTaxonomyCache, category_rows)
    ```
    `_enrich_items_and_find_ships` returns `group_info` alongside its two sets (change its return to `tuple[set[int], set[int], dict[int, dict]]` and update the single call site at `:528-534`); `_process_contracts` then awaits `self._upsert_taxonomy_names(db_session, group_info)`.

    **The retry path must not depend on re-enrichment (codex round-2 finding 5 — confirmed).** A COMPLETED-current contract is skipped by `_select_already_enriched`, so its group data never re-reaches this helper: a category whose first name fetch failed would stay missing forever unless a *new* contract happened to carry it. Therefore `category_ids` in the helper is the union of (a) the ids off this run's `group_info` and (b) **ids observed in the database but absent from the cache**: a loose-index-scan over `ix_contract_items_category_id` (the B4/B7 CTE pattern — small distinct set, sub-ms) set-differenced against `kind='category'` cache keys. That makes the cache self-healing on every run regardless of enrichment skips, and it is the same query B7's completeness condition runs — extract it as a shared module-level helper `_observed_category_ids(db_session) -> set[int]` so the two cannot drift.
- [x] **Step 3b: Failing test for the retry path:** first run with `get_universe_category` raising → no category row, contract COMPLETED; second run with the mock healed and a contract batch that does NOT include the category (e.g. a courier-only batch) → the category row appears anyway (fetched via the DB-observed missing set).
- [x] **Step 4: Green.** The shape-guard behavior (`_resolve_esi_objects` drops non-dict payloads) degrades one id per failure without killing the run; the observed-missing union above is what guarantees the retry.
- [x] **Step 5: Commit** — `feat(api): cache dogma category and group names for the taxonomy option list`

### Task A6: ESI drift-monitor manifest + snapshot

**Files:**
- Modify: `app/backend/tools/esi_spec_monitor/manifest.py`, `app/backend/tools/esi_spec_monitor/snapshot.json` (regenerated, never hand-edited)
- Test: `pdm run pytest -q tools` (the monitor's own unit lane) + `pdm run esi-spec-monitor`

No TDD exemption issues — this is tooling config, but the monitor's tests run in the ordinary lane.

- [x] **Step 1:** Add the six consumed fields (spec §6.1 point 1): `buyout`, `days_to_complete` to the `/contracts/public/{region_id}` block; `runs`, `material_efficiency`, `time_efficiency`, `item_id` to the `/contracts/public/items/{contract_id}` block — each value string naming its consumer in the house format, e.g. `"runs": "background_aggregation._fetch_item_rows -> ContractItem.runs; blueprint-copy display and the min_runs/max_runs filter (F008)"`.
- [x] **Step 2:** Amend the two existing entries (point 2): `group_id` (`manifest.py:133`) and `category_id` (`:143`) consumer notes now also name the persisted `ContractItem.group_id`/`category_id` columns and the taxonomy cache. While editing, correct the stale method name in those strings: the function is `_enrich_items_and_find_ships`, not `_enrich_items`.
- [x] **Step 3:** Add a new `Endpoint` block for `GET /universe/categories/{category_id}` (spec_path `/universe/categories/{category_id}`, call_path `/v1/universe/categories/{category_id}/` — match whatever version Task A5 verified, caller `background_aggregation._upsert_taxonomy_names`, consumed field `name`).
- [x] **Step 4:** Leave the `raw_quantity` `KnownAbsentField` (`:114-118`) **unchanged in this PR** — its "read by min_runs/max_runs" consequence stays true until PR-B rewires the filter; PR-B Task B5 amends it (spec §6.1 point 3).
- [x] **Step 5:** `pdm run esi-spec-monitor --update` to regenerate the snapshot; commit it with the reason in the message. Run `pdm run esi-spec-monitor` → green; `pytest tools -q` → green.
- [x] **Step 6: Commit** — `chore(api): extend the ESI drift manifest to the F008 field set`

### Task A7: Completion-predicate widening (requested items' categories count)

**Files:**
- Modify: `background_aggregation.py:798` (the `elif` guard)
- Test: `tests/services/test_background_aggregation.py`

**Context:** Criterion 8.1 renders requested items and 6.3 summarizes them by category, so a contract whose *requested* item failed category resolution must not be stamped COMPLETED (spec §9 "a narrow scope mismatch this feature creates"). The ship-flag `if` at `:789` keeps its `is_included` guard — only offered items decide the flag; the failure-tracking `elif` drops its guard.

- [x] **Step 1: Failing test:**
  ```python
  async def test_a_requested_items_failed_category_leaves_the_contract_retryable(db_session):
      """Want-to-buy side: an EXCLUDED item with no resolvable group must block
      COMPLETED, or the contract is withheld from every future re-fetch with a
      permanently blank requested side (spec §9)."""
      service = _make_service()
      contract = _ship_contract_dict(841)
      service.esi_client.get_contract_items = AsyncMock(return_value=[
          {"record_id": 8411, "type_id": 587, "quantity": 1, "is_included": True},
          {"record_id": 8412, "type_id": 99999, "quantity": 1, "is_included": False},
      ])
      service.esi_client.get_universe_type = AsyncMock(
          side_effect=lambda tid: {587: {"name": "Tristan", "group_id": 25},
                                   99999: {"name": "Mystery Meat"}}[tid]   # no group_id
      )
      service.esi_client.get_universe_group = AsyncMock(
          return_value={"name": "Frigate", "category_id": 6}
      )
      await service._process_contracts(db_session, [contract])
      row = (await db_session.execute(select(Contract).where(Contract.contract_id == 841))).scalar_one()
      assert row.item_processing_status == "ENRICHMENT_INCOMPLETE"
  ```
- [x] **Step 1b (codex round-2 finding 7 — confirmed): a second failing test** for the payload shape `{"name": "Frigate"}` — a NON-empty group dict with no `category_id`. Under the naive `elif not group:` fix, `not group` is False, `category_id` lands NULL, and the contract is stamped COMPLETED forever — the exact silent-unenrichment the predicate exists to prevent. Same test shape as Step 1 with `get_universe_group` returning `{"name": "Frigate"}` for the requested item's chain; assert `ENRICHMENT_INCOMPLETE`.
- [x] **Step 2: FAIL** (currently stamps COMPLETED — the guard skips excluded items).
- [x] **Step 3: Implement:** the unresolved test is **`item["category_id"] is None`** — after Task A4, that assignment (`group.get("category_id")`) is exactly "did category resolution succeed", and it covers both the empty-group and the category-less-payload shapes in one condition. Change `:798` from `elif not group and item["is_included"]:` to `elif item["category_id"] is None:` (the `elif` still chains off the ship-flag `if`, so a resolved ship item never reaches it) and update the adjacent comment block (`:792-797`) to say the category half covers every item because requested items now render by category (F008 Criteria 6.3/8.1), while the ship-flag `if` above stays offered-only.
- [x] **Step 4: Green; run `:744` and `:785`** (the existing unresolved-category tests) — they pin the offered-item half and must stay green.
- [x] **Step 5: Commit** — `fix(api): keep contracts retryable when a requested item's category fails to resolve`

### Task A8: The `ENRICHMENT_VERSION` bump (last ingestion change; nothing after this touches ingestion)

**Files:** `background_aggregation.py:73`
**Test:** existing `:673` / `:706` (they monkeypatch relative to the constant and stay green by construction; the point of this task is the production resweep).

- [x] **Step 1:** Change `ENRICHMENT_VERSION = 1` → `ENRICHMENT_VERSION = 2`. Do not edit the runbook comment (it is evergreen).
- [x] **Step 2:** Full backend suite green (Global Constraint 11 invocation), `pdm run lint` green.
- [x] **Step 3: Commit** — `feat(api): requeue the corpus to backfill item-level taxonomy and blueprint columns`

  Body must carry the operational note: the next production run after deploy is a one-off ~80-minute resweep; the lock-token-mismatch warning at its end is expected; do not redeploy mid-resweep (runbook at the constant).

### Task A9: Phase A gate — review, codex, merge

- [x] **Step 1:** Full verification: backend suite green on the scratch DB, `pdm run lint`, `alembic heads` = 1, `pytest fastapi_app/tests/test_migrations.py -q` green.
- [x] **Step 2:** Three self-review rounds with distinct lenses: (a) spec §4.1/§5/§7 coverage — every data-layer claim implemented; (b) ESI-3 sweep — every new mapping uses `.get()`, no default masquerading as data; (c) bulk-upsert semantics — uniform keys, no enrichment-maintained column added to `_build_contract_rows`, read-back covers both location roles. Fix everything found; extra rounds until clean.
- [x] **Step 3:** Push branch, open PR-A against `dev` (`## Merge classification` → `Review — database schema`, note Sam's 2026-08-06 merge grant). Run the backgrounded codex review; address findings (fix or rebut in PR comments); record any consequential choice in the decision log.
- [x] **Step 4:** CI green (verify explicitly) → `gh pr merge <n> --merge --delete-branch --body ""`. Update this plan's banner + table with SHAs. (The local branch survives in-worktree; expected — the `gh` exit-1 on local cleanup after a successful remote merge is a known worktree artifact.)

---

# Phase B — API contract (branch `feat/f008-api-contract` off merged `dev`, PR-B, `Review — public API contract`)

**Execution Status:** 🚧 IN PROGRESS — claimed 2026-08-07T14:05Z on branch `feat/f008-api-contract` (carries Tasks C1/C2 per the codex round-2 PR-boundary correction).

Everything wire-visible: the §17 model split, the contract-type filter and grouped counts, coverage, functional item-level filters, new sorts, the taxonomy endpoint, the saved-search widening, the PII log fix, and the regenerated client artifacts. Rebase onto `dev` after PR-A merges before starting.

### Task B1: `ContractType` enum + `contract_type` filter

**Files:**
- Modify: `app/backend/src/fastapi_app/schemas/contracts.py`, `app/backend/src/fastapi_app/services/contract_service.py` (`_apply_contract_filters`), `app/backend/src/fastapi_app/services/watchlist_matcher.py:151` (+ `:43`)
- Test: `tests/api/test_contract_filters.py` (private region **99999960**)

**Interfaces — Produces:** `ContractType(str, Enum)` with members `item_exchange, auction, courier, loan, unknown` (the full ESI set, spec Criterion 1.1); `ContractFilters.contract_type: Optional[List[ContractType]]`.

- [x] **Step 1: Failing tests** (HTTP-level per TEST-1; region 99999960):
  ```python
  async def test_filter_by_contract_type(client, db_session):
      """contract_type narrows to the named types; repeated params combine; an
      unknown value 422s instead of silently matching nothing (spec §17.8)."""
      now = datetime.now(timezone.utc)
      def _c(cid, ctype):
          return Contract(
              contract_id=cid, title=f"t{cid}", price=1_000_000, collateral=0,
              status="unknown", type=ctype, issuer_id=1, issuer_corporation_id=1,
              start_location_id=60003760, start_location_region_id=99999960,
              for_corporation=False, date_issued=now,
              date_expired=now + timedelta(days=7),
          )
      db_session.add_all([_c(960001, "item_exchange"), _c(960002, "auction"),
                          _c(960003, "courier"), _c(960004, "loan")])
      await db_session.flush()

      one = await client.get("/contracts/?region_ids=99999960&contract_type=courier")
      assert one.status_code == 200
      assert [c["contract_id"] for c in one.json()["items"]] == [960003]

      two = await client.get(
          "/contracts/?region_ids=99999960&contract_type=auction&contract_type=loan"
      )
      assert {c["contract_id"] for c in two.json()["items"]} == {960002, 960004}
      assert two.json()["total"] == 2

      bad = await client.get("/contracts/?region_ids=99999960&contract_type=barter")
      assert bad.status_code == 422
  ```
  Plus the FASTAPI-1 sentinel: extend `test_id_list_filters_are_query_params_in_openapi_schema` (`test_contract_filters.py:243`) to assert `contract_type` appears as a query parameter.
- [x] **Step 2: FAIL** (unknown param today is ignored → 200).
- [x] **Step 3: Implement.** In `schemas/contracts.py`, above `SortableContractFields`:
  ```python
  class ContractType(str, Enum):
      """Every contract type ESI can emit (confirmed against the committed spec
      snapshot). Typed as an enum so an unknown value 422s instead of silently
      matching nothing — the defect class this feature exists to remove (§17.8)."""

      item_exchange = "item_exchange"
      auction = "auction"
      courier = "courier"
      loan = "loan"
      unknown = "unknown"
  ```
  `ContractFilters`, next to the ID lists (copying the `region_ids` Field shape):
  ```python
      contract_type: Optional[List[ContractType]] = Field(
          default=None, description="Contract types to include (repeatable)."
      )
  ```
  `contract_service._apply_contract_filters`, in section 2b next to `is_ship_contract`:
  ```python
      if filters.contract_type:
          query = query.filter(
              Contract.type.in_([t.value for t in filters.contract_type])
          )
  ```
  (Applied inside `_apply_contract_filters` so the residual count stays synchronized — Global Constraint 19. `Contract.type` leads `ix_contracts_type_status`, so the composite serves a type-only predicate as a prefix; no new index.)
  `watchlist_matcher.py:151`: replace the tuple literal with `(ContractType.item_exchange.value, ContractType.auction.value)` (import from `..schemas.contracts`) — same behavior, one authority for the vocabulary.
- [x] **Step 4: Green**; run the watchlist matcher module too (`pytest -q fastapi_app/tests/services/test_watchlist_matcher.py`).
- [x] **Step 5: Commit** — `feat(api): filter contracts by type with a closed enum`

### Task B2: Response-model split + server-computed derived fields (§17.1–§17.4)

**Files:**
- Modify: `schemas/contracts.py` (new `CompositionCategory`, `CompositionSummary`, `BlueprintSummary`, `ContractListItemSchema`, `ContractDetailSchema`; `ContractItemSchema` gains 5 optional fields; `ContractListResponse` re-typed), `services/contract_service.py` (derived-field builder + both response constructors + `_has_blueprint_copy_item` offered-only), `api/contracts.py` (detail route builds `ContractDetailSchema`)
- Test: `tests/api/test_contract_filters.py` (region **99999961**), `tests/services/test_contract_service.py`

**Interfaces — Produces (verbatim wire names, binding on PR-C/D):**
- `ContractListItemSchema`: all current `ContractSchema` fields **except `items`**, plus `end_location_name: Optional[str]`, `buyout: Optional[float]`, `days_to_complete: Optional[int]`, `reward_per_volume: Optional[float]`, `last_seen_at: Optional[datetime]`, `is_blueprint_copy_contract: bool`, `primary_label: str`, `composition: Optional[CompositionSummary]`, `blueprint_summary: Optional[BlueprintSummary]`.
- `ContractDetailSchema(ContractListItemSchema)` adds `items: List[ContractItemSchema]`.
- `ContractItemSchema` gains `runs`, `material_efficiency`, `time_efficiency`, `category_id`, `group_id` (all `Optional[int] = None`).
- `CompositionSummary = { categories: List[CompositionCategory], total_item_rows: int, total_volume: Optional[float] }`, `CompositionCategory = { category_id: Optional[int], name: Optional[str], item_row_count: int }`.
- `BlueprintSummary = { runs: Optional[int], material_efficiency: Optional[int], time_efficiency: Optional[int], copy_count: int }`.
- Service builder: `_list_item(contract: Contract, category_names: dict[int, str]) -> ContractListItemSchema` and `_detail_item(...) -> ContractDetailSchema`.

**Binding semantics (from spec — restated so a subagent cannot drift):**
- `is_blueprint_copy_contract` and every composition/blueprint figure count **offered items only** (`is_included = true`, §3.1). This task also adds `ContractItem.is_included.is_(True)` to `_has_blueprint_copy_item()`'s WHERE — the backend predicate is the one that changes (§8), so the served flag and the `is_bpc` filter agree by construction.
- `composition` is non-NULL only when the contract has **two or more offered item rows**; counts are item **rows**, not quantities (Criterion 6.1); categories sorted by `item_row_count` desc then `name` asc; rows with NULL `category_id` aggregate into one `{category_id: null, name: null}` entry sorted last (the client buckets it as "other"). `total_volume` is the contract's own `volume` column — there is no per-item volume in the model, so §17.2's `total_volume` maps to `Contract.volume`, stated here so no implementer invents a per-item sum.
- `blueprint_summary` present iff ≥1 offered BPC; `copy_count > 1` ⇒ the three value fields are `None` (§17.3/§8).
- `primary_label` chain exactly §17.4: (1) `type_name` of the first offered item with `category == "ship"`; (2) first offered item's `type_name`; (3) trimmed non-empty `title`; (4) couriers: `f"Courier to {end_location_name}"` or `"Courier"` when unresolved; (5) `f"Contract {contract_id}"`. ("First" = lowest `record_id`, stated here so two implementers can't order differently.)
- `reward_per_volume = reward / volume`, `None` when either is NULL or `volume == 0` (§9).
- Category display names for composition come from one small SELECT over `EsiTaxonomyCache` (kind='category') per request; a missing name serves `name: null` rather than a fabricated string.

- [x] **Step 1: Failing tests.** In `test_contract_filters.py`, region 99999961 — seed one multi-item mixed contract (offered ship + offered BPC + **requested** module), one single-item contract, one courier; assert:
  - list rows carry **no** `items` key at all (`"items" not in row` — the envelope's `items` is the page, the row must not have one);
  - the mixed contract: `is_blueprint_copy_contract is True`, `primary_label` is the ship's type_name, `composition.total_item_rows == 2` (requested module excluded), `blueprint_summary.copy_count == 1` with the BPC's runs/ME/TE;
  - the courier row: `primary_label == "Courier to <name>"`, `composition is None`;
  - the detail endpoint for the mixed contract still carries full `items` including the requested module, each item exposing `runs`/`category_id` fields;
  - a contract holding **two** offered BPCs serves `blueprint_summary == {"runs": None, "material_efficiency": None, "time_efficiency": None, "copy_count": 2}`.
  In `test_contract_service.py`: extend the existing mixed-bundle partition test's fixture family with a **requested-only BPC** contract and assert it matches `is_bpc=false` (offered-only semantics — the Story 8 disagreement, resolved).
  **As executed:** that mixed-bundle partition test is `test_is_bpc_is_a_contract_level_predicate_on_a_mixed_bundle` in `test_contract_filters.py` (region 99999954), not `test_contract_service.py`; the requested-only BPC (`954003`) was added to its fixture family there. `test_contract_service.py`'s only `items`-reading assertion (`test_filter_by_is_bpc`) moved to `is_blueprint_copy_contract`.
- [x] **Step 2: FAIL.**
- [x] **Step 3: Implement** — schemas first (all new response fields `Optional` per FASTAPI-3 except `is_blueprint_copy_contract`/`primary_label`, which the builder always supplies), then the service builder (explicit keyword construction, no `model_validate` on ORM for the split models), then rewire both `ContractListResponse` constructors, then the detail route. `ContractListResponse` becomes `PaginatedResponse[ContractListItemSchema]` keeping `unknown_system_excluded`. **The detail route needs the category-names lookup too** — composition on the detail response reads the same `EsiTaxonomyCache` SELECT the list path uses; extract it as `_category_names(db) -> dict[int, str]` and call it from both `get_contracts` and the detail handler, or detail composition serves `name: null` for every category and looks broken.
- [x] **Step 4: Green.** Then run the FULL backend suite — this task breaks every test that read `items` off list rows; fix each by moving it to the detail endpoint or the new fields (that migration of assertions is in-scope here, and any test whose meaning evaporates gets flagged in the PR body, never silently deleted).
- [x] **Step 5: Update `tests/test_export_openapi.py:30-33`** envelope assertion (still `{"total","page","size","items","unknown_system_excluded"}` here; B3/B4 extend it).
  **As executed:** the envelope assertion needed no change (it is a subset check and the envelope model keeps its name). Added instead the assertions that make the split visible in the artifact the TS client is generated from: `ContractListItemSchema` has no `items` property and carries all nine new row fields, and `/contracts/{contract_id}` responds with `ContractDetailSchema`, which does.
- [x] **Step 6: Commit** — `feat(api)!: split the contract list row from the detail response and serve derived summaries`
  (The `!` is honest: list rows stop carrying `items` — a breaking wire change, §6.4.)

### Task B3: Grouped segment counts + derived total (decision-log D2; §17.5, Criteria 1.3/1.8)

**Files:**
- Modify: `services/contract_service.py`
- Test: `tests/services/test_contract_service.py`, `tests/api/test_contract_filters.py` (region **99999962**)

**Interfaces — Produces:** envelope field `segment_counts: Dict[str, int]` on `ContractListResponse` (every `ContractType` value as a key, zero-filled); internal `_segment_counts_and_total(db, filters, needs_item_join) -> tuple[dict[str, int], int]`.

**The query shape (binding):** rebuild the query exactly the way `_count_unknown_system_excluded` rebuilds its residual — `select(Contract)`, `outerjoin(ContractItem)` iff `needs_item_join` (computed from the ORIGINAL filters; lifting `contract_type`/`is_ship_contract` cannot change join need since both are contract-level), then `_apply_contract_filters` + `_apply_item_filters` with `filters.model_copy(update={"contract_type": None, "is_ship_contract": None})`; then
```python
grouped = (
    query.with_only_columns(
        Contract.type,
        func.count(func.distinct(Contract.contract_id)),
        func.count(func.distinct(Contract.contract_id)).filter(
            Contract.is_ship_contract.is_(True)
        ),
    )
    .group_by(Contract.type)
)
```
Python then: zero-fills over `ContractType`; **folds any grouped row whose stored `type` string is outside the enum into the `"unknown"` key** (codex round-2 finding 14 — `Contract.type` is an unconstrained string written straight from ESI, and a future ESI type must stay counted and reachable per Criterion 1.1, not silently vanish from the sum — which would also mis-trigger the `total == 0` short-circuit while rows exist); picks per-type counts for `segment_counts` per Criterion 1.8 (while `is_ship_contract=True` is active: item-bearing types use the ships aggregate, item-less types — courier/loan/unknown — use the lifted aggregate; `is_ship_contract=False`: `all - ships` for item-bearing; inactive: the lifted aggregate); derives `total` as the sum over the *selected* types (**all grouped rows including non-enum strings** when no `contract_type` filter) of the aggregate matching the actual `is_ship_contract` filter. The flat `_count_distinct_contracts` call disappears from `get_contracts` (it remains for the residual count). One corpus-scale aggregate per request — same as today, not one more (D2). **DISTINCT is conditional, matching decision-log D2 exactly** (codex finding 15 resolved in D2's favor): `count(DISTINCT contract_id)` when `needs_item_join` is true (the join inflates rows — SQLA-1), plain `count(contract_id)` otherwise (the PK is unique per row and the DISTINCT sort is pure cost on the hot unjoined default path — this is where the perf-audit's drop-the-DISTINCT follow-up is absorbed).

- [x] **Step 1: Failing tests:**
  - **Equivalence property (the load-bearing one):** in `test_contract_service.py`, seed a corpus in two private regions with mixed types, multi-item contracts, ships and non-ships; for each filter combination in a parametrized matrix (`search`, `is_bpc`, `type_ids` joined path, `is_ship_contract` both values, `contract_type` single + multi, price bounds), assert `response.total == await _count_distinct_contracts(db, reference_query)` where `reference_query` is built independently inside the test the pre-B3 way: `select(Contract)` + `outerjoin(ContractItem)` iff `_needs_item_join(filters)` + `_apply_contract_filters(query, filters)` + `_apply_item_filters(query, filters)` with the ORIGINAL (unlifted) filters. Run under **both** `liveness_branch` params (the fixture at `:509` — the watermark fast/fallback branches must agree).
    **As executed:** the corpus sits in `DELISTED_REGION_A`/`DELISTED_REGION_B` (99999911/99999912) rather than newly claimed private regions, because those are the two ids `liveness_branch` writes into `AGGREGATION_REGION_IDS`. Rows in any other region take the correlated fallback under *both* params, which would have made the parametrisation vacuous and left the fast branch with no coverage. `db_session` drops and recreates every table per test function, so sharing the ids with the delisting/system-coverage cases is safe. 13 filter cases × 2 branches; each case asserts its reference count is non-zero first so the equality cannot pass vacuously. One case (`unknown-contract-type`) pins that a `contract_type` selection matches the stored string exactly and does NOT sweep in the non-enum row folded beside it in `segment_counts`.
  - **Zero-fill:** every response's `segment_counts` has exactly the five keys, zeros included (`assert set(data["segment_counts"]) == {"item_exchange","auction","courier","loan","unknown"}` even against an empty region).
  - **Criterion 1.8 (HTTP-level, region 99999962):** seed 2 ship item_exchanges, 1 non-ship item_exchange, 1 courier. With `is_ship_contract=true`: `segment_counts["item_exchange"] == 2` (respects ships-only) but `segment_counts["courier"] == 1` (lifted — not 0). `total == 2`.
    **As executed:** the `is_ship_contract=false` half of the same criterion needed its own HTTP case (`test_an_item_bearing_segment_reports_the_complement_under_ships_excluded`, same fixture): `segment_counts["item_exchange"] == 1`, `courier == 1`, `total == 2`. The equivalence matrix's `ships-excluded` case asserts only `total` and the key set, so nothing pinned the complement aggregate for an item-bearing segment — see the third mutation under Step 4.
  - **Counts respect other filters (§6.2):** with a `min_price` excluding one ship, `segment_counts["item_exchange"]` drops accordingly.
  - **Distinct contracts (Criterion 1.3):** a multi-item contract counts once under a joined-path filter (`search` hitting both its items).
  - **Empty-page threading:** a filter matching nothing still returns full zero-filled `segment_counts` (Global Constraint 18 — both constructors).
    **As executed:** written as `contract_type=loan` against a corpus holding three item exchanges and a courier, so the empty page asserts the five keys *and* non-zero counts beside them. A filter that empties the corpus outright would have let an all-zeros dict pass while the short-circuit dropped the real counts.
  - **Non-enum stored type (finding 14):** seed a row with `type="somenewtype"` (write it via `db_session.add`, which the unconstrained column accepts) → it counts inside `segment_counts["unknown"]`, the unfiltered `total` includes it, and the page shows it — no silent vanishing, no spurious empty short-circuit.
- [x] **Step 2: FAIL** (no `segment_counts` key). 35 failures, all `AttributeError: 'ContractListResponse' object has no attribute 'segment_counts'`.
- [x] **Step 3: Implement** per the binding shape; thread through **both** `ContractListResponse` constructors; `total == 0` short-circuit now keys off the derived total.
- [x] **Step 4: Green; mutation-verify the equivalence test** (snapshot, drop the `FILTER` aggregate so ships counts equal all counts, confirm red, restore, green).
  **As executed:** two mutations, both killed. (1) `FILTER` aggregate replaced by a second plain aggregate → 6 red (`ships-only`, `ships-excluded`, `contract-type-with-ships-only`, both branches). (2) DISTINCT made unconditional-plain → 5 red (`search-joins-items`, `search-with-ships-only`, both branches, plus the HTTP Criterion 1.3 case). Restored from a `cp` snapshot and re-ran green both times. Note `type-ids-joins-items` survives mutation (2): no fixture contract carries two items sharing one `type_id`, so only the `search` cases reach the inflating shape — the corpus's duplication coverage rests on those.
  **Third mutation, initially survived:** making the ships-excluded case report the lifted population for item-bearing segments too (`None if segment in _ITEMLESS_CONTRACT_TYPES or filters.is_ship_contract is False else …`) left all 98 tests green. The implementation was correct; the coverage was not — the derivation's `all - ships` branch had no assertion on any segment VALUE. Closed with the ships-excluded HTTP case in Step 1; re-running the mutation now reddens exactly that test, and the restored file re-runs green.
- [x] **Step 5:** Extend `tests/test_export_openapi.py` envelope assertion with `segment_counts`. (Written as part of the Step 1 red set rather than after green.)
- [x] **Step 6: Commit** — `feat(api): serve per-type segment counts from one grouped statement`

### Task B4: Coverage envelope (decision-log D3; §17.7, Criteria 7.3/7.4)

**Files:**
- Modify: `services/contract_service.py`, `schemas/contracts.py`
- Test: `tests/services/test_contract_service.py`

**Interfaces — Produces:** envelope field `coverage: CoverageInfo` where `CoverageInfo = { ingested_region_ids: List[int], as_of: Optional[datetime] }`; internal `_observed_coverage(db) -> CoverageInfo`.

**The query (binding — a plain `SELECT DISTINCT` measures 602 ms on production; perf audit §4):** a loose index scan over `ix_contracts_region_last_seen`'s leading column via recursive CTE, as `text()` SQL with this comment attached:
```python
# Loose index scan: SELECT DISTINCT over start_location_region_id is a 600ms
# full index scan on the production corpus (perf audit 2026-08-02 §4 — PG18's
# btree skip scan does not engage). The recursive CTE walks one index probe per
# distinct region instead. as_of is the newest ingestion stamp across them.
_OBSERVED_REGIONS_SQL = text("""
    WITH RECURSIVE regions(region_id) AS (
        SELECT min(start_location_region_id) FROM contracts
        UNION ALL
        SELECT (SELECT min(start_location_region_id) FROM contracts
                WHERE start_location_region_id > regions.region_id)
        FROM regions WHERE regions.region_id IS NOT NULL
    )
    SELECT r.region_id,
           (SELECT max(c.last_seen_at) FROM contracts c
             WHERE c.start_location_region_id = r.region_id) AS newest
    FROM regions r WHERE r.region_id IS NOT NULL
""")
```
`ingested_region_ids` = the returned ids sorted ascending; `as_of` = the max of `newest` (None on an empty corpus). Sourced from observed rows, never `Settings.AGGREGATION_REGION_IDS` (Criterion 7.4 — configured-but-not-ingested is exactly the misleading state).

- [x] **Step 1: Failing tests:** seed contracts in two regions → `coverage.ingested_region_ids` equals exactly those two, `as_of` equals the newest `last_seen_at` seeded; empty DB → `ingested_region_ids == []`, `as_of is None`; and the drift case: monkeypatch `AGGREGATION_REGION_IDS` to include a third, empty region → it must NOT appear (that assertion is the criterion).
- [x] **Step 2: FAIL. Step 3: Implement** (both constructors; computed once per request alongside the counts). **Step 4: Green.**
- [x] **Step 5:** Extend the export-openapi envelope assertion with `coverage`.
- [x] **Step 6: Commit** — `feat(api): report observed region coverage on the list envelope`

### Task B5: Functional item-level range filters (runs, ME, TE) as offered-only per-family EXISTS (§3.1, Criteria 2.3/2.5)

**Files:**
- Modify: `services/contract_service.py` (`_apply_item_filters`, `_needs_item_join`), `schemas/contracts.py` (field descriptions), `app/backend/tools/esi_spec_monitor/manifest.py` (`raw_quantity` entry)
- Test: `tests/api/test_contract_filters.py` (regions **99999963** runs, **99999964** ME/TE)

**The shape (binding — SQLA-3):** one correlated EXISTS per filter *family*, all of that family's bounds inside the same EXISTS so they apply to the same item (§3.1 "bounds within a family apply to the same item"; separate families may be satisfied by different items). Factory:
```python
def _offered_item_range_exists(column, minimum, maximum):
    """Contract-level classification: at least one OFFERED item whose `column`
    satisfies every supplied bound (§3.1). One EXISTS per filter family — bounds
    compose per item, not per contract; NULL-valued items (blueprint originals
    omit runs entirely, ESI-3) satisfy nothing."""
    conditions = [
        ContractItem.contract_id == Contract.contract_id,
        ContractItem.is_included.is_(True),
    ]
    if minimum is not None:
        conditions.append(column >= minimum)
    if maximum is not None:
        conditions.append(column <= maximum)
    return (
        select(ContractItem.record_id).where(*conditions).correlate(Contract).exists()
    )
```
`_apply_item_filters` replaces the per-row `raw_quantity` predicates with:
```python
    if filters.min_runs is not None or filters.max_runs is not None:
        query = query.filter(
            _offered_item_range_exists(ContractItem.runs, filters.min_runs, filters.max_runs)
        )
    if filters.min_me is not None or filters.max_me is not None:
        query = query.filter(
            _offered_item_range_exists(
                ContractItem.material_efficiency, filters.min_me, filters.max_me
            )
        )
    if filters.min_te is not None or filters.max_te is not None:
        query = query.filter(
            _offered_item_range_exists(
                ContractItem.time_efficiency, filters.min_te, filters.max_te
            )
        )
```
**`_needs_item_join` drops `min_runs`/`max_runs`** (EXISTS needs no join — the inverse rule its own comment documents). Schema descriptions for all six fields lose their "NO MATCHES"/"NOT IMPLEMENTED — do not expose" warnings and gain the §3.1 semantics one-liner ("matches contracts with at least one offered item satisfying every bound in this family"). Manifest: rewrite the `raw_quantity` `KnownAbsentField` consumer/consequence — it is no longer read by any filter; it is kept-but-unread for the authenticated routes (spec §6.1 point 3); regenerate the snapshot if the monitor output changes.

**Spec-interpretation note (binding; decision-log D8):** §3.1's "the test must assert it lands in exactly one branch" holds for the **boolean** `is_bpc` family, whose false branch is the *negation* of the true branch — negation-derived complements partition by construction. Range families have no negation branch: under §3.1's own existential rule, a contract holding offered items on BOTH sides of complementary bounds (ME 5 and ME 15 against `max_me=9` / `min_me=10`) **legitimately matches both branches** — each bound is satisfied by a different offered item, which is exactly what "at least one offered item satisfies the predicate" means. The mixed-child fixture's discriminating assertions for ranges are therefore: (a) the straddling contract appears in BOTH single-bound branches (pins existential semantics), (b) the **window** test — no single item inside both bounds ⇒ no match (pins §3.1's "bounds within a family apply to the same item", the reading that kills the two-separate-EXISTS misimplementation), and (c) the three-way identity computed with the overlap named explicitly. A naive reading of "exactly one branch" applied to ranges would reject a correct implementation.

- [x] **Step 1: Failing tests** — for EACH family, the §3.1 three-way identity with a mixed-child fixture (template: `test_contract_filters.py:636`, adjusted per the note above). The ME one in full (runs and TE are the same shape over their columns; write all three, no "similar to above"):
  ```python
  async def test_me_filter_is_a_contract_level_predicate_with_a_three_way_identity(
      client, db_session
  ):
      """min_me/max_me classify contracts by their OFFERED items (§3.1). Complementary
      bounds do not two-way partition: NULL-ME items (non-blueprints, originals) fall
      in `neither`. Expected neither count is stated here, not derived: 2 — the
      no-blueprint contract and the requested-only-BPC contract."""
      now = datetime.now(timezone.utc)
      def _c(cid, items):
          return Contract(
              contract_id=cid, title=f"t{cid}", price=1_000_000, collateral=0,
              status="unknown", type="item_exchange", issuer_id=1,
              issuer_corporation_id=1, start_location_id=60003760,
              start_location_region_id=99999964, for_corporation=False,
              date_issued=now, date_expired=now + timedelta(days=7), items=items,
          )
      db_session.add_all([
          # Mixed offered children: ME 5 and ME 15 — must land in exactly one
          # branch per bound, and satisfies NEITHER a min_me=10&max_me=12 range
          # (no single item is inside both bounds).
          _c(964001, [
              ContractItem(record_id=9640011, type_id=621, type_name="BPC lo",
                           quantity=1, is_included=True, is_singleton=True,
                           is_blueprint_copy=True, material_efficiency=5),
              ContractItem(record_id=9640012, type_id=622, type_name="BPC hi",
                           quantity=1, is_included=True, is_singleton=True,
                           is_blueprint_copy=True, material_efficiency=15),
          ]),
          # Single offered BPC at ME 10.
          _c(964002, [ContractItem(record_id=9640021, type_id=623, type_name="BPC mid",
                                   quantity=1, is_included=True, is_singleton=True,
                                   is_blueprint_copy=True, material_efficiency=10)]),
          # No blueprint at all → neither.
          _c(964003, [ContractItem(record_id=9640031, type_id=587, type_name="Tristan",
                                   quantity=1, is_included=True, is_singleton=False,
                                   is_blueprint_copy=None)]),
          # BPC on the REQUESTED side only → neither (offered-only, §3.1/8.1).
          _c(964004, [ContractItem(record_id=9640041, type_id=624, type_name="WTB BPC",
                                   quantity=1, is_included=False, is_singleton=True,
                                   is_blueprint_copy=True, material_efficiency=20)]),
      ])
      await db_session.flush()
      base = "/contracts/?region_ids=99999964"

      low = await client.get(f"{base}&max_me=9")          # branch_a: ME ≤ 9
      high = await client.get(f"{base}&min_me=10")        # branch_b: ME ≥ 10
      unfiltered = await client.get(base)
      low_ids = {c["contract_id"] for c in low.json()["items"]}
      high_ids = {c["contract_id"] for c in high.json()["items"]}
      # The straddler appears in BOTH branches — existential semantics (D8):
      # each bound is satisfied by a different offered item.
      assert low_ids == {964001}
      assert high_ids == {964001, 964002}
      # Three-way identity with the overlap named: |A| + |B| - |A∩B| + neither
      # == unfiltered. neither == 2 as stated in the docstring (964003, 964004).
      overlap = len(low_ids & high_ids)
      assert overlap == 1
      neither = 2
      assert unfiltered.json()["total"] == 4
      assert (
          low.json()["total"] + high.json()["total"] - overlap + neither
          == unfiltered.json()["total"]
      )

      # Range composes per item: no single item sits in [10, 12].
      window = await client.get(f"{base}&min_me=10&max_me=12")
      assert [c["contract_id"] for c in window.json()["items"]] == [964002]
      assert 964001 not in {c["contract_id"] for c in window.json()["items"]}

      # Criterion 2.5's harsher assertion: the filtered count is STRICTLY LESS than
      # unfiltered — the live defect returned the identical count.
      assert high.json()["total"] < unfiltered.json()["total"]
  ```
  Note the mixed contract appears in BOTH single-bound branches (it has an item on each side) — that is correct under §3.1's existential rule; the three-way identity accounts for the overlap explicitly (`-1`). The runs-family test additionally seeds a blueprint **original** (`runs=None`) and asserts it lands in `neither` under both bounds (ESI-3: absence is not zero).
- [x] **Step 2: FAIL** (today: runs reads permanently-NULL `raw_quantity`; ME/TE ignored entirely → identical counts). Observed exactly that: the runs branches came back empty, the ME branches came back with all four fixture contracts.
- [x] **Step 3: Implement** per the binding shape. **Step 4: Green; mutation-verify** the ME test by removing `is_included.is_(True)` from the factory (must go red on 964004 leaking in), restore, green. Run the full filter + service modules. Three mutations run in all, each restored from a `cp` snapshot (TEST-12): (1) drop `is_included.is_(True)` → red, 964004 leaks into the ME high branch; (2) emit one EXISTS per bound instead of one per family → red in all three window assertions, the misimplementation §3.1 exists to forbid; (3) fold the runs bounds into the ME family's EXISTS → red on the independence test. Restored, full suite green.
- [x] **Step 5: Commit** — `fix(api): make the runs, ME, and TE filter families classify contracts by offered items`

**Executed deviations (Task B5):**
- **A fourth test, `test_range_families_are_independent_of_each_other`.** The three named tests pin bounds composing per item WITHIN a family; nothing in them fails if all three families collapse into one EXISTS. The fourth seeds a contract whose ME comes from one copy and whose runs come from another and asserts `min_me=10&min_runs=50` still matches it — mutation 3 above is the proof it is load-bearing.
- **`tests/conftest.py::setup_contracts` repaired, outside the task's Files list.** The fixture set `raw_quantity=10` on contract 102 — TEST-18's own worked example of a fixture column ingestion never writes — so pointing the runs family at `ContractItem.runs` turned `test_filter_by_bpc_runs` red. The value moved to `runs=10`, which `background_aggregation._fetch_item_rows` does assign, converting a test that proved query binding into one that proves the feature. The fixture's WARNING docstring was rewritten accordingly.
- **Two pitfall entries corrected in the same commit** (CLAUDE.md §Development Workflow). FASTAPI-2's "Where It Bit Us" asserted in the present tense that `min_me`/`max_me`/`min_te`/`max_te` are silently ignored — this task makes that false, so it is now past tense with the fix named. TEST-18's `raw_quantity=10` clause gained the same "since fixed" annotation its `start_location_system_id` sibling already carried.
- **The ESI monitor snapshot was re-projected offline, not regenerated with `--update`.** `snapshot.json` embeds the manifest's `known_absent_fields` prose, so the rewritten `raw_quantity` annotation had to reach it; `--update` would have refetched the live spec and silently accepted any real ESI drift since Task A6 took the snapshot, which is exactly what that file's own readme warns against. Instead the two views' `raw_quantity` blocks were rewritten from `MANIFEST` and the file re-serialized through `monitor.serialize`, so the diff is four lines of prose and nothing else. The monitor's findings output is unchanged either way — the diff engine compares field/parameter/status shape, never the consumer annotations.

### Task B6: Taxonomy filters (`category_id`, `group_id`) as one offered-only EXISTS family (Criteria 3.1–3.4)

**Files:** `schemas/contracts.py` (`ContractFilters`), `services/contract_service.py` (`_apply_item_filters`), test `tests/api/test_contract_filters.py` (region **99999965**)

- [x] **Step 1: Failing test:** seed a mixed-child contract (offered Ship-category item + offered Module-category item), a module-only contract, and a requested-only-in-category contract; assert `category_id=<ship>` matches the mixed + not the module-only; `category_id=<ship>&group_id=<frigate>` requires the SAME offered item to satisfy both (a contract whose ship item is group A does not match group B even though another offered item is group B — seed exactly that shape); requested-side items never match; a category with zero matches returns `total == 0` (not an error); the mixed contract appears under a ship-category query AND under a module-category query (existential semantics — a mixed contract legitimately matches both positive filters; there is no negation branch for taxonomy), and repeated `group_id` params combine.
- [x] **Step 2: FAIL. Step 3: Implement:** fields
  ```python
      category_id: Optional[List[int]] = Field(
          default=None, description="Dogma category ids; matches contracts with at least one offered item in any of them."
      )
      group_id: Optional[List[int]] = Field(
          default=None, description="Dogma group ids, scoped within category_id when both are set (same offered item satisfies both)."
      )
  ```
  and in `_apply_item_filters` one EXISTS carrying both `in_()` predicates (single family — a group belongs to a category, so same-item composition is the natural reading and the one the cascading UI produces):
  ```python
      if filters.category_id or filters.group_id:
          conditions = [
              ContractItem.contract_id == Contract.contract_id,
              ContractItem.is_included.is_(True),
          ]
          if filters.category_id:
              conditions.append(ContractItem.category_id.in_(filters.category_id))
          if filters.group_id:
              conditions.append(ContractItem.group_id.in_(filters.group_id))
          query = query.filter(
              select(ContractItem.record_id).where(*conditions).correlate(Contract).exists()
          )
  ```
  (NOT added to `_needs_item_join` — EXISTS shape.)
- [x] **Step 4: Green. Step 5: Commit** — `feat(api): filter contracts by dogma category and group`
  Two mutations run (TEST-12), each restored from a `cp` snapshot, ending on a green full-suite run (638 passed): (1) drop `is_included.is_(True)` → red, the requested-only-frigate contract leaks into every category and group answer; (2) emit one EXISTS per predicate instead of one per family → red on exactly the same-item test, the mixed bundle coming back for `category_id=6&group_id=60` it holds no item satisfying.

**Executed deviations (Task B6):**
- **Region 99999965 claimed** (Global Constraint 23), as the task's Files line assigned. A module-level `taxonomy_corpus` fixture seeds all four contracts once; the fixture docstring names 965001 as the TEST-19 mixed-child parent and the two-EXISTS discriminator, so the next reader does not have to re-derive why it holds a frigate and an afterburner.
- **Step 1's seven assertions were split across four named tests** rather than written as one. Each test is named for the single behavior it constrains (contract-level classification, same-item composition, repeated-param union, absent-category empty page), so a failure names the semantics that broke instead of "the taxonomy test". Both mutations above landed on exactly the intended test, which is the evidence the split is real and not cosmetic.
- **`test_id_list_filters_are_query_params_in_openapi_schema` gained the two new names**, outside the assertions Step 1 enumerated. That test is this module's FASTAPI-1 / TEST-1 guard for precisely this filter class — an ID list bound into the GET *body* works at the service layer and is unreachable over HTTP — and adding two `Optional[List[int]]` params while leaving the guard enumerating only the old five would have left the new ones the one shape it exists to catch.
- **`_needs_item_join`'s trailing comment widened** to name the category/group family alongside `is_bpc` and the ranges. It enumerates the filters deliberately absent from the join and why; leaving it listing three of four families makes it stale by omission the moment the fourth lands.

### Task B7: Taxonomy options endpoint with the coverage signal (decision-log D1; §17.6, Criterion 3.5)

**Files:**
- Create: route in `app/backend/src/fastapi_app/api/contracts.py` (registered **above** `/{contract_id}` — the route-order comment at `:23-26` is why), service fn in `contract_service.py`, schemas `TaxonomyCategory`, `TaxonomyGroup`, `TaxonomyResponse` in `schemas/contracts.py`
- Test: `tests/api/test_contract_filters.py`

**Interfaces — Produces:** `GET /contracts/taxonomy` →
```json
{ "categories": [ { "category_id": 6, "name": "Ship" } ],
  "groups": [ { "group_id": 25, "category_id": 6, "name": "Frigate" } ],
  "coverage": "partial" }
```
Flat, not nested (§17.6 — the client filters groups locally). Lists come from `EsiTaxonomyCache` (kind partition), sorted by name. **`coverage` is the item-surface readiness signal (D1), and it has TWO conditions — both revised per codex round-2 findings 3 and 4 (confirmed):**

1. **Enrichment ratio.** Numerator: live, item-bearing contracts with `item_processing_status = 'COMPLETED'` AND `enrichment_version == ENRICHMENT_VERSION`. Denominator: **ALL live, item-bearing contracts regardless of status** — including `PENDING_ITEMS` and `ENRICHMENT_INCOMPLETE`. (The original COMPLETED-only denominator was a real defect: 1 completed + 99 incomplete measured 1/1 = "complete". Failed and pending rows must drag the ratio — that is what it measures.) "Live" = `still_listed_by_esi()` + unexpired (§7.1's population-mixing warning made executable — delisted rows never re-enrich); "item-bearing" = `type IN (item_exchange, auction)` (couriers/loans/unknown are item-less by construction, Criterion 1.2). Threshold: ratio ≥ **0.99** with denominator > 0.
2. **Name-cache completeness.** Every distinct non-NULL `category_id` present on the items of **live** contracts has a `kind='category'` row in `EsiTaxonomyCache`. (A category-name fetch failure does not block COMPLETED stamping, so the ratio alone can read "complete" while the option list is missing names — the endpoint would gate the surface on itself being broken.) **This condition owns its own query and does NOT reuse ingestion's `_observed_category_ids`** (codex PR-A round, P2-5): that helper is deliberately unscoped (fetching a name for a delisted-only category is a harmless one-time cost), while THIS condition must scope to live contracts — an uncached category present only on delisted rows must not hold the item-level UI hostage. Shape: join `contract_items` to live `contracts` (`still_listed_by_esi()` + unexpired + item-bearing types), distinct `category_id` — the joined population is small enough that the plain distinct is acceptable here; if `EXPLAIN` at corpus scale disagrees, fall back to the loose-scan CTE with the liveness predicate in the inner probes.

`"complete"` iff both conditions hold; `"partial"` otherwise. The signal auto-degrades during any future version bump's resweep and auto-restores — a feature, not an accident (D1).

- [x] **Step 1: Failing tests:** (a) cold cache → `{"categories": [], "groups": [], "coverage": "partial"}` (200, honest, never 500); (b) seeded cache + a corpus fully stamped at the current version → `"complete"`, lists sorted, groups carrying `category_id`; (c) 1 of 200 live item-bearing contracts at the old version (0.995) → `"complete"`; 5 of 100 (0.95) → `"partial"` (the threshold is 0.99 — these numbers are chosen to sit on either side of it); (d) **50 COMPLETED-current + 50 ENRICHMENT_INCOMPLETE live contracts → `"partial"`** (the finding-3 regression case: the incomplete rows are IN the denominator); (e) a delisted old-version contract (stale `last_seen_at` in a region with a newer watermark) does NOT drag the ratio; (f) couriers/loans do not count in the denominator; (g) **ratio at 1.0 but one live item's `category_id` has no cache row → `"partial"`** (the finding-4 case); add the missing cache row → `"complete"`.
- [x] **Step 2: FAIL** — all nine items 422, the route-order failure exactly: with no `/taxonomy` route registered, `/{contract_id}` captured the path and tried to parse `"taxonomy"` as an integer.
- [x] **Step 3: Implement** (ratio via one aggregate query: `count(*) FILTER (WHERE item_processing_status = 'COMPLETED' AND enrichment_version = :v)` over the live item-bearing population; import `ENRICHMENT_VERSION` from the service module — one authority). **Step 4: Green. Step 5: Commit** — `feat(api): serve the taxonomy option list with an observed readiness signal`
  Nine mutations run (TEST-12), each restored from a `cp` snapshot, ending on a green full-suite run (647 passed): COMPLETED-only denominator, liveness dropped from the population, item-bearing type predicate dropped, name-cache condition dropped, name-cache condition unscoped from liveness, threshold lowered to 0.90, groups stop carrying `parent_category_id`, and each of the two name sorts replaced by a constant key. All nine red.

**Executed deviations (Task B7):**
- **Region 99999971 claimed** (Global Constraint 23); the task's Files line assigned none. The endpoint takes no filters, so unlike every other block in `test_contract_filters.py` its population is the whole table — the tests seed their own corpus and deliberately do not use `setup_contracts`, relying on `db_session` recreating every table per function. The region id still matters because the per-region delisting watermark needs somewhere private to work.
- **One test past the seven Step 1 enumerated:** `test_a_category_seen_only_on_delisted_rows_does_not_hold_the_signal`. The step's list covers the two conditions and the ratio's population but never the *name* condition's population, which is the whole point of it owning its own query rather than reusing ingestion's unscoped `_observed_category_ids` — a category present only on bought-or-withdrawn rows must not hold the item-level surface shut. Mutation-verified: unscoping the category sweep from liveness turns it red. The item-bearing-types test also makes a second request with an auction knocked back a version, since the enumerated fixture only proves couriers and loans are *out* and nothing proves auctions are *in*.
- **`coverage` is typed as a `TaxonomyCoverage` str-enum, not a bare `str`.** The wire values are the two §17.6 names verbatim; the enum is what makes the regenerated TypeScript a `"partial" | "complete"` union instead of `string`, so PR-D's gate cannot compare against a typo the compiler would have caught. Same reasoning as §17.8's `contract_type`.
- **The name sort runs in Python, not `ORDER BY`.** A database-side sort orders by the server's collation, so the option list a client renders would change with the deployment's `lc_collate`; the lists are a few dozen categories and ~1,500 groups, so the cost is nil.
- **Mutation caught a vacuous fixture of my own before commit** (recorded because it is the TEST-12 lesson repeating): the sort assertion originally seeded the categories already in name order, so replacing the sort key with a constant left the served order unchanged and the mutation survived. Both lists are now seeded in exactly reverse name order, and both sorts are separately mutation-killed.

### Task B8: New sortable fields (`reward_per_volume`, `days_to_complete`, `buyout`) (§6.2, Criterion 5.4, §11's five-touchpoint rule)

**Files:** `schemas/contracts.py` (`SortableContractFields`), `services/contract_service.py` (`SORT_MAP` + null ordering), test `tests/api/test_contract_filters.py` (region **99999966**)

- [x] **Step 1: Failing tests — one per field, asc AND desc, distinct-value fixtures (TEST-3):** the fixture must give EACH sort a population with ≥3 distinct non-NULL values **on rows the production writer would actually give that value** (codex round-2 finding 11 — buyout is auction-only, so couriers cannot carry it without violating TEST-18): seed **three auctions with distinct `buyout` values plus one auction without** (the null case), and **three couriers with distinct reward/volume ratios and distinct `days_to_complete`** plus one courier with `volume=0` (guard case) and one item_exchange (`reward` NULL). For each of the three new sorts assert ascending and descending produce different first rows, the expected exact order, and that NULL-valued rows sort LAST in both directions (a null `reward_per_volume` row must not occupy the "best value" end — the §15.2 display rule applied to the one ratio this feature ships). Also: `volume=0` yields `reward_per_volume: null` on the wire, not infinity/error (§9), and one sort test runs with `search` set so the grouped joined path exercises the aggregate (SQLA-1).
- [x] **Step 2: FAIL** — all five tests 422, the enum rejecting the three values exactly as predicted.
- [x] **Step 3: Implement:** enum members `reward_per_volume`, `days_to_complete`, `buyout`; SORT_MAP entries:
  ```python
      SortableContractFields.buyout: Contract.buyout,
      SortableContractFields.days_to_complete: Contract.days_to_complete,
      # Computed ratio; NULL when reward is NULL or volume is NULL/0 (spec §9).
      SortableContractFields.reward_per_volume: Contract.reward / func.nullif(Contract.volume, 0.0),
  ```
  Null ordering: in both fetch paths, when the resolved sort column is one of the three new (nullable) entries, append `.nulls_last()` to the order expression (`order_expr = order_expr.nulls_last()`), leaving the existing four sorts byte-identical (they are non-null columns; changing their plans without cause is scope creep). The grouped path's aggregate (`func.max`/`min` over the expression) already tolerates expressions.
- [x] **Step 4: Green** (652 passed, flake8 clean). Note the five-touchpoint rule: touchpoints 1–2 (SORT_MAP, enum) here; 3 (`SavedSearchParameters.sort_by`) widens automatically via the shared enum — B9's tests cover it; 4–5 (frontend `SORT_FIELDS`, regenerated types) are PR-C Task C2.
  Seven mutations run (TEST-12), each restored from a `cp` snapshot and ending on a green restore run: `nulls_last` dropped from the simple path (3 red) and from the joined path (1 red), the ratio replaced by the raw reward, by the raw volume, and by an unguarded `reward / volume` (division by zero), and each of the `buyout` / `days_to_complete` map entries repointed at `Contract.price`. All seven red, no survivors.
- [x] **Step 5: Commit** — `feat(api): sort by reward per volume, delivery window, and buyout`

**Executed deviations (Task B8):**
- **The `volume=0` guard courier also carries a `days_to_complete`,** giving that sort four distinct non-NULL values rather than the three Step 1's phrasing implies. ESI sends a delivery window on every courier, so a courier without one is not a row the writer can produce (TEST-18); leaving it NULL to keep the count at three would have bought a rounder fixture with a shape that does not exist.
- **The plan's "existing four sorts" is six.** `SORT_MAP` held `date_issued`, `date_expired`, `price`, `collateral`, `volume`, and `ship_name` before this task — the parenthetical "(they are non-null columns)" is true of four of them and false of `volume` (`models/contracts.py`, `nullable=True`) and of `ship_name` (`ContractItem.type_name`). All six are left byte-identical as the step directs, so the instruction stands; only its count and its stated reason were off. The consequence is recorded under Discoveries rather than fixed here.

### Task B9: `SavedSearchParameters` widening (decision-log D4; spec §14)

**Files:** `schemas/account.py`, tests `tests/api/test_account_schemas.py`, `tests/api/test_saved_searches.py`

- [x] **Step 1: Failing tests first, as edits to the pins:** replace the two `min_me` 422 cases (`test_saved_searches.py:125`, `test_account_schemas.py:57`) with a still-rejected key (`{"min_me_typo": 5}`-style junk) AND add acceptance cases: a blob carrying `contract_type=["courier"]`, `category_id=[6]`, `group_id=[25]`, `min_runs=1`, `min_me=10`, `max_te=20` validates and round-trips. Keep the `page` and `is_ship_contract` rejection pins (`test_account_schemas.py:58-59`) — both stay rejected. `test_saved_searches.py:168` (`additionalProperties is False`) stays green because `extra="forbid"` stays.
- [x] **Step 2: Run — the acceptance cases FAIL** (extra=forbid rejects them today).
- [x] **Step 3: Implement:** add to `SavedSearchParameters`, bounds copied from `ContractFilters` exactly:
  ```python
      contract_type: Optional[List[ContractType]] = Field(default=None)
      category_id: Optional[List[PositiveInt]] = Field(default=None)
      group_id: Optional[List[PositiveInt]] = Field(default=None)
      min_runs: Optional[int] = Field(default=None, ge=-1)
      max_runs: Optional[int] = Field(default=None, ge=-1)
      min_me: Optional[int] = Field(default=None, ge=0)
      max_me: Optional[int] = Field(default=None, ge=0)
      min_te: Optional[int] = Field(default=None, ge=0)
      max_te: Optional[int] = Field(default=None, ge=0)
  ```
  Rewrite the docstring: it no longer rejects ME/TE (they are functional as of F008); it still rejects `page`, the wire-only `is_ship_contract`, and junk.
- [x] **Step 4: Green** (all three saved-search test modules). **Step 5: Commit** — `feat(api): let saved searches hold the type, taxonomy, and blueprint filters`

### Task B10: PII log fix + regeneration + phase gate

**Files:** `services/contract_service.py` (4 sites), `app/frontend/web/openapi.json` + `src/lib/api/schema.d.ts` (regenerated), tests

- [x] **Step 1: Failing test:** in `test_contract_service.py`, following the `log_key_event`-monkeypatch idiom (`:178`/`:268`): perform a search with `filters.search="Tristan sale"`; capture ALL log calls (including the plain `logger.info` start log — monkeypatch `contract_service.logger` too); assert no captured `search_terms` dict contains the literal string, and each carries `search_len: 12` instead.
- [x] **Step 2: FAIL. Step 3: Implement:** in all FOUR `search_terms` dicts (`:373` start `logger.info`, `:421` zero-result, `:468` success, `:492` failure — the first is NOT a `log_key_event`; a task scoped to those would miss it), replace `"search": filters.search` with `"search_len": len(filters.search) if filters.search else 0`. Reconcile `tests/api/test_observability.py:42/:58` if the key change surfaces there. Also add the new filter dimensions to the two full-dimension sites (`contract_type`, `category_id`, `group_id` — dimensions only, §4.1).
- [~] **Step 4 (backend half done):** `pdm run export-openapi` && `npm run generate:api`; commit both artifacts. Full backend suite + lint green, **AND all five frontend lanes green (eslint, tsc, vitest, future-clock, Playwright fixture e2e)** — PR-B carries Tasks C1/C2's frontend adaptation, so its CI runs the frontend job and the gate must prove it locally first.

**Task B10 notes (Steps 1-4).** Three commits: `326652c` (the fix), `6eb0b9c` (the regeneration), and the follow-up below that closes the residual `326652c` left open.

- **The scrub was half-closed, and its own test could not see it.** `326652c` redacted all four `search_terms` payloads and its message claimed the search text "is treated as PII and never lands in a log line" — but the failure site passed `error_message=str(e)` in the SAME record. The exception a contract search realistically fails with is a SQLAlchemy `StatementError` (statement timeout, dropped connection, deadlock), whose `str()` appends `[parameters: {...}]`, and the failing statement is the one carrying the `ILIKE '%<search text>%'` bind — so `error_message` re-published exactly what `search_terms` withheld one key earlier. The shipped test was structurally blind to it: it injected `RuntimeError("simulated db failure")`, whose `str()` is parameter-free. Two production changes close it: `hide_parameters=True` on the application engine (`db.py`), which stops SQLAlchemy rendering bind values into any error it raises — covering `main.py`'s `generic_exception_handler`, which logs both `str(exc)` and the traceback, not just this service — and `_error_without_bound_parameters` at the log site, which holds the guarantee for an exception arriving from a session built elsewhere. Rationale and the rejected alternatives are in the decision log; the trap is now pitfalls SQLA-4 (implementation) + TEST-21 (testing).
- **Testing the engine flag without a reachable engine.** The suite runs against `DATABASE_URL_TESTS`; this worktree's `DATABASE_URL` carries placeholder credentials, so a real round-trip through `async_engine` is not available to drive an error end-to-end. `tests/test_db_engine.py` instead renders a `StatementError` with the flag the engine actually carries — the same value SQLAlchemy hands `DBAPIError.instance()` in `engine/base.py::_handle_dbapi_exception` — so the assertion is on the consequence, not on the constructor kwarg. Mutation-verified: removing `hide_parameters=True` turns it red.
- **The service-level test drives a real `StatementError`.** `test_a_failing_statement_does_not_log_its_bound_search_text` injects one carrying `%Tristan sale%` as a bind, guards against vacuity by first asserting the unscrubbed rendering *does* leak, then asserts against the whole captured record. `test_no_search_log_site_echoes_the_raw_query_text` was widened the same way — it scanned only `search_terms` before, which is what let a sibling key escape it.

- **A second test beyond Step 1's** (summarized in the top-of-plan Deviations subsection). Step 1 pins only the PII invariant, but Step 3 also *adds* three keys to the two full-dimension payloads, which is production behavior with no test behind it. `test_full_dimension_logs_carry_the_type_and_taxonomy_filters` pins the exact eleven-key set and the rendered values; stripping the new keys from either site individually turns it red. It stamps taxonomy onto contract 101's Tristan item rather than claiming a private region — the fixture writes no `category_id`/`group_id`, and one UPDATE inside the test is cheaper than a region's worth of seed.
- **Recording the logger, not `log_key_event`.** The `:178`/`:268` idiom monkeypatches `log_key_event`, which cannot see the start log. `log_key_event` renders through `logger.info`/`logger.error`, so recording `contract_service.logger` alone catches all four sites — the two idioms are not additive and only the second is used in the new tests. Factored into `_record_search_logs`.
- **`test_observability.py` needed no reconciliation.** Its `:42`/`:58` region builds a record dict and scans for `contract_search_executed`; it never reads `search_terms`, so the key rename does not surface there (verified by grep: `search_terms` appears in no test module but `test_contract_service.py`).
- **Two pre-existing tests reconciled.** `test_zero_results_returns_empty_page` and `test_db_error_logs_failure_and_reraises` pinned the old `search` key by name; both now pin `search_len`. The zero-result docstring's count of the full-dimension payload rises from eight keys to eleven.
- **Step 4's frontend half is deliberately NOT done here.** The regeneration deletes `ContractSchema`, which `client.ts` still aliases, so `npx tsc -b` cannot pass until Task C2 lands. Backend suite (666 passed) and `flake8` are green; the five frontend lanes are C2's gate, and Step 5 must not run before they are.

- [ ] **Step 5:** Three review rounds (lenses: §17 field-name conformance byte-for-byte; FASTAPI-3 optionality chain over every new field; the two-constructor/residual-sync traps 18–19), codex PR review (backgrounded), address, decision-log any judgment calls, merge PR-B per protocol.
- [x] **Step 6: Commit** (fix itself) — `fix(api): log search dimensions without the raw query text`

---

# Phase C — Frontend contract-level surface (PR boundaries revised per codex round-2 finding 1)

**Execution Status:** ⬜ NOT STARTED

**PR-boundary correction (codex round 2, finding 1 — confirmed):** PR-B's regenerated `schema.d.ts` deletes `ContractSchema`, which `client.ts:5` references — frontend CI (`npx tsc -b`) runs on PR-B because it commits frontend-path generated files, so **PR-B as originally split cannot go green**. Therefore **Tasks C1 and C2 execute on the PR-B branch** (C1 as an early commit on old types, C2 alongside the regeneration) and merge with PR-B; the B10 gate covers them. Tasks C3–C6 remain PR-C (`feat/f008-contract-surface`, `Routine`), rebased after PR-B merges. Task numbering is unchanged so cross-references and the coverage matrix stay valid.

### Task C1: Extract per-column cell renderers into their own module (single-writer; pure refactor, zero behavior change) — **executes on the PR-B branch**

**Files:**
- Create: `app/frontend/web/src/features/contracts/columns.tsx` — **the spec requires column definitions to move into their own module, not merely into an array inside the component** (spec §7 Render: "Column definitions move into their own module rather than living inside `ContractTable.tsx`"; codex round-2 finding 12). The `Column` interface, `RowContext`, and the default column set live here; per-segment sets (Task C4) are added here later.
- Modify: `app/frontend/web/src/features/contracts/components/ContractTable.tsx` (imports the definitions; keeps the frame, thead logic, and skeleton)
- Test: existing suites are the harness — `sorting.spec.ts` (asserts header names + single `aria-sort`), `pages.test.tsx`, `a11y.test.tsx` must pass unchanged.

**Binding shape (spec §7 "the body must be restructured into per-column cell renderers"):**
```tsx
interface Column {
  key: string
  label: string
  sortField?: SortField
  align?: 'right'
  /** ONE class list for both <th> and <td> — the current code duplicates
      max-lg:hidden / max-sm:hidden across header and cell and they can drift. */
  hiddenClass?: string
  cell: (contract: Contract, ctx: RowContext) => ReactNode
}
interface RowContext { expiry: string }   // computed once per row, used by two renderers today
```
The six existing columns move into renderers with their exact current JSX (link + "+N more" suffix; badges; ISK; truncated location; expiry with `text-warn`; issued date). `<thead>` keeps its current sort/aria logic; `<tbody>` maps `COLUMNS.map(c => <td className={...}>{c.cell(contract, ctx)}</td>)`. `ContractTableSkeleton`'s `aria-label="Loading contracts"` is load-bearing for e2e — do not rename.

- [x] **Step 1:** Refactor; `COLUMNS` becomes the single source for header AND cell.
- [x] **Step 2:** `npm run test` + `npm run test:future-clock` + `npx tsc -b` + `npx eslint .` + `npm run e2e` — ALL green with **zero spec edits** (that is the proof it was a pure refactor).
- [x] **Step 3: Commit** — `refactor(web): drive contract table cells from the column definitions`

### Task C2: Adopt the new wire shape (rename + derived fields + fixtures) — **executes on the PR-B branch, same commit series as the regeneration**

**Files:**
- Modify: `src/lib/api/client.ts` (type aliases), `src/features/contracts/format.ts` (delete `primaryLabel`), `ContractTable.tsx`, `ContractDetailPage.tsx`, `src/features/contracts/filters.ts` (SORT_FIELDS + new params), `e2e/fixtures/contracts.ts` (wire mirrors), every test touching list-row `items`
- Test: `pages.test.tsx`, `filters.test.ts`, `format.test.ts`, e2e fixture lane

**The moves (each mechanical, all in one task because they only compile together):**
1. `Contract = components['schemas']['ContractListItemSchema']`; add `ContractDetail = components['schemas']['ContractDetailSchema']`; `PaginatedContracts` unchanged name.
2. Delete `format.ts::primaryLabel`; the four call sites read `contract.primary_label` (the detail page calls it twice — `:110` heading and `:119` title-differs comparison; replace both).
3. `contractIsBpc` (`ContractTable.tsx:35-37`) and the detail page's independent copy (`ContractDetailPage.tsx:100`) both become reads of `is_blueprint_copy_contract`.
4. The "+N more" suffix reads `composition` (`composition && composition.total_item_rows > 1 → +{total_item_rows - 1} more`); list rows have no `items`.
5. `SORT_FIELDS` gains `'reward_per_volume', 'days_to_complete', 'buyout'` (mirror of the widened enum — the duplicated-list touchpoint §11 names).
6. `ContractSearch`/`parseContractSearch`/`toApiQuery` gain `contract_type?: ContractTypeValue[]` (an `as const` list + `.includes()` guard, the closed-enum client mirror), `category_id?: number[]`, `group_id?: number[]` (both via `toIdArray`), and `min_runs/max_runs/min_me/max_me/min_te/max_te?: number` — **all six via `toNonNegativeNumber`**: the backend allows `min_runs=-1` (a documented ESI sentinel that never occurs on public data), but the UI never produces negatives, so URL junk below 0 falls back to undefined exactly like the price bounds. Wire-through in `toApiQuery` is pass-through (no renames beyond the existing `ships_only`→`is_ship_contract`).

   **Item-less-segment normalization lives HERE, in `parseContractSearch` (codex round-2 finding 10 — confirmed):** when `contract_type` is non-empty and EVERY entry is item-less (`courier`/`loan`/`unknown` — export an `ITEM_LESS_TYPES` const beside the type list), the parsed `ships_only` is forced `false` regardless of the raw value. Putting the rule in the pure parser means deep links (`?contract_type=loan`), saved-search `apply()`, and in-app navigation all inherit Criterion 1.7 — without it, a shared loan URL defaults `ships_only` on and requests a guaranteed-empty combination. A mixed selection (`item_exchange,courier`) is NOT normalized — the item-bearing member can match, so the combination is not guaranteed-empty. `filters.test.ts` cases: `?contract_type=loan` parses with `ships_only: false`; `?contract_type=courier&ships_only=true` likewise; mixed selection leaves `ships_only` alone; and a `toApiQuery` case asserting no `is_ship_contract` is emitted for the normalized parse.
7. `e2e/fixtures/contracts.ts`: `WireContract` loses `items` and gains `end_location_name`, `buyout`, `days_to_complete`, `reward_per_volume`, `last_seen_at`, `is_blueprint_copy_contract`, `primary_label`, `composition`, `blueprint_summary`; `type` union gains `'loan' | 'unknown'`; `WirePage` gains `segment_counts` (all five keys) and `coverage`; `WireContractDetail` (new) carries `items` for detail intercepts; builders updated so every existing dataset compiles with honest values (`primary_label` derived in the builder from the same inputs it previously buried in items). Add canned `AUCTION_CONTRACTS` and `COURIER_CONTRACTS` datasets (distinct sortable values, TEST-3).
- [x] **Step 1:** Make the changes test-first where behavior exists (`filters.test.ts` cases for each new param's parse/serialize junk-tolerance; `pages.test.tsx` fixtures to the new shape) — then chase the compiler (`npx tsc -b`) to every remaining consumer.
- [x] **Step 2:** All four verification lanes green + e2e fixture lane green.
- [x] **Step 3: Commit** — `feat(web): adopt the split list-row contract and server-computed labels`

### Task C3: Contract-type segmentation UI (Criteria 1.3–1.9)

**Files:**
- Create: `src/features/contracts/components/SegmentTabs.tsx`
- Modify: `ContractsPage.tsx` (mount + heading/title logic), `filters.ts` (already has the param from C2), `FilterRail.tsx` (`hasActiveFilters` + `resetFilters` note), tests + `e2e/segments.spec.ts` (new)

**Binding behavior:**
- Four controls: **All** (no `contract_type` filter), **Item exchange**, **Auction**, **Courier** — `loan`/`unknown` get no control but stay URL-reachable and counted (Criterion 1.1). Rendered as a `radiogroup`-semantics toolbar (`role="tablist"` is for tab panels; use a `<fieldset>` of toggle buttons with `aria-pressed`, matching the codebase's no-ARIA-authoring preference) — keyboard reachable, selected state exposed (Criterion 12).
- Each control shows its count from `segment_counts`. **The All count is NOT the sum of the five** (codex round-2 finding 9 — confirmed): while ships-only is in effect (which it is whenever All is the destination, per Criterion 1.9's restore), the item-less segments contribute **zero** to what All actually shows, but their `segment_counts` entries are deliberately lifted (Criterion 1.8) — summing them overstates All. Export `ITEM_BEARING_TYPES = ['item_exchange', 'auction']` beside `ITEM_LESS_TYPES`; All's count = sum over `ITEM_BEARING_TYPES` when the destination state has ships-only on (the default), sum over all five when the current URL carries `ships_only=false` with an item-bearing or empty segment selection. Per-segment counts come straight off `segment_counts` — the client must NOT otherwise adjust them.
- Selecting **Courier** (or arriving at a `loan`/`unknown` URL) with ships-only active: the patch sets `contract_type: ['courier']` AND `ships_only: false` in one navigation — visibly, the Ships-only checkbox unchecks (Criterion 1.7: the combination must be unreachable, and clearing is visible not silent).
- Leaving an item-less segment for All/Item exchange/Auction restores the default: the patch sets `ships_only: undefined` — REMOVING the key, because `parseContractSearch` reads absence as true and "cleared" is stored as explicit `false` (Criterion 1.9; recon: `update()` spreads `prev`, so restoring requires an explicit `undefined` in the patch, which TanStack Router drops from the URL).
- The courier count reads its true total while ships-only is active because the server lifted it (Criterion 1.8) — the spec's `Courier (0)`-flips-to-`Courier (115)` defect is the thing the e2e spec pins.
- Heading/title logic gains the third axis: segment label wins over the ships-only pair when a segment is active (`'Courier Contracts'` etc.); `default-view.spec.ts`'s two assertions stay green because the default state is unchanged.
- [x] **Step 1: Component tests first** (`pages.test.tsx` style, via `renderApp` + captured fetch calls): selecting Courier issues a request with `contract_type=courier` and NO `is_ship_contract`; the URL shows `ships_only=false`; returning to All removes both params; counts render from the fixture's `segment_counts` (incl. the All-count arithmetic from the binding behavior above — both ships-only states); **loan-by-URL (`renderApp('/contracts?contract_type=loan')`) renders rows, shows no fifth tab, and — assert the captured request params — sends `contract_type=loan` WITHOUT `is_ship_contract`** (the finding-10 normalization observed at the wire, not just in the parser unit test).
- [x] **Step 2: e2e `segments.spec.ts`** (fixture lane, both projects): the wire assertions (TEST-5 — assert the captured `params`), the 1.7/1.9 checkbox choreography, count labels, URL shareability (deep-load `/contracts?contract_type=courier&ships_only=false` restores the segment).
- [x] **Step 3:** Implement; all lanes green; extend `a11y.test.tsx` with a segments-active axe case.
- [x] **Step 4:** Update `filters.spec.ts:176-185`'s clear-filters URL enumeration with the new params (Global Constraint 24).
- [x] **Step 5: Commit** — `feat(web): segment the contract list by type with honest counts`

**Task C3 deviations (details in the top-of-plan Deviations list):** the ships-only restore writes `ships_only=true` into the URL rather than omitting the parameter (`validateSearch` re-derives the default); array params serialize as TanStack Router's JSON form; the Criterion-1.7 clearing in the patch is unobservable because `parseContractSearch` already enforces it; and five peripheral test files plus `src/test/http.ts` were repaired because their contract-list stubs predate the envelope.

### Task C4: Per-segment column sets — auction and courier rows (Criteria 4.2/4.3, 5.3/5.4/5.6/5.7, §8 axes)

**Files:** `ContractTable.tsx` (column sets), `format.ts` (a `formatRewardPerVolume` helper), `ContractsPage.tsx` (passes the active segment), tests + `e2e/segments.spec.ts` extensions

**Binding column sets (axis 1 selects columns; §8):**
- **All / Item exchange** (default, unchanged): Ship/Contract · Type · Price · Location · Time left · Issued.
- **Auction:** Ship/Contract · Starting bid (`price`) · **Buyout** (`buyout`, sortable; `—`-distinct copy `"No buyout"` when null — Criterion 4.3, textual not blank) · Location · Time left · Issued.
- **Courier:** Contract (primary_label) · **Route** (`start_location_name → end_location_name`; an unresolved endpoint renders the literal text `Unknown structure` — never blank, never the raw id, never a fabricated name; §8) · **Reward** · **Collateral** · **Volume** · **Reward/m³** (`reward_per_volume`, sortable; null renders `—`) · **Deadline** (`days_to_complete` as `Nd`; null renders `—`) · Time left.
- No distance figure of any kind on courier rows (§8 — reward/m³ is the only normalization; nothing may read as near/far).
- The courier segment shows the coverage statement (Criterion 5.7): a one-line note above the table sourced from the envelope — see C5.
- [x] **Step 1: Component tests first:** auction fixture with and without buyout (exact cell text incl. `"No buyout"`); courier fixture with an unresolved destination asserting `Unknown structure`; reward/m³ formatted; sort toggles on Buyout and Reward/m³ navigate with the right `sort_by`.
- [x] **Step 2:** Implement as additional `Column[]` sets selected by the active segment; the frame component stays one (spec §8 "shared frame").
- [x] **Step 3:** All lanes green incl. future-clock; extend the sorting spec for one new sortable column (header rename hazard: `sorting.spec.ts` enumerates header names — extend, don't repurpose).
- [x] **Step 4: Commit** — `feat(web): type-aware column sets for auction and courier segments`

**Task C4 deviations (summarized in the top-of-plan Deviations list):**

1. **The column sets live in `columns.tsx`, not `ContractTable.tsx`.** The Files list above predates Task C1's deviation, which moved the definitions into their own module; C1's own Files note already directs the per-segment sets here. `ContractTable.tsx` changed only to take the active set as a `columns` prop — the frame, the `<thead>` sort/aria logic, and the skeleton are untouched. Two files outside the Files list changed as a consequence: one `activeSegment` helper decides both the heading and the columns rather than two copies of "the one type in effect" (it lives in `filters.ts` — see deviation 8); and the six existing columns became named constants (`NAME_COLUMN`, `LOCATION_COLUMN`, …) so the auction and courier sets can share them by reference instead of by copy.
2. **Two format helpers beyond the named `formatRewardPerVolume`.** `routeLabel` and `formatDeadline` also went into `format.ts` with literal-vs-literal unit tests, because each carries a rule a rendered-row assertion states only weakly: `routeLabel` must specifically NOT be `locationLabel` (whose id fallback would put `Location 60003760` in a route, spec §8's "not an ID"), and `formatDeadline` must distinguish an absent `days_to_complete` from a stored `0` (ESI-3). Both are mutation-verified.
3. **Reward, Collateral, Volume and Deadline are NOT sortable, though `collateral`, `volume` and `days_to_complete` are all server sort fields.** The binding text marks only Buyout and Reward/m³ sortable and Step 1 names only those two toggles, so that is what shipped; `?sort_by=days_to_complete` stays reachable by URL and by a saved search. **This leaves the courier segment showing a Deadline column with no way to sort it** — worth a decision in Task C6 or Phase D, since `days_to_complete` was added to the sortable enum in Task B8 specifically for hauling.
4. **The courier `Contract` column drops the `ship_name` sort** the shared name column carries. Couriers have no items, so that sort orders on a NULL `ContractItem.type_name` for every row in the segment — the pre-existing NULL-placement inconsistency the Discoveries subsection flags, which offering the toggle here would put in front of the reader.
5. **Responsive hiding was chosen, not specified — and Criterion 5.3's Deadline is exempt from it.** Eight columns do not fit a 412px viewport, so the courier set hides Collateral and Volume below `lg`; both are recoverable on the detail page. Deadline is NOT hidden: `days_to_complete` is rendered nowhere else in the app, so a breakpoint that drops the column drops a mandated field with no fallback. It first shipped hidden below `sm` and was fixed in review — measured at 412px, the courier columns total 777px against a 378px container, so the row already scrolls horizontally inside its own wrapper (the page does not) and Deadline's 85px was buying nothing. The auction set inherits the default set's Location (`max-lg`) and Issued (`max-sm`) rules unchanged. The e2e assertions consequently assert *visibility* only of columns present at every breakpoint (Route, Reward, Reward/m³, Deadline, Buyout, Starting bid) — the full ordered column set is pinned in the component lane, where jsdom applies no media queries.
6. **A test past Step 1's list:** `keeps the default column set for All and for item exchange`. Step 1 names only the auction and courier cases; with no pin on the unchanged set, a `columnsFor` that returned the auction columns for every segment would leave every auction assertion passing. It also covers the loan/unknown fallthrough by construction, since those share the default return.
7. **The Type column leaves the auction set.** Not stated either way in the binding list, which names six auction columns and does not include Type. Every row in the segment is an auction, so the badge would repeat the segment control back at the reader; the BPC badge it also carries is Phase D's (Task D4) column work, not something this task may add.
8. **The active segment is carried by the query result, not read from the URL — new pitfall WEB-1.** `columnsFor(activeSegment(search))` on the live URL was correct while the column set was segment-invariant and false the moment this task made it vary: `useContracts` sets `placeholderData: keepPreviousData`, so during a segment switch the header flipped instantly and the previous segment's rows stayed under it — an item-exchange row rendering its price as a 0 ISK hauling reward and its hull volume as cargo, under a fabricated `Unknown structure` destination (the wording spec §8 reserves for a genuine unresolvable courier endpoint). `useContracts` now derives the segment inside its query function, where the cache key already fixes it, and `ContractsPage` reads `data.segment`; `activeSegment` moved from `SegmentTabs.tsx` to `filters.ts` so the hook does not import a component module. The segment control keeps reading the live URL for its pressed state and heading — a click must answer immediately; only the *description of the rows* follows the rows. Covered by a component test that holds the courier response open across the switch; recorded as implementation-pitfalls WEB-1 (§6), which Phase D's per-segment work is subject to.

### Task C5: Freshness + coverage-honest empty states (Criteria 7.1–7.4, 5.7)

**Files:** `ContractsPage.tsx`, `ContractDetailPage.tsx`, a small `coverageLabel` helper in `format.ts`, `regions.ts` consumers, tests

- **`last_seen_at` surfacing (7.1):** the list header area (next to the results count live region) renders `Data as of {timeAgo-style relative}` from the envelope's `coverage.as_of`; the detail page renders `Last seen {relative}` from the row's `last_seen_at`. Relative rendering uses a `now`-injectable formatter (TEST-3/17 — literal-vs-literal in unit tests, clock-anchored fixtures).
- **Uncovered-region empty state (7.2/7.3):** when a `region_ids` filter includes ids NOT in `coverage.ingested_region_ids` and the result is empty, the empty state says which selected regions are not ingested (names joined from the static `regions.ts` map — it is a flat array; build a `Map` once) and distinguishes "not covered" from "nothing matched". The existing loosen-your-filters copy remains for genuinely-covered empties. `states.spec.ts:99` asserts the old copy EXACTLY — extend that spec for the new branch rather than editing the old assertion.
- **Courier coverage line (5.7):** `Couriers originating in {covered region names} only.`
- [x] **Step 1: Tests first** (component: both empty-state branches, as-of rendering under injected clock; e2e: uncovered-region deep link shows the explanation). **Step 2: Implement. Step 3: lanes green. Step 4: Commit** — `feat(web): surface data freshness and region coverage honestly`

**Task C5 deviations (summarized in the top-of-plan Deviations list):**

1. **A preparatory pure-refactor commit, so the task ships two commits rather than the one Step 4 names.** The coarse relative formatter this task needs already existed as `timeAgo` in the notifications feature, and both alternatives to moving it were worse: a second copy in `contracts/format.ts` is two definitions of one format, and importing it from `features/notifications` states a dependency the contracts feature does not have. `refactor(web): move the relative-time formatter beside the shared lib` moves the function, its tests, and its one call site to `src/lib/timeAgo.ts` with no behavior change (all lanes green with zero spec edits), and the feature commit follows.
2. **The helper is `regionNames`, not the `coverageLabel` the Files list names.** It has two call sites and only one of them is about coverage — the empty state names the *uncovered* selection with the same function. It lives in `format.ts` as directed, and the `Map` it builds lives there too rather than in `regions.ts`: that file is generated (`scripts/generate-regions.mjs`) and must not be hand-edited. An id the static map has no name for renders as `Region <id>` rather than dropping out, so a sentence about three uncovered regions cannot silently name two; the `Map` is explicitly `Map<number, string>` because `REGIONS` is `as const` and an inferred key type refuses the very lookup that must work.
3. **WEB-1 applies to this task too, and `useContracts` now carries the fetched `region_ids` beside `segment`.** The pitfall's own checklist names "empty-state copy" among the things that must follow the rows, and the copy here is the strongest case for it: with `keepPreviousData` holding the previous empty result, a selection read off the live URL blames the empty page on a region the response was never asked about. Mutation-verified — reverting the page to `search.region_ids` fails the in-flight component test and nothing else.
4. **Both freshness surfaces render nothing rather than a dash when the stamp is null.** `coverage.as_of` is null before the first ingestion run and `last_seen_at` is nullable per row; `Data as of —` and a `Last seen —` field both dress an absent signal up as a reading. Each omission has its own test.
5. **Two tests past Step 1's two branches**, both cases the two-branch framing hides: a selection mixing covered and uncovered regions (the empty result then has two causes at once, and naming only the coverage one implies the covered half was never consulted), and a corpus with nothing ingested at all (the covered-set sentence has no set to name and has to change wording rather than read `currently covers .`).
6. **One pre-existing test's fixture changed — its assertions did not.** `carries a repeated region_ids URL through to repeated API params` selects regions 10000002 and 10000020 and waits on the no-match card; 10000020 is not in the shared fixture's coverage, so it now renders the coverage branch instead. The fix widens that response's `ingested_region_ids` to the two regions it selects, which keeps the test waiting on the branch it was written for; the wire assertions it exists for are untouched.
7. **e2e reaches past the one spec Step 1 names.** `states.spec.ts` gains the uncovered-region deep link AND a freshness test; `segments.spec.ts`'s courier test gains the Criterion-5.7 coverage line (it is a courier-segment claim and belongs with the rest of that segment's assertions); `detail.spec.ts`'s first test gains the last-seen row. `states.spec.ts`'s existing empty-state assertions are untouched, as required. `a11y.test.tsx` gains an axe case for the uncovered-region card, which the existing empty-state case never renders.
8. **The Criterion-5.7 line renders only where there are rows.** It sits directly above the table in the populated branch, so a courier view that is empty shows one explanation rather than two. Left as-is deliberately; if Task C6 wants the statement to be a property of the view rather than of the rows, it moves above the branch switch.

### Task C6: Phase C gate

- [ ] Full frontend verification suite (all five lanes), three review rounds (lenses: criteria 1.x checklist one by one; a11y — keyboard/AT on every new control; TEST-17 — no literal dates entered the fixtures), codex review of PR-C (backgrounded), address, merge per protocol, update banners.

---

# Phase D — Frontend item-level surface (branch `feat/f008-item-surface` off merged `dev`, PR-D, `Routine`)

**Execution Status:** 🚧 IN PROGRESS — claimed 2026-08-08T00:00Z on branch `feat/f008-item-surface` (off `dev` @ `5cebd4b`). Prior state, retained for context: deferred 2026-08-07 pending nothing upstream — every prerequisite is merged: the taxonomy endpoint with its readiness signal (PR #139), the column-definition module and segment plumbing (PRs #139/#140). Two corrections carried into this execution, recorded in Deviations/D-log: `toSavedSearchParameters` needs EIGHT params (contract_type landed with C3), and the D2 UI should prevent a taxonomy selection from zeroing a clickable item-less segment (B6 review advisory). Production activation stays automatic via the coverage signal regardless of when D lands (decision log D1).

Everything gated on the taxonomy readiness signal (decision-log D1): the cascading taxonomy filter, ME/TE/runs controls, blueprint columns, composition rendering, and the want-to-buy split. The gate is data-driven — this PR merges to `dev` whenever it is done; production shows the controls only when `GET /contracts/taxonomy` reports `coverage: "complete"` (which follows the resweep automatically).

### Task D1: Taxonomy hook + gate plumbing

**Files:** Create `src/features/contracts/hooks/useTaxonomy.ts`; modify `FilterRail.tsx`
- `useTaxonomy`: `useQuery({ queryKey: ['contracts', 'taxonomy'], staleTime: 5 * 60_000 })` against `GET /contracts/taxonomy` (near-static per session).
- Gate scope — **the signal governs the whole item-dependent surface, not just the filter controls** (codex round-2 finding 2 — confirmed; spec §7 step 4 blocks "taxonomy filters, blueprint columns, composition summaries" alike):
  1. While `coverage === "partial"` (or the query errors), the item-level *controls* region renders a single quiet line — `Item filters are still indexing.` — instead of the controls. No spinner, no retry; the state is expected for ~80 minutes after a release and briefly on a fresh dev boot.
  2. The BPC and composition *cells/columns* (Task D4) render only when `coverage === "complete"`; while partial, those columns are omitted from the column sets entirely (blank columns across a mostly-NULL corpus read as breakage — the exact state §7 gates against).
  3. **Deep-linked item-level filter params while partial** (a shared URL carrying `category_id`/`group_id`/runs/ME/TE): the request is still sent (results are honest — they match whatever re-enriched rows exist) but an inline notice renders above the results: `Item filters are still indexing; results may be incomplete.` — the Criterion-7.2 explanatory state for a temporarily-partial population. Server-side rejection was considered and declined: the params are correct against existing data, and a 422 would break saved searches the moment a future resweep starts.
- [x] Tests first (all three gate branches + the complete-state positive), implement, lanes green, commit — `feat(web): gate the item-level surface on the taxonomy readiness signal`

**Task D1 deviations (summarized in the top-of-plan Deviations list):**

1. **The gate is read live from the taxonomy query, not carried on the list response** — decision log D13 has the full reasoning. WEB-1's rule ("anything describing the rows follows the rows") appears to cover the column set and the deep-link warning; both ways of tying readiness to the rows cost more than the seconds-long window is worth (a second corpus-scale list request on every cold load, or a first page that renders the surface closed on a fully-enriched corpus).
2. **Point 2 of the gate — omitting the blueprint and composition columns while partial — lands with Task D4, not here.** The columns it gates do not exist yet, so `columnsFor` gains its readiness parameter in the commit that adds something for it to hide. D1 ships the hook, the `useItemSurfaceReady` derivation, the rail's closed-state line, and the deep-link warning.
3. **A loading taxonomy reads as not-ready, like an errored one.** Step 1 names `partial` and the error case; it does not say what the first paint should claim. Not-ready is the safe direction — the alternative renders controls that may have to be withdrawn — and the window is invisible in practice, because the list request the table waits on is far slower than the taxonomy request beside it.
4. **`is_bpc` is deliberately outside the warning's trigger set** (`hasEnrichmentDependentFilters`, `filters.ts`). It is an item-level filter, but `is_blueprint_copy` has been ingested since M1, so it answers exactly as completely mid-resweep as after one; warning about it would cry wolf on the one item filter that was never at risk. Pinned by its own test.
5. **The e2e fixture lane gained a taxonomy route in eleven specs.** Every contracts view now queries `/contracts/taxonomy`, and an unrouted request in the fixture lane reaches whatever is listening on `:8000` — the exact non-hermeticity that lane exists to prevent. `interceptTaxonomy` is registered in a top-level `test.beforeEach` per spec rather than at all 66 intercept call sites; a test needing the surface open registers its own, which wins because `page.route` runs handlers last-registered-first.
6. **Two existing tests' `find` predicates were repaired, not their assertions.** `pages.test.tsx`'s two request-contract tests located the list call with `url.includes('/api/v1/contracts/')`, which was unambiguous until `/contracts/taxonomy` became a sibling under the same prefix; both now go through a `listCall` helper that matches the query string the list request always carries.

### Task D2: Cascading category → group filter with type-ahead (Criteria 3.2–3.4, 12)

**Files:** Create `src/features/contracts/components/TaxonomyFilter.tsx`; modify `FilterRail.tsx`, tests, `e2e/taxonomy.spec.ts` (new)

**Binding shape:** clone the region-list pattern (`FilterRail.tsx:112-148` — fieldset + legend + count chip + `<Input type="search">` + scroll-capped `CheckboxField` list + curly-quoted no-match line). Two stacked fieldsets: Category (full list), Group (**scoped to the selected categories**, type-ahead filtered client-side over the flat `groups` list — §17.6 is flat precisely so this needs no refetch). Changing category selection prunes now-invalid group selections from the URL in the same navigation, and the group legend announces the scoping (`aria-describedby` text: `Groups within the selected categories` — Criterion 12's announcement requirement, met with plain text not ARIA invention).
- [x] Component tests first (cascade scoping, type-ahead filtering, URL round-trip, pruning on category change), e2e (wire assertions: `category_id`/`group_id` repeated params; deep-link restore), axe case with the controls open, implement, lanes green, commit — `feat(web): cascading dogma category and group filters`

**Task D2 deviations (summarized in the top-of-plan Deviations list):**

1. **The B6 advisory is answered in `parseContractSearch`, not in the taxonomy UI.** The advisory asks the D2 UI to stop a taxonomy selection from zeroing a clickable item-less segment. Doing it in a control leaves three other routes into the same state open (a shared URL, an applied saved search, a segment click carrying the filter along), so the rule went where the identical ships-only rule already lives: an all-item-less `contract_type` selection now parses every offered-item filter away — the eight enrichment-dependent params **and `is_bpc`**. The params never reach the URL, so there is nothing invisible for Clear filters to miss.
2. **The zeroed count is suppressed rather than corrected, and the correction is a backend change.** With an offered-item filter active, the envelope's item-less counts are computed *with* that filter, so they read 0 — and clicking through drops the filter and delivers a non-zero page. That is the Criterion 1.8 defect wearing a numeral, and the honest client-side answer is the one D11 already established for the All control: render no numeral. Criterion 1.8's own fix (serving item-less counts with the offered-item filters lifted, as they are already lifted for ships-only) belongs to `_segment_counts` and is recorded here as the follow-up.
3. **The Show fieldset's two checkboxes are disabled on an item-less selection.** `Blueprint copies only` became a dead control the moment deviation 1 made the parser drop `is_bpc` — it would never stay checked. `Ships only` was *already* that dead control, from Task C3's Criterion-1.7 normalization; nothing had noticed. Both are now disabled with a described-by sentence saying why, rather than hidden: the reader has to be able to see what the segment did to Ships only, and the way to re-enable it is to leave the segment.
4. **No type-ahead on the Category list.** The binding shape names the region pattern for both fieldsets and the type-ahead parenthetical only for Group. The corpus-derived category list is a dozen-odd entries that fit the scroll cap without one, and a filter box over a list that never needs filtering is clutter in a rail that already has two.
5. **The group scope with no category selected is the whole taxonomy, and the described-by sentence says so.** The plan fixes the announcement text as `Groups within the selected categories`, which is simply false while nothing is selected — and the alternative (an empty group list until a category is picked) makes a `?group_id=` deep link unrepresentable in the controls. The sentence follows the state: `Every group; select a category to narrow this list` when the scope is open.
6. **`FilterRail.hasActiveFilters` took all nine params at once, not just D2's two.** The Discoveries entry splits the predicate work between D2 and D3; one `hasOfferedItemFilters(search)` call covers both halves and `is_bpc` besides, so D3 has no predicate change to remember.
7. **A shared `hasOfferedItemFilters` / `isItemLessSelection` pair now lives in `filters.ts`**, and `SegmentTabs`' private `itemLessOnly` copy is gone — three components were about to ask the same two questions.

### Task D3: ME/TE/runs controls + saved searches (Criteria 2.2/2.3/2.5)

**Files:** `FilterRail.tsx` (six bounded numeric inputs in a Blueprint fieldset, gated with the rest), `SaveSearchControl.tsx` (`toSavedSearchParameters` gains all nine new params), tests, `e2e/filters.spec.ts` additions
- [x] Tests first (each control wires to its param; sub-zero junk tolerated per the existing `toNonNegativeNumber` contract; saving a search with taxonomy+ME params round-trips through `SavedSearchesPage.apply()`), implement, lanes green, commit — `feat(web): blueprint stat filters and richer saved searches`

**Task D3 deviations (summarized in the top-of-plan Deviations list):**

1. **Three legended pairs, not one "Blueprint" fieldset.** §3.1 makes the families three independent EXISTS clauses — bounds within a family land on the same offered item, different families may be satisfied by different ones — so folding them into one group would suggest a joint window the wire does not implement, and would push a reader filtering on ME to state a runs range they do not care about.
2. **No upper bound on any input beyond the schema's own.** EVE caps ME at 10 and TE at 20, but that is a game rule this client would be asserting on its own; the six inputs carry `min="0"` like the price pair and nothing else. (The client is already one notch stricter than the wire, which accepts `min_runs=-1`; `toNonNegativeNumber` has floored that since Task C2 and its rationale is unchanged.)
3. **`summarizeSearch` gained the eight params too — outside the task's Files list.** The saved-searches page renders one criteria line per saved search, and without these every blueprint search on it read `All contracts · sorted by …`: two searches differing only in their ME window were indistinguishable without applying both. Counted rather than named for the taxonomy ids (`1 category`, `2 groups`), exactly as the region ids beside them are, because the names live behind `GET /contracts/taxonomy` and that page does not query it; the three windows render like the ISK range, open ends included (`ME 5–∞`).
4. **`SavedSearchesPage.apply()` needed no change** — it restores through `parseContractSearch`, so it took the eight new params the moment the parser did (Task C2). Step 1's round-trip is covered by the persisted-payload test plus the parser's own cases rather than by a new apply test.
5. **`hasActiveFilters` was already done** — Task D2 took all nine params in one predicate rather than splitting the Discovery's work across the two commits.

### Task D4: Blueprint columns + composition + want-to-buy split (Criteria 2.2, 6.1–6.4, 8.1, §8 discriminator)

**Files:** `ContractTable.tsx` (BPC cells in the item-exchange/auction column sets), `ContractDetailPage.tsx` (composition + offered/requested split), `format.ts` (`formatComposition`), tests

**Binding rendering:**
- **Every cell in this task exists only under `coverage === "complete"`** (the D1 gate, point 2 — the columns are omitted, not emptied, while partial).
- BPC cells (Runs · ME · TE) render values when `blueprint_summary.copy_count === 1`; render `{copy_count} BPCs` linking to the detail when >1; empty when absent (§8 discriminator, restated: exactly one offered BPC ⇒ values, several ⇒ count, none ⇒ empty).
- Composition cell (multi-item rows): from `composition.categories` — `3 Modules · 1 Blueprint · 2 other` (client formats: top two categories by count, remainder bucketed as `other`, the NULL-category entry always in `other`; counts are item rows — never quantities). Plus `total_volume` via `formatIsk`-style m³ formatting.
- Detail page: **Offered** and **Requested** item lists as two separately-headed sections, never merged (8.1); requested side renders even when enrichment left names unresolved (the A7 fix guarantees a route back).
- [x] Component tests first (all three BPC states; composition formatting incl. the other-bucket; the split with a WTB fixture), axe case, implement, lanes green, commit — `feat(web): blueprint stats, composition summaries, and the want-to-buy split`

**Task D4 deviations (summarized in the top-of-plan Deviations list):**

1. **ONE `Blueprint` column, not three (Runs · ME · TE).** §8's "first-class columns" reads as three, and three is what the plan's Files line implies — but none of the three is a server sort field (Task B8 added none), so separating them buys no scanning affordance that one column does not give. The costs are real on both sides: three columns empty for almost every row of the DEFAULT view, which is ships-only and therefore almost never blueprints; and a multi-copy state with no three-column rendering at all — "3 BPCs" repeated three times, or nominated into one column with two blank beside it. One cell carries all three figures, each named (`10 runs · ME 4 · TE 8`), and the §8 discriminator is unchanged: values / count-with-a-link / empty.
2. **The blueprint column hides below `lg`**, unlike the courier Deadline column that Task C4 exempted. C4's rule was "hidden only where the field has another surface", and this one does: the detail page now renders each offered copy's terms on its own row. The e2e asserts the seam from both sides — the desktop test skips on mobile with that reason, and a mobile test asserts the column is genuinely gone there.
3. **The composition breakdown replaces the `+N more` suffix rather than joining it**, and only while the surface is ready. Mid-resweep the categories are mostly unnamed, so the breakdown would read `4 other` — strictly less than the count it replaced — so the row keeps the count until the names arrive. `RowContext` grew `itemSurfaceReady` for this: the label cell chooses between two renderings, which the column SET cannot express.
4. **The detail page's offered/requested split is NOT gated**, though D1's gate scope says every cell in this task is. `is_included` has been ingested since M1, so the split is fully answerable mid-resweep — gating it would hide a working feature. Only the cells reading the *new* columns are gated.
5. **Per-item runs/ME/TE on the detail page, which the task's Files list does not name.** The list's multi-copy cell links here precisely because no single set of terms describes the contract; without the per-item figures the link answers nothing. Ungated for the same reason as deviation 4 — an absent figure renders as nothing, so there is no blank column to read as breakage.
6. **`formatBlueprintTerms` beyond the named `formatComposition`.** Both are mutation-verified literal-vs-literal. The blueprint helper carries a rule a rendered assertion states only weakly: an absent figure is omitted rather than shown as zero, because ESI omits `runs` for an original instead of sending -1 (ESI-3) and `ME 0` is a real blueprint meaningfully different from one whose ME is unknown.
7. **A new `columns.test.ts` pinning three set-level invariants** no rendered assertion states: the gated column discloses no sort field (which is what makes `sortableFieldsFor` safe to compute over the widest set, so a readiness flip can never reset a reader's sort), the column is inserted at one known position and never for couriers, and every key in every producible set stays unique (the table keys both `<th>` and `<td>` on it).
8. **Two existing e2e assertions changed, both retargeted rather than weakened.** `detail.spec.ts` waited on a `Contents` region that no longer exists; both sites now wait on `Offered`, and the first also asserts that a contract asking for nothing renders no `Requested` region at all — a claim the merged list could not make.

### Task D5: Phase D gate + feature-level verification

- [x] All five frontend lanes green; e2e fixture lane covers: segments, taxonomy cascade, ME window filter, BPC column states, WTB split.
- [ ] **Full-stack local verification** (the one end-to-end proof before the morning report). Order matters:
  1. Deps are up (postgres/valkey containers, started from the main checkout — ENV-10).
  2. **Migrate the dev database first**: this worktree runs with `DB_RECREATE_ON_STARTUP` unset (no wipe), so `hangar_bay_dev` still has the old schema — `pdm run migrate` with the same env exports as tests (`ESI_USER_AGENT` at minimum; `Settings` requires it and this worktree's `.env` lacks it), or startup errors on missing columns.
  3. `pdm run dev` with the exports (expect the dev-limit 100-contract ingest incl. the taxonomy cache fill; ENV-3: batch edits, one clean cycle; clear the Valkey aggregation lock first if a prior run was interrupted).
  4. `npm run dev`, then drive the real UI against real ESI-ingested data via the browser tools: default view unchanged; segments show counts; a courier row shows a route; after enrichment completes, taxonomy controls appear (dev corpus is small so coverage flips quickly). Screenshot the segmented views for the morning report.
- [x] Three review rounds (lenses: spec §3 acceptance criteria checklist item by item; §8 rendering rules; interaction coverage), codex review, address, merge, update banners.

**Codex review of PR #145 — five P1s and one P2, all verified against source, all taken.** The three self-review rounds below found real defects and still missed these; the cross-model round was the one that caught the reasoning errors, which is the argument for keeping it in the gate.

1. **[P1] The readiness signal never refetched.** `staleTime` marks data stale without scheduling anything, so a tab open across a future `ENRICHMENT_VERSION` resweep would report the stale answer for the whole ~80 minutes. Contradicted D1's "degrades on its own" outright. Fixed with `refetchInterval`; decision D13 amended.
2. **[P1] A readiness flip left the rows it now describes uncached-and-unrefreshed.** A contract known to hold a copy showed its BPC badge beside empty Runs/ME/TE cells. D13's claim that the worst rendering was "indistinguishable from a non-blueprint row" was false — the badge distinguishes it. Fixed with `useItemSurfaceRefresh`, which invalidates the list on a change between two KNOWN answers (never on the first answer, which would re-introduce the cold-load double fetch D13 rejected).
3. **[P1] `loan` and `unknown` got a permanently blank blueprint column.** `columnsFor` excluded only `courier`; Criterion 1.2 puts all three on the item-less side. Worse, `columns.test.ts` **codified the defect**, asserting the column for every non-courier segment — a test agreeing with the implementation instead of constraining it. Both fixed. The dev corpus held no loan or unknown contracts, so no amount of local verification would have shown it.
4. **[P1] The parser's nine-filter drop was unlicensed and destructive.** Criterion 1.7 authorizes clearing `ships_only` — and 1.9 defines its restore. The item-level filters have no restore, so dropping them destroyed a selection a segment round-trip should return, and silently rewrote a stored saved search from "no matches" into "every item-less contract". And `is_bpc=false` compiles to `~has_copy`, which every item-less contract SATISFIES — calling it unsatisfiable was specifically wrong. Reverted whole. The B6 advisory is now answered the way Criterion 7.2 actually asks: the combination is reachable, the count is honest, and the empty state explains itself. The count suppression went with it.
5. **[P1] The one-column blueprint deviation re-litigated a question §8 had already answered.** §8 anticipates the mostly-empty objection ("always present … what varies is whether a given row has values") and decides against it. The width argument was also just wrong: three narrow numeric cells are together narrower than one combined cell, which removes the mobile-hiding rationale as well. Now three columns, never hidden, with the multi-copy count in Runs alone.
6. **[P2] Two weak tests.** The item-less parser test asserted `is_bpc` undefined without ever supplying it; the "unanswered taxonomy request" test resolved a `partial` response immediately and merely duplicated the partial case. Both replaced — the latter now holds the request genuinely pending.

Ten mutations run against the fixes; all ten killed.

**Codex round 2, on the fixes themselves — one P1 and one P2, both real, both taken.** Four of the five first-round fixes were confirmed effective; two were not finished.

7. **[P1] The readiness coupling was still wrong in kind.** Invalidating the list on a readiness flip narrows the window without closing it — `keepPreviousData` holds the partial rows through the whole refetch, so the new columns still land on old rows. And excluding the `undefined → first answer` transition (to avoid a cold-load double fetch) left a permanent race: a taxonomy response resolving while the first list request is in flight produces the same mismatch with no transition to invalidate on. **Decision D13 is reversed as a result**: readiness is now captured in the list query function and travels with the rows, and the list waits for the taxonomy answer before fetching. The cost is one small round trip in front of the first list request — which is what the original entry mispriced, treating it as equivalent to alternative 1's *second corpus-scale list request per cold load*. Covered by a test that holds the post-flip refetch open, which is the only shape that catches it.
8. **[P2] The pending-taxonomy test was deleted rather than replaced.** Self-inflicted: the scripted removal of two stale tests took the newly written one with it, and the suite stayed green because the surviving neighbour asserts a similar thing. Restored, and now stronger — it asserts that no list request is issued at all until readiness is known.

Both fixes mutation-verified (4 more mutations, 4 killed). The lesson from D13's reversal is recorded in that entry: "describes the corpus rather than the rows" is not an exemption from WEB-1, because any value the row rendering consumes is about the rows at the moment it is consumed.

**Task D5 record — the three rounds, and what each found.** Each round found something substantive, so none of them was ceremony.

1. **Spec §3 criteria, one at a time.** Criterion 12 says the cascading filter must *announce* that changing category changes the available groups. The shipped `aria-describedby` sentence described the relationship but announced nothing: a described-by is read when focus reaches the fieldset, and the reader who just ticked a category is standing on a checkbox two fieldsets above it. The sentence became a polite live region carrying the scoped count (`37 groups within the selected categories`), so every category change is audible rather than only the first.
2. **§8 rendering rules, through the WEB-1 lens.** The "results may be incomplete" notice read `hasEnrichmentDependentFilters(search)` off the live URL while describing the rows on screen — and `keepPreviousData` holds the filtered rows through the whole of the request that drops the filter, so the warning was withdrawn while the rows it was about were still what the reader was looking at. It now travels with the rows out of `useContracts`, which is legitimate here (unlike the readiness signal of decision D13) because it *is* a function of the query key. Covered by a test that holds the unfiltered response open across the transition.
3. **The live corpus itself.** `2 Blueprints · 0 m³` on a real row. `total_volume` was 0.02 m³ and the plan's "`formatIsk`-style m³ formatting" dropped every fraction — six of the ten composition-bearing contracts in the dev sample measured under 1 m³, because a blueprint copy is 0.01 m³ and blueprint lots are exactly what the composition line most often describes. A lot claiming to have no volume is the confident-falsehood class this feature exists to remove. New `formatVolume` (two decimals below 100 m³, whole numbers above, `<0.01` rather than a rounded-down zero); the courier Volume column moved onto it too, where a sub-1 m³ cargo would otherwise have read as zero beside a non-zero Reward/m³ computed from it.

**Full-stack verification (2026-08-08), against the real dev backend and live ESI data.** `alembic upgrade head` on `hangar_bay_dev` (empty → `685dab7d6df5`), backend on :8000, Vite on :5173, driven with Playwright rather than the in-app browser (the dev server's `@vitejs/plugin-basic-ssl` certificate is refused there). Screenshots in the session scratchpad; what they show:

- **The gate opened on its own.** Cold boot reported `coverage: "partial"` with the rail showing `Item filters are still indexing.`; after ingestion the same endpoint reported `complete` with 7 categories and 56 groups, and the controls and the Blueprint column appeared with no flag flipped and no restart. This is decision-log D1's whole mechanism, end to end, on real data.
- **The three blueprint states, on real rows:** `30 runs · ME 10 · TE 20` (one copy), `2 BPCs` / `5 BPCs` / `6 BPCs` linking to their detail pages (several), and empty cells on the abyssal modules beside them (none). Following a count link showed each copy's own terms (`1 run · ME 0 · TE 0`) — the question the count raises, answered where it sends you.
- **The cascade and the windows:** `All 56 groups; select a category to narrow this list` → picking Blueprint → `37 groups within the selected categories`, 93 rows → 52. Then `min_me=1` → 28 rows. Criterion 2.5's strictly-less assertion holds against live data, on the filter that returned an unchanged result set in production on 2026-08-01.
- **A real want-to-buy contract** (233852162) renders a `REQUESTED · 1` section and no Offered section at all — the shape that read as an ordinary sale under the merged list.
- **Honest empties:** this dev-limited sample of The Forge holds no ship, auction or courier contracts, so the ships-only default view, the Auction segment and the Courier segment each render their empty state rather than pretending.
- No unexpected console errors (the four 401s are the anonymous `/me` probe).

---

## Spec-coverage matrix (self-review artifact — every criterion → its task)

| Criterion | Task | | Criterion | Task |
|---|---|---|---|---|
| 1.1 enum covers all types | B1 | | 5.1 days_to_complete persisted | A1/A2 |
| 1.2 loan/unknown item-less handling | B7 denominator, C3 | | 5.2 end_location_name served | A2/B2 |
| 1.3 distinct-contract counts | B3 | | 5.3 courier row | C4 |
| 1.4 segment ↔ URL | C3 | | 5.4 reward/m³ sortable | B8/C4 |
| 1.5 ships-only default stands | C3 (default untouched) | | 5.5 end_location_system_id written | A3 |
| 1.6 item-less excluded from ships-only | (by construction; asserted B3 test) | | 5.6 no distance metric | C4 |
| 1.7 no impossible combination | C3 | | 5.7 coverage statement | C5 |
| 1.8 lifted item-less counts | B3/C3 | | 6.1 category breakdown, rows not qty | B2/D4 |
| 1.9 ships-only restore | C3 | | 6.2 single-item leads with item | B2 (primary_label) |
| 2.1 runs/ME/TE persisted | A1/A4 | | 6.3 offered-only composition | B2 |
| 2.2 BPC rows display | D4 | | 6.4 list stops inlining items | B2 |
| 2.3 runs filter on runs | B5 | | 7.1 last_seen_at surfaced | B2/C5 |
| 2.4 original ≠ copy (ESI-3) | A4/B5 | | 7.2 empty-state-or-explain | C5 |
| 2.5 ME/TE functional + strictly-less | B5 | | 7.3 coverage is data | B4/C5 |
| 3.1 category/group persisted | A1/A4 | | 7.4 observed not configured | B4 |
| 3.2 cascading filter | B6/D2 | | 8.1 offered/requested distinct | B2/D4 |
| 3.3 type-ahead | D2 | | §4.1 instrumentation + PII fix | B10 |
| 3.4 URL-addressable | C2/D2 | | §5.1 both location widenings | A3 |
| 3.5 served option list | A5/B7 | | §5.2 taxonomy cache | A5 |
| 4.1 buyout persisted/served | A1/A2/B2 | | §6.1 manifest (3 kinds of edit) | A6/B5 |
| 4.2 bid + buyout display | C4 | | §7 phase order + resweep | A8/D1 gate |
| 4.3 no-buyout is words | C4 | | §14 saved-search collision | B9 |

**Deferred with reasons (recorded, not dropped):** §15.1's market-group NULL-rate re-measurement needs production data access, which is gone (perf-audit §0); logged as a follow-up in the morning report rather than faked locally. Abyssal display, reward-per-jump, `/route/` — out of scope by spec §4.2; `item_id` and `end_location_system_id` are written so those need no resweep.

## Production activation (after all four PRs merge — for Sam or a follow-up session)

1. Publish `dev` → `main` (release PR; production deploy is triggered only from `main`). Time the deploy into the post-ingestion idle window (DEPLOY-4).
2. The migration runs as `preDeployCommand`; first ordinary run backfills contract-level columns; the `ENRICHMENT_VERSION` bump makes the next run a one-off ~80-minute resweep — the lock-token warning at its end is expected (runbook at the constant). Do not redeploy mid-resweep.
3. No manual gate flip exists or is needed: `GET /contracts/taxonomy` reports `complete` when the observed corpus is restamped, and the item-level controls appear on their own (decision-log D1).
4. Verify per spec §7 step 4: non-NULL rates on item-level columns measured against recently-seen contracts (not the whole table), and the smoke stays green — the unfiltered count path changed shape (D2) and should be re-measured on production once, recorded in the perf-audit doc's §9.
