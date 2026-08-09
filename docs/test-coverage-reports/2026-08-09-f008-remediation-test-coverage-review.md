<!-- ABOUTME: Consolidated test-coverage review of the F008 surface + the 2026-08-08/09 remediation work. -->
<!-- ABOUTME: Four subagent reviews (read, write, frontend logic, frontend components/e2e); 130 gap rows by severity. -->

# F008 + remediation test-coverage review — consolidated (2026-08-09)

**Method:** four parallel systematic reviews (per-function path maps, every GAP row severity-tagged,
no "covered indirectly" allowed). Full per-function tables are in the four subagent reports beside
this file — they are the evidence; this file is the severity-organized view.

## Totals

| Severity | Count |
|---|---|
| Security-critical | **4** |
| Correctness | **62** |
| Nice-to-have | **60** |
| **Total** | **126** + 4 queued-input statuses |

## Coverage summary (per review)

| Review | Report | Sec | Corr | NTH |
|---|---|---|---|---|
| Backend read path (contract_service, api/contracts) | subagent-backend-read-findings.md | 3 | 13 | 10 |
| Backend write path (ingestion, matcher, upsert, migrations) | subagent-backend-write-findings.md | 1 | 11 | 19 |
| Frontend logic (filters, format, columns, hooks) | subagent-frontend-logic-findings.md | 0 | 28 | 13 |
| Frontend components + e2e | subagent-frontend-components-findings.md | 0 | 10 | 18 |

## Security-critical gaps (4)

1. **The anonymous list endpoint's `size<=100` cap has zero 422 tests** — the only thing standing
   between a caller and corpus-per-request pages, and its removal is test-invisible.
   `schemas/contracts.py:456`, `api/contracts.py:33`.
2. **`search` min-length 422 untested at the endpoint AND the field has no max_length** — unbounded
   user text binds into a double-wildcard ILIKE over two columns on an anonymous endpoint (coverage
   gap + code observation). `schemas/contracts.py:332-336`.
3. **No API-level test asserts the wire-visible 500 body carries no internals** — the SQLA-4/D12
   parameter scrub is pinned at engine/log layers, never at the HTTP surface an attacker sees.
   `main.py:88-104`.
4. **The secret-hygiene log test asserts `DATABASE_URL[:16]` — the shared dialect prefix — never
   appears in logs**, so a line leaking only credentials or host passes the guard the test exists to
   be. (Write-path review SEC-1.)

## Queued-input statuses

- **O1a (WirePage omits `unknown_system_excluded`)** — CLOSED (Wave 4). Field added, supplied
  by both page builders, and guarded by a compile-time check over the KEYS of the generated
  `ContractListResponse` (assignability alone cannot catch a MISSING field).
- **O1b (fixture tiebreak localeCompare vs Python ordinal)** — CLOSED (Wave 4). The composition
  tiebreak is now an explicit ordinal comparison; `localeCompare` is locale-dependent and
  roughly case-insensitive, and agreed with the backend only over same-case ASCII.
- **O2 (type-partition invariant)** — CLOSED (Wave 3), at **all three backend sites**.
  `ITEMLESS_CONTRACT_TYPES` / `ITEM_BEARING_CONTRACT_TYPES` now live beside `ContractType`
  in `schemas/contracts.py`, and every consumer reads them: the read path
  (`contract_service`), the ingestion writer (`background_aggregation._fetch_item_rows`,
  which hard-coded `["item_exchange", "auction"]`) and the watchlist matcher
  (`watchlist_matcher._match_and_notify`, which hard-coded the same pair as a tuple —
  found during Wave 3's adversarial review, and NOT part of O2's original register).
  A contract type is therefore classified in exactly one place. The frontend partition
  was already pinned (`filters.test.ts:70`).

  Both backend gates have tests parametrized over the derived constants rather than a
  hand-listed pair, so a sixth `ContractType` is covered the moment it is added. Verified
  by actually adding a hypothetical sixth member: the derived writer handles it, while the
  old literal fails the new test. Without the matcher fix, that sixth type would have been
  ingested with items and recognized by the read path while silently never alerting.
