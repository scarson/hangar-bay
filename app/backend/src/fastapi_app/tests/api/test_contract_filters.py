# --- Test Setup and Fixture Philosophy ---
#
# The tests in this file follow a specific pattern to ensure reliability and
# consistency, as defined in `design/fastapi/guides/09-testing-strategies.md`.
#
# Key Fixtures:
#
# - `client: AsyncClient`: Provided by `conftest.py`, this is an HTTPX client
#   that makes requests to a *real* instance of our FastAPI application. This
#   ensures we are testing against the actual application code, including all
#   routers and dependencies.
#
# - `db_session: AsyncSession`: Also from `conftest.py`, this fixture provides
#   a clean, isolated, PostgreSQL test-database session (the dedicated `hangar_bay_test` DB via `DATABASE_URL_TESTS`) for each individual
#   test function. It handles the creation and teardown of the database schema,
#   ensuring tests do not interfere with each other.
#
# How They Work Together:
# The `client` fixture uses the `test_app` fixture, which programmatically
# overrides the `get_db` dependency to point to the `db_session` for that
# specific test. This gives us the best of both worlds: testing the real app
# logic against a safe, temporary database.
#
# Data Persistence in Tests:
# To save data to the database within a test, use `await db_session.flush()`.
# Do NOT use `await db_session.commit()`, as the fixture manages the
# transaction lifecycle.

from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from fastapi_app.models import Contract, ContractItem
from fastapi_app.models.contracts import EsiTaxonomyCache
from fastapi_app.services.background_aggregation import ENRICHMENT_VERSION

# Mark all tests in this file as asyncio
pytestmark = pytest.mark.asyncio


async def test_sort_by_price_asc(
    client: AsyncClient, setup_contracts
):
    """Test sorting contracts by price in ascending order at the API level."""
    response = await client.get("/contracts/?sort_by=price&sort_direction=asc")

    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) > 1
    # Check that the prices are sorted in ascending order
    prices = [item["price"] for item in data["items"]]
    assert prices == sorted(prices)


async def test_filter_by_is_bpc(client: AsyncClient, setup_contracts):
    """Test filtering for contracts that are blueprint copies."""
    response = await client.get("/contracts/?is_bpc=true")

    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) > 0
    # Check that all returned contracts are BPCs. The row publishes the same
    # contract-level classification the filter applies, so the two cannot disagree.
    for item in data["items"]:
        assert item["is_blueprint_copy_contract"] is True


async def test_filter_by_bpc_runs(client: AsyncClient, setup_contracts):
    """Test filtering BPCs by the number of runs."""
    # There is a BPC with 10 runs in the test data.
    response = await client.get("/contracts/?is_bpc=true&min_runs=10&max_runs=10")

    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 1
    # The row publishes the run count the filter bounded — a single offered copy, so
    # blueprint_summary reports that copy's terms — and the two cannot disagree.
    assert data["items"][0]["contract_id"] == 102
    assert data["items"][0]["is_blueprint_copy_contract"] is True
    assert data["items"][0]["blueprint_summary"]["runs"] == 10


async def test_response_omits_fields_public_ingestion_cannot_populate(
    client: AsyncClient, setup_contracts
):
    """`status` and `date_completed` belong to ESI's authenticated character/corporation
    contract routes. Under public ingestion the columns behind them hold a placeholder and
    a NULL, so serving them published a value the corpus does not have."""
    response = await client.get("/contracts/")

    assert response.status_code == 200
    assert response.json()["items"], "fixture must reach the endpoint for this to mean anything"
    for contract in response.json()["items"]:
        assert "status" not in contract
        assert "date_completed" not in contract


async def test_detail_response_omits_fields_public_ingestion_cannot_populate(
    client: AsyncClient, setup_contracts
):
    """The detail endpoint serializes the same schema and must not drift from the list."""
    response = await client.get("/contracts/101")

    assert response.status_code == 200
    contract = response.json()
    assert contract["contract_id"] == 101
    assert "status" not in contract
    assert "date_completed" not in contract


async def test_detail_item_response_omits_fields_public_ingestion_cannot_populate(
    client: AsyncClient, setup_contracts
):
    """`is_singleton` and `raw_quantity` belong to ESI's authenticated character/corporation
    contract-ITEM routes. The public item route carries neither, so under public ingestion
    is_singleton is the mapping default on every row and raw_quantity is NULL on every row.

    Swept across every fixture contract rather than one: the detail endpoint is the only
    place items reach the wire, so this is the whole surface those two fields could leak
    through."""
    seen_items = 0
    for contract_id in (101, 102, 103, 104):
        response = await client.get(f"/contracts/{contract_id}")

        assert response.status_code == 200
        contract = response.json()
        assert contract["contract_id"] == contract_id
        assert contract["items"], f"contract {contract_id} must carry items"
        for item in contract["items"]:
            assert "is_singleton" not in item
            assert "raw_quantity" not in item
            seen_items += 1

    assert seen_items == 5, f"fixture item count changed: {seen_items}"


async def test_complex_filter_api(client: AsyncClient, setup_contracts):
    """Test a complex query combining multiple filters at the API level."""
    # Search for a specific ship (Tristan), with a max price, sorted by price.
    params = {
        "search": "Tristan",
        "max_price": 1_500_000,
        "sort_by": "price",
        "sort_direction": "asc",
    }
    response = await client.get("/contracts/", params=params)

    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 1
    assert data["items"][0]["primary_label"] == "Tristan"
    assert data["items"][0]["price"] < 1_500_000


async def test_filter_by_region_ids_repeated_query_params(
    client: AsyncClient, setup_contracts
):
    """Regression (FASTAPI-1): list filters must bind as repeated query params."""
    response = await client.get("/contracts/?region_ids=10000020")

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert [c["contract_id"] for c in data["items"]] == [103]


async def test_filter_by_multiple_region_ids(client: AsyncClient, setup_contracts):
    response = await client.get("/contracts/?region_ids=10000002&region_ids=10000020")

    assert response.status_code == 200
    assert response.json()["total"] == 4


async def test_filter_by_type_ids_repeated_query_params(
    client: AsyncClient, setup_contracts
):
    response = await client.get("/contracts/?type_ids=17480")

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["contract_id"] == 103


async def test_filter_by_system_ids_repeated_query_params(
    client: AsyncClient, setup_contracts
):
    """Regression (FASTAPI-1/TEST-1): system_ids must bind and filter over HTTP.

    Fixture: contract 103 is the only one in solar system 30002187; 101/102/104
    share system 30000142.
    """
    response = await client.get("/contracts/?system_ids=30002187")

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert [c["contract_id"] for c in data["items"]] == [103]


async def test_filter_by_multiple_system_ids(client: AsyncClient, setup_contracts):
    """Guard against over-filtering: the two systems together cover all 4 contracts."""
    response = await client.get(
        "/contracts/?system_ids=30000142&system_ids=30002187"
    )

    assert response.status_code == 200
    assert response.json()["total"] == 4


async def test_filter_by_station_ids_repeated_query_params(
    client: AsyncClient, setup_contracts
):
    """Regression (FASTAPI-1/TEST-1): station_ids must bind and filter over HTTP.

    Fixture: contract 103 is the only one at station 60008494; 101/102/104 share
    station 60003760.
    """
    response = await client.get("/contracts/?station_ids=60008494")

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert [c["contract_id"] for c in data["items"]] == [103]


async def test_filter_by_multiple_station_ids(client: AsyncClient, setup_contracts):
    """Guard against over-filtering: the two stations together cover all 4 contracts."""
    response = await client.get(
        "/contracts/?station_ids=60003760&station_ids=60008494"
    )

    assert response.status_code == 200
    assert response.json()["total"] == 4


async def test_id_list_filters_are_query_params_in_openapi_schema():
    """The generated schema must expose the ID lists where browser clients can use them."""
    from fastapi_app.main import app

    schema = app.openapi()
    operation = schema["paths"]["/contracts/"]["get"]

    assert "requestBody" not in operation
    param_names = {p["name"] for p in operation["parameters"]}
    assert {
        "region_ids", "system_ids", "station_ids", "type_ids", "contract_type",
        "category_id", "group_id",
    } <= param_names


async def test_pagination_with_search_returns_full_distinct_pages(
    client: AsyncClient, db_session: AsyncSession
):
    """Regression (SQLA-1/TEST-4): offset/limit must apply to distinct contracts,
    not joined rows. Three contracts x two matching items each; size=2 must give
    pages of [2, 1] contracts with no overlap."""
    now = datetime.now(timezone.utc)
    for n, cid in enumerate((201, 202, 203)):
        db_session.add(
            Contract(
                contract_id=cid, title=f"Grid Pack {cid}", price=(n + 1) * 1_000_000,
                collateral=0.0, status="outstanding", type="item_exchange",
                issuer_id=1, issuer_corporation_id=1, for_corporation=False,
                is_ship_contract=True, start_location_id=60003760,
                date_issued=now, date_expired=now + timedelta(days=7),
                items=[
                    ContractItem(
                        record_id=cid * 10 + 1, type_id=587,
                        type_name="Gridrunner Alpha", quantity=1,
                        is_included=True, is_singleton=False,
                    ),
                    ContractItem(
                        record_id=cid * 10 + 2, type_id=588,
                        type_name="Gridrunner Beta", quantity=1,
                        is_included=True, is_singleton=False,
                    ),
                ],
            )
        )
    await db_session.flush()

    base = "/contracts/?search=Gridrunner&size=2&sort_by=price&sort_direction=asc"
    page1 = (await client.get(f"{base}&page=1")).json()
    page2 = (await client.get(f"{base}&page=2")).json()

    assert page1["total"] == 3
    assert page2["total"] == 3
    ids1 = [c["contract_id"] for c in page1["items"]]
    ids2 = [c["contract_id"] for c in page2["items"]]
    assert len(ids1) == 2, f"page 1 short: {ids1}"
    assert len(ids2) == 1, f"page 2 wrong length: {ids2}"
    assert set(ids1) & set(ids2) == set(), "contract duplicated across pages"
    assert set(ids1) | set(ids2) == {201, 202, 203}, "contract skipped"
    assert ids1 == [201, 202], "price-asc order violated"


async def test_pagination_sorted_by_ship_name_no_duplicates(
    client: AsyncClient, db_session: AsyncSession
):
    """ship_name sort forces the item join even without filters; same invariants,
    with contract_id as the tiebreaker when the aggregate sort key ties."""
    now = datetime.now(timezone.utc)
    for cid in (301, 302, 303):
        db_session.add(
            Contract(
                contract_id=cid, title=f"Hull Lot {cid}", price=1_000_000,
                collateral=0.0, status="outstanding", type="item_exchange",
                issuer_id=1, issuer_corporation_id=1, for_corporation=False,
                is_ship_contract=True, start_location_id=60003760,
                date_issued=now, date_expired=now + timedelta(days=7),
                items=[
                    ContractItem(
                        record_id=cid * 10 + 1, type_id=587,
                        type_name="Atron", quantity=1,
                        is_included=True, is_singleton=False,
                    ),
                    ContractItem(
                        record_id=cid * 10 + 2, type_id=588,
                        type_name="Breacher", quantity=1,
                        is_included=True, is_singleton=False,
                    ),
                ],
            )
        )
    await db_session.flush()

    base = "/contracts/?sort_by=ship_name&sort_direction=asc&size=2"
    ids1 = [c["contract_id"] for c in (await client.get(f"{base}&page=1")).json()["items"]]
    ids2 = [c["contract_id"] for c in (await client.get(f"{base}&page=2")).json()["items"]]

    assert ids1 == [301, 302]
    assert ids2 == [303]


