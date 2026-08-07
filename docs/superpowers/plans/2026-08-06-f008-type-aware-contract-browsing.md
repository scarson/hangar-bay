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

**Overall:** Not started.

| Phase | Status | Ship SHA(s) | Notes |
|---|---|---|---|
| A — Data layer (migration, ingestion, taxonomy cache) | ⬜ Not started | — | — |
| B — API contract (model split, counts, filters, taxonomy endpoint) | ⬜ Not started | — | — |
| C — Frontend contract-level surface (renderer refactor, segments, auction/courier) | ⬜ Not started | — | — |
| D — Frontend item-level surface (taxonomy UI, ME/TE/runs, BPC, composition) | ⬜ Not started | — | — |

### Deviations
- (none yet)

### Discoveries
- (none yet)

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
16. FASTAPI-1 (filters bind via `Annotated[ContractFilters, Query()]` — already the case; keep it), FASTAPI-3 (every new response field Optional unless provably non-null for all rows), ESI-3 (absence ≠ zero: `runs` is omitted on originals; `.get()` everywhere), PROXY-1 (no `/api/v1` in FastAPI; schema paths verbatim incl. trailing slash), SQLA-1 (new sorts must survive the grouped-ID pagination), TEST-14 (never add tests to a VCR-marked module — both `tests/api/test_contracts.py` and `test_contract_filters.py` are safe, `pytestmark` asyncio-only), TEST-18 (before writing a fixture column, confirm the ingestion writer assigns it), TEST-20 (no assertions inside `if data[...]:`).
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

**Execution Status:** ⬜ NOT STARTED

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

- [ ] **Step 1: Confirm the chain has one head** — `cd app/backend/src && ../.venv/bin/python -m alembic heads` prints exactly `ea2491c47a9f (head)`. If it prints anything else, STOP: another migration landed; re-anchor `down_revision` before proceeding.
- [ ] **Step 2: Make the equivalence test the failing test.** Add all model changes (below), run
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
- [ ] **Step 3: Author the migration** (green step). `pdm run makemigration f008_type_aware_columns` may scaffold it, but hand-verify against house style — required shape (fill the generated revision id; `down_revision = 'ea2491c47a9f'`):
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
- [ ] **Step 4: Run the equivalence test green**, then the whole migration file lane: `pytest fastapi_app/tests/test_migrations.py -q` → PASS. `alembic heads` → exactly one head (the new revision).
- [ ] **Step 5: Do NOT hand-edit `openapi.json`/`schema.d.ts`** — nothing wire-visible changed yet (schemas change in PR-B).
- [ ] **Step 6: Commit** — `feat(api): add type-aware contract and item columns with taxonomy name cache`

**Do NOT:** add response-schema fields, filters, or any read path here; touch `ENRICHMENT_VERSION`; add a server_default to any new column (absence must remain NULL); reuse `EsiMarketGroupCache`.

### Task A2: Contract-level ingestion writes (`buyout`, `days_to_complete`, `end_location_name`)

**Files:**
- Modify: `app/backend/src/fastapi_app/services/background_aggregation.py` (`_build_contract_rows`, `:160-212`)
- Test: `app/backend/src/fastapi_app/tests/services/test_background_aggregation.py`

**Interfaces — Consumes:** A1's columns. **Produces:** upsert rows now carry `buyout`, `days_to_complete`, `end_location_name` keys (uniform across every row — the bulk_upsert derives update columns from `values[0]`).

- [ ] **Step 1: Write the failing test.** In `test_background_aggregation.py`, next to `test_resolved_location_names_land_on_persisted_contract_rows` (`:900`), following its end-to-end `_process_contracts` pattern:
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
- [ ] **Step 2: Run it** — FAIL (`row.buyout is None`).
- [ ] **Step 3: Implement.** In `_build_contract_rows`'s dict literal: after `"volume": c.get("volume"),` (`:198`) add
  ```python
              "buyout": c.get("buyout"),
              "days_to_complete": c.get("days_to_complete"),
  ```
  and after `"start_location_name": ...` (`:200`) add
  ```python
              "end_location_name": id_to_name_map.get(c.get("end_location_id")),
  ```
  (End locations are already in the name map — `_collect_resolvable_ids:97` unions them. Do not touch the deliberately-absent-columns comment block at `:203-209`.)
- [ ] **Step 4: Run green**, then the full aggregation module: `pytest fastapi_app/tests/services/test_background_aggregation.py -q`.
- [ ] **Step 5: Commit** — `feat(api): persist buyout, days_to_complete, and end_location_name at ingestion`

### Task A3: End-location system resolution (widen both start-only paths — spec §5.1 exactly)

**Files:**
- Modify: `app/backend/src/fastapi_app/services/background_aggregation.py` — `_npc_station_ids` (`:150-157`), `_select_known_station_systems` (`:575-598`), `_build_contract_rows`
- Test: `tests/services/test_background_aggregation.py`

**Context (do not re-derive):** §5.1 names exactly two paths to widen. The fetch set (`_npc_station_ids`) is start-only; the DB cache read-back (`_select_known_station_systems`) is start-only — and skipping the read-back does not fail loudly, it just re-fetches destination-only stations from ESI forever. The read-back's docstring hazard must be preserved: the upsert copies every supplied column on conflict, so the read-back must cover the `end_location_*` column pair too or an ESI blip writes NULL over known destinations corpus-wide.

- [ ] **Step 1: Failing tests** (three, added near the station-resolution block at `:1379+`):
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
- [ ] **Step 2: Run — all three FAIL** (first on NULL end system; third may fail on NULL-overwrite).
- [ ] **Step 3: Implement.**
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
- [ ] **Step 4: Run green; run the whole station block** (`pytest -q -k station`), confirming the four existing station tests (`:1379`, `:1398`, `:1425`, `:1484`, `:1531`) still pass — the boundary test pins the id-range logic your comprehension must preserve.
- [ ] **Step 5: Commit** — `feat(api): resolve courier end locations to solar systems at ingestion`

### Task A4: Item-level ingestion writes (`runs`, `material_efficiency`, `time_efficiency`, `item_id`, `category_id`, `group_id`)

**Files:**
- Modify: `background_aggregation.py` — `_fetch_item_rows` item mapping (`:647-662`) and `_enrich_items_and_find_ships` (`:780-800`)
- Test: `tests/services/test_background_aggregation.py`

