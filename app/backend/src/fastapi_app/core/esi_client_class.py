import asyncio
import json
import logging
from typing import Any, Dict, List
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

import httpx
import redis.asyncio as aioredis # Renamed for clarity and to use from_url

from .exceptions import ESIRequestFailedError, ESINotModifiedError
from .config import Settings # Import Settings for type hint and usage

logger = logging.getLogger(__name__)


class ESIClient:
    # DEBUG: Class variable to track if http_client is managed by ESIClient instance or externally.
    # This is more for conceptual understanding during refactor, not for runtime logic.
    MANAGES_OWN_HTTP_CLIENT = True
    """
    An asynchronous client for interacting with the EVE Online ESI API,
    with built-in support for Redis-based ETag caching.
    """

    def __init__(self, settings: Settings): # Removed http_client and redis_client
        self.settings = settings # Store settings to create http_client and redis_client

    async def get_esi_data_with_etag_caching(
        self, path: str, all_pages: bool = False, ignore_404: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Generic method to fetch data from ESI, with ETag caching, pagination, and retries.

        Args:
            path: The ESI API path to request.
            all_pages: If True, fetches all pages of a paginated endpoint.
            ignore_404: If True, treats a 404 status as the end of pages instead of an error.

        Returns:
            A list of dictionaries containing the ESI data.
        """
        redis_client = aioredis.from_url(str(self.settings.CACHE_URL))
        try:
            async with httpx.AsyncClient(
                base_url=self.settings.ESI_BASE_URL,
                headers={"User-Agent": self.settings.ESI_USER_AGENT},
                timeout=30.0
            ) as http_client:
                
                full_data = []
                page = 1
                max_retries = 3
                backoff_factor = 0.5 # seconds

                while True:
                    paginated_path = f"{path}?page={page}"
                    etag_key = f"etag:{paginated_path}"
                    data_key = f"data:{paginated_path}"
                    
                    cached_etag = await redis_client.get(etag_key)
                    headers = {"If-None-Match": cached_etag.decode() if cached_etag else ""}

                    response = None
                    last_exception = None

                    for attempt in range(max_retries):
                        try:
                            response = await http_client.get(paginated_path, headers=headers)
                            
                            # If status is not a server error (>=500), it's a definitive success or failure.
                            # No need to retry for 2xx, 3xx, or 4xx codes.
                            if response.status_code < 500:
                                last_exception = None # Clear previous exceptions
                                break # Exit retry loop

                            # It's a 5xx error, so we should retry.
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

                    # --- We now have a successful response (or a non-retriable error) ---
                    if response.status_code == 404 and ignore_404:
                        logger.debug(f"Received 404 for {paginated_path}, treating as end of pages.")
                        break
                    if response.status_code == 204:
                        logger.debug(f"Received 204 for {paginated_path}, treating as end of pages.")
                        break
                    if response.status_code == 304:
                        logger.debug(f"ETag cache hit for {paginated_path}. Serving data from cache.")
                        cached_data = await redis_client.get(data_key)
                        if cached_data:
                            full_data.extend(json.loads(cached_data))
                        break

                    response.raise_for_status() # Raise for any remaining client errors (e.g., 401, 403)

                    # Process 200 OK
                    page_data = response.json()
                    if not page_data:
                        break

                    full_data.extend(page_data)

                    # Cache new data
                    new_etag = response.headers.get("ETag")
                    if new_etag:
                        expires_header = response.headers.get("Expires")
                        cache_duration_seconds = 600  # Default
                        if expires_header:
                            try:
                                expire_time = parsedate_to_datetime(expires_header).replace(tzinfo=timezone.utc)
                                current_time = datetime.now(timezone.utc)
                                if expire_time > current_time:
                                    cache_duration_seconds = int((expire_time - current_time).total_seconds())
                            except Exception:
                                pass # Use default
                        await redis_client.set(etag_key, new_etag, ex=cache_duration_seconds)
                        await redis_client.set(data_key, response.content, ex=cache_duration_seconds)

                    if not all_pages:
                        break
                    
                    total_pages_header = response.headers.get("X-Pages")
                    if total_pages_header and page >= int(total_pages_header):
                        break

                    page += 1

                return full_data
        finally:
            await redis_client.close()



    async def get_public_contracts(self, region_id: int) -> list[dict[str, Any]]:
        """Fetches all public contracts for a specific region, handling pagination."""
        path = f"/v1/contracts/public/{region_id}/"
        # Set all_pages=True to fetch all pages and ignore_404=True to handle empty pages gracefully.
        return await self.get_esi_data_with_etag_caching(path, all_pages=True, ignore_404=True)

    async def get_contract_items(self, contract_id: int) -> list[dict[str, Any]]:
        """Fetches all items for a specific public contract."""
        path = f"/v1/contracts/public/items/{contract_id}/"
        return await self.get_esi_data_with_etag_caching(path)

    async def resolve_ids_to_names(self, ids: list[int]) -> dict[int, dict[str, Any]]:
        async with httpx.AsyncClient(
            base_url=self.settings.ESI_BASE_URL, 
            headers={"User-Agent": self.settings.ESI_USER_AGENT},
            timeout=30.0
        ) as http_client:
            """
            Resolves a list of EVE Online IDs to their names and categories.
            """
            resolved_data = {}
            unique_ids = sorted(list(set(ids)))
            chunk_size = 1000

            for i in range(0, len(unique_ids), chunk_size):
                chunk = unique_ids[i:i + chunk_size]
                try:
                    response = await http_client.post("/v3/universe/names/", json=chunk)
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
        async with httpx.AsyncClient(
            base_url=self.settings.ESI_BASE_URL, 
            headers={"User-Agent": self.settings.ESI_USER_AGENT},
            timeout=30.0
        ) as http_client:
            etag_cache_key = f"etag:{path}"
            data_cache_key = f"data:{path}"
            headers = {}
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
            # If ignore_404 is True and we got a 404, return None as a signal of no data
            if ignore_404 and e.response.status_code == 404:
                logging.debug(f"ESI returned 404 for {path}, and ignore_404 is True. Stopping pagination.")
                return None
            # Otherwise, re-raise our custom exception to be handled by the caller
            raise ESIRequestFailedError(status_code=e.response.status_code, message=str(e))
        except Exception as e:
            logger.error(f"An unexpected error occurred fetching ESI data for {path}: {e}")
            raise ESIRequestFailedError(message=str(e))

    async def get_market_groups(self) -> list[int]:
        """Fetches the list of root market group IDs."""
        path = "/v1/markets/groups/"
        return await self.get_esi_single_page_with_etag(path)
