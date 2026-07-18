# M4 Recon — Hosting Candidate: Vercel + Supabase + Upstash

ABOUTME: Read-only hosting-candidate recon for Hangar Bay M4 production readiness — Vercel (SPA + serverless/edge) + Supabase (managed Postgres) + Upstash (Redis/Valkey).
ABOUTME: Facts + classifications (BROKEN/MISSING/FIXABLE) only, symmetric template, no recommendation and no cross-candidate comparison. No code was modified.

Scope: evaluate ONE candidate stack against Hangar Bay's deployment shape. All pricing/capability
facts are as of **2026-07-18** with cited URLs. Candidate = **Vercel** for the static SPA + the
FastAPI backend as serverless/edge functions, **Supabase** for managed Postgres, **Upstash** (or
equivalent) for Redis/Valkey cache. The app shape being mapped:

- FastAPI backend (Python 3.14, uvicorn) with an **in-process APScheduler** ingesting EVE ESI data
  every few minutes; first ingest runs multi-minute (2–7 min).
- PostgreSQL (durable + backups) and Valkey/Redis (pure cache, loss-tolerable).
- Static React SPA (Vite) served from the **same registrable origin** as the API; edge must strip
  the `/api/v1` prefix before FastAPI, preserve other paths verbatim (no trailing-slash rewriting),
  SPA fallback to `index.html`, and host the EVE SSO OAuth callback on a backend route on that same
  origin. Session cookies are Secure+HttpOnly host-scoped → HTTPS + real domain required.
- Secrets: `ESI_CLIENT_ID`/`ESI_CLIENT_SECRET`, `TOKEN_CIPHER_KEYS`, `DATABASE_URL`, `CACHE_URL` —
  provisioning must avoid secrets in CLI flags/args.
- CD from GitHub Actions (repo already has CI); needs a deploy token usable from a workflow.

---

## Headline structural finding

**Vercel is a serverless/edge platform with no long-lived process.** Functions are stateless and
frozen between invocations; a background thread (APScheduler) started during a request does not keep
running after the response is sent. This collides with Hangar Bay's core architecture in two places:

1. **In-process APScheduler ingestion is incompatible** — must be re-architected into a cron-triggered
   HTTP function (**FIXABLE at significant cost**, see §3/§10).
2. **Vercel Cron on the Hobby plan is limited to once per DAY** (`design`'s "every few minutes"
   cadence is impossible on Hobby) — requires the **Pro plan** for once-per-minute cron
   (**BROKEN on Hobby / FIXABLE only by paying for Pro**, see §3/§9).

Everything else (edge routing, Postgres, cache, TLS, CD) is achievable. Details below.

---

## 1. Topology mapping

| Piece | Maps to | How |
|---|---|---|
| Static React SPA | Vercel static output | Vite build emitted to the output dir; Vercel serves it from its CDN. |
| FastAPI backend | Vercel **Python Functions** (ASGI) | Vercel's Python runtime runs ASGI apps; it looks for a FastAPI instance named `app` at a supported entrypoint (e.g. `api/index.py`). Routers still mount bare (PROXY-1 preserved) with the edge stripping `/api/v1`. |
| Ingestion job | Vercel **Cron** → HTTP function | Cron hits a protected route (e.g. `/internal/ingest`) that runs one ingestion pass and returns. Replaces the in-process APScheduler loop. |
| PostgreSQL | **Supabase** project | Managed Postgres; app connects through Supabase's Supavisor pooler in transaction mode (§4). |
| Valkey/Redis | **Upstash Redis** | Native `redis://`/`rediss://` TCP endpoint, redis-py compatible (§5). |
| Edge routing | `vercel.json` `rewrites` | Same-origin SPA + API + OAuth callback; prefix strip via rewrite (§2). |

