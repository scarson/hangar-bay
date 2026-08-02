# --- Service-Level Test Setup ---
#
# The tests in this file focus on the business logic within the service layer.
# They follow patterns from `design/fastapi/guides/09-testing-strategies.md`.
#
# Key Fixture:
#
# - `db_session: AsyncSession`: Provided by `conftest.py`, this fixture gives
#   each test function a clean, isolated, PostgreSQL test-database session (the dedicated `hangar_bay_test` DB via `DATABASE_URL_TESTS`).
#   It handles the creation and teardown of the database schema, ensuring
#   tests do not interfere with each other and can run in parallel safely.
#
# Testing Approach:
# These tests call the service functions (e.g., `get_contracts`) directly,
# passing the `db_session` fixture to them. This allows for focused testing
# of data manipulation and business logic without the overhead of the HTTP
# request/response cycle.
#
# Data Persistence in Tests:
# To save data to the database within a test, use `await db_session.flush()`.
# Do NOT use `await db_session.commit()`, as the fixture manages the
# transaction lifecycle.

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from datetime import datetime, timedelta, timezone
from fastapi_app.models.contracts import Contract, ContractItem
from fastapi_app.schemas.contracts import (
    ContractFilters,
    SortableContractFields,
    SortDirection,
)
import fastapi_app.services.contract_service as contract_service
from fastapi_app.services.contract_service import get_contracts

# Mark all tests in this file as asyncio
pytestmark = pytest.mark.asyncio





async def test_search_by_ship_name(db_session: AsyncSession, setup_contracts):
    """Test searching for contracts by a specific ship name."""
    filters = ContractFilters(search="Tristan")

    result = await get_contracts(db=db_session, filters=filters)

    assert result.total == 2
    assert len(result.items) == 2
    # Verify that both contracts containing a Tristan are returned
    contract_ids = {c.contract_id for c in result.items}
    assert 101 in contract_ids
    assert 103 in contract_ids


async def test_search_by_contract_title(db_session: AsyncSession, setup_contracts):
    """Test searching for contracts by a word in the title."""
    filters = ContractFilters(search="Starter")

    result = await get_contracts(db=db_session, filters=filters)

    assert result.total == 1
    assert result.items[0].contract_id == 103


async def test_filter_by_min_price(db_session: AsyncSession, setup_contracts):
    """Test filtering contracts by a minimum price."""
    filters = ContractFilters(min_price=10_000_000)

    result = await get_contracts(db=db_session, filters=filters)

    assert result.total == 1
    assert result.items[0].contract_id == 104


async def test_filter_by_max_price(db_session: AsyncSession, setup_contracts):
    """Test filtering contracts by a maximum price."""
    filters = ContractFilters(max_price=1_500_000)

    result = await get_contracts(db=db_session, filters=filters)

    assert result.total == 1
    assert result.items[0].contract_id == 101


async def test_filter_by_price_and_collateral(db_session: AsyncSession, setup_contracts):
    """Test filtering with a combination of price and collateral."""
    filters = ContractFilters(min_price=4_000_000, max_collateral=1_000_000)

    result = await get_contracts(db=db_session, filters=filters)

    assert result.total == 1
    assert result.items[0].contract_id == 102


async def test_filter_by_type_id(db_session: AsyncSession, setup_contracts):
    """Test filtering by a specific ship type ID."""
    # Venture's type_id is 17480
    filters = ContractFilters(type_ids=[17480])

    result = await get_contracts(db=db_session, filters=filters)

    assert result.total == 1
    assert result.items[0].contract_id == 103


async def test_filter_by_region_id(db_session: AsyncSession, setup_contracts):
    """Test filtering by a specific region ID."""
    # Region ID for the "Mining Starter Pack"
    filters = ContractFilters(region_ids=[10000020])

    result = await get_contracts(db=db_session, filters=filters)

    assert result.total == 1
    assert result.items[0].contract_id == 103


