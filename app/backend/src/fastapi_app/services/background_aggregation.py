import asyncio
import json
import logging
from contextlib import asynccontextmanager, AbstractAsyncContextManager
from typing import List, Callable # Added Callable
from datetime import datetime

import redis.asyncio as aioredis # For on-demand client creation
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.dependencies import get_cache, get_esi_client, get_settings # Restored get_cache, added get_settings
from ..core.config import settings, Settings # Settings instance and Settings type for hinting
from ..core.esi_client_class import ESIClient # ESIClient class for type hint
from ..core.exceptions import ESINotModifiedError # Restored ESINotModifiedError

from ..models.contracts import Contract, ContractItem # Models
# Removed incorrect import: from ..services.esi_client import ESIClient as ESIClientService
from .db_upsert import bulk_upsert # Upsert utility

# DEBUG: Print for the module-level settings object, AFTER all necessary ..core imports
print(f"BG_AGG_MODULE_SETTINGS_ID: id(settings)={id(settings)}, AGG_REGION_IDS_TYPE={type(settings.AGGREGATION_REGION_IDS)}, VALUE={settings.AGGREGATION_REGION_IDS!r}", flush=True)

logger = logging.getLogger(__name__)

# Lock key for Redis to ensure only one aggregation job runs at a time.
AGGREGATION_LOCK_KEY = "hangar-bay:aggregation:lock"
# Lock timeout in seconds. Should be longer than a typical aggregation run.
AGGREGATION_LOCK_TIMEOUT = 1800  # 30 minutes


class ConcurrencyLockError(Exception):
    """Custom exception for when the aggregation lock cannot be acquired."""
    pass