async def test_pagination_with_is_bpc_returns_full_distinct_pages(
    client: AsyncClient, db_session: AsyncSession
):
    """Regression (SQLA-1/TEST-4): the is_bpc trigger also forces the item join, so
    page boundaries must apply to distinct contracts, not joined rows. Three BPC
    contracts x two blueprint-copy items each; size=2 must give pages of [2, 1]
    contracts with no overlap and no skips."""
    now = datetime.now(timezone.utc)
    for n, cid in enumerate((401, 402, 403)):
        db_session.add(
            Contract(
                contract_id=cid, title=f"BPC Bundle {cid}", price=(n + 1) * 1_000_000,
                collateral=0.0, status="outstanding", type="item_exchange",
                issuer_id=1, issuer_corporation_id=1, for_corporation=False,
                is_ship_contract=True, start_location_id=60003760,
                date_issued=now, date_expired=now + timedelta(days=7),
                items=[
                    ContractItem(
                        record_id=cid * 10 + 1, type_id=621,
                        type_name="Caracal Blueprint", quantity=1,
                        is_included=True, is_singleton=True, is_blueprint_copy=True,
                        raw_quantity=10,
                    ),
                    ContractItem(
                        record_id=cid * 10 + 2, type_id=622,
                        type_name="Moa Blueprint", quantity=1,
                        is_included=True, is_singleton=True, is_blueprint_copy=True,
                        raw_quantity=10,
                    ),
                ],
            )
        )
    await db_session.flush()

    base = "/contracts/?is_bpc=true&size=2&sort_by=price&sort_direction=asc"
    page1 = (await client.get(f"{base}&page=1")).json()
    page2 = (await client.get(f"{base}&page=2")).json()

    assert page1["total"] == 3
    assert page2["total"] == 3
    ids1 = [c["contract_id"] for c in page1["items"]]
    ids2 = [c["contract_id"] for c in page2["items"]]
    assert len(ids1) == 2, f"page 1 short: {ids1}"
    assert len(ids2) == 1, f"page 2 wrong length: {ids2}"
    assert set(ids1) & set(ids2) == set(), "contract duplicated across pages"
    assert set(ids1) | set(ids2) == {401, 402, 403}, "contract skipped"
    assert ids1 == [401, 402], "price-asc order violated"


async def test_filter_by_is_ship_contract(client: AsyncClient, db_session: AsyncSession):
    """F002 Criterion 1.1 enabler: the default UI view is ship contracts only,
    which requires a contract-level is_ship_contract filter (mirrors is_bpc)."""
    now = datetime.now(timezone.utc)

    def make_contract(cid: int, is_ship: bool) -> Contract:
        return Contract(
            contract_id=cid, title=f"Contract {cid}", price=1_000_000,
            collateral=0.0, status="outstanding", type="item_exchange",
            issuer_id=1, issuer_corporation_id=1, for_corporation=False,
            is_ship_contract=is_ship, start_location_id=60003760,
            date_issued=now, date_expired=now + timedelta(days=7),
        )

    db_session.add_all([make_contract(401, True), make_contract(402, False)])
    await db_session.flush()

    filtered = (await client.get("/contracts/?is_ship_contract=true")).json()
    assert filtered["total"] == 1
    assert filtered["items"][0]["contract_id"] == 401

    unfiltered = (await client.get("/contracts/")).json()
    assert unfiltered["total"] == 2

    non_ship = (await client.get("/contracts/?is_ship_contract=false")).json()
    assert non_ship["total"] == 1
    assert non_ship["items"][0]["contract_id"] == 402



async def test_detail_still_serves_an_expired_contract(
    client: AsyncClient, db_session: AsyncSession
):
    """The LIST endpoint hides expired contracts; the DETAIL endpoint must not.

    A link pasted into chat routinely outlives the contract it points at, and 404-ing
    yesterday's link reads as a broken site rather than an expired deal. This pins the
    asymmetry deliberately, so a later change that "consistently" filters both does not
    slip through as a tidy-up.
    """
    from datetime import timedelta, timezone

    now = datetime.now(timezone.utc)
    db_session.add(
        Contract(
            contract_id=942001,
            title="Long Dead Listing",
            price=1_000_000,
            collateral=0,
            status="outstanding",
            type="item_exchange",
            issuer_id=942,
            issuer_corporation_id=942,
            start_location_id=60003760,
            start_location_system_id=30000142,
            start_location_region_id=99999903,
            for_corporation=False,
            date_issued=now - timedelta(days=20),
            date_expired=now - timedelta(days=2),
        )
    )
    await db_session.flush()

    listed = await client.get("/contracts/?region_ids=99999903")
    assert listed.status_code == 200
    assert listed.json()["total"] == 0          # absent from the list

    detail = await client.get("/contracts/942001")
    assert detail.status_code == 200            # but still reachable by direct link
    assert detail.json()["contract_id"] == 942001


# --- ESI shape fidelity -----------------------------------------------------
#
# The tests below pin behaviour against the shapes ESI's PUBLIC contract routes
# actually emit, which differ from the shapes the shared `setup_contracts`
# fixture writes. Verified 2026-08-01 against
# https://esi.evetech.net/meta/openapi.json plus a live sample of 7,292
# contracts / 1,658 item rows:
#
#   * `is_blueprint_copy` is a present-when-true flag. It was `true` on 1,396
#     item rows and ABSENT on the other 262 — never once `false`. So the column
#     is True-or-NULL in production, and NULL means "not a copy".
#   * `start_location_id` is NOT in the response schema's `required` array, so a
#     spec-conformant payload may omit it and the column is nullable.
#
# Any test that relies on `setup_contracts` writing `is_blueprint_copy=False`
# is therefore testing a shape production never produces (see the fixture note
# in conftest.py).


async def test_is_bpc_false_matches_items_esi_left_unmarked(
    client: AsyncClient, db_session: AsyncSession
):
    """is_bpc=false must treat a NULL is_blueprint_copy as "not a copy".

    ESI never sends is_blueprint_copy=false, so `== False` matches zero rows in
    production and the false branch of the filter returns an empty list.
    """
    now = datetime.now(timezone.utc)
    db_session.add_all(
        [
            Contract(
                contract_id=951001,
                title="Plain Hull",
                price=1_000_000,
                collateral=0,
                status="outstanding",
                type="item_exchange",
                issuer_id=951,
                issuer_corporation_id=951,
                start_location_id=60003760,
                start_location_region_id=99999951,
                for_corporation=False,
                date_issued=now,
                date_expired=now + timedelta(days=7),
                items=[
                    ContractItem(
                        record_id=9510011,
                        type_id=587,
                        type_name="Tristan",
                        quantity=1,
                        is_included=True,
                        is_singleton=False,
                        # ESI omitted the flag; ingestion writes NULL, not False.
                        is_blueprint_copy=None,
                    )
                ],
            ),
            Contract(
                contract_id=951002,
                title="Copy Only",
                price=2_000_000,
                collateral=0,
                status="outstanding",
                type="item_exchange",
                issuer_id=951,
                issuer_corporation_id=951,
                start_location_id=60003760,
                start_location_region_id=99999951,
                for_corporation=False,
                date_issued=now,
                date_expired=now + timedelta(days=7),
                items=[
                    ContractItem(
                        record_id=9510021,
                        type_id=621,
                        type_name="Caracal Blueprint",
                        quantity=1,
                        is_included=True,
                        is_singleton=True,
                        is_blueprint_copy=True,
                    )
                ],
            ),
        ]
    )
    await db_session.flush()

    non_copies = await client.get("/contracts/?region_ids=99999951&is_bpc=false")
    assert non_copies.status_code == 200
    assert [c["contract_id"] for c in non_copies.json()["items"]] == [951001]

    # The true branch must stay exact — a fix that widens `false` must not also
    # start matching unmarked items as copies.
    copies = await client.get("/contracts/?region_ids=99999951&is_bpc=true")
    assert copies.status_code == 200
    assert [c["contract_id"] for c in copies.json()["items"]] == [951002]


async def test_contract_response_exposes_collateral(
    client: AsyncClient, db_session: AsyncSession
):
    """collateral is filterable and sortable, so it must be readable in the payload.

    Without it a client can sort by a number it cannot show, and a courier's
    single most important term is invisible.
    """
    now = datetime.now(timezone.utc)
    db_session.add(
        Contract(
            contract_id=952001,
            title="Hauling Job",
            price=0,
            collateral=8_000_000_000,
            status="outstanding",
            type="courier",
            issuer_id=952,
            issuer_corporation_id=952,
            start_location_id=60013288,
            end_location_id=60003145,
            start_location_region_id=99999952,
            for_corporation=False,
            date_issued=now,
            date_expired=now + timedelta(days=7),
            reward=80_000_000,
            volume=899_999.97,
        )
    )
    await db_session.flush()

    listed = await client.get("/contracts/?region_ids=99999952")
    assert listed.status_code == 200
    assert listed.json()["items"][0]["collateral"] == 8_000_000_000

    detail = await client.get("/contracts/952001")
    assert detail.status_code == 200
    assert detail.json()["collateral"] == 8_000_000_000


async def test_serializes_a_contract_esi_sent_without_a_start_location(
    client: AsyncClient, db_session: AsyncSession
):
    """A NULL start_location_id must serialize, not 500.

    ESI's public-contracts schema does not list start_location_id as required, and
    the column is nullable — but the response schema declared it a bare `int`, so
    such a row fails response validation and takes down the whole page it lands on.
    """
    now = datetime.now(timezone.utc)
    db_session.add(
        Contract(
            contract_id=953001,
            title="Locationless Courier",
            price=0,
            collateral=1_000_000,
            status="outstanding",
            type="courier",
            issuer_id=953,
            issuer_corporation_id=953,
            start_location_id=None,
            start_location_region_id=99999953,
            for_corporation=False,
            date_issued=now,
            date_expired=now + timedelta(days=7),
        )
    )
    await db_session.flush()

    listed = await client.get("/contracts/?region_ids=99999953")
    assert listed.status_code == 200
    assert listed.json()["items"][0]["start_location_id"] is None

    detail = await client.get("/contracts/953001")
    assert detail.status_code == 200
    assert detail.json()["start_location_id"] is None


