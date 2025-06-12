# Guide: Integrating APScheduler with FastAPI

**Last Updated:** 2025-06-12
**Related Patterns:**
*   [Pattern: Dependency Management in Hybrid Contexts](..\patterns\01-dependency-injection.md)
*   [Pattern: Service Construction - Configuration over Live Resources](..\patterns\02-service-construction.md)
*   [Pattern: Atomic Database Transactions for Logical Units of Work](..\patterns\03-database-transactions.md)

## AI Analysis Guidance for Cascade

This file is over 200 lines long. Unless you are only looking for a specific section, you should read the entire file, which may require multiple tool calls.

## 1. Objective

This guide provides a step-by-step approach to integrating APScheduler with a FastAPI application for running background tasks. It covers:

*   Scheduler lifecycle management (startup and shutdown).
*   Defining and adding jobs.
*   Properly instantiating and using services within background jobs, adhering to established architectural patterns to avoid issues like `PicklingError`.
*   Concurrency control for background jobs.

## 2. Core Components & Setup

### 2.1. Installation

Ensure APScheduler and any necessary job store backends (e.g., `redis` for `RedisJobStore`) are installed:

```bash
pip install apscheduler redis
# or via poetry
poetry add apscheduler redis
```

### 2.2. Scheduler Initialization (`main.py`)

The scheduler should be initialized and managed within FastAPI's lifespan events.

```python
# In main.py
from fastapi import FastAPI
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.redis import RedisJobStore
from contextlib import asynccontextmanager

from .core.config import settings # Your application settings
from .services.background_aggregation import ContractAggregationService # Example service
from .core.esi_client_class import ESIClient # Example ESI client service

# Global scheduler instance (can be stored on app.state if preferred)
scheduler = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global scheduler
    logger.info("Application startup...")

    # Initialize ESIClient and ContractAggregationService with settings
    # These instances are used to *add jobs* to the scheduler, not run inside the jobs themselves directly if they contain non-picklable state.
    # The actual job functions will re-instantiate services as needed, or use passed-in picklable args.
    esi_client_for_scheduler = ESIClient(settings=settings)
    aggregation_service_for_scheduler = ContractAggregationService(
        settings=settings, 
        esi_client=esi_client_for_scheduler
    )

    jobstores = {
        'default': RedisJobStore(
            jobs_key='hangar_bay_jobs',
            run_times_key='hangar_bay_run_times',
            host=settings.CACHE_HOST,
            port=settings.CACHE_PORT,
            db=settings.CACHE_DB_APScheduler, # Use a separate DB for APScheduler
            # password=settings.CACHE_PASSWORD # if applicable
        )
    }
    executors = {
        'default': {'type': 'asyncio'}, # For asyncio compatible jobs
        'processpool': {'type': 'processpool', 'max_workers': settings.APS_MAX_WORKERS} # For CPU-bound or blocking jobs
    }
    
    scheduler = AsyncIOScheduler(jobstores=jobstores, executors=executors, timezone=str(settings.TIMEZONE))
    
    # Add jobs here (see section 3)
    # Example: Add a recurring job
    scheduler.add_job(
        aggregation_service_for_scheduler.run_public_contract_aggregation_job, 
        'interval',
        minutes=settings.AGGREGATION_JOB_INTERVAL_MINUTES,
        id='public_contract_aggregation',
        replace_existing=True,
        executor='processpool' # Run in a separate process to avoid blocking asyncio loop and for pickling
    )
    
    scheduler.start()
    logger.info("APScheduler started.")
    
    app.state.scheduler = scheduler # Optional: store on app.state

    yield

    logger.info("Application shutdown...")
    if scheduler and scheduler.running:
        scheduler.shutdown()
        logger.info("APScheduler shut down.")

app = FastAPI(lifespan=lifespan)

# ... rest of your FastAPI app setup ...
```

**Key Points:**

*   **Lifespan Events:** Use `asynccontextmanager` and `lifespan` for modern FastAPI startup/shutdown.
*   **Job Store:** `RedisJobStore` is recommended for persistence and multi-process environments. Use a separate Redis database for APScheduler to avoid key collisions.
*   **Executors:**
    *   `asyncio` (default): Suitable for I/O-bound tasks that are `async` and don't block the event loop.
    *   `processpool`: **Essential for tasks that might be CPU-bound, blocking, or involve non-picklable objects that need to be re-instantiated within the job's process.** This is the common case for our services.
*   **Timezone:** Always configure a timezone for the scheduler.
*   **Service Instantiation for Adding Jobs:** When adding a job that is a method of a service (e.g., `aggregation_service.run_aggregation_job`), you instantiate the service with `settings` (and other picklable dependencies like other services) as per the "Service Construction" pattern. APScheduler will then pickle this service instance *if the job target is a method of that instance*. This is why the service itself must be picklable (i.e., not hold live resources directly).