- **PR #156 deferred e2e null-price pin** — CLOSED (Wave 4). A fixture assigns `price: null` and
  desktop+mobile journeys assert the dash on BOTH the list and the detail surface (they render price through different components). This is what made the nullable wire type
  load-bearing: narrowing `WireContract.price` back to `number` now fails typecheck, and did
  not before — because **`tsc -b` had never covered `e2e/` at all** (tsconfig.json referenced
  only the app and node projects, and Playwright transpiles without checking). A
  `tsconfig.e2e.json` now joins the references; enabling it immediately surfaced a real defect,
  `sorting.spec`'s price comparator doing arithmetic on a `number | null` and yielding NaN for
  an unpriced row.

## What is demonstrably strong

- The F008-era backend surface: liveness branches parametrized over every delisting case, derived-total
  equivalence matrices, three-way partition identities per range family, both directions + NULL
  placement for all six nullable sorts, whole-record log-scrub assertions with vacuity guards.
- The remediation-week additions all landed with discriminating tests (mutation-verified fixtures,
  render-order pins, footprint-free migration tests).
- a11y assertions are real (aria-sort, aria-pressed, alert roles asserted per state, axe on five pages).

## Key cross-cutting observations

- **The gaps concentrate on the PRE-F008 legacy surface** (detail 404/422, collateral & date_expired
  sorts, min_collateral) and **endpoint-level input validation** (1 of ~20 constraint paths has a
  wire 422 test) — the bug-hunt's "old code predating the new rules" risk shape, third sighting.
- **This week's debounce/freeze machinery has behavior-level pins but no unit layer**
  (useDebouncedValue: no test file; sameSearch branches unpinned; DEFAULT_DIRECTION asserted for 2
  of 9 fields).
- **Write-path observability seams are trusted, not tested**: last_seen_at stamping (the watermark's
  sole input), recursive-CTE queries only ever run against one distinct value, lock-skip paths.
- **Responsive column visibility is asserted at no layer** despite the mobile Playwright project
  running every spec.

## Appendix — per-review gap registers (verbatim)

### Backend read path — gap register

## 3. Gap register (summary with severities)

### Security-critical (3)

| ID | Gap | Where |
|----|-----|-------|
| SC-1 | `size` (and implicitly the whole pagination cost cap) has zero 422 tests on the anonymous list endpoint; `le=100` is the only thing standing between a caller and corpus-per-request pages, and its removal is test-invisible. | `schemas/contracts.py:456`, `api/contracts.py:33` (row 152) |
| SC-2 | `search` min_length 422 untested at the endpoint, and the field has NO max_length — unbounded user text binds into a double-wildcard ILIKE over two columns on an anonymous endpoint. Coverage gap + code observation. | `schemas/contracts.py:332–336` (row 153) |
| SC-3 | No API-level test asserts the wire-visible 500 body on a read-path failure contains no internals; the SQLA-4/D12 scrub is pinned at the engine/log layers only, never at the HTTP surface an attacker sees. | `main.py:88–104`, `api/contracts.py` (row 158) |

### Correctness (13)

