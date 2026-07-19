# ABOUTME: Consolidated outcome of the Phase-1 adversarial review (3 parallel lenses, per-finding adversarial verification).
# ABOUTME: Lens reports in this directory are the full records; this file maps confirmed findings to the fixes applied.

# M4 Phase 1 review — consolidated outcome (2026-07-19)

Method: 3 parallel review lenses (plan-fidelity, config-correctness, pitfalls-and-ops; full reports in
this directory), 12 raw findings, each verified by an independent adversarial verifier instructed to
refute it. 7 confirmed, 5 refuted.

## Confirmed → fixes applied

| Finding | Severity | Fix |
|---|---|---|
| PF-1: deviation records (D-4/D-5) only in working tree | P2 | Plan update committed before the PR was opened (this commit series) |
| config-1: static site omits `branch:` → tracks repo default `dev`, not `main` | P2 | `branch: main` added to `hangar-bay-web` (Deviation D-6) |
| PO-1: empty untracked `versions/` breaks Task 3.9 autogen on fresh checkout | P2 | `versions/.gitkeep` added (Deviation D-8) |
| PF-2 + PO-2: Task 1.3's test file vs Standing Order 2's "exactly" allowlist | P3 | Reconciled as plan-authoring inconsistency; recorded as Deviation D-7 |
| config-2: `ipAllowList: []` comment stated inference as fact | P3 | Comment now cites the blueprint-spec's documented empty-list-blocks-all statement (post-review WebFetch of the spec's Inbound IP rules section resolved the lane's gap) |
| config-3: deploy.yml references `live-smoke-prod` / `E2E_PROD_BASE_URL` before Phase 3 delivers them | P3 | Intentional forward reference; inert until Phase 2b secrets exist, and Phase 3 merges before the first real deploy. No change; ordering constraint already recorded in plan Phase 4 Step 0 |

## Codex adversarial round (cross-model, post-lens-review)

`codex review` (model_reasoning_effort=high) against the branch diff. Gate: **FAIL → fixed → clean**.

| Finding | Severity | Fix |
|---|---|---|
| deploy.yml id-less-202 fallback binds to the FIRST deploy matching the SHA — on a rollback (re-deployed SHA) that is an OLD live/deactivated deploy, so the job reports success without awaiting the new deploy; HTTP status of the create was never validated | P1 | Both deploy steps now snapshot pre-create deploy ids, validate the create status (201/202 only), and bind the fallback to a deploy that did not exist pre-create (retry loop, 12×5s) |
| Worst-case poll budget (30+10+10 min) exceeds the 40-minute job timeout — slow-but-valid deploys get killed | P2 | `timeout-minutes: 60` |

Cross-model overlap with the 3-lens Claude review: **0/2** — codex's two findings were both missed by
the lens review, and the lens review's confirmed findings (branch pin, versions dir, plan-state) were
not raised by codex. Both rounds earned their keep independently.

## Refuted (kept for the record — see lens reports for full claims)

- PF-3 (checkbox flipping / unverified claims) — verification evidence exists in session transcript; checkboxes are updated at phase ship per the Living Document cadence.
- PF-4 (HSTS comment divergence) — evergreen-comment rewrite is sanctioned by the docs-verification outcome.
- PO-3 (short-SHA risk in release verification) — RENDER_GIT_COMMIT documented as "The commit SHA"; full-SHA is the strong reading, and a mismatch fails safe (deploy job red, not silent).
- PO-4 (`ipAllowList: []` may be rejected) — the blueprint spec documents the empty list as the block-all-external form.
- PO-5 (frontend half of drift gate unverified) — the chain was run end-to-end locally and `git diff` came back clean.