## 3. Defining and Adding Jobs

Jobs are Python functions or methods that APScheduler will execute.

### 3.1. Job Function/Method Design (Crucial for Pickling)

When a job is scheduled to run in a `processpool` executor (common for our backend services to avoid blocking the main asyncio loop and to handle potentially non-picklable resources correctly):

1.  **The Job Target:** This is the function APScheduler calls. It can be a standalone function or a method of a class.
2.  **Picklable Arguments:** Any arguments passed to the job via `scheduler.add_job(..., args=[...], kwargs={...})` **must be picklable**.
3.  **Service Instantiation within the Job (if needed):**
    *   If the job function itself needs to use services (like `ESIClient` or `ContractAggregationService`), it **must** follow the "Dynamic Resource Instantiation" sub-pattern from the "Dependency Management" pattern document.
    *   This means the job function should receive the `settings` object (which is picklable) as an argument, or import it globally, and then instantiate services *inside the job function* using these settings.
    *   **Avoid** trying to pass live, non-picklable service instances (that hold, e.g., an active Redis client) directly as arguments to jobs running in separate processes.

**Example: A Service Method as a Job Target**

```python
# In services/background_aggregation.py
from ..core.config import Settings, get_settings_for_job # A function to get settings
from ..core.esi_client_class import ESIClient
# Import other necessary components for database, logging etc.

class ContractAggregationService:
    def __init__(self, settings: Settings, esi_client: ESIClient):
        # This __init__ is called when the service is instantiated to *add the job*.
        # It must only store picklable things (settings, or other services also init'd with settings).
        self.settings = settings
        self.esi_client = esi_client # ESIClient itself is picklable if it only holds settings
        # DO NOT initialize self.db_session or self.redis_client here directly.

    async def run_public_contract_aggregation_job(self):
        # This method is the actual job executed by APScheduler in a separate process.
        # It uses the self.settings and self.esi_client that were pickled with the service instance.
        
        # If ESIClient or other services needed to be instantiated *freshly* here (e.g., if they weren't passed to __init__
        # or if you need a completely isolated instance for the job), you would do:
        # current_settings = get_settings_for_job() # Or import global settings
        # fresh_esi_client = ESIClient(settings=current_settings)

        logger.info(f"Running public contract aggregation with limit: {self.settings.AGGREGATION_DEV_CONTRACT_LIMIT}")
        
        # Acquire database session dynamically (as per DB transaction pattern)
        async with get_async_db_session_for_job(self.settings) as db:
            try:
                # --- Concurrency Lock (see section 4) ---
                lock_acquired = await self._acquire_lock(db, "public_contract_aggregation_lock")
                if not lock_acquired:
                    logger.info("Could not acquire lock for public contract aggregation. Skipping run.")
                    return

                # ... actual aggregation logic using self.esi_client and db ...
                # Example: await self.esi_client.get_public_contracts_for_region(region_id, db_session=db)
                #          await self._process_contracts(contracts, db_session=db)
                
                await db.commit()
                logger.info("Public contract aggregation job completed successfully.")
            except Exception as e:
                await db.rollback()
                logger.error(f"Error in public contract aggregation job: {e}", exc_info=True)
            finally:
                if lock_acquired:
                    await self._release_lock(db, "public_contract_aggregation_lock")
```

**Explanation:**

*   When `scheduler.add_job(aggregation_service_for_scheduler.run_public_contract_aggregation_job, ...)` is called in `main.py`, the `aggregation_service_for_scheduler` instance is pickled by APScheduler (because the job target is a method of this instance) and sent to the process pool worker.
*   For this to work, `ContractAggregationService` and `ESIClient` (if held as `self.esi_client`) must be picklable. This is achieved by them only storing `settings` or other similarly picklable objects, as per the "Service Construction" pattern.
*   Inside `run_public_contract_aggregation_job`, non-picklable resources like database sessions (`db`) or direct Redis clients for locks are acquired dynamically.

### 3.2. Adding Jobs in `main.py`

```python
# In main.py lifespan function, after scheduler is initialized:

# Example 1: Interval job for a service method
scheduler.add_job(
    aggregation_service_for_scheduler.run_public_contract_aggregation_job,
    trigger='interval',
    minutes=settings.AGGREGATION_JOB_INTERVAL_MINUTES,
    id='public_contract_aggregation', # Unique ID for the job
    name='Public Contract Aggregation Task',
    replace_existing=True, # Replaces the job if one with the same ID exists
    executor='processpool' # CRITICAL for services that need dynamic resource instantiation
)

# Example 2: Cron job for a standalone function (if it were defined)
# async def my_standalone_job_function(app_settings: Settings):
#     # Instantiate services here using app_settings
#     esi = ESIClient(settings=app_settings)
#     # ... do work ...

# scheduler.add_job(
#     my_standalone_job_function,
#     trigger='cron',
#     day_of_week='mon-fri',
#     hour=10,
#     minute=0,
#     id='my_cron_job',
#     replace_existing=True,
#     args=[settings], # Pass picklable settings object
#     executor='processpool'
# )
```

