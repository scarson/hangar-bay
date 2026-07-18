# ABOUTME: Pydantic schemas for M3 saved searches — the extra="forbid" search_parameters model + CRUD request/response shapes.
# ABOUTME: search_parameters mirrors the frontend ContractSearch minus page; ME/TE and unknown keys are rejected at the boundary (FASTAPI-2).
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, PositiveInt, field_validator, model_validator

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


class WatchlistItemCreate(BaseModel):
    """Add-watchlist body: exactly one of type_id / type_name, plus optional max_price / notes."""

    type_id: Optional[int] = Field(default=None, gt=0)
    type_name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    max_price: Optional[float] = Field(default=None, ge=0.01, description="ISK; >= 0.01 when present.")
    notes: Optional[str] = Field(default=None, max_length=500)

    @field_validator("type_name", "notes")
    @classmethod
    def _strip_blank_to_none(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        v = v.strip()
        return v or None

    @model_validator(mode="after")
    def _exactly_one_identifier(self):
        if (self.type_id is None) == (self.type_name is None):
            raise ValueError("provide exactly one of type_id or type_name")
        return self


class WatchlistItemUpdate(BaseModel):
    """Partial update: omitted field preserves, explicit JSON null clears (via model_fields_set)."""

    max_price: Optional[float] = Field(default=None, ge=0.01)
    notes: Optional[str] = Field(default=None, max_length=500)


class WatchlistItemSchema(BaseModel):
    id: int
    type_id: int
    type_name: str
    max_price: Optional[float] = None
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class NotificationSchema(BaseModel):
    id: int
    type: str
    message: str
    contract_id: Optional[int] = None
    watch_type_id: Optional[int] = None
    price: Optional[float] = None
    is_read: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class NotificationSettingsSchema(BaseModel):
    watchlist_alerts_enabled: bool

    model_config = ConfigDict(from_attributes=True)


class NotificationFilters(BaseModel):
    """Query-param model for GET /me/notifications/ — bind with Annotated[..., Query()] (FASTAPI-1)."""

    is_read: Optional[bool] = Field(default=None)
    page: int = Field(default=1, ge=1)
    size: int = Field(default=50, ge=1, le=100)
