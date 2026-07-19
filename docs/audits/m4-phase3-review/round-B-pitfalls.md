# M4 Phase 3 — Round B Review (Pitfalls Checklists)

ABOUTME: Round-B code review of the M4 Phase 3 production-hardening branch against the
implementation-pitfalls / testing-pitfalls checklists. Static analysis only (no dev server, no pytest).

**Reviewer lens:** every checklist item in `implementation-pitfalls.md` (§1.C, §2.C, §3.C, §4.C,
§5.C, §Orchestration.C) and `testing-pitfalls.md` (TEST-2 weakened-assertions, TEST-6 glob,
TEST-7 retries n/a, §1 pristine output, §5 concurrency, §3 ENV traps incl. ENV-4/ENV-6).

**Diff reviewed:** `git diff origin/dev...HEAD` excluding `docs/superpowers/plans/*` and
`docs/audits/*`. Commit series `33b8161..84b2bfb` (13 commits).

**Bottom line:** No P1 or P2 defects. The Phase-3 code is solid against this lens — the
freshness/outcome semantics match spec §8.2, the SSO two-tier diagnostic matches spec §6, the
DB-URL normalization matches DEPLOY-1, the baseline migration restates the partial-index predicate
(SQLA-2), and the reworked SSO test matrix strictly expands coverage under a spec-sanctioned
contract change. Five P3 cleanliness/test-hygiene notes follow.

---

## Findings

### P3-1 — /ready DB-failure cleanup path is unexercised by tests and can emit post-response error-log noise
- **file:** `app/backend/src/fastapi_app/tests/api/test_ops.py:72` (and `:90`); interacts with
  `app/backend/src/fastapi_app/api/ops.py:29-35` and `app/backend/src/fastapi_app/db.py:41`.
- **Defect:** `test_ready_503_when_db_down` / `test_ready_503_when_db_hangs` override `get_db` with a
  plain object / lambda (`_BoomDB()`, `_HangDB()`) — not the real generator dependency — so the real
  request-scoped session's post-yield commit()/rollback()/close() cleanup is never exercised
  against a failed DB.
- **Failure scenario:** In production with Postgres actually down, /ready swallows the SELECT 1
  exception (ops.py line 33 `except Exception`), so the real get_db (db.py) resumes past its
  yield into `await session.commit()` on a connection-failed/cancelled session — which raises
  PendingRollbackError, is caught and re-raised by get_db. Because FastAPI >=0.106 (pinned 0.139)
  runs dependency-with-yield cleanup AFTER the response is sent, the client still receives the
  correct 503 with {"db":"error",...}, but the re-raised exception surfaces server-side as an
  unhandled-in-ASGI error log on every probe while the DB is down. Client-visible contract is
  preserved; the gap is (a) untested real-dependency cleanup and (b) latent log noise. Confirmed:
  the test override is a non-generator; the runtime log-noise consequence is plausible but not
  empirically verifiable here (no pytest permitted).

### P3-2 — /metrics bearer token compared with != rather than a constant-time compare
- **file:** `app/backend/src/fastapi_app/main.py:157`
- **Defect:** `request.headers.get("authorization") != f"Bearer {token}"` is a short-circuiting
  string compare, not `secrets.compare_digest`.
- **Failure scenario:** A byte-by-byte timing side-channel could in principle leak METRICS_TOKEN.
  Low real risk (high-entropy token_urlsafe(32) token, HTTP jitter dwarfs the signal, low-value
  endpoint), but this is an auth check on a security-sensitive surface where the repo values
  defense-in-depth; `secrets.compare_digest` is the idiomatic fix.

### P3-3 — Freshness record write is not gated by lock ownership (TTL-expiry clobber window)
- **file:** `app/backend/src/fastapi_app/services/background_aggregation.py:243` (write in
  `_record_run_outcome`), reached from `run_aggregation` lines 198/202.
- **Defect:** The lock RELEASE is compare-and-delete (fencing token, `_RELEASE_LOCK_LUA`), but the
  INGEST_LAST_RUN_KEY WRITE is an unconditional `redis_client.set(...)` — it does not verify the
  runner still holds the token.
- **Failure scenario:** If a run exceeds the 30-min AGGREGATION_LOCK_TIMEOUT, a second scheduler
  tick reacquires the lock and records its (newer) outcome; the first, late-finishing runner then
  overwrites INGEST_LAST_RUN_KEY with its staler record. last_success_at could regress by one
  cycle and data_stale briefly flip. Impact is bounded: staleness never fails readiness (spec
  §2.5), the record is loss-tolerant, and it self-heals on the next tick. Consistent with the spec's
  accepted "lost on cache restart / self-heals within one tick" posture (§8.2), so arguably
  within-design, but worth recording as the one place the fencing token is not consulted.

