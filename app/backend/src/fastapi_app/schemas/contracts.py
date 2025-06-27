from datetime import datetime
from enum import Enum
from typing import List, Optional

from fastapi import Query
from pydantic import BaseModel, ConfigDict, Field


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

    model_config = ConfigDict(from_attributes=True)


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

    model_config = ConfigDict(from_attributes=True)


class PaginatedContractResponse(BaseModel):
    """Schema for a paginated response of contracts."""

    total: int = Field(..., description="Total number of contracts matching the query.")
    page: int = Field(..., description="The current page number.")
    size: int = Field(..., description="The number of items per page.")
    items: List[ContractSchema] = Field(
        ..., description="The list of contracts for the current page."
    )


class ContractSortBy(str, Enum):
    date_issued = "date_issued"
    date_expired = "date_expired"
    price = "price"
    collateral = "collateral"


class SortDirection(str, Enum):
    asc = "asc"
    desc = "desc"


class ContractFilters:
    """
    Represents the available filters for the contracts endpoint.

    This model is used as a dependency to inject query parameters from the request
    into the API endpoint. It centralizes all filtering, sorting, and pagination
    logic.
    """

    def __init__(
        self,
        # Text search
        search: Optional[str] = Query(
            default=None,
            min_length=3,
            description="Case-insensitive search across contract title and ship name.",
        ),
        # Numeric ranges
        min_price: Optional[float] = Query(
            default=None, ge=0, description="Minimum price."
        ),
        max_price: Optional[float] = Query(
            default=None, ge=0, description="Maximum price."
        ),
        min_collateral: Optional[float] = Query(
            default=None, ge=0, description="Minimum collateral."
        ),
        max_collateral: Optional[float] = Query(
            default=None, ge=0, description="Maximum collateral."
        ),
        min_runs: Optional[int] = Query(
            default=None,
            ge=-1,
            description="Minimum runs for BPCs (-1 for original).",
        ),
        max_runs: Optional[int] = Query(
            default=None, ge=-1, description="Maximum runs for BPCs."
        ),
        min_me: Optional[int] = Query(
            default=None, ge=0, description="Minimum Material Efficiency for BPCs."
        ),
        max_me: Optional[int] = Query(
            default=None, ge=0, description="Maximum Material Efficiency for BPCs."
        ),
        min_te: Optional[int] = Query(
            default=None, ge=0, description="Minimum Time Efficiency for BPCs."
        ),
        max_te: Optional[int] = Query(
            default=None, ge=0, description="Maximum Time Efficiency for BPCs."
        ),
        # ID lists
        region_ids: Optional[List[int]] = Query(
            default=None, description="List of region IDs to filter by."
        ),
        system_ids: Optional[List[int]] = Query(
            default=None, description="List of solar system IDs to filter by."
        ),
        station_ids: Optional[List[int]] = Query(
            default=None, description="List of station IDs to filter by."
        ),
        type_ids: Optional[List[int]] = Query(
            default=None, description="List of ship type IDs to filter by."
        ),
        # Boolean
        is_bpc: Optional[bool] = Query(
            default=None,
            description="Filter for contracts containing blueprints (BPCs).",
        ),
        # Pagination
        page: int = Query(default=1, ge=1, description="Page number."),
        size: int = Query(
            default=50, ge=1, le=100, description="Number of items per page."
        ),
        # Sorting
        sort_by: ContractSortBy = Query(
            default=ContractSortBy.date_issued, description="Field to sort by."
        ),
        sort_direction: SortDirection = Query(
            default=SortDirection.desc, description="Sort direction."
        ),
    ):
        self.search = search
        self.min_price = min_price
        self.max_price = max_price
        self.min_collateral = min_collateral
        self.max_collateral = max_collateral
        self.min_runs = min_runs
        self.max_runs = max_runs
        self.min_me = min_me
        self.max_me = max_me
        self.min_te = min_te
        self.max_te = max_te
        self.region_ids = region_ids
        self.system_ids = system_ids
        self.station_ids = station_ids
        self.type_ids = type_ids
        self.is_bpc = is_bpc
        self.page = page
        self.size = size
        self.sort_by = sort_by
        self.sort_direction = sort_direction
