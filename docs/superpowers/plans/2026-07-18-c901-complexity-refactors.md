# C901 Complexity Refactors Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Pay down the five functions suppressed with `# noqa: C901` in PR #47 (backend lint debt), reducing each to McCabe complexity ≤ 10 and removing its noqa, with zero behavior change proven by characterization tests (two documented exceptions: one retry-warning log prefix in Task 4.2, and the ETag-path byte/str cache-client normalization fix in Task 5.2a).

**Architecture:** One phase per function, one PR per phase, each branched off fresh `origin/dev`. Every phase follows the same shape: (a) add characterization tests that lock the CURRENT behavior — including error paths — and pass against the unrefactored code; (b) extract helpers until the function measures ≤ 10; (c) remove the `# noqa: C901`; (d) prove lint + full suite green. Phases 2 and 3 touch the same file and MUST be sequential; Phase 5 depends on a helper introduced in Phase 4.

**Tech Stack:** Python 3.14, FastAPI, SQLAlchemy 2.0 async, pytest + pytest-asyncio + pytest-httpx, flake8 + mccabe (max-complexity = 10), flake8-bugbear (active since PR #48).

---

## Living Document Contract

This plan is a living document. Every executing agent MUST update it as
execution progresses, not only at completion.

- **On phase claim:** the executor MUST flip the banner to 🚧 IN PROGRESS
  with a claim timestamp (ISO 8601 UTC) and the active branch name. The
  banner MUST NOT include an expected-completion estimate — agents cannot
  reliably estimate their own wall-clock, and a fabricated duration
  becomes a stale anchor that misleads future readers. Followers
  encountering a 🚧 banner determine liveness by observable signals (PR
  existence, recent branch commits), not by arithmetic on expected times.
  See the stale-claim reclaim protocol in
  `superpowers-plus:writing-plans-enhanced` Step 5.
- **On phase ship:** the executor MUST update that phase's **Execution
  Status** banner with the shipped commit SHA(s) and date. If a PR is
  open, the PR number and URL MUST appear in the top-of-plan Execution
  Status table.
- **On phase defer:** the executor MUST update the banner with ⏸ status
  AND a prose description of the unblock condition + a link to the
  likely-unblocker artifact (plan page, task, or PR whose own Execution
  Status banner will signal completion). Prose + link is durable across
  paraphrases and scope edits; exact-string coordination between agents
  is not.
- **On PR merge:** the executor MUST record the merge SHA in the banner
  + the top-of-plan Execution Status table.
- **On deviation from the written plan** (scope edits, structural
  refactors, dropped tasks, reordered phases): the executor MUST
  inline-document the deviation in the affected task AND summarize it
  in the top-of-plan Execution Status as a "Deviations" subsection.
  Deviation state MUST NOT live only in PR notes or status reports.
- **On discovery** (pre-existing drift surfaced during execution, new
  bugs found, architectural issues noted): the executor MUST add a
  "Discoveries" subsection at the top of the plan with pointers to the
  files/lines affected. Follow-up dispatches read this subsection to
  avoid duplicate discovery work.

The plan SHOULD reflect reality at the end of every session that touches
it. Anything worth putting in a status report to the user is worth
putting in the plan.

Rationale: `/writing-plans-enhanced` Step 5. Writing at ship time is
cheap; reconstruction by downstream readers is expensive, compounds
across dispatches, and fails silently when state is split across PR
notes and commit messages.

---

## Execution Status

**Overall:** In progress — Phase 1 shipped; Phase 2 claimed 2026-07-18.

**Baseline at Phase 1 claim** (branch point `bfaf495`, fresh `origin/dev`): `pdm run pytest` = **358 passed**; `pdm run lint` = exit 0; `grep -rn "noqa: C901" src/` = the 5 expected sites.

**Baseline at Phase 2 claim** (branch point `e84aa8a`, `origin/dev` after Phase 1 merged): `pdm run pytest` = **362 passed**; `pdm run lint` = exit 0; 4 `# noqa: C901` sites remain.

| Phase | Status | Ship SHA(s) | Notes |
|---|---|---|---|
| 1 — get_contracts | ✅ Merged | `69b0112`, `3d4e61e`, `1ca0aa0`, `7ae0576`, `63e5ddb`, `bca290b` → merge `e84aa8a` | PR #54, merged 2026-07-18; complexity 20 → 7; suite 358 → 362 |
| 2 — _process_contracts | ✅ Merged | `455f586`, `6bd9f63`, `8962daf`, `656a383`, `bca8d00` → merge `c271f19` | PR #57, merged 2026-07-18; complexity 18 → 7; suite 362 → 365 |
| 3 — run_aggregation | ✅ Merged | `9cbafc8`, `433eb9a`, `467f6f3`, `516f8ed`, `939d561` → merge `727d84f` | PR #62, merged 2026-07-19; **redone against a base rewritten by PR #60 — see Deviations**; complexity 16 → 8; suite 416 → 423 |
| 4 — _get_esi_object + shared retry helper | ✅ Merged | `4c4e158`, `402658a` → merge `e5d304d` | PR #59, merged 2026-07-19; complexity 16 → 9; introduced `_get_with_transient_retry` (8) |
| 5 — get_esi_data_with_etag_caching | 🚧 PR #68 open | `e25883c`, `fc17fdf`, `7122d98` | branch `claude/c901-etag-caching`; complexity 24 → 9; **clears the last suppression**; `Review — data-integrity`, **Sam merges** |

### Deviations

**Phase 3 was redone from scratch against a rewritten base (2026-07-19).** The first attempt
(branch `claude/c901-run-aggregation`, PR #62) was built against `run_aggregation` as it existed at
`f206399`. While that PR sat in review, **PR #60 (M4 phase-3 prod hardening) rewrote the function**:
the per-run `create_async_engine`/`sessionmaker`/`engine.dispose()` lifecycle was replaced by the app's
`AsyncSessionLocal()` factory, `regions_ok`/`regions_failed` counters were added, `_record_run_outcome`
now writes a Valkey freshness record (including a `forced_failure=True` call on the processing/commit
abort path), and an `ESINotModifiedError` arm was added to the region loop counting a 304 region as OK.
Complexity moved 14 → 16.

That made the first attempt's conflicts **substantive rather than textual**. Its `_fetch_regions`
returned only a list, so applying it would have DROPPED the new counters — an observability regression
in code PR #60 had just added — and two of its tests (engine disposal, `create_async_engine`/
`sessionmaker` monkeypatching) targeted machinery that no longer exists. PR #62 was therefore closed
unmerged rather than force-resolved, and Phase 3 was redone on `claude/c901-run-aggregation-v2` off
`e80103a`. Carried over unchanged: the two guard characterization tests and the TEST-12 pitfall entry.
Redone: `_fetch_regions` now returns `(contracts, regions_ok, regions_failed)`; its tests assert the
counters, the 304-counts-as-OK arm, and per-region stamping across two successful regions.

**Phase 3's Task 3.1 scoping note (below) is now OBSOLETE.** It argued that end-to-end
characterization of the middle section was impractical because of the dynamically created engine. That
engine is gone, and PR #60 shipped four `test_freshness_*` tests that already exercise `run_aggregation`
end-to-end through a `FakeLockRedis` and a real session factory, asserting the counter values that land
in the Valkey record. The section was already characterized. This turned out to help: the counter
mutations below went red at BOTH the new unit layer and those pre-existing end-to-end tests.

**One accepted micro-deviation in the redo — an earlier "unreachable" claim here was WRONG.** The
counters previously incremented in place, so an exception escaping mid-loop left the `forced_failure`
handler with partial counts; with `_fetch_regions` returning a tuple, the assignment never happens and
the handler sees `0, 0`. This plan first asserted that difference was unreachable, reasoning that the
loop's bare `except Exception` swallows everything the outer handler would catch. **A codex review
falsified that**: an exception raised *inside* an `except` arm's own body — realistically, logging or
filter machinery failing — escapes `_fetch_regions` and reaches the outer handler, so the freshness
record would carry `0, 0` where the inline version carried partial counts.

Accepted rather than fixed. It is reachable only when logging itself is broken, the recorded outcome is
`failure` either way (only the region tallies differ), and every alternative that preserves partial
counts across the call boundary (out-params, a mutable accumulator, a counter object) adds structural
complexity to the exact function being decomposed for complexity. Recorded as a known micro-deviation
from the zero-behavior-change contract. `CancelledError` and other `BaseException`s escape both
versions identically and record no outcome in either. Worth revisiting if that `except Exception` is
ever narrowed, or if a counter object is wanted for other reasons.

**Phase 3 mutation evidence (persisted per TEST-12 — a review noted the discipline was claimed but the
evidence was not written down anywhere durable).** Each mutation was applied to production source, run,
observed red, then reverted; production source verified byte-identical afterward.

| Mutation | Observed failure |
|---|---|
| generic `except` arm → `regions_ok += 1` | red at BOTH layers: unit `assert 2 == 1`, and pre-existing e2e freshness `assert 'success' == 'partial'` |
| `ESINotModifiedError` arm → `regions_failed += 1` | red at both layers: `assert 'failure' == 'success'` |
| stamp over the accumulated list instead of per page | `{920003: 10000043} != {920003: 10000002}` |
| `_apply_dev_limit` returns input unchanged | `assert [920005, 920006, 920007] == [920005, 920006]` |
| both `logger.*` calls → `pass` | both `caplog` assertions red against `''` — the log assertions are not decorative |
| skip stamping the FIRST region only | **passed before the fixture fix (the vacuity), red after**: `{920003: -1} != {920003: 10000002}` |
| `None` coerced to a default dev limit | `assert [920011, 920012] == [920011, 920012, 920013]` |
| drop the `all(isinstance(x, int) ...)` guard clause | new guard test red; log shows the real consequence — `Failed to fetch contracts for region not-an-int` |

**Phase 1, Task 1.1 — the plan's tiebreaker test as written was vacuous; its fixture was reshaped.**
`test_joined_pagination_tiebreaks_equal_sort_keys_by_contract_id` was specified with a normative body
in Task 1.1. Written exactly as specified, it passed against BOTH of the mutations it claimed to
guard against: deleting `Contract.contract_id.asc()` from the joined `id_query`, and merging
`_fetch_page_joined` into `_fetch_page_simple` (the change non-negotiable ground rule 4 forbids). Two
review lenses independently mutation-tested it and converged on this. Root causes: each contract
carried exactly ONE matching `ContractItem`, so the join produced no duplicated rows for SQLA-1 to
bite on; and the fixture inserted `930001` before `930002`, so heap order accidentally matched the
asserted order. Fix (commit `1ca0aa0`, test file only): contract 930001 now carries 2 matching items
(joined row count 3 > contract count 2), rows are inserted in descending contract_id order, the sort
key moved from `price` to `ship_name` so the tie is on the aggregated item column, and TEST-4
partition assertions were added (union of pages == full set, intersection empty). Test name and the
plan's normative assertions are unchanged.

**Residual limit, documented rather than faked:** the tiebreaker-removal mutation still cannot be made
red at this fixture size. `EXPLAIN` shows Postgres feeds the final sort from a `GroupAggregate` that is
already sorted by `contract_id`, so tied keys emerge contract_id-ascending whether or not the
tiebreaker exists; descending inserts, 3 contracts, item-column sorts, and forcing `HashAggregate` via
`enable_sort=off` were all tried and all still returned ascending. The tiebreaker IS covered — by the
pre-existing `tests/api/test_contract_filters.py::test_pagination_sorted_by_ship_name_no_duplicates`,
which does go red under that mutation. The test's docstring now states what it locks (SQLA-1
joined-row pagination + TEST-4 partition), what it does not (the tiebreaker), and where the tiebreaker
is actually covered. The rejected alternative was asserting on the compiled `ORDER BY` SQL text, which
tests SQL strings rather than behavior.