async def test_is_bpc_is_a_contract_level_predicate_on_a_mixed_bundle(
    client: AsyncClient, db_session: AsyncSession
):
    """is_bpc partitions contracts: true means "contains a BPC", false its negation.

    The filter is applied over a JOINED item row, so a per-item predicate makes a
    contract bundling a BPC with an ordinary item satisfy BOTH values at once —
    it has an item that is a copy AND an item that is not. The two branches must
    be exact complements, or paging through is_bpc=true and is_bpc=false shows
    the same contract twice and their totals overcount the corpus.
    """
    now = datetime.now(timezone.utc)
    db_session.add_all(
        [
            # A BPC bundled with a plain hull — the case that satisfied both filters.
            Contract(
                contract_id=954001,
                title="Blueprint And Hull Bundle",
                price=3_000_000,
                collateral=0,
                status="outstanding",
                type="item_exchange",
                issuer_id=954,
                issuer_corporation_id=954,
                start_location_id=60003760,
                start_location_region_id=99999954,
                for_corporation=False,
                date_issued=now,
                date_expired=now + timedelta(days=7),
                items=[
                    ContractItem(
                        record_id=9540011,
                        type_id=621,
                        type_name="Caracal Blueprint",
                        quantity=1,
                        is_included=True,
                        is_singleton=True,
                        is_blueprint_copy=True,
                    ),
                    ContractItem(
                        record_id=9540012,
                        type_id=587,
                        type_name="Tristan",
                        quantity=1,
                        is_included=True,
                        is_singleton=False,
                        is_blueprint_copy=None,
                    ),
                ],
            ),
            # A copy someone WANTS rather than offers. The served
            # is_blueprint_copy_contract flag counts offered items only (§3.1), so
            # the filter must agree: a want-to-buy ad is not a blueprint on sale,
            # and matching it here would put it in front of every buyer browsing
            # copies for sale.
            Contract(
                contract_id=954003,
                title="Wanted: Caracal Blueprint Copy",
                price=4_000_000,
                collateral=0,
                status="outstanding",
                type="item_exchange",
                issuer_id=954,
                issuer_corporation_id=954,
                start_location_id=60003760,
                start_location_region_id=99999954,
                for_corporation=False,
                date_issued=now,
                date_expired=now + timedelta(days=7),
                items=[
                    # Two requested rows and nothing offered. The ship carries the
                    # lowest record_id and category='ship', so every branch of the
                    # label chain that reads items would fire on it — which is the
                    # point: the label must fall through to the title instead.
                    ContractItem(
                        record_id=9540030,
                        type_id=621,
                        type_name="Caracal",
                        quantity=1,
                        is_included=False,
                        is_singleton=False,
                        is_blueprint_copy=None,
                        category="ship",
                    ),
                    ContractItem(
                        record_id=9540031,
                        type_id=621,
                        type_name="Caracal Blueprint",
                        quantity=1,
                        is_included=False,
                        is_singleton=True,
                        is_blueprint_copy=True,
                    ),
                ],
            ),
            # A contract with no copy at all, to prove false is not simply empty.
            Contract(
                contract_id=954002,
                title="Hulls Only",
                price=1_000_000,
                collateral=0,
                status="outstanding",
                type="item_exchange",
                issuer_id=954,
                issuer_corporation_id=954,
                start_location_id=60003760,
                start_location_region_id=99999954,
                for_corporation=False,
                date_issued=now,
                date_expired=now + timedelta(days=7),
                items=[
                    ContractItem(
                        record_id=9540021,
                        type_id=24698,
                        type_name="Rokh",
                        quantity=1,
                        is_included=True,
                        is_singleton=False,
                        is_blueprint_copy=None,
                    ),
                    ContractItem(
                        record_id=9540022,
                        type_id=587,
                        type_name="Tristan",
                        quantity=1,
                        is_included=True,
                        is_singleton=False,
                        is_blueprint_copy=None,
                    ),
                ],
            ),
        ]
    )
    await db_session.flush()

    copies = await client.get("/contracts/?region_ids=99999954&is_bpc=true")
    assert copies.status_code == 200
    assert [c["contract_id"] for c in copies.json()["items"]] == [954001]

    non_copies = await client.get("/contracts/?region_ids=99999954&is_bpc=false")
    assert non_copies.status_code == 200
    # The bundle contains a copy, so it is NOT a non-copy contract; the
    # want-to-buy ad offers no copy, so it is.
    assert sorted(c["contract_id"] for c in non_copies.json()["items"]) == [
        954002, 954003
    ]
    assert all(
        c["is_blueprint_copy_contract"] is False for c in non_copies.json()["items"]
    )

    # Every derived summary describes what the contract OFFERS, and the
    # want-to-buy ad offers nothing. Built from all of its items instead, it would
    # advertise the copy it is asking for as a copy for sale, headline itself with
    # the hull it wants to buy, and publish a breakdown of someone else's goods —
    # a shopping list dressed up as inventory (§3.1, Criterion 8.1).
    wanted = next(
        c for c in non_copies.json()["items"] if c["contract_id"] == 954003
    )
    assert wanted["blueprint_summary"] is None
    assert wanted["composition"] is None
    assert wanted["primary_label"] == "Wanted: Caracal Blueprint Copy"

    # Exact complements: every contract lands in exactly one branch, and the two
    # totals sum to the unfiltered total rather than double-counting the bundle.
    unfiltered = await client.get("/contracts/?region_ids=99999954")
    assert unfiltered.json()["total"] == 3
    assert copies.json()["total"] + non_copies.json()["total"] == 3


# --- Location system exposure over the wire ---------------------------------


async def test_the_wire_carries_the_start_location_system(
    client: AsyncClient, db_session: AsyncSession
):
    """A client that can filter by system must be able to read the system on a row.

    The API accepted region_ids and system_ids while returning neither on the
    contract, so a UI had no way to show what it had filtered on — or to mark the
    rows whose system is unknown.
    """
    now = datetime.now(timezone.utc)
    db_session.add_all([
        Contract(
            contract_id=952001, title="Resolved Location", price=1_000_000, collateral=0,
            status="outstanding", type="item_exchange", issuer_id=952,
            issuer_corporation_id=952, start_location_id=60003760,
            start_location_system_id=30000142, start_location_region_id=99999904,
            for_corporation=False, date_issued=now - timedelta(days=1),
            date_expired=now + timedelta(days=5),
        ),
        Contract(
            contract_id=952002, title="Structure Location", price=1_000_000, collateral=0,
            status="outstanding", type="item_exchange", issuer_id=952,
            issuer_corporation_id=952, start_location_id=1_035_466_617_946,
            start_location_system_id=None, start_location_region_id=99999904,
            for_corporation=False, date_issued=now - timedelta(days=2),
            date_expired=now + timedelta(days=5),
        ),
    ])
    await db_session.flush()

    listed = await client.get("/contracts/?region_ids=99999904")
    assert listed.status_code == 200
    body = listed.json()
    systems = {
        item["contract_id"]: item["start_location_system_id"] for item in body["items"]
    }
    assert systems == {952001: 30000142, 952002: None}
    # No system filter was applied, so there is no coverage figure to publish.
    assert body["unknown_system_excluded"] is None

    filtered = await client.get(
        "/contracts/?region_ids=99999904&system_ids=30000142"
    )
    assert filtered.status_code == 200
    filtered_body = filtered.json()
    assert [item["contract_id"] for item in filtered_body["items"]] == [952001]
    assert filtered_body["unknown_system_excluded"] == 1


async def test_the_detail_endpoint_carries_the_start_location_system(
    client: AsyncClient, db_session: AsyncSession
):
    """The detail page renders the same location block as the list row, so it needs
    the same field — the two views share one schema and must not drift."""
    now = datetime.now(timezone.utc)
    db_session.add(
        Contract(
            contract_id=952011, title="Detail Location", price=1_000_000, collateral=0,
            status="outstanding", type="item_exchange", issuer_id=952,
            issuer_corporation_id=952, start_location_id=60008494,
            start_location_system_id=30002187, start_location_region_id=99999905,
            for_corporation=False, date_issued=now - timedelta(days=1),
            date_expired=now + timedelta(days=5),
        )
    )
    await db_session.flush()

    detail = await client.get("/contracts/952011")
    assert detail.status_code == 200
    assert detail.json()["start_location_system_id"] == 30002187


async def test_filter_by_contract_type(client: AsyncClient, db_session: AsyncSession):
    """contract_type narrows to the named types; repeated params combine; an
    unknown value 422s instead of silently matching nothing (spec §17.8)."""
    now = datetime.now(timezone.utc)

    def _c(cid, ctype):
        return Contract(
            contract_id=cid, title=f"t{cid}", price=1_000_000, collateral=0,
            status="unknown", type=ctype, issuer_id=1, issuer_corporation_id=1,
            start_location_id=60003760, start_location_region_id=99999960,
            for_corporation=False, date_issued=now,
            date_expired=now + timedelta(days=7),
        )

    db_session.add_all([_c(960001, "item_exchange"), _c(960002, "auction"),
                        _c(960003, "courier"), _c(960004, "loan")])
    await db_session.flush()

    one = await client.get("/contracts/?region_ids=99999960&contract_type=courier")
    assert one.status_code == 200
    assert [c["contract_id"] for c in one.json()["items"]] == [960003]

    two = await client.get(
        "/contracts/?region_ids=99999960&contract_type=auction&contract_type=loan"
    )
    assert two.status_code == 200
    assert {c["contract_id"] for c in two.json()["items"]} == {960002, 960004}
    assert two.json()["total"] == 2

    bad = await client.get("/contracts/?region_ids=99999960&contract_type=barter")
    assert bad.status_code == 422


# --- List row / detail split and the server-computed derived fields ---------
#
# Region 99999961. The list row and the detail response are separate models: the
# row carries no item array at all, and everything a row used to derive from that
# array (the blueprint flag, the headline label, the composition breakdown) is
# computed on the server so every client agrees on it.


def _derived_now() -> datetime:
    return datetime.now(timezone.utc)


@pytest_asyncio.fixture(scope="function")
async def derived_field_contracts(db_session: AsyncSession):
    """One mixed contract, one single-item, one courier, one two-copy auction, and
    one contract whose categories exercise the composition ordering rules.

    The mixed contract's third item is REQUESTED (is_included=False): every
    derived figure counts offered items only (spec §3.1), so it must be absent
    from the composition and must not make the contract a blueprint contract on
    its own.
    """
    now = _derived_now()
    seen = now - timedelta(minutes=5)

    db_session.add_all([
        EsiTaxonomyCache(kind="category", esi_id=6, name="Ship", fetched_at=now),
        EsiTaxonomyCache(kind="category", esi_id=7, name="Module", fetched_at=now),
        EsiTaxonomyCache(kind="category", esi_id=9, name="Blueprint", fetched_at=now),
    ])

    def _contract(cid: int, **overrides) -> Contract:
        fields = dict(
            contract_id=cid, title=f"Derived {cid}", price=1_000_000, collateral=0,
            status="outstanding", type="item_exchange", issuer_id=961,
            issuer_corporation_id=961, start_location_id=60003760,
            start_location_region_id=99999961, for_corporation=False,
            date_issued=now, date_expired=now + timedelta(days=7), last_seen_at=seen,
        )
        fields.update(overrides)
        return Contract(**fields)

    db_session.add_all([
        # Offered ship + offered BPC + REQUESTED module.
        _contract(
            961001, volume=1500.0,
            items=[
                ContractItem(
                    record_id=9610011, type_id=24698, type_name="Rokh", quantity=1,
                    is_included=True, is_singleton=False, category="ship",
                    category_id=6, group_id=27,
                ),
                ContractItem(
                    record_id=9610012, type_id=621, type_name="Caracal Blueprint",
                    quantity=1, is_included=True, is_singleton=True,
                    is_blueprint_copy=True, runs=7, material_efficiency=8,
                    time_efficiency=14, category_id=9, group_id=105,
                ),
                ContractItem(
                    record_id=9610013, type_id=448, type_name="Warp Scrambler II",
                    quantity=1, is_included=False, is_singleton=False, category_id=7,
                    group_id=52,
                ),
            ],
        ),
        # One offered row: too few for a composition breakdown.
        _contract(
            961002,
            items=[
                ContractItem(
                    record_id=9610021, type_id=587, type_name="Tristan", quantity=1,
                    is_included=True, is_singleton=False, category="ship",
                    category_id=6, group_id=25,
                ),
            ],
        ),
        # Courier: no title, so the label chain reaches the courier rule rather
        # than stopping at the title.
        _contract(
            961003, type="courier", title=None, price=0, collateral=8_000_000_000,
            end_location_id=60003145,
            end_location_name="Amarr VIII (Oris) - Emperor Family Academy",
            reward=80_000_000, volume=1000.0, days_to_complete=3,
        ),
        # Two offered copies: the summary reports the count, not one copy's terms.
        _contract(
            961004, type="auction", buyout=9_000_000.0,
            items=[
                ContractItem(
                    record_id=9610041, type_id=621, type_name="Caracal Blueprint",
                    quantity=1, is_included=True, is_singleton=True,
                    is_blueprint_copy=True, runs=7, material_efficiency=8,
                    time_efficiency=14, category_id=9, group_id=105,
                ),
                ContractItem(
                    record_id=9610042, type_id=622, type_name="Moa Blueprint",
                    quantity=1, is_included=True, is_singleton=True,
                    is_blueprint_copy=True, runs=3, material_efficiency=2,
                    time_efficiency=4, category_id=9, group_id=105,
                ),
            ],
        ),
        # Composition ordering: two unresolved categories, one category with no
        # cached name, and two named ones that tie on count.
        _contract(
            961005,
            items=[
                ContractItem(
                    record_id=9610051, type_id=587, type_name="Tristan", quantity=1,
                    is_included=True, is_singleton=False, category="ship",
                    category_id=6,
                ),
                ContractItem(
                    record_id=9610052, type_id=448, type_name="Warp Scrambler II",
                    quantity=1, is_included=True, is_singleton=False, category_id=7,
                ),
                ContractItem(
                    record_id=9610053, type_id=34, type_name="Tritanium",
                    quantity=100, is_included=True, is_singleton=False, category_id=42,
                ),
                ContractItem(
                    record_id=9610054, type_id=35, type_name="Pyerite", quantity=100,
                    is_included=True, is_singleton=False, category_id=None,
                ),
                ContractItem(
                    record_id=9610055, type_id=36, type_name="Mexallon", quantity=100,
                    is_included=True, is_singleton=False, category_id=None,
                ),
            ],
        ),
    ])
    await db_session.flush()
    return seen


