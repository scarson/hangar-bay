# M4 Production Readiness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deploy Hangar Bay to production on Render — one HTTPS origin serving SPA + API + SSO callback, Alembic-managed schema, CI-gated CD, readiness/freshness observability — per the authoritative design `docs/superpowers/specs/2026-07-18-m4-production-readiness-design.md` (read it before executing any phase; its §4 topology, §5 migration rules, and §10 sequencing are binding).

**Architecture:** Four Render resources (static site with edge rewrites owning the domain, Docker web service with a 1 GB disk pinning max-1-instance/recreate deploys for the in-process scheduler, managed Postgres Basic, Key Value Valkey). Schema flows only through Alembic (`upgrade head` as Render's pre-deploy command; single baseline generated post-M3 against a blank DB). CD is a new `deploy.yml` triggered by `workflow_run` on CI success for `main`, with SHA-pinned, awaited, ordered, verified deploys.

**Tech Stack:** FastAPI 0.139 / Python 3.14 / uvicorn (single worker — design constraint), SQLAlchemy 2.0 async + asyncpg, Alembic, Valkey via redis-py, React 19 + Vite (static build), GitHub Actions, Render (blueprint IaC).

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

**Overall:** In progress (execution session claimed 2026-07-18T23:57Z).

| Phase | Status | Ship SHA(s) | Notes |
|---|---|---|---|
| 0 — Render verification spike | ⏸ BLOCKED on Render credential | — | session env lacks `RENDER_API_KEY` (MCP `unauthorized`, curl fallback impossible); docs-based verification substituted — see Deviations D-1 |
| 1 — Collision-free implementation | 🚧 IN PROGRESS (claimed 2026-07-18T23:57Z, branch `claude/m4-phase1-deploy-scaffolding`) | — | proceeding on Topology A (plan default) per Deviation D-1 |
| 2 — Platform provisioning | ⬜ 2a partially done by Sam (billing connected, domain `hangarbay.app`, prod EVE app registered) | — | **Sam-gated**; 2b (blueprint+secrets) runs as Phase 4 Step 0; see Deviation D-3 (callback `:443` mismatch to resolve at 2b) |
| 3 — Post-M3 backend/frontend work | ⬜ Not started | — | gate SATISFIED: M3 merged to dev 2026-07-18 (PR #46, merge `20ee513`) |
| 4 — First deploy + live SSO | ⬜ Not started | — | **Sam-gated exit criterion** |

### Deviations

- **D-1 (Phase 0 blocked → docs-based fallback; topology committed as A pending empirical spike).** The execution session (2026-07-18, autonomous) has no `RENDER_API_KEY` in its environment: the project-scoped Render MCP (`.mcp.json`, `${RENDER_API_KEY}` expansion) returns `unauthorized`, and the plan's curl+API fallback needs the same missing variable. The empirical probes P1–P6 therefore cannot run in this session. Substituted: a documentation-based verification of the same six questions (blueprint field names, deploy-API create/poll shapes + status enums, static-site default headers, rewrite semantics, `fromDatabase` scheme, `RENDER_GIT_COMMIT`), recorded at `docs/audits/m4-recon/render-docs-verification-2026-07-18.md`. Phase 1 proceeds on **Topology A** (the plan's committed default; Appendix B remains the specified contingency). **Unblock condition:** Sam relaunches a session with `RENDER_API_KEY` exported (1Password → env, per `.mcp.json`), then Task 0.1 runs as written; the empirical spike MUST complete before Phase 2b applies the blueprint (its P1/P2 verdict and P2b hostname check gate the apply). `docs/audits/m4-recon/render-spike-results.md` is reserved for the real spike results.
- **D-2 (spike account).** When the spike runs, it may use Sam's real Render account (billing now connected) with free-tier resources only, instead of the plan's throwaway account. Authorized by Sam 2026-07-18.
- **D-3 (prod EVE callback carries `:443`).** Sam registered the prod EVE application with callback `https://hangarbay.app:443/api/v1/auth/sso/callback` (explicit `:443`). At Phase 2b, `ESI_SSO_CALLBACK_URL` must match char-for-char — either set the env var WITH `:443` or Sam first edits the EVE portal to drop it. Decision is Sam's at 2b; surface it then.

### Discoveries

- **Phase 3 file:line citations are stale by several PRs.** Since plan authoring, dev gained M3 (#46), lint-debt (#47), flake8-bugbear (#48), gitignore (#49), pricing verification (#52, #53), and the Render MCP config (#55). Task 3.0's re-anchor is mandatory real work; drift recorded per-task in Deviations as Phase 3 executes.

---

## Standing Orders (read before ANY task)

1. **Authoritative docs:** the spec (path in Goal), `docs/pitfalls/implementation-pitfalls.md`, `docs/pitfalls/testing-pitfalls.md`. Read all three before starting a phase.
2. **M3 collision rule:** Phases 0–2 MUST NOT touch: `app/backend/src/fastapi_app/**` source, `app/backend/.env.example`, `app/frontend/web/src/**`, `app/frontend/web/e2e/**`, `README.md`, `design/features/feature-index.md`, `docs/pitfalls/*` — all M3-touched. Phase 1's allowed surface is exactly: `app/backend/Dockerfile`, `app/backend/.dockerignore`, `app/backend/src/alembic/**`, `app/backend/src/alembic.ini`, `app/backend/src/check_alembic_version.py` (delete), `app/backend/pyproject.toml` (scripts block only), `render.yaml`, `.github/workflows/deploy.yml`, `.github/workflows/ci.yml` (new job only), `docs/**` M4 files.
3. **Branching:** each phase = its own `claude/m4-phase<N>-<slug>` branch off fresh `origin/dev` (`git fetch origin dev` first), PR to dev with a `## Merge classification` heading. Phase 1 config/docs PRs → `Routine` (auto-merge on green). Phase 3 PRs touch auth-adjacent startup + data paths → classify `Review — production configuration & data-integrity surfaces` and leave for Sam.
4. **TDD** applies to every Phase 3 task changing `app/backend/src/fastapi_app/**` or `app/frontend/web/src/**`: invoke `superpowers:test-driven-development`, red → green → refactor. Dockerfiles, YAML, `render.yaml`, workflow files, `.env.example`, docs are TDD-exempt but every one carries explicit verification commands.
5. **ENV-3 batching:** Phase 3 backend edits are batched per task; never run the dev server between edits mid-task. Tests run against the test DB (`pdm run pytest`), which is safe.
6. **Assertion rigor:** if any test races or flakes, fix with deterministic synchronization — NEVER weaken an assertion (testing-pitfalls TEST-2 discipline). If synchronization cannot fix it, STOP and escalate.
7. **Secrets:** never in argv, chat, logs, git, or this plan. Phase 2/4 secret entry happens ONLY in the Render dashboard / GitHub Actions secrets UI.

---

## Phase 0 — Render verification spike

**Execution Status:** ⏸ BLOCKED (2026-07-18T23:57Z) — the session environment lacks `RENDER_API_KEY`, so neither the Render MCP nor the curl fallback can create spike resources (Deviation D-1 has the full record and the docs-based substitute). **Unblock:** a session launched with `RENDER_API_KEY` exported runs Task 0.1 as written (Deviation D-2: Sam's real account, free-tier resources only, is authorized). The empirical spike MUST complete before Phase 2b applies the blueprint.

**Purpose (spec §3.5):** prove five load-bearing Render behaviors on the free tier before any billing or topology commitment. No production resources; the spike project is throwaway and deleted at the end.

### Task 0.1: Build the spike probe app and verify all five behaviors

**Files:**
- Create: `docs/audits/m4-recon/render-spike-results.md` (the ONLY repo artifact; the probe app lives in a scratch dir OUTSIDE the repo, e.g. `~/scratch/hb-render-spike/`)

- [ ] **Step 1: Create the probe app** in `~/scratch/hb-render-spike/` (NOT in the repo):

`main.py`:
```python
# ABOUTME: Throwaway echo app for the M4 Render spike — reports exactly what
# ABOUTME: the platform delivered (method, path, body, headers) so edge claims can be verified.
import os
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

app = FastAPI()

@app.api_route("/{full_path:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def echo(full_path: str, request: Request):
    body = await request.body()
    return JSONResponse({
        "method": request.method,
        "raw_path": request.scope["path"],        # exact path seen by the app
        "query": request.scope["query_string"].decode(),
        "body_len": len(body),
        "body_prefix": body[:100].decode(errors="replace"),
        # Scheme ONLY — never any slice of the URL (a prefix slice leaks the username).
        "database_url_scheme": (lambda u: f"{u.partition('://')[0]}://" if "://" in u else "")(os.environ.get("DATABASE_URL", "")),
        "render_git_commit": os.environ.get("RENDER_GIT_COMMIT", "MISSING"),  # P6: release-verification dependency
    })
```

`requirements.txt`:
```
fastapi
uvicorn
```

`Dockerfile`:
```dockerfile
FROM python:3.14-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY main.py .
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]
```

- [ ] **Step 2: Deploy the spike** (free tier, Sam's Render account is NOT needed — a throwaway account on the free tier suffices; no payment method): push the scratch dir to a throwaway GitHub repo; create (a) a free Docker web service from it, (b) a free static site from a 3-file scaffold in the same repo — `index.html`, `404.html`, and `assets/app.abc123.js` (any content; exists so P4 can probe hashed-asset cache headers) — with rewrite rules `Source /api/v1/*` → `Destination https://<spike-service>.onrender.com/*` (first) and `Source /*` → `Destination /index.html` (second), (c) a free Postgres attached to the web service via `fromDatabase` so `DATABASE_URL` is injected.

- [ ] **Step 3: Run the five probes** against the static-site origin and record raw outputs:

```bash
# P1 — POST body pass-through across the cross-service rewrite:
curl -s -X POST "https://<spike-site>.onrender.com/api/v1/auth/sso/callback?code=abc&state=xyz" \
  -H 'Content-Type: application/x-www-form-urlencoded' -d 'grant=body-survives'
# EXPECT: method=POST, raw_path=/auth/sso/callback, query=code=abc&state=xyz,
#         body_len=19 (len("grant=body-survives")), body_prefix echoing the payload.
# The pass/fail criterion is the ECHOED VALUES matching what was sent — if you vary
# the payload, recompute the expected length; do not fail the probe on a stale constant.

# P2 — trailing-slash preservation, both shapes:
curl -s "https://<spike-site>.onrender.com/api/v1/contracts/"   # EXPECT raw_path=/contracts/
curl -s "https://<spike-site>.onrender.com/api/v1/contracts"    # EXPECT raw_path=/contracts (no added slash)

# P2b — rewrite-destination hostname reality check: record the spike service's ACTUAL
# assigned onrender.com hostname from the dashboard. Render suffixes service hostnames
# when the name is taken — the production blueprint's rewrite destination (Task 1.2)
# must use the REAL assigned hostname, verified again at Phase 2b apply time.

# P3 — fromDatabase URL scheme actually injected:
curl -s "https://<spike-site>.onrender.com/api/v1/anything" | jq .database_url_scheme
# EXPECT "postgresql://" (or record what it actually is — this drives Task 3.1)

# P4 — static-site default response headers:
curl -sI "https://<spike-site>.onrender.com/" | grep -iE 'strict-transport|cache-control|content-encoding|^HTTP'
curl -sI "https://<spike-site>.onrender.com/assets/<any-hashed-file>" | grep -iE 'cache-control'
# RECORD which of HSTS / index no-cache / assets immutable / compression Render provides by default

# P6 — RENDER_GIT_COMMIT presence (release verification in deploy.yml and /ready's
# "commit" field depend on it):
curl -s "https://<spike-site>.onrender.com/api/v1/anything" | jq .render_git_commit
# EXPECT: the spike repo's full head SHA, NOT "MISSING".

# P5 — deploy pin + poll mechanism: create a Render API key on the spike account, then:
curl -s -w '\nHTTP %{http_code}\n' -X POST -H "Authorization: Bearer $SPIKE_KEY" -H 'Content-Type: application/json' \
  -d '{"commitId": "<full-sha-of-spike-repo-head>"}' \
  "https://api.render.com/v1/services/<spike-service-id>/deploys" | tee /tmp/p5-create.json
# Then poll: curl -s -H "Authorization: Bearer $SPIKE_KEY" \
#   "https://api.render.com/v1/services/<spike-service-id>/deploys/<deploy-id>" | jq .status
# EXPECT: commitId is honored (deploy builds THAT sha) and status transitions ... -> live.
# RECORD: the exact status enum values observed, AND the create-response shape for BOTH
# 201 Created and 202 Queued — trigger a second create while the first is mid-build to
# capture the 202 body (does it carry an id?). Both shapes drive Task 1.4's poll loop.
```

- [ ] **Step 4: Write `docs/audits/m4-recon/render-spike-results.md`** with an ABOUTME header, the raw curl outputs, and a **verdict block**: `TOPOLOGY: A (static-site rewrites)` if P1 AND P2 both pass exactly, else `TOPOLOGY: B (in-container Caddy — Appendix B)`; plus the P3 scheme string, P4 header gaps table, and P5 status enums.

- [ ] **Step 5: Tear down** the spike services + throwaway repo. Commit the results file:
```bash
git add docs/audits/m4-recon/render-spike-results.md
git commit -m "docs(m4): record Render spike results (edge, URL scheme, headers, deploy API)"
```

**Do NOT:** skip P5 because P1/P2 passed — the deploy mechanism finding gates Task 1.4's poll loop. Do NOT put any spike code in the Hangar Bay repo.

---

## Phase 1 — Collision-free implementation

**Execution Status:** 🚧 IN PROGRESS — claimed 2026-07-18T23:57Z on branch `claude/m4-phase1-deploy-scaffolding` (worktree `.claude/worktrees/m4-phase1-deploy-scaffolding`). Proceeding on Topology A per Deviation D-1; Task 1.2's blueprint-spec field validation and Task 1.4's deploy-API shapes are verified against Render documentation (docs-based, see D-1) rather than the live spike.

Branch: `claude/m4-phase1-deploy-scaffolding` off fresh `origin/dev`. All tasks here are TDD-exempt config/scaffolding EXCEPT nothing — but every task has verification commands. One PR at the end (Routine; single-PR decision is binding — Task 1.6).

### Task 1.1: Backend production Dockerfile

**Files:**
- Create: `app/backend/Dockerfile`
- Create: `app/backend/.dockerignore`

- [ ] **Step 1: Write `app/backend/.dockerignore`:**
```
.venv/
__pycache__/
**/__pycache__/
.pytest_cache/
src/.env
docker/
```

- [ ] **Step 2: Write `app/backend/Dockerfile`:**
```dockerfile
# ABOUTME: Production image for the Hangar Bay FastAPI backend — uvicorn with ONE worker,
# ABOUTME: because the APScheduler ingestion job runs in-process (spec §2: N workers = N schedulers).
FROM python:3.14-slim AS deps
WORKDIR /app
RUN pip install --no-cache-dir pdm
COPY pyproject.toml pdm.lock ./
RUN pdm export --prod -o requirements.txt --without-hashes

FROM python:3.14-slim
WORKDIR /app
COPY --from=deps /app/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY src/ ./src/
ENV PYTHONPATH=/app/src \
    PYTHONUNBUFFERED=1
EXPOSE 8000
# --workers 1 is a design constraint, not a tuning choice (spec §2). Do not raise it.
CMD ["sh", "-c", "uvicorn fastapi_app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1"]
```

- [ ] **Step 3: Verify the image builds and boots prod-shaped** (deps from the dev compose stack; `ENVIRONMENT=production` exercises the fail-closed gate — no DB wipe):
```bash
cd app/backend
docker build -t hb-api-test .
docker run -d --name hb-api-smoke -e ENVIRONMENT=production \
  -e DATABASE_URL='postgresql+asyncpg://hangar:hangar@host.docker.internal:5432/hangar_bay' \
  -e CACHE_URL='redis://host.docker.internal:6379/0' \
  -e ESI_USER_AGENT='hangar-bay-docker-smoke (contact@example.com)' \
  -e AGGREGATION_REGION_IDS='[10000002]' \
  -p 8001:8000 hb-api-test
sleep 5 && curl -sf http://localhost:8001/health          # EXPECT {"status":"ok"}
docker logs hb-api-smoke 2>&1 | grep "Skipping destructive"  # EXPECT the fail-closed skip line
docker rm -f hb-api-smoke
```
Note `AGGREGATION_REGION_IDS` is a JSON array string — ENV-1; a bare int crashes boot.

- [ ] **Step 4: Commit:**
```bash
git add app/backend/Dockerfile app/backend/.dockerignore
git commit -m "build(api): add production Dockerfile (single-worker uvicorn, PDM-exported deps)"
```

**Do NOT** add `--reload`, extra workers, gunicorn, or copy `src/.env` into the image.

### Task 1.2: Render blueprint `render.yaml`

**Files:**
- Create: `render.yaml` (repo root)

- [ ] **Step 1: Write `render.yaml`** (Topology A; if the spike verdict was B, use Appendix B's variant instead and record a Deviation):
```yaml
# ABOUTME: Render blueprint for Hangar Bay production (design spec §4, topology A).
# ABOUTME: Inert until applied in Phase 2; /ready and the pre-deploy migration assume Phase 3 code has merged.
previews:
  generation: off

services:
  - type: web
    name: hangar-bay-api
    runtime: docker
    plan: starter
    region: frankfurt
    branch: main
    autoDeployTrigger: off            # CD (deploy.yml) is the sole trigger
    rootDir: app/backend
    dockerfilePath: ./Dockerfile
    healthCheckPath: /ready
    preDeployCommand: sh -c "cd /app/src && python -m alembic upgrade head"
    disk:                             # exists ONLY to pin max-1-instance + recreate deploys (spec §4/I-3)
      name: scheduler-pin
      mountPath: /var/scheduler-pin
      sizeGB: 1
    envVars:
      - key: ENVIRONMENT
        value: production
      - key: DB_RECREATE_ON_STARTUP
        value: "false"
      - key: AGGREGATION_REGION_IDS
        value: "[10000002]"           # JSON array string — ENV-1
      - key: AGGREGATION_DEV_CONTRACT_LIMIT
        value: "0"                    # disable the silent 100-contract dev cap (spec §2)
      - key: DATABASE_URL
        fromDatabase:
          name: hangar-bay-db
          property: connectionString
      - key: CACHE_URL
        fromService:
          type: keyvalue
          name: hangar-bay-cache
          property: connectionString
      - key: ESI_USER_AGENT
        sync: false                   # names in git, values dashboard-held (I-5)
      - key: ESI_CLIENT_ID
        sync: false
      - key: ESI_CLIENT_SECRET
        sync: false
      - key: TOKEN_CIPHER_KEYS
        sync: false
      - key: METRICS_TOKEN
        sync: false
      - key: ESI_SSO_CALLBACK_URL
        sync: false                   # https://<domain>/api/v1/auth/sso/callback — char-for-char vs EVE portal
      - key: FRONTEND_ORIGIN
        sync: false                   # https://<domain>

  - type: keyvalue
    name: hangar-bay-cache
    plan: free
    region: frankfurt
    maxmemoryPolicy: allkeys-lru      # accepted consequence: sessions evictable under pressure (spec §4)
    ipAllowList: []                   # private-network access only

  - type: web
    name: hangar-bay-web
    runtime: static
    rootDir: app/frontend/web
    buildCommand: npm ci && npm run build
    staticPublishPath: dist
    autoDeployTrigger: off
    routes:                           # ORDER MATTERS: prefix-strip rule before SPA fallback (PROXY-1)
      - type: rewrite
        source: /api/v1/*
        # PLACEHOLDER HOSTNAME: Render suffixes service hostnames when a name is taken.
        # At Phase 2b apply time, verify the API service's ACTUAL assigned hostname in the
        # dashboard and correct this destination in the same change if it differs (spike P2b).
        destination: https://hangar-bay-api.onrender.com/*
      - type: rewrite
        source: /*
        destination: /index.html
    headers:
      - path: /*
        name: Strict-Transport-Security
        value: max-age=31536000; includeSubDomains
        # Drop this rule ONLY if spike P4 recorded Render already sending an equal-or-stronger HSTS header.
      - path: /index.html
        name: Cache-Control
        value: no-cache
      - path: /assets/*
        name: Cache-Control
        value: public, max-age=31536000, immutable

databases:
  - name: hangar-bay-db
    plan: basic-256mb
    region: frankfurt
    postgresMajorVersion: "17"
```

- [ ] **Step 2: Validate field names against the current Blueprint spec** (`render.com/docs/blueprint-spec` — Render renames keys occasionally; the spike account's "New Blueprint" dry-run validates the file). Highest-drift-risk keys to check by name: `autoDeployTrigger` (older schema: `autoDeploy`), the Key Value service's `fromService.property: connectionString`, `previews.generation`, and `postgresMajorVersion`. Fix any renamed keys; record them as a Deviation if they differ from the block above. If the spike's P4 showed Render already sets a Cache-Control header above, keep our explicit cache rules anyway (defense in depth); the HSTS rule alone is conditional per its inline note.

- [ ] **Step 3: Commit:**
```bash
git add render.yaml
git commit -m "build(deploy): add Render blueprint (api + static edge + postgres + valkey)"
```

**Do NOT** put any secret value in this file; `sync: false` entries are name-only by design.

### Task 1.3: Alembic Stage 1 scaffolding (NO baseline revision)

**Files:**
- Delete: `app/backend/src/alembic/versions/*.py` (all six stale revisions)
- Delete: `app/backend/src/check_alembic_version.py`
- Modify: `app/backend/src/alembic/env.py`
- Modify: `app/backend/pyproject.toml` (scripts block)

- [ ] **Step 1: Delete the stale revision chain and the SQLite-era orphan** (they describe a pre-SSO schema that never shipped — spec §5):
```bash
git rm app/backend/src/alembic/versions/*.py app/backend/src/check_alembic_version.py
```

- [ ] **Step 2: Rewrite `env.py`**: delete the metadata-debug print block (current lines 41–60), enable type/server-default comparison, and restore an import-safe CLI invocation tail. The full target file:
```python
# ABOUTME: Alembic environment — async-engine CLI migrations + pytest-injected-connection support.
# ABOUTME: Import-safe: the invocation tail only fires under an alembic-provided context (tests import this module).
import asyncio
import os
import sys

# 'src' (parent of alembic/ and fastapi_app/) must be importable.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.ext.asyncio import create_async_engine

from alembic import context

from fastapi_app.core.config import get_settings
from fastapi_app.db import Base
from fastapi_app.models import user, contracts  # noqa: F401  (registers tables on Base.metadata)

settings = get_settings()
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    config = context.config
    if config.config_file_name is not None:
        fileConfig(config.config_file_name)
    context.configure(
        url=str(settings.DATABASE_URL),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )
    context.run_migrations()


def do_run_migrations(connection):
    """Run migrations on a caller-managed connection/transaction (CLI engine or pytest fixture)."""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
    )
    context.run_migrations()


async def run_migrations_online_async_cli():
    connectable = create_async_engine(
        str(settings.DATABASE_URL),
        poolclass=pool.NullPool,
        future=True,
    )
    async with connectable.begin() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online():
    config = context.config
    if config.config_file_name is not None:
        fileConfig(config.config_file_name)
    connectable = context.config.attributes.get("connection", None)
    if connectable is None:
        asyncio.run(run_migrations_online_async_cli())
    else:
        do_run_migrations(connectable)


def _running_under_alembic() -> bool:
    """True only when alembic's EnvironmentContext is active (i.e. invoked via the alembic CLI/API);
    plain `import env` from pytest must not trigger migrations."""
    try:
        context.config
        return True
    except AttributeError:
        return False


if _running_under_alembic():
    if context.is_offline_mode():
        run_migrations_offline()
    else:
        run_migrations_online()
```
Note the M3 interaction: post-M3, `fastapi_app.models` will export more modules — the wildcard `from fastapi_app.models import user, contracts` line MUST be revisited in Task 3.9 Step 1 to import every model module (or switch to importing the package if its `__init__` registers all models). Leave a matching comment out of the file (comments must be evergreen); this plan is the tracker.

- [ ] **Step 3: Add pdm scripts** in `app/backend/pyproject.toml` `[tool.pdm.scripts]` (after `export-openapi`):
```toml
migrate = {shell = "cd src && python -m alembic upgrade head"}
makemigration = {shell = "cd src && python -m alembic revision --autogenerate -m {args}"}
migrate-check = {shell = "cd src && python -m alembic current"}
```

- [ ] **Step 4: Verify against a BLANK throwaway database** (never the dev DB — ENV-2 wipes are irrelevant here but discipline matters):
```bash
docker exec hangar_bay_postgres psql -U hangar -c 'CREATE DATABASE m4_alembic_scaffold_check;'
cd app/backend
DATABASE_URL='postgresql+asyncpg://hangar:hangar@localhost:5432/m4_alembic_scaffold_check' pdm run migrate
# EXPECT: clean exit, no revisions applied (empty versions/), no debug-print spam.
DATABASE_URL='postgresql+asyncpg://hangar:hangar@localhost:5432/m4_alembic_scaffold_check' pdm run migrate-check
# EXPECT: no current revision (empty history).
pdm run pytest   # EXPECT: full suite still green
docker exec hangar_bay_postgres psql -U hangar -c 'DROP DATABASE m4_alembic_scaffold_check;'
```
Also add an import-safety test (no existing test imports env.py — the safety of plain `import` must be pinned, not assumed) in `app/backend/src/fastapi_app/tests/test_migrations.py` (created here; Task 3.9 extends it):
```python
# ABOUTME: Guards the alembic env.py contract — import-safe outside alembic, migration/model equivalence (Task 3.9).
import importlib.util
from pathlib import Path


def test_alembic_env_import_is_side_effect_free():
    """Importing env.py outside an alembic EnvironmentContext must not run migrations
    (the invocation tail is guarded); reaching the end of the module without error IS the assertion."""
    env_path = Path(__file__).resolve().parents[2] / "alembic" / "env.py"
    spec = importlib.util.spec_from_file_location("alembic_env_import_check", env_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)   # raises if the tail fires without alembic context
    assert callable(module.do_run_migrations)
```

- [ ] **Step 5: Commit:**
```bash
git add -u app/backend/src/alembic app/backend/src/check_alembic_version.py app/backend/pyproject.toml
git commit -m "chore(db): re-baseline Alembic scaffolding — drop stale pre-SSO revisions, import-safe CLI tail, compare flags"
```

**Do NOT** generate any revision in this task (spec §5: the single baseline is generated post-M3 in Task 3.9, against a blank DB).

### Task 1.4: CD workflow `deploy.yml`

**Files:**
- Create: `.github/workflows/deploy.yml`

- [ ] **Step 1: Write the workflow** (substitute the spike's observed deploy-status enums into the poll loop's success/failure sets if they differ):
```yaml
# ABOUTME: Production CD — deploys main to Render only after the CI workflow succeeds on main.
# ABOUTME: SHA-pinned + awaited + ordered (api before static) + release-verified before smoke (spec §7).
name: Deploy

on:
  workflow_run:
    workflows: [CI]
    types: [completed]
    branches: [main]
  workflow_dispatch:
    inputs:
      sha:
        description: Full commit SHA to deploy (rollback = previous good SHA)
        required: true

permissions:
  contents: read

concurrency:
  group: deploy-production        # distinct from CI's ci-${{ github.ref }} group
  cancel-in-progress: false       # queue deploys; never kill one mid-flight

jobs:
  deploy:
    if: github.event_name == 'workflow_dispatch' || github.event.workflow_run.conclusion == 'success'
    runs-on: ubuntu-latest
    timeout-minutes: 40
    env:
      RENDER_API_KEY: ${{ secrets.RENDER_API_KEY }}
      PROD_ORIGIN: ${{ vars.PROD_ORIGIN }}          # e.g. https://hangar-bay.example — repo variable, set in Phase 2
    steps:
      - name: Resolve deploy SHA
        id: sha
        env:
          INPUT_SHA: ${{ github.event.inputs.sha }}
          RUN_SHA: ${{ github.event.workflow_run.head_sha }}
        run: |
          set -euo pipefail
          sha="${INPUT_SHA:-$RUN_SHA}"
          # Untrusted workflow_dispatch input: accept ONLY a full lowercase hex SHA —
          # anything else could corrupt GITHUB_OUTPUT or splice into later commands.
          if ! printf '%s' "$sha" | grep -qE '^[0-9a-f]{40}$'; then
            echo "refusing non-SHA input: $sha"; exit 1
          fi
          echo "sha=$sha" >> "$GITHUB_OUTPUT"

      - name: Deploy backend (pin + poll)
        env:
          SERVICE_ID: ${{ secrets.RENDER_API_SERVICE_ID }}
          DEPLOY_SHA: ${{ steps.sha.outputs.sha }}
        run: |
          set -euo pipefail
          resp=$(curl -s -w '\n%{http_code}' -X POST \
            -H "Authorization: Bearer $RENDER_API_KEY" -H 'Content-Type: application/json' \
            -d "{\"commitId\": \"$DEPLOY_SHA\"}" \
            "https://api.render.com/v1/services/$SERVICE_ID/deploys")
          code=$(tail -1 <<<"$resp"); body=$(sed '$d' <<<"$resp")
          deploy_id=$(jq -r '.id // empty' <<<"$body")
          # 202 Queued may omit the id — resolve it from the deploy list for our commit.
          if [ -z "$deploy_id" ]; then
            echo "create returned HTTP $code without an id; resolving from the deploy list"
            deploy_id=$(curl -sf -H "Authorization: Bearer $RENDER_API_KEY" \
              "https://api.render.com/v1/services/$SERVICE_ID/deploys?limit=10" \
              | jq -r --arg sha "$DEPLOY_SHA" '[.[] | (.deploy // .) | select(.commit.id == $sha)][0].id // empty')
          fi
          [ -n "$deploy_id" ] || { echo "no deploy id for $DEPLOY_SHA (HTTP $code): $body"; exit 1; }
          echo "backend deploy: $deploy_id"
          for i in $(seq 1 120); do
            status=$(curl -sf -H "Authorization: Bearer $RENDER_API_KEY" \
              "https://api.render.com/v1/services/$SERVICE_ID/deploys/$deploy_id" | jq -r .status)
            echo "[$i] $status"
            case "$status" in
              live) exit 0 ;;
              build_failed|update_failed|canceled|pre_deploy_failed|deactivated) echo "deploy failed: $status"; exit 1 ;;
            esac
            sleep 15
          done
          echo "timed out waiting for backend deploy"; exit 1

      - name: Deploy static site (pin + poll)
        env:
          SERVICE_ID: ${{ secrets.RENDER_STATIC_SERVICE_ID }}
          DEPLOY_SHA: ${{ steps.sha.outputs.sha }}
        run: |
          set -euo pipefail
          resp=$(curl -s -w '\n%{http_code}' -X POST \
            -H "Authorization: Bearer $RENDER_API_KEY" -H 'Content-Type: application/json' \
            -d "{\"commitId\": \"$DEPLOY_SHA\"}" \
            "https://api.render.com/v1/services/$SERVICE_ID/deploys")
          code=$(tail -1 <<<"$resp"); body=$(sed '$d' <<<"$resp")
          deploy_id=$(jq -r '.id // empty' <<<"$body")
          if [ -z "$deploy_id" ]; then
            echo "create returned HTTP $code without an id; resolving from the deploy list"
            deploy_id=$(curl -sf -H "Authorization: Bearer $RENDER_API_KEY" \
              "https://api.render.com/v1/services/$SERVICE_ID/deploys?limit=10" \
              | jq -r --arg sha "$DEPLOY_SHA" '[.[] | (.deploy // .) | select(.commit.id == $sha)][0].id // empty')
          fi
          [ -n "$deploy_id" ] || { echo "no deploy id for $DEPLOY_SHA (HTTP $code): $body"; exit 1; }
          echo "static deploy: $deploy_id"
          for i in $(seq 1 60); do
            status=$(curl -sf -H "Authorization: Bearer $RENDER_API_KEY" \
              "https://api.render.com/v1/services/$SERVICE_ID/deploys/$deploy_id" | jq -r .status)
            echo "[$i] $status"
            case "$status" in
              live) exit 0 ;;
              build_failed|update_failed|canceled|deactivated) echo "deploy failed: $status"; exit 1 ;;
            esac
            sleep 10
          done
          echo "timed out waiting for static deploy"; exit 1

      - name: Verify deployed release
        run: |
          set -euo pipefail
          for i in $(seq 1 40); do
            body=$(curl -sf "$PROD_ORIGIN/api/v1/ready" || true)
            commit=$(jq -r '.commit // empty' <<<"$body" 2>/dev/null || true)
            if [ "$commit" = "${{ steps.sha.outputs.sha }}" ]; then echo "release verified: $commit"; exit 0; fi
            echo "[$i] ready=$body"
            sleep 15
          done
          echo "deployed release never matched ${{ steps.sha.outputs.sha }}"; exit 1

  smoke:
    needs: deploy
    runs-on: ubuntu-latest
    timeout-minutes: 15
    defaults:
      run:
        working-directory: app/frontend/web
    steps:
      - uses: actions/checkout@v7
        with:
          ref: ${{ github.event.inputs.sha || github.event.workflow_run.head_sha }}
      - uses: actions/setup-node@v6
        with:
          node-version: '22'
          cache: npm
          cache-dependency-path: app/frontend/web/package-lock.json
      - run: npm ci
      - run: npx playwright install --with-deps chromium
      - name: Live smoke against production
        run: E2E_LIVE=1 E2E_PROD_BASE_URL="${{ vars.PROD_ORIGIN }}" npx playwright test --project=live-smoke-prod
```

- [ ] **Step 2: Verify syntax** without a deploy: `gh workflow view` after push, plus `actionlint .github/workflows/deploy.yml` if available (`brew install actionlint` — optional). The workflow is inert until the Phase 2 secrets (`RENDER_API_KEY`, `RENDER_API_SERVICE_ID`, `RENDER_STATIC_SERVICE_ID`) and the `PROD_ORIGIN` repo variable exist AND a push lands on `main` — safe to merge now.

- [ ] **Step 3: Commit:**
```bash
git add .github/workflows/deploy.yml
git commit -m "ci(deploy): add CI-gated, SHA-pinned Render deploy workflow with release verification + prod smoke"
```

**Do NOT** reuse CI's concurrency group, add `push:` triggers, or widen `permissions`. The `.commit` field on `/ready` is delivered by Task 3.4 — the two MUST stay consistent (release verification reads it).

### Task 1.5: OpenAPI drift job in CI

**Files:**
- Modify: `.github/workflows/ci.yml` (append one job — touch NOTHING else in the file)

- [ ] **Step 1: Append** to `ci.yml` after the `frontend` job (same indentation level under `jobs:`):
```yaml
  openapi-drift:
    # The committed openapi.json / schema.d.ts must match what the backend exports —
    # neither existing job runs the export chain, so drift was previously invisible.
    runs-on: ubuntu-latest
    timeout-minutes: 10
    steps:
      - uses: actions/checkout@v7
      - uses: actions/setup-python@v6
        with:
          python-version: '3.14'
      - uses: pdm-project/setup-pdm@v4
        with:
          python-version: '3.14'
      - name: Install backend deps
        working-directory: app/backend
        run: pdm install -G dev
      - name: Export OpenAPI schema
        working-directory: app/backend
        run: pdm run export-openapi
      - uses: actions/setup-node@v6
        with:
          node-version: '22'
          cache: npm
          cache-dependency-path: app/frontend/web/package-lock.json
      - name: Regenerate typed client
        working-directory: app/frontend/web
        run: npm ci && npm run generate:api
      - name: Fail on drift
        run: |
          git diff --exit-code -- app/frontend/web/openapi.json app/frontend/web/src/lib/api/schema.d.ts \
            || { echo '::error::openapi.json / schema.d.ts are stale — run pdm run export-openapi && npm run generate:api and commit'; exit 1; }
```

- [ ] **Step 2: Verify locally** that the chain is currently clean (else this job would break CI on merge):
```bash
cd app/backend && pdm run export-openapi
cd ../frontend/web && npm run generate:api
git diff --stat -- app/frontend/web/openapi.json app/frontend/web/src/lib/api/schema.d.ts   # EXPECT: empty
```
If it is NOT clean, STOP: the drift predates M4 — but `openapi.json`/`schema.d.ts` are M3-regenerated files inside the Phase-1 forbidden surface (Standing Order 2), so do NOT commit a regeneration in Phase 1. Record a Discovery, drop Task 1.5 from the Phase-1 PR entirely, and re-run it as the FIRST Phase-3 commit (post-M3, when regenerating cannot collide).

- [ ] **Step 3: Commit:**
```bash
git add .github/workflows/ci.yml
git commit -m "ci: add OpenAPI drift gate (export + regenerate + fail on dirty diff)"
```

### Task 1.6: Phase 1 PR

- [ ] **Step 1:** Push and open ONE PR to dev titled `build(m4): phase 1 — deploy scaffolding (Dockerfile, blueprint, Alembic stage 1, CD workflow, drift gate)`, body listing the five tasks + `## Merge classification` → `Routine`. Single PR — do NOT split by task (five small config surfaces review together; splitting creates ordering ambiguity for zero review benefit). Auto-merge on green CI (`gh pr merge --merge --delete-branch`), one-writer rule: check `gh pr list` first; do not touch dev while the M3 session is mid-merge.
- [ ] **Step 2:** Update this plan's banners + Execution Status table; commit the plan update.

---

## Phase 2 — Platform provisioning (SAM-GATED)

**Execution Status:** ⏸ DEFERRED pending Sam's platform sign-off, billing, domain choice, and prod EVE app registration. See the design spec §11 (Blocked on Sam) — this phase IS that list, operationalized. The agent's role here is checklist support, not execution.

**SEQUENCING (load-bearing):** this phase is split. **2a needs nothing** and can happen any time. **2b MUST wait until the release PR carrying Phases 1 AND 3 has merged to `main`** — the blueprint reads from `main`, its `healthCheckPath: /ready` and pre-deploy `alembic upgrade head` are Phase 3 code, and applying the blueprint triggers an initial deploy: applied too early, that first deploy fails its own health check (no `/ready`) with an empty migration history. 2b is therefore executed as Phase 4 Step 0.

**Sam's checklist — 2a (any time, no deploy dependency):**
1. Approve Render + billing (~$14–24/mo, spec §3.3) — or veto with a runner-up pick (spec §3.4 keeps Fly/VPS decidable without new recon).
2. Register/choose the production domain.
3. developers.eveonline.com: create the PRODUCTION application (separate from dev), callback `https://<domain>/api/v1/auth/sso/callback`, zero scopes. Keep the client id/secret for 2b step 3 — in the EVE portal only, nowhere else yet.
4. Create the Render workspace (no services yet) and a Render API key; GitHub repo: add Actions secrets `RENDER_API_KEY`, and repo variable `PROD_ORIGIN` = `https://<domain>`. (`RENDER_API_SERVICE_ID`/`RENDER_STATIC_SERVICE_ID` don't exist until 2b creates the services.)

**Sam's checklist — 2b (= Phase 4 Step 0, AFTER Phases 1+3 are on `main`):**
1. **Generate every secret value BEFORE opening the blueprint flow** (Render prompts for `sync: false` values DURING "New → Blueprint", and applying starts the first deploy — values entered late mean a failed first deploy; late-added `sync: false` declarations on blueprint updates are also ignored by Render): `TOKEN_CIPHER_KEYS` (fresh: `python -c "import base64,os; print(base64.urlsafe_b64encode(os.urandom(32)).decode())"` — run locally, never reuse dev's), `METRICS_TOKEN` (fresh: `python -c "import secrets; print(secrets.token_urlsafe(32))"`), and have ready: `ESI_USER_AGENT` (real contact string), `ESI_CLIENT_ID`/`ESI_CLIENT_SECRET` (from 2a step 3), `ESI_SSO_CALLBACK_URL` = `https://<domain>/api/v1/auth/sso/callback`, `FRONTEND_ORIGIN` = `https://<domain>`.
2. Apply `render.yaml` via "New → Blueprint" pointed at the repo (`main` branch), **entering all step-1 values in the blueprint-creation form itself** (I-5 — dashboard form only, never CLI/chat). Before confirming, verify the API service's assigned hostname matches the rewrite destination in `render.yaml` (spike P2b) — if Render suffixed it, fix the destination on a branch→PR→release first.
3. Add the custom domain to `hangar-bay-web`; set the registrar DNS records Render displays; wait for cert issuance.
4. Add GitHub Actions secrets `RENDER_API_SERVICE_ID` / `RENDER_STATIC_SERVICE_ID` (service IDs from the dashboard URLs of the just-created services).

- [ ] Agent step: when Sam reports 2a/2b completion, record dates + any deviations here and flip the banner.

---

## Phase 3 — Post-M3 backend/frontend work

**Execution Status:** ⏸ DEFERRED pending the M3 account-features merge to dev. See `docs/superpowers/plans/2026-07-17-m3-account-features.md` — its own Execution Status will show the merge; the M3 PR opens as "Review — database schema + per-user data authorization" and Sam merges it. Verify by reading that plan's banner (or `git log origin/dev`), not by grepping for strings.

Branch: `claude/m4-phase3-prod-hardening` off fresh `origin/dev` AFTER the M3 merge. **Every task below cites file:line against pre-M3 dev** — M3 touches most of these files, so Task 3.0 re-anchors every citation first. TDD per Standing Order 4 applies to every task in this phase except 3.9's revision generation, 3.11, and 3.12 (docs/config).

### Task 3.0: Post-merge re-anchor

- [ ] **Step 1:** `git fetch origin dev && git log --oneline -5 origin/dev` — confirm the M3 merge commit is present.
- [ ] **Step 2:** Re-verify each Phase 3 citation (`main.py:140` gate, `background_aggregation.py:150-151`, `db.py:11`, `api/auth.py:36`, `playwright.config.ts:20`, models exported by `fastapi_app/models/__init__.py`). Record every drifted line number in **Deviations** (drift is expected; the anchors are the function/behavior names).
- [ ] **Step 3:** Extend the spec §6 env-inventory table with M3's new Settings fields (enumerate from the merged `core/config.py`; give each a prod value/source), commit as `docs(m4): extend prod env inventory with M3 settings`.

### Task 3.1: `DATABASE_URL` driver-scheme normalization

**Files:**
- Modify: `app/backend/src/fastapi_app/core/config.py`
- Test: `app/backend/src/fastapi_app/tests/core/test_config.py` (or the existing config test module — follow the merged tree's layout)

- [ ] **Step 1 (RED):** invoke `superpowers:test-driven-development`; read `docs/pitfalls/testing-pitfalls.md`. Write:
```python
def test_database_url_plain_postgresql_scheme_is_normalized_to_asyncpg():
    s = Settings(
        DATABASE_URL="postgresql://user:pw@host:5432/db",
        CACHE_URL="redis://localhost:6379/0",
        ESI_USER_AGENT="test-agent",
    )
    assert s.DATABASE_URL == "postgresql+asyncpg://user:pw@host:5432/db"


def test_database_url_asyncpg_scheme_passes_through_unchanged():
    s = Settings(
        DATABASE_URL="postgresql+asyncpg://user:pw@host:5432/db",
        CACHE_URL="redis://localhost:6379/0",
        ESI_USER_AGENT="test-agent",
    )
    assert s.DATABASE_URL == "postgresql+asyncpg://user:pw@host:5432/db"
```
Run: `pdm run pytest src/fastapi_app/tests/core/test_config.py -k normalize -v` → EXPECT FAIL (no normalization).

- [ ] **Step 2 (GREEN):** add to `Settings` (near the existing `AGGREGATION_REGION_IDS` validator):
```python
    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def normalize_database_url_driver(cls, value: Any) -> Any:
        """Render/most managed platforms inject postgresql:// URLs; the async engine and
        Alembic require the asyncpg driver scheme (design spec §4)."""
        if isinstance(value, str) and value.startswith("postgresql://"):
            return "postgresql+asyncpg://" + value[len("postgresql://"):]
        return value
```
Run the two tests → EXPECT PASS. Run the full config test module → green.

- [ ] **Step 3:** Full suite `pdm run pytest` green; commit `fix(api): normalize postgresql:// DATABASE_URL to the asyncpg driver scheme`.

### Task 3.2: Aggregation engine reuse + credential-log removal

**Files:**
- Modify: `app/backend/src/fastapi_app/services/background_aggregation.py` (the per-run engine block, currently `run_aggregation` ~lines 139–158)
- Test: the existing aggregation service test module (follow the merged tree)

- [ ] **Step 1 (RED):** write a test pinning both behaviors — no fresh engine per run, and no URL fragment in logs:
```python
async def test_run_aggregation_reuses_app_session_factory_and_never_logs_database_url(caplog, ...):
    # Arrange: service wired with fakes per the module's existing test fixtures.
    # Act: run one aggregation pass (fake ESI returning one page; fake redis lock).
    # Assert 1: fastapi_app.db.AsyncSessionLocal was the session source —
    #   monkeypatch fastapi_app.services.background_aggregation.AsyncSessionLocal with a
    #   recording wrapper and assert it was entered.
    # Assert 2: no log record contains "DATABASE_URL" content:
    for rec in caplog.records:
        assert "Creating database engine" not in rec.getMessage()
        assert settings.DATABASE_URL[:16] not in rec.getMessage()
```
(Adopt the module's existing fixture idioms exactly; the two asserts are the contract.) Run → EXPECT FAIL.

- [ ] **Step 2 (GREEN):** in `run_aggregation`, delete the local `create_async_engine`/`sessionmaker` block and the `logger.info(f"Creating database engine with URL: ...")` line; import and use the app-level factory:
```python
from ..db import AsyncSessionLocal
```
and replace `local_session_factory` usage with `AsyncSessionLocal`. Delete the `finally: engine.dispose()` bookkeeping that existed only for the per-run engine. Run tests → PASS.

- [ ] **Step 3:** Full suite green (watch for tests that relied on the per-run engine to point at a different DB — if any exist, STOP and re-read their intent before changing them; raise a Deviation rather than weakening). Commit `fix(api): reuse the app engine in aggregation and stop logging DATABASE_URL fragments`.

### Task 3.3: Ingestion-freshness recording

**Files:**
- Modify: `app/backend/src/fastapi_app/services/background_aggregation.py`
- Create: `app/backend/src/fastapi_app/core/metrics.py`
- Test: aggregation service test module

**Semantics (binding; the spec's §8.2 was updated to match in this plan's review cycle):** counters mean **regions CHECKED successfully** — a fetch success AND an ETag-304 not-modified both count as checked-ok (`ESINotModifiedError` at the current `background_aggregation.py:172` branch means ESI answered healthily and our data is already current; a steady-state all-304 run is a SUCCESS, not a failure). `success`/`partial` may be recorded ONLY after the shared transaction commits (or completes as a valid no-op — the all-304 path); any processing/commit/top-level failure forces `outcome="failure"` regardless of fetch counters, because commits are not per-region.

- [ ] **Step 1 (RED):** async tests (house async client/fixture idioms), covering the four outcome paths AND the gauge:
```python
async def test_freshness_success_when_all_regions_fetch_ok(...):
    # fake ESI: all regions return pages; run commits → key has outcome=="success",
    # regions_failed==0, finished_at ISO-8601, last_success_at == finished_at;
    # gauge: last_ingest_success_timestamp._value.get() advanced (capture before/after).

async def test_freshness_success_when_all_regions_304(...):
    # fake ESI: every region raises ESINotModifiedError → outcome=="success" (checked-ok),
    # timestamp advances. THE all-304 steady-state case — the one that must not read as failure.

async def test_freshness_partial_when_one_region_fails(...):
    # region A ok, region B raises a fetch error → outcome=="partial", regions_failed==1,
    # timestamp advances (data did refresh for A).

async def test_freshness_failure_when_commit_raises(...):
    # fetches ok but the transaction commit raises → outcome=="failure",
    # last_success_at preserves the PRIOR success value (seed the key first),
    # gauge unchanged (capture before/after).
```
Pin the exact key contract in the test file's docstring: JSON `{"finished_at": iso, "outcome": "success|partial|failure", "regions_ok": int, "regions_failed": int, "last_success_at": iso-or-null}` at key `hangar-bay:ingest:last_run`, no TTL; `regions_ok` counts checked-ok (fetched OR 304). Isolate gauge state between tests (read the gauge value before acting; assert on the delta, not absolutes). Run → FAIL.

- [ ] **Step 2 (GREEN):** implement. `core/metrics.py`:
```python
# ABOUTME: Process-global Prometheus instruments that are not per-request (the
# ABOUTME: instrumentator owns HTTP metrics; this module owns job/ingestion gauges).
from prometheus_client import Gauge

last_ingest_success_timestamp = Gauge(
    "hangar_bay_last_ingest_success_timestamp",
    "Unix time of the last aggregation run that committed data (success or partial).",
)
```
In `background_aggregation.py`, three wiring changes:
1. `_concurrency_lock` currently yields nothing and closes its private redis client on exit — change it to `yield redis_client` and consume as `async with self._concurrency_lock() as redis_client:` so the outcome write happens INSIDE the lock context with a live client. The top-level-abort recording (outcome `failure`) must also happen inside that context (before the lock releases), from an `except` that re-raises after recording.
2. Count per-region results in the existing region loop: fetch success increments `ok`; the `ESINotModifiedError` branch (current line 172) ALSO increments `ok` (checked-ok — see Semantics above); the generic fetch-error branch (current `logger.error("Failed to fetch contracts for region ...")` site) increments `failed`.
3. Call `_record_run_outcome` at exactly two sites: after the shared transaction commits (current "finished successfully" site — outcome derived from counters) and in the failure exit (forced `outcome="failure"`). A failure of the outcome WRITE itself is logged at warning and swallowed — freshness recording must never turn a successful ingest into a failed job:
```python
async def _record_run_outcome(self, redis_client, ok: int, failed: int, *, forced_failure: bool = False) -> None:
    if forced_failure:
        outcome = "failure"
    else:
        outcome = "success" if failed == 0 and ok > 0 else ("partial" if ok > 0 else "failure")
    now = datetime.now(timezone.utc).isoformat()
    prior_raw = await redis_client.get(INGEST_LAST_RUN_KEY)
    prior_success = None
    if prior_raw:
        try:
            prior_success = json.loads(prior_raw).get("last_success_at")
        except (ValueError, TypeError):
            prior_success = None
    last_success_at = now if outcome in ("success", "partial") else prior_success
    await redis_client.set(INGEST_LAST_RUN_KEY, json.dumps({
        "finished_at": now,
        "outcome": outcome,
        "regions_ok": ok,
        "regions_failed": failed,
        "last_success_at": last_success_at,
    }))
    if outcome in ("success", "partial"):
        last_ingest_success_timestamp.set_to_current_time()
```
with `INGEST_LAST_RUN_KEY = "hangar-bay:ingest:last_run"` beside the lock-key constant, and the whole `_record_run_outcome` body wrapped in `try/except Exception: logger.warning("failed to record ingest outcome", exc_info=True)` per wiring rule 3. Lock-not-acquired skips recording — a skipped run is not a run. Run tests → PASS; full suite green.

- [ ] **Step 3:** Commit `feat(api): record ingestion freshness (outcome + last-success) to Valkey and a Prometheus gauge`.

### Task 3.4: `/ready` readiness endpoint

**Files:**
- Create: `app/backend/src/fastapi_app/api/ops.py`
- Modify: `app/backend/src/fastapi_app/main.py` (router include only)
- Test: `app/backend/src/fastapi_app/tests/api/test_ops.py`

- [ ] **Step 1 (RED):** ASYNC tests via the house async `httpx.AsyncClient` fixture — every call is `await client.get(...)` with the module's async marker. The house `client` fixture wires only the DB override; these tests MUST also override the cache dependency (`app.dependency_overrides[get_cache] = ...` returning the fake redis) or `/ready`'s cache probe hits nothing:
```python
async def test_ready_ok_reports_db_cache_and_freshness(client, fake_cache_override):
    # healthy db (SELECT 1 works against the test DB), fake redis seeded with a fresh
    # ingest record (finished_at=now, outcome="success", last_success_at=now)
    r = await client.get("/ready")
    assert r.status_code == 200
    body = r.json()
    assert body["db"] == "ok" and body["cache"] == "ok"
    assert body["last_ingest_outcome"] == "success"
    assert body["last_ingest_age_seconds"] < 60
    assert body["data_stale"] is False
    assert body["commit"]  # release identifier (RENDER_GIT_COMMIT or "unknown")

async def test_ready_503_when_db_down(...):      # db override raises → 503, body["db"]=="error"
async def test_ready_503_when_db_hangs(...):     # db override awaits past the timeout → 503, body["db"]=="error" (asyncio.timeout path)
async def test_ready_503_when_cache_down(...):   # fake redis ping raises → 503, body["cache"]=="error"
async def test_ready_503_when_cache_hangs(...):  # fake redis ping sleeps past the timeout → 503 (timeout path)
async def test_ready_stale_flag_when_ingest_old(...):
    # last_success_at = now - 3 * AGGREGATION_SCHEDULER_INTERVAL_SECONDS → 200, data_stale True
async def test_ready_null_freshness_before_first_run(...):
    # no ingest key → 200, last_ingest_age_seconds None, data_stale True (never-ingested IS stale)
```
Run → FAIL (no route).

- [ ] **Step 2 (GREEN):** `api/ops.py`:
```python
# ABOUTME: Operational endpoints — /ready (dependency + freshness readiness; deploy health gate).
# ABOUTME: /health (in main.py) stays the dependency-free liveness stub per observability-spec §2.5.
import asyncio
import json
import os
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Response
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config import get_settings
from ..core.dependencies import get_cache
from ..db import get_db          # get_db lives in db.py, NOT core/dependencies (verified)
from ..services.background_aggregation import INGEST_LAST_RUN_KEY

router = APIRouter(tags=["Ops"])  # bare mount (PROXY-1)

READINESS_CHECK_TIMEOUT_SECONDS = 2.0  # spec §8.1: short timeouts so /ready never hangs a deploy gate


@router.get("/ready")
async def ready(response: Response, db: AsyncSession = Depends(get_db), cache=Depends(get_cache)):
    settings = get_settings()
    checks: dict[str, object] = {
        "commit": os.environ.get("RENDER_GIT_COMMIT", "unknown"),
    }
    healthy = True
    try:
        async with asyncio.timeout(READINESS_CHECK_TIMEOUT_SECONDS):
            await db.execute(text("SELECT 1"))
        checks["db"] = "ok"
    except Exception:            # includes TimeoutError — a hung probe is an unhealthy component
        checks["db"] = "error"
        healthy = False
    freshness = None
    try:
        async with asyncio.timeout(READINESS_CHECK_TIMEOUT_SECONDS):
            await cache.ping()
            freshness = await cache.get(INGEST_LAST_RUN_KEY)
        checks["cache"] = "ok"
    except Exception:
        checks["cache"] = "error"
        healthy = False
    age = None
    outcome = None
    if freshness:
        try:
            record = json.loads(freshness)
            outcome = record.get("outcome")
            last_success = record.get("last_success_at")
            if last_success:
                age = (datetime.now(timezone.utc) - datetime.fromisoformat(last_success)).total_seconds()
        except (ValueError, TypeError):
            pass
    checks["last_ingest_age_seconds"] = age
    checks["last_ingest_outcome"] = outcome
    # Never-ingested or over 2x the cadence counts as stale; staleness NEVER fails
    # readiness (observability-spec §2.5: ESI trouble is a freshness signal, not unreadiness).
    checks["data_stale"] = age is None or age > 2 * settings.AGGREGATION_SCHEDULER_INTERVAL_SECONDS
    if not healthy:
        response.status_code = 503
    return checks
```
`main.py`: `from .api import ops as ops_router` + `app.include_router(ops_router.router)` beside the existing includes. Import sources are as shown in the code block — `get_cache` from `core/dependencies.py`, `get_db` from `db.py`; Task 3.0 re-verifies both survive the M3 merge at those locations. Run tests → PASS; full suite green.

- [ ] **Step 3:** Commit `feat(api): add /ready readiness probe (db + cache + ingestion freshness + release commit)`.

### Task 3.5: Gate `/metrics`; Task 3.6: delete `/cache-test`

**Files:**
- Modify: `app/backend/src/fastapi_app/main.py`, `app/backend/src/fastapi_app/core/config.py`
- Test: `app/backend/src/fastapi_app/tests/test_main.py` (or merged-tree equivalent)

- [ ] **Step 1 (RED):** async tests (house async client; token via `monkeypatch` on the settings singleton — no bespoke fixture needed):
```python
async def test_metrics_open_when_no_token_configured(client):
    assert (await client.get("/metrics")).status_code == 200

async def test_metrics_401_without_bearer_when_token_set(client, monkeypatch):
    monkeypatch.setattr(settings, "METRICS_TOKEN", SecretStr("test-metrics-token"))
    assert (await client.get("/metrics")).status_code == 401

async def test_metrics_200_with_correct_bearer(client, monkeypatch):
    monkeypatch.setattr(settings, "METRICS_TOKEN", SecretStr("test-metrics-token"))
    r = await client.get("/metrics", headers={"Authorization": "Bearer test-metrics-token"})
    assert r.status_code == 200
    assert b"hangar_bay" in r.content

async def test_cache_test_endpoint_is_gone(client):
    assert (await client.get("/cache-test")).status_code == 404
```
Run → FAIL.

- [ ] **Step 2 (GREEN):** `config.py` gains `METRICS_TOKEN: SecretStr = SecretStr("")`. In `main.py`: remove `instrumentator.expose(app, ...)` (KEEP `instrumentator.instrument(app)`), delete the whole `/cache-test` route (its `CASCADE-PROD-CHECK` comment is the instruction), and add:
```python
from fastapi import HTTPException           # main.py does not currently import this — add it
from fastapi.responses import PlainTextResponse
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

@app.get("/metrics", include_in_schema=False)
async def metrics(request: Request):
    token = settings.METRICS_TOKEN.get_secret_value()
    if token and request.headers.get("authorization") != f"Bearer {token}":
        raise HTTPException(status_code=401, detail="Unauthorized")
    return PlainTextResponse(generate_latest(), media_type=CONTENT_TYPE_LATEST)
```
Run tests → PASS; full suite green (fix any test that exercised `/cache-test` by deleting it with the endpoint — it tested a dev scratch route, not production logic).

- [ ] **Step 3:** Commit `feat(api): bearer-gate /metrics via METRICS_TOKEN and remove the dev /cache-test endpoint`.

### Task 3.7: Production SSO configuration diagnostic

**Files:**
- Modify: `app/backend/src/fastapi_app/main.py` (replace `warn_if_sso_unconfigured`)
- Test: `test_main.py` / merged-tree equivalent

- [ ] **Step 1 (RED):** tests per spec §6's two tiers:
```python
def test_sso_wholly_unconfigured_warns_and_boots(...):        # empty id+cipher, any ENVIRONMENT → warning log, no raise
def test_sso_partial_config_fails_startup_in_production(...): # id set, secret empty, ENVIRONMENT=production → RuntimeError naming ESI_CLIENT_SECRET
def test_sso_localhost_urls_fail_startup_in_production(...):  # id+secret+cipher set, callback contains localhost → RuntimeError naming ESI_SSO_CALLBACK_URL
def test_sso_partial_config_only_warns_in_development(...):   # same partial config, ENVIRONMENT=development → warning, no raise
```
**Partial-config matrix (production):** parametrize over EVERY subset of `{ESI_CLIENT_ID, ESI_CLIENT_SECRET, TOKEN_CIPHER_KEYS}` that is non-empty but not the full set — including secret-set-but-id-empty and cipher-set-but-id-empty (a leftover credential with no client id is just as much a deploy mistake as the reverse) — each must raise with the missing fields named. Localhost check: any of the three configured AND `localhost` in callback/origin → raise naming the URL field. The wholly-empty set is the only warn-and-continue state.

Test mechanism: call `validate_sso_configuration()` DIRECTLY with monkeypatched settings values (`monkeypatch.setattr` on the settings singleton fields). PLUS one lifespan-wiring test proving startup actually invokes it (the rename must not silently orphan the call site): monkeypatch a production+partial settings combination AND patch the lifespan's external initializers (`init_cache`, `init_http_client`, `create_scheduler` — patch at their `fastapi_app.main` import sites), then assert `with pytest.raises(RuntimeError): async with app.router.lifespan_context(app): pass`. Run → FAIL.

- [ ] **Step 2 (GREEN):** replace `warn_if_sso_unconfigured` with `validate_sso_configuration()` implementing exactly the Step-1 matrix: the trio is `{ESI_CLIENT_ID, ESI_CLIENT_SECRET, TOKEN_CIPHER_KEYS}` (cipher via `is_token_cipher_configured()`); ALL empty → `logger.warning` in every environment, continue; in `production`, ANY non-empty proper subset of the trio → `raise RuntimeError("SSO misconfiguration: missing <named empty fields>")`, and (also production) any of the trio set while `"localhost"` appears in `ESI_SSO_CALLBACK_URL` or `FRONTEND_ORIGIN` → `raise RuntimeError` naming the URL field; outside production, those same states log a warning and continue; full-trio-plus-real-URLs → silent. Call site in `lifespan` unchanged. Run → PASS; full suite green.

- [ ] **Step 3:** Commit `feat(api): fail fast on partial or localhost SSO configuration in production`.

### Task 3.8: Engine pool tuning

**Files:**
- Modify: `app/backend/src/fastapi_app/db.py:11-15`

- [ ] **Step 1 (RED):** in the config/db test module:
```python
def test_engine_pool_production_settings():
    from fastapi_app.db import async_engine
    # _pre_ping/_max_overflow are private pool attrs — version-coupled to SQLAlchemy 2.x;
    # if a bump breaks these, fix the ATTRIBUTE ACCESS, never the config being asserted.
    assert async_engine.pool._pre_ping is True
    assert async_engine.pool.size() == 5
    assert async_engine.pool._max_overflow == 5
```
- [ ] **Step 2 (GREEN):**
```python
async_engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.ENVIRONMENT == "development",
    future=True,
    pool_pre_ping=True,   # managed-PG restarts/pooler idle-kills must not surface as request 500s
    pool_size=5,          # Render Basic's connection budget is small; scheduler + API share it
    max_overflow=5,
)
```
Full suite green. Commit `feat(api): pre-ping + bounded pool on the app engine for managed Postgres`.

### Task 3.9: Alembic Stage 2 — the single baseline + equivalence guard

**Files:**
- Modify: `app/backend/src/alembic/env.py` (model imports — cover ALL merged model modules)
- Create: `app/backend/src/alembic/versions/<rev>_baseline.py` (generated, then hand-reviewed)
- Test: `app/backend/src/fastapi_app/tests/test_migrations.py`

- [ ] **Step 1:** Update `env.py`'s model imports to the merged model set — import exactly the module list `fastapi_app/models/__init__.py` exports post-M3 (M3's plan puts the three new models in a single `models/account.py`, so the expected line is `from fastapi_app.models import user, contracts, account  # noqa: F401` — but the merged `__init__.py` is authoritative, not this example).
- [ ] **Step 2: Generate the baseline against a BLANK database** (spec §5 — autogen against a populated dev DB diffs to empty):
```bash
docker exec hangar_bay_postgres psql -U hangar -c 'CREATE DATABASE m4_baseline_gen;'
cd app/backend
DATABASE_URL='postgresql+asyncpg://hangar:hangar@localhost:5432/m4_baseline_gen' \
  pdm run makemigration "baseline"
```
- [ ] **Step 3: Hand-review the generated revision** against the checklist (spec §5 autogen hazards): partial unique index on `notifications` MUST carry `postgresql_where` matching the model predicate EXACTLY (SQLA-2); no invented server defaults for `is_ship_contract`/`item_processing_status`; FKs/ondelete match the models; the self-referential `esi_market_group_cache` FK present; M3's `users.watchlist_alerts_enabled` server default preserved. Fix by editing the revision, re-verifying with a fresh blank DB.
- [ ] **Step 4 (equivalence guard, RED-then-GREEN):** `test_migrations.py`:
```python
# ABOUTME: Guards baseline-migration <-> model-metadata equivalence so schema drift
# ABOUTME: cannot accumulate silently once production schema flows through Alembic only.
import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import create_engine

from fastapi_app.db import Base


def test_migrated_schema_matches_model_metadata(blank_migrated_sync_connection):
    """blank_migrated_sync_connection: session-scoped fixture that creates a disposable
    database, runs `alembic upgrade head` against it (env.py's do_run_migrations with an
    injected connection — the house pattern), and yields a sync connection."""
    ctx = MigrationContext.configure(blank_migrated_sync_connection)
    diff = compare_metadata(ctx, Base.metadata)
    assert diff == [], f"schema drift between migrations and models: {diff}"
```
The fixture uses the standard alembic-API pattern (env.py's `run_migrations_online` consumes the injected connection). NOTE: `conftest.py` has NO database create/drop helper (the test DB is created by CI / the operator), so this fixture owns the full lifecycle — complete code, not an idiom reference:
```python
@pytest.fixture(scope="session")
def blank_migrated_sync_connection():
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import create_engine, text
    from sqlalchemy.engine import make_url

    from fastapi_app.core.config import settings

    base_url = make_url(str(settings.DATABASE_URL_TESTS)).set(drivername="postgresql+psycopg2")
    equiv_url = base_url.set(database="m4_equiv_check")
    admin = create_engine(base_url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(text("DROP DATABASE IF EXISTS m4_equiv_check (FORCE)"))  # tolerate a prior failed run
        conn.execute(text("CREATE DATABASE m4_equiv_check"))
    engine = create_engine(equiv_url)
    try:
        with engine.connect() as conn:
            cfg = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
            cfg.attributes["connection"] = conn
            command.upgrade(cfg, "head")
            conn.commit()
            yield conn
    finally:
        engine.dispose()
        with admin.connect() as conn:
            conn.execute(text("DROP DATABASE IF EXISTS m4_equiv_check (FORCE)"))
        admin.dispose()
```
(`WITH (FORCE)` needs Postgres ≥13 — CI runs 16, compose runs ≥16; adjust `parents[2]` if the test file's depth differs from `tests/test_migrations.py` → `src/alembic.ini`.) Run → PASS. Full suite green.
- [ ] **Step 5:** Run the same upgrade twice (idempotency: second run applies nothing) and `pdm run migrate-check` shows the baseline as current. Drop the scratch DBs. Commit `feat(db): generate the post-M3 baseline revision with a migration<->metadata equivalence guard`.

### Task 3.10: `live-smoke-prod` Playwright project

**Files:**
- Modify: `app/frontend/web/playwright.config.ts`

- [ ] **Step 1:** Add after the existing `live-smoke` project (and make `webServer` conditional):
```ts
    ...(process.env.E2E_PROD_BASE_URL
      ? [{
          name: 'live-smoke-prod',
          testMatch: /live-smoke/,
          use: {
            ...devices['Desktop Chrome'],
            viewport: { width: 1280, height: 800 },
            baseURL: process.env.E2E_PROD_BASE_URL,
            ignoreHTTPSErrors: false,   // production must present a valid cert
          },
        }]
      : []),
```
and change the `webServer` block to `webServer: process.env.E2E_PROD_BASE_URL ? undefined : { ...existing config unchanged... }` — the prod lane must NEVER boot a local dev server.
- [ ] **Step 2:** Verify: `npx tsc -b` clean; `npm run e2e` (fixture lanes unchanged, still green); `E2E_PROD_BASE_URL=https://example.invalid npx playwright test --project=live-smoke-prod --list` lists the specs without starting a server. Check the live-smoke spec itself for hardcoded origins (recon flagged `live-smoke.spec.ts:29-33`) — it must derive URLs from `baseURL`; fix if not (Deviation note).
- [ ] **Step 3:** Commit `test(e2e): add prod-targeting live-smoke project (env-driven baseURL, no webServer)`.

### Task 3.11: `.env.example` production section

- [ ] Append a commented `# --- production deployment (Render dashboard, NEVER this file) ---` block to `app/backend/.env.example` documenting every §6-inventory var, its prod source (blueprint literal / fromDatabase / dashboard secret), and the two generation one-liners (cipher key, metrics token). Commit `docs(api): document the production env contract in .env.example`.

### Task 3.12: Pitfalls entries + Phase 3 PR

- [ ] **Step 1:** Add to `docs/pitfalls/implementation-pitfalls.md` (full maintenance checklist in its Appendix C — TOC, checklist item, Appendix B row, changelog): **DEPLOY-1** "Managed platforms inject `postgresql://` URLs; the async stack needs `postgresql+asyncpg://` — normalize in Settings, never hand-edit platform URLs" (Where It Bit Us: M4 codex design review, pre-deploy); **DEPLOY-2** "uvicorn stays `--workers 1`: the APScheduler runs in-process, so N workers = N schedulers racing the ingestion lock every tick — scale reads by splitting the scheduler out, not by adding workers."
- [ ] **Step 2:** Batch-review the whole phase — minimum 3 rounds, keep going past 3 if a round still finds issues: (round A) self-review vs spec §§4-8; (round B) pitfalls-checklist pass; (round C) a dispatched fresh-eyes reviewer reading the full phase diff. Round C's dispatch prompt MUST carry the ORCH-1 mandatory-persistence block from `docs/git-strategy.md` §Output persistence with the absolute path `<worktree>/docs/audits/m4-phase3-review/round-C-fresh-eyes.md` (one file per additional round: `round-D-….md`, …), and each round's report file is committed before consolidation.
  Then run the full gates:
```bash
cd app/backend && pdm run lint && pdm run pytest
cd ../frontend/web && npx tsc -b && npm run test && npm run e2e   # e2e = fixture lanes; no env vars needed
```
  Then PR to dev: `feat(m4): phase 3 — production hardening (readiness, freshness, metrics gate, SSO fail-fast, Alembic baseline)` with `## Merge classification` → `Review — production configuration & data-integrity surfaces`. **Sam merges.**
- [ ] **Step 3:** Update this plan's banners/table; commit.

---

## Phase 4 — First production deploy + live SSO verification (SAM-GATED exit)

**Execution Status:** ⏸ DEFERRED pending Phases 1–3 shipped AND Phase 2a provisioning complete. Verify by this plan's own table.

- [ ] **Step 0 (release + provision):** open the dev→main publication PR per `docs/git-strategy.md` §Release branch carrying Phases 1+3. On merge, CI runs on `main`; `deploy.yml` fires but **fails at the deploy step** (no `RENDER_API_SERVICE_ID` yet) — expected, not an error to chase. Sam then executes **Phase 2b** (apply blueprint, domain/DNS, dashboard secrets, service-ID Actions secrets). The blueprint's initial deploy IS the first schema-creating deploy — watch pre-deploy run `alembic upgrade head` on the fresh DB.
- [ ] **Step 1 (pipeline deploy):** re-run `deploy.yml` via `workflow_dispatch` with the released SHA to prove the full pipeline: backend deploy, static deploy, release verification, smoke.
- [ ] **Step 2 (verify):** `curl -s https://<domain>/api/v1/ready | jq .` → `db: ok`, `cache: ok`, `commit` = released SHA; `data_stale: true` initially, flipping false after the first scheduler tick; contracts appear in the SPA. `curl -s -o /dev/null -w '%{http_code}' https://<domain>/metrics` → 401 (token required).
- [ ] **Step 3 (Sam — the M4 exit criterion, spec §9.3):** on the production origin: login → EVE consent → callback → header shows character name → `/me` 200 → logout → 204/anonymous again; plus one denial path (`cancel` on the EVE consent screen → `?sso=denied`, no session). Report results in-session; the agent records them here with date.
- [ ] **Step 4 (rollback drill — do it once while stakes are low):** `workflow_dispatch` deploy.yml with the previous good SHA; confirm `/ready`'s `commit` reverts. Record duration.
- [ ] **Step 5:** Mark the milestone DONE in this plan; write the closing handoff.

---

## Appendix A — Execution strategy recommendation

**Phase 1: subagent-driven** (`superpowers:subagent-driven-development`) — five tasks, five disjoint file sets, each independently verifiable; review between tasks catches config drift cheaply. **Phase 3: fresh-session inline execution** (`superpowers:executing-plans`) — the tasks share `main.py`/`config.py`/the aggregation module and MUST land in order (3.0 → 3.1 → … → 3.9); a single session batching backend edits also honors ENV-3. Phases 0/2/4 are operator runbooks (this session or Sam), not dispatch targets.

## Appendix B — Topology B contingency (spike verdict = B)

If P1 or P2 fails: drop `hangar-bay-web`'s rewrites (keep it deleted entirely), extend `app/backend/Dockerfile` to a two-stage build that also `npm ci && npm run build`s the SPA and installs Caddy, and run Caddy as the service entrypoint with this Caddyfile (spec §3.5 — identical semantics to the Vite dev proxy):
```
:{$PORT} {
    handle_path /api/v1/* {
        reverse_proxy 127.0.0.1:8000
    }
    handle {
        root * /srv/spa
        try_files {path} /index.html
        file_server
    }
}
```
uvicorn moves to a supervised child on `127.0.0.1:8000` (honcho with a 2-line Procfile). `healthCheckPath` becomes `/api/v1/ready` (the path as Caddy sees it; `handle_path` strips the prefix before FastAPI). All other tasks unchanged. Record the swap as a top-of-plan Deviation.

## Appendix C — Pitfall map for this plan

ENV-1 (JSON list env vars — Tasks 1.1/1.2 set `AGGREGATION_REGION_IDS` as a JSON string); ENV-2/ENV-3 (Phase 3 batching; the prod gate is verified in Task 1.1 Step 3); ENV-4 (new Settings fields `METRICS_TOKEN` documented in `.env.example`, Task 3.11); PROXY-1 (rewrite ordering Task 1.2; verbatim paths spike P2; `/api/v1/ready` smoke path Task 1.4); SQLA-2 (partial-index predicate hand-review, Task 3.9 Step 3); ESI-1 (no new ESI routes added; `/meta/status` stays parked per spec §8.4); TEST-2 (no retries added; assertion-rigor Standing Order 6); TEST-6 (Playwright specs stay under `e2e/`, Task 3.10 touches config only); TEST-7 (error-branch tests in 3.4/3.5 drive the endpoint directly, no client retry layer); ORCH-1 (Phase-3 review dispatches carry the mandatory-persistence block with exact absolute file paths — `docs/audits/m4-phase3-review/round-<letter>-<lens>.md` — and each wave is committed before consolidation; see Task 3.12 Step 2).