**Phase 1, Task 1.2 — two annotation-level deviations from the normative helper signatures.**
(a) `_needs_item_join` wraps its expression in `bool()`; the original assigned a raw truthy value, and
the plan's normative signature declares `-> bool`. Consumed only by `if`, so no caller can observe it.
(b) `_fetch_page_simple` keeps the plan's normative `-> list[Contract]` annotation but returns a
SQLAlchemy `Sequence`. Inserting `list(...)` would have been a real (if tiny) behavior change, so the
statement was moved verbatim and the loose annotation kept. No caller performs list-specific
operations. `_fetch_page_joined`'s annotation is honest — its position-restoration step builds a real
`list` — so this applies to the simple path only.

**Phase 2 — one test added beyond the plan's task spec (`8962daf`).** Task 2.2 converted
`id_to_name_map` from a closure-captured local into an explicit parameter of the new module-level
`_build_contract_rows(contracts, id_to_name_map)`. That created a call-site wiring seam the plan did
not anticipate and no test covered: mutating the call site to pass `{}` left the ENTIRE suite green,
so name denormalization could break silently. Phase 1's review found the same defect class (and the
plan-review notes flag "orchestration wiring tests" as recurring), so it was closed rather than
deferred: one test pins all three denormalized columns (`start_location_name`, `issuer_name`,
`issuer_corporation_name`) through the full build-and-upsert path, mutation-verified to go red when
the map is emptied. Note the adversarial review round REFUTED this finding as a pre-existing coverage
gap; that is half right — the gap predates the diff, but the wiring error it now permits does not.

### Discoveries

**Ingestion failure observability — largely addressed by PR #60; a bounded residual remains
(2026-07-19, codex-reviewed).** An earlier revision of this section claimed `run_aggregation` swallows
total ingestion failure with no signal beyond one log line. **That is now stale**: PR #60's
`_record_run_outcome` writes a Valkey freshness record with `outcome` (success/partial/failure),
`regions_ok`/`regions_failed`, `finished_at`, and a preserved `last_success_at`, plus a
`forced_failure=True` record on the processing/commit abort path, and advances a Prometheus gauge.
An operator can now distinguish a failed run from a successful one.

An independent codex review (high effort) confirmed the broad concern is dead and identified the
bounded residual, **none of which is in scope for this refactor plan** — recorded here for the
observability backlog:

- `run_aggregation` still `return`s rather than re-raising, so APScheduler emits no job-error event.
  Codex notes a fix requires changing BOTH `run_aggregation` and the `run_aggregation_job` wrapper,
  since the wrapper also swallows. Its recommendation: re-raise unexpected fatal failures, while
  keeping lock contention and isolated per-region failures as normal returns.
- **Outcome-free failure paths exist**: a failure before the lock is acquired (reading
  `AGGREGATION_REGION_IDS`, redis client construction, the lock `SET`) produces no outcome record at
  all. Real but bounded; scheduler propagation is the dependable fix, since a fallback record through
  a second redis client cannot survive a failure caused by redis itself.
