# M4 Phase 1 Review — Plan Fidelity Lens

ABOUTME: Line-by-line fidelity review of the M4 Phase 1 deploy-scaffolding branch against the plan's inline specs for Tasks 1.1-1.5.
ABOUTME: Records the one P2 (uncommitted Living-Document deviation records) plus three P3 notes; committed code is otherwise a faithful, verified match.

**Reviewer lens:** plan fidelity. Every committed file compared against the plan's inline specification (`docs/superpowers/plans/2026-07-18-m4-production-readiness.md`, Tasks 1.1-1.5). Sanctioned deviations D-4/D-5 accepted; anything else that differs from inline plan content, missed steps, missing mandated-verification evidence, files outside Standing Order 2's surface, commit-message mismatches, and Living-Document contract adherence are in scope.

**Branch:** `claude/m4-phase1-deploy-scaffolding` @ HEAD `9cc10d6`, vs `origin/dev`.
**Commits reviewed:** `fc54a19` (plan claim + D-1..D-3), `9c99bcc` (Dockerfile), `c7712c7` (Alembic), `3849b60` (docs-verification), `7ad3395` (render.yaml), `d3f6601` (deploy.yml), `9cc10d6` (ci.yml drift job).

## Verdict

High-fidelity implementation. Every committed Task 1.1-1.5 file matches the plan's inline spec **byte-for-byte** except the two sanctioned deviations (D-4 Dockerfile compile stage, D-5 quoted `"off"`) and one plan-sanctioned comment adaptation. All five task commit messages match the plan's specified strings exactly. No unsanctioned code divergence found; **no P1**. One P2 (Living-Document records for the two divergences are uncommitted) and three P3 notes below.

### Per-file confirmation

- **Task 1.1 `.dockerignore`** — byte-identical to plan.
- **Task 1.1 `Dockerfile`** — diverges from plan (3 stages vs 2) exactly as D-4 sanctions; `--workers 1`, no `--reload`/gunicorn, `EXPOSE 8000`, `PYTHONPATH`/`PYTHONUNBUFFERED` all present; `src/.env` excluded by `.dockerignore`. D-4 records the build/boot/`/health`/fail-closed verification.
- **Task 1.2 `render.yaml`** — all services/envVars/routes/headers/databases match inline plan. `off`→`"off"` (×3) per D-5. Field-name validation done docs-based (`render-docs-verification/blueprint-fields.md`) per D-1. HSTS comment adaptation noted P3-4.
- **Task 1.3** — all six stale revisions + `check_alembic_version.py` deleted; `versions/` empty (no baseline generated, per "Do NOT generate any revision"); `env.py` byte-identical to plan target (debug print block gone, compare flags on, import-safe tail); `pyproject.toml` scripts appended after `export-openapi`; `test_migrations.py` byte-identical to plan. `alembic.ini` untouched. **Independently verified:** env.py imports side-effect-free outside an alembic context and `do_run_migrations` is callable.
- **Task 1.4 `deploy.yml`** — byte-identical to plan inline. Concurrency group `deploy-production` distinct from CI's; `permissions: contents: read`; no `push:` trigger.
- **Task 1.5 `ci.yml`** — `openapi-drift` job byte-identical to plan inline, appended after `frontend`, nothing else in the file touched (diff is pure addition). **Independently verified the Step-2 precondition holds:** a fresh `export-openapi` produces output identical to the committed `openapi.json`, so the new drift gate will not break CI on merge.

---

## Findings

### 1. [P2] Living Document: the deviation records justifying the two committed divergences are uncommitted
**File:** `docs/superpowers/plans/2026-07-18-m4-production-readiness.md` (working-tree only; `git status` shows ` M`, not in any branch commit)

D-4 (Dockerfile compile stage), D-5 (`render.yaml` quoted `"off"`), and the "cp314 wheel gap" Discovery exist **only as uncommitted working-tree edits** to the plan. The committed history at HEAD contains D-1..D-3 (`fc54a19`) but not D-4/D-5. The two committed files (`Dockerfile`, `render.yaml`) therefore diverge from the plan's inline spec while their sanctioning rationale is absent from the branch's committed content.

