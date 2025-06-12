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


async def get_esi_client(
    # request: Request, # No longer needed as http_client is not from app.state
    s: Settings = Depends(get_settings) # ESIClient now only needs settings
) -> ESIClient:
    """
    FastAPI dependency to get an instance of the ESIClient.
    The ESIClient now manages its own HTTP and Redis clients using settings.
    """
    # ESIClient constructor now only takes settings.
    # HTTP client and Redis client are created on-demand within ESIClient methods.
    return ESIClient(settings=s)
