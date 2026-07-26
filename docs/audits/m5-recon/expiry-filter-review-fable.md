# Adversarial review — M5 expiry filter (`claude/m5-expiry-filter`, commit 566c1c1)

Reviewer: Fable (Claude). Diff base: `origin/dev`. All claims below were verified by
reading the code and by running the backend suite against the docker Postgres in this
worktree (full suite: 455 passed). Mutation evidence (TEST-12) was gathered by
temporarily commenting out the predicate, running the new tests, and restoring the file;
`git status` is clean.

## Verdict

The production change itself is correct and complete: the predicate sits in
`_apply_contract_filters`, which every list path (count, simple fetch, joined fetch)
flows through, and every other contract-listing consumer in the codebase already
excludes expired rows. The defects are concentrated in the test layer and in deploy
mechanics.

---

## BLOCKER

### B1. `test_detail_still_serves_an_expired_contract` is vacuous — it replays its own cassette and never exercises the app

`app/backend/src/fastapi_app/tests/api/test_contracts.py` has file-level
`pytestmark = [pytest.mark.vcr, pytest.mark.esi_live, pytest.mark.asyncio]`. vcrpy's
httpx stub intercepts at the client level, **before** `ASGITransport`, so with the
committed cassette
(`tests/api/cassettes/test_detail_still_serves_an_expired_contract.yaml`) and
pytest-vcr's default record mode (`once`), both HTTP calls in the test are answered from
the cassette. The FastAPI app, the service, and the database are never touched; the
test's own `db_session.add(...)` / `flush()` is dead code at runtime.

**Proof (mutation check, TEST-12):** with the `date_expired > func.now()` predicate
commented out of `contract_service.py`, the three new service tests fail (good — they
are real) and this API test **still passes**:

```
FAILED src/fastapi_app/tests/services/test_contract_service.py::test_expired_contracts_are_excluded_from_the_list
FAILED src/fastapi_app/tests/services/test_contract_service.py::test_expired_exclusion_also_applies_on_the_item_joined_path
FAILED src/fastapi_app/tests/services/test_contract_service.py::test_expired_exclusion_holds_across_page_boundaries
3 failed, 16 passed
```
(`test_detail_still_serves_an_expired_contract` was in the passing set.)

**Concrete failure this causes:** the test's entire stated purpose is to pin the
list/detail asymmetry "so a later change that 'consistently' filters both does not slip
through as a tidy-up." If someone adds the expiry filter to the detail endpoint — the
exact regression this test exists to catch — the cassette still replays `200` and the
test still passes. The asymmetry, the headline UX decision of this branch, is therefore
**guarded by nothing**. The list half of the asymmetry is at least covered by the
service tests; the detail half has zero effective coverage.

**Verified fix path:** the behavior is genuinely implemented — with the cassette
removed, the test recorded fresh against the live app and passed (0.16s). Remove the
`vcr` marker for this test (restructure the file-level `pytestmark` so `vcr`/`esi_live`
apply only to `test_get_contracts_live`, the one test that actually replays an ESI-shaped
interaction) and delete the committed cassette. Do **not** ship a DB-driven test under a
file-level `vcr` mark.

---

## MAJOR

### M1. The four pre-existing cassette tests in `test_contracts.py` now contradict live behavior — a landmine armed by this branch

`test_filter_contracts_by_search`, `test_filter_contracts_by_price`,
`test_sort_contracts`, and `test_paginate_contracts` all build fixtures with
`date_expired = 2025-01-02` — eighteen months in the past. Under the new filter the live
app returns `total: 0` for every one of their queries; they pass only because their
cassettes replay pre-filter responses. (This is itself the proof of B1's replay
mechanism: the suite ran green with these fixtures.)