**Failure scenario:** if the Task 1.6 PR is opened from HEAD without first committing the plan update, reviewers see a 3-stage Dockerfile and quoted `"off"` enums with no in-repo record of why they differ from the plan — and the Living Document contract's "deviation MUST NOT live only in PR notes" requirement is violated at the artifact level. A `git reset`/worktree cleanup before the commit would silently lose the records. Task 1.6 Step 2 ("commit the plan update") is the designated fix and is still pending (banner correctly reads 🚧 IN PROGRESS), so this is a "must-do-before-PR" gap rather than a defect in already-committed code.

### 2. [P3] `test_migrations.py` created inside Standing Order 2's forbidden surface (plan-internal contradiction)
**File:** `app/backend/src/fastapi_app/tests/test_migrations.py:1`

Standing Order 2 lists Phase 1's allowed surface "exactly" and explicitly forbids Phases 0-2 from touching `app/backend/src/fastapi_app/**`. Task 1.3 Step 4 nonetheless mandates creating this file at exactly that path. The executor followed the specific task instruction (file is byte-identical to the plan), so this is a plan-internal contradiction, not an executor invention.

**Failure scenario:** none in practice — M3 already merged to dev (PR #46, `20ee513`), so the collision the Standing Order guards against cannot occur, and `test_migrations.py` is a new file M3 never created. Flagged only because it is a literal touch of the forbidden surface and the tension is not called out as a deviation.

### 3. [P3] Living Document tracking: no step checkboxes flipped; Task 1.3 Step 4 manual verifications leave no persisted evidence
**File:** `docs/superpowers/plans/2026-07-18-m4-production-readiness.md` (Tasks 1.1-1.5 step lists)

The plan states "Steps use checkbox (`- [ ]`) syntax for tracking," yet every Task 1.1-1.5 step remains `- [ ]` despite all five tasks being implemented and committed. Separately, Task 1.3 Step 4's mandated checks (blank-DB `migrate` → clean/no-revisions, `migrate-check` → empty history, `pdm run pytest` green) have no committed evidence and no prose record — unlike Task 1.1's checks, which D-4 records.

**Failure scenario:** a follower reading the plan cannot tell from tracking state which steps ran; and there is no artifact confirming the blank-DB Alembic scaffold check was performed. Low impact (the committed `test_migrations.py` import-safety guard runs in CI, and this reviewer independently confirmed env.py import-safety), but the formal tracking obligation is under-honored.

### 4. [P3 — note, not a defect] `render.yaml` HSTS comment diverges from the plan's inline comment (justified)
**File:** `render.yaml:85-86`

Plan inline comment: `# Drop this rule ONLY if spike P4 recorded Render already sending an equal-or-stronger HSTS header.` Committed: `# Kept: no Render doc records a default HSTS header on static sites (docs/audits/m4-recon/render-docs-verification-2026-07-18.md).`

The plan (Task 1.2 Step 2) makes the HSTS rule conditional on a keep/drop decision; with spike P4 unavailable (D-1), the docs-verification substitute found no default HSTS, so keeping the rule is correct, and rewriting the conditional instruction-comment into an evergreen rationale aligns with the repo's evergreen-comment rule. Reported only for completeness as a divergence from inline plan text; not a defect.

---

## Scope notes
- Lens is Tasks 1.1-1.5 fidelity + Living Document contract. Task 1.6 (PR) has not run — no PR exists, and the Execution Status table's Phase 1 ship-SHA cell is unfilled — which is expected pre-PR state and is the same gap as Finding 1.
- Phase 0 / Phases 2-4 and the render-docs-verification content quality are out of this lens.
- No tracked file was modified by this review (OpenAPI export was written to a scratch path, not the tracked `openapi.json`).
