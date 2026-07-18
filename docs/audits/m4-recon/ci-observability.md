# M4 Recon — CI Pipeline + Deploy-Gated Observability Backlog

ABOUTME: Read-only recon of Hangar Bay's CI workflow and the observability work deferred to a real deploy, for the M4 (production readiness / deployment) designer.
ABOUTME: Facts only — exact jobs, service containers, cache keys, health-endpoint behavior, and what a CD workflow would have to build that CI does not. No code was modified.

Scope: `.github/workflows/ci.yml`, `design/specifications/observability-spec.md`, backend health/metrics
surface, `app/backend/docker/` observability stack, and the ESI-1 pitfall. All paths below are
relative to `/Users/sam/Code/hangar-bay/.claude/worktrees/hangar-bay-frontend-rebuild-2e4fe7/`.

---

## 1. CI workflow — `.github/workflows/ci.yml`

Two independent jobs, no dependency edge between them (they run in parallel). File header
(`ci.yml:1-2`) states the intent: "backend pytest + frontend lint/types/unit/e2e-fixture. Green CI is
the merge gate the git-strategy merge-authority policy assumes." **There is exactly ONE workflow file
today** — M4 will add a second (deploy) workflow.

### Triggers (`ci.yml:5-14`)

- `push` to `[dev, main]` (`ci.yml:6-7`).
- `pull_request` with **no `branches:` filter** — deliberate. The inline comment (`ci.yml:8-13`)
  explains: a `[dev, main]` base filter would leave stacked phase PRs (based on the previous phase's
  `claude/*` branch) with **no CI run at all**, because the PR filter matches the PR's *base* branch and
  a base-retarget only fires an `edited` event that default activity types don't run on. **A deploy
  workflow must not naively copy a `[dev, main]` filter if it needs to observe stacked PRs** — but a CD
  workflow more likely triggers on `push` to `main`/`dev` or on release tags, which is unaffected.

### Concurrency (`ci.yml:20-23`)

```yaml
concurrency:
  group: ci-${{ github.ref }}
  cancel-in-progress: true
```

Group is `ci-<ref>`. Rapid pushes to the same ref (stacked-PR rebases) supersede in-flight runs. **A
deploy workflow MUST use a DIFFERENT concurrency group** (e.g. `deploy-<ref>` or a single global
`deploy-production` group) — reusing `ci-${{ github.ref }}` would let a CI rebase cancel an in-flight
deploy, and a deploy should generally NOT set `cancel-in-progress: true` (cancelling a half-applied
deploy is dangerous). This is the single most important non-duplication note for M4.

### Permissions (`ci.yml:16-18`)

`permissions: contents: read` — token pinned read-only because nothing in CI uses it. **A deploy
workflow needs MORE** (e.g. `packages: write` to push a container image to GHCR, `id-token: write`
for OIDC cloud auth, `contents: read`). Set these per-job in the new file, not globally.

### Job `backend` (`ci.yml:26-78`)

