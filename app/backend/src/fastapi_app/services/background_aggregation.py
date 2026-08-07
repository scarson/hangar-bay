import asyncio
import json
import logging
import uuid
from contextlib import asynccontextmanager, AbstractAsyncContextManager
from typing import Iterable, Iterator, List, Callable  # Added Callable
from datetime import datetime, timezone

import redis.asyncio as aioredis  # For on-demand client creation
from sqlalchemy import select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config import Settings  # Settings type for hinting
from ..core.esi_client_class import ESIClient  # ESIClient class for type hint
from ..core.exceptions import ESINotModifiedError  # Restored ESINotModifiedError
from ..core.metrics import last_ingest_success_timestamp

from ..db import AsyncSessionLocal
from ..models.contracts import Contract, ContractItem, EsiTaxonomyCache  # Models
# Removed incorrect import: from ..services.esi_client import ESIClient as ESIClientService
from .db_upsert import bulk_upsert  # Upsert utility

logger = logging.getLogger(__name__)

# Lock key for Redis to ensure only one aggregation job runs at a time.
AGGREGATION_LOCK_KEY = "hangar-bay:aggregation:lock"
# Margin added to the scheduler interval to form the lock TTL (see _lock_ttl_seconds):
# the TTL must strictly exceed the interval so a run that outlasts its own interval
# still holds the lock when the overlapping tick fires, and the margin keeps it held
# through that tick's acquisition attempt.
AGGREGATION_LOCK_TTL_MARGIN_SECONDS = 300
# Freshness record for the last aggregation run (design spec §8.2): JSON
# {finished_at, outcome, regions_ok, regions_failed, last_success_at}, no TTL —
# overwritten each run; lost on cache restart, which self-heals within one tick.
INGEST_LAST_RUN_KEY = "hangar-bay:ingest:last_run"

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

# EVE assigns NPC stations (and the conquerable outposts sharing their ESI route) ids
# in [60,000,000, 64,000,000). GET /v2/universe/stations/ answers for those without a
# token. Player-owned Upwell structures fall outside the range and have no tokenless
# route, so they are never requested: a guaranteed-401 lookup would spend ESI error
# budget (100 errors/60s buys a 420) on a location it still could not resolve.
NPC_STATION_ID_MIN = 60_000_000
NPC_STATION_ID_MAX = 64_000_000

# Bump to re-queue every contract for re-enrichment after an enrichment-logic fix.
# Runbook for a bump: the next run is a one-off full-corpus resweep (~80 min at a
# ~46k corpus), which outlives the aggregation lock TTL — the "Aggregation lock
# token mismatch on release" warning at its end is expected then, not a concurrency
# incident. What actually serializes runs is APScheduler's max_instances=1, safe
# while a run stays under 2x the scheduler interval — so don't deploy again or
# scale out mid-resweep, and re-derive that margin before shortening
# AGGREGATION_SCHEDULER_INTERVAL_SECONDS.
ENRICHMENT_VERSION = 1


def _chunk_ids(ids: Iterable[int]) -> Iterator[list[int]]:
    """Yield id-list slices capped at UPDATE_ID_CHUNK_SIZE (asyncpg bind limit)."""
    id_list = list(ids)
    for start in range(0, len(id_list), UPDATE_ID_CHUNK_SIZE):
        yield id_list[start : start + UPDATE_ID_CHUNK_SIZE]


def _parse_esi_datetime(date_string: str | None) -> datetime | None:
    """Parse ESI's ISO 8601 date strings into datetime objects."""
    if date_string is None:
        return None
    # ESI dates are like "2024-05-20T14:47:32Z". The 'Z' means UTC.
    # fromisoformat handles this correctly if we replace 'Z' with '+00:00'.
    return datetime.fromisoformat(date_string.replace("Z", "+00:00"))


def _collect_resolvable_ids(contracts: List[dict]) -> list[int]:
    """Collect the unique issuer/corporation/location IDs resolvable to names."""
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
    return all_ids_to_resolve


