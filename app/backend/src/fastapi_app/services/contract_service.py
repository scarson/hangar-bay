import asyncio
import time
from sqlalchemy import func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from ..core.logging import get_logger, log_key_event
from ..models.contracts import Contract, ContractItem
from ..schemas.common import PaginatedResponse
from ..schemas.contracts import (
    ContractFilters,
    SortDirection,
    ContractSchema,
    SortableContractFields,
)

# Initialize logger for this module
logger = get_logger(__name__)

# This SORT_MAP is a critical security feature. It prevents arbitrary column sorting
# by mapping API-facing sort keys to the actual, safe SQLAlchemy model columns.
SORT_MAP = {
    SortableContractFields.date_issued: Contract.date_issued,
    SortableContractFields.date_expired: Contract.date_expired,
    SortableContractFields.price: Contract.price,
    SortableContractFields.collateral: Contract.collateral,
    SortableContractFields.volume: Contract.volume,
    # Note: Sorting by ship_name joins the items table.
    SortableContractFields.ship_name: ContractItem.type_name,
}


def _needs_item_join(filters: ContractFilters) -> bool:
    """
    Determine if a JOIN on the ContractItem table is necessary. A join is
    required if we need to filter or sort on item attributes.
    """
    return bool(
        filters.search
        or filters.type_ids
        or filters.is_bpc is not None
        or filters.min_runs is not None
        or filters.max_runs is not None
        # Add sorting by ship name to the condition
        or filters.sort_by == SortableContractFields.ship_name
    )


def _apply_contract_filters(query, filters: ContractFilters):
    """Apply the contract-level filters, narrowing the results."""
    # 1. Text search (on contract title or item name)
    if filters.search:
        search_term = f"%{filters.search}%"
        # This OR condition requires the join to be present.
        query = query.filter(
            or_(
                Contract.title.ilike(search_term),
                ContractItem.type_name.ilike(search_term),
            )
        )

    # 2. Price and Collateral filters
    if filters.min_price is not None:
        query = query.filter(Contract.price >= filters.min_price)
    if filters.max_price is not None:
        query = query.filter(Contract.price <= filters.max_price)
    if filters.min_collateral is not None:
        query = query.filter(Contract.collateral >= filters.min_collateral)
    if filters.max_collateral is not None:
        query = query.filter(Contract.collateral <= filters.max_collateral)

    # 2b. Contract-level flags (indexed column; no item join required)
    if filters.is_ship_contract is not None:
        query = query.filter(Contract.is_ship_contract == filters.is_ship_contract)

    # 3. Location filters
    if filters.region_ids:
        query = query.filter(Contract.start_location_region_id.in_(filters.region_ids))
    if filters.system_ids:
        query = query.filter(Contract.start_location_system_id.in_(filters.system_ids))
    if filters.station_ids:
        query = query.filter(Contract.start_location_id.in_(filters.station_ids))

    return query


def _apply_item_filters(query, filters: ContractFilters):
    """Apply the Contract Item specific filters."""
    if filters.type_ids:
        query = query.filter(ContractItem.type_id.in_(filters.type_ids))
    if filters.is_bpc is not None:
        query = query.filter(ContractItem.is_blueprint_copy == filters.is_bpc)
    # BPC Run filters (Note: ME/TE not implemented as data is not in model)
    if filters.min_runs is not None:
        query = query.filter(ContractItem.raw_quantity >= filters.min_runs)
    if filters.max_runs is not None:
        query = query.filter(ContractItem.raw_quantity <= filters.max_runs)

    return query


async def _count_distinct_contracts(db: AsyncSession, query) -> int:
    """
    To get an accurate total count of matching *contracts* (not items),
    we must count the distinct contract_ids from our filtered query.
    This is crucial because the join can create duplicate contract rows.
    """
    count_subquery = select(query.subquery().c.contract_id).distinct().subquery()
    count_query = select(func.count()).select_from(count_subquery)

    total_result = await db.execute(count_query)
    return total_result.scalar_one()


async def _fetch_page_joined(
    db: AsyncSession,
    query,
    filters: ContractFilters,
    sort_column,
    descending: bool,
) -> list[Contract]:
    # Paginating the joined query directly would offset/limit over
    # joined (duplicated) rows, producing short pages and contracts
    # skipped or repeated across page boundaries. Paginate over
    # distinct contract IDs first, then load that page's contracts.
    # Ordering uses an aggregate of the sort column (min/max picks
    # the sort-direction-appropriate representative when a contract
    # has multiple items) with contract_id as a deterministic
    # tiebreaker.
    sort_aggregate = func.max(sort_column) if descending else func.min(sort_column)
    order_expr = sort_aggregate.desc() if descending else sort_aggregate.asc()
    id_query = (
        query.with_only_columns(Contract.contract_id)
        .group_by(Contract.contract_id)
        .order_by(order_expr, Contract.contract_id.asc())
        .offset((filters.page - 1) * filters.size)
        .limit(filters.size)
    )
    id_result = await db.execute(id_query)
    page_ids = [row[0] for row in id_result.all()]

    data_query = (
        select(Contract)
        .where(Contract.contract_id.in_(page_ids))
        .options(selectinload(Contract.items))
    )
    result = await db.execute(data_query)
    contracts = list(result.scalars().unique().all())
    # Restore the page order computed by id_query.
    position = {cid: index for index, cid in enumerate(page_ids)}
    contracts.sort(key=lambda contract: position[contract.contract_id])
    return contracts


