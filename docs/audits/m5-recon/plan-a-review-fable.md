# ABOUTME: Adversarial review (Fable) of Plan A — docs/superpowers/plans/2026-07-27-ingestion-correctness-and-cost.md
# ABOUTME: Judged against the fresh-subagent-zero-context standard; code verified against current source.

# Plan A review — ingestion correctness & steady-state cost (Fable)

Everything below was verified against the worktree source, not assumed. Where the plan's
code is right I say so in one line; the findings are where it is not.

**Verdict in one line:** the plan's logic, task decomposition, migration ordering, and
the services-side test code are solid — but the Alembic chain it builds on **does not
exist on this branch** (confirmed: `c7e2a9b41d36` is absent; head here is
`b1c4d7e9f204`), and both ESI-client test blocks are written against fixtures
(`esi_client`, `httpx_mock`) that **do not exist in the target module**, which fails the
fresh-subagent standard for Tasks 1, 3, and 6.

---

## Verified-good (one line each, evidence checked)

- `_make_service` (MagicMock esi_client + AsyncMock `resolve_ids_to_names` + inert
  `get_contract_items`), `_ship_contract_dict(cid)`, `db_session`, `pytest.MonkeyPatch`
  usage, `select`/`AsyncMock` imports, and the `import ... as bg_agg` alias (line 20)
  ALL exist in `tests/services/test_background_aggregation.py` exactly as Tasks 2/4/5
  assume — the services-side test code drops in as written.
- `item_processing_status` default is the literal `'PENDING_ITEMS'` (client-side
  `default=`, `models/contracts.py:65`) — Task 2's predicate and Task 5's queue
  definition use the right strings.
- `ix_contract_items_contract_id` exists (`models/contracts.py:110`), so Task 3's
  correlated subqueries are indexed — the repair UPDATE will not seq-scan per row.
- Task 2's set arithmetic is correct against the current
  `_update_item_processing_status`, and its failure modes were re-derived: the
  zero-item cases reaching `completed` today are exactly {evicted-304 body, 204, empty
  200}, all failure-shaped — no legitimate zero-item case exists.
- Task 6's control flow is correct in context: the `continue` skips the trailing
  backoff sleep (no double sleep), `float(None)` → `TypeError` → fallback backoff,
  exhausted retries surface as `ESIRequestFailedError` with the 4xx status, which
  callers already map correctly.
- Task 5's mutation pair (delete `continue`; hardcode `1`) genuinely pins both
  behaviors.
- Phase ordering Task 3 → Task 4 is correct in **both** ship configurations (see Q3).

---

## Q1 + Q2 — Subagent executability and code correctness

### BLOCKER-1: The migration chain is wrong on this branch, and the plan's own verification step can't detect it correctly

Confirmed by listing `app/backend/src/alembic/versions/` in this worktree: it contains
**only** `3aca702a74e3_baseline.py` and `b1c4d7e9f204_index_contracts_date_expired.py`.
`c7e2a9b41d36` (`contracts.last_seen_at`) exists only on PR #91's unmerged branch, yet
Task 3's template hardcodes it as `down_revision` **twice** (docstring + module attr),
and the prose asserts "at time of writing that is `c7e2a9b41d36`" — false for the branch
the subagent will be standing in. The verification instruction (`ls src/alembic/versions/`)
lists *filenames*, which neither reveal the chain order nor match the prose, so a
zero-context subagent faces a contradiction with no resolution procedure. And the
failure is not hypothetical in either direction:

