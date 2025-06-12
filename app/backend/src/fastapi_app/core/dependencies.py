from typing import Optional

from fastapi import Request
from redis.asyncio import Redis
from fastapi import Depends

from .esi_client_class import ESIClient
from .config import settings, Settings # Import global settings and Settings model for type hint

async def get_cache(request: Request) -> Optional[Redis]:
    """
    FastAPI dependency to get the initialized Redis client instance
    from the application state.
    Returns None if the client is not available (e.g., connection failed).
    """
    return getattr(request.app.state, "redis", None)


async def get_esi_client(
    request: Request,
    rd: Redis = Depends(get_cache)
) -> ESIClient:
    """
    FastAPI dependency to get an instance of the ESIClient.
    """
    if not hasattr(request.app.state, 'http_client') or not request.app.state.http_client:
        raise RuntimeError("HTTP client not initialized. Ensure it's set up in the application startup event.")
    
    if not rd:
        raise RuntimeError("Redis client not available. Ensure it's set up in the application startup event.")

    return ESIClient(http_client=request.app.state.http_client, redis_client=rd)


def get_settings() -> Settings:
    """
    FastAPI dependency to get the globally configured Settings object.
    """
    # The 'settings' object is imported from .config and is initialized once.
    # Pydantic ensures it's validated upon its first creation.
    # This function simply returns that single, global instance.
    # DEBUG: Print statements to verify which settings object is being returned by the dependency.
    print(f"DEPENDENCY_GET_SETTINGS_ID: id(settings)={id(settings)}, AGG_REGION_IDS_TYPE={type(settings.AGGREGATION_REGION_IDS)}, VALUE={settings.AGGREGATION_REGION_IDS!r}", flush=True)
    return settings
