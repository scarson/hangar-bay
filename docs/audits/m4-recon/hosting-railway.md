# M4 Recon — Hosting Candidate: Railway

ABOUTME: Read-only evaluation of Railway as a hosting target for Hangar Bay (FastAPI + in-process scheduler, Postgres, Valkey, static SPA, same-origin edge).
ABOUTME: One candidate in a comparative eval — merits only, no cross-platform recommendation. Pricing/capabilities as of access date 2026-07-18.

Scope: evaluate whether Railway can host the full Hangar Bay stack at hobby scale
(target well under ~$40/mo, ideally ~$5–25/mo). Findings are classified
**BROKEN** (cannot be done on this platform) / **MISSING** (not offered natively;
needs a workaround or external service) / **FIXABLE** (supported but needs
non-default config or app-level work). No recommendation is given here.

All external claims cite a URL and were checked on **2026-07-18**.

---

## 0. What Railway is (one paragraph)

Railway deploys **containers**, not serverless functions. Each "service" is a
long-running container built from a Dockerfile (our case), Nixpacks/Railpack
autodetect, or a prebuilt image, attached optionally to a persistent **volume**.
Services in a project share a private IPv6 network (`*.railway.internal`) and can
each be given a public domain with automatic TLS. Databases (Postgres, Redis,
etc.) are just services deployed from Railway's templates onto a volume — managed
*templates*, not a fully managed DBaaS control plane. Billing is **usage-based**
(vCPU-seconds + memory-GB-hours + volume-GB + egress) on top of a plan floor.
Background workers, persistent connections, and long-running processes "just
work" because the runtime is a container, not a function
([docs.railway.com/overview/advanced-concepts](https://docs.railway.com/overview/advanced-concepts);
Railway serverless/worker note in
[station.railway.com healthcheck-on-serverless](https://station.railway.com/questions/healthcheck-on-service-serverless-wakeup-0554b21f)).

---

## 1. Topology mapping

Recommended layout: **four services in one Railway project + environment**.

| Service | Build | Public? | Volume | Role |
|---|---|---|---|---|
| `edge` (Caddy) | Dockerfile (Caddy + built SPA `dist/`) | **Yes** — the registrable domain | no | Serves SPA with `try_files … /index.html`; reverse-proxies `/api/v1/*` to `backend` with prefix stripped |
| `backend` (FastAPI) | Dockerfile (`python:3.14-slim`, uvicorn) | **No** — private only | no | API + in-process APScheduler ingestion; listens on `::` (IPv6) |
| `postgres` | Railway Postgres template | No | **Yes** (durable) | Primary store |
| `cache` (Valkey/Redis) | Docker image (`valkey/valkey` or Railway Redis template) | No | no (loss-tolerable) | Cache |

Key wiring facts:

- **Same origin is achieved by making only `edge` public.** `backend` gets *no*
  public domain — it is reached over private networking at
  `backend.railway.internal:8000`. This is the standard Railway pattern for
  "one domain, multiple internal services"
  ([docs.railway.com/guides/spa-routing-configuration](https://docs.railway.com/guides/spa-routing-configuration)).
- **IPv6-only private net.** Both `edge`→`backend` and `backend`→`postgres`/`cache`
  use `.railway.internal` hostnames, which resolve to IPv6. FastAPI/uvicorn must
  bind `::` (not `0.0.0.0`) or the private-net traffic won't reach it
  ([docs.railway.com/guides/private-networking](https://docs.railway.com/reference/private-networking)).
- **Config files that live in the repo:** a `Dockerfile` per service (or one repo
  with `railway.json`/service-level root-directory settings), a `Caddyfile` for
  `edge`, and Railway service settings for start command / health-check path /
  region. Railway can build multiple services from one monorepo by pointing each
  service at a different root directory or Dockerfile path.

**Classification: FIXABLE** — the topology is a well-trodden Railway pattern, but
it is *not* zero-config: you must hand-author the Caddy edge rather than lean on
Railway's built-in static hosting (which cannot strip a prefix or proxy — see §2).

---

## 2. Edge requirements (prefix strip, SPA fallback, no trailing-slash meddling, same origin)

The four edge requirements are: (a) serve SPA with fallback to `index.html`,
(b) route `/api/v1/*` to backend **with `/api/v1` stripped**, (c) preserve all
other paths verbatim (no trailing-slash rewriting), (d) same registrable origin.

Railway's **built-in static hosting / Nixpacks staticfile provider cannot do (b)**
— it serves files and does SPA fallback but has no reverse-proxy or path-rewrite
capability ([docs.railway.com/guides/static-hosting](https://docs.railway.com/guides/static-hosting)).
The documented SPA guide only shows a pass-through proxy (`handle /api/* {
reverse_proxy backend:3000 }`) with **no prefix stripping**
([docs.railway.com/guides/spa-routing-configuration](https://docs.railway.com/guides/spa-routing-configuration)).

So the edge must be **your own Caddy service**. Caddy meets all four exactly:

```
# Caddyfile on the `edge` service
:{$PORT} {
    # (b)+(c): strip /api/v1 and proxy the remainder verbatim.
    # handle_path strips the MATCHED prefix (/api/v1) before proxying;
    # Caddy's reverse_proxy passes the remaining URI as-is and does NOT
    # normalize trailing slashes.
    handle_path /api/v1/* {
        reverse_proxy backend.railway.internal:8000
    }

    # (a): SPA — serve file if present, else fall back to index.html.
    handle {
        root * /srv
        try_files {path} /index.html
        file_server
    }
}
```

- **Prefix strip:** `handle_path` (not `handle`) strips the matched `/api/v1`
  segment. `/api/v1/contracts` → backend sees `/contracts`, matching the
  bare-router convention (PROXY-1). ✔
- **No trailing-slash meddling:** Caddy's `reverse_proxy` forwards the path
  untouched; there is no implicit `/`→`` or `redir`/canonicalization on proxied
  routes unless you add it. ✔ (Do **not** add `file_server`'s directory-index
  behavior to the proxied path — it's in a separate `handle` block, so it can't.)
- **SPA fallback:** `try_files {path} /index.html`. ✔
- **Same origin:** only `edge` is public; the OAuth (EVE SSO) callback hits
  `/api/v1/auth/...` on the same host and is proxied to `backend`. `Secure`+
  `HttpOnly` cookies work because Railway terminates real TLS on the custom domain
  (§7). ✔

**Classification: FIXABLE** — every requirement is met *exactly*, but only via a
self-authored Caddy edge; Railway's native static hosting is **MISSING** the
prefix-strip/proxy capability, so the Caddy service is mandatory, not optional.

---

## 3. Single-scheduler safety (the load-bearing constraint)

Requirement: exactly **one** backend instance may run the APScheduler ingestion;
briefly-two during a deploy risks duplicate ESI ingestion.

Railway's deploy model (["Deployments" reference](https://docs.railway.com/deployments/reference)):

- **Singleton by default:** "by default, Railway maintains only one deploy per
  service." Do **not** set replicas > 1 (replicas would run N schedulers
  simultaneously — that's the multi-instance load-balanced mode and is
  disqualifying for the in-process scheduler).
- **Deploys overlap on purpose:** on a new deploy Railway starts the new
  container, waits for it to become `Active` (health check must pass first if
  configured), and only *then* tears down the old one "with a slight overlap for
  zero downtime."
- `RAILWAY_DEPLOYMENT_OVERLAP_SECONDS` controls the time **from when the new
  deploy becomes `Active` until the old one is removed**. Setting it to `0`
  minimizes the *post-Active* overlap.
- `RAILWAY_DEPLOYMENT_DRAINING_SECONDS` controls the SIGTERM→SIGKILL grace on the
  old container (default 0s).

**The trap:** even with `RAILWAY_DEPLOYMENT_OVERLAP_SECONDS=0`, the *new*
container is **booting while the old one is still Active**. Our APScheduler starts
in-process at process startup — i.e., before the health check passes — so during
the new container's boot+healthcheck window, **two schedulers are alive at once**.
`OVERLAP_SECONDS` only governs the window *after* the new deploy is Active; it does
nothing about the boot-time overlap. There is **no Railway setting for "stop the
old instance before starting the new one"** (that would mean downtime, which
Railway's model deliberately avoids). So the platform **cannot, by config alone,
guarantee max-one-scheduler across a deploy.**

Two ways to make this safe (both app-level, both cheap):

1. **Postgres advisory lock around the scheduler** (recommended). On startup the
   backend attempts `pg_try_advisory_lock(<const>)`; only the holder runs the
   APScheduler job loop; a non-holder serves API traffic but skips ingestion. The
   old instance holds the lock until it exits on SIGTERM (release the lock in a
   shutdown handler); the new instance blocks/those-few-seconds until it acquires
   it. This makes duplicate ingestion **impossible** regardless of overlap timing,
   and is the standard fix for in-process schedulers on any rolling platform.
2. **Idempotent ingestion** (defense-in-depth, likely already partly true): the
   ESI pipeline already uses ETag/Valkey caching and upserts normalized rows, so a
   duplicated run is mostly wasted work rather than data corruption — but "mostly"
   isn't a guarantee, so pair it with the advisory lock.

**Classification: FIXABLE, but flag prominently.** Railway's singleton-with-overlap
model is **MISSING** a "recreate / stop-before-start" strategy, so a
platform-only single-scheduler guarantee is not achievable. The app-level advisory
lock closes the gap completely and is the right design anyway (it also protects
against the operator accidentally scaling replicas, and against a crashed
container that Railway restarts while the old is draining).

---

## 4. Postgres — managed offering, storage, backups, cost

- **Offering:** Railway Postgres is a template-deployed container on a volume, not
  a hyperscaler-managed RDS. You get a real Postgres with a `DATABASE_URL`, but
  you own version bumps and tuning
  ([docs.railway.com/databases/postgresql](https://docs.railway.com/databases/postgresql)).
- **Storage:** backed by a Railway volume, billed at **$0.15 / GB / month**
  ([docs.railway.com/pricing/plans](https://docs.railway.com/pricing/plans)). A
  hobby-scale contracts dataset is small (single-digit GB).
- **Backups:** Railway now has **native, snapshot-based backups** for any service
  with a volume. Snapshot-based means restore-to-last-snapshot, with a data-loss
  window "of hours or even a full day." **Point-in-Time Recovery (7-day WAL
  window)** is being rolled out as a **Pro-only, opt-in** feature — *not* available
  on Hobby ([blog.railway.com/p/automated-postgresql-backups](https://blog.railway.com/p/automated-postgresql-backups);
  [station.railway.com PITR feedback](https://station.railway.com/feedback/point-in-time-recovery-for-postgre-sql-d8c063e2)).
  For stronger guarantees on Hobby, community templates (`Postgres Daily Backups`,
  `Postgresus`) push `pg_dump` to S3/GCS on a schedule
  ([railway.com/deploy/postgres-daily-backups](https://railway.com/deploy/postgres-daily-backups)).
- **Cost at hobby scale:** compute for a small idle Postgres ~0.25–0.5 GB RAM →
  ~$3–5/mo, plus ~$0.15–0.75 for 1–5 GB volume. Call it **~$4–6/mo**.

**Classification: FIXABLE** — durable storage ✔; automated backups exist but on
Hobby they are **snapshot-granularity only** (PITR is Pro-gated), which is a
**MISSING** capability for tight RPO. Acceptable for this app (contract data is
re-ingestable from ESI), but worth an explicit decision.

---

## 5. Valkey / Redis — managed or sidecar, cost

- Railway offers a one-click **Redis** template; **Valkey** can be run as a plain
  Docker-image service (`valkey/valkey`) since Railway deploys arbitrary images
  ([railway.com/pricing](https://railway.com/pricing) lists Redis among built-in
  databases; arbitrary images per advanced-concepts doc above).
- Because the cache is **loss-tolerable**, attach **no volume** — run it ephemeral.
  That drops storage cost to $0 and sidesteps the backup question entirely.
- **Cost:** tiny memory footprint (~0.1–0.25 GB) → **~$1–3/mo** compute.

**Classification: FIXABLE** (effectively native) — Redis is one-click; Valkey is a
one-image service. No blockers.

---

## 6. Secrets provisioning (avoid CLI-arg exposure)

Secrets in scope: `ESI_CLIENT_ID`, `ESI_CLIENT_SECRET`, `TOKEN_CIPHER_KEYS`,
`DATABASE_URL`, `CACHE_URL`.

- `DATABASE_URL` / `CACHE_URL` are best set as **reference variables** (e.g.
  `${{Postgres.DATABASE_URL}}`, `${{cache.REDIS_URL}}`) so they're wired
  automatically and never typed by hand
  ([docs.railway.com/reference/variables](https://docs.railway.com/reference/variables)).
- **The exposure risk:** the CLI `railway variables --set "KEY=value"` puts the
  secret **in argv**, visible in `ps`/shell history — violates the project's
  "no secrets in CLI flags" rule
  ([docs.railway.com/cli/variable](https://docs.railway.com/cli/variable)).
- **Safe paths that avoid argv exposure:**
  1. **Dashboard** — paste `ESI_CLIENT_SECRET` / `TOKEN_CIPHER_KEYS` into the
     service Variables UI (or the multiline "Raw Editor" that accepts a
     `.env`-style paste). This is the recommended one-time path; nothing hits a
     shell.
  2. **GraphQL API `variableUpsert`** with the token in an env var and the
     payload supplied from a **file/stdin** (`curl … --data @payload.json`), so the
     secret value is never a command-line argument
     (public API; referenced in
     [docs.railway.com/reference/public-api](https://docs.railway.com/reference/public-api)).
- Railway does **not** document a first-class `railway variables --set-from-stdin`
  / file-import flag on the CLI, so the CLI `--set` path is the one to avoid.

**Classification: FIXABLE** — safe provisioning is fully available (dashboard, or
API-with-file), but the *obvious* CLI path (`variables --set`) is exposure-prone,
so this needs a documented "use the dashboard/API, not the CLI flag" convention.

---

## 7. TLS + custom domain

- Add a custom domain to the `edge` service → Railway auto-issues and renews a
  **Let's Encrypt** certificate; you add a CNAME (apex needs a provider that
  supports CNAME-flattening / ALIAS, or use a `www` + redirect)
  ([docs.railway.com/networking/domains/working-with-domains](https://docs.railway.com/networking/domains/working-with-domains)).
- Real HTTPS on a real domain satisfies the `Secure`+`HttpOnly` cookie / OAuth
  callback requirement.
- Wildcards work but need an extra `_acme-challenge` CNAME + TXT; not needed here
  (single host). Community reports occasional wildcard cert-issuance hiccups —
  irrelevant for a single apex/`www`
  ([station.railway.com wildcard cert issue](https://station.railway.com/questions/wildcard-custom-domain-brimwise-com-fa-4721f68b)).

**Classification: FIXABLE** (native) — no blocker.

---

## 8. GitHub Actions CD

- Railway supports **Project/Deploy tokens** scoped to a single project +
  environment, usable non-interactively. In a workflow, set `RAILWAY_TOKEN` (a
  GitHub Actions secret) and run `railway up` (or `railway redeploy`) via the
  Railway CLI ([docs.railway.com/cli/deploying](https://docs.railway.com/cli/deploying);
  [station.railway.com token-for-github-action](https://station.railway.com/questions/token-for-git-hub-action-53342720)).
- The token scoping is appropriate (environment-scoped, deploy-only actions).
- Alternative: Railway's native GitHub integration auto-deploys on push to a
  branch, but the workflow-token path gives the repo's existing CI more control
  (build/test gate → then deploy).
- **Deploy-strategy interaction:** whichever trigger, each deploy runs the §3
  overlap dance — so the advisory-lock guard is what makes CD safe, not the CD
  mechanism itself.

**Classification: FIXABLE** (native) — official CLI + scoped token. Note the token
must be a masked GitHub secret (not inlined), consistent with the no-secrets-in-CI
rule.

---

## 9. Total monthly cost estimate (hobby scale, mid-2026)

Pricing basis, all from [docs.railway.com/pricing/plans](https://docs.railway.com/pricing/plans)
(accessed 2026-07-18): **Hobby $5/mo including $5 of usage** (usage credit resets
monthly, does **not** roll over); overage billed at **RAM $10/GB/mo, CPU
$20/vCPU/mo, volume $0.15/GB/mo, egress $0.05/GB**. Bill ≈ `max($5, actual usage)`.

Itemized (usage-metered, low-traffic assumptions — services mostly idle CPU):

| Component | Memory (avg) | CPU (avg) | Volume | Est. $/mo |
|---|---|---|---|---|
| `backend` (FastAPI + scheduler, always-on) | ~0.35 GB | ~0.05 vCPU | — | ~$4.5 |
| `edge` (Caddy, always-on) | ~0.1 GB | ~0.02 vCPU | — | ~$1.5 |
| `postgres` | ~0.35 GB | idle | 1–3 GB | ~$4.5 |
| `cache` (Valkey, ephemeral) | ~0.15 GB | idle | — | ~$1.5 |
| egress | — | — | — | <$1 |
| **Subtotal (usage)** | | | | **~$13** |
| Plan floor (Hobby, includes first $5) | | | | — |
| **Estimated bill** | | | | **~$13–20/mo** |

- The estimate lands **inside the ~$5–25 ideal band** and well under the ~$40 cap.
- **Sensitivity:** the number is usage-metered, so a memory-hungrier Python
  process (uvicorn workers, large in-memory caches) or heavier ESI-ingest CPU
  bursts push it up. A realistic worst case (backend ~0.7 GB + more CPU) is
  ~$25–30/mo — still under cap but eating the ideal band. Third-party trackers put
  a "web + worker + Postgres + Redis" combo at **$50–80/mo** if services are
  provisioned generously ([buildmvpfast Railway pricing](https://www.buildmvpfast.com/tools/api-pricing-estimator/railway);
  [servercompass Railway pricing](https://servercompass.app/blog/railway-pricing-what-youll-actually-pay))
  — that reflects heavier apps than this one, but it's the direction cost drifts if
  usage grows.
- Cost control lever: because the scheduler needs the backend always-on, **App
  Sleeping cannot be used on `backend`** (see §10), so you can't scale-to-zero the
  main cost driver. `edge`/`cache`/`postgres` also stay warm.

**Classification: FIXABLE** — comfortably in-budget at true hobby load; watch
memory, since Railway meters it and it's the largest single line.

---

## 10. Risks / limitations specific to THIS app

1. **Deploy overlap vs. in-process scheduler (§3).** *Highest-severity item.*
   Railway has no stop-before-start deploy mode; new boots while old is Active, so
   two schedulers briefly coexist. **MISSING** at platform level →
   **FIXABLE** with a Postgres advisory lock in the app. Must be designed in.

2. **App Sleeping would kill continuous ingestion — keep it OFF.** Railway's
   Serverless/App-Sleeping pauses a service after ~10 min of no traffic
   ([docs.railway.com/reference/app-sleeping](https://docs.railway.com/reference/app-sleeping)).
   It's **opt-in / off by default**, and its inactivity trigger is *outbound*
   packets — our scheduler's ESI calls every few minutes would keep it awake even
   if enabled — but the safe rule is **do not enable Serverless on `backend`**, or
   the scheduler stops when traffic is quiet. **FIXABLE** (just don't opt in).
   Note the docs' own caveat that wake-from-sleep uses TCP-connect, not the
   configured health path — another reason to leave `backend` always-on.

3. **Python 3.14: non-issue with Dockerfile.** We build from a Dockerfile
   (`python:3.14-slim`), so the runtime version is fully under our control and does
   not depend on Nixpacks/Railpack language detection. **Not a risk.**

4. **Long-running background job model: supported.** Railway runs containers, so a
   long-lived in-process APScheduler loop, persistent DB connections, and outbound
   HTTP to ESI all "just work" — no function timeout, no cold-start eviction of the
   loop ([advanced-concepts](https://docs.railway.com/overview/advanced-concepts)).
   **Not a risk** (given #2's "don't sleep it").

5. **Health-check model.** Railway gates a new deploy on an HTTP-200 health path
   before it goes Active ([docs.railway.com/deployments/healthchecks](https://docs.railway.com/deployments/healthchecks)).
   Good for zero-downtime, but (a) it *lengthens* the boot-time double-scheduler
   window from #1 (the old stays Active until the new passes its check), and (b)
   the health endpoint should assert DB/cache reachability without triggering an
   ingest. **FIXABLE** — add a cheap `/health` on the backend; the advisory lock
   (not the health check) is what enforces single-scheduler.

6. **Backups on Hobby are snapshot-granularity (PITR is Pro-only).** Data-loss
   window up to hours/day on Hobby (§4). **MISSING** for tight RPO; acceptable here
   because contract data is re-ingestable, but it's an explicit accepted risk (or
   add an S3 `pg_dump` template).

7. **Managed-*ish* databases mean you own upgrades/tuning.** Railway Postgres/Redis
   are template containers, not a hands-off DBaaS. Version bumps, `shared_buffers`
   tuning, and connection-limit management are yours. **FIXABLE** but ongoing
   operational surface at hobby scale it's minimal.

8. **Edge is self-built (§2).** The Caddy service is mandatory (native static
   hosting can't strip the prefix). Small but real: a Dockerfile + Caddyfile you
   maintain, and the SPA build must be baked into (or volume-shared with) that
   image. **FIXABLE**, standard pattern.

9. **IPv6-only private networking.** uvicorn must bind `::`; a stray `0.0.0.0`-only
   bind makes `backend` unreachable from `edge`. Easy to miss, easy to fix.
   **FIXABLE.**

---

## Sources (accessed 2026-07-18)

- Deployments reference (overlap/singleton/SIGTERM): https://docs.railway.com/deployments/reference
- Healthchecks: https://docs.railway.com/deployments/healthchecks
- App Sleeping / Serverless: https://docs.railway.com/reference/app-sleeping
- Advanced concepts (containers, workers): https://docs.railway.com/overview/advanced-concepts
- SPA routing guide: https://docs.railway.com/guides/spa-routing-configuration
- Static hosting: https://docs.railway.com/guides/static-hosting
- Pricing plans (rates): https://docs.railway.com/pricing/plans
- Pricing overview: https://railway.com/pricing
- Postgres docs: https://docs.railway.com/databases/postgresql
- Automated PostgreSQL backups (snapshot + PITR-on-Pro): https://blog.railway.com/p/automated-postgresql-backups
- PITR feedback (Pro opt-in): https://station.railway.com/feedback/point-in-time-recovery-for-postgre-sql-d8c063e2
- Postgres daily-backups template: https://railway.com/deploy/postgres-daily-backups
- Variables reference: https://docs.railway.com/reference/variables
- CLI variable command: https://docs.railway.com/cli/variable
- Public API: https://docs.railway.com/reference/public-api
- Custom domains: https://docs.railway.com/networking/domains/working-with-domains
- CLI deploying / RAILWAY_TOKEN: https://docs.railway.com/cli/deploying
- Token for GitHub Action (station): https://station.railway.com/questions/token-for-git-hub-action-53342720
- Serverless wakeup / healthcheck caveat (station): https://station.railway.com/questions/healthcheck-on-service-serverless-wakeup-0554b21f
- Wildcard cert issue (station): https://station.railway.com/questions/wildcard-custom-domain-brimwise-com-fa-4721f68b
- Third-party pricing tracker: https://www.buildmvpfast.com/tools/api-pricing-estimator/railway
- Third-party pricing analysis: https://servercompass.app/blog/railway-pricing-what-youll-actually-pay