async def test_list_rows_carry_no_item_array(
    client: AsyncClient, derived_field_contracts
):
    """The row is a summary, not a container: `items` on the envelope is the page.

    A row that also carried an `items` array made the two meanings collide, and
    shipped every item of every contract on the page to render one label.
    """
    listed = await client.get("/contracts/?region_ids=99999961")

    assert listed.status_code == 200
    rows = listed.json()["items"]
    assert len(rows) == 5, "fixture must reach the endpoint for this to mean anything"
    for row in rows:
        assert "items" not in row, f"contract {row['contract_id']} still carries items"


async def test_list_row_derives_blueprint_label_and_composition_from_offered_items(
    client: AsyncClient, derived_field_contracts
):
    """The mixed contract: offered ship + offered BPC + requested module."""
    listed = await client.get("/contracts/?region_ids=99999961")

    assert listed.status_code == 200
    rows = {c["contract_id"]: c for c in listed.json()["items"]}
    mixed = rows[961001]

    assert mixed["is_blueprint_copy_contract"] is True
    # The hull is the headline, not whichever item happens to sort first.
    assert mixed["primary_label"] == "Rokh"
    # The requested module is excluded: two offered rows, not three.
    assert mixed["composition"]["total_item_rows"] == 2
    assert mixed["composition"]["total_volume"] == 1500.0
    assert mixed["composition"]["categories"] == [
        {"category_id": 9, "name": "Blueprint", "item_row_count": 1},
        {"category_id": 6, "name": "Ship", "item_row_count": 1},
    ]
    assert mixed["blueprint_summary"] == {
        "runs": 7, "material_efficiency": 8, "time_efficiency": 14, "copy_count": 1,
    }
    assert mixed["last_seen_at"] is not None
    assert datetime.fromisoformat(mixed["last_seen_at"]) == derived_field_contracts


async def test_single_item_contract_has_no_composition(
    client: AsyncClient, derived_field_contracts
):
    """One offered row is not a composition — there is nothing to break down."""
    listed = await client.get("/contracts/?region_ids=99999961")

    rows = {c["contract_id"]: c for c in listed.json()["items"]}
    single = rows[961002]

    assert single["composition"] is None
    assert single["is_blueprint_copy_contract"] is False
    assert single["blueprint_summary"] is None
    assert single["primary_label"] == "Tristan"


async def test_courier_row_labels_its_destination_and_prices_by_volume(
    client: AsyncClient, derived_field_contracts
):
    """A courier has no items, so its label and its terms come from the contract."""
    listed = await client.get("/contracts/?region_ids=99999961")

    rows = {c["contract_id"]: c for c in listed.json()["items"]}
    courier = rows[961003]

    assert courier["primary_label"] == (
        "Courier to Amarr VIII (Oris) - Emperor Family Academy"
    )
    assert courier["end_location_name"] == "Amarr VIII (Oris) - Emperor Family Academy"
    assert courier["composition"] is None
    assert courier["days_to_complete"] == 3
    assert courier["reward_per_volume"] == 80_000.0
    assert courier["buyout"] is None


async def test_auction_row_carries_its_buyout_and_counts_its_copies(
    client: AsyncClient, derived_field_contracts
):
    """Two offered copies: the terms belong to no single copy, so only the count
    is reported (spec §17.3)."""
    listed = await client.get("/contracts/?region_ids=99999961")

    rows = {c["contract_id"]: c for c in listed.json()["items"]}
    auction = rows[961004]

    assert auction["buyout"] == 9_000_000.0
    assert auction["is_blueprint_copy_contract"] is True
    assert auction["blueprint_summary"] == {
        "runs": None, "material_efficiency": None, "time_efficiency": None,
        "copy_count": 2,
    }


async def test_composition_orders_every_entry_by_share_then_name(
    client: AsyncClient, derived_field_contracts
):
    """Sort is item_row_count desc for EVERY entry — the NULL-category bucket
    included, so a dominant "other" cannot hide at the end (§17.2). At equal
    counts, named entries sort by name and unnamed ones after them; a category
    with no cached name serves a null name rather than a fabricated one."""
    listed = await client.get("/contracts/?region_ids=99999961")

    rows = {c["contract_id"]: c for c in listed.json()["items"]}
    composition = rows[961005]["composition"]

    assert composition["total_item_rows"] == 5
    assert composition["categories"] == [
        {"category_id": None, "name": None, "item_row_count": 2},
        {"category_id": 7, "name": "Module", "item_row_count": 1},
        {"category_id": 6, "name": "Ship", "item_row_count": 1},
        {"category_id": 42, "name": None, "item_row_count": 1},
    ]


async def test_detail_response_carries_every_item_and_its_blueprint_terms(
    client: AsyncClient, derived_field_contracts
):
    """The detail response is the row plus the full item array — REQUESTED items
    included, because the detail page shows both sides of the trade."""
    detail = await client.get("/contracts/961001")

    assert detail.status_code == 200
    body = detail.json()
    items = {item["record_id"]: item for item in body["items"]}
    assert set(items) == {9610011, 9610012, 9610013}

    blueprint = items[9610012]
    assert blueprint["runs"] == 7
    assert blueprint["material_efficiency"] == 8
    assert blueprint["time_efficiency"] == 14
    assert blueprint["category_id"] == 9
    assert blueprint["group_id"] == 105
    assert items[9610011]["category_id"] == 6
    # An original omits runs entirely rather than sending -1 (ESI-3).
    assert items[9610013]["runs"] is None

    # The detail response computes the same derived fields as the row, from the
    # same category-name lookup — without it every category here reads as null.
    assert body["primary_label"] == "Rokh"
    assert body["composition"]["categories"][0]["name"] == "Blueprint"
    assert body["is_blueprint_copy_contract"] is True


async def test_reward_per_volume_is_null_when_the_division_is_undefined(
    client: AsyncClient, db_session: AsyncSession
):
    """A zero or absent volume has no per-m3 price, and 0.0 would read as free
    hauling (spec §9)."""
    now = _derived_now()

    def _courier(cid: int, volume) -> Contract:
        return Contract(
            contract_id=cid, title=None, price=0, collateral=0, status="outstanding",
            type="courier", issuer_id=961, issuer_corporation_id=961,
            start_location_id=60003760, start_location_region_id=99999961,
            for_corporation=False, date_issued=now,
            date_expired=now + timedelta(days=7), reward=1_000_000.0, volume=volume,
        )

    db_session.add_all([_courier(961101, 0.0), _courier(961102, None)])
    # A reward-less contract cannot have a per-volume price either.
    db_session.add(
        Contract(
            contract_id=961103, title=None, price=5_000_000, collateral=0,
            status="outstanding", type="item_exchange", issuer_id=961,
            issuer_corporation_id=961, start_location_id=60003760,
            start_location_region_id=99999961, for_corporation=False,
            date_issued=now, date_expired=now + timedelta(days=7), reward=None,
            volume=250.0,
        )
    )
    await db_session.flush()

    listed = await client.get("/contracts/?region_ids=99999961")

    assert listed.status_code == 200
    rows = {c["contract_id"]: c for c in listed.json()["items"]}
    assert len(rows) == 3
    assert rows[961101]["reward_per_volume"] is None
    assert rows[961102]["reward_per_volume"] is None
    assert rows[961103]["reward_per_volume"] is None


# --- Segment counts on the list envelope -----------------------------------
#
# Region 99999962. The envelope carries a count per contract type, computed with
# contract_type lifted so the segment a reader is NOT on still reads its own
# total. Criterion 1.8 governs how the ships-only flag interacts with that: an
# item-less type has no ships by construction, so it reports the count the reader
# would see after switching rather than the 0 the combined filter would give.

SEGMENT_KEYS = {"item_exchange", "auction", "courier", "loan", "unknown"}


def _segment_contract(
    cid: int,
    *,
    contract_type: str,
    is_ship: bool,
    price: float,
    items: list[ContractItem] | None = None,
) -> Contract:
    now = datetime.now(timezone.utc)
    return Contract(
        contract_id=cid, title=f"Segment {cid}", price=price, collateral=0,
        status="outstanding", type=contract_type, issuer_id=962,
        issuer_corporation_id=962, start_location_id=60003760,
        start_location_region_id=99999962, for_corporation=False,
        date_issued=now, date_expired=now + timedelta(days=7),
        is_ship_contract=is_ship, items=items or [],
    )


@pytest_asyncio.fixture(scope="function")
async def segment_count_contracts(db_session: AsyncSession):
    """Two ship item exchanges, one non-ship item exchange, one courier."""
    db_session.add_all([
        _segment_contract(962101, contract_type="item_exchange", is_ship=True,
                          price=1_000_000),
        _segment_contract(962102, contract_type="item_exchange", is_ship=True,
                          price=50_000_000),
        _segment_contract(962103, contract_type="item_exchange", is_ship=False,
                          price=2_000_000),
        _segment_contract(962104, contract_type="courier", is_ship=False, price=0),
    ])
    await db_session.flush()


async def test_an_item_less_segment_reports_its_true_count_under_ships_only(
    client: AsyncClient, segment_count_contracts
):
    """Criterion 1.8. ESI returns no items for couriers and the ship flag is
    derived from items, so a courier can never be a ship contract — a `Courier (0)`
    label that turns into `Courier (1)` the instant it is clicked is the
    silent-filter-no-op defect wearing a numeral. The item-bearing segments still
    respect the flag; only the item-less ones read it lifted."""
    listed = await client.get("/contracts/?region_ids=99999962&is_ship_contract=true")

    assert listed.status_code == 200
    data = listed.json()
    assert set(data["segment_counts"]) == SEGMENT_KEYS
    assert data["segment_counts"]["item_exchange"] == 2
    assert data["segment_counts"]["courier"] == 1
    # The total answers the query that was actually made, so it is NOT lifted.
    assert data["total"] == 2
    assert {row["contract_id"] for row in data["items"]} == {962101, 962102}


async def test_an_item_bearing_segment_reports_the_complement_under_ships_excluded(
    client: AsyncClient, segment_count_contracts
):
    """The other half of Criterion 1.8. Excluding ships is not the same lift as
    selecting them: an item-bearing segment must report the non-ships it would
    actually show (all minus ships), not its full population — the number beside
    `Item Exchange` has to be the number of rows behind it. Item-less segments stay
    lifted here too, since they have no ships to subtract."""
    listed = await client.get("/contracts/?region_ids=99999962&is_ship_contract=false")

    assert listed.status_code == 200
    data = listed.json()
    assert set(data["segment_counts"]) == SEGMENT_KEYS
    # 962103 is the only non-ship item exchange; 962101/962102 are ships.
    assert data["segment_counts"]["item_exchange"] == 1
    assert data["segment_counts"]["courier"] == 1
    assert data["total"] == 2
    assert {row["contract_id"] for row in data["items"]} == {962103, 962104}


async def test_segment_counts_read_every_type_with_the_type_filter_lifted(
    client: AsyncClient, segment_count_contracts
):
    """Selecting one segment must not blank the others' labels: the counts are
    computed with contract_type lifted, so the reader can see what switching costs
    while `total` stays the count of what they asked for."""
    listed = await client.get("/contracts/?region_ids=99999962&contract_type=courier")

    assert listed.status_code == 200
    data = listed.json()
    assert data["total"] == 1
    assert data["segment_counts"]["item_exchange"] == 3
    assert data["segment_counts"]["courier"] == 1
    assert data["segment_counts"]["auction"] == 0


