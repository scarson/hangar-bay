import asyncio
import logging
from contextlib import asynccontextmanager
from typing import List

from redis.asyncio import Redis
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.dependencies import get_cache
from ..core.config import settings, Settings
from ..db import get_db
from ..models.contracts import Contract, ContractItem
from .db_upsert import bulk_upsert
from ..core.dependencies import get_esi_client
from ..core.esi_client_class import ESIClient
from ..core.exceptions import ESINotModifiedError

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
        db: AsyncSession,
        cache: Redis,
        esi_client: ESIClient,
        settings: Settings,
    ):
        self.db = db
        self.cache = cache
        self.esi_client = esi_client
        self.settings = settings

    @asynccontextmanager
    async def _concurrency_lock(self):
        """
        An async context manager to handle concurrency locking via Redis.
        """
        lock_acquired = await self.cache.set(
            AGGREGATION_LOCK_KEY, "1", nx=True, ex=AGGREGATION_LOCK_TIMEOUT
        )
        if not lock_acquired:
            logger.warning("Contract aggregation job is already running. Skipping this run.")
            raise ConcurrencyLockError("Could not acquire aggregation lock.")

        try:
            logger.info("Concurrency lock acquired for contract aggregation.")
            yield
        finally:
            logger.info("Releasing concurrency lock for contract aggregation.")
            await self.cache.delete(AGGREGATION_LOCK_KEY)

    async def run_aggregation(self):
        """
        Runs the full public contract aggregation and ingestion process.
        """
        try:
            async with self._concurrency_lock():
                logger.info("Starting public contract aggregation run.")

                region_ids_str = self.settings.AGGREGATION_REGION_IDS
                if not region_ids_str:
                    logger.warning("AGGREGATION_REGION_IDS is not set. Skipping aggregation.")
                    return

                try:
                    region_ids = [int(rid.strip()) for rid in region_ids_str.split(',')]
                except (ValueError, AttributeError):
                    logger.error(
                        f"Could not parse AGGREGATION_REGION_IDS: '{region_ids_str}'. "
                        f"Please provide a comma-separated list of integers.",
                        exc_info=True,
                    )
                    return
                all_contracts: List[dict] = []

                for region_id in region_ids:
                    try:
                        contracts = await self.esi_client.get_public_contracts(region_id)
                        logger.info(f"Fetched {len(contracts)} contracts for region {region_id}.")
                        all_contracts.extend(contracts)
                    except ESINotModifiedError:
                        logger.info(f"Contracts for region {region_id} not modified.")
                    except Exception as e:
                        logger.error(f"Failed to fetch contracts for region {region_id}: {e}", exc_info=True)

                if not all_contracts:
                    logger.info("No new contracts found to process.")
                    return

                await self._process_contracts(all_contracts)

                logger.info("Public contract aggregation run finished successfully.")

        except ConcurrencyLockError:
            # This is expected if another job is running, so we just return.
            return
        except Exception as e:
            logger.error(f"An unexpected error occurred during aggregation: {e}", exc_info=True)

    async def _process_contracts(self, contracts: List[dict]):
        """
        Processes a list of contracts, fetches their items, and upserts them.
        """
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
                "for_corporation": c["for_corporation"],
                "date_issued": c["date_issued"],
                "date_expired": c["date_expired"],
                "date_completed": c.get("date_completed"),
                "price": c.get("price"),
                "reward": c.get("reward"),
                "volume": c.get("volume"),
                "is_ship_contract": False,  # Placeholder, to be enriched later
            }
            for c in contracts
        ]

        logger.info(f"Upserting {len(contract_values)} contracts.")
        await bulk_upsert(self.db, Contract, contract_values)

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
                        "is_singleton": i["is_singleton"],
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
            logger.info(f"Upserting {len(all_items)} contract items.")
            await bulk_upsert(self.db, ContractItem, all_items)


# Dependency for getting the service
async def get_aggregation_service(
    db: AsyncSession = Depends(get_db),
    cache: Redis = Depends(get_cache),
    esi_client: ESIClient = Depends(get_esi_client),
) -> "ContractAggregationService":
    """
    FastAPI dependency to get an instance of the ContractAggregationService.
    """
    return ContractAggregationService(
        db=db, cache=cache, esi_client=esi_client, settings=settings
    )
