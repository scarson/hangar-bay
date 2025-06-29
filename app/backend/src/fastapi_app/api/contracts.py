from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..db import get_db
from ..models.contracts import Contract
from ..schemas.common import PaginatedResponse
from ..schemas.contracts import (
    ContractFilters,
    ContractSchema,
)
from ..services.contract_service import get_contracts

router = APIRouter(
    prefix="/contracts",
    tags=["Contracts"],
)


@router.get("/{contract_id}", response_model=ContractSchema)
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

    return contract


@router.get("/", response_model=PaginatedResponse[ContractSchema])
async def list_public_contracts(
    db: AsyncSession = Depends(get_db),
    filters: ContractFilters = Depends(ContractFilters),
):
    """
    Retrieves a paginated list of contracts based on specified filters.

    This endpoint uses a service layer to apply advanced filtering, sorting,
    and pagination to public contracts.
    """
    return await get_contracts(db=db, filters=filters)
