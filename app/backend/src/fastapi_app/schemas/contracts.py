from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class ContractItemSchema(BaseModel):
    """Schema for an item within a contract."""
    record_id: int
    type_id: int
    quantity: int
    is_included: bool
    is_singleton: bool
    raw_quantity: Optional[int] = None
    type_name: Optional[str] = None
    category: Optional[str] = None
    market_group_id: Optional[int] = None

    class Config:
        from_attributes = True


class ContractSchema(BaseModel):
    """Schema for a public contract."""
    contract_id: int
    issuer_id: int
    issuer_corporation_id: int
    start_location_id: int
    end_location_id: Optional[int] = None
    type: str
    status: str
    title: Optional[str] = None
    for_corporation: bool
    date_issued: datetime
    date_expired: datetime
    date_completed: Optional[datetime] = None
    price: Optional[float] = None
    reward: Optional[float] = None
    volume: Optional[float] = None
    start_location_name: Optional[str] = None
    issuer_name: Optional[str] = None
    issuer_corporation_name: Optional[str] = None
    is_ship_contract: bool
    items: List[ContractItemSchema] = []

    class Config:
        from_attributes = True


class PaginatedContractResponse(BaseModel):
    """Schema for a paginated response of contracts."""
    total: int = Field(..., description="Total number of contracts matching the query.")
    page: int = Field(..., description="The current page number.")
    size: int = Field(..., description="The number of items per page.")
    items: List[ContractSchema] = Field(..., description="The list of contracts for the current page.")
