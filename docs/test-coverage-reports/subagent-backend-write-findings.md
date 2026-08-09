# ABOUTME: Systematic test-coverage review of the backend WRITE/ingestion path (background_aggregation,
# ABOUTME: watchlist_matcher, db_upsert, price-nullable + issuer-int64 migrations) — path map, GAP rows, severities.

# Backend write-path test coverage review — 2026-08-08

**Scope:** `app/backend/src/fastapi_app/services/background_aggregation.py`, `watchlist_matcher.py`,
`db_upsert.py`, migrations `f2a91c3b7e04_contracts_price_nullable.py` +
`a7c44d19e582_location_indexes_issuer_int64.py`, against their test files
(`tests/services/test_background_aggregation.py` [2074 lines], `tests/services/test_watchlist_matcher.py`,
`tests/services/test_db_upsert.py`, `tests/test_migrations.py`).

**Method:** every function path-mapped with line numbers; a path counts as covered only when a test
exercises it with its own assertion (no "covered indirectly"). Intent sources consulted: F008 spec §7,
testing-pitfalls TEST-18/TEST-22/TEST-23, the 2026-08-08 overnight-followups decision log, and the
consolidated bug-hunt report (design concerns D-c and D-d are KNOWN and referenced, not re-found).

**Totals: 1 security-critical, 11 correctness, 19 nice-to-have.**

The suite is unusually strong — the enrichment-status state machine, preserve_on_null semantics,
watermark/delisting predicate, price-NULL matcher branches, and migration guard/clean/offline paths are
all pinned with mechanism-level assertions. The gaps below are what path-by-path mapping still surfaces.

---

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

## 4. Path-map summary (evidence of coverage, per function)

Depth check: every function exceeding the 25-line rule was path-mapped individually
(`run_aggregation`, `_process_contracts`, `_update_item_processing_status`, `_upsert_taxonomy_names`,
`_enrich_items_and_find_ships`, `_resolve_station_systems`, `_fetch_item_rows`, `_record_run_outcome`,
`_concurrency_lock`, `_match_and_notify`, `_prune`, `bulk_upsert`, both migration downgrades).

**background_aggregation.py — covered with own assertions:**
region-id guards (non-list / list-with-str / empty, each with exact log-level assertions); per-region
fetch isolation + 304-counts-ok + per-region stamping (with the anti-vacuity `-1` stamp overwrite);
dev-limit truncate/0/None; freshness success/all-304/partial/forced-failure/non-object-prior + gauge
both directions; lock happy release / TTL>interval (two intervals) / token-mismatch-leaves-intact;
region-id persistence + NULL; structure-id 1e11 boundary both sides (with name-everything-passed
anti-vacuity resolver); all four denormalized names populated + preserved-on-degraded + rename-updates;
NPC station range both edges ×2 roles, structure never-requested ×2 roles, known-pair outage survival
×2 roles, payload-missing-system_id, lookup-failure-degrades; type-specific fields (buyout/days/
end name) present + absent; item columns (runs/ME/TE/item_id/BPC true/taxonomy ids) present + absent;
spec-minimal TEST-22 payload; ship flag set / excluded-item not / clear-on-version-bump /
degraded-never-clears; status machine COMPLETED / ENRICHMENT_INCOMPLETE (type, category, requested-
side, category-less-group) / PENDING_ITEMS (fetch fail, zero items) with per-contract isolation;
skip predicate both arms (status demotion, version bump) + chunk-crossing on skip-SELECT and
flag/status UPDATEs; 304 re-ingestion keeps flag + old stamp; multipage item walk over a real
ESIClient; taxonomy cache write / cache-first skip / category repair / nameless-group repair (both
with fresh-service restart proof); session-factory reuse.

**watchlist_matcher.py — covered:** happy match + exact message; idempotent second run; partial-index
`index_where` binding; chunk crossing; bundle-price both sides; price ==/> boundary; expired /
completed / delisted / at-watermark / per-region stalled watermark; requested-item excluded; disabled
user excluded; NULL-price × {unbounded watch → dash message, bounded watch → excluded}; prune
delete-gone / keep-outstanding / delete-delisted / keep-recent; lock held-skip / mismatch / raise /
TTL×2; session-factory reuse.

**db_upsert.py — covered:** preserve-NULL keeps + same-statement plain copy; non-NULL overwrites;
unpreserved NULL overwrites; fresh-insert NULL stays NULL; NotImplementedError on other dialects with
preserve_on_null; merge fallback invoked without it (see C-11 for the hazard); omitted-column
preservation via the aggregation 304 test.

**Migrations — covered:** model↔migration equivalence with `compare_server_default`; env.py
import-safety; price downgrade refusal (message-matched) + clean restore + offline BEGIN<LOCK<guard<
ALTER<COMMIT ordering; issuer downgrade refusal for EITHER column (loop over both arms) + clean narrow
of both; TEST-23 restoration discipline present in every mutating migration test (finally-scoped
rollback + row delete + upgrade-to-head).

**Concurrency/TOCTOU review (instruction 6):** acquisition is a single atomic `SET NX EX` and release a
single atomic Lua CAD — no check-then-act window exists inside either lock at the Redis level; the only
residual window is TTL-expiry-mid-run, which is exactly what the TTL-derivation tests and the
token-mismatch tests pin. The aggregation and matcher locks use distinct keys (constants; divergence is
a code-review property, not testable behavior). Cross-job TOCTOU (matcher reading mid-aggregation) is
closed by the aggregation's single-transaction commit; matcher-vs-delist between its SELECT and INSERT
is an accepted design race (alert for a just-delisted contract), consistent with the still_listed
tradeoff notes. Untested residuals are C-4 (held-lock skip, aggregation side) and N-6 (release-on-
exception assertion).

**ON CONFLICT semantics (instruction 5):** update set = supplied columns minus PK; omitted columns
(is_ship_contract, item_processing_status, enrichment_version, and every model default) preserved —
pinned by the 304-reingestion test; `preserve_on_null` = {start_location_name, end_location_name,
issuer_name, issuer_corporation_name} — NULL-keeps pinned per column end-to-end, non-NULL-overwrites
pinned for one of four (N-16). `last_seen_at` is a *supplied* column and therefore restamps on
conflict — load-bearing and unasserted (C-3). Notification insert uses ON CONFLICT DO NOTHING against
the partial unique index with a literal `index_where` — binding and idempotency both pinned.
