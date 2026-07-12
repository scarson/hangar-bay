"""Seam regression tests for ESIClient's single-object endpoints.

Found live during the design phase: the paginated ETag helper accumulates with
`full_data.extend(page_data)`, which flattens a dict payload into its KEYS —
so /universe/types/{id} came back as a list of field-name strings and killed
the aggregation run. Unit tests with dict-returning mocks could never catch it
(the mock bypassed the seam); these tests pin the client's actual return shape
against a mocked HTTP layer instead.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from fastapi_app.core.esi_client_class import ESIClient
from fastapi_app.core.exceptions import ESIRequestFailedError

pytestmark = pytest.mark.asyncio

TYPE_PAYLOAD = {"type_id": 587, "name": "Tristan", "group_id": 25, "market_group_id": 1367}


def _client_with_response(json_data, content: bytes = b"{}") -> ESIClient:
    response = MagicMock()
    response.json.return_value = json_data
    response.content = content
    response.raise_for_status = MagicMock()
    http_client = MagicMock()
    http_client.get = AsyncMock(return_value=response)
    redis_client = MagicMock()
    redis_client.get = AsyncMock(return_value=None)
    redis_client.set = AsyncMock()
    return ESIClient(settings=MagicMock(), http_client=http_client, redis_client=redis_client)


async def test_get_universe_type_returns_the_object_not_its_keys():
    client = _client_with_response(TYPE_PAYLOAD)

    result = await client.get_universe_type(587)

    assert isinstance(result, dict)
    assert result["name"] == "Tristan"
    assert result["group_id"] == 25


async def test_get_universe_type_serves_from_cache_without_http():
    import json

    client = _client_with_response(TYPE_PAYLOAD)
    client.redis_client.get = AsyncMock(return_value=json.dumps(TYPE_PAYLOAD).encode())

    result = await client.get_universe_type(587)

    assert result["name"] == "Tristan"
    client.http_client.get.assert_not_called()


async def test_get_esi_object_rejects_non_object_payloads():
    client = _client_with_response(["type_id", "name", "group_id"])

    with pytest.raises(ESIRequestFailedError):
        await client.get_universe_group(25)