| ID | Gap | Where |
|----|-----|-------|
| C-1 | `GET /contracts/{id}` 404 branch has zero tests anywhere. | `api/contracts.py:76–77` (row 163) |
| C-2 | Non-integer `/contracts/{id}` 422 untested. | `api/contracts.py:60–63` (row 164) |
| C-3 | int64-overflow contract id → currently a driver 500; behavior unpinned. | `api/contracts.py:60–74` (row 165) |
| C-4 | `min_collateral` filter has zero assertions anywhere (only `max_collateral`, and only in combination). | `contract_service.py:286–287` (row 30) |
| C-5 | `sort_by=date_expired` ("Time left") — both directions untested; the silent-no-op-sort defect class F008 §6.2 names. | `contract_service.py:43`, SORT_MAP (row 86) |
| C-6 | `sort_by=collateral` — both directions untested. | `contract_service.py:45` (row 87) |
| C-7 | `sort_by=date_issued&sort_direction=asc` untested (desc pinned only via the fallback test). | row 85 |
| C-8 | `still_listed_by_esi` case-`else_` correlated fallback under a NON-empty config (config-drift path) has no row-level regression test; verified once manually per the 2026-08-02 perf audit. | `contract_service.py:159–168` (row 11) |
| C-9 | `_primary_label` ship-priority branch not distinguishably tested — no fixture where the offered ship has a higher record_id than a named non-ship item; `named[0]` alone passes every test. | `contract_service.py:710–714` (row 96) |
| C-10 | Expiry criterion of `_live_item_bearing_contracts` (readiness denominator) untested — delisted sibling pinned, expired one not. | `contract_service.py:867` (row 120) |
| C-11 | `page=0` / negative page 422 untested (constraint removal → negative OFFSET → 500). | `schemas/contracts.py:455` (row 154) |
| C-12 | Negative-bound 422s untested across all six numeric range families at the endpoint. | `schemas/contracts.py:338–398` (row 155) |
| C-13 | Malformed value types (non-int id-list members, non-bool `is_bpc`) and unknown `sort_by`/`sort_direction` 422s untested at the endpoint. | rows 156–157 |

### Nice-to-have (10)

| ID | Gap | Where |
|----|-----|-------|
| N-1 | Out-of-range page (beyond last) with total > 0 — empty-`IN` joined branch and simple branch both unpinned. | row 77 |
| N-2 | Joined-path `nulls_last` exercised for only 2 of 6 NULLABLE sorts (shared branch, low residual risk). | rows 71–72 |
| N-3 | `_composition.total_volume is None` branch unasserted. | row 108 |
| N-4 | `_primary_label` "Courier" (no destination) and `Contract {id}` fallbacks execute in fixtures but are never read. | rows 101–102 |
| N-5 | Blank-string title (`"  "`) treated as absent — untested despite the comment calling it the common ESI shape. | row 99 |
| N-6 | Detail item array record_id ORDER unasserted (set-only assertion). | row 116 |
| N-7 | Taxonomy sort tie-break by id at equal names unasserted. | row 133 |
| N-8 | `_taxonomy_coverage` short-circuit ordering (cost property) unasserted. | row 129 |
| N-9 | `_error_without_bound_parameters` restore-after-render (`finally`) unasserted. | row 136 |
| N-10 | Delisted-but-unexpired contract reachable via detail (asymmetry sibling of the pinned expired case) unasserted; also `min_runs=-1` boundary admission (`ge=-1` vs ESI-3 "never sends -1") unasserted. | rows 166, `schemas/contracts.py:351–366` |

---

## 4. What is demonstrably strong (for calibration)

The F008-era surface is exceptionally well covered: both liveness branches parametrized over every delisting case; the derived-total equivalence matrix (13 filter shapes × 2 watermark branches, vacuity-guarded); three-way partition identities for every range family; both directions asserted for all six nullable sorts with NULL placement; log scrubbing pinned at four sites with whole-record assertions and a vacuity guard; the empty-page short-circuit discriminated by log-payload shape rather than response shape. The gaps concentrate in (a) the pre-F008 legacy surface (detail 404, collateral/date sorts, min_collateral) and (b) endpoint-level input validation, where exactly one of ~20 constraint paths (contract_type) has a wire-level 422 test.


### Backend write path — severity sections

## 1. Security-critical