They were already replay-zombies before this branch, but this branch changes them from
"zombie and consistent with the code" to "zombie and asserting behavior the code no
longer has." **Concrete failure:** the first re-record — cassette deletion, a
`--record-mode=all` run, a vcrpy/httpx upgrade that changes request matching — fails all
four at once with confusing `total == 0` diffs, in a file nobody will connect to this
branch. The author demonstrably understood this exact rot class (the
`_ship_contract_dict` comment in `test_background_aggregation.py` describes it verbatim:
"a fixture pinned to a past date is invisible to any test that queries over HTTP") and
fixed it in the file where it caused a visible failure, while leaving the same rot in
place wherever cassette replay masked it. Fix the fixtures to relative future dates in
this PR — same one-line pattern as `_ship_contract_dict` — and preferably re-record or
un-vcr these tests too.

### M2. Non-concurrent `CREATE INDEX` in `preDeployCommand` can queue behind a minutes-long ingestion transaction

`render.yaml` runs `python -m alembic upgrade head` as `preDeployCommand`, while the
**old** instance — which hosts the APScheduler ingestion job in-process
(`main.py` lifespan) — is still live. `_process_contracts` upserts the contracts batch
(taking `ROW EXCLUSIVE` on `contracts`), then holds that transaction open across the
per-contract ESI item fetches (network I/O inside the open transaction), item upserts,
and status updates, committing only at the end of the run. In production that window is
minutes, not milliseconds.

`op.create_index` takes a `SHARE` lock, which conflicts with `ROW EXCLUSIVE`. With no
`lock_timeout`, the migration waits for the in-flight aggregation run to commit, and the
next aggregation run's first upsert queues behind the waiting `SHARE` request.
**Concrete failure:** a deploy that happens to overlap an aggregation run stalls in
pre-deploy for up to a full ingestion cycle, and can hit Render's pre-deploy timeout and
fail the release. At ~50k rows the index build itself is trivial (well under a second) —
the entire risk is the lock queue.