### P3-4 — main.py carries imports orphaned by the /cache-test deletion (ENV-6 cleanliness)
- **file:** `app/backend/src/fastapi_app/main.py:21` (`AsyncSessionLocal`), also `:4` (`Response`),
  `:7` (`BaseHTTPMiddleware`).
- **Defect:** The /cache-test removal correctly dropped most of its imports (`Optional`, `Redis`,
  `get_cache`, `Depends`, `APIRouter`), but `AsyncSessionLocal` remains imported and is now unused in
  main.py (`create_db_tables` uses `async_engine`+`Base` only). `Response` and `BaseHTTPMiddleware`
  are likewise imported-but-unused (at least `BaseHTTPMiddleware` looks pre-existing).
- **Failure scenario:** None functional. flake8 ignores F401 project-wide (ENV-6), so CI gives no
  signal, and there is no F811 collision (no module-level `settings` import is shadowed by a
  same-named parameter in this module), so the ENV-6 live hazard is not triggered. This is the
  exact "deletion orphans an import that F401-ignore hides" shape ENV-6 warns about — cosmetic here,
  worth a one-line cleanup. background_aggregation.py's per-run-engine removal was cleaner: it
  dropped create_async_engine and reuses `..db.AsyncSessionLocal` (its remaining unused
  get_cache/Callable/AbstractAsyncContextManager imports live only in comments and are
  pre-existing, not introduced by this diff).

### P3-5 — Freshness failure/partial tests trigger uncaptured logger.error(..., exc_info=True)
- **file:** `app/backend/src/fastapi_app/tests/services/test_background_aggregation.py:463`
  (`test_freshness_partial_when_one_region_fails`), `:485` (`test_freshness_failure_when_commit_raises`).
- **Defect:** Both tests intentionally trigger errors (RuntimeError("ESI 500") per-region;
  RuntimeError("simulated commit failure")) that reach `logger.error(..., exc_info=True)` in
  run_aggregation (lines 177 / 212), but neither test captures/asserts that error output.
- **Failure scenario:** Under CLAUDE.md's strict rule ("if a test is intentionally triggering an
  error, we must capture and validate the error output"), these should caplog-assert the emitted
  ERROR. In practice pytest's default log capture keeps stdout/stderr pristine on pass, and this
  matches an existing pattern (test_process_contracts_type_resolution_failure_degrades_gracefully),
  so §1 pristine-output is not violated on green — but the intentional-error output is unasserted.

---

## Checklist walk (explicit results)

### implementation-pitfalls.md

**§1.C — API & Request Binding**
- FASTAPI-1 (Annotated[Model, Query()]): n/a / clean — new endpoints /ready, /metrics take no
  Pydantic query model; no Depends(Model) on a GET.
- FASTAPI-2 (declared-but-inert filters): n/a — no filter params added.
- PROXY-1 (bare-mounted routers): clean — ops_router.router is APIRouter(tags=["Ops"]) with a
  bare /ready (main.py:249 comment confirms bare mount); no /api/v1 added.

**§2.C — Data & Persistence**
- SQLA-1 (paginate distinct parents): n/a — no join pagination changed.
- SQLA-2 (partial-index ON CONFLICT restates predicate): clean — baseline migration line 123
  renders uq_notifications_watchlist_dedup with postgresql_where=sa.text("type = 'watchlist_match'"),
  matching the model DDL; the matcher's ON CONFLICT (M3) is unchanged. The post-enrichment
  is_ship_contract/item_processing_status UPDATEs chunk their id-lists (_chunk_ids,
  UPDATE_ID_CHUNK_SIZE=1000) against the asyncpg 32767 bind cap — covered by
  test_id_list_updates_batch_across_the_chunk_boundary (chunk forced to 2, 3 contracts).

**§3.C — Environment & Dev Loop**
- ENV-1 (JSON complex fields): clean — AGGREGATION_REGION_IDS validator unchanged; prod value
  documented as JSON array string in .env.example.
- ENV-2/ENV-3 (destructive startup): clean — create_db_tables remains dev-gated behind BOTH
  ENVIRONMENT=="development" AND DB_RECREATE_ON_STARTUP, secure-by-default; gate tests preserved.
- ENV-4 (extra="ignore" + document new field): clean — extra="ignore" retained
  (config.py:112); new METRICS_TOKEN is a declared field with an empty-SecretStr default, documented
  in .env.example (prod section, lines 61-62). Absence from the dev section is correct — unset =
  open /metrics per spec §8.3.