- `runs-on: ubuntu-latest`, `timeout-minutes: 15`, `working-directory: app/backend` (`ci.yml:27-31`).
- **Service containers** (`ci.yml:32-48`):
  - `postgres:16` — `POSTGRES_USER=hangar / POSTGRES_PASSWORD=hangar / POSTGRES_DB=hangar_bay`, port
    `5432:5432`, healthcheck `pg_isready -U hangar` (interval 5s, 20 retries).
  - `valkey/valkey:7.2` — port `6379:6379`, healthcheck `valkey-cli ping`.
  - Note these images/versions **differ** from the dev compose stack: dev uses `postgres:16-alpine` and
    `valkey/valkey:7.2-alpine` (`compose.dependencies.yml:31,55`). CI's DB name is `hangar_bay`
    (dev's is `hangar_bay_dev`).
- **Env block** (`ci.yml:49-63`) — the CD workflow's runtime env will overlap heavily with this list:
  - `DATABASE_URL=postgresql+asyncpg://hangar:hangar@localhost:5432/hangar_bay`
  - `DATABASE_URL_TESTS=...hangar_bay_test`
  - `CACHE_URL=redis://localhost:6379/0`
  - `ESI_USER_AGENT`, `AGGREGATION_REGION_IDS="[10000002]"` (must be JSON — ENV-1; comment `ci.yml:54-56`),
  - `TOKEN_CIPHER_KEYS=<throwaway Fernet key>` (inline, throwaway CI-only, comment `ci.yml:58-62`).
    **This is a real secret-shaped value committed in plaintext in CI** — acceptable here because it
    only encrypts ephemeral tokens in a throwaway CI DB, but a production deploy MUST source
    `TOKEN_CIPHER_KEYS`, `ESI_CLIENT_SECRET`, DB creds from real secrets (see §5).
- **Steps** (`ci.yml:64-78`): `checkout@v7` → `setup-python@v6` (3.14) → `setup-pdm@v4` (3.14) → manual
  `CREATE DATABASE hangar_bay_test` via psql → `pdm install -G dev` → `pdm run pytest`.
  - Comment `ci.yml:66` mandates the two `python-version` pins (setup-python + setup-pdm) stay in sync.
  - **No dependency cache** on the backend job (no `actions/cache` for PDM/pip). pytest drops+recreates
    `DATABASE_URL_TESTS` per test (conftest behavior) — the manual `CREATE DATABASE` is the one-time bootstrap.

### Job `frontend` (`ci.yml:80-124`)

- `runs-on: ubuntu-latest`, `timeout-minutes: 20`, `working-directory: app/frontend/web` (`ci.yml:81-85`).
- **No service containers** (pure static/unit/e2e-fixture lane).
- **Steps**: `checkout@v7` → `setup-node@v6` node 22 with **npm cache** keyed on
  `app/frontend/web/package-lock.json` (`ci.yml:88-92`) → `npm ci` → `npx eslint .` → `npx tsc -b` →
  `npm run test` (vitest) → Playwright browser cache → `npm run e2e` (fixture lane) → upload traces on
  failure (`ci.yml:117-124`, `upload-artifact@v7`, retention 7d).
- **Playwright browser cache** (`ci.yml:101-112`): `actions/cache@v6`, path `~/.cache/ms-playwright`,
  key `playwright-<os>-<hash of package-lock.json>`. On cache-hit installs only system deps
  (`playwright install-deps chromium`); on miss installs `--with-deps chromium`.

### What CI does NOT do (gaps a deploy workflow inherits or must fill) — §5 expands

- **No `npm run build`** — CI runs `tsc -b` (typecheck) but never `vite build`; there is **no
  production frontend `dist/` artifact produced anywhere** (grep of `ci.yml`: no `build`/`vite build`
  step). CD must build it.
- **No OpenAPI drift check** — CI never runs `pdm run export-openapi` or `npm run generate:api`, so a
  stale committed `openapi.json` / `schema.d.ts` would NOT fail CI. (The frontend `tsc -b` would only
  catch it if the committed `schema.d.ts` disagrees with usage, not if it disagrees with the backend.)
- **No container image build** — there are **zero Dockerfiles in the repo** (find across `app/`, whole
  tree excluding node_modules/.git: none). The compose files run stock images + host-run app; there is
  no backend image to deploy.
- **No live-smoke / real-ESI lane** — `npm run e2e` is the fixture lane; the `E2E_LIVE=1`
  live-smoke project auto-skips without a real backend (per CLAUDE.md), and CI has no backend serving.

---

## 2. Observability spec §2.5 — the deploy-gated backlog (`observability-spec.md:87-96`)

§2.5 "Health, Readiness & Upstream (ESI) Status" is the precise M4 observability scope. It opens
(`:89`) by stating the current reality: the app exposes **a single static liveness stub — `GET /health`
returns `{"status": "ok"}` unconditionally** — which confirms the process is up but does NOT report
readiness or data freshness. All three items below are explicitly framed as **deferred enhancements,
none required until a real deploy** (`:89`), ordered by value:

1. **Meaningful readiness probe** (`:91`). Distinguish *liveness* (process running) from *readiness*
   (can serve correct responses). Readiness SHOULD verify the PostgreSQL connection AND Valkey cache
   are reachable, and SHOULD report the age of the last successful ESI ingestion. **Keep liveness
   cheap and dependency-free** so an orchestrator doesn't kill an instance over a transient DB blip;
   dependency checks go behind *readiness*. Key insight (`:91`): because reads are served from the
   local DB, **ESI being down does NOT make the app unready** — it makes data stale, a distinct signal.

2. **Ingestion freshness / data-staleness indicator** (`:93`). The real failure mode under an ESI
   outage is *stale data*, not downtime: the aggregation job (`services/background_aggregation.py`)
   stops refreshing while the API keeps serving last-ingested contracts. The system SHOULD record the
   **timestamp AND outcome of the last successful aggregation run** — per region and/or globally — and
   surface staleness both operationally (a metric/alert when last-success exceeds expected cadence) and
   to users (a "contract data may be stale" indicator in the SPA, relates to F001). This is the
   user-facing complement to the ESI-interaction metrics in §2.2.

3. **ESI upstream health via `/meta/status`** (`:95-96`). ESI publishes per-route health at
   `https://esi.evetech.net/meta/status` with values `OK` / `Degraded` / `Down` / `Recovering`. Two
   uses: (1) a **scheduler pre-flight** — skip/defer an ingestion run and widen backoff when contracts
   routes report `Down`, instead of fanning dozens of region requests into a struggling API; (2) a data
   source for the staleness indicator. Framed as an *enhancement, not a prerequisite* — the ESI client
   already observes ground-truth health via its own 5XX/timeout retry-and-backoff
   (`core/esi_client_class.py`), so `/meta/status` adds a coarser predictive cross-route signal.
   **Gate the work on a real production deploy PLUS the freshness surface existing first.**
   - **MUST target `/meta/status`, never the removed `/status.json`** (`:96`). ESI's legacy
     `/status.json` was removed 24 March 2026; `/meta/status` is the replacement. Cross-refs pitfall
     ESI-1 (§4 below).

§5 "CI/CD Integration" (`observability-spec.md:133-136`) is a one-line placeholder: "Ensure that
observability configurations and instrumentation are part of the deployment pipeline." No concrete CD
requirements are specified there — M4 defines them.

---

## 3. What observability ALREADY EXISTS (and what's dev-only)

### Structured logging — WIRED, production-ready (`core/logging.py`)

- `setup_logging(settings)` is called first thing in `lifespan` startup (`main.py:42`). It configures
  **structlog with a `JSONRenderer`** (`core/logging.py:58-78`): processors include
  `merge_contextvars`, `add_log_level`, `add_logger_name`, `TimeStamper(fmt="iso")`,
  `StackInfoRenderer`, `format_exc_info`, `JSONRenderer`; `wrapper_class=BoundLogger`,
  `logger_factory=stdlib.LoggerFactory()`.
- **Correlation IDs are wired:** `RequestIDMiddleware` (`core/logging.py`, added `main.py:100`) binds a
  per-request `request_id` into structlog contextvars (`core/logging.py:40-42`).
- Helpers `get_logger(name)` (`:100-110`) and `log_key_event(...)` (`:114-133`) exist; auth uses them
  (`api/auth.py:19`). The global exception handler logs via `structlog.get_logger("uvicorn.error")`
  (`main.py:88-93`).
- Note a pre-structlog `logging.basicConfig(...)` for early startup messages remains at module import
  (`main.py:33`), documented as a baseline in `observability-spec.md:28-33`. Not a conflict — it's the
  pre-`setup_logging` bootstrap.
- **This logging is environment-agnostic (works in prod as-is).** No dev gate.

### Prometheus metrics — WIRED, endpoint always exposed (`main.py:102-113`)

- `prometheus_fastapi_instrumentator.Instrumentator` instruments the app and **exposes `/metrics`**
  (`main.py:113`), with `should_respect_env_var=False  # Always enable metrics` (`main.py:105`) — so
  `/metrics` is live in every environment including production. Custom in-progress gauge
  `hangar_bay_requests_inprogress` (`main.py:109`). This is the standard request-count/latency/error
  surface from §2.2; it is NOT dev-gated.

### Prometheus + Grafana compose stack — DEV-ONLY (`app/backend/docker/`)

- `compose.observability.yml` defines `prometheus` (`prom/prometheus:v3.4.2`, port 9090) and `grafana`
  (`grafana/grafana:12.0.2`, port 3000), both isolated on `hb-monitoring-net`
  (`compose.observability.yml:19-64`). Grafana provisioning files exist:
  `grafana/provisioning/datasources/datasource.yml` and `.../dashboards/dashboard.yml`.
- **This stack is explicitly local-development scaffolding.** `compose.observability.yml:3-4`: "auxiliary
  services for local development, specifically for observability." The Prometheus scrape target is
  `host.docker.internal:8000` with the comment "assumes the FastAPI app is running on the host machine"
  (`prometheus/prometheus.yml:14-17`) — i.e. it scrapes a host-run dev backend, not a containerized
  prod service. **A production deploy needs its own metrics collection** (managed Prometheus / hosted
  Grafana / cloud-provider metrics); this compose stack is not it.
- The top-level `compose.yml` (`compose.yml`) only defines the three segmented networks
  (`hb-public-net`, `hb-data-tier-net`, `hb-monitoring-net`) — no services. It documents the intended
  Zero-Trust segmentation (FastAPI is the only service on all three networks).

### What does NOT exist yet

- **No OpenTelemetry** anywhere (tracing §2.3, frontend metrics §2.2/§2.3 are all marked "not yet
  wired" / "target to be defined" in the spec, `:59,:76`).
- **No error-tracking integration** (Sentry/Rollbar — §2.4 is placeholders).
- **No frontend telemetry** at all.

---

## 4. Existing health endpoints + ESI-1 pitfall

### Health surface today (grep for `/health`, `/ready`, `/meta`)

- **`GET /health`** (`main.py:123-125`): `async def health_check(): return {"status": "ok"}`.
  **Unconditional, touches NOTHING** — no DB, no cache. This is a pure liveness stub. It is the
  liveness half §2.5 item 1 wants to keep cheap. Tested at `tests/api/test_main_endpoints.py:38-41`.
- **`GET /` root** (`main.py:116-120`): welcome message with env name. Not a health probe.
- **`GET /cache-test`** (`main.py:168-188`): a dev/test endpoint (tagged `Development/Test`, banner
  `CASCADE-PROD-CHECK: Remove or disable this endpoint for production.` at `main.py:168`) that DOES
  touch Valkey (set/get round-trip via `get_cache`). **It is NOT a readiness probe** and is marked for
  removal/disabling in prod — but it demonstrates the `Depends(get_cache)` building block a real
  readiness check would use.
- **`GET /metrics`** (`main.py:113`): Prometheus scrape endpoint (see §3).
- **No `/ready`, `/readyz`, `/livez`, `/healthz`, or `/meta/*` route exists** (grep of
  `app/backend/src/` for `readyz|/ready|readiness|liveness|livez`: empty). §2.5's readiness probe is
  **greenfield** — M4 builds it.
- **Building block for readiness:** `get_cache` (`core/dependencies.py:11-22`) reads
  `request.app.state.redis` and raises `HTTPException(503, "Redis client is not available.")` when
  absent; a sibling `get_http_client` follows the same pattern. A readiness route can compose these
  plus a `SELECT 1` over `get_db` to check DB reachability.

### ESI-1 verbatim (`docs/pitfalls/implementation-pitfalls.md:199-211`)

> **### ESI-1: Pin explicit ESI route versions; avoid removed legacy/meta routes**
>
> **The Flaw:** ESI periodically retires unversioned and legacy routes. The "Spring Cleaning" removal
> (24 March 2026) dropped `/status.json`, `/swagger.json` (plus `/dev/`, `/_dev/`, `/legacy/`,
> `/_legacy/` variants), `/diff`, `/versions`, and `/headers`, and began redirecting `/verify` to
> `https://login.eveonline.com/v2/oauth/verify` (the redirect itself removed 28 April 2026). The
> `/latest/*` alias is soft-deprecated — its `swagger.json` is frozen and new routes appear only in the
> OpenAPI specs.
>
> **Why It Matters:** A request built on any of these routes keeps working until the removal date, then
> fails with no code change on our side — the hardest kind of breakage to anticipate.
>
> **The Fix:**
> * Pin an explicit version prefix on every ESI request (`/v1`, `/v3`, …), matching the `ESIClient`
>   convention (`core/esi_client_class.py`). Never `/latest`.
> * For upstream health, use `/meta/status` (values `OK` / `Degraded` / `Down` / `Recovering`) — never
>   the removed `/status.json`. See `design/specifications/observability-spec.md` §2.5.
> * Validate SSO JWTs offline against JWKS (`services/sso.py`), not by calling `/verify`.
> * Consume ESI data from the OpenAPI specs, not the removed legacy `swagger.json`.
>
> **Where It Stands:** The backend already complies — every data route pins `/v1`/`/v3` and JWTs are
> validated offline, so Hangar Bay was unaffected by the 24 March 2026 removals. The lone `/latest`
> usage, the `generate-regions.mjs` build script, was pinned to `/v1`.

The §4.C review checklist (`:213-218`) restates: every ESI request names an explicit version prefix;
**upstream status checks target `/meta/status`, not the removed `/status.json`**; SSO JWT validation is
offline. **No observability-specific pitfall exists beyond ESI-1** — a scan of the pitfalls doc found no
HEALTH-* / OBS-* / METRICS-* entries; ESI-1 is the only one §2.5's `/meta/status` work must obey.

### Freshness-tracking status in the aggregation service

`services/background_aggregation.py` currently records **no last-success timestamp anywhere** (grep for
`last_success|last_run|freshness|stale|completed_at`: no persisted field). `run_aggregation`
(`:124-211`) logs success/failure to the logger only — e.g. `"Public contract aggregation run finished
successfully and changes committed."` (`:192`) — there is no DB row, cache key, or metric capturing
run outcome/time. So §2.5 item 2 (freshness surface) is **fully greenfield**: M4 must add the
recording mechanism (a `Contract`-adjacent table row, a Valkey key, or a Prometheus gauge) before the
readiness probe or a user-facing staleness indicator can read it. This is the stated ordering
dependency — the `/meta/status` work (item 3) is gated on the freshness surface (item 2) existing first
(`observability-spec.md:95`).

---

## 5. What CD needs from the repo side — CI produces vs. deploy must build

The repo has **no deploy tooling of any kind**: no Dockerfiles, no `fly.toml`/`render.yaml`/
`wrangler.toml`/`Procfile`/`railway`/`vercel`/`netlify` config anywhere (find across the tree ex
node_modules/.git: none). CI/CD is listed as "none yet" in CLAUDE.md. Everything below is greenfield.

### Backend artifact

- **CI produces:** nothing deployable. It installs deps (`pdm install -G dev`) and runs `pdm run
  pytest` against ephemeral service containers, then discards everything (`ci.yml:75-78`).
- **CD must build:** a runnable backend artifact. There is **no Dockerfile** — CD either authors one
  (PDM → CPython 3.14 base image; app entrypoint is `uvicorn fastapi_app.main:app --app-dir src`, per
  the `dev` pdm script `pyproject.toml:39` minus `--reload`) or uses a buildpack/PaaS. Runtime env it
  needs (from `.env.example` + CI env): `ENVIRONMENT`, `LOG_LEVEL`, `DB_RECREATE_ON_STARTUP` (MUST be
  false/unset in prod — see below), `DATABASE_URL`, `CACHE_URL`, `ESI_USER_AGENT`,
  `AGGREGATION_REGION_IDS`, `ESI_CLIENT_ID`, `ESI_CLIENT_SECRET`, `TOKEN_CIPHER_KEYS`
  (`.env.example` full key list confirmed).

### Frontend artifact

- **CI produces:** no build output — it runs `tsc -b` (typecheck) + `vitest` + Playwright fixture lane,
  but **never `vite build`** (`ci.yml:93-114`). No `dist/`.
- **CD must build:** `npm run build` (`= tsc -b && vite build`, `package.json` scripts) to produce the
  static SPA bundle, then serve it behind whatever edge owns the `/api/v1` prefix and proxies to the
  backend (PROXY-1: the `/api/v1` namespace + trailing-slash handling belongs to the deploy edge, NOT
  FastAPI — routers mount bare, confirmed `main.py:191-194`). The dev Vite proxy strips `/api/v1`; prod
  needs an equivalent reverse proxy / edge rule.

### OpenAPI client chain

- **CI produces:** no OpenAPI export and **no drift check** (grep of `ci.yml`: no `export-openapi` /
  `generate:api` / `openapi.json` step). The committed `openapi.json` and `src/lib/api/schema.d.ts` are
  trusted as-is.
- **CD (or a CI gate M4 may add):** the chain is `pdm run export-openapi` (backend,
  `pyproject.toml:40` → `python src/export_openapi.py`, which self-provides dummy env so it runs
  anywhere — `export_openapi.py:1-24`) → `npm run generate:api` (frontend → `schema.d.ts`). A deploy
  built from a stale committed schema would ship a client that disagrees with the backend. **Consider a
  CI drift-guard** (regenerate + `git diff --exit-code`) as cheap insurance, separate from CD.

### Test gates before deploy

- **CI already provides the green-CI merge gate** (backend pytest + frontend lint/typecheck/unit/e2e-
  fixture) that git-strategy relies on. A CD workflow triggered on `push` to `main`/`dev` runs *after*
  merge, so those gates already passed. If CD triggers on tags, it should either depend on the CI
  workflow's success (`workflow_run`) or re-run the gates.
- **The `E2E_LIVE=1` live-smoke lane** (real backend on :8000, per CLAUDE.md) is a natural **post-deploy
  smoke** candidate — it is NOT run in CI today (auto-skips without a live backend) and would give CD a
  real end-to-end verification against a deployed instance.

### Secrets — what's configured in the repo vs. what a deploy needs

- **Repo has NO real secrets configured for deploy.** CI inlines only throwaway values:
  `TOKEN_CIPHER_KEYS` (plaintext, throwaway, `ci.yml:63`) and DB creds `hangar:hangar` (ephemeral
  container, `ci.yml:50-51`). `ESI_CLIENT_ID`/`ESI_CLIENT_SECRET` are **absent from CI** (SSO isn't
  exercised in the pytest lane). There is **no evidence of GitHub Actions repo/environment secrets**
  being referenced anywhere (grep of `ci.yml` for `secrets.`: none — the only occurrence class would be
  `${{ secrets.* }}` and CI uses none).
- **CD must introduce real secret management:** production `TOKEN_CIPHER_KEYS` (Fernet keyring — note
  the model supports rotation via a keylist per the `TOKEN_CIPHER_KEYS` name/config), `ESI_CLIENT_SECRET`,
  `ESI_CLIENT_ID`, real `DATABASE_URL`/`CACHE_URL` creds. These belong in GitHub Environment secrets or
  the target platform's secret store — never CLI flags or committed env (Universal Gotcha: no secrets in
  CLI flags / command-line overrides; `compose.dependencies.yml:37` even carries a `TODO: Consider using
  Docker secrets ... for production` on the DB password).

### The production-schema gap CD must confront (cross-ref M3 recon)

- Dev/CI create schema via `Base.metadata.create_all` on a destructive drop+recreate, gated on
  `ENVIRONMENT == "development" AND DB_RECREATE_ON_STARTUP` (`main.py:128-150`). **In production this
  gate is fail-closed** (omitted `ENVIRONMENT` resolves to `"production"` → skip drop), so a prod boot
  **creates no tables at all** — there is currently **no live migration path** (Alembic is present but
  vestigial/stale per the M3 recon at `docs/audits/m3-recon/backend-data-auth.md` §6). **A real deploy
  needs a schema-provisioning story** (revived Alembic, or an initial `create_all` run) — this is a
  hard M4 blocker the CD design must resolve, not a CI concern.

---

## Quick-reference: CI facts + M4 deltas

| Concern | Today (CI) | What M4 deploy adds / must not break |
|---|---|---|
| Workflow files | 1 (`ci.yml`) | +1 deploy workflow (separate file) |
| Concurrency group | `ci-${{ github.ref }}`, cancel-in-progress | MUST differ (`deploy-*`); do NOT cancel in-progress deploys |
| Token permissions | `contents: read` (global) | deploy needs `packages: write` / `id-token: write` per-job |
| Backend services | `postgres:16`, `valkey:7.2` (CI-only, ephemeral) | prod needs managed PG + Valkey |
| Frontend build | none (`tsc -b` only, no `vite build`) | CD runs `npm run build` → `dist/` |
| Backend image | none (zero Dockerfiles) | CD authors Dockerfile / buildpack |
| OpenAPI drift | not checked | optional CI drift-guard; CD builds from committed schema |
| Metrics | `/metrics` always exposed (`main.py:113`) | prod scraper (compose stack is dev-only) |
| Readiness probe | none (`/health` is static liveness) | greenfield: DB+cache reachability + ingestion age (§2.5) |
| Ingestion freshness | not recorded anywhere | greenfield: persist last-success ts+outcome (§2.5) |
| ESI `/meta/status` | not integrated | gated on deploy + freshness surface; MUST use `/meta/status` (ESI-1) |
| Secrets | throwaway inline only, no `secrets.*` refs | real secret store for cipher keys / ESI / DB |
| Schema in prod | none (`create_all` dev-gated, Alembic stale) | migration/provisioning story required |

`/health` → `main.py:123-125`. `/metrics` → `main.py:113`. structlog → `core/logging.py:58-78`.
Dev observability compose → `app/backend/docker/compose.observability.yml`. ESI-1 →
`docs/pitfalls/implementation-pitfalls.md:199-211`. Deploy-gated backlog → `observability-spec.md:87-96`.
