<!-- ABOUTME: M4 recon of Hangar Bay's data layer for someone planning Alembic revival for production — vestigial Alembic state, live model inventory, create_all paths, the M3 schema delta + file-collision map, and engine/session config. -->
<!-- ABOUTME: Facts only, evidence-backed with file:line citations. No code was modified. Read-only recon. -->

# M4 Recon — Data Layer & Alembic Revival

Scope: `app/backend/`. All paths below are absolute under
`/Users/sam/Code/hangar-bay/.claude/worktrees/hangar-bay-frontend-rebuild-2e4fe7/`.
Purpose: give an M4 designer/implementer everything needed to (a) decide how to revive
Alembic for durable production schema management, and (b) avoid colliding with the in-flight
M3 account-features branch until it merges.

**Headline:** Today there is **no live migration system**. Dev and tests create schema via
`Base.metadata.drop_all` + `create_all` (destructive on every dev boot). The `alembic/` tree
exists but is **stale, wrong-schema, and unwired** — reviving it is a genuine M4 greenfield task,
not a "catch up the migrations" task. M3 adds 3 tables + 1 column + 1 partial unique index on top
of this, all still riding `create_all`; M4 and M3 both want to touch `models/__init__.py`,
`main.py`, `core/config.py`, and `core/scheduler.py` — see the collision map (§4).

---

## 1. The vestigial Alembic state

### Layout

- `app/backend/src/alembic.ini` — config; `script_location = %(here)s/alembic`, `prepend_sys_path = .`
  (alembic.ini:8,19). Fresh Alembic 1.16-era template (the long `path_separator`/`version_locations`
  comment block is the 1.16 default). **No `sqlalchemy.url` is set** (alembic.ini:87 is commented) —
  the URL comes entirely from `env.py` reading app settings.
- `app/backend/src/alembic/env.py` — the migration environment (5.7 KB, last modified Jul 18).
- `app/backend/src/alembic/versions/` — 6 revision files (§1.3).
- `app/backend/src/alembic/script.py.mako`, `alembic/README` (`README` says only
  "Generic single-database configuration").
- `app/backend/src/check_alembic_version.py` — **SQLite-era orphan** (§1.4).
- `alembic` is a declared runtime dependency: `pyproject.toml:8` pins `alembic>=1.16.1`
  (installed: `alembic-1.16.1` under `.venv`). Sync drivers for offline/CLI use are also present:
  `psycopg2-binary>=2.9.10` and `aiosqlite>=0.21.0` (pyproject.toml:8).

### 1.2 `env.py` wiring (async, target_metadata correct, CLI block removed)

`app/backend/src/alembic/env.py`:

- **sys.path hack** to make `fastapi_app` importable (env.py:7).
- **Imports the real models for autogenerate** — `from fastapi_app.models import user, contracts`
  plus the explicit class imports (env.py:31-34). So `target_metadata = Base.metadata`
  (env.py:62) is the **live** metadata, meaning autogenerate WOULD see the current SSO `User` +
  contracts models correctly. **This is the one part that is not stale.**
- **URL source:** `settings = get_settings()` (env.py:36) and both offline
  (`url=str(settings.DATABASE_URL)`, env.py:87) and online-CLI
  (`create_async_engine(str(settings.DATABASE_URL), poolclass=pool.NullPool)`, env.py:122-126)
  read `settings.DATABASE_URL` — which is the **asyncpg** URL
  (`postgresql+asyncpg://…`, see §5). Offline mode with an asyncpg URL + `literal_binds=True`
  (env.py:89) works for SQL generation (no DBAPI connect), but note the driver token is async.
- **Async online path is wired:** `run_migrations_online_async_cli()` (env.py:115-131) uses
  `connectable.begin()` + `connection.run_sync(do_run_migrations)` — the canonical async-Alembic
  shape. `run_migrations_online()` (env.py:134-153) branches: if
  `context.config.attributes["connection"]` is present it uses the caller's (pytest) connection;
  else `asyncio.run(run_migrations_online_async_cli())`.
