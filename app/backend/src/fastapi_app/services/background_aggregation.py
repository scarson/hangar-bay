import asyncio
import json
import logging
import uuid
from contextlib import asynccontextmanager, AbstractAsyncContextManager
from typing import Iterable, Iterator, List, Callable # Added Callable
from datetime import datetime

import redis.asyncio as aioredis # For on-demand client creation
from fastapi import Depends
from sqlalchemy import update
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

# Atomic compare-and-delete: only release the lock if THIS runner still holds it
# (the stored value equals our token). Guards against the TTL expiring mid-run
# and a second scheduler tick reacquiring the key — an unconditional DELETE would
# then drop the other runner's lock and cascade into concurrent runs.
_RELEASE_LOCK_LUA = (
    "if redis.call('get', KEYS[1]) == ARGV[1] then "
    "return redis.call('del', KEYS[1]) else return 0 end"
)

# asyncpg caps a statement at 32767 bind parameters; a single UPDATE ... WHERE
# contract_id IN (<all ids>) over a whole run (production scale ~35k contracts)
# blows that ceiling and rolls back the entire aggregation transaction. Chunk the
# id-list UPDATEs so no statement ever exceeds the cap.
UPDATE_ID_CHUNK_SIZE = 1000

# Bounded concurrency for the cold-cache type/group enrichment fan-out: without
# it, thousands of unique types resolve as strictly sequential ESI round-trips,
# minutes of added runtime that also push a run past the lock TTL.
ENRICHMENT_CONCURRENCY = 8