async def test_filter_by_is_bpc(db_session: AsyncSession, setup_contracts):
    """Test filtering for contracts that are blueprint copies."""
    filters = ContractFilters(is_bpc=True)

    result = await get_contracts(db=db_session, filters=filters)

    assert result.total == 1
    assert result.items[0].contract_id == 102
    assert result.items[0].items[0].is_blueprint_copy is True


async def test_sorting_by_price_asc(db_session: AsyncSession, setup_contracts):
    """Test sorting contracts by price in ascending order."""
    filters = ContractFilters(sort_by=SortableContractFields.price, sort_direction=SortDirection.asc)

    result = await get_contracts(db=db_session, filters=filters)

    assert result.total == 4
    prices = [c.price for c in result.items]
    assert prices == [1_000_000, 2_500_000, 5_000_000, 200_000_000]


async def test_pagination(db_session: AsyncSession, setup_contracts):
    """Test the pagination functionality."""
    # Get the second page, with 2 items per page
    filters = ContractFilters(page=2, size=2, sort_by=SortableContractFields.price, sort_direction=SortDirection.asc)

    result = await get_contracts(db=db_session, filters=filters)

    assert result.total == 4
    assert result.page == 2
    assert result.size == 2
    assert len(result.items) == 2
    # The second page should have the 3rd and 4th items from the sorted list
    contract_ids = {c.contract_id for c in result.items}
    assert 102 in contract_ids  # price 5,000,000
    assert 104 in contract_ids  # price 200,000,000


async def test_complex_query(db_session: AsyncSession, setup_contracts):
    """Test a complex query with multiple filters, sorting, and pagination."""
    # Search for "Tristan", in region 10000002, max price 2_000_000, sorted by price asc
    filters = ContractFilters(
        search="Tristan",
        region_ids=[10000002],
        max_price=2_000_000,
        sort_by=SortableContractFields.price,
        sort_direction=SortDirection.asc
    )

    result = await get_contracts(db=db_session, filters=filters)

    # Only contract 101 should match all these criteria
    assert result.total == 1
    assert len(result.items) == 1
    assert result.items[0].contract_id == 101


async def test_zero_results_returns_empty_page(
    db_session: AsyncSession, setup_contracts, monkeypatch
):
    """No matching contracts short-circuits to an empty page that still echoes page/size.

    The short-circuit is pinned by the key event it emits, not by the response alone.
    Deleting the early return would still yield an empty response through the normal
    pagination path, so the response assertions cannot tell the two branches apart. The
    early return's search_terms payload carries exactly four keys; the normal path's
    carries eight, which is the difference this test locks.
    """
    events = []
    real_log_key_event = contract_service.log_key_event

    def recording_log_key_event(*args, **kwargs):
        events.append(kwargs)
        return real_log_key_event(*args, **kwargs)

    monkeypatch.setattr(contract_service, "log_key_event", recording_log_key_event)

    filters = ContractFilters(search="no-such-ship-name-anywhere", page=1, size=10)

    result = await get_contracts(db_session, filters)

    assert result.total == 0
    assert result.items == []
    assert result.page == 1
    assert result.size == 10

    assert len(events) == 1
    assert events[0]["event"] == "contract_search_executed"
    assert events[0]["success"] is True
    assert events[0]["results_count"] == 0
    assert set(events[0]["search_terms"]) == {"search", "type_ids", "page", "size"}
    assert events[0]["search_terms"]["search"] == "no-such-ship-name-anywhere"
    assert events[0]["search_terms"]["page"] == 1
    assert events[0]["search_terms"]["size"] == 10


