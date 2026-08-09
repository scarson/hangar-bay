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

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from datetime import datetime, timedelta, timezone

from fastapi_app.models import Contract, ContractItem

# Fixture contracts must stay LIVE. The contracts list endpoint excludes anything past
# date_expired, so a hardcoded past expiry makes a fixture invisible to the very endpoint
# these tests exercise, and the failure reads as a baffling total==0 (TEST-17).
# Keep date_issued fixed where ordering is asserted; only the expiry tracks the clock.
LIVE_EXPIRY = datetime.now(timezone.utc) + timedelta(days=7)

# Asyncio only. These tests drive our OWN endpoints and database through ASGITransport, so
# `pytest.mark.vcr` must never be applied here: vcrpy intercepts below httpx and ahead of
# ASGITransport, which turns every request into a cassette replay that asserts nothing about
# the application (TEST-14). Per `design/fastapi/guides/09-testing-strategies.md` §5, the
# vcr/esi_live pair belongs only on tests of the client-to-ESI interaction — never on tests
# of our own database or internal endpoints. `tests/api/conftest.py` enforces this at
# collection time.
pytestmark = [pytest.mark.asyncio]


async def test_list_contracts_returns_paginated_envelope(
    client: AsyncClient, db_session: AsyncSession
):
    """The list endpoint wraps results in a page envelope carrying the core contract fields."""
    # Arrange
    db_session.add_all([
        Contract(contract_id=1, title="Envelope Probe", price=100, collateral=0.0, is_ship_contract=True, type="item_exchange", status="outstanding", issuer_id=7, issuer_corporation_id=9, for_corporation=False, date_issued=datetime.fromisoformat("2025-01-01T00:00:00Z"), date_expired=LIVE_EXPIRY, start_location_id=60003760),
        ContractItem(contract_id=1, type_id=101, type_name="Test Ship Alpha", quantity=1, is_included=True, is_singleton=True),
    ])
    await db_session.flush()

    # Act
    response = await client.get("/contracts/")

    # Assert
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, dict)
    assert data["total"] == 1
    assert data["page"] == 1
    assert data["size"] == 50
    assert isinstance(data["items"], list)

    # Unconditional on purpose: an `if data["items"]:` guard skips the entire point of the
    # test the moment the fixture stops reaching the endpoint, and reports that as a pass.
    first_contract = data["items"][0]
    assert first_contract["contract_id"] == 1
    assert first_contract["issuer_id"] == 7
    assert first_contract["title"] == "Envelope Probe"
    assert first_contract["type"] == "item_exchange"


@pytest.mark.asyncio
async def test_filter_contracts_by_search(client: AsyncClient, db_session: AsyncSession):
    """Tests text search against contract title and item name."""
    # Arrange
    contract1 = Contract(contract_id=1, title="My Special Contract", price=100, collateral=0.0, is_ship_contract=True, type="item_exchange", status="outstanding", issuer_id=1, issuer_corporation_id=1, for_corporation=False, date_issued=datetime.fromisoformat("2025-01-01T00:00:00Z"), date_expired=LIVE_EXPIRY, start_location_id=60003760)
    item1 = ContractItem(contract_id=1, type_id=101, type_name="Test Ship Alpha", quantity=1, is_included=True, is_singleton=True)
    
    contract2 = Contract(contract_id=2, title="Another Deal", price=200, collateral=0.0, is_ship_contract=True, type="item_exchange", status="outstanding", issuer_id=1, issuer_corporation_id=1, for_corporation=False, date_issued=datetime.fromisoformat("2025-01-01T00:00:00Z"), date_expired=LIVE_EXPIRY, start_location_id=60003760)
    item2 = ContractItem(contract_id=2, type_id=102, type_name="Test Ship Beta", quantity=1, is_included=True, is_singleton=True)
    
    db_session.add_all([contract1, item1, contract2, item2])
    await db_session.flush()  # Use flush to persist data within the ongoing transaction

    # Act: Search by contract title
    response = await client.get("/contracts/", params={"search": "Special"})
    data = response.json()
    assert response.status_code == 200
    assert data["total"] == 1
    assert data["items"][0]["contract_id"] == 1

    # Act: Search by item name
    response = await client.get("/contracts/", params={"search": "Beta"})
    data = response.json()
    assert response.status_code == 200
    assert data["total"] == 1
    assert data["items"][0]["contract_id"] == 2


