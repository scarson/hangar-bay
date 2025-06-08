import logging # Added for basic logging config
from typing import Optional

from fastapi import FastAPI, Depends
import redis.asyncio as aioredis # For type hinting Redis client
from .config import get_settings
from .core.cache import init_cache, close_cache
from .core.dependencies import get_cache

# Configure basic logging to ensure messages are surfaced
logging.basicConfig(level=logging.INFO, format='%(levelname)s:     %(name)s - %(message)s')

settings = get_settings()

app = FastAPI(
    title="Hangar Bay API",
    description="API for the Hangar Bay application, providing access to EVE Online public contract data and related services.",
    version="0.1.0",
    # Additional OpenAPI metadata can be added here
    # See: https://fastapi.tiangolo.com/tutorial/metadata/
)


@app.get("/")
async def read_root():
    return {
        "message": f"Welcome to Hangar Bay API - {settings.ENVIRONMENT} environment"
    }


@app.get("/health")
async def health_check():
    return {"status": "ok"}


# Cache lifecycle event handlers
@app.on_event("startup")
async def startup_event():
    await init_cache(app)

@app.on_event("shutdown")
async def shutdown_event():
    await close_cache()


# CASCADE-PROD-CHECK: Remove or disable this endpoint for production.
@app.get("/cache-test", tags=["Development/Test"])
async def cache_test(rd: Optional[aioredis.Redis] = Depends(get_cache)):
    """Temporary endpoint to test cache connectivity and basic operations."""
    if not rd:
        return {"status": "error", "message": "Redis client not available"}
    try:
        test_key = "temp_cache_test_key"
        test_value = "Hello Hangar Bay Cache! - Temporary Test"
        await rd.set(test_key, test_value, ex=60)  # Set with a 60-second expiry
        retrieved_value = await rd.get(test_key)
        if retrieved_value == test_value:
            return {"status": "ok", "key_set": test_key, "value_retrieved": retrieved_value}
        else:
            return {"status": "error", "message": "Value mismatch after set/get", "expected": test_value, "got": retrieved_value}
    except Exception as e:
        # Log the exception for more details during development
        logging.error(f"Cache test endpoint error: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}


# Further application setup, routers, middleware, etc., will go here
