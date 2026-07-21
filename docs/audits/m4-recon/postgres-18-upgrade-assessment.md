# ABOUTME: Assessment of upgrading production Postgres (Render, basic-256mb, ohio) from 17 to 18 — PG18 compat/wins, driver support, Render upgrade mechanics, and a now-vs-later recommendation.
# ABOUTME: Researched 2026-07-21 while the prod DB holds only re-ingestable ESI data + empty SSO tables (recreate-at-18 is nearly free until real users exist).

# PostgreSQL 17 → 18 upgrade assessment (production, Render)

**Verdict: upgrade NOW via recreate-at-18, and fix the version-parity skew (CI and dev compose are on 16, not even 17) in the same change.** The disposability window makes today's cost ~15 minutes of ingestion downtime with zero irreplaceable data at risk; the future path is a user-visible maintenance window of up to an hour plus test-clone diligence. No breaking change in PG18 touches this stack.

## Context (verified 2026-07-21)

- Prod DB: Render managed Postgres `dpg-d9fipb3bc2fs73bam7ag-a`, plan `basic-256mb`, region ohio, **PostgreSQL 17**, created 2026-07-20. Contents: re-ingestable EVE ESI contract/market data + empty SSO account tables. The app's Alembic pre-deploy recreates the schema on a blank DB.
- `render.yaml` (this worktree, `databases:` block) pins `postgresMajorVersion: "17"`; the web service gets `DATABASE_URL` via `fromDatabase`, so a recreated instance re-wires automatically.
- CI (`.github/workflows/ci.yml`, backend job services) pins **`postgres:16`**. Dev compose (`app/backend/docker/compose.dependencies.yml`) pins **`postgres:16-alpine`**. So today's skew is already prod-17 / CI-16 / dev-16 — parity work is owed regardless of this decision.
- Locked backend deps (`app/backend/pdm.lock` at released SHA f60515c): asyncpg 0.30.0, SQLAlchemy 2.0.41, alembic 1.16.1, psycopg2-binary 2.9.12 (test-suite migration-equivalence fixture only). Python 3.14; the Dockerfile compile stage exists because locked asyncpg/httptools/uvloop publish no cp314 wheels.
- Postgres feature usage in `app/backend/src/fastapi_app/models/`: standard DDL, `BigInteger` PKs, generic `JSON` columns (`raw_esi_response`, `search_parameters`), FKs with `ondelete="CASCADE"`, `server_default=func.now()`, plain b-tree indexes, and one partial unique index (`uq_notifications_watchlist_dedup`, `postgresql_where=text("type = 'watchlist_match'")`). No triggers, no table inheritance/partitioning, no FTS/pg_trgm, no generated columns, no COPY-based loads, no nondeterministic collations.

## 1. PostgreSQL 18 — what changed (released 2025-09-25)

### Breaking/compat changes, rated against this stack

| Change | Relevance |
|---|---|
| MD5 password auth deprecated (warnings on CREATE/ALTER ROLE) | **None.** Render provisions SCRAM credentials; asyncpg and psycopg2 both speak SCRAM. |
| `initdb` enables data checksums by default | **None.** Render owns initdb. (Matters only for self-run `pg_upgrade` checksum matching — not our path.) |
| Wire protocol 3.2 / 256-bit cancel keys | **None.** Opt-in; asyncpg still negotiates protocol 3.0, which PG18 fully supports. |
| `VACUUM`/`ANALYZE` now recurse into inheritance children by default | **None.** No inheritance or partitioned tables. |
| `COPY FROM` CSV `\.` EOF-marker change | **None.** No CSV COPY anywhere in the app. |
| AFTER triggers run as the role active at queue time | **None.** No triggers. |
| PK/FK collation determinism requirement (pg_dump/pg_upgrade fail otherwise) | **None.** Default deterministic collations throughout. |
| FTS/pg_trgm indexes need reindex after upgrade on non-libc-collation clusters | **None.** No FTS or trigram indexes (`ix_contracts_title` is a plain b-tree). |
| Removed catalog columns (`pg_stat_wal.*`, `pg_backend_memory_contexts.parent`), rule privileges, old configure options | **None.** Nothing queries these. |

