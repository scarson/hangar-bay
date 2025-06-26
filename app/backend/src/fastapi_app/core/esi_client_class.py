import asyncio
import json
import logging
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

import httpx
import redis.asyncio as aioredis

from .exceptions import ESIRequestFailedError
from .config import Settings

logger = logging.getLogger(__name__)


class ESIClient:
    """
    An asynchronous client for interacting with the EVE Online ESI API.

    This client can operate in two modes:
    1.  As a dependency-injected service with shared `httpx` and `redis` clients
        for high-performance API request handling.
    2.  As a picklable, standalone context manager for background jobs (e.g.,
        APScheduler), where it creates and manages its own clients on-demand.
    """

    def __init__(
        self,
        settings: Settings,
        http_client: Optional[httpx.AsyncClient] = None,
        redis_client: Optional[aioredis.Redis] = None,
    ):
        self.settings = settings
        self._http_client = http_client
        self._redis_client = redis_client
        self._managed_http_client: Optional[httpx.AsyncClient] = None
        self._managed_redis_client: Optional[aioredis.Redis] = None

    @property
    def http_client(self) -> httpx.AsyncClient:
        """Returns the active HTTP client, raising an error if unavailable."""
        client = self._http_client or self._managed_http_client
        if not client:
            raise RuntimeError(
                "HTTP client is not available. ESIClient must be used as a context "
                "manager if clients are not injected at instantiation."
            )
        return client

    @property
    def redis_client(self) -> aioredis.Redis:
        """Returns the active Redis client, raising an error if unavailable."""
        client = self._redis_client or self._managed_redis_client
        if not client:
            raise RuntimeError(
                "Redis client is not available. ESIClient must be used as a context "
                "manager if clients are not injected at instantiation."
            )
        return client

    async def __aenter__(self):
        """Initializes clients if they were not provided during instantiation."""
        if not self._http_client:
            self._managed_http_client = httpx.AsyncClient(
                base_url=self.settings.ESI_BASE_URL,
                headers={"User-Agent": self.settings.ESI_USER_AGENT},
                timeout=self.settings.ESI_TIMEOUT,
            )
        if not self._redis_client:
            self._managed_redis_client = aioredis.from_url(
                str(self.settings.CACHE_URL)
            )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Closes clients that were created by the context manager."""
        if self._managed_http_client:
            await self._managed_http_client.aclose()
        if self._managed_redis_client:
            await self._managed_redis_client.close()

    async def get_esi_data_with_etag_caching(
        self, path: str, all_pages: bool = False, ignore_404: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Generic method to fetch data from ESI, with ETag caching, pagination, and retries.
        This method uses the shared httpx and redis clients.
        """
        full_data = []
        page = 1
        max_retries = 3
        backoff_factor = 0.5  # seconds

        while True:
            paginated_path = f"{path}?page={page}"
            etag_key = f"etag:{paginated_path}"
            data_key = f"data:{paginated_path}"

            cached_etag = await self.redis_client.get(etag_key)
            headers = {"If-None-Match": cached_etag.decode() if cached_etag else ""}

            response = None
            last_exception = None

            for attempt in range(max_retries):
                try:
                    response = await self.http_client.get(paginated_path, headers=headers)
                    if response.status_code < 500:
                        last_exception = None
                        break
                    last_exception = httpx.HTTPStatusError(
                        f"Server error '{response.status_code}'", request=response.request, response=response
                    )
                    logger.warning(f"ESI request to {paginated_path} failed with status {response.status_code}. Attempt {attempt + 1}/{max_retries}.")
                except (httpx.ReadTimeout, httpx.ConnectError) as e:
                    last_exception = e
                    logger.warning(f"Network error for {paginated_path} on attempt {attempt + 1}/{max_retries}: {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(backoff_factor * (2 ** attempt))

            if last_exception:
                if isinstance(last_exception, httpx.HTTPStatusError):
                    raise ESIRequestFailedError(status_code=last_exception.response.status_code, message=str(last_exception))
                else:
                    raise ESIRequestFailedError(message=f"Network error for {paginated_path}: {last_exception}")

            if response.status_code == 404 and ignore_404:
                logger.debug(f"Received 404 for {paginated_path}, treating as end of pages.")
                break
            if response.status_code == 204:
                logger.debug(f"Received 204 for {paginated_path}, treating as end of pages.")
                break
            
            page_data = []
            if response.status_code == 304:
                logger.debug(f"ETag cache hit for {paginated_path}. Serving data from cache.")
                cached_data = await self.redis_client.get(data_key)
                if cached_data:
                    page_data = json.loads(cached_data)
                    full_data.extend(page_data)
            else:
                response.raise_for_status()
                # ESI can return 200 OK with an empty body, which is not valid JSON.
                # Check for content before attempting to parse.
                if not response.content:
                    page_data = []
                else:
                    page_data = response.json()

                if page_data:
                    full_data.extend(page_data)
                    new_etag = response.headers.get("ETag")
                    if new_etag:
                        expires_header = response.headers.get("Expires")
                        cache_duration_seconds = 600
                        if expires_header:
                            try:
                                expire_time = parsedate_to_datetime(expires_header).replace(tzinfo=timezone.utc)
                                current_time = datetime.now(timezone.utc)
                                if expire_time > current_time:
                                    cache_duration_seconds = int((expire_time - current_time).total_seconds())
                            except Exception:
                                pass
                        await self.redis_client.set(etag_key, new_etag, ex=cache_duration_seconds)
                        await self.redis_client.set(data_key, response.content, ex=cache_duration_seconds)

            if not all_pages:
                break
            
            if not page_data:
                break
            
            total_pages_header = response.headers.get("X-Pages")
            if total_pages_header and page >= int(total_pages_header):
                break

            page += 1

        return full_data

    async def get_public_contracts(self, region_id: int) -> list[dict[str, Any]]:
        """Fetches all public contracts for a specific region, handling pagination."""
        path = f"/v1/contracts/public/{region_id}/"
        return await self.get_esi_data_with_etag_caching(path, all_pages=True, ignore_404=True)

    async def get_contract_items(self, contract_id: int) -> list[dict[str, Any]]:
        """Fetches all items for a specific public contract."""
        path = f"/v1/contracts/public/items/{contract_id}/"
        return await self.get_esi_data_with_etag_caching(path)

    async def resolve_ids_to_names(self, ids: list[int]) -> dict[int, str]:
        """Resolves a list of EVE Online IDs to their names."""
        if not ids:
            return {}


        resolved_names = {}
        unique_ids = sorted(list(set(ids)))
        chunk_size = 1000

        for i in range(0, len(unique_ids), chunk_size):
            chunk = unique_ids[i:i + chunk_size]
            try:
                response = await self.http_client.post("/v3/universe/names/", json=chunk)
                response.raise_for_status()
                for item in response.json():
                    resolved_names[item['id']] = item['name']
            except httpx.HTTPStatusError as e:
                logger.error(f"ESI ID resolution failed for chunk starting with {chunk[0]}: {e}")
                continue
            except Exception as e:
                logger.error(f"An unexpected error occurred during ID resolution: {e}")
                continue

        return resolved_names
