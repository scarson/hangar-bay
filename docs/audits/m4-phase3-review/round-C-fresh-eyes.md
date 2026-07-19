# M4 Phase 3 — Round C review (fresh eyes, full diff)

ABOUTME: Round-C adversarial review of the M4 Phase-3 production-hardening branch.
ABOUTME: Fresh-eyes cold read of the complete phase diff (git diff origin/dev...HEAD), static analysis only.

- **Branch:** `claude/m4-phase3-prod-hardening`, off dev @ `6885b67`
- **Commits reviewed:** `33b8161`..`84b2bfb` (13 commits; plan/audit docs excluded per scope)
- **Method:** static analysis. Did NOT run `pdm run dev`, `pdm run pytest`, or any dev server (ENV-2/ENV-3, orchestrator-serialized test DB). Read no `.env`.
- **Verdict:** NOT clean — 1 × P1 (CI-blocking), 2 × P3 (hardening / test-rigor notes).

---

## P1 — Stale OpenAPI client chain will fail the Phase-1 `openapi-drift` CI gate

**Files:** `app/frontend/web/openapi.json` (stale), `app/frontend/web/src/lib/api/schema.d.ts` (stale) vs `app/backend/src/fastapi_app/api/ops.py:22`, `app/backend/src/fastapi_app/main.py:152`; gate at `.github/workflows/ci.yml:128-158`.

**Defect:** Phase 3 changes the API's public route surface but the committed OpenAPI client artifacts were never regenerated, so the `openapi-drift` CI job (added in Phase 1, runs on every `pull_request` with no branch filter) will diff non-empty and fail, blocking the PR.

The current backend produces a schema that differs from the committed files in three ways:
1. `api/ops.py:22` adds `@router.get("/ready")` with **no** `include_in_schema=False` → `/ready` is IN the exported schema. The committed `openapi.json` has **no** `/ready` (the file is alphabetically key-sorted and ends at `/metrics` on line 2233/2249; `/ready` would sort after `/metrics` and is absent).
2. `main.py:152` replaces the instrumentator's `.expose()` with `@app.get("/metrics", include_in_schema=False)` → `/metrics` DROPS out of the exported schema. The committed `openapi.json:2233-2249` still carries the old in-schema `/metrics` (`"operationId": "metrics_metrics_get"`, `"description": "Endpoint that serves Prometheus metrics."`).
3. Task 3.6 deletes `/cache-test`, but the committed `openapi.json:1016` still has it (`"summary": "Cache Test"`, tag `Development/Test`).

**Failure scenario:** The PR opens against `dev`. The `openapi-drift` job runs `pdm run export-openapi` (backend, current code) then `npm run generate:api`, then `git diff --exit-code -- app/frontend/web/openapi.json app/frontend/web/src/lib/api/schema.d.ts` (`ci.yml:157`). The freshly-exported schema adds `/ready`, removes in-schema `/metrics`, and removes `/cache-test`; the committed files have the opposite. The diff is non-empty → the step prints `::error::openapi.json / schema.d.ts are stale …` and exits 1. CI is red; the PR cannot merge on green. Note `npx tsc -b` in the `frontend` job does NOT catch this (the SPA consumes neither `/ready` nor `/metrics`, so `schema.d.ts` still type-checks) — the dedicated drift job is the only guard, and it was built for exactly this.

