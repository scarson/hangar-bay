# ABOUTME: Empirical results of the M4 Phase 0 Render verification spike (plan Task 0.1, probes P1–P6) —
# ABOUTME: the real-platform gate for the Topology A vs B decision that the docs-based verification could not settle.

# Render spike results — M4 Phase 0 (2026-07-21)

**Verdict up front:**

```
TOPOLOGY: A (static-site rewrites)
```

P1 (POST pass-through) and P2 (trailing-slash preservation) both pass **exactly**. No render.yaml
topology change is needed; Appendix B (in-container Caddy) stays unused.

**How this ran.** Free-tier resources on Sam's Render workspace `Primary` (plan Deviation D-2), probe
app from throwaway repo `scarson/hb-render-spike-m4` @ `bc5068ecc240983e44e6e7bf149316bf06c56cc3`
(spike-repo access saga: Deviation D-11 — resolved by making the repo public on Sam's instruction).
Resources: Docker web service `hb-spike-api` (frankfurt) + static site `hb-spike-web` with the two
production-shaped rewrite rules and **no custom headers** (so P4 observes true defaults) + free
Postgres `hb-spike-db` (frankfurt, PG 17). One method deviation from the plan's Step 2: `DATABASE_URL`
was injected via the env-var API from the Postgres `internalConnectionString` (the API create path has
no blueprint `fromDatabase`; the injected value is the same connection string that mechanism delivers,
so P3's observation carries over). All resources deleted after the probes — see Teardown.

## P1 — POST body/method/query pass-through across the cross-service rewrite: **PASS (exact)**

```
$ curl -s -X POST "https://hb-spike-web.onrender.com/api/v1/auth/sso/callback?code=abc&state=xyz" \
    -H 'Content-Type: application/x-www-form-urlencoded' -d 'grant=body-survives'
{"method":"POST","raw_path":"/auth/sso/callback","query":"code=abc&state=xyz","body_len":19,
 "body_prefix":"grant=body-survives","database_url_scheme":"postgresql://",
 "render_git_commit":"bc5068ecc240983e44e6e7bf149316bf06c56cc3"}
```

Method preserved, `/api/v1` prefix stripped by the rewrite (PROXY-1 semantics), query string intact,
body delivered byte-for-byte (`body_len` 19 = `len("grant=body-survives")`). SSO callback/logout and
all M3 account POST/DELETE calls are safe on Topology A.

## P2 — trailing-slash preservation: **PASS (exact, both shapes)**

```
$ curl -s "https://hb-spike-web.onrender.com/api/v1/contracts/"   →  "raw_path":"/contracts/"
$ curl -s "https://hb-spike-web.onrender.com/api/v1/contracts"    →  "raw_path":"/contracts"
```

No slash added, none removed, no 307 escape — the PROXY-1 excluded failure mode does not occur.

## P2b — assigned-hostname reality

Both spike services received their **exact requested names, un-suffixed**:
`hb-spike-api.onrender.com`, `hb-spike-web.onrender.com`. So un-suffixed grants do happen when the
name is globally free; this raises confidence in the blueprint's placeholder destination
`https://hangar-bay-api.onrender.com`, but the 2b apply-time check remains **mandatory** (whether
`hangar-bay-api` is free can only be observed when the production blueprint is applied).

## P3 — injected `DATABASE_URL` scheme: **`postgresql://`**

Observed twice: directly from the Postgres `connection-info` endpoint's `internalConnectionString`
(scheme extracted without printing the credential), and through the runtime env via the echo app
(`"database_url_scheme":"postgresql://"` above). Task 3.1's `postgresql://` → `postgresql+asyncpg://`
normalization (DEPLOY-1, shipped in Phase 3) is confirmed necessary and sufficient.

## P4 — static-site default response headers

Raw (custom-header-free site, `HEAD /` and `HEAD /assets/app.abc123.js`, plus an
`Accept-Encoding: br, gzip` pass):

```
HTTP/2 200
cache-control: public, max-age=0, s-maxage=300
strict-transport-security: max-age=315360000; includeSubdomains; preload
x-content-type-options: nosniff
etag: W/"..."            (weak ETags on both)
server: cloudflare       (cf-cache-status: MISS first hit, HIT after; rndr-id present)
content-encoding: br     (with Accept-Encoding: br,gzip — Brotli by default)
```

| Default | Observed | Consequence for render.yaml |
|---|---|---|
| HSTS | **Present**: `max-age=315360000; includeSubdomains; preload` (10 y, stronger than our rule) | Our explicit HSTS rule's drop-condition (its inline note) is **met**, but the rule is **kept** as defense-in-depth: the default was observed on `*.onrender.com` (an HSTS-preloaded suffix) and we could not verify the same default applies on a custom domain. Duplicate/parallel HSTS headers are harmless. |
| Cache-Control | `public, max-age=0, s-maxage=300` on **everything**, including hashed assets | Our explicit rules (index `no-cache`, `/assets/*` immutable) are **required** — the platform default would re-validate hashed assets and CDN-cache stale indexes for up to 300 s. Keep both rules. |
| Compression | Brotli by default | Nothing to add. |
| ETag | Weak ETags on all responses | Nothing to add. |
| Edge | Served via Cloudflare in front of Render | Explains `s-maxage=300`; deploys purge the CDN per Render docs. |

## P5 — deploy pin + poll mechanism

**Create #1** (`POST /v1/services/{id}/deploys` with `{"commitId": "<full sha>"}`) → **HTTP 201**, full
deploy object, `commit.id` = the pinned SHA:

```json
{"id":"dep-d9fhmmjrjlhs73ac3ij0","commit":{"id":"bc5068ec…"},"status":"build_in_progress",
 "trigger":"api","createdAt":"2026-07-21T07:10:18Z", …}
```

**Create #2, fired while #1 was mid-build** → **HTTP 202 with an EMPTY body** (no id, no JSON). This
settles the docs-verification's open "201-vs-202 trigger condition": **202 = a deploy is already in
flight** (Wait-policy queue). deploy.yml's list-fallback is therefore **required**, and it works: the
queued deploy appears in `GET …/deploys` with its own id and is matchable by `commit.id`.

**Status transitions observed:** `build_in_progress` → `live` (~29 s for this trivial image); the
enum values seen across the run were `build_in_progress`, `live`, `deactivated` (+ `created` implied
by docs; no failure states exercised).

**Operational nuances recorded for deploy.yml (no change needed):**
- The deploy list is returned **newest-first** (relied on by the fallback; previously undocumented).
- `deactivated` also marks a deploy **superseded by a newer live deploy**, not only platform failure —
  the queued create #2 went `live` and flipped create #1 (briefly `live`) to `deactivated`. deploy.yml
  treating `deactivated` as failure remains CORRECT: a pinned deploy that got superseded is not
  serving, and the workflow's own `concurrency: deploy-production` queue prevents self-supersede; only
  an out-of-band (dashboard) deploy during a CD run could trigger it, which SHOULD fail loudly.
- Deploy-create POST rate limit (20/hour, docs) was respected: 2 API creates total.

## P6 — `RENDER_GIT_COMMIT`: **full 40-char SHA present**

`"render_git_commit":"bc5068ecc240983e44e6e7bf149316bf06c56cc3"` — matches the spike repo head
exactly. deploy.yml's release verification and `/ready`'s `commit` field stand on solid ground.

## Teardown

All Render resources deleted 2026-07-21 (DELETE → 204 for `hb-spike-api`, `hb-spike-web`,
`hb-spike-db`; account verified empty: no services, no postgres instances). Throwaway repo
`scarson/hb-render-spike-m4` still exists — the session's GitHub token lacks the `delete_repo`
scope; Sam deletes it with `gh auth refresh -h github.com -s delete_repo && gh repo delete
scarson/hb-render-spike-m4 --yes` (or the GitHub UI). Probe app source lives nowhere else; nothing
in it is worth keeping.
