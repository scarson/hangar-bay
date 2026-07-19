# M4 Recon — Hosting Candidate: Fly.io

ABOUTME: Read-only evaluation of Fly.io (Fly Machines + Postgres + Redis) as the Hangar Bay production host for M4.
ABOUTME: Facts + pricing as of 2026-07-18, per-requirement BROKEN/MISSING/FIXABLE classification. No recommendation, no cross-candidate comparison.

Scope: evaluate ONE candidate (Fly.io) against the Hangar Bay deploy requirements — FastAPI + in-process
APScheduler, Postgres, Valkey/Redis cache, static React SPA on the same registrable origin with prefix-strip
edge routing, EVE SSO callback, secure cookies, GitHub Actions CD, hobby budget (target < ~$40/mo, ideally
$5–25/mo). All prices are USD, sourced mid-2026, cited inline. Access date for every URL below: **2026-07-18**.

> Fly.io changed materially in the last ~18 months: the **standing free tier / free allowances were removed for
> new accounts (Oct 2024)** — new signups get only a time-limited free trial, then pay-as-you-go
> ([community.fly.io/t/free-tier-is-dead](https://community.fly.io/t/free-tier-is-dead/20651),
> [fly.io/docs/about/free-trial](https://fly.io/docs/about/free-trial/)). Fly also shipped a **fully Managed
> Postgres (MPG)** product and now treats the old `fly postgres` as **"unmanaged"** and unsupported
> ([fly.io/docs/postgres](https://fly.io/docs/postgres/)). And **volume snapshots became billable in Jan 2026**
> ($0.08/GB-mo after a 10 GB free grant), where they were previously free
> ([sota.io/blog/fly-io-hidden-costs-2026](https://sota.io/blog/fly-io-hidden-costs-2026)). These three shifts
> all push hobby cost upward vs. Fly's historical reputation.

---

## 1. Topology

Fly runs OCI containers ("Fly Machines" — lightweight Firecracker microVMs) defined by a **Dockerfile** you
control, configured by a per-app **`fly.toml`**. There is no buildpack lock-in; because you supply the image,
**Python 3.14 + uvicorn is fully supported** — you pick the base image (e.g. `python:3.14-slim`). Fly's global
Anycast **fly-proxy** terminates TLS and load-balances into your Machines by **port and host only**.

Concrete mapping for Hangar Bay:

| Concern | Fly primitive | Notes |
|---|---|---|
| FastAPI + APScheduler | 1 Fly Machine, `[[vm]]`, `count = 1` | in-process scheduler → must stay single-instance (§3, §10) |
| Static SPA + edge routing | a reverse proxy **inside the container** (Caddy/nginx) | fly-proxy can't path-route (§2) — this is the load-bearing design choice |
| Postgres | Fly **Managed Postgres (MPG)** *or* unmanaged `fly postgres` app | MPG over budget; unmanaged fits budget but is self-owned (§4) |
| Redis/Valkey | **Upstash for Redis** (`fly redis create`) *or* self-run Redis Machine | cache is loss-tolerable → cheapest tier fine (§5) |
| Edge/TLS/domain | fly-proxy + `fly certs` (Let's Encrypt) | free ACME certs, $0.10/mo per hostname (§7) |
| Secrets | `fly secrets import` (stdin) → injected as env at boot | avoids CLI-arg exposure (§6) |
| CD | `superfly/flyctl-actions` + app-scoped deploy token | (§8) |

**Two viable shapes:**

- **Shape A (single container, simplest for hobby):** one Machine, `count = 1`, running **Caddy as the
  entrypoint** (serves the built SPA from disk, reverse-proxies `/api/v1/*` → `127.0.0.1:8000`) **plus uvicorn**
  (FastAPI + in-process APScheduler) under a tiny process manager (honcho/supervisord, or Caddy started as a
  child of the app). One public hostname, same origin, one scheduler. Deploys briefly drop to zero instances —
  fine for hobby, and *desirable* for the scheduler (§3).
- **Shape B (process groups, if web ever needs HA):** one image, three `[processes]` in `fly.toml` — `edge`
  (Caddy, public), `web` (uvicorn, N replicas, private `.flycast`), `scheduler` (uvicorn+APScheduler,
  `count = 1`). Cleanly isolates the single-scheduler constraint from web scaling. More moving parts than a
  hobby app needs today, but the shape is available without re-platforming.

For hobby scale Shape A is sufficient. Classification: **FIXABLE** (topology maps cleanly; the only non-obvious
piece is that the edge must live in-container, see §2).
Sources: [fly.io/docs/reference/configuration](https://fly.io/docs/reference/configuration/),
[fly.io/docs/launch/deploy](https://fly.io/docs/launch/deploy/).

---

## 2. Edge requirements (prefix strip, no trailing-slash meddling, SPA fallback, same origin)

**Critical finding: fly-proxy does NOT do path-based routing, prefix stripping, or trailing-slash rewriting.**
It routes purely by external port and host to an `internal_port`; the path reaches your app verbatim
([fly.io/docs/reference/configuration](https://fly.io/docs/reference/configuration/) — "Fly Proxy does not
perform path-based routing… If you need URL-based routing, implement it within your application"). So **none of
the four edge requirements can be satisfied by Fly's edge itself** — they must be met by a reverse proxy you
bundle in the container.

This is straightforwardly achievable with **Caddy** (or nginx). A Caddyfile meets all four requirements exactly:

```
:8080 {
    handle_path /api/v1/* {          # handle_path STRIPS the matched /api/v1 prefix
        reverse_proxy 127.0.0.1:8000 # → FastAPI sees bare paths, PROXY-1 satisfied
    }
    handle {
        root * /srv/spa
        try_files {path} /index.html # SPA fallback
        file_server
    }
}
```

- **Prefix strip:** Caddy `handle_path` strips the matched prefix before proxying — FastAPI sees `/contracts`,
  not `/api/v1/contracts`. Matches the project's PROXY-1 invariant (routers mounted bare).
- **No trailing-slash rewriting:** Caddy `reverse_proxy` preserves the path/query verbatim; it does not add or
  remove trailing slashes (unlike some nginx `proxy_pass` forms). Requirement met — just don't add `redir`
  rules.
- **SPA fallback:** `try_files {path} /index.html` serves `index.html` for unknown routes.
- **Same origin:** one hostname, one Caddy, both SPA and API behind it → same registrable origin, so the EVE
  SSO callback and `Secure; HttpOnly; SameSite` cookies work with no CORS config (consistent with the app's
  no-CORS same-origin design).

Classification: **FIXABLE** — every requirement is met, but *only* by shipping an in-container reverse proxy;
the platform edge alone cannot do it. This is a real (small) amount of config Fly does not provide out of the
box, unlike platforms with a path-routing edge or a static-site product with rewrite rules.

---

## 3. Single-scheduler safety

This is where Fly's single-Machine model is unexpectedly **well-suited**. With `count = 1` and the **default
`rolling`** (or `immediate`) strategy, a deploy **destroys the old Machine before the replacement boots** —
i.e., it passes through **zero** instances, never two. Fly's own docs/community confirm: "If you only have one
machine, it will be destroyed before there's a new one that can handle requests"
([community.fly.io/t/rolling-deployment-details](https://community.fly.io/t/rolling-deployment-details/24820),
[fly.io/docs/blueprints/seamless-deployments](https://fly.io/docs/blueprints/seamless-deployments/)). For a
web app that's "downtime"; for a **single-writer scheduler it is exactly the guarantee we want** — no
overlapping ingestion.

Deploy-strategy matrix for the scheduler:

| Strategy | Overlap risk | Verdict for in-process scheduler |
|---|---|---|
| `rolling` (default, count=1) | none — old killed first, brief zero | **safe** — recommended |
| `immediate` | none at count=1 — replaces in place | safe; no health-check gating |
| `bluegreen` | **runs new alongside old** before cutover | **UNSAFE — would double-ingest**; also can't use attached volumes |
| `canary` | temporarily runs >1 Machine | **UNSAFE** for scheduler; also can't use attached volumes |

Guarantee mechanics: keep `count = 1` (or, in Shape B, the `scheduler` process group at `count = 1`), set
`[deploy] strategy = "rolling"` (or `immediate`), and **do not** enable `bluegreen`/`canary` on the scheduler.
Additionally set `min_machines_running = 1` and `auto_stop_machines = "off"` so the scheduler is never
scaled-to-zero (§10). Because deploys pass through zero, ingestion pauses for a few seconds per deploy — benign,
since the scheduler re-runs every few minutes.

Classification: **FIXABLE / actually a strength** — max-one-instance is guaranteed by construction with the
default strategy; the only failure mode is *opting into* bluegreen/canary, which the config must avoid.
Sources: [fly.io/docs/reference/configuration](https://fly.io/docs/reference/configuration/),
[community.fly.io/t/rolling-deployment-details](https://community.fly.io/t/rolling-deployment-details/24820).

---

## 4. Postgres (managed, storage, backups, cost)

Two options, and the split matters for budget:

**(a) Fly Managed Postgres (MPG)** — the supported, fully-managed product (HA, automated backups, connection
pooling included). **Cheapest plan is "Basic": Shared-2x CPU / 1 GB RAM at ~$38/mo**, then Starter $72, Launch
$282, etc.; **storage $0.28/provisioned-GB-mo**, up to 1 TB
([fly.io/docs/mpg](https://fly.io/docs/mpg/),
[kuberns.com/blogs/flyio-pricing](https://kuberns.com/blogs/flyio-pricing/),
[community.fly.io/t/managed-postgres-pricing](https://community.fly.io/t/managed-postgres-pricing/25734)). At
$38+ this **single line item consumes essentially the entire ~$40 budget**.

**(b) Unmanaged `fly postgres`** — a Postgres-on-a-Machine app you own. A single-node Development preset
(shared-cpu-1x, 256 MB, 1 GB disk) runs **~$2/mo** for the VM plus **volume at $0.15/GB-mo**
([fly.io/docs/postgres](https://fly.io/docs/postgres/),
[fly.io/docs/postgres/getting-started/create-pg-cluster](https://fly.io/docs/postgres/getting-started/create-pg-cluster/)).
Backups are **your responsibility** and come from **volume snapshots** — which are **no longer free as of Jan
2026**: $0.08/GB-mo after a 10 GB monthly free grant, and Fly keeps several snapshots so effective cost can be
2–5× raw until they age out
([sota.io/blog/fly-io-hidden-costs-2026](https://sota.io/blog/fly-io-hidden-costs-2026)). Fly explicitly warns
it "is not able to provide support or guidance for unmanaged Postgres"
([fly.io/docs/postgres/getting-started/what-you-should-know](https://fly.io/docs/postgres/getting-started/what-you-should-know/)).

Findings:
- **Affordable *managed* Postgres with automated backups: MISSING** — MPG's floor (~$38/mo) blows the ideal
  $5–25 budget and nearly hits the $40 ceiling by itself.
- **Budget-fitting Postgres: FIXABLE** via unmanaged single-node (~$2–3/mo VM + snapshot backups), but you own
  durability/backup/upgrades and get no vendor support. Snapshots give point-in-time-ish recovery; for a
  loss-sensitive DB you'd want to also script `pg_dump` to R2/S3 off-platform.

For a hobby app whose *only* durable data is aggregated public ESI contracts (re-derivable by re-ingesting),
the unmanaged node is a defensible budget choice — but it is a genuine downgrade in backup/support posture vs.
a managed offering, and must be an explicit decision.

---

## 5. Valkey/Redis (cache — loss-tolerable)

Two options:

**(a) Upstash for Redis** (Fly's integrated managed Redis, `fly redis create`): a **free tier of 256 MB /
500K commands/mo** remains available in 2026; **pay-as-you-go** is $0.20/100K commands + $0.25/GB-mo storage
beyond 1 GB free, no bandwidth charge; **fixed plans from $10/mo (250 MB)**
([fly.io/docs/upstash/redis](https://fly.io/docs/upstash/redis/),
[upstash.com/blog/redis-pricing-comparison…-2026](https://upstash.com/blog/redis-pricing-comparison-every-major-provider-in-2026-with-numbers)).
Since the cache is loss-tolerable and low-traffic, the **free tier or PAYG (cents/mo)** is ample. Note it's
Redis-API (Upstash), not literally Valkey — wire-compatible with redis-py, so the app's `CACHE_URL` client is
unaffected.

**(b) Self-run Redis/Valkey sidecar Machine:** a `redis:alpine`/`valkey` Machine at shared-cpu-1x 256 MB
(~$2/mo), no persistence needed (cache). Slightly cheaper than a fixed Upstash plan, one more Machine to
operate. Reachable over private `.flycast`/6PN networking.

Classification: **FIXABLE / low-risk** — cache is cheap either way; Upstash free/PAYG is the path of least
effort and likely $0–2/mo at this traffic.

---

## 6. Secrets provisioning (no CLI-arg exposure)

Fly stores secrets encrypted in a vault and injects them as **environment variables at Machine boot**
([fly.io/docs/apps/secrets](https://fly.io/docs/apps/secrets/)). The exposure-safe path:

- **`fly secrets import`** reads **`NAME=VALUE` pairs from stdin** — set all of `ESI_CLIENT_ID`,
  `ESI_CLIENT_SECRET`, `TOKEN_CIPHER_KEYS`, `DATABASE_URL`, `CACHE_URL` in one shot with **no values on the
  command line** ([fly.io/docs/flyctl/secrets-import](https://fly.io/docs/flyctl/secrets-import/)):
  ```bash
  fly secrets import < secrets.env      # or: some-generator | fly secrets import
  ```
- **`fly secrets set NAME=VALUE`** *does* put the value in argv (visible in `ps`/shell history) — **avoid this
  form**; but `fly secrets set` can also read from stdin, and `--stage` defers the restart.
- **GitHub Actions:** in CD, secrets come from **GitHub repository/environment secrets** piped to
  `fly secrets import` (or already-set and left alone), never as workflow-literal args.

Classification: **FIXABLE / satisfied** — `fly secrets import` from stdin fully meets the "no secrets in CLI
flags" constraint. There is no web-dashboard secret editor emphasized in docs (CLI/API only), but the stdin
path is sufficient and scriptable. The one discipline note: use `import` (stdin), not `set NAME=VALUE` (argv).

---

## 7. TLS + custom domain

Fully supported. `fly certs add <domain>` provisions **free Let's Encrypt (ACME) certificates**, auto-validated
(TLS-ALPN / HTTP-01 / DNS-01) and auto-renewed; you point DNS (A/AAAA to Fly's Anycast IPs, or CNAME) and Fly
issues + renews. Billing: **$0.10/mo per hostname** for cert issuance/renewal
([fly.io/docs/networking/custom-domain](https://fly.io/docs/networking/custom-domain/),
[fly.io/docs/flyctl/certs](https://fly.io/docs/flyctl/certs/)). HTTPS with a real domain — required for the
`Secure` cookies and the EVE SSO callback — is a solved, cheap problem here.

Classification: **FIXABLE / satisfied** (essentially free; $0.10/mo/hostname).

---

## 8. GitHub Actions CD

First-class. Fly publishes **`superfly/flyctl-actions/setup-flyctl`** and documents the workflow
([fly.io/docs/launch/continuous-deployment-with-github-actions](https://fly.io/docs/launch/continuous-deployment-with-github-actions/),
[github.com/superfly/flyctl-actions](https://github.com/superfly/flyctl-actions)):

```yaml
- uses: superfly/flyctl-actions/setup-flyctl@master
- run: flyctl deploy --remote-only
  env:
    FLY_API_TOKEN: ${{ secrets.FLY_API_TOKEN }}
```

**Token scoping:** create an **app-scoped deploy token** — `fly tokens create deploy -x 999999h` — which is
limited to deploying **that one app**, the recommended narrow scope for CI/CD, rather than an org-scoped or
personal auth token ([fly.io/docs/security/tokens](https://fly.io/docs/security/tokens/)). Store it as the
`FLY_API_TOKEN` repo secret. `--remote-only` builds the image on Fly's builders so CI needs no Docker daemon.

Classification: **FIXABLE / satisfied** — official action, properly scoped least-privilege deploy token.

---

## 9. Total monthly cost estimate (hobby scale, mid-2026)

Fly is **pure pay-as-you-go, per-second billing**; stopped Machines don't bill CPU/RAM, but **volumes bill
whether attached or not** ([fly.io/docs/about/pricing](https://fly.io/docs/about/pricing/)). Two scenarios:

**Scenario 1 — budget build (unmanaged PG + Upstash free/PAYG):**

| Item | Config | Est. $/mo |
|---|---|---|
| Backend Machine (Caddy+uvicorn+APScheduler) | shared-cpu-1x, 512 MB–1 GB, always-on | $3–6 |
| Postgres (unmanaged single node) | shared-cpu-1x 256 MB + ~2 GB volume | ~$2 VM + ~$0.30 vol ≈ $2.50 |
| PG snapshot backups | ~1–3 GB, under/near 10 GB free grant | $0–1 |
| Redis cache | Upstash free tier or PAYG | $0–2 |
| TLS cert | 1 hostname | $0.10 |
| Egress bandwidth | < 100 GB free (NA/EU), then $0.02/GB | $0 |
| **Total** | | **~$8–12/mo** |

**Scenario 2 — managed-DB build (MPG Basic + Upstash fixed):**

| Item | Config | Est. $/mo |
|---|---|---|
| Backend Machine | shared-cpu-1x, 512 MB–1 GB | $3–6 |
| **Fly Managed Postgres** | Basic (Shared-2x/1 GB), incl. backups | **$38** + $0.28/GB storage |
| Redis | Upstash $10 fixed (or free) | $0–10 |
| TLS + bandwidth | | ~$0.10 |
| **Total** | | **~$41–54/mo** |

So: **Scenario 1 lands comfortably in the $5–25 ideal band (~$8–12/mo)**; **Scenario 2 exceeds the ~$40
ceiling** almost entirely because of MPG's $38 floor. Bandwidth is effectively free at this traffic (100 GB/mo
NA/EU free grant, then $0.02/GB —
[deployhandbook.com/pricing/fly-io](https://deployhandbook.com/pricing/fly-io)). The budget outcome hinges
entirely on the Postgres decision (§4).

---

## 10. Risks / limitations specific to THIS app

- **Scale-to-zero would kill the scheduler — CONFIG-CRITICAL (FIXABLE).** Fly's `auto_stop_machines` +
  `min_machines_running = 0` idles Machines with no traffic. If enabled on the backend, an idle period stops
  the Machine and **the in-process APScheduler stops ingesting**. Must set **`auto_stop_machines = "off"` and
  `min_machines_running = 1`** so the scheduler Machine is always on. This also means you pay for an always-on
  Machine (already in the §9 estimate) — you cannot use scale-to-zero to save money without breaking ingestion.
  ([fly.io/docs/reference/configuration](https://fly.io/docs/reference/configuration/))
- **Health-check model (FIXABLE).** fly-proxy health checks (`[[http_service.checks]]` / `[[services.tcp_checks]]`)
  gate rolling deploys and restart unhealthy Machines. In Shape A the check must hit **Caddy** (port 8080),
  which must in turn reach uvicorn — point it at a cheap `/healthz`. A too-aggressive check could restart the
  Machine mid-ingest; keep grace periods generous. Not a blocker, just needs a lightweight liveness endpoint.
- **Deploy = brief ingestion pause (benign).** Single-Machine deploys pass through zero instances (§3); the API
  is unreachable for a few seconds and ingestion skips a beat. Acceptable for hobby; note it's inherent, not
  tunable away without going multi-instance (which reintroduces the double-scheduler problem unless you split
  process groups per Shape B).
- **Python 3.14 (NOT a risk).** You own the Dockerfile, so `python:3.14-slim` (or a `uv`-based image matching
  the repo's toolchain) just works — no platform runtime pin.
- **Edge routing is in-app, not platform (see §2).** The reverse-proxy responsibility (prefix strip, SPA
  fallback, verbatim paths) is on you; a Caddyfile bug (e.g. `proxy_pass`-style trailing-slash rewriting in
  nginx) could silently violate PROXY-1. Caddy `handle_path` + `reverse_proxy` is the safe idiom.
- **Postgres durability/support downgrade if going unmanaged (see §4) — MISSING affordable managed option.**
  The budget path (unmanaged PG) means you own backups; snapshots are now billable and multi-copy. For public,
  re-derivable ESI data this is tolerable, but it is a real posture reduction and must be a conscious call.
- **No standing free tier (MISSING vs. reputation).** New accounts get only a time-limited trial; there is no
  ongoing free allowance to offset hobby cost
  ([fly.io/docs/about/free-trial](https://fly.io/docs/about/free-trial/)).
- **Long-running background job (NOT a risk).** Machines run arbitrary long-lived processes; APScheduler in a
  persistent uvicorn process is a normal Fly workload — no function-timeout or request-lifetime limit as on
  serverless platforms.

---

## Summary classification

| # | Requirement | Verdict |
|---|---|---|
| 1 | Topology mapping | FIXABLE (clean; edge is in-container) |
| 2 | Edge: prefix-strip / no-slash-rewrite / SPA fallback / same origin | FIXABLE — met only via bundled Caddy; **fly-proxy cannot path-route** |
| 3 | Single-scheduler safety | FIXABLE / strength — count=1 rolling passes through zero, never two |
| 4 | Postgres managed + backups + budget | MISSING affordable managed (MPG floor ~$38); FIXABLE via unmanaged node |
| 5 | Redis/Valkey cache | FIXABLE / low-risk — Upstash free/PAYG or self-run sidecar |
| 6 | Secrets without CLI exposure | FIXABLE / satisfied — `fly secrets import` from stdin |
| 7 | TLS + custom domain | FIXABLE / satisfied — free ACME, $0.10/mo/hostname |
| 8 | GitHub Actions CD | FIXABLE / satisfied — official action + app-scoped deploy token |
| 9 | Total cost | ~$8–12/mo (unmanaged PG) or ~$41–54/mo (MPG) — budget hinges on §4 |
| 10 | App-specific risks | Scale-to-zero-kills-scheduler is the one CONFIG-CRITICAL item; all FIXABLE |

No BROKEN items. Two MISSING items (affordable managed Postgres; standing free tier). Everything else is
FIXABLE with standard config. The single decisive variable for hitting the hobby budget is the Postgres choice
(managed-and-over-budget vs. unmanaged-and-self-owned).
