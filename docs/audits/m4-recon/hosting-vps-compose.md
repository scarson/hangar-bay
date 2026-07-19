# M4 Recon — Hosting Candidate: Single VPS + Docker Compose + Caddy

ABOUTME: Read-only hosting-candidate recon for Hangar Bay M4 production readiness — one VPS (Hetzner/DigitalOcean) running Docker Compose with Caddy edge, self-run Postgres + Valkey containers, deployed via GitHub Actions over SSH.
ABOUTME: Facts + classifications (BROKEN/MISSING/FIXABLE) only, symmetric template, no recommendation and no cross-candidate comparison. No code was modified.

Scope: evaluate ONE candidate stack against Hangar Bay's deployment shape. All pricing/capability
facts are as of **2026-07-18** with cited URLs. Candidate = **a single VPS** (Hetzner CX/CAX line or
DigitalOcean droplet) running **Docker Compose**, with **Caddy** as the TLS edge/reverse proxy,
**PostgreSQL** and **Valkey** as sibling containers, and **CD from GitHub Actions over SSH**. The app
shape being mapped:

- FastAPI backend (Python 3.14, uvicorn) with an **in-process APScheduler** ingesting EVE ESI data
  every few minutes; first ingest runs multi-minute. **Exactly one** backend instance may run the
  scheduler — a deploy that briefly runs two instances risks duplicate ingestion.
- PostgreSQL (durable + backups) and Valkey/Redis (pure cache, loss-tolerable).
- Static React SPA (Vite) served from the **same registrable origin** as the API; edge must strip the
  `/api/v1` prefix before FastAPI, preserve other paths verbatim (no trailing-slash rewriting), SPA
  fallback to `index.html`, and host the EVE SSO OAuth callback on a backend route on that same
  origin. Session cookies are Secure+HttpOnly → HTTPS + real domain required.
- Secrets: `ESI_CLIENT_ID`/`ESI_CLIENT_SECRET`, `TOKEN_CIPHER_KEYS`, `DATABASE_URL`, `CACHE_URL` —
  provisioning must avoid secrets in CLI flags/args (visible in `ps`/shell history).
- CD from GitHub Actions (repo already has CI); needs a deploy token usable from a workflow.

---

## Headline structural finding

**This candidate is a persistent, self-managed Linux VM — the app maps onto it almost verbatim,
because it is essentially the same shape as the project's existing `docker/compose.yml` dev stack.**
There is no serverless/PaaS impedance mismatch: a long-lived container runs 24/7, the in-process
APScheduler is never frozen or evicted, Python 3.14 is whatever base image you choose, and the edge
routing is a hand-written Caddyfile that does exactly what you tell it. Every "does the platform
support X" question that trips up serverless candidates answers trivially **yes** here, because you
own the whole box.

The cost is inverted: nothing is managed **for** you. Postgres durability, backups, OS patching,
firewalling, uptime monitoring, and single-host failure are all **your** responsibility. The dollar
cost is the lowest of any realistic option (~$6–10/mo all-in); the *operational* cost is the highest.
Classify the whole candidate as **FIXABLE with sysadmin effort** — nothing is BROKEN, several things
are MISSING-by-default and must be built.

---

## 1. Topology

Single VM, one `compose.yml`, four (or five) services on a private compose network. Only Caddy binds
public ports (80/443); everything else is internal.

```yaml
# compose.prod.yml (illustrative)
services:
  caddy:
    image: caddy:2-alpine
    ports: ["80:80", "443:443"]
    volumes:
      - ./Caddyfile:/etc/caddy/Caddyfile:ro
      - ./web-dist:/srv/www:ro        # Vite build output (SPA)
      - caddy_data:/data              # ACME certs (persist!)
      - caddy_config:/config
    depends_on: [backend]
    restart: unless-stopped

  backend:
    image: ghcr.io/scarson/hangar-bay-backend:${SHA}
    env_file: [/opt/hangar-bay/backend.env]   # secrets, root-owned 600
    depends_on:
      postgres: {condition: service_healthy}
      valkey:   {condition: service_started}
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request;urllib.request.urlopen('http://localhost:8000/health')"]
      interval: 30s
      timeout: 5s
      retries: 3

  postgres:
    image: postgres:17
    env_file: [/opt/hangar-bay/postgres.env]
    volumes: [pgdata:/var/lib/postgresql/data]
    restart: unless-stopped
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U hangar"]
      interval: 10s
      retries: 5

  valkey:
    image: valkey/valkey:8-alpine
    command: ["valkey-server", "--save", "", "--appendonly", "no"]  # cache-only, no persistence
    restart: unless-stopped

volumes: { pgdata: {}, caddy_data: {}, caddy_config: {} }
```

