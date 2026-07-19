# ABOUTME: M4 Phase 3 review — Round A (spec fidelity). Clause-by-clause walk of design spec §§4–8 against the Phase-3 diff.
# ABOUTME: Verdict: NEAR-CLEAN. One P2 (equivalence guard blind to server-default drift) + one P3 (.env.example omits pure-default ESI rows).

**Reviewer lens:** Round A — spec fidelity. Design spec `docs/superpowers/specs/2026-07-18-m4-production-readiness-design.md` §§4–8, walked clause by clause against `git diff origin/dev...HEAD` on branch `claude/m4-phase3-prod-hardening`.
**Date:** 2026-07-19
**Diff reviewed:** commits `33b8161..84b2bfb` (Tasks 3.0–3.12 Step 1). Excludes plan/audit docs per the review contract.

## Verdict

**NEAR-CLEAN.** The implementation is a faithful, careful realization of spec §§4–8. Every binding clause I checked holds. Two findings, neither a PR blocker:

- **A1 (P2)** — the migration↔metadata equivalence guard is configured without `compare_server_default`, so it is blind to server-default drift — exactly the autogen-hazard class §5 flags for hand review.
- **A2 (P3)** — the `.env.example` production block omits the pure-default ESI rows (`ESI_BASE_URL`, `ESI_TIMEOUT`, the three SSO endpoint URLs) that §6's inventory lists as "defaults." Trivial/optional.

Every Task 3.1–3.11 has a corresponding commit; nothing was silently skipped.

---

## Clause-by-clause

### §4 Production topology
- **Single-worker constraint untouched.** The diff does not touch the Dockerfile CMD or any worker count; the `--workers 1` constraint (Phase 1) is unmodified. PASS.
- **Driver-scheme normalization.** `core/config.py` gains a `mode="before"` `field_validator` on `DATABASE_URL` rewriting `postgresql://` → `postgresql+asyncpg://` (config.py:78–85). Idempotent for already-qualified URLs. Covers both the app engine (`db.py:12`) and Alembic's CLI path (env.py reads the same `settings.DATABASE_URL`). Tested both directions in `test_config.py`. PASS.
- **`/ready` as the health gate.** New bare-mounted `api/ops.py` router; `main.py:249` includes it. Returns a `checks` dict with `commit`, `db`, `cache`, `last_ingest_age_seconds`, `last_ingest_outcome`, `data_stale`; 503 only when db or cache fails. PASS (detail under §8).
- **Pool tuning covers the shared engine (§4/§5 dual-engine requirement).** `db.py:15–17` adds `pool_pre_ping=True`, `pool_size=5`, `max_overflow=5`; the per-run second engine in aggregation is deleted (see §5), so there is now exactly one tuned engine. PASS.

### §5 Schema management — Alembic revival
- **Single baseline, generated once against a blank DB.** One revision `3aca702a74e3_baseline.py`, `down_revision = None`. Structure matches a from-blank autogen (all `create_table`/`create_index`, no ALTERs). PASS.
- **Immutability posture.** Nothing regenerates or mutates the baseline; env.py's model-import line extended to `user, contracts, account` so future autogen sees the full metadata. PASS.
- **conftest stays on `create_all`.** `db_session` fixture (conftest.py:48–84) still does `Base.metadata.drop_all/create_all`; the baseline is exercised only by the new session-scoped `blank_migrated_sync_connection` fixture against a disposable `m4_equiv_check` DB. PASS.
- **Autogen hazards — hand-review verified against the models:**
  - Partial index `uq_notifications_watchlist_dedup`: migration carries `postgresql_where=sa.text("type = 'watchlist_match'")` (baseline.py:179), predicate char-for-char equal to `account.py:99`. SQLA-2 respected. PASS.
  - No invented server defaults for `is_ship_contract` / `item_processing_status`: both are `nullable=False` with NO `server_default` in the migration (baseline.py:102–103), matching the Python-side `default=` on the model (`contracts.py:64–65`). PASS.
  - `ondelete` shapes: account tables `ondelete='CASCADE'` (baseline.py:173/187/201) matching `account.py`; `contract_items` FK has NO ondelete (baseline.py:156), matching the app-side `cascade="all, delete-orphan"` relationship. PASS.
  - Self-referential FK on `esi_market_group_cache.parent_group_id` present (baseline.py:123). PASS.
  - `users.watchlist_alerts_enabled` server default preserved: `server_default=sa.text('true')` (baseline.py:136) matching `user.py:23–25`. Also `notifications.is_read` `false`, and all `created_at`/`updated_at` `now()` defaults are present and correct.
- **The equivalence-guard test's real strength → see Finding A1.** The guard catches table/column add-remove, nullability, **type** (`compare_type` defaults True), indexes, unique constraints, and FK presence — but is **blind to server-default drift** because `compare_server_default` defaults False and the guard does not enable it. env.py's own CLI autogen path sets `compare_server_default=True`; the guard does not.