- ENV-6 (deletion orphans imports): see P3-4 — orphaned AsyncSessionLocal in main.py; no F811.

**§4.C — External Integrations (ESI)**
- clean / n/a — no ESI route changes; freshness uses ESINotModifiedError; no /latest,
  /status.json, or /verify introduced.

**§5.C — Deployment & Platform**
- DEPLOY-1 (postgresql:// -> +asyncpg): clean — Settings.normalize_database_url_driver
  (config.py:78) rewrites the scheme; Alembic env.py consumes str(settings.DATABASE_URL), so the
  CLI path inherits normalization; covered by test_config.py (plain + already-asyncpg cases).
- DEPLOY-2 (--workers 1): n/a for this diff — carried by the Phase-1 Dockerfile CMD, not in the
  Phase-3 diff. db.py pool is bounded (pool_size=5, max_overflow=5, pool_pre_ping=True) and
  the aggregation service now reuses the single app engine via ..db.AsyncSessionLocal (no per-run
  second engine), covered by test_run_aggregation_reuses_app_session_factory...

**§Orchestration.C** — n/a to the code diff; satisfied by this review persisting its report here.

### testing-pitfalls.md

- TEST-2 (no weakened assertions / no deleted tests): clean. The SSO warn tests were reworked
  from warn_if_sso_unconfigured (5 parametrized cases over a 2-element {ESI_CLIENT_ID,
  TOKEN_CIPHER_KEYS} set + 1 message test) to validate_sso_configuration (8 test functions:
  wholly-unconfigured warns in all 3 envs, message-naming, 6 partial-subset prod-fail cases, 2
  localhost prod-fail cases, dev/test partial-warn, prod fully-configured silent, dev-localhost
  silent, lifespan integration). The matrix strictly EXPANDS coverage (adds ESI_CLIENT_SECRET
  to the trio; adds prod fail-fast and localhost checks; adds lifespan wiring). The one changed
  expectation — production wholly-unconfigured flipped from SILENT (old ("production","","",
  False)) to WARN — is sanctioned by spec §6 tier (a) ("warn in EVERY environment and
  continue"). No non-SSO tests were deleted; the destructive-gate tests are preserved verbatim.
- TEST-6 (Playwright/vitest glob collision): clean. playwright.config.ts adds a
  live-smoke-prod project (testMatch: /live-smoke/, webServer: undefined when
  E2E_PROD_BASE_URL set) under e2e/; vitest still excludes e2e/**; no *.test.ts added.
- TEST-7 (error-path exhausts QueryClient retries): n/a — no frontend hook/component error
  tests in this diff; the retry policy concern is frontend-only.
- §1 Pristine output: clean on green — no new deprecated APIs (datetime.now(timezone.utc),
  not utcnow); pytest log-capture keeps passing output clean. See P3-5 for the unasserted
  intentional errors.
- §5 Concurrency: freshness recording happens INSIDE the lock context (records at
  run_aggregation lines 198/202, before the _concurrency_lock finally releases), so in the normal
  case a record is never written after release, and only one runner holds the lock. The one gap is
  the TTL-expiry clobber window — see P3-3. _record_run_outcome is called exactly once per run
  (mutually-exclusive success vs forced-failure branches; the method swallows its own exceptions so
  it can't double-fire).

---

## Notes / things checked and cleared

- Freshness outcome semantics (_record_run_outcome) match spec §8.2 exactly: success (all
  regions checked ok incl. 304s + committed-or-valid-noop), partial (>=1 ok, >=1 failed), failure
  (0 ok, or any processing/commit/top-level abort via forced_failure=True); last_success_at
  advances on success/partial and is preserved through failure; gauge advances only on success/partial.
  All four freshness tests assert these correctly.
- /ready staleness never fails readiness (only db/cache errors set 503); data_stale = never
  ingested OR age > 2x interval — matches spec §8.2 / §2.5.
- validate_sso_configuration ordering (before create_db_tables in lifespan) fails fast on
  prod misconfig before touching the DB; tier (a) warn-and-boot preserves the anonymous marketplace.
- Baseline migration <-> model equivalence is guarded by test_migrated_schema_matches_model_metadata
  (real psycopg2 path; psycopg2-binary is a pinned dep) and env.py import-safety by
  test_alembic_env_import_is_side_effect_free. Not runnable here, but structurally sound.
- is_ship_contract/item_processing_status are deliberately omitted from the contract upsert's
  mapped columns so ETag-304 re-ingestion can't decay them to False — covered by
  test_reingestion_with_unmodified_items_keeps_ship_flag.