- [ ] **Step 1: Failing test** (end-to-end through `_process_contracts`, the enrichment-stubbing idiom from `:133-144`):
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
- [ ] **Step 2: Run — FAIL.**
- [ ] **Step 3: Implement.** In `_fetch_item_rows`'s dict literal (after `"raw_quantity"`):
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
- [ ] **Step 4: Green; run the enrichment-version tests** (`:573`, `:595`, `:673`, `:706`) to confirm the added keys didn't disturb the upsert's uniform key set.
- [ ] **Step 5: Mutation-verify** (TEST-12): `cp` snapshot, delete the `item["category_id"] = ...` line, confirm the new test goes red on `category_id is None`, restore, rerun green.
- [ ] **Step 6: Commit** — `feat(api): persist blueprint stats, item_id, and dogma taxonomy ids during enrichment`

### Task A5: Taxonomy name cache population

**Files:**
- Modify: `app/backend/src/fastapi_app/core/esi_client_class.py` (new `get_universe_category`), `background_aggregation.py` (`_enrich_items_and_find_ships` + a new `_upsert_taxonomy_names` helper)
- Test: `tests/services/test_background_aggregation.py`

**Interfaces — Produces:** `EsiTaxonomyCache` rows: `('group', <id>, name, parent_category_id, fetched_at)` from group payloads already in hand; `('category', <id>, name, NULL, fetched_at)` from the one new ESI call. `ESIClient.get_universe_category(category_id: int) -> dict[str, Any]`.

- [ ] **Step 1: Failing test:**
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
- [ ] **Step 2: FAIL** (no `EsiTaxonomyCache` import / no rows).
- [ ] **Step 3: Implement.**
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
- [ ] **Step 4: Green.** Also confirm the shape-guard behavior: `_resolve_esi_objects` drops non-dict payloads, so a failed category fetch degrades to a missing name, and the next run retries it (cache-first check only skips *cached* ids).
- [ ] **Step 5: Commit** — `feat(api): cache dogma category and group names for the taxonomy option list`

### Task A6: ESI drift-monitor manifest + snapshot