- **`compare_type` is disabled** — offline config has it commented out (env.py:91:
  `# compare_type=True,  # Temporarily commented out to detect type changes`) and online
  `do_run_migrations` (env.py:104-107) passes only `connection` + `target_metadata`, so **type
  changes and server-default changes are NOT detected by autogenerate** as configured. An M4
  revival should turn on `compare_type=True` and `compare_server_default=True` (relevant because
  the models carry `server_default=func.now()` and M3 adds boolean server defaults — §2, §4).
- **The CLI execution block was removed** (env.py:156-157: "The CLI execution block has been
  removed to make this module safely importable by pytest. The test suite now calls
  do_run_migrations() directly."). **Consequence: running `alembic upgrade head` from the CLI
  will fail** — env.py never calls `run_migrations_offline()`/`run_migrations_online()` at module
  scope the way stock Alembic env.py does. Reviving CLI use requires re-adding the standard
  `if context.is_offline_mode(): run_migrations_offline() else: run_migrations_online()` tail.
- **Debug cruft:** env.py:41-60 prints every table/column to stdout+stderr on import
  ("ALEMBIC METADATA DEBUG"). Harmless but should be deleted on revival.
- **Duplicate `import asyncio`** at env.py:1 and env.py:9 (dead but harmless).

### 1.3 Existing revision files — stale and schema-wrong

`app/backend/src/alembic/versions/` (6 files, all dated 2025-06, i.e. pre-SSO-rebuild). Linear chain:

```
c74c05fbe554 (initial empty)                         → base
  └ baa67b53c016 (create users table w/ account types)
      └ c199a09ccc55 (add contract, item, market group models)
          └ 7c17d7179a7d (manual add contract fields)
              └ 01e3c3fb3e96 (check after manual add)
                  └ 3fa2eefb2d7e (rename contract_type → type)   ← head
```

**Why they are wrong / cannot be trusted as the schema source of truth:**

1. **The `users` migration describes a completely different table.**
   `baa67b53c016_create_users_table_with_account_types_.py:18-46` creates `users` with
   `username`, `email`, `hashed_password`, `is_active`, `eve_character_id` **(Integer!)**,
   `user_type Enum('EVE_SSO','LOCAL', name='usertype')`, `is_admin`, `is_test_user`. The **current**
   SSO `User` model (`models/user.py:12-32`) has `character_id BigInteger unique`, `owner_hash`,
   `esi_access_token`/`esi_refresh_token`/`esi_scopes` vault columns, `last_login_at`,
   `created_at`/`updated_at` — **zero overlap** beyond the `id` PK. The test suite explicitly
   asserts the legacy columns are GONE: `tests/models/test_user_model.py` checks `username`/`email`/
   `hashed_password`/`user_type` etc. are absent (`test_legacy_user_columns_are_gone`). A
   `pg_enum usertype` type is created by this migration that the live model never uses.
2. **The contracts migration is also drifted from the model.**
   `c199a09ccc55…:22-42` creates `contracts` with `start_location_id BigInteger nullable=False`,
   `price Float`, `reward Float` and **no** `start_location_system_id`/`start_location_region_id`,
   `collateral`, `is_ship_contract` default, denormalized `*_name` columns beyond a few, the
   sort/filter indexes, etc. The live `Contract` model (`models/contracts.py:37-83`) has
   `price Numeric` **not null**, `collateral Numeric not null`, `start_location_id` **nullable**,
   `start_location_system_id`/`start_location_region_id`, and 8 indexes
   (`ix_contracts_type_status`, `_start_location_name`, `_title`, `_is_ship_contract`, `_price`,
   `_date_issued`, `_collateral`, `_volume` — contracts.py:70-80). The migration chain only ever
   created a subset and renamed `contract_type→type` (`3fa2eefb2d7e…`).
3. **`01e3c3fb3e96…:22-26` references the phantom `users.is_active` column** in a
   `batch_alter_table('users')` — a column that does not exist in the live model; this migration
   would fail against the current DB.

**M4 takeaway:** do **not** try to `alembic stamp head` the existing chain onto a live
`create_all`-built database — the recorded head does not describe the real schema. The clean path is
to **delete all six revision files, re-baseline** with a single fresh autogenerate against the live
`Base.metadata` (which env.py already imports correctly), review it by hand (autogen misses the
items in §2), and make that the `down_revision=None` root. This matches what the M3 design already
assumes ("Alembic revival stays out of scope, same as M2" — design spec:25,252). Cross-referenced by
the M3 recon which independently flagged the same: `docs/audits/m3-recon/backend-data-auth.md`
§6 ("Alembic is vestigial and stale", lines 384-404).

### 1.4 `check_alembic_version.py` — SQLite orphan

`app/backend/src/check_alembic_version.py:1-30` opens `hangar_bay_dev.db` via the **`sqlite3`**
stdlib module (check_alembic_version.py:6,15) and reads `alembic_version`. Runtime is PostgreSQL
(§5); this file is a leftover from a SQLite-era local dev DB (the `aiosqlite` dep is the matching
vestige). No production value; delete on revival.

---

## 2. Current model inventory (what a fresh baseline must emit)

Base: `Base = declarative_base()` at `db.py:8` (classic `declarative_base`, not the 2.0
`DeclarativeBase` subclass; models use typed `Mapped[...]`/`mapped_column` on top). Registered
models: `models/__init__.py:1-9` exports `User`, `Contract`, `ContractItem`, `EsiMarketGroupCache`.

Autogen handles plain columns/indexes/FKs fine. **Items an M4 baseline must eyeball because
autogenerate mis-renders or (as configured, §1.2) misses them:**

| Model / table | PK | Notable columns & defaults | Indexes | Autogen hazards |
|---|---|---|---|---|
| `User` / `users` (`models/user.py:12-32`) | `id` Integer autoincrement (user.py:15) | `character_id BigInteger unique index not null` (16); `owner_hash String(255) index` (18); `esi_access_token/refresh_token/scopes Text nullable` (19,21,22); `created_at`/`updated_at DateTime(tz) server_default func.now()`, updated_at also `onupdate=func.now()` (24-29) | implicit unique on `character_id`, index on `owner_hash` | `server_default=func.now()` renders as `sa.text('now()')`; `onupdate` is **Python-side only** (SQLAlchemy emits it at UPDATE time, NOT a DB trigger) so autogen does not and cannot represent it in DDL — a migration will silently omit the onupdate behavior, which is fine because it lives in the ORM. `BigInteger` PK-adjacent columns must not be truncated to Integer (the old migration's bug). |
| `Contract` / `contracts` (`models/contracts.py:37-83`) | `contract_id BigInteger primary_key autoincrement=False` (40) | `price Numeric not null` (42), `collateral Numeric not null` (43) — **bare `Numeric` = unbounded precision** (no scale); `is_ship_contract Boolean default=False` (63) — **Python-side `default`, NOT `server_default`**; `item_processing_status String default='PENDING_ITEMS' index=True` (64) — again Python `default`, not server; `date_*` `DateTime(timezone=True)` (53-55) | 8 explicit `Index()` in `__table_args__` (70-80): `ix_contracts_type_status` composite `(type,status)`, plus singles on `start_location_name`, `title`, `is_ship_contract`, `price`, `date_issued`, `collateral`, `volume` | `default=False`/`default='PENDING_ITEMS'` are **client-side** — the column is created **without a server default**, so a raw `INSERT` (or a future column add on a populated table) has no DB fallback. If M4 wants these enforced at the DB, the migration must add `server_default` explicitly. `Numeric` with no precision maps to Postgres `NUMERIC` (arbitrary precision) — fine, but pin precision if that matters. |
| `ContractItem` / `contract_items` (`models/contracts.py:86-114`) | `record_id BigInteger autoincrement=True` (89) | `contract_id BigInteger FK contracts.contract_id not null` (90); booleans `is_included`/`is_singleton` not null (93-94); `is_blueprint_copy Boolean nullable` (95) | 4 indexes (105-111): `_contract_id`, `_type_id`, `_is_blueprint_copy`, `_raw_quantity` | `relationship(..., cascade="all, delete-orphan")` on the parent (contracts.py:68) is ORM-level cascade, **not** a DB `ON DELETE` — the FK (contracts.py:90) has no `ondelete=`, so the DB constraint is `NO ACTION`. Autogen emits the bare FK correctly; just know the cascade is app-side. |
| `EsiMarketGroupCache` / `esi_market_group_cache` (`models/contracts.py:21-34`) | `market_group_id Integer` (24) | **self-referential FK** `parent_group_id → esi_market_group_cache.market_group_id nullable` (27); `raw_esi_response JSON not null` (29) | `ix_esi_market_group_cache_parent_group_id` (31) | **Self-referential FK** — autogen orders single-table self-FKs fine, but on a fresh baseline confirm the FK is emitted inside/after the `create_table`. `JSON` column → Postgres `JSON` (not `JSONB`); if M4 wants `JSONB` (indexable), that's a deliberate migration choice, not an autogen default. |

**General autogen caveats for the revival:**
- `compare_type` / `compare_server_default` are **off** as configured (§1.2) — turn them on or the
  first "no changes detected" will be a lie.
- No enums in the *live* models (the phantom `usertype` enum only exists in the stale
  `baa67b53c016` migration). A clean baseline emits none.
- No expression indexes, no partial indexes **yet** in the live models — but **M3 introduces the
  first partial unique index** (§4), which autogenerate renders imperfectly (see SQLA-2 note).

---

## 3. Where `create_all` / `drop_all` is called, and who depends on it

There is **exactly one runtime schema path and one test schema path**; both are `create_all`-based.
No `alembic upgrade`, `command.upgrade`, or `run_migrations` call exists anywhere in
`fastapi_app/` runtime (grep for `alembic|command.upgrade|run_migrations` over `fastapi_app/`
returns empty — confirmed).

1. **Dev startup (destructive, gated):** `main.create_db_tables()` (`main.py:128-150`).
   - Runs `Base.metadata.drop_all` then `create_all` inside `async_engine.begin()`
     (main.py:147-149).
   - **Fail-closed gate** (main.py:140): runs only when
     `settings.ENVIRONMENT == "development" AND settings.DB_RECREATE_ON_STARTUP` — else logs
     "Skipping destructive create_db_tables" and returns (main.py:141-145). `ENVIRONMENT` defaults
     to `"production"` (config.py:21) and `DB_RECREATE_ON_STARTUP` defaults to `False`
     (config.py:28), so **absent config never recreates** (secure-by-default; the P1 rider).
   - Called unconditionally from the lifespan (`main.py:45`, inside `async def lifespan`) — the gate
     is inside the function, not the call site.
   - **Import-for-registration dependency:** `main.py:27` (`from .models import contracts # This
     import is crucial for Base.metadata to find the tables.`) — a table exists for `create_all`
     iff its model module is imported so the class body registers on `Base.metadata`. This is the
     load-bearing coupling M3/M4 must preserve when adding models (`models/__init__.py` re-export +
     ensure it's in the import graph).
   - This is the **ENV-2/ENV-3 pitfall**: every backend `.py` save under `--reload` re-triggers
     this drop+recreate+re-ingest. Cited in CLAUDE.md and `docs/pitfalls/`.
2. **Tests (destructive per-test):** `tests/conftest.py` `db_session` fixture (conftest.py:46-82).
   - Per **function**: new engine on `TEST_DATABASE_URL` (conftest.py:60), `drop_all`
     (conftest.py:65), `create_all` (conftest.py:69), run test in one `session_maker.begin()`
     transaction (conftest.py:74-75), `drop_all` again (conftest.py:79), `engine.dispose()`
     (conftest.py:82). No Alembic in the test path. New models appear automatically once imported
     (conftest.py:20 `from fastapi_app.main import app` pulls the graph; conftest.py:26 also
     imports `Contract, ContractItem` explicitly).
3. **Gate regression tests:** `tests/test_create_db_tables_gate.py` asserts the gate behavior —
   skips outside development (line 12), skips when ENVIRONMENT unset (35), skips in development
   without the explicit flag (70), and **runs** in development with both set, asserting the exact
   call sequence `synced == [Base.metadata.drop_all, Base.metadata.create_all]`
   (test_create_db_tables_gate.py:119). **An M4 revival that swaps `create_all` for
   `alembic upgrade` in the dev/prod path will break these tests** — they encode the current
   mechanism, so they must be rewritten as part of the migration cutover.

**Code paths that assume `create_all` semantics** (i.e. "the schema is whatever the models say,
recreated fresh"): the entire dev loop (data re-ingested every boot — ENV-3), the whole pytest suite
(clean DB per test), and CI. **None of these tolerate incremental schema drift** — that's exactly the
gap a production Alembic story fills, because production must NOT drop+recreate. The M4 design
question is: keep `create_all` for dev+tests (fast, clean) and add Alembic **only for production**,
or unify on Alembic everywhere (slower tests, but real migration coverage). The M3 design assumes the
former (create_all for "dev + tests + CI", spec:25).

---

## 4. THE M3 DELTA (avoid these until `claude/m3-account-features` merges)

Source of truth: `docs/superpowers/specs/2026-07-17-m3-account-features-design.md` (§4) and the
7035-line plan `docs/superpowers/plans/2026-07-17-m3-account-features.md`. M3 is a **campaign branch
`claude/m3-account-features` off `origin/dev`, landing as a single PR** (design spec:30,238-240) —
NOT yet merged. Its live worktree is `.claude/worktrees/m3-account-features` (do not enter).

### 4.1 Schema M3 adds (all still on `create_all`, no Alembic — spec:25)

**3 new tables** + **1 new column** + **1 partial unique index** + several plain indexes:

- **`saved_searches`** (design spec:110-119): `id Integer PK`; `user_id Integer FK users.id
  ondelete=CASCADE, index, not null`; `name String(100) not null`; `search_parameters JSON not
  null`; `created_at`/`updated_at DateTime(tz) server_default func.now()`;
  **`UniqueConstraint(user_id, name)`**.
- **`watchlist_items`** (spec:121-132): `id Integer PK`; `user_id Integer FK users.id CASCADE,
  index, not null`; `type_id Integer not null`; `type_name String(255) not null`;
  `max_price Numeric(20,2) nullable`; `notes String(500) nullable`; timestamps;
  **`UniqueConstraint(user_id, type_id)`**.
- **`notifications`** (spec:134-151): `id Integer PK`; `user_id Integer FK users.id CASCADE, index,
  not null`; `type String(50) not null`; `message Text not null`; `contract_id BigInteger nullable
  — deliberately NOT an FK` (spec:141-144, 280: notification history must outlive pruned contract
  rows); `watch_type_id Integer nullable`; `price Numeric(20,2) nullable`;
  `is_read Boolean not null server_default false`; `created_at DateTime(tz) server_default
  func.now()`; plain `Index(user_id, is_read)` and `Index(user_id, created_at)`; **and the
  subtle one →**
- **Partial unique index on `notifications`:** `(user_id, contract_id, watch_type_id) WHERE type =
  'watchlist_match'` (spec:150). **This is the SQLA-2 subtlety** (§4.3).
- **`users` gains one column:** `watchlist_alerts_enabled Boolean not null server_default true`
  (spec:83,153).

New models live in `fastapi_app/models/account.py` (`SavedSearch`, `WatchlistItem`, `Notification`),
registered in `models/__init__.py`; `models/user.py` gains the new column (spec:82-83).

### 4.2 Config additions M3 makes (`core/config.py`)

5 new settings, all with defaults (spec:157-165): `WATCHLIST_MATCH_INTERVAL_SECONDS=900`,
`WATCHLIST_MATCH_LOCK_TTL_SECONDS=900`, `NOTIFICATION_RETENTION_DAYS=90`,
`MAX_SAVED_SEARCHES_PER_USER=100`, `MAX_WATCHLIST_ITEMS_PER_USER=200`.

### 4.3 The partial-index / `ON CONFLICT` subtlety (pitfall SQLA-2)

Recorded in user memory as "partial-index ON CONFLICT needs literal `index_where` (codex catch, now
SQLA-2)". **Status: SQLA-2 is NOT yet written into `docs/pitfalls/implementation-pitfalls.md`** — a
grep for `SQLA-2` in the pitfalls dir returns nothing (only SQLA-1 exists there, at
implementation-pitfalls.md:92). It is slated to land with the M3 PR. The mechanism (design
spec:174, Appendix A:278):

- The matcher inserts notifications with `INSERT … ON CONFLICT DO NOTHING` targeting the **partial**
  unique index. **Postgres will not infer a partial unique index** from column list alone — it
  raises `no unique or exclusion constraint matching the ON CONFLICT specification` at runtime
  unless the statement **restates the index predicate**. The mandated SQLAlchemy form:
  `on_conflict_do_nothing(index_elements=["user_id","contract_id","watch_type_id"],
  index_where=(Notification.type == "watchlist_match"))`.
- The matcher must **always populate both nullable dedup columns** (`contract_id`, `watch_type_id`)
  — Postgres treats NULLs as distinct in unique indexes, so a NULL-bearing row never conflicts and
  the dedup guarantee hollows out (spec:174).
- **Autogenerate implication for M4:** Alembic autogen renders partial/conditional indexes
  imperfectly — it will emit `op.create_index(..., postgresql_where=...)` but round-tripping the
  predicate and detecting drift on it is fragile. A hand-review of any migration touching
  `notifications` is mandatory, and `compare_type`/`compare_server_default` being off (§1.2) means
  the `server_default false`/`true` booleans won't be diffed either.

### 4.4 Other M3 surface (job + routers)

- **New APScheduler job:** `core/scheduler.py` gains `add_watchlist_matcher_job`; new
  `services/watchlist_matcher.py` (`WatchlistMatcherService`) and `services/scheduled_jobs.py`
  (`run_watchlist_matcher_job`); job registered in `main.py` lifespan after the aggregation job,
  `id="match_watchlists"` (spec:88-89,178). Own Valkey lock key `hangar-bay:watchlist-match:lock`
  (spec:171) — never the aggregation lock.
- **New routers** (bare-mounted, PROXY-1): `api/saved_searches.py`, `api/watchlist.py`,
  `api/notifications.py` under `/me/*`; new dependency `core/current_user.py`
  (`get_current_user` — session→row resolution with `character_id` equality check, spec:84,91-106);
  new `schemas/account.py`; new services `saved_search_service.py`, `watchlist_service.py`
  (spec:82-89).
- **`ESIClient` gains `resolve_names`** for add-by-name (`POST /v1/universe/ids/`, spec:202).
- **Codegen chain** regenerated: `openapi.json` + `schema.d.ts` (spec:206).

### 4.5 FILE COLLISION MAP (M4 must avoid editing these until M3 merges)

Files M3 **creates** (low collision risk — M4 just shouldn't create same-named files):
`fastapi_app/models/account.py`, `fastapi_app/core/current_user.py`,
`fastapi_app/schemas/account.py`, `fastapi_app/services/saved_search_service.py`,
`fastapi_app/services/watchlist_service.py`, `fastapi_app/services/watchlist_matcher.py`,
`fastapi_app/services/scheduled_jobs.py`, `fastapi_app/api/saved_searches.py`,
`fastapi_app/api/watchlist.py`, `fastapi_app/api/notifications.py`, plus frontend
`src/features/{saved-searches,watchlists,notifications}/` and routes/fixtures (spec:82-89,210,236).

Files M3 **modifies** — **HIGH collision risk with an Alembic-revival PR that also touches schema
wiring** (both PRs naturally converge on the same 4 backend files):

| File | M3 change | M4 (Alembic) likely change | Conflict? |
|---|---|---|---|
| `fastapi_app/models/__init__.py` | add `SavedSearch`, `WatchlistItem`, `Notification` exports (spec:82,155) | none needed for Alembic, but env.py imports it | LOW (append-only), but rebase-sensitive |
| `fastapi_app/models/user.py` | add `watchlist_alerts_enabled` column (spec:83,153) | none, unless M4 adds server_default/backfill migration | LOW |
| `fastapi_app/core/config.py` | +5 settings (spec:157-165) | M4 may add `DB_RECREATE_ON_STARTUP`-adjacent / migration flags, prod DB settings | **MEDIUM** — same file, same region |
| `fastapi_app/main.py` | +3 `include_router`, +matcher job in lifespan, +model import (spec:88,178) | **M4 swaps `create_db_tables()` call for `alembic upgrade` in lifespan** (main.py:45,128-150) | **HIGH** — both edit the lifespan + startup schema path |
| `fastapi_app/core/scheduler.py` | `add_watchlist_matcher_job` (spec:89) | none typically | LOW |
| `tests/conftest.py` | new `authed_user`/`other_user` fixtures (spec:225) | **M4 may switch fixture from `create_all` to Alembic** (conftest.py:46-82) | **HIGH** if M4 unifies tests on migrations |
| `tests/test_create_db_tables_gate.py` | none | **M4 rewrites/deletes** — it pins `create_all` (§3) | HIGH (but M3 doesn't touch it) |
| `app/frontend/web/openapi.json`, `src/lib/api/schema.d.ts` | regenerated (spec:206) | regenerated if M4 changes any schema | MEDIUM (generated — regenerate, don't merge) |

**Strong recommendation:** sequence M4's Alembic cutover of `main.py:45`/`create_db_tables` and
`conftest.py` **after** M3 merges to `dev`, or scope M4's first PR to the Alembic scaffolding only
(delete stale revisions, re-baseline autogen, fix env.py CLI tail, `pdm` script) **without** yet
rewiring the startup/test paths — that scaffolding touches only `alembic/`, `alembic.ini`,
`check_alembic_version.py`, and `pyproject.toml`, none of which M3 touches. The disruptive cutover
(replacing `create_all` in lifespan + conftest, rewriting the gate test) is the part that collides;
land it once M3's schema is in.

---

## 5. Engine / session config relevant to migrations

- **App engine:** `db.py:11-15` — `async_engine = create_async_engine(settings.DATABASE_URL,
  echo=(ENVIRONMENT=="development"), future=True)`. **No pool tuning** — no `pool_size`,
  `max_overflow`, `pool_pre_ping`, or `pool_recycle` anywhere in `fastapi_app/` (grep confirmed
  empty). Uses SQLAlchemy's default `QueuePool` (async variant) with default sizing (5 + 10
  overflow). **This is an M4 production gap to flag:** production behind a connection pooler
  (PgBouncer) or with tight DB connection limits will want explicit pool config and possibly
  `pool_pre_ping=True`. asyncpg + PgBouncer transaction-pooling also needs
  `statement_cache_size=0` / `prepared_statement_cache_size` handling — not currently set.
- **Session factory:** `db.py:17-22` — `AsyncSessionLocal = async_sessionmaker(bind=async_engine,
  class_=AsyncSession, expire_on_commit=False, autoflush=False)`. `get_db()` (db.py:30-43)
  commits on clean exit, rolls back on exception, closes in finally.
  `get_db_session_factory()` (db.py:25-27) returns the factory for background jobs (the aggregation
  job and the M3 matcher open their own sessions/engines outside requests).
- **URL formats (all asyncpg):**
  - `DATABASE_URL` — required, no default (config.py:61). `.env.example:13`:
    `postgresql+asyncpg://user:password@localhost:5432/hangar_bay_db`.
  - `DATABASE_URL_TESTS` — `Optional[PostgresDsn]`, default `None` (config.py:63); **conftest hard-
    requires it** (conftest.py:31-32 raises `ValueError` if unset). `.env.example:18`:
    `postgresql+asyncpg://user:password@localhost:5432/hangar_bay_test`. Tests run against a
    **separate real Postgres database** (conftest.py:28-34), not SQLite.
  - `CACHE_URL` / `CACHE_URL_TESTS` — Valkey/Redis (`redis://localhost:6379/0` and `…/1`,
    .env.example:14,19); irrelevant to schema but note the matcher's lock lives here.
  - `ENVIRONMENT="development"`, `DB_RECREATE_ON_STARTUP="true"` in `.env.example:4,10` (the dev
    workflow; production omits both and defaults to safe).
- **Migration-URL consideration:** `env.py` feeds the **asyncpg** `DATABASE_URL` to both offline
  and online modes (§1.2). Offline `literal_binds` SQL generation works regardless of driver, and
  the online async path (`create_async_engine` + `run_sync`) is correct. But if M4 wants a **sync**
  Alembic CLI path (common for CI/CD `alembic upgrade head` steps), it needs a `psycopg2`
  (`postgresql+psycopg2://…`) URL — `psycopg2-binary` is already a dep (pyproject.toml:8), so a
  derived sync URL or a second `DATABASE_URL_SYNC` setting is the low-friction option.
- **No `pdm` alembic script exists.** `pyproject.toml` `[tool.pdm.scripts]` (line 36) defines
  `dev`, `export-openapi`, `pytest`, `lint`, `format` — **no `migrate`/`alembic` entry**. M4 should
  add one (`alembic = {cmd="alembic", working_dir="src"}` or similar) so migrations are invoked the
  house way.

---

## Quick reference for the M4 designer

| Need | Fact | Where |
|---|---|---|
| Is Alembic wired to runtime? | No — zero `upgrade`/`run_migrations` calls in `fastapi_app/` | grep (empty) |
| Schema mechanism today | `Base.metadata.drop_all`+`create_all`, gated to dev; per-test in conftest | main.py:140-149; conftest.py:65-69 |
| Are existing revisions usable? | No — `users` migration is a totally different pre-SSO table; contracts drifted; one migration references a phantom column | versions/baa67b53c016…:18-46; …01e3c3fb3e96…:22-26 |
| Is `target_metadata` correct? | Yes — env.py imports live models; `target_metadata = Base.metadata` | env.py:31-34,62 |
| Can `alembic upgrade` run from CLI today? | No — the module-scope invocation tail was removed | env.py:156-157 |
| Autogen type/server-default diffing | OFF (commented / not passed) — turn on for revival | env.py:91,104-107 |
| First partial unique index | M3's `notifications` dedup index — needs literal `index_where` on ON CONFLICT (SQLA-2, not yet in pitfalls) | design spec:150,174 |
| Files M3+M4 both edit | `main.py`, `core/config.py`, `conftest.py`, `models/__init__.py` (+ generated client) | §4.5 |
| Pool config | None set — default QueuePool; flag for production | db.py:11-15 |
| Migration URL driver | asyncpg everywhere; `psycopg2-binary` available for a sync CLI path | env.py:122; pyproject.toml:8 |
| pdm alembic script | Does not exist — add one | pyproject.toml:36-40 |