async def test_unmapped_sort_falls_back_to_date_issued(db_session: AsyncSession):
    """An unmapped sort key falls back to date_issued with the default desc direction.

    sort_by is NON-optional in the schema (default SortableContractFields.date_issued,
    sort_direction default desc), so SORT_MAP.get(filters.sort_by) can only return None
    if validation is bypassed — the fallback branch is defensive. It is characterized via
    model_construct, which skips validation while still populating declared defaults, so
    only the overrides need passing.

    TEST-3: setup_contracts is deliberately NOT used here — its date_issued values are
    independent datetime.now() calls (nondeterministic, possibly equal). These three
    contracts carry fixed, strictly distinct date_issued values in a region id no other
    fixture uses.

    date_expired is relative to now while date_issued stays fixed: the ordering under
    test needs stable, distinct issue dates, but the liveness filter needs the rows to
    outlive the clock. A fixed expiry silently empties this result set once real time
    passes it.
    """
    region_id = 99999901
    base_date = datetime(2026, 7, 1, tzinfo=timezone.utc)
    expiry_date = datetime.now(timezone.utc) + timedelta(days=30)
    db_session.add_all([
        Contract(
            contract_id=940000 + offset,
            title=f"Sort Fallback {offset}",
            price=1_000_000,
            collateral=0,
            status="outstanding",
            type="item_exchange",
            issuer_id=940,
            issuer_corporation_id=940,
            start_location_id=60003760,
            start_location_system_id=30000142,
            start_location_region_id=region_id,
            for_corporation=False,
            date_issued=base_date + timedelta(days=offset - 1),
            date_expired=expiry_date,
        )
        for offset in (1, 2, 3)
    ])
    await db_session.flush()

    filters = ContractFilters.model_construct(sort_by=None, region_ids=[region_id])

    result = await get_contracts(db_session, filters)

    # Fallback = Contract.date_issued, default direction desc, contract_id tiebreak:
    assert [item.contract_id for item in result.items] == [940003, 940002, 940001]


async def test_db_error_logs_failure_and_reraises(
    db_session: AsyncSession, setup_contracts, monkeypatch
):
    """A query failure logs a failure key event and the original exception propagates."""
    events = []
    real_log_key_event = contract_service.log_key_event

    def recording_log_key_event(*args, **kwargs):
        events.append(kwargs)
        return real_log_key_event(*args, **kwargs)

    monkeypatch.setattr(contract_service, "log_key_event", recording_log_key_event)

    boom_error = RuntimeError("simulated db failure")

    async def boom(*args, **kwargs):
        raise boom_error

    monkeypatch.setattr(db_session, "execute", boom)

    filters = ContractFilters(page=1, size=10)
    with pytest.raises(RuntimeError, match="simulated db failure") as excinfo:
        await get_contracts(db_session, filters)

    # The except block re-raises bare, so the ORIGINAL exception object propagates —
    # not an equivalent instance wrapped around the same message.
    assert excinfo.value is boom_error

    failure_events = [e for e in events if e.get("success") is False]
    assert len(failure_events) == 1
    assert failure_events[0]["event"] == "contract_search_executed"
    assert failure_events[0]["error_message"] == "simulated db failure"
    assert set(failure_events[0]["search_terms"]) == {
        "search",
        "type_ids",
        "min_price",
        "max_price",
        "page",
        "size",
    }