async def _resolve_esi_objects(
    fetch: Callable, obj_ids: Iterable[int], kind: str
) -> dict[int, dict]:
    """Fan single-object ESI lookups out under bounded concurrency, dropping failures.

    Bounded because without it thousands of unique ids resolve as strictly sequential
    round-trips — minutes of added runtime that can also push a run past the lock TTL.
    Each lookup keeps its own try/except and shape guard, so one bad or failing id
    degrades to an absent entry rather than killing the run; gather never sees an
    exception. An absent id means "could not resolve", which callers must not conflate
    with a resolved falsy value.
    """
    semaphore = asyncio.Semaphore(ENRICHMENT_CONCURRENCY)

    async def _resolve(obj_id: int) -> tuple[int, dict | None]:
        async with semaphore:
            try:
                payload = await fetch(obj_id)
            except Exception as e:
                logger.warning(f"{kind} resolution failed for {kind.lower()} {obj_id}: {e}")
                return obj_id, None
        # Shape guard (outside the semaphore): a surprise payload must degrade this
        # one id, never kill the run (this happened live when the list-shaped ETag
        # helper flattened object payloads into keys).
        if isinstance(payload, dict):
            return obj_id, payload
        logger.warning(
            f"Unexpected {kind.lower()} payload shape for {obj_id}: {type(payload).__name__}"
        )
        return obj_id, None

    results = await asyncio.gather(*(_resolve(obj_id) for obj_id in obj_ids))
    return {obj_id: payload for obj_id, payload in results if payload is not None}


# Loose index scan over ix_contract_items_category_id. SELECT DISTINCT category_id
# reads the whole index on a corpus this size (perf audit 2026-08-02 §4 measured the
# equivalent region query at 602 ms; PG18's btree skip scan does not engage), while
# the recursive CTE costs one index probe per distinct category — a set of a few dozen.
# min() ignores NULLs, so items whose taxonomy never resolved drop out on their own.
_OBSERVED_CATEGORY_IDS_SQL = text("""
    WITH RECURSIVE categories(category_id) AS (
        SELECT min(category_id) FROM contract_items
        UNION ALL
        SELECT (SELECT min(category_id) FROM contract_items
                 WHERE category_id > categories.category_id)
        FROM categories WHERE categories.category_id IS NOT NULL
    )
    SELECT category_id FROM categories WHERE category_id IS NOT NULL
""")


async def _observed_category_ids(db_session: AsyncSession) -> set[int]:
    """The distinct dogma categories present on stored contract items.

    Shared by the name-cache writer and the taxonomy endpoint's completeness
    condition so the two cannot drift: both ask what the corpus actually contains,
    rather than what the current batch happens to mention.
    """
    rows = await db_session.execute(_OBSERVED_CATEGORY_IDS_SQL)
    return set(rows.scalars())


def _npc_station_ids(contracts: List[dict]) -> set[int]:
    """The distinct start and end locations /universe/stations/ can answer for."""
    return {
        location_id
        for contract in contracts
        for location_id in (contract.get("start_location_id"), contract.get("end_location_id"))
        if location_id is not None
        and NPC_STATION_ID_MIN <= location_id < NPC_STATION_ID_MAX
    }


