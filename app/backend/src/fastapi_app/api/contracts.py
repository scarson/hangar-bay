from typing import Optional

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
):
    """
    Lists public contracts with pagination and optional search.
    """
    offset = (page - 1) * size

    # Base query for contracts, loading related items efficiently
    query = select(Contract).options(selectinload(Contract.items))

    # Search filter
    if search:
        search_term = f"%{search}%"
        query = query.where(
            (Contract.title.ilike(search_term)) |
            (Contract.start_location_name.ilike(search_term))
        )

    # Get total count for pagination
    count_query = select(func.count()).select_from(query.subquery())
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
