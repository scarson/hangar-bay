# Ingestion Correctness & Steady-State Cost Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stop re-fetching item data the database already holds, and make "enrichment succeeded" mean it actually did — taking a steady-state ingestion run from ~77 minutes to seconds.

**Architecture:** EVE public contracts are immutable once issued, so each contract's items need fetching exactly once. Today `_fetch_item_rows` re-fetches all ~46,000 every run. This plan makes enrichment idempotent and skippable: fix what "success" means, repair rows that were wrongly marked successful, add a version stamp so a future enrichment bug can re-queue the corpus deliberately, then skip already-enriched contracts. Design: `docs/audits/m5-recon/ingestion-clean-sheet-design.md` (migration steps 1–3, plus the limiter-correctness fix).

**Tech Stack:** FastAPI, SQLAlchemy 2.0 async, Alembic, PostgreSQL 18, httpx, pytest.

---

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

**Overall:** 🚧 In progress — claimed 2026-07-27T02:58Z on branch `claude/m5-plan-a-ingestion` (subagent-driven execution).

| Phase | Status | Ship SHA(s) | Notes |
|---|---|---|---|
| 1 — Make "enriched" mean it | ✅ Implemented on branch, review clean | d7db161, e70fa48, 39a8cf4 (T1) · 88670e4, da5b580, 8b29950 (T2) · d068fa2, ae68ca9, b0e47d4, b663872 (T3) | 2026-07-27; 3-round batch review clean; PR pending with Phases 2–3 |
| 2 — Skip what we already have | 🚧 In progress | — | Tasks 4–5 |
| 3 — Rate-limit honesty | ⬜ Not started | — | Task 6; independent |

### Deviations

- **(Task 4, 2026-07-27) `ix_contracts_enrichment_queue` is NOT created.** The plan (and design) specified a composite index on `(item_processing_status, enrichment_version)`. Review measured Task 5's actual predicate on a 46k-row replica: Postgres resolves the per-batch skip query through the contracts **PK** with the two columns as a filter (1.1 ms per 1000-id chunk); the composite index is never consulted — `(COMPLETED, current-version)` covers ~97% of rows, so it has no selectivity to offer — and a future "NOT (COMPLETED AND current)" queue scan can't use a btree either. Carrying it would add a second write target on the hottest ingestion column for nothing. Dropped from both the migration and the model. If Plan B's discovery/enrichment split needs a queue scan, the existing single-column `ix_contracts_item_processing_status` (baseline) serves a `PENDING_ITEMS` scan.

### Discoveries

