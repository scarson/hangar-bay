# ABOUTME: Pins the request-scoped ESIClient wiring in core/dependencies.py.
# ABOUTME: Deleting the rate_limit_wait_budget kwarg would keep the rest of the suite green.
from unittest.mock import MagicMock

import pytest

from fastapi_app.core.dependencies import get_esi_client

pytestmark = pytest.mark.asyncio


async def test_get_esi_client_sets_a_1s_rate_limit_wait_budget():
    """The request-scoped client must fail fast rather than hold a user's connection
    through ESI's cool-down (design: watchlist add pipeline). No behavioral test of
    the watchlist API would fail if this wiring were dropped — a 60s default budget
    still lets those tests' short mocked backoffs complete — so this pins the
    constructor argument directly.
    """
    client = await get_esi_client(
        settings=MagicMock(), http_client=MagicMock(), redis_client=MagicMock()
    )

    assert client.rate_limit_wait_budget == 1.0
