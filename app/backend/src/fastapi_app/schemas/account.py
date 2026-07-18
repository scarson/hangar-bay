# ABOUTME: Pydantic schemas for M3 saved searches — the extra="forbid" search_parameters model + CRUD request/response shapes.
# ABOUTME: search_parameters mirrors the frontend ContractSearch minus page; ME/TE and unknown keys are rejected at the boundary (FASTAPI-2).
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, PositiveInt, field_validator

from .contracts import SortableContractFields, SortDirection


class SavedSearchParameters(BaseModel):
    """Server-side validation model for a saved search's stored filter blob. Mirrors the
    frontend ContractSearch shape minus `page`; extra="forbid" rejects the inert ME/TE params
    (FASTAPI-2), the wire-only `is_ship_contract`, `page`, and arbitrary junk (design §4.5)."""

    model_config = ConfigDict(extra="forbid")

    search: Optional[str] = Field(default=None, min_length=3)
    min_price: Optional[float] = Field(default=None, ge=0)
    max_price: Optional[float] = Field(default=None, ge=0)
    region_ids: Optional[List[PositiveInt]] = Field(default=None)
    is_bpc: Optional[bool] = Field(default=None)
    ships_only: bool = Field(default=True)
    size: int = Field(default=50, ge=1, le=100)
    sort_by: SortableContractFields = Field(default=SortableContractFields.date_issued)
    sort_direction: SortDirection = Field(default=SortDirection.desc)


def _trimmed_nonempty_name(value: str) -> str:
    value = value.strip()
    if not value:
        raise ValueError("name must not be empty")
    return value


class SavedSearchCreate(BaseModel):
    name: str = Field(..., max_length=100)
    search_parameters: SavedSearchParameters

    _trim_name = field_validator("name")(_trimmed_nonempty_name)


class SavedSearchUpdate(BaseModel):
    name: str = Field(..., max_length=100)

    _trim_name = field_validator("name")(_trimmed_nonempty_name)


class SavedSearchSchema(BaseModel):
    id: int
    name: str
    search_parameters: SavedSearchParameters
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
