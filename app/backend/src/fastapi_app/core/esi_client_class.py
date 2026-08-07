import asyncio
import json
import logging
import math
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

import httpx
import redis.asyncio as aioredis

from .exceptions import ESIRequestFailedError
from .config import Settings

logger = logging.getLogger(__name__)

# ESI's error-limit (420) and per-group token-bucket (429) responses mean "come back
# later", not "this request failed" — see _get_with_transient_retry.
RATE_LIMIT_STATUSES = frozenset({420, 429})

# ESI's error-limit window is 60s; nothing legitimate asks a caller to wait longer.
RATE_LIMIT_SLEEP_CEILING = 60.0

# TTL for a page whose response describes no freshness lifetime we can read.
DEFAULT_CACHE_TTL_SECONDS = 600


def _parse_cache_control(header: Optional[str]) -> Dict[str, Optional[str]]:
    """Split a Cache-Control header into lower-cased directives.

    A directive with no `=value` maps to None, which is how `no-store` and a
    valueless `max-age` are told apart from `max-age=0`.
    """
    directives: Dict[str, Optional[str]] = {}
    if not header:
        return directives
    for part in header.split(","):
        name, sep, value = part.strip().partition("=")
        if name:
            directives[name.strip().lower()] = value.strip() if sep else None
    return directives


def _freshness_from_cache_control(
    directives: Dict[str, Optional[str]], age_header: Optional[str]
) -> Optional[int]:
    """Remaining freshness in seconds from Cache-Control, or None if it says nothing.

    None means "this header carries no lifetime" — an absent or invalid `max-age`
    (unparseable, valueless, or negative, none of which are valid delta-seconds) —
    and the caller falls back to Expires. A returned 0 is a real answer meaning
    "not fresh", not a missing one.

    `no-store` forbids storage outright. `no-cache` does not: it requires
    revalidation before reuse, and every read here is already a conditional
    request whose cached body is served only on a 304 — the origin confirming it
    is still current — so a stored entry satisfies it.

    Age is subtracted because max-age is the response's total lifetime, not its
    remaining one: a shared upstream cache can hand us a response most of the way
    through it (RFC 9111 §4.2). An unparseable Age is ignored rather than assumed.
    """
    if "no-store" in directives:
        return 0
    raw_max_age = directives.get("max-age")
    if raw_max_age is None:
        return None
    try:
        max_age = int(raw_max_age)
    except ValueError:
        return None
    if max_age < 0:
        return None
    try:
        age = int(age_header) if age_header is not None else 0
    except ValueError:
        age = 0
    return max(max_age - max(age, 0), 0)


