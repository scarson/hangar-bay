# M4 Plan — Codex Adversarial Review (Round 2, cross-model, 2026-07-18)

ABOUTME: Verbatim Codex CLI (high reasoning) cold review of the M4 implementation plan, run as plan-review-cycle round 2 alongside an independent Opus cold review.
ABOUTME: 13 P1 + 8 P2 findings; merged with the Opus set (5 overlaps, mutual confirmation) and applied in the round-2 fix commit.

DONE_WITH_CONCERNS — Sam, this plan is not subagent-ready. I found 13 execution-blocking defects and 8 advisory gaps. No files were edited.

## P1 — execution-blocking

1. **[P1] Task 0.1 Step 3 — wrong POST-body expectation.**  
   `grant=body-survives` is 19 bytes, not 18. Because the verdict requires P1/P2 to “pass exactly,” the stated expectation can falsely force Topology B.  
   **Fix:** change the expected `body_len` to `19`, or compute the expected length in the probe instead of hard-coding it.

2. **[P1] Task 0.1 Steps 1, 3, and 4 — credential leakage in the committed spike report.**  
   `DATABASE_URL[:16]` returns text such as `postgresql://use`, exposing the beginning of the database username. It also cannot equal the expected `"postgresql://"`. Step 4 then commits this output.  
   **Fix:** derive only the scheme:
   ```python
   raw_url = os.environ.get("DATABASE_URL", "")
   scheme, separator, _ = raw_url.partition("://")
   database_url_scheme = f"{scheme}://" if separator else ""
   ```
   Return and record `database_url_scheme`, never a URL slice.

