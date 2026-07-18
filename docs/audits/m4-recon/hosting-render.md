# M4 Recon — Hosting Candidate: Render

ABOUTME: Read-only evaluation of Render (web service + static site + managed Postgres + Key Value) as a host for Hangar Bay at hobby scale.
ABOUTME: Facts + classified findings only — no cross-platform comparison, no overall recommendation. Pricing and capabilities current as of access date 2026-07-18.

Scope: one candidate, evaluated on its own merits against the M4 deploy requirements
(single-scheduler safety, same-origin edge routing with prefix strip, managed Postgres +
Valkey, CLI-safe secrets, GitHub Actions CD, hobby-scale budget). Each material finding is
tagged **BROKEN** / **MISSING** / **FIXABLE** / **OK**. All prices are USD/month unless noted.
Sources are cited inline with URLs; all accessed **2026-07-18**.

> Note on pricing precision: Render's public `/pricing` page renders its tables client-side, so
> the exact figures below are drawn from Render's own docs (pricing model, storage rates, PITR)
> plus third-party pricing aggregators for the per-plan compute numbers. Where a number comes
> only from an aggregator it is flagged as such. Render ran a **Postgres "flexible plans" refresh**
> that decoupled compute from storage — that change is reflected below.

---

## 0. TL;DR findings

- **Single-scheduler safety is cleanly solvable** on Render, and the mechanism is documented, not a hack around the platform: **attaching a persistent disk to the backend web service (a) caps it at max 1 instance and (b) disables zero-downtime deploys**, so Render *stops the old instance before starting the new one* — the deploy passes through **briefly zero** instances and **never two**. This is exactly the guarantee the in-process APScheduler ingester needs. **FIXABLE/OK.**
- **Python 3.14 is a first-class default** — Render bumped its default to **Python 3.14.3** in Feb 2026. **OK.** (But PDM is not a natively-detected package manager — **MISSING**, workaround below.)
- **Same-origin edge routing is achievable** via a Render **Static Site** with rewrite rules that proxy `/api/v1/*` to the backend service (full-URL rewrite, placeholder-based prefix strip) and fall back `/*` → `/index.html`. One caveat to verify empirically: cross-service full-URL rewrite behavior for non-GET methods (the OAuth callback) and trailing-slash handling.
- **Cost fits the budget comfortably: ~$13–24/mo** on the free Hobby workspace, well under the $40 ceiling and inside the $5–25 target.
- **The free tiers are traps for this app**: free web services **spin down after 15 min idle** (kills the scheduler), and free Postgres is **deleted after 30 days** with no backups. Production must use paid instances. **BROKEN if free tiers used; FIXABLE by paying.**

---

## 1. Topology mapping

