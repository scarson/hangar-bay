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
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from fastapi_app.models import Contract, ContractItem

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
    # Check that all returned contracts are BPCs
    for item in data["items"]:
        # A contract is a BPC contract if it has at least one item that is a BPC
        assert any(i.get("is_blueprint_copy") for i in item["items"])


async def test_filter_by_bpc_runs(client: AsyncClient, setup_contracts):
    """Test filtering BPCs by the number of runs."""
    # There is a BPC with 10 runs in the test data.
    response = await client.get("/contracts/?is_bpc=true&min_runs=10&max_runs=10")

    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 1
    bpc_item = data["items"][0]["items"][0]
    assert bpc_item["raw_quantity"] == 10


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
    assert data["items"][0]["items"][0]["type_name"] == "Tristan"
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
    assert {"region_ids", "system_ids", "station_ids", "type_ids"} <= param_names


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

    Deliberately NOT in test_contracts.py: that module carries a file-level
    pytest.mark.vcr, and vcrpy intercepts ahead of ASGITransport — so this test
    replayed a cassette and passed even with the expiry predicate deleted. It has to
    live somewhere that actually reaches the app.

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