### §6 Configuration & secrets
- **Env inventory completeness incl. M3 fields.** All five M3 Settings fields (`MAX_SAVED_SEARCHES_PER_USER`, `MAX_WATCHLIST_ITEMS_PER_USER`, `WATCHLIST_MATCH_INTERVAL_SECONDS`, `WATCHLIST_MATCH_LOCK_TTL_SECONDS`, `NOTIFICATION_RETENTION_DAYS`) are present in `core/config.py:66–70`, added to the spec §6 table, and documented in the `.env.example` prod block. `METRICS_TOKEN` added (config.py:54). PASS (minor gap → A2).
- **SSO two-tier semantics — exactly as specified, incl. D-10.** `validate_sso_configuration` (main.py:199–236):
  - Trio wholly empty → warn in EVERY environment, continue (tier a). ✓
  - Production + any non-empty proper subset of the trio → `RuntimeError` naming the missing fields. ✓
  - Production + any trio member set while `localhost` in `ESI_SSO_CALLBACK_URL`/`FRONTEND_ORIGIN` → `RuntimeError` naming the URL field. ✓
  - Outside production: partial trio warns; localhost is **not evaluated at all** (the loop is inside `if ENVIRONMENT == "production"`), so a correctly-configured dev boot with `https://localhost:5173/...` is silent — D-10 honored, pinned by `test_sso_dev_localhost_urls_are_silent_when_fully_configured`. ✓
  - Lifespan call site updated (`main.py:47`); wiring test asserts the rename didn't orphan startup. PASS.
- **`DATABASE_URL[:30]` log line really gone.** The `logger.info(f"Creating database engine with URL: {...DATABASE_URL[:30]}...")` line and the entire per-run engine block are deleted from `background_aggregation.py`; aggregation now uses `AsyncSessionLocal` (bg_agg:20, 156). I read every module that consumes `DATABASE_URL`/`CACHE_URL` (`background_aggregation.py`, `config.py`, `db.py`, `main.py`, `core/cache.py`, `core/dependencies.py`, `core/scheduler.py`) — none logs a URL or a URL fragment. `scheduler.py:20` `urlparse(CACHE_URL)` is used only to build the jobstore, never logged. A regression test pins both behaviors (`test_run_aggregation_reuses_app_session_factory_and_never_logs_database_url`). PASS. *(Caveat: the repo-wide grep could not run — the Bash safety classifier was intermittently unavailable this session — but the module-by-module read is exhaustive for the URL-consuming surface.)*

### §7 CD pipeline — `live-smoke-prod` Playwright project
- **Project name** `live-smoke-prod` matches `deploy.yml`'s `--project=live-smoke-prod` (playwright.config.ts:40). ✓
- **Env-driven origin** `baseURL: process.env.E2E_PROD_BASE_URL`; `deploy.yml` sets `E2E_PROD_BASE_URL=${{ vars.PROD_ORIGIN }}`. ✓
- **Real certs enforced** `ignoreHTTPSErrors: false`. ✓
- **No webServer for the prod lane** `webServer: process.env.E2E_PROD_BASE_URL ? undefined : {…}` (playwright.config.ts:46). The project is added only when `E2E_PROD_BASE_URL` is set (empty spread otherwise), so normal `npm run e2e` is unchanged and the fixture lanes still boot the dev server. PASS.

### §8 Observability
- **Freshness — checked-ok counting incl. 304s.** Region loop increments `regions_ok` on both fetch success (bg_agg:170) AND `ESINotModifiedError` (bg_agg:175); generic fetch errors increment `regions_failed` (bg_agg:178). PASS.
- **Outcome derivation.** `_record_run_outcome` (bg_agg:230–233): `forced_failure` → `failure`; else `success` iff `failed==0 and ok>0`, `partial` iff `ok>0`, else `failure`. Matches §8.2's success/partial/failure definition. Success/failure recording both happen INSIDE the lock context (bg_agg:198/202, before `_concurrency_lock` releases); the forced-failure path re-raises after recording. PASS.
- **`last_success_at` preservation.** `last_success_at = now if outcome in ("success","partial") else prior_success`, where `prior_success` is read back from the existing key (bg_agg:235–242). Failure records preserve the prior success timestamp; the gauge advances only on success/partial. Pinned by `test_freshness_failure_when_commit_raises`. PASS.
- **`/ready` field names + staleness formula + 503 semantics + never-fail-on-staleness.**
  - Fields `last_ingest_age_seconds`, `last_ingest_outcome`, `data_stale`, plus `db`/`cache`/`commit` (ops.py:302–307). ✓
  - Staleness: `data_stale = age is None or age > 2 * AGGREGATION_SCHEDULER_INTERVAL_SECONDS` — never-ingested is stale; matches §8.2. ✓
  - 503 set only when `healthy` flips (db or cache error), incl. the `asyncio.timeout` hung-probe path; staleness never touches `healthy`. ✓
  - Both timeouts are `READINESS_CHECK_TIMEOUT_SECONDS = 2.0` (ops.py:266), tested for the hung-db and hung-cache paths. PASS.
