from datetime import datetime
from enum import Enum
from typing import List, Optional, Dict, Any

from pydantic import BaseModel, ConfigDict, Field, computed_field


class EsiTypeSchema(BaseModel):
    """Schema for ESI type information with schema-model parity to EsiTypeCache.
    
    Includes computed fields for EVE image server URLs (render and icon).
    """
    
    type_id: int
    name: str
    description: str
    category_id: Optional[int] = None
    group_id: Optional[int] = None
    market_group_id: Optional[int] = None
    
    # Physical properties
    mass: Optional[float] = None
    volume: Optional[float] = None
    capacity: Optional[float] = None
    
    # Visual representation IDs
    icon_id: Optional[int] = None
    graphic_id: Optional[int] = None
    
    # Publishing status
    published: bool = True
    
    # Comprehensive attribute data from ESI
    dogma_attributes: Optional[Dict[str, Any]] = None
    dogma_effects: Optional[Dict[str, Any]] = None
    
    # Store the complete ESI response for future-proofing
    raw_esi_response: Optional[Dict[str, Any]] = None
    
    @computed_field
    @property
    def icon_url(self) -> str:
        """Generate EVE image server icon URL."""
        return f"https://images.evetech.net/types/{self.type_id}/icon?size=64"
    
    @computed_field
    @property
    def image_url(self) -> str:
        """Generate EVE image server render URL (alias for render_url)."""
        return f"https://images.evetech.net/types/{self.type_id}/render?size=512"
    
    @computed_field
    @property
    def render_url(self) -> str:
        """Generate EVE image server render URL."""
        return f"https://images.evetech.net/types/{self.type_id}/render?size=512"
    
    @computed_field
    @property
    def thumbnail_url(self) -> str:
        """Generate EVE image server thumbnail render URL."""
        return f"https://images.evetech.net/types/{self.type_id}/render?size=128"
    
    model_config = ConfigDict(from_attributes=True)


class ShipAttributeGroupSchema(BaseModel):
    """Schema for a group of related ship attributes."""
    
    group_name: str = Field(..., description="Name of the attribute group (e.g., 'Tank', 'Capacitor')")
    attributes: Dict[str, Any] = Field(default_factory=dict, description="Attributes in this group")
    
    model_config = ConfigDict(from_attributes=True)


class ShipAttributeSchema(BaseModel):
    """Schema for displaying ship attributes in organized groups.
    
    Processes dogma_attributes JSON into user-friendly attribute groups
    like Tank, Capacitor, Targeting, Slots, etc.
    """
    
    # Key attributes for quick overview
    key_attributes: Dict[str, ShipAttributeGroupSchema] = Field(
        default_factory=dict, 
        description="Essential ship attributes grouped by category"
    )
    
    # Complete attribute set for detailed view
    all_attributes: Dict[str, ShipAttributeGroupSchema] = Field(
        default_factory=dict, 
        description="Complete ship attributes grouped by category"
    )
    
    # Raw attribute data for debugging/advanced use
    raw_dogma_attributes: Optional[Dict[str, Any]] = Field(
        default=None, 
        description="Raw dogma attributes from ESI (optional, for debugging)"
    )
    
    # Derived ship statistics
    ship_stats: Dict[str, Any] = Field(
        default_factory=dict,
        description="Calculated ship statistics (EHP, DPS, etc.)"
    )
    
    @computed_field
    @property
    def has_key_attributes(self) -> bool:
        """Check if key attributes are available."""
        return len(self.key_attributes) > 0
    
    @computed_field
    @property
    def attribute_group_names(self) -> List[str]:
        """Get list of available attribute group names."""
        return list(self.all_attributes.keys())
    
    @computed_field
    @property
    def total_attribute_count(self) -> int:
        """Get total count of individual attributes across all groups."""
        return sum(len(group.attributes) for group in self.all_attributes.values())
    
    model_config = ConfigDict(from_attributes=True)


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
    min_me: Optional[int] = Field(
        default=None, ge=0, description="Minimum Material Efficiency for BPCs."
    )
    max_me: Optional[int] = Field(
        default=None, ge=0, description="Maximum Material Efficiency for BPCs."
    )
    min_te: Optional[int] = Field(
        default=None, ge=0, description="Minimum Time Efficiency for BPCs."
    )
    max_te: Optional[int] = Field(
        default=None, ge=0, description="Maximum Time Efficiency for BPCs."
    )
    # ID lists - FastAPI handles string-to-list conversion for query params
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


class ContractDetailsItemSchema(BaseModel):
    """Enhanced schema for contract items with comprehensive ESI data."""
    
    record_id: int
    type_id: int
    type_name: Optional[str] = None
    category: Optional[str] = None
    quantity: int
    is_included: bool
    is_singleton: bool
    is_blueprint_copy: Optional[bool] = None
    raw_quantity: Optional[int] = None
    market_group_id: Optional[int] = None
    
    # ESI-enhanced fields
    description: Optional[str] = None
    mass: Optional[float] = None
    volume: Optional[float] = None
    capacity: Optional[float] = None
    icon_url: Optional[str] = None
    image_url: Optional[str] = None
    
    # Ship-specific attributes (present if item is a ship)
    ship_attributes: Optional[Dict[str, Any]] = None
    
    model_config = ConfigDict(from_attributes=True)


class ShipDetailsSchema(BaseModel):
    """Detailed ship information for ship contracts."""
    
    type_id: int
    type_name: str
    description: Optional[str] = None
    
    # Ship attributes (power, slots, resistances, etc.)
    attributes: Dict[str, Any] = Field(default_factory=dict)
    
    # Visual representation URLs
    icon_url: Optional[str] = None
    image_url: Optional[str] = None
    render_url: Optional[str] = None
    
    # Physical properties
    mass: Optional[float] = None
    volume: Optional[float] = None
    capacity: Optional[float] = None
    
    model_config = ConfigDict(from_attributes=True)


class ContractDetailsSchema(BaseModel):
    """Comprehensive schema for detailed contract view."""
    
    contract_id: int
    title: Optional[str] = None
    type: str
    status: str
    price: float = 0.0
    collateral: float = 0.0
    reward: Optional[float] = None
    volume: Optional[float] = None
    
    # Dates
    date_issued: Optional[str] = None  # ISO format string
    date_expired: Optional[str] = None  # ISO format string
    date_completed: Optional[str] = None  # ISO format string
    
    # Issuer information
    issuer_id: int
    issuer_name: Optional[str] = None
    issuer_corporation_id: int
    issuer_corporation_name: Optional[str] = None
    
    # Location information
    start_location_id: Optional[int] = None
    start_location_name: Optional[str] = None
    start_location_system_id: Optional[int] = None
    start_location_region_id: Optional[int] = None
    end_location_id: Optional[int] = None
    
    # Contract flags
    for_corporation: bool
    is_ship_contract: bool
    
    # Enhanced data
    items: List[ContractDetailsItemSchema] = Field(default_factory=list)
    ship_details: Optional[ShipDetailsSchema] = None
    
    model_config = ConfigDict(from_attributes=True)