3. **[P1] Task 1.2 Step 1 — the static rewrite assumes an unproven backend hostname.**  
   `https://hangar-bay-api.onrender.com/*` assumes the service name becomes that exact globally available subdomain. Render permits full-URL rewrite destinations, but the actual service URL must be known and stable; its own deployment guide instructs users to substitute the created service’s URL. [Render rewrite documentation](https://render.com/docs/redirects-rewrites)  
   **Fix:** choose and verify a globally unique backend service name before committing the blueprint, and use that exact hostname in both `name` and `destination`; alternatively bind a separately managed backend hostname. Add a Phase-0/2 assertion that the resolved API URL equals the rewrite destination before applying the production blueprint.

4. **[P1] Task 1.4 Step 1 — deploy creation does not handle Render’s queued response.**  
   The Trigger Deploy endpoint returns either `201 Created` or `202 Queued`. The workflow blindly extracts `.id`; a queued response without an ID produces an empty poll URL. Phase 0 does not test the overlapping-deploy case. [Render Trigger Deploy API](https://api-docs.render.com/reference/create-deploy)  
   **Fix:** capture the HTTP status and response body, reject an empty deploy ID, and explicitly handle `202` by resolving the queued deploy ID through the deploy list API. Extend P5 to trigger while another deploy is active and record the 202 response shape.

5. **[P1] Task 1.4 Step 1 — manual SHA input is shell/output-injection capable.**  
   `github.event.inputs.sha` is interpolated directly into an `echo` command and then into JSON. The plan describes it as a full SHA but never validates that constraint. A newline or shell metacharacter can corrupt `$GITHUB_OUTPUT` or execute in a secret-bearing job.  
   **Fix:** pass both candidate SHAs through step `env`, select them inside the shell, require `^[0-9a-f]{40}$`, and only then write the validated value to `$GITHUB_OUTPUT`.

6. **[P1] Task 1.5 Step 2 — the drift-repair branch violates the M3 collision boundary.**  
   If drift exists, the plan orders a commit touching `app/frontend/web/openapi.json` and `src/lib/api/schema.d.ts`. M3 explicitly regenerates both, and `schema.d.ts` is inside the Phase-1 forbidden `app/frontend/web/src/**` surface.  
   **Fix:** on pre-M3 drift, record a Discovery and defer Task 1.5 until M3 regenerates its artifacts, or split the drift job into a post-M3 PR. Do not authorize a Phase-1 regeneration commit.

7. **[P1] Phase 2b Steps 1–3 — secrets are entered too late for the initial deploy.**  
   Render prompts for `sync: false` values during initial Blueprint creation; applying the Blueprint starts deployment. Entering required values afterward means the first import/pre-deploy can fail because `ESI_USER_AGENT` and other configuration are missing. Render also ignores new `sync:false` declarations on later Blueprint updates. [Render Blueprint secret behavior](https://render.com/docs/blueprint-spec)  
   **Fix:** generate the values locally beforehand and enter every `sync:false` value in the New Blueprint flow itself. Domain attachment can follow creation; secret entry cannot.

8. **[P1] Task 3.3 Step 2 — `_record_run_outcome` has no Redis client to receive.**  
   Current [`_concurrency_lock()`](/Users/sam/Code/hangar-bay/.claude/worktrees/hangar-bay-frontend-rebuild-2e4fe7/app/backend/src/fastapi_app/services/background_aggregation.py:81) yields no value and closes its private Redis client on exit. The proposed `_record_run_outcome(self, redis_client, ...)` therefore cannot be called as written.  
   **Fix:** explicitly change the context manager to `yield redis_client`, consume it with `async with self._concurrency_lock() as redis_client`, and perform outcome writes before leaving that context. Specify and test what happens if the outcome write itself fails.

9. **[P1] Task 3.3 Steps 1–2 — outcome counters do not represent committed data.**  
   The proposed logic increments counters in the fetch loop, then derives outcome solely from `ok`/`failed`. If all fetches succeed but `_process_contracts` or `commit()` fails, it records `success`. The current service uses one transaction for all regions, not a per-region commit. ETag-304 and an empty successful result are also undefined.  
   **Fix:** define exact transitions:
   - Fetch success and ETag-304 count as successfully checked regions.
   - `success`/`partial` may only be recorded after the shared transaction commits or completes as a valid no-op.
   - Any processing/commit/top-level abort forces `failure`, regardless of fetch counters.
   - Specify whether counters mean “regions checked successfully” rather than “regions committed,” since commits are not per region.

10. **[P1] Task 3.4 Step 2 — the proposed module imports `get_db` from the wrong place.**  
    [`core/dependencies.py`](/Users/sam/Code/hangar-bay/.claude/worktrees/hangar-bay-frontend-rebuild-2e4fe7/app/backend/src/fastapi_app/core/dependencies.py:1) exports `get_cache` but not `get_db`; [`get_db` lives in db.py](/Users/sam/Code/hangar-bay/.claude/worktrees/hangar-bay-frontend-rebuild-2e4fe7/app/backend/src/fastapi_app/db.py:30). The supplied `ops.py` will fail to import.  
    **Fix:** use:
    ```python
    from ..core.dependencies import get_cache
    from ..db import get_db
    ```

11. **[P1] Task 3.4 Step 2 — the implementation omits the design’s short readiness timeouts.**  
    The authoritative design requires DB and cache probes with short timeouts. The supplied code awaits `SELECT 1`, `PING`, and `GET` without bounds, so `/ready` and Render deployment health checks can hang behind dead network connections.  
    **Fix:** bind a concrete timeout such as `READINESS_CHECK_TIMEOUT_SECONDS = 2.0`, wrap each component check in `asyncio.timeout(...)`, classify timeout as that component’s error, and add DB-timeout and cache-timeout tests.

12. **[P1] Task 3.4 Step 1 and Task 3.5 Step 1 — the provided tests do not match the repository’s async client.**  
    The house `client` is an async `httpx.AsyncClient`, but Task 3.4 calls `client.get()` without `await`, while Task 3.5 declares synchronous tests. `client_with_metrics_token` does not exist anywhere. These tests will not run as written.  
    **Fix:** provide complete `async def` tests with `await client.get(...)`, the appropriate async marker, exact dependency overrides for DB/cache, and a defined metrics-token fixture—or monkeypatch `settings.METRICS_TOKEN` within each test. Account for TEST-10 by wiring `app.state` or overriding the captured dependencies.

13. **[P1] Task 3.9 Step 4 — the migration fixture is a non-executable sketch referencing a nonexistent house idiom.**  
    Current `conftest.py` drops/creates tables in an existing database; it contains no database create/drop helper. The plan leaves both critical operations as comments, derives the database name using fragile string replacement, does not specify autocommit/admin connection handling, and lacks partial-setup cleanup.  
    **Fix:** include a complete fixture using `sqlalchemy.engine.make_url()` to replace the database component, a psycopg2 admin engine with `AUTOCOMMIT`, explicit create/drop operations, connection termination before cleanup, and `try/finally`. It must tolerate a database left by a previous failed run.

## P2 — advisory but material

14. **[P2] Task 1.2 Steps 1–2 — HSTS has no executable owner.**  
    The design binds HSTS, but the target `headers` block only sets cache headers. “Close the gaps the spike found” gives a cold agent no value or path to add.  
    **Fix:** specify the exact `Strict-Transport-Security` rule for `/*` and its agreed value, conditional only on P4 proving Render already supplies an equal or stronger header.

15. **[P2] Task 1.3 Step 4 — the import-safety verification claim is false.**  
    The plan says the existing tests import `env.py`’s `do_run_migrations`; repository search finds no such test. The CLI check exercises the Alembic-active path, not plain import.  
    **Fix:** add a Stage-1 test importing `alembic/env.py` without an active `EnvironmentContext` and asserting that no migration execution occurs.

16. **[P2] Task 3.3 Steps 1–2 — the plan silently changes the authoritative key schema and does not test the gauge.**  
    The design defines four fields; the plan adds `last_success_at`. That addition is sensible but is an undocumented spec deviation. None of the proposed assertions verifies that the Prometheus gauge advances on success/partial and stays unchanged on failure.  
    **Fix:** update the design contract before execution, then add gauge assertions with state isolated between tests.

17. **[P2] Task 3.7 Steps 1–2 — “partial configuration” coverage is incomplete and lifespan wiring is untested.**  
    The matrix only covers “client ID set, another field empty.” It does not cover secret or cipher configured while client ID is empty. Direct function tests also do not prove lifespan invokes the renamed validator; the repository has no existing lifespan boot test despite the plan’s claim.  
    **Fix:** enumerate every required-field combination outside the wholly-empty state, and add one controlled lifespan test with startup dependencies patched at their external boundaries.

18. **[P2] Task 3.8 Steps 1–2 — the pool test cannot pin the intended connection budget.**  
    `pool.size() <= 5` would accept any smaller accidental value, and `max_overflow=5` is completely untested. It also relies on private `_pre_ping` without acknowledging version coupling.  
    **Fix:** assert exact pool size and overflow configuration, or factor engine construction behind a small configuration seam whose public arguments can be asserted.

19. **[P2] Task 3.9 Step 1 — the expected M3 module examples are wrong.**  
    M3 creates one `models/account.py` exporting `SavedSearch`, `WatchlistItem`, and `Notification`; it does not create `saved_search`, `watchlist`, or `notification` modules.  
    **Fix:** replace the examples with `account`, or state only that importing `fastapi_app.models` must register every class in the post-M3 `__all__`.

20. **[P2] Task 3.12 Step 2 — verification commands have no working directories.**  
    Executed literally from the repository root, neither `pdm run ...` nor the npm commands target a project.  
    **Fix:** provide explicit grouped commands under `app/backend` and `app/frontend/web`, including the exact E2E environment requirements.

21. **[P2] Task 3.12 Step 2 and Appendix C — ORCH-1 is claimed but not satisfied.**  
    `docs/audits/m4-phase3-review/` is only a directory, not an exact persistence path; no dispatch prompt contains the mandatory persistence instruction, and no wave-by-wave commit step exists.  
    **Fix:** name one file per review round/agent, require writing before return, and require the orchestrator to commit each review wave before consolidation.

22. **[P2] Task 1.6 Step 1 — optional PR splitting is underspecified.**  
    “Split Task 1.3 into its own PR if review size warrants” supplies no threshold, branch topology, merge order, or retargeting procedure. Two agents can make incompatible choices.  
    **Fix:** choose one structure now, or provide an objective split threshold and exact branches/PR dependencies.

The PDM export flags, Render Blueprint field names, Playwright conditional `webServer` shape, Pydantic v2 validator form, and `prometheus_client` gauge/API calls themselves checked out. The blockers are primarily wiring, sequencing, security, and incomplete test instructions.
