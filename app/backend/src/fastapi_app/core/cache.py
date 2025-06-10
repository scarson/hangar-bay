"""
Manages the application's asynchronous Redis cache connection and lifecycle.

Key points about this module:
- Uses redis.asyncio for the asynchronous Redis client, suitable for FastAPI.
- The CacheManager class encapsulates the Redis client and its lifecycle methods (initialize, close, get_client).
- `initialize` method connects to Redis (using CACHE_URL from settings) and pings the server.
  (Note: CACHE_URL was confirmed to exist in config.py, so no addition was needed there).
- `close` method handles closing the Redis connection pool.
- `get_client` provides access to the initialized Redis client instance.
- `init_cache` and `close_cache` are FastAPI event handlers designed for application startup and shutdown.
- `init_cache` stores the initialized Redis client on `app.state.redis` for easy access via dependencies.
- Includes basic print statements for connection status; these should be replaced with proper logging in a production environment.
"""
import logging # Added for proper logging
from typing import Optional

from redis.asyncio import Redis, from_url
from fastapi import FastAPI

from fastapi_app.config import get_settings

# Get a logger instance for this module
logger = logging.getLogger(__name__)

class CacheManager:
    """
    Manages the Redis cache connection using an asynchronous client (redis.asyncio).
    The client instance is initialized during FastAPI app startup via the `initialize` method
    and made available through `get_client`. Its lifecycle is tied to the FastAPI app.
    """

    def __init__(self):
        self.redis_client: Optional[Redis] = None

    async def initialize(self, cache_url: str):
        """
        Initializes the asynchronous Redis client (redis.asyncio) and its connection pool.
        Uses the `cache_url` (from Pydantic settings, e.g., settings.CACHE_URL) to connect.
        Performs a PING to test the connection upon initialization.
        This method should be called on FastAPI application startup.
        """
        if self.redis_client is None:
            self.redis_client = from_url(cache_url, encoding="utf-8", decode_responses=True)
            # Test connection
            try:
                await self.redis_client.ping()
                logger.info("Successfully connected to Redis.")
            except Exception as e:
                logger.error(f"Error connecting to Redis: {e}", exc_info=True)
                self.redis_client = None # Ensure client is None if connection failed

    async def close(self):
        """Closes the Redis connection pool if it has been initialized."""
        if self.redis_client:
            await self.redis_client.close()
            self.redis_client = None
            logger.info("Redis connection closed.")

    def get_client(self) -> Optional[Redis]:
        """
        Returns the initialized asynchronous Redis client (redis.asyncio.Redis) instance.
        Returns None if the client has not been initialized or connection failed.
        """
        return self.redis_client


# Global instance of CacheManager
# This instance will be initialized during app startup and its client
# stored on app.state for easy access via dependency.
cache_manager = CacheManager()

async def init_cache(app: FastAPI):
    """FastAPI startup event handler to initialize the global cache_manager and store client on app.state."""
    current_settings = get_settings()
    await cache_manager.initialize(current_settings.CACHE_URL)
    app.state.redis = cache_manager.get_client()
    if app.state.redis is None:
        # Handle failed connection scenario, e.g., log critical error
        # For now, using logger, but in production, this might halt startup or trigger alerts
        logger.critical("Redis client could not be initialized. Cache will not be available.")


async def close_cache(app: FastAPI):
    """FastAPI shutdown event handler to close the global cache_manager's connection."""
    await cache_manager.close()