async def test_segment_counts_respect_the_other_filters(
    client: AsyncClient, segment_count_contracts
):
    """Only contract_type and the ships-only flag are lifted (spec §6.2). A price
    bound the reader set still narrows every segment's count, or the labels
    advertise results the list cannot show."""
    listed = await client.get(
        "/contracts/?region_ids=99999962&is_ship_contract=true&max_price=10000000"
    )

    assert listed.status_code == 200
    data = listed.json()
    assert data["segment_counts"]["item_exchange"] == 1   # 962102 costs too much
    assert data["segment_counts"]["courier"] == 1         # free, so it survives
    assert data["total"] == 1


async def test_segment_counts_count_contracts_not_joined_item_rows(
    client: AsyncClient, db_session: AsyncSession
):
    """Criterion 1.3. `search` outer-joins the items table, so a contract with two
    matching items contributes two rows to the grouped statement — counting them
    reports one contract as two."""
    def _item(record_id: int, type_id: int) -> ContractItem:
        return ContractItem(
            record_id=record_id, type_id=type_id, type_name="Rifter", quantity=1,
            is_included=True, is_singleton=False,
        )

    db_session.add_all([
        _segment_contract(
            962201, contract_type="item_exchange", is_ship=True, price=1_000_000,
            items=[_item(9622011, 587), _item(9622012, 588)],
        ),
        _segment_contract(
            962202, contract_type="auction", is_ship=True, price=1_000_000,
            items=[_item(9622021, 587)],
        ),
    ])
    await db_session.flush()

    listed = await client.get("/contracts/?region_ids=99999962&search=Rifter")

    assert listed.status_code == 200
    data = listed.json()
    assert data["segment_counts"]["item_exchange"] == 1
    assert data["segment_counts"]["auction"] == 1
    assert data["total"] == 2


async def test_the_empty_page_still_carries_the_full_segment_counts(
    client: AsyncClient, segment_count_contracts
):
    """The empty result is where the counts matter most: they are the only thing
    telling a reader who filtered themselves into an empty segment that the corpus
    is not empty. The short-circuit that skips the page query must not skip them."""
    listed = await client.get("/contracts/?region_ids=99999962&contract_type=loan")

    assert listed.status_code == 200
    data = listed.json()
    assert data["total"] == 0
    assert data["items"] == []
    assert set(data["segment_counts"]) == SEGMENT_KEYS
    assert data["segment_counts"]["loan"] == 0
    assert data["segment_counts"]["item_exchange"] == 3
    assert data["segment_counts"]["courier"] == 1


async def test_a_contract_type_outside_the_enum_stays_counted_and_reachable(
    client: AsyncClient, db_session: AsyncSession
):
    """Criterion 1.1. `contracts.type` is an unconstrained string written straight
    from ESI, so a type added after this enum was written is storable. It folds
    into the `unknown` segment instead of vanishing from the sum — a total short of
    the corpus would also fire the empty-page short-circuit while rows exist."""
    db_session.add_all([
        _segment_contract(962301, contract_type="somenewtype", is_ship=False, price=1),
        _segment_contract(962302, contract_type="unknown", is_ship=False, price=1),
        _segment_contract(962303, contract_type="item_exchange", is_ship=True, price=1),
    ])
    await db_session.flush()

    listed = await client.get("/contracts/?region_ids=99999962")

    assert listed.status_code == 200
    data = listed.json()
    assert data["segment_counts"]["unknown"] == 2
    assert data["total"] == 3
    assert 962301 in {row["contract_id"] for row in data["items"]}

    # Selecting the segment returns everything its numeral advertised: the
    # literal "unknown" row AND the folded out-of-enum row (a count of 2 that
    # yields 1 row is the silent-no-op defect wearing a numeral).
    selected = await client.get(
        "/contracts/?region_ids=99999962&contract_type=unknown"
    )
    assert selected.status_code == 200
    assert selected.json()["total"] == 2
    assert {row["contract_id"] for row in selected.json()["items"]} == {962301, 962302}


async def test_a_dominant_uncategorized_bucket_leads_the_composition(
    client: AsyncClient, db_session: AsyncSession
):
    """§17.2 orders composition entries by item_row_count descending for EVERY
    entry — the NULL-category bucket included. Three unresolved rows must not
    hide behind a one-row named category."""
    now = datetime.now(timezone.utc)
    db_session.add(Contract(
        contract_id=962401, title="Mystery Lot", price=1_000_000, collateral=0,
        status="unknown", type="item_exchange", issuer_id=1,
        issuer_corporation_id=1, start_location_id=60003760,
        start_location_region_id=99999962, for_corporation=False,
        date_issued=now, date_expired=now + timedelta(days=7), volume=900.0,
        items=[
            ContractItem(record_id=9624011, type_id=587, type_name="Tristan",
                         quantity=1, is_included=True, is_singleton=False,
                         is_blueprint_copy=None, category_id=6),
            ContractItem(record_id=9624012, type_id=701, type_name="Widget A",
                         quantity=1, is_included=True, is_singleton=False,
                         is_blueprint_copy=None),
            ContractItem(record_id=9624013, type_id=702, type_name="Widget B",
                         quantity=1, is_included=True, is_singleton=False,
                         is_blueprint_copy=None),
            ContractItem(record_id=9624014, type_id=703, type_name="Widget C",
                         quantity=1, is_included=True, is_singleton=False,
                         is_blueprint_copy=None),
        ],
    ))
    await db_session.flush()

    listed = await client.get("/contracts/?region_ids=99999962")
    row = {c["contract_id"]: c for c in listed.json()["items"]}[962401]
    counts = [
        (entry["category_id"], entry["item_row_count"])
        for entry in row["composition"]["categories"]
    ]
    assert counts == [(None, 3), (6, 1)]


# --- Item-level range families (runs / ME / TE) ------------------------------
#
# Each family is a contract-level classification over OFFERED items (§3.1), so
# each is one correlated EXISTS holding every bound of that family — bounds
# within a family must be satisfied by the SAME item (SQLA-3 / TEST-19).
#
# Ranges do not two-way partition the way the boolean is_bpc family does. is_bpc
# false is the negation of is_bpc true, so the branches are complements by
# construction; complementary range bounds are two independent existential
# questions, and a contract offering items on both sides legitimately answers
# yes to both. The identity below therefore names the overlap explicitly.


async def test_runs_filter_is_a_contract_level_predicate_with_a_three_way_identity(
    client: AsyncClient, db_session: AsyncSession
):
    """min_runs/max_runs classify contracts by their OFFERED items (§3.1).

    Complementary bounds do not two-way partition: NULL-runs items fall in
    `neither`. Expected neither count is stated here, not derived: 2 — the
    blueprint ORIGINAL (ESI omits `runs` on originals rather than sending -1, so
    absence is not zero — ESI-3) and the requested-only copy.
    """
    now = datetime.now(timezone.utc)

    def _c(cid, items):
        return Contract(
            contract_id=cid, title=f"t{cid}", price=1_000_000, collateral=0,
            status="unknown", type="item_exchange", issuer_id=1,
            issuer_corporation_id=1, start_location_id=60003760,
            start_location_region_id=99999963, for_corporation=False,
            date_issued=now, date_expired=now + timedelta(days=7), items=items,
        )

    db_session.add_all([
        # Mixed offered children: 5 runs and 15 runs. Each bound is satisfied by a
        # different item, so this contract answers yes to both single-bound
        # branches and no to the [10, 12] window.
        _c(963001, [
            ContractItem(record_id=9630011, type_id=621, type_name="BPC few",
                         quantity=1, is_included=True, is_singleton=True,
                         is_blueprint_copy=True, runs=5),
            ContractItem(record_id=9630012, type_id=622, type_name="BPC many",
                         quantity=1, is_included=True, is_singleton=True,
                         is_blueprint_copy=True, runs=15),
        ]),
        # Single offered copy at 10 runs.
        _c(963002, [ContractItem(record_id=9630021, type_id=623, type_name="BPC mid",
                                 quantity=1, is_included=True, is_singleton=True,
                                 is_blueprint_copy=True, runs=10)]),
        # A blueprint ORIGINAL: ESI sends no `runs` at all, so the column is NULL.
        # NULL satisfies no bound in either direction — it must not read as zero.
        _c(963003, [ContractItem(record_id=9630031, type_id=624, type_name="BPO",
                                 quantity=1, is_included=True, is_singleton=True,
                                 is_blueprint_copy=None, runs=None)]),
        # A copy on the REQUESTED side only → neither (offered-only, §3.1/8.1).
        _c(963004, [ContractItem(record_id=9630041, type_id=625, type_name="WTB BPC",
                                 quantity=1, is_included=False, is_singleton=True,
                                 is_blueprint_copy=True, runs=20)]),
    ])
    await db_session.flush()
    base = "/contracts/?region_ids=99999963"

    low = await client.get(f"{base}&max_runs=9")
    high = await client.get(f"{base}&min_runs=10")
    unfiltered = await client.get(base)
    assert low.status_code == 200
    assert high.status_code == 200
    low_ids = {c["contract_id"] for c in low.json()["items"]}
    high_ids = {c["contract_id"] for c in high.json()["items"]}
    assert low_ids == {963001}
    assert high_ids == {963001, 963002}
    # The original and the want-to-buy ad are in neither branch.
    assert 963003 not in low_ids | high_ids
    assert 963004 not in low_ids | high_ids

    overlap = len(low_ids & high_ids)
    assert overlap == 1
    neither = 2
    assert unfiltered.json()["total"] == 4
    assert (
        low.json()["total"] + high.json()["total"] - overlap + neither
        == unfiltered.json()["total"]
    )

    # Bounds of one family compose per ITEM: no single item sits in [10, 12].
    window = await client.get(f"{base}&min_runs=10&max_runs=12")
    assert [c["contract_id"] for c in window.json()["items"]] == [963002]

    # Criterion 2.5: the filtered count is STRICTLY LESS than unfiltered — the
    # live defect returned an empty page off a permanently-NULL column, and an
    # inert filter returns the identical count.
    assert high.json()["total"] < unfiltered.json()["total"]


