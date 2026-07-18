<!-- ABOUTME: M3 implementation plan — F005 Saved Searches, F006 Watchlists, F007 Alerts on the zero-scope SSO identity. -->
<!-- ABOUTME: Executes docs/superpowers/specs/2026-07-17-m3-account-features-design.md on campaign branch claude/m3-account-features; single Review-classified PR. -->

# M3 Account Features (F005 / F006 / F007) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship Saved Searches, Watchlists, and in-app Alerts/Notifications for authenticated users on the existing zero-scope EVE SSO identity — per-user CRUD under `/me/*`, a periodic watchlist-vs-contracts matcher job, and the three frontend surfaces — as one campaign branch ending in a single `Review`-classified PR to `dev`.

**Architecture:** Three new tables (`saved_searches`, `watchlist_items`, `notifications`) FK'd to `users.id` with a session→row-resolving `get_current_user` dependency guarding every route; a second APScheduler job matching enabled users' watchlists against outstanding contracts with DB-constraint-backed dedup (`ON CONFLICT DO NOTHING` against a partial unique index); frontend features built from existing primitives only (inline disclosures, two-step confirms, a bell that links to a notifications page). Authoritative design: `docs/superpowers/specs/2026-07-17-m3-account-features-design.md` (read it before executing any phase; its §4.5 API table and §6 test strategy are binding).

**Tech Stack:** FastAPI 0.139 / SQLAlchemy 2.0 async / PostgreSQL / Valkey / APScheduler / pytest + pytest-httpx; React 19 / TanStack Router + Query / Tailwind v4 / vitest + Playwright; openapi-typescript codegen chain.

**Plan provenance:** authored in three sections (backend foundations + F005; F006 + F007 backend; frontend + E2E + docs) against a binding naming contract; assembled and reconciled 2026-07-17 (path-param literals normalized to `{search_id}` / `{item_id}` / `{notification_id}`). Recon grounding: `docs/audits/m3-recon/`; adversarial design-review log: design spec Appendix B.

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

---

## Execution Status

**Overall:** Phase 0 shipped; Phase 1 next.

**Baseline (Phase 0, captured against `origin/dev` tip `27dac66`):** backend `pdm run pytest -q` → `220 passed`; frontend `npx vitest run --reporter=dot` → `Test Files 12 passed (12)`, `Tests 62 passed (62)`. Phase 1/2 backend work must never drop the pytest count below 220.

| Phase | Status | Ship SHA(s) | Notes |
|---|---|---|---|
| 0 — Campaign branch setup | ✅ Shipped | `70e8d1a` | Baseline: backend 220 passed, frontend 12 files / 62 tests passed |
| 1 — Backend foundations | ✅ Shipped | `c0c341c` | Task 1.4 recovered via cherry-pick (wrong-cwd executor) |
| 2 — F005 Saved Searches backend | ✅ Shipped | `c4c1dab` | CRUD + full HTTP/schema matrix; backend 257 passed |
| 3 — F006 Watchlist backend | ✅ Shipped | `bd3aa68` | ESIClient.resolve_names + watchlist CRUD add pipeline; backend 285 passed |
| 4 — F007 Notifications backend + matcher | ✅ Shipped | `b6d1e13` | notifications API + `WatchlistMatcherService` + scheduler/lifespan wiring; backend 319 passed |
| 5 — Codegen | ⬜ Not started | — | — |
| 6 — Frontend F005 | ⬜ Not started | — | — |
| 7 — Frontend F006 | ⬜ Not started | — | — |
| 8 — Frontend F007 | ⬜ Not started | — | — |
| 9 — E2E | ⬜ Not started | — | — |
| 10 — Docs, gates, PR | ⬜ Not started | — | — |

### Deviations
- Task 1.4: the original executor performed the work in the wrong checkout (inherited session cwd) and committed there; recovered by cherry-picking `8638582` → `c0c341c` onto the campaign branch. Work verified green in-branch (12 passed incl. the two-session race test). Remaining executors carry an explicit cwd-guard.

- **Design §9.2 — backfilling real `users` rows into the `test_auth_flow` sessions "where trivial" — deliberately deferred.** No reduction in duplication materialized from the migration: the new `authed_user` fixture (Task 1.2) already covers the M3 tests that need a real `users` row, and the existing `test_auth_flow` tests keep their minted-session `user_id` values, which no longer FK anywhere they insert. Recorded here so the design and plan agree with an audit trail rather than a silent drop (round-2 review MINOR-7); mirror this line into the Task 10.2 PR-body deviation notes at ship time.

---
<!-- SECTION A of the M3 implementation plan: Phase 0 (campaign setup) + Phase 1 (backend foundations) + Phase 2 (F005 Saved Searches backend). Authoritative design: docs/superpowers/specs/2026-07-17-m3-account-features-design.md. -->

## Section A — cross-task conventions (read once before executing any task in this section)

These bind every task below and are stated here so no task repeats them:

- **cwd.** Backend commands run from `app/backend` inside the campaign worktree (`.claude/worktrees/m3-account-features`). Test invocations use `pdm run pytest src/fastapi_app/tests/…`. Never run `pdm run dev` during implementation — every backend `.py` save under `--reload` drops+recreates the DB and re-ingests (ENV-2/ENV-3); tests are the only backend execution.
- **`asyncio_mode = "strict"`.** Every async test file MUST declare `pytestmark = pytest.mark.asyncio` at module top (or mark each test). Async fixtures use `@pytest_asyncio.fixture`.
- **The begin-once test transaction + IntegrityError = poison.** The `db_session` fixture (`tests/conftest.py:46-82`) wraps the whole test in ONE `session_maker.begin()` transaction that is rolled back at the end — persist rows with `await db_session.flush()`, NEVER `commit()`. A constraint violation (unique / FK) raised on a `flush()` **poisons that outer transaction**: every later statement fails until a rollback. So:
  - **In tests**, any assertion that a duplicate/FK-violating write raises `IntegrityError` MUST wrap that write in a SAVEPOINT — `async with db_session.begin_nested():` — so only the failed statement rolls back and the arranged rows (and the outer transaction) survive. Bare `pytest.raises(IntegrityError)` without a savepoint leaves the transaction poisoned and breaks the rest of the test.
  - **In service code**, the same rule is why F005's create/rename map the unique violation to a 409 via a SAVEPOINT around the flush (Task 2.2), not a whole-transaction rollback: a whole-transaction rollback would discard the already-created sibling row and break both production semantics and the "duplicate leaves exactly one row" test.
- **Async server-default reload.** After an `INSERT`/`flush()` of a row whose response the route serializes, the server-default columns (`created_at`, `updated_at`, `is_read`) are expired/unloaded; reading them during Pydantic `from_attributes` serialization would trigger implicit async IO and raise a `MissingGreenlet` error. F005's create/rename services therefore call `await db.refresh(row)` after the flush so all columns are in-memory before the route serializes (Task 2.2).
- **Naming contract.** All symbol names, table names, index names, route prefixes, and fixture names are taken verbatim from the plan brief's BINDING naming contract. No renames were required.

---

## Phase 0 — Campaign branch setup

**Execution Status:** ✅ SHIPPED at `70e8d1a` on 2026-07-18

Establishes the campaign worktree off `origin/dev` and captures the green baseline (backend pytest + frontend vitest) so every later phase measures against a known-good starting point. No production code.

### Task 0.1: Create the campaign worktree and record the green baseline

```
BEFORE starting work:
1. Invoke superpowers:test-driven-development
2. Read docs/pitfalls/testing-pitfalls.md
This task writes NO production code (environment + baseline capture), so TDD's
red→green cycle does not apply here — it begins at Task 1.1. The point of this
task is a trustworthy baseline: the suites MUST be green before any M3 code lands.
```

**Files:** none created/modified (worktree + local `.env` + baseline capture only).

- [x] **Step 1: Create the worktree off `origin/dev`.** From the main repo root `/Users/sam/Code/hangar-bay`:
  ```bash
  cd /Users/sam/Code/hangar-bay
  git fetch origin dev
  git worktree add .claude/worktrees/m3-account-features -b claude/m3-account-features origin/dev
  cd .claude/worktrees/m3-account-features
  ```
  All later task commands run from inside this worktree.
- [x] **Step 2: Bring up the dependency containers.**
  ```bash
  docker compose -f app/backend/docker/compose.yml -f app/backend/docker/compose.dependencies.yml up -d --wait postgres_db valkey_cache
  ```
- [x] **Step 3: Provision the backend `.env`.** The worktree has no `app/backend/src/.env` (it is gitignored). Create it from the template and fill the required values:
  ```bash
  cp app/backend/.env.example app/backend/src/.env
  ```
  Then ensure `app/backend/src/.env` sets, at minimum: `ENVIRONMENT=development`, `DB_RECREATE_ON_STARTUP=true`, `ESI_USER_AGENT=...`, `DATABASE_URL=postgresql+asyncpg://…/hangar_bay_db`, `CACHE_URL=redis://…/0`, and — required for pytest — `DATABASE_URL_TESTS=postgresql+asyncpg://…/hangar_bay_test` (a dedicated test database; conftest raises at import if unset). Match the connection strings to the compose containers from Step 2. (If a working dev `.env` already exists in another local worktree, copying it is fine.)
- [x] **Step 4: Install backend deps and capture the backend baseline.**
  ```bash
  cd app/backend && pdm install && pdm run pytest -q
  ```
  Expected: all tests pass (≈196 test functions at `origin/dev` tip `a7b0f26`). Record the exact `N passed` count from the summary line in this plan's Execution Status before proceeding — this is the number Phase 1/2 must never reduce.

  **Actual:** `220 passed in 6.95s`, clean output, no warnings. `origin/dev` tip at execution time was `27dac66` (commits since `a7b0f26` are docs-only — no production code — so the higher count is the plan estimate being approximate, not drift).
- [x] **Step 5: Install frontend deps and capture the frontend baseline.**
  ```bash
  cd ../frontend/web && npm ci && npx vitest run --reporter=dot
  ```
  Expected: all vitest suites pass (12 unit/component test files at baseline). Record the `Test Files N passed` / `Tests N passed` counts in this plan's Execution Status. (The frontend baseline is captured now for later phases; Section A touches no frontend code.)

  **Actual:** `Test Files  12 passed (12)` / `Tests  62 passed (62)`. jsdom logs expected `Not implemented: Window's scrollTo()` / `HTMLCanvasElement's getContext()` noise throughout (pre-existing jsdom environment limitations, not test failures) — no assertion failures, no errors.

```
BEFORE marking this task complete:
1. Review tests against docs/pitfalls/testing-pitfalls.md
2. Verify test coverage (error paths? edge cases?) — N/A for setup; verify instead that
   BOTH baselines are fully green and their counts are recorded in Execution Status.
3. Run tests and confirm green (backend pytest + frontend vitest).
```

```
After completing this phase:
Review the batch from multiple perspectives (correctness, pitfalls compliance, test coverage).
Minimum 3 review rounds. If round 3 still finds issues, keep going until clean.
```

---

## Phase 1 — Backend foundations

**Execution Status:** ✅ SHIPPED at `c0c341c` on 2026-07-18 (Task 1.4 recovered via cherry-pick from a wrong-cwd executor commit — see Deviations)

The auth backbone and data model every M3 feature stands on: the three per-user tables + the `users.watchlist_alerts_enabled` column (Task 1.1), the `authed_user` fixture + `login_as` helper that make FK'd-table tests possible (Task 1.2), the `get_current_user` session→row resolution dependency (Task 1.3), and the ride-along first-login upsert race fix (Task 1.4). Design authority: §4.1, §4.2, §9.1.

### Task 1.1: Account data model — `SavedSearch`, `WatchlistItem`, `Notification`, and `User.watchlist_alerts_enabled`

```
BEFORE starting work:
1. Invoke superpowers:test-driven-development
2. Read docs/pitfalls/testing-pitfalls.md
Follow TDD: write failing test → implement → verify green.
```

```
If any test assertion races, flakes, or fails nondeterministically, the fix is deterministic
synchronization or deterministic fixture data — NOT assertion removal or weakening. If
synchronization cannot make the assertion pass reliably, STOP and raise to the dispatching
agent. Do not ship a weaker test. Prefer mechanism assertions (state observed) over symptom
assertions (timing bounds).
```

**Files:**
- Create: `app/backend/src/fastapi_app/models/account.py`
- Modify: `app/backend/src/fastapi_app/models/user.py` (add `watchlist_alerts_enabled`; extend the `sqlalchemy` import line)
- Modify: `app/backend/src/fastapi_app/models/__init__.py` (register the three new models)
- Test: `app/backend/src/fastapi_app/tests/models/test_account_models.py`

- [x] **Step 1: Write the failing model tests.** Create `app/backend/src/fastapi_app/tests/models/test_account_models.py`:
  ```python
  # ABOUTME: Registration + constraint-binding guards for the M3 account tables.
  # ABOUTME: Proves FK-to-users, the two UniqueConstraints, and the notifications partial dedup index.
  import pytest
  from sqlalchemy import insert, select
  from sqlalchemy.exc import IntegrityError

  from fastapi_app.db import Base
  from fastapi_app.models import Notification, SavedSearch, User, WatchlistItem


  def test_account_tables_registered():
      for table in ("saved_searches", "watchlist_items", "notifications"):
          assert table in Base.metadata.tables


  def test_user_has_watchlist_alerts_enabled_not_null():
      col = Base.metadata.tables["users"].columns["watchlist_alerts_enabled"]
      assert col.nullable is False


  async def _make_user(db_session, character_id=91000001):
      user = User(character_id=character_id, character_name="Sesta Hound", owner_hash="OWN1")
      db_session.add(user)
      await db_session.flush()
      return user


  @pytest.mark.asyncio
  async def test_watchlist_alerts_enabled_defaults_true(db_session):
      user = await _make_user(db_session, character_id=91000201)
      await db_session.refresh(user)
      assert user.watchlist_alerts_enabled is True


  @pytest.mark.asyncio
  async def test_saved_search_fk_requires_real_user(db_session):
      # A row FK'd to a nonexistent users.id raises IntegrityError (savepoint keeps the tx alive).
      with pytest.raises(IntegrityError):
          async with db_session.begin_nested():
              db_session.add(SavedSearch(user_id=987654, name="orphan", search_parameters={}))
              await db_session.flush()


  @pytest.mark.asyncio
  async def test_saved_search_fk_accepts_real_user(db_session):
      user = await _make_user(db_session, character_id=91000202)
      db_session.add(SavedSearch(user_id=user.id, name="ok", search_parameters={}))
      await db_session.flush()  # succeeds — FK satisfied


  @pytest.mark.asyncio
  async def test_saved_search_unique_user_name(db_session):
      user = await _make_user(db_session, character_id=91000203)
      db_session.add(SavedSearch(user_id=user.id, name="dup", search_parameters={}))
      await db_session.flush()
      with pytest.raises(IntegrityError):
          async with db_session.begin_nested():
              db_session.add(SavedSearch(user_id=user.id, name="dup", search_parameters={}))
              await db_session.flush()


  @pytest.mark.asyncio
  async def test_watchlist_item_unique_user_type(db_session):
      user = await _make_user(db_session, character_id=91000204)
      db_session.add(WatchlistItem(user_id=user.id, type_id=587, type_name="Rifter"))
      await db_session.flush()
      with pytest.raises(IntegrityError):
          async with db_session.begin_nested():
              db_session.add(WatchlistItem(user_id=user.id, type_id=587, type_name="Rifter"))
              await db_session.flush()


  @pytest.mark.asyncio
  async def test_notifications_partial_dedup_index_blocks_duplicate_watchlist_match(db_session):
      user = await _make_user(db_session, character_id=91000205)
      await db_session.execute(insert(Notification).values(
          user_id=user.id, type="watchlist_match", message="first",
          contract_id=777, watch_type_id=587, is_read=False,
      ))
      await db_session.flush()
      # A second identical (user_id, contract_id, watch_type_id) watchlist_match row is blocked.
      with pytest.raises(IntegrityError):
          async with db_session.begin_nested():
              await db_session.execute(insert(Notification).values(
                  user_id=user.id, type="watchlist_match", message="second",
                  contract_id=777, watch_type_id=587, is_read=False,
              ))
      # A row with a DIFFERENT type value (outside the partial index predicate) is allowed through.
      await db_session.execute(insert(Notification).values(
          user_id=user.id, type="other_kind", message="third",
          contract_id=777, watch_type_id=587, is_read=False,
      ))
      await db_session.flush()  # succeeds — predicate WHERE type='watchlist_match' excludes it
      rows = (await db_session.execute(
          select(Notification).where(Notification.user_id == user.id)
      )).scalars().all()
      assert len(rows) == 2  # the first watchlist_match + the other_kind row
  ```
- [x] **Step 2: Run the tests and confirm they fail.**
  ```bash
  cd app/backend && pdm run pytest src/fastapi_app/tests/models/test_account_models.py -v
  ```
  Expected failure: `ImportError: cannot import name 'Notification' from 'fastapi_app.models'` (the account module does not exist yet).
- [x] **Step 3: Create `app/backend/src/fastapi_app/models/account.py`.**
  ```python
  # ABOUTME: M3 per-user account tables — saved searches, watchlist items, notifications — FK'd to users.id (ondelete CASCADE).
  # ABOUTME: Notifications carry the uq_notifications_watchlist_dedup partial unique index the matcher relies on for ON CONFLICT dedup.
  from datetime import datetime
  from typing import Any, Optional

  from sqlalchemy import (
      BigInteger,
      Boolean,
      DateTime,
      ForeignKey,
      Index,
      Integer,
      JSON,
      Numeric,
      String,
      Text,
      UniqueConstraint,
      false,
      func,
      text,
  )
  from sqlalchemy.orm import Mapped, mapped_column

  from ..db import Base


  class SavedSearch(Base):
      __tablename__ = "saved_searches"

      id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
      user_id: Mapped[int] = mapped_column(
          Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
      )
      name: Mapped[str] = mapped_column(String(100), nullable=False)
      search_parameters: Mapped[Any] = mapped_column(JSON, nullable=False)
      created_at: Mapped[datetime] = mapped_column(
          DateTime(timezone=True), server_default=func.now(), nullable=False
      )
      updated_at: Mapped[datetime] = mapped_column(
          DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
      )

      __table_args__ = (UniqueConstraint("user_id", "name", name="uq_saved_searches_user_name"),)


  class WatchlistItem(Base):
      __tablename__ = "watchlist_items"

      id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
      user_id: Mapped[int] = mapped_column(
          Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
      )
      type_id: Mapped[int] = mapped_column(Integer, nullable=False)
      type_name: Mapped[str] = mapped_column(String(255), nullable=False)
      max_price: Mapped[Optional[float]] = mapped_column(Numeric(20, 2), nullable=True)
      notes: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
      created_at: Mapped[datetime] = mapped_column(
          DateTime(timezone=True), server_default=func.now(), nullable=False
      )
      updated_at: Mapped[datetime] = mapped_column(
          DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
      )

      __table_args__ = (UniqueConstraint("user_id", "type_id", name="uq_watchlist_items_user_type"),)


  class Notification(Base):
      __tablename__ = "notifications"

      id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
      user_id: Mapped[int] = mapped_column(
          Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
      )
      type: Mapped[str] = mapped_column(String(50), nullable=False)
      message: Mapped[str] = mapped_column(Text, nullable=False)
      # contract_id is NOT a foreign key: contracts are upsert-only external data, and a
      # pruned/wiped contract must never cascade-delete a user's notification history (design §4.2).
      contract_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
      watch_type_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
      price: Mapped[Optional[float]] = mapped_column(Numeric(20, 2), nullable=True)
      is_read: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=false())
      created_at: Mapped[datetime] = mapped_column(
          DateTime(timezone=True), server_default=func.now(), nullable=False
      )

      __table_args__ = (
          Index("ix_notifications_user_is_read", "user_id", "is_read"),
          Index("ix_notifications_user_created_at", "user_id", "created_at"),
          # Partial unique index — the matcher's ON CONFLICT dedup target. The predicate keeps
          # the constraint from binding future notification types whose dedup columns are NULL
          # (NULLs are distinct in Postgres unique indexes); the matcher always populates both
          # dedup columns for watchlist_match rows (design §4.4).
          Index(
              "uq_notifications_watchlist_dedup",
              "user_id",
              "contract_id",
              "watch_type_id",
              unique=True,
              postgresql_where=text("type = 'watchlist_match'"),
          ),
      )
  ```
- [x] **Step 4: Add `watchlist_alerts_enabled` to `models/user.py`.** Change the import line `from sqlalchemy import BigInteger, DateTime, String, Text, func` to also import `Boolean` and `true`:
  ```python
  from sqlalchemy import BigInteger, Boolean, DateTime, String, Text, func, true
  ```
  and add this column to the `User` class body (place it after `esi_scopes`, before `last_login_at`):
  ```python
      watchlist_alerts_enabled: Mapped[bool] = mapped_column(
          Boolean, nullable=False, server_default=true()
      )
  ```
- [x] **Step 5: Register the models in `models/__init__.py`.** Replace the file body with:
  ```python
  from .user import User
  from .contracts import Contract, ContractItem, EsiMarketGroupCache
  from .account import SavedSearch, WatchlistItem, Notification

  __all__ = [
      "User",
      "Contract",
      "ContractItem",
      "EsiMarketGroupCache",
      "SavedSearch",
      "WatchlistItem",
      "Notification",
  ]
  ```
  (Registration is sufficient for `create_all` in dev and tests because `main.py` imports `from .models import contracts`, which runs this package `__init__` and imports `account`; `conftest.py` pulls the app import chain too — recon backend-data-auth §1.)
- [x] **Step 6: Run the tests and confirm green.**
  ```bash
  cd app/backend && pdm run pytest src/fastapi_app/tests/models/test_account_models.py -v
  ```
  Expected: all pass. Also run the existing user-model guard to confirm no regression: `pdm run pytest src/fastapi_app/tests/models/test_user_model.py -v`.
- [x] **Step 7: Lint + commit.**
  ```bash
  cd app/backend && pdm run lint
  git add app/backend/src/fastapi_app/models/account.py app/backend/src/fastapi_app/models/user.py app/backend/src/fastapi_app/models/__init__.py app/backend/src/fastapi_app/tests/models/test_account_models.py
  ```
  then commit with:
  ```
  feat(backend): add M3 account models and watchlist-alerts flag

  Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>
  ```

```
BEFORE marking this task complete:
1. Review tests against docs/pitfalls/testing-pitfalls.md
2. Verify test coverage (error paths? edge cases?) — FK-miss, both UniqueConstraints,
   the partial-index dedup AND its predicate exclusion, and the server-default flag are all pinned.
3. Run tests and confirm green.
```

### Task 1.2: Test fixtures — `authed_user` + `login_as`

```
BEFORE starting work:
1. Invoke superpowers:test-driven-development
2. Read docs/pitfalls/testing-pitfalls.md
Follow TDD: write failing test → implement → verify green.
```

**Files:**
- Modify: `app/backend/src/fastapi_app/tests/conftest.py` (add two imports, `login_as`, `authed_user`)
- Test: `app/backend/src/fastapi_app/tests/api/test_account_fixtures.py`

- [x] **Step 1: Write the failing fixture tests.** Create `app/backend/src/fastapi_app/tests/api/test_account_fixtures.py`:
  ```python
  # ABOUTME: Round-trip proofs for the M3 authed_user fixture and login_as helper (real session in FakeRedis).
  import pytest

  from fastapi_app.tests.conftest import login_as

  pytestmark = pytest.mark.asyncio


  async def test_authed_user_round_trips_me(authed_user):
      user, client = authed_user
      resp = await client.get("/me")
      assert resp.status_code == 200
      assert resp.json() == {"character_id": 91000001, "character_name": "Sesta Hound"}
      assert user.id is not None  # inserted + flushed, real users.id


  async def test_login_as_switches_identity(auth_client, db_session):
      other = await login_as(
          auth_client, db_session,
          character_id=91000042, character_name="Bravo Pilot", owner_hash="OWN2",
      )
      resp = await auth_client.get("/me")
      assert resp.status_code == 200
      assert resp.json()["character_id"] == 91000042
      assert other.character_id == 91000042
  ```
- [x] **Step 2: Run and confirm failure.**
  ```bash
  cd app/backend && pdm run pytest src/fastapi_app/tests/api/test_account_fixtures.py -v
  ```
  Expected failure: `ImportError: cannot import name 'login_as' from 'fastapi_app.tests.conftest'`.
- [x] **Step 3: Add the fixture + helper to `conftest.py`.** Add these imports near the existing `from fastapi_app.core.config import settings` (top region of the file):
  ```python
  from fastapi_app.core import session as sess
  from fastapi_app.models import User
  ```
  and add this fixture + helper at the end of `conftest.py` (after `configured_sso`):
  ```python
  async def login_as(auth_client, db_session, *, character_id, character_name, owner_hash):
      """Insert a real User, mint a server-side session pointing at its users.id, and set the
      session cookie on auth_client. OVERWRITES the client cookie, so cross-user tests either
      capture each user's sid before switching or accept that the last login_as wins. Returns
      the User (for FK'd-row arrangement and assertions)."""
      user = User(character_id=character_id, character_name=character_name, owner_hash=owner_hash)
      db_session.add(user)
      await db_session.flush()  # populates user.id (the FK target for M3 tables)
      sid = await sess.create_session(
          auth_client.fake_redis,
          user_id=user.id, character_id=user.character_id, character_name=user.character_name,
      )
      auth_client.cookies.set(settings.SESSION_COOKIE_NAME, sid)
      return user


  @pytest_asyncio.fixture
  async def authed_user(auth_client, db_session):
      """The canonical authenticated M3 caller: a real User row + a real session, returned as
      (user, auth_client). Use for happy-path and single-user CRUD tests; use login_as for the
      second identity in cross-user isolation tests."""
      user = await login_as(
          auth_client, db_session,
          character_id=91000001, character_name="Sesta Hound", owner_hash="OWN1",
      )
      return user, auth_client
  ```
- [x] **Step 4: Run and confirm green.**
  ```bash
  cd app/backend && pdm run pytest src/fastapi_app/tests/api/test_account_fixtures.py -v
  ```
  Expected: both pass.
- [x] **Step 5: Lint + commit.**
  ```bash
  cd app/backend && pdm run lint
  git add app/backend/src/fastapi_app/tests/conftest.py app/backend/src/fastapi_app/tests/api/test_account_fixtures.py
  ```
  then commit with:
  ```
  test(backend): add authed_user fixture and login_as helper

  Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>
  ```

```
BEFORE marking this task complete:
1. Review tests against docs/pitfalls/testing-pitfalls.md
2. Verify test coverage (error paths? edge cases?) — the fixture round-trips /me and login_as
   demonstrably switches identity; both insert real users.id rows (the FK prerequisite).
3. Run tests and confirm green.
```

### Task 1.3: `get_current_user` — session→row resolution dependency

```
BEFORE starting work:
1. Invoke superpowers:test-driven-development
2. Read docs/pitfalls/testing-pitfalls.md
Follow TDD: write failing test → implement → verify green.
```

**Files:**
- Create: `app/backend/src/fastapi_app/core/current_user.py`
- Test: `app/backend/src/fastapi_app/tests/core/test_current_user.py`

Design §4.1: resolve `session["user_id"]` to a live `users` row; if the row is absent OR its `character_id` differs from the session's, destroy the server-side session (re-reading the sid from the request cookie, since the session payload does not carry its own sid) and raise 401. The `character_id` equality check is load-bearing — after a dev wipe + a different user's re-login, `users.id` can be reassigned, so an existence check alone would silently read/write another character's data.

- [x] **Step 1: Write the failing tests.** Create `app/backend/src/fastapi_app/tests/core/test_current_user.py`:
  ```python
  # ABOUTME: get_current_user resolves session->users row and forces re-login on miss/mismatch (design §4.1).
  # ABOUTME: Direct-call unit tests; HTTP-level coverage (401 anon, cross-user) lands in Phase 2's CRUD suite.
  from types import SimpleNamespace

  import pytest
  from fastapi import HTTPException

  from fastapi_app.core import session as sess
  from fastapi_app.core.config import settings
  from fastapi_app.core.current_user import get_current_user
  from fastapi_app.models import User
  from fastapi_app.tests.fake_redis import FakeRedis

  pytestmark = pytest.mark.asyncio


  def _request_with_sid(sid):
      return SimpleNamespace(cookies={settings.SESSION_COOKIE_NAME: sid})


  async def _mint(redis, *, user_id, character_id):
      sid = await sess.create_session(
          redis, user_id=user_id, character_id=character_id, character_name="Sesta Hound"
      )
      payload = await sess.read_session(redis, sid)
      return sid, payload


  async def test_happy_path_returns_user_and_keeps_session(db_session):
      redis = FakeRedis()
      user = User(character_id=91000001, character_name="Sesta Hound", owner_hash="OWN1")
      db_session.add(user)
      await db_session.flush()
      sid, payload = await _mint(redis, user_id=user.id, character_id=user.character_id)
      result = await get_current_user(
          request=_request_with_sid(sid), session=payload, db=db_session, redis=redis
      )
      assert result.id == user.id
      assert await redis.exists(f"session:{sid}") == 1  # session preserved


  async def test_missing_row_401_and_session_deleted(db_session):
      redis = FakeRedis()
      # No users row for user_id=987654 (e.g. session survived a dev DB wipe).
      sid, payload = await _mint(redis, user_id=987654, character_id=91000001)
      with pytest.raises(HTTPException) as exc:
          await get_current_user(
              request=_request_with_sid(sid), session=payload, db=db_session, redis=redis
          )
      assert exc.value.status_code == 401
      assert await redis.exists(f"session:{sid}") == 0  # forced re-login


  async def test_wrong_character_id_401_and_session_deleted(db_session):
      redis = FakeRedis()
      user = User(character_id=91000001, character_name="Sesta Hound", owner_hash="OWN1")
      db_session.add(user)
      await db_session.flush()
      # Session points at the right users.id but a DIFFERENT character_id (reassigned-id hazard).
      sid, payload = await _mint(redis, user_id=user.id, character_id=91000999)
      with pytest.raises(HTTPException) as exc:
          await get_current_user(
              request=_request_with_sid(sid), session=payload, db=db_session, redis=redis
          )
      assert exc.value.status_code == 401
      assert await redis.exists(f"session:{sid}") == 0
  ```
- [x] **Step 2: Run and confirm failure.**
  ```bash
  cd app/backend && pdm run pytest src/fastapi_app/tests/core/test_current_user.py -v
  ```
  Expected failure: `ModuleNotFoundError: No module named 'fastapi_app.core.current_user'`.
- [x] **Step 3: Create `app/backend/src/fastapi_app/core/current_user.py`.**
  ```python
  # ABOUTME: get_current_user — the M3 auth backbone: resolves the session to a live users row and
  # ABOUTME: verifies character_id, forcing re-login (destroy session + 401) on a missing/reassigned row (design §4.1).
  from fastapi import Depends, HTTPException, Request, status
  from redis.asyncio import Redis
  from sqlalchemy import select
  from sqlalchemy.ext.asyncio import AsyncSession

  from ..db import get_db
  from ..models import User
  from .config import get_settings
  from .dependencies import get_cache
  from .session import destroy_session, get_current_session


  async def get_current_user(
      request: Request,
      session: dict = Depends(get_current_session),
      db: AsyncSession = Depends(get_db),
      redis: Redis = Depends(get_cache),
  ) -> User:
      user = (
          await db.execute(select(User).where(User.id == session["user_id"]))
      ).scalar_one_or_none()
      if user is None or user.character_id != session["character_id"]:
          # The row is gone (dev wipe) or the autoincrement id was reassigned to a different
          # character. Either way the stale session must not resolve to anyone — destroy it
          # (re-reading the sid from the request cookie, since the payload carries no sid) so the
          # browser cookie points at nothing and the next login replaces it (design §4.1 step 2).
          sid = request.cookies.get(get_settings().SESSION_COOKIE_NAME)
          if sid:
              await destroy_session(redis, sid)
          raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
      return user
  ```
- [x] **Step 4: Run and confirm green.**
  ```bash
  cd app/backend && pdm run pytest src/fastapi_app/tests/core/test_current_user.py -v
  ```
  Expected: all three pass.
- [x] **Step 5: Lint + commit.**
  ```bash
  cd app/backend && pdm run lint
  git add app/backend/src/fastapi_app/core/current_user.py app/backend/src/fastapi_app/tests/core/test_current_user.py
  ```
  then commit with:
  ```
  feat(backend): add get_current_user session-to-row resolution dependency

  Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>
  ```

```
BEFORE marking this task complete:
1. Review tests against docs/pitfalls/testing-pitfalls.md
2. Verify test coverage (error paths? edge cases?) — happy path + BOTH failure shapes
   (row-absent, character_id-mismatch) assert 401 AND the mechanism (session key deleted).
3. Run tests and confirm green.
```

### Task 1.4: Ride-along — make the first-login upsert race-safe via `ON CONFLICT DO UPDATE`

```
BEFORE starting work:
1. Invoke superpowers:test-driven-development
2. Read docs/pitfalls/testing-pitfalls.md
Follow TDD: write failing test → implement → verify green.
```

```
If any test assertion races, flakes, or fails nondeterministically, the fix is deterministic
synchronization or deterministic fixture data — NOT assertion removal or weakening. If
synchronization cannot make the assertion pass reliably, STOP and raise to the dispatching
agent. Do not ship a weaker test. Prefer mechanism assertions (state observed) over symptom
assertions (timing bounds).
```

**Files:**
- Modify: `app/backend/src/fastapi_app/services/auth_service.py` (rewrite `upsert_user`; extend imports; remove ONLY the first-login-race TODO block)
- Test: `app/backend/src/fastapi_app/tests/services/test_auth_service.py` (add one deterministic two-session concurrency test)

**Nature of the change:** this refactor closes the first-login race (design §9.1). The new deterministic two-session test below IS the red-first behavior test: it drives two concurrent first logins for the same `character_id` on independent connections, and Postgres's unique-index lock on the winner's uncommitted insert makes the ordering deterministic (a lock wait, not a timing race). Against the current select-then-insert the losing session raises `IntegrityError` once the winner commits (RED); against `INSERT ... ON CONFLICT DO UPDATE` it lands on the winner's row (GREEN). The existing `test_auth_service.py` suite remains the regression guard for external behavior (encryption, rotation, owner-hash transfer). The red→green cycle here is: new test RED against current code → rewrite → new test GREEN + existing suite still green.

- [x] **Step 1: Add the failing concurrency test.** Append to `app/backend/src/fastapi_app/tests/services/test_auth_service.py`. It needs three imports the module does not have yet — add to the import block: `import asyncio`, `from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine`, and `from fastapi_app.db import Base`:
  ```python
  @pytest.mark.asyncio
  async def test_concurrent_first_login_both_succeed_single_row():
      # Two genuinely concurrent first logins for the SAME character_id, on independent connections.
      # Blocking is enforced by Postgres's unique-index lock on session A's uncommitted insert — NOT
      # by sleep timing — so the ordering is deterministic. Against the current select-then-insert,
      # session B raises IntegrityError once A commits (RED); against ON CONFLICT DO UPDATE, B lands
      # on A's row (GREEN). This test does NOT take the db_session fixture: both sessions must commit
      # independently, so it manages its own two engines against DATABASE_URL_TESTS.
      url = str(settings.DATABASE_URL_TESTS)
      engine_a = create_async_engine(url)
      engine_b = create_async_engine(url)
      session_a = None
      task_b = None
      try:
          async with engine_a.begin() as conn:   # commit the schema so BOTH connections see the table
              await conn.run_sync(Base.metadata.drop_all)
              await conn.run_sync(Base.metadata.create_all)
          maker_a = async_sessionmaker(engine_a, expire_on_commit=False)
          maker_b = async_sessionmaker(engine_b, expire_on_commit=False)

          ident_a = VerifiedIdentity(character_id=91000001, character_name="First", owner_hash="OWN1")
          ident_b = VerifiedIdentity(character_id=91000001, character_name="Second", owner_hash="OWN2")

          session_a = maker_a()
          user_a = await auth_service.upsert_user(
              session_a, ident_a, {"access_token": "AT1", "expires_in": 1200}
          )   # A's insert is flushed but NOT committed — its unique-index entry now blocks B.

          b_out: dict = {}

          async def _upsert_in_session_b():
              async with maker_b() as session_b:
                  b_out["user"] = await auth_service.upsert_user(
                      session_b, ident_b, {"access_token": "AT2", "expires_in": 1200}
                  )
                  await session_b.commit()

          task_b = asyncio.create_task(_upsert_in_session_b())
          await asyncio.sleep(0.1)     # let B reach its insert and BLOCK on A's lock (a lock wait, not a race)
          assert not task_b.done()     # B is parked on the lock — neither finished nor errored yet

          await session_a.commit()     # release the lock; B now resolves against A's committed row
          await task_b                  # RED: current select-then-insert raises IntegrityError here. GREEN: B succeeds.

          async with maker_a() as verify:
              rows = (
                  await verify.execute(select(User).where(User.character_id == 91000001))
              ).scalars().all()
          assert len(rows) == 1                       # exactly one users row — no duplicate
          assert user_a.character_id == 91000001
          assert b_out["user"].character_id == 91000001
          assert rows[0].owner_hash == "OWN2"         # B was the last writer — updated A's row in place
      finally:
          if task_b is not None:       # never orphan the background task (keeps output pristine on failure)
              task_b.cancel()
              try:
                  await task_b
              except BaseException:
                  pass
          if session_a is not None:    # roll A's tx back BEFORE the DDL drop so it can't deadlock on A's lock
              await session_a.close()
          async with engine_a.begin() as conn:
              await conn.run_sync(Base.metadata.drop_all)
          await engine_a.dispose()
          await engine_b.dispose()
  ```
  Run it against the CURRENT implementation to confirm it fails RED — session B raises `IntegrityError`:
  ```bash
  cd app/backend && pdm run pytest src/fastapi_app/tests/services/test_auth_service.py::test_concurrent_first_login_both_succeed_single_row -v
  ```
- [x] **Step 2: Rewrite `upsert_user`.** In `services/auth_service.py`, change the import line `from sqlalchemy import select` to:
  ```python
  from sqlalchemy import func, select
  from sqlalchemy.dialects.postgresql import insert as pg_insert
  ```
  and replace the entire `upsert_user` function (its current docstring/TODO comment block AND body, lines ~16-49) with:
  ```python
  async def upsert_user(db: AsyncSession, identity: VerifiedIdentity, tokens: dict) -> User:
      # Race-safe first login: INSERT ... ON CONFLICT (character_id) DO UPDATE so two simultaneous
      # first logins for the same character_id both succeed against the single row (the loser updates
      # the winner's row instead of raising IntegrityError). Owner-hash transfer stays: on any login
      # the mutable identity/token columns are overwritten — data follows the character (§4.1).
      now = datetime.now(timezone.utc)
      expires_at = now + timedelta(seconds=int(tokens["expires_in"]))
      encrypted_access = token_cipher.encrypt_token(tokens["access_token"])
      # Zero-scope logins carry no refresh_token key (D-DELTA-2); store NULL, never "".
      refresh_token = tokens.get("refresh_token")
      encrypted_refresh = (
          token_cipher.encrypt_token(refresh_token) if refresh_token is not None else None
      )
      mutable = {
          "character_name": identity.character_name,
          "owner_hash": identity.owner_hash,
          "esi_access_token": encrypted_access,
          "esi_refresh_token": encrypted_refresh,
          "esi_access_token_expires_at": expires_at,
          "last_login_at": now,
      }
      stmt = (
          pg_insert(User)
          .values(character_id=identity.character_id, **mutable)
          .on_conflict_do_update(
              index_elements=["character_id"],
              set_={**mutable, "updated_at": func.now()},
          )
      )
      await db.execute(stmt)
      # Re-select with populate_existing so an already-identity-mapped instance (e.g. a prior
      # upsert in the same session) is refreshed with the new column values, and so the returned
      # ORM row is fully loaded (no expired server-default columns) for the caller.
      user = (
          await db.execute(
              select(User)
              .where(User.character_id == identity.character_id)
              .execution_options(populate_existing=True)
          )
      ).scalar_one()
      return user
  ```
  Leave the `refresh_user_tokens` `TODO(M3)` block (lines ~88-94) and the `mark_for_reauth` deferred-note (lines ~52-54) exactly as they are — those items are scope-gated to the first token-using caller (design §1, §8), not this milestone.
- [x] **Step 3: Run the auth-service suite and confirm green.**
  ```bash
  cd app/backend && pdm run pytest src/fastapi_app/tests/services/test_auth_service.py -v
  ```
  Expected: every existing test (create+encrypt, refresh-token-present, owner-hash transfer, mark_for_reauth, all refresh_user_tokens paths) plus the new two-session concurrency test pass. The owner-hash-transfer test in particular proves the ON-CONFLICT update path (`len(rows) == 1`, `owner_hash == "OWN2"`, `last_login_at` advanced) still holds.
- [x] **Step 4: Confirm the callback flow is unaffected.** Run the auth-flow HTTP suite (it exercises `_finalize_login` → `upsert_user`):
  ```bash
  cd app/backend && pdm run pytest src/fastapi_app/tests/api/test_auth_flow.py -v
  ```
  Expected: green. (`_finalize_login`'s try/except-rollback stays as defensive handling for other failure shapes; it is not modified here.)
- [x] **Step 5: Lint + commit.**
  ```bash
  cd app/backend && pdm run lint
  git add app/backend/src/fastapi_app/services/auth_service.py app/backend/src/fastapi_app/tests/services/test_auth_service.py
  ```
  then commit with:
  ```
  fix(auth): make first-login upsert race-safe with ON CONFLICT DO UPDATE

  Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>
  ```

```
BEFORE marking this task complete:
1. Review tests against docs/pitfalls/testing-pitfalls.md
2. Verify test coverage (error paths? edge cases?) — the full existing suite (encryption,
   rotation, outage-keeps-vault, wrong-key re-auth) stays green AND the new two-session test pins
   race-safe same-row-on-conflict (RED against the old code, GREEN after the rewrite).
3. Run tests and confirm green (test_auth_service.py + test_auth_flow.py).
```

```
After completing this phase:
Review the batch from multiple perspectives (correctness, pitfalls compliance, test coverage).
Minimum 3 review rounds. If round 3 still finds issues, keep going until clean.
```

---

## Phase 2 — F005 Saved Searches backend

**Execution Status:** ✅ SHIPPED at `c4c1dab` on 2026-07-18

The complete F005 backend: the `search_parameters` validation model + request/response schemas (Task 2.1), then the ownership-scoped CRUD service, the auth-gated router, its `main.py` mount, the `MAX_SAVED_SEARCHES_PER_USER` setting, and the full HTTP + schema test matrix (Task 2.2). Design authority: §4.5, §3.5. All routes are bare-mounted (PROXY-1), auth-gated via `get_current_user`, and ownership-scoped; not-found and not-owned are the same 404 (anti-enumeration).

### Task 2.1: Saved-search schemas — `SavedSearchParameters`, `SavedSearchCreate`, `SavedSearchUpdate`, `SavedSearchSchema`

```
BEFORE starting work:
1. Invoke superpowers:test-driven-development
2. Read docs/pitfalls/testing-pitfalls.md
Follow TDD: write failing test → implement → verify green.
```

**Files:**
- Create: `app/backend/src/fastapi_app/schemas/account.py`
- Test: `app/backend/src/fastapi_app/tests/api/test_account_schemas.py`

`SavedSearchParameters` mirrors the frontend `ContractSearch` shape minus `page` (design §4.5) and sets `extra="forbid"` — this rejects the four inert ME/TE params (FASTAPI-2), `is_ship_contract` (the wire name; the saved blob uses the frontend `ships_only` form per design Appendix A), `page`, and arbitrary junk by construction, at the API boundary. It reuses the existing `SortableContractFields` / `SortDirection` enums.

- [x] **Step 1: Write the failing schema tests.** Create `app/backend/src/fastapi_app/tests/api/test_account_schemas.py`:
  ```python
  # ABOUTME: Unit tests for the SavedSearchParameters validation model + saved-search request/response schemas.
  # ABOUTME: Pins extra="forbid" (ME/TE + junk rejection), constraint bounds, and name trimming.
  import pytest
  from pydantic import ValidationError

  from fastapi_app.schemas.account import (
      SavedSearchCreate,
      SavedSearchParameters,
      SavedSearchUpdate,
  )


  def test_parameters_defaults_materialize():
      p = SavedSearchParameters()
      assert p.ships_only is True
      assert p.size == 50
      assert p.sort_by.value == "date_issued"
      assert p.sort_direction.value == "desc"
      assert p.search is None and p.region_ids is None


  def test_parameters_accepts_valid_payload():
      p = SavedSearchParameters(search="frigate", max_price=5_000_000, region_ids=[10000002], is_bpc=False)
      assert p.search == "frigate"
      assert p.region_ids == [10000002]


  @pytest.mark.parametrize("bad", [
      {"search": "ab"},          # min_length 3
      {"min_price": -1},         # ge 0
      {"max_price": -0.01},      # ge 0
      {"region_ids": [0]},       # positive ints only
      {"size": 0},               # ge 1
      {"size": 101},             # le 100
      {"min_me": 5},             # extra="forbid" — inert ME param rejected (FASTAPI-2)
      {"page": 2},               # extra="forbid" — page is per-view, not a saved property
      {"is_ship_contract": True},  # extra="forbid" — the blob uses ships_only, not the wire name
  ])
  def test_parameters_reject_invalid(bad):
      with pytest.raises(ValidationError):
          SavedSearchParameters(**bad)


  def test_create_trims_name_and_rejects_blank():
      c = SavedSearchCreate(name="  Cheap frigs  ", search_parameters={})
      assert c.name == "Cheap frigs"
      with pytest.raises(ValidationError):
          SavedSearchCreate(name="   ", search_parameters={})
      with pytest.raises(ValidationError):
          SavedSearchCreate(search_parameters={})  # name required


  def test_update_requires_and_trims_name():
      u = SavedSearchUpdate(name="  Renamed ")
      assert u.name == "Renamed"
      with pytest.raises(ValidationError):
          SavedSearchUpdate(name="")
  ```
- [x] **Step 2: Run and confirm failure.**
  ```bash
  cd app/backend && pdm run pytest src/fastapi_app/tests/api/test_account_schemas.py -v
  ```
  Expected failure: `ModuleNotFoundError: No module named 'fastapi_app.schemas.account'`.
- [x] **Step 3: Create `app/backend/src/fastapi_app/schemas/account.py`.**
  ```python
  # ABOUTME: Pydantic schemas for M3 saved searches — the extra="forbid" search_parameters model + CRUD request/response shapes.
  # ABOUTME: search_parameters mirrors the frontend ContractSearch minus page; ME/TE and unknown keys are rejected at the boundary (FASTAPI-2).
  from datetime import datetime
  from typing import List, Optional

  from pydantic import BaseModel, ConfigDict, Field, PositiveInt, field_validator

  from .contracts import SortableContractFields, SortDirection


  class SavedSearchParameters(BaseModel):
      """Server-side validation model for a saved search's stored filter blob. Mirrors the
      frontend ContractSearch shape minus `page`; extra="forbid" rejects the inert ME/TE params
      (FASTAPI-2), the wire-only `is_ship_contract`, `page`, and arbitrary junk (design §4.5)."""

      model_config = ConfigDict(extra="forbid")

      search: Optional[str] = Field(default=None, min_length=3)
      min_price: Optional[float] = Field(default=None, ge=0)
      max_price: Optional[float] = Field(default=None, ge=0)
      region_ids: Optional[List[PositiveInt]] = Field(default=None)
      is_bpc: Optional[bool] = Field(default=None)
      ships_only: bool = Field(default=True)
      size: int = Field(default=50, ge=1, le=100)
      sort_by: SortableContractFields = Field(default=SortableContractFields.date_issued)
      sort_direction: SortDirection = Field(default=SortDirection.desc)


  def _trimmed_nonempty_name(value: str) -> str:
      value = value.strip()
      if not value:
          raise ValueError("name must not be empty")
      return value


  class SavedSearchCreate(BaseModel):
      name: str = Field(..., max_length=100)
      search_parameters: SavedSearchParameters

      _trim_name = field_validator("name")(_trimmed_nonempty_name)


  class SavedSearchUpdate(BaseModel):
      name: str = Field(..., max_length=100)

      _trim_name = field_validator("name")(_trimmed_nonempty_name)


  class SavedSearchSchema(BaseModel):
      id: int
      name: str
      search_parameters: SavedSearchParameters
      created_at: datetime
      updated_at: datetime

      model_config = ConfigDict(from_attributes=True)
  ```
- [x] **Step 4: Run and confirm green.**
  ```bash
  cd app/backend && pdm run pytest src/fastapi_app/tests/api/test_account_schemas.py -v
  ```
  Expected: all pass.
- [x] **Step 5: Lint + commit.**
  ```bash
  cd app/backend && pdm run lint
  git add app/backend/src/fastapi_app/schemas/account.py app/backend/src/fastapi_app/tests/api/test_account_schemas.py
  ```
  then commit with:
  ```
  feat(api): add saved-search request/response schemas

  Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>
  ```

```
BEFORE marking this task complete:
1. Review tests against docs/pitfalls/testing-pitfalls.md
2. Verify test coverage (error paths? edge cases?) — defaults, valid payload, every constraint
   boundary, extra="forbid" (ME/page/wire-name), and name trim/blank/required are all pinned.
3. Run tests and confirm green.
```

### Task 2.2: Saved-searches service + router + mount + config, with the full HTTP test matrix

```
BEFORE starting work:
1. Invoke superpowers:test-driven-development
2. Read docs/pitfalls/testing-pitfalls.md
Follow TDD: write failing test → implement → verify green.
```

```
If any test assertion races, flakes, or fails nondeterministically, the fix is deterministic
synchronization or deterministic fixture data — NOT assertion removal or weakening. If
synchronization cannot make the assertion pass reliably, STOP and raise to the dispatching
agent. Do not ship a weaker test. Prefer mechanism assertions (state observed) over symptom
assertions (timing bounds).
```

**Files:**
- Create: `app/backend/src/fastapi_app/services/saved_search_service.py`
- Create: `app/backend/src/fastapi_app/api/saved_searches.py`
- Modify: `app/backend/src/fastapi_app/core/config.py` (add `MAX_SAVED_SEARCHES_PER_USER`)
- Modify: `app/backend/.env.example` (document the new setting — ENV-4)
- Modify: `app/backend/src/fastapi_app/main.py` (import + mount the router)
- Test: `app/backend/src/fastapi_app/tests/api/test_saved_searches.py`

**Codegen note:** mounting the router changes `app.openapi()` (the schema tests below read the live schema, so they pass immediately). The committed `openapi.json` / `schema.d.ts` FILES are NOT regenerated in this phase — the design batches the codegen chain into one dedicated step after all backend surface lands (design §7). No backend test asserts file-freshness (`tests/test_export_openapi.py` regenerates to a tmp path and only checks `/contracts`), so this phase stays green without regenerating.

- [x] **Step 1: Write the failing HTTP + schema test matrix.** Create `app/backend/src/fastapi_app/tests/api/test_saved_searches.py`:
  ```python
  # ABOUTME: HTTP-level (TEST-1) + app.openapi() schema tests for the F005 saved-searches CRUD surface.
  # ABOUTME: Covers CRUD, 401 anon, cross-user 404, 409 duplicate/rename via real constraint, cap 400, 422s, ordering, PROXY-1.
  import pytest

  from fastapi_app.main import app
  from fastapi_app.tests.conftest import login_as


  def _body(name="Frigs", **params):
      return {"name": name, "search_parameters": params}


  # ---------- happy-path CRUD ----------
  @pytest.mark.asyncio
  async def test_create_and_list_roundtrip(authed_user):
      user, client = authed_user
      resp = await client.post("/me/saved-searches/", json=_body(
          name="Cheap frigates", search="frigate", max_price=5_000_000, region_ids=[10000002], ships_only=True
      ))
      assert resp.status_code == 201
      created = resp.json()
      assert created["name"] == "Cheap frigates"
      assert created["search_parameters"]["search"] == "frigate"
      assert created["search_parameters"]["region_ids"] == [10000002]
      assert created["search_parameters"]["size"] == 50          # default materialized
      assert created["search_parameters"]["sort_by"] == "date_issued"
      assert "id" in created and "created_at" in created and "updated_at" in created

      listed = await client.get("/me/saved-searches/")
      assert listed.status_code == 200
      assert [s["id"] for s in listed.json()] == [created["id"]]


  @pytest.mark.asyncio
  async def test_rename_happy(authed_user):
      user, client = authed_user
      a = (await client.post("/me/saved-searches/", json=_body(name="Old"))).json()
      resp = await client.put(f"/me/saved-searches/{a['id']}", json={"name": "New"})
      assert resp.status_code == 200
      assert resp.json()["name"] == "New"


  @pytest.mark.asyncio
  async def test_delete_happy_then_404(authed_user):
      user, client = authed_user
      a = (await client.post("/me/saved-searches/", json=_body(name="Temp"))).json()
      assert (await client.delete(f"/me/saved-searches/{a['id']}")).status_code == 204
      assert (await client.delete(f"/me/saved-searches/{a['id']}")).status_code == 404


  @pytest.mark.asyncio
  async def test_list_ordered_name_asc(authed_user):
      user, client = authed_user
      for n in ["Zeta", "Alpha", "Mike"]:
          await client.post("/me/saved-searches/", json=_body(name=n))
      names = [s["name"] for s in (await client.get("/me/saved-searches/")).json()]
      assert names == ["Alpha", "Mike", "Zeta"]


  # ---------- 401 anonymous on every route ----------
  @pytest.mark.asyncio
  async def test_all_routes_401_anonymous(auth_client):
      assert (await auth_client.get("/me/saved-searches/")).status_code == 401
      assert (await auth_client.post("/me/saved-searches/", json=_body())).status_code == 401
      assert (await auth_client.put("/me/saved-searches/1", json={"name": "x"})).status_code == 401
      assert (await auth_client.delete("/me/saved-searches/1")).status_code == 401


  # ---------- cross-user isolation (404, indistinguishable from not-found) ----------
  @pytest.mark.asyncio
  async def test_cross_user_isolation(authed_user, db_session):
      user_a, client = authed_user
      a = (await client.post("/me/saved-searches/", json=_body(name="A-secret"))).json()
      # Switch to user B (login_as overwrites the cookie on the same client).
      await login_as(client, db_session, character_id=91000002, character_name="Bravo", owner_hash="OWN2")
      b_list = (await client.get("/me/saved-searches/")).json()
      assert all(s["id"] != a["id"] for s in b_list)  # B never sees A's row
      assert (await client.put(f"/me/saved-searches/{a['id']}", json={"name": "hijack"})).status_code == 404
      assert (await client.delete(f"/me/saved-searches/{a['id']}")).status_code == 404


  # ---------- 409 duplicate name via the real constraint (no pre-check) ----------
  @pytest.mark.asyncio
  async def test_duplicate_name_409_and_leaves_one_row(authed_user):
      user, client = authed_user
      assert (await client.post("/me/saved-searches/", json=_body(name="Dup"))).status_code == 201
      assert (await client.post("/me/saved-searches/", json=_body(name="Dup"))).status_code == 409
      # The 409 must NOT have rolled back the first row (savepoint discipline).
      dups = [s for s in (await client.get("/me/saved-searches/")).json() if s["name"] == "Dup"]
      assert len(dups) == 1


  @pytest.mark.asyncio
  async def test_rename_to_existing_name_409(authed_user):
      user, client = authed_user
      a = (await client.post("/me/saved-searches/", json=_body(name="A"))).json()
      b = (await client.post("/me/saved-searches/", json=_body(name="B"))).json()
      assert (await client.put(f"/me/saved-searches/{b['id']}", json={"name": "A"})).status_code == 409
      # B keeps its own name; A untouched.
      by_id = {s["id"]: s["name"] for s in (await client.get("/me/saved-searches/")).json()}
      assert by_id[b["id"]] == "B" and by_id[a["id"]] == "A"


  # ---------- per-user cap (best-effort, sequential — design §3.5) ----------
  @pytest.mark.asyncio
  async def test_cap_returns_400(authed_user, monkeypatch):
      from fastapi_app.core.config import settings
      monkeypatch.setattr(settings, "MAX_SAVED_SEARCHES_PER_USER", 2)
      user, client = authed_user
      for i in range(2):
          assert (await client.post("/me/saved-searches/", json=_body(name=f"S{i}"))).status_code == 201
      resp = await client.post("/me/saved-searches/", json=_body(name="S2"))
      assert resp.status_code == 400
      assert "limit" in resp.json()["detail"].lower()


  # ---------- 422 validation (bad search_parameters + name) ----------
  @pytest.mark.asyncio
  async def test_validation_422(authed_user):
      user, client = authed_user
      assert (await client.post("/me/saved-searches/", json=_body(search="ab"))).status_code == 422       # short search
      assert (await client.post("/me/saved-searches/", json=_body(min_price=-1))).status_code == 422      # negative price
      assert (await client.post("/me/saved-searches/", json=_body(min_me=5))).status_code == 422          # unknown key (extra=forbid)
      assert (await client.post("/me/saved-searches/", json={"search_parameters": {}})).status_code == 422  # missing name
      assert (await client.post("/me/saved-searches/", json=_body(name="   "))).status_code == 422         # blank name


  # ---------- app.openapi() schema assertions ----------
  def test_saved_searches_schema_bare_and_declares_errors():
      schema = app.openapi()
      assert "/me/saved-searches/" in schema["paths"]
      assert "/me/saved-searches/{search_id}" in schema["paths"]
      assert not any(p.startswith("/api/v1") for p in schema["paths"])  # PROXY-1 sentinel
      post_responses = schema["paths"]["/me/saved-searches/"]["post"]["responses"]
      for code in ("400", "401", "409"):
          assert code in post_responses
          assert post_responses[code]["content"]["application/json"]["schema"]["$ref"].endswith("ErrorDetail")
      put_responses = schema["paths"]["/me/saved-searches/{search_id}"]["put"]["responses"]
      assert "404" in put_responses and "409" in put_responses
      comps = schema["components"]["schemas"]
      assert comps["SavedSearchParameters"]["additionalProperties"] is False  # extra="forbid"
  ```
- [x] **Step 2: Run and confirm failure.**
  ```bash
  cd app/backend && pdm run pytest src/fastapi_app/tests/api/test_saved_searches.py -v
  ```
  Expected failure: collection/import error — `ModuleNotFoundError: No module named 'fastapi_app.services.saved_search_service'` (and the schema test asserts a `/me/saved-searches/` path that is not mounted yet).
- [x] **Step 3: Add the config setting.** In `core/config.py`, add under the Aggregation block (any location with the other scalars is fine). This establishes the single canonical `# --- M3 account features ---` block that Tasks 3.2 and 4.3 append their config fields INTO (do not start a second M3 block later):
  ```python
      # --- M3 account features ---
      # Per-user soft caps (best-effort count-checks, design §3.5).
      MAX_SAVED_SEARCHES_PER_USER: int = 100
  ```
  (Has a default, so no `export_openapi.py` `_ENV_DEFAULTS` change is needed — recon backend-api-patterns §5.) Document it in `app/backend/.env.example` per ENV-4 by adding, near the aggregation settings:
  ```bash
  # --- M3 account features ---
  # Per-user soft cap on saved searches (best-effort; enforced count-then-insert).
  MAX_SAVED_SEARCHES_PER_USER=100
  ```
- [x] **Step 4: Create the service `app/backend/src/fastapi_app/services/saved_search_service.py`.**
  ```python
  # ABOUTME: F005 saved-search CRUD — ownership-scoped queries, best-effort per-user cap, and unique-name
  # ABOUTME: 409 mapping via a SAVEPOINT (so a duplicate leaves the sibling row + outer transaction intact).
  from fastapi import HTTPException, status
  from sqlalchemy import func, select
  from sqlalchemy.exc import IntegrityError
  from sqlalchemy.ext.asyncio import AsyncSession

  from ..core.config import get_settings
  from ..models.account import SavedSearch
  from ..schemas.account import SavedSearchCreate, SavedSearchUpdate

  _DUPLICATE_DETAIL = "A saved search with this name already exists."


  async def list_saved_searches(db: AsyncSession, user_id: int) -> list[SavedSearch]:
      result = await db.execute(
          select(SavedSearch)
          .where(SavedSearch.user_id == user_id)
          .order_by(SavedSearch.name.asc())
      )
      return list(result.scalars().all())


  async def _get_owned(db: AsyncSession, user_id: int, search_id: int) -> SavedSearch:
      # Scope by user_id so not-owned is indistinguishable from not-found — a uniform 404
      # (anti-enumeration, design §4.5).
      row = (
          await db.execute(
              select(SavedSearch).where(
                  SavedSearch.id == search_id, SavedSearch.user_id == user_id
              )
          )
      ).scalar_one_or_none()
      if row is None:
          raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Saved search not found")
      return row


  async def create_saved_search(
      db: AsyncSession, user_id: int, payload: SavedSearchCreate
  ) -> SavedSearch:
      settings = get_settings()
      count = (
          await db.execute(
              select(func.count()).select_from(SavedSearch).where(SavedSearch.user_id == user_id)
          )
      ).scalar_one()
      if count >= settings.MAX_SAVED_SEARCHES_PER_USER:
          raise HTTPException(
              status_code=status.HTTP_400_BAD_REQUEST,
              detail=f"Saved search limit reached (maximum {settings.MAX_SAVED_SEARCHES_PER_USER}).",
          )
      row = SavedSearch(
          user_id=user_id,
          name=payload.name,
          search_parameters=payload.search_parameters.model_dump(),
      )
      try:
          # SAVEPOINT: a unique-name violation rolls back only this insert, keeping the outer
          # transaction (and any sibling rows) alive — the 409 is race-safe (no pre-check).
          async with db.begin_nested():
              db.add(row)
              await db.flush()
      except IntegrityError:
          raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=_DUPLICATE_DETAIL)
      # Reload server-default columns (created_at/updated_at) so response serialization is
      # pure in-memory and never triggers an async lazy-load (MissingGreenlet).
      await db.refresh(row)
      return row


  async def rename_saved_search(
      db: AsyncSession, user_id: int, search_id: int, payload: SavedSearchUpdate
  ) -> SavedSearch:
      row = await _get_owned(db, user_id, search_id)
      try:
          # begin_nested() flushes pending state when the savepoint is ENTERED, so the rename
          # assignment MUST happen INSIDE the savepoint. If `row.name = payload.name` were set
          # before `begin_nested()`, the unique-name violation would flush OUTSIDE the savepoint
          # and poison the begin-once outer transaction instead of rolling back only this statement.
          async with db.begin_nested():
              row.name = payload.name
              await db.flush()
      except IntegrityError:
          raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=_DUPLICATE_DETAIL)
      await db.refresh(row)
      return row


  async def delete_saved_search(db: AsyncSession, user_id: int, search_id: int) -> None:
      row = await _get_owned(db, user_id, search_id)
      await db.delete(row)
      await db.flush()
  ```
- [x] **Step 5: Create the router `app/backend/src/fastapi_app/api/saved_searches.py`.**
  ```python
  # ABOUTME: F005 saved-searches router — bare-mounted /me/saved-searches (PROXY-1), auth-gated via get_current_user.
  # ABOUTME: Declares 400/401/404/409 with ErrorDetail so the typed client sees the real error bodies (design §4.5).
  from fastapi import APIRouter, Depends, Response, status
  from sqlalchemy.ext.asyncio import AsyncSession

  from ..core.current_user import get_current_user
  from ..db import get_db
  from ..models import User
  from ..schemas.account import SavedSearchCreate, SavedSearchSchema, SavedSearchUpdate
  from ..schemas.auth import ErrorDetail
  from ..services import saved_search_service

  router = APIRouter(prefix="/me/saved-searches", tags=["Saved Searches"])

  _UNAUTH = {401: {"model": ErrorDetail, "description": "Not authenticated"}}
  _NOT_FOUND = {404: {"model": ErrorDetail, "description": "Saved search not found"}}
  _DUPLICATE = {409: {"model": ErrorDetail, "description": "Duplicate saved-search name"}}
  _CAP = {400: {"model": ErrorDetail, "description": "Per-user saved-search cap reached"}}


  @router.get("/", response_model=list[SavedSearchSchema], responses={**_UNAUTH})
  async def list_saved_searches(
      user: User = Depends(get_current_user),
      db: AsyncSession = Depends(get_db),
  ):
      return await saved_search_service.list_saved_searches(db, user.id)


  @router.post(
      "/",
      response_model=SavedSearchSchema,
      status_code=status.HTTP_201_CREATED,
      responses={**_UNAUTH, **_CAP, **_DUPLICATE},
  )
  async def create_saved_search(
      payload: SavedSearchCreate,
      user: User = Depends(get_current_user),
      db: AsyncSession = Depends(get_db),
  ):
      return await saved_search_service.create_saved_search(db, user.id, payload)


  @router.put(
      "/{search_id}",
      response_model=SavedSearchSchema,
      responses={**_UNAUTH, **_NOT_FOUND, **_DUPLICATE},
  )
  async def rename_saved_search(
      search_id: int,
      payload: SavedSearchUpdate,
      user: User = Depends(get_current_user),
      db: AsyncSession = Depends(get_db),
  ):
      return await saved_search_service.rename_saved_search(db, user.id, search_id, payload)


  @router.delete(
      "/{search_id}",
      status_code=status.HTTP_204_NO_CONTENT,
      responses={**_UNAUTH, **_NOT_FOUND},
  )
  async def delete_saved_search(
      search_id: int,
      user: User = Depends(get_current_user),
      db: AsyncSession = Depends(get_db),
  ):
      await saved_search_service.delete_saved_search(db, user.id, search_id)
      return Response(status_code=status.HTTP_204_NO_CONTENT)
  ```
- [x] **Step 6: Mount the router in `main.py`.** Add the import beside the existing router imports (near `main.py:25-26`):
  ```python
  from .api import saved_searches as saved_searches_router
  ```
  and add the mount beside the existing `include_router` calls (near `main.py:192-194`):
  ```python
  app.include_router(saved_searches_router.router)   # /me/saved-searches/* (bare, PROXY-1)
  ```
- [x] **Step 7: Run the F005 suite and confirm green.**
  ```bash
  cd app/backend && pdm run pytest src/fastapi_app/tests/api/test_saved_searches.py -v
  ```
  Expected: all pass (CRUD, 401×4, cross-user 404×3, 409 duplicate+rename, cap 400, 422×5, ordering, schema).
- [x] **Step 8: Run the full backend suite to confirm no regression.**
  ```bash
  cd app/backend && pdm run pytest -q
  ```
  Expected: the Phase-0 baseline count plus all Section-A additions, green. In particular `test_me_schema.py`'s PROXY-1 sentinel still passes (no `/api/v1` path introduced).
- [x] **Step 9: Lint + commit.**
  ```bash
  cd app/backend && pdm run lint
  git add app/backend/src/fastapi_app/services/saved_search_service.py app/backend/src/fastapi_app/api/saved_searches.py app/backend/src/fastapi_app/core/config.py app/backend/.env.example app/backend/src/fastapi_app/main.py app/backend/src/fastapi_app/tests/api/test_saved_searches.py
  ```
  then commit with:
  ```
  feat(api): add saved-searches CRUD endpoints

  Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>
  ```
- [x] **Step 10: Push the campaign branch (first push of the campaign).**
  ```bash
  git push -u origin claude/m3-account-features
  ```

```
BEFORE marking this task complete:
1. Review tests against docs/pitfalls/testing-pitfalls.md — TEST-1 (HTTP-level + app.openapi()),
   TEST-3 (ordering fixture uses distinct names), §3 error-path + anti-enumeration (uniform 404),
   §5 idempotency (duplicate 409 does not 500 and leaves exactly one row).
2. Verify test coverage (error paths? edge cases?) — every declared status (201/200/204/400/401/404/409/422)
   is exercised over HTTP, and the 409 test proves the SAVEPOINT preserves the sibling row.
3. Run tests and confirm green (F005 suite + full backend suite).
```

```
After completing this phase:
Review the batch from multiple perspectives (correctness, pitfalls compliance, test coverage).
Minimum 3 review rounds. If round 3 still finds issues, keep going until clean.
```
<!-- Section B of the M3 implementation plan: Phase 3 (F006 Watchlist backend), Phase 4 (F007 Alerts backend), Phase 5 (codegen). -->
<!-- Authored against origin/dev tip a7b0f26; every signature verified against real source 2026-07-17. -->

# M3 Plan — Section B: F006 Watchlist backend, F007 Alerts backend, Codegen

> **Scope of this section:** Phases 3–5. Phase 3 builds the F006 watchlist backend (ESI name
> resolution, watchlist CRUD, the add pipeline). Phase 4 builds the F007 alerts backend (notifications
> API, the watchlist matcher job, scheduler wiring). Phase 5 regenerates the typed client.
>
> **Assumed-already-built by earlier phases (do NOT recreate — you ADD to these files):**
> - `app/backend/src/fastapi_app/models/account.py` — `SavedSearch`, `WatchlistItem`, `Notification`
>   (columns per design §4.2), re-exported from `models/__init__.py`; the partial unique index
>   `uq_notifications_watchlist_dedup` on `(user_id, contract_id, watch_type_id)` with
>   `postgresql_where=(type == 'watchlist_match')`; `User.watchlist_alerts_enabled` (Boolean, not
>   null, `server_default sa.true()`).
> - `app/backend/src/fastapi_app/core/current_user.py` — `get_current_user` (design §4.1) returning the
>   ORM `User`; `session: dict = Depends(get_current_session)` is its first dependency, so a request
>   with no session cookie 401s **before** `get_current_user`'s body runs.
> - `app/backend/src/fastapi_app/schemas/account.py` — exists with the saved-search half
>   (`SavedSearchParameters`, `SavedSearchCreate`, `SavedSearchUpdate`, `SavedSearchSchema`). You ADD
>   the watchlist and notification schemas to this same file.
> - `app/backend/src/fastapi_app/tests/conftest.py` — `authed_user` async fixture (returns
>   `(user, auth_client)`; inserts `User(character_id=91000001, character_name="Sesta Hound",
>   owner_hash="OWN1")`, flushes, mints a session with `user_id=user.id`, sets the cookie) and the
>   helper `async def login_as(auth_client, db_session, *, character_id, character_name, owner_hash)`
>   (inserts + logs in another user, returns the `User`; it OVERWRITES the client cookie).
> - `app/backend/src/fastapi_app/main.py` — the F005 saved-searches router is mounted by the earlier
>   phase. You ADD the watchlist + notifications router mounts and the matcher lifespan wiring.
>
> **Campaign branch (established in Phase 0):** all commands below run inside the worktree
> `.claude/worktrees/m3-account-features` on branch `claude/m3-account-features`. Backend edits run
> under `pdm run pytest` ONLY — never under `pdm run dev`/`--reload` during implementation (ENV-2/ENV-3
> drop+recreate the DB and re-ingest on every `.py` save). Commit after every green step-pair; push at
> phase boundaries.

---

## Verified-source notes that shape these phases (READ FIRST — source overrode recon here)

1. **`ESIClient._get_esi_object` raises `httpx.HTTPStatusError` on 4xx, `ESIRequestFailedError` only on
   5xx/network.** `core/esi_client_class.py:217-244`: the retry loop `break`s on any `status_code < 500`
   with `last_exception = None`, then falls through to `response.raise_for_status()` — which raises
   `httpx.HTTPStatusError` for a 404. So `get_universe_type`/`get_universe_group` on a **404** raise
   `httpx.HTTPStatusError` (NOT `ESIRequestFailedError`); only a persistent **5xx** (after 3 retries,
   ~1.5 s) or a network error raises `ESIRequestFailedError`. **Consequence:** the watchlist service
   MUST catch BOTH exception types around the type/group calls, or the design's "ESI type-404 ⇒ 400,
   not 502" requirement fails (an uncaught `HTTPStatusError` would 500). This is why Task 3.2's service
   maps `httpx.HTTPStatusError` 4xx→400 and `ESIRequestFailedError` 5xx→502.
2. **The test-lane ESI base URL is `http://sso.test`.** `conftest.py:183` sets
   `real_app.state.http_client = httpx.AsyncClient(base_url="http://sso.test")`, and `get_esi_client`
   (`core/dependencies.py:39-50`) injects that client into the request-path `ESIClient`. So watchlist
   HTTP tests register `httpx_mock` responses at `http://sso.test/v1/universe/ids/`,
   `http://sso.test/v3/universe/types/{id}/`, `http://sso.test/v1/universe/groups/{gid}/`.
3. **Type/group lookups read the Valkey cache first.** `_get_esi_object` reads `esi-object:{path}` from
   `app.state.redis` (the test `FakeRedis`) before the HTTP call and writes it after. A second add of
   the same `type_id` inside one test hits that cache — register type/group responses with
   `is_reusable=True` when a test triggers two lookups of the same id (the 409-duplicate test).
4. **Matcher DB correctness is tested via the INNER methods, not `run_matching()`.** `run_matching()`
   builds its OWN engine on `settings.DATABASE_URL` (the dev DB), so it cannot see rows arranged in the
   test's rolled-back `db_session` — exactly like `ContractAggregationService.run_aggregation` vs
   `_process_contracts`. Tests call `_match_and_notify(db_session)` / `_prune(db_session)` directly
   with the test session (design §6). `run_matching()`'s only unit-tested path is the lock (via the
   `FakeLockRedis` double), which returns before any engine is created.
5. **All five M3 config fields have defaults**, so `export_openapi.py`'s `_ENV_DEFAULTS` needs NO change
   (verified `src/export_openapi.py:16-23` + the `_ENV_DEFAULTS` trap in recon §5). Add
   `MAX_WATCHLIST_ITEMS_PER_USER` in Task 3.2 (its first consumer) and the three matcher/notification
   fields in Task 4.3. `MAX_SAVED_SEARCHES_PER_USER` is owned by the F005 saved-searches section (its
   first consumer is `saved_search_service`); if that section did not add it, add it alongside Task
   4.3's fields. See the "Cross-section coordination" note at the end.

---

## Phase 3 — F006 Watchlist backend (ESI resolution + watchlist CRUD)

**Execution Status:** ✅ SHIPPED at `bd3aa68` on 2026-07-18

Goal: `ESIClient.resolve_names`, the watchlist request/response schemas, `watchlist_service` (the design
§4.5 add pipeline in binding order), `api/watchlist.py`, the `main.py` mount, the
`MAX_WATCHLIST_ITEMS_PER_USER` config field, and the full HTTP test matrix.

---

### Task 3.1: `ESIClient.resolve_names` (exact-name → ids)

```
BEFORE starting work:
1. Invoke superpowers:test-driven-development
2. Read docs/pitfalls/testing-pitfalls.md
Follow TDD: write failing test → implement → verify green.
```

**Files:**
- Modify: `app/backend/src/fastapi_app/core/esi_client_class.py` (add `resolve_names` after
  `resolve_ids_to_names`, ~line 288).
- Test (Create): `app/backend/src/fastapi_app/tests/core/test_esi_client_resolve_names.py`.

- [x] **Step 1: Write the failing test module.** Create
  `app/backend/src/fastapi_app/tests/core/test_esi_client_resolve_names.py`:

```python
# ABOUTME: Unit tests for ESIClient.resolve_names (POST /v1/universe/ids/, ESI-1 version pin).
# ABOUTME: Drives the seam with pytest-httpx; covers hit, empty-result body, 4xx, 5xx, network error.
from unittest.mock import MagicMock

import httpx
import pytest

from fastapi_app.core.esi_client_class import ESIClient
from fastapi_app.core.exceptions import ESIRequestFailedError

pytestmark = pytest.mark.asyncio

ESI = "http://esi.test"
IDS_URL = f"{ESI}/v1/universe/ids/"


def _client(http: httpx.AsyncClient) -> ESIClient:
    # settings is unused by resolve_names (only http_client is touched); a MagicMock is enough.
    return ESIClient(settings=MagicMock(), http_client=http)


async def test_resolve_names_returns_parsed_body(httpx_mock):
    httpx_mock.add_response(
        method="POST", url=IDS_URL,
        json={"inventory_types": [{"id": 587, "name": "Rifter"}]},
    )
    async with httpx.AsyncClient(base_url=ESI) as http:
        body = await _client(http).resolve_names(["Rifter"])
    assert body["inventory_types"][0]["id"] == 587
    posted = httpx_mock.get_requests()[0]
    assert posted.url.path == "/v1/universe/ids/"   # ESI-1 version pin


async def test_resolve_names_empty_result_body_returns_empty_dict(httpx_mock):
    # ESI answers 200 with no matching category keys when nothing resolves.
    httpx_mock.add_response(method="POST", url=IDS_URL, json={})
    async with httpx.AsyncClient(base_url=ESI) as http:
        body = await _client(http).resolve_names(["Not A Real Ship 9000"])
    assert body == {}


async def test_resolve_names_4xx_raises_with_status(httpx_mock):
    httpx_mock.add_response(method="POST", url=IDS_URL, status_code=404, json={"error": "not found"})
    async with httpx.AsyncClient(base_url=ESI) as http:
        with pytest.raises(ESIRequestFailedError) as exc:
            await _client(http).resolve_names(["x"])
    assert exc.value.status_code == 404


async def test_resolve_names_5xx_raises_with_status(httpx_mock):
    httpx_mock.add_response(method="POST", url=IDS_URL, status_code=503, text="upstream down")
    async with httpx.AsyncClient(base_url=ESI) as http:
        with pytest.raises(ESIRequestFailedError) as exc:
            await _client(http).resolve_names(["x"])
    assert exc.value.status_code == 503


async def test_resolve_names_network_error_raises(httpx_mock):
    httpx_mock.add_exception(httpx.ConnectError("boom"), url=IDS_URL)
    async with httpx.AsyncClient(base_url=ESI) as http:
        with pytest.raises(ESIRequestFailedError):
            await _client(http).resolve_names(["x"])


async def test_resolve_names_non_json_body_raises(httpx_mock):
    # A 200 with a non-JSON body (e.g. an upstream HTML error page) must not escape as a raw
    # ValueError/500 — response.json() failures normalize to ESIRequestFailedError (design §4.5).
    httpx_mock.add_response(method="POST", url=IDS_URL, status_code=200, text="<html>not json</html>")
    async with httpx.AsyncClient(base_url=ESI) as http:
        with pytest.raises(ESIRequestFailedError):
            await _client(http).resolve_names(["x"])
```

- [x] **Step 2: Run the test, confirm it fails.**
  `cd app/backend && pdm run pytest src/fastapi_app/tests/core/test_esi_client_resolve_names.py -v`
  Expected failure: `AttributeError: 'ESIClient' object has no attribute 'resolve_names'` (collection
  passes; each test errors on the missing method).

- [x] **Step 3: Implement `resolve_names`.** In `core/esi_client_class.py`, add after
  `resolve_ids_to_names` (the file already imports `httpx` and `ESIRequestFailedError`):

```python
    async def resolve_names(self, names: list[str]) -> dict[str, Any]:
        """Resolve exact EVE names to ids via POST /v1/universe/ids/ (version-pinned per ESI-1).

        Returns the parsed response body — a dict of category → [{id, name}, ...] (e.g.
        `inventory_types`); an unmatched name yields a 200 with that category absent. Unlike
        the enrichment fetches this is not cached: watchlist adds are rare and the caller wants
        an authoritative resolution. Non-2xx statuses and network errors surface as
        ESIRequestFailedError so the caller can map 4xx→400 / 5xx→502 (design §4.5).
        """
        try:
            response = await self.http_client.post("/v1/universe/ids/", json=names)
        except httpx.RequestError as e:
            # RequestError covers ReadTimeout / ConnectError / ConnectTimeout / etc. — any transport
            # failure surfaces as ESIRequestFailedError so the caller maps it to 502, never a raw 500.
            raise ESIRequestFailedError(message=f"Network error resolving names: {e}")
        if not (200 <= response.status_code < 300):
            raise ESIRequestFailedError(
                status_code=response.status_code,
                message=f"universe/ids resolution failed: HTTP {response.status_code}",
            )
        try:
            data = response.json()
        except ValueError:
            raise ESIRequestFailedError(message="Non-JSON body from /v1/universe/ids/")
        if not isinstance(data, dict):
            raise ESIRequestFailedError(
                message=f"Expected JSON object from /v1/universe/ids/, got {type(data).__name__}"
            )
        return data
```

- [x] **Step 4: Run the test, confirm green.**
  `cd app/backend && pdm run pytest src/fastapi_app/tests/core/test_esi_client_resolve_names.py -v`
  All 6 pass; output pristine.

- [x] **Step 5: Commit.**
  `git add app/backend/src/fastapi_app/core/esi_client_class.py app/backend/src/fastapi_app/tests/core/test_esi_client_resolve_names.py`
  ```
  feat(api): add ESIClient.resolve_names for exact ship-name resolution

  Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>
  ```

```
BEFORE marking this task complete:
1. Review tests against docs/pitfalls/testing-pitfalls.md
2. Verify test coverage (error paths? edge cases?)
3. Run tests and confirm green
```

---

### Task 3.2: Watchlist schemas + `watchlist_service` + `api/watchlist.py` + mount + config + tests

```
BEFORE starting work:
1. Invoke superpowers:test-driven-development
2. Read docs/pitfalls/testing-pitfalls.md
Follow TDD: write failing test → implement → verify green.
```

```
If any test assertion races, flakes, or fails nondeterministically, the fix is deterministic
synchronization or deterministic fixture data — NOT assertion removal or weakening. If
synchronization cannot make the assertion pass reliably, STOP and raise to the dispatching
agent. Do not ship a weaker test. Prefer mechanism assertions (state observed) over symptom
assertions (timing bounds).
```
(This task's ordering assertion — `type_name ASC, type_id ASC` — is TEST-3 territory: build fixtures
with a deliberate same-name/distinct-type_id tiebreaker, never rely on insertion order.)

**Files:**
- Modify: `app/backend/src/fastapi_app/schemas/account.py` (ADD watchlist schemas).
- Modify: `app/backend/src/fastapi_app/core/config.py` (ADD `MAX_WATCHLIST_ITEMS_PER_USER`).
- Create: `app/backend/src/fastapi_app/services/watchlist_service.py`.
- Create: `app/backend/src/fastapi_app/api/watchlist.py`.
- Modify: `app/backend/src/fastapi_app/main.py` (import + mount `watchlist` router).
- Test (Create): `app/backend/src/fastapi_app/tests/api/test_watchlist.py`.

- [x] **Step 1: Add the config field.** In `core/config.py`, append INTO the single
  `# --- M3 account features ---` block established in Task 2.2 (do NOT start a second M3 block) — add
  the field beside `MAX_SAVED_SEARCHES_PER_USER` (default present → no `_ENV_DEFAULTS` change needed):

```python
    MAX_WATCHLIST_ITEMS_PER_USER: int = 200
```
Also document it in `app/backend/.env.example` (ENV-4), under the same `# --- M3 account features ---`
block: `MAX_WATCHLIST_ITEMS_PER_USER=200`.

- [x] **Step 2: Add the watchlist schemas.** Append to `schemas/account.py` (ensure imports at top of
  the file include `from datetime import datetime`, `from typing import Optional`,
  `from pydantic import BaseModel, ConfigDict, Field, model_validator, field_validator`):

```python
class WatchlistItemCreate(BaseModel):
    """Add-watchlist body: exactly one of type_id / type_name, plus optional max_price / notes."""

    type_id: Optional[int] = Field(default=None, gt=0)
    type_name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    max_price: Optional[float] = Field(default=None, ge=0.01, description="ISK; >= 0.01 when present.")
    notes: Optional[str] = Field(default=None, max_length=500)

    @field_validator("type_name", "notes")
    @classmethod
    def _strip_blank_to_none(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        v = v.strip()
        return v or None

    @model_validator(mode="after")
    def _exactly_one_identifier(self):
        if (self.type_id is None) == (self.type_name is None):
            raise ValueError("provide exactly one of type_id or type_name")
        return self


class WatchlistItemUpdate(BaseModel):
    """Partial update: omitted field preserves, explicit JSON null clears (via model_fields_set)."""

    max_price: Optional[float] = Field(default=None, ge=0.01)
    notes: Optional[str] = Field(default=None, max_length=500)


class WatchlistItemSchema(BaseModel):
    id: int
    type_id: int
    type_name: str
    max_price: Optional[float] = None
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
```

- [x] **Step 3: Write the failing test module.** Create
  `app/backend/src/fastapi_app/tests/api/test_watchlist.py`. This is the full design-§6 matrix; it
  fails at import (`api.watchlist` / `services.watchlist_service` don't exist yet).

```python
# ABOUTME: HTTP-level tests for the /me/watchlist-items surface (F006) — add pipeline, CRUD, auth.
# ABOUTME: ESI is mocked at the app.state.http_client seam (base http://sso.test) via pytest-httpx.
import pytest
from sqlalchemy import select

from fastapi_app.main import app as real_app
from fastapi_app.models import WatchlistItem
from fastapi_app.core.config import settings


ESI = "http://sso.test"
IDS_URL = f"{ESI}/v1/universe/ids/"


def _type_url(type_id: int) -> str:
    return f"{ESI}/v3/universe/types/{type_id}/"


def _group_url(group_id: int) -> str:
    return f"{ESI}/v1/universe/groups/{group_id}/"


def _published_ship(name="Rifter", group_id=25):
    return {"name": name, "group_id": group_id, "published": True, "market_group_id": 1}


def _ship_group(group_id=25):
    return {"name": "Frigate", "category_id": 6}


# ---------- happy paths ----------

@pytest.mark.asyncio
async def test_add_by_type_id_denormalizes_name(authed_user, httpx_mock, db_session):
    user, client = authed_user
    httpx_mock.add_response(method="GET", url=_type_url(587), json=_published_ship("Rifter", 25))
    httpx_mock.add_response(method="GET", url=_group_url(25), json=_ship_group(25))

    resp = await client.post("/me/watchlist-items/", json={"type_id": 587, "max_price": 5000000})
    assert resp.status_code == 201
    body = resp.json()
    assert body["type_id"] == 587
    assert body["type_name"] == "Rifter"
    assert body["max_price"] == 5000000.0

    row = (await db_session.execute(select(WatchlistItem).where(WatchlistItem.user_id == user.id))).scalar_one()
    assert row.type_name == "Rifter"


@pytest.mark.asyncio
async def test_add_by_name_resolves_then_validates(authed_user, httpx_mock, db_session):
    user, client = authed_user
    httpx_mock.add_response(method="POST", url=IDS_URL,
                            json={"inventory_types": [{"id": 587, "name": "Rifter"}]})
    httpx_mock.add_response(method="GET", url=_type_url(587), json=_published_ship("Rifter", 25))
    httpx_mock.add_response(method="GET", url=_group_url(25), json=_ship_group(25))

    resp = await client.post("/me/watchlist-items/", json={"type_name": "Rifter", "notes": "wishlist"})
    assert resp.status_code == 201
    assert resp.json()["type_id"] == 587
    assert resp.json()["notes"] == "wishlist"


# ---------- validation / ESI error discrimination (no row inserted) ----------

@pytest.mark.asyncio
async def test_add_non_ship_category_400(authed_user, httpx_mock, db_session):
    user, client = authed_user
    httpx_mock.add_response(method="GET", url=_type_url(34), json=_published_ship("Tritanium", 18))
    httpx_mock.add_response(method="GET", url=_group_url(18), json={"name": "Mineral", "category_id": 4})
    resp = await client.post("/me/watchlist-items/", json={"type_id": 34})
    assert resp.status_code == 400
    assert (await db_session.execute(select(WatchlistItem))).first() is None


@pytest.mark.asyncio
async def test_add_unpublished_400(authed_user, httpx_mock, db_session):
    user, client = authed_user
    httpx_mock.add_response(method="GET", url=_type_url(999),
                            json={"name": "Old Hull", "group_id": 25, "published": False})
    resp = await client.post("/me/watchlist-items/", json={"type_id": 999})
    assert resp.status_code == 400
    assert (await db_session.execute(select(WatchlistItem))).first() is None


@pytest.mark.asyncio
async def test_add_esi_type_404_is_400_not_502(authed_user, httpx_mock, db_session):
    # _get_esi_object 4xx -> httpx.HTTPStatusError (NOT ESIRequestFailedError); service maps 4xx->400.
    user, client = authed_user
    httpx_mock.add_response(method="GET", url=_type_url(424242), status_code=404, json={"error": "nope"})
    resp = await client.post("/me/watchlist-items/", json={"type_id": 424242})
    assert resp.status_code == 400
    assert (await db_session.execute(select(WatchlistItem))).first() is None


@pytest.mark.asyncio
async def test_add_esi_5xx_is_502(authed_user, httpx_mock, db_session):
    # _get_esi_object retries 5xx 3x (~1.5s) then raises ESIRequestFailedError(status=503) -> 502.
    # Repeatable response; DO NOT assert request count == 1 (retries are load-bearing).
    user, client = authed_user
    httpx_mock.add_response(method="GET", url=_type_url(587), status_code=503, text="down", is_reusable=True)
    resp = await client.post("/me/watchlist-items/", json={"type_id": 587})
    assert resp.status_code == 502
    assert (await db_session.execute(select(WatchlistItem))).first() is None


@pytest.mark.asyncio
async def test_add_unknown_name_400(authed_user, httpx_mock, db_session):
    user, client = authed_user
    httpx_mock.add_response(method="POST", url=IDS_URL, json={})   # no inventory_types
    resp = await client.post("/me/watchlist-items/", json={"type_name": "Notaship 9000"})
    assert resp.status_code == 400
    assert "unknown ship name" in resp.json()["detail"]
    assert (await db_session.execute(select(WatchlistItem))).first() is None


@pytest.mark.asyncio
async def test_add_neither_identifier_422(authed_user, db_session):
    user, client = authed_user
    resp = await client.post("/me/watchlist-items/", json={"max_price": 5})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_add_both_identifiers_422(authed_user, db_session):
    user, client = authed_user
    resp = await client.post("/me/watchlist-items/", json={"type_id": 587, "type_name": "Rifter"})
    assert resp.status_code == 422


# ---------- duplicate + cap ----------

@pytest.mark.asyncio
async def test_add_duplicate_type_409(authed_user, httpx_mock, db_session):
    user, client = authed_user
    # reusable because the 2nd add re-reads type/group (cache may or may not serve it).
    httpx_mock.add_response(method="GET", url=_type_url(587), json=_published_ship("Rifter", 25), is_reusable=True)
    httpx_mock.add_response(method="GET", url=_group_url(25), json=_ship_group(25), is_reusable=True)
    first = await client.post("/me/watchlist-items/", json={"type_id": 587})
    assert first.status_code == 201
    second = await client.post("/me/watchlist-items/", json={"type_id": 587})
    assert second.status_code == 409
    rows = (await db_session.execute(select(WatchlistItem).where(WatchlistItem.user_id == user.id))).scalars().all()
    assert len(rows) == 1


@pytest.mark.asyncio
async def test_cap_short_circuits_before_any_esi_call(authed_user, httpx_mock, db_session, monkeypatch):
    user, client = authed_user
    monkeypatch.setattr(settings, "MAX_WATCHLIST_ITEMS_PER_USER", 0)
    resp = await client.post("/me/watchlist-items/", json={"type_id": 587})
    assert resp.status_code == 400
    assert httpx_mock.get_requests() == []   # cap check fired before ESI traffic
    assert (await db_session.execute(select(WatchlistItem))).first() is None


# ---------- PUT partial-update semantics ----------

async def _seed_item(db_session, user, *, type_id=587, type_name="Rifter", max_price=100, notes="a"):
    item = WatchlistItem(user_id=user.id, type_id=type_id, type_name=type_name,
                         max_price=max_price, notes=notes)
    db_session.add(item)
    await db_session.flush()
    return item


@pytest.mark.asyncio
async def test_put_omitted_field_preserves(authed_user, db_session):
    user, client = authed_user
    item = await _seed_item(db_session, user, max_price=100, notes="a")
    resp = await client.put(f"/me/watchlist-items/{item.id}", json={"notes": "x"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["notes"] == "x"
    assert body["max_price"] == 100.0   # omitted -> preserved


@pytest.mark.asyncio
async def test_put_explicit_null_clears(authed_user, db_session):
    user, client = authed_user
    item = await _seed_item(db_session, user, max_price=100, notes="a")
    resp = await client.put(f"/me/watchlist-items/{item.id}", json={"max_price": None})
    assert resp.status_code == 200
    body = resp.json()
    assert body["max_price"] is None      # explicit null -> cleared
    assert body["notes"] == "a"           # omitted -> preserved


# ---------- list ordering (TEST-3: same-name tiebreaker on type_id) ----------

@pytest.mark.asyncio
async def test_list_ordered_type_name_then_type_id(authed_user, db_session):
    user, client = authed_user
    await _seed_item(db_session, user, type_id=200, type_name="Alpha", max_price=None, notes=None)
    await _seed_item(db_session, user, type_id=100, type_name="Alpha", max_price=None, notes=None)
    await _seed_item(db_session, user, type_id=50, type_name="Beta", max_price=None, notes=None)
    resp = await client.get("/me/watchlist-items/")
    assert resp.status_code == 200
    ordered = [(r["type_name"], r["type_id"]) for r in resp.json()]
    assert ordered == [("Alpha", 100), ("Alpha", 200), ("Beta", 50)]


# ---------- cross-user isolation (uniform 404) ----------

@pytest.mark.asyncio
async def test_cross_user_put_and_delete_404(authed_user, db_session):
    user_a, client = authed_user
    item = await _seed_item(db_session, user_a)
    # login_as overwrites the cookie to user B; A's item id must be invisible to B.
    from fastapi_app.tests.conftest import login_as  # helper defined by the earlier phase
    await login_as(client, db_session, character_id=91000002, character_name="Other Pilot", owner_hash="OWN2")
    assert (await client.put(f"/me/watchlist-items/{item.id}", json={"notes": "y"})).status_code == 404
    assert (await client.delete(f"/me/watchlist-items/{item.id}")).status_code == 404
    # A's row is untouched.
    still = (await db_session.execute(select(WatchlistItem).where(WatchlistItem.id == item.id))).scalar_one()
    assert still.notes == "a"


# ---------- delete happy + not-found ----------

@pytest.mark.asyncio
async def test_delete_removes_own_item(authed_user, db_session):
    user, client = authed_user
    item = await _seed_item(db_session, user)
    assert (await client.delete(f"/me/watchlist-items/{item.id}")).status_code == 204
    assert (await db_session.execute(select(WatchlistItem).where(WatchlistItem.id == item.id))).first() is None


@pytest.mark.asyncio
async def test_delete_missing_404(authed_user, db_session):
    user, client = authed_user
    assert (await client.delete("/me/watchlist-items/999999")).status_code == 404


# ---------- anonymous 401 on EVERY route+method (auth_client sets app.state.redis; no session cookie) ----------

@pytest.mark.parametrize("method, path, json_body", [
    ("POST", "/me/watchlist-items/", {"type_id": 587}),
    ("GET", "/me/watchlist-items/", None),
    ("PUT", "/me/watchlist-items/1", {"notes": "x"}),
    ("DELETE", "/me/watchlist-items/1", None),
])
@pytest.mark.asyncio
async def test_every_watchlist_route_401_anonymous(auth_client, method, path, json_body):
    # get_current_user's first dependency is get_current_session, so a cookieless request 401s
    # before any handler body runs — assert it for every method/path the router declares.
    resp = await auth_client.request(method, path, json=json_body)
    assert resp.status_code == 401


# ---------- OpenAPI schema (PROXY-1 + declared error bodies + 401 on every operation) ----------

def test_openapi_watchlist_paths_bare_and_declared():
    schema = real_app.openapi()
    paths = schema["paths"]
    assert "/me/watchlist-items/" in paths
    assert "/me/watchlist-items/{item_id}" in paths
    assert not any(p.startswith("/api/v1") for p in paths)   # PROXY-1 sentinel
    post = paths["/me/watchlist-items/"]["post"]
    assert set(post["responses"]) >= {"201", "400", "401", "409", "422", "502"}
    # every new watchlist operation must declare a 401 response (design §4.5 acceptance criterion).
    for path, method in [
        ("/me/watchlist-items/", "post"),
        ("/me/watchlist-items/", "get"),
        ("/me/watchlist-items/{item_id}", "put"),
        ("/me/watchlist-items/{item_id}", "delete"),
    ]:
        assert "401" in paths[path][method]["responses"]
```

- [x] **Step 4: Run the test, confirm it fails.**
  `cd app/backend && pdm run pytest src/fastapi_app/tests/api/test_watchlist.py -v`
  Expected failure: `ModuleNotFoundError: No module named 'fastapi_app.api.watchlist'` (import-time
  collection error).

- [x] **Step 5: Implement `watchlist_service.py`.** Create
  `app/backend/src/fastapi_app/services/watchlist_service.py`:

```python
# ABOUTME: F006 watchlist CRUD + the design §4.5 add pipeline (cap -> resolve -> validate -> insert).
# ABOUTME: ESI error discrimination: 4xx -> 400 (bad request), 5xx/network -> 502 (retryable outage).
from typing import Any, Optional

import httpx
from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config import settings
from ..core.esi_client_class import ESIClient
from ..core.exceptions import ESIRequestFailedError
from ..models import User, WatchlistItem
from ..schemas.account import WatchlistItemCreate, WatchlistItemUpdate

SHIP_CATEGORY_ID = 6  # EVE static "Ship" category


def _map_esi_failure(status_code: int, invalid_msg: str) -> HTTPException:
    """4xx from ESI is a bad request (400); 5xx / network (status 0) is a retryable outage (502)."""
    if 400 <= status_code < 500:
        return HTTPException(status_code=400, detail=invalid_msg)
    return HTTPException(status_code=502, detail="Ship metadata service is unavailable; try again.")


async def _fetch_type_or_400_502(esi_client: ESIClient, type_id: int) -> dict[str, Any]:
    try:
        return await esi_client.get_universe_type(type_id)
    except ESIRequestFailedError as e:                 # 5xx / network after retries
        raise _map_esi_failure(e.status_code, "unknown or invalid type")
    except httpx.HTTPStatusError as e:                 # 4xx (e.g. 404) — see source note #1
        raise _map_esi_failure(e.response.status_code, "unknown or invalid type")


async def _fetch_group_or_400_502(esi_client: ESIClient, group_id: int) -> dict[str, Any]:
    try:
        return await esi_client.get_universe_group(group_id)
    except ESIRequestFailedError as e:
        raise _map_esi_failure(e.status_code, "unknown or invalid type")
    except httpx.HTTPStatusError as e:
        raise _map_esi_failure(e.response.status_code, "unknown or invalid type")


async def _resolve_name_to_type_id(esi_client: ESIClient, name: str) -> int:
    try:
        body = await esi_client.resolve_names([name])
    except ESIRequestFailedError as e:
        raise _map_esi_failure(e.status_code, "unknown ship name")
    inventory_types = body.get("inventory_types") or []
    if not inventory_types:
        raise HTTPException(status_code=400, detail="unknown ship name")
    # ESI exact-matches; a non-empty inventory_types means the name resolved.
    return int(inventory_types[0]["id"])


async def add_watchlist_item(
    db: AsyncSession, esi_client: ESIClient, user: User, payload: WatchlistItemCreate
) -> WatchlistItem:
    # (1) cap-count check — BEFORE any ESI traffic (design §4.5 binding order).
    count = await db.scalar(
        select(func.count()).select_from(WatchlistItem).where(WatchlistItem.user_id == user.id)
    )
    if count >= settings.MAX_WATCHLIST_ITEMS_PER_USER:
        raise HTTPException(
            status_code=400,
            detail=f"watchlist is full (max {settings.MAX_WATCHLIST_ITEMS_PER_USER} items)",
        )

    # (2) resolution — name -> type_id when type_id absent.
    type_id = payload.type_id
    if type_id is None:
        type_id = await _resolve_name_to_type_id(esi_client, payload.type_name)

    # (3) validation — published ship (category 6).
    type_info = await _fetch_type_or_400_502(esi_client, type_id)
    if not type_info.get("published"):
        raise HTTPException(status_code=400, detail="type is not a published item")
    group_info = await _fetch_group_or_400_502(esi_client, type_info.get("group_id"))
    if group_info.get("category_id") != SHIP_CATEGORY_ID:
        raise HTTPException(status_code=400, detail="type is not a ship")

    # (4) insert — duplicate caught via the real unique constraint (no pre-check; race-safe).
    item = WatchlistItem(
        user_id=user.id,
        type_id=type_id,
        type_name=type_info.get("name"),
        max_price=payload.max_price,
        notes=payload.notes,
    )
    try:
        async with db.begin_nested():   # SAVEPOINT: an IntegrityError rolls back only this insert
            db.add(item)
            await db.flush()
    except IntegrityError:
        raise HTTPException(status_code=409, detail="already watching this type")
    return item


async def list_watchlist_items(db: AsyncSession, user: User) -> list[WatchlistItem]:
    result = await db.execute(
        select(WatchlistItem)
        .where(WatchlistItem.user_id == user.id)
        .order_by(WatchlistItem.type_name.asc(), WatchlistItem.type_id.asc())   # names not unique
    )
    return list(result.scalars().all())


async def update_watchlist_item(
    db: AsyncSession, user: User, item_id: int, payload: WatchlistItemUpdate
) -> WatchlistItem:
    item = (
        await db.execute(
            select(WatchlistItem).where(
                WatchlistItem.id == item_id, WatchlistItem.user_id == user.id
            )
        )
    ).scalar_one_or_none()
    if item is None:
        raise HTTPException(status_code=404, detail="Watchlist item not found")
    # Omit preserves, explicit null clears — driven by which keys the client actually sent.
    fields = payload.model_fields_set
    if "max_price" in fields:
        item.max_price = payload.max_price
    if "notes" in fields:
        item.notes = payload.notes
    await db.flush()
    # updated_at carries onupdate=func.now() (a server-evaluated UPDATE default). SQLAlchemy fetches
    # UPDATE-generated defaults only on refresh — without this the router's WatchlistItemSchema
    # serialization reads an expired attribute and raises MissingGreenlet (implicit async IO). Section A.
    await db.refresh(item)
    return item


async def delete_watchlist_item(db: AsyncSession, user: User, item_id: int) -> None:
    item = (
        await db.execute(
            select(WatchlistItem).where(
                WatchlistItem.id == item_id, WatchlistItem.user_id == user.id
            )
        )
    ).scalar_one_or_none()
    if item is None:
        raise HTTPException(status_code=404, detail="Watchlist item not found")
    await db.delete(item)
    await db.flush()
```

- [x] **Step 6: Implement `api/watchlist.py`.** Create `app/backend/src/fastapi_app/api/watchlist.py`:

```python
# ABOUTME: F006 watchlist router — /me/watchlist-items (bare-mounted, PROXY-1; auth-gated per user).
# ABOUTME: Declares error bodies (400/401/409/502) so the typed client sees them (closes the /me gap).
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.current_user import get_current_user
from ..core.dependencies import get_esi_client
from ..core.esi_client_class import ESIClient
from ..db import get_db
from ..models import User
from ..schemas.account import (
    WatchlistItemCreate,
    WatchlistItemSchema,
    WatchlistItemUpdate,
)
from ..schemas.auth import ErrorDetail
from ..services import watchlist_service

router = APIRouter(prefix="/me/watchlist-items", tags=["Watchlist"])

_AUTH = {401: {"model": ErrorDetail, "description": "Not authenticated"}}
_NOT_FOUND = {404: {"model": ErrorDetail, "description": "Not found"}}


@router.post(
    "/",
    response_model=WatchlistItemSchema,
    status_code=status.HTTP_201_CREATED,
    responses={
        **_AUTH,
        400: {"model": ErrorDetail, "description": "Cap reached / unknown name / not a published ship"},
        409: {"model": ErrorDetail, "description": "Already watching this type"},
        502: {"model": ErrorDetail, "description": "ESI unreachable"},
    },
)
async def add_watchlist_item(
    payload: WatchlistItemCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    esi_client: ESIClient = Depends(get_esi_client),
) -> WatchlistItemSchema:
    item = await watchlist_service.add_watchlist_item(db, esi_client, user, payload)
    return WatchlistItemSchema.model_validate(item)


@router.get("/", response_model=list[WatchlistItemSchema], responses={**_AUTH})
async def list_watchlist_items(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[WatchlistItemSchema]:
    items = await watchlist_service.list_watchlist_items(db, user)
    return [WatchlistItemSchema.model_validate(i) for i in items]


@router.put(
    "/{item_id}",
    response_model=WatchlistItemSchema,
    responses={**_AUTH, **_NOT_FOUND},
)
async def update_watchlist_item(
    item_id: int,
    payload: WatchlistItemUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> WatchlistItemSchema:
    item = await watchlist_service.update_watchlist_item(db, user, item_id, payload)
    return WatchlistItemSchema.model_validate(item)


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT, responses={**_AUTH, **_NOT_FOUND})
async def delete_watchlist_item(
    item_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    await watchlist_service.delete_watchlist_item(db, user, item_id)
```

- [x] **Step 7: Mount the router in `main.py`.** Add the import next to the other `from .api import …`
  lines (`main.py:25-26`): `from .api import watchlist as watchlist_router`. Add the mount after the
  saved-searches mount added by the earlier phase (near `main.py:192-194`):

```python
app.include_router(watchlist_router.router)   # /me/watchlist-items (bare, PROXY-1)
```
**Shared-file note:** `main.py` is edited by the F005 section (saved-searches mount) and by Task 4.1
(notifications mount) and Task 4.3 (matcher lifespan wiring). Add your line; never revert a sibling's.

- [x] **Step 8: Run the test, confirm green.**
  `cd app/backend && pdm run pytest src/fastapi_app/tests/api/test_watchlist.py -v`
  All pass. Then confirm the wider suite still passes and lint is clean:
  `cd app/backend && pdm run pytest -q && pdm run lint`

- [x] **Step 9: Commit.**
  `git add app/backend/src/fastapi_app/schemas/account.py app/backend/src/fastapi_app/core/config.py app/backend/.env.example app/backend/src/fastapi_app/services/watchlist_service.py app/backend/src/fastapi_app/api/watchlist.py app/backend/src/fastapi_app/main.py app/backend/src/fastapi_app/tests/api/test_watchlist.py`
  ```
  feat(api): add F006 watchlist CRUD with ESI add pipeline

  Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>
  ```

```
BEFORE marking this task complete:
1. Review tests against docs/pitfalls/testing-pitfalls.md
2. Verify test coverage (error paths? edge cases?)
3. Run tests and confirm green
```

```
After completing this phase:
Review the batch from multiple perspectives (correctness, pitfalls compliance, test coverage).
Minimum 3 review rounds. If round 3 still finds issues, keep going until clean.
```

---

## Phase 4 — F007 Alerts backend (notifications API + matcher job + scheduler)

**Execution Status:** ✅ SHIPPED at `b6d1e13` on 2026-07-18

Goal: the notifications schemas + `api/notifications.py` (list/mark-read/mark-all-read/settings), the
`WatchlistMatcherService` (design §4.4, exactly), the config fields + scheduler wiring + lifespan
registration, and the shared `FakeLockRedis` double.

---

### Task 4.1: Notification schemas + `api/notifications.py` + mount + tests

```
BEFORE starting work:
1. Invoke superpowers:test-driven-development
2. Read docs/pitfalls/testing-pitfalls.md
Follow TDD: write failing test → implement → verify green.
```

```
If any test assertion races, flakes, or fails nondeterministically, the fix is deterministic
synchronization or deterministic fixture data — NOT assertion removal or weakening. If
synchronization cannot make the assertion pass reliably, STOP and raise to the dispatching
agent. Do not ship a weaker test. Prefer mechanism assertions (state observed) over symptom
assertions (timing bounds).
```
(The pagination boundary test is TEST-3 + TEST-4: deterministic `created_at` fixtures with an `id`
tiebreaker, crossing a page boundary.)

**Files:**
- Modify: `app/backend/src/fastapi_app/schemas/account.py` (ADD notification schemas + filter model).
- Create: `app/backend/src/fastapi_app/api/notifications.py`.
- Modify: `app/backend/src/fastapi_app/main.py` (mount `router` + `settings_router`).
- Test (Create): `app/backend/src/fastapi_app/tests/api/test_notifications.py`.

- [x] **Step 1: Add the notification schemas + filter model.** Append to `schemas/account.py`:

```python
class NotificationSchema(BaseModel):
    id: int
    type: str
    message: str
    contract_id: Optional[int] = None
    watch_type_id: Optional[int] = None
    price: Optional[float] = None
    is_read: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class NotificationSettingsSchema(BaseModel):
    watchlist_alerts_enabled: bool

    model_config = ConfigDict(from_attributes=True)


class NotificationFilters(BaseModel):
    """Query-param model for GET /me/notifications/ — bind with Annotated[..., Query()] (FASTAPI-1)."""

    is_read: Optional[bool] = Field(default=None)
    page: int = Field(default=1, ge=1)
    size: int = Field(default=50, ge=1, le=100)
```

- [x] **Step 2: Write the failing test module.** Create
  `app/backend/src/fastapi_app/tests/api/test_notifications.py`:

```python
# ABOUTME: HTTP-level tests for /me/notifications and /me/notification-settings (F007).
# ABOUTME: total-after-filter (badge contract), pagination boundary (TEST-4), ownership, settings.
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from fastapi_app.main import app as real_app
from fastapi_app.models import Notification


BASE = datetime(2026, 7, 1, 12, 0, 0, tzinfo=timezone.utc)


async def _seed(db_session, user, *, n, is_read=False, start=0):
    # Distinct, strictly-decreasing created_at + id tiebreaker (TEST-3).
    for i in range(start, start + n):
        db_session.add(Notification(
            user_id=user.id, type="watchlist_match", message=f"m{i}",
            contract_id=1000 + i, watch_type_id=587, price=1000000 + i,
            is_read=is_read, created_at=BASE - timedelta(minutes=i),
        ))
    await db_session.flush()


@pytest.mark.asyncio
async def test_list_orders_created_desc_id_desc(authed_user, db_session):
    user, client = authed_user
    await _seed(db_session, user, n=3)
    resp = await client.get("/me/notifications/")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 3
    msgs = [i["message"] for i in body["items"]]
    assert msgs == ["m0", "m1", "m2"]   # created_at desc (m0 newest)


@pytest.mark.asyncio
async def test_pagination_crosses_boundary(authed_user, db_session):
    user, client = authed_user
    await _seed(db_session, user, n=5)
    p1 = (await client.get("/me/notifications/?page=1&size=2")).json()
    p2 = (await client.get("/me/notifications/?page=2&size=2")).json()
    p3 = (await client.get("/me/notifications/?page=3&size=2")).json()
    assert p1["total"] == p2["total"] == p3["total"] == 5
    assert len(p1["items"]) == 2 and len(p2["items"]) == 2 and len(p3["items"]) == 1
    ids = [i["id"] for i in p1["items"] + p2["items"] + p3["items"]]
    assert len(ids) == len(set(ids)) == 5   # union == full set, no dup/skip across boundary


@pytest.mark.asyncio
async def test_total_reflects_is_read_filter(authed_user, db_session):
    # Badge contract: total under is_read=false == unread count, NOT the all-time row count.
    user, client = authed_user
    await _seed(db_session, user, n=2, is_read=False, start=0)
    await _seed(db_session, user, n=3, is_read=True, start=10)
    unread = (await client.get("/me/notifications/?is_read=false")).json()
    allrows = (await client.get("/me/notifications/")).json()
    assert unread["total"] == 2
    assert allrows["total"] == 5


@pytest.mark.asyncio
async def test_mark_read_and_ownership(authed_user, db_session):
    user, client = authed_user
    await _seed(db_session, user, n=1)
    row = (await db_session.execute(select(Notification))).scalar_one()
    assert (await client.post(f"/me/notifications/{row.id}/mark-read")).status_code == 204
    await db_session.refresh(row)
    assert row.is_read is True
    assert (await client.post("/me/notifications/999999/mark-read")).status_code == 404


@pytest.mark.asyncio
async def test_mark_all_read_idempotent(authed_user, db_session):
    user, client = authed_user
    await _seed(db_session, user, n=3)
    assert (await client.post("/me/notifications/mark-all-read")).status_code == 204
    assert (await client.post("/me/notifications/mark-all-read")).status_code == 204   # idempotent
    rows = (await db_session.execute(select(Notification).where(Notification.user_id == user.id))).scalars().all()
    assert all(r.is_read for r in rows)


@pytest.mark.asyncio
async def test_cross_user_mark_read_404(authed_user, db_session):
    user_a, client = authed_user
    await _seed(db_session, user_a, n=1)
    row = (await db_session.execute(select(Notification))).scalar_one()
    from fastapi_app.tests.conftest import login_as
    await login_as(client, db_session, character_id=91000002, character_name="Other", owner_hash="OWN2")
    assert (await client.post(f"/me/notifications/{row.id}/mark-read")).status_code == 404
    await db_session.refresh(row)
    assert row.is_read is False   # B could not touch A's row


@pytest.mark.asyncio
async def test_settings_round_trip(authed_user, db_session):
    user, client = authed_user
    get1 = await client.get("/me/notification-settings")
    assert get1.status_code == 200
    assert get1.json()["watchlist_alerts_enabled"] is True   # server_default true
    put = await client.put("/me/notification-settings", json={"watchlist_alerts_enabled": False})
    assert put.status_code == 200
    assert put.json()["watchlist_alerts_enabled"] is False
    await db_session.refresh(user)
    assert user.watchlist_alerts_enabled is False


# ---------- anonymous 401 on EVERY route+method (auth_client sets app.state.redis; no session cookie) ----------

@pytest.mark.parametrize("method, path, json_body", [
    ("GET", "/me/notifications/", None),
    ("POST", "/me/notifications/1/mark-read", None),
    ("POST", "/me/notifications/mark-all-read", None),
    ("GET", "/me/notification-settings", None),
    ("PUT", "/me/notification-settings", {"watchlist_alerts_enabled": False}),
])
@pytest.mark.asyncio
async def test_every_notification_route_401_anonymous(auth_client, method, path, json_body):
    # get_current_user 401s a cookieless request before any handler body runs — assert it on
    # every method/path the two routers declare.
    resp = await auth_client.request(method, path, json=json_body)
    assert resp.status_code == 401


def test_openapi_notification_paths_bare():
    schema = real_app.openapi()
    paths = schema["paths"]
    for p in ("/me/notifications/", "/me/notifications/{notification_id}/mark-read",
              "/me/notifications/mark-all-read", "/me/notification-settings"):
        assert p in paths
    assert not any(p.startswith("/api/v1") for p in paths)
    # 401 declared on every new notification operation (design §4.5 acceptance criterion).
    for path, method in [
        ("/me/notifications/", "get"),
        ("/me/notifications/{notification_id}/mark-read", "post"),
        ("/me/notifications/mark-all-read", "post"),
        ("/me/notification-settings", "get"),
        ("/me/notification-settings", "put"),
    ]:
        assert "401" in paths[path][method]["responses"]
```

- [x] **Step 3: Run the test, confirm it fails.**
  `cd app/backend && pdm run pytest src/fastapi_app/tests/api/test_notifications.py -v`
  Expected failure: `ModuleNotFoundError: No module named 'fastapi_app.api.notifications'`.

- [x] **Step 4: Implement `api/notifications.py`.** Create
  `app/backend/src/fastapi_app/api/notifications.py`:

```python
# ABOUTME: F007 notifications router (/me/notifications) + settings router (/me/notification-settings).
# ABOUTME: List total is computed AFTER the is_read filter — the unread badge reads it (design §4.5).
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.current_user import get_current_user
from ..db import get_db
from ..models import Notification, User
from ..schemas.account import (
    NotificationFilters,
    NotificationSchema,
    NotificationSettingsSchema,
)
from ..schemas.auth import ErrorDetail
from ..schemas.common import PaginatedResponse

router = APIRouter(prefix="/me/notifications", tags=["Notifications"])
settings_router = APIRouter(prefix="/me/notification-settings", tags=["Notifications"])

_AUTH = {401: {"model": ErrorDetail, "description": "Not authenticated"}}
_NOT_FOUND = {404: {"model": ErrorDetail, "description": "Not found"}}


@router.get("/", response_model=PaginatedResponse[NotificationSchema], responses={**_AUTH})
async def list_notifications(
    filters: Annotated[NotificationFilters, Query()],   # FASTAPI-1: Annotated[..., Query()], not Depends
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PaginatedResponse[NotificationSchema]:
    base = select(Notification).where(Notification.user_id == user.id)
    if filters.is_read is not None:
        base = base.where(Notification.is_read == filters.is_read)
    # total is computed AFTER the is_read filter so the unread badge is honest.
    total = await db.scalar(select(func.count()).select_from(base.subquery()))
    rows = (
        await db.execute(
            base.order_by(Notification.created_at.desc(), Notification.id.desc())
            .offset((filters.page - 1) * filters.size)
            .limit(filters.size)
        )
    ).scalars().all()
    return PaginatedResponse[NotificationSchema](
        total=total or 0,
        page=filters.page,
        size=filters.size,
        items=[NotificationSchema.model_validate(r) for r in rows],
    )


# NOTE: /mark-all-read (one segment) and /{notification_id}/mark-read (two segments) never collide.
@router.post("/mark-all-read", status_code=status.HTTP_204_NO_CONTENT, responses={**_AUTH})
async def mark_all_read(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    await db.execute(
        update(Notification)
        .where(Notification.user_id == user.id, Notification.is_read.is_(False))
        .values(is_read=True)
    )
    await db.flush()   # idempotent: a second call updates zero rows


@router.post(
    "/{notification_id}/mark-read",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={**_AUTH, **_NOT_FOUND},
)
async def mark_read(
    notification_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    result = await db.execute(
        update(Notification)
        .where(Notification.id == notification_id, Notification.user_id == user.id)
        .values(is_read=True)
    )
    if result.rowcount == 0:   # not found OR not owned — uniform 404 (anti-enumeration)
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Notification not found")
    await db.flush()


@settings_router.get("", response_model=NotificationSettingsSchema, responses={**_AUTH})
async def get_notification_settings(
    user: User = Depends(get_current_user),
) -> NotificationSettingsSchema:
    return NotificationSettingsSchema.model_validate(user)


@settings_router.put("", response_model=NotificationSettingsSchema, responses={**_AUTH})
async def update_notification_settings(
    payload: NotificationSettingsSchema,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> NotificationSettingsSchema:
    user.watchlist_alerts_enabled = payload.watchlist_alerts_enabled
    await db.flush()
    return NotificationSettingsSchema.model_validate(user)
```
**Note on the settings routes' path:** the router prefix is `/me/notification-settings`, so the route
decorators use `""` (empty), yielding the exact path `/me/notification-settings` (no trailing slash —
it's a singleton resource, not a collection; the collection trailing-slash convention applies to
`/me/notifications/`).

- [x] **Step 5: Mount both routers in `main.py`.** Add the import
  `from .api import notifications as notifications_router` next to the others, and after the watchlist
  mount:

```python
app.include_router(notifications_router.router)           # /me/notifications (bare, PROXY-1)
app.include_router(notifications_router.settings_router)  # /me/notification-settings (bare)
```

- [x] **Step 6: Run the test, confirm green.**
  `cd app/backend && pdm run pytest src/fastapi_app/tests/api/test_notifications.py -v`
  All pass.

- [x] **Step 7: Commit.**
  `git add app/backend/src/fastapi_app/schemas/account.py app/backend/src/fastapi_app/api/notifications.py app/backend/src/fastapi_app/main.py app/backend/src/fastapi_app/tests/api/test_notifications.py`
  ```
  feat(api): add F007 notifications list, mark-read, and settings routes

  Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>
  ```

```
BEFORE marking this task complete:
1. Review tests against docs/pitfalls/testing-pitfalls.md
2. Verify test coverage (error paths? edge cases?)
3. Run tests and confirm green
```

---

### Task 4.2: `WatchlistMatcherService` + shared `FakeLockRedis` double + matcher tests

```
BEFORE starting work:
1. Invoke superpowers:test-driven-development
2. Read docs/pitfalls/testing-pitfalls.md
Follow TDD: write failing test → implement → verify green.
```

```
If any test assertion races, flakes, or fails nondeterministically, the fix is deterministic
synchronization or deterministic fixture data — NOT assertion removal or weakening. If
synchronization cannot make the assertion pass reliably, STOP and raise to the dispatching
agent. Do not ship a weaker test. Prefer mechanism assertions (state observed) over symptom
assertions (timing bounds).
```
(This task is concurrency + ordering + clock-injection heavy. Idempotency asserts first-run-N>0 THEN
second-run-zero; the dedup partial index is exercised directly; prune uses the injectable `now_fn`
with backdated `created_at` fixtures. All deterministic — no timing bounds.)

**Files:**
- Create: `app/backend/src/fastapi_app/tests/lock_double.py` (promote `FakeLockRedis`).
- Modify: `app/backend/src/fastapi_app/tests/services/test_background_aggregation.py` (import the shared
  double, drop the local class — same behavior).
- Create: `app/backend/src/fastapi_app/services/watchlist_matcher.py`.
- Test (Create): `app/backend/src/fastapi_app/tests/services/test_watchlist_matcher.py`.

- [x] **Step 1: Promote the lock double.** Create `app/backend/src/fastapi_app/tests/lock_double.py`
  with the byte-identical behavior of `_FakeLockRedis` (`test_background_aggregation.py:275-295`):

```python
# ABOUTME: Shared in-memory async Redis double for the concurrency-lock set/eval(CAD)/close path.
# ABOUTME: Used by both the aggregation-lock tests and the watchlist-matcher-lock tests.


class FakeLockRedis:
    """Minimal in-memory async Redis for the lock's set / eval(CAD) / close path."""

    def __init__(self, store: dict):
        self.store = store

    async def set(self, key, value, nx=False, ex=None):
        if nx and key in self.store:
            return None
        self.store[key] = value
        return True

    async def eval(self, script, numkeys, *args):
        key, token = args[0], args[1]
        if self.store.get(key) == token:
            del self.store[key]
            return 1
        return 0

    async def close(self):
        pass
```
Then in `test_background_aggregation.py`: delete the local `class _FakeLockRedis` (lines ~275-295) and
add `from fastapi_app.tests.lock_double import FakeLockRedis as _FakeLockRedis` near the top imports
(keeping the `_FakeLockRedis` local alias so the two existing lock tests at lines ~298-321 read
unchanged).

- [x] **Step 2: Run the aggregation lock tests, confirm still green after the refactor.**
  `cd app/backend && pdm run pytest src/fastapi_app/tests/services/test_background_aggregation.py -v -k lock`
  Both `test_lock_release_deletes_only_its_own_token` and
  `test_lock_release_does_not_delete_a_reacquired_lock` pass unchanged (proves the promotion preserved
  behavior).

- [x] **Step 3: Write the failing matcher test module.** Create
  `app/backend/src/fastapi_app/tests/services/test_watchlist_matcher.py`:

```python
# ABOUTME: Service-level tests for WatchlistMatcherService (F007 matcher) — the design §6 matcher matrix.
# ABOUTME: Inner methods take the test db_session directly (run_matching builds its own engine, §6).
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

import fastapi_app.services.watchlist_matcher as wm
from fastapi_app.models import Contract, ContractItem, Notification, User, WatchlistItem
from fastapi_app.services.watchlist_matcher import (
    ConcurrencyLockError,
    WatchlistMatcherService,
)
from fastapi_app.tests.lock_double import FakeLockRedis

pytestmark = pytest.mark.asyncio

NOW = datetime(2026, 7, 10, 12, 0, 0, tzinfo=timezone.utc)


def _settings():
    s = MagicMock()
    s.NOTIFICATION_RETENTION_DAYS = 90
    s.WATCHLIST_MATCH_LOCK_TTL_SECONDS = 900
    s.DATABASE_URL = "postgresql+asyncpg://unused/unused"
    s.CACHE_URL = "redis://unused"
    return s


def _service(now=None):
    return WatchlistMatcherService(settings=_settings(), now_fn=(lambda: now) if now else None)


async def _user(db, *, enabled=True, cid=91000001):
    u = User(character_id=cid, character_name="Pilot", owner_hash=f"OWN{cid}",
             watchlist_alerts_enabled=enabled)
    db.add(u)
    await db.flush()
    return u


async def _contract(db, *, cid, price, ctype="auction", expired_in_days=7, completed=False,
                    location="Jita IV - Moon 4"):
    c = Contract(
        contract_id=cid, title="t", price=price, collateral=0, status="unknown", type=ctype,
        issuer_id=1, issuer_corporation_id=1, start_location_id=60003760,
        start_location_region_id=10000002, for_corporation=False,
        date_issued=datetime.now(timezone.utc) - timedelta(days=1),
        date_expired=datetime.now(timezone.utc) + timedelta(days=expired_in_days),
        date_completed=(datetime.now(timezone.utc) if completed else None),
        start_location_name=location,
    )
    db.add(c)
    await db.flush()
    return c


async def _item(db, *, cid, type_id, is_included=True, record_id=None):
    it = ContractItem(record_id=record_id or (cid * 10 + type_id) % 10_000_000, contract_id=cid,
                      type_id=type_id, quantity=1, is_included=is_included, is_singleton=False)
    db.add(it)
    await db.flush()
    return it


async def _watch(db, user, *, type_id, type_name="Caracal", max_price=None):
    w = WatchlistItem(user_id=user.id, type_id=type_id, type_name=type_name, max_price=max_price)
    db.add(w)
    await db.flush()
    return w


# ---------- happy match + price-honest message ----------

async def test_match_creates_price_honest_notification(db_session: AsyncSession):
    u = await _user(db_session)
    await _watch(db_session, u, type_id=621, type_name="Caracal", max_price=20_000_000)
    await _contract(db_session, cid=5001, price=10_500_000, ctype="auction", location="Jita IV - Moon 4")
    await _item(db_session, cid=5001, type_id=621)

    matched, created = await _service()._match_and_notify(db_session)
    assert matched == 1 and created == 1
    note = (await db_session.execute(select(Notification))).scalar_one()
    assert note.watch_type_id == 621
    assert note.contract_id == 5001
    assert note.message == "Caracal available in an auction priced 10,500,000 ISK in Jita IV - Moon 4"


# ---------- idempotency: first run N>0, second run zero ----------

async def test_second_run_creates_zero(db_session: AsyncSession):
    u = await _user(db_session)
    await _watch(db_session, u, type_id=621, max_price=None)
    await _contract(db_session, cid=5002, price=1_000_000)
    await _item(db_session, cid=5002, type_id=621)
    svc = _service()
    _, created1 = await svc._match_and_notify(db_session)
    _, created2 = await svc._match_and_notify(db_session)
    assert created1 == 1
    assert created2 == 0   # ON CONFLICT DO NOTHING against the partial unique index
    assert (await db_session.scalar(select(func.count()).select_from(Notification))) == 1


# ---------- the partial unique index binds (needs index_where) ----------

async def test_dedup_partial_index_binds(db_session: AsyncSession):
    u = await _user(db_session)
    row = dict(user_id=u.id, type="watchlist_match", message="m", contract_id=7001,
               watch_type_id=621, price=1, is_read=False)
    db_session.add(Notification(**row))
    await db_session.flush()
    # A second insert with the SAME (user_id, contract_id, watch_type_id) must no-op — which only
    # works if the ON CONFLICT restates the partial-index predicate (index_where).
    stmt = pg_insert(Notification).values(**row).on_conflict_do_nothing(
        index_elements=["user_id", "contract_id", "watch_type_id"],
        index_where=text("type = 'watchlist_match'"),
    )
    await db_session.execute(stmt)
    assert (await db_session.scalar(select(func.count()).select_from(Notification))) == 1


# ---------- chunk boundary ----------

async def test_insert_crosses_chunk_boundary(db_session: AsyncSession, monkeypatch):
    monkeypatch.setattr(wm, "NOTIFICATION_INSERT_CHUNK", 2)
    u = await _user(db_session)
    await _watch(db_session, u, type_id=621, max_price=None)
    for cid in (6001, 6002, 6003):
        await _contract(db_session, cid=cid, price=1_000_000)
        await _item(db_session, cid=cid, type_id=621)
    _, created = await _service()._match_and_notify(db_session)
    assert created == 3
    assert (await db_session.scalar(select(func.count()).select_from(Notification))) == 3


# ---------- bundle-price semantics (whole-contract price) ----------

async def test_bundle_above_max_no_notification(db_session: AsyncSession):
    u = await _user(db_session)
    await _watch(db_session, u, type_id=621, max_price=5_000_000)
    await _contract(db_session, cid=6100, price=9_000_000)   # ship + extra item, bundle over max
    await _item(db_session, cid=6100, type_id=621)
    await _item(db_session, cid=6100, type_id=34, record_id=61001)
    _, created = await _service()._match_and_notify(db_session)
    assert created == 0


async def test_bundle_under_max_notifies_at_bundle_price(db_session: AsyncSession):
    u = await _user(db_session)
    await _watch(db_session, u, type_id=621, max_price=5_000_000)
    await _contract(db_session, cid=6101, price=4_000_000)
    await _item(db_session, cid=6101, type_id=621)
    await _item(db_session, cid=6101, type_id=34, record_id=61011)
    _, created = await _service()._match_and_notify(db_session)
    assert created == 1
    note = (await db_session.execute(select(Notification))).scalar_one()
    assert note.price == 4_000_000


# ---------- price boundary ==/> ----------

async def test_price_equal_to_max_matches(db_session: AsyncSession):
    u = await _user(db_session)
    await _watch(db_session, u, type_id=621, max_price=1_000_000)
    await _contract(db_session, cid=6200, price=1_000_000)
    await _item(db_session, cid=6200, type_id=621)
    _, created = await _service()._match_and_notify(db_session)
    assert created == 1


async def test_price_above_max_excluded(db_session: AsyncSession):
    u = await _user(db_session)
    await _watch(db_session, u, type_id=621, max_price=1_000_000)
    await _contract(db_session, cid=6201, price=1_000_001)
    await _item(db_session, cid=6201, type_id=621)
    _, created = await _service()._match_and_notify(db_session)
    assert created == 0


# ---------- date gates + is_included + disabled alerts ----------

async def test_expired_contract_excluded(db_session: AsyncSession):
    u = await _user(db_session)
    await _watch(db_session, u, type_id=621, max_price=None)
    await _contract(db_session, cid=6300, price=1, expired_in_days=-1)   # already expired
    await _item(db_session, cid=6300, type_id=621)
    _, created = await _service()._match_and_notify(db_session)
    assert created == 0


async def test_completed_contract_excluded(db_session: AsyncSession):
    u = await _user(db_session)
    await _watch(db_session, u, type_id=621, max_price=None)
    await _contract(db_session, cid=6301, price=1, completed=True)
    await _item(db_session, cid=6301, type_id=621)
    _, created = await _service()._match_and_notify(db_session)
    assert created == 0


async def test_requested_item_excluded(db_session: AsyncSession):
    u = await _user(db_session)
    await _watch(db_session, u, type_id=621, max_price=None)
    await _contract(db_session, cid=6302, price=1)
    await _item(db_session, cid=6302, type_id=621, is_included=False)   # asked-for, not offered
    _, created = await _service()._match_and_notify(db_session)
    assert created == 0


async def test_disabled_alerts_user_excluded(db_session: AsyncSession):
    u = await _user(db_session, enabled=False)
    await _watch(db_session, u, type_id=621, max_price=None)
    await _contract(db_session, cid=6303, price=1)
    await _item(db_session, cid=6303, type_id=621)
    _, created = await _service()._match_and_notify(db_session)
    assert created == 0


# ---------- prune (injectable now_fn + backdated created_at) ----------

async def _note(db, user, *, cid, created_at):
    n = Notification(user_id=user.id, type="watchlist_match", message="m", contract_id=cid,
                     watch_type_id=621, price=1, is_read=False, created_at=created_at)
    db.add(n)
    await db.flush()
    return n


async def test_prune_deletes_old_when_contract_gone(db_session: AsyncSession):
    u = await _user(db_session)
    # old notification (100 days before the injected now) whose contract is expired/absent.
    await _note(db_session, u, cid=7100, created_at=NOW - timedelta(days=100))
    pruned = await _service(now=NOW)._prune(db_session)
    assert pruned == 1
    assert (await db_session.scalar(select(func.count()).select_from(Notification))) == 0


async def test_prune_keeps_old_when_contract_outstanding(db_session: AsyncSession):
    u = await _user(db_session)
    await _contract(db_session, cid=7200, price=1, expired_in_days=7)   # still outstanding
    await _note(db_session, u, cid=7200, created_at=NOW - timedelta(days=100))
    pruned = await _service(now=NOW)._prune(db_session)
    assert pruned == 0
    assert (await db_session.scalar(select(func.count()).select_from(Notification))) == 1


async def test_prune_keeps_recent(db_session: AsyncSession):
    u = await _user(db_session)
    await _note(db_session, u, cid=7300, created_at=NOW - timedelta(days=10))   # inside window
    pruned = await _service(now=NOW)._prune(db_session)
    assert pruned == 0


# ---------- lock behavior (via the shared FakeLockRedis double) ----------

async def test_run_matching_skips_when_lock_held():
    store = {wm.WATCHLIST_MATCH_LOCK_KEY: "other-runner-token"}
    with patch.object(wm.aioredis, "from_url", return_value=FakeLockRedis(store)):
        await _service().run_matching()   # lock held -> ConcurrencyLockError caught -> returns
    assert store[wm.WATCHLIST_MATCH_LOCK_KEY] == "other-runner-token"   # untouched, no engine built


async def test_lock_release_declines_on_token_mismatch(caplog):
    store: dict = {}
    with patch.object(wm.aioredis, "from_url", return_value=FakeLockRedis(store)):
        svc = _service()
        with caplog.at_level("WARNING"):
            async with svc._concurrency_lock():
                store[wm.WATCHLIST_MATCH_LOCK_KEY] = "second-runner-token"   # our TTL "expired"
    assert store.get(wm.WATCHLIST_MATCH_LOCK_KEY) == "second-runner-token"
    assert "token mismatch" in caplog.text


async def test_concurrency_lock_raises_when_held():
    store = {wm.WATCHLIST_MATCH_LOCK_KEY: "held"}
    with patch.object(wm.aioredis, "from_url", return_value=FakeLockRedis(store)):
        svc = _service()
        with pytest.raises(ConcurrencyLockError):
            async with svc._concurrency_lock():
                pass
```

- [x] **Step 4: Run the matcher tests, confirm they fail.**
  `cd app/backend && pdm run pytest src/fastapi_app/tests/services/test_watchlist_matcher.py -v`
  Expected failure: `ModuleNotFoundError: No module named 'fastapi_app.services.watchlist_matcher'`.

- [x] **Step 5: Implement `watchlist_matcher.py`.** Create
  `app/backend/src/fastapi_app/services/watchlist_matcher.py`:

```python
# ABOUTME: F007 watchlist matcher — set-based match of enabled users' watchlists vs outstanding
# ABOUTME: contracts; dedup via a partial unique index (ON CONFLICT); defensive age-based prune.
import logging
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import Callable, Optional

import redis.asyncio as aioredis
from sqlalchemy import delete, func, or_, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from ..core.config import Settings
from ..core.logging import get_logger, log_key_event
from ..models.account import Notification, WatchlistItem
from ..models.contracts import Contract, ContractItem
from ..models.user import User

logger = logging.getLogger(__name__)
slog = get_logger(__name__)

# Own lock key — never the aggregation lock (reusing it would mutually serialize the two jobs).
WATCHLIST_MATCH_LOCK_KEY = "hangar-bay:watchlist-match:lock"

# asyncpg caps a statement at 32767 bind params; ~7 params/row keeps 1000 comfortably safe.
NOTIFICATION_INSERT_CHUNK = 1000

# Compare-and-delete: release only if THIS runner still holds the token (guards TTL-expiry-then-reacquire).
_RELEASE_LOCK_LUA = (
    "if redis.call('get', KEYS[1]) == ARGV[1] then "
    "return redis.call('del', KEYS[1]) else return 0 end"
)

_SHIP_TYPE_LABELS = {"item_exchange": "an item exchange", "auction": "an auction"}


class ConcurrencyLockError(Exception):
    """Raised when the watchlist-match lock cannot be acquired (another run holds it)."""


def _render_message(type_name: str, contract_type: str, price, location: Optional[str]) -> str:
    # Price-honest: name the CONTRACT as the priced thing (bundle price), not the ship (design §4.4).
    label = _SHIP_TYPE_LABELS.get(contract_type, "a contract")
    where = location or "an unknown location"
    return f"{type_name} available in {label} priced {price:,.0f} ISK in {where}"


class WatchlistMatcherService:
    """Picklable (no live clients at rest) so RedisJobStore can persist the job — mirrors
    ContractAggregationService. `now_fn` stays None in production (a lambda would not pickle);
    tests inject a fixed clock for the retention boundary."""

    def __init__(self, settings: Settings, now_fn: Optional[Callable[[], datetime]] = None):
        self.settings = settings
        self.now_fn = now_fn

    def _now(self) -> datetime:
        return self.now_fn() if self.now_fn is not None else datetime.now(timezone.utc)

    @asynccontextmanager
    async def _concurrency_lock(self):
        redis_client = aioredis.from_url(str(self.settings.CACHE_URL))
        lock_token = uuid.uuid4().hex
        lock_acquired = False
        try:
            lock_acquired = await redis_client.set(
                WATCHLIST_MATCH_LOCK_KEY, lock_token,
                nx=True, ex=self.settings.WATCHLIST_MATCH_LOCK_TTL_SECONDS,
            )
            if not lock_acquired:
                raise ConcurrencyLockError("Could not acquire watchlist-match lock.")
            yield
        finally:
            if lock_acquired:
                released = await redis_client.eval(
                    _RELEASE_LOCK_LUA, 1, WATCHLIST_MATCH_LOCK_KEY, lock_token
                )
                if not released:
                    logger.warning(
                        "Watchlist-match lock token mismatch on release: the %ss TTL likely "
                        "expired mid-run and was reacquired by another runner. Leaving it intact.",
                        self.settings.WATCHLIST_MATCH_LOCK_TTL_SECONDS,
                    )
            await redis_client.close()

    async def run_matching(self) -> None:
        started = time.monotonic()
        matched = created = pruned = 0
        try:
            async with self._concurrency_lock():
                engine = create_async_engine(self.settings.DATABASE_URL)
                try:
                    session_factory = async_sessionmaker(
                        bind=engine, class_=AsyncSession, expire_on_commit=False
                    )
                    async with session_factory() as db_session:
                        matched, created = await self._match_and_notify(db_session)
                        pruned = await self._prune(db_session)
                        await db_session.commit()
                finally:
                    await engine.dispose()
        except ConcurrencyLockError:
            logger.info("Watchlist matcher skipped: lock held by another run.")
            return
        except Exception as e:  # noqa: BLE001 — job boundary: log, don't propagate to the scheduler
            log_key_event(
                slog, "watchlist_match_run", success=False,
                duration_ms=(time.monotonic() - started) * 1000, error_message=str(e),
            )
            logger.error("Watchlist matcher run failed: %s", e, exc_info=True)
            return
        log_key_event(
            slog, "watchlist_match_run", success=True,
            duration_ms=(time.monotonic() - started) * 1000,
            matches=matched, created=created, pruned=pruned,
        )

    async def _match_and_notify(self, db_session: AsyncSession) -> tuple[int, int]:
        # Set-based match: enabled users' watchlists vs OUTSTANDING item_exchange/auction contracts
        # carrying an INCLUDED item of the watched type_id, at or under the (optional) max_price.
        stmt = (
            select(
                WatchlistItem.user_id,
                WatchlistItem.type_id,
                WatchlistItem.type_name,
                Contract.contract_id,
                Contract.price,
                Contract.type,
                Contract.start_location_name,
            )
            .join(User, User.id == WatchlistItem.user_id)
            .join(ContractItem, ContractItem.type_id == WatchlistItem.type_id)
            .join(Contract, Contract.contract_id == ContractItem.contract_id)
            .where(
                User.watchlist_alerts_enabled.is_(True),
                ContractItem.is_included.is_(True),
                Contract.type.in_(("item_exchange", "auction")),
                Contract.date_expired > func.now(),
                Contract.date_completed.is_(None),
                or_(WatchlistItem.max_price.is_(None), Contract.price <= WatchlistItem.max_price),
            )
            .distinct()
        )
        rows = (await db_session.execute(stmt)).all()
        if not rows:
            return 0, 0

        payloads = [
            {
                "user_id": r.user_id,
                "type": "watchlist_match",
                "message": _render_message(r.type_name, r.type, r.price, r.start_location_name),
                "contract_id": r.contract_id,
                "watch_type_id": r.type_id,
                "price": r.price,
                "is_read": False,
            }
            for r in rows
        ]

        created = 0
        for start in range(0, len(payloads), NOTIFICATION_INSERT_CHUNK):
            chunk = payloads[start : start + NOTIFICATION_INSERT_CHUNK]
            # The conflict target MUST restate the partial-index predicate (index_where) or Postgres
            # raises "no unique or exclusion constraint matching the ON CONFLICT specification". The
            # predicate MUST be a literal identical to the index DDL: a parameterized predicate
            # compiles to `type = $1`, which Postgres's partial-index implication check cannot match
            # against the index's literal predicate, so inference can fail.
            stmt_ins = (
                pg_insert(Notification)
                .values(chunk)
                .on_conflict_do_nothing(
                    index_elements=["user_id", "contract_id", "watch_type_id"],
                    index_where=text("type = 'watchlist_match'"),
                )
                .returning(Notification.id)
            )
            result = await db_session.execute(stmt_ins)
            created += len(result.fetchall())
        return len(rows), created

    async def _prune(self, db_session: AsyncSession) -> int:
        cutoff = self._now() - timedelta(days=self.settings.NOTIFICATION_RETENTION_DAYS)
        outstanding = select(Contract.contract_id).where(
            Contract.contract_id == Notification.contract_id,
            Contract.date_expired > func.now(),
            Contract.date_completed.is_(None),
        )
        # Delete only aged rows whose target contract is no longer outstanding (no-resurrection guard).
        stmt = delete(Notification).where(
            Notification.created_at < cutoff,
            ~outstanding.exists(),
        )
        result = await db_session.execute(stmt)
        return result.rowcount
```

- [x] **Step 6: Run the matcher tests, confirm green.**
  `cd app/backend && pdm run pytest src/fastapi_app/tests/services/test_watchlist_matcher.py -v`
  All pass; output pristine (the run-failure path is not triggered in these tests, so no error spam).

- [x] **Step 7: Commit.**
  `git add app/backend/src/fastapi_app/tests/lock_double.py app/backend/src/fastapi_app/tests/services/test_background_aggregation.py app/backend/src/fastapi_app/services/watchlist_matcher.py app/backend/src/fastapi_app/tests/services/test_watchlist_matcher.py`
  ```
  feat(api): add watchlist matcher service with dedup and defensive prune

  Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>
  ```

```
BEFORE marking this task complete:
1. Review tests against docs/pitfalls/testing-pitfalls.md
2. Verify test coverage (error paths? edge cases?)
3. Run tests and confirm green
```

---

### Task 4.3: Config fields + scheduler job + lifespan wiring + thin tests

```
BEFORE starting work:
1. Invoke superpowers:test-driven-development
2. Read docs/pitfalls/testing-pitfalls.md
Follow TDD: write failing test → implement → verify green.
```

```
If any test assertion races, flakes, or fails nondeterministically, the fix is deterministic
synchronization or deterministic fixture data — NOT assertion removal or weakening. If
synchronization cannot make the assertion pass reliably, STOP and raise to the dispatching
agent. Do not ship a weaker test. Prefer mechanism assertions (state observed) over symptom
assertions (timing bounds).
```
(The scheduler tests assert on the `add_job` call arguments via a stub scheduler — a mechanism
assertion, never a running clock.)

**Files:**
- Modify: `app/backend/src/fastapi_app/core/config.py` (ADD three matcher/notification fields).
- Modify: `app/backend/src/fastapi_app/core/scheduler.py` (ADD `add_watchlist_matcher_job`).
- Modify: `app/backend/src/fastapi_app/services/scheduled_jobs.py` (ADD `run_watchlist_matcher_job`).
- Modify: `app/backend/src/fastapi_app/main.py` (lifespan: build matcher service + register job).
- Test (Create): `app/backend/src/fastapi_app/tests/services/test_scheduled_jobs_watchlist.py`.

- [x] **Step 1: Add the config fields.** In `core/config.py`, append these three fields INTO the single
  `# --- M3 account features ---` block (established in Task 2.2, extended in Task 3.2) — do NOT start a
  second M3 block. The consolidated block then reads:

```python
    # --- M3 account features ---
    MAX_SAVED_SEARCHES_PER_USER: int = 100             # (Task 2.2)
    MAX_WATCHLIST_ITEMS_PER_USER: int = 200            # (Task 3.2)
    WATCHLIST_MATCH_INTERVAL_SECONDS: int = 900        # 15 min
    WATCHLIST_MATCH_LOCK_TTL_SECONDS: int = 900
    NOTIFICATION_RETENTION_DAYS: int = 90              # prune window (matcher §4.4 step 5)
```
Document all three new fields in `app/backend/.env.example` (ENV-4), under the same
`# --- M3 account features ---` block. All have defaults → no `_ENV_DEFAULTS` change. (If
`MAX_SAVED_SEARCHES_PER_USER` is somehow missing here — its owning F005 section didn't run — add it in
this same block.)

- [x] **Step 2: Write the failing thin tests.** Create
  `app/backend/src/fastapi_app/tests/services/test_scheduled_jobs_watchlist.py`:

```python
# ABOUTME: Thin tests for the matcher scheduler wiring — job registration args + wrapper error-swallow.
# ABOUTME: The scheduler itself is not run (mirrors how add_aggregation_job is left unexercised).
from unittest.mock import AsyncMock, MagicMock

import pytest

from fastapi_app.core.scheduler import add_watchlist_matcher_job
from fastapi_app.services.scheduled_jobs import run_watchlist_matcher_job
from fastapi_app.services.watchlist_matcher import WatchlistMatcherService



def test_add_watchlist_matcher_job_registers_expected_id():
    scheduler = MagicMock()
    settings = MagicMock(WATCHLIST_MATCH_INTERVAL_SECONDS=900)
    svc = WatchlistMatcherService(settings=settings)
    add_watchlist_matcher_job(scheduler, svc, settings)
    scheduler.add_job.assert_called_once()
    call = scheduler.add_job.call_args
    assert call.args[0] is run_watchlist_matcher_job
    assert call.kwargs["id"] == "match_watchlists"
    assert call.kwargs["seconds"] == 900
    assert call.kwargs["args"] == [svc]
    assert call.kwargs["replace_existing"] is True


def test_matcher_service_is_picklable():
    import pickle
    # RedisJobStore pickles the job func + args; the SERVICE itself must round-trip (a MagicMock
    # settings or a lambda now_fn would break this — use the real settings singleton).
    from fastapi_app.core.config import settings as real_settings
    svc = WatchlistMatcherService(settings=real_settings, now_fn=None)
    restored = pickle.loads(pickle.dumps(svc))
    assert restored.now_fn is None
    assert restored.settings.WATCHLIST_MATCH_INTERVAL_SECONDS == real_settings.WATCHLIST_MATCH_INTERVAL_SECONDS


@pytest.mark.asyncio
async def test_run_watchlist_matcher_job_swallows_exceptions():
    svc = MagicMock()
    svc.run_matching = AsyncMock(side_effect=RuntimeError("boom"))
    await run_watchlist_matcher_job(svc)   # must NOT raise
    svc.run_matching.assert_awaited_once()
```
(Note: `test_matcher_service_is_picklable` pickles the FULL service using the real `settings` singleton
— a `MagicMock` settings or a `lambda` `now_fn` would not pickle, so RedisJobStore requires production
to construct the service with the real `Settings` and leave `now_fn=None`. The test asserts exactly
that: the round-tripped service's default `now_fn` is `None`, not a lambda, and its settings survive.)

- [x] **Step 3: Run the tests, confirm they fail.**
  `cd app/backend && pdm run pytest src/fastapi_app/tests/services/test_scheduled_jobs_watchlist.py -v`
  Expected failure: `ImportError: cannot import name 'add_watchlist_matcher_job'` /
  `'run_watchlist_matcher_job'`.

- [x] **Step 4: Implement `run_watchlist_matcher_job`.** In `services/scheduled_jobs.py`, add
  (top-level, importable, picklable-reference; mirrors `run_aggregation_job`):

```python
async def run_watchlist_matcher_job(matcher_service):
    """Top-level, importable wrapper for the watchlist matcher (RedisJobStore pickles the reference)."""
    logger.info("Executing scheduled job: run_watchlist_matcher_job")
    try:
        await matcher_service.run_matching()
    except Exception as e:
        logger.error(f"An error occurred during the scheduled watchlist matcher job: {e}", exc_info=True)
    finally:
        logger.info("Finished scheduled job: run_watchlist_matcher_job")
```

- [x] **Step 5: Implement `add_watchlist_matcher_job`.** In `core/scheduler.py`, add the import
  `from datetime import datetime, timedelta` (extend the existing `from datetime import datetime`),
  `from ..services.scheduled_jobs import run_watchlist_matcher_job`, and
  `from ..services.watchlist_matcher import WatchlistMatcherService`; then:

```python
def add_watchlist_matcher_job(
    scheduler: AsyncIOScheduler, matcher_service: WatchlistMatcherService, settings: Settings
):
    """Register the watchlist matcher as a second interval job (own id/lock/interval).

    First run is offset now+120s so boot-time ingestion gets a head start; jobs don't chain, so the
    matcher just reads whatever is committed (a first pass over last cycle's data self-corrects).
    """
    scheduler.add_job(
        run_watchlist_matcher_job,
        trigger="interval",
        args=[matcher_service],
        seconds=settings.WATCHLIST_MATCH_INTERVAL_SECONDS,
        id="match_watchlists",
        replace_existing=True,
        misfire_grace_time=300,
        next_run_time=datetime.now() + timedelta(seconds=120),
    )
    logger.info(
        f"Scheduled watchlist matcher job to run every "
        f"{settings.WATCHLIST_MATCH_INTERVAL_SECONDS} seconds (first run in 120s)."
    )
```

- [x] **Step 6: Wire the lifespan in `main.py`.** Extend the scheduler import to
  `from .core.scheduler import add_aggregation_job, add_watchlist_matcher_job, create_scheduler`, add
  `from .services.watchlist_matcher import WatchlistMatcherService`, and in `lifespan` after
  `add_aggregation_job(scheduler, aggregation_service, settings)` (main.py:56), before
  `scheduler.start()`:

```python
    matcher_service = WatchlistMatcherService(settings=settings)
    add_watchlist_matcher_job(scheduler, matcher_service, settings)
```

- [x] **Step 7: Run the thin tests, confirm green.**
  `cd app/backend && pdm run pytest src/fastapi_app/tests/services/test_scheduled_jobs_watchlist.py -v`
  All pass.

- [x] **Step 8: Run the full backend suite + lint (whole phase green before the PR gate).**
  `cd app/backend && pdm run pytest -q && pdm run lint`

- [x] **Step 9: Commit.**
  `git add app/backend/src/fastapi_app/core/config.py app/backend/.env.example app/backend/src/fastapi_app/core/scheduler.py app/backend/src/fastapi_app/services/scheduled_jobs.py app/backend/src/fastapi_app/main.py app/backend/src/fastapi_app/tests/services/test_scheduled_jobs_watchlist.py`
  ```
  feat(api): register the watchlist matcher as a scheduled interval job

  Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>
  ```

```
BEFORE marking this task complete:
1. Review tests against docs/pitfalls/testing-pitfalls.md
2. Verify test coverage (error paths? edge cases?)
3. Run tests and confirm green
```

```
After completing this phase:
Review the batch from multiple perspectives (correctness, pitfalls compliance, test coverage).
Minimum 3 review rounds. If round 3 still finds issues, keep going until clean.
```

---

## Phase 5 — Codegen: regenerate the typed client for the M3 account endpoints

**Execution Status:** ⬜ NOT STARTED

Goal: after ALL backend account endpoints exist (F005 saved-searches from the earlier section, plus
this section's F006 watchlist + F007 notifications), regenerate `openapi.json` and `schema.d.ts` and
commit them together (CLAUDE.md: regenerate the client chain after any backend schema change). This
phase writes NO production code and NO tests — it is generated-artifact regeneration (TDD does not
apply to generated code).

**Files:**
- Modify (generated): `app/frontend/web/openapi.json`.
- Modify (generated): `app/frontend/web/src/lib/api/schema.d.ts`.

- [ ] **Step 1: Export the OpenAPI schema from the live app.**
  `cd app/backend && pdm run export-openapi`
  Expected stdout: `OpenAPI schema written to ../frontend/web/openapi.json (<N> paths)` where `<N>` has
  grown by the M3 routes.

- [ ] **Step 2: Verify the new paths landed in `openapi.json`.** From the repo root:
  `grep -c '/me/saved-searches/' app/frontend/web/openapi.json` → non-zero (F005 sentinel, earlier
  section), and:
  `grep -c '/me/watchlist-items/' app/frontend/web/openapi.json` → non-zero, and
  `grep -c '/me/notifications/' app/frontend/web/openapi.json` → non-zero, and
  `grep -c '"/api/v1' app/frontend/web/openapi.json` → **0** (PROXY-1: no `/api/v1` prefix in the
  backend schema). If any expected path is missing, STOP — a router was not mounted; do not hand-edit
  the generated file, fix the mount and re-export.

- [ ] **Step 3: Regenerate the typed TS client.**
  `cd app/frontend/web && npm run generate:api`
  This overwrites `src/lib/api/schema.d.ts` from `openapi.json`.

- [ ] **Step 4: Confirm the frontend still typechecks against the regenerated schema.**
  `cd app/frontend/web && npx tsc -b`
  Expected: clean (no consumers of the new paths exist yet — the frontend feature work is a later
  section — so this only proves the generated types are well-formed).

- [ ] **Step 5: Commit both generated artifacts together.**
  `git add app/frontend/web/openapi.json app/frontend/web/src/lib/api/schema.d.ts`
  ```
  chore(api): regenerate client for M3 account endpoints

  Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>
  ```

```
After completing this phase:
Review the batch from multiple perspectives (correctness, pitfalls compliance, test coverage).
Minimum 3 review rounds. If round 3 still finds issues, keep going until clean.
```

---

## Cross-section coordination notes (for the plan consolidator)

1. **`main.py` is edited by three sections.** The F005 section mounts the saved-searches router; this
   section mounts the watchlist router (Task 3.2 Step 7), the notifications routers (Task 4.1 Step 5),
   and adds the matcher lifespan wiring (Task 4.3 Step 6). Each task adds its own lines; the shared-file
   rule (never revert a sibling's edit) applies. If the sections run sequentially on one branch this is
   just additive; if parallelized, expect trivial mount-list conflicts, resolved by keeping all mounts.
2. **`schemas/account.py` is appended by both sections.** F005 owns the saved-search schemas; this
   section appends watchlist schemas (Task 3.2 Step 2) and notification schemas (Task 4.1 Step 1).
   Ensure the file's top-of-file imports cover everything used:
   `datetime`, `Optional`, `BaseModel, ConfigDict, Field, model_validator, field_validator`.
3. **Config field ownership.** This section adds `MAX_WATCHLIST_ITEMS_PER_USER` (Task 3.2, its first
   consumer) and `WATCHLIST_MATCH_INTERVAL_SECONDS` / `WATCHLIST_MATCH_LOCK_TTL_SECONDS` /
   `NOTIFICATION_RETENTION_DAYS` (Task 4.3). `MAX_SAVED_SEARCHES_PER_USER` belongs to the F005 section
   (its first consumer is `saved_search_service`). If F005 did not add it, Task 4.3 Step 1 adds it.
   Placement chosen to guarantee no config field is referenced before it exists in phase order.
4. **`tests/conftest.py` — `authed_user` / `login_as` are prerequisites** built by the earlier phase.
   Every test module in this section imports `login_as` via
   `from fastapi_app.tests.conftest import login_as` and consumes `authed_user` as a fixture; if the
   earlier phase named them differently, reconcile before running.
# M3 Implementation Plan — Section C (Phases 6–10: Frontend F005/F006/F007, E2E, Docs & PR)

> This section continues the M3 plan. Phases 0–5 (backend) are authored elsewhere and are assumed **complete and merged into the campaign branch** before Phase 6 begins: all `/me/*` endpoints exist, the OpenAPI schema is exported, and `src/lib/api/schema.d.ts` has been regenerated (`pdm run export-openapi` → `npm run generate:api`) so every new backend schema is present in the generated `components['schemas']`. Phase 6 Task 6.1 adds the named type-alias re-exports for them in `lib/api/client.ts`.

## Standing notes for every Phase 6–8 task (read once, apply throughout)

**Working directory.** All frontend commands run from `app/frontend/web` inside the campaign worktree `.claude/worktrees/m3-account-features` (established in Phase 0). Written as `cd app/frontend/web && …`.

**Vitest command.** The repo script is `npm run test` → `vitest run` (whole suite). For per-file runs during TDD use `npx vitest run <path> --reporter=dot`. Component/unit tests use the `*.test.tsx` suffix (TEST-6). Never place a Vitest test under `e2e/` (Vitest excludes `e2e/**`; Playwright owns `*.spec.ts`).

**`/me/*` path literals are type-checked (PROXY-1 + codegen).** openapi-fetch validates every path string and path-param key against the generated `paths` type. The literals this section uses — `/me/saved-searches/`, `/me/saved-searches/{search_id}`, `/me/watchlist-items/`, `/me/watchlist-items/{item_id}`, `/me/notifications/`, `/me/notifications/{notification_id}/mark-read`, `/me/notifications/mark-all-read`, `/me/notification-settings` — and the path-param key `item_id` follow the backend binding contract (collection routes carry the trailing slash; item routes are `/{item_id}`; settings is a slash-less singleton). If `npx tsc -b` rejects any literal or the `item_id` key, open `src/lib/api/schema.d.ts` and copy the exact key the backend generated. **The only sanctioned adaptation is matching the generated key verbatim — never add `/api/v1`, never change a trailing-slash choice (PROXY-1).**

**Hook 401 discipline (design §5, recon §2.2 — applies to EVERY `/me/*` hook below, queries AND mutations).** `openapi-fetch` resolves non-2xx as `{ error, response }` and does **not** throw. So every hook routes a failure through the shared `raiseApiError(queryClient, response.status)` helper (added to `client.ts` in Task 6.1): a query's `queryFn` calls it when `data === undefined`, and a mutation's `mutationFn` calls it when `!response.ok`. `raiseApiError` invalidates `['auth','me']` when the status is `401` (so a server-side force-logout collapses the header to anonymous in the same breath — design §5 auth-state coherence) and then always throws `ApiError(status)` so the query/mutation still surfaces the failure. A mutation's `onSuccess` additionally invalidates its domain list prefix; no `onError` handler is needed because the 401 invalidation happens inside `mutationFn` before the error propagates.

**Type aliases vs input schemas.** The five aliases the binding contract names (`SavedSearch`, `WatchlistItem`, `Notification`, `NotificationSettings`, `PaginatedNotifications`) are added to `client.ts` in Task 6.1 and imported from `../../../lib/api/client`. Request-body input schemas that are NOT aliased (e.g. `SavedSearchCreate`, `WatchlistItemUpdate`) are type-imported directly from the generated schema: `import type { components } from '../../../lib/api/schema'` then `type X = components['schemas']['X']`.

---

## Phase 6 — Frontend F005: Saved Searches

**Execution Status:** ⬜ NOT STARTED

Delivers: the five type aliases; the saved-searches query + three mutations with fetch-seam tests; the reusable `RequireSignIn` auth-gate; the in-header `SaveSearchControl`; and the `/saved-searches` page with Apply / Rename / two-step Delete.

### Task 6.1: Type aliases + `useSavedSearches` hooks (query + create/rename/delete) with fetch-seam tests

```
BEFORE starting work:
1. Invoke superpowers:test-driven-development
2. Read docs/pitfalls/testing-pitfalls.md
Follow TDD: write failing test → implement → verify green.
```

**Files:**
- Modify: `app/frontend/web/src/lib/api/client.ts` (add five aliases after line 7, the `CurrentUser` alias)
- Create: `app/frontend/web/src/features/saved-searches/hooks/useSavedSearches.ts`
- Test: `app/frontend/web/src/features/saved-searches/hooks/useSavedSearches.test.tsx`

- [ ] **Step 1: Add the five type aliases and the shared 401 helper to `client.ts`.** Insert the aliases after the existing `CurrentUser` alias (client.ts line 7); add the `QueryClient` type import at the top and the `raiseApiError` helper after the `ApiError` class. These are re-exports of generated types plus one shared helper (not feature logic), so this precedes the TDD loop; a `tsc` run confirms the underlying schemas exist.

```ts
// at the top of client.ts, alongside the other imports:
import type { QueryClient } from '@tanstack/react-query'

// after the CurrentUser alias (line 7):
export type SavedSearch = components['schemas']['SavedSearchSchema']
export type WatchlistItem = components['schemas']['WatchlistItemSchema']
export type Notification = components['schemas']['NotificationSchema']
export type NotificationSettings = components['schemas']['NotificationSettingsSchema']
export type PaginatedNotifications = components['schemas']['PaginatedResponse_NotificationSchema_']

// after the ApiError class — the ONE shared 401 handler every /me/* hook (queries AND mutations)
// routes failures through: a 401 means get_current_user destroyed the server-side session
// (design §4.1), so invalidate ['auth','me'] to collapse the header to anonymous in the same breath
// (design §5); then always throw so the query/mutation still surfaces the error to the caller.
export function raiseApiError(queryClient: QueryClient, status: number): never {
  if (status === 401) {
    queryClient.invalidateQueries({ queryKey: ['auth', 'me'] })
  }
  throw new ApiError(status)
}
```

- [ ] **Step 2: Verify the aliases resolve.** Run `cd app/frontend/web && npx tsc -b`. Expected: green. If it errors with "Property 'SavedSearchSchema' does not exist", the backend codegen chain did not land those schemas — STOP and raise to the dispatching agent (the backend phases must complete first); do not hand-edit `schema.d.ts`.

- [ ] **Step 3: Write the failing hook tests.** Create `useSavedSearches.test.tsx`. Mirrors `useLogout.test.tsx` exactly: stub `fetch` at the seam, capture `{url, method, body}`, assert them, and assert `invalidateQueries` is/ isn't called. COMPLETE file:

```tsx
// ABOUTME: useSavedSearches hook contracts — query + create/rename/delete mutations at the fetch seam.
// ABOUTME: Asserts URL/method/body (TEST-5) and that only 2xx invalidates ['savedSearches']; 401 also invalidates ['auth','me'].
import { afterEach, describe, expect, it, vi } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import {
  useSavedSearches,
  useCreateSavedSearch,
  useRenameSavedSearch,
  useDeleteSavedSearch,
} from './useSavedSearches'

interface Call {
  url: string
  method?: string
  body?: string
}

function stubFetch(handler: (call: Call) => Response): Call[] {
  const calls: Call[] = []
  vi.stubGlobal('fetch', async (input: RequestInfo | URL, init?: RequestInit) => {
    const req = input as Request
    const call: Call = {
      url: req.url ?? String(input),
      method: req.method ?? init?.method,
      body: typeof (req as Request).text === 'function' ? await req.clone().text() : undefined,
    }
    calls.push(call)
    return handler(call)
  })
  return calls
}

function wrap() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const spy = vi.spyOn(qc, 'invalidateQueries')
  const wrapper = ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={qc}>{children}</QueryClientProvider>
  )
  return { qc, spy, wrapper }
}

afterEach(() => vi.unstubAllGlobals())

describe('useSavedSearches (query)', () => {
  it('GETs /api/v1/me/saved-searches/ and returns the array', async () => {
    const rows = [{ id: 1, name: 'A', search_parameters: { ships_only: true, size: 50, sort_by: 'date_issued', sort_direction: 'desc' }, created_at: '2026-07-17T00:00:00Z', updated_at: '2026-07-17T00:00:00Z' }]
    const calls = stubFetch(() => new Response(JSON.stringify(rows), { status: 200, headers: { 'Content-Type': 'application/json' } }))
    const { wrapper } = wrap()
    const { result } = renderHook(() => useSavedSearches(), { wrapper })
    await waitFor(() => expect(result.current.data).toHaveLength(1))
    expect(calls[0].url).toContain('/api/v1/me/saved-searches/')
    expect(calls[0].method ?? 'GET').toBe('GET')
    expect(result.current.data![0].name).toBe('A')
  })

  it('invalidates ["auth","me"] when the query 401s', async () => {
    const { spy, wrapper } = wrap()
    stubFetch(() => new Response(JSON.stringify({ detail: 'unauthenticated' }), { status: 401, headers: { 'Content-Type': 'application/json' } }))
    const { result } = renderHook(() => useSavedSearches(), { wrapper })
    await waitFor(() => expect(result.current.isError).toBe(true))
    expect(spy).toHaveBeenCalledWith({ queryKey: ['auth', 'me'] })
  })
})

describe('useCreateSavedSearch', () => {
  const body = { name: 'Cheap frigates', search_parameters: { ships_only: true, size: 50, sort_by: 'price', sort_direction: 'asc' } }

  it('POSTs the body and invalidates ["savedSearches"] on 201', async () => {
    const calls = stubFetch(() => new Response(JSON.stringify({ id: 9, ...body, created_at: 'x', updated_at: 'x' }), { status: 201, headers: { 'Content-Type': 'application/json' } }))
    const { spy, wrapper } = wrap()
    const { result } = renderHook(() => useCreateSavedSearch(), { wrapper })
    result.current.mutate(body)
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(calls[0].url).toContain('/api/v1/me/saved-searches/')
    expect(calls[0].method).toBe('POST')
    expect(JSON.parse(calls[0].body!)).toEqual(body)
    expect(spy).toHaveBeenCalledWith({ queryKey: ['savedSearches'] })
  })

  it('does NOT invalidate on a non-2xx (409) and surfaces the status', async () => {
    const { spy, wrapper } = wrap()
    stubFetch(() => new Response(JSON.stringify({ detail: 'duplicate' }), { status: 409, headers: { 'Content-Type': 'application/json' } }))
    const { result } = renderHook(() => useCreateSavedSearch(), { wrapper })
    result.current.mutate(body)
    await waitFor(() => expect(result.current.isError).toBe(true))
    expect(spy).not.toHaveBeenCalledWith({ queryKey: ['savedSearches'] })
  })

  it('does NOT invalidate on a network failure', async () => {
    const { spy, wrapper } = wrap()
    stubFetch(() => { throw new TypeError('Failed to fetch') })
    const { result } = renderHook(() => useCreateSavedSearch(), { wrapper })
    result.current.mutate(body)
    await waitFor(() => expect(result.current.isError).toBe(true))
    expect(spy).not.toHaveBeenCalledWith({ queryKey: ['savedSearches'] })
  })

  it('invalidates ["auth","me"] when the server 401s', async () => {
    const { spy, wrapper } = wrap()
    stubFetch(() => new Response(JSON.stringify({ detail: 'unauthenticated' }), { status: 401, headers: { 'Content-Type': 'application/json' } }))
    const { result } = renderHook(() => useCreateSavedSearch(), { wrapper })
    result.current.mutate(body)
    await waitFor(() => expect(result.current.isError).toBe(true))
    expect(spy).toHaveBeenCalledWith({ queryKey: ['auth', 'me'] })
    expect(spy).not.toHaveBeenCalledWith({ queryKey: ['savedSearches'] })
  })
})

describe('useRenameSavedSearch', () => {
  it('PUTs the name to the item route and invalidates on 200', async () => {
    const calls = stubFetch(() => new Response(JSON.stringify({ id: 5, name: 'New', search_parameters: {}, created_at: 'x', updated_at: 'x' }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
    const { spy, wrapper } = wrap()
    const { result } = renderHook(() => useRenameSavedSearch(), { wrapper })
    result.current.mutate({ id: 5, name: 'New' })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(calls[0].url).toContain('/api/v1/me/saved-searches/5')
    expect(calls[0].method).toBe('PUT')
    expect(JSON.parse(calls[0].body!)).toEqual({ name: 'New' })
    expect(spy).toHaveBeenCalledWith({ queryKey: ['savedSearches'] })
  })

  it('does NOT invalidate on a non-2xx (404)', async () => {
    const { spy, wrapper } = wrap()
    stubFetch(() => new Response(JSON.stringify({ detail: 'not found' }), { status: 404, headers: { 'Content-Type': 'application/json' } }))
    const { result } = renderHook(() => useRenameSavedSearch(), { wrapper })
    result.current.mutate({ id: 5, name: 'New' })
    await waitFor(() => expect(result.current.isError).toBe(true))
    expect(spy).not.toHaveBeenCalledWith({ queryKey: ['savedSearches'] })
  })
})

describe('useDeleteSavedSearch', () => {
  it('DELETEs the item route and invalidates on 204', async () => {
    const calls = stubFetch(() => new Response(null, { status: 204 }))
    const { spy, wrapper } = wrap()
    const { result } = renderHook(() => useDeleteSavedSearch(), { wrapper })
    result.current.mutate(7)
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(calls[0].url).toContain('/api/v1/me/saved-searches/7')
    expect(calls[0].method).toBe('DELETE')
    expect(spy).toHaveBeenCalledWith({ queryKey: ['savedSearches'] })
  })

  it('does NOT invalidate on a non-2xx (404)', async () => {
    const { spy, wrapper } = wrap()
    stubFetch(() => new Response(JSON.stringify({ detail: 'not found' }), { status: 404, headers: { 'Content-Type': 'application/json' } }))
    const { result } = renderHook(() => useDeleteSavedSearch(), { wrapper })
    result.current.mutate(7)
    await waitFor(() => expect(result.current.isError).toBe(true))
    expect(spy).not.toHaveBeenCalledWith({ queryKey: ['savedSearches'] })
  })
})
```

- [ ] **Step 4: Run the tests, confirm they fail.** `cd app/frontend/web && npx vitest run src/features/saved-searches/hooks/useSavedSearches.test.tsx --reporter=dot`. Expected: failure — `Failed to resolve import "./useSavedSearches"` (module does not exist yet).

- [ ] **Step 5: Implement `useSavedSearches.ts`.** COMPLETE file:

```ts
// ABOUTME: TanStack Query hooks for F005 saved searches — list query + create/rename/delete mutations.
// ABOUTME: Every hook routes non-2xx through raiseApiError (invalidates ['auth','me'] on 401); mutations invalidate ['savedSearches'] on 2xx.
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api, raiseApiError, type SavedSearch } from '../../../lib/api/client'
import type { components } from '../../../lib/api/schema'

type SavedSearchCreate = components['schemas']['SavedSearchCreate']

export function useSavedSearches() {
  const queryClient = useQueryClient()
  return useQuery<SavedSearch[]>({
    queryKey: ['savedSearches', 'list'],
    queryFn: async () => {
      const { data, response } = await api.GET('/me/saved-searches/')
      if (data === undefined) raiseApiError(queryClient, response.status)
      return data
    },
  })
}

export function useCreateSavedSearch() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (body: SavedSearchCreate) => {
      const { data, response } = await api.POST('/me/saved-searches/', { body })
      if (!response.ok) raiseApiError(queryClient, response.status)
      return data
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['savedSearches'] }),
  })
}

export function useRenameSavedSearch() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async ({ id, name }: { id: number; name: string }) => {
      const { data, response } = await api.PUT('/me/saved-searches/{search_id}', {
        params: { path: { search_id: id } },
        body: { name },
      })
      if (!response.ok) raiseApiError(queryClient, response.status)
      return data
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['savedSearches'] }),
  })
}

export function useDeleteSavedSearch() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (id: number) => {
      const { response } = await api.DELETE('/me/saved-searches/{search_id}', {
        params: { path: { search_id: id } },
      })
      if (!response.ok) raiseApiError(queryClient, response.status)
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['savedSearches'] }),
  })
}
```

- [ ] **Step 6: Run the tests green.** `cd app/frontend/web && npx vitest run src/features/saved-searches/hooks/useSavedSearches.test.tsx --reporter=dot`. Expected: all pass. Then `npx tsc -b` (green) and `npx eslint src/features/saved-searches src/lib/api/client.ts` (green).

- [ ] **Step 7: Commit.**
  `git add app/frontend/web/src/lib/api/client.ts app/frontend/web/src/features/saved-searches/hooks/useSavedSearches.ts app/frontend/web/src/features/saved-searches/hooks/useSavedSearches.test.tsx`
  ```
  feat(web): add saved-search type aliases and CRUD query hooks

  Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>
  ```

```
BEFORE marking this task complete:
1. Review tests against docs/pitfalls/testing-pitfalls.md
2. Verify test coverage (error paths? edge cases?)
3. Run tests and confirm green
```

### Task 6.2: `RequireSignIn` auth-gate component + test

```
BEFORE starting work:
1. Invoke superpowers:test-driven-development
2. Read docs/pitfalls/testing-pitfalls.md
Follow TDD: write failing test → implement → verify green.
```

**Files:**
- Create: `app/frontend/web/src/features/auth/components/RequireSignIn.tsx`
- Test: `app/frontend/web/src/features/auth/components/RequireSignIn.test.tsx`

- [ ] **Step 1: Write the failing test.** Renders `RequireSignIn` inside a minimal TanStack memory router (so `useLocation` resolves) at a URL carrying a transient `?sso=` plus a real param, and asserts the login link's `href` carries `next` = encoded path+search with `sso` stripped — the exact `HeaderIdentity` mechanic (recon §5.3). COMPLETE file:

```tsx
// ABOUTME: RequireSignIn renders the sign-in prompt; its login href mirrors HeaderIdentity (next=encoded path+search, sso stripped).
import { afterEach, describe, expect, it } from 'vitest'
import { cleanup, render, screen } from '@testing-library/react'
import { createMemoryHistory, createRootRoute, createRouter, RouterProvider } from '@tanstack/react-router'
import { RequireSignIn } from './RequireSignIn'

afterEach(cleanup)

function renderAt(initialUrl: string) {
  const rootRoute = createRootRoute({ component: () => <RequireSignIn feature="saved searches" /> })
  const router = createRouter({
    routeTree: rootRoute,
    history: createMemoryHistory({ initialEntries: [initialUrl] }),
  })
  render(<RouterProvider router={router} />)
}

describe('RequireSignIn', () => {
  it('renders a prompt naming the feature and a login link with the encoded next', async () => {
    renderAt('/saved-searches?foo=bar')
    expect(await screen.findByRole('heading', { name: /sign in to use saved searches/i })).toBeInTheDocument()
    const link = screen.getByRole('link', { name: /log in with eve/i })
    const next = encodeURIComponent('/saved-searches?foo=bar')
    expect(link).toHaveAttribute('href', `/api/v1/auth/sso/login?next=${next}`)
  })

  it('strips a transient ?sso flag out of the encoded next', async () => {
    renderAt('/saved-searches?sso=denied&foo=bar')
    const link = await screen.findByRole('link', { name: /log in with eve/i })
    const next = encodeURIComponent('/saved-searches?foo=bar')
    expect(link).toHaveAttribute('href', `/api/v1/auth/sso/login?next=${next}`)
    // The href legitimately contains "/auth/sso/login", so `.not.toContain('sso')` could never pass.
    // The thing that must be stripped is the transient `sso` QUERY param inside `next` — parse the
    // URL and assert the DECODED next carries no `sso=`, while the endpoint path is untouched.
    const href = link.getAttribute('href')!
    expect(href.startsWith('/api/v1/auth/sso/login')).toBe(true)
    const decodedNext = decodeURIComponent(new URL(href, 'https://localhost:5173').searchParams.get('next')!)
    expect(decodedNext).not.toContain('sso=')
  })
})
```

- [ ] **Step 2: Run it, confirm failure.** `cd app/frontend/web && npx vitest run src/features/auth/components/RequireSignIn.test.tsx --reporter=dot`. Expected: `Failed to resolve import "./RequireSignIn"`.

- [ ] **Step 3: Implement `RequireSignIn.tsx`.** COMPLETE file:

```tsx
// ABOUTME: Shared auth-gate prompt for the M3 pages — a sign-in card whose login link deep-links back to the current path.
// ABOUTME: Login is a FULL navigation (not an SPA Link) to the backend redirect; next=encoded path+search with ?sso stripped (mirrors HeaderIdentity).
import { useLocation } from '@tanstack/react-router'
import { buttonClasses } from '../../../components/Button'

export function RequireSignIn({ feature }: { feature: string }) {
  const location = useLocation()
  // Strip a transient ?sso=denied|error before baking it into next, or a successful
  // login round-trips the user back to a stale SSO notice (same as HeaderIdentity §4.1).
  const params = new URLSearchParams(location.searchStr)
  params.delete('sso')
  const search = params.toString()
  const next = encodeURIComponent(location.pathname + (search ? `?${search}` : ''))
  return (
    <div className="flex flex-col items-start gap-3 rounded-md border border-line bg-surface px-5 py-8">
      <h2 className="text-base font-medium text-ink">Sign in to use {feature}</h2>
      <p className="max-w-[52ch] text-sm text-ink-dim">
        Log in with your EVE character to view and manage {feature}.
      </p>
      {/* Full navigation (not an SPA route): the browser must leave the app to hit the backend redirect. */}
      <a href={`/api/v1/auth/sso/login?next=${next}`} className={buttonClasses('primary')}>
        Log in with EVE
      </a>
    </div>
  )
}
```

- [ ] **Step 4: Run green.** `cd app/frontend/web && npx vitest run src/features/auth/components/RequireSignIn.test.tsx --reporter=dot` (pass), then `npx tsc -b` and `npx eslint src/features/auth/components/RequireSignIn.tsx` (green).

- [ ] **Step 5: Commit.**
  `git add app/frontend/web/src/features/auth/components/RequireSignIn.tsx app/frontend/web/src/features/auth/components/RequireSignIn.test.tsx`
  ```
  feat(web): add RequireSignIn auth-gate prompt

  Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>
  ```

```
BEFORE marking this task complete:
1. Review tests against docs/pitfalls/testing-pitfalls.md
2. Verify test coverage (error paths? edge cases?)
3. Run tests and confirm green
```

### Task 6.3: `SaveSearchControl` in the ContractsPage results header + tests

```
BEFORE starting work:
1. Invoke superpowers:test-driven-development
2. Read docs/pitfalls/testing-pitfalls.md
Follow TDD: write failing test → implement → verify green.
```

**Files:**
- Create: `app/frontend/web/src/features/saved-searches/components/SaveSearchControl.tsx`
- Modify: `app/frontend/web/src/features/contracts/components/ContractsPage.tsx` (results-header `<div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">`, lines 107–116)
- Test: `app/frontend/web/src/features/saved-searches/components/SaveSearchControl.test.tsx`

- [ ] **Step 1: Write the failing integration test.** Drives the control through `renderApp('/contracts')` so the real ContractsPage + header render; stubs `/me` (authed/anonymous), the contract list, and captures the saved-search POST at the seam. COMPLETE file:

```tsx
// ABOUTME: SaveSearchControl integration over the real /contracts route — hidden when anonymous; posts search-minus-page; 409 inline.
// ABOUTME: Asserts the POSTed wire payload (TEST-5), incl. the sub-MIN_SEARCH_LENGTH search-drop that mirrors toApiQuery.
import { afterEach, describe, expect, it, vi } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { anonymousMe, jsonResponse } from '../../../test/http'
import { renderApp } from '../../../test/renderApp'

interface Call { url: string; method?: string; body?: string }

const AUTHED = { character_id: 91000001, character_name: 'Sesta Hound' }
const EMPTY_PAGE = { total: 0, page: 1, size: 50, items: [] }

function stubFetch(handler: (url: string, call: Call) => Response): Call[] {
  const calls: Call[] = []
  vi.stubGlobal('fetch', async (input: RequestInfo | URL, init?: RequestInit) => {
    const req = input as Request
    const url = req.url ?? String(input)
    const call: Call = { url, method: req.method ?? init?.method, body: await req.clone().text() }
    calls.push(call)
    return handler(url, call)
  })
  return calls
}

afterEach(() => vi.unstubAllGlobals())

describe('SaveSearchControl', () => {
  it('is hidden for anonymous users', async () => {
    stubFetch(anonymousMe(() => jsonResponse(EMPTY_PAGE)))
    renderApp('/contracts')
    await screen.findByRole('heading', { level: 1, name: /ship contracts/i })
    expect(screen.queryByRole('button', { name: /save search/i })).not.toBeInTheDocument()
  })

  it('posts search-minus-page with the correct wire payload', async () => {
    const calls = stubFetch((url) => {
      if (/\/api\/v1\/me$/.test(url)) return jsonResponse(AUTHED)
      if (/\/me\/saved-searches\//.test(url)) return jsonResponse({ id: 1, name: 'Cheap', search_parameters: {}, created_at: 'x', updated_at: 'x' }, 201)
      return jsonResponse(EMPTY_PAGE)
    })
    renderApp('/contracts?min_price=1000&sort_by=price&sort_direction=asc')
    await userEvent.click(await screen.findByRole('button', { name: /save search/i }))
    await userEvent.type(screen.getByLabelText(/search name/i), 'Cheap')
    await userEvent.click(screen.getByRole('button', { name: /^save$/i }))
    await waitFor(() => expect(calls.some((c) => /\/me\/saved-searches\//.test(c.url) && c.method === 'POST')).toBe(true))
    const post = calls.find((c) => /\/me\/saved-searches\//.test(c.url) && c.method === 'POST')!
    const payload = JSON.parse(post.body!)
    expect(payload.name).toBe('Cheap')
    expect(payload.search_parameters).toMatchObject({ min_price: 1000, ships_only: true, sort_by: 'price', sort_direction: 'asc' })
    expect(payload.search_parameters).not.toHaveProperty('page')
  })

  it('drops a sub-3-character search from the persisted payload (mirrors toApiQuery)', async () => {
    const calls = stubFetch((url) => {
      if (/\/api\/v1\/me$/.test(url)) return jsonResponse(AUTHED)
      if (/\/me\/saved-searches\//.test(url)) return jsonResponse({ id: 1, name: 'x', search_parameters: {}, created_at: 'x', updated_at: 'x' }, 201)
      return jsonResponse(EMPTY_PAGE)
    })
    renderApp('/contracts?search=ab')
    await userEvent.click(await screen.findByRole('button', { name: /save search/i }))
    await userEvent.type(screen.getByLabelText(/search name/i), 'Typo hunt')
    await userEvent.click(screen.getByRole('button', { name: /^save$/i }))
    await waitFor(() => expect(calls.some((c) => /\/me\/saved-searches\//.test(c.url) && c.method === 'POST')).toBe(true))
    const post = calls.find((c) => /\/me\/saved-searches\//.test(c.url) && c.method === 'POST')!
    expect(JSON.parse(post.body!).search_parameters).not.toHaveProperty('search')
  })

  it('renders an inline error when the name conflicts (409)', async () => {
    stubFetch((url) => {
      if (/\/api\/v1\/me$/.test(url)) return jsonResponse(AUTHED)
      if (/\/me\/saved-searches\//.test(url)) return jsonResponse({ detail: 'duplicate' }, 409)
      return jsonResponse(EMPTY_PAGE)
    })
    renderApp('/contracts')
    await userEvent.click(await screen.findByRole('button', { name: /save search/i }))
    await userEvent.type(screen.getByLabelText(/search name/i), 'Dupe')
    await userEvent.click(screen.getByRole('button', { name: /^save$/i }))
    expect(await screen.findByText(/name already exists/i)).toBeInTheDocument()
  })
})
```

- [ ] **Step 2: Run it, confirm failure.** `cd app/frontend/web && npx vitest run src/features/saved-searches/components/SaveSearchControl.test.tsx --reporter=dot`. Expected: no "Save search" button found (control not wired into ContractsPage yet).

- [ ] **Step 3: Implement `SaveSearchControl.tsx`.** Exports the pure `toSavedSearchParameters` (search-minus-page + sub-min search drop) plus the control. COMPLETE file:

```tsx
// ABOUTME: Authed-only "Save search" control for the ContractsPage results header — inline name disclosure, posts search-minus-page.
// ABOUTME: toSavedSearchParameters drops `page` and gates a sub-MIN_SEARCH_LENGTH search exactly as toApiQuery does, so a mid-typing 1–2-char search never 422s the save.
import { useState } from 'react'
import { Button } from '../../../components/Button'
import { Input } from '../../../components/Input'
import { ApiError } from '../../../lib/api/client'
import type { components } from '../../../lib/api/schema'
import { useCurrentUser } from '../../auth/hooks/useCurrentUser'
import { MIN_SEARCH_LENGTH, type ContractSearch } from '../../contracts/filters'
import { useCreateSavedSearch } from '../hooks/useSavedSearches'

type SavedSearchParameters = components['schemas']['SavedSearchParameters']

export function toSavedSearchParameters(search: ContractSearch): SavedSearchParameters {
  const { page: _page, search: rawSearch, ...rest } = search
  const trimmed = rawSearch?.trim()
  return {
    ...rest,
    search: trimmed !== undefined && trimmed.length >= MIN_SEARCH_LENGTH ? trimmed : undefined,
  }
}

export function SaveSearchControl({ search }: { search: ContractSearch }) {
  const { data: user } = useCurrentUser()
  const [open, setOpen] = useState(false)
  const [name, setName] = useState('')
  const create = useCreateSavedSearch()

  if (!user) return null

  if (!open) {
    return (
      <Button
        className="ml-auto"
        onClick={() => {
          create.reset()
          setOpen(true)
        }}
      >
        Save search
      </Button>
    )
  }

  const conflict = create.error instanceof ApiError && create.error.status === 409
  const close = () => {
    setOpen(false)
    setName('')
    create.reset()
  }

  const submit = (event: React.FormEvent) => {
    event.preventDefault()
    const trimmed = name.trim()
    if (trimmed.length === 0) return
    create.mutate(
      { name: trimmed, search_parameters: toSavedSearchParameters(search) },
      { onSuccess: () => close() },
    )
  }

  return (
    <form onSubmit={submit} aria-label="Save this search" className="ml-auto flex flex-wrap items-center gap-2">
      <label htmlFor="save-search-name" className="sr-only">Search name</label>
      <Input
        id="save-search-name"
        value={name}
        onChange={(event) => setName(event.target.value)}
        placeholder="Name this search"
        autoFocus
      />
      <Button type="submit" variant="primary" disabled={create.isPending || name.trim().length === 0}>
        Save
      </Button>
      <Button type="button" onClick={close}>Cancel</Button>
      {conflict ? (
        <p role="alert" aria-live="polite" className="w-full text-xs text-danger">
          A saved search with that name already exists.
        </p>
      ) : create.isError ? (
        <p role="alert" aria-live="polite" className="w-full text-xs text-danger">
          Could not save the search. Try again.
        </p>
      ) : null}
    </form>
  )
}
```

- [ ] **Step 4: Wire `SaveSearchControl` into ContractsPage.** Add the import and render it in the results-header flex row. Edit `ContractsPage.tsx`: add `import { SaveSearchControl } from '../../saved-searches/components/SaveSearchControl'` alongside the other imports, and inside the `<div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">` (after the `{data !== undefined ? (<p …>… matching</p>) : null}` block, still inside the div) add:

```tsx
          <SaveSearchControl search={search} />
```

The control's own `ml-auto` pushes it to the right of the count; for anonymous users it returns `null` so the header is unchanged (existing `pages.test.tsx` uses `anonymousMe`, so nothing there regresses).

- [ ] **Step 5: Run green.** `cd app/frontend/web && npx vitest run src/features/saved-searches/components/SaveSearchControl.test.tsx --reporter=dot` (pass). Then re-run the neighbouring suite to prove no regression: `npx vitest run src/features/contracts/components/pages.test.tsx --reporter=dot` (pass). Then `npx tsc -b` and `npx eslint src/features/saved-searches src/features/contracts/components/ContractsPage.tsx` (green).

- [ ] **Step 6: Commit.**
  `git add app/frontend/web/src/features/saved-searches/components/SaveSearchControl.tsx app/frontend/web/src/features/saved-searches/components/SaveSearchControl.test.tsx app/frontend/web/src/features/contracts/components/ContractsPage.tsx`
  ```
  feat(web): add Save Search control to the contracts results header

  Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>
  ```

```
BEFORE marking this task complete:
1. Review tests against docs/pitfalls/testing-pitfalls.md
2. Verify test coverage (error paths? edge cases?)
3. Run tests and confirm green
```

### Task 6.4: `/saved-searches` route + `SavedSearchesPage` (Apply / Rename / two-step Delete) + page tests

```
BEFORE starting work:
1. Invoke superpowers:test-driven-development
2. Read docs/pitfalls/testing-pitfalls.md
Follow TDD: write failing test → implement → verify green.
```

**Files:**
- Create: `app/frontend/web/src/routes/saved-searches.tsx`
- Create: `app/frontend/web/src/features/saved-searches/components/SavedSearchesPage.tsx`
- Test: `app/frontend/web/src/features/saved-searches/components/SavedSearchesPage.test.tsx`
- Test: `app/frontend/web/src/features/saved-searches/components/SavedSearchesPage.a11y.test.tsx` (vitest-axe, design §6)

- [ ] **Step 1: Write the failing page tests.** Cover the three auth branches, the empty state, Apply (navigates to `/contracts` with parsed params), Rename, two-step Delete, and the TEST-7 (error) + TEST-8 (skeleton-unmount sync) disciplines. Because `renderApp` builds a QueryClient with `retry: false`, error-state stubs fail **every** call to the endpoint (the robust form of TEST-7). Every authed stub answers the header bell's unread-count query (`GET /me/notifications/?is_read=false&size=1`) with the page shape `{ total: 0, page: 1, size: 1, items: [] }` — once Task 8.2 mounts the bell into `HeaderIdentity`, a bare `[]` would leave that count query with `data.total === undefined` and silently error (NIT-9); stubbing the real shape now keeps these tests hermetic afterward. COMPLETE file:

```tsx
// ABOUTME: SavedSearchesPage tests over the real /saved-searches route — auth branches, empty state, Apply/Rename/Delete, error + skeleton sync.
// ABOUTME: TEST-8: wait for the loading skeleton (role=status "Loading saved searches") to unmount before asserting list content.
import { afterEach, describe, expect, it, vi } from 'vitest'
import { act, screen, waitFor, waitForElementToBeRemoved } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { jsonResponse } from '../../../test/http'
import { renderApp } from '../../../test/renderApp'
import { summarizeSearch } from './SavedSearchesPage'

const AUTHED = { character_id: 91000001, character_name: 'Sesta Hound' }
const SAVED = [
  { id: 1, name: 'Cheap frigates', search_parameters: { ships_only: true, min_price: 0, max_price: 5000000, size: 50, sort_by: 'price', sort_direction: 'asc' }, created_at: '2026-07-17T00:00:00Z', updated_at: '2026-07-17T00:00:00Z' },
]

interface Call { url: string; method?: string; body?: string }
function stubFetch(handler: (url: string, call: Call) => Response): Call[] {
  const calls: Call[] = []
  vi.stubGlobal('fetch', async (input: RequestInfo | URL, init?: RequestInit) => {
    const req = input as Request
    const url = req.url ?? String(input)
    const call: Call = { url, method: req.method ?? init?.method, body: await req.clone().text() }
    calls.push(call)
    return handler(url, call)
  })
  return calls
}

afterEach(() => vi.unstubAllGlobals())

describe('SavedSearchesPage', () => {
  it('prompts anonymous users to sign in', async () => {
    stubFetch((url) => (/\/api\/v1\/me$/.test(url) ? jsonResponse({ detail: 'unauthenticated' }, 401) : jsonResponse([])))
    renderApp('/saved-searches')
    expect(await screen.findByRole('heading', { name: /sign in to use saved searches/i })).toBeInTheDocument()
  })

  it('lists saved searches for an authed user after the skeleton unmounts (TEST-8)', async () => {
    stubFetch((url) => {
      if (/\/api\/v1\/me$/.test(url)) return jsonResponse(AUTHED)
      if (/\/me\/notifications\//.test(url)) return jsonResponse({ total: 0, page: 1, size: 1, items: [] })
      if (/\/me\/saved-searches\//.test(url)) return jsonResponse(SAVED)
      return jsonResponse([])
    })
    renderApp('/saved-searches')
    // Skeleton and the always-mounted live region are both role=status while loading;
    // sync on the skeleton unmounting before asserting content (TEST-8).
    const skeleton = await screen.findByRole('status', { name: /loading saved searches/i })
    await waitForElementToBeRemoved(skeleton)
    expect(screen.getByText('Cheap frigates')).toBeInTheDocument()
  })

  it('shows the empty state when the user has no saved searches', async () => {
    stubFetch((url) => {
      if (/\/api\/v1\/me$/.test(url)) return jsonResponse(AUTHED)
      if (/\/me\/notifications\//.test(url)) return jsonResponse({ total: 0, page: 1, size: 1, items: [] })
      if (/\/me\/saved-searches\//.test(url)) return jsonResponse([])
      return jsonResponse([])
    })
    renderApp('/saved-searches')
    expect(await screen.findByText(/no saved searches yet/i)).toBeInTheDocument()
  })

  it('shows an error state when the list fails to load (TEST-7: every call fails)', async () => {
    stubFetch((url) => {
      if (/\/api\/v1\/me$/.test(url)) return jsonResponse(AUTHED)
      if (/\/me\/notifications\//.test(url)) return jsonResponse({ total: 0, page: 1, size: 1, items: [] })
      if (/\/me\/saved-searches\//.test(url)) return jsonResponse({ detail: 'boom' }, 500)
      return jsonResponse([])
    })
    renderApp('/saved-searches')
    expect(await screen.findByRole('alert')).toHaveTextContent(/couldn.t load your saved searches/i)
  })

  it('applies a saved search by navigating to /contracts with the parsed params', async () => {
    stubFetch((url) => {
      if (/\/api\/v1\/me$/.test(url)) return jsonResponse(AUTHED)
      if (/\/me\/notifications\//.test(url)) return jsonResponse({ total: 0, page: 1, size: 1, items: [] })
      if (/\/me\/saved-searches\//.test(url)) return jsonResponse(SAVED)
      return jsonResponse({ total: 0, page: 1, size: 50, items: [] })
    })
    const { router } = renderApp('/saved-searches')
    await screen.findByText('Cheap frigates')
    await userEvent.click(screen.getByRole('button', { name: /apply/i }))
    await waitFor(() => expect(router.state.location.pathname).toBe('/contracts'))
    expect(router.state.location.searchStr).toContain('sort_by=price')
  })

  it('renames a saved search (PUT with the new name)', async () => {
    const calls = stubFetch((url) => {
      if (/\/api\/v1\/me$/.test(url)) return jsonResponse(AUTHED)
      if (/\/me\/notifications\//.test(url)) return jsonResponse({ total: 0, page: 1, size: 1, items: [] })
      if (/\/me\/saved-searches\/1/.test(url)) return jsonResponse({ ...SAVED[0], name: 'Renamed' })
      if (/\/me\/saved-searches\//.test(url)) return jsonResponse(SAVED)
      return jsonResponse([])
    })
    renderApp('/saved-searches')
    await screen.findByText('Cheap frigates')
    await userEvent.click(screen.getByRole('button', { name: /rename/i }))
    const input = screen.getByLabelText(/new name/i)
    await userEvent.clear(input)
    await userEvent.type(input, 'Renamed')
    await userEvent.click(screen.getByRole('button', { name: /^save$/i }))
    await waitFor(() => expect(calls.some((c) => /\/me\/saved-searches\/1/.test(c.url) && c.method === 'PUT')).toBe(true))
    const put = calls.find((c) => /\/me\/saved-searches\/1/.test(c.url) && c.method === 'PUT')!
    expect(JSON.parse(put.body!)).toEqual({ name: 'Renamed' })
  })

  it('requires a second click to delete (two-step)', async () => {
    const calls = stubFetch((url) => {
      if (/\/api\/v1\/me$/.test(url)) return jsonResponse(AUTHED)
      if (/\/me\/notifications\//.test(url)) return jsonResponse({ total: 0, page: 1, size: 1, items: [] })
      if (/\/me\/saved-searches\/1/.test(url)) return new Response(null, { status: 204 })
      if (/\/me\/saved-searches\//.test(url)) return jsonResponse(SAVED)
      return jsonResponse([])
    })
    renderApp('/saved-searches')
    await screen.findByText('Cheap frigates')
    await userEvent.click(screen.getByRole('button', { name: /^delete$/i }))
    // First click arms; no request yet.
    expect(calls.some((c) => c.method === 'DELETE')).toBe(false)
    await userEvent.click(screen.getByRole('button', { name: /confirm delete/i }))
    await waitFor(() => expect(calls.some((c) => /\/me\/saved-searches\/1/.test(c.url) && c.method === 'DELETE')).toBe(true))
  })

  it('auto-disarms the two-step delete after 5s (timeout reset)', async () => {
    stubFetch((url) => {
      if (/\/api\/v1\/me$/.test(url)) return jsonResponse(AUTHED)
      if (/\/me\/notifications\//.test(url)) return jsonResponse({ total: 0, page: 1, size: 1, items: [] })
      if (/\/me\/saved-searches\//.test(url)) return jsonResponse(SAVED)
      return jsonResponse([])
    })
    renderApp('/saved-searches')
    await screen.findByText('Cheap frigates')
    // Enable fake timers AFTER the initial load so the arming click schedules the 5s timeout on the
    // fake clock; userEvent advances the fake clock for its own internal timing.
    vi.useFakeTimers()
    try {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime })
      await user.click(screen.getByRole('button', { name: /^delete$/i }))
      expect(screen.getByRole('button', { name: /confirm delete/i })).toBeInTheDocument()
      act(() => { vi.advanceTimersByTime(5000) })
      expect(screen.queryByRole('button', { name: /confirm delete/i })).not.toBeInTheDocument()
    } finally {
      vi.useRealTimers()
    }
  })
})

describe('summarizeSearch', () => {
  it('defaults the sort fields when an older stored blob omits them', () => {
    // Older blobs may omit the server-defaulted sort_by/sort_direction; the summary must still render
    // (a `.replace()` on undefined would be a TS build error and a runtime crash).
    expect(summarizeSearch({})).toContain('sorted by date issued desc')
  })
})
```

- [ ] **Step 2: Run, confirm failure.** `cd app/frontend/web && npx vitest run src/features/saved-searches/components/SavedSearchesPage.test.tsx --reporter=dot`. Expected failure: the `/saved-searches` route does not exist, so `renderApp` renders a not-found and the prompt/heading assertions fail.

- [ ] **Step 3: Create the route file `src/routes/saved-searches.tsx`.** Named-`RouteComponent` pattern (recon §1). COMPLETE file:

```tsx
import { createFileRoute } from '@tanstack/react-router'
import { SavedSearchesPage } from '../features/saved-searches/components/SavedSearchesPage'

export const Route = createFileRoute('/saved-searches')({
  component: RouteComponent,
})

// Named (uppercase) component so eslint-plugin-react-hooks@7 recognizes the hooks
// inside SavedSearchesPage as hooks-in-a-component (same rationale as contracts.index.tsx).
function RouteComponent() {
  return <SavedSearchesPage />
}
```

- [ ] **Step 4: Implement `SavedSearchesPage.tsx`.** Exports `summarizeSearch` (criteria summary) plus the page. COMPLETE file:

```tsx
// ABOUTME: F005 saved-searches manage page — auth-gated list with per-row Apply (navigate to /contracts), inline Rename, and two-step Delete.
// ABOUTME: summarizeSearch renders a human-readable criteria line from the stored SavedSearchParameters blob.
import { useEffect, useState } from 'react'
import { useNavigate } from '@tanstack/react-router'
import { Button } from '../../../components/Button'
import { Input } from '../../../components/Input'
import type { SavedSearch } from '../../../lib/api/client'
import type { components } from '../../../lib/api/schema'
import { useDocumentTitle } from '../../../lib/useDocumentTitle'
import { RequireSignIn } from '../../auth/components/RequireSignIn'
import { useCurrentUser } from '../../auth/hooks/useCurrentUser'
import { parseContractSearch } from '../../contracts/filters'
import { formatIsk } from '../../contracts/format'
import { useDeleteSavedSearch, useRenameSavedSearch, useSavedSearches } from '../hooks/useSavedSearches'

type SavedSearchParameters = components['schemas']['SavedSearchParameters']

export function summarizeSearch(p: SavedSearchParameters): string {
  const parts: string[] = []
  if (p.search) parts.push(`“${p.search}”`)
  parts.push(p.ships_only ? 'Ships only' : 'All contracts')
  if (p.is_bpc) parts.push('BPC only')
  if (p.min_price != null || p.max_price != null) {
    const lo = p.min_price != null ? formatIsk(p.min_price) : '0'
    const hi = p.max_price != null ? formatIsk(p.max_price) : '∞'
    parts.push(`${lo}–${hi} ISK`)
  }
  if (p.region_ids && p.region_ids.length > 0) {
    parts.push(`${p.region_ids.length} region${p.region_ids.length === 1 ? '' : 's'}`)
  }
  // sort_by / sort_direction have server-side defaults, so openapi-typescript types them optional
  // (possibly-undefined). Default before use — a `.replace()` on undefined is a TS18048 build error
  // AND an older stored blob may genuinely omit them.
  parts.push(`sorted by ${(p.sort_by ?? 'date_issued').replace(/_/g, ' ')} ${p.sort_direction ?? 'desc'}`)
  return parts.join(' · ')
}

export function SavedSearchesPage() {
  useDocumentTitle('Saved Searches')
  const { data: user, isPending } = useCurrentUser()

  if (isPending) {
    return (
      <div role="status" aria-label="Loading account" className="mx-auto max-w-3xl">
        <span className="skeleton block h-7 w-48" />
        <span className="sr-only">Loading…</span>
      </div>
    )
  }
  if (!user) return <RequireSignIn feature="saved searches" />
  return <SavedSearchesList />
}

function SavedSearchesList() {
  const { data, isPending, isError } = useSavedSearches()
  return (
    <div className="mx-auto max-w-3xl">
      {/* Always-mounted polite region so mutation outcomes reach assistive tech (WCAG 4.1.3). */}
      <p className="sr-only" role="status" aria-live="polite" />
      <h1 className="text-h1 mb-4 font-semibold">Saved Searches</h1>
      {isPending ? (
        <div role="status" aria-label="Loading saved searches">
          <span className="skeleton block h-16 w-full" />
          <span className="sr-only">Loading saved searches…</span>
        </div>
      ) : isError ? (
        <div role="alert" className="rounded-md border border-danger/40 bg-danger-wash px-4 py-4 text-sm text-ink">
          Couldn’t load your saved searches. Reload the page to try again.
        </div>
      ) : data.length === 0 ? (
        <div className="rounded-md border border-line bg-surface px-5 py-8">
          <h2 className="text-base font-medium text-ink">No saved searches yet</h2>
          <p className="mt-1 max-w-[52ch] text-sm text-ink-dim">
            On the contracts page, set up a filter you like and choose “Save search” to keep it here.
          </p>
        </div>
      ) : (
        <ul className="flex flex-col gap-2">
          {data.map((saved) => (
            <SavedSearchRow key={saved.id} saved={saved} />
          ))}
        </ul>
      )}
    </div>
  )
}

function SavedSearchRow({ saved }: { saved: SavedSearch }) {
  const navigate = useNavigate()
  const rename = useRenameSavedSearch()
  const remove = useDeleteSavedSearch()
  const [renaming, setRenaming] = useState(false)
  const [name, setName] = useState(saved.name)
  const [confirmDelete, setConfirmDelete] = useState(false)

  // Auto-disarm the two-step delete after 5s so a stray first click can't leave the row armed
  // indefinitely (blur also disarms; this covers the focus-retained case). Cleared on unmount/re-arm.
  useEffect(() => {
    if (!confirmDelete) return
    const timer = setTimeout(() => setConfirmDelete(false), 5000)
    return () => clearTimeout(timer)
  }, [confirmDelete])

  const apply = () =>
    navigate({ to: '/contracts', search: parseContractSearch(saved.search_parameters as Record<string, unknown>) })

  const submitRename = (event: React.FormEvent) => {
    event.preventDefault()
    const trimmed = name.trim()
    if (trimmed.length === 0) return
    rename.mutate({ id: saved.id, name: trimmed }, { onSuccess: () => setRenaming(false) })
  }

  return (
    <li className="flex flex-wrap items-center gap-3 rounded-md border border-line bg-surface px-4 py-3">
      <div className="min-w-0 flex-1">
        {renaming ? (
          <form onSubmit={submitRename} className="flex flex-wrap items-center gap-2" aria-label={`Rename ${saved.name}`}>
            <label htmlFor={`rename-${saved.id}`} className="sr-only">New name</label>
            <Input id={`rename-${saved.id}`} value={name} onChange={(e) => setName(e.target.value)} autoFocus />
            <Button type="submit" variant="primary" disabled={rename.isPending || name.trim().length === 0}>Save</Button>
            <Button type="button" onClick={() => { setRenaming(false); setName(saved.name) }}>Cancel</Button>
          </form>
        ) : (
          <>
            <p className="truncate font-medium text-ink">{saved.name}</p>
            <p className="truncate text-xs text-ink-dim">{summarizeSearch(saved.search_parameters as SavedSearchParameters)}</p>
          </>
        )}
      </div>
      {!renaming ? (
        <div className="flex shrink-0 items-center gap-2">
          <Button variant="primary" onClick={apply}>Apply</Button>
          <Button onClick={() => setRenaming(true)}>Rename</Button>
          {confirmDelete ? (
            <Button
              className="text-danger"
              disabled={remove.isPending}
              onClick={() => remove.mutate(saved.id)}
              onBlur={() => setConfirmDelete(false)}
            >
              Confirm delete?
            </Button>
          ) : (
            <Button className="text-danger" onClick={() => setConfirmDelete(true)}>Delete</Button>
          )}
        </div>
      ) : null}
    </li>
  )
}
```

Note on `parseContractSearch(saved.search_parameters …)`: the stored blob is re-validated on the way back out (design §5) — `parseContractSearch` accepts arbitrary input and always returns a well-formed `ContractSearch`, so a drifted blob can never break navigation.

- [ ] **Step 5: Add the accessibility (axe) test.** Design §6 binds a `vitest-axe` pass on each new page. Mirror the house pattern (`src/features/contracts/components/a11y.test.tsx`) — create `app/frontend/web/src/features/saved-searches/components/SavedSearchesPage.a11y.test.tsx`. COMPLETE file:

```tsx
// ABOUTME: Automated axe accessibility checks for the saved-searches page — authed-with-data and anonymous states.
// ABOUTME: Mirrors src/features/contracts/components/a11y.test.tsx (vitest-axe on the designed UI, design §6).
import { afterEach, describe, expect, it, vi } from 'vitest'
import { screen } from '@testing-library/react'
import { axe } from 'vitest-axe'
import * as matchers from 'vitest-axe/matchers'
import { jsonResponse } from '../../../test/http'
import { renderApp } from '../../../test/renderApp'

expect.extend(matchers)

const AUTHED = { character_id: 91000001, character_name: 'Sesta Hound' }
const SAVED = [
  { id: 1, name: 'Cheap frigates', search_parameters: { ships_only: true, min_price: 0, max_price: 5000000, size: 50, sort_by: 'price', sort_direction: 'asc' }, created_at: '2026-07-17T00:00:00Z', updated_at: '2026-07-17T00:00:00Z' },
]

function stubFetch(handler: (url: string) => Response) {
  vi.stubGlobal('fetch', async (input: RequestInfo | URL) => {
    const url = typeof input === 'string' ? input : input instanceof URL ? input.toString() : input.url
    return handler(url)
  })
}

afterEach(() => vi.unstubAllGlobals())

describe('accessibility (axe) — saved searches', () => {
  it('authed list view has no violations', async () => {
    stubFetch((url) => {
      if (/\/api\/v1\/me$/.test(url)) return jsonResponse(AUTHED)
      if (/\/me\/notifications\//.test(url)) return jsonResponse({ total: 0, page: 1, size: 1, items: [] })
      if (/\/me\/saved-searches\//.test(url)) return jsonResponse(SAVED)
      return jsonResponse([])
    })
    const { container } = renderApp('/saved-searches')
    await screen.findByText('Cheap frigates')
    expect(await axe(container)).toHaveNoViolations()
  })

  it('anonymous sign-in prompt has no violations', async () => {
    stubFetch((url) => (/\/api\/v1\/me$/.test(url) ? jsonResponse({ detail: 'unauthenticated' }, 401) : jsonResponse([])))
    const { container } = renderApp('/saved-searches')
    await screen.findByRole('heading', { name: /sign in to use saved searches/i })
    expect(await axe(container)).toHaveNoViolations()
  })
})
```

- [ ] **Step 6: Run green.** `cd app/frontend/web && npx vitest run src/features/saved-searches/components/SavedSearchesPage.test.tsx src/features/saved-searches/components/SavedSearchesPage.a11y.test.tsx --reporter=dot` (pass). `routeTree.gen.ts` regenerates automatically when Vite/the test harness picks up the new route file; if the route is not found, run `npx vite build --mode development` once to force tree regeneration, or start `npm run dev` briefly — do NOT hand-edit `routeTree.gen.ts`. Then `npx tsc -b` and `npx eslint src/routes/saved-searches.tsx src/features/saved-searches` (green).

- [ ] **Step 7: Commit.**
  `git add app/frontend/web/src/routes/saved-searches.tsx app/frontend/web/src/routeTree.gen.ts app/frontend/web/src/features/saved-searches/components/SavedSearchesPage.tsx app/frontend/web/src/features/saved-searches/components/SavedSearchesPage.test.tsx app/frontend/web/src/features/saved-searches/components/SavedSearchesPage.a11y.test.tsx`
  ```
  feat(web): add saved-searches manage page with apply/rename/delete

  Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>
  ```

```
BEFORE marking this task complete:
1. Review tests against docs/pitfalls/testing-pitfalls.md
2. Verify test coverage (error paths? edge cases?)
3. Run tests and confirm green
```

```
After completing this phase:
Review the batch from multiple perspectives (correctness, pitfalls compliance, test coverage).
Minimum 3 review rounds. If round 3 still finds issues, keep going until clean.
```

Push at the phase boundary: `git push -u origin claude/m3-account-features` (first push of the frontend work; subsequent phases just `git push`).

---

## Phase 7 — Frontend F006: Watchlists

**Execution Status:** ⬜ NOT STARTED

Delivers: the watchlist query + add/update/remove mutations with fetch-seam tests; the quick-watch button on contract-detail ship rows; and the `/watchlist` page with the add-by-name form and inline-editable rows (clear-to-null).

### Task 7.1: `useWatchlist` hooks (list + add/update/remove) with fetch-seam tests

```
BEFORE starting work:
1. Invoke superpowers:test-driven-development
2. Read docs/pitfalls/testing-pitfalls.md
Follow TDD: write failing test → implement → verify green.
```

**Files:**
- Create: `app/frontend/web/src/features/watchlists/hooks/useWatchlist.ts`
- Test: `app/frontend/web/src/features/watchlists/hooks/useWatchlist.test.tsx`

- [ ] **Step 1: Write the failing hook tests.** Same seam discipline as 6.1: assert URL/method/body and invalidation. The critical extra assertion for F006 is the **clear-to-null PUT body** (`{ max_price: null }` must serialize as JSON `null`, not be dropped). COMPLETE file:

```tsx
// ABOUTME: useWatchlist hook contracts — list query + add/update/remove mutations at the fetch seam.
// ABOUTME: Asserts URL/method/body incl. the clear-to-null PUT ({max_price: null}); only 2xx invalidates ['watchlists']; 401 also invalidates ['auth','me'].
import { afterEach, describe, expect, it, vi } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { useWatchlist, useAddWatchlistItem, useUpdateWatchlistItem, useRemoveWatchlistItem } from './useWatchlist'

interface Call { url: string; method?: string; body?: string }
function stubFetch(handler: (call: Call) => Response): Call[] {
  const calls: Call[] = []
  vi.stubGlobal('fetch', async (input: RequestInfo | URL, init?: RequestInit) => {
    const req = input as Request
    const call: Call = { url: req.url ?? String(input), method: req.method ?? init?.method, body: await req.clone().text() }
    calls.push(call)
    return handler(call)
  })
  return calls
}
function wrap() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const spy = vi.spyOn(qc, 'invalidateQueries')
  const wrapper = ({ children }: { children: React.ReactNode }) => <QueryClientProvider client={qc}>{children}</QueryClientProvider>
  return { spy, wrapper }
}
afterEach(() => vi.unstubAllGlobals())

describe('useWatchlist (query)', () => {
  it('GETs /api/v1/me/watchlist-items/ and returns the array', async () => {
    const rows = [{ id: 1, type_id: 587, type_name: 'Rifter', max_price: null, notes: null, created_at: 'x', updated_at: 'x' }]
    const calls = stubFetch(() => new Response(JSON.stringify(rows), { status: 200, headers: { 'Content-Type': 'application/json' } }))
    const { wrapper } = wrap()
    const { result } = renderHook(() => useWatchlist(), { wrapper })
    await waitFor(() => expect(result.current.data).toHaveLength(1))
    expect(calls[0].url).toContain('/api/v1/me/watchlist-items/')
  })

  it('invalidates ["auth","me"] when the query 401s', async () => {
    const { spy, wrapper } = wrap()
    stubFetch(() => new Response(JSON.stringify({ detail: 'unauth' }), { status: 401, headers: { 'Content-Type': 'application/json' } }))
    const { result } = renderHook(() => useWatchlist(), { wrapper })
    await waitFor(() => expect(result.current.isError).toBe(true))
    expect(spy).toHaveBeenCalledWith({ queryKey: ['auth', 'me'] })
  })
})

describe('useAddWatchlistItem', () => {
  it('POSTs the body and invalidates on 201', async () => {
    const calls = stubFetch(() => new Response(JSON.stringify({ id: 2, type_id: 587, type_name: 'Rifter', max_price: null, notes: null, created_at: 'x', updated_at: 'x' }), { status: 201, headers: { 'Content-Type': 'application/json' } }))
    const { spy, wrapper } = wrap()
    const { result } = renderHook(() => useAddWatchlistItem(), { wrapper })
    result.current.mutate({ type_id: 587 })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(calls[0].url).toContain('/api/v1/me/watchlist-items/')
    expect(calls[0].method).toBe('POST')
    expect(JSON.parse(calls[0].body!)).toEqual({ type_id: 587 })
    expect(spy).toHaveBeenCalledWith({ queryKey: ['watchlists'] })
  })

  it('surfaces a 409 without invalidating', async () => {
    const { spy, wrapper } = wrap()
    stubFetch(() => new Response(JSON.stringify({ detail: 'dup' }), { status: 409, headers: { 'Content-Type': 'application/json' } }))
    const { result } = renderHook(() => useAddWatchlistItem(), { wrapper })
    result.current.mutate({ type_name: 'Rifter' })
    await waitFor(() => expect(result.current.isError).toBe(true))
    expect(spy).not.toHaveBeenCalledWith({ queryKey: ['watchlists'] })
  })

  it('invalidates ["auth","me"] on a 401', async () => {
    const { spy, wrapper } = wrap()
    stubFetch(() => new Response(JSON.stringify({ detail: 'unauth' }), { status: 401, headers: { 'Content-Type': 'application/json' } }))
    const { result } = renderHook(() => useAddWatchlistItem(), { wrapper })
    result.current.mutate({ type_id: 1 })
    await waitFor(() => expect(result.current.isError).toBe(true))
    expect(spy).toHaveBeenCalledWith({ queryKey: ['auth', 'me'] })
  })
})

describe('useUpdateWatchlistItem', () => {
  it('PUTs {max_price: null} to clear (JSON null, not dropped)', async () => {
    const calls = stubFetch(() => new Response(JSON.stringify({ id: 3, type_id: 1, type_name: 'x', max_price: null, notes: 'keep', created_at: 'x', updated_at: 'x' }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
    const { spy, wrapper } = wrap()
    const { result } = renderHook(() => useUpdateWatchlistItem(), { wrapper })
    result.current.mutate({ id: 3, body: { max_price: null, notes: 'keep' } })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(calls[0].url).toContain('/api/v1/me/watchlist-items/3')
    expect(calls[0].method).toBe('PUT')
    const parsed = JSON.parse(calls[0].body!)
    expect(parsed).toHaveProperty('max_price', null)
    expect(parsed.notes).toBe('keep')
    expect(spy).toHaveBeenCalledWith({ queryKey: ['watchlists'] })
  })
})

describe('useRemoveWatchlistItem', () => {
  it('DELETEs the item route and invalidates on 204', async () => {
    const calls = stubFetch(() => new Response(null, { status: 204 }))
    const { spy, wrapper } = wrap()
    const { result } = renderHook(() => useRemoveWatchlistItem(), { wrapper })
    result.current.mutate(4)
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(calls[0].url).toContain('/api/v1/me/watchlist-items/4')
    expect(calls[0].method).toBe('DELETE')
    expect(spy).toHaveBeenCalledWith({ queryKey: ['watchlists'] })
  })
})
```

- [ ] **Step 2: Run, confirm failure.** `cd app/frontend/web && npx vitest run src/features/watchlists/hooks/useWatchlist.test.tsx --reporter=dot`. Expected: `Failed to resolve import "./useWatchlist"`.

- [ ] **Step 3: Implement `useWatchlist.ts`.** The clear-to-null contract depends on the caller passing an explicit `null` (a JS `null` serializes to JSON `null`; `undefined` would be dropped) — the update mutation forwards the body verbatim, and the WatchlistPage row (Task 7.3) is what maps an emptied input to `null`. COMPLETE file:

```ts
// ABOUTME: TanStack Query hooks for F006 watchlists — list query + add/update/remove mutations.
// ABOUTME: update forwards the body verbatim so an explicit {max_price: null} clears (JSON null); every hook routes non-2xx through raiseApiError (['watchlists'] on 2xx, ['auth','me'] on 401).
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api, raiseApiError, type WatchlistItem } from '../../../lib/api/client'
import type { components } from '../../../lib/api/schema'

type WatchlistItemCreate = components['schemas']['WatchlistItemCreate']
type WatchlistItemUpdate = components['schemas']['WatchlistItemUpdate']

export function useWatchlist() {
  const queryClient = useQueryClient()
  return useQuery<WatchlistItem[]>({
    queryKey: ['watchlists', 'list'],
    queryFn: async () => {
      const { data, response } = await api.GET('/me/watchlist-items/')
      if (data === undefined) raiseApiError(queryClient, response.status)
      return data
    },
  })
}

export function useAddWatchlistItem() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (body: WatchlistItemCreate) => {
      const { data, response } = await api.POST('/me/watchlist-items/', { body })
      if (!response.ok) raiseApiError(queryClient, response.status)
      return data
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['watchlists'] }),
  })
}

export function useUpdateWatchlistItem() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async ({ id, body }: { id: number; body: WatchlistItemUpdate }) => {
      const { data, response } = await api.PUT('/me/watchlist-items/{item_id}', {
        params: { path: { item_id: id } },
        body,
      })
      if (!response.ok) raiseApiError(queryClient, response.status)
      return data
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['watchlists'] }),
  })
}

export function useRemoveWatchlistItem() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (id: number) => {
      const { response } = await api.DELETE('/me/watchlist-items/{item_id}', {
        params: { path: { item_id: id } },
      })
      if (!response.ok) raiseApiError(queryClient, response.status)
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['watchlists'] }),
  })
}
```

- [ ] **Step 4: Run green.** `cd app/frontend/web && npx vitest run src/features/watchlists/hooks/useWatchlist.test.tsx --reporter=dot` (pass), then `npx tsc -b` and `npx eslint src/features/watchlists` (green).

- [ ] **Step 5: Commit.**
  `git add app/frontend/web/src/features/watchlists/hooks/useWatchlist.ts app/frontend/web/src/features/watchlists/hooks/useWatchlist.test.tsx`
  ```
  feat(web): add watchlist CRUD query hooks

  Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>
  ```

```
BEFORE marking this task complete:
1. Review tests against docs/pitfalls/testing-pitfalls.md
2. Verify test coverage (error paths? edge cases?)
3. Run tests and confirm green
```

### Task 7.2: `WatchButton` on contract-detail ship rows + tests

```
BEFORE starting work:
1. Invoke superpowers:test-driven-development
2. Read docs/pitfalls/testing-pitfalls.md
Follow TDD: write failing test → implement → verify green.
```

**Files:**
- Create: `app/frontend/web/src/features/watchlists/components/WatchButton.tsx`
- Modify: `app/frontend/web/src/features/contracts/components/ContractDetailPage.tsx` (item `<li>`, lines 179–194)
- Test: `app/frontend/web/src/features/watchlists/components/WatchButton.test.tsx`

- [ ] **Step 1: Write the failing test.** Drives the detail page via `renderApp('/contracts/101')` with a ship-bearing contract; asserts: anonymous → no Watch button; authed → Watch button on the ship row; click → POST `{type_id}`; 409 → "already watching" inline. COMPLETE file:

```tsx
// ABOUTME: WatchButton over the real contract-detail route — authed-only, one-click add by type_id, 409 "already watching".
import { afterEach, describe, expect, it, vi } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { anonymousMe, jsonResponse } from '../../../test/http'
import { renderApp } from '../../../test/renderApp'

const AUTHED = { character_id: 91000001, character_name: 'Sesta Hound' }
const CONTRACT = {
  contract_id: 101, issuer_id: 1, issuer_corporation_id: 101, start_location_id: 60003760,
  type: 'item_exchange', status: 'unknown', title: 'Rifter for sale', for_corporation: false,
  date_issued: '2026-07-01T00:00:00Z', date_expired: '2030-07-08T00:00:00Z', date_completed: null,
  price: 1000000, reward: 0, volume: 27, start_location_name: 'Jita IV - Moon 4', issuer_name: 'Sesta Hound',
  issuer_corporation_name: 'COB', is_ship_contract: true,
  items: [{ record_id: 1011, type_id: 587, quantity: 1, is_included: true, is_singleton: false, is_blueprint_copy: false, raw_quantity: null, type_name: 'Rifter', category: 'ship', market_group_id: 61 }],
}

interface Call { url: string; method?: string; body?: string }
function stubFetch(handler: (url: string, call: Call) => Response): Call[] {
  const calls: Call[] = []
  vi.stubGlobal('fetch', async (input: RequestInfo | URL, init?: RequestInit) => {
    const req = input as Request
    const url = req.url ?? String(input)
    const call: Call = { url, method: req.method ?? init?.method, body: await req.clone().text() }
    calls.push(call)
    return handler(url, call)
  })
  return calls
}
afterEach(() => vi.unstubAllGlobals())

describe('WatchButton', () => {
  it('is hidden for anonymous users', async () => {
    stubFetch(anonymousMe(() => jsonResponse(CONTRACT)))
    renderApp('/contracts/101')
    await screen.findByRole('heading', { level: 1, name: 'Rifter' })
    expect(screen.queryByRole('button', { name: /^watch$/i })).not.toBeInTheDocument()
  })

  it('adds by type_id on click for an authed user', async () => {
    const calls = stubFetch((url) => {
      if (/\/api\/v1\/me$/.test(url)) return jsonResponse(AUTHED)
      if (/\/me\/watchlist-items\//.test(url)) return jsonResponse({ id: 1, type_id: 587, type_name: 'Rifter', max_price: null, notes: null, created_at: 'x', updated_at: 'x' }, 201)
      return jsonResponse(CONTRACT)
    })
    renderApp('/contracts/101')
    await userEvent.click(await screen.findByRole('button', { name: /^watch$/i }))
    await waitFor(() => expect(calls.some((c) => /\/me\/watchlist-items\//.test(c.url) && c.method === 'POST')).toBe(true))
    const post = calls.find((c) => /\/me\/watchlist-items\//.test(c.url) && c.method === 'POST')!
    expect(JSON.parse(post.body!)).toEqual({ type_id: 587 })
    expect(await screen.findByText(/watching/i)).toBeInTheDocument()
  })

  it('shows "already watching" on a 409', async () => {
    stubFetch((url) => {
      if (/\/api\/v1\/me$/.test(url)) return jsonResponse(AUTHED)
      if (/\/me\/watchlist-items\//.test(url)) return jsonResponse({ detail: 'dup' }, 409)
      return jsonResponse(CONTRACT)
    })
    renderApp('/contracts/101')
    await userEvent.click(await screen.findByRole('button', { name: /^watch$/i }))
    expect(await screen.findByText(/already watching/i)).toBeInTheDocument()
  })
})
```

- [ ] **Step 2: Run, confirm failure.** `cd app/frontend/web && npx vitest run src/features/watchlists/components/WatchButton.test.tsx --reporter=dot`. Expected: no Watch button (component not wired into the detail page).

- [ ] **Step 3: Implement `WatchButton.tsx`.** COMPLETE file:

```tsx
// ABOUTME: Quick-watch button for a listed ship on the contract-detail page — authed-only, one-click add by type_id, no price field.
// ABOUTME: 409 renders "Already watching" inline; success renders "Watching" (display-tier feedback, no toast primitive exists).
import { Button } from '../../../components/Button'
import { ApiError } from '../../../lib/api/client'
import { useCurrentUser } from '../../auth/hooks/useCurrentUser'
import { useAddWatchlistItem } from '../hooks/useWatchlist'

export function WatchButton({ typeId }: { typeId: number }) {
  const { data: user } = useCurrentUser()
  const add = useAddWatchlistItem()

  if (!user) return null
  if (add.isSuccess) return <span className="text-xs text-ok">Watching</span>
  if (add.error instanceof ApiError && add.error.status === 409) {
    return <span className="text-xs text-ink-dim">Already watching</span>
  }
  return (
    <Button variant="ghost" disabled={add.isPending} onClick={() => add.mutate({ type_id: typeId })}>
      Watch
    </Button>
  )
}
```

- [ ] **Step 4: Wire `WatchButton` into ContractDetailPage.** Add `import { WatchButton } from '../../watchlists/components/WatchButton'` with the other imports, and inside the item `<li>` (after the existing badge/`asked for, not included` spans, still inside the `<li>`, ContractDetailPage.tsx ~line 192) add — gated on `category === 'ship'` and inclusion:

```tsx
                {item.is_included && item.category === 'ship' ? (
                  <span className="ml-auto">
                    <WatchButton typeId={item.type_id} />
                  </span>
                ) : null}
```

`ml-auto` right-aligns the button within the flex row. `WatchButton` itself returns `null` when anonymous, so existing detail tests (which use `anonymousMe`) are unaffected.

- [ ] **Step 5: Run green.** `cd app/frontend/web && npx vitest run src/features/watchlists/components/WatchButton.test.tsx --reporter=dot` (pass); then regression-check the detail suite: `npx vitest run src/features/contracts/components/pages.test.tsx src/features/contracts/components/a11y.test.tsx --reporter=dot` (pass). Then `npx tsc -b` and `npx eslint src/features/watchlists src/features/contracts/components/ContractDetailPage.tsx` (green).

- [ ] **Step 6: Commit.**
  `git add app/frontend/web/src/features/watchlists/components/WatchButton.tsx app/frontend/web/src/features/watchlists/components/WatchButton.test.tsx app/frontend/web/src/features/contracts/components/ContractDetailPage.tsx`
  ```
  feat(web): add quick-watch button to contract detail ship rows

  Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>
  ```

```
BEFORE marking this task complete:
1. Review tests against docs/pitfalls/testing-pitfalls.md
2. Verify test coverage (error paths? edge cases?)
3. Run tests and confirm green
```

### Task 7.3: `/watchlist` route + `WatchlistPage` (add-by-name form, inline-editable rows, clear-to-null, two-step Remove) + tests

```
BEFORE starting work:
1. Invoke superpowers:test-driven-development
2. Read docs/pitfalls/testing-pitfalls.md
Follow TDD: write failing test → implement → verify green.
```

**Files:**
- Create: `app/frontend/web/src/routes/watchlist.tsx`
- Create: `app/frontend/web/src/features/watchlists/components/WatchlistPage.tsx`
- Test: `app/frontend/web/src/features/watchlists/components/WatchlistPage.test.tsx`
- Test: `app/frontend/web/src/features/watchlists/components/WatchlistPage.a11y.test.tsx` (vitest-axe, design §6)

- [ ] **Step 1: Write the failing page tests.** Cover: anonymous prompt; list render after skeleton unmount (TEST-8); empty state; add-by-name form posting `{type_name, max_price?, notes?}`; 400 unknown-name inline error; clear-to-null PUT body assertion; the max-price 0-boundary guard; two-step Remove (incl. the 5s timeout reset). Every authed stub answers the header bell's unread-count query (`GET /me/notifications/?is_read=false&size=1`) with `{ total: 0, page: 1, size: 1, items: [] }` — a bare `[]` would leave that count query erroring once Task 8.2 mounts the bell (NIT-9). COMPLETE file:

```tsx
// ABOUTME: WatchlistPage tests over the real /watchlist route — auth branches, add-by-name form, clear-to-null edit, two-step remove.
// ABOUTME: Asserts add-form and clear-to-null PUT wire payloads (TEST-5); TEST-8 skeleton-unmount sync before list assertions.
import { afterEach, describe, expect, it, vi } from 'vitest'
import { act, screen, waitFor, waitForElementToBeRemoved } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { jsonResponse } from '../../../test/http'
import { renderApp } from '../../../test/renderApp'

const AUTHED = { character_id: 91000001, character_name: 'Sesta Hound' }
const ROWS = [{ id: 1, type_id: 587, type_name: 'Rifter', max_price: 5000000, notes: 'cheap', created_at: 'x', updated_at: 'x' }]

interface Call { url: string; method?: string; body?: string }
function stubFetch(handler: (url: string, call: Call) => Response): Call[] {
  const calls: Call[] = []
  vi.stubGlobal('fetch', async (input: RequestInfo | URL, init?: RequestInit) => {
    const req = input as Request
    const url = req.url ?? String(input)
    const call: Call = { url, method: req.method ?? init?.method, body: await req.clone().text() }
    calls.push(call)
    return handler(url, call)
  })
  return calls
}
afterEach(() => vi.unstubAllGlobals())

describe('WatchlistPage', () => {
  it('prompts anonymous users to sign in', async () => {
    stubFetch((url) => (/\/api\/v1\/me$/.test(url) ? jsonResponse({ detail: 'unauth' }, 401) : jsonResponse([])))
    renderApp('/watchlist')
    expect(await screen.findByRole('heading', { name: /sign in to use your watchlist/i })).toBeInTheDocument()
  })

  it('lists rows after the skeleton unmounts (TEST-8)', async () => {
    stubFetch((url) => {
      if (/\/api\/v1\/me$/.test(url)) return jsonResponse(AUTHED)
      if (/\/me\/notifications\//.test(url)) return jsonResponse({ total: 0, page: 1, size: 1, items: [] })
      if (/\/me\/watchlist-items\//.test(url)) return jsonResponse(ROWS)
      return jsonResponse([])
    })
    renderApp('/watchlist')
    const skeleton = await screen.findByRole('status', { name: /loading watchlist/i })
    await waitForElementToBeRemoved(skeleton)
    expect(screen.getByText('Rifter')).toBeInTheDocument()
  })

  it('adds by name with the optional price + notes payload', async () => {
    const calls = stubFetch((url) => {
      if (/\/api\/v1\/me$/.test(url)) return jsonResponse(AUTHED)
      if (/\/me\/notifications\//.test(url)) return jsonResponse({ total: 0, page: 1, size: 1, items: [] })
      if (/\/me\/watchlist-items\//.test(url)) return jsonResponse({ id: 2, type_id: 24694, type_name: 'Maelstrom', max_price: 300000000, notes: 'flagship', created_at: 'x', updated_at: 'x' }, 201)
      return jsonResponse([])
    })
    renderApp('/watchlist')
    await screen.findByRole('heading', { level: 1, name: /watchlist/i })
    await userEvent.type(screen.getByLabelText(/ship name/i), 'Maelstrom')
    await userEvent.type(screen.getByLabelText(/max price/i), '300000000')
    await userEvent.type(screen.getByLabelText(/notes/i), 'flagship')
    await userEvent.click(screen.getByRole('button', { name: /add to watchlist/i }))
    await waitFor(() => expect(calls.some((c) => /\/me\/watchlist-items\//.test(c.url) && c.method === 'POST')).toBe(true))
    const post = calls.find((c) => /\/me\/watchlist-items\//.test(c.url) && c.method === 'POST')!
    expect(JSON.parse(post.body!)).toEqual({ type_name: 'Maelstrom', max_price: 300000000, notes: 'flagship' })
  })

  it('shows an inline error when the name is unknown (400)', async () => {
    stubFetch((url) => {
      if (/\/api\/v1\/me$/.test(url)) return jsonResponse(AUTHED)
      if (/\/me\/notifications\//.test(url)) return jsonResponse({ total: 0, page: 1, size: 1, items: [] })
      if (/\/me\/watchlist-items\//.test(url)) return jsonResponse({ detail: 'unknown ship name' }, 400)
      return jsonResponse([])
    })
    renderApp('/watchlist')
    await screen.findByRole('heading', { level: 1, name: /watchlist/i })
    await userEvent.type(screen.getByLabelText(/ship name/i), 'Rlfter')
    await userEvent.click(screen.getByRole('button', { name: /add to watchlist/i }))
    expect(await screen.findByText(/couldn.t find a ship/i)).toBeInTheDocument()
  })

  it('clears max_price to null via the clear affordance (PUT body is JSON null)', async () => {
    const calls = stubFetch((url) => {
      if (/\/api\/v1\/me$/.test(url)) return jsonResponse(AUTHED)
      if (/\/me\/notifications\//.test(url)) return jsonResponse({ total: 0, page: 1, size: 1, items: [] })
      if (/\/me\/watchlist-items\/1/.test(url)) return jsonResponse({ ...ROWS[0], max_price: null })
      if (/\/me\/watchlist-items\//.test(url)) return jsonResponse(ROWS)
      return jsonResponse([])
    })
    renderApp('/watchlist')
    await screen.findByText('Rifter')
    await userEvent.click(screen.getByRole('button', { name: /clear max price/i }))
    await waitFor(() => expect(calls.some((c) => /\/me\/watchlist-items\/1/.test(c.url) && c.method === 'PUT')).toBe(true))
    const put = calls.find((c) => /\/me\/watchlist-items\/1/.test(c.url) && c.method === 'PUT')!
    expect(JSON.parse(put.body!)).toHaveProperty('max_price', null)
  })

  it('requires a second click to remove (two-step)', async () => {
    const calls = stubFetch((url) => {
      if (/\/api\/v1\/me$/.test(url)) return jsonResponse(AUTHED)
      if (/\/me\/notifications\//.test(url)) return jsonResponse({ total: 0, page: 1, size: 1, items: [] })
      if (/\/me\/watchlist-items\/1/.test(url)) return new Response(null, { status: 204 })
      if (/\/me\/watchlist-items\//.test(url)) return jsonResponse(ROWS)
      return jsonResponse([])
    })
    renderApp('/watchlist')
    await screen.findByText('Rifter')
    await userEvent.click(screen.getByRole('button', { name: /^remove$/i }))
    expect(calls.some((c) => c.method === 'DELETE')).toBe(false)
    await userEvent.click(screen.getByRole('button', { name: /confirm remove/i }))
    await waitFor(() => expect(calls.some((c) => /\/me\/watchlist-items\/1/.test(c.url) && c.method === 'DELETE')).toBe(true))
  })

  it('rejects an entered max price of 0 with an inline message and does not POST', async () => {
    const calls = stubFetch((url) => {
      if (/\/api\/v1\/me$/.test(url)) return jsonResponse(AUTHED)
      if (/\/me\/notifications\//.test(url)) return jsonResponse({ total: 0, page: 1, size: 1, items: [] })
      if (/\/me\/watchlist-items\//.test(url)) return jsonResponse([])
      return jsonResponse([])
    })
    renderApp('/watchlist')
    await screen.findByRole('heading', { level: 1, name: /watchlist/i })
    await userEvent.type(screen.getByLabelText(/ship name/i), 'Rifter')
    await userEvent.type(screen.getByLabelText(/max price/i), '0')
    await userEvent.click(screen.getByRole('button', { name: /add to watchlist/i }))
    expect(await screen.findByText(/max price must be at least 0\.01/i)).toBeInTheDocument()
    expect(calls.some((c) => /\/me\/watchlist-items\//.test(c.url) && c.method === 'POST')).toBe(false)
  })

  it('auto-disarms the two-step remove after 5s (timeout reset)', async () => {
    stubFetch((url) => {
      if (/\/api\/v1\/me$/.test(url)) return jsonResponse(AUTHED)
      if (/\/me\/notifications\//.test(url)) return jsonResponse({ total: 0, page: 1, size: 1, items: [] })
      if (/\/me\/watchlist-items\//.test(url)) return jsonResponse(ROWS)
      return jsonResponse([])
    })
    renderApp('/watchlist')
    await screen.findByText('Rifter')
    // Fake timers AFTER the initial load so the arming click schedules the 5s timeout on the fake
    // clock; userEvent advances the fake clock for its own internal timing.
    vi.useFakeTimers()
    try {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime })
      await user.click(screen.getByRole('button', { name: /^remove$/i }))
      expect(screen.getByRole('button', { name: /confirm remove/i })).toBeInTheDocument()
      act(() => { vi.advanceTimersByTime(5000) })
      expect(screen.queryByRole('button', { name: /confirm remove/i })).not.toBeInTheDocument()
    } finally {
      vi.useRealTimers()
    }
  })
})
```

- [ ] **Step 2: Run, confirm failure.** `cd app/frontend/web && npx vitest run src/features/watchlists/components/WatchlistPage.test.tsx --reporter=dot`. Expected: route missing → sign-in heading not found.

- [ ] **Step 3: Create `src/routes/watchlist.tsx`.** COMPLETE file:

```tsx
import { createFileRoute } from '@tanstack/react-router'
import { WatchlistPage } from '../features/watchlists/components/WatchlistPage'

export const Route = createFileRoute('/watchlist')({
  component: RouteComponent,
})

function RouteComponent() {
  return <WatchlistPage />
}
```

- [ ] **Step 4: Implement `WatchlistPage.tsx`.** The add form maps an empty max-price/notes input to an omitted key; each row's inline edit and "Clear max price" affordance map an emptied field to explicit `null` (clear). COMPLETE file:

```tsx
// ABOUTME: F006 watchlist page — add-by-name form (name + optional max price/notes) and inline-editable rows with clear-to-null and two-step remove.
// ABOUTME: Empty max-price/notes on ADD is omitted (create); an emptied field on EDIT sends explicit null (clear) per the backend PUT semantics.
import { useEffect, useState } from 'react'
import { Button } from '../../../components/Button'
import { Input } from '../../../components/Input'
import { ApiError, type WatchlistItem } from '../../../lib/api/client'
import { useDocumentTitle } from '../../../lib/useDocumentTitle'
import { RequireSignIn } from '../../auth/components/RequireSignIn'
import { useCurrentUser } from '../../auth/hooks/useCurrentUser'
import { formatIsk } from '../../contracts/format'
import { useAddWatchlistItem, useRemoveWatchlistItem, useUpdateWatchlistItem, useWatchlist } from '../hooks/useWatchlist'

export function WatchlistPage() {
  useDocumentTitle('Watchlist')
  const { data: user, isPending } = useCurrentUser()

  if (isPending) {
    return (
      <div role="status" aria-label="Loading account" className="mx-auto max-w-3xl">
        <span className="skeleton block h-7 w-48" />
        <span className="sr-only">Loading…</span>
      </div>
    )
  }
  if (!user) return <RequireSignIn feature="your watchlist" />
  return <WatchlistBody />
}

function WatchlistBody() {
  const { data, isPending, isError } = useWatchlist()
  return (
    <div className="mx-auto max-w-3xl">
      <p className="sr-only" role="status" aria-live="polite" />
      <h1 className="text-h1 mb-4 font-semibold">Watchlist</h1>
      <AddByNameForm />
      {isPending ? (
        <div role="status" aria-label="Loading watchlist" className="mt-4">
          <span className="skeleton block h-16 w-full" />
          <span className="sr-only">Loading watchlist…</span>
        </div>
      ) : isError ? (
        <div role="alert" className="mt-4 rounded-md border border-danger/40 bg-danger-wash px-4 py-4 text-sm text-ink">
          Couldn’t load your watchlist. Reload the page to try again.
        </div>
      ) : data.length === 0 ? (
        <div className="mt-4 rounded-md border border-line bg-surface px-5 py-8">
          <h2 className="text-base font-medium text-ink">Your watchlist is empty</h2>
          <p className="mt-1 max-w-[52ch] text-sm text-ink-dim">
            Add a ship by name above, or use the “Watch” button on any contract that lists one.
          </p>
        </div>
      ) : (
        <ul className="mt-4 flex flex-col gap-2">
          {data.map((item) => (
            <WatchlistRow key={item.id} item={item} />
          ))}
        </ul>
      )}
    </div>
  )
}

function AddByNameForm() {
  const add = useAddWatchlistItem()
  const [name, setName] = useState('')
  const [maxPrice, setMaxPrice] = useState('')
  const [notes, setNotes] = useState('')
  const [priceError, setPriceError] = useState('')

  const submit = (event: React.FormEvent) => {
    event.preventDefault()
    const typeName = name.trim()
    if (typeName.length === 0) return
    const price = maxPrice.trim()
    const note = notes.trim()
    // The backend requires max_price >= 0.01; guard 0 (and anything below) here and show an inline
    // message instead of POSTing a value we know will 422.
    if (price !== '' && Number(price) < 0.01) {
      setPriceError('Max price must be at least 0.01 ISK, or leave it blank for any price.')
      return
    }
    setPriceError('')
    add.mutate(
      {
        type_name: typeName,
        ...(price !== '' ? { max_price: Number(price) } : {}),
        ...(note !== '' ? { notes: note } : {}),
      },
      {
        onSuccess: () => {
          setName('')
          setMaxPrice('')
          setNotes('')
        },
      },
    )
  }

  const status = add.error instanceof ApiError ? add.error.status : undefined
  const message =
    status === 400 ? 'Couldn’t find a ship with that exact name. Check the spelling.'
    : status === 409 ? 'You’re already watching that ship.'
    : status === 502 ? 'EVE’s type service is unavailable right now. Try again shortly.'
    : add.isError ? 'Couldn’t add that ship. Try again.'
    : undefined

  return (
    <form onSubmit={submit} aria-label="Add a ship to your watchlist" className="flex flex-wrap items-end gap-3 rounded-md border border-line bg-surface p-4">
      <div className="flex min-w-[12rem] flex-1 flex-col gap-1">
        <label htmlFor="watch-name" className="text-label">Ship name</label>
        <Input id="watch-name" value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Maelstrom" />
      </div>
      <div className="flex w-40 flex-col gap-1">
        <label htmlFor="watch-price" className="text-label">Max price (ISK)</label>
        <Input
          id="watch-price"
          type="number"
          min="0.01"
          step="0.01"
          value={maxPrice}
          onChange={(e) => { setMaxPrice(e.target.value); if (priceError) setPriceError('') }}
          placeholder="optional"
          aria-invalid={priceError ? true : undefined}
          aria-describedby={priceError ? 'watch-price-error' : undefined}
        />
      </div>
      <div className="flex min-w-[10rem] flex-1 flex-col gap-1">
        <label htmlFor="watch-notes" className="text-label">Notes</label>
        <Input id="watch-notes" value={notes} onChange={(e) => setNotes(e.target.value)} placeholder="optional" />
      </div>
      <Button type="submit" variant="primary" disabled={add.isPending || name.trim().length === 0}>
        Add to watchlist
      </Button>
      {priceError ? (
        <p id="watch-price-error" role="alert" aria-live="polite" className="w-full text-xs text-danger">{priceError}</p>
      ) : message ? (
        <p role="alert" aria-live="polite" className="w-full text-xs text-danger">{message}</p>
      ) : null}
    </form>
  )
}

function WatchlistRow({ item }: { item: WatchlistItem }) {
  const update = useUpdateWatchlistItem()
  const remove = useRemoveWatchlistItem()
  const [maxPrice, setMaxPrice] = useState(item.max_price != null ? String(item.max_price) : '')
  const [notes, setNotes] = useState(item.notes ?? '')
  const [confirmRemove, setConfirmRemove] = useState(false)

  // Auto-disarm the two-step remove after 5s so a stray first click can't leave the row armed
  // indefinitely (blur also disarms; this covers the focus-retained case). Cleared on unmount/re-arm.
  useEffect(() => {
    if (!confirmRemove) return
    const timer = setTimeout(() => setConfirmRemove(false), 5000)
    return () => clearTimeout(timer)
  }, [confirmRemove])

  // Empty input → explicit null (clear); a value → the number/string. Both fields are
  // always sent, so the backend's omit-preserves path is never relied on from the UI.
  const save = () =>
    update.mutate({
      id: item.id,
      body: {
        max_price: maxPrice.trim() === '' ? null : Number(maxPrice),
        notes: notes.trim() === '' ? null : notes.trim(),
      },
    })

  const clearMaxPrice = () => {
    setMaxPrice('')
    update.mutate({ id: item.id, body: { max_price: null } })
  }

  return (
    <li className="flex flex-wrap items-center gap-3 rounded-md border border-line bg-surface px-4 py-3">
      <img
        src={`https://images.evetech.net/types/${item.type_id}/render?size=64`}
        alt=""
        width={32}
        height={32}
        className="h-8 w-8 rounded-sm"
      />
      <span className="min-w-0 flex-1 truncate font-medium text-ink">{item.type_name}</span>
      <div className="flex items-center gap-1">
        <label htmlFor={`price-${item.id}`} className="sr-only">Max price for {item.type_name}</label>
        <Input
          id={`price-${item.id}`}
          type="number"
          min="0.01"
          step="0.01"
          className="w-32 text-data"
          value={maxPrice}
          onChange={(e) => setMaxPrice(e.target.value)}
          placeholder={item.max_price != null ? formatIsk(item.max_price) : 'any price'}
        />
        <Button type="button" onClick={clearMaxPrice} aria-label={`Clear max price for ${item.type_name}`}>Clear</Button>
      </div>
      <div className="flex items-center gap-1">
        <label htmlFor={`notes-${item.id}`} className="sr-only">Notes for {item.type_name}</label>
        <Input id={`notes-${item.id}`} className="w-40" value={notes} onChange={(e) => setNotes(e.target.value)} placeholder="notes" />
      </div>
      <Button type="button" variant="primary" onClick={save} disabled={update.isPending}>Save</Button>
      {confirmRemove ? (
        <Button type="button" className="text-danger" disabled={remove.isPending} onClick={() => remove.mutate(item.id)} onBlur={() => setConfirmRemove(false)}>
          Confirm remove?
        </Button>
      ) : (
        <Button type="button" className="text-danger" onClick={() => setConfirmRemove(true)}>Remove</Button>
      )}
    </li>
  )
}
```

- [ ] **Step 5: Add the accessibility (axe) test.** Design §6 binds a `vitest-axe` pass on each new page. Mirror the house pattern (`src/features/contracts/components/a11y.test.tsx`) — create `app/frontend/web/src/features/watchlists/components/WatchlistPage.a11y.test.tsx`. COMPLETE file:

```tsx
// ABOUTME: Automated axe accessibility checks for the watchlist page — authed-with-data and anonymous states.
// ABOUTME: Mirrors src/features/contracts/components/a11y.test.tsx (vitest-axe on the designed UI, design §6).
import { afterEach, describe, expect, it, vi } from 'vitest'
import { screen } from '@testing-library/react'
import { axe } from 'vitest-axe'
import * as matchers from 'vitest-axe/matchers'
import { jsonResponse } from '../../../test/http'
import { renderApp } from '../../../test/renderApp'

expect.extend(matchers)

const AUTHED = { character_id: 91000001, character_name: 'Sesta Hound' }
const ROWS = [{ id: 1, type_id: 587, type_name: 'Rifter', max_price: 5000000, notes: 'cheap', created_at: 'x', updated_at: 'x' }]

function stubFetch(handler: (url: string) => Response) {
  vi.stubGlobal('fetch', async (input: RequestInfo | URL) => {
    const url = typeof input === 'string' ? input : input instanceof URL ? input.toString() : input.url
    return handler(url)
  })
}

afterEach(() => vi.unstubAllGlobals())

describe('accessibility (axe) — watchlist', () => {
  it('authed list view has no violations', async () => {
    stubFetch((url) => {
      if (/\/api\/v1\/me$/.test(url)) return jsonResponse(AUTHED)
      if (/\/me\/notifications\//.test(url)) return jsonResponse({ total: 0, page: 1, size: 1, items: [] })
      if (/\/me\/watchlist-items\//.test(url)) return jsonResponse(ROWS)
      return jsonResponse([])
    })
    const { container } = renderApp('/watchlist')
    await screen.findByText('Rifter')
    expect(await axe(container)).toHaveNoViolations()
  })

  it('anonymous sign-in prompt has no violations', async () => {
    stubFetch((url) => (/\/api\/v1\/me$/.test(url) ? jsonResponse({ detail: 'unauth' }, 401) : jsonResponse([])))
    const { container } = renderApp('/watchlist')
    await screen.findByRole('heading', { name: /sign in to use your watchlist/i })
    expect(await axe(container)).toHaveNoViolations()
  })
})
```

- [ ] **Step 6: Run green.** `cd app/frontend/web && npx vitest run src/features/watchlists/components/WatchlistPage.test.tsx src/features/watchlists/components/WatchlistPage.a11y.test.tsx --reporter=dot` (pass; force route-tree regen as in Task 6.4 if the route isn't found). Then `npx tsc -b` and `npx eslint src/routes/watchlist.tsx src/features/watchlists` (green).

- [ ] **Step 7: Commit.**
  `git add app/frontend/web/src/routes/watchlist.tsx app/frontend/web/src/routeTree.gen.ts app/frontend/web/src/features/watchlists/components/WatchlistPage.tsx app/frontend/web/src/features/watchlists/components/WatchlistPage.test.tsx app/frontend/web/src/features/watchlists/components/WatchlistPage.a11y.test.tsx`
  ```
  feat(web): add watchlist page with add-by-name and inline editing

  Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>
  ```

```
BEFORE marking this task complete:
1. Review tests against docs/pitfalls/testing-pitfalls.md
2. Verify test coverage (error paths? edge cases?)
3. Run tests and confirm green
```

```
After completing this phase:
Review the batch from multiple perspectives (correctness, pitfalls compliance, test coverage).
Minimum 3 review rounds. If round 3 still finds issues, keep going until clean.
```

Push: `git push`.

---

## Phase 8 — Frontend F007: Alerts / Notifications

**Execution Status:** ⬜ NOT STARTED

Delivers: the notifications hooks (list, unread-count with a testable queryOptions factory, mark-read/all, settings); the header bell inside `HeaderIdentity`; and the `/notifications` page with pagination, mark-read-on-click, mark-all-read, and the settings checkbox.

### Task 8.1: `useNotifications` hooks (list, unread-count, mark-read/all, settings) + tests

```
BEFORE starting work:
1. Invoke superpowers:test-driven-development
2. Read docs/pitfalls/testing-pitfalls.md
Follow TDD: write failing test → implement → verify green.
```

**Files:**
- Create: `app/frontend/web/src/features/notifications/hooks/useNotifications.ts`
- Test: `app/frontend/web/src/features/notifications/hooks/useNotifications.test.tsx`

- [ ] **Step 1: Write the failing tests.** Per the brief: fake timers are NOT required — assert the queryOptions object fields directly (the `unreadCountQueryOptions` factory carries `refetchInterval: 60_000` and `enabled`), drive its `queryFn` to assert the count URL (`is_read=false&size=1`) and that it returns `total`; the list hook asserts its URL/params; mutations assert URL/method + invalidation; the list error path uses a persistent failure (TEST-7). COMPLETE file:

```tsx
// ABOUTME: useNotifications hook contracts — list, unread-count queryOptions factory, mark-read/all, settings.
// ABOUTME: Asserts count queryOptions fields (refetchInterval/enabled) directly + the count URL; mutations assert URL/method/invalidation (TEST-5).
import { afterEach, describe, expect, it, vi } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import {
  useNotifications,
  unreadCountQueryOptions,
  useMarkRead,
  useMarkAllRead,
  useNotificationSettings,
  useUpdateNotificationSettings,
} from './useNotifications'

interface Call { url: string; method?: string; body?: string }
function stubFetch(handler: (call: Call) => Response): Call[] {
  const calls: Call[] = []
  vi.stubGlobal('fetch', async (input: RequestInfo | URL, init?: RequestInit) => {
    const req = input as Request
    const call: Call = { url: req.url ?? String(input), method: req.method ?? init?.method, body: await req.clone().text() }
    calls.push(call)
    return handler(call)
  })
  return calls
}
function wrap() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const spy = vi.spyOn(qc, 'invalidateQueries')
  const wrapper = ({ children }: { children: React.ReactNode }) => <QueryClientProvider client={qc}>{children}</QueryClientProvider>
  return { spy, wrapper }
}
afterEach(() => vi.unstubAllGlobals())

describe('unreadCountQueryOptions', () => {
  it('carries the polling config and count query key', () => {
    const qc = new QueryClient()
    const opts = unreadCountQueryOptions(qc, true)
    expect(opts.queryKey).toEqual(['notifications', 'unreadCount'])
    expect(opts.refetchInterval).toBe(60_000)
    expect(opts.enabled).toBe(true)
    expect(unreadCountQueryOptions(qc, false).enabled).toBe(false)
  })

  it('queryFn hits the size=1 unread endpoint and returns total', async () => {
    const qc = new QueryClient()
    const calls = stubFetch(() => new Response(JSON.stringify({ total: 5, page: 1, size: 1, items: [] }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
    const opts = unreadCountQueryOptions(qc, true)
    const total = await (opts.queryFn as () => Promise<number>)()
    expect(total).toBe(5)
    expect(calls[0].url).toContain('/api/v1/me/notifications/')
    expect(calls[0].url).toContain('is_read=false')
    expect(calls[0].url).toContain('size=1')
  })

  it('invalidates ["auth","me"] when the count poll 401s', async () => {
    const qc = new QueryClient()
    const spy = vi.spyOn(qc, 'invalidateQueries')
    stubFetch(() => new Response(JSON.stringify({ detail: 'unauth' }), { status: 401, headers: { 'Content-Type': 'application/json' } }))
    const opts = unreadCountQueryOptions(qc, true)
    await expect((opts.queryFn as () => Promise<number>)()).rejects.toThrow()
    expect(spy).toHaveBeenCalledWith({ queryKey: ['auth', 'me'] })
  })
})

describe('useNotifications (list)', () => {
  it('GETs the list with page/size params', async () => {
    const calls = stubFetch(() => new Response(JSON.stringify({ total: 0, page: 2, size: 20, items: [] }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
    const { wrapper } = wrap()
    const { result } = renderHook(() => useNotifications({ page: 2, size: 20 }), { wrapper })
    await waitFor(() => expect(result.current.data).toBeDefined())
    expect(calls[0].url).toContain('/api/v1/me/notifications/')
    expect(calls[0].url).toContain('page=2')
    expect(calls[0].url).toContain('size=20')
  })

  it('surfaces an error after a persistent failure (TEST-7)', async () => {
    stubFetch(() => new Response(JSON.stringify({ detail: 'boom' }), { status: 500, headers: { 'Content-Type': 'application/json' } }))
    const { wrapper } = wrap()
    const { result } = renderHook(() => useNotifications({ page: 1, size: 20 }), { wrapper })
    await waitFor(() => expect(result.current.isError).toBe(true))
  })

  it('invalidates ["auth","me"] when the list 401s', async () => {
    const { spy, wrapper } = wrap()
    stubFetch(() => new Response(JSON.stringify({ detail: 'unauth' }), { status: 401, headers: { 'Content-Type': 'application/json' } }))
    const { result } = renderHook(() => useNotifications({ page: 1, size: 20 }), { wrapper })
    await waitFor(() => expect(result.current.isError).toBe(true))
    expect(spy).toHaveBeenCalledWith({ queryKey: ['auth', 'me'] })
  })
})

describe('useMarkRead / useMarkAllRead', () => {
  it('marks one read and invalidates ["notifications"]', async () => {
    const calls = stubFetch(() => new Response(null, { status: 204 }))
    const { spy, wrapper } = wrap()
    const { result } = renderHook(() => useMarkRead(), { wrapper })
    result.current.mutate(7)
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(calls[0].url).toContain('/api/v1/me/notifications/7/mark-read')
    expect(calls[0].method).toBe('POST')
    expect(spy).toHaveBeenCalledWith({ queryKey: ['notifications'] })
  })

  it('marks all read', async () => {
    const calls = stubFetch(() => new Response(null, { status: 204 }))
    const { spy, wrapper } = wrap()
    const { result } = renderHook(() => useMarkAllRead(), { wrapper })
    result.current.mutate()
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(calls[0].url).toContain('/api/v1/me/notifications/mark-all-read')
    expect(calls[0].method).toBe('POST')
    expect(spy).toHaveBeenCalledWith({ queryKey: ['notifications'] })
  })

  it('invalidates ["auth","me"] when mark-read 401s', async () => {
    const { spy, wrapper } = wrap()
    stubFetch(() => new Response(JSON.stringify({ detail: 'unauth' }), { status: 401, headers: { 'Content-Type': 'application/json' } }))
    const { result } = renderHook(() => useMarkRead(), { wrapper })
    result.current.mutate(7)
    await waitFor(() => expect(result.current.isError).toBe(true))
    expect(spy).toHaveBeenCalledWith({ queryKey: ['auth', 'me'] })
  })
})

describe('notification settings', () => {
  it('GETs the settings', async () => {
    const calls = stubFetch(() => new Response(JSON.stringify({ watchlist_alerts_enabled: true }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
    const { wrapper } = wrap()
    const { result } = renderHook(() => useNotificationSettings(), { wrapper })
    await waitFor(() => expect(result.current.data).toEqual({ watchlist_alerts_enabled: true }))
    expect(calls[0].url).toContain('/api/v1/me/notification-settings')
  })

  it('invalidates ["auth","me"] when the settings GET 401s', async () => {
    const { spy, wrapper } = wrap()
    stubFetch(() => new Response(JSON.stringify({ detail: 'unauth' }), { status: 401, headers: { 'Content-Type': 'application/json' } }))
    const { result } = renderHook(() => useNotificationSettings(), { wrapper })
    await waitFor(() => expect(result.current.isError).toBe(true))
    expect(spy).toHaveBeenCalledWith({ queryKey: ['auth', 'me'] })
  })

  it('PUTs the settings body and invalidates the settings key', async () => {
    const calls = stubFetch(() => new Response(JSON.stringify({ watchlist_alerts_enabled: false }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
    const { spy, wrapper } = wrap()
    const { result } = renderHook(() => useUpdateNotificationSettings(), { wrapper })
    result.current.mutate({ watchlist_alerts_enabled: false })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(calls[0].method).toBe('PUT')
    expect(JSON.parse(calls[0].body!)).toEqual({ watchlist_alerts_enabled: false })
    expect(spy).toHaveBeenCalledWith({ queryKey: ['notifications', 'settings'] })
  })
})
```

- [ ] **Step 2: Run, confirm failure.** `cd app/frontend/web && npx vitest run src/features/notifications/hooks/useNotifications.test.tsx --reporter=dot`. Expected: `Failed to resolve import "./useNotifications"`.

- [ ] **Step 3: Implement `useNotifications.ts`.** `unreadCountQueryOptions` is a standalone factory (independently testable) that now takes the caller's `queryClient` so its poll routes 401s through `raiseApiError` like every other query; `useUnreadCount` supplies that `queryClient` and calls `useCurrentUser` to derive `enabled`. COMPLETE file:

```ts
// ABOUTME: TanStack Query hooks for F007 notifications — paginated list, unread-count poll, mark-read/all, settings.
// ABOUTME: unreadCountQueryOptions is a standalone factory (testable without a component); every hook routes non-2xx through raiseApiError (['auth','me'] on 401).
import { QueryClient, queryOptions, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api, raiseApiError, type NotificationSettings, type PaginatedNotifications } from '../../../lib/api/client'
import { useCurrentUser } from '../../auth/hooks/useCurrentUser'

export function useNotifications(params: { page: number; size: number; is_read?: boolean }) {
  const queryClient = useQueryClient()
  return useQuery<PaginatedNotifications>({
    queryKey: ['notifications', 'list', params],
    queryFn: async () => {
      const { data, response } = await api.GET('/me/notifications/', { params: { query: params } })
      if (data === undefined) raiseApiError(queryClient, response.status)
      return data
    },
  })
}

// The unread badge reads `total` off a filtered size=1 page — no dedicated count
// endpoint (design §3.4). Polls every 60s; only enabled when authed. Takes the caller's
// queryClient so a 401 poll invalidates ['auth','me'] like every other /me/* query.
export function unreadCountQueryOptions(queryClient: QueryClient, enabled: boolean) {
  return queryOptions({
    queryKey: ['notifications', 'unreadCount'],
    enabled,
    refetchInterval: 60_000,
    queryFn: async () => {
      const { data, response } = await api.GET('/me/notifications/', {
        params: { query: { is_read: false, size: 1 } },
      })
      if (data === undefined) raiseApiError(queryClient, response.status)
      return data.total
    },
  })
}

export function useUnreadCount() {
  const queryClient = useQueryClient()
  const { data: user } = useCurrentUser()
  return useQuery(unreadCountQueryOptions(queryClient, !!user))
}

export function useMarkRead() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (id: number) => {
      const { response } = await api.POST('/me/notifications/{notification_id}/mark-read', {
        params: { path: { notification_id: id } },
      })
      if (!response.ok) raiseApiError(queryClient, response.status)
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['notifications'] }),
  })
}

export function useMarkAllRead() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async () => {
      const { response } = await api.POST('/me/notifications/mark-all-read')
      if (!response.ok) raiseApiError(queryClient, response.status)
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['notifications'] }),
  })
}

export function useNotificationSettings() {
  const queryClient = useQueryClient()
  return useQuery<NotificationSettings>({
    queryKey: ['notifications', 'settings'],
    queryFn: async () => {
      const { data, response } = await api.GET('/me/notification-settings')
      if (data === undefined) raiseApiError(queryClient, response.status)
      return data
    },
  })
}

export function useUpdateNotificationSettings() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (body: NotificationSettings) => {
      const { data, response } = await api.PUT('/me/notification-settings', { body })
      if (!response.ok) raiseApiError(queryClient, response.status)
      return data
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['notifications', 'settings'] }),
  })
}
```

- [ ] **Step 4: Run green.** `cd app/frontend/web && npx vitest run src/features/notifications/hooks/useNotifications.test.tsx --reporter=dot` (pass), then `npx tsc -b` and `npx eslint src/features/notifications` (green).

- [ ] **Step 5: Commit.**
  `git add app/frontend/web/src/features/notifications/hooks/useNotifications.ts app/frontend/web/src/features/notifications/hooks/useNotifications.test.tsx`
  ```
  feat(web): add notifications query and mutation hooks

  Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>
  ```

```
BEFORE marking this task complete:
1. Review tests against docs/pitfalls/testing-pitfalls.md
2. Verify test coverage (error paths? edge cases?)
3. Run tests and confirm green
```

### Task 8.2: `NotificationBell` inside `HeaderIdentity` + tests (and hermetic-lane fix for existing auth specs)

```
BEFORE starting work:
1. Invoke superpowers:test-driven-development
2. Read docs/pitfalls/testing-pitfalls.md
Follow TDD: write failing test → implement → verify green.
```

**Files:**
- Create: `app/frontend/web/src/features/notifications/components/NotificationBell.tsx`
- Modify: `app/frontend/web/src/features/auth/components/HeaderIdentity.tsx` (authenticated branch, lines 32–46)
- Test: `app/frontend/web/src/features/notifications/components/NotificationBell.test.tsx`
- Modify: `app/frontend/web/e2e/helpers/api.ts` (add `AccountCall`, `readBody`, and the shared `interceptNotifications` helper — this task is its first consumer)
- Modify: `app/frontend/web/e2e/auth.spec.ts` (the two authenticated tests — keep the lane hermetic)

- [ ] **Step 1: Write the failing test.** Drives the bell through `renderApp('/contracts')` with authed `/me` and a stubbed count endpoint; asserts the `Link` to `/notifications` with `aria-label` "Notifications (N unread)", the badge shows N when N>0, and no badge number when N=0. COMPLETE file:

```tsx
// ABOUTME: NotificationBell over the real header — Link to /notifications with an unread badge; badge hidden at zero.
// ABOUTME: aria-label announces the unread count; zero-count renders the link but no numeric badge.
import { afterEach, describe, expect, it, vi } from 'vitest'
import { screen } from '@testing-library/react'
import { jsonResponse } from '../../../test/http'
import { renderApp } from '../../../test/renderApp'

const AUTHED = { character_id: 91000001, character_name: 'Sesta Hound' }

function stubFetch(unreadTotal: number) {
  vi.stubGlobal('fetch', async (input: RequestInfo | URL) => {
    const url = typeof input === 'string' ? input : (input as Request).url
    if (/\/api\/v1\/me$/.test(url)) return jsonResponse(AUTHED)
    if (/\/me\/notifications\//.test(url)) return jsonResponse({ total: unreadTotal, page: 1, size: 1, items: [] })
    return jsonResponse({ total: 0, page: 1, size: 50, items: [] })
  })
}
afterEach(() => vi.unstubAllGlobals())

describe('NotificationBell', () => {
  it('links to /notifications and shows the unread count in the accessible name and badge', async () => {
    stubFetch(3)
    renderApp('/contracts')
    const bell = await screen.findByRole('link', { name: /notifications \(3 unread\)/i })
    expect(bell).toHaveAttribute('href', '/notifications')
    expect(bell).toHaveTextContent('3')
  })

  it('renders no numeric badge when there are zero unread', async () => {
    stubFetch(0)
    renderApp('/contracts')
    const bell = await screen.findByRole('link', { name: /notifications \(0 unread\)/i })
    expect(bell).not.toHaveTextContent('0')
  })
})
```

- [ ] **Step 2: Run, confirm failure.** `cd app/frontend/web && npx vitest run src/features/notifications/components/NotificationBell.test.tsx --reporter=dot`. Expected: no Notifications link (bell not in the header yet).

- [ ] **Step 3: Implement `NotificationBell.tsx`.** COMPLETE file:

```tsx
// ABOUTME: Header notification bell — a Link to /notifications with an unread-count badge; the badge is hidden at zero.
// ABOUTME: The unread count comes from useUnreadCount (60s poll, authed-only); the accessible name always announces the count.
import { Link } from '@tanstack/react-router'
import { useUnreadCount } from '../hooks/useNotifications'

export function NotificationBell() {
  const { data } = useUnreadCount()
  const count = data ?? 0
  return (
    <Link
      to="/notifications"
      aria-label={`Notifications (${count} unread)`}
      className="relative inline-flex h-8 w-8 items-center justify-center rounded-md text-ink-body hover:bg-raised"
    >
      <svg viewBox="0 0 20 20" width={18} height={18} fill="currentColor" aria-hidden="true">
        <path d="M10 2a5 5 0 0 0-5 5v3l-1.5 2.5A.5.5 0 0 0 4 15h12a.5.5 0 0 0 .4-.8L15 12V7a5 5 0 0 0-5-5Zm0 16a2.5 2.5 0 0 0 2.45-2h-4.9A2.5 2.5 0 0 0 10 18Z" />
      </svg>
      {count > 0 ? (
        <span className="absolute -top-1 -right-1 inline-flex min-w-4 items-center justify-center rounded-full border border-brand-dim bg-brand-wash px-1 font-mono text-micro text-brand">
          {count}
        </span>
      ) : null}
    </Link>
  )
}
```

- [ ] **Step 4: Wire `NotificationBell` into `HeaderIdentity`.** Add `import { NotificationBell } from '../../notifications/components/NotificationBell'`, and in the authenticated-branch return (HeaderIdentity.tsx line 32–46) place the bell first inside the cluster:

```tsx
  return (
    <div className="ml-auto flex items-center gap-3">
      <NotificationBell />
      <img
        src={`https://images.evetech.net/characters/${user.character_id}/portrait?size=64`}
        alt=""
        width={24}
        height={24}
        className="h-6 w-6 rounded-full"
      />
      <span className="text-ink text-sm">{user.character_name}</span>
      <Button variant="ghost" onClick={() => logout.mutate()} disabled={logout.isPending}>
        Log out
      </Button>
    </div>
  )
```

The bell renders only in this authed branch, so anonymous headers are unchanged; `useUnreadCount`'s `enabled: !!user` means no count request fires when anonymous. The existing `HeaderIdentity.test.tsx` authed tests have a fallback handler returning `{total:0,…}`, so the count query resolves to 0 (no badge) and those tests keep passing with no change.

- [ ] **Step 5: Add the shared `interceptNotifications` E2E helper (first consumer) and keep the auth lane hermetic.** The header now fires `GET /me/notifications/?is_read=false&size=1` on every authed render, so the two authenticated tests in `e2e/auth.spec.ts` ("authenticated header shows portrait…" and "logout POSTs exactly once…") would leak an un-intercepted request (TEST-9 discipline). This task is the first consumer of the notifications intercept, so define it here (Phase 9 Task 9.1 reuses it verbatim and its `AccountCall`/`readBody` scaffolding). Append to `e2e/helpers/api.ts` after the existing helpers (`Page` is already imported at the top):

```ts
export interface AccountCall {
  url: URL
  method: string
  body: unknown
}

function readBody(route: import('@playwright/test').Route): unknown {
  try {
    return route.request().postDataJSON()
  } catch {
    return undefined
  }
}

/** Intercept /me/notifications/* and /me/notification-settings. The count query (is_read=false&size=1)
 * returns { total: unread, items: [] }; the list query returns the page; mark-read/all return 204;
 * settings GET returns `settings`, PUT captures + echoes. Shared by the header bell's auth specs and
 * the notifications spec (Task 9.4). */
export async function interceptNotifications(
  page: Page,
  opts: { items?: ReadonlyArray<{ is_read: boolean }>; unread?: number; settings?: { watchlist_alerts_enabled: boolean } } = {},
): Promise<AccountCall[]> {
  const calls: AccountCall[] = []
  const items = opts.items ?? []
  const unread = opts.unread ?? items.filter((n) => !n.is_read).length
  let settings = opts.settings ?? { watchlist_alerts_enabled: true }
  await page.route(/\/api\/v1\/me\/notification-settings/, async (route) => {
    const req = route.request()
    const method = req.method()
    if (method === 'PUT') {
      const body = readBody(route) as { watchlist_alerts_enabled: boolean }
      settings = body
      calls.push({ url: new URL(req.url()), method, body })
      return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(settings) })
    }
    calls.push({ url: new URL(req.url()), method, body: undefined })
    return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(settings) })
  })
  await page.route(/\/api\/v1\/me\/notifications/, async (route) => {
    const req = route.request()
    const method = req.method()
    const url = new URL(req.url())
    calls.push({ url, method, body: method === 'POST' ? readBody(route) : undefined })
    if (/\/mark-all-read$/.test(url.pathname) || /\/mark-read$/.test(url.pathname)) {
      return route.fulfill({ status: 204, body: '' })
    }
    if (url.searchParams.get('is_read') === 'false' && url.searchParams.get('size') === '1') {
      return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ total: unread, page: 1, size: 1, items: [] }) })
    }
    const pageNum = Number(url.searchParams.get('page') ?? '1')
    const size = Number(url.searchParams.get('size') ?? '20')
    return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ total: items.length, page: pageNum, size, items }) })
  })
  return calls
}
```

Note: the two routes are registered settings-first then notifications — Playwright runs last-registered-first, so `/me/notifications` (registered last) is evaluated first; its pattern does NOT match `/me/notification-settings` (different literal), so each request lands on the right handler. Then wire it into `e2e/auth.spec.ts`: add `interceptNotifications` to the `./helpers/api` import and call `await interceptNotifications(page, { unread: 0 })` (before `page.goto`) in both authenticated tests.

- [ ] **Step 6: Run green.** `cd app/frontend/web && npx vitest run src/features/notifications/components/NotificationBell.test.tsx src/features/auth/components/HeaderIdentity.test.tsx --reporter=dot` (all pass). `npx tsc -b` and `npx eslint src/features/notifications src/features/auth/components/HeaderIdentity.tsx e2e/helpers/api.ts` (green). Fixture-lane smoke for the touched spec: `npx playwright test auth.spec.ts --project=desktop` (green).

- [ ] **Step 7: Commit.**
  `git add app/frontend/web/src/features/notifications/components/NotificationBell.tsx app/frontend/web/src/features/notifications/components/NotificationBell.test.tsx app/frontend/web/src/features/auth/components/HeaderIdentity.tsx app/frontend/web/e2e/helpers/api.ts app/frontend/web/e2e/auth.spec.ts`
  ```
  feat(web): add notification bell to the header identity cluster

  Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>
  ```

```
BEFORE marking this task complete:
1. Review tests against docs/pitfalls/testing-pitfalls.md
2. Verify test coverage (error paths? edge cases?)
3. Run tests and confirm green
```

### Task 8.3: `/notifications` route + `NotificationsPage` (paginated list, mark-read-on-click, mark-all-read, settings) + tests

```
BEFORE starting work:
1. Invoke superpowers:test-driven-development
2. Read docs/pitfalls/testing-pitfalls.md
Follow TDD: write failing test → implement → verify green.
```

**Files:**
- Create: `app/frontend/web/src/features/notifications/format.ts` (relative-time helper)
- Create: `app/frontend/web/src/routes/notifications.tsx`
- Create: `app/frontend/web/src/features/notifications/components/NotificationsPage.tsx`
- Modify: `app/frontend/web/src/features/contracts/components/Pagination.tsx` (add an optional `unitLabel` so the pager reads "notifications", not "contracts")
- Modify: `app/frontend/web/src/components/Checkbox.tsx` (add an optional `disabled` prop — backward-safe)
- Test: `app/frontend/web/src/features/notifications/format.test.ts`
- Test: `app/frontend/web/src/features/notifications/components/NotificationsPage.test.tsx`
- Test: `app/frontend/web/src/features/notifications/components/NotificationsPage.a11y.test.tsx` (vitest-axe, design §6)

- [ ] **Step 1: Write the failing `format.ts` test.** COMPLETE file:

```ts
// ABOUTME: timeAgo formats a past ISO timestamp as a coarse relative span; now is injectable for determinism (TEST-3).
import { describe, expect, it } from 'vitest'
import { timeAgo } from './format'

describe('timeAgo', () => {
  const now = Date.parse('2026-07-17T12:00:00Z')
  it('returns "just now" under a minute', () => {
    expect(timeAgo('2026-07-17T11:59:30Z', now)).toBe('just now')
  })
  it('returns minutes, hours, and days', () => {
    expect(timeAgo('2026-07-17T11:30:00Z', now)).toBe('30m ago')
    expect(timeAgo('2026-07-17T09:00:00Z', now)).toBe('3h ago')
    expect(timeAgo('2026-07-14T12:00:00Z', now)).toBe('3d ago')
  })
  it('returns em dash for an unparseable input', () => {
    expect(timeAgo('not-a-date', now)).toBe('—')
  })
})
```

- [ ] **Step 2: Run, confirm failure.** `cd app/frontend/web && npx vitest run src/features/notifications/format.test.ts --reporter=dot`. Expected: `Failed to resolve import "./format"`.

- [ ] **Step 3: Implement `format.ts`.** COMPLETE file:

```ts
// ABOUTME: Relative-time formatting for notification timestamps ("3h ago"); now is injectable for deterministic tests.
// ABOUTME: Coarse by design — minutes, hours, then days — mirroring the list view's timeRemaining granularity.
export function timeAgo(iso: string, now: number = Date.now()): string {
  const ms = now - new Date(iso).getTime()
  if (Number.isNaN(ms)) return '—'
  const minutes = Math.floor(ms / 60_000)
  if (minutes < 1) return 'just now'
  if (minutes < 60) return `${minutes}m ago`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours}h ago`
  const days = Math.floor(hours / 24)
  return `${days}d ago`
}
```

- [ ] **Step 4: Run `format.test.ts` green.** `cd app/frontend/web && npx vitest run src/features/notifications/format.test.ts --reporter=dot` (pass).

- [ ] **Step 5: Add the optional `unitLabel` to `Pagination.tsx`.** Small backward-safe extension (default keeps `contracts`, so existing call sites and the contracts pagination E2E are unaffected). Replace the component signature + label line:

```tsx
export function Pagination({
  page,
  size,
  total,
  onPage,
  unitLabel = 'contracts',
}: {
  page: number
  size: number
  total: number
  onPage: (page: number) => void
  unitLabel?: string
}) {
```

and the label span:

```tsx
      <span className="text-data text-ink-dim">
        Page {page} of {pageCount} · {total.toLocaleString('en-US')} {unitLabel}
      </span>
```

Also extend the shared `CheckboxField` (`src/components/Checkbox.tsx`) with an optional `disabled` prop (backward-safe default `false`) so the settings toggle can lock while its query is pending — add `disabled = false` to the destructured props and its type, and pass `disabled={disabled}` to the `<input>`:

```tsx
export function CheckboxField({
  label,
  checked,
  onChange,
  disabled = false,
}: {
  label: ReactNode
  checked: boolean
  onChange: (checked: boolean) => void
  disabled?: boolean
}) {
  return (
    <label className="flex cursor-pointer items-center gap-2 rounded-sm py-0.5 text-sm text-ink-body select-none hover:text-ink">
      <input
        type="checkbox"
        className="size-4 shrink-0 cursor-pointer accent-(--color-brand)"
        checked={checked}
        disabled={disabled}
        onChange={(event) => onChange(event.target.checked)}
      />
      {label}
    </label>
  )
}
```

- [ ] **Step 6: Write the failing NotificationsPage tests.** Cover: anonymous prompt; authed list after skeleton unmount (TEST-8); mark-read fires on row click; pagination wiring (page 2 requested); mark-all-read POST; settings checkbox PUT body; contract deep-link present. COMPLETE file:

```tsx
// ABOUTME: NotificationsPage tests over the real /notifications route — auth branches, mark-read on click, pagination, mark-all-read, settings toggle.
// ABOUTME: Asserts mark-read/mark-all-read/settings wire calls (TEST-5); TEST-8 skeleton-unmount sync before list assertions.
import { afterEach, describe, expect, it, vi } from 'vitest'
import { screen, waitFor, waitForElementToBeRemoved } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { jsonResponse } from '../../../test/http'
import { renderApp } from '../../../test/renderApp'

const AUTHED = { character_id: 91000001, character_name: 'Sesta Hound' }
const N = (over: Record<string, unknown> = {}) => ({
  id: 1, type: 'watchlist_match', message: 'Rifter available in an auction priced 900,000 ISK in Jita IV - Moon 4',
  contract_id: 101, watch_type_id: 587, price: 900000, is_read: false, created_at: '2026-07-17T11:00:00Z', ...over,
})

interface Call { url: string; method?: string; body?: string }
function stubFetch(handler: (url: string, call: Call) => Response): Call[] {
  const calls: Call[] = []
  vi.stubGlobal('fetch', async (input: RequestInfo | URL, init?: RequestInit) => {
    const req = input as Request
    const url = req.url ?? String(input)
    const call: Call = { url, method: req.method ?? init?.method, body: await req.clone().text() }
    calls.push(call)
    return handler(url, call)
  })
  return calls
}
// Route notifications endpoints; the list vs count vs settings vs mark endpoints share a prefix.
function notificationsHandler(unread: typeof N extends never ? never : ReturnType<typeof N>[], settings = { watchlist_alerts_enabled: true }) {
  return (url: string): Response | null => {
    if (/\/me\/notification-settings/.test(url)) return jsonResponse(settings)
    if (/\/me\/notifications\/mark-all-read/.test(url)) return new Response(null, { status: 204 })
    if (/\/me\/notifications\/\d+\/mark-read/.test(url)) return new Response(null, { status: 204 })
    if (/is_read=false&size=1/.test(url) || /size=1&is_read=false/.test(url)) return jsonResponse({ total: unread.length, page: 1, size: 1, items: [] })
    if (/\/me\/notifications\//.test(url)) {
      const u = new URL(url)
      const page = Number(u.searchParams.get('page') ?? '1')
      return jsonResponse({ total: unread.length, page, size: 20, items: unread })
    }
    return null
  }
}
afterEach(() => vi.unstubAllGlobals())

describe('NotificationsPage', () => {
  it('prompts anonymous users to sign in', async () => {
    stubFetch((url) => (/\/api\/v1\/me$/.test(url) ? jsonResponse({ detail: 'unauth' }, 401) : jsonResponse({ total: 0, page: 1, size: 20, items: [] })))
    renderApp('/notifications')
    expect(await screen.findByRole('heading', { name: /sign in to use notifications/i })).toBeInTheDocument()
  })

  it('lists notifications after the skeleton unmounts and links to the contract', async () => {
    const handle = notificationsHandler([N()])
    stubFetch((url) => (/\/api\/v1\/me$/.test(url) ? jsonResponse(AUTHED) : (handle(url) ?? jsonResponse({}, 404))))
    renderApp('/notifications')
    const skeleton = await screen.findByRole('status', { name: /loading notifications/i })
    await waitForElementToBeRemoved(skeleton)
    expect(screen.getByText(/rifter available/i)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /rifter available/i })).toHaveAttribute('href', '/contracts/101')
  })

  it('marks a notification read on click', async () => {
    const handle = notificationsHandler([N()])
    const calls = stubFetch((url) => (/\/api\/v1\/me$/.test(url) ? jsonResponse(AUTHED) : (handle(url) ?? jsonResponse({}, 404))))
    renderApp('/notifications')
    await screen.findByText(/rifter available/i)
    await userEvent.click(screen.getByRole('link', { name: /rifter available/i }))
    await waitFor(() => expect(calls.some((c) => /\/me\/notifications\/1\/mark-read/.test(c.url) && c.method === 'POST')).toBe(true))
  })

  it('requests page 2 when Next is clicked', async () => {
    const many = Array.from({ length: 25 }, (_, i) => N({ id: i + 1, message: `Alert ${i + 1}`, contract_id: null }))
    const handle = notificationsHandler(many)
    const calls = stubFetch((url) => (/\/api\/v1\/me$/.test(url) ? jsonResponse(AUTHED) : (handle(url) ?? jsonResponse({}, 404))))
    renderApp('/notifications')
    await screen.findByText('Alert 1')
    await userEvent.click(screen.getByRole('button', { name: /next/i }))
    await waitFor(() => expect(calls.some((c) => /\/me\/notifications\//.test(c.url) && /page=2/.test(c.url))).toBe(true))
  })

  it('marks all read', async () => {
    const handle = notificationsHandler([N()])
    const calls = stubFetch((url) => (/\/api\/v1\/me$/.test(url) ? jsonResponse(AUTHED) : (handle(url) ?? jsonResponse({}, 404))))
    renderApp('/notifications')
    await screen.findByText(/rifter available/i)
    await userEvent.click(screen.getByRole('button', { name: /mark all as read/i }))
    await waitFor(() => expect(calls.some((c) => /\/me\/notifications\/mark-all-read/.test(c.url) && c.method === 'POST')).toBe(true))
  })

  it('toggles the watchlist-alerts setting (PUT body)', async () => {
    const handle = notificationsHandler([N()])
    const calls = stubFetch((url) => (/\/api\/v1\/me$/.test(url) ? jsonResponse(AUTHED) : (handle(url) ?? jsonResponse({}, 404))))
    renderApp('/notifications')
    await screen.findByText(/rifter available/i)
    await userEvent.click(await screen.findByLabelText(/watchlist alerts/i))
    await waitFor(() => expect(calls.some((c) => /\/me\/notification-settings/.test(c.url) && c.method === 'PUT')).toBe(true))
    const put = calls.find((c) => /\/me\/notification-settings/.test(c.url) && c.method === 'PUT')!
    expect(JSON.parse(put.body!)).toEqual({ watchlist_alerts_enabled: false })
  })

  it('disables the watchlist-alerts toggle until settings load (no PUT before load)', async () => {
    const calls: Call[] = []
    vi.stubGlobal('fetch', async (input: RequestInfo | URL, init?: RequestInit) => {
      const req = input as Request
      const url = req.url ?? String(input)
      calls.push({ url, method: req.method ?? init?.method, body: await req.clone().text() })
      if (/\/api\/v1\/me$/.test(url)) return jsonResponse(AUTHED)
      // Settings GET never resolves → useNotificationSettings stays isPending → the checkbox is disabled.
      if (/\/me\/notification-settings/.test(url)) return new Promise<Response>(() => {})
      if (/\/me\/notifications\//.test(url)) return jsonResponse({ total: 1, page: 1, size: 20, items: [N()] })
      return jsonResponse({}, 404)
    })
    renderApp('/notifications')
    await screen.findByText(/rifter available/i)
    const toggle = screen.getByLabelText(/watchlist alerts/i)
    expect(toggle).toBeDisabled()
    await userEvent.click(toggle)   // disabled → no interaction, so no settings write
    expect(calls.some((c) => /\/me\/notification-settings/.test(c.url) && c.method === 'PUT')).toBe(false)
  })
})
```

- [ ] **Step 7: Run, confirm failure.** `cd app/frontend/web && npx vitest run src/features/notifications/components/NotificationsPage.test.tsx --reporter=dot`. Expected: route missing → sign-in heading not found.

- [ ] **Step 8: Create `src/routes/notifications.tsx`.** COMPLETE file:

```tsx
import { createFileRoute } from '@tanstack/react-router'
import { NotificationsPage } from '../features/notifications/components/NotificationsPage'

export const Route = createFileRoute('/notifications')({
  component: RouteComponent,
})

function RouteComponent() {
  return <NotificationsPage />
}
```

- [ ] **Step 9: Implement `NotificationsPage.tsx`.** COMPLETE file:

```tsx
// ABOUTME: F007 notifications page — auth-gated paginated list, mark-read-on-click (+deep-link), mark-all-read, and the watchlist-alerts settings checkbox.
// ABOUTME: Unread rows are visually distinct; row activation marks read then (when a contract is present) navigates to it.
import { useState } from 'react'
import { Link } from '@tanstack/react-router'
import { Button } from '../../../components/Button'
import { CheckboxField } from '../../../components/Checkbox'
import type { Notification } from '../../../lib/api/client'
import { useDocumentTitle } from '../../../lib/useDocumentTitle'
import { RequireSignIn } from '../../auth/components/RequireSignIn'
import { useCurrentUser } from '../../auth/hooks/useCurrentUser'
import { Pagination } from '../../contracts/components/Pagination'
import { timeAgo } from '../format'
import {
  useMarkAllRead,
  useMarkRead,
  useNotificationSettings,
  useNotifications,
  useUpdateNotificationSettings,
} from '../hooks/useNotifications'

const PAGE_SIZE = 20

export function NotificationsPage() {
  useDocumentTitle('Notifications')
  const { data: user, isPending } = useCurrentUser()

  if (isPending) {
    return (
      <div role="status" aria-label="Loading account" className="mx-auto max-w-3xl">
        <span className="skeleton block h-7 w-48" />
        <span className="sr-only">Loading…</span>
      </div>
    )
  }
  if (!user) return <RequireSignIn feature="notifications" />
  return <NotificationsBody />
}

function NotificationsBody() {
  const [page, setPage] = useState(1)
  const { data, isPending, isError } = useNotifications({ page, size: PAGE_SIZE })
  const markAll = useMarkAllRead()

  return (
    <div className="mx-auto max-w-3xl">
      <p className="sr-only" role="status" aria-live="polite" />
      <div className="mb-4 flex flex-wrap items-center gap-3">
        <h1 className="text-h1 font-semibold">Notifications</h1>
        <Button className="ml-auto" onClick={() => markAll.mutate()} disabled={markAll.isPending}>
          Mark all as read
        </Button>
      </div>

      <SettingsToggle />

      {isPending ? (
        <div role="status" aria-label="Loading notifications" className="mt-4">
          <span className="skeleton block h-16 w-full" />
          <span className="sr-only">Loading notifications…</span>
        </div>
      ) : isError ? (
        <div role="alert" className="mt-4 rounded-md border border-danger/40 bg-danger-wash px-4 py-4 text-sm text-ink">
          Couldn’t load your notifications. Reload the page to try again.
        </div>
      ) : data.items.length === 0 ? (
        <div className="mt-4 rounded-md border border-line bg-surface px-5 py-8">
          <h2 className="text-base font-medium text-ink">No notifications yet</h2>
          <p className="mt-1 max-w-[52ch] text-sm text-ink-dim">
            When a ship on your watchlist appears in a contract at or below your max price, you’ll see it here.
          </p>
        </div>
      ) : (
        <>
          <ul className="mt-4 flex flex-col gap-2">
            {data.items.map((n) => (
              <NotificationRow key={n.id} n={n} />
            ))}
          </ul>
          <div className="mt-4">
            <Pagination page={page} size={data.size ?? PAGE_SIZE} total={data.total} onPage={setPage} unitLabel="notifications" />
          </div>
        </>
      )}
    </div>
  )
}

function SettingsToggle() {
  const settingsQuery = useNotificationSettings()
  const update = useUpdateNotificationSettings()
  return (
    <div className="rounded-md border border-line bg-surface px-4 py-3">
      <CheckboxField
        label="Watchlist alerts"
        checked={settingsQuery.data?.watchlist_alerts_enabled ?? false}
        // Disabled until settings load so a click can't PUT a value derived from the `?? false`
        // fallback rather than the user's persisted state; also locked during an in-flight write.
        disabled={settingsQuery.isPending || update.isPending}
        onChange={(checked) => update.mutate({ watchlist_alerts_enabled: checked })}
      />
    </div>
  )
}

function NotificationRow({ n }: { n: Notification }) {
  const markRead = useMarkRead()
  const activate = () => {
    if (!n.is_read) markRead.mutate(n.id)
  }
  const className = `flex flex-col gap-1 rounded-md border px-4 py-3 text-left ${
    n.is_read ? 'border-line bg-surface' : 'border-l-2 border-l-brand border-line bg-raised'
  }`
  const body = (
    <>
      {!n.is_read ? <span className="sr-only">Unread. </span> : null}
      <span className="text-sm text-ink">{n.message}</span>
      <span className="text-xs text-ink-dim">{timeAgo(n.created_at)}</span>
    </>
  )
  if (n.contract_id != null) {
    return (
      <li>
        <Link
          to="/contracts/$contractId"
          params={{ contractId: String(n.contract_id) }}
          onClick={activate}
          className={`${className} hover:border-brand-dim`}
        >
          {body}
        </Link>
      </li>
    )
  }
  return (
    <li>
      <button type="button" onClick={activate} className={`${className} w-full`}>
        {body}
      </button>
    </li>
  )
}
```

- [ ] **Step 10: Add the accessibility (axe) test.** Design §6 binds a `vitest-axe` pass on each new page. Mirror the house pattern (`src/features/contracts/components/a11y.test.tsx`) — create `app/frontend/web/src/features/notifications/components/NotificationsPage.a11y.test.tsx`. COMPLETE file:

```tsx
// ABOUTME: Automated axe accessibility checks for the notifications page — authed-with-data and anonymous states.
// ABOUTME: Mirrors src/features/contracts/components/a11y.test.tsx (vitest-axe on the designed UI, design §6).
import { afterEach, describe, expect, it, vi } from 'vitest'
import { screen } from '@testing-library/react'
import { axe } from 'vitest-axe'
import * as matchers from 'vitest-axe/matchers'
import { jsonResponse } from '../../../test/http'
import { renderApp } from '../../../test/renderApp'

expect.extend(matchers)

const AUTHED = { character_id: 91000001, character_name: 'Sesta Hound' }
const NOTE = {
  id: 1, type: 'watchlist_match', message: 'Rifter available in an auction priced 900,000 ISK in Jita IV - Moon 4',
  contract_id: 101, watch_type_id: 587, price: 900000, is_read: false, created_at: '2026-07-17T11:00:00Z',
}

function stubFetch(handler: (url: string) => Response) {
  vi.stubGlobal('fetch', async (input: RequestInfo | URL) => {
    const url = typeof input === 'string' ? input : input instanceof URL ? input.toString() : input.url
    return handler(url)
  })
}

afterEach(() => vi.unstubAllGlobals())

describe('accessibility (axe) — notifications', () => {
  it('authed list view has no violations', async () => {
    stubFetch((url) => {
      if (/\/api\/v1\/me$/.test(url)) return jsonResponse(AUTHED)
      if (/\/me\/notification-settings/.test(url)) return jsonResponse({ watchlist_alerts_enabled: true })
      if (/is_read=false&size=1/.test(url)) return jsonResponse({ total: 1, page: 1, size: 1, items: [] })
      if (/\/me\/notifications\//.test(url)) return jsonResponse({ total: 1, page: 1, size: 20, items: [NOTE] })
      return jsonResponse({}, 404)
    })
    const { container } = renderApp('/notifications')
    await screen.findByText(/rifter available/i)
    expect(await axe(container)).toHaveNoViolations()
  })

  it('anonymous sign-in prompt has no violations', async () => {
    stubFetch((url) => (/\/api\/v1\/me$/.test(url) ? jsonResponse({ detail: 'unauth' }, 401) : jsonResponse({ total: 0, page: 1, size: 20, items: [] })))
    const { container } = renderApp('/notifications')
    await screen.findByRole('heading', { name: /sign in to use notifications/i })
    expect(await axe(container)).toHaveNoViolations()
  })
})
```

- [ ] **Step 11: Run green.** `cd app/frontend/web && npx vitest run src/features/notifications/components/NotificationsPage.test.tsx src/features/notifications/components/NotificationsPage.a11y.test.tsx --reporter=dot` (pass; force route-tree regen as in Task 6.4 if needed). Regression-check the contracts pagination usage: `npx vitest run src/features/contracts/components/pages.test.tsx --reporter=dot` (pass). Then `npx tsc -b` and `npx eslint src/routes/notifications.tsx src/features/notifications src/features/contracts/components/Pagination.tsx src/components/Checkbox.tsx` (green).

- [ ] **Step 12: Commit.**
  `git add app/frontend/web/src/routes/notifications.tsx app/frontend/web/src/routeTree.gen.ts app/frontend/web/src/features/notifications/format.ts app/frontend/web/src/features/notifications/format.test.ts app/frontend/web/src/features/notifications/components/NotificationsPage.tsx app/frontend/web/src/features/notifications/components/NotificationsPage.test.tsx app/frontend/web/src/features/notifications/components/NotificationsPage.a11y.test.tsx app/frontend/web/src/features/contracts/components/Pagination.tsx app/frontend/web/src/components/Checkbox.tsx`
  ```
  feat(web): add notifications page with mark-read, pagination, and settings

  Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>
  ```

```
BEFORE marking this task complete:
1. Review tests against docs/pitfalls/testing-pitfalls.md
2. Verify test coverage (error paths? edge cases?)
3. Run tests and confirm green
```

```
After completing this phase:
Review the batch from multiple perspectives (correctness, pitfalls compliance, test coverage).
Minimum 3 review rounds. If round 3 still finds issues, keep going until clean.
```

Push: `git push`.

---

## Phase 9 — E2E (Playwright fixture lane)

**Execution Status:** ⬜ NOT STARTED

Delivers: account wire fixtures, account intercept helpers (captured-calls shape), and three specs asserting the authed flows at the wire plus the anonymous prompts. **All specs: `interceptCurrentUser` FIRST in every test (TEST-9), `failUnexpectedApiCalls` registered first where used, role/label selectors only, `retries` stays 0.**

### Task 9.1: `e2e/fixtures/account.ts` + `e2e/helpers/api.ts` intercepts + confirm `stubPortraits` covers type renders

```
BEFORE starting work:
1. Invoke superpowers:test-driven-development
2. Read docs/pitfalls/testing-pitfalls.md
Follow TDD: write failing test → implement → verify green.
```

Because these are E2E fixtures/helpers (test infrastructure, not production code under `src/`), the TDD "write a failing test first" is satisfied by the specs in Tasks 9.2–9.4 that import them — build the helpers here, then the specs drive them. Verify the helpers compile and a smoke spec uses them before moving on.

**Files:**
- Create: `app/frontend/web/e2e/fixtures/account.ts`
- Modify: `app/frontend/web/e2e/helpers/api.ts` (add `interceptSavedSearches`, `interceptWatchlist`; `interceptNotifications` + `AccountCall`/`readBody` were already added in Task 8.2 — reuse them; update the `stubPortraits` JSDoc)

- [ ] **Step 1: Read the current `e2e/helpers/api.ts`** (already reviewed in recon) to match the captured-calls shape and the last-registered-first routing discipline.

- [ ] **Step 2: Create `e2e/fixtures/account.ts`.** COMPLETE file:

```ts
// ABOUTME: Wire-shape fixtures for the M3 account APIs — saved searches, watchlist items, notifications.
// ABOUTME: Overrides let specs vary a field without inventing new wire shapes (mirrors fixtures/auth.ts + contracts.ts).

export interface WireSavedSearch {
  id: number
  name: string
  search_parameters: Record<string, unknown>
  created_at: string
  updated_at: string
}

export function makeSavedSearch(overrides: Partial<WireSavedSearch> = {}): WireSavedSearch {
  return {
    id: 1,
    name: 'Cheap frigates',
    search_parameters: { ships_only: true, min_price: 0, max_price: 5_000_000, size: 50, sort_by: 'price', sort_direction: 'asc' },
    created_at: '2026-07-17T00:00:00Z',
    updated_at: '2026-07-17T00:00:00Z',
    ...overrides,
  }
}

export interface WireWatchlistItem {
  id: number
  type_id: number
  type_name: string
  max_price: number | null
  notes: string | null
  created_at: string
  updated_at: string
}

export function makeWatchlistItem(overrides: Partial<WireWatchlistItem> = {}): WireWatchlistItem {
  return {
    id: 1,
    type_id: 587,
    type_name: 'Rifter',
    max_price: null,
    notes: null,
    created_at: '2026-07-17T00:00:00Z',
    updated_at: '2026-07-17T00:00:00Z',
    ...overrides,
  }
}

export interface WireNotification {
  id: number
  type: string
  message: string
  contract_id: number | null
  watch_type_id: number | null
  price: number | null
  is_read: boolean
  created_at: string
}

export function makeNotification(overrides: Partial<WireNotification> = {}): WireNotification {
  return {
    id: 1,
    type: 'watchlist_match',
    message: 'Rifter available in an auction priced 900,000 ISK in Jita IV - Moon 4',
    contract_id: 232_100_001,
    watch_type_id: 587,
    price: 900_000,
    is_read: false,
    created_at: '2026-07-17T11:00:00Z',
    ...overrides,
  }
}
```

- [ ] **Step 3: Add the saved-searches + watchlist intercept helpers to `e2e/helpers/api.ts`.** `interceptNotifications` and its `AccountCall`/`readBody` scaffolding are **already present** — added in Task 8.2 (its first consumer). Verify they exist and do NOT redefine them; the two helpers below reuse the existing `AccountCall`/`readBody`. Append after the existing helpers. Each returns a live captured-calls array `{ url, method, body }` (the same "captured calls" idea as `interceptContractList`, extended with `method`/`body` because these are write endpoints). COMPLETE additions:

```ts
// (add to the imports at the top of e2e/helpers/api.ts)
import { makeSavedSearch, type WireSavedSearch } from '../fixtures/account'
import type { WireWatchlistItem } from '../fixtures/account'

/** Intercept /me/saved-searches/* — GET returns `list`, POST echoes a made row (201), PUT 200, DELETE 204. */
export async function interceptSavedSearches(page: Page, list: WireSavedSearch[] = []): Promise<AccountCall[]> {
  const calls: AccountCall[] = []
  await page.route(/\/api\/v1\/me\/saved-searches\//, async (route) => {
    const req = route.request()
    const method = req.method()
    const body = method === 'POST' || method === 'PUT' ? readBody(route) : undefined
    calls.push({ url: new URL(req.url()), method, body })
    if (method === 'GET') return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(list) })
    if (method === 'DELETE') return route.fulfill({ status: 204, body: '' })
    const echo = makeSavedSearch(body as Partial<WireSavedSearch>)
    return route.fulfill({ status: method === 'POST' ? 201 : 200, contentType: 'application/json', body: JSON.stringify(echo) })
  })
  return calls
}

/** Intercept /me/watchlist-items/* — GET returns `list`, POST echoes (201), PUT 200, DELETE 204. */
export async function interceptWatchlist(page: Page, list: WireWatchlistItem[] = []): Promise<AccountCall[]> {
  const calls: AccountCall[] = []
  await page.route(/\/api\/v1\/me\/watchlist-items\//, async (route) => {
    const req = route.request()
    const method = req.method()
    const body = method === 'POST' || method === 'PUT' ? readBody(route) : undefined
    calls.push({ url: new URL(req.url()), method, body })
    if (method === 'GET') return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(list) })
    if (method === 'DELETE') return route.fulfill({ status: 204, body: '' })
    const src = (body ?? {}) as Partial<WireWatchlistItem>
    return route.fulfill({ status: method === 'POST' ? 201 : 200, contentType: 'application/json', body: JSON.stringify({ id: 999, type_id: src.type_id ?? 587, type_name: src.type_name ?? 'Rifter', max_price: src.max_price ?? null, notes: src.notes ?? null, created_at: 'x', updated_at: 'x' }) })
  })
  return calls
}
```

`interceptNotifications` (and `AccountCall`/`readBody`) already live in `e2e/helpers/api.ts` from Task 8.2 — the notifications specs (Task 9.4) import it from `./helpers/api` unchanged.

- [ ] **Step 4: Confirm `stubPortraits` already covers type renders (no functional change needed).** The existing glob `**://images.evetech.net/**` already matches `images.evetech.net/types/{id}/render` — the watchlist row icon URL — so watchlist specs stay offline with the current helper. Update only the JSDoc to say so; do NOT narrow or duplicate the route. Replace the `stubPortraits` doc comment with:

```ts
/** Serve a tiny PNG for ALL images.evetech.net requests — character portraits AND type renders
 * (e.g. /types/{id}/render on the watchlist page) — so authenticated specs stay fully offline. */
```

- [ ] **Step 5: Verify it compiles.** `cd app/frontend/web && npx tsc -b` (green) and `npx eslint e2e/fixtures/account.ts e2e/helpers/api.ts` (green). No spec runs yet — the specs in 9.2–9.4 exercise these.

- [ ] **Step 6: Commit.**
  `git add app/frontend/web/e2e/fixtures/account.ts app/frontend/web/e2e/helpers/api.ts`
  ```
  test(e2e): add account fixtures and intercept helpers

  Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>
  ```

```
BEFORE marking this task complete:
1. Review tests against docs/pitfalls/testing-pitfalls.md
2. Verify test coverage (error paths? edge cases?)
3. Run tests and confirm green
```

### Task 9.2: `saved-searches.spec.ts` (authed save flow wire assertion; anonymous prompt)

```
BEFORE starting work:
1. Invoke superpowers:test-driven-development
2. Read docs/pitfalls/testing-pitfalls.md
Follow TDD: write failing test → implement → verify green.
```

**Files:**
- Create: `app/frontend/web/e2e/saved-searches.spec.ts`

- [ ] **Step 1: Write the spec.** `interceptCurrentUser` first in every test. COMPLETE file:

```ts
import { expect, test } from '@playwright/test'
import { SEVEN_SHIPS, pageOf } from './fixtures/contracts'
import { makeCurrentUser } from './fixtures/auth'
import { makeSavedSearch } from './fixtures/account'
import { interceptContractList, interceptCurrentUser, interceptNotifications, interceptSavedSearches, stubPortraits } from './helpers/api'

test.describe('saved searches', () => {
  test('anonymous /saved-searches shows the sign-in prompt', async ({ page }) => {
    await interceptCurrentUser(page, { status: 401 })
    await page.goto('/saved-searches')
    await expect(page.getByRole('heading', { name: /sign in to use saved searches/i })).toBeVisible()
    await expect(page.getByRole('link', { name: /log in with eve/i })).toBeVisible()
  })

  test('authed user saves the current search and the POST carries search-minus-page', async ({ page }) => {
    await interceptCurrentUser(page, makeCurrentUser())
    await interceptNotifications(page, { unread: 0 })
    await interceptContractList(page, pageOf(SEVEN_SHIPS))
    const calls = await interceptSavedSearches(page, [])
    await stubPortraits(page)

    await page.goto('/contracts?min_price=1000&sort_by=price&sort_direction=asc')
    await page.getByRole('button', { name: /save search/i }).click()
    await page.getByLabel(/search name/i).fill('Cheap ships')
    await page.getByRole('button', { name: /^save$/i }).click()

    await expect.poll(() => calls.filter((c) => c.method === 'POST').length).toBe(1)
    const post = calls.find((c) => c.method === 'POST')!
    const body = post.body as { name: string; search_parameters: Record<string, unknown> }
    expect(body.name).toBe('Cheap ships')
    expect(body.search_parameters).toMatchObject({ min_price: 1000, ships_only: true, sort_by: 'price', sort_direction: 'asc' })
    expect(body.search_parameters).not.toHaveProperty('page')
  })

  test('authed /saved-searches lists a saved search and applies it', async ({ page }) => {
    await interceptCurrentUser(page, makeCurrentUser())
    await interceptNotifications(page, { unread: 0 })
    await interceptContractList(page, pageOf(SEVEN_SHIPS))
    await interceptSavedSearches(page, [makeSavedSearch({ name: 'Cheap frigates' })])
    await stubPortraits(page)

    await page.goto('/saved-searches')
    await expect(page.getByText('Cheap frigates')).toBeVisible()
    await page.getByRole('button', { name: /apply/i }).click()
    await expect(page).toHaveURL(/\/contracts\?/)
    await expect(page).toHaveURL(/sort_by=price/)
  })
})
```

- [ ] **Step 2: Run it.** `cd app/frontend/web && npx playwright test saved-searches.spec.ts --project=desktop`. Expected: green. If the save-flow assertion fails on the POST body, re-check `toSavedSearchParameters` (Task 6.3) — do NOT weaken the assertion (TEST-2).

- [ ] **Step 3: Run mobile too.** `npx playwright test saved-searches.spec.ts --project=mobile` (green).

- [ ] **Step 4: Commit.**
  `git add app/frontend/web/e2e/saved-searches.spec.ts`
  ```
  test(e2e): cover saved-search save + apply flows

  Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>
  ```

```
BEFORE marking this task complete:
1. Review tests against docs/pitfalls/testing-pitfalls.md
2. Verify test coverage (error paths? edge cases?)
3. Run tests and confirm green
```

### Task 9.3: `watchlist.spec.ts` (add-by-name wire assertion; two-step remove)

```
BEFORE starting work:
1. Invoke superpowers:test-driven-development
2. Read docs/pitfalls/testing-pitfalls.md
Follow TDD: write failing test → implement → verify green.
```

**Files:**
- Create: `app/frontend/web/e2e/watchlist.spec.ts`

- [ ] **Step 1: Write the spec.** COMPLETE file:

```ts
import { expect, test } from '@playwright/test'
import { makeCurrentUser } from './fixtures/auth'
import { makeWatchlistItem } from './fixtures/account'
import { interceptCurrentUser, interceptNotifications, interceptWatchlist, stubPortraits } from './helpers/api'

test.describe('watchlist', () => {
  test('anonymous /watchlist shows the sign-in prompt', async ({ page }) => {
    await interceptCurrentUser(page, { status: 401 })
    await page.goto('/watchlist')
    await expect(page.getByRole('heading', { name: /sign in to use your watchlist/i })).toBeVisible()
  })

  test('add-by-name POSTs the exact wire payload', async ({ page }) => {
    await interceptCurrentUser(page, makeCurrentUser())
    await interceptNotifications(page, { unread: 0 })
    const calls = await interceptWatchlist(page, [])
    await stubPortraits(page)

    await page.goto('/watchlist')
    await page.getByLabel(/ship name/i).fill('Maelstrom')
    await page.getByLabel(/max price/i).fill('300000000')
    await page.getByLabel(/notes/i).fill('flagship')
    await page.getByRole('button', { name: /add to watchlist/i }).click()

    await expect.poll(() => calls.filter((c) => c.method === 'POST').length).toBe(1)
    expect(calls.find((c) => c.method === 'POST')!.body).toEqual({ type_name: 'Maelstrom', max_price: 300000000, notes: 'flagship' })
  })

  test('two-step remove DELETEs only after confirm', async ({ page }) => {
    await interceptCurrentUser(page, makeCurrentUser())
    await interceptNotifications(page, { unread: 0 })
    const calls = await interceptWatchlist(page, [makeWatchlistItem({ id: 1, type_name: 'Rifter' })])
    await stubPortraits(page)

    await page.goto('/watchlist')
    await expect(page.getByText('Rifter')).toBeVisible()
    await page.getByRole('button', { name: /^remove$/i }).click()
    expect(calls.filter((c) => c.method === 'DELETE')).toHaveLength(0)
    await page.getByRole('button', { name: /confirm remove/i }).click()
    await expect.poll(() => calls.filter((c) => c.method === 'DELETE').length).toBe(1)
  })
})
```

- [ ] **Step 2: Run desktop + mobile.** `cd app/frontend/web && npx playwright test watchlist.spec.ts --project=desktop` then `--project=mobile` (both green).

- [ ] **Step 3: Commit.**
  `git add app/frontend/web/e2e/watchlist.spec.ts`
  ```
  test(e2e): cover watchlist add-by-name and two-step remove

  Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>
  ```

```
BEFORE marking this task complete:
1. Review tests against docs/pitfalls/testing-pitfalls.md
2. Verify test coverage (error paths? edge cases?)
3. Run tests and confirm green
```

### Task 9.4: `notifications.spec.ts` (badge count; mark-all-read wire call; TEST-8 sync)

```
BEFORE starting work:
1. Invoke superpowers:test-driven-development
2. Read docs/pitfalls/testing-pitfalls.md
Follow TDD: write failing test → implement → verify green.
```

For this task's timing/synchronization assertions, the assertion-rigor discipline applies:

```
If any test assertion races, flakes, or fails nondeterministically, the fix is deterministic
synchronization or deterministic fixture data — NOT assertion removal or weakening. If
synchronization cannot make the assertion pass reliably, STOP and raise to the dispatching
agent. Do not ship a weaker test. Prefer mechanism assertions (state observed) over symptom
assertions (timing bounds).
```

**Files:**
- Create: `app/frontend/web/e2e/notifications.spec.ts`

- [ ] **Step 1: Write the spec.** The list page's loading skeleton (`role="status"`, name "Loading notifications") coexists with the always-mounted live region — sync on skeleton unmount before asserting the list (TEST-8). COMPLETE file:

```ts
import { expect, test } from '@playwright/test'
import { SEVEN_SHIPS, pageOf } from './fixtures/contracts'
import { makeCurrentUser } from './fixtures/auth'
import { makeNotification } from './fixtures/account'
import { interceptContractList, interceptCurrentUser, interceptNotifications, stubPortraits } from './helpers/api'

test.describe('notifications', () => {
  test('header bell renders the unread count from total', async ({ page }) => {
    await interceptCurrentUser(page, makeCurrentUser())
    await interceptNotifications(page, { unread: 4 })
    await interceptContractList(page, pageOf(SEVEN_SHIPS))
    await stubPortraits(page)

    await page.goto('/contracts')
    const bell = page.getByRole('link', { name: /notifications \(4 unread\)/i })
    await expect(bell).toBeVisible()
    await expect(bell).toContainText('4')
  })

  test('notifications page lists rows (after skeleton unmount) and marks all read', async ({ page }) => {
    await interceptCurrentUser(page, makeCurrentUser())
    const calls = await interceptNotifications(page, {
      items: [makeNotification({ id: 1, message: 'Rifter available in an auction priced 900,000 ISK' })],
      unread: 1,
    })
    await stubPortraits(page)

    await page.goto('/notifications')
    // TEST-8: the loading skeleton (role=status "Loading notifications") must unmount before the list
    // shows. `interceptNotifications` resolves instantly, so asserting the skeleton *visible* first
    // would race the fixture; instead use the loaded row as the deterministic synchronization gate,
    // then assert the skeleton has detached (a non-vacuous check now that content is confirmed loaded).
    // Do NOT weaken this to a bare toHaveCount(0) before the row renders (TEST-2 / TEST-8).
    await expect(page.getByText(/rifter available/i)).toBeVisible()
    await expect(page.getByRole('status', { name: 'Loading notifications' })).toHaveCount(0)

    await page.getByRole('button', { name: /mark all as read/i }).click()
    await expect.poll(() => calls.some((c) => /\/mark-all-read$/.test(c.url.pathname) && c.method === 'POST')).toBe(true)
  })

  test('anonymous /notifications shows the sign-in prompt', async ({ page }) => {
    await interceptCurrentUser(page, { status: 401 })
    await page.goto('/notifications')
    await expect(page.getByRole('heading', { name: /sign in to use notifications/i })).toBeVisible()
  })
})
```

- [ ] **Step 2: Run desktop + mobile.** `cd app/frontend/web && npx playwright test notifications.spec.ts --project=desktop` then `--project=mobile` (both green).

- [ ] **Step 3: Commit.**
  `git add app/frontend/web/e2e/notifications.spec.ts`
  ```
  test(e2e): cover notification badge and mark-all-read

  Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>
  ```

```
BEFORE marking this task complete:
1. Review tests against docs/pitfalls/testing-pitfalls.md
2. Verify test coverage (error paths? edge cases?)
3. Run tests and confirm green
```

```
After completing this phase:
Review the batch from multiple perspectives (correctness, pitfalls compliance, test coverage).
Minimum 3 review rounds. If round 3 still finds issues, keep going until clean.
```

Push: `git push`.

---

## Phase 10 — Docs, gates, and PR

**Execution Status:** ⬜ NOT STARTED

Delivers: two new pitfall entries with full completeness-checklist maintenance; README + feature-index + per-feature deviation notes; the full local gate run; and the (unmerged) PR to `dev`.

### Task 10.1: Pitfalls entries — implementation `SQLA-2` and testing `TEST-11`

```
BEFORE starting work:
1. Invoke superpowers:test-driven-development
2. Read docs/pitfalls/testing-pitfalls.md
Follow TDD: write failing test → implement → verify green.
```

This task edits Markdown only (no production code / no test suite). TDD does not apply (CLAUDE.md §TDD Scope: docs are exempt). The "test" here is the completeness self-check in Step 4.

**Files:**
- Modify: `docs/pitfalls/implementation-pitfalls.md`
- Modify: `docs/pitfalls/testing-pitfalls.md`

- [ ] **Step 1: Add `SQLA-2` to implementation-pitfalls.md §Section 2 (Data & Persistence).** Insert after the SQLA-1 entry (before the `### §2.C — Review Checklist` heading). Follows the house `Flaw → Why It Matters → Fix → Where It Bit Us` shape; the "Where It Bit Us" is written pre-emptively (the design mandated the fix, so this documents the trap the matcher's write path would hit without it):

```markdown
### SQLA-2: `ON CONFLICT` against a partial unique index must restate the index predicate

**The Flaw:** `INSERT … ON CONFLICT DO NOTHING` / `DO UPDATE` targeting a **partial** unique index (`CREATE UNIQUE INDEX … WHERE <predicate>`) will not infer the index from `index_elements` alone. Postgres raises `no unique or exclusion constraint matching the ON CONFLICT specification` at runtime — every insert fails, not just conflicting ones.

**Why It Matters:** The failure is runtime-only (schema and query both look valid), so it surfaces on the first real insert, not at review or migration time. For a scheduled writer (the watchlist matcher) that means every run raises and zero notifications are ever created.

**The Fix:** Restate the partial-index predicate in the conflict clause as a **literal identical to the index DDL**. SQLAlchemy: `insert(...).on_conflict_do_nothing(index_elements=["user_id", "contract_id", "watch_type_id"], index_where=text("type = 'watchlist_match'"))`. Use `text(...)`, not the ORM comparison `Notification.type == "watchlist_match"` — the latter compiles to a parameterized `type = $1`, which Postgres's partial-index implication check cannot match against the index's literal predicate, so inference can fail. Also populate **every** column in the index — Postgres treats NULLs as distinct in a unique index, so a NULL-bearing dedup column would never conflict and hollow out the guarantee.

**Where It Bit Us:** Pre-empted in the M3 watchlist-matcher design (`docs/superpowers/specs/2026-07-17-m3-account-features-design.md` §4.4); the partial index `uq_notifications_watchlist_dedup` on `(user_id, contract_id, watch_type_id) WHERE type='watchlist_match'` requires the `index_where` restatement or the matcher's core insert raises on every run. See testing-pitfalls.md TEST-11.
```

- [ ] **Step 2: Add the SQLA-2 review-checklist item.** Under `### §2.C — Review Checklist`, add a second bullet after the SQLA-1 item:

```markdown
- [ ] **`ON CONFLICT` against a partial unique index restates the index predicate** — `index_where=` matches the index's `WHERE`, and every indexed column is non-NULL on insert (Postgres NULLs never conflict) (SQLA-2)
```

- [ ] **Step 3: Update the TOC and Appendix B for SQLA-2.** In the Table of Contents row for section 2, change the Entries cell `SQLA-1` → `SQLA-1, SQLA-2`. In Appendix B (Unified Summary Table), add a row after the SQLA-1 row:

```markdown
| SQLA-2 | ON CONFLICT vs a partial unique index needs index_where | HIGH | VALIDATED | Data & Persistence |
```

- [ ] **Step 4: Run the Appendix C completeness checklist for SQLA-2.** Confirm all of: entry added to the domain section ✓; review-checklist item added (§2.C) ✓; TOC entry list updated ✓; Appendix B row added ✓; cross-reference to testing-pitfalls TEST-11 present ✓. (These four+one are exactly the "Completeness Checklist" in Appendix C.)

- [ ] **Step 5: Add `TEST-11` to testing-pitfalls.md §8.** Append after the TEST-10 entry (before the `## How to Add a Testing-Pitfall` heading):

```markdown
- [ ] **🔥 TEST-11 — Writer-side bulk inserts need a test that crosses one chunk boundary.** A bulk insert split into fixed-size chunks (asyncpg caps a statement at 32767 bind params, so the matcher inserts ≤1000 rows/statement) has an off-by-one or last-chunk-dropped bug that is invisible to any test whose match set fits in a single chunk. **Do instead:** arrange a match set strictly larger than one insert chunk (e.g. > `NOTIFICATION_INSERT_CHUNK` rows) and assert every row lands — `created == len(match_set)` and the union of inserted dedup keys equals the expected set. **Bit us:** pre-empted in the M3 watchlist matcher (`services/watchlist_matcher.py`, `NOTIFICATION_INSERT_CHUNK=1000`); pairs with implementation-pitfalls SQLA-2 (the chunked insert is the same statement that carries the partial-index ON CONFLICT). Relates to §4 Bounded growth.
```

- [ ] **Step 6: Commit.**
  `git add docs/pitfalls/implementation-pitfalls.md docs/pitfalls/testing-pitfalls.md`
  ```
  docs(pitfalls): add SQLA-2 (partial-index ON CONFLICT) and TEST-11 (chunk-boundary insert)

  Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>
  ```

```
BEFORE marking this task complete:
1. Review tests against docs/pitfalls/testing-pitfalls.md
2. Verify test coverage (error paths? edge cases?)
3. Run tests and confirm green
```

### Task 10.2: README implementation status + feature-index statuses + F005/F006/F007 deviation notes

```
BEFORE starting work:
1. Invoke superpowers:test-driven-development
2. Read docs/pitfalls/testing-pitfalls.md
Follow TDD: write failing test → implement → verify green.
```

Docs only; TDD N/A. First **read** each file to match its existing structure before editing (the exact heading names and table shapes below must be confirmed against the live files — if a heading differs, adapt to the real one; do not invent a new section shape).

**Files:**
- Modify: `README.md` (the Implementation Status section)
- Modify: `design/features/feature-index.md` (F005/F006/F007 status cells)
- Modify: `design/features/F005-Saved-Searches.md`, `design/features/F006-Watchlists.md`, `design/features/F007-Alerts-Notifications.md` (append a deviations note each)

- [ ] **Step 1: Read the three target docs' current shape.** `cat README.md | sed -n '1,120p'` to find the implementation-status block; open `design/features/feature-index.md` and the three feature specs to see their status conventions and where a note belongs.

- [ ] **Step 2: Update `README.md` Implementation Status.** Mark F005 Saved Searches, F006 Watchlists, and F007 Alerts/Notifications as implemented (zero-scope, this milestone), matching the surrounding table/list style. Reference the design spec path `docs/superpowers/specs/2026-07-17-m3-account-features-design.md` for the scope framing (self-identifying cross-reference: it is the authoritative M3 design).

- [ ] **Step 3: Update `design/features/feature-index.md`.** Set the F005/F006/F007 status cells to "Implemented with deviations" (or the index's equivalent term), each linking the design spec.

- [ ] **Step 4: Append an "Implemented with deviations (M3)" note to each feature spec.** Each note lists the recorded §8 deviations relevant to that feature and links the design spec `docs/superpowers/specs/2026-07-17-m3-account-features-design.md`. COMPLETE note bodies:

  For `F005-Saved-Searches.md`:
```markdown
## Implemented with deviations (M3, 2026-07-17)

Implemented zero-scope per [the M3 design spec](../../docs/superpowers/specs/2026-07-17-m3-account-features-design.md). Recorded deviations (design §8):
- **Per-user cap of 100 saved searches** — overrides this spec's §15 "no hard limit for MVP"; enforced best-effort (count-then-insert), race-safe only for the name-uniqueness constraint.
- **No `GET /me/saved-searches/{search_id}`** — the list response carries complete rows; the single-resource GET is deferred until a consumer needs it.
- **Rename-only update** — updating stored criteria in place is deferred (this spec already defers it); the PUT changes `name` only.
- **`extra="forbid"` on stored parameters** — the saved blob is the frontend `ContractSearch` minus `page`; ME/TE and unknown keys are rejected at the API boundary.
```

  For `F006-Watchlists.md`:
```markdown
## Implemented with deviations (M3, 2026-07-17)

Implemented zero-scope per [the M3 design spec](../../docs/superpowers/specs/2026-07-17-m3-account-features-design.md). Recorded deviations (design §8):
- **No `esi_type_cache` table** — type→name/category is resolved at add-time via public, version-pinned ESI (`/v3/universe/types/`, `/v1/universe/groups/`, `POST /v1/universe/ids/`) and denormalized onto the watchlist row.
- **Per-user cap of 200 watchlist items** — best-effort count-then-insert; only the `(user_id, type_id)` uniqueness is constraint-backed.
- **Two zero-scope add paths** — quick-watch on the contract detail page (one-click, no price) and add-by-exact-name on the watchlist page (satisfies Criterion 2.1 price-at-add-time and covers unlisted ships). Fuzzy type-ahead search is deferred (needs a local type dataset).
- **No `GET /me/watchlist-items/{item_id}`** — deferred until a consumer needs it.
```

  For `F007-Alerts-Notifications.md`:
```markdown
## Implemented with deviations (M3, 2026-07-17)

Implemented zero-scope per [the M3 design spec](../../docs/superpowers/specs/2026-07-17-m3-account-features-design.md). Recorded deviations (design §8):
- **APScheduler, not Celery** — the matcher is an APScheduler interval job mirroring the aggregation job (§4.4).
- **Bundle-price match semantics** — a watched ship inside a multi-item contract matches on the whole-contract price (per-item pricing does not exist in the data); the notification message names the contract price, not a per-ship price.
- **De-dup is a partial unique index + `ON CONFLICT DO NOTHING`** — re-notification on further price drops / cooldown is deferred (Criterion 1.3 "may").
- **Bell links to a `/notifications` page** (no dropdown panel); a single "Watchlist alerts" checkbox is the settings surface. Email/push/WebSockets and saved-search alerts (Story 2) remain deferred.
- **Notification messages are pre-rendered English** — `message_key`/`message_params` i18n columns are not built (house-wide i18n deferral).
```

Confirm the relative link depth (`../../docs/...`) matches `design/features/` → repo root when editing; adjust to the real relative path if the feature specs live at a different depth.

- [ ] **Step 5: Commit.**
  `git add README.md design/features/feature-index.md design/features/F005-Saved-Searches.md design/features/F006-Watchlists.md design/features/F007-Alerts-Notifications.md`
  ```
  docs: mark F005/F006/F007 implemented with recorded M3 deviations

  Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>
  ```

```
BEFORE marking this task complete:
1. Review tests against docs/pitfalls/testing-pitfalls.md
2. Verify test coverage (error paths? edge cases?)
3. Run tests and confirm green
```

### Task 10.3: Full local gates, push, and open the PR (do NOT merge)

```
BEFORE starting work:
1. Invoke superpowers:test-driven-development
2. Read docs/pitfalls/testing-pitfalls.md
Follow TDD: write failing test → implement → verify green.
```

No new code; this task runs the gates and opens the PR. Invoke `superpowers:verification-before-completion` before claiming green.

- [ ] **Step 1: Backend gate — pytest.** From the campaign worktree: `docker compose -f app/backend/docker/compose.yml -f app/backend/docker/compose.dependencies.yml up -d --wait postgres_db valkey_cache`, then `cd app/backend && pdm run pytest -q`. Expected: all pass, output pristine (TEST §1 — no stray errors/warnings). Record the pass count.

- [ ] **Step 2: Frontend lint.** `cd app/frontend/web && npx eslint .`. Expected: no errors.

- [ ] **Step 3: Frontend typecheck.** `cd app/frontend/web && npx tsc -b`. Expected: clean.

- [ ] **Step 4: Frontend unit/component suite.** `cd app/frontend/web && npm run test`. Expected: all pass (this is `vitest run`, which excludes `e2e/**` per TEST-6). Record the pass count.

- [ ] **Step 5: E2E fixture lane — desktop + mobile.** `cd app/frontend/web && npm run e2e` (runs the desktop + mobile projects; live-smoke auto-skips). Expected: all pass, `retries` at 0. If any spec flakes, fix with deterministic synchronization (TEST-2), never a retry bump. Record the pass count per project.

- [ ] **Step 6: Confirm the codegen artifacts are committed and current.** `git status --porcelain app/frontend/web/openapi.json app/frontend/web/src/lib/api/schema.d.ts app/frontend/web/src/routeTree.gen.ts` — expected: clean (no uncommitted regen diff). If `routeTree.gen.ts` shows a diff, commit it — subject `chore(web): regenerate route tree`, ending with the `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>` trailer like every other commit. The backend-schema codegen (`openapi.json` + `schema.d.ts`) was committed in the backend phases; if a diff appears, STOP and raise — a late schema change means the client is stale.

- [ ] **Step 7: Push the branch.** `git push` (branch already tracks `origin/claude/m3-account-features` from Phase 6).

- [ ] **Step 8: Open the PR to `dev` (do NOT merge).** `gh pr create --base dev --head claude/m3-account-features --title "feat: M3 account features (F005 saved searches, F006 watchlists, F007 notifications)" --body "<body below>"`. Fill the test-evidence placeholders with the REAL numbers recorded in Steps 1/4/5. COMPLETE body template:

```markdown
## Summary

Zero-scope M3 account features on the existing SSO identity (no new ESI scope):
- **F005 Saved Searches** — per-user saved contract filters; save from the contracts header, manage/apply/rename/delete on `/saved-searches`.
- **F006 Watchlists** — watch ships by type; quick-watch on contract detail + add-by-exact-name on `/watchlist`, inline max-price/notes editing.
- **F007 Alerts/Notifications** — APScheduler matcher notifies on watchlist matches against outstanding local contracts; header bell + `/notifications` page + mark-read/all + settings.

Backend: three new tables (`saved_searches`, `watchlist_items`, `notifications`) + `users.watchlist_alerts_enabled`, `get_current_user` session→row resolution, `/me/*` routers, and the watchlist matcher job. Frontend: three feature folders, three routes, the `RequireSignIn` gate, and the notification bell. Full design: `docs/superpowers/specs/2026-07-17-m3-account-features-design.md`.

## Test evidence

- Backend pytest: <N> passed (fill from gate Step 1).
- Frontend vitest: <N> passed (fill from gate Step 4).
- Playwright fixture lane: desktop <N> passed, mobile <N> passed, retries 0 (fill from gate Step 5).
- eslint: clean. tsc -b: clean.

## Deviations (Sam's sign-off requested)

Recorded in design §8 and each feature spec's "Implemented with deviations" note: per-user caps (100 searches / 200 watchlist items, override F005 §15); bundle-price match semantics (whole-contract price, per-item pricing doesn't exist); notification messages name the contract price, not a per-ship price; bell-as-link (no dropdown) + single settings checkbox `[REVIEW]`; `GET /me/{saved-searches,watchlist-items}/{id}` not built (no consumer).

## Merge classification

**Review — database schema + per-user data authorization.** Both Domain triggers apply (new schema; authorization-scoping code), so auto-merge is off the table by policy. **Sam merges.** Adversarial code review (`/codex review`) to be recorded before merge.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
```

- [ ] **Step 9: Confirm the PR is open and unmerged.** `gh pr view --json state,mergeStateStatus` — expected `state: OPEN`. **The plan ends here — do NOT merge.** Report the PR URL and the recorded gate numbers to Sam.

```
BEFORE marking this task complete:
1. Review tests against docs/pitfalls/testing-pitfalls.md
2. Verify test coverage (error paths? edge cases?)
3. Run tests and confirm green
```

```
After completing this phase:
Review the batch from multiple perspectives (correctness, pitfalls compliance, test coverage).
Minimum 3 review rounds. If round 3 still finds issues, keep going until clean.
```