async def test_joined_pagination_tiebreaks_equal_sort_keys_by_contract_id(
    db_session: AsyncSession, setup_contracts
):
    """Equal sort keys under the item join split deterministically on contract_id ASC.

    SQLA-1 net: 930001 carries TWO matching items, so the joined row count (3) exceeds the
    contract count (2). Every item shares one type_name, so the aggregate sort key ties and
    930001's second row lands at offset 1 — paginating the joined rows directly repeats
    930001 on page 2 and drops 930002 entirely. This is the assertion that bites: merging
    the joined fetch path into the simple one turns page 2 into [930001]. The pages are
    also asserted to partition the result set exactly, with no contract skipped or repeated
    across the boundary (TEST-4).

    Scope limit — what this test does NOT lock: the `Contract.contract_id.asc()` tiebreaker
    on the joined path's id_query. At this fixture size Postgres feeds the final sort from a
    GroupAggregate that is already sorted by contract_id, so tied keys emerge ascending
    whether or not the tiebreaker is present and its removal is unobservable here. The
    tiebreaker matters at scale, where a HashAggregate emits groups in arbitrary order; it
    is covered behaviorally by test_pagination_sorted_by_ship_name_no_duplicates in
    tests/api/test_contract_filters.py, whose larger row set does reach that plan.
    """
    ship_name = "Tiebreakship"

    def tiebreak_item(record_id: int, type_id: int) -> ContractItem:
        return ContractItem(
            record_id=record_id,
            type_id=type_id,
            type_name=ship_name,
            quantity=1,
            is_included=True,
            is_singleton=False,
            is_blueprint_copy=False,
        )

    def tiebreak_contract(contract_id: int, items: list[ContractItem]) -> Contract:
        return Contract(
            contract_id=contract_id,
            title="Tiebreak Listing",
            price=500.0,
            collateral=0,
            status="outstanding",
            type="item_exchange",
            issuer_id=930,
            issuer_corporation_id=930,
            start_location_id=60003760,
            start_location_system_id=30000142,
            start_location_region_id=10000002,
            for_corporation=False,
            date_issued=datetime.now(timezone.utc),
            date_expired=datetime.now(timezone.utc) + timedelta(days=7),
            items=items,
        )

    db_session.add_all([
        tiebreak_contract(930002, [tiebreak_item(9300021, 587)]),
        tiebreak_contract(930001, [
            tiebreak_item(9300011, 587),
            tiebreak_item(9300012, 588),
        ]),
    ])
    await db_session.flush()

    filters_p1 = ContractFilters(search=ship_name, sort_by=SortableContractFields.ship_name,
                                 sort_direction=SortDirection.asc, page=1, size=1)
    filters_p2 = filters_p1.model_copy(update={"page": 2})

    page1 = await get_contracts(db_session, filters_p1)
    page2 = await get_contracts(db_session, filters_p2)

    assert page1.total == 2 and page2.total == 2
    assert [c.contract_id for c in page1.items] == [930001]
    assert [c.contract_id for c in page2.items] == [930002]

    page1_ids = {c.contract_id for c in page1.items}
    page2_ids = {c.contract_id for c in page2.items}
    assert page1_ids | page2_ids == {930001, 930002}
    assert page1_ids & page2_ids == set()


# --- Expiry filtering -------------------------------------------------------
#
# A contract past date_expired cannot be accepted in game, so listing it wastes a
# slot in a result set and, worse, sorting by "Time left" ascending puts every dead
# contract ahead of every live one. These use a dedicated region id so no other
# fixture's rows leak in, and expiry offsets are whole days so app/DB clock skew
# cannot flip an assertion.

EXPIRY_REGION_ID = 99999902


def _expiry_contract(contract_id: int, *, expired: bool, items: list[ContractItem] | None = None) -> Contract:
    now = datetime.now(timezone.utc)
    return Contract(
        contract_id=contract_id,
        title=f"Expiry Case {contract_id}",
        price=1_000_000,
        collateral=0,
        status="outstanding",
        type="item_exchange",
        issuer_id=941,
        issuer_corporation_id=941,
        start_location_id=60003760,
        start_location_system_id=30000142,
        start_location_region_id=EXPIRY_REGION_ID,
        for_corporation=False,
        date_issued=now - timedelta(days=20),
        date_expired=now - timedelta(days=2) if expired else now + timedelta(days=5),
        items=items or [],
    )


async def test_expired_contracts_are_excluded_from_the_list(db_session: AsyncSession):
    """The simple (unjoined) path drops contracts whose date_expired has passed."""
    db_session.add_all([
        _expiry_contract(941001, expired=False),
        _expiry_contract(941002, expired=True),
        _expiry_contract(941003, expired=False),
    ])
    await db_session.flush()

    result = await get_contracts(db_session, ContractFilters(region_ids=[EXPIRY_REGION_ID]))

    # Sorted, not positional: these fixtures' date_issued values come from separate
    # datetime.now() calls microseconds apart, so their order under the default
    # date_issued-desc sort is not deterministic (TEST-3). Exclusion is what this pins.
    assert sorted(item.contract_id for item in result.items) == [941001, 941003]
    # total comes from a separate count query; if the predicate reaches only the fetch
    # path the pages shrink while total keeps counting the dead rows (SQLA-1's shape).
    assert result.total == 2