### SEC-1 — The secret-hygiene assertion checks the URL *scheme*, not the credentials
`test_run_aggregation_reuses_app_session_factory_and_never_logs_database_url`
(test_background_aggregation.py:1291-1328) sets
`DATABASE_URL = "postgresql+asyncpg://secret_user:secret_pw@db.internal:5432/hb"` and asserts
`service.settings.DATABASE_URL[:16] not in msg`. `DATABASE_URL[:16]` is `"postgresql+async"` — the
dialect prefix every URL shares. The test catches a log line carrying the *full* URL, but a log line
that renders only the credentials or netloc (`secret_user`, `secret_pw`, `db.internal`) — which is how
sanitizers typically fail, by stripping the scheme and leaking the rest — passes. The docstring claims
"no log line may carry any fragment of DATABASE_URL"; the assertion enforces one fragment, the least
secret one. **Fix:** assert `"secret_pw" not in msg` and `"secret_user" not in msg` explicitly.
Severity: security-critical (the test exists precisely as the secret-leak guard, and it is near-vacuous
for the leak shapes that matter).

---

## 2. Correctness

### C-1 — `_resolve_esi_objects` non-dict payload shape guard has no test
background_aggregation.py:139-144. The guard exists because of a *documented live incident* ("this
happened live when the list-shaped ETag helper flattened object payloads into keys"), yet no test ever
returns a non-dict from `get_universe_type` / `get_universe_group` / `get_universe_station` /
`get_universe_category`. All failure-path tests raise exceptions (the 131-134 branch). If the
`isinstance(payload, dict)` check regressed, a list payload would flow into `.get()` calls and kill the
run — the exact incident the guard repaired. GAP: feed a list/str payload, assert the one id degrades
(warning logged, entry absent) and the run completes.

### C-2 — The recursive-CTE observed-ids queries are only ever executed against ONE distinct value
`_OBSERVED_CATEGORY_IDS_SQL` (156-165) and `_OBSERVED_GROUP_IDS_SQL` (170-179) are hand-written loose
index scans whose `UNION ALL` recursion step only produces output when ≥2 distinct ids exist. Every
repair test (`test_a_failed_category_name_fetch_is_repaired_from_observed_items`,
`test_a_nameless_group_payload_is_repaired_from_observed_items`) stores items of exactly one category
(6) and one group (25). A broken recursion returning only `min(category_id)` passes the entire suite,
and the self-healing cache would silently repair only the lowest-numbered category/group forever. GAP:
a repair test with two distinct missing categories (and groups), asserting both cache rows land.

### C-3 — `last_seen_at` stamping is never asserted on the write path
`_build_contract_rows` (263) stamps every row with one shared `seen_at`, and re-sighting restamps via
the upsert's copy-on-conflict — this is the sole input to the `still_listed_by_esi()` watermark that
decides site-wide visibility AND watchlist alerting. No aggregation test asserts (a) that a persisted
row carries a fresh `last_seen_at`, (b) that all rows of one batch carry the SAME stamp (the
"one run writes one value" invariant the docstring declares), or (c) that a re-sighted contract's stamp
advances. The matcher tests hand-write `last_seen_at` on fixtures (legitimate for the reader side, but
per TEST-18 that is exactly the seam where the writer can silently stop writing: if
`last_seen_at` were dropped from the row dict, or added to `preserve_on_null`, every re-sighted
contract would read as delisted one run later and no current test goes red). GAP: ingest, capture
stamp; re-ingest, assert the stamp advanced and equals its batch-mates'.

### C-4 — `run_aggregation`'s held-lock skip path is untested (matcher has it; aggregation does not)
background_aggregation.py:473-476 (`except ConcurrencyLockError: log + return`) and the acquire-failure
raise at 334-340. `grep ConcurrencyLockError test_background_aggregation.py` → no matches. The
watchlist suite pins both (`test_run_matching_skips_when_lock_held`,
`test_concurrency_lock_raises_when_held`); the aggregation suite pins release/TTL/mismatch but never a
pre-held lock. A regression that let `run_aggregation` proceed (or crash the scheduler) on a held lock
— the concurrent-run scenario the whole mechanism exists for — is invisible. GAP: pre-seed the store
with a foreign token, run `run_aggregation`, assert no fetch/session activity and clean return.

### C-5 — All-regions-failed outcome ("failure" via counters, not forced) is untested
`_record_run_outcome` (499): `outcome = "failure"` when `ok == 0` without `forced_failure`. Tests cover
success, all-304 success, partial, and forced failure (commit raise). The natural path — every region's
fetch raises, `all_contracts_data` empty, no exception propagates, outcome derives from `(0, N)` — has
no test asserting `outcome == "failure"`, gauge unmoved, and `last_success_at` preserved from the prior
record. This is the readiness signal for a total ESI outage.

### C-6 — The freshness-writer's own failure swallow is untested
`_record_run_outcome` 495-523: "A failure of the outcome WRITE itself is logged and swallowed —
freshness recording must never turn a successful ingest into a failed job." No test makes
`redis_client.get`/`set` raise inside the recorder and asserts the run still completes as a success
(and the warning is logged). If the try/except were narrowed or removed, a cache blip after a healthy
commit would mark the whole job failed.

### C-7 — `run_matching`'s job-boundary exception swallow is untested
watchlist_matcher.py:127-133: a generic exception must be caught, logged via `log_key_event(...,
success=False)`, and NOT propagate to the scheduler. No test raises from `_match_and_notify`/`_prune`/
commit and asserts run_matching returns quietly with the failure event recorded. A regression here
crash-loops the APScheduler job.

### C-8 — No write-path test ingests an issuer id above 2^31 (the a7c migration's motivating bug)
Migration a7c44d19e582 exists because "a CCP id above 2^31 would poison ingestion the same way a
price-less contract did before f2a91c3b7e04". The price half got its TEST-22 write-path test
(`test_a_spec_minimal_contract_persists_with_absent_optionals_null_or_defended` asserts `price is
None` persists); the issuer half got only schema tests (model↔migration equivalence, downgrade
guards). No test feeds `_process_contracts` a contract with `issuer_id=3_000_000_000` and asserts the
row persists. The schema-equivalence test pins the column type, but the end-to-end "spec-extreme value
survives the writer" test — the TEST-22 mirror this migration's own docstring invokes — is absent.

### C-9 — The a7c downgrade's offline (`--sql`) rendering is unpinned
`test_offline_downgrade_renders_a_transaction_wrapped_locked_guard` pins BEGIN < LOCK < guard < ALTER <
COMMIT for **f2a91c3b7e04 only**. a7c44d19e582's downgrade uses the same emitted-SQL guard shape
(docstring: "the f2a91c3b7e04 pattern") plus an additional ordering property of its own — index drops
BEFORE the narrowing rewrite (a7c:81-85) — and neither the transaction wrapping nor the drop-before-
rewrite order is asserted for it. Deleting a7c's `LOCK TABLE` line or reordering the drops regresses
silently. (Escalated per instruction: the guard-atomicity property is what makes the refusal safe
against a concurrent writer.)

### C-10 — The matcher's contract-type gate is tested through one arm only
watchlist_matcher.py:159-161 `Contract.type.in_((item_exchange, auction))`. Every matcher fixture is
`ctype="auction"` (the `_contract` default); no test creates a matching **item_exchange** contract
(positive arm — also leaves `_SHIP_TYPE_LABELS`' "an item exchange" rendering unasserted, see N-11) and
no test creates a courier/other-type contract carrying an included watched item and asserts exclusion
(negative arm). Dropping `item_exchange` from the tuple, or the tuple membership entirely, passes the
suite.

### C-11 — Mocked-behavior hazards beyond the known D-c (flag per CLAUDE.md testing rules)
- **`test_plain_upsert_still_merges_on_dialects_without_conflict_support`** (test_db_upsert.py:125-141)
  asserts against a hand-rolled `_RecordingSession` whose `merge` just appends to a list — it verifies
  `db.merge` is *called*, not that merge-based upsert semantics work. The real fallback path (db_upsert
  .py:77-79) never executes against any real non-PG database in the suite.
- **The sqlite branch of `bulk_upsert`** (db_upsert.py:62-67), including preserve_on_null-on-sqlite,
  never executes at all — the suite runs PostgreSQL only. The docstring's "compatible with both
  PostgreSQL and SQLite" and "Supported on PostgreSQL and SQLite" claims are unverified; the branch is
  effectively dead code carrying a compatibility promise no test backs.
- **`FakeLockRedis.eval`** (tests/lock_double.py:24-29) reimplements the compare-and-delete Lua script
  in Python. The double's semantics match today, but the Lua source itself (`_RELEASE_LOCK_LUA`) is
  never executed by any test — a typo in the Lua (e.g. `KEYS[1]`/`ARGV[1]` swap) passes every lock test.
  Lower priority than the first two (the script is 2 lines and shared), but it is the same hazard class.
- *(Known, referenced, not re-counted: D-c — the `ESINotModifiedError` handlers in
  `_fetch_regions`/`_fetch_item_rows` are dead against the real client, and the tests that exercise
  them (`test_fetch_regions_counts_a_304_region_as_ok`,
  `test_reingestion_with_unmodified_items_keeps_ship_flag`, the all-304 freshness test) mock a raise
  the client never performs. D-d — Valkey-evicted page body truncating a region walk — likewise known.)*

---

## 3. Nice-to-have

### N-1 — `_parse_esi_datetime` edge paths
The `None → None` path (83-89) runs constantly via `date_completed` but no test asserts
`row.date_completed is None` (spec-minimal asserts eight other optionals, not this one), and no test
ever supplies a *populated* `date_completed`. A malformed date string raising `ValueError` inside
`_build_contract_rows` kills the whole batch — behavior neither pinned nor decided.

### N-2 — Per-field mapping assertions missing in `_build_contract_rows` (240-282)
Fields whose *populated* value is never asserted on a persisted row: `status` (both the `"unknown"`
default and a supplied value), `title`, `for_corporation=True`, `collateral` (non-zero), `reward`,
`volume`. A `reward`↔`volume` mapping swap is undetectable by the current suite. `date_issued`/
`date_expired` values are also never directly asserted post-persist (a swap is only accidentally caught
by the expiry filter in the is_bpc HTTP test).

### N-3 — Item-payload absence paths partially unasserted
`is_blueprint_copy` absent → NULL is never asserted (ESI sends the flag true-or-absent per TEST-18;
`test_item_level_columns...` asserts runs/ME/TE/item_id None for record 8212 but not the BPC flag), and
`is_singleton`'s `.get(..., False)` default is never asserted.

### N-4 — `_apply_dev_limit` with a configured limit and an under-limit batch
Paths tested: limit>len (truncate), 0, None. The `limit and limit>0` but `len(contracts) <= limit`
pass-through-without-warning path (421) has no test.

### N-5 — `_record_run_outcome`'s invalid-JSON prior branch
The `except (ValueError, TypeError)` at 510-511 (prior record is *unparseable* JSON, e.g. `"not json"`)
is distinct from the tested valid-JSON-non-object branch (`"[]"`); it has no test.

### N-6 — Lock release on body exception and client close are unasserted
When the locked body raises (e.g. the commit-failure freshness test), the finally-release runs but no
test asserts the lock key was removed from the store afterward; `aclose()` on all paths (including the
acquire-failure path) is a no-op in the double and never asserted.

### N-7 — `_select_known_station_systems` chunk boundary and mixed batches
The read-back loop chunks via `UPDATE_ID_CHUNK_SIZE` (667) — monkeypatchable, but no test forces >1
chunk here (the two existing chunk-boundary tests cover the status UPDATEs and the skip SELECT). Also
no test mixes one already-known station with one needing a fresh fetch in a single batch (the partial
fall-through at 632-644).

### N-8 — The contract/item upsert 500-row batch loops are untestable as written
`batch_size = 500` (544) and `BATCH_SIZE = 500` (587) are function-local literals — unlike
`UPDATE_ID_CHUNK_SIZE` they cannot be monkeypatched, so crossing their boundary requires 500+ row
fixtures nobody writes. Testability defect: hoist to module level so a boundary test becomes possible.

### N-9 — Chunk crossing unforced for the incomplete-status and non-ship-clear UPDATE loops
`test_id_list_updates_batch_across_the_chunk_boundary` crosses the boundary for the COMPLETED-set and
ship-flag loops; the `incomplete_contract_ids` loop (818-823) and the `non_ship_completed` clear loop
(812-817) are separate loops that could each independently stop after chunk one.

### N-10 — No test asserts a courier contract triggers zero `get_contract_items` calls
The `contract["type"] not in ["item_exchange", "auction"]` skip (720-721) is relied on by a dozen
courier fixtures but never asserted (`get_contract_items.assert_not_awaited()` on a courier-only run).

### N-11 — `_render_message` branch coverage
`location=None → "an unknown location"` (57) never tested; the `"an item exchange"` label never
rendered (see C-10); the `"a contract"` fallback label is unreachable given the query's type gate —
either test it as defense-in-depth or note it as such.

### N-12 — Matcher `distinct()` and fan-out shapes
No test with two included items of the same watched type in one contract (pins `.distinct()`, 179 —
without it `matched` double-counts even while `created` stays right); no multi-user test (two enabled
users watching the same type both get notifications); no one-user-two-watches-one-contract test (two
rows differing in `watch_type_id` both insert past the unique index).

### N-13 — `_prune` sub-branches of "outstanding"
The delete-when-gone test uses an *absent* contract row; the expired-but-present row, the
completed-but-present row, and the `created_at == cutoff` strict-`<` boundary (231) each lack a test.

### N-14 — `run_matching` happy path never runs end-to-end
The only `run_matching` tests stub `_match_and_notify`/`_prune` (session-factory test) or hold the
lock. No test drives a real match through `run_matching` asserting the commit lands (notifications
visible post-commit) and the success `log_key_event` carries `matches/created/pruned`.

### N-15 — `bulk_upsert([])` early return (db_upsert.py:32-33) untested
A regression reordering it below `values[0]` access crashes on the aggregation's no-op paths.

### N-16 — Non-NULL overwrite pinned for only one preserved column
`preserve_on_null` NULL-keeps is asserted for all four name columns end-to-end
(`test_resolved_names_survive_a_degraded_name_resolution_run`), but the "non-NULL still overwrites"
direction is asserted only for `issuer_corporation_name` (rename test) — the other three columns'
overwrite arm of the COALESCE rides on it. Also untested: one statement carrying mixed rows (one NULL,
one non-NULL in the same preserved column) exercising per-row COALESCE.

### N-17 — a7c clean downgrade never asserts the two indexes were dropped
`test_clean_downgrade_restores_int32_issuer_columns` asserts column types only; index absence is caught
only accidentally (a retained index would crash the `finally` re-upgrade on duplicate name). Assert
`pg_indexes` directly.

### N-18 — Failure before the region fetch records `failure` with 0/0 counters
If `esi_client.__aenter__` or the session factory raises (before `_fetch_regions`), the forced-failure
record carries the initial `regions_ok=0, regions_failed=0` (437-438) — reasonable, but unpinned.

### N-19 — Spec-minimal contract does not assert the resolver/station calls are skipped
`test_a_spec_minimal_contract_persists...` asserts NULLs persist but not that
`get_universe_station` was never awaited for a contract with no locations (the `is not None` guard in
`_npc_station_ids`, 208).

---


### Frontend logic and components

Full registers in their reports (60+ rows): `subagent-frontend-logic-findings.md` (28 correctness / 13 nice-to-have; summary at its §Summary counts) and `subagent-frontend-components-findings.md` (10 / 18; queued-input statuses at its §1).

---

## Remediation status (living — update per wave)

**Sam's directive (2026-08-09): fix ALL gaps.** Execution proceeds in waves, one PR each, using the
four per-file registers as work orders.

| Wave | Scope | Status |
|---|---|---|
| 1 | Security-critical (4) | ✅ DONE — PR #163 (three test-only + this report committed), PR #164 (search max_length, `Review — public API contract`, held for Sam) |
| 2 | Backend read correctness (13) | ✅ implemented — PR #166 (`Review — public API contract`, held for Sam: detail-id bounds ride along); three mutation kills verified |
| 3 | Backend write correctness (11) + O2's backend partition pin | ⚠️ **10 of 11 closed** — PR #169 (`Routine`); backend 705 → 733, 24 regressions mutation-verified, all killed. C-11 is PARTIALLY closed: two of its three mocked-behavior hazards now run against real dependencies, the third needs a decision from Sam (see Wave 3 residual below). O2 closed at all three sites |
| 4 | Frontend logic (28) + components (10) + e2e pins (O1a, O1b, null-price) | ⚠️ **partial** — PR #170 (`Routine`): frontend logic **28/28**, all three e2e pins closed, components **4/10** (C1–C4; C3 came via Wave 3). Remaining: **C5–C10** — responsive column visibility, detail Reward row, empty-items Contents card, five of six BlueprintFilter bounds, the Deadline header sort journey, the WatchButton gate. vitest 322 → 376, e2e 140 → 144 |
| 5 | Nice-to-have (60) | ⬜ queued — sweep last; drop any a wave above already covered |

Each wave: TDD where a fix changes code, mutation-verification for load-bearing new tests
(TEST-12), footprint-free discipline on shared fixtures (TEST-23), five frontend lanes for any
frontend commit, Routine classification unless a wave touches schema or the public contract.

### Wave 3 residual — one mocked-behavior hazard is Sam's call

C-11 flagged three tests that assert against a double rather than against real logic. Two are
now closed for real:

- `_RELEASE_LOCK_LUA` executes against a live Valkey for BOTH the aggregation and matcher
  scripts (`tests/test_lock_script.py`). Previously every lock test drove `FakeLockRedis.eval`,
  which reimplements the compare-and-delete in Python, so the Lua source was never run and a
  `KEYS[1]`/`ARGV[1]` swap passed the whole suite — mutation-verified, that swap now fails.
- `bulk_upsert`'s SQLite branch runs on a real in-memory `sqlite+aiosqlite` engine, backing the
  docstring's "Supported on PostgreSQL and SQLite" claim that nothing had ever executed.

The third needs a decision rather than a test.
`test_plain_upsert_still_merges_on_dialects_without_conflict_support` drives a hand-rolled
`_RecordingSession` whose `merge` appends to a list — it asserts `db.merge` is *called*, not
that merge-based upsert semantics work. The real fallback (`db_upsert.py:77-79`) runs only on a
dialect that is neither PostgreSQL nor SQLite, and the project has no third dialect to exercise
it against, so no test can close this the way the other two closed. Per CLAUDE.md's rule on
tests that exercise mocked behavior, flagging rather than choosing:

- **(a) Delete the fallback and its test.** Every environment is PostgreSQL; SQLite exists only
  for that branch and its new unit test. Deleting production code needs explicit approval.
- **(b) Keep it, rename the test** to say it pins dialect *dispatch*, not merge semantics, so
  nobody reads it as coverage of behavior it does not cover.
- **(c) Accept the residual** as recorded here and move on.

Until one of those is chosen, Wave 3 stands at **10 of 11 correctness rows closed**, not DONE —
the wave table says so rather than rounding up. Whoever picks an option should flip the Wave 3
row at the same time.

### Wave 3 erratum against the write-path register

`subagent-backend-write-findings.md` C-9 describes a7c44d19e582's downgrade as dropping the two
location indexes **before** the narrowing rewrite. It does the reverse — narrow, then drop in
reverse creation order, which is the exact inverse of the upgrade and the correct shape. The
register's stated ordering property does not exist in the code; the test written for C-9 pins
what the migration actually emits (independently confirmed during adversarial review). No code
change was made: editing an already-applied migration to satisfy a misreading would be the
wrong repair.