def _build_contract_rows(
    contracts: List[dict],
    id_to_name_map: dict,
    station_to_system: dict[int, int] | None = None,
    seen_at: datetime | None = None,
) -> list[dict]:
    """Transform ESI contract payloads into Contract upsert rows, enriched with names.

    Every row carries the SAME seen_at for the whole run: a contract is judged present
    by matching the newest stamp in its region, which only works if one run writes one
    value. The upsert copies mapped columns on conflict, so re-sighting restamps.
    """
    seen_at = seen_at or datetime.now(timezone.utc)
    station_to_system = station_to_system or {}
    return [
        {
            "contract_id": c["contract_id"],
            "issuer_id": c["issuer_id"],
            "issuer_corporation_id": c["issuer_corporation_id"],
            "start_location_id": c.get("start_location_id"),
            # NULL for anything the station route cannot answer for — chiefly
            # player-owned structures. The system_ids filter is honest about that
            # gap rather than silent: the list response publishes how many rows it
            # excluded for want of a system.
            "start_location_system_id": station_to_system.get(c.get("start_location_id")),
            "start_location_region_id": c.get("_hb_region_id"),
            "end_location_id": c.get("end_location_id"),
            "end_location_system_id": station_to_system.get(c.get("end_location_id")),
            "type": c["type"],  # Direct mapping - field names now match
            "status": c.get("status", "unknown"),
            "title": c.get("title"),
            "for_corporation": c.get("for_corporation", False),
            "date_issued": _parse_esi_datetime(c["date_issued"]),
            "date_expired": _parse_esi_datetime(c["date_expired"]),
            "date_completed": _parse_esi_datetime(c.get("date_completed")),
            "price": c.get("price"),
            "collateral": c.get("collateral", 0.0),  # Default to 0.0 if null
            "last_seen_at": seen_at,
            "reward": c.get("reward"),
            "volume": c.get("volume"),
            "buyout": c.get("buyout"),
            "days_to_complete": c.get("days_to_complete"),
            # Denormalized data for search performance
            "start_location_name": id_to_name_map.get(c.get("start_location_id")),
            "end_location_name": id_to_name_map.get(c.get("end_location_id")),
            "issuer_name": id_to_name_map.get(c.get('issuer_id')),
            "issuer_corporation_name": id_to_name_map.get(c.get('issuer_corporation_id')),
            # is_ship_contract, item_processing_status and enrichment_version are
            # deliberately ABSENT: they are maintained by item enrichment, and the
            # upsert copies every mapped column on conflict — including them here
            # decayed ship flags to False whenever items were ETag-304'd and
            # skipped re-enrichment, and would likewise reset a stamped
            # enrichment_version to 0 on every re-sighting, re-queueing the corpus
            # forever. Column defaults cover fresh inserts.
        }
        for c in contracts
    ]


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
        settings: Settings,  # Settings will now be injected
    ):
        # self.session_factory = session_factory # Removed
        # self.cache = cache # Removed cache client attribute
        self.esi_client = esi_client
        self.settings = settings  # Assign the injected settings

    def _lock_ttl_seconds(self) -> int:
        """Mutual-exclusion window for one aggregation run: the scheduler interval
        plus a margin. A fixed TTL shorter than a real run expires mid-run, at which
        point the next tick can legally start a concurrent run — deriving from the
        interval keeps the window ahead of any run the schedule can overlap."""
        return (
            self.settings.AGGREGATION_SCHEDULER_INTERVAL_SECONDS
            + AGGREGATION_LOCK_TTL_MARGIN_SECONDS
        )

    @asynccontextmanager
    async def _concurrency_lock(self):
        """
        An async context manager to handle concurrency locking via Redis.
        Creates its own Redis client on-demand.
        """
        redis_client = aioredis.from_url(str(self.settings.CACHE_URL))
        lock_ttl = self._lock_ttl_seconds()
        # Unique fencing token: the lock value identifies THIS runner so release
        # can verify ownership (see _RELEASE_LOCK_LUA) instead of blindly deleting.
        lock_token = uuid.uuid4().hex
        lock_acquired = False
        try:
            lock_acquired = await redis_client.set(
                AGGREGATION_LOCK_KEY, lock_token, nx=True, ex=lock_ttl
            )
            if not lock_acquired:
                logger.warning("Contract aggregation job is already running. Skipping this run.")
                # Do not raise here, allow the finally to close the client, then re-raise or return
                # For context manager, it's better to let it exit cleanly if lock not acquired.
                # The caller of the context manager should check if the lock was acquired.
                # However, the current design raises, so we'll stick to it but ensure client closes.
                raise ConcurrencyLockError("Could not acquire aggregation lock.")

            logger.info("Concurrency lock acquired for contract aggregation.")
            # The live client is yielded so run-outcome recording (freshness) can
            # happen INSIDE the lock context, before release closes the client.
            yield redis_client  # If this raises, the finally block below still runs
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
                        lock_ttl,
                    )
            await redis_client.close()  # Ensure redis client is closed

    def _usable_region_ids(self) -> List[int] | None:
        """Validate the configured region list, or None when the run must be skipped.

        A non-list (or non-int-element) config is a deployment error and aborts at
        ERROR; an empty list is a benign no-op and skips at WARNING. Both bail out
        before the concurrency lock so a misconfigured deployment cannot occupy the
        lock slot.
        """
        current_region_ids = self.settings.AGGREGATION_REGION_IDS

        if not isinstance(current_region_ids, list) or not all(isinstance(x, int) for x in current_region_ids):
            logger.error(f"CRITICAL_ERROR_AGG_SERVICE: AGGREGATION_REGION_IDS is not a list of int: {current_region_ids!r} (type: {type(current_region_ids)}) Aborting aggregation.")
            return None

        if not current_region_ids:
            logger.warning("AGGREGATION_REGION_IDS is empty. Skipping aggregation.")
            return None

        return current_region_ids

    async def _fetch_regions(self, region_ids: List[int]) -> tuple[List[dict], int, int]:
        """Fetch public contracts for each region, returning (contracts, ok, failed).

        The counters feed the freshness record: a 304 counts as CHECKED OK (ESI
        answered healthily and our data is already current), while a fetch error
        isolates that one region without aborting the others.
        """
        all_contracts_data: List[dict] = []
        regions_ok = 0
        regions_failed = 0

        for region_id in region_ids:
            try:
                contracts_page = await self.esi_client.get_public_contracts(region_id)
                logger.info(f"Fetched {len(contracts_page)} contracts for region {region_id}.")
                # ESI contract payloads carry no region; stamp the
                # fetch region so it survives into the DB (the
                # region_ids filter reads start_location_region_id).
                for contract_data in contracts_page:
                    contract_data["_hb_region_id"] = region_id
                all_contracts_data.extend(contracts_page)
                regions_ok += 1
            except ESINotModifiedError:
                # ESI answered healthily and our data is already
                # current — a 304 region counts as CHECKED OK.
                logger.info(f"Contracts for region {region_id} not modified.")
                regions_ok += 1
            except Exception as e:
                logger.error(f"Failed to fetch contracts for region {region_id}: {e}", exc_info=True)
                regions_failed += 1

        return all_contracts_data, regions_ok, regions_failed

    def _apply_dev_limit(self, contracts: List[dict]) -> List[dict]:
        """Truncate the batch to AGGREGATION_DEV_CONTRACT_LIMIT when one is configured."""
        if self.settings.AGGREGATION_DEV_CONTRACT_LIMIT and self.settings.AGGREGATION_DEV_CONTRACT_LIMIT > 0:
            limit = self.settings.AGGREGATION_DEV_CONTRACT_LIMIT
            if len(contracts) > limit:
                logger.warning(f"DEV_MODE: Limiting contracts to process from {len(contracts)} to {limit}.")
                return contracts[:limit]
        return contracts

    async def run_aggregation(self):
        """
        Runs the full public contract aggregation and ingestion process.
        Uses a database session from the session factory.
        """
        current_region_ids = self._usable_region_ids()
        if current_region_ids is None:
            return

        try:
            async with self._concurrency_lock() as redis_client:  # Handles concurrent job runs
                regions_ok = 0
                regions_failed = 0
                try:
                    # Use the ESIClient as a context manager to ensure its http_client is initialized.
                    async with self.esi_client:
                        logger.info("Concurrency lock acquired. Starting public contract aggregation run.")

                        async with AsyncSessionLocal() as db_session:  # Obtain a new session for this run
                            logger.info(f"Processing contracts for region IDs: {current_region_ids}")

                            all_contracts_data, regions_ok, regions_failed = await self._fetch_regions(
                                current_region_ids
                            )

                            if not all_contracts_data:
                                logger.info("No new contracts found across all specified regions.")
                                # No need to commit or process further if no data was fetched.
                            else:
                                all_contracts_data = self._apply_dev_limit(all_contracts_data)

                                await self._process_contracts(db_session, all_contracts_data)

                                await db_session.commit()
                                logger.info("Public contract aggregation run finished successfully and changes committed.")

                    # The shared transaction committed (or completed as a valid
                    # no-op — the all-304 path); outcome derives from the counters.
                    await self._record_run_outcome(redis_client, regions_ok, regions_failed)
                except Exception:
                    # Any processing/commit/top-level abort is a failed run no matter
                    # what the fetch counters say; record while the lock is still held.
                    await self._record_run_outcome(
                        redis_client, regions_ok, regions_failed, forced_failure=True
                    )
                    raise

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

    async def _record_run_outcome(self, redis_client, ok: int, failed: int, *, forced_failure: bool = False) -> None:
        """Write the freshness record (INGEST_LAST_RUN_KEY) and advance the success gauge.

        last_success_at survives failure records unchanged so staleness is always
        measured against the last real refresh. A failure of the outcome WRITE itself
        is logged and swallowed — freshness recording must never turn a successful
        ingest into a failed job.
        """
        try:
            if forced_failure:
                outcome = "failure"
            else:
                outcome = "success" if failed == 0 and ok > 0 else ("partial" if ok > 0 else "failure")
            now = datetime.now(timezone.utc).isoformat()
            prior_raw = await redis_client.get(INGEST_LAST_RUN_KEY)
            prior_success = None
            if prior_raw:
                try:
                    prior_record = json.loads(prior_raw)
                    # Valid-but-non-object JSON (null, [], "str") is corrupt: treat as
                    # no-prior so this SET repairs the key instead of raising forever.
                    if isinstance(prior_record, dict):
                        prior_success = prior_record.get("last_success_at")
                except (ValueError, TypeError):
                    prior_success = None
            last_success_at = now if outcome in ("success", "partial") else prior_success
            await redis_client.set(INGEST_LAST_RUN_KEY, json.dumps({
                "finished_at": now,
                "outcome": outcome,
                "regions_ok": ok,
                "regions_failed": failed,
                "last_success_at": last_success_at,
            }))
            if outcome in ("success", "partial"):
                last_ingest_success_timestamp.set_to_current_time()
        except Exception:
            logger.warning("failed to record ingest outcome", exc_info=True)

    async def _process_contracts(self, db_session: AsyncSession, contracts: List[dict]):
        """
        Processes a list of contracts, fetches their items, and upserts them using the provided db_session.
        """
        # Step 1: Collect all unique IDs from the current batch of contracts.
        all_ids_to_resolve = _collect_resolvable_ids(contracts)

        # Step 2: Resolve all IDs to names in a single batch operation.
        id_to_name_map = {}
        if all_ids_to_resolve:
            logger.info(f"Resolving {len(all_ids_to_resolve)} unique IDs to names.")
            id_to_name_map = await self.esi_client.resolve_ids_to_names(all_ids_to_resolve)
            logger.info(f"Successfully resolved {len(id_to_name_map)} names.")

        # Step 3: Resolve start locations to solar systems, then transform contracts
        # into the format for the database model, enriching with names and systems.
        station_to_system = await self._resolve_station_systems(db_session, contracts)
        contract_values = _build_contract_rows(contracts, id_to_name_map, station_to_system)

        batch_size = 500  # Number of contracts to process in each batch
        total_contracts = len(contract_values)
        logger.info(f"Upserting {total_contracts} contracts in batches of {batch_size}.")

        for i in range(0, total_contracts, batch_size):
            batch = contract_values[i:i + batch_size]
            logger.info(f"Processing batch {i // batch_size + 1}/{(total_contracts + batch_size - 1) // batch_size} ({len(batch)} contracts)")
            await bulk_upsert(db_session, Contract, batch)
            logger.info(f"Successfully upserted batch {i // batch_size + 1}.")

        logger.info(f"Finished upserting all {total_contracts} contracts.")

        already_enriched = await self._select_already_enriched(db_session, contracts)

        all_items, processed_contract_ids = await self._fetch_item_rows(
            contracts, already_enriched
        )
        # Counts the EFFECT, not the intent: a skip that silently stopped working still
        # reports what it meant to skip, so the fetched count is what the log has to
        # carry for the run to be verifiable from its output alone.
        logger.info(
            f"Fetched items for {len(processed_contract_ids)} contracts "
            f"({len(already_enriched)} skipped as already enriched)."
        )

        # Enrich items with static type data BEFORE upserting so a single
        # write carries names/categories, and collect which contracts hold an
        # included ship (fills the gap that left is_ship_contract permanently
        # False — "will be updated later" never happened; found during the
        # /impeccable design phase when the ships-only default matched nothing).
        ship_contract_ids, unresolved_category_contract_ids, group_info = (
            await self._enrich_items_and_find_ships(all_items)
        )
        await self._upsert_taxonomy_names(db_session, group_info)

        if all_items:
            logger.info(f"Preparing to upsert {len(all_items)} contract items in batches.")
            BATCH_SIZE = 50  # Number of items to process in each batch
            for i in range(0, len(all_items), BATCH_SIZE):
                batch_items = all_items[i:i + BATCH_SIZE]
                logger.info(f"Upserting batch of {len(batch_items)} contract items (items {i + 1}-{i + len(batch_items)} of {len(all_items)}).")
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

        await self._update_item_processing_status(
            db_session,
            processed_contract_ids,
            all_items,
            ship_contract_ids,
            unresolved_category_contract_ids,
        )

    async def _resolve_station_systems(
        self, db_session: AsyncSession, contracts: List[dict]
    ) -> dict[int, int]:
        """Map the batch's NPC stations — start and end alike — to their solar system ids.

        ESI's public contract payload carries a location id and no system id, so
        without this the system_ids filter has nothing to match. Station→system is
        static universe data: a pair resolved once is correct forever, which is why
        pairs already stored on contract rows are read back instead of re-fetched.

        Structures are absent from the result and their contracts keep a NULL system
        (see NPC_STATION_ID_MIN/MAX). A station whose lookup fails is likewise absent
        and gets retried next run, since no pair for it lands in the table.
        """
        station_ids = _npc_station_ids(contracts)
        if not station_ids:
            return {}

        station_to_system = await self._select_known_station_systems(db_session, station_ids)
        unresolved = station_ids - station_to_system.keys()
        if not unresolved:
            return station_to_system

        payloads = await _resolve_esi_objects(
            self.esi_client.get_universe_station, unresolved, "Station"
        )
        for station_id, payload in payloads.items():
            # ESI omits fields rather than sending falsy ones (pitfall ESI-3), so an
            # absent system_id means unresolved — not system 0.
            system_id = payload.get("system_id")
            if system_id is not None:
                station_to_system[station_id] = system_id

        logger.info(
            f"Resolved {len(payloads)} new station→system pairs "
            f"({len(station_ids) - len(unresolved)} already known)."
        )
        return station_to_system

    async def _select_known_station_systems(
        self, db_session: AsyncSession, station_ids: set[int]
    ) -> dict[int, int]:
        """Station→system pairs already recorded on stored contracts, in either role.

        Makes the contracts table its own durable cache for a lookup whose answer never
        changes, so steady state costs zero station requests. It is also what keeps an
        ESI outage from blanking the filter: the upsert copies every supplied column on
        conflict, so a run that re-resolved from scratch and came back empty would write
        NULL over every system the site already knew — the same decay that ETag-304s once
        inflicted on is_ship_contract. Both the start and the end column pair are read
        back for exactly that reason: a station known only as some contract's destination
        would otherwise be re-fetched forever, and blanked whenever the fetch failed.
        """
        known: dict[int, int] = {}
        for chunk in _chunk_ids(station_ids):
            for location_column, system_column in (
                (Contract.start_location_id, Contract.start_location_system_id),
                (Contract.end_location_id, Contract.end_location_system_id),
            ):
                rows = await db_session.execute(
                    select(location_column, system_column)
                    .where(
                        location_column.in_(chunk),
                        system_column.is_not(None),
                    )
                    .distinct()
                )
                known.update({station_id: system_id for station_id, system_id in rows})
        return known

    async def _select_already_enriched(
        self, db_session: AsyncSession, contracts: List[dict]
    ) -> set[int]:
        """Return the contract IDs already enriched at the current ENRICHMENT_VERSION.

        Public contracts are immutable, so a contract already enriched at the current
        version never needs re-fetching. This is what turns a corpus-sized run into a
        churn-sized one. Reads back the status column that enrichment writes; a
        contract at any other status (PENDING_ITEMS from a failed fetch,
        ENRICHMENT_INCOMPLETE from degraded type resolution) is still re-fetched, so
        transient failures keep recovering on the next run.
        """
        already_enriched: set[int] = set()
        for chunk in _chunk_ids(c["contract_id"] for c in contracts):
            rows = await db_session.execute(
                select(Contract.contract_id).where(
                    Contract.contract_id.in_(chunk),
                    Contract.item_processing_status == "COMPLETED",
                    Contract.enrichment_version == ENRICHMENT_VERSION,
                )
            )
            already_enriched.update(rows.scalars())
        return already_enriched

    async def _fetch_item_rows(
        self, contracts: List[dict], already_enriched: set[int]
    ) -> tuple[list[dict], set[int]]:
        """Fetch contract items from ESI, returning the item rows and the contract IDs reached.

        A per-contract fetch failure is isolated: that contract is left out of the
        processed set and the run continues. Contracts in already_enriched are not
        fetched at all, and are likewise absent from the processed set — the status
        bookkeeping keys off that set, so their existing COMPLETED status stands.
        """
        all_items: List[dict] = []
        processed_contract_ids: set[int] = set()
        for contract in contracts:
            if contract["type"] not in ["item_exchange", "auction"]:
                continue
            if contract["contract_id"] in already_enriched:
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
                        # Blueprint stats and the dynamic-item join key. A blueprint
                        # ORIGINAL omits `runs` rather than sending a sentinel, so
                        # absence must stay NULL (ESI-3).
                        "runs": i.get("runs"),
                        "material_efficiency": i.get("material_efficiency"),
                        "time_efficiency": i.get("time_efficiency"),
                        "item_id": i.get("item_id"),
                    }
                    for i in items
                ]
                all_items.extend(item_values)
            except ESINotModifiedError:
                logger.info(f"Items for contract {contract['contract_id']} not modified.")
            except Exception as e:
                logger.error(f"Failed to fetch items for contract {contract['contract_id']}: {e}", exc_info=True)

        return all_items, processed_contract_ids

    async def _update_item_processing_status(
        self,
        db_session: AsyncSession,
        processed_contract_ids: set[int],
        all_items: list[dict],
        ship_contract_ids: set[int],
        unresolved_category_contract_ids: set[int],
    ) -> None:
        """Record per-contract item enrichment outcome on the Contract rows."""
        # item_processing_status must not imply enrichment SUCCESS: a contract
        # whose type/group resolution failed keeps NULL enrichment (the
        # graceful-degrade path), so a future consumer trusting 'COMPLETED' would
        # skip re-enriching a transiently-failed row. Mark COMPLETED only when every
        # fetched item resolved a type_name AND a category; the rest are
        # ENRICHMENT_INCOMPLETE. An unresolved category is a half-done enrichment
        # exactly like an unresolved type — it decides the ship flag and the
        # per-category rendering of both contract sides — and stamping it COMPLETED
        # would hand it to the skip, which withholds it from every later run:
        # silently unenriched with no route back.
        incomplete_contract_ids = {
            item["contract_id"] for item in all_items if item.get("type_name") is None
        } | unresolved_category_contract_ids
        # A contract that produced NO items cannot have succeeded: item_exchange and
        # auction contracts always carry at least one item. Excluding it from the
        # COMPLETED set means it is not recorded as successfully enriched, so it
        # remains in the re-fetch set. COMPLETED must mean the items were actually
        # fetched; a zero-item result must not claim success.
        contracts_with_items = {item["contract_id"] for item in all_items}
        empty_contract_ids = processed_contract_ids - contracts_with_items
        completed_contract_ids = (
            processed_contract_ids - incomplete_contract_ids - empty_contract_ids
        )
        for chunk in _chunk_ids(completed_contract_ids):
            await db_session.execute(
                update(Contract)
                .where(Contract.contract_id.in_(chunk))
                .values(
                    item_processing_status="COMPLETED",
                    enrichment_version=ENRICHMENT_VERSION,
                )
            )
        # A completed contract's ship verdict is authoritative in BOTH directions, so
        # it may clear the flag as well as set it: without this the flag is monotonic
        # and a false positive from a past enrichment bug survives every re-enrichment,
        # which is precisely what an ENRICHMENT_VERSION bump is meant to repair.
        # "Could not tell" never reaches here to begin with: an unresolved category
        # makes the contract incomplete above, and completed excludes incomplete. That
        # is what keeps a degraded group lookup — which reads as "not a ship" while the
        # type_name still resolves — from stripping correct flags off the ships-only
        # default view during an ESI blip.
        non_ship_completed = completed_contract_ids - ship_contract_ids
        for chunk in _chunk_ids(non_ship_completed):
            await db_session.execute(
                update(Contract)
                .where(Contract.contract_id.in_(chunk))
                .values(is_ship_contract=False)
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
                "(item type or category resolution degraded)."
            )
        if empty_contract_ids:
            logger.warning(
                f"{len(empty_contract_ids)} contracts returned zero items and were not "
                "marked COMPLETED (an item_exchange/auction contract cannot be empty); "
                "they stay in the item re-fetch set."
            )

    async def _upsert_taxonomy_names(
        self, db_session: AsyncSession, group_info: dict[int, dict]
    ) -> None:
        """Persist dogma names for the taxonomy option list (spec §5.2).

        Group names ride payloads enrichment already fetched. Category names need
        the one ESI call this feature adds — issued cache-first, because the set is
        tiny and immutable, so steady state fetches zero categories.

        The categories considered are this run's PLUS every category observed on
        stored items that has no cache row yet. That second source is what makes the
        cache self-healing: a contract stamped COMPLETED is withheld from the item
        re-fetch, so its group payload never reaches this writer again, and a
        category whose first name fetch failed would otherwise stay nameless until
        some unrelated contract happened to carry it.
        """
        now = datetime.now(timezone.utc)
        group_rows = [
            {"kind": "group", "esi_id": group_id, "name": info["name"],
             "parent_category_id": info.get("category_id"), "fetched_at": now}
            for group_id, info in group_info.items()
            if info.get("name") is not None
        ]
        if group_rows:
            await bulk_upsert(db_session, EsiTaxonomyCache, group_rows)

        category_ids = {
            info["category_id"] for info in group_info.values()
            if info.get("category_id") is not None
        }
        category_ids |= await _observed_category_ids(db_session)
        if not category_ids:
            return
        cached = set((await db_session.execute(
            select(EsiTaxonomyCache.esi_id).where(
                EsiTaxonomyCache.kind == "category",
                EsiTaxonomyCache.esi_id.in_(sorted(category_ids)),
            )
        )).scalars())
        missing = category_ids - cached
        if not missing:
            return
        payloads = await _resolve_esi_objects(
            self.esi_client.get_universe_category, missing, "Category"
        )
        category_rows = [
            {"kind": "category", "esi_id": category_id, "name": payload["name"],
             "parent_category_id": None, "fetched_at": now}
            for category_id, payload in payloads.items()
            if payload.get("name") is not None
        ]
        if category_rows:
            await bulk_upsert(db_session, EsiTaxonomyCache, category_rows)

    SHIP_CATEGORY_ID = 6  # EVE static category: Ship

    async def _enrich_items_and_find_ships(
        self, item_values: List[dict]
    ) -> tuple[set[int], set[int], dict[int, dict]]:
        """Resolve type -> group -> category for fetched items (ESI static data,
        ETag-cached in Valkey, so repeat runs are near-free), enrich the item
        dicts in place (type_name, market_group_id, category), and return
        (ship_contract_ids, unresolved_category_contract_ids, group_info): the
        contract_ids whose INCLUDED items contain a ship (EVE category 6), those
        with ANY item whose category could not be determined, and the group
        payloads this run resolved, keyed by group_id.

        Resolution failures degrade gracefully: the item keeps NULL enrichment
        and the contract stays unflagged; the aggregation run never dies here.
        The second set is what keeps "not a ship" distinguishable from "we could
        not tell" — only the former may clear an existing flag. The third value
        carries the group names and owning categories on to the name cache, which
        would otherwise need a second fan-out over the same ids.
        """
        if not item_values:
            return set(), set(), {}

        type_info = await _resolve_esi_objects(
            self.esi_client.get_universe_type,
            {item["type_id"] for item in item_values},
            "Type",
        )

        group_ids = {
            info.get("group_id") for info in type_info.values() if info.get("group_id") is not None
        }
        group_info = await _resolve_esi_objects(
            self.esi_client.get_universe_group, group_ids, "Group"
        )

        ship_contract_ids: set[int] = set()
        unresolved_category_contract_ids: set[int] = set()
        for item in item_values:
            info = type_info.get(item["type_id"]) or {}
            group = group_info.get(info.get("group_id")) or {}
            is_ship = group.get("category_id") == self.SHIP_CATEGORY_ID
            # Keys must be uniform across every dict for the bulk upsert.
            item["type_name"] = info.get("name")
            item["market_group_id"] = info.get("market_group_id")
            item["category"] = "ship" if is_ship else None
            # The taxonomy ids the ship flag already walked past, kept for the
            # category/group filter families. No extra ESI call: both payloads
            # are in hand.
            item["group_id"] = info.get("group_id")
            item["category_id"] = group.get("category_id")
            # Only INCLUDED items decide the flag, so only they classify the contract.
            if is_ship and item["is_included"]:
                ship_contract_ids.add(item["contract_id"])
            # A NULL category_id means the category is UNKNOWN, not "not a ship": the
            # group fetch failed, the payload arrived without a category_id, or the
            # type carried no group_id. Testing the resolved value rather than the
            # group dict is what covers that middle shape — a non-empty group payload
            # missing category_id would otherwise read as success and stamp the
            # contract COMPLETED with a permanently NULL category.
            # Every item counts here, included or not: the requested side is rendered
            # and summarized by category, so a NULL there is a blank half of the
            # contract, not a missing badge. The ship-flag branch above stays
            # offered-only — only included items decide what the contract IS.
            elif item["category_id"] is None:
                unresolved_category_contract_ids.add(item["contract_id"])
        return ship_contract_ids, unresolved_category_contract_ids, group_info
