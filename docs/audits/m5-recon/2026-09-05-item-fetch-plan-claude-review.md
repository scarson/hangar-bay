ABOUTME: Preserves the independent cross-provider review of the item-fetch integrity implementation plan.
ABOUTME: Records the exact findings and review provenance before the plan repair wave.

# Item-fetch integrity plan review

Reviewer: Claude Opus 5, high effort, cold independent review through Claude CLI in safe mode with tools and MCP disabled. The supplied bundle contained the draft and selected public project sources, including both pitfalls documents. No local environment files or credentials were included.

Draft SHA256: `81CD6A09568F0437B7C2AAD22EFA2772C9CCE810CC1712D977F2FDA0C1064DB3`.
Bundle SHA256: `d5df1e0f3334d45ed6807b71384e616432df4e910f728f9ee5deadfce7f3d1da`.
Review completed 2026-09-05; CLI exited 0 with a successful result and no permission denials.

The five findings below are the reviewer's output. Their disposition is tracked in the coordinating continuation record; this report preserves the as-raised review.
## Findings

---

**Finding 1 — Task 1, step "Strengthen the database seam and demonstrate failure preservation"**

> Quoted: *"The transport-failure handler raises `httpx.ConnectError("item transport unavailable", request=request)` for all three attempts; capture the existing sleep boundary to avoid real backoff delays and assert attempts/waits `[0.5, 1.0]`. Capture the retry warnings and aggregation error by logger, level and complete message, and **check the final error's cause**."*

**Dimension:** implementation/testing pitfall — assertion against a property the source cannot produce.

**Claim:** In `esi_client_class.py::_get_with_transient_retry`, the network-error exit is `raise ESIRequestFailedError(message=f"Network error for {path}: {last_exception}")` — a bare `raise` executed *after* the retry loop, outside any `except` block. It therefore carries `__cause__ is None` and `__context__ is None`. Unlike the plan's own `_read_contract_item_page`, which correctly specifies `from exc` for JSON decode failures, the transport path has no chained cause. Compounding this, in the `_process_contracts` flow that this test drives, `_fetch_item_rows` swallows it (`except Exception as e: logger.error(f"Failed to fetch items for contract {contract['contract_id']}: {e}", exc_info=True)`) and does not re-raise — so no exception object is observable to the test at all. The `[0.5, 1.0]` wait assertion and the three `logger.warning(f"Network error for {path} on attempt {attempt + 1}/{max_retries}: {e}")` records are correct and verifiable; the cause assertion is not.

**Smallest correction:** Delete "and check the final error's cause" from this step. Assert instead on the captured `ERROR` record from `fastapi_app.services.background_aggregation` whose message begins `Failed to fetch items for contract <id>:` and contains the `ESIRequestFailedError.__str__` text (`ESI request failed with status 0: Network error for /v1/contracts/public/items/<id>/?page=3: ...`). Keep a `__cause__` assertion only on the client-level invalid-JSON case, where `from exc` is actually specified.

---

**Finding 2 — Task 2, replacement table row for `test_freshness_success_when_all_regions_304`**

> Quoted: *"Two region HTTP 304s with nonempty cached bodies and `X-Pages: 1`. Run real region fetch and `_process_contracts` through a committed scratch-DB transaction; assert both contracts persisted with their distinct source regions, success counters 2/0, last-success time and advancing gauge."*

**Dimension:** context gap for a fresh executor.

**Claim:** The existing `test_freshness_success_when_all_regions_304` has signature `(monkeypatch: pytest.MonkeyPatch)` and works today *only because* `ESINotModifiedError` produces an empty `all_contracts_data`, so `run_aggregation` opens `AsyncSessionLocal()` but never issues a statement and never connects. Once the cached bodies are nonempty, `_process_contracts` runs against `bg_agg.AsyncSessionLocal`, which `db.py` binds to the real `settings.DATABASE_URL`. Every other `run_aggregation` test that reaches the DB does five things this row does not name — takes `db_session`, builds `create_async_engine(TEST_DATABASE_URL)` and `async_sessionmaker(...)`, `monkeypatch.setattr(bg_agg, "AsyncSessionLocal", maker, raising=False)`, and `await engine.dispose()` (see `test_freshness_success_when_all_regions_fetch_ok`). Omitting the bind makes the run die on a connection/`relation contracts does not exist` error, which `run_aggregation`'s outer handler converts into `forced_failure=True` — so the test fails with `outcome == "failure"` for a reason unrelated to 304 handling, exactly the misdirection `test_a_run_that_persists_nothing_records_failure_though_the_fetch_worked` documents inline (TEST-12), and it risks writing to whatever `DATABASE_URL` is configured, which the plan's global constraints forbid.

**Smallest correction:** Add to this row (and to the new cached-region processing/commit-failure case): "bind `bg_agg.AsyncSessionLocal` to a `TEST_DATABASE_URL` sessionmaker via `monkeypatch`, take the `db_session` fixture, and dispose the engine — the pattern in `test_freshness_success_when_all_regions_fetch_ok`."

---

**Finding 3 — Task 2, the real-`ESIClient` helper**

> Quoted: *"A helper may construct the real `ESIClient` with a controlled HTTP transport and Redis get/set boundary double, but must not stub `get_public_contracts`."*

**Dimension:** testing pitfall — unserved boundaries degrade into swallowed failures, defeating the pristine-output gate.