async def test_me_filter_is_a_contract_level_predicate_with_a_three_way_identity(
    client: AsyncClient, db_session: AsyncSession
):
    """min_me/max_me classify contracts by their OFFERED items (§3.1). Complementary
    bounds do not two-way partition: NULL-ME items (non-blueprints, originals) fall
    in `neither`. Expected neither count is stated here, not derived: 2 — the
    no-blueprint contract and the requested-only-BPC contract."""
    now = datetime.now(timezone.utc)

    def _c(cid, items):
        return Contract(
            contract_id=cid, title=f"t{cid}", price=1_000_000, collateral=0,
            status="unknown", type="item_exchange", issuer_id=1,
            issuer_corporation_id=1, start_location_id=60003760,
            start_location_region_id=99999964, for_corporation=False,
            date_issued=now, date_expired=now + timedelta(days=7), items=items,
        )

    db_session.add_all([
        # Mixed offered children: ME 5 and ME 15 — one item satisfies each bound,
        # and no single item satisfies a min_me=10&max_me=12 range.
        _c(964001, [
            ContractItem(record_id=9640011, type_id=621, type_name="BPC lo",
                         quantity=1, is_included=True, is_singleton=True,
                         is_blueprint_copy=True, material_efficiency=5),
            ContractItem(record_id=9640012, type_id=622, type_name="BPC hi",
                         quantity=1, is_included=True, is_singleton=True,
                         is_blueprint_copy=True, material_efficiency=15),
        ]),
        # Single offered BPC at ME 10.
        _c(964002, [ContractItem(record_id=9640021, type_id=623, type_name="BPC mid",
                                 quantity=1, is_included=True, is_singleton=True,
                                 is_blueprint_copy=True, material_efficiency=10)]),
        # No blueprint at all → neither.
        _c(964003, [ContractItem(record_id=9640031, type_id=587, type_name="Tristan",
                                 quantity=1, is_included=True, is_singleton=False,
                                 is_blueprint_copy=None)]),
        # BPC on the REQUESTED side only → neither (offered-only, §3.1/8.1).
        _c(964004, [ContractItem(record_id=9640041, type_id=624, type_name="WTB BPC",
                                 quantity=1, is_included=False, is_singleton=True,
                                 is_blueprint_copy=True, material_efficiency=20)]),
    ])
    await db_session.flush()
    base = "/contracts/?region_ids=99999964"

    low = await client.get(f"{base}&max_me=9")          # branch_a: ME <= 9
    high = await client.get(f"{base}&min_me=10")        # branch_b: ME >= 10
    unfiltered = await client.get(base)
    assert low.status_code == 200
    assert high.status_code == 200
    low_ids = {c["contract_id"] for c in low.json()["items"]}
    high_ids = {c["contract_id"] for c in high.json()["items"]}
    # The straddler appears in BOTH branches — existential semantics: each bound
    # is satisfied by a different offered item.
    assert low_ids == {964001}
    assert high_ids == {964001, 964002}
    # Three-way identity with the overlap named: |A| + |B| - |A and B| + neither
    # == unfiltered. neither == 2 as stated in the docstring (964003, 964004).
    overlap = len(low_ids & high_ids)
    assert overlap == 1
    neither = 2
    assert unfiltered.json()["total"] == 4
    assert (
        low.json()["total"] + high.json()["total"] - overlap + neither
        == unfiltered.json()["total"]
    )

    # Range composes per item: no single item sits in [10, 12].
    window = await client.get(f"{base}&min_me=10&max_me=12")
    window_ids = {c["contract_id"] for c in window.json()["items"]}
    assert [c["contract_id"] for c in window.json()["items"]] == [964002]
    assert 964001 not in window_ids

    # Criterion 2.5's harsher assertion: the filtered count is STRICTLY LESS than
    # unfiltered — the live defect returned the identical count.
    assert high.json()["total"] < unfiltered.json()["total"]


async def test_te_filter_is_a_contract_level_predicate_with_a_three_way_identity(
    client: AsyncClient, db_session: AsyncSession
):
    """min_te/max_te classify contracts by their OFFERED items (§3.1). Expected
    neither count is stated here, not derived: 2 — the no-blueprint contract and
    the requested-only-BPC contract."""
    now = datetime.now(timezone.utc)

    def _c(cid, items):
        return Contract(
            contract_id=cid, title=f"t{cid}", price=1_000_000, collateral=0,
            status="unknown", type="item_exchange", issuer_id=1,
            issuer_corporation_id=1, start_location_id=60003760,
            start_location_region_id=99999964, for_corporation=False,
            date_issued=now, date_expired=now + timedelta(days=7), items=items,
        )

    db_session.add_all([
        # Mixed offered children: TE 5 and TE 15.
        _c(964101, [
            ContractItem(record_id=9641011, type_id=621, type_name="BPC lo",
                         quantity=1, is_included=True, is_singleton=True,
                         is_blueprint_copy=True, time_efficiency=5),
            ContractItem(record_id=9641012, type_id=622, type_name="BPC hi",
                         quantity=1, is_included=True, is_singleton=True,
                         is_blueprint_copy=True, time_efficiency=15),
        ]),
        # Single offered BPC at TE 10.
        _c(964102, [ContractItem(record_id=9641021, type_id=623, type_name="BPC mid",
                                 quantity=1, is_included=True, is_singleton=True,
                                 is_blueprint_copy=True, time_efficiency=10)]),
        # No blueprint at all → neither.
        _c(964103, [ContractItem(record_id=9641031, type_id=587, type_name="Tristan",
                                 quantity=1, is_included=True, is_singleton=False,
                                 is_blueprint_copy=None)]),
        # BPC on the REQUESTED side only → neither (offered-only, §3.1/8.1).
        _c(964104, [ContractItem(record_id=9641041, type_id=624, type_name="WTB BPC",
                                 quantity=1, is_included=False, is_singleton=True,
                                 is_blueprint_copy=True, time_efficiency=20)]),
    ])
    await db_session.flush()
    base = "/contracts/?region_ids=99999964"

    low = await client.get(f"{base}&max_te=9")
    high = await client.get(f"{base}&min_te=10")
    unfiltered = await client.get(base)
    assert low.status_code == 200
    assert high.status_code == 200
    low_ids = {c["contract_id"] for c in low.json()["items"]}
    high_ids = {c["contract_id"] for c in high.json()["items"]}
    assert low_ids == {964101}
    assert high_ids == {964101, 964102}

    overlap = len(low_ids & high_ids)
    assert overlap == 1
    neither = 2
    assert unfiltered.json()["total"] == 4
    assert (
        low.json()["total"] + high.json()["total"] - overlap + neither
        == unfiltered.json()["total"]
    )

    window = await client.get(f"{base}&min_te=10&max_te=12")
    assert [c["contract_id"] for c in window.json()["items"]] == [964102]

    assert high.json()["total"] < unfiltered.json()["total"]


async def test_range_families_are_independent_of_each_other(
    client: AsyncClient, db_session: AsyncSession
):
    """Separate families may be satisfied by DIFFERENT items (§3.1): one EXISTS
    per family, not one EXISTS holding every bound of every family. A contract
    whose ME comes from one copy and whose runs come from another still matches
    both — collapsing the families into a single EXISTS would drop it."""
    now = datetime.now(timezone.utc)
    db_session.add(
        Contract(
            contract_id=964201, title="t964201", price=1_000_000, collateral=0,
            status="unknown", type="item_exchange", issuer_id=1,
            issuer_corporation_id=1, start_location_id=60003760,
            start_location_region_id=99999964, for_corporation=False,
            date_issued=now, date_expired=now + timedelta(days=7),
            items=[
                # High ME, no runs recorded.
                ContractItem(record_id=9642011, type_id=621, type_name="BPC me",
                             quantity=1, is_included=True, is_singleton=True,
                             is_blueprint_copy=True, material_efficiency=10,
                             runs=None),
                # Many runs, no ME recorded.
                ContractItem(record_id=9642012, type_id=622, type_name="BPC runs",
                             quantity=1, is_included=True, is_singleton=True,
                             is_blueprint_copy=True, material_efficiency=None,
                             runs=50),
            ],
        )
    )
    await db_session.flush()

    both = await client.get(
        "/contracts/?region_ids=99999964&min_me=10&min_runs=50"
    )

    assert both.status_code == 200
    assert [c["contract_id"] for c in both.json()["items"]] == [964201]


# --- Taxonomy filters: category_id and group_id (region 99999965) ---
#
# One EXISTS holding BOTH predicates, not two: a group belongs to a category, so
# "category 6 and group 60" asks for a single offered item that is both, which is
# also the only pair a cascading category -> group UI can produce. Two separate
# EXISTS would answer yes to a contract offering a frigate and an unrelated
# propulsion module, which holds nothing the buyer asked for.
#
# Real ids throughout so the fixture reads the way production data does:
# category 6 Ship / 7 Module, group 25 Frigate / 26 Cruiser / 60 Propulsion Module.

SHIP_CATEGORY = 6
MODULE_CATEGORY = 7
FRIGATE_GROUP = 25
CRUISER_GROUP = 26
PROPULSION_GROUP = 60


@pytest_asyncio.fixture
async def taxonomy_corpus(db_session: AsyncSession):
    """Four contracts in region 99999965, spanning every taxonomy reading.

    965001 is the mixed-child parent TEST-19 requires: one offered frigate
    (Ship/Frigate) and one offered afterburner (Module/Propulsion). It is also the
    fixture that separates same-item composition from two independent EXISTS —
    it holds a category-6 item and a group-60 item, but no item that is both.
    """
    now = datetime.now(timezone.utc)

    def _c(cid, items):
        return Contract(
            contract_id=cid, title=f"t{cid}", price=1_000_000, collateral=0,
            status="unknown", type="item_exchange", issuer_id=1,
            issuer_corporation_id=1, start_location_id=60003760,
            start_location_region_id=99999965, for_corporation=False,
            date_issued=now, date_expired=now + timedelta(days=7), items=items,
        )

    db_session.add_all([
        _c(965001, [
            ContractItem(record_id=9650011, type_id=587, type_name="Rifter",
                         quantity=1, is_included=True, is_singleton=False,
                         category_id=SHIP_CATEGORY, group_id=FRIGATE_GROUP),
            ContractItem(record_id=9650012, type_id=12056, type_name="Afterburner II",
                         quantity=1, is_included=True, is_singleton=False,
                         category_id=MODULE_CATEGORY, group_id=PROPULSION_GROUP),
        ]),
        # Module only — must never answer a Ship-category query.
        _c(965002, [ContractItem(record_id=9650021, type_id=12058, type_name="1MN Afterburner I",
                                 quantity=1, is_included=True, is_singleton=False,
                                 category_id=MODULE_CATEGORY, group_id=PROPULSION_GROUP)]),
        # Frigate on the REQUESTED side only → never matches (offered-only, §3.1/8.1).
        _c(965003, [ContractItem(record_id=9650031, type_id=588, type_name="WTB Rifter",
                                 quantity=1, is_included=False, is_singleton=False,
                                 category_id=SHIP_CATEGORY, group_id=FRIGATE_GROUP)]),
        # A second ship, one group over, so repeated group_id params have something
        # to combine that a single-group query does not already return.
        _c(965004, [ContractItem(record_id=9650041, type_id=622, type_name="Stabber",
                                 quantity=1, is_included=True, is_singleton=False,
                                 category_id=SHIP_CATEGORY, group_id=CRUISER_GROUP)]),
    ])
    await db_session.flush()


TAXONOMY_BASE = "/contracts/?region_ids=99999965"


async def _ids(client: AsyncClient, query: str) -> set[int]:
    response = await client.get(f"{TAXONOMY_BASE}{query}")
    assert response.status_code == 200
    return {c["contract_id"] for c in response.json()["items"]}


async def test_category_filter_is_a_contract_level_predicate_on_a_mixed_bundle(
    client: AsyncClient, taxonomy_corpus
):
    """category_id classifies contracts by their OFFERED items (§3.1, SQLA-3).

    The mixed bundle answers yes to BOTH category queries — there is no negation
    branch for taxonomy, so a contract offering a ship and a module genuinely is
    both a ship contract and a module contract. What it must not do is drag the
    module-only contract into the ship answer.
    """
    unfiltered = await client.get(TAXONOMY_BASE)
    assert unfiltered.json()["total"] == 4

    ships = await _ids(client, f"&category_id={SHIP_CATEGORY}")
    modules = await _ids(client, f"&category_id={MODULE_CATEGORY}")

    assert ships == {965001, 965004}
    assert modules == {965001, 965002}
    # The requested-only frigate never makes its contract a ship contract.
    assert 965003 not in ships
    assert 965003 not in modules


async def test_category_and_group_must_be_satisfied_by_the_same_offered_item(
    client: AsyncClient, taxonomy_corpus
):
    """A group belongs to a category, so both predicates land on ONE item.

    965001 offers a category-6 item and a group-60 item and would match under two
    independent EXISTS. It holds no propulsion module that is a ship, so it must
    not come back — that pairing describes nothing in the contract.
    """
    scoped = await client.get(
        f"{TAXONOMY_BASE}&category_id={SHIP_CATEGORY}&group_id={PROPULSION_GROUP}"
    )

    assert scoped.status_code == 200
    assert scoped.json()["total"] == 0
    assert scoped.json()["items"] == []

    # The pairing that DOES describe one of its items still matches.
    assert await _ids(
        client, f"&category_id={SHIP_CATEGORY}&group_id={FRIGATE_GROUP}"
    ) == {965001}