*   **`id`:** Provide a unique ID for each job. This allows you to modify or remove it later and is used by `replace_existing=True`.
*   **`replace_existing=True`:** Useful during development and deployment to ensure the latest job definition is used.
*   **`executor='processpool'`:** Use this for most service-based jobs to ensure they run in a separate process, preventing `PicklingError` for services that dynamically instantiate resources and avoiding blocking the main FastAPI event loop.

## 4. Concurrency Control for Background Jobs

If a background job could potentially run multiple times concurrently (e.g., if the interval is short and a previous run is still ongoing, or due to multiple application instances), you **must** implement a concurrency control mechanism.

*   **Mechanism:** Distributed lock using Redis (or Valkey).
*   **Implementation:** Before the main logic of the job, attempt to acquire a lock. If the lock cannot be acquired, it means another instance of the job is likely running, so the current instance should exit gracefully.

```python
# Inside your service method that is the job target (e.g., run_public_contract_aggregation_job)

async def _acquire_lock(self, job_name: str, timeout_seconds: int = 5, expiry_seconds: int = 3600) -> bool:
    # This method would use a Redis client, instantiated dynamically
    redis = await aioredis.from_url(str(self.settings.CACHE_URL_CONCURRENCY_LOCKS))
    lock_key = f"job_lock:{job_name}"
    try:
        # Attempt to set the lock key with NX (only if not exists) and EX (expire time)
        # The value can be anything, e.g., a timestamp or instance ID
        if await redis.set(lock_key, "locked", nx=True, ex=expiry_seconds):
            logger.info(f"Acquired lock: {lock_key}")
            return True
        else:
            logger.warning(f"Could not acquire lock: {lock_key}. Another instance may be running.")
            return False
    except Exception as e:
        logger.error(f"Error acquiring lock {lock_key}: {e}", exc_info=True)
        return False # Fail safe, assume lock not acquired
    finally:
        await redis.close()

async def _release_lock(self, job_name: str):
    redis = await aioredis.from_url(str(self.settings.CACHE_URL_CONCURRENCY_LOCKS))
    lock_key = f"job_lock:{job_name}"
    try:
        await redis.delete(lock_key)
        logger.info(f"Released lock: {lock_key}")
    except Exception as e:
        logger.error(f"Error releasing lock {lock_key}: {e}", exc_info=True)
    finally:
        await redis.close()

# In the job method:
# ...
lock_acquired = False
try:
    lock_acquired = await self._acquire_lock("public_contract_aggregation_job")
    if not lock_acquired:
        return # Exit if lock not acquired
    
    # ... main job logic ...

finally:
    if lock_acquired:
        await self._release_lock("public_contract_aggregation_job")
# ...
```

*   **Separate Redis DB/URL:** Consider using a separate Redis database or even a separate Redis instance for concurrency locks to isolate them from cache data.
*   **Lock Expiry:** Always set an expiry time on locks to prevent deadlocks if a job crashes before releasing the lock.

## 5. Logging and Monitoring

*   Ensure proper logging is configured for APScheduler itself and for your job functions.
*   Monitor job execution (successes, failures, durations) through logs or a dedicated monitoring system.

## 6. Best Practices & Troubleshooting

*   **PicklingError:** The most common issue. Ensure services are initialized with picklable `Settings` and dynamically create non-picklable resources (DB connections, HTTP clients) *inside* job methods when using `processpool` executor. Refer to the "Dependency Management" and "Service Construction" patterns.
*   **Blocking Jobs:** If a job blocks the asyncio event loop (for `asyncio` executor) or takes too long, it can affect FastAPI's performance. Use `processpool` executor for such jobs.
*   **Database Sessions:** Each job execution in a separate process should manage its own database session lifecycle (acquire, use, commit/rollback, close).
*   **Configuration:** Ensure the `settings` object passed to or used by jobs contains all necessary configurations (database URLs, API keys, etc.).
*   **Testing:** Mock APScheduler or the job functions/services during unit/integration tests. You typically don't want actual background jobs running during automated tests unless specifically testing the scheduler integration.

This guide provides a foundational approach. Adapt and extend it based on your project's specific requirements. Always refer to the official APScheduler documentation for detailed API information.