- Plan A ships with `down_revision = c7e2a9b41d36` before #91 merges → `alembic upgrade
  head` fails instantly (unknown revision) → **production pre-deploy failure**.
- Plan A ships re-parented onto `b1c4d7e9f204`, then #91 merges with the *same* parent →
  two heads → `alembic upgrade head` errors ("multiple heads") → **production pre-deploy
  failure**, one release later.

**Fix:** make the dependency explicit and mechanical. Either gate Phase 1 on PR #91's
merge (add a ⏸ precondition to the Execution Status table: "blocked until #91 merges to
dev; then rebase and re-verify the head"), or decide Plan A ships first and #91
re-parents — but the plan must pick one and say it. And replace `ls` with the command
that answers the actual question:
`ALEMBIC_CONFIG=src/alembic.ini .venv/bin/python -m alembic heads`.

### BLOCKER-2: Tasks 1 and 6 ship test code that cannot run in the target module

`tests/core/test_esi_client.py` has **no `esi_client` fixture and no `httpx_mock`
usage**. Its idiom is local doubles: `_etag_response(...)` (MagicMock responses with
real-dict headers) fed to `_etag_client(AsyncMock(side_effect=[...]), cache={...})`,
which injects MagicMock http/redis clients into `ESIClient`. The plan's `httpx_mock`
approach would additionally require a real `httpx.AsyncClient` *and* a redis client the
tests never construct (the `redis_client` property raises `RuntimeError` without one) —
so the blocks fail at fixture resolution before any assertion runs. Task 1 carries a
one-line escape hatch ("mirror the construction used by existing tests"); Task 6 has
**none**. A fresh subagent that trusts the plan's code gets collection-time errors and
then improvises — the precise failure mode this standard exists to prevent.

**Fix:** rewrite both test blocks in the module idiom. Task 1 can mirror
`test_pagination_follows_x_pages` (line 360) almost verbatim — same two-page
`X-Pages: 2` doubles, but calling `esi_client.get_contract_items(999)`; red/green works
identically. Task 6: `_etag_client(AsyncMock(side_effect=[_etag_response(status_code=429,
headers={"Retry-After": "7"}), _etag_response(json_data=[...], headers={"ETag": "ok"})]))`
plus the monkeypatched sleep (the dotted-path monkeypatch target is fine — it patches
`asyncio.sleep` via the module reference and restores after).

### MAJOR-3: Task 4's migration template is missing the module attributes Alembic requires

The Task 4 code block defines only the docstring, `upgrade()`, and `downgrade()` — no
`revision: str = ...`, no `down_revision = ...` assignments (Task 3's template has
them). Alembic reads the module attributes, not the docstring; a pasted file fails with
"Could not determine revision id". The plan also never tells the subagent to scaffold
via `alembic revision -m ...` (which would generate them). Add the attributes to the
template or add the scaffold command.

### MAJOR-4: Task 5's snippet uses `select(...)` — not imported in `background_aggregation.py`

The module imports only `from sqlalchemy import update`. The pasted skip query raises
`NameError` at runtime; the plan never mentions the import. One line in Task 5 Step 3:
"add `select` to the existing `from sqlalchemy import update` import." (Checked the
mirror concern in Task 4: `models/contracts.py` already imports `Integer` for
`ContractItem` — that snippet is fine.)

---

## Q3 — Task 4's backfill and its ordering against Task 3: correct, both ways

Walked both configurations:

- **Separate releases (as planned):** Task 3 flips bad rows to `PENDING_ITEMS`; between
  releases the still-refetch-everything runtime re-enriches them under the *fixed* code
  (Task 1 all-pages + Task 2 invariant are live) and re-marks them `COMPLETED`; Task 4's
  backfill then stamps them `1` — with genuinely good data. Correct.
- **Same release:** repaired rows are `PENDING_ITEMS` at backfill time → excluded →
  stay version 0 → first post-deploy run fetches them (skip doesn't match). Correct.

So yes: backfilling existing `COMPLETED` rows to 1 is right, and it is precisely what
prevents the adoption deploy from being a 46k self-inflicted backfill. One MINOR
tightening: the migration hardcodes `= 1` while the constant is `ENRICHMENT_VERSION = 1`
— add a comment stating the backfill value MUST equal the constant *at ship time*; if
anyone bumps the constant before Phase 2 ships, the backfill re-queues the whole corpus,
the exact cost the step exists to avoid.

---

## Q4 — Cross-task conflicts: none destructive, one unstated assumption

Task 2 and Task 4 both edit `_update_item_processing_status`, and Task 4's snippet
presupposes Task 2's variables — verified compatible: `completed_contract_ids` survives
Task 2's rewrite, so Task 4's `.values(...)` chunk applies cleanly on top. Task 5
touches different functions in the same file; Tasks 1 and 6 touch different functions in
`esi_client_class.py`. **But the plan never states that tasks execute sequentially in
one worktree.** Under subagent-driven-development that is the norm, and the phase
structure implies it — still, one sentence ("tasks are sequential; never dispatch two
tasks touching the same file concurrently") removes the one interpretation that ends in
a destructive merge. MINOR.

---

## Q5 — What's missing entirely

1. **(MAJOR-5) Task 3's verification verifies nothing.** An empty scratch DB prints
   `0 / 0` and the UPDATE matches no rows — the predicate is never exercised. For a
   data-repair migration this is the step that mattered. Add a seeded check with exact
   commands: psql-insert three contracts (COMPLETED + zero items; COMPLETED + exactly
   1,000 items; COMPLETED + 5 items), run `upgrade head`, assert the first two are
   `PENDING_ITEMS` and the third untouched. Cheap, and it also exercises the
   count-log output the plan leans on for the mechanism question.
2. **(MAJOR-6) No PR/merge instructions, and the phase-atomicity constraint (Q6) has no
   mechanism.** See Q6 below.
3. **(MINOR) Deploy-time lock contention:** the repair UPDATE can queue behind a live
   77-minute ingestion transaction; the 30 s `lock_timeout` fail-fast is the established
   pattern and a failed pre-deploy is retryable — acceptable, but worth one sentence in
   Task 3 so the executing agent recognizes the failure as environmental, not a bug.
4. **(MINOR) Task 5 hollows an existing regression test rather than breaking it:**
   `test_reingestion_with_unmodified_items_keeps_ship_flag` (line ~216) still passes,
   but its second-run 304 path becomes unreachable for COMPLETED contracts — after Task
   5 it pins the skip, not the flag-decay regression it names. Note this in the plan so
   a subagent doesn't "fix" it; the 304 path remains live for `ENRICHMENT_INCOMPLETE`
   retries, which is where the decay regression can still occur.
5. **(MINOR) TDD honesty in Task 5 Step 2:** the version-bump test **passes before
   implementation** (pre-skip, everything refetches, so the count increments anyway) —
   only mutation B ever reddens it. The plan says "run both and watch them fail," which
   is false for the second test; a TDD-strict subagent will stall on it. Say explicitly:
   test 1 is the red; test 2 is green-by-construction pre-implementation and is pinned
   by mutation B.
6. **(MINOR) Task 2's log wording:** "left PENDING_ITEMS" is only true for new rows; a
   previously-COMPLETED row that empty-fails on a version-bump refetch stays
   `COMPLETED@old-version` (still correctly retried via version mismatch). Log
   "left un-COMPLETED for retry" instead — the mechanism, not a status name.

Interaction with PR #91 beyond the chain: none — the watermark filters on
`last_seen_at`, the skip filters on status+version; orthogonal. The `NOT EXISTS` branch
of REQUEUE is redundant (count 0 satisfies `% 1000 = 0`) — harmless, keep for
readability. False positives (legitimately exactly-1000×k-item contracts) cost one
re-fetch each — fine.

---

## Q6 — Is phase-1-ships-together enforced? No — asserted twice, enforced nowhere

The constraint appears in prose (Phase 1 header) and the status table ("MUST ship as one
release"), but every task ends in its own commit and the plan contains **no PR, merge,
or release instructions at all** — a subagent finishing Task 2 has nothing stopping it
from opening a per-task PR, and repo policy would also demand a `## Merge
classification` section the plan never mentions (this phase is a clear **Review**
trigger: schema migration + data-integrity path). Also note the constraint's precise
form: merging Tasks 1–3 to `dev` in separate PRs is *compatible* with the requirement —
what must be atomic is the **dev→main publication** (deploys happen only there). Fix
with mechanism, not prose: (a) "Phase 1 is one PR containing Tasks 1–3; classification:
Review — schema migration + data-integrity"; (b) if ever split, "no dev→main publication
may occur between the first and last Phase-1 merge." Put it in the task bodies, where a
subagent reads, not only the phase header.

---

## Q7 — Does Task 5 deliver the win? Yes — walked, with one calibration error in the plan

Path walk: list fetch (unchanged, 34 pages) → name resolution (unchanged) → contract
upsert (unchanged, ~46k rows / ~103 statements) → **skip query** (~46 chunked SELECTs,
correctly placed after the upsert so same-run inserts are visible, correctly keyed on
`COMPLETED` + current version) → `_fetch_item_rows` skips before fetch *and before
`processed_contract_ids.add`*, so skipped contracts are untouched by the status update
and keep their stamp → enrichment fan-out sees only churn items → ship-flag UPDATE only
adds flags (upsert never clears them — pinned by the existing regression test). Nothing
upstream re-fetches items; `ENRICHMENT_INCOMPLETE` rows correctly remain in the fetch
set every run until they succeed. The win is real.

**(MAJOR-7) But the acceptance criterion is miscalibrated:** "duration drops from ~77
minutes to seconds" — steady state still performs the 34-page sweep, ~30 name-resolution
POSTs, the 46k-row contract upsert, ~46 skip-SELECTs, and ~100–250 churn item fetches
(~100 ms each, sequential — concurrency is correctly out of scope). Realistic
steady-state run: **low single-digit minutes**, not seconds. A literal subagent
verifying "seconds" will report the plan failed when it succeeded. Reword: "run duration
under ~5 minutes, and item fetches per run ≈ churn (hundreds), not corpus (~46k)" — the
second clause is the actual proof of the mechanism and is directly observable from the
skip log line the plan adds.

## The split itself

Right call. Plan A is independently shippable and coherent; Task 6 is genuinely
independent (it could even ship first — it is pure hardening). One seam to keep visible:
Plan A deliberately leaves item-page ETag caching ON, so every run still churns ~2×
fetched-contract keys through the 25 MB shared Valkey — small after skip-known (~hundreds
of keys, not 92k), so the pressure mostly dissolves as a side effect, but the *decision*
to remove it stays parked in Plan B and should not silently evaporate there.

---

## Summary table

| # | Rank | Finding | Concrete failure |
|---|------|---------|------------------|
| 1 | BLOCKER | `down_revision c7e2a9b41d36` doesn't exist on this branch (head: `b1c4d7e9f204`; #91 unmerged); no dependency gate; `ls` can't verify a chain | Pre-deploy `alembic upgrade head` fails in production — immediately, or one release later via two heads |
| 2 | BLOCKER | Tasks 1 & 6 test code targets nonexistent `esi_client`/`httpx_mock` fixtures; module idiom is `_etag_response`/`_etag_client`; Task 6 has no escape hatch | Fresh subagent hits collection-time errors and improvises the tests |
| 3 | MAJOR | Task 4 migration template lacks `revision`/`down_revision` module attributes | "Could not determine revision id" on a pasted file |
| 4 | MAJOR | Task 5 snippet uses unimported `select` | NameError at first run |
| 5 | MAJOR | Task 3 verification runs against an empty DB — predicate never exercised | Repair ships untested; a predicate typo reaches production silently |
| 6 | MAJOR | Phase-1 atomicity asserted, not enforced; no PR/merge-classification instructions anywhere | Per-task PRs + an intervening dev→main publication recreate the repair-then-remint window |
| 7 | MAJOR | "77 minutes to seconds" acceptance criterion; reality is low minutes | Executor reports false failure; or worse, "fixes" until a broken metric reads seconds |
| 8 | MINOR | Sequential-execution assumption unstated; version-bump test is green pre-implementation (contradicts "watch them fail"); hollowed 304 regression test; backfill `= 1` / constant coupling; log wording; lock-contention note | Each a small subagent stall or drift, cheap to pre-empt |
