from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class ContractItemSchema(BaseModel):
    """Schema for an item within a contract."""

    record_id: int
    type_id: int
    quantity: int
    is_included: bool
    is_singleton: bool
    is_blueprint_copy: Optional[bool] = None
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


class SortableContractFields(str, Enum):
    """Fields that can be used for sorting contracts."""

    date_issued = "date_issued"
    date_expired = "date_expired"
    price = "price"
    collateral = "collateral"
    ship_name = "ship_name"
    volume = "volume"


class SortDirection(str, Enum):
    asc = "asc"
    desc = "desc"


class ContractFilters(BaseModel):
    """
    Represents the available filters for the contracts endpoint.

    This Pydantic model serves as a pure data container for filter parameters.
    FastAPI uses it for dependency injection, automatically populating it from
    query parameters. This approach decouples the data schema from the API layer,
    allowing it to be safely instantiated in tests and other services.
    """

    # Text search
    search: Optional[str] = Field(
        default=None,
        min_length=3,
        description="Case-insensitive search across contract title and ship name.",
    )
    # Numeric ranges
    min_price: Optional[float] = Field(default=None, ge=0, description="Minimum price.")
    max_price: Optional[float] = Field(default=None, ge=0, description="Maximum price.")
    min_collateral: Optional[float] = Field(
        default=None, ge=0, description="Minimum collateral."
    )
    max_collateral: Optional[float] = Field(
        default=None, ge=0, description="Maximum collateral."
    )
    min_runs: Optional[int] = Field(
        default=None, ge=-1, description="Minimum runs for BPCs (-1 for original)."
    )
    max_runs: Optional[int] = Field(default=None, ge=-1, description="Maximum runs for BPCs.")
    # NOTE (FASTAPI-2): min_me/max_me/min_te/max_te are accepted but never applied
    # by the service (ME/TE data is not in the model). The descriptions flag them as
    # inert so generated clients (openapi.json → frontend codegen) do not surface them
    # as functional controls.
    min_me: Optional[int] = Field(
        default=None,
        ge=0,
        description=(
            "Minimum Material Efficiency for BPCs. "
            "(NOT IMPLEMENTED — accepted but ignored by the service; do not expose in clients)"
        ),
    )
    max_me: Optional[int] = Field(
        default=None,
        ge=0,
        description=(
            "Maximum Material Efficiency for BPCs. "
            "(NOT IMPLEMENTED — accepted but ignored by the service; do not expose in clients)"
        ),
    )
    min_te: Optional[int] = Field(
        default=None,
        ge=0,
        description=(
            "Minimum Time Efficiency for BPCs. "
            "(NOT IMPLEMENTED — accepted but ignored by the service; do not expose in clients)"
        ),
    )
    max_te: Optional[int] = Field(
        default=None,
        ge=0,
        description=(
            "Maximum Time Efficiency for BPCs. "
            "(NOT IMPLEMENTED — accepted but ignored by the service; do not expose in clients)"
        ),
    )
    # ID lists — bound as repeated query params via Annotated[ContractFilters, Query()]
    # in the endpoint (see pitfall FASTAPI-1: bare Depends() sends lists to the GET body).
    region_ids: Optional[List[int]] = Field(
        default=None, description="List of region IDs to filter by."
    )
    system_ids: Optional[List[int]] = Field(
        default=None, description="List of solar system IDs to filter by."
    )
    station_ids: Optional[List[int]] = Field(
        default=None, description="List of station IDs to filter by."
    )
    type_ids: Optional[List[int]] = Field(
        default=None, description="List of ship type IDs to filter by."
    )
    # Boolean
    is_bpc: Optional[bool] = Field(
        default=None, description="Filter for contracts containing blueprints (BPCs)."
    )
    is_ship_contract: Optional[bool] = Field(
        default=None,
        description="Filter for contracts flagged as ship contracts (contract-level flag).",
    )
    # Pagination
    page: int = Field(default=1, ge=1, description="Page number.")
    size: int = Field(default=50, ge=1, le=100, description="Number of items per page.")
    # Sorting
    sort_by: SortableContractFields = Field(
        default=SortableContractFields.date_issued, description="Field to sort by."
    )
    sort_direction: SortDirection = Field(
        default=SortDirection.desc, description="Sort direction."
    )
