import asyncio
from sqlalchemy import func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from ..models.contracts import Contract, ContractItem
from ..schemas.contracts import (
    ContractFilters,
    PaginatedContractResponse,
    SortDirection,
    ContractSchema,
)


async def get_contracts(
    db: AsyncSession, filters: ContractFilters
) -> PaginatedContractResponse:
    """
    Retrieves a paginated list of contracts based on specified filters.

    This function constructs a single, dynamic query to handle searching,
    filtering, sorting, and pagination. It addresses the complexity of
    conditionally joining the ContractItem table and ensuring correct counts
    when one-to-many relationships are involved.
    """
    # Start with the base query for the Contract model.
    query = select(Contract)

    # Determine if a JOIN on the ContractItem table is necessary. A join is
    # required if we need to filter on item attributes (name, type_id, bpc status).
    needs_item_join = (
        filters.search or filters.type_ids or filters.is_bpc is not None
    )

    if needs_item_join:
        query = query.join(ContractItem)

    # --- Apply Filters ---
    # Each filter is applied to the query object, narrowing the results.

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

    # 3. Location filters
    if filters.region_ids:
        query = query.filter(Contract.start_location_region_id.in_(filters.region_ids))
    if filters.system_ids:
        query = query.filter(Contract.start_location_system_id.in_(filters.system_ids))
    if filters.station_ids:
        query = query.filter(Contract.start_location_id.in_(filters.station_ids))

    # 4. Contract Item specific filters
    if filters.type_ids:
        query = query.filter(ContractItem.type_id.in_(filters.type_ids))
    if filters.is_bpc is not None:
        query = query.filter(ContractItem.is_blueprint_copy == filters.is_bpc)

    # --- Count Query ---
    # To get an accurate total count of matching *contracts* (not items),
    # we must count the distinct contract_ids from our filtered query.
    # This is crucial because the join can create duplicate contract rows.
    count_subquery = select(query.subquery().c.contract_id).distinct().subquery()
    count_query = select(func.count()).select_from(count_subquery)
    
    total_result = await db.execute(count_query)
    total = total_result.scalar_one()

    if total == 0:
        return PaginatedContractResponse(total=0, page=filters.page, size=filters.size, items=[])

    # --- Data Query ---
    # Now, apply sorting and pagination to the filtered query to get the
    # specific page of results.
    sort_column = getattr(Contract, filters.sort_by.value)
    if filters.sort_direction == SortDirection.desc:
        sort_column = sort_column.desc()

    data_query = (
        query
        .order_by(sort_column)
        .offset((filters.page - 1) * filters.size)
        .limit(filters.size)
        .options(selectinload(Contract.items))
        .distinct()  # Use distinct to prevent duplicate contracts in the final result set
    )

    result = await db.execute(data_query)
    contracts = result.scalars().all()

    return PaginatedContractResponse(
        total=total,
        page=filters.page,
        size=filters.size,
        items=[ContractSchema.model_validate(c) for c in contracts],
    )