- **SPA**: Vite `dist/` is built in CI and shipped to the host (rsync/scp, or baked into a tiny image);
  Caddy `file_server` serves it. No Node runtime on the box.
- **Backend**: one `python:3.14-slim`-based image, uvicorn, APScheduler in-process. Bound only on the
  compose network (`backend:8000`), never published to the host.
- **Postgres/Valkey**: official images. Postgres data on a named volume on the VM's own NVMe; Valkey
  configured with persistence **off** (loss-tolerable cache).
- **Edge**: Caddy terminates TLS and does all routing (see §2). Choosing Caddy over nginx/Traefik is
  deliberate: automatic HTTPS with zero cert plumbing.

Config files that live in git and ship to the host: `compose.prod.yml`, `Caddyfile`. Secrets live in
root-owned `*.env` files on the host, never in git (see §6).

**Sizing.** All four containers at hobby traffic fit comfortably in **2 vCPU / 4 GB**: Postgres idle
~150–250 MB, Valkey tens of MB, uvicorn + Python ~150–300 MB, Caddy ~20 MB. 40 GB NVMe is ample for a
contracts DB. Classification: **FIXABLE / native fit** — this is the same stack the repo already runs
in `app/backend/docker/`.

---

## 2. Edge requirements — can they be met exactly?

**Yes, all four, exactly.** Caddy is a hand-written config, so there is no platform-imposed rewriting
to fight. Minimal Caddyfile:

```caddyfile
hangar-bay.example.com {
    encode zstd gzip

    # /api/v1/* → backend WITH the /api/v1 prefix stripped, path otherwise verbatim
    handle_path /api/v1/* {
        reverse_proxy backend:8000
    }

    # everything else → SPA with fallback to index.html
    handle {
        root * /srv/www
        try_files {path} /index.html
        file_server
    }
}
```

- **Prefix strip (PROXY-1).** `handle_path /api/v1/*` matches the prefix **and removes it** before the
  request reaches `reverse_proxy`, so `/api/v1/contracts` arrives at FastAPI as `/contracts` — exactly
  what the bare-mounted routers expect. (`handle_path` = `handle` + `uri strip_prefix`.) Source:
  Caddy `handle_path` docs. https://caddyserver.com/docs/caddyfile/directives/handle_path
- **No trailing-slash meddling.** Caddy's `reverse_proxy` forwards the request URI **verbatim**; it
  performs no canonicalization or slash redirects on proxied paths. (The only Caddy component that
  emits a trailing-slash 301 is `file_server` for real directories — that is on the SPA branch, not the
  API branch, and the SPA branch resolves through `try_files … /index.html` anyway.) Source:
  Caddy `reverse_proxy` docs. https://caddyserver.com/docs/caddyfile/directives/reverse_proxy
  Note: FastAPI's own `redirect_slashes` still applies **inside** the app — that is a backend config,
  not an edge behavior, so the edge requirement ("edge must not rewrite") is satisfied.
- **SPA fallback.** `try_files {path} /index.html` serves the built asset if it exists, else returns
  `index.html` so the TanStack Router client route resolves. Standard SPA pattern. Source: Caddy
  `try_files` docs. https://caddyserver.com/docs/caddyfile/directives/try_files
- **Same registrable origin.** SPA and API are both served by the same Caddy site block on
  `hangar-bay.example.com` → same-origin by construction. The EVE SSO callback (e.g.
  `/api/v1/auth/callback`) is just another `/api/v1/*` path routed to the backend. Secure+HttpOnly
  host-scoped cookies work because the whole thing is one HTTPS origin.

Classification: **FIXABLE / native fit** — the edge contract is met precisely with ~12 lines of config.

---

## 3. Single-scheduler safety

This is the candidate's **strongest** point, and it is essentially free.

- **Docker Compose's default deploy is replace-in-place, not rolling.** `docker compose up -d` on a
  changed image **stops the old container, then starts the new one** — there is never a moment with two
  `backend` containers running. This gives the required guarantee natively: **at most one instance,
  briefly zero**, during a deploy. Source: Docker Compose `up` recreates changed services (stop→start,
  no overlap by default). https://docs.docker.com/reference/cli/docker/compose/up/
