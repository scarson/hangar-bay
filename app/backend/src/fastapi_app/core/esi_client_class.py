import asyncio
import json
import logging
from typing import Any, Dict, List
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

import httpx
from redis.asyncio import Redis

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

    def __init__(self, redis_client: Redis, settings: Settings): # Removed http_client, added settings
        self.settings = settings # Store settings to create http_client
        self.redis_client = redis_client

    async def get_esi_data_with_etag_caching(
        self, path: str, all_pages: bool = False
    ) -> List[Dict[str, Any]]:
        async with httpx.AsyncClient(
            base_url=self.settings.ESI_BASE_URL,
            headers={"User-Agent": self.settings.ESI_USER_AGENT},
            timeout=30.0
        ) as http_client:
            """Generic method to fetch data from ESI, with ETag and Redis caching.

            Args:
                path: The ESI API path to request.
                all_pages: If True, fetches all pages of a paginated endpoint.

            Returns:
                A list of dictionaries containing the ESI data.
            """
            full_data = []
            page = 1
            # TEMPORARY: Limit pages for faster debugging of contract fetching
            MAX_PAGES_FOR_DEBUG = 1
            is_public_contracts_path = path.startswith("/v1/contracts/public/") and path.endswith("/")

            while True:
                page_data = [] # Always reset page_data before a new attempt
                paginated_path = f"{path}?page={page}"

                # ETag Caching Logic
                etag_key = f"etag:{paginated_path}"
                data_key = f"data:{paginated_path}"
                cached_etag = await self.redis_client.get(etag_key)
                headers = {"If-None-Match": cached_etag.decode() if cached_etag else ""}

                # Retry Logic
                max_retries = 3
                for attempt in range(max_retries):
                    try:
                        response = await http_client.get(paginated_path, headers=headers)
                        response.raise_for_status() # Raise exception for 4xx/5xx responses
                        break # Success, exit retry loop
                    except httpx.HTTPStatusError as e:
                        # Retry on server-side errors (5xx)
                        if e.response.status_code >= 500:
                            logger.warning(
                                f"ESI request failed for {paginated_path} with status {e.response.status_code}. "
                                f"Attempt {attempt + 1} of {max_retries}. Retrying..."
                            )
                            if attempt < max_retries - 1:
                                await asyncio.sleep(2 * (attempt + 1)) # Exponential backoff
                            else:
                                logger.error(f"ESI request failed after {max_retries} retries for {paginated_path}.")
                                raise ESIRequestFailedError(status_code=e.response.status_code, message=str(e))
                        else:
                            # Don't retry on client-side errors (4xx), raise immediately
                            raise ESIRequestFailedError(status_code=e.response.status_code, message=str(e))
                    except (httpx.ReadTimeout, httpx.ConnectError) as e:
                        logger.warning(
                            f"ESI request failed for {paginated_path} with a network error ({type(e).__name__}). "
                            f"Attempt {attempt + 1} of {max_retries}. Retrying..."
                        )
                        if attempt < max_retries - 1:
                            await asyncio.sleep(2 * (attempt + 1))
                        else:
                            logger.error(f"ESI request failed after {max_retries} retries for {paginated_path}.")
                            raise ESIRequestFailedError(message=str(e))
                    except Exception as e:
                        logger.exception(f"An unexpected error occurred fetching ESI data for {paginated_path}: {e}")
                        raise ESIRequestFailedError(message=str(e))

                # Process response
                if response.status_code == 200:
                    new_etag = response.headers.get("ETag")
                    if new_etag:
                        expires_header = response.headers.get("Expires")
                        cache_duration_seconds = 600  # Default cache duration
                        if expires_header:
                            try:
                                expire_time = parsedate_to_datetime(expires_header)
                                if expire_time.tzinfo is None:
                                    expire_time = expire_time.replace(tzinfo=timezone.utc) # Assume UTC if no tzinfo
                                # Calculate remaining seconds until expiry
                                # Ensure current_time is also timezone-aware (UTC)
                                current_time = datetime.now(timezone.utc)
                                if expire_time > current_time:
                                    cache_duration_seconds = int((expire_time - current_time).total_seconds())
                                else:
                                    # Header is in the past, use a very short cache or default
                                    cache_duration_seconds = 10 # Cache for a very short period
                            except Exception as e:
                                logger.warning(f"Could not parse 'Expires' header '{expires_header}': {e}. Using default cache duration.")
                        
                        await self.redis_client.set(etag_key, new_etag, ex=cache_duration_seconds)
                        # Also cache the data itself for 304 responses
                        await self.redis_client.set(data_key, response.content, ex=cache_duration_seconds)
                    page_data = response.json()

                elif response.status_code == 304:
                    # Not Modified, data is fresh
                    logger.debug(f"ETag cache hit for {paginated_path}. Data is fresh.")
                    # Not Modified, try to serve from cache
                    cached_data = await self.redis_client.get(data_key)
                    if cached_data:
                        logger.debug(f"ETag cache hit for {paginated_path}. Serving data from cache.")
                        page_data = json.loads(cached_data)
                    else:
                        # This case is rare: ETag matches but data is gone from cache.
                        # We must re-fetch without the ETag to get the data.
                        logger.warning(f"ETag match but no cached data for {data_key}, re-fetching.")
                        response = await http_client.get(paginated_path) # Re-fetch without headers
                        response.raise_for_status()
                        page_data = response.json()

                elif response.status_code == 204:
                    # No Content, typically on the last page of items
                    logger.debug(f"Received 204 No Content for {paginated_path}. Assuming end of pages.")
                    break

                # Pagination Logic
                if page_data:
                    full_data.extend(page_data)

                if not all_pages:
                    break

                # Check for last page
                pages_header = response.headers.get("X-Pages")
                if pages_header:
                    total_pages = int(pages_header)
                    if page >= total_pages:
                        break
                elif not page_data:
                    # If X-Pages header is missing and we get no data, assume we are done.
                    break

                # Temporary debug limit
                if is_public_contracts_path and page >= MAX_PAGES_FOR_DEBUG:
                    logger.info(f"DEV MODE: Stopping public contract fetch at page {page} as per debug limit.")
                    break
                page += 1

            return full_data



    async def get_public_contracts(self, region_id: int) -> list[dict[str, Any]]:
        """Fetches all public contracts for a specific region."""
        path = f"/v1/contracts/public/{region_id}/"
        return await self.get_esi_data_with_etag_caching(path)

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
            logger.error(f"ESI request failed for {path}: {e}")
            raise ESIRequestFailedError(status_code=e.response.status_code, message=str(e))
        except Exception as e:
            logger.error(f"An unexpected error occurred fetching ESI data for {path}: {e}")
            raise ESIRequestFailedError(message=str(e))

    async def get_market_groups(self) -> list[int]:
        """Fetches the list of root market group IDs."""
        path = "/v1/markets/groups/"
        return await self.get_esi_single_page_with_etag(path)