- **(Task 1 review, 2026-07-27)** A silent-truncation path survives the `all_pages=True` fix: if a mid-walk item page returns 304 while its cached body was evicted from Valkey, `_read_etag_cached_page` returns `[]` and `_last_page_reached`'s empty-page check fires *before* the `X-Pages` check (`esi_client_class.py` ~lines 132–186), so the walk stops early and returns a short non-empty list with no exception — Task 2's zero-item guard cannot see it, and fetch-once would make it permanent. Requires memory-pressure eviction between the ETag key surviving and the data key dying (low probability, real mechanism). **Dissolved entirely by the parked Plan B decision to remove the ETag cache on item pages** (see Out of scope) — that decision now carries correctness weight, not just cost weight.
- **(Task 2 review, 2026-07-27)** The test suite's model of a 304 has diverged from production: `ESINotModifiedError` is defined (`core/exceptions.py`) and caught (`background_aggregation.py` `_fetch_item_rows`) but **raised nowhere in production code** — real 304s are resolved inside `get_esi_data_with_etag_caching` (cache hit → cached body; evicted body → `[]`). Tests that stub `get_contract_items` with `side_effect=ESINotModifiedError()` (e.g. `test_reingestion_with_unmodified_items_keeps_ship_flag`) model a shape the client never produces, so the real-world trigger of Task 2's zero-item guard (304 + evicted body → `[]`) is unmodelled in tests. Route to Plan B alongside the ETag-cache decision — if the item-page ETag cache is removed, both the dead exception path and the divergent test model should be cleaned up with it.
- **(Task 3 review, 2026-07-27)** Two accepted risks, recorded deliberately. (a) The repair migration's predicate has no automated regression test — CI executes it only against an empty database (`tests/conftest.py` runs `alembic upgrade head`), which exercises nothing. Accepted because applied migrations are run-once artifacts: after production applies `d5f83b17c0ae`, future edits to it are inert, so regression protection has near-zero value; the seeded scratch-DB verification (three-case seed, exact-row assertions, done independently twice) is the evidence of record. (b) Alembic's `env.py` wraps an entire `upgrade head` invocation in ONE transaction, so when the Phase 1 and Phase 2 migrations deploy together, the repair UPDATE's row locks are held across Task 4's ~44.5k-row backfill — a larger contention window with a concurrent ingestion run than either migration alone. Mitigated by the existing rule (time deploys just after an ingestion run completes) and bounded by `lock_timeout='30s'` → failed pre-deploy aborts the deploy, which is the intended failure mode. Verified empirically in review: `lock_timeout` does bound row-lock waits, and a deadlock can also choose the ingestion run as victim (acceptable: the run retries next tick).
- **(Task 3 re-review, 2026-07-27)** The widely-cited **"3.1%" zero-item rate was an arithmetic slip**: the raw measurement is 15 of a 384-contract sample, which is **~3.9%** (3.1% would imply ~12/384). Raw counts are the record of truth. Corrected in this plan, the handoff, the clean-sheet design, and the migration comments; left as-is in immutable history (Task 2's shipped commit message says 3.1%) and in the review-record docs (`clean-sheet-review-fable.md`), which quote the era's number. No decision changes: the guard threshold (25%) has ~6.4× headroom either way.
- **(Phase 1 batch review, 2026-07-27)** Three mechanism facts verified and worth not re-deriving. (a) **Re-queued rows cannot duplicate items on re-fetch:** `ContractItem.record_id` is the ESI-supplied sole PK and `bulk_upsert` does `ON CONFLICT (record_id) DO UPDATE`, so a truncated-then-repaired contract's re-fetch updates its first 1,000 rows in place and inserts the rest. (b) **The migration→cutover window self-heals in both release shapes:** old code re-minting a flipped listed row is repaired by the new code's next cycle (status is not yet read as a gate), and under Phase 1+2 together a window re-mint stays `enrichment_version=0` (old code cannot write that column), so the skip predicate re-fetches it. (c) **Withhold-not-demote is deliberate and load-bearing:** `_update_item_processing_status` never demotes an existing COMPLETED row, nothing in ingestion deletes `contract_items`, so `COMPLETED ⇒ items persisted` holds even when a later run returns zero items for an already-enriched contract — the invariant Phase 2's skip depends on. Also live-verified: ESI 304 responses carry `X-Pages` on both the region and items endpoints, so the multi-page walk terminates correctly across a deploy's ETag reuse.
- **(Task 4 review, 2026-07-27)** Latent test-ordering hazard: `alembic/env.py` calls `logging.config.fileConfig`, which disables existing loggers process-wide, so running `tests/test_migrations.py` BEFORE `tests/services/test_background_aggregation.py` breaks 8 caplog-based tests. Default collection order runs `services/` first, so the suite is green today — but any reordering plugin or targeted-subset run in the wrong order will hit it. Pre-existing, not introduced by this plan. **Fixed on dev 2026-07-27 via PR [#93](https://github.com/scarson/hangar-bay/pull/93)** (merge `9e2e430`, both fileConfig call sites pass `disable_existing_loggers=False`); this branch predates the fix, which arrives at merge.
- **(Phase 2 batch review, 2026-07-27)** The version-bump resweep runbook, traced with real numbers: a bump's next run is ~80 min, outliving the 65-min aggregation lock TTL. What actually serializes runs is **APScheduler `max_instances=1`** (safe while run < 2× interval), not the lock — so the end-of-resweep "Aggregation lock token mismatch on release" warning is expected then, a deploy or scale-out mid-resweep re-opens the concurrent-runner window, and shortening the scheduler interval requires re-deriving that margin (the TTL shrinks in lockstep). Recorded in the `ENRICHMENT_VERSION` constant's comment. Also verified: no path can produce `(COMPLETED, current-version)` for a zero-item contract, so the skip can never protect an empty one; the stamp UPDATE has no status predicate, so deploy-window rows minted `(COMPLETED, 0)` by old code are re-stamped on the next cycle.
- **(Phase 2 batch review round 2, 2026-07-27)** The `enrichment_version` backfill migration is accepted without automated coverage (same run-once rationale as the repair migration), and its failure modes are asymmetric: **too-narrow** (WHERE mismatch / literal drift) costs one full resweep, self-heals in a single run, and announces itself in the "0 skipped" log line; **too-broad** (stamping non-COMPLETED rows) is harmless *only because* the skip predicate's status arm re-fetches them anyway. That interlock is why the status arm and the never-stamp-INCOMPLETE property are now pinned by dedicated tests — the acceptance is sound because of them, not luck.

---

## How to execute this plan

Tasks are **sequential in a single worktree**, in the order given. Tasks 2, 4 and 5 all modify
`background_aggregation.py` and Tasks 1 and 6 both modify `esi_client_class.py`; later snippets
presuppose earlier edits. Do not dispatch them to parallel agents on separate branches.

Verify the migration chain with `python -m alembic heads` (from `app/backend`, with
`ALEMBIC_CONFIG=src/alembic.ini`), **never by listing filenames** — filenames cannot show
parentage, and a second head only surfaces at `upgrade head` time, in pre-deploy, in production.

## Mandatory reading before any task

```
BEFORE starting work:
1. Invoke /superpowers:test-driven-development
2. Read docs/pitfalls/testing-pitfalls.md and docs/pitfalls/implementation-pitfalls.md
Follow TDD: write failing test → run it and SEE it fail → implement → verify green.
```

Pitfalls that bite specifically in this plan:
- **TEST-14** — `tests/api/test_contracts.py` has a file-level `pytest.mark.vcr`; a test added there replays a cassette and passes even with the behavior deleted. Put API-level tests in `tests/api/test_contract_filters.py`.
- **TEST-12** — mutation-verify every test: break the named behavior, confirm red, revert. Revert with a `cp` snapshot, never `git checkout --`, which discards uncommitted work.
- **TEST-4** — pagination tests must cross a page boundary.
- **DEPLOY-1** — migrations run as Render's pre-deploy command; both migrations here set `lock_timeout`.

Test environment (the backend suite needs a database):

```bash
cd app/backend
ESI_USER_AGENT="hangar-bay-tests/1.0 (local dev)" \
DATABASE_URL="postgresql+asyncpg://hangar_bay_user:hangar_bay_password@localhost:5432/hangar_bay_dev" \
CACHE_URL="redis://localhost:6379/0" CACHE_URL_TESTS="redis://localhost:6379/1" \
DATABASE_URL_TESTS="postgresql+asyncpg://hangar_bay_user:hangar_bay_password@localhost:5432/hangar_bay_test_wlttl" \
.venv/bin/pytest -q
```

Do NOT use `env VAR=x` with a shell variable holding the pairs — zsh does not word-split it and only the first pair survives.

---

## Phase 1 — Make "enriched" mean it

**Execution Status:** ✅ IMPLEMENTED on `claude/m5-plan-a-ingestion` 2026-07-27; per-task spec+quality reviews plus a 3-round batch review (holistic / adversarial-tests / fresh-eyes), all findings fixed, final round clean. Ships in the single Plan A PR (pending).

Tasks 1–3 **MUST reach production in a single release.**

Precisely: separate merges to `dev` are fine. What must be atomic is the `dev` → `main`
**publication** — repairing rows in production before the invariant is also in production
leaves a window where the old code re-mints the same bad rows.

**Enforcement, not just assertion:** Phase 1 ships as **one PR** containing Tasks 1–3. If it
is ever split, no publication PR may run between the first and last Phase-1 merge. State the
`## Merge classification` in that PR body as **Review — schema migration and data integrity**
(a repo-mandated heading, and a genuine Review trigger).

### Task 1: Fetch every page of a contract's items

**Why:** `get_contract_items` calls the ETag helper with the default `all_pages=False`, so any contract with more than 1,000 items is silently truncated to page 1. Its sibling `get_public_contracts` correctly passes `all_pages=True`. Latent today (a 384-contract production sample showed max 422 items, none at 1,000) but fetch-once in Phase 2 would make truncation permanent and unrepairable.

**Files:**
- Modify: `app/backend/src/fastapi_app/core/esi_client_class.py` (`get_contract_items`)
- Test: `app/backend/src/fastapi_app/tests/core/test_esi_client.py`

- [x] **Step 1: Write the failing test**

Append to `app/backend/src/fastapi_app/tests/core/test_esi_client.py`. **Use that module's
existing doubles — `_etag_response` (line 88) and `_etag_client` (line 110). It has no
`esi_client` or `httpx_mock` fixture; `test_pagination_follows_x_pages` (line 360) is the
template this mirrors.**

```python
async def test_get_contract_items_fetches_every_page():
    """A contract with more items than one page must return all of them.

    TEST-4: a single-page fixture cannot detect truncation, so this crosses the
    boundary. Truncation is silent — the caller sees a short, plausible list.
    """
    page_1 = _etag_response(
        json_data=[{"record_id": 1, "type_id": 587}],
        content=b'[{"record_id": 1, "type_id": 587}]',
        headers={"ETag": "etag-p1", "X-Pages": "2"},
    )
    page_2 = _etag_response(
        json_data=[{"record_id": 2, "type_id": 588}],
        content=b'[{"record_id": 2, "type_id": 588}]',
        headers={"ETag": "etag-p2", "X-Pages": "2"},
    )
    get_mock = AsyncMock(side_effect=[page_1, page_2])
    client = _etag_client(get_mock)

    items = await client.get_contract_items(999)

    assert [i["record_id"] for i in items] == [1, 2]
    assert get_mock.await_count == 2
```

- [x] **Step 2: Run the test and watch it fail**

```bash
cd app/backend && .venv/bin/pytest src/fastapi_app/tests/core/test_esi_client.py::test_get_contract_items_fetches_every_page -v
```
Expected: FAIL — only `record_id` 1 is returned, because the walk stops after page 1.

- [x] **Step 3: Implement**

In `esi_client_class.py`, change `get_contract_items`:

```python
    async def get_contract_items(self, contract_id: int) -> list[dict[str, Any]]:
        """Fetches all items for a specific public contract.

        all_pages=True is load-bearing: contracts can exceed one 1,000-item page, and
        the default (False) stops after page 1, truncating silently. Enrichment is
        fetch-once, so a truncated result would be permanent.
        """
        path = f"/v1/contracts/public/items/{contract_id}/"
        return await self.get_esi_data_with_etag_caching(path, all_pages=True)
```

- [x] **Step 4: Verify green, then mutation-verify**

```bash
cd app/backend && .venv/bin/pytest src/fastapi_app/tests/core/test_esi_client.py -v
```
Then revert `all_pages=True` to the default, confirm the new test goes red, and restore from a `cp` snapshot (TEST-12).

- [x] **Step 5: Commit**

```bash
git add app/backend/src/fastapi_app/core/esi_client_class.py app/backend/src/fastapi_app/tests/core/test_esi_client.py
git commit -m "fix(api): fetch every page of a contract's items

get_contract_items used the default all_pages=False while get_public_contracts
passes True, truncating any contract past 1,000 items to page 1. Latent today
(sampled max 422 items) but permanent once enrichment becomes fetch-once."
```

### Task 2: An empty item result is a failure, not a success

**Why:** `_update_item_processing_status` computes `completed = processed - incomplete`, where `incomplete` only contains contracts whose items lacked a `type_name`. A contract that returned **zero** items contributes nothing to `all_items`, so it falls into `completed` and is marked `COMPLETED`. An `item_exchange`/`auction` contract cannot legitimately have zero items — measured at **15 of a 384-contract production sample (~3.9%)**. Under Phase 2's skip-known these rows become permanently invisible.

**Files:**
- Modify: `app/backend/src/fastapi_app/services/background_aggregation.py` (`_update_item_processing_status`)
- Test: `app/backend/src/fastapi_app/tests/services/test_background_aggregation.py`

- [x] **Step 1: Write the failing test**

```python
async def test_contract_returning_no_items_is_not_marked_completed(db_session: AsyncSession):
    """An item_exchange contract with zero items is impossible — the fetch failed or
    returned an evicted-cache empty page. Marking it COMPLETED makes the failure
    permanent once skip-known lands, so it must stay retryable."""
    service = _make_service()
    service.esi_client.get_contract_items = AsyncMock(return_value=[])

    await service._process_contracts(db_session, [_ship_contract_dict(930001)])
    await db_session.flush()

    row = (
        await db_session.execute(select(Contract).where(Contract.contract_id == 930001))
    ).scalar_one()
    assert row.item_processing_status != "COMPLETED"
```

- [x] **Step 2: Run the test and watch it fail**

```bash
cd app/backend && .venv/bin/pytest src/fastapi_app/tests/services/test_background_aggregation.py::test_contract_returning_no_items_is_not_marked_completed -v
```
Expected: FAIL — status is `COMPLETED`.

- [x] **Step 3: Implement**

In `_update_item_processing_status`, replace the two set computations:

```python
        incomplete_contract_ids = {
            item["contract_id"] for item in all_items if item.get("type_name") is None
        }
        # A contract that produced NO items cannot have succeeded: item_exchange and
        # auction contracts always carry at least one item. Leaving it out of the
        # COMPLETED set keeps its status at PENDING_ITEMS so a later run retries it —
        # which is what makes fetch-once safe to adopt in Phase 2.
        contracts_with_items = {item["contract_id"] for item in all_items}
        empty_contract_ids = processed_contract_ids - contracts_with_items
        completed_contract_ids = (
            processed_contract_ids - incomplete_contract_ids - empty_contract_ids
        )
```

Then, after the existing `ENRICHMENT_INCOMPLETE` logging block, add:

```python
        if empty_contract_ids:
            logger.warning(
                f"{len(empty_contract_ids)} contracts returned zero items and were left "
                "PENDING_ITEMS for retry (an item_exchange/auction contract cannot be empty)."
            )
```

**Do NOT** add a new status value — reusing `PENDING_ITEMS` keeps the queue definition in Task 5 to one predicate.

- [x] **Step 4: Verify green, run the full suite, mutation-verify**

```bash
cd app/backend && .venv/bin/pytest -q
```
Mutation: restore `completed = processed - incomplete`, confirm the new test reddens, restore from a `cp` snapshot.

- [x] **Step 5: Commit**

```bash
git add app/backend/src/fastapi_app/services/background_aggregation.py app/backend/src/fastapi_app/tests/services/test_background_aggregation.py
git commit -m "fix(api): treat a zero-item enrichment result as failure, not success

An item_exchange/auction contract cannot legitimately have zero items, but such
contracts landed in the COMPLETED set and stopped being retried. Measured at 3.1%
of a production sample. They now stay PENDING_ITEMS."
```

### Task 3: Repair rows already marked wrongly

**Why:** Task 2 stops the bleeding; existing rows are still wrong. This MUST be in the same release as Task 2.

**Files:**
- Create: `app/backend/src/alembic/versions/<rev>_requeue_falsely_completed_contracts.py`

- [x] **Step 1: Generate the revision id and find the current head**

```bash
cd app/backend && ls src/alembic/versions/
```
Use the latest revision as `down_revision`. At time of writing that is `c7e2a9b41d36` (contracts.last_seen_at) — **verify**, since PR #91 may have merged since.

- [x] **Step 2: Write the migration**

```python
"""requeue falsely-completed contracts

Contracts marked COMPLETED while holding zero items never actually enriched; a
zero-item item_exchange/auction contract is impossible. Also re-queues item counts
at an exact multiple of 1,000 — the signature of the page-1 truncation fixed in the
same release. Both are permanent once enrichment becomes fetch-once.

Revision ID: <rev>
Revises: c7e2a9b41d36
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "<rev>"
down_revision: Union[str, None] = "c7e2a9b41d36"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

REQUEUE = sa.text("""
    UPDATE contracts c
       SET item_processing_status = 'PENDING_ITEMS'
     WHERE c.item_processing_status = 'COMPLETED'
       AND (
             NOT EXISTS (SELECT 1 FROM contract_items i WHERE i.contract_id = c.contract_id)
          OR (SELECT count(*) FROM contract_items i WHERE i.contract_id = c.contract_id) % 1000 = 0
           )
""")

COUNT_EMPTY = sa.text("""
    SELECT count(*) FROM contracts c
     WHERE c.item_processing_status = 'COMPLETED'
       AND NOT EXISTS (SELECT 1 FROM contract_items i WHERE i.contract_id = c.contract_id)
""")

COUNT_TRUNCATED = sa.text("""
    SELECT count(*) FROM contracts c
     WHERE c.item_processing_status = 'COMPLETED'
       AND (SELECT count(*) FROM contract_items i WHERE i.contract_id = c.contract_id) % 1000 = 0
       AND EXISTS (SELECT 1 FROM contract_items i WHERE i.contract_id = c.contract_id)
""")


def upgrade() -> None:
    """Upgrade schema."""
    # Pre-deploy command on a live database; fail fast rather than queue behind
    # the outgoing instance's ingestion transaction (DEPLOY-1 step class).
    op.execute("SET lock_timeout = '30s'")
    bind = op.get_bind()
    # Logged deliberately: the rate is measured (15 of 384, ~3.9%) but the mechanism behind it is
    # still inferred, and this is the one cheap opportunity to see the real split.
    empty = bind.execute(COUNT_EMPTY).scalar()
    truncated = bind.execute(COUNT_TRUNCATED).scalar()
    print(f"[requeue] zero-item COMPLETED contracts: {empty}")
    print(f"[requeue] 1000-multiple (truncation suspect) contracts: {truncated}")
    bind.execute(REQUEUE)


def downgrade() -> None:
    """Downgrade schema."""
    # Irreversible by nature: the prior status was wrong, and re-marking these
    # COMPLETED would restore the defect. Re-enrichment is the recovery path.
    pass
```

- [x] **Step 3: Verify the migration on a scratch database**

```bash
cd app/backend
docker exec hangar_bay_postgres psql -U hangar_bay_user -d hangar_bay_dev \
  -c "DROP DATABASE IF EXISTS hb_mig_repair;" -c "CREATE DATABASE hb_mig_repair OWNER hangar_bay_user;"
ESI_USER_AGENT="t/1.0" CACHE_URL="redis://localhost:6379/0" \
DATABASE_URL="postgresql+asyncpg://hangar_bay_user:hangar_bay_password@localhost:5432/hb_mig_repair" \
ALEMBIC_CONFIG=src/alembic.ini .venv/bin/python -m alembic upgrade head
```
Expected: runs clean. **An empty database prints 0/0 and the UPDATE matches no rows — that
verifies nothing.** Seed the cases first, then assert only the right rows flipped:

```bash
docker exec hangar_bay_postgres psql -U hangar_bay_user -d hb_mig_repair <<'SQL'
-- one wrongly-COMPLETED (zero items), one truncation suspect (exactly 1000 items),
-- one legitimately good row that MUST be left alone.
INSERT INTO contracts (contract_id, price, collateral, status, type, issuer_id,
  issuer_corporation_id, for_corporation, date_issued, date_expired, item_processing_status)
VALUES (1, 1, 0, 'unknown', 'item_exchange', 1, 1, false, now(), now() + interval '5 days', 'COMPLETED'),
       (2, 1, 0, 'unknown', 'item_exchange', 1, 1, false, now(), now() + interval '5 days', 'COMPLETED'),
       (3, 1, 0, 'unknown', 'item_exchange', 1, 1, false, now(), now() + interval '5 days', 'COMPLETED');
INSERT INTO contract_items (record_id, contract_id, type_id, quantity, is_included, is_singleton)
SELECT g, 2, 587, 1, true, false FROM generate_series(1, 1000) g;
INSERT INTO contract_items (record_id, contract_id, type_id, quantity, is_included, is_singleton)
VALUES (100001, 3, 587, 1, true, false);
SQL
```

Re-run the migration, then assert:

```bash
docker exec hangar_bay_postgres psql -U hangar_bay_user -d hb_mig_repair -tAc \
  "SELECT contract_id, item_processing_status FROM contracts ORDER BY contract_id;"
```
Expected: `1|PENDING_ITEMS`, `2|PENDING_ITEMS`, `3|COMPLETED`. If row 3 flipped, the
predicate is over-broad and would re-enrich the entire corpus.

- [x] **Step 4: Commit**

```bash
git add app/backend/src/alembic/versions/
git commit -m "fix(api): re-queue contracts falsely marked COMPLETED

Zero-item COMPLETED rows never enriched, and 1000-multiple item counts are the
truncation signature fixed in this release. Ships with the invariant, not after
it: repairing first leaves a window where the old code re-mints the same rows."
```

```
After completing Phase 1:
Review the batch from multiple perspectives. Minimum 3 review rounds.
If round 3 still finds issues, keep going until clean.
```

---

## Phase 2 — Skip what we already have

**Execution Status:** 🚧 IN PROGRESS — claimed 2026-07-27, branch `claude/m5-plan-a-ingestion`

### Task 4: Add `enrichment_version`

**Why:** Fetch-once removes an accidental safety net. The refetch-everything loop has silently repaired two real enrichment bugs in this repo's history (`is_ship_contract` never set; `is_blueprint_copy` never mapped). A version stamp makes that recovery deliberate: bumping a constant re-queues the corpus through the same machinery.

**Files:**
- Modify: `app/backend/src/fastapi_app/models/contracts.py`
- Modify: `app/backend/src/fastapi_app/services/background_aggregation.py`
- Create: `app/backend/src/alembic/versions/<rev>_contracts_enrichment_version.py`
- Test: `app/backend/src/fastapi_app/tests/services/test_background_aggregation.py`

- [x] **Step 1: Write the failing test**

```python
async def test_successful_enrichment_stamps_the_current_version(db_session: AsyncSession):
    """The version stamp is what lets a future enrichment bug re-queue the corpus
    deliberately, replacing the refetch loop's accidental self-healing."""
    service = _make_service()
    service.esi_client.get_contract_items = AsyncMock(
        return_value=[{"record_id": 71, "type_id": 587, "quantity": 1, "is_included": True}]
    )
    service.esi_client.get_universe_type = AsyncMock(
        return_value={"name": "Rifter", "group_id": 25, "market_group_id": 4}
    )
    service.esi_client.get_universe_group = AsyncMock(
        return_value={"name": "Frigate", "category_id": 6}
    )

    await service._process_contracts(db_session, [_ship_contract_dict(930101)])
    await db_session.flush()

    row = (
        await db_session.execute(select(Contract).where(Contract.contract_id == 930101))
    ).scalar_one()
    assert row.enrichment_version == bg_agg.ENRICHMENT_VERSION
```

- [x] **Step 2: Run and watch it fail** — `AttributeError`/`UndefinedColumn` on `enrichment_version`.

- [x] **Step 3: Add the column**

In `models/contracts.py`, beside `item_processing_status`:

```python
    # Stamped on successful enrichment. Bumping ENRICHMENT_VERSION re-queues the corpus
    # through the normal budgeted path — the deliberate replacement for the refetch
    # loop's accidental self-healing, which this repo has relied on twice.
    enrichment_version: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
```

In `background_aggregation.py`, near the other module constants:

```python
# Bump to re-queue every contract for re-enrichment after an enrichment-logic fix.
ENRICHMENT_VERSION = 1
```

In `_update_item_processing_status`, stamp it alongside `COMPLETED`:

```python
        for chunk in _chunk_ids(completed_contract_ids):
            await db_session.execute(
                update(Contract)
                .where(Contract.contract_id.in_(chunk))
                .values(item_processing_status="COMPLETED", enrichment_version=ENRICHMENT_VERSION)
            )
```

- [x] **Step 4: Write the migration**

> **Deviation applied:** the `create_index`/`drop_index` lines below were NOT shipped — the composite index is never consulted by Task 5's predicate. See Deviations at the top of this plan. Do not re-add it from this snippet.

```python
"""contracts.enrichment_version

Revision ID: <rev>
Revises: <task 3 rev>
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# Alembic reads these MODULE ATTRIBUTES, not the docstring. Omitting them fails with
# "Could not determine revision id" when the file is applied.
revision: str = "<rev>"
down_revision: Union[str, None] = "<task 3 rev>"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    """Upgrade schema."""
    op.execute("SET lock_timeout = '30s'")
    op.add_column(
        "contracts",
        sa.Column("enrichment_version", sa.Integer(), nullable=False, server_default="0"),
    )
    # Backfill already-enriched rows to the CURRENT version. Without this every existing
    # COMPLETED contract mismatches version 1 and the first deploy triggers a full ~46k
    # re-enrichment backfill — the exact cost this plan exists to remove.
    # The literal 1 MUST equal ENRICHMENT_VERSION at ship time. If that constant is
    # bumped before this migration runs, update both together or the backfill stamps
    # a version that no longer matches and re-queues the whole corpus.
    op.execute("UPDATE contracts SET enrichment_version = 1 WHERE item_processing_status = 'COMPLETED'")
    op.create_index("ix_contracts_enrichment_queue", "contracts",
                    ["item_processing_status", "enrichment_version"], unique=False)

def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_contracts_enrichment_queue", table_name="contracts")
    op.drop_column("contracts", "enrichment_version")
```

- [x] **Step 5: Verify green + migration up/down/up, then commit**

```bash
cd app/backend && .venv/bin/pytest -q
git add -A app/backend && git commit -m "feat(api): stamp enrichment_version on successful enrichment

Replaces the refetch loop's accidental self-healing with a deliberate mechanism:
bumping the constant re-queues the corpus. Existing COMPLETED rows are backfilled
to the current version so adopting this does not itself trigger a 46k backfill."
```

### Task 5: Skip contracts already enriched at the current version

**Why:** This is the change that collapses steady-state cost. ~46,000 item fetches per run become ~230/hour of churn.

**Files:**
- Modify: `app/backend/src/fastapi_app/services/background_aggregation.py` (`_process_contracts`, `_fetch_item_rows`)
- Test: `app/backend/src/fastapi_app/tests/services/test_background_aggregation.py`

- [x] **Step 1: Write the failing tests** (two — skip, and version-bump re-queue)

```python
async def test_already_enriched_contracts_are_not_refetched(db_session: AsyncSession):
    """The whole point: public contracts are immutable, so a contract enriched at the
    current version never needs fetching again."""
    service = _make_service()
    service.esi_client.get_contract_items = AsyncMock(
        return_value=[{"record_id": 81, "type_id": 587, "quantity": 1, "is_included": True}]
    )
    service.esi_client.get_universe_type = AsyncMock(
        return_value={"name": "Rifter", "group_id": 25, "market_group_id": 4})
    service.esi_client.get_universe_group = AsyncMock(
        return_value={"name": "Frigate", "category_id": 6})

    await service._process_contracts(db_session, [_ship_contract_dict(930201)])
    await db_session.flush()
    first_call_count = service.esi_client.get_contract_items.await_count

    await service._process_contracts(db_session, [_ship_contract_dict(930201)])
    await db_session.flush()

    assert service.esi_client.get_contract_items.await_count == first_call_count


async def test_bumping_the_enrichment_version_requeues_a_contract(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
):
    """Version bump is the deliberate replacement for accidental self-healing, so it
    must actually re-fetch."""
    service = _make_service()
    service.esi_client.get_contract_items = AsyncMock(
        return_value=[{"record_id": 82, "type_id": 587, "quantity": 1, "is_included": True}]
    )
    service.esi_client.get_universe_type = AsyncMock(
        return_value={"name": "Rifter", "group_id": 25, "market_group_id": 4})
    service.esi_client.get_universe_group = AsyncMock(
        return_value={"name": "Frigate", "category_id": 6})

    await service._process_contracts(db_session, [_ship_contract_dict(930202)])
    await db_session.flush()
    before = service.esi_client.get_contract_items.await_count

    monkeypatch.setattr(bg_agg, "ENRICHMENT_VERSION", bg_agg.ENRICHMENT_VERSION + 1)
    await service._process_contracts(db_session, [_ship_contract_dict(930202)])
    await db_session.flush()

    assert service.esi_client.get_contract_items.await_count == before + 1
```

- [x] **Step 2: Run both and watch them fail** — the first fails because the fetch happens twice.

- [x] **Step 3: Implement the skip**

First add the missing import — `background_aggregation.py` imports `update` but **not** `select`:

```python
from sqlalchemy import select, update
```

(adjust to match the existing import line rather than adding a second one).

Then in `_process_contracts`, after the contract upsert and before item fetching:

```python
        # Public contracts are immutable, so a contract already enriched at the current
        # version never needs re-fetching. This is what turns a corpus-sized run into a
        # churn-sized one. Reads the status column that was written but never read back.
        candidate_ids = [c["contract_id"] for c in contracts]
        already_enriched: set[int] = set()
        for chunk in _chunk_ids(candidate_ids):
            rows = await db_session.execute(
                select(Contract.contract_id).where(
                    Contract.contract_id.in_(chunk),
                    Contract.item_processing_status == "COMPLETED",
                    Contract.enrichment_version == ENRICHMENT_VERSION,
                )
            )
            already_enriched.update(row[0] for row in rows)
        if already_enriched:
            logger.info(f"Skipping item fetch for {len(already_enriched)} already-enriched contracts.")
```

Change the `_fetch_item_rows` signature and call site:

```python
    async def _fetch_item_rows(
        self, contracts: List[dict], already_enriched: set[int] | None = None
    ) -> tuple[list[dict], set[int]]:
```

and inside its loop, immediately after the courier skip:

```python
            if already_enriched and contract["contract_id"] in already_enriched:
                continue
```

Update the call site in `_process_contracts` to pass `already_enriched`.

**Do NOT** add concurrency here. That is a later phase and needs the governor first.

- [x] **Step 4: Verify green, run the full suite, mutation-verify both tests**

Mutation A: delete the `continue` — the skip test reddens.
Mutation B: compare against a hardcoded `1` instead of `ENRICHMENT_VERSION` — the version-bump test reddens.

- [x] **Step 5: Commit**

```bash
git add -A app/backend
git commit -m "perf(api): skip contracts already enriched at the current version

Public contracts are immutable, so their items need fetching exactly once. The
run stops re-fetching ~46,000 contracts every cycle and fetches only churn
(~230/hour measured), taking a steady-state run from ~77 minutes to seconds."
```

```
After completing Phase 2:
Review the batch from multiple perspectives. Minimum 3 review rounds.
If round 3 still finds issues, keep going until clean.
```

---

## Phase 3 — Rate-limit honesty

**Execution Status:** ⬜ NOT STARTED

### Task 6: Treat 420 and 429 as retryable rate-limit signals

**Why:** `_get_with_transient_retry` breaks out of its retry loop on any status `< 500`. That is deliberate for ordinary 4xx ("callers decide what non-5xx statuses mean") but wrong for 420 (ESI's error-limit signal) and 429 (token bucket): both are "come back later," and both currently degrade into per-contract failures that consume error budget. This is a prerequisite for any future concurrency.

**Files:**
- Modify: `app/backend/src/fastapi_app/core/esi_client_class.py` (`_get_with_transient_retry`)
- Test: `app/backend/src/fastapi_app/tests/core/test_esi_client.py`

- [ ] **Step 1: Write the failing test**

```python
async def test_rate_limit_status_is_retried_and_honours_retry_after(monkeypatch):
    """420 and 429 mean 'come back later', not 'this contract failed'. Treating them as
    ordinary 4xx burns error budget and, under concurrency, turns one tripped limit into
    a sustained firehose that still records a successful run.

    Uses this module's _etag_response/_etag_client doubles — there is no httpx_mock here.
    """
    slept: list[float] = []

    async def fake_sleep(seconds):
        slept.append(seconds)

    monkeypatch.setattr("fastapi_app.core.esi_client_class.asyncio.sleep", fake_sleep)
    limited = _etag_response(status_code=429, headers={"Retry-After": "7"})
    ok = _etag_response(
        json_data=[{"record_id": 1, "type_id": 587}],
        content=b'[{"record_id": 1, "type_id": 587}]',
        headers={"ETag": "etag-ok"},
    )
    get_mock = AsyncMock(side_effect=[limited, ok])
    client = _etag_client(get_mock)

    items = await client.get_contract_items(777)

    assert [i["record_id"] for i in items] == [1]
    assert 7 in slept, "Retry-After must drive the wait, not the fixed backoff schedule"
```

- [ ] **Step 2: Run and watch it fail** — the 429 returns immediately and the caller sees a non-JSON/empty result rather than a retry.

- [ ] **Step 3: Implement**

In `_get_with_transient_retry`, replace the break condition:

```python
RATE_LIMIT_STATUSES = frozenset({420, 429})
```
(module level, near the other constants), and inside the loop:

```python
                response = await self.http_client.get(path, headers=headers)
                # 420 (ESI error limit) and 429 (token bucket) mean "come back later", not
                # "this request failed". Treating them as ordinary 4xx burns error budget and
                # records the run as successful over missing data.
                if response.status_code in RATE_LIMIT_STATUSES:
                    last_exception = httpx.HTTPStatusError(
                        f"Rate limited '{response.status_code}'",
                        request=response.request, response=response,
                    )
                    retry_after = response.headers.get("Retry-After")
                    logger.warning(
                        f"ESI rate limited {path} with {response.status_code}; "
                        f"Retry-After={retry_after!r}. Attempt {attempt + 1}/{max_retries}."
                    )
                    if attempt < max_retries - 1:
                        try:
                            await asyncio.sleep(float(retry_after))
                        except (TypeError, ValueError):
                            await asyncio.sleep(backoff_factor * (2 ** attempt))
                    continue
                if response.status_code < 500:
                    last_exception = None
                    break
```

**Do NOT** build the shared governor here — that is a later phase. This task only stops rate-limit responses being misread as per-request failures.

- [ ] **Step 4: Verify green + mutation-verify**

Mutation: remove `420`/`429` from `RATE_LIMIT_STATUSES` — the new test reddens.

```
BEFORE marking this task complete:
If any assertion races or flakes, the fix is deterministic synchronization — NOT
assertion removal or weakening. The monkeypatched sleep above exists so the test
never depends on real time. If synchronization cannot make it reliable, STOP and
raise it rather than shipping a weaker test.
```

- [ ] **Step 5: Commit**

```bash
git add app/backend/src/fastapi_app/core/esi_client_class.py app/backend/src/fastapi_app/tests/core/test_esi_client.py
git commit -m "fix(api): retry 420/429 with Retry-After instead of failing the request

The retry loop broke on any status < 500, so ESI's error-limit (420) and token-bucket
(429) responses degraded into per-contract failures that consumed error budget while
the run still recorded success."
```

```
After completing Phase 3:
Review the batch from multiple perspectives. Minimum 3 review rounds.
If round 3 still finds issues, keep going until clean.
```

---

## Verification before the plan is considered done

- [ ] Full backend suite green with pristine output: `.venv/bin/pytest -q`
- [ ] `flake8` clean on every touched file
- [ ] Both migrations verified up → down → up on a scratch database
- [ ] Every new test mutation-verified, with the failure output recorded in the PR
- [ ] After deploy: a run completes in **under ~5 minutes**, and — the real proof of
      mechanism — **item fetches per run are in the hundreds (churn-sized), not ~46,000**.
      Not "seconds": steady state still performs the 34-page discovery sweep, name
      resolution, a ~46k-row upsert and ~100–250 sequential churn fetches. The fetch-count
      clause is what actually demonstrates skip-known is working. **Expected fetch count is
      `churn + persistent-failure set`, not churn alone:** any listed contract that keeps
      failing enrichment (zero-item results — measured 15/384 ≈ 3.9% — plus
      ENRICHMENT_INCOMPLETE and fetch errors) is retried every run by design. If the
      zero-item rate is a persistent property of those contracts rather than a transient
      artifact, steady state could be **~1,800 fetches/run (~3 min sequential)** — that is
      the retry loop working, NOT skip-known failing. The repair migration's `[requeue]`
      counts at deploy time and the per-run zero-item warning are the evidence that
      separates the two. Read the new "Fetched items for N contracts (M skipped)" log line
      for the direct number.
- [ ] `/ready`'s freshness advances within one cycle

## Out of scope (deliberately)

- **Concurrency** — needs the shared governor first; Plan B.
- **Discovery/enrichment split and `Expires` scheduling** — Plan B.
- **Alert delivery to Discord** — Plan C, and the other half of the user story.
- **Removing the ETag cache on item pages** — correct per the design (a validator on immutable
  read-once data buys nothing and costs pressure in a 25 MB instance), but it interacts with the
  discovery-side caching decisions in Plan B. Keeping it changes nothing about this plan's
  correctness. **Carry it into Plan B explicitly** — it is the kind of parked decision that
  silently evaporates between plans.