**Files:**
- Modify: `app/backend/tools/esi_spec_monitor/manifest.py`, `app/backend/tools/esi_spec_monitor/snapshot.json` (regenerated, never hand-edited)
- Test: `pdm run pytest -q tools` (the monitor's own unit lane) + `pdm run esi-spec-monitor`

No TDD exemption issues — this is tooling config, but the monitor's tests run in the ordinary lane.

- [ ] **Step 1:** Add the six consumed fields (spec §6.1 point 1): `buyout`, `days_to_complete` to the `/contracts/public/{region_id}` block; `runs`, `material_efficiency`, `time_efficiency`, `item_id` to the `/contracts/public/items/{contract_id}` block — each value string naming its consumer in the house format, e.g. `"runs": "background_aggregation._fetch_item_rows -> ContractItem.runs; blueprint-copy display and the min_runs/max_runs filter (F008)"`.
- [ ] **Step 2:** Amend the two existing entries (point 2): `group_id` (`manifest.py:133`) and `category_id` (`:143`) consumer notes now also name the persisted `ContractItem.group_id`/`category_id` columns and the taxonomy cache. While editing, correct the stale method name in those strings: the function is `_enrich_items_and_find_ships`, not `_enrich_items`.
- [ ] **Step 3:** Add a new `Endpoint` block for `GET /universe/categories/{category_id}` (spec_path `/universe/categories/{category_id}`, call_path `/v1/universe/categories/{category_id}/` — match whatever version Task A5 verified, caller `background_aggregation._upsert_taxonomy_names`, consumed field `name`).
- [ ] **Step 4:** Leave the `raw_quantity` `KnownAbsentField` (`:114-118`) **unchanged in this PR** — its "read by min_runs/max_runs" consequence stays true until PR-B rewires the filter; PR-B Task B5 amends it (spec §6.1 point 3).
- [ ] **Step 5:** `pdm run esi-spec-monitor --update` to regenerate the snapshot; commit it with the reason in the message. Run `pdm run esi-spec-monitor` → green; `pytest tools -q` → green.
- [ ] **Step 6: Commit** — `chore(api): extend the ESI drift manifest to the F008 field set`

### Task A7: Completion-predicate widening (requested items' categories count)

**Files:**
- Modify: `background_aggregation.py:798` (the `elif` guard)
- Test: `tests/services/test_background_aggregation.py`

**Context:** Criterion 8.1 renders requested items and 6.3 summarizes them by category, so a contract whose *requested* item failed category resolution must not be stamped COMPLETED (spec §9 "a narrow scope mismatch this feature creates"). The ship-flag `if` at `:789` keeps its `is_included` guard — only offered items decide the flag; the failure-tracking `elif` drops its guard.

- [ ] **Step 1: Failing test:**
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
- [ ] **Step 2: FAIL** (currently stamps COMPLETED — the guard skips excluded items).
- [ ] **Step 3: Implement:** change `:798` from `elif not group and item["is_included"]:` to `elif not group:` and update the adjacent comment block (`:792-797`) to say the category half covers every item because requested items now render by category (F008 Criteria 6.3/8.1), while the ship-flag `if` above stays offered-only.
- [ ] **Step 4: Green; run `:744` and `:785`** (the existing unresolved-category tests) — they pin the offered-item half and must stay green.
- [ ] **Step 5: Commit** — `fix(api): keep contracts retryable when a requested item's category fails to resolve`

### Task A8: The `ENRICHMENT_VERSION` bump (last ingestion change; nothing after this touches ingestion)

**Files:** `background_aggregation.py:73`
**Test:** existing `:673` / `:706` (they monkeypatch relative to the constant and stay green by construction; the point of this task is the production resweep).

- [ ] **Step 1:** Change `ENRICHMENT_VERSION = 1` → `ENRICHMENT_VERSION = 2`. Do not edit the runbook comment (it is evergreen).
- [ ] **Step 2:** Full backend suite green (Global Constraint 11 invocation), `pdm run lint` green.
- [ ] **Step 3: Commit** — `feat(api): requeue the corpus to backfill item-level taxonomy and blueprint columns`

  Body must carry the operational note: the next production run after deploy is a one-off ~80-minute resweep; the lock-token-mismatch warning at its end is expected; do not redeploy mid-resweep (runbook at the constant).

### Task A9: Phase A gate — review, codex, merge

- [ ] **Step 1:** Full verification: backend suite green on the scratch DB, `pdm run lint`, `alembic heads` = 1, `pytest fastapi_app/tests/test_migrations.py -q` green.
- [ ] **Step 2:** Three self-review rounds with distinct lenses: (a) spec §4.1/§5/§7 coverage — every data-layer claim implemented; (b) ESI-3 sweep — every new mapping uses `.get()`, no default masquerading as data; (c) bulk-upsert semantics — uniform keys, no enrichment-maintained column added to `_build_contract_rows`, read-back covers both location roles. Fix everything found; extra rounds until clean.
- [ ] **Step 3:** Push branch, open PR-A against `dev` (`## Merge classification` → `Review — database schema`, note Sam's 2026-08-06 merge grant). Run the backgrounded codex review; address findings (fix or rebut in PR comments); record any consequential choice in the decision log.
- [ ] **Step 4:** CI green (verify explicitly) → `gh pr merge <n> --merge --delete-branch --body ""`. Update this plan's banner + table with SHAs. (The local branch survives in-worktree; expected — the `gh` exit-1 on local cleanup after a successful remote merge is a known worktree artifact.)

---

# Phase B — API contract (branch `feat/f008-api-contract` off merged `dev`, PR-B, `Review — public API contract`)

**Execution Status:** ⬜ NOT STARTED

Everything wire-visible: the §17 model split, the contract-type filter and grouped counts, coverage, functional item-level filters, new sorts, the taxonomy endpoint, the saved-search widening, the PII log fix, and the regenerated client artifacts. Rebase onto `dev` after PR-A merges before starting.

### Task B1: `ContractType` enum + `contract_type` filter

**Files:**
- Modify: `app/backend/src/fastapi_app/schemas/contracts.py`, `app/backend/src/fastapi_app/services/contract_service.py` (`_apply_contract_filters`), `app/backend/src/fastapi_app/services/watchlist_matcher.py:151` (+ `:43`)
- Test: `tests/api/test_contract_filters.py` (private region **99999960**)

**Interfaces — Produces:** `ContractType(str, Enum)` with members `item_exchange, auction, courier, loan, unknown` (the full ESI set, spec Criterion 1.1); `ContractFilters.contract_type: Optional[List[ContractType]]`.

- [ ] **Step 1: Failing tests** (HTTP-level per TEST-1; region 99999960):
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
- [ ] **Step 2: FAIL** (unknown param today is ignored → 200).
- [ ] **Step 3: Implement.** In `schemas/contracts.py`, above `SortableContractFields`:
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
- [ ] **Step 4: Green**; run the watchlist matcher module too (`pytest -q fastapi_app/tests/services/test_watchlist_matcher.py`).
- [ ] **Step 5: Commit** — `feat(api): filter contracts by type with a closed enum`

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
- `composition` is non-NULL only when the contract has **two or more offered item rows**; counts are item **rows**, not quantities (Criterion 6.1); categories sorted by `item_row_count` desc then `name` asc; rows with NULL `category_id` aggregate into one `{category_id: null, name: null}` entry sorted last (the client buckets it as "other"); `total_volume` sums offered rows' `quantity`-independent contract `volume`? **No** — total_volume is the contract's own `volume` field (there is no per-item volume in the model; §17.2's `total_volume` maps to `Contract.volume`).
- `blueprint_summary` present iff ≥1 offered BPC; `copy_count > 1` ⇒ the three value fields are `None` (§17.3/§8).
- `primary_label` chain exactly §17.4: (1) `type_name` of the first offered item with `category == "ship"`; (2) first offered item's `type_name`; (3) trimmed non-empty `title`; (4) couriers: `f"Courier to {end_location_name}"` or `"Courier"` when unresolved; (5) `f"Contract {contract_id}"`. ("First" = lowest `record_id`, stated here so two implementers can't order differently.)
- `reward_per_volume = reward / volume`, `None` when either is NULL or `volume == 0` (§9).
- Category display names for composition come from one small SELECT over `EsiTaxonomyCache` (kind='category') per request; a missing name serves `name: null` rather than a fabricated string.

- [ ] **Step 1: Failing tests.** In `test_contract_filters.py`, region 99999961 — seed one multi-item mixed contract (offered ship + offered BPC + **requested** module), one single-item contract, one courier; assert:
  - list rows carry **no** `items` key at all (`"items" not in row` — the envelope's `items` is the page, the row must not have one);
  - the mixed contract: `is_blueprint_copy_contract is True`, `primary_label` is the ship's type_name, `composition.total_item_rows == 2` (requested module excluded), `blueprint_summary.copy_count == 1` with the BPC's runs/ME/TE;
  - the courier row: `primary_label == "Courier to <name>"`, `composition is None`;
  - the detail endpoint for the mixed contract still carries full `items` including the requested module, each item exposing `runs`/`category_id` fields;
  - a contract holding **two** offered BPCs serves `blueprint_summary == {"runs": None, "material_efficiency": None, "time_efficiency": None, "copy_count": 2}`.
  In `test_contract_service.py`: extend the existing mixed-bundle partition test's fixture family with a **requested-only BPC** contract and assert it matches `is_bpc=false` (offered-only semantics — the Story 8 disagreement, resolved).
- [ ] **Step 2: FAIL.**
- [ ] **Step 3: Implement** — schemas first (all new response fields `Optional` per FASTAPI-3 except `is_blueprint_copy_contract`/`primary_label`, which the builder always supplies), then the service builder (explicit keyword construction, no `model_validate` on ORM for the split models), then rewire both `ContractListResponse` constructors, then the detail route. `ContractListResponse` becomes `PaginatedResponse[ContractListItemSchema]` keeping `unknown_system_excluded`.
- [ ] **Step 4: Green.** Then run the FULL backend suite — this task breaks every test that read `items` off list rows; fix each by moving it to the detail endpoint or the new fields (that migration of assertions is in-scope here, and any test whose meaning evaporates gets flagged in the PR body, never silently deleted).
- [ ] **Step 5: Update `tests/test_export_openapi.py:30-33`** envelope assertion (still `{"total","page","size","items","unknown_system_excluded"}` here; B3/B4 extend it).
- [ ] **Step 6: Commit** — `feat(api)!: split the contract list row from the detail response and serve derived summaries`
  (The `!` is honest: list rows stop carrying `items` — a breaking wire change, §6.4.)

### Task B3: Grouped segment counts + derived total (decision-log D2; §17.5, Criteria 1.3/1.8)

**Files:**
- Modify: `services/contract_service.py`
- Test: `tests/services/test_contract_service.py`, `tests/api/test_contract_filters.py` (region **99999962**)

**Interfaces — Produces:** envelope field `segment_counts: Dict[str, int]` on `ContractListResponse` (every `ContractType` value as a key, zero-filled); internal `_segment_counts_and_total(db, filters, needs_item_join) -> tuple[dict[str, int], int]`.

**The query shape (binding):** build the same filtered query as the list, but from `filters.model_copy(update={"contract_type": None, "is_ship_contract": None})`; then
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
Python then: zero-fills over `ContractType`; picks per-type counts for `segment_counts` per Criterion 1.8 (while `is_ship_contract=True` is active: item-bearing types use the ships aggregate, item-less types — courier/loan/unknown — use the lifted aggregate; `is_ship_contract=False`: `all - ships` for item-bearing; inactive: the lifted aggregate); derives `total` as the sum over the *selected* types (all five when no `contract_type` filter) of the aggregate matching the actual `is_ship_contract` filter. The flat `_count_distinct_contracts` call disappears from `get_contracts` (it remains for the residual count). One corpus-scale aggregate per request — same as today, not one more (D2). `count(DISTINCT ...)` is required because the item join inflates rows (SQLA-1); when `needs_item_join` is false the DISTINCT is unnecessary but harmless — keep the single shape, and note the perf-audit's DISTINCT-wrapper follow-up is absorbed by this rewrite.

- [ ] **Step 1: Failing tests:**
  - **Equivalence property (the load-bearing one):** in `test_contract_service.py`, seed a corpus in two private regions with mixed types, multi-item contracts, ships and non-ships; for each filter combination in a parametrized matrix (`search`, `is_bpc`, `type_ids` joined path, `is_ship_contract` both values, `contract_type` single + multi, price bounds), assert `response.total == await _count_distinct_contracts(db, <the same fully-filtered query built the old way>)`. Run under **both** `liveness_branch` params (the fixture at `:509` — the watermark fast/fallback branches must agree).
  - **Zero-fill:** every response's `segment_counts` has exactly the five keys, zeros included (`assert set(data["segment_counts"]) == {"item_exchange","auction","courier","loan","unknown"}` even against an empty region).
  - **Criterion 1.8 (HTTP-level, region 99999962):** seed 2 ship item_exchanges, 1 non-ship item_exchange, 1 courier. With `is_ship_contract=true`: `segment_counts["item_exchange"] == 2` (respects ships-only) but `segment_counts["courier"] == 1` (lifted — not 0). `total == 2`.
  - **Counts respect other filters (§6.2):** with a `min_price` excluding one ship, `segment_counts["item_exchange"]` drops accordingly.
  - **Distinct contracts (Criterion 1.3):** a multi-item contract counts once under a joined-path filter (`search` hitting both its items).
  - **Empty-page threading:** a filter matching nothing still returns full zero-filled `segment_counts` (Global Constraint 18 — both constructors).
- [ ] **Step 2: FAIL** (no `segment_counts` key).
- [ ] **Step 3: Implement** per the binding shape; thread through **both** `ContractListResponse` constructors; `total == 0` short-circuit now keys off the derived total.
- [ ] **Step 4: Green; mutation-verify the equivalence test** (snapshot, drop the `FILTER` aggregate so ships counts equal all counts, confirm red, restore, green).
- [ ] **Step 5:** Extend `tests/test_export_openapi.py` envelope assertion with `segment_counts`.
- [ ] **Step 6: Commit** — `feat(api): serve per-type segment counts from one grouped statement`

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

- [ ] **Step 1: Failing tests:** seed contracts in two regions → `coverage.ingested_region_ids` equals exactly those two, `as_of` equals the newest `last_seen_at` seeded; empty DB → `ingested_region_ids == []`, `as_of is None`; and the drift case: monkeypatch `AGGREGATION_REGION_IDS` to include a third, empty region → it must NOT appear (that assertion is the criterion).
- [ ] **Step 2: FAIL. Step 3: Implement** (both constructors; computed once per request alongside the counts). **Step 4: Green.**
- [ ] **Step 5:** Extend the export-openapi envelope assertion with `coverage`.
- [ ] **Step 6: Commit** — `feat(api): report observed region coverage on the list envelope`

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

- [ ] **Step 1: Failing tests** — for EACH family, the §3.1 three-way identity with a mixed-child fixture (template: `test_contract_filters.py:636`). The ME one in full (runs and TE are the same shape over their columns; write all three, no "similar to above"):
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
      assert {c["contract_id"] for c in low.json()["items"]} == {964001}
      assert {c["contract_id"] for c in high.json()["items"]} == {964001, 964002}
      # Three-way identity with the mixed contract counted once per branch it
      # genuinely has an item in, and neither == 2 as stated above.
      assert unfiltered.json()["total"] == 4
      neither = unfiltered.json()["total"] - len(
          {964001} | {964001, 964002}
      )
      assert neither == 2
      assert low.json()["total"] + high.json()["total"] - 1 + neither == unfiltered.json()["total"]

      # Range composes per item: no single item sits in [10, 12].
      window = await client.get(f"{base}&min_me=10&max_me=12")
      assert [c["contract_id"] for c in window.json()["items"]] == [964002]
      assert 964001 not in {c["contract_id"] for c in window.json()["items"]}

      # Criterion 2.5's harsher assertion: the filtered count is STRICTLY LESS than
      # unfiltered — the live defect returned the identical count.
      assert high.json()["total"] < unfiltered.json()["total"]
  ```
  Note the mixed contract appears in BOTH single-bound branches (it has an item on each side) — that is correct under §3.1's existential rule; the three-way identity accounts for the overlap explicitly (`-1`). The runs-family test additionally seeds a blueprint **original** (`runs=None`) and asserts it lands in `neither` under both bounds (ESI-3: absence is not zero).
- [ ] **Step 2: FAIL** (today: runs reads permanently-NULL `raw_quantity`; ME/TE ignored entirely → identical counts).
- [ ] **Step 3: Implement** per the binding shape. **Step 4: Green; mutation-verify** the ME test by removing `is_included.is_(True)` from the factory (must go red on 964004 leaking in), restore, green. Run the full filter + service modules.
- [ ] **Step 5: Commit** — `fix(api): make the runs, ME, and TE filter families classify contracts by offered items`

### Task B6: Taxonomy filters (`category_id`, `group_id`) as one offered-only EXISTS family (Criteria 3.1–3.4)

**Files:** `schemas/contracts.py` (`ContractFilters`), `services/contract_service.py` (`_apply_item_filters`), test `tests/api/test_contract_filters.py` (region **99999965**)

- [ ] **Step 1: Failing test:** seed a mixed-child contract (offered Ship-category item + offered Module-category item), a module-only contract, and a requested-only-in-category contract; assert `category_id=<ship>` matches the mixed + not the module-only; `category_id=<ship>&group_id=<frigate>` requires the SAME offered item to satisfy both (a contract whose ship item is group A does not match group B even though another offered item is group B — seed exactly that shape); requested-side items never match; a category with zero matches returns `total == 0` (not an error); the mixed contract appears under a ship-category query AND under a module-category query (existential semantics — a mixed contract legitimately matches both positive filters; there is no negation branch for taxonomy), and repeated `group_id` params combine.
- [ ] **Step 2: FAIL. Step 3: Implement:** fields
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
- [ ] **Step 4: Green. Step 5: Commit** — `feat(api): filter contracts by dogma category and group`

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
Flat, not nested (§17.6 — the client filters groups locally). Lists come from `EsiTaxonomyCache` (kind partition), sorted by name. **`coverage` is the item-surface readiness signal (D1):** `"complete"` iff the share of live (`still_listed_by_esi()` + unexpired), item-bearing (`type IN (item_exchange, auction)`), `item_processing_status='COMPLETED'` contracts whose `enrichment_version == ENRICHMENT_VERSION` is ≥ **0.99** (and the denominator is > 0); `"partial"` otherwise. The denominator restriction to *live* contracts is §7.1's population-mixing warning made executable — delisted rows never re-enrich and must not drag the ratio. The threshold tolerates stragglers (`ENRICHMENT_INCOMPLETE` retries). This signal auto-degrades during any future version bump's resweep and auto-restores — that is a feature, not an accident (D1).

- [ ] **Step 1: Failing tests:** (a) cold cache → `{"categories": [], "groups": [], "coverage": "partial"}` (200, honest, never 500); (b) seeded cache + a corpus fully stamped at the current version → `"complete"`, lists sorted, groups carrying `category_id`; (c) same corpus with 5% of live item-bearing contracts at the old version → still `"complete"` (0.99 threshold); with 50% → `"partial"`; (d) a delisted old-version contract (stale `last_seen_at` in a region with a newer watermark) does NOT drag the ratio (the §7.1 denominator case); (e) couriers/loans (never enriched by construction, Criterion 1.2) do not count in the denominator.
- [ ] **Step 2: FAIL. Step 3: Implement** (ratio via one aggregate query: `count(*) FILTER (WHERE enrichment_version = :v)` over the restricted population; import `ENRICHMENT_VERSION` from the service module — one authority). **Step 4: Green. Step 5: Commit** — `feat(api): serve the taxonomy option list with an observed readiness signal`

### Task B8: New sortable fields (`reward_per_volume`, `days_to_complete`, `buyout`) (§6.2, Criterion 5.4, §11's five-touchpoint rule)

**Files:** `schemas/contracts.py` (`SortableContractFields`), `services/contract_service.py` (`SORT_MAP` + null ordering), test `tests/api/test_contract_filters.py` (region **99999966**)

- [ ] **Step 1: Failing tests — one per field, asc AND desc, distinct-value fixtures (TEST-3):** seed three couriers with distinct reward/volume ratios plus one with `volume=0` (guard case) and one item_exchange (`reward` NULL); for each of the three new sorts assert ascending and descending produce different first rows, the expected exact order, and that NULL-valued rows sort LAST in both directions (a null `reward_per_volume` row must not occupy the "best value" end — the §15.2 display rule applied to the one ratio this feature ships). Also: `volume=0` yields `reward_per_volume: null` on the wire, not infinity/error (§9), and one sort test runs with `search` set so the grouped joined path exercises the aggregate (SQLA-1).
- [ ] **Step 2: FAIL** (enum rejects the values → 422).
- [ ] **Step 3: Implement:** enum members `reward_per_volume`, `days_to_complete`, `buyout`; SORT_MAP entries:
  ```python
      SortableContractFields.buyout: Contract.buyout,
      SortableContractFields.days_to_complete: Contract.days_to_complete,
      # Computed ratio; NULL when reward is NULL or volume is NULL/0 (spec §9).
      SortableContractFields.reward_per_volume: Contract.reward / func.nullif(Contract.volume, 0.0),
  ```
  Null ordering: in both fetch paths, when the resolved sort column is one of the three new (nullable) entries, append `.nulls_last()` to the order expression (`order_expr = order_expr.nulls_last()`), leaving the existing four sorts byte-identical (they are non-null columns; changing their plans without cause is scope creep). The grouped path's aggregate (`func.max`/`min` over the expression) already tolerates expressions.
- [ ] **Step 4: Green.** Note the five-touchpoint rule: touchpoints 1–2 (SORT_MAP, enum) here; 3 (`SavedSearchParameters.sort_by`) widens automatically via the shared enum — B9's tests cover it; 4–5 (frontend `SORT_FIELDS`, regenerated types) are PR-C Task C2.
- [ ] **Step 5: Commit** — `feat(api): sort by reward per volume, delivery window, and buyout`

### Task B9: `SavedSearchParameters` widening (decision-log D4; spec §14)

**Files:** `schemas/account.py`, tests `tests/api/test_account_schemas.py`, `tests/api/test_saved_searches.py`

- [ ] **Step 1: Failing tests first, as edits to the pins:** replace the two `min_me` 422 cases (`test_saved_searches.py:125`, `test_account_schemas.py:57`) with a still-rejected key (`{"min_me_typo": 5}`-style junk) AND add acceptance cases: a blob carrying `contract_type=["courier"]`, `category_id=[6]`, `group_id=[25]`, `min_runs=1`, `min_me=10`, `max_te=20` validates and round-trips. Keep the `page` and `is_ship_contract` rejection pins (`test_account_schemas.py:58-59`) — both stay rejected. `test_saved_searches.py:168` (`additionalProperties is False`) stays green because `extra="forbid"` stays.
- [ ] **Step 2: Run — the acceptance cases FAIL** (extra=forbid rejects them today).
- [ ] **Step 3: Implement:** add to `SavedSearchParameters`, bounds copied from `ContractFilters` exactly:
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
- [ ] **Step 4: Green** (all three saved-search test modules). **Step 5: Commit** — `feat(api): let saved searches hold the type, taxonomy, and blueprint filters`

### Task B10: PII log fix + regeneration + phase gate

**Files:** `services/contract_service.py` (4 sites), `app/frontend/web/openapi.json` + `src/lib/api/schema.d.ts` (regenerated), tests

- [ ] **Step 1: Failing test:** in `test_contract_service.py`, following the `log_key_event`-monkeypatch idiom (`:178`/`:268`): perform a search with `filters.search="Tristan sale"`; capture ALL log calls (including the plain `logger.info` start log — monkeypatch `contract_service.logger` too); assert no captured `search_terms` dict contains the literal string, and each carries `search_len: 12` instead.
- [ ] **Step 2: FAIL. Step 3: Implement:** in all FOUR `search_terms` dicts (`:373` start `logger.info`, `:421` zero-result, `:468` success, `:492` failure — the first is NOT a `log_key_event`; a task scoped to those would miss it), replace `"search": filters.search` with `"search_len": len(filters.search) if filters.search else 0`. Reconcile `tests/api/test_observability.py:42/:58` if the key change surfaces there. Also add the new filter dimensions to the two full-dimension sites (`contract_type`, `category_id`, `group_id` — dimensions only, §4.1).
- [ ] **Step 4:** `pdm run export-openapi` && `npm run generate:api`; commit both artifacts. Full backend suite + lint green.
- [ ] **Step 5:** Three review rounds (lenses: §17 field-name conformance byte-for-byte; FASTAPI-3 optionality chain over every new field; the two-constructor/residual-sync traps 18–19), codex PR review (backgrounded), address, decision-log any judgment calls, merge PR-B per protocol.
- [ ] **Step 6: Commit** (fix itself) — `fix(api): log search dimensions without the raw query text`

---

# Phase C — Frontend contract-level surface (branch `feat/f008-contract-surface` off merged `dev`, PR-C, `Routine`)

**Execution Status:** ⬜ NOT STARTED

The cell-renderer refactor, the new wire shape, segments with counts, auction and courier columns, freshness, and coverage-honest empty states. Rebase onto `dev` after PR-B merges (the regenerated `schema.d.ts` arrives with it).

### Task C1: `ContractTable` per-column cell renderers (single-writer; pure refactor, zero behavior change)

**Files:**
- Modify: `app/frontend/web/src/features/contracts/components/ContractTable.tsx`
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

- [ ] **Step 1:** Refactor; `COLUMNS` becomes the single source for header AND cell.
- [ ] **Step 2:** `npm run test` + `npm run test:future-clock` + `npx tsc -b` + `npx eslint .` + `npm run e2e` — ALL green with **zero spec edits** (that is the proof it was a pure refactor).
- [ ] **Step 3: Commit** — `refactor(web): drive contract table cells from the column definitions`

### Task C2: Adopt the new wire shape (rename + derived fields + fixtures)

**Files:**
- Modify: `src/lib/api/client.ts` (type aliases), `src/features/contracts/format.ts` (delete `primaryLabel`), `ContractTable.tsx`, `ContractDetailPage.tsx`, `src/features/contracts/filters.ts` (SORT_FIELDS + new params), `e2e/fixtures/contracts.ts` (wire mirrors), every test touching list-row `items`
- Test: `pages.test.tsx`, `filters.test.ts`, `format.test.ts`, e2e fixture lane

**The moves (each mechanical, all in one task because they only compile together):**
1. `Contract = components['schemas']['ContractListItemSchema']`; add `ContractDetail = components['schemas']['ContractDetailSchema']`; `PaginatedContracts` unchanged name.
2. Delete `format.ts::primaryLabel`; the four call sites read `contract.primary_label` (the detail page calls it twice — `:110` heading and `:119` title-differs comparison; replace both).
3. `contractIsBpc` (`ContractTable.tsx:35-37`) and the detail page's independent copy (`ContractDetailPage.tsx:100`) both become reads of `is_blueprint_copy_contract`.
4. The "+N more" suffix reads `composition` (`composition && composition.total_item_rows > 1 → +{total_item_rows - 1} more`); list rows have no `items`.
5. `SORT_FIELDS` gains `'reward_per_volume', 'days_to_complete', 'buyout'` (mirror of the widened enum — the duplicated-list touchpoint §11 names).
6. `ContractSearch`/`parseContractSearch`/`toApiQuery` gain `contract_type?: ContractTypeValue[]` (an `as const` list + `.includes()` guard, the closed-enum client mirror), `category_id?: number[]`, `group_id?: number[]`, `min_runs/max_runs/min_me/max_me/min_te/max_te?: number` (via `toNonNegativeNumber`; min_runs via `toNumber` — `ge=-1` upstream). Wire-through in `toApiQuery` is pass-through (no renames beyond the existing `ships_only`→`is_ship_contract`).
7. `e2e/fixtures/contracts.ts`: `WireContract` loses `items` and gains `end_location_name`, `buyout`, `days_to_complete`, `reward_per_volume`, `last_seen_at`, `is_blueprint_copy_contract`, `primary_label`, `composition`, `blueprint_summary`; `type` union gains `'loan' | 'unknown'`; `WirePage` gains `segment_counts` (all five keys) and `coverage`; `WireContractDetail` (new) carries `items` for detail intercepts; builders updated so every existing dataset compiles with honest values (`primary_label` derived in the builder from the same inputs it previously buried in items). Add canned `AUCTION_CONTRACTS` and `COURIER_CONTRACTS` datasets (distinct sortable values, TEST-3).
- [ ] **Step 1:** Make the changes test-first where behavior exists (`filters.test.ts` cases for each new param's parse/serialize junk-tolerance; `pages.test.tsx` fixtures to the new shape) — then chase the compiler (`npx tsc -b`) to every remaining consumer.
- [ ] **Step 2:** All four verification lanes green + e2e fixture lane green.
- [ ] **Step 3: Commit** — `feat(web): adopt the split list-row contract and server-computed labels`

### Task C3: Contract-type segmentation UI (Criteria 1.3–1.9)

**Files:**
- Create: `src/features/contracts/components/SegmentTabs.tsx`
- Modify: `ContractsPage.tsx` (mount + heading/title logic), `filters.ts` (already has the param from C2), `FilterRail.tsx` (`hasActiveFilters` + `resetFilters` note), tests + `e2e/segments.spec.ts` (new)

**Binding behavior:**
- Four controls: **All** (no `contract_type` filter), **Item exchange**, **Auction**, **Courier** — `loan`/`unknown` get no control but stay URL-reachable and counted (Criterion 1.1). Rendered as a `radiogroup`-semantics toolbar (`role="tablist"` is for tab panels; use a `<fieldset>` of toggle buttons with `aria-pressed`, matching the codebase's no-ARIA-authoring preference) — keyboard reachable, selected state exposed (Criterion 12).
- Each control shows its count from `segment_counts` (All = sum of the five). Counts reflect all other active filters because the server computed them that way — the client must NOT adjust them.
- Selecting **Courier** (or arriving at a `loan`/`unknown` URL) with ships-only active: the patch sets `contract_type: ['courier']` AND `ships_only: false` in one navigation — visibly, the Ships-only checkbox unchecks (Criterion 1.7: the combination must be unreachable, and clearing is visible not silent).
- Leaving an item-less segment for All/Item exchange/Auction restores the default: the patch sets `ships_only: undefined` — REMOVING the key, because `parseContractSearch` reads absence as true and "cleared" is stored as explicit `false` (Criterion 1.9; recon: `update()` spreads `prev`, so restoring requires an explicit `undefined` in the patch, which TanStack Router drops from the URL).
- The courier count reads its true total while ships-only is active because the server lifted it (Criterion 1.8) — the spec's `Courier (0)`-flips-to-`Courier (115)` defect is the thing the e2e spec pins.
- Heading/title logic gains the third axis: segment label wins over the ships-only pair when a segment is active (`'Courier Contracts'` etc.); `default-view.spec.ts`'s two assertions stay green because the default state is unchanged.
- [ ] **Step 1: Component tests first** (`pages.test.tsx` style, via `renderApp` + captured fetch calls): selecting Courier issues a request with `contract_type=courier` and NO `is_ship_contract`; the URL shows `ships_only=false`; returning to All removes both params; counts render from the fixture's `segment_counts`; loan-by-URL renders rows and no fifth tab.
- [ ] **Step 2: e2e `segments.spec.ts`** (fixture lane, both projects): the wire assertions (TEST-5 — assert the captured `params`), the 1.7/1.9 checkbox choreography, count labels, URL shareability (deep-load `/contracts?contract_type=courier&ships_only=false` restores the segment).
- [ ] **Step 3:** Implement; all lanes green; extend `a11y.test.tsx` with a segments-active axe case.
- [ ] **Step 4:** Update `filters.spec.ts:176-185`'s clear-filters URL enumeration with the new params (Global Constraint 24).
- [ ] **Step 5: Commit** — `feat(web): segment the contract list by type with honest counts`

### Task C4: Per-segment column sets — auction and courier rows (Criteria 4.2/4.3, 5.3/5.4/5.6/5.7, §8 axes)

**Files:** `ContractTable.tsx` (column sets), `format.ts` (a `formatRewardPerVolume` helper), `ContractsPage.tsx` (passes the active segment), tests + `e2e/segments.spec.ts` extensions

**Binding column sets (axis 1 selects columns; §8):**
- **All / Item exchange** (default, unchanged): Ship/Contract · Type · Price · Location · Time left · Issued.
- **Auction:** Ship/Contract · Starting bid (`price`) · **Buyout** (`buyout`, sortable; `—`-distinct copy `"No buyout"` when null — Criterion 4.3, textual not blank) · Location · Time left · Issued.
- **Courier:** Contract (primary_label) · **Route** (`start_location_name → end_location_name`; an unresolved endpoint renders the literal text `Unknown structure` — never blank, never the raw id, never a fabricated name; §8) · **Reward** · **Collateral** · **Volume** · **Reward/m³** (`reward_per_volume`, sortable; null renders `—`) · **Deadline** (`days_to_complete` as `Nd`; null renders `—`) · Time left.
- No distance figure of any kind on courier rows (§8 — reward/m³ is the only normalization; nothing may read as near/far).
- The courier segment shows the coverage statement (Criterion 5.7): a one-line note above the table sourced from the envelope — see C5.
- [ ] **Step 1: Component tests first:** auction fixture with and without buyout (exact cell text incl. `"No buyout"`); courier fixture with an unresolved destination asserting `Unknown structure`; reward/m³ formatted; sort toggles on Buyout and Reward/m³ navigate with the right `sort_by`.
- [ ] **Step 2:** Implement as additional `Column[]` sets selected by the active segment; the frame component stays one (spec §8 "shared frame").
- [ ] **Step 3:** All lanes green incl. future-clock; extend the sorting spec for one new sortable column (header rename hazard: `sorting.spec.ts` enumerates header names — extend, don't repurpose).
- [ ] **Step 4: Commit** — `feat(web): type-aware column sets for auction and courier segments`

### Task C5: Freshness + coverage-honest empty states (Criteria 7.1–7.4, 5.7)

**Files:** `ContractsPage.tsx`, `ContractDetailPage.tsx`, a small `coverageLabel` helper in `format.ts`, `regions.ts` consumers, tests

- **`last_seen_at` surfacing (7.1):** the list header area (next to the results count live region) renders `Data as of {timeAgo-style relative}` from the envelope's `coverage.as_of`; the detail page renders `Last seen {relative}` from the row's `last_seen_at`. Relative rendering uses a `now`-injectable formatter (TEST-3/17 — literal-vs-literal in unit tests, clock-anchored fixtures).
- **Uncovered-region empty state (7.2/7.3):** when a `region_ids` filter includes ids NOT in `coverage.ingested_region_ids` and the result is empty, the empty state says which selected regions are not ingested (names joined from the static `regions.ts` map — it is a flat array; build a `Map` once) and distinguishes "not covered" from "nothing matched". The existing loosen-your-filters copy remains for genuinely-covered empties. `states.spec.ts:99` asserts the old copy EXACTLY — extend that spec for the new branch rather than editing the old assertion.
- **Courier coverage line (5.7):** `Couriers originating in {covered region names} only.`
- [ ] **Step 1: Tests first** (component: both empty-state branches, as-of rendering under injected clock; e2e: uncovered-region deep link shows the explanation). **Step 2: Implement. Step 3: lanes green. Step 4: Commit** — `feat(web): surface data freshness and region coverage honestly`

### Task C6: Phase C gate

- [ ] Full frontend verification suite (all five lanes), three review rounds (lenses: criteria 1.x checklist one by one; a11y — keyboard/AT on every new control; TEST-17 — no literal dates entered the fixtures), codex review of PR-C (backgrounded), address, merge per protocol, update banners.

---

# Phase D — Frontend item-level surface (branch `feat/f008-item-surface` off merged `dev`, PR-D, `Routine`)

**Execution Status:** ⬜ NOT STARTED

Everything gated on the taxonomy readiness signal (decision-log D1): the cascading taxonomy filter, ME/TE/runs controls, blueprint columns, composition rendering, and the want-to-buy split. The gate is data-driven — this PR merges to `dev` whenever it is done; production shows the controls only when `GET /contracts/taxonomy` reports `coverage: "complete"` (which follows the resweep automatically).

### Task D1: Taxonomy hook + gate plumbing

**Files:** Create `src/features/contracts/hooks/useTaxonomy.ts`; modify `FilterRail.tsx`
- `useTaxonomy`: `useQuery({ queryKey: ['contracts', 'taxonomy'], staleTime: 5 * 60_000 })` against `GET /contracts/taxonomy` (near-static per session).
- Gate: while `coverage === "partial"` (or the query errors), the item-level controls region renders a single quiet line — `Item filters are still indexing.` — instead of the controls. No spinner, no retry buttons; the state is expected for ~80 minutes after a release and permanently in a fresh dev boot's first minutes.
- [ ] Tests first (both gate branches), implement, lanes green, commit — `feat(web): read the taxonomy option list and its readiness signal`

### Task D2: Cascading category → group filter with type-ahead (Criteria 3.2–3.4, 12)

**Files:** Create `src/features/contracts/components/TaxonomyFilter.tsx`; modify `FilterRail.tsx`, tests, `e2e/taxonomy.spec.ts` (new)

**Binding shape:** clone the region-list pattern (`FilterRail.tsx:112-148` — fieldset + legend + count chip + `<Input type="search">` + scroll-capped `CheckboxField` list + curly-quoted no-match line). Two stacked fieldsets: Category (full list), Group (**scoped to the selected categories**, type-ahead filtered client-side over the flat `groups` list — §17.6 is flat precisely so this needs no refetch). Changing category selection prunes now-invalid group selections from the URL in the same navigation, and the group legend announces the scoping (`aria-describedby` text: `Groups within the selected categories` — Criterion 12's announcement requirement, met with plain text not ARIA invention).
- [ ] Component tests first (cascade scoping, type-ahead filtering, URL round-trip, pruning on category change), e2e (wire assertions: `category_id`/`group_id` repeated params; deep-link restore), axe case with the controls open, implement, lanes green, commit — `feat(web): cascading dogma category and group filters`

### Task D3: ME/TE/runs controls + saved searches (Criteria 2.2/2.3/2.5)

**Files:** `FilterRail.tsx` (six bounded numeric inputs in a Blueprint fieldset, gated with the rest), `SaveSearchControl.tsx` (`toSavedSearchParameters` gains all nine new params), tests, `e2e/filters.spec.ts` additions
- [ ] Tests first (each control wires to its param; sub-zero junk tolerated per the existing `toNonNegativeNumber` contract; saving a search with taxonomy+ME params round-trips through `SavedSearchesPage.apply()`), implement, lanes green, commit — `feat(web): blueprint stat filters and richer saved searches`

### Task D4: Blueprint columns + composition + want-to-buy split (Criteria 2.2, 6.1–6.4, 8.1, §8 discriminator)

**Files:** `ContractTable.tsx` (BPC cells in the item-exchange/auction column sets), `ContractDetailPage.tsx` (composition + offered/requested split), `format.ts` (`formatComposition`), tests

**Binding rendering:**
- BPC cells (Runs · ME · TE) render values when `blueprint_summary.copy_count === 1`; render `{copy_count} BPCs` linking to the detail when >1; empty when absent (§8 discriminator, restated: exactly one offered BPC ⇒ values, several ⇒ count, none ⇒ empty).
- Composition cell (multi-item rows): from `composition.categories` — `3 Modules · 1 Blueprint · 2 other` (client formats: top two categories by count, remainder bucketed as `other`, the NULL-category entry always in `other`; counts are item rows — never quantities). Plus `total_volume` via `formatIsk`-style m³ formatting.
- Detail page: **Offered** and **Requested** item lists as two separately-headed sections, never merged (8.1); requested side renders even when enrichment left names unresolved (the A7 fix guarantees a route back).
- [ ] Component tests first (all three BPC states; composition formatting incl. the other-bucket; the split with a WTB fixture), axe case, implement, lanes green, commit — `feat(web): blueprint stats, composition summaries, and the want-to-buy split`

### Task D5: Phase D gate + feature-level verification

- [ ] All five frontend lanes green; e2e fixture lane covers: segments, taxonomy cascade, ME window filter, BPC column states, WTB split.
- [ ] **Full-stack local verification** (the one end-to-end proof before the morning report): start deps (already up), run the backend (`pdm run dev` — this worktree does not wipe; expect the dev-limit 100-contract ingest incl. the taxonomy cache fill), `npm run dev`, then drive the real UI against real ESI-ingested data via the browser tools: default view unchanged; segments show counts; a courier row shows a route; after enrichment completes, taxonomy controls appear (dev corpus is small so coverage flips quickly). Screenshot the segmented views for the morning report.
- [ ] Three review rounds (lenses: spec §3 acceptance criteria checklist item by item; §8 rendering rules; interaction coverage), codex review, address, merge, update banners.

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