async def test_group_filter_stands_alone_and_repeats(
    client: AsyncClient, taxonomy_corpus
):
    """group_id filters without a category, and repeated params union (FASTAPI-1)."""
    assert await _ids(client, f"&group_id={PROPULSION_GROUP}") == {965001, 965002}
    assert await _ids(client, f"&group_id={FRIGATE_GROUP}") == {965001}
    assert await _ids(
        client, f"&group_id={FRIGATE_GROUP}&group_id={CRUISER_GROUP}"
    ) == {965001, 965004}
    # Repeated categories union the same way.
    assert await _ids(
        client, f"&category_id={SHIP_CATEGORY}&category_id={MODULE_CATEGORY}"
    ) == {965001, 965002, 965004}


async def test_a_category_absent_from_the_corpus_returns_an_empty_page(
    client: AsyncClient, taxonomy_corpus
):
    """An unrepresented category is an empty answer, not an error — the cascading
    UI can send any id the taxonomy endpoint serves, including one whose contracts
    have all expired since."""
    empty = await client.get(f"{TAXONOMY_BASE}&category_id=87")

    assert empty.status_code == 200
    assert empty.json()["total"] == 0
    assert empty.json()["items"] == []


# --- Taxonomy options endpoint: GET /contracts/taxonomy (region 99999971) ---
#
# The endpoint takes no filters, so unlike every other block in this file its
# population is the whole table. These tests therefore seed their own corpus and
# deliberately do NOT use setup_contracts; db_session drops and recreates every
# table per test function, so the corpus is exactly what each test writes. The
# private region is claimed anyway, under the plan's 99999960-99999979
# allocation, so the per-region delisting watermark has somewhere to work.
#
# `coverage` is the readiness signal the item-level UI gates on, and it asks two
# questions at once. Is the live corpus enriched at the CURRENT enrichment
# version — which is what makes the taxonomy columns on the items trustworthy —
# and does the name cache actually name every category that corpus holds? Either
# one failing leaves the filter rail unable to do its job, so either one failing
# reports "partial".

TAXONOMY_OPTIONS_REGION = 99999971


def _cached_taxonomy(
    kind: str, esi_id: int, name: str, parent_category_id: int | None = None
) -> EsiTaxonomyCache:
    """One name-cache row, shaped the way enrichment writes it: categories carry no
    parent, groups carry the category they belong to."""
    return EsiTaxonomyCache(
        kind=kind,
        esi_id=esi_id,
        name=name,
        parent_category_id=parent_category_id,
        fetched_at=datetime.now(timezone.utc),
    )


def _taxonomy_item(record_id: int, *, category_id: int, group_id: int) -> ContractItem:
    """An offered item carrying the dogma ids enrichment resolves for it."""
    return ContractItem(
        record_id=record_id,
        type_id=587,
        type_name="Rifter",
        quantity=1,
        is_included=True,
        is_singleton=False,
        category_id=category_id,
        group_id=group_id,
    )


def _enriched_contract(
    contract_id: int,
    *,
    version: int = ENRICHMENT_VERSION,
    processing_status: str = "COMPLETED",
    contract_type: str = "item_exchange",
    seen: datetime | None = None,
    items: list[ContractItem] | None = None,
) -> Contract:
    """A live contract carrying the enrichment bookkeeping the readiness ratio reads.

    Every column set here is one ingestion writes (TEST-18): item_processing_status
    and enrichment_version are stamped by the enrichment pass, last_seen_at by every
    sighting, and the items' category_id/group_id by type resolution.
    """
    now = datetime.now(timezone.utc)
    return Contract(
        contract_id=contract_id,
        title=f"Taxonomy Case {contract_id}",
        price=1_000_000,
        collateral=0,
        status="unknown",
        type=contract_type,
        issuer_id=1,
        issuer_corporation_id=1,
        start_location_id=60003760,
        start_location_region_id=TAXONOMY_OPTIONS_REGION,
        for_corporation=False,
        date_issued=now - timedelta(days=1),
        date_expired=now + timedelta(days=7),
        item_processing_status=processing_status,
        enrichment_version=version,
        last_seen_at=seen,
        items=items or [],
    )


async def _taxonomy(client: AsyncClient) -> dict:
    response = await client.get("/contracts/taxonomy")
    assert response.status_code == 200
    return response.json()


async def test_taxonomy_on_a_cold_cache_is_empty_and_partial_rather_than_an_error(
    client: AsyncClient,
):
    """Before the first enrichment run there are no names to serve. Two empty lists
    and an honest "partial" is a state the client can render; a 500 is not.

    This is also what proves the route is matched ahead of /{contract_id} — parsing
    "taxonomy" as a contract id would 422 instead.
    """
    assert await _taxonomy(client) == {
        "categories": [],
        "groups": [],
        "coverage": "partial",
    }


async def test_taxonomy_serves_name_sorted_flat_lists_with_each_group_naming_its_category(
    client: AsyncClient, db_session: AsyncSession
):
    """Flat rather than nested (§17.6): the client scopes groups to the selected
    categories locally, which needs every group to carry its category id.

    Both lists are seeded in exactly REVERSE name order, so an endpoint that served
    them in the order it read them would fail this assertion rather than pass it by
    coincidence — seeding them already sorted makes the assertion agree with the sort
    without constraining it (TEST-12).
    """
    db_session.add_all([
        _cached_taxonomy("category", 6, "Ship"),
        _cached_taxonomy("category", 7, "Module"),
        _cached_taxonomy("group", 60, "Propulsion Module", 7),
        _cached_taxonomy("group", 25, "Frigate", 6),
        _cached_taxonomy("group", 26, "Cruiser", 6),
        _enriched_contract(
            971001, items=[_taxonomy_item(9710011, category_id=6, group_id=25)]
        ),
    ])
    await db_session.flush()

    body = await _taxonomy(client)

    assert body["categories"] == [
        {"category_id": 7, "name": "Module"},
        {"category_id": 6, "name": "Ship"},
    ]
    assert body["groups"] == [
        {"group_id": 26, "category_id": 6, "name": "Cruiser"},
        {"group_id": 25, "category_id": 6, "name": "Frigate"},
        {"group_id": 60, "category_id": 7, "name": "Propulsion Module"},
    ]
    assert body["coverage"] == "complete"


@pytest.mark.parametrize(
    "population, unstamped, expected",
    [(200, 1, "complete"), (100, 5, "partial")],
    ids=["0.995-clears", "0.95-does-not"],
)
async def test_the_readiness_ratio_gates_the_signal_at_ninety_nine_percent(
    client: AsyncClient, db_session: AsyncSession, population, unstamped, expected
):
    """The corpus is resweept contract by contract after a version bump, so the
    signal has to tolerate a tail without opening on a mostly-stale corpus. These
    two populations sit either side of the 0.99 threshold.
    """
    seen = datetime.now(timezone.utc)
    db_session.add_all([
        _enriched_contract(
            971100 + index,
            version=ENRICHMENT_VERSION - 1 if index < unstamped else ENRICHMENT_VERSION,
            seen=seen,
        )
        for index in range(population)
    ])
    await db_session.flush()

    assert (await _taxonomy(client))["coverage"] == expected


async def test_contracts_still_awaiting_or_failing_enrichment_stay_in_the_denominator(
    client: AsyncClient, db_session: AsyncSession
):
    """The denominator is every live item-bearing contract, not just the COMPLETED
    ones. Measured over COMPLETED rows alone, one enriched contract beside
    ninety-nine broken ones reads as 1/1 — a fully enriched corpus — which is the
    opposite of what the signal exists to say.

    The failed rows keep the current version deliberately: an ENRICHMENT_INCOMPLETE
    row holds whatever version it last stamped, so the numerator's status condition
    is the only thing keeping them out of it.
    """
    db_session.add_all(
        [_enriched_contract(971300 + index) for index in range(50)]
        + [
            _enriched_contract(971400 + index, processing_status="ENRICHMENT_INCOMPLETE")
            for index in range(25)
        ]
        + [
            _enriched_contract(971450 + index, processing_status="PENDING_ITEMS")
            for index in range(25)
        ]
    )
    await db_session.flush()

    assert (await _taxonomy(client))["coverage"] == "partial"


async def test_a_delisted_contract_does_not_drag_the_readiness_ratio(
    client: AsyncClient, db_session: AsyncSession
):
    """A contract that has left ESI's public list is never re-enriched, so counting
    it would leave the ratio permanently short of the threshold — the signal would
    read "partial" forever on a corpus that is entirely up to date."""
    latest = datetime.now(timezone.utc)
    db_session.add_all([
        _enriched_contract(971501, seen=latest),
        _enriched_contract(
            971502,
            version=ENRICHMENT_VERSION - 1,
            processing_status="PENDING_ITEMS",
            seen=latest - timedelta(hours=2),
        ),
    ])
    await db_session.flush()

    assert (await _taxonomy(client))["coverage"] == "complete"


async def test_only_item_bearing_contract_types_count_in_the_denominator(
    client: AsyncClient, db_session: AsyncSession
):
    """Couriers and loans carry no items by construction, so enrichment never
    completes for them and including them would peg the ratio below the threshold
    forever. Auctions DO carry items, so they belong — asserted by making one stale
    and watching the signal degrade.
    """
    db_session.add_all([
        _enriched_contract(971601),
        _enriched_contract(971602, contract_type="auction"),
        _enriched_contract(
            971603, contract_type="courier", processing_status="PENDING_ITEMS", version=0
        ),
        _enriched_contract(
            971604, contract_type="loan", processing_status="PENDING_ITEMS", version=0
        ),
    ])
    await db_session.flush()

    assert (await _taxonomy(client))["coverage"] == "complete"

    auction = await db_session.get(Contract, 971602)
    auction.enrichment_version = ENRICHMENT_VERSION - 1
    await db_session.flush()

    assert (await _taxonomy(client))["coverage"] == "partial"


async def test_a_category_the_name_cache_is_missing_holds_the_signal_at_partial(
    client: AsyncClient, db_session: AsyncSession
):
    """A category-name fetch failure does not block COMPLETED stamping, so the ratio
    can read 1.0 while the option list is missing names the filter rail renders.
    Gating on the ratio alone would open the item-level surface on a list that
    cannot describe the corpus behind it.
    """
    db_session.add_all([
        _cached_taxonomy("category", 6, "Ship"),
        _enriched_contract(
            971701, items=[_taxonomy_item(9717011, category_id=6, group_id=25)]
        ),
        _enriched_contract(
            971702, items=[_taxonomy_item(9717021, category_id=7, group_id=60)]
        ),
    ])
    await db_session.flush()

    body = await _taxonomy(client)
    assert body["coverage"] == "partial"
    assert [entry["category_id"] for entry in body["categories"]] == [6]

    db_session.add(_cached_taxonomy("category", 7, "Module"))
    await db_session.flush()

    assert (await _taxonomy(client))["coverage"] == "complete"


async def test_a_category_seen_only_on_delisted_rows_does_not_hold_the_signal(
    client: AsyncClient, db_session: AsyncSession
):
    """The name-cache condition scopes to LIVE contracts, deliberately unlike
    ingestion's unscoped sweep of observed categories. A category that appeared only
    on rows since bought or withdrawn is not one the filter rail can return results
    for, so waiting for its name would shut the surface over data nobody can reach.
    """
    latest = datetime.now(timezone.utc)
    db_session.add_all([
        _cached_taxonomy("category", 6, "Ship"),
        _enriched_contract(
            971801,
            seen=latest,
            items=[_taxonomy_item(9718011, category_id=6, group_id=25)],
        ),
        _enriched_contract(
            971802,
            seen=latest - timedelta(hours=2),
            items=[_taxonomy_item(9718021, category_id=7, group_id=60)],
        ),
    ])
    await db_session.flush()

    assert (await _taxonomy(client))["coverage"] == "complete"


