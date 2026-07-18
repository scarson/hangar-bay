# M4 — Production Readiness & Deployment: Design

ABOUTME: Design spec for Milestone 4 — taking Hangar Bay from a dev-only stack to a deployed, operable production service (hosting, schema migrations, secrets, CD, deploy-gated observability, live SSO verification).
ABOUTME: Decisions carry documented reasoning chains, considered-and-ruled-out alternatives, and open uncertainties per the thinking-documentation discipline; recon evidence lives in docs/audits/m4-recon/.

**Status:** Draft for review (docs-only PR to dev).
**Author:** Claude (M4 session, 2026-07-18), from 11 recon lanes committed at `docs/audits/m4-recon/` (5 repo lanes + 6 hosting-candidate evaluations, all evidence-cited with access date 2026-07-18).
**Prereqs read:** `docs/pitfalls/implementation-pitfalls.md` (all entries), `docs/superpowers/specs/2026-07-12-m2-eve-sso-design.md` §4 (prod cookie-origin invariant), `design/specifications/observability-spec.md` §2.5, `docs/audits/m3-recon/backend-data-auth.md` (Alembic vestigial finding), M3 design + plan (schema delta and collision surface only — M3 is in flight on `claude/m3-account-features` and its worktree is hands-off).

---

## 1. Goal and scope

**Goal:** a public, HTTPS, real-domain deployment of Hangar Bay — SPA + API + EVE SSO on one origin — with non-destructive schema management, secret hygiene, a CD pipeline gated on CI, and enough observability to know the deploy is alive and the data is fresh. Hobby-scale budget: well under $40/mo, ideally $5–25/mo.

**In scope (M4):**
1. Hosting platform decision + production topology (§3–§4).
2. Alembic revival: re-baseline migrations, cut production over from `create_all` to `alembic upgrade head` (§5).
3. Production config + secrets provisioning, with the destructive-startup gate verified on the platform (§6).
4. CD: a new GitHub Actions workflow deploying on push to `main`, gated on CI (§7).
5. Deploy-gated observability, first tranche: meaningful readiness probe + operational ingestion-freshness surface; `/metrics` protection; `/cache-test` removal (§8).
6. Production EVE app registration + live SSO verification as a Sam-gated exit criterion (§9).

**Out of scope (recorded, not forgotten):** ESI `/meta/status` scheduler pre-flight and the user-facing SPA staleness indicator (§8.4 parks them with reasons); horizontal scaling/HA; staging environment; CDN beyond what the platform provides; scope-bearing ESI tokens (M3 owns that thread).

**The five production invariants** every decision below serves:

| # | Invariant | Source |
|---|---|---|
| I-1 | SPA, `/api/v1/*` API, and the SSO callback share ONE public HTTPS origin; the host-scoped `hb_session` cookie makes a split-host deploy silently no-op login | M2 design §4 (prod cookie-origin invariant) |
| I-2 | The edge owns `/api/v1` prefix-strip and passes paths verbatim (no trailing-slash rewriting); FastAPI routers stay bare | PROXY-1 |
| I-3 | At most one APScheduler instance runs at any time; deploys may pass through zero, never sustain two (defense-in-depth: the fencing-tokened Valkey ingestion lock, `background_aggregation.py:88-120`, already serializes runs) | deploy-runtime recon |
| I-4 | Production never runs destructive schema paths: `create_all`/`drop_all` stays dev-gated (already fail-closed — `ENVIRONMENT` defaults to `production`, recreate additionally requires `DB_RECREATE_ON_STARTUP=true`); prod schema changes flow only through migrations | ENV-2, `main.py:128-150` |
| I-5 | Secrets come from platform secret stores/dashboards/stdin — never CLI flags/argv, never chat, never git | Universal Gotchas |

---

## 2. What exists vs. what's missing (recon summary)

Full evidence: `docs/audits/m4-recon/deploy-runtime.md`, `data-migrations.md`, `frontend-edge.md`, `auth-prod.md`, `ci-observability.md`.