@pytest.mark.asyncio
async def test_filter_contracts_by_price(client: AsyncClient, db_session: AsyncSession):
    """Tests filtering by min_price and max_price."""
    # Arrange
    contracts = [
        Contract(contract_id=1, title="C1", price=50.0, collateral=0.0, is_ship_contract=True, type="item_exchange", status="outstanding", issuer_id=1, issuer_corporation_id=1, for_corporation=False, date_issued=datetime.fromisoformat("2025-01-01T00:00:00Z"), date_expired=LIVE_EXPIRY, start_location_id=60003760),
        Contract(contract_id=2, title="C2", price=100.0, collateral=0.0, is_ship_contract=True, type="item_exchange", status="outstanding", issuer_id=1, issuer_corporation_id=1, for_corporation=False, date_issued=datetime.fromisoformat("2025-01-01T00:00:00Z"), date_expired=LIVE_EXPIRY, start_location_id=60003760),
        Contract(contract_id=3, title="C3", price=150.0, collateral=0.0, is_ship_contract=True, type="item_exchange", status="outstanding", issuer_id=1, issuer_corporation_id=1, for_corporation=False, date_issued=datetime.fromisoformat("2025-01-01T00:00:00Z"), date_expired=LIVE_EXPIRY, start_location_id=60003760),
    ]
    items = [ContractItem(contract_id=c.contract_id, type_id=101, type_name="Ship", quantity=1, is_included=True, is_singleton=True) for c in contracts]
    db_session.add_all(contracts + items)
    await db_session.flush()  # Use flush to persist data within the ongoing transaction

    # Act: Test min_price
    response = await client.get("/contracts/", params={"min_price": 99.0})
    data = response.json()
    assert response.status_code == 200
    assert data["total"] == 2
    assert {c["contract_id"] for c in data["items"]} == {2, 3}

    # Act: Test max_price
    response = await client.get("/contracts/", params={"max_price": 101.0})
    data = response.json()
    assert response.status_code == 200
    assert data["total"] == 2
    assert {c["contract_id"] for c in data["items"]} == {1, 2}

    # Act: Test both min and max price
    response = await client.get("/contracts/", params={"min_price": 75.0, "max_price": 125.0})
    data = response.json()
    assert response.status_code == 200
    assert data["total"] == 1
    assert data["items"][0]["contract_id"] == 2


@pytest.mark.asyncio
async def test_sort_contracts(client: AsyncClient, db_session: AsyncSession):
    """Tests sorting by different fields and directions."""
    # Arrange
    contract1 = Contract(contract_id=1, title="Z-Contract", price=2000.0, collateral=0.0, is_ship_contract=True, type="item_exchange", status="outstanding", issuer_id=1, issuer_corporation_id=1, for_corporation=False, date_issued=datetime.fromisoformat("2025-01-01T00:00:00Z"), date_expired=LIVE_EXPIRY, start_location_id=60003760)
    item1 = ContractItem(contract_id=1, type_id=102, type_name="Zephyr Frigate", quantity=1, is_included=True, is_singleton=True)

    contract2 = Contract(contract_id=2, title="A-Contract", price=1000.0, collateral=0.0, is_ship_contract=True, type="item_exchange", status="outstanding", issuer_id=1, issuer_corporation_id=1, for_corporation=False, date_issued=datetime.fromisoformat("2025-01-01T00:00:00Z"), date_expired=LIVE_EXPIRY, start_location_id=60003760)
    item2 = ContractItem(contract_id=2, type_id=101, type_name="Abyssal Cruiser", quantity=1, is_included=True, is_singleton=True)
    
    db_session.add_all([contract1, item1, contract2, item2])
    await db_session.flush()  # Use flush to persist data within the ongoing transaction

    # Act: Sort by price ascending
    response = await client.get("/contracts/", params={"sort_by": "price", "sort_direction": "asc"})
    data = response.json()
    assert response.status_code == 200
    assert [c["contract_id"] for c in data["items"]] == [2, 1]

    # Act: Sort by ship_name descending
    response = await client.get("/contracts/", params={"sort_by": "ship_name", "sort_direction": "desc"})
    data = response.json()
    assert response.status_code == 200
    assert [c["contract_id"] for c in data["items"]] == [1, 2]


