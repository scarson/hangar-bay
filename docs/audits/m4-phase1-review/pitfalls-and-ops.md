# M4 Phase 1 review — pitfalls + operational failure modes

**Reviewer lens:** implementation-pitfalls §1–§4 checklists + first-production-deploy operational reasoning.
**Diff under review:** `git diff origin/dev...HEAD` on `claude/m4-phase1-deploy-scaffolding` (7 commits: Dockerfile, render.yaml, deploy.yml, ci.yml openapi-drift job, Alembic re-baseline, docs).
**Date:** 2026-07-18.

## Bottom line

Merging this branch to `dev` (and eventually to `main`) is **operationally safe** — everything deploy-related is inert until the Phase 2b blueprint apply, which the plan gates to after Phases 1+3 are on `main`:

- `render.yaml` does nothing on merge — Render only acts when a human runs "New → Blueprint", and `autoDeployTrigger: "off"` means even after apply, commits don't auto-deploy.
- `deploy.yml` triggers only on `workflow_run` for `branches: [main]`; merging to `dev` never fires it. On `main` before the Phase-2 secrets exist it fails closed (loud red X, no partial deploy).
- The CI test suite builds schema via `Base.metadata.create_all` (`conftest.py:71`), **not** Alembic — so the empty `versions/` dir cannot break the test job.
- I empirically verified `alembic upgrade head` (the `preDeployCommand`) and `alembic current` (`migrate-check`) **no-op cleanly (exit 0)** on a fresh, `versions/`-less checkout against a throwaway Postgres — see PO-1.
- The new import-safety test passes with CI-equivalent env; `context.config` raises `AttributeError` (caught by the guard) in the installed alembic 1.16.1 — see "Verified safe" below.
- Backend `openapi.json` export is byte-identical to the committed file (drift gate's backend half is clean).

Pitfalls §1–§4 walk: **ENV-1** JSON env formats are correct (`AGGREGATION_REGION_IDS: "[10000002]"`, `AGGREGATION_DEV_CONTRACT_LIMIT: "0"`). **PROXY-1** route order and prefix-strip are correct (`/api/v1/*` before `/*`; destination strips `/api/v1`). **ESI-1** n/a (no ESI route changes). No §2 SQLA surfaces touched.

No P1 (merge-blocking) findings. One P2 and four P3 notes below.

---

## Findings

### PO-1 (P2) — `alembic/versions/` is empty + untracked; Task 3.9's `makemigration` will die on the missing dir

**File:** `app/backend/src/alembic/versions/` (absent from git tree) — created empty by Task 1.3, which deleted all six revision `.py` files.

**Defect:** Git cannot persist an empty directory and there is no `.gitkeep`, so `alembic/versions/` is **absent on every fresh checkout** (verified: `git archive HEAD app/backend/src/alembic | tar -x` produces `alembic/` with README + env.py + script.py.mako but **no** `versions/`).

**What is NOT broken (verified, disproves the obvious worry):** `alembic upgrade head` and `alembic current` both **exit 0 and no-op** against a versions-less checkout (they create only the `alembic_version` bookkeeping table). So the `preDeployCommand`, the `migrate-check` script, and CI are all fine. Alembic 1.16.1 tolerates the missing dir for read/upgrade.

**What IS broken (verified):** `alembic revision` — i.e. Task 3.9's `pdm run makemigration "baseline"` (`alembic revision --autogenerate`) — dies with `FileNotFoundError: .../alembic/versions/<rev>_baseline.py`. Alembic does **not** create the missing directory before writing the new revision file. A Phase-3 executor on a fresh worktree who runs the plan's own `pdm run makemigration` command will hit this and burn a debugging cycle, because Task 3.9 gives no instruction to `mkdir versions/` first.

**Failure scenario:** Phase-3 session checks out fresh → `alembic/versions/` doesn't exist → `pdm run makemigration "baseline"` → `FileNotFoundError`, no baseline generated, until someone manually recreates the directory.

**Fix (in-scope for this PR — `alembic/**` is Phase-1 allowed surface):** add `app/backend/src/alembic/versions/.gitkeep`. This both restores Task 1.3's evident intent (leave a ready-to-use empty `versions/` for Task 3.9) and hardens `upgrade head` against any stricter alembic version.

---

### PO-2 (P3) — new test file lands outside Standing Order 2's declared Phase-1 allowed surface, undocumented as a deviation

**File:** `app/backend/src/fastapi_app/tests/test_migrations.py:1` (new file, added by Task 1.3 Step 4).

**Defect:** Standing Order 2 states "Phases 0–2 MUST NOT touch: `app/backend/src/fastapi_app/**` source" and defines Phase 1's allowed surface as an exact list that does **not** include `app/backend/src/fastapi_app/tests/`. Task 1.3 Step 4 nonetheless prescribes creating this file there. The plan body and its own collision rule are internally inconsistent, and the Deviations section doesn't record it (the Living Document Contract requires deviations to be inline-documented).

**Failure scenario:** Practically none — M3 already merged to `dev` (PR #46), so the original merge-collision risk this rule guarded against is moot, and a brand-new file can't conflict. The test passes in CI. This is a plan-hygiene / traceability gap, not a runtime defect. Reconcile by adding a one-line Deviation note (the allowed-surface list predates the M3-merge gate being satisfied).

---

### PO-3 (P3) — deploy.yml release-verification depends on `RENDER_GIT_COMMIT` being the FULL 40-hex SHA

**File:** `.github/workflows/deploy.yml:158-168` ("Verify deployed release").

**Defect:** The step loops comparing `/api/v1/ready`'s `.commit` field against `steps.sha.outputs.sha` (a validated 40-hex string). The `.commit` value is delivered by Phase-3 Task 3.4 and sourced from Render's `RENDER_GIT_COMMIT`. The recon docs (`render-docs-verification-2026-07-18.md`, P6) record that full-SHA is "the strong reading, not literally stated." If `RENDER_GIT_COMMIT` is a **short** SHA (or `/ready` truncates it), the equality never holds, the step exhausts its 40 iterations, and **every otherwise-healthy deploy job fails**.

**Failure scenario:** First real deploy (Phase 4). Backend + static deploy `live`, app healthy, but "Verify deployed release" times out because `.commit` = 12-char short SHA ≠ 40-char pinned SHA → deploy job red, `smoke` skipped. Inert until main+2b, but confirm the SHA width on the first deploy (and/or normalize with a prefix comparison in Task 3.4).

---

### PO-4 (P3) — `ipAllowList: []` on the Key Value service may be rejected at blueprint apply

**File:** `render.yaml:62`.

**Defect:** The recon lane doc (`render-docs-verification/blueprint-fields.md`, Gap #1) records that for a **Key Value** service Render marks `ipAllowList` **Required**, and the documented block-all-external form is the dummy range `0.0.0.0/32`, **not** an empty list. Whether the API accepts `[]` is untested (no Render credential this session).

**Failure scenario:** Phase 2b "New → Blueprint" apply rejects `ipAllowList: []` for `hangar-bay-cache`, blocking the first provision until it's changed to `[0.0.0.0/32]`. Already tracked as an apply-time open item in the recon docs; surfaced here because it ships in `render.yaml`. Confirm at 2b.

---

### PO-5 (P3) — openapi-drift gate: only the backend half was verifiable in this review

**File:** `.github/workflows/ci.yml:128-158` (new `openapi-drift` job).

**Defect / status:** The job runs `pdm run export-openapi` then `npm run generate:api` then `git diff --exit-code` on `openapi.json` + `schema.d.ts`. I verified the **backend** half is clean (`export_openapi.py` output byte-matches committed `openapi.json`; and it safely `setdefault`s dummy env so it won't crash on the job's empty `env:` block). I could **not** verify the **frontend** `schema.d.ts` half (no node toolchain run this review). If `schema.d.ts` is stale on `dev`, this new gate turns the Phase-1 PR **red**, defeating the intended "Routine auto-merge on green."

**Failure scenario:** `schema.d.ts` drifted from `openapi.json` on dev → new `openapi-drift` job fails on the Phase-1 PR → auto-merge blocked. Before relying on Routine auto-merge, run `cd app/frontend/web && npm run generate:api && git diff --stat -- src/lib/api/schema.d.ts` and confirm empty (plan Task 1.5 Step 2 mandates this check).

---

## Verified safe (checked, no defect)

- **`upgrade head` / `current` on empty `versions/`** — exit 0, no-op, only `alembic_version` created (throwaway Postgres, versions-less `git archive` checkout).
- **Import-safety test** — `test_migrations.py` passes with CI-equivalent env; `context.config` raises `AttributeError` in alembic 1.16.1, which `_running_under_alembic()` catches. CI's `backend` job supplies `DATABASE_URL`/`CACHE_URL`/`ESI_USER_AGENT`/`AGGREGATION_REGION_IDS`/`TOKEN_CIPHER_KEYS`, so the env.py top-level `get_settings()` succeeds. (Local-only caveat: without `src/.env` the import fails — irrelevant to CI.)
- **`export-openapi` in the drift job with no `env:`** — does not crash; `export_openapi.py` `os.environ.setdefault`s dummy `DATABASE_URL`/`CACHE_URL`/`ESI_USER_AGENT`/`AGGREGATION_REGION_IDS` before importing the app.
- **Prod image has migration deps** — `alembic` and `asyncpg` are in `[project] dependencies` (not the `dev` group), so `pdm export --prod` includes them; the `preDeployCommand`'s `python -m alembic upgrade head` resolves in the runtime image.
- **`render.yaml` YAML-1.1 boolean trap (D-5)** — `previews.generation`, both `autoDeployTrigger` values parse as the **string** `'off'`, not boolean `false` (verified with pyyaml). File parses; route order is `/api/v1/*` then `/*` (PROXY-1).
- **ENV-1** — all complex/JSON env fields in `render.yaml` are quoted JSON strings.
- **Inert-until-2b** — merging `render.yaml` + `deploy.yml` triggers no deploy; `deploy.yml` is `main`-only via `workflow_run`; `/ready` and the pre-deploy migration (both Phase-3 assumptions) are only reached at 2b, which the plan gates to after Phase 3.
