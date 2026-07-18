# M4 Recon — Hosting Candidate: Cloudflare

ABOUTME: Read-only recon of Cloudflare as an M4 production-hosting candidate for Hangar Bay (FastAPI + in-process APScheduler + Postgres + Valkey + React SPA, same-origin).
ABOUTME: Evaluates BOTH sub-shapes — Workers-native (Python Workers/Pyodide) and the container shape (Workers static assets + Cloudflare Containers + external Postgres/Redis). Facts + classified findings only; no recommendation, no cross-platform comparison.

Access date for all citations: **2026-07-18**. Prices/GA status as of mid-2026.

Scope note: this file evaluates ONE candidate on the shared template. It does NOT rank Cloudflare against other candidates and gives no overall recommendation (that is the synthesis step's job). Every material finding is tagged **BROKEN** / **MISSING** / **FIXABLE** (FIXABLE includes "possible but requires real re-architecture / added cost").

The app under evaluation (recap): FastAPI (Python 3.14, uvicorn) with an **in-process APScheduler** job ingesting EVE ESI data every few minutes (multi-minute runs); **exactly one** backend instance may run the scheduler. PostgreSQL (durable, backups) + Valkey/Redis (pure cache, `redis://` over raw TCP via redis-py). Static React SPA served **same registrable origin** as the API, `/api/v1/*` proxied to the backend with the `/api/v1` prefix **stripped**, paths otherwise verbatim (no trailing-slash rewriting), EVE SSO OAuth callback on a backend route on that origin, HTTPS + real domain (Secure HttpOnly host-scoped cookies). Secrets: `ESI_CLIENT_ID/SECRET`, `TOKEN_CIPHER_KEYS`, `DATABASE_URL`, `CACHE_URL`. CD from GitHub Actions.

---

## 0. Verdict-at-a-glance (per sub-shape)

- **Sub-shape (a) Workers-native (Python Workers / Pyodide): BROKEN for this app.** FastAPI itself runs (there is an official ASGI shim), but the three load-bearing pieces do not: the **in-process APScheduler cannot exist** (Workers have no always-on process / background threads), **asyncpg does not run** (no Pyodide/PyEmscripten wheel; Workers Postgres is expected to go through Hyperdrive with JS/HTTP drivers), and **redis-py over `redis://` raw TCP does not run** unmodified. Porting to this shape is a rewrite (HTTP Postgres driver + Workers KV cache + Cron-Triggers/Durable-Object ingestion), not a deployment.
- **Sub-shape (b) container shape (Workers static assets for the SPA + Cloudflare Containers for FastAPI + external managed Postgres + external/self-run Redis): FIXABLE and viable.** Containers went **GA 2026-04-13**. The container runs the app unmodified (Python 3.14, uvicorn, asyncpg, redis-py, APScheduler — it is a normal Linux amd64 container). The edge requirements map cleanly onto Workers static-assets + `run_worker_first`. The single-scheduler constraint maps onto a **Durable-Object singleton container** (`getContainer(binding, "cf-singleton-container")` + `max_instances: 1`). The real work is (i) keeping that one instance always-on OR moving ingestion onto a Cron Trigger, and (ii) accepting Container-lifecycle nuances (sleep-on-idle, rollout SIGTERM). Cost lands roughly **$14–35/mo** depending on how much of Postgres/Redis you keep on free tiers.

---

## 1. Topology mapping (each sub-shape, concretely)

### (a) Workers-native

Single Python Worker. `pyproject.toml` declares `fastapi` (+ `workers-py`, `workers-runtime-sdk` dev deps); deploy with `uv run pywrangler deploy`, which bundles PyPI/Pyodide packages into the Worker. FastAPI is wired to the runtime's built-in ASGI server. Static assets served from the same Worker via the `assets` config. There is **no place to run the ingestion loop** except Cron Triggers (`scheduled()` handler) — the in-process scheduler is gone. See §3/§10 for why this shape is BROKEN.
Sources: [Python Workers](https://developers.cloudflare.com/workers/languages/python/) · [FastAPI on Python Workers](https://developers.cloudflare.com/workers/languages/python/packages/fastapi/) · [Python packages](https://developers.cloudflare.com/workers/languages/python/packages/) (all accessed 2026-07-18).

### (b) container shape (the viable one)

One Worker deployment that owns the registrable origin and contains three things: (1) **static assets** (the Vite `dist/`), (2) a **container-enabled Durable Object** wrapping the FastAPI image, (3) a thin **Worker script** that routes `/api/*` to the container and lets everything else fall through to static assets.

`wrangler.jsonc` (illustrative):

```jsonc
{
  "name": "hangar-bay",
  "main": "./src/worker.ts",
  "compatibility_date": "2026-07-18",
  "assets": {
    "directory": "./web/dist",
    "not_found_handling": "single-page-application",
    "binding": "ASSETS",
    "run_worker_first": ["/api/*"]        // API to the Worker; SPA served as assets
  },
  "containers": [
    {
      "class_name": "BackendContainer",
      "image": "./app/backend/Dockerfile",  // linux/amd64
      "instance_type": "basic",             // 1/4 vCPU, 1 GiB, 4 GB disk (see §9)
      "max_instances": 1                    // hard cap: single scheduler (see §3)
    }
  ],
  "durable_objects": { "bindings": [{ "name": "BACKEND", "class_name": "BackendContainer" }] },
  "migrations": [{ "tag": "v1", "new_sqlite_classes": ["BackendContainer"] }],
  "triggers": { "crons": ["* * * * *"] }     // optional keep-alive / or ingestion trigger (§3)
}
```

`src/worker.ts` (illustrative — this is where prefix-strip lives):

```ts
import { Container, getContainer } from "@cloudflare/containers";

export class BackendContainer extends Container {
  defaultPort = 8000;
  sleepAfter = "30m";                       // see §3 keep-alive discussion
  envVars = {                               // injected at container start from Worker secrets
    DATABASE_URL: undefined as any, CACHE_URL: undefined as any,
    ESI_CLIENT_ID: undefined as any, ESI_CLIENT_SECRET: undefined as any,
    TOKEN_CIPHER_KEYS: undefined as any,
  };
}

export default {
  async fetch(req: Request, env: Env) {
    const url = new URL(req.url);
    if (url.pathname.startsWith("/api/v1/")) {
      // strip the /api/v1 prefix, keep the rest verbatim (PROXY-1)
      url.pathname = url.pathname.slice("/api/v1".length);   // "/api/v1/contracts" -> "/contracts"
      return getContainer(env.BACKEND, "cf-singleton-container")
        .fetch(new Request(url, req));
    }
    return env.ASSETS.fetch(req);           // SPA + static assets (index.html fallback)
  },
  async scheduled(_e, env: Env) {           // keep-alive OR ingestion trigger (§3)
    await getContainer(env.BACKEND, "cf-singleton-container").fetch("http://c/internal/tick");
  },
} satisfies ExportedHandler<Env>;
```

Container config keys (`instance_type`, `max_instances`, `rollout_step_percentage`, `rollout_active_grace_period`, `constraints.regions`) are documented in Wrangler config.
Sources: [Containers get-started](https://developers.cloudflare.com/containers/get-started/) · [Container class reference](https://developers.cloudflare.com/containers/container-class/) · [Wrangler config → Containers/Assets](https://developers.cloudflare.com/workers/wrangler/configuration/) · [Static assets routing](https://developers.cloudflare.com/workers/static-assets/) (accessed 2026-07-18).

---

## 2. Can the edge requirements be met exactly?

**Yes, exactly — this is a strong fit for the container shape.**

- **SPA fallback → index.html:** `assets.not_found_handling: "single-page-application"` returns `200` + `index.html` for any non-asset path. ([Static assets routing](https://developers.cloudflare.com/workers/static-assets/), 2026-07-18)
- **`/api/v1/*` to the backend, prefix stripped, paths otherwise verbatim:** `assets.run_worker_first: ["/api/*"]` (GA'd 2025-06-17; needs Wrangler ≥ 4.20.0) makes the Worker script run first for API paths only; everything else is served straight from assets without invoking the Worker. The Worker then does the prefix strip **in code** (`url.pathname.slice("/api/v1".length)`) and forwards the rest byte-for-byte to the container. Because the rewrite is explicit string surgery, there is **no automatic trailing-slash rewriting** on the API path — `html_handling` (default `"auto-trailing-slash"`) governs **static assets only**, and API requests bypass assets entirely. This satisfies PROXY-1 precisely. ([run_worker_first advanced routing](https://developers.cloudflare.com/changelog/post/2025-06-17-advanced-routing/), [assets config](https://developers.cloudflare.com/workers/wrangler/configuration/), 2026-07-18)
- **OAuth callback on the same origin:** the EVE SSO callback is just another path. If it lives under `/api/v1/...` it is already covered; if it is a bare top-level path, add it to `run_worker_first` (`["/api/*", "/auth/callback"]`). Same registrable origin, so Secure HttpOnly host-scoped cookies work. FIXABLE-trivial.
- **Same origin, no CORS:** SPA + API + callback all served by one Worker on one custom domain — same-origin by construction, matching the project's no-CORS design.

**Finding (edge): FIXABLE (well-supported).** The static-assets + `run_worker_first` + in-Worker rewrite pattern meets every edge requirement without workarounds.

---

## 3. Single-scheduler safety (the critical constraint)

**Container lifecycle facts (GA `@cloudflare/containers`):**

- A container instance is fronted by a **Durable Object**. `getContainer(env.BINDING, name)` returns the stub for a **named** instance; the default name is `cf-singleton-container`. Using one fixed name = exactly one logical instance. `max_instances: 1` additionally caps concurrent running instances (enforced in production only, not local dev). This gives a **true singleton** — a natural fit for "exactly one scheduler," and arguably cleaner than autoscaling PaaS where you must actively suppress replicas. ([Container class → getContainer](https://developers.cloudflare.com/containers/container-class/), [Wrangler config](https://developers.cloudflare.com/workers/wrangler/configuration/), 2026-07-18)
- **Sleep-on-idle is the core hazard.** `sleepAfter` sets an idle timeout; when no requests arrive for that window the DO calls `stop()` and the container (and your in-process APScheduler with it) **dies**. Incoming requests auto-reset the timer; background work inside the container does **not** count as activity. So sparse hobby web traffic will let it sleep, killing ingestion. ([Container class → onActivityExpired / renewActivityTimeout](https://developers.cloudflare.com/containers/container-class/), 2026-07-18)

**Two ways to satisfy the single-scheduler requirement:**

1. **Always-on + keep-alive (smallest code change; keeps in-process APScheduler).** Set a long `sleepAfter` and add a **Worker Cron Trigger** (`scheduled()`, min interval 1 min) that pings the container each minute so the idle timer never expires (or call `renewActivityTimeout()`). The container then never sleeps and the existing in-process APScheduler runs unmodified. Cost = 24/7 memory+disk billing (see §9). Classify **FIXABLE**.
2. **Cron-Triggers-drives-ingestion (more re-architecture; cheaper; arguably the "right" CF design).** Delete the in-process APScheduler `BackgroundScheduler`; expose a single idempotent "run one ingestion pass" entrypoint on the container; fire it from a Worker Cron Trigger every few minutes via `getContainer(singleton).startAndWaitForPorts(...)`/`fetch(...)`. The container can scale to zero between passes (paying only while ingesting + serving), and single-scheduler safety is guaranteed because the cron fires once globally and the DO singleton serializes. **Cost of the re-architecture:** modest — the ingestion job must become a callable single-pass function with an overlap guard (a Postgres advisory lock or a DO/DB "already running" flag) so a slow pass that outlasts the cron interval isn't double-started. Classify **FIXABLE** (moderate effort). Note this also removes the always-on cost.

**What happens to a long ingestion run on migrate/restart/deploy:**

- **Rollouts / deploys:** default `rollout_step_percentage` is `[10, 100]`; for a singleton this means the new-version container starts and the old one is sent **SIGTERM with a 15-minute grace period** before force-kill (`rollout_active_grace_period` tunable). This creates a **brief window where the draining old instance and the new instance could both run the scheduler → double ingestion**, OR a short gap. Mitigation: ESI ingestion is upsert-based (largely idempotent), plus the overlap guard from option 2. `--containers-rollout=immediate` collapses the rollout to one step. Classify **FIXABLE**.
- **Host migration / maintenance restart:** container disk is **ephemeral** (Durable Object SQLite storage persists, but the app doesn't rely on container-local disk). A restart kills an in-flight pass; the next scheduled pass re-runs it. With the 15-min SIGTERM grace, a multi-minute pass normally finishes before force-kill. Acceptable / **FIXABLE**.

**Finding (single-scheduler): FIXABLE.** Cloudflare's DO-singleton model actually expresses "exactly one" more directly than replica-based platforms, but sleep-on-idle means you MUST either keep-alive an always-on instance (cost) or move ingestion onto Cron Triggers (re-architecture). Deploy overlap needs an idempotency/lock guard.

---

## 4. PostgreSQL (external) + Hyperdrive

Cloudflare has **no first-party managed Postgres** (D1 is SQLite — wrong engine for this app's SQLAlchemy/asyncpg stack). So Postgres is external.

- **Concrete options:** **Neon** (serverless PG; Free = 100 CU-hours/mo compute + scale-to-zero, Launch usage-based ~$0.106/CU-hour + $0.35/GB-mo storage, no monthly floor; **Scale-to-zero conflicts with an always-connected backend** — a persistently-connected 0.25 CU compute burns ~6 CU-hr/day > the free 100 CU-hr/mo ≈ 3.3/day, so the **Neon free tier will not cover an always-on connection pool**; expect Neon Launch ~$5–15/mo for this app). **Supabase** (Free = 500 MB DB / shared CPU / 500 MB RAM / 7-day backups / 5 GB egress, no scale-to-zero surprise; Pro $25/mo). **PlanetScale Postgres** is also billable through the Cloudflare invoice. ([Neon pricing](https://neon.com/pricing), [Supabase pricing](https://supabase.com/pricing), [Hyperdrive → PlanetScale](https://developers.cloudflare.com/hyperdrive/platform/pricing/), 2026-07-18)
- **Backups:** provided by the managed DB (Neon PITR / Supabase daily snapshots), not by Cloudflare.
- **Is Hyperdrive needed? For the container shape, NO.** Hyperdrive is a **Workers binding** (connection pooling + query caching for Workers making PG connections). The **container is not a Worker** — it opens a normal TCP connection to the external Postgres via asyncpg using `DATABASE_URL` directly, so Hyperdrive is neither usable-as-a-binding from inside the container nor necessary. (Hyperdrive would only matter in the Workers-native shape, and it is **free** on both Free and Paid Workers plans — Free is capped at 100k queries/day, pooling/caching/egress incur no extra charge.) Classify: Hyperdrive is **not required** for the viable shape — a simplification and a cost saving. ([Hyperdrive pricing](https://developers.cloudflare.com/hyperdrive/platform/pricing/), [how Hyperdrive works](https://developers.cloudflare.com/hyperdrive/concepts/how-hyperdrive-works/), 2026-07-18)

**Finding (Postgres): FIXABLE.** External managed PG required; direct asyncpg from the container works; Hyperdrive unnecessary. Watch the Neon-free-tier vs always-connected-pool mismatch — budget for Supabase free (if 500 MB suffices) or a small paid PG tier.

---

## 5. Redis / Valkey (pure cache)

The container is a full Linux VM with unrestricted outbound TCP, so `redis://` over raw TCP works from the container (unlike from a Worker). Options:

- **Upstash Redis (external, TCP):** Free = 256 MB / 500K commands per month; pay-as-you-go $0.20 per 100K commands + $0.25/GB-mo beyond 1 GB; fixed plans from $10/mo. For a pure cache at hobby scale the **free tier likely suffices** ($0). ([Upstash Redis pricing](https://upstash.com/pricing/redis), 2026-07-18)
- **Self-run Valkey inside the same container:** zero network cost and no external dependency, but it shares the container's 1 GiB (basic) memory and dies/reloads when the container restarts — acceptable for a pure cache (cache is rebuildable). Adds a process-manager wrinkle (uvicorn + valkey in one image).
- **Managed alternatives:** any Redis-compatible host reachable over TCP (Redis Cloud, etc.).

Note: a Worker (not the container) **cannot** reach `redis://` over arbitrary TCP except via a **VPC Network binding** `connect()` (Tunnel/Mesh, plaintext TCP only) — irrelevant to the container shape but confirms why the Workers-native shape can't use redis-py. ([Workers VPC connect()](https://developers.cloudflare.com/workers-vpc/api/), [TCP sockets](https://developers.cloudflare.com/workers/runtime-apis/tcp-sockets/), 2026-07-18)

**Finding (Redis): FIXABLE.** Free Upstash tier or self-run Valkey in-container; both fine for a pure cache.

---

## 6. Secrets provisioning (no secrets in CLI args)

- **`wrangler secret put <NAME>`** prompts and reads the value from **stdin**, not a command-line argument — safe (nothing in `ps`/shell history). **`wrangler secret bulk < secrets.json`** reads a JSON blob from **stdin** for batch set (and can delete by setting a key to `null`, Wrangler ≥ 4.97.0). The **dashboard** (Workers → Settings → Variables and Secrets) is a third non-CLI path. All satisfy the "no `--secret` flag" rule. ([wrangler secret commands](https://developers.cloudflare.com/workers/wrangler/commands/workers/), [Secrets](https://developers.cloudflare.com/workers/configuration/secrets/), 2026-07-18)
- **Getting the five secrets into the container:** set them as **Worker secrets** (they land in `env`), then inject them into the container at start via the `Container` class `envVars` / `startOptions.envVars` (see the [env-vars-and-secrets example](https://developers.cloudflare.com/containers/examples/env-vars-and-secrets/)). Values live encrypted as Worker secrets and are passed process-internally to the container — never on a CLI arg. Note `image_vars` is **build-time** only; do NOT put runtime secrets there.
- Secrets can be **declared** as required in `wrangler.jsonc` (`"secrets": { "required": [...] }`) so deploys fail fast if any are unset.

**Finding (secrets): FIXABLE (well-supported).** stdin/dashboard paths avoid CLI-arg exposure; container receives them via `envVars` injection from Worker secrets.

---

## 7. TLS + custom domain

- **Custom Domain** on the Worker: Cloudflare auto-creates the DNS record and **issues + manages the certificate** (Advanced Certificate) for the target hostname — no manual cert management, HTTPS out of the box. Set via dashboard, `wrangler.jsonc` `routes: [{ pattern: "hangar-bay.example.com", custom_domain: true }]`, or API. The domain can be registered through Cloudflare Registrar (at-cost, ~$10/yr for common TLDs) or an existing zone. A 2026-05 **Domains tab** in the Worker dashboard centralizes buy/connect/manage. ([Custom Domains](https://developers.cloudflare.com/workers/configuration/routing/custom-domains/), [Domains tab changelog](https://developers.cloudflare.com/changelog/post/2026-05-14-domains-tab/), 2026-07-18)
- All paths of the domain route to the Worker (Custom Domains match the whole host, path-agnostic), which is exactly what a single-origin SPA+API app wants.

**Finding (TLS/domain): FIXABLE (well-supported).** Fully managed TLS + custom domain, no cert ops.

---

## 8. GitHub Actions CD

- **`cloudflare/wrangler-action`** runs `wrangler deploy` in CI; pass the token as `apiToken` from a GitHub Actions secret (`CLOUDFLARE_API_TOKEN`), never inline. ([GitHub Actions for Workers](https://developers.cloudflare.com/workers/ci-cd/external-cicd/github-actions/), [cloudflare/wrangler-action](https://github.com/cloudflare/wrangler-action), 2026-07-18)
- **Token scoping:** create a **scoped API token** using the **"Edit Cloudflare Workers"** template (the minimal scope wrangler needs) rather than a broad "Read/Edit all resources" token; scope it to the specific account/zone. Deploying **Containers** also builds+pushes the image, so the deploy step needs Docker available in the runner (or a pre-built image reference) — the token itself is the Workers-edit token; image push goes to the Cloudflare Registry under the same auth.
- **Secrets are set out-of-band** (once, via stdin/dashboard) — the CD workflow only carries the deploy token, not the app secrets, so a compromised workflow log never leaks `DATABASE_URL` etc.

**Finding (CD): FIXABLE (well-supported).** Standard `wrangler-action` + scoped "Edit Workers" token. Container image build in CI is the one extra moving part.

---

## 9. Total monthly cost estimate (hobby scale, mid-2026)

Containers **require the Workers Paid plan ($5/mo)** — there is no free-tier Containers. Billing: **memory & disk are billed on *provisioned* resources for the whole time the instance is running** (not sleeping); **CPU is billed on *active usage only*** (used cycles). Included on Workers Paid: **25 GiB-hours memory, 375 vCPU-minutes CPU, 200 GB-hours disk, 1 TB egress (NA/EU)** per month. Rates beyond: memory $0.0000025/GiB-s, CPU $0.000020/vCPU-s, disk $0.00000007/GB-s; egress $0.025/GB (NA/EU). ([Workers pricing](https://developers.cloudflare.com/workers/platform/pricing/), [Containers pricing](https://developers.cloudflare.com/containers/pricing/), 2026-07-18)

**Always-on `basic` instance (1/4 vCPU, 1 GiB, 4 GB disk), 730 hr/mo — the option-1 design:**

| Item | Calc | ~$/mo |
|---|---|---|
| Workers Paid (required) | flat | **$5.00** |
| Container memory | (730−25) GiB-hr ×3600× $0.0000025 | **~$6.35** |
| Container disk | (2920−200) GB-hr ×3600× $0.00000007 | **~$0.69** |
| Container CPU (active only) | scheduler duty-cycle, ~30% of 0.25 vCPU, minus 375 vCPU-min incl. | **~$2–5** |
| Egress | ESI fetches are ingress (free); JSON responses ≪ 1 TB incl. | **~$0** |
| Hyperdrive | not used in container shape | **$0** |
| Postgres (external) | Supabase Free (500 MB) **$0**, or Neon Launch **~$5–15** | **$0–15** |
| Redis (external) | Upstash Free (256 MB) **$0**, or self-run in container **$0** | **$0** |
| Domain | Cloudflare Registrar ~$10/yr | **~$1** |
| **TOTAL (always-on)** | | **~$15–33/mo** |

**Option-2 (Cron-Triggers ingestion, scale-to-zero between passes):** container memory/disk billed only while awake — if the container is warm, say, 25% of the month, memory drops to ~$1.6 and disk to ~$0.2, pulling Cloudflare-side compute to roughly **$8–10/mo** total (Workers Paid + intermittent container + minimal CPU), plus the same external DB/Redis. This lands the whole stack near the **$5–25/mo ideal** if Postgres/Redis stay on free tiers — at the cost of the re-architecture in §3 and cold-start latency on the web path after idle.

**Bottom line:** realistically **~$15–20/mo** with always-on + free DB/Redis tiers; **~$25–35/mo** with a paid Neon/Supabase + paid Upstash; **potentially ~$10–15/mo** with the Cron-Triggers re-architecture and free data tiers. All within the <$40 target; the ~$5–25 sweet spot is reachable but leans on free managed-DB tiers.

---

## 10. Risks / limitations specific to THIS app

- **[BROKEN] Python Workers can't run this app's core (sub-shape a).** In-process **APScheduler** needs an always-on process with background threads — Workers are request/event-scoped with no persistent process; impossible. **asyncpg** has no Pyodide/PyEmscripten wheel and needs its own socket/event-loop plumbing the Python runtime doesn't provide (Workers Postgres is designed to go through Hyperdrive with JS/HTTP drivers). **redis-py over `redis://` raw TCP** doesn't run unmodified in the Python Worker sandbox. FastAPI *itself* is supported (ASGI shim) and `cryptography`/Fernet is likely available in Pyodide (FIXABLE), but those don't rescue the shape. Net: Workers-native is a **rewrite** (HTTP PG driver + Workers KV + Cron/DO ingestion), not a port. ([Python Workers packages](https://developers.cloudflare.com/workers/languages/python/packages/), [TCP sockets considerations](https://developers.cloudflare.com/workers/runtime-apis/tcp-sockets/), 2026-07-18)
- **[FIXABLE] Python 3.14 in the container is a non-issue** — it's a normal `linux/amd64` image; ship whatever Python/uvicorn/asyncpg/redis-py/APScheduler versions the app already uses. Image must be amd64; size is bounded by instance disk (basic = 4 GB) and total account image storage is 50 GB. ([Containers get-started](https://developers.cloudflare.com/containers/get-started/), [Containers limits](https://developers.cloudflare.com/containers/platform-details/limits/), 2026-07-18)
- **[FIXABLE] Sleep-on-idle vs an always-on scheduler** — the central operational risk (see §3). Requires a keep-alive Cron Trigger (option 1) or moving ingestion to Cron Triggers (option 2). If the container ever *does* sleep unexpectedly, the in-process scheduler is silent until the next request wakes it.
- **[FIXABLE] Deploy/rollout overlap** — SIGTERM+15-min-grace rollout of a singleton can briefly run two schedulers; guard with idempotent upserts + a Postgres advisory lock (or DO/DB "running" flag). `--containers-rollout=immediate` reduces the window.
- **[FIXABLE] Ephemeral container disk** — fine here (state lives in external Postgres; cache is rebuildable; DO SQLite storage available if ever needed). No local-disk reliance.
- **[FIXABLE] Egress model** — ESI ingestion is inbound (free); user-facing JSON egress is tiny and well under the 1 TB NA/EU included allotment. Not a cost driver at hobby scale.
- **[FIXABLE] Maturity** — Containers reached **GA on 2026-04-13** (Workers Paid), with Figma running Figma Make in production on it; limits raised 15× in Feb 2026. Reasonably mature for a hobby workload, though newer than classic PaaS container hosts. ([Containers & Sandboxes GA](https://developers.cloudflare.com/changelog/post/2026-04-13-containers-sandbox-ga/), [InfoQ: Sandboxes GA](https://www.infoq.com/news/2026/04/cloudflare-sandboxes-ga/), [higher limits](https://developers.cloudflare.com/changelog/post/2026-02-25-higher-container-resource-limits/), 2026-07-18)
- **[MISSING] No first-party managed Postgres or Redis** — both must be external (D1 is SQLite, wrong engine). Adds two external vendors to the ops surface (Neon/Supabase + Upstash) and their own billing/backup story. Not a blocker, but it means Cloudflare is not a one-stop shop for this app's data tier.

---

## Findings summary (classification table)

| # | Area | Sub-shape | Finding | Class |
|---|---|---|---|---|
| a | Workers-native runtime | (a) | APScheduler impossible (no persistent process) | **BROKEN** |
| a | asyncpg on Python Workers | (a) | No Pyodide wheel; needs socket/event-loop plumbing | **BROKEN** |
| a | redis-py `redis://` TCP on Workers | (a) | Not runnable unmodified in Python Worker sandbox | **BROKEN** |
| a | FastAPI on Python Workers | (a) | Supported via ASGI shim (but moot given above) | FIXABLE |
| 1 | Topology / config | (b) | Clean map: assets + DO-singleton container + Worker router | FIXABLE |
| 2 | Edge: SPA fallback, prefix strip, no trailing-slash meddling, same origin | (b) | `not_found_handling: single-page-application` + `run_worker_first` + in-Worker rewrite | FIXABLE (well-supported) |
| 3 | Single-scheduler safety | (b) | DO-singleton + `max_instances:1`; but sleep-on-idle → need keep-alive cron or Cron-Trigger ingestion; rollout overlap needs a lock | FIXABLE |
| 4 | External Postgres | (b) | Neon/Supabase; asyncpg direct from container; **Hyperdrive not needed**; Neon free won't cover always-connected pool | FIXABLE |
| 4 | Hyperdrive necessity | (b) | Unnecessary for container shape (Workers-only binding); free anyway | FIXABLE (n/a) |
| 5 | Redis/Valkey | (b) | Upstash free (TCP) or self-run in-container | FIXABLE |
| 6 | Secrets provisioning | (b) | `wrangler secret put`/`bulk` via stdin, dashboard; injected to container via `envVars` | FIXABLE (well-supported) |
| 7 | TLS + custom domain | (b) | Fully managed cert + Custom Domain | FIXABLE (well-supported) |
| 8 | GitHub Actions CD | (b) | `wrangler-action` + scoped "Edit Workers" token; image build in CI | FIXABLE (well-supported) |
| 9 | Cost @ hobby scale | (b) | ~$15–35/mo always-on; ~$10–15/mo with Cron re-arch + free data tiers | FIXABLE (in budget) |
| 10 | No managed PG/Redis | (b) | Must use external vendors (D1 is SQLite) | MISSING |
| 10 | Containers maturity | (b) | GA 2026-04-13; production-used | FIXABLE |

---

## Sources (all accessed 2026-07-18)

- Cloudflare Containers — [overview](https://developers.cloudflare.com/containers/) · [get-started](https://developers.cloudflare.com/containers/get-started/) · [Container class reference](https://developers.cloudflare.com/containers/container-class/) · [limits/instance types](https://developers.cloudflare.com/containers/platform-details/limits/) · [image management](https://developers.cloudflare.com/containers/platform-details/image-management/) · [pricing](https://developers.cloudflare.com/containers/pricing/) · [env vars & secrets example](https://developers.cloudflare.com/containers/examples/env-vars-and-secrets/)
- Containers & Sandboxes **GA** — [changelog 2026-04-13](https://developers.cloudflare.com/changelog/post/2026-04-13-containers-sandbox-ga/) · [InfoQ 2026-04](https://www.infoq.com/news/2026/04/cloudflare-sandboxes-ga/) · [15× limits 2026-02-25](https://developers.cloudflare.com/changelog/post/2026-02-25-higher-container-resource-limits/)
- Workers pricing (Containers rates, egress, Paid-plan inclusions) — [workers/platform/pricing](https://developers.cloudflare.com/workers/platform/pricing/)
- Durable Object container API — [durable-objects/api/container](https://developers.cloudflare.com/durable-objects/api/container/)
- Wrangler config (containers, assets, secrets, routes) — [workers/wrangler/configuration](https://developers.cloudflare.com/workers/wrangler/configuration/) · [wrangler secret commands](https://developers.cloudflare.com/workers/wrangler/commands/workers/)
- Static assets / SPA routing — [workers/static-assets](https://developers.cloudflare.com/workers/static-assets/) · [run_worker_first advanced routing 2025-06-17](https://developers.cloudflare.com/changelog/post/2025-06-17-advanced-routing/)
- Python Workers — [overview](https://developers.cloudflare.com/workers/languages/python/) · [packages](https://developers.cloudflare.com/workers/languages/python/packages/) · [FastAPI](https://developers.cloudflare.com/workers/languages/python/packages/fastapi/)
- TCP / sockets / VPC — [workers/runtime-apis/tcp-sockets](https://developers.cloudflare.com/workers/runtime-apis/tcp-sockets/) · [workers-vpc/api](https://developers.cloudflare.com/workers-vpc/api/)
- Hyperdrive — [pricing](https://developers.cloudflare.com/hyperdrive/platform/pricing/) · [how it works](https://developers.cloudflare.com/hyperdrive/concepts/how-hyperdrive-works/)
- Secrets — [workers/configuration/secrets](https://developers.cloudflare.com/workers/configuration/secrets/)
- Custom domains / TLS — [workers/configuration/routing/custom-domains](https://developers.cloudflare.com/workers/configuration/routing/custom-domains/) · [Domains tab 2026-05-14](https://developers.cloudflare.com/changelog/post/2026-05-14-domains-tab/)
- CD — [workers/ci-cd/external-cicd/github-actions](https://developers.cloudflare.com/workers/ci-cd/external-cicd/github-actions/) · [cloudflare/wrangler-action](https://github.com/cloudflare/wrangler-action)
- External data tiers — [Neon pricing](https://neon.com/pricing) · [Supabase pricing](https://supabase.com/pricing) · [Upstash Redis pricing](https://upstash.com/pricing/redis)