- `/ready` exposes the freshness fields but **still returns HTTP 200 for stale or failed ingestion** —
  readiness status is not actually derived from them. (This corrects an assumption stated earlier in
  this plan's own PR notes.) There is also no failure counter/metric and no alert.

Two findings about `_record_run_outcome` itself, also from that review:

- The `GET`/`SET` update is **neither atomic nor fenced**. If the lock TTL expires and runners overlap,
  a failure writer can overwrite a newer `last_success_at` with an older value.
- The Prometheus gauge update sits **inside the same `try` as the Valkey write**, so a Valkey outage
  needlessly prevents the independent gauge from advancing.
- `success` does not mean complete ingestion: the classification covers region fetch and the
  transaction, not item-fetch or enrichment failures.

**Concurrent pytest runs clobber the shared test database.** `pdm run pytest` drops and recreates the
database named by `DATABASE_URL_TESTS`; isolation comes from per-run drop/recreate, not per-test
rollback. Two agents running the suite simultaneously produce spurious `IntegrityError` / `DROP TABLE`
failures that look like real test defects. Reviewers doing mutation testing must serialize, or point
their own `DATABASE_URL_TESTS` at a scratch database. This bit the Phase 1 review round (2026-07-18)
and cost one reviewer several confusing runs before it was diagnosed.

**CORRECTED — contracts at `PENDING_ITEMS` recover on their own; no retry sweep is needed.** An
earlier revision of this entry (and PR #57's body) claimed a transient item-fetch failure strands a
contract "until its next full re-ingest happens to succeed", and asked whether a retry sweep was
wanted. **That claim was wrong and is retracted.** Verified 2026-07-18 by reading the loop and then
proving it empirically:

- `_fetch_item_rows` gates ONLY on `contract["type"] not in ["item_exchange", "auction"]`. There is no
  status gate. Every run re-fetches items for every eligible contract in the batch, so a contract left
  at `PENDING_ITEMS` is retried by the very next aggregation run with no machinery at all.
- `test_failed_item_fetch_recovers_on_the_next_run` pins this: run 1 fails the fetch (status stays
  `PENDING_ITEMS`), run 2 succeeds (status becomes `COMPLETED`, items land). Mutation-verified — adding
  a plausible once-per-contract skip strands the contract and turns the test red.

**Decision: no retry sweep.** It would be machinery for a problem that does not exist, and it would key
off a column that currently signals nothing to anyone (see the next entry).

**`item_processing_status` is a write-only column.** Nothing reads it — not the API layer, not the
frontend, not any query, not any retry logic. `grep` over `src/` outside tests finds only the model
definition (`models/contracts.py:65`, which also carries `index=True`) and the three write sites in
`background_aggregation.py`. So the column, and the index backing it, currently cost writes and space
while informing no consumer. Not deleted here (out of scope, and it is plausibly intended for future
ops/observability) — but if no reader is planned, the column and its index are dead weight.

**`ESINotModifiedError` handlers are unreachable.** The exception is defined
(`core/exceptions.py:19`), imported, and caught in TWO places (`background_aggregation.py:239` and
`:373`) — but it is **raised nowhere in the codebase**. `get_esi_data_with_etag_caching` serves a 304
from cache rather than raising. Both `except ESINotModifiedError:` arms are therefore dead code, and
the `logger.info("Items for contract ... not modified.")` line can never fire. Relevant to Phase 5,
whose 304 characterization tests will confirm the serve-from-cache path. Recorded, not removed.

**Backend tests are excluded from flake8.** `app/backend/.flake8` line 24 carries
`exclude = .venv,.git,__pycache__,docs,migrations,*/tests/*,src/alembic`,
so `pdm run lint` does NOT cover test code. Style in test files is convention-enforced only; do not
assume a green lint says anything about new tests.

**`_apply_contract_filters` measures exactly 10 — at the C901 limit.** The plan's contingency
(`_apply_location_filters`) was correctly NOT applied, since the plan says do not preemptively split
and the measurement is not > 10. But the next filter added to `get_contracts` will break the build.
Whoever adds it should apply the documented contingency at that time.

---

## Ground rules for every phase (read before any task)

1. **Worktree + branch.** Create a worktree per `superpowers:using-git-worktrees` / CLAUDE.md convention: `git worktree add .claude/worktrees/<slug> -b <branch>` off **fresh** `origin/dev` (`git fetch origin dev` first). Branch names use the agent namespace per `docs/git-strategy.md`: `claude/c901-<function-slug>` (e.g. `claude/c901-get-contracts`). Commit types stay `test`/`refactor` per rule 10.
1a. **Dev-env bootstrap (fresh worktree).** `cd app/backend && pdm install -G dev`. The env file lives at `app/backend/src/.env` (NOT `app/backend/.env`) and is gitignored — copy it from a sibling worktree (`ls /path/to/repo/.claude/worktrees/*/app/backend/src/.env`, take the newest; stale M1-era copies lack required fields and fail Settings validation). Start DB/cache deps before pytest: `docker compose -f docker/compose.yml -f docker/compose.dependencies.yml up -d --wait postgres_db valkey_cache` (from `app/backend/`).
2. **Characterization-first, adapted TDD.** These are refactors, so the red→green cycle is split in two:
   - *Tests*: new characterization tests MUST pass against the UNREFACTORED code first. A characterization test that fails against current code means you guessed behavior instead of reading it — fix the test, not the code.
   - *Refactor gate*: BEFORE extracting helpers, delete the `# noqa: C901` and run `pdm run lint` — it MUST fail with the expected C901 line (this is the "red"). After extraction, lint MUST exit 0 (the "green"). Restore the noqa if you pause mid-phase; never commit a red lint.
3. **BEFORE starting work** on any task: invoke `superpowers:test-driven-development`, and read `docs/pitfalls/testing-pitfalls.md` and `docs/pitfalls/implementation-pitfalls.md`. Pitfalls that WILL bite here: ENV-2/ENV-3 (every backend `.py` save under `pdm run dev --reload` wipes the DB — do not run the dev server while editing; the test suite manages its own DB), TEST-7 (error-state tests must exhaust retries).
4. **Zero behavior change is the contract.** Helpers are extracted verbatim wherever possible: same statements, same order, same log messages (message strings are observable behavior — tests and operators grep them), same exception types and messages. TWO documented exceptions exist in the whole plan, each accepted where defined, called out in its PR body, and permitted nowhere else: Task 4.2's retry-helper consolidation changes the object variant's retry-warning prefix ("ESI object request to …" → "ESI request to …"), and Task 5.2a hardens the ETag path's cached-etag read to tolerate str-valued cache clients (a Sam-directed fix for a verified latent bug, TDD'd as its own commit). If you believe you found a bug in current behavior, do NOT fix it silently: record it under Discoveries, keep the characterization test locking CURRENT behavior, and flag it in the PR body.
5. **No API changes.** Every extracted helper is module-private (`_` prefix) or a private method. Public signatures (`get_contracts`, `run_aggregation`, `get_esi_data_with_etag_caching`, `get_public_contracts`, `get_contract_items`, `get_universe_type`, `get_universe_group`) MUST NOT change.
6. **Complexity check command.** `cd app/backend && .venv/bin/flake8 --select=C901 src/fastapi_app/<file>` — empty output means every function in the file is ≤ 10.
7. **BEFORE marking any task complete:** review new tests against `docs/pitfalls/testing-pitfalls.md`; verify error paths and edge cases are covered; run the phase's test file AND `pdm run lint` AND the full `pdm run pytest` and confirm green.
8. **Assertion rigor.** If any test assertion races, flakes, or fails nondeterministically, the fix is deterministic synchronization or deterministic fakes (e.g. monkeypatched `asyncio.sleep`, pytest-httpx response queues) — NOT assertion removal or weakening. If synchronization cannot make the assertion pass reliably, STOP and raise to the dispatching agent. Do not ship a weaker test. Weakened assertions rationalized as "CI stability fixes" are the exact pattern this rule prevents. Prefer mechanism assertions (e.g. "3 requests were made, backoff slept twice") over symptom assertions (elapsed-time bounds).
9. **After completing each phase:** review the batch from multiple perspectives (behavior preservation, test quality, complexity actually ≤ 10, no public-API drift). Minimum 3 review rounds; if round 3 still finds issues, keep going until clean. Then PR to `dev` with a `## Merge classification` heading, codex adversarial review (`/codex review`), and merge per `docs/git-strategy.md` §Merge authority. **Classification is per-phase, not blanket:** Phase 1 = `Routine — auto-merge on green CI` (read-path query construction; the full literal form is required by git-strategy §Opening-agent classification). Phases 2, 3, 4, 5 = `Review — data-integrity (ingestion pipeline refactor)`: they modify contract ingestion, database writes/status updates, and the ESI transport feeding them, which is a Domain trigger regardless of the refactor's intent to preserve behavior — Sam merges those, the agent does not.
10. **Commit style:** Conventional Commits, e.g. `test(api): characterize get_contracts error path` / `refactor(api): extract get_contracts filter helpers to clear C901`.

---

## Phase 1 — `get_contracts` (complexity 20 → ≤ 10)

**Execution Status:** ✅ MERGED 2026-07-18 — PR #54, merge commit `e84aa8a`, branch `claude/c901-get-contracts`.
Commits `69b0112` (characterization tests), `3d4e61e` (extraction), `1ca0aa0` (mutation-sensitivity fix
for the tiebreaker fixture — see Deviations). Gates: red gate observed
(`C901 'get_contracts' is too complex (20)`); after extraction `pdm run lint` exit 0,
`--select=C901` empty, `get_contracts` 20 → 7, `_apply_contract_filters` 10, `_apply_item_filters` 5;
full suite 358 → 362 passed; 4 `# noqa: C901` remain (Phases 2-5).

**Files:**
- Modify: `app/backend/src/fastapi_app/services/contract_service.py`
- Test: `app/backend/src/fastapi_app/tests/services/test_contract_service.py`

**Context.** `get_contracts(db, filters)` builds one dynamic query: join decision → ~13 conditional filters → distinct count → early return on 0 → sort resolution → two pagination strategies (joined = group_by over IDs then reload; simple = direct offset/limit) → success/failure `log_key_event` + re-raise. Existing tests (11) cover filters/sort/pagination against a real DB via the `setup_contracts` fixture. NOT covered: the exception path (lines with `log_key_event(success=False, ...)` then `raise`), the `total == 0` early return, and the joined-pagination tiebreaker ordering.

### Task 1.1: Characterization tests for the uncovered paths

- [ ] **Step 1: Write the tests** (append to `test_contract_service.py`, matching its fixture style):

```python
async def test_zero_results_returns_empty_page(db_session: AsyncSession, setup_contracts):
    filters = ContractFilters(search="no-such-ship-name-anywhere", page=1, size=10)
    result = await get_contracts(db_session, filters)
    assert result.total == 0
    assert result.items == []
    assert result.page == 1
    assert result.size == 10


async def test_unmapped_sort_falls_back_to_date_issued(db_session: AsyncSession):
    # sort_by is NON-optional in the schema (default SortableContractFields.date_issued,
    # sort_direction default desc), so SORT_MAP.get(filters.sort_by) can only return
    # None if validation is bypassed — the fallback branch is defensive. Characterize
    # it via model_construct (skips VALIDATION; declared defaults ARE still
    # populated, so only the override needs passing), the one seam that reaches it.
    #
    # TEST-3: do NOT use setup_contracts here — its date_issued values are
    # independent datetime.now() calls (nondeterministic, possibly equal).
    # Insert three contracts with FIXED, strictly distinct date_issued values in
    # a region id no other fixture uses, mirroring the fixture's field set:
    # contract_ids 940001/940002/940003 with date_issued 2026-07-01/02/03 (UTC),
    # start_location_region_id=99999901, no items.
    filters = ContractFilters.model_construct(sort_by=None, region_ids=[99999901])
    result = await get_contracts(db_session, filters)
    # Fallback = Contract.date_issued, default direction desc, contract_id tiebreak:
    assert [item.contract_id for item in result.items] == [940003, 940002, 940001]


async def test_db_error_logs_failure_and_reraises(db_session: AsyncSession, setup_contracts, monkeypatch):
    # Pins the except branch: log_key_event(success=False, error_message=...)
    # fires and the original exception propagates unchanged.
    events = []
    real_log_key_event = contract_service.log_key_event

    def recording_log_key_event(*args, **kwargs):
        events.append(kwargs)
        return real_log_key_event(*args, **kwargs)

    monkeypatch.setattr(contract_service, "log_key_event", recording_log_key_event)

    async def boom(*args, **kwargs):
        raise RuntimeError("simulated db failure")
    monkeypatch.setattr(db_session, "execute", boom)

    filters = ContractFilters(page=1, size=10)
    with pytest.raises(RuntimeError, match="simulated db failure"):
        await get_contracts(db_session, filters)

    failure_events = [e for e in events if e.get("success") is False]
    assert len(failure_events) == 1
    assert "simulated db failure" in failure_events[0]["error_message"]


async def test_joined_pagination_tiebreaks_equal_sort_keys_by_contract_id(db_session: AsyncSession, setup_contracts):
    # SQLA-1 net: with the item join active (search filter) and EQUAL sort keys,
    # pages must split deterministically on the contract_id ASC tiebreaker, with
    # no contract skipped or repeated across the boundary (TEST-4). Insert two
    # contracts with IDENTICAL price whose items both match one search term —
    # follow the setup_contracts fixture's insert idiom for Contract+ContractItem
    # rows (read it first), using contract_ids 930001 and 930002, price 500.0,
    # and an item type_name both matching search="tiebreakship".
    filters_p1 = ContractFilters(search="tiebreakship", sort_by=SortableContractFields.price,
                                 sort_direction=SortDirection.asc, page=1, size=1)
    filters_p2 = filters_p1.model_copy(update={"page": 2})
    page1 = await get_contracts(db_session, filters_p1)
    page2 = await get_contracts(db_session, filters_p2)
    assert page1.total == 2 and page2.total == 2
    assert [c.contract_id for c in page1.items] == [930001]
    assert [c.contract_id for c in page2.items] == [930002]
```

(Read `fastapi_app/schemas/contracts.py` before finalizing the `model_construct` call to confirm field names. Required imports for these tests, added at the top of the test file if absent: `import fastapi_app.services.contract_service as contract_service` — so `log_key_event` can be monkeypatched at its use site — plus `SortDirection` and `SortableContractFields` from `fastapi_app.schemas.contracts`.)

- [ ] **Step 2: Run them against UNREFACTORED code** — `pdm run pytest src/fastapi_app/tests/services/test_contract_service.py -v`. Expected: ALL PASS. If any fail, the test is mischaracterizing current behavior; fix the test.
- [ ] **Step 3: Commit** — `test(api): characterize get_contracts zero-result, sort-fallback, and error paths`

### Task 1.2: Red gate, then extract helpers

- [ ] **Step 1: Red gate.** Remove `  # noqa: C901` from the `async def get_contracts(` line. Run `pdm run lint`. Expected: exactly one failure — `C901 'get_contracts' is too complex (20)`.
- [ ] **Step 2: Extract these module-level helpers** (verbatim statement moves; signatures below are normative):

```python
def _needs_item_join(filters: ContractFilters) -> bool:
    # body: the existing `needs_item_join = (...)` boolean expression, returned directly

def _apply_contract_filters(query, filters: ContractFilters):
    # body: the existing blocks for: search (the or_ over title/type_name),
    # min/max price, min/max collateral, is_ship_contract, region/system/station
    # id filters — in the same order; returns query

def _apply_item_filters(query, filters: ContractFilters):
    # body: the existing blocks for type_ids, is_bpc, min_runs, max_runs; returns query

async def _count_distinct_contracts(db: AsyncSession, query) -> int:
    # body: the existing count_subquery/count_query/scalar_one lines

async def _fetch_page_joined(db: AsyncSession, query, filters, sort_column, descending) -> list[Contract]:
    # body: the existing group_by/id_query/page_ids/data_query/position-sort block

async def _fetch_page_simple(db: AsyncSession, query, filters, sort_column, descending) -> list[Contract]:
    # body: the existing direct order_by/offset/limit/selectinload block
```

`get_contracts` keeps: start log, try, query construction calling the helpers, count + `total == 0` early return, sort resolution (`SORT_MAP.get` + fallback + `descending`), the joined-vs-simple branch calling the two fetch helpers, response build, success `log_key_event`, and the except block verbatim. Do NOT change any log message text or the `log_key_event` payload dicts. Do NOT rename `SORT_MAP` or alter its security comment.

**Pitfall SQLA-1 boundary (implementation-pitfalls.md).** The `_fetch_page_joined` body IS the fix for SQLA-1 (paginating a joined one-to-many query paginates duplicated rows — short pages, skipped/repeated contracts). Do NOT "simplify" it to a direct offset/limit on the joined query, do NOT drop the aggregate-based ordering or the `contract_id` tiebreaker, and do NOT merge the two fetch paths. Move the block verbatim, including its explanatory comment.

**Complexity contingency.** `_apply_contract_filters` lands at exactly 10 by straight counting (9 `if`s). If mccabe measures it 11 for any reason, split the three location-id filters into `_apply_location_filters(query, filters)` — do not restructure anything else.

- [ ] **Step 3: Green gates.** `pdm run lint` → exit 0 (no noqa present). `.venv/bin/flake8 --select=C901 src/fastapi_app/services/contract_service.py` → empty. `pdm run pytest` → full suite green (baseline count from `dev` at phase start; record it in this plan when claiming the phase).
- [ ] **Step 4: Commit** — `refactor(api): extract get_contracts query helpers to clear C901`

### Task 1.3: Phase review + PR

- [ ] Three review rounds (behavior preservation diff-read; test quality vs testing-pitfalls; complexity + API surface). Fix anything found; repeat until a clean round.
- [ ] PR to `dev` titled `refactor(api): reduce get_contracts complexity below the C901 budget`, Merge classification `Routine — auto-merge on green CI`, `/codex review`, merge on green CI. Update this plan's banners + table.

---

## Phase 2 — `_process_contracts` (complexity 18 → ≤ 10)

**Execution Status:** 🚧 PR OPEN — branch `claude/c901-process-contracts`, claimed 2026-07-18T23:25Z off
`origin/dev` at `e84aa8a`. Commits `455f586` (characterization tests), `6bd9f63` (extraction),
`8962daf` (name-denormalization wiring test — see Deviations). Gates: red gate observed
(`C901 'ContractAggregationService._process_contracts' is too complex (18)`); after extraction
`pdm run lint` exit 0, `_process_contracts` no longer flagged by `--select=C901`, complexity 18 → 7
(`_fetch_item_rows` 6, `_update_item_processing_status` 4, `_collect_resolvable_ids` 2,
`_parse_esi_datetime` 2, `_build_contract_rows` 1); full suite 362 → 365 passed. `run_aggregation`
keeps its own noqa for Phase 3, untouched. Classification `Review — data-integrity` — Sam merges.

**Files:**
- Modify: `app/backend/src/fastapi_app/services/background_aggregation.py`
- Test: `app/backend/src/fastapi_app/tests/services/test_background_aggregation.py`

**Context.** `_process_contracts(db_session, contracts)` is already staged by comments: collect IDs → filter structure IDs (the keep-condition is `id < 100_000_000_000`, i.e. IDs ≥ 10^11 are dropped) → resolve names → build contract rows → batched contract upsert → per-contract item fetch loop (with `ESINotModifiedError` and generic-exception isolation) → item enrichment (`_enrich_items_and_find_ships`, already a helper) → batched item upsert → ship-flag updates → `item_processing_status` COMPLETED/ENRICHMENT_INCOMPLETE updates. Existing coverage is strong (region stamp, ship flags, degradation, chunk boundary, bpc flag). NOT covered: the structure-ID filter log line and the per-contract item-fetch failure isolation (one contract's fetch exception must not abort the batch).

### Task 2.1: Characterization tests for the uncovered seams

- [ ] **Step 1: Write the tests** (append to `test_background_aggregation.py`; they reuse the file's `_make_service()` + `db_session` idioms and the contract-dict shape from `test_process_contracts_persists_fetch_region_id`; the universe-type/group stub shapes mirror `test_process_contracts_flags_ships_and_resolves_type_names` — read that test and match its exact stub dicts before running):

```python
async def test_item_fetch_failure_for_one_contract_does_not_abort_batch(db_session: AsyncSession):
    """One contract's item fetch raising must not prevent the other contract's
    items from landing, and the failed contract must never be marked processed."""
    service = _make_service()

    async def items_side_effect(contract_id):
        if contract_id == 910001:
            raise RuntimeError("simulated ESI items failure")
        return [{"record_id": 21, "type_id": 587, "quantity": 1, "is_included": True}]

    service.esi_client.get_contract_items = AsyncMock(side_effect=items_side_effect)
    service.esi_client.get_universe_type = AsyncMock(
        return_value={"name": "Rifter", "group_id": 25, "market_group_id": 64}
    )
    service.esi_client.get_universe_group = AsyncMock(
        return_value={"name": "Frigate", "category_id": 6}
    )
    contracts = [
        dict(_ship_contract_dict(910001)),
        dict(_ship_contract_dict(910002)),
    ]

    await service._process_contracts(db_session, contracts)

    item_rows = (
        await db_session.execute(
            select(ContractItem).where(ContractItem.contract_id == 910002)
        )
    ).scalars().all()
    assert len(item_rows) == 1  # the healthy contract's items landed

    failed_row = (
        await db_session.execute(
            select(Contract).where(Contract.contract_id == 910001)
        )
    ).scalar_one()
    healthy_row = (
        await db_session.execute(
            select(Contract).where(Contract.contract_id == 910002)
        )
    ).scalar_one()
    # The model default is 'PENDING_ITEMS' (models/contracts.py) — a contract
    # whose item fetch failed keeps the default, it is NEVER marked COMPLETED
    # or ENRICHMENT_INCOMPLETE (both require membership in processed ids).
    assert failed_row.item_processing_status == "PENDING_ITEMS"
    assert healthy_row.item_processing_status == "COMPLETED"


async def test_structure_ids_are_excluded_from_name_resolution(db_session: AsyncSession, caplog):
    """The resolvable-ID cut is `id < 100_000_000_000` (10^11): player-structure
    IDs at or above 10^11 are unresolvable via /universe/names/ and are filtered
    out of the resolve batch (name column stays NULL). Pin BOTH sides of the
    boundary so an off-by-one in the extracted helper cannot slip through."""
    caplog.set_level("INFO")  # the filter log is INFO; default capture level misses it
    service = _make_service()
    contract = dict(_ship_contract_dict(910003))
    contract["start_location_id"] = 99_999_999_999       # last resolvable id
    contract["end_location_id"] = 100_000_000_000        # first excluded id
    contract["type"] = "courier"  # skip the item-fetch loop entirely

    await service._process_contracts(db_session, [contract])

    resolved_ids = service.esi_client.resolve_ids_to_names.await_args.args[0]
    assert 99_999_999_999 in resolved_ids
    assert 100_000_000_000 not in resolved_ids
    assert "Filtered out 1 unresolvable structure IDs." in caplog.text
    row = (
        await db_session.execute(
            select(Contract).where(Contract.contract_id == 910003)
        )
    ).scalar_one()
    assert row.start_location_name is None  # 99999999999 resolves to nothing in the stub map
```

(Characterization gate applies: if either fails against current code, the fixture shape is wrong — compare against the neighboring tests, fix the test.)

- [ ] **Step 2: Run against UNREFACTORED code** — expected ALL PASS.
- [ ] **Step 3: Commit** — `test(api): characterize _process_contracts failure isolation and structure-id filtering`

### Task 2.2: Red gate, then extract helpers

- [ ] **Step 1: Red gate.** Remove the noqa from `async def _process_contracts(...)`; `pdm run lint` must report exactly `C901 '..._process_contracts' is too complex (18)`.
- [ ] **Step 2: Extract private methods / module helpers** (verbatim moves; `_parse_datetime` stays nested in the row-building helper or moves to module level — either is fine, pick module level):

```python
def _parse_esi_datetime(date_string: str | None) -> datetime | None:
    # body: existing _parse_datetime nested helper, unchanged

def _collect_resolvable_ids(contracts: List[dict]) -> list[int]:
    # body: existing steps 1 (id set unions) + structure-ID filter + its log line

def _build_contract_rows(contracts: List[dict], id_to_name_map: dict) -> list[dict]:
    # body: existing step-3 comprehension, unchanged INCLUDING the comment about
    # is_ship_contract / item_processing_status being deliberately absent

async def _fetch_item_rows(self, contracts: List[dict]) -> tuple[list[dict], set[int]]:
    # body: the per-contract loop (type gate, get_contract_items, item_values
    # comprehension, ESINotModifiedError / Exception handlers) returning
    # (all_items, processed_contract_ids)

async def _update_item_processing_status(self, db_session, processed_contract_ids: set[int], all_items: list[dict]) -> None:
    # body: the incomplete/completed set math + the two _chunk_ids update loops
    # + the ENRICHMENT_INCOMPLETE log, unchanged INCLUDING its rationale comment
```

`_process_contracts` keeps: name resolution call + its two log lines, the two batched upsert loops (contracts batch_size=500, items BATCH_SIZE=50) OR extract them too if the residual measures > 10 — measure with the flake8 command and extract `_upsert_in_batches` only if needed (do NOT extract speculatively; YAGNI). Do NOT change either batch-size constant (500 / 50): no test pins them (the existing chunk-boundary test covers `UPDATE_ID_CHUNK_SIZE` for the ID-list updates, NOT these upsert loops), so a silent change would ship unproven — and changing them is out of scope regardless.

- [ ] **Step 3: Green gates** (lint 0, C901 select empty, full pytest green).
- [ ] **Step 4: Commit** — `refactor(api): extract _process_contracts stages to clear C901`

### Task 2.3: Phase review + PR

- [ ] Same as Task 1.3 EXCEPT the merge classification: per ground rule 9 this phase is `Review — data-integrity (ingestion pipeline refactor)` — open the PR, run codex review, then hand the merge to Sam (do NOT self-merge). Update this plan.

---

## Phase 3 — `run_aggregation` (complexity 14 → ≤ 10)

**Execution Status:** ⬜ NOT STARTED — MUST NOT start until Phase 2's PR is merged (same file; sequencing avoids conflicts).

**Files:**
- Modify: `app/backend/src/fastapi_app/services/background_aggregation.py`
- Test: `app/backend/src/fastapi_app/tests/services/test_background_aggregation.py`

**Context.** `run_aggregation` = region-config validation (two early returns) → concurrency lock → ESI client context → dynamic engine/session creation → per-region fetch loop with `_hb_region_id` stamping and per-region failure isolation → dev-limit truncation → `_process_contracts` + commit → `ConcurrencyLockError` and generic exception handlers → engine disposal in `finally`. Lock behavior is tested; the config-validation early returns, per-region failure isolation, and dev-limit truncation are NOT directly tested.

### Task 3.1: Characterization tests (config guards only — see the scoping note)

**⚠️ OBSOLETE — see the Phase 3 entry in Deviations.** The dynamic engine this note reasons about was
removed by PR #60, and that PR's own `test_freshness_*` tests already characterize the middle section
end-to-end. The note is retained below for provenance only; do not act on it.

**Scoping note (deliberate tradeoff, not an oversight).** `run_aggregation`'s middle section runs inside `_concurrency_lock()` + a dynamically created engine/session, so pre-refactor end-to-end characterization of the per-region loop and dev limit would need patches for redis-lock creation and `sqlalchemy.ext.asyncio.create_async_engine` (imported inside the function body), plus pointing the dynamic engine at `DATABASE_URL_TESTS` — note the conftest `db_session` fixture COMMITS on successful exit (isolation comes from drop/recreate-all-tables per run, not rollback), and the dynamically created engine is not governed by that fixture at all. That harness costs more than it protects for what Task 3.2 moves VERBATIM. Instead: the two config guards (which return before the lock) are characterized pre-refactor here; the region-isolation and dev-limit behaviors get direct unit tests against the extracted helpers in Task 3.2 Step 3, immediately after extraction, locking them against future regressions. The diff review in Task 3.3 is the no-change check for the verbatim moves.

- [ ] **Step 1: Write the guard tests** (append to `test_background_aggregation.py`):

```python
async def test_run_aggregation_rejects_non_list_region_config(caplog):
    service = _make_service()
    service.settings.AGGREGATION_REGION_IDS = "10000002"  # str, not list[int]
    with patch.object(service, "_concurrency_lock") as lock:
        await service.run_aggregation()
    lock.assert_not_called()  # bailed before ever touching the lock
    assert "CRITICAL_ERROR_AGG_SERVICE" in caplog.text


async def test_run_aggregation_skips_on_empty_region_list(caplog):
    service = _make_service()
    service.settings.AGGREGATION_REGION_IDS = []
    with patch.object(service, "_concurrency_lock") as lock:
        await service.run_aggregation()
    lock.assert_not_called()
    assert "AGGREGATION_REGION_IDS is empty" in caplog.text
```

- [ ] **Step 2: Run against UNREFACTORED code** — expected ALL PASS.
- [ ] **Step 3: Commit** — `test(api): characterize run_aggregation region-config guards`

### Task 3.2: Red gate, then extract helpers

- [ ] **Step 1: Red gate** (remove noqa; expect `C901 ... too complex (14)`).
- [ ] **Step 2: Extract:**

```python
def _usable_region_ids(self) -> List[int] | None:
    # NOTE: the module imports List but NOT Optional — use the PEP 604 union
    # (Python 3.14 target) rather than adding a typing import.
    # body: both existing guards verbatim (CRITICAL_ERROR log + empty-list warning);
    # returns the list, or None when aggregation should be skipped

async def _fetch_regions(self, region_ids: List[int]) -> List[dict]:
    # body: the per-region loop incl. _hb_region_id stamping and both except arms

def _apply_dev_limit(self, contracts: List[dict]) -> List[dict]:
    # body: the AGGREGATION_DEV_CONTRACT_LIMIT truncation incl. DEV_MODE warning
```

`run_aggregation` keeps the lock/client/engine/session orchestration, the `if not all_contracts_data` branch, both except handlers, and the `finally` engine disposal — all verbatim.

- [ ] **Step 3: Unit-test the extracted helpers AND the orchestration wiring** (per the Task 3.1 scoping note — the helper tests lock the behaviors that were impractical to characterize end-to-end, and the final wiring test proves the refactored orchestrator routes fetched → limited → processed → committed correctly, closing the gap the scoping tradeoff opened):

```python
async def test_fetch_regions_isolates_one_regions_failure(caplog):
    service = _make_service()

    async def contracts_side_effect(region_id):
        if region_id == 10000002:
            raise RuntimeError("simulated region fetch failure")
        return [{"contract_id": 920001}]

    service.esi_client.get_public_contracts = AsyncMock(side_effect=contracts_side_effect)
    result = await service._fetch_regions([10000002, 10000043])
    assert result == [{"contract_id": 920001, "_hb_region_id": 10000043}]
    assert "Failed to fetch contracts for region 10000002" in caplog.text


async def test_fetch_regions_stamps_the_fetch_region():
    service = _make_service()
    service.esi_client.get_public_contracts = AsyncMock(
        return_value=[{"contract_id": 920002}]
    )
    result = await service._fetch_regions([10000002])
    assert result[0]["_hb_region_id"] == 10000002


def test_apply_dev_limit_truncates_and_warns(caplog):
    service = _make_service()
    service.settings.AGGREGATION_DEV_CONTRACT_LIMIT = 1
    contracts = [{"contract_id": 1}, {"contract_id": 2}]
    assert service._apply_dev_limit(contracts) == [{"contract_id": 1}]
    assert "DEV_MODE" in caplog.text


def test_apply_dev_limit_disabled_passes_through():
    service = _make_service()
    service.settings.AGGREGATION_DEV_CONTRACT_LIMIT = 0
    contracts = [{"contract_id": 1}, {"contract_id": 2}]
    assert service._apply_dev_limit(contracts) == contracts


async def test_run_aggregation_orchestrates_fetch_limit_process_commit(monkeypatch):
    """Wiring proof for the refactored orchestrator: the fetched list flows
    through the dev limit into _process_contracts, the session commits, and the
    engine is disposed. Collaborators are stubbed at the same seams the file's
    other tests use; the code under test is run_aggregation's own routing."""
    from contextlib import asynccontextmanager

    service = _make_service()
    service.settings.AGGREGATION_REGION_IDS = [10000002]
    service.settings.DATABASE_URL = "postgresql+asyncpg://unused:unused@localhost/unused"

    @asynccontextmanager
    async def fake_lock():
        yield
    monkeypatch.setattr(service, "_concurrency_lock", fake_lock)
    service.esi_client.__aenter__ = AsyncMock(return_value=service.esi_client)
    service.esi_client.__aexit__ = AsyncMock(return_value=False)

    fetched = [{"contract_id": 1, "_hb_region_id": 10000002},
               {"contract_id": 2, "_hb_region_id": 10000002}]
    limited = fetched[:1]
    monkeypatch.setattr(service, "_fetch_regions", AsyncMock(return_value=fetched))
    apply_limit = MagicMock(return_value=limited)
    monkeypatch.setattr(service, "_apply_dev_limit", apply_limit)
    process = AsyncMock()
    monkeypatch.setattr(service, "_process_contracts", process)

    fake_session = MagicMock()
    fake_session.commit = AsyncMock()
    fake_session.__aenter__ = AsyncMock(return_value=fake_session)
    fake_session.__aexit__ = AsyncMock(return_value=False)
    fake_engine = MagicMock()
    fake_engine.dispose = AsyncMock()
    # run_aggregation does `from sqlalchemy.ext.asyncio import create_async_engine`
    # and `from sqlalchemy.orm import sessionmaker` INSIDE the function body, so
    # patch the source modules, not this module's namespace.
    monkeypatch.setattr("sqlalchemy.ext.asyncio.create_async_engine", MagicMock(return_value=fake_engine))
    monkeypatch.setattr("sqlalchemy.orm.sessionmaker", MagicMock(return_value=MagicMock(return_value=fake_session)))

    await service.run_aggregation()

    apply_limit.assert_called_once_with(fetched)
    process.assert_awaited_once_with(fake_session, limited)
    fake_session.commit.assert_awaited_once()
    fake_engine.dispose.assert_awaited_once()
```

- [ ] **Step 4: Green gates** (lint 0, C901 select empty on the file, full pytest green).
- [ ] **Step 5: Commit** — `refactor(api): extract run_aggregation guards and fetch loop to clear C901`

### Task 3.3: Phase review + PR — same protocol as Task 2.3 (classification `Review — data-integrity`; Sam merges).

---

## Phase 4 — `_get_esi_object` (complexity 16 → ≤ 10) + shared transient-retry helper

**Execution Status:** 🚧 PR OPEN — branch `claude/c901-esi-object`, claimed 2026-07-18, rebased onto
`origin/dev` at `c271f19`. Commits `4c4e158` (cache-failure characterization tests), `402658a`
(shared helper + rewire). Gates: red gate observed (`C901 'ESIClient._get_esi_object' is too complex
(16)`); after extraction `pdm run lint` exit 0, `--select=C901` clean, `_get_esi_object` 16 → 9, new
`_get_with_transient_retry` 8; full suite 368 passed. `get_esi_data_with_etag_caching` verified
**byte-identical** (method bodies extracted from both revisions and hash-compared — identical
SHA-256, 4567 bytes) with its `# noqa: C901` intact, so Phase 5's characterization gate is
unaffected. Classification `Review — data-integrity` — Sam merges.

**Files:**
- Modify: `app/backend/src/fastapi_app/core/esi_client_class.py`
- Test: `app/backend/src/fastapi_app/tests/core/test_esi_client.py`

**Context.** `_get_esi_object` is well tested (6 tests: object-not-keys, cache hit, non-object rejection, 5xx retry, network retry, retry exhaustion). Its complexity comes from the retry loop it shares — copy-pasted — with `get_esi_data_with_etag_caching`. This phase introduces the shared helper and rewires ONLY `_get_esi_object` onto it. **Phase 4 MUST NOT modify `get_esi_data_with_etag_caching` in any way** — not even to adopt the helper. That method keeps its own copy of the loop and its `# noqa: C901` until Phase 5, whose characterization-before-refactor gate depends on Phase 4 leaving it untouched.

### Task 4.1: Characterization gap check

- [ ] **Step 1:** The cache read-failure and write-failure warning paths (`except Exception ... logger.warning("Object cache read/write failed ...")`) are untested. Add two tests (names normative): `test_get_esi_object_survives_cache_read_failure` — a redis stub whose `get` raises → function still fetches over HTTP and returns the object (warning logged, asserted via `caplog`); `test_get_esi_object_survives_cache_write_failure` — a stub whose `set` raises → object still returned. Match the file's existing stub idioms (read the six neighboring `_get_esi_object` tests first).
- [ ] **Step 2:** Run against unrefactored code — PASS. Commit: `test(api): characterize _get_esi_object cache-failure degradation`

### Task 4.2: Red gate, then extract the shared retry helper

- [ ] **Step 1: Red gate** (remove noqa from `_get_esi_object`; expect `C901 ... (16)`).
- [ ] **Step 2: Add the shared helper** to `ESIClient` (this is new code, shown in full; it is the existing loop parameterized by `headers`):

```python
async def _get_with_transient_retry(
    self, path: str, headers: Optional[Dict[str, str]] = None
) -> httpx.Response:
    """GET with bounded retry on transient failures (5xx + network errors).

    4xx responses return normally — callers decide what non-5xx statuses mean.
    Exhausted retries surface as ESIRequestFailedError (status carried when the
    failure was HTTP, absent for pure network errors).
    """
    max_retries = 3
    backoff_factor = 0.5  # seconds
    response = None
    last_exception = None
    for attempt in range(max_retries):
        try:
            response = await self.http_client.get(path, headers=headers)
            if response.status_code < 500:
                last_exception = None
                break
            last_exception = httpx.HTTPStatusError(
                f"Server error '{response.status_code}'", request=response.request, response=response
            )
            logger.warning(
                f"ESI request to {path} failed with status {response.status_code}. "
                f"Attempt {attempt + 1}/{max_retries}."
            )
        except (httpx.ReadTimeout, httpx.ConnectError) as e:
            last_exception = e
            logger.warning(f"Network error for {path} on attempt {attempt + 1}/{max_retries}: {e}")
        if attempt < max_retries - 1:
            await asyncio.sleep(backoff_factor * (2 ** attempt))

    if last_exception is not None:
        if isinstance(last_exception, httpx.HTTPStatusError):
            raise ESIRequestFailedError(
                status_code=last_exception.response.status_code, message=str(last_exception)
            )
        raise ESIRequestFailedError(message=f"Network error for {path}: {last_exception}")
    return response
```

  **Known, accepted log-message deltas** (document in the PR body; update any test that pinned the old strings): the object variant's warning currently reads `"ESI object request to ..."` — the shared helper says `"ESI request to ..."`. This is the ONLY permitted behavior delta in the whole plan, it is log-text-only, and it must be called out in the PR body. Do NOT parameterize the message to preserve both strings — that is complexity for a log prefix.

- [ ] **Step 3:** Rewrite `_get_esi_object` to call `response = await self._get_with_transient_retry(path)`, keeping verbatim: the cache-read guard, `raise_for_status()`, the JSON/type validation with its design-§4.5 comment, and the cache-write guard.
- [ ] **Step 4: Green gates.** Lint 0; `--select=C901` empty for `_get_esi_object` (the ETag method still carries its noqa until Phase 5); the 8 `test_esi_client.py` tests green; full suite green.
- [ ] **Step 5: Commit** — `refactor(api): extract shared ESI transient-retry helper to clear _get_esi_object C901`

### Task 4.3: Phase review + PR — same protocol as Task 2.3 (classification `Review — data-integrity`; Sam merges).

---

## Phase 5 — `get_esi_data_with_etag_caching` (complexity 23 → ≤ 10)

**Execution Status:** 🚧 PR OPEN — branch `claude/c901-etag-caching`. Commits `e25883c` (20-test
characterization suite), `fc17fdf` (Task 5.2a str/bytes fix), `7122d98` (decomposition). Gates: red gate
observed at **24** (not the plan's 23 — Task 5.2a's `isinstance` check added a decision point after the
plan was written); after decomposition `pdm run lint` exit 0, `--select=C901` empty,
`get_esi_data_with_etag_caching` 24 → 9 (`_cache_ttl_seconds` 5, `_last_page_reached` 3,
`_read_etag_cached_page` 2, `_store_page_cache` 2); suite 435 passed.

**Task 5.3 live sanity check — PASSED (2026-07-19).** Dev server run against real ESI on this branch:
`"Public contract aggregation run finished successfully and changes committed."` appeared, **100
contracts / 152 contract_items** landed in `hangar_bay_dev` (100 is the configured dev limit), **zero**
`ERROR` lines in the log, and **134 `etag:*` keys** were written to Valkey — direct evidence that the
extracted `_store_page_cache` and the conditional-GET path work against the live API, not just under
mocks. Server stopped cleanly afterward.

**Sequencing deviation:** Task 5.1's characterization suite was written while Phase 4's PR was still
open, on a branch stacked on Phase 4 rather than off `dev`. This was safe because the suite targets
`get_esi_data_with_etag_caching`, which Phase 4 left byte-identical by contract — so the tests were
valid regardless of Phase 4's outcome. The branch was rebased onto `dev` after Phase 4 merged
(`e5d304d`); the Phase 4 commits dropped out as already-applied and no conflict arose.

**Files:**
- Modify: `app/backend/src/fastapi_app/core/esi_client_class.py`
- Test: `app/backend/src/fastapi_app/tests/core/test_esi_client.py`

**Context — read carefully, this is the riskiest phase.** The ETag method currently has **zero direct tests**. It is the ingestion hot path: pagination loop where each page does ETag lookup → conditional GET (via the retry pattern) → terminal-status handling (404-with-ignore, 204) → 304 cache-serve vs 200 parse-and-store (with `Expires`-derived TTL) → loop-termination logic (`all_pages`, empty page, `X-Pages`). Characterization tests come FIRST and are the bulk of the phase.

### Task 5.1: Characterization test suite (the core of this phase)

- [ ] **Step 1: Build fixtures.** Mirror the existing `_get_esi_object` test idiom in this file: `MagicMock` http/redis clients with `AsyncMock` methods (`_client_with_response` / `_client_with_get` helpers) — NOT `pytest_httpx` and NOT `tests/fake_redis.py`'s `FakeRedis`. Two contracts to respect:
  - **Redis values are BYTES on this path.** `ESIClient`'s managed client is `aioredis.from_url(...)` with default `decode_responses=False`, and the ETag code calls `cached_etag.decode()`. Stub `redis.get` to return `b"..."` (or `None`), never `str` — `FakeRedis` is str-valued (house `decode_responses=True` pattern) and would crash this path with `AttributeError` against the CURRENT code, which is exactly why it is the wrong double for characterization. (Task 5.2a later makes str clients tolerated; the characterization suite still runs on the bytes contract, which stays the production reality for this client.)
  - **Wiring already verified (2026-07-18, plan-authoring session) — latent hazard, not live:** the shared cache client (`core/cache.py:45`, `decode_responses=True`, str-valued) never reaches the ETag path today. The aggregation service — the only ETag-method caller — is built at `main.py:55` as `ESIClient(settings=settings)` with no injected redis, so it uses the managed bytes-returning client; `get_esi_client` (which injects the str client) is consumed only by the watchlist API, whose calls (`get_universe_type`/`get_universe_group`/`resolve_names`) avoid the ETag path; and `get_aggregation_service` (`background_aggregation.py:458`) — the one wiring that WOULD combine the str client with the ETag path — has zero callers (dead code). Task 5.2a fixes the latent crash; flag the dead provider in this phase's PR body for Sam's removal decision (do NOT delete it yourself).
  - Monkeypatch `asyncio.sleep` inside retry tests so backoff is a no-op (mechanism assertion: count requests, don't time them).
- [ ] **Step 2: Write these tests** (names are normative; bodies follow the existing file's idioms):

```
test_etag_single_page_200_returns_data_and_stores_etag_and_body
    # 200 with ETag header; assert returned list == payload; assert redis has
    # etag:<path>?page=1 and data:<path>?page=1 with ex=600 (no Expires header)
test_etag_304_serves_cached_body
    # seed redis data-key; 304 response; assert cached payload returned and NO
    # second HTTP request
test_etag_304_with_missing_cache_returns_empty
    # 304 but no data-key in redis: current behavior returns [] for the page —
    # pin it (this is a real production edge: evicted body, live etag)
test_etag_sends_if_none_match_from_cached_etag
    # seed etag-key; assert request carried If-None-Match with that value
    # (and empty string when absent — pin the current empty-string behavior)
test_expires_header_sets_cache_ttl
    # 200 with Expires 90s in the future: redis set called with 85 <= ex <= 90
test_malformed_expires_falls_back_to_600
test_pagination_follows_x_pages
    # all_pages=True, X-Pages: 2, two 200 pages; assert both pages concatenated
    # in order and exactly 2 requests made
test_pagination_stops_on_empty_page
test_404_with_ignore_404_ends_pagination_quietly
test_204_ends_pagination
test_single_page_mode_ignores_x_pages
    # all_pages=False with X-Pages: 5 → exactly 1 request
test_retry_exhaustion_raises_esi_request_failed
    # three 503s → ESIRequestFailedError with status_code == 503; assert
    # exactly 3 requests (mechanism assertion)
test_200_with_empty_body_treated_as_empty_page
test_single_page_mode_never_reads_x_pages
    # all_pages=False + X-Pages: "garbage" (unparseable) → returns normally with
    # 1 request. Pins the termination ORDER: current code breaks on `not
    # all_pages` before ever calling int(X-Pages); a reordered implementation
    # crashes with ValueError and fails this test.
test_empty_page_breaks_before_x_pages_is_parsed
    # all_pages=True + a 200 page with empty JSON list + X-Pages: "garbage" →
    # returns [] with 1 request, no ValueError. Pins that `not page_data` is
    # checked before the X-Pages parse.
test_404_without_ignore_propagates_http_status_error
    # ignore_404=False + a 404 response → httpx.HTTPStatusError from
    # raise_for_status propagates — NOT ESIRequestFailedError. Pin this asymmetry
    # vs _get_esi_object (which normalizes); do NOT "harmonize" it in the refactor.
test_redis_read_failure_propagates_on_etag_path
    # redis.get raising RuntimeError → RuntimeError propagates. Unlike
    # _get_esi_object, the ETag path has NO cache-failure guard — pin the
    # propagate-as-is behavior so the extraction doesn't quietly add degradation.
test_malformed_cached_json_propagates
    # 304 + data-key seeded with b"not-json" → json.JSONDecodeError propagates.
test_malformed_200_json_propagates
    # 200 with non-JSON, non-empty body → the response.json() decode error
    # propagates as-is (no ESIRequestFailedError normalization on this path).
```

- [ ] **Step 3: Run against UNREFACTORED code.** ALL must pass. Any failure = your fixture or your reading of the code is wrong (or you found a live bug → Discoveries subsection + STOP for triage; do not fix silently).
- [ ] **Step 4: Commit** — `test(api): characterize get_esi_data_with_etag_caching (etag, pagination, ttl, retry)`

### Task 5.2a: Fix the latent str-client crash on the ETag path (Sam-directed, 2026-07-18)

This is the plan's second documented behavior change (see ground rule 4). The cached-etag read assumes a bytes-returning client (`cached_etag.decode()`); a `decode_responses=True` client (the app's shared cache client) would crash it with `AttributeError` on the first ETag cache hit. Verified latent today (see the wiring note in Task 5.1 Step 1) — fix it now so the hazard doesn't outlive the refactor. Run this task AFTER Task 5.1's characterization suite is green (the suite is the net for this change too) and BEFORE Task 5.2.

- [ ] **Step 1: Write the failing test** (append to `test_esi_client.py`):

```python
async def test_etag_path_tolerates_str_valued_redis_client():
    """A decode_responses=True cache client returns str; the ETag read must
    accept both str and bytes without crashing (latent-hazard fix, 2026-07-18)."""
    response = _ok_response([{"contract_id": 1}], content=b'[{"contract_id": 1}]')
    response.status_code = 200
    response.headers = {}
    http_client = MagicMock()
    http_client.get = AsyncMock(return_value=response)
    redis_client = MagicMock()
    redis_client.get = AsyncMock(return_value="an-etag-as-str")  # str, not bytes
    redis_client.set = AsyncMock()
    client = ESIClient(settings=MagicMock(), http_client=http_client, redis_client=redis_client)

    data = await client.get_esi_data_with_etag_caching("/v1/test/")

    assert data == [{"contract_id": 1}]
    sent_headers = http_client.get.await_args.kwargs["headers"]
    assert sent_headers["If-None-Match"] == "an-etag-as-str"
```

  (Adapt the response-mock construction to the file's `_ok_response` helper signature; the load-bearing parts are the str-returning `redis_client.get`, the surviving call, and the `If-None-Match` value passing through un-mangled.)

- [ ] **Step 2: Run it — expected FAIL** with `AttributeError: 'str' object has no attribute 'decode'`.
- [ ] **Step 3: Minimal fix** in `get_esi_data_with_etag_caching` — replace the header construction with:

```python
if isinstance(cached_etag, bytes):
    cached_etag = cached_etag.decode()
headers = {"If-None-Match": cached_etag or ""}
```

- [ ] **Step 4: Run the test — PASS**; run the full Task 5.1 suite — still green (bytes-client behavior unchanged).
- [ ] **Step 5: Commit** — `fix(api): tolerate str-valued cache clients on the ESI etag path`

### Task 5.2: Red gate, then decompose

- [ ] **Step 1: Red gate** (remove noqa; expect `C901 ... (23)`).
- [ ] **Step 2: Extract private methods:**

```python
async def _read_etag_cached_page(self, data_key: str) -> list:
    # body: the 304 branch's redis get + json.loads, returning [] when absent

def _cache_ttl_seconds(self, response: httpx.Response) -> int:
    # body: the Expires parsing block, returning 600 on absent/past/malformed

async def _store_page_cache(self, etag_key: str, data_key: str, response: httpx.Response) -> None:
    # body: the ETag presence check + the two redis .set calls using _cache_ttl_seconds

def _last_page_reached(self, response: httpx.Response, page: int, page_data: list, all_pages: bool) -> bool:
    # body: the three loop-termination conditions IN CURRENT ORDER:
    # not all_pages → True; not page_data → True; X-Pages present and
    # page >= int(X-Pages) → True; else False
```

  The loop body becomes: build keys → `If-None-Match` header from cached etag → `response = await self._get_with_transient_retry(paginated_path, headers=headers)` → 404/204 terminal checks (keep verbatim, with their debug logs) → 304 ? `_read_etag_cached_page` : (raise_for_status, parse-or-empty, extend + `_store_page_cache` when `page_data`) → `if self._last_page_reached(...): break` → `page += 1`.

  **Ordering trap:** the current code checks `all_pages` BEFORE `page_data` and `X-Pages`; `_last_page_reached` must preserve exactly that order or the single-page-mode and empty-page tests will diverge. The characterization tests from 5.1 are the net.

- [ ] **Step 3: Green gates.** Lint exit 0 — at this point ZERO `# noqa: C901` remain in the codebase (verify: `grep -rn "noqa: C901" src/` → empty). Full suite green.
- [ ] **Step 4: Commit** — `refactor(api): decompose ESI etag pagination loop to clear the final C901`

### Task 5.3: Phase review + PR — same protocol as Task 2.3 (classification `Review — data-integrity`; Sam merges), PLUS a bounded live sanity check (the one intentional dev-server run in the plan; ENV-2/3 drop/recreate is expected and acceptable in the dev DB):

- [ ] Deps up (ground rule 1a command), then from `app/backend`: `pdm run dev > /tmp/hb-live-check.log 2>&1 &` (note the PID).
- [ ] Success condition (poll, bounded at 10 minutes — portable, no GNU `timeout` on stock macOS): `ok=0; for i in $(seq 1 60); do grep -q "aggregation run finished successfully" /tmp/hb-live-check.log && ok=1 && break; sleep 10; done; echo "ingest_ok=$ok"` — require `ingest_ok=1`.
- [ ] Verify rows landed: `docker exec hangar_bay_postgres psql -U hangar_bay_user -d hangar_bay_dev -c "SELECT count(*) FROM contracts;"` → count > 0. Also `grep -c "ERROR" /tmp/hb-live-check.log` and read any hits — unexplained errors are a STOP, not a footnote.
- [ ] Kill the dev server (the noted PID). If the success line never appears within the timeout: STOP, capture the log, and escalate — do not proceed to PR.

---

## Execution strategy recommendation

**Subagent-driven (`superpowers:subagent-driven-development`), one phase per subagent, sequenced 1 → 2 → 3 → 4 → 5** (2→3 same-file, 4→5 helper dependency; 1 can interleave anywhere but running it first builds reviewer confidence on the least-risky decomposition). Rationale: each phase is self-contained with its own tests, PR, and review gate; fresh context per phase prevents refactor fatigue from bleeding across functions; and the plan is deliberately subagent-proofed (exact helpers, exact test names, exact gates). Parallel dispatch is NOT recommended: the phases' PRs each rebase on the previous merge, and two of the dependencies are hard.

## What this plan deliberately does NOT do

- No behavior changes and no bug fixes beyond the two documented exceptions (Task 4.2 log-prefix delta; Task 5.2a etag byte/str normalization) — anything else discovered goes to Discoveries + flag, never a silent fix.
- No public API changes, no renames of existing symbols, no docstring rewrites beyond moved code.
- No new abstractions beyond the listed helpers (no strategy patterns, no config knobs, no generic "query builder" — YAGNI).
- No `max-complexity` config changes and no surviving `# noqa: C901` after Phase 5.