def _chunk_ids(ids: Iterable[int]) -> Iterator[list[int]]:
    """Yield id-list slices capped at UPDATE_ID_CHUNK_SIZE (asyncpg bind limit)."""
    id_list = list(ids)
    for start in range(0, len(id_list), UPDATE_ID_CHUNK_SIZE):
        yield id_list[start : start + UPDATE_ID_CHUNK_SIZE]


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
        # Unique fencing token: the lock value identifies THIS runner so release
        # can verify ownership (see _RELEASE_LOCK_LUA) instead of blindly deleting.
        lock_token = uuid.uuid4().hex
        lock_acquired = False
        try:
            lock_acquired = await redis_client.set(
                AGGREGATION_LOCK_KEY, lock_token, nx=True, ex=AGGREGATION_LOCK_TIMEOUT
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
                # Compare-and-delete: release only if we still hold the token. A
                # zero result means the TTL expired mid-run and another runner
                # reacquired the key — deleting it would drop THEIR lock.
                released = await redis_client.eval(
                    _RELEASE_LOCK_LUA, 1, AGGREGATION_LOCK_KEY, lock_token
                )
                if not released:
                    logger.warning(
                        "Aggregation lock token mismatch on release: the %ss lock TTL "
                        "likely expired mid-run and was reacquired by another runner. "
                        "Leaving the current holder's lock intact.",
                        AGGREGATION_LOCK_TIMEOUT,
                    )
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
                                # ESI contract payloads carry no region; stamp the
                                # fetch region so it survives into the DB (the
                                # region_ids filter reads start_location_region_id).
                                for contract_data in contracts_page:
                                    contract_data["_hb_region_id"] = region_id
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

        # Step 1: Collect all unique IDs from the current batch of contracts.
        issuer_ids = {c['issuer_id'] for c in contracts}
        corporation_ids = {c['issuer_corporation_id'] for c in contracts}
        start_location_ids = {c.get('start_location_id') for c in contracts if c.get('start_location_id')}
        end_location_ids = {c.get('end_location_id') for c in contracts if c.get('end_location_id')}

        all_ids_to_resolve = list(
            issuer_ids.union(corporation_ids).union(start_location_ids).union(end_location_ids)
        )

        # Player-owned structures have IDs > 10^11 and are not resolvable
        # by the public /universe/names/ endpoint. We filter them out.
        original_id_count = len(all_ids_to_resolve)
        all_ids_to_resolve = [
            id_ for id_ in all_ids_to_resolve if id_ < 100_000_000_000
        ]
        filtered_count = len(all_ids_to_resolve)
        if original_id_count > filtered_count:
            logger.info(f"Filtered out {original_id_count - filtered_count} unresolvable structure IDs.")

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
                "start_location_id": c.get("start_location_id"),
                "start_location_region_id": c.get("_hb_region_id"),
                "end_location_id": c.get("end_location_id"),
                "type": c["type"],  # Direct mapping - field names now match
                "status": c.get("status", "unknown"),
                "title": c.get("title"),
                "for_corporation": c.get("for_corporation", False),
                "date_issued": _parse_datetime(c["date_issued"]),
                "date_expired": _parse_datetime(c["date_expired"]),
                "date_completed": _parse_datetime(c.get("date_completed")),
                "price": c.get("price"),
                "collateral": c.get("collateral", 0.0),  # Default to 0.0 if null
                "reward": c.get("reward"),
                "volume": c.get("volume"),
                # Denormalized data for search performance
                "start_location_name": id_to_name_map.get(c.get("start_location_id")),
                "issuer_name": id_to_name_map.get(c.get('issuer_id')),
                "issuer_corporation_name": id_to_name_map.get(c.get('issuer_corporation_id')),
                # is_ship_contract and item_processing_status are deliberately
                # ABSENT: they are maintained by item enrichment, and the upsert
                # copies every mapped column on conflict — including them here
                # decayed ship flags to False whenever items were ETag-304'd and
                # skipped re-enrichment. Column defaults cover fresh inserts.
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
        processed_contract_ids: set[int] = set()
        for contract in contracts:
            if contract["type"] not in ["item_exchange", "auction"]:
                continue

            try:
                items = await self.esi_client.get_contract_items(contract["contract_id"])
                processed_contract_ids.add(contract["contract_id"])
                logger.debug(f"Fetched {len(items)} items for contract {contract['contract_id']}.")

                item_values = [
                    {
                        "record_id": i["record_id"],
                        "contract_id": contract["contract_id"],
                        "type_id": i["type_id"],
                        "quantity": i["quantity"],
                        "is_included": i["is_included"],
                        "is_singleton": i.get("is_singleton", False),
                        # ESI item payloads carry is_blueprint_copy; without this
                        # mapping the column stayed NULL and the is_bpc filter was
                        # dead on real data (same class as the ship-flag gap).
                        "is_blueprint_copy": i.get("is_blueprint_copy"),
                        "raw_quantity": i.get("raw_quantity"),
                    }
                    for i in items
                ]
                all_items.extend(item_values)
            except ESINotModifiedError:
                logger.info(f"Items for contract {contract['contract_id']} not modified.")
            except Exception as e:
                logger.error(f"Failed to fetch items for contract {contract['contract_id']}: {e}", exc_info=True)

        # Enrich items with static type data BEFORE upserting so a single
        # write carries names/categories, and collect which contracts hold an
        # included ship (fills the gap that left is_ship_contract permanently
        # False — "will be updated later" never happened; found during the
        # /impeccable design phase when the ships-only default matched nothing).
        ship_contract_ids = await self._enrich_items_and_find_ships(all_items)

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

        for chunk in _chunk_ids(ship_contract_ids):
            await db_session.execute(
                update(Contract)
                .where(Contract.contract_id.in_(chunk))
                .values(is_ship_contract=True)
            )
        if ship_contract_ids:
            logger.info(f"Flagged {len(ship_contract_ids)} contracts as ship contracts.")

        # item_processing_status must not imply enrichment SUCCESS: a contract
        # whose type/group resolution failed keeps NULL enrichment (the
        # graceful-degrade path), so a future consumer trusting 'COMPLETED' would
        # skip re-enriching a transiently-failed row. Mark COMPLETED only when
        # every fetched item resolved a type_name; the rest are ENRICHMENT_INCOMPLETE.
        incomplete_contract_ids = {
            item["contract_id"] for item in all_items if item.get("type_name") is None
        }
        completed_contract_ids = processed_contract_ids - incomplete_contract_ids
        for chunk in _chunk_ids(completed_contract_ids):
            await db_session.execute(
                update(Contract)
                .where(Contract.contract_id.in_(chunk))
                .values(item_processing_status="COMPLETED")
            )
        for chunk in _chunk_ids(incomplete_contract_ids):
            await db_session.execute(
                update(Contract)
                .where(Contract.contract_id.in_(chunk))
                .values(item_processing_status="ENRICHMENT_INCOMPLETE")
            )
        if incomplete_contract_ids:
            logger.info(
                f"{len(incomplete_contract_ids)} contracts left ENRICHMENT_INCOMPLETE "
                "(item type/group resolution degraded)."
            )

    SHIP_CATEGORY_ID = 6  # EVE static category: Ship

    async def _enrich_items_and_find_ships(self, item_values: List[dict]) -> set:
        """Resolve type -> group -> category for fetched items (ESI static data,
        ETag-cached in Valkey, so repeat runs are near-free), enrich the item
        dicts in place (type_name, market_group_id, category), and return the
        contract_ids whose INCLUDED items contain a ship (EVE category 6).

        Resolution failures degrade gracefully: the item keeps NULL enrichment
        and the contract stays unflagged; the aggregation run never dies here.
        """
        if not item_values:
            return set()

        # Bounded-concurrency fan-out: resolve unique ids through a shared
        # semaphore instead of strictly sequential awaits. Each resolver keeps the
        # per-id try/except + shape guard, so one bad/failed id degrades to NULL
        # enrichment without killing the run — gather never sees an exception.
        semaphore = asyncio.Semaphore(ENRICHMENT_CONCURRENCY)

        async def _resolve(fetch, obj_id: int, kind: str) -> tuple[int, dict | None]:
            async with semaphore:
                try:
                    payload = await fetch(obj_id)
                except Exception as e:
                    logger.warning(f"{kind} resolution failed for {kind.lower()} {obj_id}: {e}")
                    return obj_id, None
            # Shape guard (outside the semaphore): a surprise payload must degrade
            # this one id, never kill the run (this happened live when the
            # list-shaped ETag helper flattened object payloads into keys).
            if isinstance(payload, dict):
                return obj_id, payload
            logger.warning(
                f"Unexpected {kind.lower()} payload shape for {obj_id}: {type(payload).__name__}"
            )
            return obj_id, None

        type_results = await asyncio.gather(
            *(
                _resolve(self.esi_client.get_universe_type, type_id, "Type")
                for type_id in {item["type_id"] for item in item_values}
            )
        )
        type_info: dict[int, dict] = {
            type_id: info for type_id, info in type_results if info is not None
        }

        group_ids = {
            info.get("group_id") for info in type_info.values() if info.get("group_id") is not None
        }
        group_results = await asyncio.gather(
            *(
                _resolve(self.esi_client.get_universe_group, group_id, "Group")
                for group_id in group_ids
            )
        )
        group_info: dict[int, dict] = {
            group_id: group for group_id, group in group_results if group is not None
        }

        ship_contract_ids: set[int] = set()
        for item in item_values:
            info = type_info.get(item["type_id"]) or {}
            group = group_info.get(info.get("group_id")) or {}
            is_ship = group.get("category_id") == self.SHIP_CATEGORY_ID
            # Keys must be uniform across every dict for the bulk upsert.
            item["type_name"] = info.get("name")
            item["market_group_id"] = info.get("market_group_id")
            item["category"] = "ship" if is_ship else None
            if is_ship and item["is_included"]:
                ship_contract_ids.add(item["contract_id"])
        return ship_contract_ids


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