**Function layout (concrete):** a single repo with `api/index.py` exposing the ASGI `app`, a
`vercel.json` at repo root, the Vite SPA build output, and `requirements.txt`/`pyproject` pinning
`fastapi`, `uvicorn` (or just the ASGI app — Vercel wraps it), `asyncpg`, `redis`. The Vercel Python
runtime auto-detects FastAPI. Sources:
[Python runtime](https://vercel.com/docs/functions/runtimes/python) (accessed 2026-07-18),
[Deploy FastAPI on Vercel](https://vercel.com/docs/frameworks/backend/fastapi) (accessed 2026-07-18).

## 2. Edge requirements (prefix strip, no trailing-slash meddling, SPA fallback, same origin)

All four are achievable in one `vercel.json` because the SPA, the API, and the OAuth callback all
live on the same Vercel deployment origin (single registrable domain).

- **Prefix strip** `/api/v1/*` → FastAPI bare paths: a rewrite
  `{ "source": "/api/v1/:path*", "destination": "/api/index.py?..." }` (or route to the function and
  strip the prefix) sends the request to the Python function without the `/api/v1` segment. This
  preserves PROXY-1 (FastAPI never sees `/api/v1`).
- **SPA fallback**: standard `{ "source": "/(.*)", "destination": "/index.html" }` rewrite for
  non-API paths; the React router takes over. Ordering matters — the `/api/v1` rewrite must precede
  the catch-all.
- **OAuth callback same origin**: the EVE SSO callback is just another `/api/v1/...` route → handled
  by the same rewrite; cookies are set by the Python function and are first-party to the Vercel
  origin.
- **Trailing-slash behavior**: Vercel's default is `trailingSlash: undefined`, meaning **no redirect**
  is issued for a path with or without a trailing slash — this is the behavior the app needs (paths
  preserved verbatim, no 308 slash rewriting). Do NOT set `trailingSlash: true/false`, which would
  issue 308 redirects. **CAVEAT (FIXABLE / must-verify):** there are documented community reports of
  Vercel appending a trailing slash to *rewrite destinations* in some configurations
  ([Vercel community thread](https://community.vercel.com/t/vercel-add-trailing-slash-for-rewrite-destination-causing-failures/22013),
  accessed 2026-07-18). This must be validated against the actual `vercel.json` before trusting it;
  the app is trailing-slash-sensitive.

Sources: [vercel.json configuration](https://vercel.com/docs/project-configuration/vercel-json)
(accessed 2026-07-18).

## 3. Single-scheduler safety

**The in-process APScheduler cannot run on Vercel** (no long-lived process; §Headline). The
replacement is Vercel Cron invoking an HTTP function. Two hazards:

- **Cadence — BROKEN on Hobby.** Cron minimum interval is **once per day on Hobby**, once per minute
  on Pro/Enterprise. Cron expressions more frequent than daily **fail at deploy time** on Hobby
  ("Hobby accounts are limited to daily cron jobs"). Hangar Bay's "every few minutes" ingestion is
  therefore impossible on Hobby and requires **Pro** ($20/user/mo). On Hobby, scheduling precision is
  per-hour (±59 min); on Pro it is per-minute.
  ([Cron usage & pricing](https://vercel.com/docs/cron-jobs/usage-and-pricing), accessed 2026-07-18.)
- **Concurrency / at-most-once — FIXABLE, needs a distributed lock.** Vercel Cron does **not**
  guarantee that a prior invocation has finished before it fires the next one. If an ingestion pass
  runs longer than the cron interval (plausible: 2–7 min first ingest vs a 1-minute cron), a second
  invocation can start concurrently. The current in-process design got single-scheduler safety for
  free (one process, one scheduler). On serverless this must be added explicitly — e.g. a Postgres
  advisory lock (`pg_try_advisory_lock`) or a Redis `SET key NX EX` lock at the top of the ingestion
  function, bailing out if the lock is held. This is net-new code Hangar Bay does not have today.

## 4. Postgres (Supabase)

- **Offering:** managed Postgres with pooling (Supavisor), REST/realtime layers (unused here),
  dashboard, and point-in-time/daily backups on paid tiers.
- **Free tier:** 500 MB database, 1 GB file storage, unlimited API requests, **no backups**, no SLA.
  Free projects also pause after inactivity. **MISSING for a "durable + backups" production
  requirement** — the free tier does not meet the backup requirement.
- **Pro tier ($25/mo per org, includes 8 GB DB + 100 GB storage):** daily backups included;
  point-in-time-recovery / longer retention is a paid add-on (~$100/mo per 7 days retention — likely
  overkill at hobby scale). Meets the backup requirement.
- **Connection pooling for serverless (critical):** use the **Supavisor transaction-mode pooler on
  port 6543**, not the direct 5432 connection — serverless functions open many short-lived
  connections and would exhaust direct connections. With **asyncpg** through the transaction-mode
  pooler you MUST disable prepared-statement caching (`statement_cache_size=0`, and set
  `prepared_statement_cache_size=0` on the SQLAlchemy asyncpg dialect) and use a `NullPool` (let
  Supavisor own pooling), because transaction mode does not preserve session-level prepared
  statements across pooled connections. This is a concrete `DATABASE_URL` + engine-config change vs
  the current long-lived-process assumption (**FIXABLE, small-to-moderate**). Sources:
  [Supabase connecting to Postgres](https://supabase.com/docs/guides/database/connecting-to-postgres),
  [Supavisor FAQ](https://supabase.com/docs/guides/troubleshooting/supavisor-faq-YyP5tI) (both accessed 2026-07-18),
  [Supabase pricing](https://supabase.com/pricing) (accessed 2026-07-18).

## 5. Valkey/Redis (Upstash)

- **Protocol — OK.** Upstash Redis exposes a native **TCP `redis://`/`rediss://`** endpoint in
  addition to its REST API. The app uses redis-py over a `redis://` URL, which is supported directly
  (no REST-only limitation). `CACHE_URL` can point at the Upstash `rediss://` string. Caveat: from a
  *serverless function*, native TCP connections work but Upstash markets the REST API for edge/HTTP
  environments; for the Python function (Node/Python serverless, not edge runtime) the TCP protocol
  is fine.
- **Cost:** Free tier = 256 MB / 500K commands per month; pay-as-you-go = $0.20 per 100K commands +
  $0.25/GB-month storage, 200 GB bandwidth free; fixed plans from $10/mo. As a pure loss-tolerable
  cache at hobby traffic, the **free tier likely suffices** (256 MB, 500K cmds/mo). Sources:
  [Upstash Redis pricing](https://upstash.com/pricing/redis),
  [Upstash pricing & limits](https://upstash.com/docs/redis/overall/pricing) (both accessed 2026-07-18).

## 6. Secrets provisioning (avoiding CLI-arg exposure)

- **Vercel:** environment variables/secrets can be set via the **dashboard UI** (no shell exposure)
  or `vercel env add <NAME>` which **reads the value from an interactive stdin prompt**, not a
  `--flag` argument. Both satisfy the "no secrets in CLI args" rule (nothing lands in `ps`/shell
  history). Values are injected into functions as env vars at runtime. **OK.**
- **Supabase / Upstash:** connection strings are generated in their dashboards and copy-pasted into
  Vercel env vars via the paths above; no CLI-flag exposure required. **OK.**
- The one caution: in GitHub Actions, tokens must come from repo secrets referenced as
  `${{ secrets.X }}` and passed via **environment variables** (e.g. `VERCEL_TOKEN`), never as
  `--token <value>` literals in the workflow (§8).

## 7. TLS + custom domain

- Vercel provisions **automatic TLS** (managed certificates) for custom domains added in the project
  settings; HTTPS is on by default with HTTP→HTTPS redirect. A real custom domain gives the stable
  registrable origin needed for host-scoped Secure+HttpOnly session cookies and the EVE SSO callback.
  **OK.** Custom domains are available on Hobby and Pro. Source:
  [vercel.json / domains docs](https://vercel.com/docs/project-configuration/vercel-json) (accessed 2026-07-18).

## 8. GitHub Actions CD

- **Official path:** install the Vercel CLI in the workflow, `vercel pull` to fetch env, `vercel build`,
  then `vercel deploy --prebuilt` — authenticating via the **`VERCEL_TOKEN` environment variable**
  (the documented non-interactive path), with `VERCEL_ORG_ID` and `VERCEL_PROJECT_ID` as repo
  secrets/vars. Token is a personal/team access token scoped to the account; store as a **repository
  secret**. Third-party actions (`amondnet/vercel-action`, `BetaHuhn/deploy-to-vercel-action`) exist
  but the first-party CLI path is sufficient and keeps the token in an env var, not an arg. Sources:
  [Vercel + GitHub Actions KB](https://vercel.com/kb/guide/how-can-i-use-github-actions-with-vercel),
  [deploy-to-vercel-action](https://github.com/marketplace/actions/deploy-to-vercel-action) (both accessed 2026-07-18).
- **Note:** the repo already auto-deploys from Git if the Vercel GitHub integration is connected;
  the Actions path is for teams that want CI to gate deploys. Either works.

## 9. TOTAL monthly cost estimate (hobby scale, mid-2026)

Two scenarios, because the ingestion cadence forces the Vercel plan:

**Scenario A — cadence honored ("every few minutes" ingestion):**

| Item | Plan | Cost/mo |
|---|---|---|
| Vercel | **Pro** (required for sub-daily cron) | **$20** |
| Supabase | **Pro** (required for backups) | **$25** |
| Upstash Redis | Free (pure cache, hobby traffic) | $0 |
| Custom domain | (registrar, external) | ~$1–2 amortized |
| **Total** | | **~$45–47/mo** |

This is **above the stated ~$40/mo ceiling** and well above the $5–25 ideal, driven by the two
mandatory paid tiers.

**Scenario B — requirements relaxed (all-free tiers):**

| Item | Plan | Cost/mo |
|---|---|---|
| Vercel | Hobby | $0 |
| Supabase | Free (no backups, project auto-pauses) | $0 |
| Upstash Redis | Free | $0 |
| **Total** | | **$0** |

But Scenario B **fails two hard requirements**: cron cannot run more than once/day (BROKEN cadence)
and there are no Postgres backups (MISSING durability). So the realistic figure for Hangar Bay's
actual requirements is **Scenario A (~$45/mo)**. Sources:
[Vercel Hobby plan](https://vercel.com/docs/plans/hobby),
[Vercel functions limits](https://vercel.com/docs/functions/limitations),
[Supabase pricing](https://supabase.com/pricing),
[Upstash pricing](https://upstash.com/pricing/redis) (all accessed 2026-07-18).

## 10. Risks / limitations specific to THIS app

| # | Finding | Class |
|---|---|---|
| R1 | **In-process APScheduler is fundamentally incompatible** with serverless (no long-lived process; background threads frozen between invocations). Must re-architect ingestion into a cron-triggered HTTP endpoint. Touches the scheduler bootstrap in `main.py`/app startup, the ESI ingestion service entrypoint (extract a "run one pass" callable invoked by the HTTP route instead of the APScheduler loop), and startup wiring. The ingestion *logic* (ESIClient, ETag/cache, DB writes) is reusable; the *driver* changes. | **FIXABLE at significant cost** (re-architecture, not a config tweak) |
| R2 | **Cron cadence: once/day on Hobby.** "Every few minutes" is impossible on Hobby; requires Vercel Pro ($20/mo) for once-per-minute. | **BROKEN on Hobby / FIXABLE via Pro** |
| R3 | **Function duration vs multi-minute ingest.** Hobby max = **300 s (5 min)**; a 2–7 min first ingest can exceed 300 s → `FUNCTION_INVOCATION_TIMEOUT` (504). Pro is configurable to **800 s** (GA) / 1800 s (beta), which covers 7 min. So the first-ingest duration *also* effectively forces Pro, or requires chunking the ingest into resumable sub-passes (more re-architecture). | **BROKEN on Hobby / FIXABLE via Pro or chunking** |
| R4 | **At-most-once concurrency not guaranteed** by Vercel Cron; overlapping invocations possible if a pass runs long. Needs an explicit distributed lock (Postgres advisory lock or Redis `SET NX`). Net-new code. | **FIXABLE (moderate)** |
| R5 | **Python 3.14 support unconfirmed on Vercel.** Vercel's Python runtime documents 3.12/3.13-era support in 2026 examples; **3.14 availability is not confirmed** and Vercel controls the runtime version (you cannot ship an arbitrary interpreter). The project targets 3.14 (per CLAUDE.md). If Vercel tops out at 3.13, the backend would need to run on 3.13 on this platform. Must be verified against the live runtimes doc before committing. | **MISSING / must-verify** ([Python runtimes](https://vercel.com/docs/functions/runtimes/python), accessed 2026-07-18) |
| R6 | **Cold starts.** FastAPI functions with many imports add ~300–800 ms to the first request after idle; each ingestion cron invocation also pays cold start. Acceptable for a hobby app but a UX note for the SPA's first API call. | **FIXABLE / acceptable** |
| R7 | **asyncpg + transaction-mode pooler config** (statement cache off, NullPool, port 6543) is mandatory or connections break under serverless fan-out. Concrete engine-config change. | **FIXABLE (small)** |
| R8 | **Session-cookie / same-origin across the rewrite** works because SPA + API + OAuth callback share one Vercel origin; the Python function sets host-scoped Secure+HttpOnly cookies that are first-party. No cross-origin/CORS needed (matches the app's no-CORS design). Only risk is the trailing-slash-on-rewrite caveat (§2) altering the callback path. | **OK / verify §2 caveat** |
| R9 | **Two mandatory paid tiers push cost to ~$45/mo**, over the ~$40 ceiling and far over the $5–25 ideal. | **Cost limitation (not fixable without dropping requirements)** |

### Classification summary

- **BROKEN (on the intended Hobby/budget target):** cron cadence once/day (R2); function-duration
  timeout on 7-min ingest (R3). Both dissolve only by paying for Vercel Pro.
- **MISSING:** Postgres backups absent on Supabase free tier (§4); Python 3.14 runtime support
  unconfirmed (R5).
- **FIXABLE:** re-architect APScheduler → cron+HTTP (R1, significant cost); distributed lock for
  at-most-once (R4); asyncpg transaction-pooler config (R7); trailing-slash-on-rewrite verification
  (§2).
- **OK:** edge prefix-strip + SPA fallback + same-origin (§2), Upstash native `redis://` for redis-py
  (§5), secrets via dashboard/stdin (§6), automatic TLS + custom domain (§7), GitHub Actions CD via
  `VERCEL_TOKEN` env (§8), same-origin session cookies (R8).

---

## Sources (all accessed 2026-07-18)

- Vercel Python runtime — https://vercel.com/docs/functions/runtimes/python
- Deploy FastAPI on Vercel — https://vercel.com/docs/frameworks/backend/fastapi
- Vercel function limits — https://vercel.com/docs/functions/limitations
- Vercel function duration config — https://vercel.com/docs/functions/configuring-functions/duration
- Vercel Cron usage & pricing — https://vercel.com/docs/cron-jobs/usage-and-pricing
- Vercel Hobby plan — https://vercel.com/docs/plans/hobby
- vercel.json configuration — https://vercel.com/docs/project-configuration/vercel-json
- Vercel trailing-slash-on-rewrite community report — https://community.vercel.com/t/vercel-add-trailing-slash-for-rewrite-destination-causing-failures/22013
- Vercel + GitHub Actions — https://vercel.com/kb/guide/how-can-i-use-github-actions-with-vercel
- Supabase pricing — https://supabase.com/pricing
- Supabase connecting to Postgres — https://supabase.com/docs/guides/database/connecting-to-postgres
- Supabase Supavisor FAQ — https://supabase.com/docs/guides/troubleshooting/supavisor-faq-YyP5tI
- Upstash Redis pricing — https://upstash.com/pricing/redis
- Upstash pricing & limits — https://upstash.com/docs/redis/overall/pricing
