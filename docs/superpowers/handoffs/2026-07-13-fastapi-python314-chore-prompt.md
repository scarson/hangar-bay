# Chore: migrate FastAPI 0.115 → current and move Python 3.12 → 3.14 (Hangar Bay)

> **What this is:** a ready-to-paste starting prompt for the agent that will run the post-M2 FastAPI/Python-3.14 migration. Paste the body below into a fresh session. Written 2026-07-13, after the full M2 stack + both hardening PRs (#31–#37) landed on `dev`.

---

You are executing a post-M2 maintenance chore for Hangar Bay: lift the FastAPI 0.115 hold, migrate to current FastAPI/Starlette, and move the backend and CI from Python 3.12 to 3.14. This is Sam's own app; the auth code you'll run tests against is standard defensive OAuth — describe any auth behavior in plain correctness terms (what the correct handshake/validation does), never threat-actor phrasing. It trips a safeguard classifier otherwise. (Durable record: user-memory `hangar-bay-auth-framing`.)

## State of the world (all prerequisites are now met)
The entire M2 EVE SSO milestone is merged to `dev`: all 9 phases (#31–#35) plus both hardening PRs (#36 frontend, #37 backend). So `dev` already contains `services/auth_service.py`, `api/auth.py`, `core/session.py`, `services/sso.py`, and the hardened error boundaries. Nothing else is in flight. Read user-memory `m2-eve-sso-shipped` for the full topology.

- **The `ENVIRONMENT` default is now `"production"`** (secure-by-default, from #37) and the destructive `create_db_tables` recreate is gated on `ENVIRONMENT == "development" AND DB_RECREATE_ON_STARTUP`. Local dev needs `ENVIRONMENT=development` + `DB_RECREATE_ON_STARTUP=true` in `.env` (both are in `.env.example`). Don't regress this.

## Prerequisites / constraints
- Work in a **fresh git worktree off `dev`**: `cd /Users/sam/Code/hangar-bay && git fetch origin dev && git worktree add .claude/worktrees/m2-fastapi-314 origin/dev -b chore/fastapi-current-python-314`.
- **Runs the full backend `pytest`** against the single shared docker Postgres/Valkey test DB (`hangar_bay_*`). Nothing else backend-pytest is running now, but don't launch a second backend-test workload concurrently.

## Environment facts
- Repo root `/Users/sam/Code/hangar-bay`; integration branch `dev`; backend `app/backend` (pdm); frontend `app/frontend/web`.
- **Backend commands need `export PATH="$HOME/.local/bin:$PATH"` and run from `app/backend`.** Test: `pdm run pytest`. Lint: `pdm run lint` (flake8) — exits nonzero on a pre-existing W293 ledger (`services/contract_service.py`, `services/scheduled_jobs.py`); diff against a baseline, don't demand exit 0.
- The machine default `python3` is already CPython **3.14** (uv-managed shims). Apple's 3.9 at `/usr/bin/python3` is a fallback only — do not target 3.9 (PEP 604 `X | None` unions etc. are fine). The backend venv is currently pinned to **3.12** because of the FastAPI hold you're lifting.
- The hold: `fastapi>=0.115.12,<0.116` in `app/backend/pyproject.toml`. Commit `cdc38b7` (the pydantic relock) explains why. The pydantic stack (2.13.4 / pydantic-core 2.46.4 / pydantic-settings 2.14.2) already ships cp314 wheels — **do not touch it unless the FastAPI resolve forces a bump.**
- **Never read or print `app/backend/src/.env`.** Tests don't depend on it; if you need a local `.env`, build it from `.env.example` with the non-secret dev values (they match the checked-in `docker/compose.dependencies.yml`).

## Why the hold exists (root context, not a symptom to patch)
FastAPI 0.115's internals call `asyncio.iscoroutinefunction`, which Python 3.14 deprecates. Under 3.14 that emits a `DeprecationWarning` on every test — you'll currently see **16 such warnings** when the suite runs on a 3.14 venv (CI on 3.12 is pristine). That deprecation is the *sole* reason 3.14 was blocked; the fix is to move to a FastAPI/Starlette version that no longer calls the deprecated API, then flip the interpreter and confirm the warning summary is empty. A **first spike** at FastAPI 0.139 / Starlette 0.52 broke 19 of 53 tests — but the suite is now much larger (**~245 tests** after M2 + hardening), so expect a different count and a real migration, not a version bump.

## The job — three parts, in order

### Part 1 — Migrate FastAPI/Starlette to current, get the suite green (stay on 3.12 first)
1. Isolate library-migration failures from interpreter failures by staying on the 3.12 venv. Lift the hold — target current FastAPI (let pdm resolve the compatible Starlette). `pdm lock` + install.
2. Run `pdm run pytest` and triage failures **by root-cause class** (systematic-debugging skill). Expect classes like Starlette `TestClient`/`ASGITransport`/response-API changes, middleware or exception-handler signature changes, `Request`/`Response` behavior, `openapi()` schema-shape drift, lifespan changes. For each class, fix the ONE root cause at the source — **no symptom patches, no `# type: ignore` band-aids, no test weakening.**
3. **Guard the auth surface.** M2 added `api/auth.py` (routes over `ASGITransport`), `core/session.py`, `services/sso.py`, and the `auth_client` conftest fixture that wires `app.state` by hand because `ASGITransport` skips lifespan (testing-pitfalls TEST-10). Starlette major bumps most often move `TestClient`/`ASGITransport`/cookie-jar semantics — verify the callback-flow tests (`tests/api/test_auth_flow.py`), the `[TIMING]` single-use-state test, and the cookie-attribute assertions still hold *for the right reason*. Don't weaken a timing/single-use assertion; fix with deterministic sync or injected clocks.
4. If the OpenAPI shape drifts, regenerate the typed client: `pdm run export-openapi` (from `app/backend`) → `npm run generate:api` + `npx tsc -b` (from `app/frontend/web`), and commit `openapi.json` + `schema.d.ts` together with the schema-affecting change (CLAUDE.md codegen rule). Confirm `npm run e2e` is unaffected.
5. Exit criterion: `pdm run pytest` fully green, **pristine** (no new `filterwarnings` — silencing warnings was explicitly rejected across M2 review; the point is to eliminate them, not hide them). Still on 3.12.

### Part 2 — Flip the interpreter to 3.14
1. Rebuild the backend venv on 3.14 (`pdm use` against 3.14; machine default is already 3.14). Re-install, re-run `pdm run pytest`.
2. Confirm the **pytest warnings summary is empty** — the 16 `asyncio.iscoroutinefunction` deprecations must be gone and no new 3.14 deprecation may replace them. If a new one appears, root-cause it (may be a different dependency); don't filter it.
3. Update CI: in `.github/workflows/ci.yml` flip every `python-version` from `3.12` to `3.14` (`actions/setup-python` + `setup-pdm`). `grep 3.12 .github/workflows/ci.yml` to catch them all (comments note "both pins move together").
4. Exit criterion: full suite green + pristine on 3.14, locally and in CI after push.

### Part 3 — Retire the ENV-5 pitfalls entry
`docs/pitfalls/implementation-pitfalls.md` `ENV-5` ("pin Python 3.12 until the FastAPI 0.115 hold lifts") is now false. Per the file's **Appendix C** framework, delete it or rewrite it into a resolved/historical note; either way update the §3 TOC list, the §3.C Review Checklist item, the Appendix B summary row, and add an Appendix A changelog line dated to your run. Do NOT renumber the other ENV IDs (ENV-1/2/3/4/6 stay). Preserve any still-true parts of ENV-5's body (e.g. the pydantic-relock rationale); only the "pin 3.12" claim is retired.

## Verification & delivery
- Full backend suite green + pristine on 3.14 (`pdm run pytest` from `app/backend` with the PATH export).
- `pdm run lint`: no NEW findings beyond the pre-existing W293 ledger in files you touched.
- Frontend E2E unaffected (`npm run e2e` from `app/frontend/web`; responsive/live-smoke skips expected).
- Conventional Commits; every message ends with `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`.
- Open a PR against `dev` (`chore(backend): migrate FastAPI to current and move to Python 3.14`). Body: the failure classes you root-caused + how, the interpreter flip, the empty-warnings confirmation, the ENV-5 retirement. Run `/codex review`; fix any real defect (and re-review — the M2 backend hardening PR needed three codex rounds to fully converge, so don't assume one pass is clean). Merge when green + codex-clean.
- Clean up: `git worktree remove .claude/worktrees/m2-fastapi-314`.

## Anti-patterns that fail review
- Silencing the 3.14 deprecation with `filterwarnings` instead of migrating off the deprecated API.
- Weakening/deleting a failing auth/timing test to go green — fix the root cause or the deterministic-sync seam.
- "Fixing" code for 3.9 compatibility. Target is 3.14.
- Touching the pydantic stack unless the FastAPI resolve requires it.
- One squashed "migrate everything" commit with no per-failure-class root-cause narrative.
