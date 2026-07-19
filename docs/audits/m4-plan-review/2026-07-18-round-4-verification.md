# ABOUTME: Round-4 cold verification sweep of the M4 production-readiness plan — checks whether every
# ABOUTME: round-2 codex + opus finding was applied, plus a fresh end-to-end cold pass for new defects.

**Reviewer:** independent cold verification reviewer (zero prior context), READ-ONLY.
**Plan:** `docs/superpowers/plans/2026-07-18-m4-production-readiness.md`
**Spec:** `docs/superpowers/specs/2026-07-18-m4-production-readiness-design.md`
**Round-2 inputs verified:** `docs/audits/m4-plan-review/2026-07-18-codex-round-2.md` (13 P1 + 8 P2), `docs/audits/m4-plan-review/2026-07-18-opus-round-2.md` (2 P1 + 6 P2).
**Method:** read the full plan (1278 lines) + the two round-2 artifacts + spec §8.2; empirically re-checked every code-verifiable anchor against the live repo (`main.py`, `background_aggregation.py`, `db.py`, `core/dependencies.py`, `core/config.py`, `tests/conftest.py`).

---

## Verification tally

**27 applied / 2 partially applied / 0 not-applied / 0 regressed** (29 findings classified: 21 codex + 8 opus).

---

## Part 1 — Verification sweep

### Codex round-2 (13 P1 + 8 P2)

| # | Finding (short) | Classification | Evidence in current plan |
|---|---|---|---|
| P1-1 | POST body_len 18→19 | **APPLIED** | L155 `body_len=19 (len("grant=body-survives"))` + recompute-if-varied note |
| P1-2 | `DATABASE_URL[:16]` credential leak | **APPLIED** | L122-123 derive scheme only via `partition('://')`; P3 probe L167 expects `postgresql://` |
| P1-3 | rewrite assumes unproven backend hostname | **APPLIED** | Spike P2b L161-164 + Task 1.2 PLACEHOLDER note L350-352 + Phase 2b verify L771 |
| P1-4 | 202-Queued deploy response unhandled | **APPLIED** | Task 1.4 L599-606 resolves empty id from deploy list; P5 L188-189 captures 202 shape |
| P1-5 | SHA input shell/output injection | **APPLIED** | "Resolve deploy SHA" step L572-585 gates `^[0-9a-f]{40}$` via env before `$GITHUB_OUTPUT` |
| P1-6 | drift-repair violates M3 collision boundary | **APPLIED** | Task 1.5 Step 2 L742: record Discovery, drop from Phase-1 PR, re-run as first Phase-3 commit |
| P1-7 | secrets entered too late for initial deploy | **APPLIED** | Phase 2b Step 1 L770 generate + enter all `sync:false` in blueprint-creation form |
| P1-8 | `_record_run_outcome` has no redis client | **APPLIED** | Task 3.3 wiring rule 1 L905: `yield redis_client` + `async with ... as redis_client` |
| P1-9 | counters don't represent committed data | **APPLIED** | Semantics block L869 + spec §8.2 (L203) both define success/partial/failure vs commit |
| P1-10 | `get_db` imported from wrong module | **APPLIED** | ops.py L984 `from ..db import get_db`; L983 `from ..core.dependencies import get_cache` |
| P1-11 | missing short readiness timeouts | **APPLIED** | ops.py `READINESS_CHECK_TIMEOUT_SECONDS=2.0` + `asyncio.timeout`; hang tests L959,L961 |
| P1-12 | tests don't match async client | **APPLIED** | Task 3.4/3.5 tests are `async def` + `await client.get`; token via `monkeypatch` L1051 |
| P1-13 | migration fixture non-executable sketch | **APPLIED** | Task 3.9 Step 4 L1168-1195 full fixture: `make_url`, AUTOCOMMIT admin, try/finally, DROP...FORCE |
| P2-14 | HSTS has no executable owner | **APPLIED** | render.yaml L358-361 explicit `Strict-Transport-Security` rule + conditional note |
| P2-15 | import-safety claim false | **APPLIED** | Task 1.3 Step 4 adds `test_alembic_env_import_is_side_effect_free` L516-524 |
| P2-16 | key-schema deviation + gauge untested | **APPLIED** | Spec §8.2 L203 updated to `regions_ok/regions_failed/last_success_at`; gauge before/after asserts L876,L889 |
| P2-17 | partial-config coverage + lifespan untested | **APPLIED** | Task 3.7 L1095 parametrizes every non-empty subset incl. secret/cipher-set-id-empty; lifespan test L1097 |
| P2-18 | pool test can't pin budget | **APPLIED** | Task 3.8 L1115-1116 assert exact `size()==5` and `_max_overflow==5` |
| P2-19 | wrong M3 module examples | **APPLIED** | Task 3.9 Step 1 L1138 uses `account`; "merged `__init__.py` is authoritative" |
| P2-20 | verification commands lack working dirs | **APPLIED** | Task 3.12 Step 2 L1233-1234 `cd app/backend` / `cd ../frontend/web` |
| P2-21 | ORCH-1 claimed not satisfied | **APPLIED** | Task 3.12 Step 2 L1230 names exact per-round file paths, commit-before-consolidate |
| P2-22 | optional PR-split underspecified | **PARTIALLY APPLIED** | Task 1.6 L752 chose "Single PR — do NOT split", BUT Phase 1 intro **L208 still offers** "or split Task 1.3 into its own PR if review size warrants" — the contradiction the fix was meant to remove survives at L208. See NEW-2. |

