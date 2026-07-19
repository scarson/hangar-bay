"""Tests for ESIClient's fetch paths: single-object endpoints and the paginated ETag helper.

Found live during the design phase: the paginated ETag helper accumulates with
`full_data.extend(page_data)`, which flattens a dict payload into its KEYS —
so /universe/types/{id} came back as a list of field-name strings and killed
the aggregation run. Unit tests with dict-returning mocks could never catch it
(the mock bypassed the seam); these tests pin the client's actual return shape
against a mocked HTTP layer instead.

The second half of this file characterizes `get_esi_data_with_etag_caching` —
conditional requests, the 304 cache-serve, TTL derivation, pagination
termination, and error propagation — pinning observed behavior so the loop can
be decomposed without drift.
"""

import json
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from fastapi_app.core.esi_client_class import ESIClient
from fastapi_app.core.exceptions import ESIRequestFailedError

pytestmark = pytest.mark.asyncio

TYPE_PAYLOAD = {"type_id": 587, "name": "Tristan", "group_id": 25, "market_group_id": 1367}

ETAG_PATH = "/v1/test/"
ETAG_KEY_PAGE_1 = "etag:/v1/test/?page=1"
DATA_KEY_PAGE_1 = "data:/v1/test/?page=1"


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


def _etag_response(
    status_code: int = 200,
    json_data=None,
    content: bytes = b"[]",
    headers: dict | None = None,
) -> MagicMock:
    """Build a response double for the paginated ETag path.

    `headers` is always a real dict: on a bare MagicMock `response.headers.get("ETag")`
    answers with a truthy mock, which silently fires the cache-write branch with a junk
    etag and makes `int(X-Pages)` raise. Pass `headers={}` to mean "no headers".
    """
    response = MagicMock()
    response.status_code = status_code
    response.json.return_value = json_data
    response.content = content
    response.headers = dict(headers or {})
    response.request = MagicMock()
    response.raise_for_status = MagicMock()
    return response


def _etag_client(get_mock: AsyncMock, cache: dict | None = None) -> ESIClient:
    """Wire an ESIClient for the ETag path against a bytes-valued cache double.

    The ETag path's production client is `aioredis.from_url(...)` with the default
    `decode_responses=False`, and the cached-etag read calls `.decode()` — so seeded
    values are bytes and an unseeded key reads back as None.
    """
    store = dict(cache or {})
    http_client = MagicMock()
    http_client.get = get_mock
    redis_client = MagicMock()
    redis_client.get = AsyncMock(side_effect=lambda key: store.get(key))
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


async def test_etag_single_page_200_returns_data_and_stores_etag_and_body():
    body = b'[{"contract_id": 1}]'
    response = _etag_response(
        json_data=[{"contract_id": 1}], content=body, headers={"ETag": "etag-v1"}
    )
    client = _etag_client(AsyncMock(return_value=response))

    data = await client.get_esi_data_with_etag_caching(ETAG_PATH)

    assert data == [{"contract_id": 1}]
    client.redis_client.set.assert_any_await(ETAG_KEY_PAGE_1, "etag-v1", ex=600)
    client.redis_client.set.assert_any_await(DATA_KEY_PAGE_1, body, ex=600)


async def test_etag_304_serves_cached_body():
    get_mock = AsyncMock(return_value=_etag_response(status_code=304, headers={}))
    client = _etag_client(
        get_mock,
        cache={ETAG_KEY_PAGE_1: b"etag-v1", DATA_KEY_PAGE_1: b'[{"contract_id": 42}]'},
    )

    data = await client.get_esi_data_with_etag_caching(ETAG_PATH)

    assert data == [{"contract_id": 42}]
    assert get_mock.await_count == 1


async def test_etag_304_with_missing_cache_returns_empty():
    """A live etag whose cached body was evicted yields an empty page: the 304
    branch never falls through to the live-fetch branch to recover the body.

    The response double carries a body no real 304 would have, purely so a
    fall-through would produce visibly different data than the [] pinned here.
    """
    live_body = [{"contract_id": 999}]
    get_mock = AsyncMock(
        return_value=_etag_response(
            status_code=304,
            json_data=live_body,
            content=b'[{"contract_id": 999}]',
            headers={},
        )
    )
    client = _etag_client(get_mock, cache={ETAG_KEY_PAGE_1: b"etag-v1"})

    data = await client.get_esi_data_with_etag_caching(ETAG_PATH)

    assert data == []
    assert get_mock.await_count == 1


async def test_etag_sends_if_none_match_from_cached_etag():
    warm_get = AsyncMock(return_value=_etag_response(json_data=[], headers={}))
    warm_client = _etag_client(warm_get, cache={ETAG_KEY_PAGE_1: b'W/"deadbeef"'})

    await warm_client.get_esi_data_with_etag_caching(ETAG_PATH)

    assert warm_get.await_args.kwargs["headers"]["If-None-Match"] == 'W/"deadbeef"'

    cold_get = AsyncMock(return_value=_etag_response(json_data=[], headers={}))
    cold_client = _etag_client(cold_get)

    await cold_client.get_esi_data_with_etag_caching(ETAG_PATH)

    assert cold_get.await_args.kwargs["headers"]["If-None-Match"] == ""