- **Rolling / zero-overlap-downtime is opt-in, not default.** Compose *can* do `--wait` with a rolling
  update only under `deploy.update_config` in Swarm mode; plain `compose up` does not. So the dangerous
  "two instances briefly" scenario **only happens if you deliberately configure it** — the safe default
  is the one you want. https://docs.docker.com/reference/compose-file/deploy/
- **The trade-off is a few seconds of downtime** on each backend deploy (old stops, new boots, first
  ingest kicks off). For a hobby marketplace this is a blip; the SPA and Caddy stay up, only in-flight
  API calls during the ~2–10 s restart get a 502.
- **If zero-downtime is ever wanted**, the correct pattern is to **split the scheduler out of the web
  process**: run the ingestion as its own single-replica `scheduler` service (replace-strategy, brief
  gap OK — a skipped tick self-heals next interval) and roll the stateless `web` service behind Caddy
  independently. YAGNI at hobby scale, but the option stays open at low cost. This also happens to be
  the clean way to scale the API horizontally later without ever duplicating the scheduler.
- **Defense in depth (optional):** APScheduler with `max_instances=1` + `coalesce=True`, or a Postgres
  advisory lock around the ingest job, makes duplicate ingestion impossible even if two schedulers ever
  co-existed. Cheap insurance, not required by this topology.

Classification: **FIXABLE / native fit — arguably a STRENGTH.** The default compose deploy already
satisfies "max one, briefly zero." No leader election, no platform min/max-instance knobs needed.

---

## 4. PostgreSQL — storage, backups, cost

- **Offering:** self-run `postgres:17` container. No managed control plane — you get exactly the
  Postgres you configure.
- **Durable storage:** a named Docker volume (or bind mount) on the VM's own NVMe. Data persists across
  container recreates and reboots. It does **not** persist across a VM disk failure or an accidental
  volume delete → backups are non-negotiable.
- **Automated backups are MISSING by default — this is the single biggest gap of the candidate.** There
  is no managed PITR, no automated daily snapshot. You must build it:
  - **Logical:** a `pg_dump` cron (or a sidecar like `prodrigestivill/postgres-backup-local`) writing
    compressed dumps, pushed **off-box** to object storage — Backblaze B2, Hetzner Storage Box, or S3.
    Off-box is the point: a dump sitting on the same failed disk is worthless.
  - **Physical/whole-disk:** Hetzner "server backups" (automatic, 7 retained) at **20 % of the server
    price** — for a €5.49 server that is ~€1.10/mo — or DO backups at 20 %/wk or 30 %/day of droplet
    cost. Whole-disk snapshots of a *running* Postgres are crash-consistent-at-best; prefer `pg_dump`
    for restore confidence and combine with disk backups for bare-metal recovery.
- **Cost:** the Postgres container itself is **$0** (rides the VM). Off-box dump storage for a few GB of
  compressed dumps is **<$1/mo** (Backblaze B2 is ~$6/TB-mo). Hetzner/DO whole-disk backups add ~20 %
  of the VM price (~€1.10/mo).