async def test_expired_exclusion_also_applies_on_the_item_joined_path(db_session: AsyncSession):
    """`search` forces an outer join to ContractItem, which is a different query plan
    and a different fetch function — the predicate must hold there too."""
    def item(record_id: int) -> ContractItem:
        return ContractItem(
            record_id=record_id, type_id=587, type_name="Rifter", quantity=1,
            is_included=True, is_singleton=False, is_blueprint_copy=False,
        )

    db_session.add_all([
        _expiry_contract(941011, expired=False, items=[item(9411)]),
        _expiry_contract(941012, expired=True, items=[item(9412)]),
    ])
    await db_session.flush()

    result = await get_contracts(
        db_session,
        ContractFilters(region_ids=[EXPIRY_REGION_ID], search="Rifter"),
    )

    assert [item_.contract_id for item_ in result.items] == [941011]
    assert result.total == 1


async def test_expired_exclusion_holds_across_page_boundaries(db_session: AsyncSession):
    """TEST-4: a filter that leaks on later pages is invisible to a single-page test.
    Five live and four dead contracts, paged two at a time — the union of pages must be
    exactly the live set, with no duplicates and no dead rows anywhere."""
    live_ids = [941101, 941103, 941105, 941107, 941109]
    dead_ids = [941102, 941104, 941106, 941108]
    db_session.add_all(
        [_expiry_contract(cid, expired=False) for cid in live_ids]
        + [_expiry_contract(cid, expired=True) for cid in dead_ids]
    )
    await db_session.flush()

    seen: list[int] = []
    for page in (1, 2, 3):
        result = await get_contracts(
            db_session,
            ContractFilters(region_ids=[EXPIRY_REGION_ID], page=page, size=2),
        )
        assert result.total == len(live_ids)
        seen.extend(item.contract_id for item in result.items)

    assert sorted(seen) == live_ids           # every live contract, exactly once
    assert not set(seen) & set(dead_ids)      # and no dead one on any page


# --- Delisted (sold) contract filtering ------------------------------------
#
# Expiry only catches contracts that ran out of time. A contract that is ACCEPTED
# vanishes from ESI's public list while keeping a future date_expired, so it passes
# the expiry filter and shows as available for up to two weeks. Ingestion stamps
# last_seen_at on every upsert; a contract is present if its stamp matches the newest
# stamp IN ITS OWN REGION. Per-region, not global, so a region whose fetch failed
# stalls its own watermark instead of erasing every contract it holds.

DELISTED_REGION_A = 99999911
DELISTED_REGION_B = 99999912


# The predicate has two branches that must agree. A region named in
# AGGREGATION_REGION_IDS is judged by an UNCORRELATED per-region watermark, evaluated
# once per query; any other region falls back to the correlated form. Configuration is an
# optimization hint, so every delisting case below runs under both branches and must give
# the same answer. Without this parametrisation the fast branch has no coverage at all —
# the default config names only The Forge, and these fixtures use two private region ids.
@pytest.fixture(params=["region-configured", "region-not-configured"])
def liveness_branch(request, monkeypatch):
    """Run a delisting case under the fast branch and the fallback branch alike."""
    configured = (
        [DELISTED_REGION_A, DELISTED_REGION_B] if request.param == "region-configured" else []
    )
    monkeypatch.setattr(
        contract_service.get_settings(), "AGGREGATION_REGION_IDS", configured
    )
    return request.param


def _seen_contract(contract_id: int, *, region: int, seen: datetime | None) -> Contract:
    now = datetime.now(timezone.utc)
    return Contract(
        contract_id=contract_id,
        title=f"Seen Case {contract_id}",
        price=1_000_000,
        collateral=0,
        status="outstanding",
        type="item_exchange",
        issuer_id=943,
        issuer_corporation_id=943,
        start_location_id=60003760,
        start_location_system_id=30000142,
        start_location_region_id=region,
        for_corporation=False,
        date_issued=now - timedelta(days=1),
        date_expired=now + timedelta(days=5),   # live, so only delisting can hide it
        last_seen_at=seen,
    )