**Already production-shaped (verify, don't rebuild):**
- Fail-closed destructive-startup gate (I-4) and secure-by-default `ENVIRONMENT`.
- Valkey ingestion lock with fencing token + 30-min TTL (I-3 defense-in-depth).
- structlog JSON logging with request-ID correlation; Prometheus instrumentation.
- Offline JWT validation (no `/verify` calls); every ESI data route pins `/v1`/`/v3` (ESI-1 compliant).
- No CORS anywhere — the same-origin contract is load-bearing and stays.

**Missing entirely (M4 builds):**
- Any Dockerfile, any production launch command (only `pdm run dev` exists), any frontend production build in CI (`vite build` never runs — CI only typechecks).
- A live migration path: the six existing Alembic revisions describe a pre-SSO schema that never matched production reality (stale `users` table with `username`/`hashed_password`; a phantom `users.is_active`); `env.py`'s CLI invocation tail was removed, so no alembic command currently runs.
- Readiness probing (`/health` is a static stub touching neither DB nor cache) and any record of last-successful-ingestion (the aggregation service only logs success — nothing persisted to read back).
- Deploy secrets (CI uses throwaway inline values only), a CD workflow, and a prod EVE app registration.

**Prod-hostile defaults that must be overridden (silent failures if missed):**
- `AGGREGATION_DEV_CONTRACT_LIMIT` defaults to **100** and is not env-gated — an unconfigured prod deploy silently ingests only 100 contracts. Prod must set `0` (disable).
- `ESI_SSO_CALLBACK_URL` and `FRONTEND_ORIGIN` default to `https://localhost:5173`.
- `AGGREGATION_REGION_IDS` must arrive as a JSON array string (`[10000002]`) or boot crashes (ENV-1).
- `/metrics` is exposed unauthenticated; `/cache-test` (marked `CASCADE-PROD-CHECK`) ships in the app unconditionally.
- `db.py` creates the engine with no pool tuning (`pool_pre_ping`, sizing) — a gap behind any pooler and across managed-PG restarts. Worse, **every aggregation run creates a second, untuned engine** (`background_aggregation.py:151`) — production pool policy must cover both, preferably by making ingestion reuse the app engine/session factory.
- **`background_aggregation.py:150` logs the first 30 characters of `DATABASE_URL`** — on a real managed-PG URL that prefix can include username and password. Removing/redacting this log line is a hard M4 prerequisite (secret hygiene isn't only argv/git/chat — it's logs too).
- uvicorn worker count: **must stay 1**. The scheduler runs in-process; N workers = N schedulers racing the Valkey lock every tick. Single-worker is a design constraint until the scheduler is split out (deliberately deferred — YAGNI at hobby traffic).

---

## 3. Hosting decision

### 3.1 Method

Six candidates evaluated symmetrically (same 10-question template, findings classified BROKEN/MISSING/FIXABLE, no cross-comparison inside any lane, all pricing cited as of 2026-07-18): Fly.io, Render, Railway, single VPS (Hetzner/DO + Compose + Caddy), Vercel+Supabase, Cloudflare (Workers-native AND Containers sub-shapes — the latter two added at Sam's request). Full evaluations: `docs/audits/m4-recon/hosting-*.md`. Comparative-evaluation rules from CLAUDE.md applied: no recommendation until all lanes completed; symmetric depth; clean-story suspicion (see §3.4).

### 3.2 Decision matrix (condensed — details in the lane files)

| Candidate | $/mo | Managed PG + backups in budget | Single-scheduler on deploy | Edge contract (I-2) | Structural risk |
|---|---|---|---|---|---|
| **Render** | **14–24** | **✓ Basic ~$7–8 with automatic PITR** | ✓ documented: persistent disk ⇒ max 1 instance + recreate deploys | static-site rewrites; **2 items unverified** (§3.5) | RAM watch on 512 MB Starter |
| Fly.io | 8–12 | ✗ managed floor $38; unmanaged = self-owned backups, billable snapshots, "no support" | ✓ default (count=1 rolling passes through zero) | in-container Caddy (fly-proxy can't path-route) | PG durability posture |
| Railway | 13–20 | snapshot-only on Hobby (PITR Pro-gated) | ✗ platform can't stop-before-start; boot-window overlap is unavoidable by config | mandatory self-run Caddy service | usage-metered cost drift |
| VPS Hetzner CX23 | 7–9 | DIY (pg_dump cron + offsite + tested restores — must be built) | ✓ compose replace-in-place default | Caddy, exact | ongoing sysadmin burden; single point of failure; 2026 Hetzner price volatility |
| Vercel+Supabase | ~45 | ✓ but forces Supabase Pro $25 | requires re-architecting ingestion (Vercel Cron + lock); 300 s Hobby fn cap vs 2–7 min ingest | ✓ rewrites (1 slash quirk to verify) | two forced paid tiers; Python 3.14 unconfirmed |
| Cloudflare Containers | 15–35 | ✗ none first-party (D1 is SQLite); external Neon/Supabase | ✓ DO-singleton `max_instances:1`, but sleep-on-idle kills the scheduler without keep-alive | ✓ exact (assets + `run_worker_first`) | platform GA only since 2026-04; most moving parts; Workers-native sub-shape is BROKEN outright (no APScheduler/asyncpg/redis-py) |

### 3.3 Decision: Render

**The deciding argument is durability-per-dollar after M3.** M3 makes the database hold real user data — accounts, encrypted ESI tokens, saved searches, watchlists, notifications — which, unlike contract rows, is **not re-derivable by re-ingesting from ESI**. That upgrade in data criticality happens this milestone-cycle, so "the DB is disposable" reasoning (which would favor Fly's $8–12 unmanaged build or the VPS) no longer holds. Render is the only candidate offering managed Postgres with automatic point-in-time recovery *inside* the budget; every alternative either blows the ceiling (Fly MPG $38, Vercel stack $45), downgrades to snapshot-or-DIY backups (Railway Hobby, Fly unmanaged, VPS), or outsources the DB anyway (Cloudflare).

Secondary factors, in order of weight:
1. **Scheduler safety is documented platform behavior**, not a hack: a persistent disk on the web service both caps it at one instance and switches deploys to stop-old-then-start-new (briefly zero, never two — exactly I-3's shape). The disk is a 1 GB, ~$0.25/mo lever used purely for its deploy semantics.
2. **Ops burden is lowest tier**: managed PG, managed Valkey (Render Key Value runs Valkey 8 natively), free static hosting, free managed TLS, platform health-gated deploys. The VPS wins on dollars but loses on recurring attention (patching, hardening, backup drills, uptime monitoring — all DIY), which for a solo hobby project is the scarcer resource.
3. **Toolchain fit**: Python 3.14 is Render's platform default (Feb 2026), and we ship a Dockerfile anyway (PDM isn't natively detected — the Dockerfile route sidesteps detection and pins the runtime exactly).
4. **Deploy-downtime tradeoff accepted**: recreate deploys cost a few seconds of API 502s. At hobby scale, correctness (never two schedulers) beats zero-downtime. Recorded as deliberate.

**Runner-up:** Fly.io — take it if the budget ceiling ever drops below Render's ~$14–24 or if Render's §3.5 verification fails badly; its `count=1` rolling deploy has the same I-3 shape and the in-container-Caddy topology is the same as the Render fallback below. **Cost of switching later:** low-to-moderate — the Dockerfile, Caddyfile-fallback, env inventory, and Alembic work all transfer verbatim; only the CD trigger step and platform config files are Render-specific.

### 3.4 Clean-story check (mandated suspicion)

The story is *not* fully clean, which is reassuring: Render carries two empirically-unverified edge behaviors (§3.5), an unverified-under-load 512 MB Starter RAM budget, and a per-deploy downtime tradeoff. The comparison also hides a genuine judgment call — weighting managed-PITR above the VPS's $7/mo price and above Fly's cleaner default deploy semantics. If Sam weights dollars or platform-independence higher, VPS and Fly are both capability-complete choices; the matrix supports re-deciding without new recon.

### 3.5 Phase-0 verification spike (before any account/billing action)

Two Render behaviors are load-bearing and undocumented-in-detail; both must be proven with a throwaway free-tier project before the topology is committed:
1. **Cross-service full-URL rewrite pass-through for non-GET**: the static-site rewrite `Source /api/v1/*` → `Destination https://<backend>.onrender.com/*` must forward POST bodies and query strings intact (the SSO callback and logout are the consumers).
2. **Trailing-slash preservation**: `/api/v1/contracts/` must reach FastAPI as `/contracts/` (and `/contracts` as `/contracts`, un-normalized) — PROXY-1's 307-escape is the failure mode being excluded.

**Designed fallback (stays on Render):** if either check fails, drop the static-site rewrite layer and bundle Caddy into the backend container — Caddy serves the built SPA and does `handle_path /api/v1/*` prefix-stripping to `127.0.0.1:8000` (verbatim-path semantics are Caddy-documented). This is the identical edge config Fly/VPS/Railway would use, so the spike cannot strand us: worst case we converge on the portable in-container topology, still on Render, same cost.

### 3.6 Considered and ruled out, kept visible

- **Vercel + Supabase** — the SPA/edge story is genuinely strong, but the in-process scheduler is structurally incompatible with request-scoped compute: ingestion would be re-architected onto Vercel Cron (Pro-only at our cadence) with an explicit new lock, first-ingest length fights the function-duration cap, and two mandatory paid tiers land ~$45/mo. FIXABLE-at-significant-cost on every axis, over budget at the end of it.
- **Cloudflare Workers-native** — BROKEN, not just awkward: no persistent process for APScheduler, no asyncpg (Pyodide), no redis-py TCP. A port is a rewrite.
- **Cloudflare Containers** — closest loser. The DO-singleton instance guarantee and exact edge mapping are attractive, but it stacks: newest platform (GA 2026-04), no first-party Postgres (external DB re-introduces the cost/complexity Render bundles), and sleep-on-idle semantics that must be actively defeated to keep the scheduler alive. Worth revisiting if we ever *want* the scheduler re-architected onto Cron Triggers.
- **Switching the database to D1** (Sam's question, answered in-session 2026-07-18): D1 is only reachable via Workers bindings or a per-statement HTTP API with no interactive transactions — no TCP, no SQLAlchemy driver. Adopting it implies the full Workers rewrite above, plus replacing Alembic with wrangler-managed SQL migrations, plus losing the Postgres concurrency semantics M3's race-safety test depends on (`docs/superpowers/plans/2026-07-17-m3-account-features.md` Task 1.4). Data-shape-wise SQLite would suffice; access-path-wise it forces a re-platform. Ruled out for M4; revisit only as a deliberate future re-platform milestone.
- **Kubernetes / managed k8s** — three orders of magnitude more platform than a 4-container hobby app needs; nothing in M1–M3 wants it.
- **Staging environment** — deliberate omission at this budget; the Phase-0 spike project + post-deploy live-smoke lane (§7) carry the risk instead. Revisit when a second maintainer or real users arrive.

---

## 4. Production topology (Render)

Four resources, one `render.yaml` blueprint (IaC committed to the repo), one region (**Frankfurt** — EVE's Tranquility server is in London; EU keeps SSO/ESI round-trips short; override freely if Sam prefers US):

| Resource | Type | Plan | Role |
|---|---|---|---|
| `hangar-bay-web` | Static Site | Free | Built SPA (`vite build` → `dist/`); **owns the custom domain**; rewrite rules: `/api/v1/*` → backend URL with prefix stripped (ordered first), `/*` → `/index.html` SPA fallback |
| `hangar-bay-api` | Web Service (Docker) | Starter $7 + 1 GB disk (~$0.25) | FastAPI + in-process APScheduler, uvicorn **single worker**; the disk exists solely to pin max-1-instance + recreate deploys (I-3) |
| `hangar-bay-db` | Render Postgres | Basic ~$7–8 | Primary store; automatic PITR (3-day on Hobby workspace) + 7-day logical exports |
| `hangar-bay-cache` | Key Value (Valkey 8) | Free 25 MB (upgrade $10 if evicting) | Cache + **sessions + ingestion lock + APScheduler jobstore** — NOT purely loss-tolerable; persistence off is still chosen, with consequences accepted explicitly: a restart/eviction logs every user out (sessions re-establish via SSO — hobby-acceptable) and clears scheduler/lock state (self-heals: locks are TTL-bounded, jobs re-register at boot). Watch memory/evictions post-launch; the $10 tier is the priced escape if sessions start evicting |

- **Backend Dockerfile** (net-new): `python:3.14-slim`, PDM-installed deps, `uvicorn fastapi_app.main:app --host 0.0.0.0 --port $PORT --workers 1`. No `--reload`, no dev limit. Also used by the CD build and (eventually) local prod-parity testing.
- **Internal wiring**: `DATABASE_URL`/`CACHE_URL` via blueprint `fromDatabase`/`fromService` references — never typed by a human (I-5). **Driver-scheme normalization (required):** Render emits `postgresql://` connection strings, but both the app engine (`db.py:11`) and Alembic call `create_async_engine`, which requires `postgresql+asyncpg://`. `Settings` gains a validator normalizing `postgresql://` → `postgresql+asyncpg://` (Phase 3 — `core/config.py` is M3-touched), and the Phase-0 spike confirms the actual string shape Render injects.
- **Edge response headers (bound requirements, owner: Phase 1 config + Phase 0 verification):** HSTS on the public origin; `index.html` served no-cache (SPA deploys must propagate); hashed `/assets/*` served immutable/far-future; compression enabled. Phase 0 records which of these Render's static-site defaults already provide; gaps are closed with `render.yaml` static-site header rules. These come from the security/performance specs via the frontend-edge recon and need an explicit owner or they silently vanish.
- **Health check path**: `/ready` (new, §8.1) gates deploys; a recreate deploy waits on it before the instance takes traffic.
- **Cookie topology (I-1)**: custom domain on the static site; the rewrite proxies keep the browser on that one origin for SPA, API, and the SSO callback. `ESI_SSO_CALLBACK_URL = https://<domain>/api/v1/auth/sso/callback`, `FRONTEND_ORIGIN = https://<domain>` — char-for-char equal to the prod EVE app registration (§9).
- **RAM watch**: Starter is 512 MB. If ingestion pressure OOMs, the documented step is Standard ($25 — total lands ~$32–42, still under ceiling). Watch item, not a design change.

---

## 5. Schema management: Alembic revival

**Decision: clean re-baseline, not catch-up.** The six existing revisions describe a schema that never shipped (§2). Deleting them and generating a fresh baseline from live models is honest history; replaying provably-wrong migrations is not. The stale `check_alembic_version.py` (SQLite-era orphan) and `env.py`'s debug-print block go with them.

**Two-stage sequencing around M3 (the collision map is the constraint; the baseline is generated exactly once):**

- **Stage 1 — scaffolding only, NO baseline revision (collision-free, can start immediately):** touches only `src/alembic/`, `alembic.ini`, `check_alembic_version.py` (delete), `pyproject.toml` (add `pdm run` migration scripts). Work: delete stale revisions; restore `env.py`'s CLI invocation tail; enable `compare_type` + `compare_server_default`; wire async engine handling (`run_sync` against the asyncpg URL — no second driver dependency); verify `alembic upgrade head` runs cleanly with an empty revision history. M3 touches none of these files (`docs/audits/m4-recon/data-migrations.md` §collision-map). Deliberately **no revision is generated here** — a pre-M3 baseline would either be rewritten (mutating migration history) or need an immediate stacked delta, both worse than waiting.
- **Stage 2 — single baseline + cutover (AFTER the M3 merge):** generate THE baseline revision once, from post-M3 models, **against a blank disposable database** (autogen against a `create_all`-populated dev DB diffs to empty — the comparison target must be an empty schema), with **hand review of the partial index**: autogen renders `postgresql_where` imperfectly, and the predicate must match the model exactly or the matcher's `ON CONFLICT` dedup raises at runtime (SQLA-2 in session memory; M3 is adding the pitfall entry). Once applied to the production DB the baseline is **immutable** — all later schema changes are new revisions. Then: `main.py` lifespan keeps the dev-only `create_db_tables` path but production schema comes exclusively from `alembic upgrade head` run as **Render's pre-deploy command** (runs after build, before the old instance stops — with recreate deploys the old instance briefly serves on the new schema, so migrations must stay additive-compatible one release back; recorded as the operating rule). `conftest.py` stays on create_all for test speed — tests verify *models*; a dedicated test asserts baseline-migration ⇒ `Base.metadata` equivalence (offline `alembic-autogen-check` shape) so drift can't silently accumulate.
- **First prod boot bootstrap**: fresh DB + `alembic upgrade head` = full schema. No create_all involvement (I-4 holds; `ENVIRONMENT=production` skips it with a logged notice — already implemented).

**Autogen hazards to hand-review in the baseline** (from recon): Python-side `default=` on `Contract.is_ship_contract`/`item_processing_status` (no server defaults — keep as-is, don't invent them in DDL); ORM-only `onupdate` on `User.updated_at`; app-side cascade on `contract_items` (no `ondelete` — preserve); self-referential FK + plain `JSON` column on `esi_market_group_cache`.

**Also in Stage 2:** `db.py` engine gains `pool_pre_ping=True` and explicit modest pool sizing (Render Basic's connection budget is small; exact numbers in the plan) — and the policy must cover **both** engines: ingestion currently builds its own default engine per run (`background_aggregation.py:151`); the fix of record is reusing the app engine/session factory there, not tuning two engines in parallel.

---

## 6. Configuration & secrets

**Full prod env inventory** (every Settings field, its prod value/source — the deploy checklist; ENV-1 formats where applicable):

| Var | Prod value / source | Notes |
|---|---|---|
| `ENVIRONMENT` | `production` (set explicitly) | defaults safe anyway (I-4) |
| `DB_RECREATE_ON_STARTUP` | unset | belt+braces with I-4 |
| `LOG_LEVEL` | `INFO` | |
| `ESI_USER_AGENT` | real contact string incl. Sam's email | ESI etiquette; required, no default |
| `ESI_BASE_URL`/`ESI_TIMEOUT`/SSO URLs | defaults | pinned versions comply with ESI-1 |
| `ESI_CLIENT_ID` / `ESI_CLIENT_SECRET` | **prod EVE app registration (Sam, §9)** — dashboard-entered secret | distinct from dev registration |
| `ESI_SSO_CALLBACK_URL` | `https://<domain>/api/v1/auth/sso/callback` | must equal EVE portal registration char-for-char |
| `FRONTEND_ORIGIN` | `https://<domain>` | same host as callback (I-1) |
| `TOKEN_CIPHER_KEYS` | fresh Fernet key, dashboard-entered secret | generate with the documented one-liner; **prod keys are never dev keys**; rotation = prepend-new-comma-keep-old, never drop an in-use key (silently invalidates stored tokens) |
| `SESSION_*` | defaults | |
| `AGGREGATION_SCHEDULER_INTERVAL_SECONDS` | `3600` (default) | freshness surface (§8.2) keys off this |
| `AGGREGATION_REGION_IDS` | `[10000002]` JSON string | ENV-1: JSON array or boot crash |
| `AGGREGATION_DEV_CONTRACT_LIMIT` | **`0` (disable)** | silent 100-contract cap otherwise (§2) |
| `DATABASE_URL` / `CACHE_URL` | blueprint `fromDatabase`/`fromService` refs | never human-typed; `postgresql://` → `+asyncpg` normalized in Settings (§4) |
| `DATABASE_URL_TESTS` / `CACHE_URL_TESTS` | unset | test-only |
| `METRICS_TOKEN` (new, §8.3) | fresh random token, dashboard-entered secret | unset ⇒ `/metrics` open (dev); prod MUST set it |
| *M3's new Settings fields* | *enumerate from merged `core/config.py` at plan time (post-M3)* | this table is authoritative for pre-M3 fields only — the plan MUST extend it after the M3 merge, or M3 features run on defaults nobody chose |

**Provisioning paths (I-5):** secret values (`ESI_CLIENT_SECRET`, `TOKEN_CIPHER_KEYS`, `METRICS_TOKEN`) enter via the Render dashboard or blueprint `sync: false` declarations (names in git, values dashboard-held); connection strings via blueprint references; the CD credential lives only in GitHub Actions secrets. **Forbidden forms, named:** any `render`/`curl` CLI invocation with a secret in argv; secrets in `render.yaml` literals; secrets in chat or committed `.env` files; **secrets (or their prefixes) in log lines** — the existing `DATABASE_URL[:30]` log at `background_aggregation.py:150` is removed as a Phase-3 prerequisite. `.env.example` gains a commented production section documenting this inventory (**Phase 3, not Phase 1** — M3 edits `.env.example` repeatedly; touching it pre-merge would collide).

**Boot-time misconfig surfacing:** today a prod deploy with empty SSO config just 503s at request time (the startup warning is dev-only). M4 replaces `warn_if_sso_unconfigured` with a production-aware diagnostic covering ALL required SSO fields, with two tiers: (a) SSO wholly unconfigured (empty client id + cipher) → **warn** in every environment and continue — SSO-less operation stays valid, the marketplace works anonymously; (b) SSO *partially or inconsistently* configured in production — ANY non-empty proper subset of `{ESI_CLIENT_ID, ESI_CLIENT_SECRET, TOKEN_CIPHER_KEYS}` (a leftover secret with no client id is as much a deploy mistake as the reverse), or any of the trio set while `ESI_SSO_CALLBACK_URL`/`FRONTEND_ORIGIN` still contains `localhost`, while `ENVIRONMENT == "production"` — → **fail startup with a named-field error**. Tier (b) is always a deploy mistake, never a valid state; failing fast beats a silently broken login. Post-M3 change (`main.py`).

---

## 7. CD pipeline

**New workflow `.github/workflows/deploy.yml`** — zero edits to `ci.yml` (collision-free with M3, which doesn't touch workflows but does touch README/docs):

- **Trigger:** `workflow_run` on the CI workflow completing for `main` (the release branch — deploys are publications, matching git-strategy §Release branch), gated `if: conclusion == 'success'`, plus `workflow_dispatch` for manual/rollback deploys. This makes the FULL CI suite (backend pytest, frontend lint/typecheck/unit, **and the Playwright fixture lane**) the deploy gate by construction — a bare `push: main` trigger would race CI and could deploy a commit CI later fails; a partial re-run `verify` job would silently gate on less than CI does. `concurrency: group: deploy-production, cancel-in-progress: false` (queue, never cancel a mid-flight deploy; distinct from CI's `ci-${{ github.ref }}` group).
- **Permissions:** `contents: read` only; Render credentials live in GitHub Actions secrets.
- **Deploy semantics (bound requirements, mechanism finalized in the Phase-0 spike):** the deploy MUST be (a) **SHA-pinned** to the gated commit (`workflow_run.head_sha`), (b) **awaited** — the workflow polls the created deploy to a terminal state and fails on anything but success (a fire-and-forget hook POST returns immediately and an already-healthy old instance would pass smoke while the new build/migration fails later), (c) **ordered** backend-first, static site second, and (d) **verified** — the deployed release identifier (commit SHA surfaced by the backend, e.g. on `/ready`) must match before smoke runs. Plain deploy hooks satisfy none of (a)/(b) alone; the spike determines whether hook-response deploy-IDs + the deploys API, or a service-scoped API call creating the deploy with an explicit `commitId`, is the cleanest compliant mechanism (least-privilege preference unchanged: narrowest credential that can pin+poll).
- **Smoke:** poll `https://<domain>/api/v1/ready` (the PUBLIC origin path — bare `/ready` on the public origin would hit the SPA fallback, not the backend), then run the Playwright live-smoke lane against prod via a **new `live-smoke-prod` project**: env-driven `baseURL`, `ignoreHTTPSErrors` off, and **no `webServer`** — the existing config hardcodes `https://localhost:5173` and always boots `npm run dev`, so it cannot target a deployed origin as-is (Phase 3, `playwright.config.ts`). Failure marks the run red; rollback is `workflow_dispatch` pinning the previous good SHA.
- **Migrations** run inside Render's pre-deploy command (§5), not in the workflow — keeps DB credentials off GitHub entirely.
- **Separate small CI addition (own PR, not deploy-coupled):** an OpenAPI drift job — run `pdm run export-openapi` + `npm run generate:api` and fail on dirty diff. Recon found CI cannot currently catch a stale committed `openapi.json`/`schema.d.ts`. Cheap, high-value, collision-safe (new job in `ci.yml` — M3 doesn't touch it; verified against the M3 plan's file list).

## 8. Observability (deploy-gated backlog, first tranche)

Scope decisions against `design/specifications/observability-spec.md` §2.5 — what lands in M4 vs. stays parked, recorded per the mission:

### 8.1 IN — Meaningful readiness probe (post-M3)
`GET /ready` (new, bare-mounted): checks Postgres (`SELECT 1`) and Valkey (`PING`) with short timeouts; returns 200 + `{"db": "ok", "cache": "ok", "last_ingest_age_seconds": N|null}` or 503 with the failing component. `/health` stays the dependency-free liveness stub (the spec's explicit cheap-liveness requirement). Render's health check targets `/ready` so deploys gate on real readiness. Per the spec: ESI being down does NOT unready the app (reads serve from local DB) — ESI state is a freshness concern, next item.

### 8.2 IN — Operational ingestion-freshness surface (post-M3)
The aggregation service records the last run's result under one Valkey key (`hangar-bay:ingest:last_run`, JSON `{finished_at, outcome, regions_ok, regions_failed, last_success_at}`, **no TTL** — overwritten each run, lost on cache restart, which self-heals within one scheduler tick) plus a Prometheus gauge `hangar_bay_last_ingest_success_timestamp`. **Defined semantics** (today's code catches per-region errors and swallows top-level failures, so "success" must be pinned): region counters mean **regions CHECKED successfully** — a fetch success and an ETag-304 not-modified both count (a steady-state all-304 run is healthy, not a failure); commits are one shared transaction, not per-region, so `outcome` ∈ `success` (all regions checked ok AND the transaction committed or validly no-op'd) / `partial` (≥1 region checked ok, ≥1 failed, transaction committed) / `failure` (no region checked ok, or any processing/commit/top-level abort — regardless of fetch counters). `last_success_at` (and the gauge) advances on `success` AND `partial` — data DID refresh — and is preserved unchanged through `failure` records so staleness is measured against the last real refresh; `outcome` preserves the degradation signal. `/ready` exposes `last_ingest_age_seconds` + `last_ingest_outcome` and a derived `data_stale` boolean at age > 2 × `AGGREGATION_SCHEDULER_INTERVAL_SECONDS`. Staleness/outcome never fail readiness (spec §2.5: ESI problems ≠ unready). **Honest limitation, recorded:** nothing scrapes `/metrics` in M4 (no Prometheus server is deployed; the dev Grafana stack is compose-local) — the readiness fields are the operational surface; alerting on the gauge is parked with §8.4. Valkey chosen over a DB table: loss-tolerable operational signal, no migration, no write-amplification on user data.

### 8.3 IN — Endpoint hygiene (post-M3)
`/cache-test` deleted (its `CASCADE-PROD-CHECK` marker is the instruction). `/metrics` gated: when `METRICS_TOKEN` is set (prod), require `Authorization: Bearer <token>`; unset (dev) = open. New optional Settings field; dashboard-held token.

### 8.4 PARKED, with reasons
- **ESI `/meta/status` scheduler pre-flight** — the observability spec itself gates this on "a real production deploy plus the freshness surface existing first"; both conditions post-date M4's own deliverables. Park to M5; the ESI client's per-route retry/backoff remains the ground-truth signal. When built: `/meta/status` only, never `/status.json` (ESI-1).
- **User-facing SPA staleness indicator** — frontend surface M3 is actively churning; the operational signal (§8.2) must stabilize first. Park to M5 with the data already exposed via `/ready`.

## 9. SSO production bring-up (Sam-gated)

1. **Prod EVE app registration** (Sam, developers.eveonline.com): new application, callback `https://<domain>/api/v1/auth/sso/callback`, **zero scopes** — M2 ships identity-only login, M3 is explicitly zero-scope by its own design (§1.5 of the M3 design), and the first ESI scope belongs to an unnamed future milestone; no scope work is owned or completed by M3 or M4. Yields the prod `ESI_CLIENT_ID`/`ESI_CLIENT_SECRET`. Requires the domain decision first. Dev registration stays untouched.
2. **JWKS egress note:** offline validation ≠ network-free — PyJWKClient fetches `login.eveonline.com/oauth/jwks` live (300 s cache). Render egress is unrestricted; recorded so nobody firewall-hardens it away.
3. **Live SSO verification — the milestone exit criterion (Sam-gated):** the M2-deferred manual thread, now against prod: login → EVE consent → callback → `/me` shows character → logout; plus the `sso=denied` path. M4 is not DONE until Sam has run this on the prod origin. (The E2E live-smoke lane covers anonymous browsing only; SSO needs a human with real EVE credentials.)

## 10. Execution sequencing (collision-safe with M3)

| Phase | Content | Gate |
|---|---|---|
| 0 | Render verification spike (§3.5) — throwaway free project, no billing. Verifies: rewrite POST/body pass-through; trailing-slash preservation; **deploy pin+poll mechanism** (§7); **static-site default response headers** (§4); the `fromDatabase` URL scheme actually injected | none (free) |
| 1 | Collision-free implementation: Dockerfile, `render.yaml`, Caddyfile-fallback (if spike says so), Alembic Stage 1 scaffolding (**no baseline revision**), `deploy.yml`, OpenAPI-drift CI job | none |
| 2 | Platform provisioning: accounts, billing, domain, DNS, secrets, prod EVE registration | **Sam** (billing + domain + EVE portal) |
| 3 | Post-M3 backend/frontend work: Alembic Stage 2 (single baseline vs blank DB + cutover), `DATABASE_URL` scheme normalization, `/ready` + freshness surface, `/metrics` gate, `/cache-test` deletion, engine reuse + pool tuning, `DATABASE_URL[:30]` log-line removal, production SSO diagnostic (fail-fast tier), `live-smoke-prod` Playwright project, `.env.example` production section, extend the §6 env inventory with M3's fields | **M3 merged to dev** |
| 4 | First production deploy + live SSO verification | Sam (exit criterion §9.3) |

Phases 1's PRs are docs/config/new-file only — no file M3 touches (verified against the M3 plan's file list; the one shared surface, `ci.yml`, gets only a new independent job). TDD applies to all Phase-3 production code per CLAUDE.md; config/docs/workflow files are TDD-exempt but get the §3.5 spike + smoke verification.

## 11. Blocked on Sam (accumulating list)

1. **Platform sign-off + billing** (§3 — Render, ~$14–24/mo; reversible-by-docs until you act).
2. **Domain**: choose + register (~$12/yr) + DNS to Render.
3. **Prod EVE app registration** (§9.1 — needs the domain).
4. **Secrets entry**: `ESI_CLIENT_SECRET`, fresh `TOKEN_CIPHER_KEYS`, `METRICS_TOKEN` into the Render dashboard (never chat/CLI).
5. **Live SSO verification** (§9.3 — exit criterion).
6. Optional preference overrides: region (default Frankfurt), Valkey paid tier, Pro workspace for 7-day PITR.

---

## Appendix A — Reasoning chain & uncertainties (thinking-documentation)

**How the hosting decision was actually reached:** the recon was launched with four "obvious" container-shaped candidates; Sam added Vercel+Supabase and Cloudflare mid-flight. The initial working assumption — that the single-scheduler constraint would be the great differentiator — was substantially *defused* by recon: the existing fencing-tokened Valkey lock already makes overlap a wasted-tick problem, not a correctness problem. That shifted the deciding weight onto data durability (sharpened by realizing M3's user data breaks the "everything is re-derivable" premise) and recurring ops burden — which is what eliminated the two structurally-cheapest candidates (VPS: DIY backups + sysadmin time; Fly: managed-PG price wall). The runner-up ordering (Fly over VPS) is a judgment call weighting platform-managed deploy semantics over $3/mo.

**Uncertainties that remain:**
1. The two Render edge behaviors (§3.5) — could flip the topology to in-container Caddy (designed fallback, bounded blast radius).
2. Starter 512 MB under ingestion load — unmeasured; watch item with a priced escape ($25 Standard).
3. Render Basic Postgres connection budget vs. our pool settings — plan must pick numbers conservatively.
4. Additive-compatibility operating rule for migrations (§5, one release back) — is discipline, not tooling; a future guard (e.g. squawk-style lint) is possible if it's ever violated.
5. Third-party pricing aggregators back some Render compute figures (client-rendered pricing page) — absolute dollars could drift ±20%; does not change the ordering.

**What I'd add with more time:** a load-test of ingestion memory on a Starter-shaped container; an empirical Neon-vs-Supabase lane for the external-PG pairing (matters only if the Render decision falls); a cost-tracking note after the first full billing month.

**Things almost missed (surfaced by specific recon lanes, not by the author's first pass):** `AGGREGATION_DEV_CONTRACT_LIMIT`'s silent prod cap (deploy-runtime lane); CI's concurrency-group collision hazard for a naive deploy workflow (ci-observability lane); the JWKS "offline ≠ network-free" nuance (auth-prod lane); M3's partial-index baseline interaction with autogen (data-migrations lane, SQLA-2).

**Codex adversarial review round (2026-07-18, cross-model, pre-merge).** Six P1 + eight P2 findings; every code-verifiable claim checked against the repo before applying (all held — no false claims this round, unlike M2's). What it changed: `postgresql://`→`+asyncpg` normalization requirement (P1 — deploy would not have booted); Stage 1 stripped of baseline generation + blank-DB autogen rule (P1 — the two-stage shape as first written could mutate applied history or diff-to-empty); CD trigger moved from `push: main` to `workflow_run`-on-CI-success and deploy semantics bound to pin/await/order/verify (two P1s — the original design could deploy a commit CI later failed, and smoke could pass against the OLD deploy); smoke path corrected to `/api/v1/ready` + a dedicated prod Playwright project (P1 — bare `/ready` on the public origin hits the SPA fallback and the existing config can't leave localhost); `DATABASE_URL[:30]` log-line removal added as a secret-hygiene prerequisite (P1). P2s applied: env-inventory completeness (METRICS_TOKEN + M3-fields extension rule), freshness outcome semantics pinned (success/partial/failure + no-scraper honesty), Valkey non-cache contents acknowledged with accepted consequences, dual-engine pool coverage, scope-backlog ownership corrected (M3 is zero-scope by design), `.env.example` resequenced to Phase 3, edge response-header requirements bound with an owner, SSO misconfig diagnostic expanded to a fail-fast tier. The round validated the review-before-merge policy: the two most expensive misses (async URL scheme, un-gated deploy race) were invisible in every recon lane because each lane was correct in isolation — only the cross-cutting adversarial pass connected them.