Reads are unaffected (`ACCESS SHARE` doesn't conflict with `SHARE`), so user impact
during the stall is nil; this is a deploy-reliability problem, not an outage. Cheapest
robust fix: `SET lock_timeout` + short retry loop in the migration, or accept the risk
explicitly in the PR body after checking the aggregation cadence vs. deploy frequency.
(`CREATE INDEX CONCURRENTLY` is overkill at this size and needs alembic's
`autocommit_block`.)

### M3. Nothing covered here removes expired rows — the filter institutionalizes invisible, unbounded growth

Ingestion is upsert-only (`_process_contracts`; no `DELETE` of contracts anywhere in
`services/`). Expired contracts now accumulate forever, invisible to users. The count
query must still evaluate the predicate against an ever-growing dead majority, the five
per-column indexes all keep absorbing writes for rows that will never be listed again,
and any future full-table operation gets slower monthly. Not caused by this branch, but
this branch is the moment "dead rows stay forever" became a silent policy instead of a
visible product bug. Needs at minimum a backlog entry for a reaper/retention job;
flagging because nobody asked.

---

## MINOR

### m1. Comment overstates what `func.now()` buys for the index

`contract_service.py`: "func.now() keeps the comparison on the database clock, so no
application-side timezone conversion sits between the predicate and its index." The
database-clock half is right (and the transaction-start snapshot of Postgres `now()`
also makes count and page see the same instant within a request — worth stating, since
it's the actual consistency argument). The index half is misleading: a bound tz-aware
`datetime` parameter is exactly as index-usable as `now()`. A future reader could infer
that parameterized timestamps break index use; they don't.

Related expectation-setting on the model/migration comments ("on the hot path for all of
them"): the index existing does not mean the planner uses it. While live rows are the
majority, `date_expired > now()` is unselective and typical first-page queries will be
served off `ix_contracts_date_issued` (sort) with the expiry check as a filter. The
index earns its keep only as dead rows become the majority (see M3) and for
`sort_by=date_expired`. Not wrong to add it; the comment just promises more than the
planner will initially deliver.

### m2. Two more hardcoded past expiries in `test_background_aggregation.py`

Lines ~51 and ~78 (`test_process_contracts_stamps_fetch_region`,
`..._without_region_stamp_stores_null`) still use `"date_expired": "2026-07-08T00:00:00Z"`
— already in the past. Harmless today because both read rows back with `select(Contract)`
directly, but they are the same trap the `_ship_contract_dict` comment warns about, one
refactor-to-HTTP away from firing. Cheap to fix in the same file the branch already
touched.

### m3. Untested interaction: `sort_by=date_expired` with the filter

No test combines the expiry filter with sorting by `date_expired` (either path). Risk is
low — filter and sort are orthogonal clauses, and the joined path's min/max aggregate
ordering is covered by pre-existing tests — but it is the one sort column the feature is
semantically entangled with, and the frontend's "Time left" default (`date_expired: 'asc'`,
`ContractsPage.tsx`) makes it the second-most-likely real query. One service test with
mixed live/dead rows sorted by `date_expired asc` would close it.

### m4. Frontend e2e stub fixtures now depict responses the real API can never produce

`app/frontend/web/e2e/fixtures/contracts.ts` includes list rows with past `date_expired`
(e.g. `'2026-07-20T23:36:29Z'`). The Playwright fixture lane stubs the network, so
nothing fails, and I confirmed no spec asserts on time-left text — but the wire-shape
fixtures now model an impossible list response (expired rows present). Worth a sweep to
relative dates whenever that file is next touched, per the fixture-realism convention.

---

## Sections verified sound (one line each)

- **Predicate placement:** `_apply_contract_filters` is upstream of `_count_distinct_contracts`, `_fetch_page_simple`, and `_fetch_page_joined` (the `with_only_columns` id-query retains the WHERE); no list path escapes it.
- **Other consumers:** watchlist matcher already filters `Contract.date_expired > func.now()` in both match and prune; saved searches store filter params and execute through the list endpoint; notifications link to the (deliberately unfiltered) detail endpoint; `ops.py` doesn't count contracts. No divergence introduced.
- **`func.now()` semantics:** `timestamptz > timestamptz` against `DateTime(timezone=True)`, transaction-start snapshot keeps count/page mutually consistent within a request; test fixtures use whole-day offsets so txn-start-vs-`datetime.now()` skew can't flip an assertion (the tests' own comment about this is accurate).
- **Migration correctness:** revision chain `3aca702a74e3 → b1c4d7e9f204` is the sole head; index name/DDL matches the model; the migration↔metadata equivalence test (`test_migrations.py`) passes with the new index; dev's drop/recreate startup and prod alembic stay aligned.
- **The three service tests:** all fail under predicate mutation (verified), use a dedicated region, sorted-not-positional assertions (TEST-3), and a real page-boundary sweep with per-page `total` checks (TEST-4).
- **`_ship_contract_dict` change:** all call sites are in `test_background_aggregation.py`; the one that queries over HTTP (`?is_bpc=true`, in a file *not* vcr-marked) is exactly the test the comment says broke, and the relative-future date fixes it without affecting the direct-row-read call sites. The comment's claims check out.
- **Suite state:** full backend suite green in natural order (455 passed); the 7 `test_migrations`+`test_background_aggregation` ordering failures I hit when running those two files in reversed order reproduce identically on the dev-state worktree — pre-existing caplog/order sensitivity, not this branch.

## Evidence log

- Full suite: `pdm run pytest -q` → `455 passed in 31.38s` (m5 worktree, docker Postgres).
- Mutation run: predicate commented out → 3 new service tests failed, new API test passed (transcript excerpt in B1).
- Cassette-removed run: `test_detail_still_serves_an_expired_contract` → `1 passed in 0.16s`, fresh cassette recorded (then restored via `git checkout --`).
- Reversed-order pair run on `origin/dev`-state worktree → same 7 failures (pre-existing).
- Worktree left clean: `git status --short` empty (an untracked, gitignored `app/backend/src/.env` was copied in from a sibling worktree to run the suite).