async def test_contracts_missing_from_the_latest_run_are_excluded(db_session: AsyncSession, liveness_branch):
    """A contract not restamped by the most recent run for its region was not in ESI's
    public list any more — sold or withdrawn — so it must stop being offered."""
    latest = datetime.now(timezone.utc)
    stale = latest - timedelta(hours=2)
    db_session.add_all([
        _seen_contract(943001, region=DELISTED_REGION_A, seen=latest),
        _seen_contract(943002, region=DELISTED_REGION_A, seen=stale),   # sold
        _seen_contract(943003, region=DELISTED_REGION_A, seen=latest),
    ])
    await db_session.flush()

    result = await get_contracts(db_session, ContractFilters(region_ids=[DELISTED_REGION_A]))

    assert sorted(c.contract_id for c in result.items) == [943001, 943003]
    assert result.total == 2


async def test_a_region_whose_run_failed_keeps_all_its_contracts(db_session: AsyncSession, liveness_branch):
    """THE case that can take the site down. Region A refreshed; region B's fetch failed,
    so nothing in B was restamped. B's contracts must all remain visible — judging them
    against A's newer watermark would erase an entire region at once."""
    fresh = datetime.now(timezone.utc)
    older = fresh - timedelta(hours=3)
    db_session.add_all([
        _seen_contract(943101, region=DELISTED_REGION_A, seen=fresh),
        _seen_contract(943102, region=DELISTED_REGION_B, seen=older),
        _seen_contract(943103, region=DELISTED_REGION_B, seen=older),
    ])
    await db_session.flush()

    result = await get_contracts(
        db_session, ContractFilters(region_ids=[DELISTED_REGION_A, DELISTED_REGION_B])
    )

    assert sorted(c.contract_id for c in result.items) == [943101, 943102, 943103]
    assert result.total == 3


async def test_never_stamped_contracts_stay_visible(db_session: AsyncSession, liveness_branch):
    """Rows predating the last_seen_at column carry NULL. Treating NULL as 'not in the
    latest run' would blank the entire site between the migration and the first run —
    the migration backfills, and this pins the belt-and-braces behaviour besides."""
    db_session.add_all([
        _seen_contract(943201, region=DELISTED_REGION_A, seen=None),
        _seen_contract(943202, region=DELISTED_REGION_A, seen=None),
    ])
    await db_session.flush()

    result = await get_contracts(db_session, ContractFilters(region_ids=[DELISTED_REGION_A]))

    assert result.total == 2


# --- system_ids coverage ----------------------------------------------------
#
# start_location_system_id is populated for NPC stations and NULL for player-owned
# structures, which have no tokenless location→system route. So system_ids has
# PARTIAL coverage by construction, and a bare "N results" hides that: rows the
# user's other criteria selected are dropped for a reason unrelated to their query.
# The list response publishes the size of that residual alongside the total, the
# same convention the ecosystem uses (Adam4EVE's NoP column, EVE Tycoon's per-row
# appraisal method).

SYSTEM_COVERAGE_REGION_ID = 99999911
JITA_SYSTEM_ID = 30000142


def _coverage_contract(
    contract_id: int, *, system_id: int | None, price: float = 1_000_000
) -> Contract:
    now = datetime.now(timezone.utc)
    return Contract(
        contract_id=contract_id,
        title=f"Coverage Case {contract_id}",
        price=price,
        collateral=0,
        status="outstanding",
        type="item_exchange",
        issuer_id=951,
        issuer_corporation_id=951,
        start_location_id=60003760 if system_id is not None else 1_035_466_617_946,
        start_location_system_id=system_id,
        start_location_region_id=SYSTEM_COVERAGE_REGION_ID,
        for_corporation=False,
        date_issued=now - timedelta(days=1),
        date_expired=now + timedelta(days=5),
    )


