import logging
import json
from typing import Any, Optional

import httpx
from redis.asyncio import Redis

from .exceptions import ESIRequestFailedError, ESINotModifiedError

logger = logging.getLogger(__name__)


class ESIClient:
    """
    An asynchronous client for interacting with the EVE Online ESI API,
    with built-in support for Redis-based ETag caching.
    """

    def __init__(self, http_client: httpx.AsyncClient, redis_client: Redis):
        self.http_client = http_client
        self.redis_client = redis_client

    async def get_esi_data_with_etag_caching(
        self, path: str
    ) -> list[dict[str, Any]]:
        """
        Fetches paginated data from an ESI endpoint, handling ETag caching.

        Args:
            path: The ESI API path to request (e.g., '/v1/contracts/public/10000002/').

        Returns:
            A list of dictionaries containing the data from all pages.

        Raises:
            ESIRequestFailedError: If any ESI request fails.
            ESINotModifiedError: If the initial request returns a 304, indicating no new data.
        """
        all_data = []
        page = 1
        first_page = True

        while True:
            paginated_path = f"{path}?page={page}"
            etag_cache_key = f"etag:{paginated_path}"
            data_cache_key = f"data:{paginated_path}"
            headers = {}

            try:
                etag = await self.redis_client.get(etag_cache_key)
                if etag:
                    headers["If-None-Match"] = etag
            except Exception as e:
                logger.warning(f"Redis ETag check failed for {paginated_path}: {e}", exc_info=True)

            try:
                response = await self.http_client.get(paginated_path, headers=headers)

                if response.status_code == 304:  # Not Modified
                    logger.info(f"ETag match for {paginated_path}, using cached data.")
                    if first_page:
                        raise ESINotModifiedError(f"Content for {path} not modified.")
                    
                    cached_data = await self.redis_client.get(data_cache_key)
                    if cached_data:
                        page_data = json.loads(cached_data)
                    else:
                        logger.warning(f"ETag match but no cached data for {data_cache_key}, re-fetching.")
                        response = await self.http_client.get(paginated_path)
                        response.raise_for_status()
                        page_data = response.json()
                elif response.status_code == 200:  # OK
                    page_data = response.json()
                    new_etag = response.headers.get("ETag")
                    if new_etag:
                        try:
                            await self.redis_client.set(etag_cache_key, new_etag, ex=3600)
                            await self.redis_client.set(data_cache_key, json.dumps(page_data), ex=3600)
                        except Exception as e:
                            logger.warning(f"Redis ETag/data caching failed for {paginated_path}: {e}", exc_info=True)
                else:
                    response.raise_for_status()

                if not page_data:
                    break

                all_data.extend(page_data)
                page += 1
                first_page = False

                x_pages = response.headers.get('x-pages')
                if x_pages and page > int(x_pages):
                    break

            except httpx.HTTPStatusError as e:
                logger.error(f"ESI request failed for {paginated_path}: {e}")
                raise ESIRequestFailedError(status_code=e.response.status_code, message=str(e))
            except ESINotModifiedError:
                raise
            except Exception as e:
                logger.error(f"An unexpected error occurred fetching ESI data for {paginated_path}: {e}")
                raise ESIRequestFailedError(message=str(e))

        return all_data

    async def get_public_contracts(self, region_id: int) -> list[dict[str, Any]]:
        """Fetches all public contracts for a specific region."""
        path = f"/v1/contracts/public/{region_id}/"
        return await self.get_esi_data_with_etag_caching(path)

    async def get_contract_items(self, contract_id: int) -> list[dict[str, Any]]:
        """Fetches all items for a specific public contract."""
        path = f"/v1/contracts/public/items/{contract_id}/"
        return await self.get_esi_data_with_etag_caching(path)

    async def resolve_ids_to_names(self, ids: list[int]) -> dict[int, dict[str, Any]]:
        """
        Resolves a list of EVE Online IDs to their names and categories.
        """
        resolved_data = {}
        unique_ids = sorted(list(set(ids)))
        chunk_size = 1000

        for i in range(0, len(unique_ids), chunk_size):
            chunk = unique_ids[i:i + chunk_size]
            try:
                response = await self.http_client.post("/v3/universe/names/", json=chunk)
                response.raise_for_status()
                
                for item in response.json():
                    resolved_data[item['id']] = {
                        'name': item.get('name'),
                        'category': item.get('category')
                    }

            except httpx.HTTPStatusError as e:
                logger.error(f"ESI ID resolution failed: {e}")
                continue 
            except Exception as e:
                logger.error(f"An unexpected error occurred during ID resolution: {e}")
                continue

        return resolved_data

    async def get_esi_single_page_with_etag(self, path: str) -> dict[str, Any] | list[Any]:
        """
        Fetches data from a single-page ESI endpoint, handling ETag caching.
        """
        etag_cache_key = f"etag:{path}"
        data_cache_key = f"data:{path}"
        headers = {}

        try:
            etag = await self.redis_client.get(etag_cache_key)
            if etag:
                headers["If-None-Match"] = etag
        except Exception as e:
            logger.warning(f"Redis ETag check failed for {path}: {e}", exc_info=True)

        try:
            response = await self.http_client.get(path, headers=headers)

            if response.status_code == 304:
                logger.info(f"ETag match for {path}, using cached data.")
                cached_data = await self.redis_client.get(data_cache_key)
                if cached_data:
                    return json.loads(cached_data)
                else:
                    logger.warning(f"ETag match but no cached data for {data_cache_key}, re-fetching.")
                    response = await self.http_client.get(path)
                    response.raise_for_status()
                    data = response.json()
            elif response.status_code == 200:
                data = response.json()
                new_etag = response.headers.get("ETag")
                if new_etag:
                    try:
                        await self.redis_client.set(etag_cache_key, new_etag, ex=3600)
                        await self.redis_client.set(data_cache_key, json.dumps(data), ex=3600)
                    except Exception as e:
                        logger.warning(f"Redis ETag/data caching failed for {path}: {e}", exc_info=True)
            else:
                response.raise_for_status()
                data = response.json()

            return data

        except httpx.HTTPStatusError as e:
            logger.error(f"ESI request failed for {path}: {e}")
            raise ESIRequestFailedError(status_code=e.response.status_code, message=str(e))
        except Exception as e:
            logger.error(f"An unexpected error occurred fetching ESI data for {path}: {e}")
            raise ESIRequestFailedError(message=str(e))

    async def get_market_groups(self) -> list[int]:
        """Fetches the list of root market group IDs."""
        path = "/v1/markets/groups/"
        return await self.get_esi_single_page_with_etag(path)