async def test_expires_header_sets_cache_ttl():
    expires = format_datetime(
        datetime.now(timezone.utc) + timedelta(seconds=90), usegmt=True
    )
    response = _etag_response(
        json_data=[{"contract_id": 1}],
        content=b'[{"contract_id": 1}]',
        headers={"ETag": "etag-v1", "Expires": expires},
    )
    client = _etag_client(AsyncMock(return_value=response))

    await client.get_esi_data_with_etag_caching(ETAG_PATH)

    ttls = {call.kwargs["ex"] for call in client.redis_client.set.await_args_list}
    assert len(ttls) == 1, f"etag and body must share one TTL, got {ttls}"
    ttl = ttls.pop()
    # HTTP dates are whole seconds, so the derived delta truncates just under 90.
    assert 85 <= ttl <= 90, f"expected an Expires-derived TTL, got {ttl}"


async def test_malformed_expires_falls_back_to_600():
    response = _etag_response(
        json_data=[{"contract_id": 1}],
        content=b'[{"contract_id": 1}]',
        headers={"ETag": "etag-v1", "Expires": "not-a-date"},
    )
    client = _etag_client(AsyncMock(return_value=response))

    await client.get_esi_data_with_etag_caching(ETAG_PATH)

    client.redis_client.set.assert_any_await(ETAG_KEY_PAGE_1, "etag-v1", ex=600)


async def test_past_expires_falls_back_to_600():
    """An already-elapsed Expires must not produce a zero or negative TTL."""
    expires = format_datetime(
        datetime.now(timezone.utc) - timedelta(seconds=90), usegmt=True
    )
    response = _etag_response(
        json_data=[{"contract_id": 1}],
        content=b'[{"contract_id": 1}]',
        headers={"ETag": "etag-v1", "Expires": expires},
    )
    client = _etag_client(AsyncMock(return_value=response))

    await client.get_esi_data_with_etag_caching(ETAG_PATH)

    client.redis_client.set.assert_any_await(ETAG_KEY_PAGE_1, "etag-v1", ex=600)


async def test_pagination_follows_x_pages():
    page_1 = _etag_response(
        json_data=[{"contract_id": 1}],
        content=b'[{"contract_id": 1}]',
        headers={"ETag": "etag-p1", "X-Pages": "2"},
    )
    page_2 = _etag_response(
        json_data=[{"contract_id": 2}],
        content=b'[{"contract_id": 2}]',
        headers={"ETag": "etag-p2", "X-Pages": "2"},
    )
    get_mock = AsyncMock(side_effect=[page_1, page_2])
    client = _etag_client(get_mock)

    data = await client.get_esi_data_with_etag_caching(ETAG_PATH, all_pages=True)

    assert data == [{"contract_id": 1}, {"contract_id": 2}]
    assert get_mock.await_count == 2
    assert [call.args[0] for call in get_mock.await_args_list] == [
        "/v1/test/?page=1",
        "/v1/test/?page=2",
    ]


async def test_pagination_stops_on_empty_page():
    """X-Pages claims a third page; the empty second page ends the walk anyway."""
    page_1 = _etag_response(
        json_data=[{"contract_id": 1}],
        content=b'[{"contract_id": 1}]',
        headers={"ETag": "etag-p1", "X-Pages": "3"},
    )
    page_2 = _etag_response(json_data=[], content=b"[]", headers={"X-Pages": "3"})
    get_mock = AsyncMock(side_effect=[page_1, page_2])
    client = _etag_client(get_mock)

    data = await client.get_esi_data_with_etag_caching(ETAG_PATH, all_pages=True)

    assert data == [{"contract_id": 1}]
    assert get_mock.await_count == 2


async def test_404_with_ignore_404_ends_pagination_quietly():
    page_1 = _etag_response(
        json_data=[{"contract_id": 1}],
        content=b'[{"contract_id": 1}]',
        headers={"ETag": "etag-p1", "X-Pages": "3"},
    )
    page_2 = _etag_response(status_code=404, headers={})
    get_mock = AsyncMock(side_effect=[page_1, page_2])
    client = _etag_client(get_mock)

    data = await client.get_esi_data_with_etag_caching(
        ETAG_PATH, all_pages=True, ignore_404=True
    )

    assert data == [{"contract_id": 1}]
    assert get_mock.await_count == 2
    page_2.raise_for_status.assert_not_called()


async def test_204_ends_pagination():
    """204 is terminal regardless of ignore_404."""
    page_1 = _etag_response(
        json_data=[{"contract_id": 1}],
        content=b'[{"contract_id": 1}]',
        headers={"ETag": "etag-p1", "X-Pages": "3"},
    )
    page_2 = _etag_response(status_code=204, content=b"", headers={})
    get_mock = AsyncMock(side_effect=[page_1, page_2])
    client = _etag_client(get_mock)

    data = await client.get_esi_data_with_etag_caching(ETAG_PATH, all_pages=True)

    assert data == [{"contract_id": 1}]
    assert get_mock.await_count == 2
    page_2.raise_for_status.assert_not_called()


