# ABOUTME: Consolidated documentation-based verification of the six Phase-0 spike questions (P1–P6), substituted
# ABOUTME: for the empirical spike per plan Deviation D-1 (no RENDER_API_KEY in the executing session's environment).

# Render docs-based verification — M4 (2026-07-18)

**Why this file exists:** the M4 plan's Phase 0 spike (Task 0.1, probes P1–P6) could not run — the session
had no `RENDER_API_KEY`, so neither the Render MCP nor the curl fallback could create spike resources
(plan Deviation D-1). This is the substitute: the same six questions answered from official Render
documentation only, by four parallel research lanes with per-answer confidence labels. Lane reports
(full quotes + URLs + gaps): [`render-docs-verification/`](render-docs-verification/) —
`blueprint-fields.md`, `deploy-api.md`, `static-site-defaults.md`, `connection-strings.md`.

**This file does NOT retire the empirical spike.** `render-spike-results.md` is reserved for the real
probe outputs; the spike MUST run before Phase 2b applies the blueprint. The verdict below is
provisional on the two questions documentation cannot answer.

## Verdict vs the spike probes

| Probe | Docs-based answer | Confidence | Empirical spike still required? |
|---|---|---|---|
| P1 — POST body/method pass-through across cross-service rewrite | **Undocumented.** Rewrites to absolute URLs are described as serving "content from the rule's destination" (proxy-like), but nothing covers non-GET methods, bodies, or query strings | not-found | **YES — load-bearing.** SSO logout + all M3 account POST/DELETE calls ride this |
| P2 — trailing-slash preservation | **Undocumented.** No normalization (slash/case/redirect) is documented; the only automatic edge redirect documented is HTTP→HTTPS | not-found | **YES — load-bearing** (PROXY-1 307-escape is the excluded failure mode) |
| P2b — assigned hostname reality | N/A from docs (account-specific) | — | YES (checked at 2b apply per render.yaml's inline note) |
| P3 — `fromDatabase` URL scheme | **`postgresql://`** (documented format `postgresql://user:password@host:port/database`, internal/private-network URL). Task 3.1's `+asyncpg` normalization is confirmed necessary. Key Value `fromService` yields **`redis://`** (internal, non-TLS, unauthenticated by default) — redis-py-compatible as-is | documented | No (format documented verbatim) |
| P4 — static-site default headers | **No documented default HSTS, no documented default Cache-Control, no documented ETags.** Brotli compression IS documented as default; CDN caches are invalidated on every deploy. Our explicit HSTS + Cache-Control header rules in render.yaml are therefore REQUIRED, not defense-in-depth | documented-absence / documented | Optional (headers are now explicitly set regardless of defaults) |
| P5 — deploy pin+poll mechanism | **Fully documented.** `POST /v1/services/{id}/deploys` accepts `commitId`; returns **201** (full deploy object, `id` required) or **202 Queued (NO body)** — deploy.yml's list-fallback (`GET …/deploys` → array of `{deploy, cursor}`, match `.commit.id`) is the documented-shape recovery. Complete `status` enum (11 values): `created, queued, build_in_progress, update_in_progress, live, deactivated, build_failed, update_failed, canceled, pre_deploy_in_progress, pre_deploy_failed`. deploy.yml's success set `{live}` and failure set `{build_failed, update_failed, canceled, pre_deploy_failed, deactivated}` cover every terminal state. Rate limits: GET 400/min (polling fine), deploy-creation POST **20/hour** (never retry-loop the POST) | documented | Only for the 201-vs-202 trigger condition (undocumented; hypothesis: 202 = Wait-policy queue) |
| P6 — `RENDER_GIT_COMMIT` | **Documented** runtime env var: "The commit SHA for a service or deploy" (full-SHA is the strong reading, not literally stated) | documented | Cheap to confirm on first deploy |

**TOPOLOGY: A (static-site rewrites) — PROVISIONAL.** Every render.yaml field name is confirmed current
(no deprecated keys; `autoDeployTrigger`, `previews.generation`, `type: keyvalue`, `staticPublishPath`,
`postgresMajorVersion` all verified against the live Blueprint spec), and `ipAllowList: []` is the
documented block-all-external form. But P1/P2 — the two behaviors that CHOOSE Topology A over
Appendix B's in-container Caddy — are undocumented and remain unverified. The empirical spike is the
gate: if P1 or P2 fails live, switch to Appendix B before 2b.

## Corrections applied to the plan's inline file contents

1. **YAML 1.1 boolean trap:** the plan's inline render.yaml writes `autoDeployTrigger: off` and
   `generation: off` unquoted — YAML 1.1 parses bare `off` as boolean `false` (verified with pyyaml),
   which for these string enums would be invalid or silently mean "auto-deploy on commit". Render's own
   spec example quotes `'off'`. The committed render.yaml quotes all three occurrences (Deviation D-5).
2. **Dockerfile compile stage:** the locked `asyncpg 0.30.0` / `httptools 0.6.4` / `uvloop 0.21.0`
   predate CPython 3.14 and publish no cp314 wheels; `python:3.14-slim` has no compiler, so the plan's
   two-stage Dockerfile cannot install them. A dedicated build stage (`build-essential`, `pip install
   --prefix`) was added; the runtime stage stays slim (Deviation D-4).

## Facts worth keeping (from the lane reports)

- `sync: false` env vars are prompted **only during initial Blueprint creation** and **ignored on
  blueprint updates** — matches the plan's 2b step-1 warning; treat it as hard.
- Disks: paid services only (starter ✓); documented single-instance pin + "stops the existing instance
  before bringing up the new instance" (the I-3 recreate semantics, in Render's words); disk is
  **unavailable during build and pre-deploy commands** (fine — migrations don't touch it).
- `staticPublishPath`/`dockerfilePath`/commands resolve **relative to `rootDir`** (monorepo doc) —
  `rootDir: app/frontend/web` + `staticPublishPath: dist` is correct.
- Postgres majors 13–18 available; blueprint pins `"17"` (plan's choice; `18` is current newest —
  flip at 2b if preferred, immutable after creation).
- Concurrent deploy creates are not rejected: workspace policy is Wait (queue+skip intermediates,
  default for workspaces created ≥2025-07-14) or Override (cancel in-flight). deploy.yml's
  `concurrency: deploy-production` queueing already serializes our own creates.
- Key Value free tier: no documented memory cap (the 25 MB figure is pricing-page lore — client-rendered,
  unverifiable this session); free instances lose all data on restart (documented) — consistent with the
  spec §4 accepted consequences.

## Gaps that stay open (do not guess)

Empirical-only: P1 POST pass-through; P2 trailing slash; 201-vs-202 trigger condition; list default sort
order (newest-first is relied-on but not stated); `ipAllowList: []` API acceptance (documented on the
spec page, still worth watching at apply); internal-Postgres TLS posture for asyncpg (undocumented;
don't add `ssl=` until verified); Key Value free memory cap.