**Fix:** `cd app/backend && pdm run export-openapi` then `cd ../frontend/web && npm run generate:api`, and commit the regenerated `openapi.json` + `schema.d.ts` in this branch. (The plan's per-task steps for 3.4/3.5/3.6 and the Task 3.12 local gate omit the export→regenerate chain, which is why this slipped.)

---

## P3 — `/metrics` bearer token compared with non-constant-time `!=`

**File:** `app/backend/src/fastapi_app/main.py:157`

**Defect:** `request.headers.get("authorization") != f"Bearer {token}"` uses Python's short-circuiting string inequality; the comparison is not constant-time and leaks timing on a per-byte basis.

**Failure scenario:** A network attacker who can measure response latency against `/metrics` could, in principle, recover `METRICS_TOKEN` byte-by-byte via a timing side channel. In practice this is low severity — spec §8.3 does not mandate constant-time comparison, network jitter dominates the signal, and the token gates only a Prometheus scrape (no user data). But given the project's otherwise careful security posture (fencing tokens, fail-closed gates), `hmac.compare_digest(request.headers.get("authorization") or "", f"Bearer {token}")` is the idiomatic hardening. Note only — not a blocker.

---

## P3 — Migration↔metadata equivalence guard is weaker than the migration config it protects

**Files:** `app/backend/src/fastapi_app/tests/test_migrations.py:24`, `app/backend/src/fastapi_app/tests/conftest.py:238-268`

**Defect:** `test_migrated_schema_matches_model_metadata` builds its context with `MigrationContext.configure(blank_migrated_sync_connection)` and no opts, so `compare_metadata` runs with `compare_type=False` and `compare_server_default=False` (the SQLAlchemy defaults). Meanwhile `alembic/env.py:40-48` (`do_run_migrations`) sets both to `True`. The automated guard therefore catches structural drift (added/removed tables, columns, indexes, unique constraints, nullability) but NOT column-type drift or server-default drift.

**Failure scenario:** If a future model change alters a column's type or `server_default` without a matching migration edit, `alembic revision --autogenerate` would emit an op, but this equivalence test stays green — the drift is invisible to the guard and relies entirely on the Task 3.9 Step-3 manual hand-review. Closing the gap: `MigrationContext.configure(conn, opts={"compare_type": True, "compare_server_default": True})`. Note only — the baseline (`3aca702a74e3_baseline.py`) is correct today (partial index `uq_notifications_watchlist_dedup` carries `postgresql_where`, and the `now()`/`true`/`false` server defaults are present), so nothing is currently mis-guarded.

---

## Areas traced and found CLEAN under this lens

- **`run_aggregation` try/except nesting & outcome recording (`background_aggregation.py:132-253`).** Traced every path the prompt named:
  - *lock-not-acquired* → `ConcurrencyLockError` raised at context entry (before `yield`), bypasses the inner try, caught by the outer `except ConcurrencyLockError` → **no** freshness record (correct: a skipped run is not a run).
  - *esi context-manager failure* → inner `except` records `forced_failure=True` once, re-raises → outer generic `except` logs + returns.
  - *region-loop exception* → each iteration's own `try/except` counts it as `regions_failed` and does not propagate; the run continues to the single success-site record.
  - *commit failure* → inner `except` records `forced_failure` once, re-raises.
  - *recording failure* → `_record_run_outcome` wraps its whole body in `try/except Exception: logger.warning(...)`, so it cannot raise through `Exception`; critically this means the success-site call can never trip the inner `except` into a second (forced-failure) record. Exactly one record per run.
  - *lock-release failure* → happens in `_concurrency_lock` `finally` after the body already recorded; propagates to the outer `except` with no re-record.
  - `_record_run_outcome` can only propagate `BaseException` (e.g. `CancelledError`), which is the correct behavior. `last_success_at` preservation on failure and advance-on-success/partial match spec §8.2 exactly.
- **`test_freshness_failure_when_commit_raises` honesty (`test_background_aggregation.py:485-536`).** The `boom_factory` overrides only `session.commit`; `_process_contracts` runs for real and production reaches the real `await db_session.commit()` site (`background_aggregation.py:193`), which raises → genuinely exercises the forced-failure path. Not a mocked-behavior test.
- **`/ready` ISO parsing & timezone (`ops.py:36-60` vs writer `background_aggregation.py:234-249`).** Writer emits `datetime.now(timezone.utc).isoformat()` (aware, `+00:00`); reader `datetime.fromisoformat(...)` yields an aware datetime and subtracts from `datetime.now(timezone.utc)` → both aware, age is positive, no naive/aware `TypeError` on the happy path; a malformed/naive stored value is caught by `except (ValueError, TypeError): pass` → `age=None`, `data_stale=True`. Age sign and the `> 2 × interval` staleness threshold match spec §8.2.
- **`asyncio.timeout` usage (`ops.py:30, 38`).** 3.11+ API (target 3.14); `TimeoutError` is caught by `except Exception`; a hung DB/cache probe → 503 with the component flagged. Cache probe shares one budget across `ping`+`get`; on `get` failure `freshness` stays `None` and degrades gracefully.
- **`/ready` info disclosure.** Returns only `commit` (deliberate per spec/release-verification), `db`/`cache` = `ok|error`, ingest outcome/age, `data_stale`. No secrets, URLs, or exception detail leak.
- **`validate_sso_configuration` (`main.py:199-236`).** Two-tier matrix matches spec §6 and D-10: wholly-empty trio warns in every env; production partial-trio or localhost-in-URL raises naming the fields; dev partial warns; dev localhost with full trio is silent. `getattr(settings, field)` targets are plain `str` (config.py:43-44) — no `None`-membership hazard.
- **Lifespan wiring test (`test_create_db_tables_gate.py:237-256`).** `validate_sso_configuration()` is the 2nd lifespan call (`main.py:47`), before every patched initializer, so the production+partial config aborts on the real call site; patch set is adequate for the assertion.
- **alembic `env.py` (`env.py:73-87`) + baseline + equivalence fixture.** Import-safe tail guarded by `_running_under_alembic()` (pinned by `test_migrations.py:6-13`); the model-import line correctly lists `user, contracts, account` (matches D-9). `blank_migrated_sync_connection` (`conftest.py:238-268`) cleans up its scratch DB in `finally` even on upgrade failure (`DROP DATABASE … WITH (FORCE)`), and `psycopg2-binary` is a declared dependency (`pyproject.toml:8`) so the sync driver resolves.
- **`/metrics` gate correctness (`main.py:152-159`).** Empty token → open (dev); set token → exact `Bearer <token>` required else 401. `instrumentator.instrument(app)` retained without `.expose()` is correct — metrics are still collected by the middleware and served by the manual route; the custom gauge is import-registered.
- **`DATABASE_URL` normalization (`config.py:78-85`).** `postgresql://` → `postgresql+asyncpg://`; `postgresql+asyncpg://` and other explicit `postgresql+<driver>://` schemes pass through unchanged. (Render injects `postgresql://` per the docs verification, so `postgres://` — unhandled — is out of scope.)
- **`playwright.config.ts` prod lane (`:43-65`).** `live-smoke-prod` project and the `webServer: undefined` gate are both keyed on `E2E_PROD_BASE_URL`; fixture lanes unchanged; `ignoreHTTPSErrors:false` for prod.
- **`.env.example` production block (`:45-73`).** Commented, no secret values, correct generation one-liners.
