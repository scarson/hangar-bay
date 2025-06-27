import logging
import pydantic

# Print Pydantic version right at the start for immediate visibility
print(f"PYDANTIC_VERSION_CHECK_PRINT: {pydantic.__version__}", flush=True)
logger = logging.getLogger(__name__)


from typing import Optional

from fastapi import FastAPI, Depends, APIRouter
from redis.asyncio import Redis # For type hinting Redis client
from .core.config import settings
from .core.cache import init_cache, close_cache
from .core.http_client import init_http_client, close_http_client
from .core.scheduler import add_aggregation_job, create_scheduler
from .core.dependencies import get_cache
from .db import AsyncSessionLocal # For manual session creation
from .core.esi_client_class import ESIClient # For manual ESI client creation
from .services.background_aggregation import ContractAggregationService # For manual service creation
from .api import contracts as contracts_router
from .db import async_engine, Base
from .models import contracts # This import is crucial for Base.metadata to find the tables.

# Configure basic logging to ensure messages are surfaced
logging.basicConfig(level=logging.INFO, format='%(levelname)s:     %(name)s - %(message)s')



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


async def create_db_tables():
    """
    Drops and recreates database tables to ensure the schema is up-to-date.
    NOTE: This is a destructive operation suitable for development.
    """
    logger.info("Dropping and recreating database tables...")
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables successfully recreated.")


# Application lifecycle event handlers
@app.on_event("startup")
async def startup_event():
    """Initializes all necessary services on application startup."""
    await create_db_tables()
    init_http_client(app)
    await init_cache(app)



    # Initialize and start the scheduler
    scheduler = create_scheduler(app, settings)

    # Manually create dependencies for the ContractAggregationService for the scheduler
    # This ensures the scheduler uses the main application's settings instance and a session factory

    # Ensure http_client and redis are available from app.state
    if not hasattr(app.state, 'http_client') or not app.state.http_client:
        raise RuntimeError("HTTP client not initialized in app.state before scheduler setup.")
    if not hasattr(app.state, 'redis') or not app.state.redis:
        raise RuntimeError("Redis client not initialized in app.state before scheduler setup.")

    # For the scheduler, we create a picklable ESIClient that will manage
    # its own clients on-demand within the job's execution context.
    esi_client = ESIClient(settings=settings)
    
    # Instantiate the service with the session factory (AsyncSessionLocal)
    aggregation_service = ContractAggregationService(
        # cache=app.state.redis, # ContractAggregationService no longer takes cache client directly
        esi_client=esi_client,
        settings=settings, # Pass the globally imported settings from main.py
    )
    add_aggregation_job(scheduler, aggregation_service, settings)
    
    scheduler.start()
    logging.info("Application startup complete with all services initialized.")


@app.on_event("shutdown")
async def shutdown_event():
    """Gracefully shuts down all services on application shutdown."""
    # Shut down the scheduler first to stop new jobs
    if hasattr(app.state, "scheduler") and app.state.scheduler.running:
        app.state.scheduler.shutdown()
        logging.info("Scheduler has been shut down.")

    await close_http_client(app)
    await close_cache(app)
    logging.info("Application shutdown complete.")


# CASCADE-PROD-CHECK: Remove or disable this endpoint for production.
@app.get("/cache-test", tags=["Development/Test"])
async def cache_test(rd: Optional[Redis] = Depends(get_cache)):
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


# Include API routers
# The /api/v1 prefix is handled by the frontend proxy configuration.
# The router is included here without a prefix to match the incoming requests.
app.include_router(contracts_router.router, prefix="/api/v1")

# Further application setup, routers, middleware, etc., will go here
