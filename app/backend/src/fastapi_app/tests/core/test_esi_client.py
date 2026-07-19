"""Seam regression tests for ESIClient's single-object endpoints.

Found live during the design phase: the paginated ETag helper accumulates with
`full_data.extend(page_data)`, which flattens a dict payload into its KEYS —
so /universe/types/{id} came back as a list of field-name strings and killed
the aggregation run. Unit tests with dict-returning mocks could never catch it
(the mock bypassed the seam); these tests pin the client's actual return shape
against a mocked HTTP layer instead.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from fastapi_app.core.esi_client_class import ESIClient
from fastapi_app.core.exceptions import ESIRequestFailedError

pytestmark = pytest.mark.asyncio

TYPE_PAYLOAD = {"type_id": 587, "name": "Tristan", "group_id": 25, "market_group_id": 1367}


def _ok_response(json_data, content: bytes = b"{}") -> MagicMock:
    response = MagicMock()
    response.status_code = 200
    response.json.return_value = json_data
    response.content = content
    response.request = MagicMock()
    response.raise_for_status = MagicMock()
    return response


def _server_error_response(status_code: int = 503) -> MagicMock:
    response = MagicMock()
    response.status_code = status_code
    response.request = MagicMock()
    return response


def _client_with_response(json_data, content: bytes = b"{}") -> ESIClient:
    response = _ok_response(json_data, content)
    http_client = MagicMock()
    http_client.get = AsyncMock(return_value=response)
    redis_client = MagicMock()
    redis_client.get = AsyncMock(return_value=None)
    redis_client.set = AsyncMock()
    return ESIClient(settings=MagicMock(), http_client=http_client, redis_client=redis_client)


def _client_with_get(get_mock: AsyncMock) -> ESIClient:
    http_client = MagicMock()
    http_client.get = get_mock
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


async def test_get_esi_object_retries_transient_5xx_then_succeeds():
    """A transient 5xx must be retried (mirroring the paginated helper), so a
    blip on /universe/types doesn't silently un-enrich a run's ship contracts."""
    get_mock = AsyncMock(side_effect=[_server_error_response(503), _ok_response(TYPE_PAYLOAD)])
    client = _client_with_get(get_mock)

    with patch("asyncio.sleep", new=AsyncMock()):
        result = await client.get_universe_type(587)

    assert result["name"] == "Tristan"
    assert get_mock.await_count == 2


async def test_get_esi_object_retries_network_errors_then_succeeds():
    """Network errors (timeout/connect) are transient too and must be retried."""
    get_mock = AsyncMock(
        side_effect=[httpx.ConnectError("boom"), _ok_response(TYPE_PAYLOAD)]
    )
    client = _client_with_get(get_mock)

    with patch("asyncio.sleep", new=AsyncMock()):
        result = await client.get_universe_type(587)

    assert result["name"] == "Tristan"
    assert get_mock.await_count == 2


async def test_get_esi_object_raises_after_exhausting_retries():
    """A persistent 5xx exhausts the 3 attempts and raises (never returns junk)."""
    get_mock = AsyncMock(return_value=_server_error_response(500))
    client = _client_with_get(get_mock)

    with patch("asyncio.sleep", new=AsyncMock()):
        with pytest.raises(ESIRequestFailedError):
            await client.get_universe_type(587)

    assert get_mock.await_count == 3


async def test_get_esi_object_survives_cache_read_failure(caplog):
    """An unreachable cache degrades to a live fetch instead of failing the call."""
    client = _client_with_response(TYPE_PAYLOAD)
    client.redis_client.get = AsyncMock(side_effect=RuntimeError("valkey down"))

    with caplog.at_level("WARNING"):
        result = await client.get_universe_type(587)

    assert result["name"] == "Tristan"
    client.http_client.get.assert_awaited_once()
    assert "Object cache read failed for /v3/universe/types/587/: valkey down" in caplog.text


async def test_get_esi_object_survives_cache_write_failure(caplog):
    """A cache write that blows up must not lose the object already fetched."""
    client = _client_with_response(TYPE_PAYLOAD)
    client.redis_client.set = AsyncMock(side_effect=RuntimeError("valkey down"))

    with caplog.at_level("WARNING"):
        result = await client.get_universe_type(587)

    assert result["name"] == "Tristan"
    client.redis_client.set.assert_awaited_once()
    assert "Object cache write failed for /v3/universe/types/587/: valkey down" in caplog.text