async def test_system_ids_matches_resolved_contracts_and_reports_the_residual(
    db_session: AsyncSession,
):
    """The filter selects the rows with a known system and says how many it dropped
    for want of one — so "1 result" is readable as "1 of 3 locations we can place"."""
    db_session.add_all([
        _coverage_contract(951001, system_id=JITA_SYSTEM_ID),
        _coverage_contract(951002, system_id=None),
        _coverage_contract(951003, system_id=None),
    ])
    await db_session.flush()

    result = await get_contracts(
        db_session,
        ContractFilters(
            region_ids=[SYSTEM_COVERAGE_REGION_ID], system_ids=[JITA_SYSTEM_ID]
        ),
    )

    assert [item.contract_id for item in result.items] == [951001]
    assert result.total == 1
    assert result.unknown_system_excluded == 2


async def test_the_residual_is_absent_when_system_ids_is_not_applied(
    db_session: AsyncSession,
):
    """Nothing was excluded for want of a system, so there is no coverage figure to
    publish. Null, not 0 — 0 would assert full coverage of a filter never applied."""
    db_session.add_all([
        _coverage_contract(951011, system_id=JITA_SYSTEM_ID),
        _coverage_contract(951012, system_id=None),
    ])
    await db_session.flush()

    result = await get_contracts(
        db_session, ContractFilters(region_ids=[SYSTEM_COVERAGE_REGION_ID])
    )

    assert result.total == 2
    assert result.unknown_system_excluded is None


async def test_the_residual_counts_only_rows_the_other_filters_kept(
    db_session: AsyncSession,
):
    """The figure answers "what did the SYSTEM filter cost me", so a system-less row
    that the user's own criteria already rejected must not inflate it. Counting every
    system-less row in the corpus instead would make the number meaningless."""
    db_session.add_all([
        _coverage_contract(951021, system_id=JITA_SYSTEM_ID, price=1_000_000),
        _coverage_contract(951022, system_id=None, price=1_000_000),
        # Excluded by max_price, not by the system filter.
        _coverage_contract(951023, system_id=None, price=900_000_000),
    ])
    await db_session.flush()

    result = await get_contracts(
        db_session,
        ContractFilters(
            region_ids=[SYSTEM_COVERAGE_REGION_ID],
            system_ids=[JITA_SYSTEM_ID],
            max_price=5_000_000,
        ),
    )

    assert result.total == 1
    assert result.unknown_system_excluded == 1


async def test_the_residual_is_still_reported_when_nothing_matched(
    db_session: AsyncSession,
):
    """The empty result is exactly where the figure matters most: without it, a system
    with only structure-hosted contracts is indistinguishable from an empty one."""
    db_session.add_all([
        _coverage_contract(951031, system_id=None),
        _coverage_contract(951032, system_id=None),
    ])
    await db_session.flush()

    result = await get_contracts(
        db_session,
        ContractFilters(
            region_ids=[SYSTEM_COVERAGE_REGION_ID], system_ids=[JITA_SYSTEM_ID]
        ),
    )

    assert result.total == 0
    assert result.items == []
    assert result.unknown_system_excluded == 2


async def test_the_residual_holds_on_the_item_joined_path(db_session: AsyncSession):
    """`search` forces an outer join to ContractItem — a different query plan whose
    duplicated rows would inflate a naive count. The residual counts DISTINCT
    contracts, so a contract with three items still counts once."""
    def item(record_id: int, contract: Contract) -> ContractItem:
        return ContractItem(
            record_id=record_id, type_id=587, type_name="Rifter", quantity=1,
            is_included=True, is_singleton=False, is_blueprint_copy=False,
        )

    matched = _coverage_contract(951041, system_id=JITA_SYSTEM_ID)
    unresolved = _coverage_contract(951042, system_id=None)
    matched.items = [item(9511, matched)]
    unresolved.items = [item(9512, unresolved), item(9513, unresolved), item(9514, unresolved)]
    db_session.add_all([matched, unresolved])
    await db_session.flush()

    result = await get_contracts(
        db_session,
        ContractFilters(
            region_ids=[SYSTEM_COVERAGE_REGION_ID],
            system_ids=[JITA_SYSTEM_ID],
            search="Rifter",
        ),
    )

    assert result.total == 1
    assert result.unknown_system_excluded == 1
