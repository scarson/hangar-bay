from typing import Optional

from fastapi import Request
import redis.asyncio as aioredis

async def get_cache(request: Request) -> Optional[aioredis.Redis]:
    """
    FastAPI dependency to get the initialized Redis client instance
    from the application state.
    Returns None if the client is not available (e.g., connection failed).
    """
    return getattr(request.app.state, "redis", None)