**Claim:** Swapping `_make_service()`'s `MagicMock` ESI client for a real `ESIClient` removes three conveniences the current tests depend on: `resolve_ids_to_names` (armed AsyncMock), `get_universe_category` (armed specifically, per its comment, "keeps captured logs free of 'can't be awaited' warnings"), and `get_contract_items` (inert `return_value=[]`). With a real client, `_process_contracts` will drive `resolve_ids_to_names` → `self.http_client.post("/v3/universe/names/", ...)` and `_resolve_station_systems` → `get_universe_station` → `GET /v2/universe/stations/60003760/` (60003760 is inside `NPC_STATION_ID_MIN..MAX`). Both call sites catch `Exception` and continue — `resolve_ids_to_names` logs `An unexpected error occurred during ID resolution`, `_resolve_esi_objects` logs `Station resolution failed for station 60003760`. Because `_ship_contract_dict` sets `"type": "item_exchange"`, which is in `ITEM_BEARING_CONTRACT_TYPES`, `_fetch_item_rows` will additionally call the real `get_contract_items`, and an unserved item path yields `logger.error("Failed to fetch items for contract ...")` while the freshness outcome still reads `success` — a pass with error spam. Separately, committing item rows here would be the first `run_aggregation` test to commit `contract_items`/`esi_taxonomy_cache` outside the rollback-scoped `db_session`; `test_a_failed_category_name_fetch_is_repaired_from_observed_items`, `test_a_nameless_group_payload_is_repaired_from_observed_items` and `test_two_distinct_missing_groups_are_both_repaired` all assert those tables are empty *unscoped*, and `_observed_category_ids`/`_observed_group_ids` read them unscoped.

**Smallest correction:** State in the helper bullet that the fixture contracts for the cached-region tests use `type="courier"` (which `_fetch_item_rows` skips entirely, and which still proves persistence and distinct region stamps), and that the transport must serve `POST /v3/universe/names/` and `GET /v2/universe/stations/60003760/` — or explicitly re-arm those two on the real client — so no boundary degrades into a captured WARNING/ERROR.

---

**Finding 4 — Task 2, the cached-304 example snippet**

> Quoted:
> ```python
> f"data:{region_path}": json.dumps([_ship_contract_dict(920001)]),
> ...
> assert [(c["contract_id"], c["_hb_region_id"]) for c in contracts] == [
>     (920001, 10000002), (920002, 10000043),
> ]
> ```

**Dimension:** testing pitfall — an assertion satisfiable by the fixture rather than by the code (TEST-25 observation point).

**Claim:** `_ship_contract_dict` already sets `"_hb_region_id": 10000002`, and `region_path` in the snippet is region `10000002`. The cached body is round-tripped through `json.dumps`/`json.loads`, so the pre-stamp survives into `contracts`. The first tuple `(920001, 10000002)` therefore holds even if `_fetch_regions`'s `for contract_data in contracts_page: contract_data["_hb_region_id"] = region_id` loop were deleted — i.e. the clause that is supposed to prove the 304 region's contracts are region-stamped is vacuous for the 304 region specifically. This is the exact trap the existing `test_fetch_regions_stamps_each_contract_with_its_own_region` documents inline ("a run that never stamped anything would still satisfy the first contract's assertion by accident… Overwrite both stamps with a value no region uses"). The same hazard applies to the `test_fetch_regions_counts_a_304_region_as_ok` row's "per-contract source-region stamps".

**Smallest correction:** In the snippet and both affected rows, overwrite `_hb_region_id` with a sentinel (`-1`) in the dict before `json.dumps`, mirroring `test_fetch_regions_stamps_each_contract_with_its_own_region`, so the 10000002 stamp can only come from `_fetch_regions`.

---

**Finding 5 — Task 1, "Verify the full focused modules and lint" and the no-cache test snippet**

> Quoted: *"Verify default headers through the existing compatibility tests."*
> and: `async with httpx.AsyncClient(base_url="https://esi.evetech.net", transport=httpx.MockTransport(respond)) as http_client:`

**Dimension:** claimed verification that does not verify the stated invariant.

**Claim:** `tests/core/test_esi_compatibility_date.py` never calls `get_contract_items` (or any `ESIClient` fetch method); its three tests construct a bare `httpx.AsyncClient` with `ESIClient.default_headers(settings)` and `GET /anything`, compare the setting to `snapshot.json`, and compare it to `PINNED_COMPATIBILITY_DATE`. They therefore cannot verify that the rewritten item path still carries `X-Compatibility-Date`/`User-Agent`, which the plan's global constraints require preserved and which pitfall ESI-4 makes load-bearing (an absent header is served the oldest published date, not an error). The plan's own no-cache test then builds its `AsyncClient` *without* `ESIClient.default_headers`, so it cannot observe them either — while asserting the absence of two other headers on the same request.

**Smallest correction:** Construct the no-cache test's client as `httpx.AsyncClient(base_url=..., headers=ESIClient.default_headers(settings), transport=...)` with a real `Settings(_env_file=None, ...)` (as `test_esi_compatibility_date.py::_settings` does), and add to the `respond` handler `assert request.headers["x-compatibility-date"] == settings.ESI_COMPATIBILITY_DATE` and `assert request.headers["user-agent"] == settings.ESI_USER_AGENT`; replace the "Verify default headers through the existing compatibility tests" clause with a pointer to that assertion.

---

**As-raised substantive finding count: 5**