class ContractAggregationService:
    """
    Service responsible for aggregating public contract data from the ESI API
    and storing it in the local database.
    """

    def __init__(
        self,
        # session_factory: Callable[..., AbstractAsyncContextManager[AsyncSession]], # Removed
        # cache: Redis, # Removed cache client from constructor
        esi_client: ESIClient,
        settings: Settings, # Settings will now be injected
    ):
        # self.session_factory = session_factory # Removed
        # self.cache = cache # Removed cache client attribute
        self.esi_client = esi_client
        self.settings = settings # Assign the injected settings
        # DEBUG: Print for the settings object as seen by __init__
        print(f"BG_AGG___INIT___SETTINGS_ARG_ID: id(settings)={id(settings)}, TYPE={type(settings.AGGREGATION_REGION_IDS)}, VAL={settings.AGGREGATION_REGION_IDS!r}", flush=True)
        # DEBUG: The AGG_SERVICE_INIT prints are still useful for now to see the settings object ID
        print(f"AGG_SERVICE_INIT_SETTINGS_ID: id(self.settings)={id(self.settings)}, id(self.settings.AGGREGATION_REGION_IDS)={id(self.settings.AGGREGATION_REGION_IDS)}", flush=True)
        # DEBUG: Print for AGG_SERVICE_INIT_SETTINGS_VALUE
        print(f"AGG_SERVICE_INIT_SETTINGS_VALUE: self.settings.AGGREGATION_REGION_IDS = {self.settings.AGGREGATION_REGION_IDS!r} (type: {type(self.settings.AGGREGATION_REGION_IDS)})", flush=True)

    @asynccontextmanager
    async def _concurrency_lock(self):
        """
        An async context manager to handle concurrency locking via Redis.
        Creates its own Redis client on-demand.
        """
        redis_client = aioredis.from_url(str(self.settings.CACHE_URL))
        lock_acquired = False
        try:
            lock_acquired = await redis_client.set(
                AGGREGATION_LOCK_KEY, "1", nx=True, ex=AGGREGATION_LOCK_TIMEOUT
            )
            if not lock_acquired:
                logger.warning("Contract aggregation job is already running. Skipping this run.")
                # Do not raise here, allow the finally to close the client, then re-raise or return
                # For context manager, it's better to let it exit cleanly if lock not acquired.
                # The caller of the context manager should check if the lock was acquired.
                # However, the current design raises, so we'll stick to it but ensure client closes.
                raise ConcurrencyLockError("Could not acquire aggregation lock.")

            logger.info("Concurrency lock acquired for contract aggregation.")
            yield # If this raises, the finally block below still runs
        finally:
            if lock_acquired:
                logger.info("Releasing concurrency lock for contract aggregation.")
                await redis_client.delete(AGGREGATION_LOCK_KEY)
            await redis_client.close() # Ensure redis client is closed

    async def run_aggregation(self):
        """
        Runs the full public contract aggregation and ingestion process.
        Uses a database session from the session factory.
        """
        print(f"AGG_RUN_SETTINGS_ID: id(self.settings)={id(self.settings)}, id(self.settings.AGGREGATION_REGION_IDS)={id(self.settings.AGGREGATION_REGION_IDS)}", flush=True)
        current_region_ids = self.settings.AGGREGATION_REGION_IDS
        print(f"AGG_DEBUG: AGGREGATION_REGION_IDS from settings: {current_region_ids!r} (type: {type(current_region_ids)} )", flush=True)

        if not isinstance(current_region_ids, list) or not all(isinstance(x, int) for x in current_region_ids):
            logger.error(f"CRITICAL_ERROR_AGG_SERVICE: AGGREGATION_REGION_IDS is not a list of int: {current_region_ids!r} (type: {type(current_region_ids)}) Aborting aggregation.")
            return

        if not current_region_ids:
            logger.warning("AGGREGATION_REGION_IDS is empty. Skipping aggregation.")
            return

        engine = None  # Initialize engine to None for the finally block
        try:
            async with self._concurrency_lock():  # Handles concurrent job runs
                # Use the ESIClient as a context manager to ensure its http_client is initialized.
                async with self.esi_client:
                    logger.info("Concurrency lock acquired. Starting public contract aggregation run.")
                    
                    # Dynamically create engine and session factory
                    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
                    from sqlalchemy.orm import sessionmaker
                    
                    logger.info(f"Creating database engine with URL: {self.settings.DATABASE_URL[:30]}...") # Log part of URL for privacy
                    engine = create_async_engine(self.settings.DATABASE_URL)
                    local_session_factory = sessionmaker(
                        bind=engine,
                        class_=AsyncSession,
                        expire_on_commit=False
                    )
                    
                    async with local_session_factory() as db_session: # Obtain a new session for this run
                        logger.info(f"Processing contracts for region IDs: {current_region_ids}")
                        all_contracts_data: List[dict] = []

                        for region_id in current_region_ids:
                            try:
                                contracts_page = await self.esi_client.get_public_contracts(region_id)
                                logger.info(f"Fetched {len(contracts_page)} contracts for region {region_id}.")
                                all_contracts_data.extend(contracts_page)
                            except ESINotModifiedError:
                                logger.info(f"Contracts for region {region_id} not modified.")
                            except Exception as e:
                                logger.error(f"Failed to fetch contracts for region {region_id}: {e}", exc_info=True)


                        if not all_contracts_data:
                            logger.info("No new contracts found across all specified regions.")
                            # No need to commit or process further if no data was fetched.
                        else:
                            # Apply development limit if configured
                            if self.settings.AGGREGATION_DEV_CONTRACT_LIMIT and self.settings.AGGREGATION_DEV_CONTRACT_LIMIT > 0:
                                limit = self.settings.AGGREGATION_DEV_CONTRACT_LIMIT
                                if len(all_contracts_data) > limit:
                                    logger.warning(f"DEV_MODE: Limiting contracts to process from {len(all_contracts_data)} to {limit}.")
                                    all_contracts_data = all_contracts_data[:limit]

                            await self._process_contracts(db_session, all_contracts_data)

                            await db_session.commit()
                            logger.info("Public contract aggregation run finished successfully and changes committed.")

        except ConcurrencyLockError:
            # This is expected if another job is running, so we just log and return.
            logger.info("Aggregation job did not run due to existing concurrency lock.")
            return
        except Exception as e:
            logger.error(f"An unexpected error occurred during the aggregation process: {e}", exc_info=True)
            # Rollback should happen within the session context if it was established
            # However, if error is before session_factory() or in _concurrency_lock, db_session might not exist.
            # The session context manager itself handles rollback on unhandled exceptions within its block.
            logger.info("Aggregation run failed. Database changes (if any within an active session) should be rolled back by session context manager.")
            # No explicit rollback here as the session context manager handles it.
            # If the error was in _concurrency_lock, no db_session was active yet.
            return
        finally:
            if engine: # Check if engine was initialized
                logger.info("Disposing of database engine.")
                await engine.dispose()
                logger.info("Database engine disposed.")

    async def _process_contracts(self, db_session: AsyncSession, contracts: List[dict]):
        """
        Processes a list of contracts, fetches their items, and upserts them using the provided db_session.
        """
        # Helper to parse ESI's ISO 8601 date strings into datetime objects.
        def _parse_datetime(date_string: str | None) -> datetime | None:
            if date_string is None:
                return None
            # ESI dates are like "2024-05-20T14:47:32Z". The 'Z' means UTC.
            # fromisoformat handles this correctly if we replace 'Z' with '+00:00'.
            return datetime.fromisoformat(date_string.replace("Z", "+00:00"))

        # Step 1: Collect all unique issuer and corporation IDs from the current batch of contracts.
        issuer_ids = {c['issuer_id'] for c in contracts}
        corporation_ids = {c['issuer_corporation_id'] for c in contracts}
        all_ids_to_resolve = list(issuer_ids.union(corporation_ids))

        # Step 2: Resolve all IDs to names in a single batch operation.
        id_to_name_map = {}
        if all_ids_to_resolve:
            logger.info(f"Resolving {len(all_ids_to_resolve)} unique IDs to names.")
            id_to_name_map = await self.esi_client.resolve_ids_to_names(all_ids_to_resolve)
            logger.info(f"Successfully resolved {len(id_to_name_map)} names.")

        # Step 3: Transform contracts into the format for the database model, enriching with names.
        contract_values = [
            {
                "contract_id": c["contract_id"],
                "issuer_id": c["issuer_id"],
                "issuer_corporation_id": c["issuer_corporation_id"],
                "start_location_id": c["start_location_id"],
                "end_location_id": c.get("end_location_id"),
                "type": c["type"],
                "status": c.get("status", "outstanding"),
                "title": c.get("title", ""),
                "for_corporation": c.get("for_corporation", False),
                "date_issued": _parse_datetime(c["date_issued"]),
                "date_expired": _parse_datetime(c["date_expired"]),
                "date_completed": _parse_datetime(c.get("date_completed")),
                "price": c.get("price"),
                "reward": c.get("reward"),
                "volume": c.get("volume"),
                "issuer_name": id_to_name_map.get(c['issuer_id']),
                "issuer_corporation_name": id_to_name_map.get(c['issuer_corporation_id']),
                "is_ship_contract": False,  # Placeholder, to be enriched later
            }
            for c in contracts
        ]

        batch_size = 500  # Number of contracts to process in each batch
        total_contracts = len(contract_values)
        logger.info(f"Upserting {total_contracts} contracts in batches of {batch_size}.")

        for i in range(0, total_contracts, batch_size):
            batch = contract_values[i:i + batch_size]
            logger.info(f"Processing batch {i // batch_size + 1}/{(total_contracts + batch_size - 1) // batch_size} ({len(batch)} contracts)")
            await bulk_upsert(db_session, Contract, batch)
            logger.info(f"Successfully upserted batch {i // batch_size + 1}.")

        logger.info(f"Finished upserting all {total_contracts} contracts.")

        all_items: List[dict] = []
        for contract in contracts:
            if contract["type"] not in ["item_exchange", "auction"]:
                continue

            try:
                items = await self.esi_client.get_contract_items(contract["contract_id"])
                logger.debug(f"Fetched {len(items)} items for contract {contract['contract_id']}.")

                item_values = [
                    {
                        "record_id": i["record_id"],
                        "contract_id": contract["contract_id"],
                        "type_id": i["type_id"],
                        "quantity": i["quantity"],
                        "is_included": i["is_included"],
                        "is_singleton": i.get("is_singleton", False),
                        "raw_quantity": i.get("raw_quantity"),
                    }
                    for i in items
                ]
                all_items.extend(item_values)
            except ESINotModifiedError:
                logger.info(f"Items for contract {contract['contract_id']} not modified.")
            except Exception as e:
                logger.error(f"Failed to fetch items for contract {contract['contract_id']}: {e}", exc_info=True)

        if all_items:
            logger.info(f"Preparing to upsert {len(all_items)} contract items in batches.")
            BATCH_SIZE = 50  # Number of items to process in each batch
            for i in range(0, len(all_items), BATCH_SIZE):
                batch_items = all_items[i:i + BATCH_SIZE]
                logger.info(f"Upserting batch of {len(batch_items)} contract items (items {i+1}-{i+len(batch_items)} of {len(all_items)}).")
                await bulk_upsert(db_session, ContractItem, batch_items)
            logger.info(f"Finished upserting all {len(all_items)} contract items.")
        else:
            logger.info("No new contract items to process.")


# Dependency for getting the service
async def get_aggregation_service(
    # cache: Redis = Depends(get_cache), # Service no longer takes cache client directly
    esi_client: ESIClient = Depends(get_esi_client),
    settings: Settings = Depends(get_settings), # Use the new get_settings dependency
) -> ContractAggregationService:
    """
    FastAPI dependency to get an instance of the ContractAggregationService.
    The service manages its own database sessions for scheduled tasks.
    The global `settings` object from `..core.config` is used by default.
    """
    # Uses the global `settings` imported at the top of the file for now.
    # If specific settings injection per request is needed later, that would require a `Depends(get_settings_func)`
    return ContractAggregationService(esi_client=esi_client, settings=settings)