# --- New sortable fields: buyout, days_to_complete, reward_per_volume (region 99999966) ---
#
# Each of the three gets its own acceptance evidence (spec §6.2): a sort that
# silently no-ops is the same defect class as a filter that silently no-ops, and
# Criterion 5.4 only covers the ratio. Every test asserts the exact order in BOTH
# directions, because a sort that ignores its column still produces two orders that
# look plausible when only the first row is checked.
#
# All three columns are NULL on most of the corpus, so where NULL lands is part of
# the contract: a row with no reward per m3 is not the best deal on offer, and a
# contract with no buyout is not the cheapest way to end an auction (§15.2).

SORTABLE_REGION = 99999966


@pytest_asyncio.fixture
async def sortable_field_contracts(db_session: AsyncSession):
    """Nine contracts in region 99999966, spanning the three new sorts.

    Each sort gets at least three distinct non-NULL values, and every value sits on
    a row whose ingestion writer would actually produce it (TEST-18): ESI sends
    `buyout` only for auctions and `days_to_complete` only for couriers, so no row
    here carries a field its type cannot have.

    The couriers' reward-per-m3 ratios are deliberately ordered differently from
    both their rewards (1M, 6M, 4M) and their volumes (100, 100, 20), so an
    implementation that sorts by either column instead of the ratio cannot agree
    with the expected order by accident.

    Every title shares the token the joined-path test searches on, and 966021 is the
    only contract with items — two of them, so its joined rows duplicate and the
    grouped-id pagination has something to collapse (SQLA-1).
    """
    now = datetime.now(timezone.utc)

    def _contract(cid: int, **overrides) -> Contract:
        fields = dict(
            contract_id=cid, title=f"Freightpost {cid}", price=1_000_000,
            collateral=0, status="outstanding", type="item_exchange", issuer_id=966,
            issuer_corporation_id=966, start_location_id=60003760,
            start_location_region_id=SORTABLE_REGION, for_corporation=False,
            date_issued=now, date_expired=now + timedelta(days=7), last_seen_at=now,
        )
        fields.update(overrides)
        return Contract(**fields)

    db_session.add_all([
        _contract(966001, type="auction", buyout=1_000_000.0),
        _contract(966002, type="auction", buyout=5_000_000.0),
        _contract(966003, type="auction", buyout=9_000_000.0),
        # An auction can run with no buy-it-now price at all; ESI omits the field.
        _contract(966004, type="auction"),
        # Ratios: 10k, 60k, 200k ISK per m3.
        _contract(966011, type="courier", reward=1_000_000.0, volume=100.0,
                  days_to_complete=1),
        _contract(966012, type="courier", reward=6_000_000.0, volume=100.0,
                  days_to_complete=3),
        _contract(966013, type="courier", reward=4_000_000.0, volume=20.0,
                  days_to_complete=7),
        # Nothing to divide by, so no per-m3 price (§9) — but a real delivery window.
        _contract(966014, type="courier", reward=2_000_000.0, volume=0.0,
                  days_to_complete=10),
        # No reward, no buyout, no delivery window: NULL under all three sorts.
        _contract(966021, volume=250.0, items=[
            ContractItem(record_id=9660211, type_id=587, type_name="Rifter",
                         quantity=1, is_included=True, is_singleton=False),
            ContractItem(record_id=9660212, type_id=12058,
                         type_name="1MN Afterburner I", quantity=1,
                         is_included=True, is_singleton=False),
        ]),
    ])
    await db_session.flush()


async def _sorted_ids(
    client: AsyncClient, field: str, direction: str, region: int = SORTABLE_REGION
) -> list[int]:
    response = await client.get(
        f"/contracts/?region_ids={region}"
        f"&sort_by={field}&sort_direction={direction}"
    )
    assert response.status_code == 200, response.text
    return [row["contract_id"] for row in response.json()["items"]]


async def test_buyout_sorts_both_ways_and_leaves_auctions_without_one_last(
    client: AsyncClient, sortable_field_contracts
):
    """A contract with no buy-it-now price is not the cheapest way to end an
    auction, so it belongs at the end of the sort in both directions."""
    without_a_buyout = [966004, 966011, 966012, 966013, 966014, 966021]

    ascending = await _sorted_ids(client, "buyout", "asc")
    descending = await _sorted_ids(client, "buyout", "desc")

    assert ascending == [966001, 966002, 966003] + without_a_buyout
    assert descending == [966003, 966002, 966001] + without_a_buyout
    assert ascending[0] != descending[0]


async def test_days_to_complete_sorts_both_ways_and_leaves_non_couriers_last(
    client: AsyncClient, sortable_field_contracts
):
    """Only a courier has a delivery window; the rest have no deadline rather than
    an instant one, so they must not lead the shortest-first sort."""
    without_a_window = [966001, 966002, 966003, 966004, 966021]

    ascending = await _sorted_ids(client, "days_to_complete", "asc")
    descending = await _sorted_ids(client, "days_to_complete", "desc")

    assert ascending == [966011, 966012, 966013, 966014] + without_a_window
    assert descending == [966014, 966013, 966012, 966011] + without_a_window
    assert ascending[0] != descending[0]


async def test_reward_per_volume_sorts_both_ways_and_leaves_unpriced_rows_last(
    client: AsyncClient, sortable_field_contracts
):
    """The ratio haulers compare offers on (Criterion 5.4). A row without one is not
    the best value on the board — it has no value to compare."""
    without_a_ratio = [966001, 966002, 966003, 966004, 966014, 966021]

    ascending = await _sorted_ids(client, "reward_per_volume", "asc")
    descending = await _sorted_ids(client, "reward_per_volume", "desc")

    assert ascending == [966011, 966012, 966013] + without_a_ratio
    assert descending == [966013, 966012, 966011] + without_a_ratio
    assert ascending[0] != descending[0]


async def test_a_zero_volume_courier_sorts_as_unpriced_not_as_the_best_deal(
    client: AsyncClient, sortable_field_contracts
):
    """A reward divided by a zero volume has no answer. Serving 0 or infinity would
    park the row at one end of the value sort and call it the best or worst offer on
    the board; the wire carries null and the row sorts with the other unpriced ones
    (§9)."""
    response = await client.get(
        f"/contracts/?region_ids={SORTABLE_REGION}"
        "&sort_by=reward_per_volume&sort_direction=desc"
    )

    assert response.status_code == 200
    rows = response.json()["items"]
    assert {row["contract_id"] for row in rows} == {
        966001, 966002, 966003, 966004, 966011, 966012, 966013, 966014, 966021,
    }
    by_id = {row["contract_id"]: row for row in rows}
    assert by_id[966014]["reward_per_volume"] is None
    assert by_id[966013]["reward_per_volume"] == 200_000.0

    ids = [row["contract_id"] for row in rows]
    assert ids[:3] == [966013, 966012, 966011]
    assert 966014 in ids[3:]


async def test_a_new_sort_survives_the_grouped_joined_pagination_path(
    client: AsyncClient, sortable_field_contracts
):
    """A search joins the item table, so the page is paginated over grouped contract
    ids ordered by an AGGREGATE of the sort expression rather than the expression
    itself (SQLA-1). 966021 has two items, so its joined rows duplicate and the
    grouping has something to collapse."""
    response = await client.get(
        f"/contracts/?region_ids={SORTABLE_REGION}&search=Freightpost"
        "&sort_by=reward_per_volume&sort_direction=desc"
    )

    assert response.status_code == 200
    ids = [row["contract_id"] for row in response.json()["items"]]

    assert len(ids) == len(set(ids)) == 9, "the joined rows must collapse per contract"
    assert ids == [
        966013, 966012, 966011,
        966001, 966002, 966003, 966004, 966014, 966021,
    ]


# --- NULL placement for the pre-F008 nullable sorts: volume, ship_name (region 99999972) ---
#
# volume is a nullable column and ship_name resolves to ContractItem.type_name
# across an outer join, so before these tests both sorts led with their
# no-value rows under a descending sort while buyout, days_to_complete and
# reward_per_volume put theirs last. A missing volume is not a small cargo and
# a contract with no items has no ship to alphabetize, so NULL goes to the end
# in both directions — the same contract the three newer sorts already pin.

NULLSORT_REGION = 99999972


@pytest_asyncio.fixture
async def volume_and_ship_name_sort_contracts(db_session: AsyncSession):
    """Seven contracts in region 99999972, spanning the two pre-F008 nullable sorts.

    Volume gets four distinct non-NULL values on rows whose ingestion writer would
    produce them (TEST-18): couriers always carry a volume, and 972014 follows the
    item-exchange-with-volume shape 966021 established. The NULL-volume rows are
    auctions, which ship without one in the 99999966 fixture too. Ship names get
    three distinct values on auctioned items; 972013 carries two items so the
    grouped-id pagination has joined rows to collapse (SQLA-1), and its
    sort-direction-appropriate representative is "Sabre" ascending, "Zealot"
    descending — inside the alphabet range of the other two either way.
    """
    now = datetime.now(timezone.utc)

    def _contract(cid: int, **overrides) -> Contract:
        fields = dict(
            contract_id=cid, title=f"Nullsort {cid}", price=1_000_000,
            collateral=0, status="outstanding", type="item_exchange", issuer_id=972,
            issuer_corporation_id=972, start_location_id=60003760,
            start_location_region_id=NULLSORT_REGION, for_corporation=False,
            date_issued=now, date_expired=now + timedelta(days=7), last_seen_at=now,
        )
        fields.update(overrides)
        return Contract(**fields)

    db_session.add_all([
        _contract(972001, type="courier", reward=1_000_000.0, volume=50.0),
        _contract(972002, type="courier", reward=2_000_000.0, volume=300.0),
        _contract(972003, type="courier", reward=3_000_000.0, volume=120.0),
        _contract(972011, type="auction", items=[
            ContractItem(record_id=9720111, type_id=608, type_name="Atron",
                         quantity=1, is_included=True, is_singleton=False),
        ]),
        _contract(972012, type="auction", items=[
            ContractItem(record_id=9720121, type_id=603, type_name="Merlin",
                         quantity=1, is_included=True, is_singleton=False),
        ]),
        _contract(972013, type="auction", items=[
            ContractItem(record_id=9720131, type_id=22456, type_name="Sabre",
                         quantity=1, is_included=True, is_singleton=False),
            ContractItem(record_id=9720132, type_id=12003, type_name="Zealot",
                         quantity=1, is_included=True, is_singleton=False),
        ]),
        _contract(972014, volume=250.0),
    ])
    await db_session.flush()


async def test_volume_sorts_both_ways_and_leaves_contracts_without_one_last(
    client: AsyncClient, volume_and_ship_name_sort_contracts
):
    """A contract with no recorded volume is not a small cargo — it has no cargo
    to compare, so it belongs at the end of the sort in both directions."""
    without_a_volume = [972011, 972012, 972013]

    ascending = await _sorted_ids(client, "volume", "asc", region=NULLSORT_REGION)
    descending = await _sorted_ids(client, "volume", "desc", region=NULLSORT_REGION)

    assert ascending == [972001, 972003, 972014, 972002] + without_a_volume
    assert descending == [972002, 972014, 972003, 972001] + without_a_volume
    assert ascending[0] != descending[0]


async def test_ship_name_sorts_both_ways_and_leaves_item_less_contracts_last(
    client: AsyncClient, volume_and_ship_name_sort_contracts
):
    """An item-less contract has no ship to alphabetize, so it must not lead the
    Z-first sort. The sort joins the items table, so the page paginates over
    grouped contract ids (SQLA-1) — 972013's two rows must collapse to one."""
    without_an_item = [972001, 972002, 972003, 972014]

    ascending = await _sorted_ids(client, "ship_name", "asc", region=NULLSORT_REGION)
    descending = await _sorted_ids(client, "ship_name", "desc", region=NULLSORT_REGION)

    assert len(descending) == len(set(descending)) == 7
    assert ascending == [972011, 972012, 972013] + without_an_item
    assert descending == [972013, 972012, 972011] + without_an_item
    assert ascending[0] != descending[0]
