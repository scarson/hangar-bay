# ABOUTME: Round-trip proofs for the M3 authed_user fixture and login_as helper (real session in FakeRedis).
import pytest

from fastapi_app.tests.conftest import login_as

pytestmark = pytest.mark.asyncio


async def test_authed_user_round_trips_me(authed_user):
    user, client = authed_user
    resp = await client.get("/me")
    assert resp.status_code == 200
    assert resp.json() == {"character_id": 91000001, "character_name": "Sesta Hound"}
    assert user.id is not None  # inserted + flushed, real users.id


async def test_login_as_switches_identity(auth_client, db_session):
    other = await login_as(
        auth_client, db_session,
        character_id=91000042, character_name="Bravo Pilot", owner_hash="OWN2",
    )
    resp = await auth_client.get("/me")
    assert resp.status_code == 200
    assert resp.json()["character_id"] == 91000042
    assert other.character_id == 91000042
