# ABOUTME: Consolidated outcome of the Phase-3 batch review — 3 lens rounds + codex cross-model round,
# ABOUTME: every finding adversarially verified; this file maps confirmed findings to applied fixes.

# M4 Phase 3 review — consolidated outcome (2026-07-19)

Method: plan Task 3.12 Step 2, executed as (1) three parallel review rounds — A spec-fidelity
(§§4-8 clause walk), B pitfalls-checklists, C fresh-eyes bug hunt — with per-finding adversarial
verification (full reports in this directory), and (2) a codex cross-model `codex review`
(model_reasoning_effort=high) as the repo-policy adversarial second opinion. Full gates
(flake8, 398 pytest, tsc, 161 vitest, 92 e2e) green before and after fixes.

## Codex round (gate: FAIL → all fixed → re-verified)

| Finding | Severity | Fix |
|---|---|---|
| /ready depends on `get_cache`, which raises when startup cache init failed — bare 503 body, no re-probe, instance bricked until restart | P1 | /ready reads the client off `app.state` and attempts one `init_cache` self-heal per call inside the probe timeout; structured body always (commit `14942cf`) |
| A failed `SELECT 1` probe leaves the request session uncommitted; `get_db`'s post-request `commit()` then raises → 500 instead of the structured 503 | P2 | Best-effort `rollback()` in the db-probe failure path (same commit) |
| The M3 watchlist matcher still `create_async_engine()`s per run — outside the tuned pre-ping/bounded pool; a connection-budget blind spot the plan missed (M3 merged after plan authoring) | P2 | Matcher reuses `fastapi_app.db.AsyncSessionLocal` (commit `454e7b0`) |

## Lens rounds (12 raw findings → 3 confirmed, 7 refuted, 2 self-resolved)

| Finding | Severity | Fix |
|---|---|---|
| A1: equivalence guard ran `compare_metadata` without `compare_server_default` — blind to exactly the server-default autogen-hazard class spec §5 hand-reviews | P2 | Guard now passes `opts={"compare_type": True, "compare_server_default": True}` (matches env.py); green with no reflection false positives (commit `88663de`) |
| A2: prod env block omitted the pure-default ESI rows from spec §6's inventory | P3 | Row added to `.env.example` (same commit) |
| P3-4: `/cache-test` deletion left `AsyncSessionLocal`/`Response`/`BaseHTTPMiddleware` imported-unused in main.py (ENV-6 shape, no F811 tripped) | P3 | Imports dropped (same commit) |

**Self-resolved mid-review:** C1 (OpenAPI chain not regenerated after the route-surface change —
the Phase-1 drift gate would have failed CI) was fixed as commit `ec63276` while verification ran;
its verifier refuted it against the updated tree.

## Codex round 2 (fix verification on the default model — gate: FAIL → fixed)

| Finding | Severity | Fix |
|---|---|---|
| The cache self-heal is unreachable for a PERSISTENT boot-time outage: `scheduler.start()`'s RedisJobStore write crashes the lifespan first (pre-existing posture; platform restart loop recovers) | P1 | Docstring corrected to the honest scope (the reinit covers the ping-blip window only); posture recorded as a plan Discovery, scheduler-start tolerance parked to M5 |
| A `db.rollback()` that itself raises falls through to `get_db`'s post-yield `commit()` on the dead session → 500; rollback also sat outside the probe timeout | P2 | The db probe moved to a dedicated `async_engine.connect()` (no session, no commit path at all) inside the timeout; `/ready` no longer takes the `get_db` dependency |

## Codex 5.6-Sol high round (the delegated merge gate — Sam, in-session 2026-07-19)

Round 1 (1 finding → fixed): valid-but-non-object JSON (`null`, `[]`) in the freshness key raised
`AttributeError` past both except-tuples — permanently skipping the recorder's repairing SET and
500-wedging `/ready`, the deployment health gate. Both sites now isinstance-guard and treat
non-object JSON as no-record; pinned by 5 tests. Final Sol round on the fixed head: see below.

## Refuted (see lens reports for the full verifier reasoning)

- P3-1 (non-generator get_db double masks real cleanup) — the rollback-mechanism test pins the interplay; the real-session path is covered by the dependency's own tests.
- P3-2 / C2 (/metrics token compare not constant-time) — refuted as immaterial at this threat model: the token gates a metrics read, HTTPS + network jitter dominate, and FastAPI receives the full header regardless; noted for a future hardening pass rather than this PR.
- P3-3 (freshness SET not lock-ownership-gated) — the write happens inside the lock context by construction; a TTL-expired writer overwrites at worst one record that the next tick replaces (loss-tolerable by spec §8.2).
- P3-5 (freshness tests don't assert logged errors) — the tests assert the recorded outcome, which IS the behavior under test; log content is asserted where it is the contract (SSO warnings).
- C3 (duplicate of A1, weaker form — claimed compare_type also off; compare_type defaults True).