FastAPI + Postgres + Valkey + static SPA + edge routing maps onto Render as **four resources**,
all definable in one `render.yaml` Blueprint (Render's IaC model — [infrastructure-as-code docs](https://render.com/docs/infrastructure-as-code)):

| Concern | Render resource | Notes |
|---|---|---|
| FastAPI + APScheduler | **Web Service** (native Python runtime or Docker) | Starter instance, **+ a small persistent disk** to force single-instance/recreate deploys (see §3). |
| PostgreSQL | **Render Postgres** (managed) | Paid Basic instance for durability + backups. |
| Valkey cache | **Render Key Value** (managed **Valkey 8**) | Render replaced Redis with Valkey natively — see [changelog: Key Value now runs Valkey 8](https://render.com/changelog/new-render-key-value-instances-run-valkey-8). |
| React SPA (Vite output) | **Static Site** (free) | Also owns the **edge routing** via rewrite rules (§2). |
| Edge / same-origin routing | Rewrite rules **on the Static Site** | Static sites are the only Render resource with a rewrite engine; web services have none. |

**Recommended shape:** the **Static Site holds the custom domain** and is the public origin; its
rewrite rules proxy the API subtree to the backend web service's `onrender.com` URL. This is the
standard Render pattern for same-origin SPA + API and is what makes the OAuth-callback-same-origin
requirement work (§2). Private networking (internal URLs) connects the web service to Postgres and
Key Value within the same region — [Key Value docs recommend the internal URL](https://render.com/docs/key-value).

A rejected alternative — a **single web service that serves both the built SPA and the API** — would
trivially satisfy same-origin but **cannot meet "strip `/api/v1` before FastAPI sees it" at the edge**,
because web services have no rewrite layer; you'd have to do prefix handling inside FastAPI, which the
project's PROXY-1 pitfall explicitly keeps out of the app. So Topology A (static site + separate
backend) is the fit. **OK.**

Source: [Render Blueprints (IaC)](https://render.com/docs/infrastructure-as-code); [Blueprint YAML reference](https://render.com/docs/blueprint-spec) (accessed 2026-07-18).

---

## 2. Edge requirements — can they be met exactly?

Render Static Site rewrite rules have three fields — **Source**, **Destination**, **Action** (Redirect
or Rewrite) — and **Destination may be a path OR a full, publicly-accessible URL**; placeholders carry
path components from Source into Destination. A **rewrite** (vs redirect) "serves the content from the
rule's destination at the original path" — i.e. a **server-side proxy**, URL unchanged in the browser.
Source: [Static Site Redirects and Rewrites](https://render.com/docs/redirects-rewrites) (accessed 2026-07-18).

Mapping each requirement:

- **Serve SPA with fallback-to-index.html** — rewrite `Source /*` → `Destination /index.html`, Action
  Rewrite (200, not redirect). Render also "does not apply redirect or rewrite rules to a path if a
  resource exists at that path," so real static assets are served directly and only unknown routes hit
  the fallback. **OK.**
- **Route `/api/v1/*` to the backend WITH `/api/v1` stripped** — rewrite `Source /api/v1/*` →
  `Destination https://<backend>.onrender.com/*` (placeholder carries the tail). This strips the
  `/api/v1` prefix before the request reaches FastAPI, satisfying **PROXY-1**. The `/api/v1` rule must
  be ordered **before** the `/*` SPA fallback (rules evaluate top-down). **FIXABLE/OK** (achievable, but
  requires correct rule ordering).
- **Same registrable origin** — put the custom domain on the **Static Site**; the full-URL rewrite makes
  the browser see only `yourdomain.com`, and the API responses come back at `yourdomain.com/api/v1/...`.
  The **OAuth (EVE SSO) callback** therefore lands on the same origin, so `Secure`+`HttpOnly` session
  cookies are first-party. **OK** (subject to the verify item below).
- **Preserve paths verbatim / no trailing-slash meddling** — the docs describe path-preserving rewrites
  and **do not document any automatic trailing-slash insertion** on rewrites. **MISSING explicit
  confirmation** — flag to **verify empirically** that a request to `/api/v1/contracts` is proxied as
  `/contracts` (not `/contracts/`) and that Render does not 301-normalize trailing slashes on the static
  site. This is the one edge behavior I could not positively confirm from docs.

**One material item to verify before committing:** full-URL cross-service rewrites proxying **non-GET
methods with bodies** (the OAuth token exchange / any POST). The docs frame rewrites around serving
content and don't spell out method/body pass-through for external-URL destinations. Classify as
**FIXABLE-pending-verification** — the pattern is widely used, but prove it with a POST before relying on it.

---

## 3. Single-scheduler safety (the load-bearing requirement)

**Default behavior is the wrong one for us:** Render web services do **zero-downtime rolling deploys by
default** — a new instance is built and made healthy **while the old instance keeps serving**, then
traffic swaps and the old instance gets `SIGTERM` after ~60s. During that window **two instances run
simultaneously** → **two in-process APScheduler loops** → duplicate ESI ingestion. **BROKEN if left at
defaults.** Source: [Deploying on Render](https://render.com/docs/deploys) (accessed 2026-07-18).

**The fix is documented and clean — attach a persistent disk:**
> "Adding a persistent disk to your service disables zero-downtime deploys for it." When you redeploy,
> "Render stops the existing instance before bringing up the new instance" — a necessary safeguard
> against two app versions writing the same disk.

And, independently: **a service with a persistent disk cannot scale past one instance** (max instance
count is effectively pinned to 1 regardless of plan). Sources: [Persistent Disks](https://render.com/docs/disks),
[Scaling Render Services](https://render.com/docs/scaling) (accessed 2026-07-18).

Combining the two properties gives exactly the required guarantee:

- **Max one instance, always** (disk caps scaling at 1; also set autoscaling off / count = 1 as belt-and-suspenders).
- **Deploys are stop-old-then-start-new**, so the transition is **briefly zero** schedulers, **never two**.
- The scheduler runs continuously on a **paid** instance (paid services do **not** scale to zero — §10).

**Tradeoff:** the recreate deploy costs a few seconds of API downtime per deploy. At hobby scale, and
with idempotent-ish every-few-minutes ingestion tolerating a brief zero-scheduler gap, this is
acceptable. The disk itself is otherwise unused by the app (Postgres holds state) — it exists purely to
flip the deploy strategy — so provision the **minimum 1 GB**. **FIXABLE/OK — this is the strongest part
of the Render fit.**

(Render also has a manual **maintenance mode**, but the disk mechanism is automatic and doesn't require
a human in the deploy loop, so it's the right lever here.)

---

## 4. PostgreSQL — managed offering, storage, backups, cost

- **Managed:** yes, first-party [Render Postgres](https://render.com/docs/postgresql). Render ran a
  **flexible-plans refresh** decoupling compute from storage — [postgresql-refresh docs](https://render.com/docs/postgresql-refresh).
- **Storage:** billed at **$0.30 / GB / month**, prorated to the second, independent of compute.
- **Cheapest paid compute:** the **Basic** tier (compute/pricing comparable to the legacy Starter/Standard
  tiers) — roughly **$6–7/mo for a ~256 MB-RAM instance** per aggregator data
  ([kuberns Render pricing](https://kuberns.com/blogs/render-pricing/)), plus storage at $0.30/GB. For
  hobby-scale contract data this lands around **$7–8/mo all-in**.
- **Automated backups:** **All paid databases get point-in-time recovery (PITR) automatically.** Retention
  is **workspace-plan-gated: 3 days on the free Hobby workspace, 7 days on Pro** ($19/user/mo). Plus
  **logical exports** (downloadable compressed dumps) retained **7 days** regardless of workspace tier.
  Sources: [postgresql-refresh](https://render.com/docs/postgresql-refresh), [managed Postgres pricing summary](https://kuberns.com/blogs/render-postgres-pricing-setup-limits/).
- **Free tier is unusable for production:** Free Postgres is fixed at 1 GB, has **no backups / no PITR**,
  and is **deleted after 30 days with no grace period**. **BROKEN for production; FIXABLE by using a paid Basic instance.**

**Net: OK** on a paid Basic instance; durable storage + automatic PITR (3-day on Hobby) + 7-day logical
exports satisfy the "durable storage, backups" requirement at ~$7–8/mo.

---

## 5. Valkey / Redis — managed vs sidecar, cost

- **Managed, and natively Valkey:** [Render Key Value](https://render.com/docs/key-value) instances run
  **Valkey 8** (Render migrated off Redis) — [changelog](https://render.com/changelog/new-render-key-value-instances-run-valkey-8),
  [Valkey FAQ](https://render.com/docs/valkey-faq). No self-run sidecar needed.
- **Persistence modes:** paid instances support disk-backed persistence (Journal+Snapshot / Snapshot /
  Off). Since Hangar Bay uses Valkey as a **pure, loss-tolerable cache**, persistence can be **Off** (the
  doc's recommended mode for caching) — meaning even the cheapest option is fine.
- **Free tier:** **25 MB, 50 connections, no persistence** — adequate as an ephemeral cache for a
  low-traffic app, but 25 MB is tight and free instances carry limits. **OK for pure cache, with headroom risk.**
- **Cheapest paid:** **Starter ≈ $10/mo for 256 MB**; Standard ≈ $32/mo for 1 GB (aggregator figures,
  [kuberns](https://kuberns.com/blogs/render-pricing/)). Pricing "unchanged" across the Redis→Valkey switch.
- Connect over the **internal URL** (same region) for zero-egress private networking.

**Net: OK.** Run free (25 MB) to hit the low end of budget, or $10/mo Starter for comfortable cache headroom.

---

## 6. Secrets provisioning (must avoid CLI-arg exposure)

Render supports **multiple provisioning paths that keep secrets off the command line / out of `ps`**:

- **Dashboard entry** — type secret env vars (`ESI_CLIENT_ID/SECRET`, `TOKEN_CIPHER_KEYS`, `DATABASE_URL`,
  `CACHE_URL`) directly into the service's Environment tab. No shell involvement. **OK.**
- **Blueprint with `sync: false`** — declare the *names* of secret env vars in `render.yaml` with
  `sync: false`, which tells Render **not to read the value from the (git-committed) Blueprint**; the value
  is set once in the dashboard. This is Render's documented pattern for keeping credentials out of IaC.
  Source: [Blueprint YAML reference](https://render.com/docs/blueprint-spec). **OK.**
- **`DATABASE_URL` / `CACHE_URL` via `fromService`/`fromDatabase` references** — Blueprints can wire the
  Postgres/Key Value connection strings automatically, so those two secrets never need to be typed or
  passed anywhere. **OK.**
- **REST API** — env vars can be set via the Render API (secret travels in an HTTPS request **body**,
  not an argv flag). Env-var **groups** allow sharing across services. **OK.**

No path requires putting a secret in a CLI flag. **Net: OK** — fully satisfies the "no secrets in
`--flag`/argv" constraint.

---

## 7. TLS + custom domain

Fully managed and free: Render issues certificates via **Let's Encrypt and Google Trust Services** for
both the `onrender.com` subdomain and any **custom domains** (including **wildcards**), **auto-renews**
them, and **redirects all HTTP → HTTPS** automatically. Setup is add-domain + DNS verification in the
dashboard. This gives the real HTTPS domain that `Secure`+`HttpOnly` cookies and the EVE SSO callback
require. Sources: [Managed TLS Certificates](https://render.com/docs/tls), [Custom Domains](https://render.com/docs/custom-domains)
(accessed 2026-07-18). **Net: OK** (put the domain on the Static Site per §2). Domain registration itself
is an external cost (~$10–15/yr, not billed by Render).

---

## 8. GitHub Actions CD

Two token models, both usable from a workflow and both keeping the credential in **GitHub Actions
Secrets** (never in argv):

- **Deploy Hook (recommended, tightly scoped):** each service has a **secret deploy-hook URL**; a workflow
  does a single authenticated `POST` to trigger a deploy. Store as a repo secret
  (`RENDER_DEPLOY_HOOK_URL`). It is **scoped to that one service** — no account/API access — which is the
  least-privilege option. Turn **off auto-deploy** on the service so CI is the sole trigger. Source:
  [Deploy Hooks](https://render.com/docs/deploy-hooks).
- **Render API key + `serviceId`:** an account-scoped key from Account Settings → API Keys, stored as a GH
  secret; community actions (e.g. `johnbeynon/render-deploy-action`) call the API to deploy. More powerful,
  broader blast radius than a deploy hook. Source: [Deploy to Render (Marketplace)](https://github.com/marketplace/actions/deploy-to-render).

**Net: OK.** Prefer per-service **deploy hooks** for CD from the existing GH Actions CI — least privilege,
no account-wide token. The repo already has CI, so this bolts on as a final "on green, POST the hook" step.

---

## 9. Total monthly cost estimate (hobby scale, mid-2026)

Assumes the **free Hobby workspace** (static sites free; Postgres PITR 3-day). Itemized:

| Line item | Plan | Est. $/mo |
|---|---|---|
| Backend web service | Starter (512 MB, 0.5 CPU) | **$7** |
| Persistent disk (to force single-instance/recreate deploy) | 1 GB minimum | **~$0.25** |
| Postgres | Basic (~256 MB) + small storage | **~$7–8** |
| Key Value (Valkey) — cache | Free (25 MB) *or* Starter 256 MB | **$0** *or* **$10** |
| Static site (SPA + edge rewrites) | Free | **$0** |
| TLS + custom domain (Render side) | Free managed certs | **$0** |
| Workspace | Hobby | **$0** |
| **Total** | | **~$14/mo** (free cache) → **~$24/mo** (paid cache) |

Notes / knobs:
- Web-service compute figures: Starter **$7** (512 MB / 0.5 CPU), Standard **$25** (2 GB / 1 CPU) — see §10
  RAM caveat; if 512 MB proves tight during ingestion, Standard pushes the total to ~$32–42.
- Upgrading the **workspace to Pro** ($19/user/mo) buys **7-day** Postgres PITR (vs 3-day) — optional;
  adds $19 to the total (~$33–43). Not required for hobby.
- Domain registration (~$10–15/yr ≈ $1/mo) is external to Render.

**Conclusion: comfortably within the $40 ceiling and inside the $5–25 target** at ~$14–24/mo with the
free/near-free options. **OK.**

Pricing sources: [Render pricing overview](https://render.com/pricing) (tables render client-side),
[kuberns 2026 breakdown](https://kuberns.com/blogs/render-pricing/), [Postgres storage/PITR docs](https://render.com/docs/postgresql-refresh),
[saaspricepulse Render pricing](https://www.saaspricepulse.com/tools/render) (accessed 2026-07-18).

---

## 10. App-specific risks / limitations

- **Python 3.14 support — OK (strong).** Render's **default Python is 3.14.3** as of Feb 2026
  ([changelog: Python → 3.14.3, uv → 0.10.2](https://render.com/changelog/updated-version-defaults-python-to-3-14-3-uv-to-0-10-2)),
  and version is pinnable ([Setting Your Python Version](https://render.com/docs/python-version)). No 3.14 gap.
- **PDM is not a natively-detected package manager — MISSING.** Render's native Python build auto-detects
  **uv** (needs `uv.lock`) and **Poetry** (`poetry install`); PDM is not in the first-class set
  ([Supported Languages](https://render.com/docs/language-support)). Workarounds (all FIXABLE): (a) ship a
  **Dockerfile** and let Render build the image (full control, sidesteps buildpack detection); (b)
  `pdm export -o requirements.txt` in CI and let Render's pip path install it; (c) migrate the backend to
  uv. Given the project is a PDM project, the **Dockerfile route is the cleanest** and also gives exact
  control over the Python 3.14 base image.
- **Long-running in-process background job — OK on paid.** Paid web services run continuously and do **not**
  scale to zero; the APScheduler loop stays alive between the every-few-minutes ingests. No separate
  worker/cron resource is required (though Render offers Background Workers and Cron Jobs if the schedule
  were ever externalized).
- **Free-tier spin-down would kill the scheduler — BROKEN if used.** Free web services **spin down after
  15 min of inactivity** (30–60s cold start). A slept instance = a dead scheduler = no ingestion. **Must
  run the paid Starter** (which does not sleep). FIXABLE by paying $7/mo. Source: [Deploys](https://render.com/docs/deploys),
  [free-tier behavior summary](https://render.com/articles/platforms-with-a-real-free-tier-for-developers-in-2026).
- **512 MB RAM on Starter may be tight — watch item.** FastAPI + async SQLAlchemy + asyncpg + APScheduler +
  ESI batch ingestion could pressure 512 MB during large contract pulls. If OOM/restarts appear, move to
  **Standard (2 GB, $25)**. Flag as a **monitor-and-maybe-upgrade** risk, not a blocker.
- **Health-check model — OK, with a caveat.** Render gates traffic on a health-check path; provide a
  lightweight backend health endpoint. Note the interaction with §3: with a disk-forced recreate deploy,
  there's a few-second window where the API is down (old stopped, new not yet healthy). Acceptable at
  hobby scale but real — not truly zero-downtime.
- **Deploy downtime is the price of scheduler safety — accepted tradeoff.** The same mechanism that
  guarantees "never two schedulers" (§3) guarantees a brief API gap on each deploy. This is the central
  design tension for this app on Render, and it resolves in favor of correctness (no duplicate ingestion)
  over zero-downtime — the right call given the CRITICAL single-instance constraint.
- **Cross-service rewrite for non-GET + trailing slashes — verify (FIXABLE-pending).** As in §2, prove the
  static-site → backend full-URL rewrite passes POST bodies (OAuth) and does not inject trailing slashes
  before relying on it in production.

---

## Findings summary (classified)

| # | Finding | Class |
|---|---|---|
| 1 | Single-scheduler guarantee via persistent-disk-forced recreate deploy (max 1, briefly 0, never 2) | **FIXABLE/OK** — documented mechanism |
| 2 | Default zero-downtime rolling deploy runs two instances → duplicate ingestion | **BROKEN at defaults**, fixed by #1 |
| 3 | Python 3.14.3 is the platform default | **OK** |
| 4 | PDM not natively detected (uv/Poetry are) | **MISSING** → Dockerfile / `pdm export` |
| 5 | Same-origin edge (SPA fallback + `/api/v1` strip via static-site rewrites) | **FIXABLE/OK** |
| 6 | Cross-service full-URL rewrite for POST + trailing-slash behavior unconfirmed | **MISSING confirmation** — verify |
| 7 | Managed Postgres, paid Basic, auto PITR (3-day Hobby / 7-day Pro) + 7-day logical exports | **OK** (paid) |
| 8 | Free Postgres deleted after 30 days, no backups | **BROKEN for prod**, use paid |
| 9 | Managed Valkey 8 (Key Value); free 25 MB cache or $10 Starter | **OK** |
| 10 | Secrets via dashboard / `sync:false` / `fromService` / API — no argv exposure | **OK** |
| 11 | Free managed TLS + custom domains (LE/Google, auto-renew, wildcard, HTTP→HTTPS) | **OK** |
| 12 | CD via per-service deploy hook (least-privilege) or API key, GH-Secrets-stored | **OK** |
| 13 | Free web service spins down at 15 min idle → kills scheduler | **BROKEN if used**, use paid Starter |
| 14 | 512 MB Starter RAM may be tight during ingestion | **Watch / FIXABLE** (→ Standard) |
| 15 | Total ~$14–24/mo hobby scale, within $40 ceiling / $5–25 target | **OK** |

---

### Sources (all accessed 2026-07-18)
- Render deploys / zero-downtime / recreate: https://render.com/docs/deploys
- Persistent disks (disables ZDD, caps at 1 instance): https://render.com/docs/disks
- Scaling: https://render.com/docs/scaling
- Static site redirects & rewrites: https://render.com/docs/redirects-rewrites
- Blueprints (IaC): https://render.com/docs/infrastructure-as-code ; YAML ref: https://render.com/docs/blueprint-spec
- Key Value (Valkey): https://render.com/docs/key-value ; Valkey 8 changelog: https://render.com/changelog/new-render-key-value-instances-run-valkey-8 ; Valkey FAQ: https://render.com/docs/valkey-faq
- Postgres flexible plans / storage / PITR: https://render.com/docs/postgresql-refresh ; https://render.com/docs/postgresql
- Managed TLS: https://render.com/docs/tls ; Custom domains: https://render.com/docs/custom-domains
- Deploy hooks: https://render.com/docs/deploy-hooks ; GH Action: https://github.com/marketplace/actions/deploy-to-render
- Python version / language support: https://render.com/docs/python-version ; https://render.com/docs/language-support ; default→3.14.3 changelog: https://render.com/changelog/updated-version-defaults-python-to-3-14-3-uv-to-0-10-2
- Pricing (client-side page + aggregators): https://render.com/pricing ; https://kuberns.com/blogs/render-pricing/ ; https://kuberns.com/blogs/render-postgres-pricing-setup-limits/ ; https://www.saaspricepulse.com/tools/render