**Net: no identified PG18 incompatibility affects Hangar Bay.** The partial unique index (`postgresql_where`), `ON CONFLICT` dedup, JSON columns, and FK `ondelete` are all untouched by 18.

### Headline wins, rated for a small FastAPI+SQLAlchemy app on a 256MB instance

- **Async I/O subsystem** (`io_method`; seq scans, bitmap heap scans, vacuum; up to 3x on reads) — **moderate**. The contract-browse endpoints are read-heavy; some benefit likely, but at current data volume (tens of MB of contracts) most working set is cached, so don't expect visible latency change. Render controls the server config; whether they enable `io_uring` vs the `worker` default is theirs.
- **B-tree skip scan** — **small but real**. We index heavily single-column plus `ix_contracts_type_status (type, status)`; queries filtering `status` without `type` can now use that composite index.
- **Preserved planner statistics across `pg_upgrade`** — **relevant to future upgrades** (18→19 won't start with a cold planner). An argument for getting onto 18 before the DB matters.
- **`uuidv7()`** — unused today (integer PKs); nice option for future public-facing IDs.
- **Virtual generated columns (new default)** — unused; see SQLAlchemy note below.
- **`RETURNING old/new`, temporal constraints, server-side OAuth auth, `EXPLAIN` buffers-by-default** — unused / dev niceties only.

Sources: [PG18 release notes](https://www.postgresql.org/docs/18/release-18.html), [PG18 announcement](https://www.postgresql.org/about/news/postgresql-18-released-3142/).

## 2. Driver/ORM compatibility

- **asyncpg 0.30.0 (locked)** — no known PG18 incompatibility found (searched GitHub issues/releases). It predates PG18, so the *official* "PostgreSQL 9.5–18" support claim starts at **asyncpg 0.31.0 (released 2025-11-24)**. Since asyncpg speaks protocol 3.0 and PG18 changed nothing on that path, 0.30.0 against PG18 is low-risk but formally unsupported. **Recommended (not prerequisite): bump to 0.31.0** — it also ships **cp314 wheels** (including free-threading), which removes asyncpg from the Dockerfile's compile-from-source rationale (httptools/uvloop are separate questions; the `build-essential` stage stays until all three have cp314 wheels). Note 0.31.0 drops Python ≤3.8 — irrelevant on 3.14.
- **SQLAlchemy 2.0.41** — works against PG18. The only PG18-aware dialect behavior (rendering `Computed` columns as VIRTUAL by default) landed in **SQLAlchemy 2.1**; on 2.0 a `Computed` without `persisted=` renders `STORED`. We define no generated columns, so this is a non-issue. No bump required.
- **alembic 1.16.1** — no PG18-specific issues found; our migrations use standard DDL + the partial index, all fine on 18.
- **psycopg2-binary 2.9.12** — libpq-based, PG-version agnostic for our usage; only exercised by the test-suite migration-equivalence fixture against local/CI Postgres. No action.

## 3. Render specifics

- **PG18 available since 2025-11-13** and is the **default for new databases** ([changelog](https://render.com/changelog/postgresql-18-is-now-available-for-render-postgres-databases)); the create API accepts version 18.
- **In-place major upgrade exists** for existing instances: triggered from the database's Info page in the dashboard; "upgrading your database requires downtime"; "usually takes less than one hour"; same credentials/connection string afterward; a failed attempt leaves the DB on its original version. Render **strongly recommends a test upgrade on a clone first** — and cloning requires PITR, which legacy/low-tier instances may gain only at a later maintenance window ([upgrade docs](https://render.com/docs/postgresql-upgrading)). The internal mechanism (pg_upgrade vs dump/restore) is not documented.
- **Blueprint interaction:** `postgresMajorVersion` is **immutable after creation** in the blueprint spec. So the yaml `"17"` cannot be flipped to `"18"` to upgrade the existing instance; an in-place dashboard upgrade would leave render.yaml lying about prod. The recreate path is: delete the instance, set `postgresMajorVersion: "18"` in render.yaml, sync — `fromDatabase` re-wires `DATABASE_URL` into the API service automatically (new instance = new host/credentials, but nothing else references them).

## 4. Options

### A. Upgrade NOW — recreate at 18 (recommended)

Cost: ~15–30 minutes end-to-end, during which the API serves errors/empty data. Steps: delete `dpg-d9fipb3bc2fs73bam7ag-a` → bump render.yaml to `"18"` → blueprint sync creates the new instance → redeploy runs Alembic pre-deploy on the blank DB → scheduler re-ingests ESI data within minutes. Nothing irreplaceable exists to lose; empty SSO tables recreate identically. Risks: essentially the asyncpg-0.30-formal-support gap (low; mitigate by bumping to 0.31.0 in the same milestone) and any surprise in blueprint recreate mechanics (see unknowns).

### B. Upgrade LATER — Render in-place

Cost: a scheduled maintenance window with up to ~1h of downtime **for real users**, plus a test upgrade on a clone (PITR-dependent on this plan — unverified), plus the render.yaml drift problem (yaml stays `"17"` forever or gets a cosmetic-only edit). Every month of delay grows the data and the caution required. PG17 is supported until Nov 2029, so there is no forcing function — just a strictly worsening cost curve.

### C. Stay on 17

Defensible (17 is EOL 2029), but: Render's default is 18 (future instances/clones will skew), we forgo preserved-statistics for the *next* upgrade, and the parity work must happen anyway. Choosing C converts today's free upgrade into option B in a year or two.

### Parity work (required under every option)

- `.github/workflows/ci.yml` backend job: `postgres:16` → the prod major (`postgres:18` under A).
- `app/backend/docker/compose.dependencies.yml`: `postgres:16-alpine` → `postgres:18-alpine`.
- `render.yaml`: `postgresMajorVersion: "18"` (under A; keep truthful under B/C).
- Optional, recommended: asyncpg `>=0.31.0` bump + lock refresh; revisit the Dockerfile compile-stage comment (asyncpg no longer needs it; httptools/uvloop verification is a separate check).

## 5. Unknowns / could not verify

1. **Render's in-place upgrade internals** (pg_upgrade vs dump/restore) — undocumented; only downtime bounds are published.
2. **Whether `basic-256mb` supports PITR-based cloning today** (prereq for Render's recommended test-upgrade rehearsal on path B).
3. **Blueprint behavior when an immutable `postgresMajorVersion` changes on an existing resource** (ignored vs sync error) — the recreate path should delete the instance first rather than rely on sync semantics.
4. **asyncpg 0.30.0 vs PG18 in anger** — no known issues found, but 0.30.0 predates PG18 and the official support claim begins at 0.31.0; our CI would exercise it only after the CI image bump.
5. One WebFetch of the asyncpg releases page returned inconsistent dates; the load-bearing facts (0.31.0 released 2025-11-24, PG 9.5–18 support, cp314 wheels) were cross-checked against PyPI.

Sources: [PG18 release notes](https://www.postgresql.org/docs/18/release-18.html) · [PG18 announcement](https://www.postgresql.org/about/news/postgresql-18-released-3142/) · [Render: Upgrading Your Render Postgres Version](https://render.com/docs/postgresql-upgrading) · [Render changelog: PostgreSQL 18 available](https://render.com/changelog/postgresql-18-is-now-available-for-render-postgres-databases) · [asyncpg on PyPI](https://pypi.org/project/asyncpg/) · [asyncpg releases](https://github.com/MagicStack/asyncpg/releases) · [SQLAlchemy 2.1 PostgreSQL dialect docs (Computed/VIRTUAL)](https://docs.sqlalchemy.org/en/21/dialects/postgresql.html)