### Opus round-2 (2 P1 + 6 P2)

| # | Finding (short) | Classification | Evidence |
|---|---|---|---|
| P1-1 | `get_db` wrong import + Step-2 note | **PARTIALLY APPLIED** | Code import fixed (ops.py L984). But the Step-2 **prose note L1035** still reads "Adapt `get_db`/`get_cache` names to the merged `core/dependencies.py` exports" — Opus explicitly asked to correct this; `get_db` is in db.py and is NOT and will not be in dependencies (verified: dependencies.py exports only get_cache/get_http_client/get_esi_client). See NEW-3. |
| P1-2 | freshness mislabels 304 as failure | **APPLIED** | Semantics L869 + all-304 test `test_freshness_success_when_all_regions_304` L878; 304 branch increments `ok` (wiring rule 2 L906) |
| P2-3 | `/metrics` uses `HTTPException` unimported | **APPLIED** | Task 3.5 Step 2 L1067 `from fastapi import HTTPException  # ... add it` |
| P2-4 | redis client unspecified + "inside lock" wrong | **APPLIED** | Task 3.3 rule 1 L905 top-level-abort recording moved inside lock context, except re-raises |
| P2-5 | fixture cites non-existent house idiom | **APPLIED** | Task 3.9 Step 4 now owns full DB lifecycle (autocommit admin engine, create/drop). See NEW-1 for a residual import gap. |
| P2-6 | speculative M3 schema names | **APPLIED** | Step 1 L1138 uses `account`. (Step 3 L1146 still names the `notifications` table, but that is defensible hand-review guidance against the actual generated revision, not a module-import guess.) |
| P2-7 | most-likely-renamed blueprint keys | **APPLIED** | Task 1.2 Step 2 L376 names `autoDeployTrigger` and Key-Value `fromService.property: connectionString` explicitly |
| P2-8 | `/ready` tests must override `get_cache` | **APPLIED** | Task 3.4 Step 1 L944 "these tests MUST also override the cache dependency (`dependency_overrides[get_cache]`)" |