- **`/metrics` gate tiers.** `instrumentator.instrument(app)` kept, `.expose()` removed; custom `@app.get("/metrics")` (main.py:152–159) is open when `METRICS_TOKEN` empty, requires `Authorization: Bearer <token>` when set. Matches §8.3. PASS.
- **`/cache-test` really gone.** Route deleted from `main.py`; `test_cache_test_endpoint_is_gone` asserts 404. No `cache_test`/`cache-test` reference survives in the source I read. PASS.

---

## Findings

### A1 (P2) — Equivalence guard is blind to server-default drift
**File:** `app/backend/src/fastapi_app/tests/test_migrations.py:23` (guard) + `app/backend/src/fastapi_app/tests/conftest.py:238` (fixture).
**Defect:** The guard configures `MigrationContext.configure(blank_migrated_sync_connection)` with no `opts`. Confirmed against the installed Alembic (`runtime/migration.py:180–182`): `compare_type` defaults **True** but `compare_server_default` defaults **False**, and `_compare_server_default` short-circuits to "no diff" when the flag is off (`migration.py:731`, invoked from `autogenerate/compare.py:1169`). So the guard cannot see a server-default mismatch between a migration and the models — precisely the autogen-hazard class spec §5 calls out for hand review (`users.watchlist_alerts_enabled`, `notifications.is_read`, the `now()` timestamp defaults). env.py's CLI autogen path sets `compare_server_default=True`; the guard that is supposed to be the anti-drift net does not.
**Failure scenario:** A future model changes `watchlist_alerts_enabled`'s `server_default` (or a later migration adds a column whose server default differs from the model). `compare_metadata` returns `[]`, `test_migrated_schema_matches_model_metadata` stays green, and production schema silently diverges from the models — the exact "drift accumulates silently" outcome §5's guard exists to prevent.
**Fix:** `MigrationContext.configure(conn, opts={"compare_type": True, "compare_server_default": True})` to match env.py. **Honest caveat:** `compare_server_default` carries a real false-positive risk (reflection renders `now()`/`true` differently than the model), which is why Alembic defaults it off — but the current baseline was generated under env.py's `compare_server_default=True` and hand-reviewed clean, so enabling it in the guard should be diff-free today. Not a current bug (the baseline matches the models); a latent gap in the guarantee. Not a PR blocker on its own.

### A2 (P3) — `.env.example` prod block omits the pure-default ESI rows
**File:** `app/backend/.env.example` (production section, diff lines 10–38).
**Defect:** Task 3.11 says the block documents "every §6-inventory var." §6's table includes an `ESI_BASE_URL/ESI_TIMEOUT/SSO URLs → defaults` row; the prod block lists `ESI_USER_AGENT`, `ESI_CLIENT_ID/SECRET`, and `ESI_SSO_CALLBACK_URL` but omits `ESI_BASE_URL`, `ESI_TIMEOUT`, `ESI_SSO_AUTHORIZE_URL`, `ESI_SSO_TOKEN_URL`, `ESI_SSO_JWKS_URI`.
**Failure scenario:** None operational — these are unchanging defaults already documented in the non-prod portion of `.env.example`. A deployer skimming only the prod block wouldn't see them, but they need no prod override. Purely a documentation-completeness nit; arguably intentional (the block covers everything that needs a *non-default* prod value). Fix only if strict §6 parity is wanted.

---

## Task-commit coverage
Every plan Task has a commit (git log `origin/dev..HEAD`): 3.0 (`33b8161`+`39d5ead`), 3.1 (`2973f66`), 3.2 (`9379b4f`), 3.3 (`20e42cd`), 3.4 (`a8020f2`), 3.5+3.6 (`42ade48`), 3.7 (`5e95a57`), 3.8 (`d175b4b`), 3.9 (`e9e1ab5`), 3.10 (`ca405d6`), 3.11 (`343c6a2`), 3.12 Step 1 (`84b2bfb`). Nothing silently skipped. `psycopg2-binary` is a declared runtime dep (pyproject.toml:8), so the sync `postgresql+psycopg2` equivalence fixture will import in CI.

## Limits of this pass
The Bash safety classifier was intermittently unavailable, so a single repo-wide `grep` sweep for URL-fragment logging could not be captured as one command. I compensated by reading every module in the `DATABASE_URL`/`CACHE_URL` consuming surface directly; the finding set above reflects that exhaustive read, not a grep shortcut. This is a static-analysis pass only — no tests were executed (per the review contract).
