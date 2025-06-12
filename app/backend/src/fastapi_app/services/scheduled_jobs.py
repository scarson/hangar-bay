import logging

from ..core.cache import CacheManager
from ..core.config import settings
from ..db import AsyncSessionLocal as async_session_factory
from .background_aggregation import ContractAggregationService
from ..core.esi_client_class import ESIClient
import httpx

logger = logging.getLogger(__name__)


async def run_aggregation_job():
    """
    A top-level, importable function to run the contract aggregation service.
    This function is responsible for setting up and tearing down its own dependencies.
    """
    logger.info("Executing scheduled job: run_aggregation_job")
    
    # Manually create dependencies for the background job
    cache_manager = CacheManager()
    db_session_context = async_session_factory()

    try:
        await cache_manager.initialize(settings.CACHE_URL)
        redis_client = cache_manager.get_client()
        db_session = await db_session_context.__aenter__()

        headers = {"User-Agent": settings.ESI_USER_AGENT}
        async with httpx.AsyncClient(base_url="https://esi.evetech.net", headers=headers) as http_client:
            esi_client = ESIClient(http_client=http_client, redis_client=redis_client)
            
            aggregation_service = ContractAggregationService(
                db=db_session,
                cache=redis_client,
                esi_client=esi_client,
                settings=settings,
            )

            await aggregation_service.run_aggregation()

    except Exception as e:
        logger.error(f"An error occurred during the scheduled aggregation job: {e}", exc_info=True)
    finally:
        await cache_manager.close()
        if 'db_session' in locals() and db_session:
            await db_session_context.__aexit__(None, None, None)
        logger.info("Finished scheduled job: run_aggregation_job")