def _rate_limit_wait(retry_after: Optional[str], attempt: int, backoff_factor: float) -> float:
    """Seconds to wait before retrying a 420/429.

    Retry-After drives the wait when it parses to a sane number; otherwise this falls
    back to the same exponential backoff schedule as a 5xx. The result is always
    finite, positive, and clamped to RATE_LIMIT_SLEEP_CEILING — an absent, garbled,
    negative, or non-finite header must not translate into an unbounded sleep
    (float("inf") parses, and asyncio.sleep honors it: an unclamped value can wedge
    the singleton ingestion job until restart). Note 420 (error limit) does not carry
    Retry-After at all — it always takes the fallback schedule; reading
    X-Esi-Error-Limit-Reset is deferred to the rate-limit governor phase.
    """
    try:
        wait = float(retry_after)
    except (TypeError, ValueError):
        wait = backoff_factor * (2 ** attempt)
    if not math.isfinite(wait) or wait <= 0:
        wait = backoff_factor * (2 ** attempt)
    return min(wait, RATE_LIMIT_SLEEP_CEILING)


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
        rate_limit_wait_budget: float = RATE_LIMIT_SLEEP_CEILING,
    ):
        self.settings = settings
        self._http_client = http_client
        self._redis_client = redis_client
        self._managed_http_client: Optional[httpx.AsyncClient] = None
        self._managed_redis_client: Optional[aioredis.Redis] = None
        # A computed rate-limit wait beyond this budget is not slept at all — the
        # caller fails fast instead. This bounds each individual wait, not the request
        # total: under a 1.0s budget a 420's fallback schedule sleeps 0.5s (attempt 1)
        # and 1.0s (attempt 2, exactly at the strict > threshold), so a user request
        # can still spend ~1.5s per ESI call retrying before it gives up.
        # Background ingestion (its own managed clients, no override) keeps the full 60s
        # patience; the request-scoped dependency overrides this down to fail user
        # requests fast (core/dependencies.py).
        self.rate_limit_wait_budget = rate_limit_wait_budget

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

    @staticmethod
    def default_headers(settings) -> Dict[str, str]:
        """The headers every ESI request carries.

        X-Compatibility-Date is not optional in practice. A request without it is served
        the OLDEST published date rather than the newest, so omitting it pins the whole
        application to a contract chosen by CCP rather than by us — one CCP can raise with
        notice, changing response shapes with no commit on our side (pitfall ESI-4).
        """
        return {
            "User-Agent": settings.ESI_USER_AGENT,
            "X-Compatibility-Date": settings.ESI_COMPATIBILITY_DATE,
        }

    async def __aenter__(self):
        """Initializes clients if they were not provided during instantiation."""
        if not self._http_client:
            self._managed_http_client = httpx.AsyncClient(
                base_url=self.settings.ESI_BASE_URL,
                headers=self.default_headers(self.settings),
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

        while True:
            paginated_path = f"{path}?page={page}"
            etag_key = f"etag:{paginated_path}"
            data_key = f"data:{paginated_path}"

            cached_etag = await self.redis_client.get(etag_key)
            if isinstance(cached_etag, bytes):
                cached_etag = cached_etag.decode()
            headers = {"If-None-Match": cached_etag or ""}

            response = await self._get_with_transient_retry(paginated_path, headers=headers)

            if response.status_code == 404 and ignore_404:
                logger.debug(f"Received 404 for {paginated_path}, treating as end of pages.")
                break
            if response.status_code == 204:
                logger.debug(f"Received 204 for {paginated_path}, treating as end of pages.")
                break

            if response.status_code == 304:
                logger.debug(f"ETag cache hit for {paginated_path}. Serving data from cache.")
                page_data = await self._read_etag_cached_page(data_key)
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
                    await self._store_page_cache(etag_key, data_key, response)

            if self._last_page_reached(response, page, page_data, all_pages):
                break

            page += 1

        return full_data

    async def _read_etag_cached_page(self, data_key: str) -> list:
        """Read a page body previously stored alongside its ETag.

        An absent entry yields an empty page: a 304 whose cached body was evicted
        does not fall back to a live fetch.
        """
        cached_data = await self.redis_client.get(data_key)
        if not cached_data:
            return []
        return json.loads(cached_data)

    def _cache_ttl_seconds(self, response: httpx.Response) -> int:
        """Seconds to cache a page for, read from Cache-Control, else Expires.

        Cache-Control wins where it states a lifetime, per RFC 9111 and ESI's own
        guidance: routes converting to event-driven invalidation keep emitting
        Expires for back-compat only, where it no longer describes when the cache
        turns over (CCP dev blog, 2026-01-27 — see pitfall ESI-2). Routes that have
        not converted send a bare `Cache-Control: public` with no lifetime at all,
        so Expires stays in charge there and their TTLs are unchanged.

        Zero means "do not store". An absent, already-elapsed, or unparseable
        Expires with nothing better available yields DEFAULT_CACHE_TTL_SECONDS.

        An over-long TTL costs freshness nothing: entries are never served blind,
        only revalidated by a conditional request, so a stale one yields a 200 with
        the new body. Too short merely forfeits a 304.
        """
        directives = _parse_cache_control(response.headers.get("Cache-Control"))
        freshness = _freshness_from_cache_control(directives, response.headers.get("Age"))
        if freshness is not None:
            return freshness

        expires_header = response.headers.get("Expires")
        cache_duration_seconds = DEFAULT_CACHE_TTL_SECONDS
        if expires_header:
            try:
                expire_time = parsedate_to_datetime(expires_header).replace(tzinfo=timezone.utc)
                current_time = datetime.now(timezone.utc)
                if expire_time > current_time:
                    cache_duration_seconds = int((expire_time - current_time).total_seconds())
            except Exception:
                pass
        return cache_duration_seconds

    async def _store_page_cache(
        self, etag_key: str, data_key: str, response: httpx.Response
    ) -> None:
        """Store a page's ETag and raw body under a shared TTL.

        A response carrying no ETag is not cached at all — without a validator the
        stored body could never be revalidated by a later conditional request.
        Neither is one whose headers give it no remaining freshness (`no-store`, or
        a max-age already spent): a zero TTL is Valkey's "no expiry" sentinel, so
        writing it would strand the entry forever rather than skip it.
        """
        new_etag = response.headers.get("ETag")
        if not new_etag:
            return
        cache_duration_seconds = self._cache_ttl_seconds(response)
        if cache_duration_seconds <= 0:
            return
        await self.redis_client.set(etag_key, new_etag, ex=cache_duration_seconds)
        await self.redis_client.set(data_key, response.content, ex=cache_duration_seconds)

    def _last_page_reached(
        self, response: httpx.Response, page: int, page_data: list, all_pages: bool
    ) -> bool:
        """Whether the pagination walk ends after this page.

        Order is load-bearing: single-page mode and an empty page each terminate
        before X-Pages is read, so an unparseable header on those responses never
        reaches int() and stays inert.
        """
        if not all_pages:
            return True
        if not page_data:
            return True
        total_pages_header = response.headers.get("X-Pages")
        return bool(total_pages_header and page >= int(total_pages_header))

    async def get_public_contracts(self, region_id: int) -> list[dict[str, Any]]:
        """Fetches all public contracts for a specific region, handling pagination."""
        path = f"/v1/contracts/public/{region_id}/"
        return await self.get_esi_data_with_etag_caching(path, all_pages=True, ignore_404=True)

    async def get_contract_items(self, contract_id: int) -> list[dict[str, Any]]:
        """Fetches all items for a specific public contract.

        all_pages=True is load-bearing: contracts can exceed one 1,000-item page, and
        the default (False) stops after page 1, truncating silently. Once enrichment
        stops revisiting completed contracts, a truncated result would be permanent.
        """
        path = f"/v1/contracts/public/items/{contract_id}/"
        return await self.get_esi_data_with_etag_caching(path, all_pages=True)

    async def _wait_out_rate_limit_or_give_up(
        self, path: str, response: httpx.Response, attempt: int, max_retries: int, backoff_factor: float
    ) -> tuple[httpx.HTTPStatusError, bool]:
        """Log a 420/429, then either sleep out its (clamped) wait or give up on it.

        Returns (exception_to_record, gave_up). gave_up is True when the computed wait
        exceeds this client's rate_limit_wait_budget — the caller must stop retrying now,
        failing fast rather than holding the connection through ESI's cool-down, instead
        of sleeping. Otherwise this sleeps (skipped on the final attempt) and the caller
        retries as usual.
        """
        exc = httpx.HTTPStatusError(
            f"Rate limited '{response.status_code}'", request=response.request, response=response,
        )
        retry_after = response.headers.get("Retry-After")
        logger.warning(
            f"ESI rate limited {path} with {response.status_code}; "
            f"Retry-After={retry_after!r}. Attempt {attempt + 1}/{max_retries}."
        )
        wait = _rate_limit_wait(retry_after, attempt, backoff_factor)
        if wait > self.rate_limit_wait_budget:
            return exc, True
        if attempt < max_retries - 1:
            await asyncio.sleep(wait)
        return exc, False

    async def _get_with_transient_retry(
        self, path: str, headers: Optional[Dict[str, str]] = None
    ) -> httpx.Response:
        """GET with bounded retry on transient failures (5xx + network errors).

        4xx responses return normally — callers decide what non-5xx statuses mean.
        Exhausted retries surface as ESIRequestFailedError (status carried when the
        failure was HTTP, absent for pure network errors).
        """
        max_retries = 3
        backoff_factor = 0.5  # seconds
        response = None
        last_exception = None
        for attempt in range(max_retries):
            try:
                response = await self.http_client.get(path, headers=headers)
                # 420 (ESI error limit) and 429 (token bucket) mean "come back later", not
                # "this request failed". Treating them as ordinary 4xx burns error budget and
                # records the run as successful over missing data.
                if response.status_code in RATE_LIMIT_STATUSES:
                    last_exception, gave_up = await self._wait_out_rate_limit_or_give_up(
                        path, response, attempt, max_retries, backoff_factor
                    )
                    if gave_up:
                        # last_exception is already set; exhaustion handling below raises the
                        # identical ESIRequestFailedError a spent retry budget would.
                        break
                    continue
                if response.status_code < 500:
                    last_exception = None
                    break
                last_exception = httpx.HTTPStatusError(
                    f"Server error '{response.status_code}'", request=response.request, response=response
                )
                logger.warning(
                    f"ESI request to {path} failed with status {response.status_code}. "
                    f"Attempt {attempt + 1}/{max_retries}."
                )
            except (httpx.ReadTimeout, httpx.ConnectError) as e:
                last_exception = e
                logger.warning(f"Network error for {path} on attempt {attempt + 1}/{max_retries}: {e}")
            if attempt < max_retries - 1:
                await asyncio.sleep(backoff_factor * (2 ** attempt))

        if last_exception is not None:
            if isinstance(last_exception, httpx.HTTPStatusError):
                raise ESIRequestFailedError(
                    status_code=last_exception.response.status_code, message=str(last_exception)
                )
            raise ESIRequestFailedError(message=f"Network error for {path}: {last_exception}")
        return response

    async def _get_esi_object(self, path: str, cache_seconds: int = 86_400) -> dict[str, Any]:
        """GET a single-OBJECT ESI endpoint with a plain Valkey TTL cache.

        The paginated ETag helper is list-shaped: `full_data.extend(page)`
        flattens a dict payload into its KEYS, silently destroying the data
        (found live when type resolution returned key lists). Object endpoints
        must come through here instead. These are static-data endpoints, so a
        long dumb TTL beats conditional requests.
        """
        cache_key = f"esi-object:{path}"
        try:
            cached = await self.redis_client.get(cache_key)
            if cached:
                return json.loads(cached)
        except Exception as e:
            logger.warning(f"Object cache read failed for {path}: {e}")

        # Transient failures (5xx + network) are retried so a blip on
        # /universe/types|groups doesn't silently un-enrich a run's ship contracts.
        # 4xx (e.g. 404) still falls straight through to raise_for_status below.
        response = await self._get_with_transient_retry(path)

        response.raise_for_status()
        # A malformed 2xx body (e.g. an upstream HTML error page) must not escape as a raw
        # ValueError/500 — decoding failures normalize to ESIRequestFailedError (status 0),
        # which the caller maps to a retryable 502 alongside network/5xx outages (design §4.5).
        try:
            data = response.json()
        except ValueError:
            raise ESIRequestFailedError(message=f"Non-JSON body from {path}")
        if not isinstance(data, dict):
            raise ESIRequestFailedError(
                message=f"Expected JSON object from {path}, got {type(data).__name__}"
            )
        try:
            await self.redis_client.set(cache_key, response.content, ex=cache_seconds)
        except Exception as e:
            logger.warning(f"Object cache write failed for {path}: {e}")
        return data

    async def get_universe_type(self, type_id: int) -> dict[str, Any]:
        """Fetches static type info (name, group_id, market_group_id)."""
        return await self._get_esi_object(f"/v3/universe/types/{type_id}/")

    async def get_universe_group(self, group_id: int) -> dict[str, Any]:
        """Fetches static group info (name, category_id)."""
        return await self._get_esi_object(f"/v1/universe/groups/{group_id}/")

    async def get_universe_category(self, category_id: int) -> dict[str, Any]:
        """Fetches static dogma category info (name). Immutable set; long TTL."""
        return await self._get_esi_object(f"/v1/universe/categories/{category_id}/")

    async def get_universe_station(self, station_id: int) -> dict[str, Any]:
        """Fetches static NPC-station info (name, `system_id`, type_id).

        Public — no token, no scope. The player-structure counterpart
        (/universe/structures/) is not: it requires
        esi-universe.read_structures.v1 and 403s for structures the token's
        character cannot dock at, so it has no tokenless equivalent here. That
        route also names the field `solar_system_id`, not `system_id`.
        """
        return await self._get_esi_object(f"/v2/universe/stations/{station_id}/")

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

    async def resolve_names(self, names: list[str]) -> dict[str, Any]:
        """Resolve exact EVE names to ids via POST /v1/universe/ids/ (version-pinned per ESI-1).

        Returns the parsed response body — a dict of category → [{id, name}, ...] (e.g.
        `inventory_types`); an unmatched name yields a 200 with that category absent. Unlike
        the enrichment fetches this is not cached: watchlist adds are rare and the caller wants
        an authoritative resolution. Non-2xx statuses and network errors surface as
        ESIRequestFailedError so the caller can map 4xx→400 / 5xx→502 (design §4.5).
        """
        try:
            response = await self.http_client.post("/v1/universe/ids/", json=names)
        except httpx.RequestError as e:
            # RequestError covers ReadTimeout / ConnectError / ConnectTimeout / etc. — any transport
            # failure surfaces as ESIRequestFailedError so the caller maps it to 502, never a raw 500.
            raise ESIRequestFailedError(message=f"Network error resolving names: {e}")
        if not (200 <= response.status_code < 300):
            raise ESIRequestFailedError(
                status_code=response.status_code,
                message=f"universe/ids resolution failed: HTTP {response.status_code}",
            )
        try:
            data = response.json()
        except ValueError:
            raise ESIRequestFailedError(message="Non-JSON body from /v1/universe/ids/")
        if not isinstance(data, dict):
            raise ESIRequestFailedError(
                message=f"Expected JSON object from /v1/universe/ids/, got {type(data).__name__}"
            )
        return data