- Sources: Hetzner backup = 20 % of server price, up to 7 backups
  (https://docs.hetzner.com/cloud/servers/getting-started/enabling-backups/);
  DO backups 20 %/wk or 30 %/day and snapshots $0.06/GB-mo
  (https://www.digitalocean.com/pricing/droplets, accessed 2026-07-18).

Classification: **MISSING → FIXABLE.** Durability is solid; *automated, offsite, tested* backups are
DIY and must be an explicit M4 deliverable (dump cron + offsite target + a documented restore drill).

---

## 5. Valkey / Redis — managed or sidecar, cost

- **Sidecar container**, `valkey/valkey:8-alpine`, on the compose network. Since the cache is
  loss-tolerable, run it with **persistence disabled** (`--save "" --appendonly no`) — a restart simply
  cold-starts the cache, which the app tolerates (ETag/page cache repopulates on next ingest tick).
- **Cost: $0** — it rides the VM. Tens of MB of RAM at hobby scale.
- No managed offering is involved or needed. (DigitalOcean *does* sell Managed Valkey from **$15/mo**
  single-node if one ever wanted to offload it, but that quadruples the whole hosting bill for a
  cache the app is explicitly happy to lose. https://docs.digitalocean.com/products/databases/valkey/details/pricing/,
  accessed 2026-07-18.)

Classification: **FIXABLE / native fit** — trivial, and free.

---

## 6. Secrets provisioning — avoiding CLI-arg exposure

The requirement is that secrets never appear in CLI flags/args (visible in `ps`/shell history). The
compose model satisfies this cleanly **if** you use file-based provisioning, not inline env:

- **Recommended: root-owned `env_file` on the host.** Store `ESI_CLIENT_ID/SECRET`,
  `TOKEN_CIPHER_KEYS`, `DATABASE_URL`, `CACHE_URL` in `/opt/hangar-bay/backend.env` (`chmod 600`, owned
  by root/deploy user). Compose loads it via `env_file:`; the values become container env, **never**
  compose CLI arguments. Nothing sensitive is in `ps` output or shell history.
- **Writing the file from CI without leaking it:** GitHub Actions holds the secrets; the deploy job
  writes them to the host over SSH via **stdin/scp**, not as command arguments. Safe patterns:
  - `appleboy/scp-action` to copy a rendered `.env` (the file is created in the runner from
    `${{ secrets.* }}`, then transferred). https://github.com/appleboy/scp-action
  - or pipe over SSH stdin: `ssh host 'cat > /opt/hangar-bay/backend.env' < rendered.env` — the secret
    travels through stdin, not argv.
  - Avoid `ssh host "echo $SECRET > file"` and `docker run -e FOO=$SECRET …` style — those **do** put
    the value in argv/history. This is a discipline requirement, not a platform limitation.
- **Docker's own file-secret mechanism** (`secrets:` in compose, mounted at `/run/secrets/<name>`) is
  available and is even cleaner (secrets are files, never env); Swarm's `docker secret create` reads
  from **stdin/file** by design. Either is compatible with "no secrets in argv."
- **Caution to document:** compose interpolates `${VAR}` from the shell environment of whoever runs
  `docker compose`; if the deploy step exports secrets into that shell, they can briefly appear in the
  remote process environment. Keeping secrets in `env_file`/`secrets:` (consumed by the *container*,
  not by the compose CLI) avoids this.

Classification: **FIXABLE / native fit** — the platform imposes nothing; correct file/stdin discipline
fully meets the no-argv-exposure requirement.

---

## 7. TLS + custom domain

- **Automatic HTTPS out of the box.** Caddy provisions and auto-renews Let's Encrypt/ZeroSSL certs for
  any domain named in the Caddyfile — no certbot, no cron, no manual renewal. Just point DNS
  A/AAAA at the VM's IP and Caddy handles the ACME challenge on first request.
  Source: Caddy automatic HTTPS. https://caddyserver.com/docs/automatic-https
- **Custom domain:** you bring a real domain (registrar of choice, ~$10–15/yr). Required anyway for the
  Secure+HttpOnly host-scoped session cookies and the EVE SSO callback URL.
- **Cert persistence caveat:** Caddy's `/data` volume **must** be persisted (it holds the ACME account
  + certs); otherwise every redeploy re-requests certs and can hit Let's Encrypt rate limits. Shown in
  the §1 compose (`caddy_data`). One-line gotcha, easy to miss.

Classification: **FIXABLE / native fit — a STRENGTH.** TLS + real domain is the easiest part of this
candidate.

---

## 8. GitHub Actions CD

No platform-specific deploy token exists (there is no PaaS control plane) — CD is **SSH-key based**:

- **Mechanism:** CI builds the backend image, pushes to **GHCR** (`ghcr.io`, auth via the built-in
  `GITHUB_TOKEN` with `packages: write`), then SSHes to the host to `docker compose pull && docker
  compose up -d`. SPA `dist/` is rsync'd/scp'd to the host in the same job. Standard 2026 pattern using
  `appleboy/ssh-action` (+ `scp-action`). https://github.com/appleboy/ssh-action
- **Token/credential scoping:**
  - **Deploy SSH key:** a dedicated Ed25519 keypair; private key in GH Actions secrets, public key in
    the host `deploy` user's `authorized_keys`. Lock it down with `authorized_keys` restrictions or a
    forced command if you want least privilege.
  - **GHCR pull on the host:** either make the image package **public** (no host credential needed) or
    give the host a **read-only** GHCR PAT. The push side uses the workflow's `GITHUB_TOKEN`, scoped to
    the repo.
  - **Deploy user = docker group ≈ root.** Membership in the `docker` group is root-equivalent
    (`docker run -v /:/host …` escapes trivially). Treat the deploy key as a root credential, restrict
    its source (GH Actions IP ranges are wide, so rely on key secrecy + optional forced command), and
    keep it out of any low-trust context.
- **Migrations in the deploy:** run `alembic upgrade head` as a one-shot (`docker compose run --rm
  backend alembic upgrade head`) **before** `up -d` on the backend, so the new schema is in place when
  the new container starts. Ordering is on you (no managed release-phase hook).

Classification: **FIXABLE / native fit.** No official platform action, but the SSH+GHCR pattern is
well-trodden; the only real hazard is that the deploy key is effectively root.

---

## 9. Total monthly cost estimate (hobby scale, mid-2026)

Everything except the VM, the domain, and a few GB of offsite dump storage is **$0** (self-run
containers). Itemized, two representative VM choices:

**Option A — Hetzner (cheapest realistic):**

| Item | Plan / detail | Monthly |
|---|---|---|
| VM | **CX23** 2 vCPU / 4 GB / 40 GB NVMe / 20 TB traffic | **€5.49** |
| Primary IPv4 | required for a public server | €0.50 |
| Whole-disk backup (optional) | 20 % of server price, 7 retained | ~€1.10 |
| Offsite pg_dump storage | Backblaze B2, few GB | <$1 (~€0.50) |
| Domain | amortized (~$12/yr) | ~$1 (~€0.90) |
| TLS | Caddy / Let's Encrypt | €0 |
| **Total** | | **≈ €6.5–8.5/mo (~$7–9)** |

ARM alternative: **CAX11** (2 vCPU Ampere / 4 GB) at **€5.99/mo** — same ballpark; Python 3.14 has
`manylinux` aarch64 wheels and official arm64 base images, so it works, just build a multi-arch or
arm64 image. https://docs.hetzner.com/general/infrastructure-and-availability/price-adjustment/

**Option B — DigitalOcean (simpler dashboard, US-default):**

| Item | Plan / detail | Monthly |
|---|---|---|
| Droplet | **Basic 2 GB / 1 vCPU / 50 GB / 2 TB** | **$12.00** |
| (or) Droplet | Basic 4 GB / 2 vCPU / 80 GB / 4 TB | $24.00 |
| Backups | 20 %/wk (or 30 %/day) of droplet | ~$2.40 |
| Offsite dump storage | Backblaze B2 / DO Spaces | <$1 |
| Domain | amortized | ~$1 |
| **Total (2 GB tier)** | | **≈ $15/mo** |

Both land **well under the ~$40 ceiling** and inside the **$5–25 sweet spot** — Hetzner at the very
bottom (~$7–9), DO mid-range (~$15). A 512 MB/1 GB droplet is too tight to run Postgres + Valkey +
uvicorn + Caddy together; 2–4 GB is the practical floor.

Sources (accessed 2026-07-18): Hetzner June-2026 price list
(https://docs.hetzner.com/general/infrastructure-and-availability/price-adjustment/,
https://www.hetzner.com/cloud/); DigitalOcean droplet pricing
(https://www.digitalocean.com/pricing/droplets); Backblaze B2 ~$6/TB-mo (https://www.backblaze.com/cloud-storage/pricing).

---

## 10. Risks / limitations specific to THIS app

- **Python 3.14 — non-issue (STRENGTH).** You choose the base image (`python:3.14-slim`); there is no
  platform-imposed runtime version. This candidate is immune to the "does the platform support 3.14
  yet" question that constrains PaaS/serverless options. Classification: **not a risk.**
- **Long-running in-process APScheduler — non-issue (STRENGTH).** A container runs continuously; there
  is no request-driven lifecycle, no function freeze, no idle eviction. The scheduler thread lives for
  the life of the container. Classification: **not a risk.**
- **No idle shutdown / no scale-to-zero — non-issue (STRENGTH).** The VM (and the container with
  `restart: unless-stopped`) runs 24/7 by default. Nothing on the platform will silently pause the
  process and kill the scheduler. This is the exact failure mode that hurts serverless/scale-to-zero
  candidates and it **does not exist here.** Classification: **not a risk.**
- **Single point of failure (LIMITATION, inherent).** One VM = no HA. A host hardware failure, a noisy
  neighbor, a bad kernel reboot, or an OOM cascade takes the whole app down. Postgres data lives on
  that one disk; a disk/volume loss without off-box backups = permanent data loss. Hobby-acceptable,
  but real. Mitigation is backups (§4) + monitoring, not redundancy.
- **Automated backups are DIY (MISSING → FIXABLE).** See §4 — must be built and, crucially, a restore
  must be **tested**. Untested backups are the classic hobby-VPS regret.
- **Uptime monitoring / health gating is DIY (MISSING → FIXABLE).** Docker `healthcheck` +
  `restart: unless-stopped` gives local self-heal (container restarts on crash), but there is **no
  platform health gate** on deploys and **no external uptime alerting**. Add a free external monitor
  (UptimeRobot/Better Stack) hitting `/health`; otherwise a wedged box is invisible until a user
  notices. A bad deploy that boots but is unhealthy will **not** be auto-rolled-back — you own that.
- **OS/patching/hardening burden (LIMITATION, inherent).** SSH hardening (key-only, no root login),
  `ufw`/Hetzner Cloud Firewall (expose only 22/80/443), `fail2ban`, and unattended security upgrades
  are all on you. This is the dominant *time* cost of the candidate; budget for it.
- **Deploy key ≈ root (SECURITY, FIXABLE).** The `docker` group is root-equivalent (§8). The GH-Actions
  deploy key is therefore a root credential to the box; guard it accordingly (key secrecy, optional
  forced command, scoped `authorized_keys`).
- **Brief deploy downtime (LIMITATION, accepted).** The single-instance-safe replace strategy (§3)
  costs a few seconds of API 502s per backend deploy. Trivial for a hobby marketplace; note it so it is
  not mistaken for an outage. Zero-downtime is possible only by splitting the scheduler out and
  rolling the web tier — extra complexity, deliberately deferred.
- **Hetzner pricing volatility (RISK, recent change — flag).** Hetzner raised cloud prices **three
  times in 2026**; the **15 June 2026** adjustment hit the performance **CPX** line especially hard
  (e.g. CPX22 €7.99 → **€19.49**, +144 %; CPX32 €13.99 → €35.49, +154 %), while the **cost-optimized CX
  and ARM CAX lines** stayed cheap (CX23 → €5.49, CAX11 → €5.99). **Use CX/CAX, not CPX**, for this
  budget — the CPX line is no longer a hobby-budget option. Provider-price risk is a live 2026 factor.
  https://docs.hetzner.com/general/infrastructure-and-availability/price-adjustment/,
  https://wz-it.com/en/blog/hetzner-price-increase-june-2026-cpx-ccx-alternatives/ (accessed 2026-07-18).
- **Region/egress (non-issue).** EVE ESI is a public HTTPS API; both Hetzner (EU/US/SG) and DO regions
  reach it fine, and included traffic (20 TB Hetzner / 2–4 TB DO) dwarfs hobby usage. **Not a risk.**

---

## Summary of classifications

| Area | Finding | Class |
|---|---|---|
| Topology / fit | Same shape as existing dev compose stack; maps verbatim | FIXABLE / native |
| Edge (prefix strip, no slash meddling, SPA fallback, same origin) | Met exactly with ~12-line Caddyfile | FIXABLE / native |
| Single-scheduler safety | Compose default replace = max one, briefly zero — free guarantee | FIXABLE / STRENGTH |
| Postgres durability | Named volume on VM NVMe, persists reboots | FIXABLE / native |
| Postgres automated offsite backups | None by default; must build pg_dump cron + offsite + restore test | MISSING → FIXABLE |
| Valkey cache | Sidecar container, persistence off, $0 | FIXABLE / native |
| Secrets (no argv exposure) | `env_file`/`secrets:` + stdin/scp provisioning satisfies it | FIXABLE / native |
| TLS + domain | Caddy automatic HTTPS; persist `caddy_data` | FIXABLE / STRENGTH |
| GitHub Actions CD | SSH + GHCR; deploy key ≈ root | FIXABLE / native |
| Python 3.14 / long jobs / no scale-to-zero | You own the runtime; scheduler never evicted | STRENGTH (not a risk) |
| Single host = no HA | Inherent; mitigate with backups + monitoring, not redundancy | LIMITATION |
| Uptime monitoring / health gating | DIY; no platform rollback on unhealthy deploy | MISSING → FIXABLE |
| OS patching / hardening | Full sysadmin burden | LIMITATION (time cost) |
| Hetzner 2026 price volatility | 3 hikes in 2026; use CX/CAX not CPX | RISK (recent change) |
| Total cost | ~$7–9/mo Hetzner, ~$15/mo DO — under budget | — |

**Nothing is BROKEN.** The candidate fits the app's shape more directly than any managed alternative;
its cost is dollars-cheap but sysadmin-expensive, and its two genuine gaps — **automated offsite
backups** and **external uptime monitoring** — are MISSING-by-default and must be explicit M4
deliverables, not assumed.
