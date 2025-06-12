import logging

from ..core.cache import CacheManager
from ..core.config import settings
from ..db import AsyncSessionLocal as async_session_factory
from .background_aggregation import ContractAggregationService
from ..core.esi_client_class import ESIClient
import httpx

logger = logging.getLogger(__name__)


async def run_aggregation_job(aggregation_service: ContractAggregationService):
    """
    A top-level, importable function to run the contract aggregation service.
    This function now expects an already initialized ContractAggregationService instance.
    """
    logger.info("Executing scheduled job: run_aggregation_job with injected service")
    
    try:
        await aggregation_service.run_aggregation()
    except Exception as e:
        logger.error(f"An error occurred during the scheduled aggregation job: {e}", exc_info=True)
    finally:
        logger.info("Finished scheduled job: run_aggregation_job")
