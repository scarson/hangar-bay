from typing import Optional

import httpx
from fastapi import Depends, HTTPException, Request, status
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from .config import Settings, settings
from .esi_client_class import ESIClient
from ..db import get_db
from ..services.esi_type_service import ESITypeService


async def get_cache(request: Request) -> Redis:
    """
    FastAPI dependency to get the initialized Redis client from the app state.
    Raises HTTPException if the client is not available.
    """
    redis_client = getattr(request.app.state, "redis", None)
    if redis_client is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Redis client is not available.",
        )
    return redis_client


async def get_http_client(request: Request) -> httpx.AsyncClient:
    """
    FastAPI dependency to get the shared httpx.AsyncClient from the app state.
    Raises HTTPException if the client is not available.
    """
    http_client = getattr(request.app.state, "http_client", None)
    if http_client is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="HTTP client is not available.",
        )
    return http_client


def get_settings() -> Settings:
    """
    FastAPI dependency to get the globally configured Settings object.
    """
    return settings


async def get_esi_client(
    settings: Settings = Depends(get_settings),
    http_client: httpx.AsyncClient = Depends(get_http_client),
    redis_client: Redis = Depends(get_cache),
) -> ESIClient:
    """
    FastAPI dependency to get an instance of the ESIClient, configured with
    shared, application-level HTTP and Redis clients.
    """
    return ESIClient(
        settings=settings, http_client=http_client, redis_client=redis_client
    )


async def get_esi_type_service(
    db: AsyncSession = Depends(get_db),
    esi_client: ESIClient = Depends(get_esi_client),
) -> ESITypeService:
    """
    FastAPI dependency to get an instance of the ESITypeService.
    
    This service provides comprehensive ESI type information with caching,
    used for detailed contract views including ship attributes and images.
    """
    return ESITypeService(db_session=db, esi_client=esi_client)
