from typing import Literal, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..db import get_db
from ..models.contracts import Contract
from ..schemas.contracts import PaginatedContractResponse

router = APIRouter(
    prefix="/contracts",
    tags=["Contracts"],
)


@router.get("/", response_model=PaginatedContractResponse)
async def list_public_contracts(
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(20, ge=1, le=100, description="Page size"),
    search: Optional[str] = Query(None, description="Search by title or location name"),
    type: Optional[Literal["item_exchange", "auction"]] = Query(
        None, description="Filter by contract type"
    ),
    sort_by: Optional[Literal["price", "date_issued", "date_expired"]] = Query(
        "date_expired", description="Column to sort by"
    ),
    sort_order: Optional[Literal["asc", "desc"]] = Query(
        "asc", description="Sort order (asc/desc)"
    ),
):
    """
    Lists public contracts with pagination, filtering, and sorting.
    """
    offset = (page - 1) * size

    # Base query for contracts, loading related items efficiently
    query = select(Contract).options(selectinload(Contract.items))

    # Search filter
    if search:
        search_term = f"%{search}%"
        query = query.where(
            (Contract.title.ilike(search_term))
            | (Contract.start_location_name.ilike(search_term))
        )

    # Type filter
    if type:
        query = query.where(Contract.contract_type == type)

    # Sorting logic
    sort_column_map = {
        "price": Contract.price,
        "date_issued": Contract.date_issued,
        "date_expired": Contract.date_expired,
    }

    sort_column = sort_column_map.get(sort_by)

    if sort_column is not None:
        if sort_order == "desc":
            query = query.order_by(sort_column.desc())
        else:
            query = query.order_by(sort_column.asc())

    # Get total count for pagination.
    # We create the count query from the existing query to ensure all filters are applied,
    # then replace the selected columns with a count function.
    count_query = query.with_only_columns(
        func.count(Contract.contract_id)
    ).order_by(None)
    total_count = (await db.execute(count_query)).scalar_one()

    # Get paginated results
    results_query = query.offset(offset).limit(size)
    contracts = (await db.execute(results_query)).scalars().all()

    return {
        "total": total_count,
        "page": page,
        "size": size,
        "items": contracts,
    }
