# ABOUTME: Unit tests for ESIClient.resolve_names (POST /v1/universe/ids/, ESI-1 version pin).
# ABOUTME: Drives the seam with pytest-httpx; covers hit, empty-result body, 4xx, 5xx, network error.
from unittest.mock import MagicMock

import httpx
import pytest

from fastapi_app.core.esi_client_class import ESIClient
from fastapi_app.core.exceptions import ESIRequestFailedError

pytestmark = pytest.mark.asyncio

ESI = "http://esi.test"
IDS_URL = f"{ESI}/v1/universe/ids/"


def _client(http: httpx.AsyncClient) -> ESIClient:
    # settings is unused by resolve_names (only http_client is touched); a MagicMock is enough.
    return ESIClient(settings=MagicMock(), http_client=http)


async def test_resolve_names_returns_parsed_body(httpx_mock):
    httpx_mock.add_response(
        method="POST", url=IDS_URL,
        json={"inventory_types": [{"id": 587, "name": "Rifter"}]},
    )
    async with httpx.AsyncClient(base_url=ESI) as http:
        body = await _client(http).resolve_names(["Rifter"])
    assert body["inventory_types"][0]["id"] == 587
    posted = httpx_mock.get_requests()[0]
    assert posted.url.path == "/v1/universe/ids/"   # ESI-1 version pin


async def test_resolve_names_empty_result_body_returns_empty_dict(httpx_mock):
    # ESI answers 200 with no matching category keys when nothing resolves.
    httpx_mock.add_response(method="POST", url=IDS_URL, json={})
    async with httpx.AsyncClient(base_url=ESI) as http:
        body = await _client(http).resolve_names(["Not A Real Ship 9000"])
    assert body == {}


async def test_resolve_names_4xx_raises_with_status(httpx_mock):
    httpx_mock.add_response(method="POST", url=IDS_URL, status_code=404, json={"error": "not found"})
    async with httpx.AsyncClient(base_url=ESI) as http:
        with pytest.raises(ESIRequestFailedError) as exc:
            await _client(http).resolve_names(["x"])
    assert exc.value.status_code == 404


async def test_resolve_names_5xx_raises_with_status(httpx_mock):
    httpx_mock.add_response(method="POST", url=IDS_URL, status_code=503, text="upstream down")
    async with httpx.AsyncClient(base_url=ESI) as http:
        with pytest.raises(ESIRequestFailedError) as exc:
            await _client(http).resolve_names(["x"])
    assert exc.value.status_code == 503


async def test_resolve_names_network_error_raises(httpx_mock):
    httpx_mock.add_exception(httpx.ConnectError("boom"), url=IDS_URL)
    async with httpx.AsyncClient(base_url=ESI) as http:
        with pytest.raises(ESIRequestFailedError):
            await _client(http).resolve_names(["x"])


async def test_resolve_names_non_json_body_raises(httpx_mock):
    # A 200 with a non-JSON body (e.g. an upstream HTML error page) must not escape as a raw
    # ValueError/500 — response.json() failures normalize to ESIRequestFailedError (design §4.5).
    httpx_mock.add_response(method="POST", url=IDS_URL, status_code=200, text="<html>not json</html>")
    async with httpx.AsyncClient(base_url=ESI) as http:
        with pytest.raises(ESIRequestFailedError):
            await _client(http).resolve_names(["x"])