@pytest.mark.asyncio
async def test_paginate_contracts(client: AsyncClient, db_session: AsyncSession):
    """Tests pagination logic."""
    # Arrange
    contracts = [Contract(contract_id=i, title=f"C{i}", price=i*10, collateral=0.0, is_ship_contract=True, type="item_exchange", status="outstanding", issuer_id=1, issuer_corporation_id=1, for_corporation=False, date_issued=datetime.fromisoformat("2025-01-01T00:00:00Z"), date_expired=LIVE_EXPIRY, start_location_id=60003760) for i in range(1, 11)]
    items = [ContractItem(contract_id=c.contract_id, type_id=101, type_name="Ship", quantity=1, is_included=True, is_singleton=True) for c in contracts]
    db_session.add_all(contracts + items)
    await db_session.flush()  # Use flush to persist data within the ongoing transaction

    # Act: Get page 2 with a size of 3
    response = await client.get("/contracts/", params={"page": 2, "size": 3, "sort_by": "price", "sort_direction": "asc"})
    data = response.json()

    # Assert
    assert response.status_code == 200
    assert data["total"] == 10
    assert data["page"] == 2
    assert data["size"] == 3
    assert [c["contract_id"] for c in data["items"]] == [4, 5, 6]


# --- Endpoint guardrails: the constraints standing between an anonymous caller and the corpus ---

async def test_size_above_the_cap_is_rejected_before_it_reaches_the_corpus(client: AsyncClient):
    """size<=100 is the only thing between a caller and corpus-per-request pages;
    its removal must fail a test, not pass silently."""
    over = await client.get("/contracts/?size=101")
    assert over.status_code == 422

    at_cap = await client.get("/contracts/?size=100")
    assert at_cap.status_code == 200


async def test_a_search_below_min_length_is_rejected_at_the_wire(client: AsyncClient):
    """The schema's min_length=3 guard, pinned at the HTTP surface — toApiQuery
    gates short searches client-side, but the wire contract must hold for any
    caller."""
    response = await client.get("/contracts/?search=ab")
    assert response.status_code == 422


