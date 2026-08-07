from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..db import get_db
from ..models.contracts import Contract
from ..schemas.contracts import (
    ContractDetailSchema,
    ContractFilters,
    ContractListResponse,
    TaxonomyResponse,
)
from ..services.contract_service import (
    _category_names,
    _detail_item,
    get_contracts,
    get_taxonomy,
)

router = APIRouter(
    prefix="/contracts",
    tags=["Contracts"],
)


# This route must be defined BEFORE the /{contract_id} route.
# FastAPI matches routes in order, so a request to /ships would otherwise
# be incorrectly captured by the /{contract_id} route, leading to a
# validation error trying to parse "ships" as an integer.
@router.get("/", response_model=ContractListResponse)
async def list_public_contracts(
    filters: Annotated[ContractFilters, Query()],
    db: AsyncSession = Depends(get_db),
):
    """
    Retrieves a paginated list of contracts based on specified filters.

    This endpoint uses a service layer to apply advanced filtering, sorting,
    and pagination to public contracts.
    """
    return await get_contracts(db=db, filters=filters)


# Subject to the same ordering rule as the route above: defined BEFORE
# /{contract_id}, or "taxonomy" is parsed as a contract id and the request 422s.
@router.get("/taxonomy", response_model=TaxonomyResponse)
async def list_contract_taxonomy(
    db: AsyncSession = Depends(get_db),
):
    """
    Retrieves the dogma category and group option lists for the item-level filters,
    with a readiness signal saying whether those filters can be trusted yet.
    """
    return await get_taxonomy(db=db)


@router.get("/{contract_id}", response_model=ContractDetailSchema)
async def get_contract(
    contract_id: int,
    db: AsyncSession = Depends(get_db),
):
    """
    Retrieves a single contract by its ID, including its items.
    """
    query = (
        select(Contract)
        .where(Contract.contract_id == contract_id)
        .options(selectinload(Contract.items))
    )
    result = await db.execute(query)
    contract = result.scalar_one_or_none()

    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found")

    # The same category-name lookup the list path uses: composition is derived here
    # too, and without the names every category on the detail page reads as null.
    return _detail_item(contract, await _category_names(db))
