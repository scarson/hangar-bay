# ABOUTME: M4 Phase 1 deploy-scaffolding review — configuration-correctness lens.
# ABOUTME: render.yaml / deploy.yml / ci.yml drift job / Dockerfile audited against the recorded Render docs facts.

# M4 Phase 1 review — configuration correctness

**Reviewer lens:** configuration correctness (render.yaml vs Render Blueprint spec facts; deploy.yml as a GitHub Actions workflow; the ci.yml OpenAPI-drift job; the Dockerfile + .dockerignore).
**Diff reviewed:** `git diff origin/dev...HEAD` (commits `fc54a19..9cc10d6`) in worktree `.claude/worktrees/m4-phase1-deploy-scaffolding`.
**Authoritative facts cross-checked against:** `docs/audits/m4-recon/render-docs-verification/{blueprint-fields,deploy-api,static-site-defaults,connection-strings}.md`, the plan `docs/superpowers/plans/2026-07-18-m4-production-readiness.md`, the spec `…-design.md` §§4–7, and empirical checks (PDM 2.28 flag support, `pdm run export-openapi` execution, `gh repo view` default branch).

**Verdict:** not clean. One P2 (real latent config defect that would misbehave at Phase-2b apply), plus two P3 notes (an apply-time risk already flagged in recon that the file's comment overstates as settled, and a cross-phase forward reference worth surfacing). The bulk of the config surface is correct and was verified positively — see "Verified clean" below.

---

## Findings

### 1. P2 — static site `hangar-bay-web` omits `branch:`, so it deploys from `dev`, not `main`

**File:** `render.yaml:64-70` (the `- type: web` / `name: hangar-bay-web` / `runtime: static` service; compare the API service's `branch: main` at `render.yaml:14`).

**Defect:** The API web service pins `branch: main`, but the static site service declares no `branch` field. Per the Render Blueprint spec, an omitted `branch` defaults to the repository's default branch. This repo's **authoritative default branch is `dev`** (`gh repo view --json defaultBranchRef` → `dev`; the local `origin/HEAD` symbolic ref still points at `main` and is stale/misleading). So the two git-backed services are asymmetric: the backend is pinned to the release branch `main`, while the frontend silently tracks the integration branch `dev`.

**Failure scenario:** When the blueprint is applied at Phase 2b (Phase 4 Step 0), the static site's initial deploy — and any later Render-dashboard "deploy latest commit" — builds from `dev`. The design intent (spec §4, and the CD workflow's whole SHA-pinning apparatus) is "one origin serving `main`." Result: integration-branch frontend code reaches production, and frontend/backend fall out of lockstep with each other. Even though `deploy.yml` POSTs an explicit `commitId` at CD time (masking the skew on pipeline deploys), the configured branch still governs the first blueprint-apply deploy and any manual/dashboard deploy, and it encodes the wrong branch in the service's identity.

**Fix:** add `branch: main` to the `hangar-bay-web` service, matching `hangar-bay-api`. One line, same file — cheap to fix now while the file is fresh. (The plan's inline render.yaml in Task 1.2 Step 1 also omits it, so this is a plan-level oversight carried into the committed file, not a transcription slip; worth a Deviation note if fixed.)

---

### 2. P3 — `ipAllowList: []` presented as settled, but recon flags it as unverified and possibly invalid

**File:** `render.yaml:62` (`ipAllowList: []   # private-network access only`).

**Defect (severity-capped by being apply-time-gated + already tracked):** The inline comment asserts "private-network access only" as fact, but the recon evidence disagrees on certainty. `blueprint-fields.md` Q6 + Gap 1 records that `ipAllowList` is marked **Required** for a Key Value service, that "empty list == private-only" is an **inference the docs never state verbatim**, and that Render's *documented* block-all-external recipe is the dummy range `0.0.0.0/32`, **not** an empty list — and that whether `[]` is even accepted by the API could not be tested (Render API unreachable this session).

**Failure scenario:** At Phase 2b apply, the Blueprint validator rejects `ipAllowList: []` (required-field-with-empty-value), failing the apply; or it accepts `[]` with semantics that differ from the intended "external URL unreachable." Either way the render.yaml comment currently reads as if this were confirmed, which could lead a future applier to skip the check.

**Fix / disposition:** No code change strictly required in Phase 1 (the blueprint is inert and the Phase-0 spike is the designated gate). Recommend softening the comment to reference the open question (e.g. "private-network intent; confirm `[]` vs `0.0.0.0/32` at apply — see blueprint-fields.md Gap 1") so the uncertainty travels with the file, and treat "does `[]` apply cleanly" as a required Phase-2b pre-apply check.

---

### 3. P3 — deploy.yml smoke job forward-references a Playwright project/env that Phase 3 supplies (intentional, but flag the cross-phase dependency)

**File:** `.github/workflows/deploy.yml:690` (`E2E_LIVE=1 E2E_PROD_BASE_URL="${{ vars.PROD_ORIGIN }}" npx playwright test --project=live-smoke-prod`).

**Not a Phase-1 defect — recorded so the dependency is visible.** Neither `live-smoke-prod` nor `E2E_PROD_BASE_URL` exists in the current tree: `app/frontend/web/playwright.config.ts` defines only `desktop` / `mobile` / `live-smoke`, and the `live-smoke` project hardcodes `baseURL: 'https://localhost:5173'` and always boots `webServer: npm run dev`. Both the project and the env-driven baseURL are explicit Phase-3 deliverables (plan Task 3.10; spec §7 line 191). The workflow is inert until Phase 2 secrets + a `main` push, and Phase 3 merges to `main` before the first real deploy (Phase 2b runs as Phase 4 Step 0), so by the time this job can run, the project exists.

**Failure scenario (only if invariants are violated):** If `deploy.yml` were ever `workflow_dispatch`-triggered before Phase 3 merges, the `smoke` job fails with "no project named 'live-smoke-prod'" — and had the project existed but not the webServer guard, it would have booted a local Vite dev server and smoke-tested localhost instead of prod. The sequencing in the plan prevents this; the note exists so the ordering constraint isn't lost.

---

## Verified clean (positive coverage)

**render.yaml — full YAML 1.1 scalar audit (every scalar checked, not just the `off`s):**
- Boolean-trap enums quoted correctly: `previews.generation: "off"` (line 6), `autoDeployTrigger: "off"` (lines 15, 70) — all three quoted, matching Render's own spec example and Deviation D-5. Correct.
- String-typed `value:` fields that would mis-parse unquoted are all quoted: `"false"` (DB_RECREATE_ON_STARTUP), `"[10000002]"` (AGGREGATION_REGION_IDS JSON array — ENV-1), `"0"` (AGGREGATION_DEV_CONTRACT_LIMIT), `postgresMajorVersion: "17"`. Correct — unquoted, these would become a YAML bool/flow-seq/int and violate Render's string-typed schema.
- `sync: false` entries use a bare (real) boolean — correct, because `sync` is a genuine boolean in Render's schema (unlike `value`, which is a string). No over-quoting.
- Plain scalars with embedded specials are safe: `preDeployCommand: sh -c "cd /app/src && python -m alembic upgrade head"` (embedded `"` legal mid plain scalar; no `: ` or ` #`), `value: max-age=31536000; includeSubDomains` (`;` not special outside flow), `value: public, max-age=31536000, immutable` (commas literal in block context), `destination: https://…onrender.com/*` (`://` colon-not-followed-by-space, trailing `/*` fine), `source: /api/v1/*` and `/*` (leading `/`, so no YAML alias `*` ambiguity). All parse as intended strings.
- Field names / enums vs `blueprint-fields.md`: `autoDeployTrigger`, `runtime`, `type: keyvalue`, `previews.generation`, `fromDatabase.property: connectionString`, `fromService.type: keyvalue`+`property: connectionString`, `maxmemoryPolicy: allkeys-lru`, `staticPublishPath`, `routes[{type,source,destination}]`, `headers[{path,name,value}]`, `plan: basic-256mb`, `postgresMajorVersion` — all current, none deprecated. Route ordering (prefix-strip before SPA fallback) is correct (PROXY-1).
- `preDeployCommand` runtime feasibility: `alembic` is a **main/prod** dependency (`pyproject.toml:8`), so `pdm export --prod` ships it; `src/alembic.ini` + `src/alembic/` are copied by `COPY src/ ./src/`; the image sets `PYTHONPATH=/app/src`, so `cd /app/src && python -m alembic upgrade head` can import `fastapi_app`. Works. (The disk being unavailable during pre-deploy is irrelevant — migrations touch the DB, not the disk.)

**Dockerfile (`app/backend/Dockerfile`):**
- Three-stage layering is coherent: `deps` (pdm → requirements.txt) → `build` (build-essential + `pip install --prefix=/install`, needed because the locked asyncpg/httptools/uvloop have no cp314 wheels — Deviation D-4/Discovery) → slim runtime `COPY --from=build /install /usr/local`. Empirically verified to build+boot per D-4.
- `pdm export --prod -o requirements.txt --without-hashes`: confirmed valid on the installed PDM 2.28.0 (`--without-hashes` is an accepted alias of `--no-hashes`; `--prod` unselects the dev group while keeping the default/main group). `pdm.lock` is present and copied.
- `PYTHONPATH=/app/src` matches `COPY src/ ./src/` + `uvicorn fastapi_app.main:app`. `--port ${PORT:-8000}` via `sh -c` honors Render's injected `PORT`. `--workers 1` matches the in-process-scheduler design constraint (spec §2). No `--reload`, no gunicorn, no extra workers. Correct.

**.dockerignore (`app/backend/.dockerignore`):**
- Build context is `app/backend` (`rootDir: app/backend` + `dockerfilePath: ./Dockerfile`), so the `src/.env` pattern matches `app/backend/src/.env` and excludes it. The image never copies a root `.env` either (only `pyproject.toml`, `pdm.lock`, `src/`). Secret exclusion holds. (Minor, not a defect: `src/fastapi_app/tests/` still ships in the runtime image — image bloat only.)

**ci.yml OpenAPI-drift job (`.github/workflows/ci.yml:128-158`):**
- Does it fail on drift? Yes — `git diff --exit-code` returns non-zero on any delta and the `|| { …; exit 1; }` guard exits 1 (and GitHub's default `bash -eo pipefail` doesn't mask it because the `||` handles it explicitly).
- Does `pdm run export-openapi` need env vars the job doesn't set? **No.** `src/export_openapi.py` `os.environ.setdefault`s dummies for exactly the three no-default required Settings fields (`ESI_USER_AGENT`, `DATABASE_URL`, `CACHE_URL`; `AGGREGATION_REGION_IDS` has a default_factory and is also seeded). Confirmed by running it here: "OpenAPI schema written … (18 paths)", no DB present. No database service needed — `db.py:11` `create_async_engine(...)` is lazy and importing `fastapi_app.main` opens no connection.
- Checkout depth: default shallow (depth 1) is sufficient — the job regenerates into the working tree and diffs against HEAD; no history needed.

**deploy.yml GitHub Actions correctness (`.github/workflows/deploy.yml`):**
- Expression-injection: the only untrusted input (`github.event.inputs.sha`) is routed through an `env:` var and regex-gated to `^[0-9a-f]{40}$` before it is written to `$GITHUB_OUTPUT` or used; every later inline `${{ steps.sha.outputs.sha }}` is therefore a validated 40-hex string. `vars.PROD_ORIGIN` is a maintainer-set repo variable (trusted). `ref: ${{ … }}` in the smoke checkout is an action input, not shell. No injection vector.
- Poll-loop terminal states vs the 11 documented deploy statuses (`deploy-api.md` Q3): backend loop exits on `live` and fails on all five terminal-failure states (`build_failed|update_failed|canceled|pre_deploy_failed|deactivated`); static loop omits `pre_deploy_failed`, which is correct because a static site has no pre-deploy phase. Spelling `canceled` (one "l") matches the enum. Non-terminal states correctly fall through to sleep/retry.
- 201-vs-202 create handling: reads `.id` from the create body, and on an id-less 202 falls back to `GET …/deploys?limit=10` filtered by `commit.id == $sha`, correctly unwrapping the documented `{deploy, cursor}` list shape via `(.deploy // .)`. jq is robust on empty/error bodies (`// empty`, and the verify step adds `2>/dev/null || true`). `set -euo pipefail` + non-`-f` POST (captures HTTP errors) + `-f` on GETs (fails fast) behave correctly; no false "success."
- Timeouts sane: backend 120×15s≈30m < job 40m; static 60×10s≈10m; verify 40×15s≈10m. Concurrency `group: deploy-production`, `cancel-in-progress: false` is distinct from CI's `ci-${{ github.ref }}` and correctly queues rather than kills deploys.
- Trigger wiring: `workflow_run.workflows: [CI]` matches `ci.yml`'s `name: CI`; `branches: [main]` filters on the triggering run's head branch; `if: … workflow_run.conclusion == 'success'` gates on CI success; `workflow_dispatch` short-circuits the `||`. Because deploy.yml lands on the **default branch `dev`** (where CI also lives), the `workflow_run` event will actually fire — the default-branch-hosting requirement is satisfied by the normal merge flow.

**Cross-phase dependencies traced and confirmed non-defects (documented in render.yaml's ABOUTME "assume Phase 3 code has merged"):**
- The `preDeployCommand`'s `create_async_engine(str(settings.DATABASE_URL))` requires the `postgresql+asyncpg` scheme, but Render's `fromDatabase.connectionString` yields plain `postgresql://`. The `+asyncpg` normalization is Phase 3 Task 3.1; Phase 2b applies the blueprint only after Phase 3 is on `main`. Correct sequencing.
- `env.py:19` imports only `user, contracts` models; Task 3.9 must widen this before the baseline is generated. No revision exists in Phase 1 (empty `versions/`), so `alembic upgrade head` is a no-op now. Tracked in the plan.