async def test_a_read_path_failure_serves_the_fixed_body_with_no_internals(
    test_app, monkeypatch
):
    """The generic 500 handler's body is a fixed sentence. A failure whose
    exception text carries statement internals (the SQLA-4 shape — an ILIKE
    bind with the user's own search text) must not surface any of it on the
    wire an anonymous caller sees; the scrub is pinned at the log layer
    elsewhere, and this pins the HTTP layer. Starlette's Exception handler
    builds the response AND re-raises, so this client must not re-raise app
    exceptions the way the shared fixture's transport does — the response is
    the subject here."""
    from httpx import ASGITransport

    from fastapi_app.api import contracts as contracts_api

    async def raiser(*args, **kwargs):
        raise RuntimeError("params: {'search_pattern': '%SECRET-BIND-TEXT%'}")

    monkeypatch.setattr(contracts_api, "get_contracts", raiser)

    transport = ASGITransport(app=test_app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as quiet_client:
        response = await quiet_client.get("/contracts/?search=widget")
    assert response.status_code == 500
    assert response.json() == {"detail": "An unexpected server error occurred."}
    assert "SECRET-BIND-TEXT" not in response.text


async def test_a_search_above_max_length_is_rejected_at_the_wire(client: AsyncClient):
    """The search box carries ship and contract names — nothing legitimate needs
    more than 100 characters, and without a ceiling arbitrary-length text binds
    into a double-wildcard ILIKE over two columns on an anonymous endpoint."""
    over = await client.get("/contracts/", params={"search": "x" * 101})
    assert over.status_code == 422

    at_cap = await client.get("/contracts/", params={"search": "x" * 100})
    assert at_cap.status_code == 200


# --- The detail path's own guardrails (coverage register C-1..C-3) ---

async def test_detail_serves_404_for_an_absent_contract(client: AsyncClient, db_session: AsyncSession):
    """The 404 branch had zero tests anywhere in the suite."""
    response = await client.get("/contracts/424242")
    assert response.status_code == 404
    assert response.json() == {"detail": "Contract not found"}


async def test_detail_rejects_a_non_integer_id_at_the_wire(client: AsyncClient):
    response = await client.get("/contracts/not-a-number")
    assert response.status_code == 422


async def test_detail_rejects_ids_outside_the_representable_range(client: AsyncClient):
    """An id above int64 previously rode past validation into the driver and
    surfaced as a 500; ids that cannot exist are a validation failure, not a
    server error. Zero and negatives fall under the same floor."""
    over = await client.get("/contracts/99999999999999999999")
    assert over.status_code == 422

    zero = await client.get("/contracts/0")
    assert zero.status_code == 422


# --- Endpoint 422 sweep over the list params (coverage register C-11..C-13) ---

async def test_page_zero_and_negatives_are_rejected(client: AsyncClient):
    """page ge=1 stands between a caller and a negative OFFSET 500."""
    for value in ("0", "-1"):
        response = await client.get(f"/contracts/?page={value}")
        assert response.status_code == 422, f"page={value}"


async def test_below_floor_numeric_bounds_are_rejected_per_family(client: AsyncClient):
    """Every numeric family's floor, one row each — testing one does not cover
    its siblings. runs floors at -1 (the ESI sentinel the wire tolerates), the
    rest at 0."""
    cases = {
        "min_price": "-1", "max_price": "-1",
        "min_collateral": "-1", "max_collateral": "-1",
        "min_runs": "-2", "max_runs": "-2",
        "min_me": "-1", "max_me": "-1",
        "min_te": "-1", "max_te": "-1",
    }
    for param, value in cases.items():
        response = await client.get(f"/contracts/?{param}={value}")
        assert response.status_code == 422, f"{param}={value}"


async def test_malformed_value_types_are_rejected_per_param(client: AsyncClient):
    """Type junk per param family: id-list members, booleans, and both sort
    enums each parse through different validators."""
    cases = [
        "region_ids=abc",
        "category_id=1.5",
        "is_bpc=maybe",
        "sort_by=bogus_field",
        "sort_direction=sideways",
    ]
    for query in cases:
        response = await client.get(f"/contracts/?{query}")
        assert response.status_code == 422, query


async def test_primary_label_prefers_the_offered_ship_over_an_earlier_named_item(
    client: AsyncClient, db_session: AsyncSession
):
    """The hull is the headline on a ship marketplace: a fitted-hull contract
    whose module row precedes the ship row must still headline the ship. With
    the module first by record_id, named[0] alone produces the wrong answer —
    only the ship-priority branch produces this label."""
    db_session.add_all([
        Contract(
            contract_id=31, title="Fitted hull", price=100, collateral=0.0,
            is_ship_contract=True, type="item_exchange", status="outstanding",
            issuer_id=1, issuer_corporation_id=1, for_corporation=False,
            date_issued=datetime.fromisoformat("2025-01-01T00:00:00Z"),
            date_expired=LIVE_EXPIRY, start_location_id=60003760,
        ),
        ContractItem(
            record_id=310001, contract_id=31, type_id=12058,
            type_name="1MN Afterburner I", quantity=1, is_included=True,
            is_singleton=False, category="module",
        ),
        ContractItem(
            record_id=310002, contract_id=31, type_id=587, type_name="Rifter",
            quantity=1, is_included=True, is_singleton=False, category="ship",
        ),
    ])
    await db_session.flush()

    response = await client.get("/contracts/")
    assert response.status_code == 200
    assert response.json()["items"][0]["primary_label"] == "Rifter"
