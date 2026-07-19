import logging
import math
import structlog
from fastapi import Request, Response
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from starlette.middleware.base import BaseHTTPMiddleware
from prometheus_fastapi_instrumentator import Instrumentator

from typing import Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends, APIRouter
from redis.asyncio import Redis  # For type hinting Redis client
from .core.config import settings
from .core.cache import init_cache, close_cache
from .core.http_client import init_http_client, close_http_client
from .core.scheduler import add_aggregation_job, add_watchlist_matcher_job, create_scheduler
from .core.dependencies import get_cache
from .core.logging import setup_logging, RequestIDMiddleware
from .core.token_cipher import is_token_cipher_configured
from .db import AsyncSessionLocal, async_engine, Base
from .core.esi_client_class import ESIClient  # For manual ESI client creation
from .services.background_aggregation import ContractAggregationService  # For manual service creation
from .services.watchlist_matcher import WatchlistMatcherService
from .api import contracts as contracts_router
from .api import auth as auth_router
from .api import ops as ops_router
from .api import saved_searches as saved_searches_router
from .api import watchlist as watchlist_router
from .api import notifications as notifications_router
from .models import contracts  # This import is crucial for Base.metadata to find the tables.
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

# Configure basic logging for early startup messages
# This will be enhanced with structured logging in the lifespan function
logging.basicConfig(level=logging.INFO, format='%(levelname)s:     %(name)s - %(message)s')


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manages application startup and shutdown events."""
    # Startup logic
    # Setup structured logging first
    setup_logging(settings)
    warn_if_sso_unconfigured()

    await create_db_tables()
    init_http_client(app)
    await init_cache(app)

    # Initialize and start the scheduler
    scheduler = create_scheduler(app, settings)
    esi_client = ESIClient(settings=settings)
    aggregation_service = ContractAggregationService(
        esi_client=esi_client,
        settings=settings,
    )
    add_aggregation_job(scheduler, aggregation_service, settings)
    matcher_service = WatchlistMatcherService(settings=settings)
    add_watchlist_matcher_job(scheduler, matcher_service, settings)
    scheduler.start()
    logging.info("Application startup complete with all services initialized.")

    yield  # The application runs here

    # Shutdown logic
    if hasattr(app.state, "scheduler") and app.state.scheduler.running:
        app.state.scheduler.shutdown()
        logging.info("Scheduler has been shut down.")
    await close_http_client(app)
    await close_cache(app)
    logging.info("Application shutdown complete.")


app = FastAPI(
    title="Hangar Bay API",
    description="API for the Hangar Bay application, providing access to EVE Online public contract data and related services.",
    version="0.1.0",
    lifespan=lifespan,
    # Additional OpenAPI metadata can be added here
    # See: https://fastapi.tiangolo.com/tutorial/metadata/
)

# Add global exception handler FIRST, before middleware


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    """
    Global exception handler to catch any unhandled exceptions and return a
    standardized 500 error response.
    """
    # Use structlog to log the exception with context
    logger = structlog.get_logger("uvicorn.error")
    logger.error(
        "unhandled_exception",
        exc_info=exc,
        error_message=str(exc),
    )
    return JSONResponse(
        status_code=500,
        content={"detail": "An unexpected server error occurred."},
    )


def _json_safe(value):
    """Coerce non-finite floats (inf/-inf/nan) to their string form, recursing through dict/list
    containers, so a payload is renderable by Starlette's allow_nan=False JSON encoder."""
    if isinstance(value, float) and not math.isfinite(value):
        return str(value)
    if isinstance(value, dict):
        return {k: _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    return value


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Return the standard 422 body even when a rejected value is a non-finite float.

    Pydantic echoes the offending input in every error entry. A client sending the JSON number
    1e309 (which parses to inf) or a NaN token would otherwise crash Starlette's allow_nan=False
    encoder while it renders the 422, surfacing a 500. Stringifying non-finite inputs keeps the
    {"detail": [...]} shape valid JSON; behaviour is identical to FastAPI's default handler for
    every finite input.
    """
    return JSONResponse(
        status_code=422, content={"detail": _json_safe(jsonable_encoder(exc.errors()))}
    )

# Add RequestID middleware for structured logging correlation
app.add_middleware(RequestIDMiddleware)

# Setup Prometheus metrics instrumentation
instrumentator = Instrumentator(
    should_group_status_codes=False,
    should_ignore_untemplated=True,
    should_respect_env_var=False,  # Always enable metrics
    should_instrument_requests_inprogress=True,
    excluded_handlers=[],  # Don't exclude metrics endpoint
    inprogress_name="hangar_bay_requests_inprogress",
    inprogress_labels=True,
)
instrumentator.instrument(app)
instrumentator.expose(app, endpoint="/metrics")


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
    Drops and recreates database tables to keep the dev schema current (ENV-2).
    Development-only: production schema management is future migrations work (M2 SSO design spec §8, future work).

    Fail-closed gate (P1): two independent conditions, and ENVIRONMENT is
    secure-by-default. An OMITTED ENVIRONMENT resolves to "production" (see
    core/config.py), so an operator who forgets to set it never trips this path
    even if DB_RECREATE_ON_STARTUP was inherited/copied as true. Recreate requires
    BOTH ENVIRONMENT == "development" AND DB_RECREATE_ON_STARTUP true, set
    explicitly — .env.example sets both, preserving the dev workflow.
    """
    if settings.ENVIRONMENT != "development" or not settings.DB_RECREATE_ON_STARTUP:
        logger.info(
            "Skipping destructive create_db_tables (ENVIRONMENT=%s, DB_RECREATE_ON_STARTUP=%s).",
            settings.ENVIRONMENT, settings.DB_RECREATE_ON_STARTUP,
        )
        return
    logger.info("Dropping and recreating database tables...")
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables successfully recreated.")


def warn_if_sso_unconfigured() -> None:
    """Development-only startup notice (spec §4.4): SSO routes 503 until .env is filled."""
    if settings.ENVIRONMENT != "development":
        return
    if not settings.ESI_CLIENT_ID or not is_token_cipher_configured():
        # Only login and callback are guarded (require_sso_configured) — logout
        # stays operational (204) regardless, so the message must name the two
        # affected routes rather than claim the whole /auth/sso/* family 503s.
        logger.warning(
            "EVE SSO is not configured (ESI_CLIENT_ID/TOKEN_CIPHER_KEYS empty); "
            "/auth/sso/login and /auth/sso/callback return 503."
        )


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
app.include_router(contracts_router.router)
app.include_router(auth_router.router)      # /auth/sso/login|callback|logout (bare, PROXY-1)
app.include_router(auth_router.me_router)   # /me (bare)
app.include_router(saved_searches_router.router)   # /me/saved-searches/* (bare, PROXY-1)
app.include_router(watchlist_router.router)   # /me/watchlist-items (bare, PROXY-1)
app.include_router(notifications_router.router)           # /me/notifications (bare, PROXY-1)
app.include_router(notifications_router.settings_router)  # /me/notification-settings (bare)
app.include_router(ops_router.router)                     # /ready (bare; Render health-check gate)

# Further application setup, routers, middleware, etc., will go here
