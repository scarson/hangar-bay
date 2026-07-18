# M4 Handoff — Design + Plan Complete (2026-07-18)

ABOUTME: End-of-session handoff for the M4 production-readiness design/planning session — what shipped, what's executable now, what waits on the M3 merge, and exactly what's blocked on Sam.
ABOUTME: The authoritative artifacts are the spec (2026-07-18-m4-production-readiness-design.md) and plan (2026-07-18-m4-production-readiness.md); this file is orientation, not a second source of truth.

## What shipped this session

1. **Recon wave** — `docs/audits/m4-recon/`: 5 repo lanes (deploy-runtime, data-migrations, frontend-edge, auth-prod, ci-observability) + 6 hosting-candidate evaluations under a symmetric template (Fly.io, Render, Railway, VPS+Compose, Vercel+Supabase at Sam's request, Cloudflare at Sam's request). Merged in PR #44.
2. **Design spec** — `docs/superpowers/specs/2026-07-18-m4-production-readiness-design.md`. Decision: **Render** (managed-Postgres-with-PITR-in-budget is the deciding axis post-M3; full matrix + clean-story check + runner-up in §3). Codex adversarial review pre-merge: 14 findings, all verified and applied (`docs/audits/m4-design-review/`). Merged in PR #44 (dev @ `ce3c82b`).
3. **Implementation plan** — `docs/superpowers/plans/2026-07-18-m4-production-readiness.md`. Phases 0–4, Living Document Contract, execution banners. Reviewed through a 5-round plan-review cycle (runner → codex-xhigh/high + cold Opus in parallel → runner → independent verification round → clean runner sweep); 32 findings applied total; artifacts in `docs/audits/m4-plan-review/`. This handoff rides the plan PR.
4. **D1 question answered** (Sam asked in-session): switching to D1 is a backend re-platform (no TCP/SQLAlchemy path, no interactive transactions over HTTP), not a database swap — recorded in spec §3.6 considered-and-ruled-out.

## Execution state (mirrors the plan's Execution Status table)

| Phase | Ready? |
|---|---|
| 0 — Render spike (free tier, 6 probes) | **Executable now** by any session; no billing, no Sam gate |
| 1 — Scaffolding (Dockerfile, blueprint, Alembic stage 1, deploy.yml, drift gate) | **Executable now**; collision-free with M3 (Standing Order 2 lists the exact allowed surface) |
| 2a — Sam: billing sign-off, domain, prod EVE app registration, RENDER_API_KEY + PROD_ORIGIN | **Blocked on Sam**, no technical prerequisite |
| 2b — Blueprint apply + secrets (runs as Phase 4 Step 0) | After Phases 1+3 reach `main` |
| 3 — Post-M3 hardening (11 tasks, TDD) | **Blocked on the M3 merge to dev** (M3 session in flight on `claude/m3-account-features`; its PR opens as "Review — database schema + per-user data authorization", Sam merges) |
| 4 — First deploy + live SSO verification | Blocked on 1+2+3; **exit criterion is Sam's manual prod SSO login** (spec §9.3) |

## Blocked on Sam (the complete list)

1. **Platform sign-off + billing** — Render, ~$14–24/mo (spec §3.3; §3.4 documents how to re-decide toward Fly/VPS without new recon if you weight cost or platform-independence differently).
2. **Domain** — choose + register (~$12/yr); needed before the EVE registration.
3. **Prod EVE app registration** — developers.eveonline.com, new app, callback `https://<domain>/api/v1/auth/sso/callback`, zero scopes (plan Phase 2a step 3).
4. **Secrets entry at blueprint-apply time** — generated BEFORE the "New → Blueprint" flow, entered in the flow itself (plan Phase 2b step 1 has the exact generation one-liners). Never CLI, never chat.
5. **M3 PR merge** (when it opens) — unblocks Phase 3.
6. **Live SSO verification on prod** — the M4 exit criterion (plan Phase 4 Step 3).

## Watch-fors for the executing session

- **One-writer rule**: the M3 session performs post-merge dev realignments; check `gh pr list` before any merge you run.
- **Phase 3 starts with Task 3.0 re-anchoring** — every file:line in Phase 3 cites pre-M3 dev and WILL have drifted; that's expected and handled, not a plan bug.
- **The spike verdict gates the topology** — Topology B (in-container Caddy, plan Appendix B) is fully specified if the static-rewrite probes fail; don't improvise a third shape.
- **deploy.yml is inert until 2b's secrets exist** — its first `workflow_run` firing after the release will fail at the deploy step by design (plan Phase 4 Step 0 says so); don't chase it.
- **Session memory hygiene**: the M4 memory files in the user-scoped store were updated this session; read them before re-deriving any of the above.
