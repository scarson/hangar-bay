<!-- ABOUTME: Source evidence and SQL design for ordering contracts by their displayed headline. -->
<!-- ABOUTME: Defines regression fixtures, deliberate expectation updates, and performance verification. -->

# Contract headline sort planning evidence

Sam approved sorting Name by the displayed contract headline, using one direction-independent key and the existing ascending contract-ID tie breaker. The decision replaces the unresolved Name-sort disposition in the [contract-search consolidated report](2026-09-05-contract-search-consolidated.md#q3-define-what-the-name-sort-represents). This is planning evidence for the coordinator's implementation plan, not an executed or performance-validated implementation.

## Investigation checklist

- [x] Trace headline, sort, filter, model and frontend-column semantics.
- [x] Identify a minimal SQL expression and every headline branch.
- [x] Identify regression fixtures and conflicting intentional expectations.
- [x] Specify executable correctness checks and the performance evidence still needed.

## Verified source contract

The [contract service](../../app/backend/src/fastapi_app/services/contract_service.py) owns `_offered_items` (line 663), `_primary_label` (687), both page fetch paths (585/627), `SORT_MAP` (43), and `_needs_item_join` (80). The [item model](../../app/backend/src/fastapi_app/models/contracts.py) has non-null Boolean `is_included`, globally unique non-null `record_id`, nullable `type_name` and `category`, and an existing `ix_contract_items_contract_id` index. The frontend [contract columns](../../app/frontend/web/src/features/contracts/columns.tsx) render `primary_label` (77) and dispatch `ship_name` (99). Neither the API sort-key spelling nor frontend rendering needs to change.

The exact label algorithm is:

1. Among offered items (`is_included` true), discard only NULL and empty names. Whitespace-only names remain valid and are returned verbatim.
2. Prefer a named item whose **string** `category` is exactly `"ship"`; among those take the lowest `record_id`. If none exists, take the lowest-record-ID named offered item of any category. Neither `category_id=6`, `is_ship_contract`, quantity nor requested items determine this selection.
3. Otherwise use `contract.title.strip()` if nonempty. Python strips more than ASCII spaces; retain embedded whitespace.
4. Otherwise, for stored type exactly `"courier"`, return `"Courier to " + end_location_name` if that name is non-null/nonempty, or `"Courier"`. Destination whitespace is not trimmed; a whitespace-only destination is truthy.
5. Otherwise return `"Contract " + decimal contract_id`, including loans and unknown stored contract types.

`primary_label` is consequently never NULL. Search is an OR over title and joined item name (273–281); `type_ids` restricts the joined item (346–347). Those predicates must continue selecting the same contracts without constraining the separate headline selection. Taxonomy and blueprint predicates already use correlated EXISTS.

## Minimal expression and integration

Use one explicitly aliased, Contract-correlated scalar subquery. The following SQLAlchemy sketch uses actual model columns; `String`, `cast` and `literal` are additions to the service's SQLAlchemy imports. `select`, `case`, `func`, `aliased` and `ContractType` already exist there. Define the helper before `SORT_MAP` and map `SortableContractFields.ship_name` to its result.

```python
from sqlalchemy import String, cast, literal

_TITLE_WHITESPACE = (
    "\t\n\v\f\r\x1c\x1d\x1e\x1f \x85\xa0\u1680"
    "\u2000\u2001\u2002\u2003\u2004\u2005\u2006"
    "\u2007\u2008\u2009\u200a\u2028\u2029\u202f\u205f\u3000"
)


def _primary_label_sort_key():
    item = aliased(ContractItem, name="headline_item")
    item_name = (
        select(item.type_name)
        .where(
            item.contract_id == Contract.contract_id,
            item.is_included.is_(True),
            item.type_name.is_not(None),
            item.type_name != "",
        )
        .order_by(
            case((item.category == "ship", 0), else_=1),
            item.record_id.asc(),
        )
        .limit(1)
        .correlate(Contract)
        .scalar_subquery()
    )
    title = func.nullif(func.btrim(Contract.title, _TITLE_WHITESPACE), "")
    courier = case(
        (
            Contract.type == ContractType.courier.value,
            case(
                (
                    func.nullif(Contract.end_location_name, "").is_not(None),
                    literal("Courier to ") + Contract.end_location_name,
                ),
                else_=literal("Courier"),
            ),
        ),
        else_=literal("Contract ") + cast(Contract.contract_id, String),
    )
    return func.coalesce(item_name, title, courier)
```

The whitespace string contains all 29 characters reported by the installed Python 3.14 `str.isspace()` over Unicode. It has no NUL and can be passed as a text bind; ordinary SQLAlchemy string arguments remain bound parameters. PostgreSQL `btrim(text, characters)` removes characters from that set at both ends, which matches `str.strip()` for this set. Do not use plain `btrim(title)` (space only), `string.whitespace` (ASCII only), or an unverified database regex whitespace class. Real PostgreSQL execution must still verify this expression, including control characters and Unicode, through the parity test below. Do not scan all Unicode on every request or at service import; keep the explicit set and independently verify it in tests.

Keep `_primary_label` and `_offered_items` unchanged. The SQL duplicates only their selection rule where the database needs it; differential parity tests protect that necessary cross-language duplication.

Remove Name from `NULLABLE_SORTS` and remove Name as a reason for `_needs_item_join`; search/type filtering still forces the join. Update only comments made false by those changes. Name alone then uses `_fetch_page_simple`, with no sort-induced join in count queries.

On `_fetch_page_joined`, use `sort_column` directly for `ship_name`; preserve the existing min/max aggregation for other sorts. Grouping by `Contract.contract_id`, the Contract primary key, allows its functionally dependent columns in the order expression; the item scalar explicitly correlates only to that grouped contract. This avoids evaluating the correlated headline key inside an aggregate once per matching joined item. Retain grouped-ID pagination, `contract_id.asc()`, page-only selectin loading and ID-order restoration. Exercise this SQL against PostgreSQL: compilation alone cannot validate functional-dependency/grouping behavior.

Use the same key in both directions, applying only `.asc()` or `.desc()` to it. Preserve PostgreSQL's configured collation; add no `lower`, `casefold`, natural/numeric ordering or explicit alternate collation. Mixed-case key values must remain byte-for-byte identical to displayed labels. Expected locale-sensitive ordering should be obtained by asking the same database to order independently supplied literal headline values, not by Python `sorted()`. Basic ASCII fixture order may be pinned directly.

No schema, migration, index, ingestion, title normalization, response schema or generated-code change is proposed. If the measured cost makes this expression unsuitable, bring that evidence back before expanding scope.

## Tests and exact expectation changes

Use real PostgreSQL and the existing function-scoped `db_session`/ASGI `client` fixtures from [backend conftest](../../app/backend/src/fastapi_app/tests/conftest.py). This fixture drops/recreates every table in `DATABASE_URL_TESTS`; use only the confirmed disposable test database, with no concurrent tests against that same database. Do not start `pdm run dev` to obtain a test server. Give each corpus one region, one shared future-safe issuance/expiry window and one identical `last_seen_at`, explicit disordered insertion/record IDs, and title text that does not accidentally satisfy a search intended to match an item.

Add to [service tests](../../app/backend/src/fastapi_app/tests/services/test_contract_service.py):

- `test_primary_label_sort_key_matches_displayed_headline`: one parameterized real-database differential test selects `(contract_id, _primary_label_sort_key())` and compares each key both to a literal fixture label and to `_primary_label(contract, _offered_items(contract))` with items eagerly loaded. Cover requested ship before offered module; offered module before offered ship; two offered ships with lexical order opposed to record order; two nonships in opposed lexical/record order; unnamed/empty ship before named nonship; all unnamed/empty; category NULL, `"Ship"`, and category-ID/string disagreement; whitespace-only item name; padded title; NULL/empty/whitespace title; courier with NULL/empty/named/whitespace destination; titled courier; loan and unknown type; large valid int64 ID. Mixed-case and non-ASCII names remain unchanged. Literal expectations prevent two simultaneously wrong helpers from agreeing vacuously.
- `test_primary_label_sort_key_matches_python_title_whitespace`: verify the constant equals the independent set `''.join(chr(cp) for cp in range(0x110000) if chr(cp).isspace())` as sets and that its length is 29 on supported Python 3.14. Batch-seed each whitespace character around `"Alpha"` and as the entire title; assert keys `"Alpha"` and the literal fallback respectively. Add embedded whitespace and non-whitespace U+200B/U+FEFF to prove they are preserved. Perform one database fixture lifecycle for the whole batch, not one per codepoint.

Add to [contract-filter API tests](../../app/backend/src/fastapi_app/tests/api/test_contract_filters.py):

- `test_name_sort_uses_displayed_headlines`: parameterize asc/desc and filters absent, title-search (matches all), item-search (only requested/module rows match), and `type_ids` (only requested/module rows match). A shared three-contract corpus should display `Rifter`, `Rokh`, `Venture`, while its matching distractor names order differently; the Rokh has an earlier alphabetic module, and the Venture has a later alphabetically earlier offered ship. Assert complete ordered `(contract_id, primary_label)` lists and unchanged totals for every filter. This reaches both fetch paths and kills accidental filter correlation, module/min-max ordering, requested-item selection and record-order mistakes.
- `test_name_sort_paginates_equal_headlines_in_both_directions`: tie at least three parent rows with multiple matching item rows each, seed contracts out of ID order, request size 2 and all pages under both the simple path and search/type-triggered joined path. Assert ID-ascending ties in both directions, complete page partition, no duplicates/skips, consistent total and unchanged segment counts. Retain the existing service regression `test_joined_pagination_tiebreaks_equal_sort_keys_by_contract_id` at line 542; its `search` argument still reaches the joined path.
- `test_name_sort_orders_fallbacks_with_named_items`: interleave literal labels `Atron`, `Bantam`, `Contract <id>`, `Courier`, `Courier to Jita`, `Merlin`, and a trimmed title. Assert both complete orders; itemlessness must not put a row at the end automatically. Include a search matching itemless titles to exercise fallback grouping on the joined path.
- `test_name_sort_preserves_database_collation`: with independently declared mixed-case/non-ASCII literal labels, ask PostgreSQL to order a VALUES/reference relation by that literal string then ID, in each direction, and compare the endpoint IDs. Do not reuse the production key expression to generate the reference.

Two intentional expectation groups must change under Sam's approved semantics:

1. `test_ship_name_sorts_both_ways_and_leaves_item_less_contracts_last` at filter-test line 2532 explicitly pins min/max direction-dependent representatives and NULL itemless placement. Replace it with a headline-order test while retaining `volume_and_ship_name_sort_contracts` and the volume test. Its exact existing fixture labels produce ascending IDs `[972011, 972013, 972012, 972001, 972002, 972003, 972014]` and descending `[972014, 972003, 972002, 972001, 972012, 972013, 972011]`: `972013` is always Bantam, and the itemless rows use their `Nullsort <id>` titles. Correct this fixture's representative prose and section commentary; preserve volume assertions.
2. `ITEM_BEARING_JOINED_SORTS` at line 2930 includes `ship_name`; `test_the_joined_path_puts_nulls_last_for_the_item_bearing_sorts` therefore expects unnamed item `978003` last despite its displayed `Null Placement 978003` title. Remove Name from that nullable tuple as it leaves production `NULLABLE_SORTS`, retain the exhaustiveness assertion and all five truly nullable sorts, and add a separate Name test on `joined_auction_corpus`. With its existing type filter, asc IDs are `[978001, 978003, 978002]`, desc `[978002, 978003, 978001]`; assert labels `Apocalypse`, `Null Placement 978003`, `Zealot` as well.

Keep `test_pagination_sorted_by_ship_name_no_duplicates` at line 302, parameterize both directions if useful, and update its false assertion that Name alone forces a join. It now provides simple-path tied pagination; retain separate joined-path pagination with explicit search/type criteria. Existing `test_sort_contracts` and primary-label API tests in [contract API tests](../../app/backend/src/fastapi_app/tests/api/test_contracts.py) continue unchanged.

## Verification commands and performance gate

The [remediation plan's database preflight](../plans/2026-09-05-contract-search-bug-hunt-remediation-plan.md#runtime-and-database-preflight) governs execution, including the full suite's separate migration-equivalence database and shared-server exclusion.

Run from `app/backend` after the coordinator verifies/reuses project dependencies and confirms the disposable database. `pdm` is not on this sandbox's PATH, but its module is discoverable, so `python -m pdm` is the available invocation form. No dependency acquisition is part of this investigation.

```powershell
python -m pdm run pytest src/fastapi_app/tests/services/test_contract_service.py src/fastapi_app/tests/api/test_contract_filters.py -k "primary_label_sort_key or name_sort" -q
python -m pdm run pytest src/fastapi_app/tests/services/test_contract_service.py src/fastapi_app/tests/api/test_contract_filters.py src/fastapi_app/tests/api/test_contracts.py -q
python -m pdm run lint
python -m pdm run pytest
```

Run intended-behavior tests before production edits and record their expected assertion failures; repeat after the minimal service change. Import/fixture failures are not TDD red evidence. The renamed replacement tests should contain `name_sort` so the focused command selects them. Source inspection and differential key tests supplement API ordering tests; neither replaces actual returned-row assertions.

The existing contract-ID index makes a per-contract item lookup plausible, but its total cost is unmeasured. The [August correlated-subquery performance investigation](../perf-audits/2026-08-02-contract-list-watermark-subquery.md) demonstrates why a selective lookup can be cheap while the same subplan over the whole corpus dominates latency. Name sorting must evaluate candidate keys before LIMIT; do not assume it probes only 50 contracts.

For a bounded repeatable comparison, the implementation phase should create a temporary diagnostic pytest module `app/backend/src/fastapi_app/tests/services/test_contract_sort_performance.py` (absent until the measurement task writes it; archive its exact source beside these audit reports afterward). It should use `db_session`, synthesize 1,000 then 10,000 live contracts with a fixed 1/8/32-item fanout mix, and capture actual SELECT statements/parameters executed by `get_contracts` through SQLAlchemy engine events without altering their results. For each size, measure both directions, page 1 and a later valid page, under unrestricted, ships-only, region, requested/module-search and type-filter cases. Compare baseline and candidate on the same generated population/settings; include unchanged date-issued sort as a control. Run ANALYZE on the disposable fixture tables before measurements, exclude warm-up, and record five measured samples rather than one timing.

```powershell
python -m pdm run pytest src/fastapi_app/tests/services/test_contract_sort_performance.py -q -s
```

Replay each captured page and count SELECT with the same driver parameters prefixed by `EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON)`; use the existing async session connection and `exec_driver_sql`, with a session-local statement timeout. Record server execution time, buffers, temp spills, row counts, item-index use, subplan loops, joined fanout versus grouped parents, query count and end-to-end service time. Preserve SQL placeholders and avoid logging credentials or any live user search values. The page subplan must not perform a full item-table scan per parent or multiply with joined fanout; investigate any such plan before proceeding. Counts should lose the Name-only item join, not acquire the headline scalar.

Synthetic measurements establish comparative scaling, not production P95. Where an already-authorized representative read-only snapshot is available, repeat its supported queries there without test-fixture setup, DDL, ingestion or cache clearing. Report inability to obtain representative evidence as an explicit performance limitation. Do not invent a pass threshold from the performance spec's placeholder targets; any material slowdown or timeout needs explanation and review. No speculative index/migration is authorized by this note.

## Evidence limits

Inspected source and intentional tests against production-code base `d43da7c`; coordinator documentation commits advanced worktree HEAD to `2d19d06` during investigation. No production file was edited. Python 3.14 executed the Unicode whitespace enumeration successfully. `importlib.util.find_spec` found no SQLAlchemy, asyncpg or pytest in the current interpreter; no backend suite, SQL compilation, database query, benchmark, dependency installation, external acquisition or server startup ran. Git read initially hit the sandbox ownership guard; a command-scoped `safe.directory` for this exact worktree allowed status/revision inspection without changing global Git configuration.