**Empirical spot-checks that confirmed the fixes are correct (not just present):**
- `main.py:142` logs exactly `"Skipping destructive create_db_tables (...)"` → Task 1.1 smoke `grep "Skipping destructive"` will match.
- `background_aggregation.py`: `_concurrency_lock` yields no value (`yield` at :105); per-run `create_async_engine` at :151 with `DATABASE_URL[:30]` log at :150; `ESINotModifiedError` caught at :172, distinct from `logger.error("Failed to fetch...")` at :175 — every anchor the plan cites is real.
- `db.py`: `get_db` at :30, `AsyncSessionLocal` at :17, `async_engine` at :11 — Task 3.2/3.4/3.8 anchors correct.
- `core/dependencies.py` exports get_cache/get_http_client/get_esi_client, **no** get_db — confirms both the P1-10/Opus-P1-1 import fix and the residual note problem (NEW-3).
- Spec §8.2 (L203) genuinely carries the updated 304-counts-as-checked-ok / last_success_at semantics — the plan's "spec was updated to match" claim (L869) is true, not aspirational.

---

## Part 2 — Fresh cold pass (NEW findings)

### [P2] NEW-1 — Task 3.9 Step 4 fixture references `settings` but never imports it
The `blank_migrated_sync_connection` fixture (L1176) calls `make_url(str(settings.DATABASE_URL_TESTS))`, and the equivalence test file is billed as "complete code, not an idiom reference" (L1167). But neither the Task 1.3 `test_migrations.py` header (imports only `importlib.util` + `pathlib.Path`) nor the Task 3.9 Step 4 snippet (imports `pytest`, `compare_metadata`, `MigrationContext`, `create_engine`, `Base`) imports `settings`. A cold subagent copy-pasting the "complete" fixture hits `NameError: name 'settings' is not defined` on first run. The house idiom is a module-level singleton import: `from fastapi_app.core.config import settings` (used verbatim in `tests/conftest.py:25`, `tests/core/test_session.py:8`, etc.). **Fix:** add `from fastapi_app.core.config import settings` to the Task 3.9 Step 4 imports list.

### [P2] NEW-2 — Phase 1 intro (L208) still offers a split-PR path the round-2 P2-22 fix removed
Task 1.6 Step 1 (L752) authoritatively resolves the structure: "Single PR — do NOT split by task ... splitting creates ordering ambiguity for zero review benefit." But the Phase 1 preamble (L208) still reads: "One PR at the end (Routine), **or split Task 1.3 into its own PR if review size warrants**." A cold executor reads the Phase intro before reaching Task 1.6 and can act on the stale option, exactly the two-agents-diverge hazard codex P2-22 flagged. **Fix:** delete the "or split Task 1.3…" clause at L208 so the intro matches Task 1.6's decision. (Same locus as codex P2-22 → classified PARTIALLY APPLIED above.)

### [P2] NEW-3 — Task 3.4 Step-2 note (L1035) still mislocates `get_db` in `core/dependencies`
The code block is correct (`from ..db import get_db`, L984, with an inline "get_db lives in db.py, NOT core/dependencies" comment at L984). But the surrounding prose at L1035 still says "Adapt `get_db`/`get_cache` names to the merged `core/dependencies.py` exports (Task 3.0 verified them)" — which re-asserts the very error the import fix corrected, and contradicts the adjacent code comment. Verified: `core/dependencies.py` exports only get_cache/get_http_client/get_esi_client; M3 does not move get_db (Opus round-2 confirmed M3 touches dependencies.py once, not db.py). **Fix:** trim L1035 to "Adapt `get_cache` to the merged `core/dependencies.py` exports; `get_db` stays imported from `..db`." (Same locus as Opus P1-1 → classified PARTIALLY APPLIED above.)

All three NEW findings are P2 (a TDD executor would surface NEW-1 as an immediate NameError, and NEW-2/NEW-3 are self-contradiction hazards rather than hard blockers). No new P1 defects found. No regressions from the round-2/3 fixes.

---

## Bottom line
27 of 29 round-2 findings are cleanly applied and empirically correct against the live repo; 2 are partially applied (residual stale prose at plan L208 and L1035 — the code/decision is right, the surrounding text still carries the old error). The fresh pass adds 3 P2 items, all minor and two of them the un-swept tails of the partial applications. No P1 remains open.