async def _fetch_page_simple(
    db: AsyncSession,
    query,
    filters: ContractFilters,
    sort_column,
    descending: bool,
) -> list[Contract]:
    order_expr = sort_column.desc() if descending else sort_column.asc()
    data_query = (
        query.order_by(order_expr, Contract.contract_id.asc())
        .offset((filters.page - 1) * filters.size)
        .limit(filters.size)
        .options(selectinload(Contract.items))
    )
    result = await db.execute(data_query)
    return result.scalars().unique().all()


async def get_contracts(
    db: AsyncSession, filters: ContractFilters
) -> PaginatedResponse[ContractSchema]:
    """
    Retrieves a paginated list of contracts based on specified filters.

    This function constructs a single, dynamic query to handle searching,
    filtering, sorting, and pagination. It addresses the complexity of
    conditionally joining the ContractItem table and ensuring correct counts
    when one-to-many relationships are involved.
    """
    start_time = time.time()

    # Log the start of the contract search operation
    logger.info(
        "Starting contract search",
        search_terms={
            "search": filters.search,
            "type_ids": filters.type_ids,
            "min_price": filters.min_price,
            "max_price": filters.max_price,
            "page": filters.page,
            "size": filters.size,
            "sort_by": filters.sort_by.value if filters.sort_by else None,
            "sort_direction": filters.sort_direction.value if filters.sort_direction else None,
        }
    )

    try:
        # Start with the base query for the Contract model.
        query = select(Contract)

        needs_item_join = _needs_item_join(filters)

        if needs_item_join:
            # Use an outer join to ensure contracts without items are not excluded
            # unless specifically filtered out.
            query = query.outerjoin(ContractItem)

        # --- Apply Filters ---
        # Each filter is applied to the query object, narrowing the results.
        query = _apply_contract_filters(query, filters)
        query = _apply_item_filters(query, filters)

        # --- Count Query ---
        total = await _count_distinct_contracts(db, query)

        if total == 0:
            duration_ms = (time.time() - start_time) * 1000
            log_key_event(
                logger=logger,
                event="contract_search_executed",
                success=True,
                duration_ms=duration_ms,
                results_count=0,
                search_terms={
                    "search": filters.search,
                    "type_ids": filters.type_ids,
                    "page": filters.page,
                    "size": filters.size,
                }
            )
            return PaginatedResponse(total=0, page=filters.page, size=filters.size, items=[])

        # --- Data Query ---
        # Apply sorting and pagination to get the specific page of results.
        sort_column = SORT_MAP.get(filters.sort_by)
        if sort_column is None:
            # Fallback to default or raise an error for an unsupported sort key
            sort_column = Contract.date_issued

        descending = filters.sort_direction == SortDirection.desc

        if needs_item_join:
            contracts = await _fetch_page_joined(db, query, filters, sort_column, descending)
        else:
            contracts = await _fetch_page_simple(db, query, filters, sort_column, descending)

        # Calculate duration and log successful completion
        duration_ms = (time.time() - start_time) * 1000

        response = PaginatedResponse(
            total=total,
            page=filters.page,
            size=filters.size,
            items=[ContractSchema.model_validate(c) for c in contracts],
        )

        # Log successful contract search with key event schema
        log_key_event(
            logger=logger,
            event="contract_search_executed",
            success=True,
            duration_ms=duration_ms,
            results_count=len(contracts),
            search_terms={
                "search": filters.search,
                "type_ids": filters.type_ids,
                "min_price": filters.min_price,
                "max_price": filters.max_price,
                "page": filters.page,
                "size": filters.size,
                "sort_by": filters.sort_by.value if filters.sort_by else None,
                "sort_direction": filters.sort_direction.value if filters.sort_direction else None,
            }
        )

        return response

    except Exception as e:
        # Calculate duration and log failure
        duration_ms = (time.time() - start_time) * 1000

        log_key_event(
            logger=logger,
            event="contract_search_executed",
            success=False,
            duration_ms=duration_ms,
            error_message=str(e),
            search_terms={
                "search": filters.search,
                "type_ids": filters.type_ids,
                "min_price": filters.min_price,
                "max_price": filters.max_price,
                "page": filters.page,
                "size": filters.size,
            }
        )

        # Re-raise the exception to maintain existing error handling behavior
        raise
