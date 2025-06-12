import logging
from datetime import datetime # Added for next_run_time

from urllib.parse import urlparse

from apscheduler.jobstores.redis import RedisJobStore
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI

from ..core.config import Settings # Keep for type hint if settings obj is still passed for interval
from ..services.scheduled_jobs import run_aggregation_job
from ..services.background_aggregation import ContractAggregationService # Import the service

logger = logging.getLogger(__name__)


def create_scheduler(app: FastAPI, settings: Settings) -> AsyncIOScheduler:
    """Creates and configures the APScheduler instance."""
    redis_url = urlparse(settings.CACHE_URL)
    jobstores = {
        "default": RedisJobStore(
            host=redis_url.hostname,
            port=redis_url.port,
            db=int(redis_url.path.lstrip("/") or 0),
            password=redis_url.password,
        )
    }
    scheduler = AsyncIOScheduler(jobstores=jobstores)
    app.state.scheduler = scheduler
    return scheduler


def add_aggregation_job(scheduler: AsyncIOScheduler, aggregation_service: ContractAggregationService, settings: Settings): # Add service, keep settings for interval
    """Adds the contract aggregation job to the scheduler."""
    scheduler.add_job(
        run_aggregation_job,
        trigger="interval",
        args=[aggregation_service],
        seconds=settings.AGGREGATION_SCHEDULER_INTERVAL_SECONDS,
        id="aggregate_public_contracts",
        replace_existing=True,
        misfire_grace_time=300,  # 5 minutes
        next_run_time=datetime.now() # Run immediately on startup
    )
    logger.info(
        f"Scheduled contract aggregation job to run every "
        f"{settings.AGGREGATION_SCHEDULER_INTERVAL_SECONDS} seconds."
    )
