"""ABOUTME: Tests for bulk_upsert's on-conflict semantics, chiefly preserve_on_null:
ABOUTME: NULL in a preserved update column keeps the stored value instead of blanking it.

A transient /universe/names outage makes resolve_ids_to_names return a partial map,
so every re-sighted contract's row carries NULL in the denormalized name columns.
Without per-column coalesce semantics the upsert copies that NULL over names it had
already resolved (F008 decision log D10). These tests pin the preserve_on_null
contract at the bulk_upsert level; the aggregation-pipeline tests cover the same
hazard end-to-end.
"""

from datetime import datetime, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from fastapi_app.models.contracts import Contract
from fastapi_app.services.db_upsert import bulk_upsert

pytestmark = pytest.mark.asyncio


def _contract_row(contract_id: int, **overrides) -> dict:
    row = {
        "contract_id": contract_id,
        "issuer_id": 1,
        "issuer_corporation_id": 1,
        "type": "item_exchange",
        "status": "outstanding",
        "price": 100.0,
        "collateral": 0.0,
        "for_corporation": False,
        "date_issued": datetime(2026, 7, 1, tzinfo=timezone.utc),
        "date_expired": datetime(2027, 7, 1, tzinfo=timezone.utc),
        "issuer_name": "Original Pilot",
        "title": "first sighting",
    }
    row.update(overrides)
    return row


async def _fetch(db_session: AsyncSession, contract_id: int) -> Contract:
    return (
        await db_session.execute(
            select(Contract).where(Contract.contract_id == contract_id)
        )
    ).scalar_one()


async def test_preserved_column_keeps_stored_value_when_update_supplies_null(
    db_session: AsyncSession,
):
    await bulk_upsert(db_session, Contract, [_contract_row(910001)])

    await bulk_upsert(
        db_session,
        Contract,
        [_contract_row(910001, issuer_name=None, title="second sighting")],
        preserve_on_null={"issuer_name"},
    )

    row = await _fetch(db_session, 910001)
    assert row.issuer_name == "Original Pilot"
    # Non-preserved columns keep plain copy semantics within the same statement.
    assert row.title == "second sighting"


async def test_preserved_column_still_updates_on_a_non_null_value(
    db_session: AsyncSession,
):
    await bulk_upsert(db_session, Contract, [_contract_row(910002)])

    await bulk_upsert(
        db_session,
        Contract,
        [_contract_row(910002, issuer_name="Renamed Pilot")],
        preserve_on_null={"issuer_name"},
    )

    row = await _fetch(db_session, 910002)
    assert row.issuer_name == "Renamed Pilot"


async def test_unpreserved_column_null_still_overwrites(db_session: AsyncSession):
    """preserve_on_null is opt-in per column; everything else keeps copy semantics."""
    await bulk_upsert(db_session, Contract, [_contract_row(910003)])

    await bulk_upsert(
        db_session,
        Contract,
        [_contract_row(910003, title=None)],
        preserve_on_null={"issuer_name"},
    )

    row = await _fetch(db_session, 910003)
    assert row.title is None


async def test_preserved_null_on_a_fresh_insert_stays_null(db_session: AsyncSession):
    """The coalesce fallback only fires on conflict; an unresolved name on first
    sighting inserts as NULL exactly as before."""
    await bulk_upsert(
        db_session,
        Contract,
        [_contract_row(910004, issuer_name=None)],
        preserve_on_null={"issuer_name"},
    )

    row = await _fetch(db_session, 910004)
    assert row.issuer_name is None