async def test_single_page_mode_ignores_x_pages():
    response = _etag_response(
        json_data=[{"contract_id": 1}],
        content=b'[{"contract_id": 1}]',
        headers={"ETag": "etag-v1", "X-Pages": "5"},
    )
    get_mock = AsyncMock(return_value=response)
    client = _etag_client(get_mock)

    data = await client.get_esi_data_with_etag_caching(ETAG_PATH)

    assert data == [{"contract_id": 1}]
    assert get_mock.await_count == 1


async def test_retry_exhaustion_raises_esi_request_failed():
    get_mock = AsyncMock(return_value=_server_error_response(503))
    client = _etag_client(get_mock)

    with patch("asyncio.sleep", new=AsyncMock()):
        with pytest.raises(ESIRequestFailedError) as excinfo:
            await client.get_esi_data_with_etag_caching(ETAG_PATH)

    assert excinfo.value.status_code == 503
    assert get_mock.await_count == 3


async def test_200_with_empty_body_treated_as_empty_page():
    """ESI answers 200 with an empty body; the content guard keeps that off json()."""
    response = _etag_response(
        json_data=[{"contract_id": 1}], content=b"", headers={"ETag": "etag-v1"}
    )
    client = _etag_client(AsyncMock(return_value=response))

    data = await client.get_esi_data_with_etag_caching(ETAG_PATH)

    assert data == []
    response.json.assert_not_called()
    client.redis_client.set.assert_not_awaited()


async def test_single_page_mode_never_reads_x_pages():
    """Single-page mode breaks before X-Pages is parsed, so an unparseable value
    is inert. Reordering the termination checks surfaces here as a ValueError."""
    response = _etag_response(
        json_data=[{"contract_id": 1}],
        content=b'[{"contract_id": 1}]',
        headers={"ETag": "etag-v1", "X-Pages": "garbage"},
    )
    get_mock = AsyncMock(return_value=response)
    client = _etag_client(get_mock)

    data = await client.get_esi_data_with_etag_caching(ETAG_PATH)

    assert data == [{"contract_id": 1}]
    assert get_mock.await_count == 1


async def test_empty_page_breaks_before_x_pages_is_parsed():
    """An empty page ends the walk before X-Pages is parsed, so an unparseable
    value is inert. Reordering the termination checks surfaces here as a ValueError."""
    response = _etag_response(json_data=[], content=b"[]", headers={"X-Pages": "garbage"})
    get_mock = AsyncMock(return_value=response)
    client = _etag_client(get_mock)

    data = await client.get_esi_data_with_etag_caching(ETAG_PATH, all_pages=True)

    assert data == []
    assert get_mock.await_count == 1


async def test_404_without_ignore_propagates_http_status_error():
    """Unlike _get_esi_object, this path does not normalize a 4xx into
    ESIRequestFailedError — raise_for_status escapes verbatim."""
    response = _etag_response(status_code=404, headers={})
    response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "Client error '404 Not Found'", request=response.request, response=response
    )
    client = _etag_client(AsyncMock(return_value=response))

    with pytest.raises(httpx.HTTPStatusError) as excinfo:
        await client.get_esi_data_with_etag_caching(ETAG_PATH)

    assert not isinstance(excinfo.value, ESIRequestFailedError)


async def test_redis_read_failure_propagates_on_etag_path():
    """This path has no cache-failure guard: an unreachable cache fails the call
    outright rather than degrading to a live fetch."""
    get_mock = AsyncMock(return_value=_etag_response(json_data=[], headers={}))
    client = _etag_client(get_mock)
    client.redis_client.get = AsyncMock(side_effect=RuntimeError("valkey down"))

    with pytest.raises(RuntimeError, match="valkey down"):
        await client.get_esi_data_with_etag_caching(ETAG_PATH)

    get_mock.assert_not_awaited()


async def test_malformed_cached_json_propagates():
    get_mock = AsyncMock(return_value=_etag_response(status_code=304, headers={}))
    client = _etag_client(
        get_mock,
        cache={ETAG_KEY_PAGE_1: b"etag-v1", DATA_KEY_PAGE_1: b"not-json"},
    )

    with pytest.raises(json.JSONDecodeError):
        await client.get_esi_data_with_etag_caching(ETAG_PATH)


async def test_malformed_200_json_propagates():
    body = "<html>bad gateway</html>"
    response = _etag_response(content=body.encode(), headers={"ETag": "etag-v1"})
    response.json.side_effect = json.JSONDecodeError("Expecting value", body, 0)
    client = _etag_client(AsyncMock(return_value=response))

    with pytest.raises(json.JSONDecodeError) as excinfo:
        await client.get_esi_data_with_etag_caching(ETAG_PATH)

    assert not isinstance(excinfo.value, ESIRequestFailedError)
