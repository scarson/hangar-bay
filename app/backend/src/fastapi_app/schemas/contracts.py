from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field

from .common import PaginatedResponse


class ContractItemSchema(BaseModel):
    """Schema for an item within a contract.

    `is_singleton` and `raw_quantity` are deliberately absent. Both are fields of ESI's
    AUTHENTICATED character/corporation contract-item routes; the public item route
    Hangar Bay reads carries neither, so `is_singleton` is the mapping default and
    `raw_quantity` is NULL for every item in the corpus today. The columns stay — they
    fill in the moment a user's own contracts are ingested — but a wire field that can
    only misinform is worse than no wire field (ESI-3).
    """

    record_id: int
    type_id: int
    quantity: int
    is_included: bool
    is_blueprint_copy: Optional[bool] = None
    type_name: Optional[str] = None
    category: Optional[str] = None
    market_group_id: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)


class ContractSchema(BaseModel):
    """Schema for a public contract.

    `status` and `date_completed` are deliberately absent. Both are fields of ESI's
    AUTHENTICATED character/corporation contract routes; the public route Hangar Bay
    reads carries neither, so the columns behind them hold a placeholder and a NULL for
    every contract in the corpus today. The columns stay — they fill in the moment a
    user's own contracts are ingested — but a wire field that can only misinform is
    worse than no wire field (ESI-3).
    """

    contract_id: int
    issuer_id: int
    issuer_corporation_id: int
    # ESI's public-contracts schema does not list start_location_id as required, and the
    # column is nullable to match. Declaring it a bare int made a spec-conformant row fail
    # response validation, which 500s the whole page that row lands on.
    start_location_id: Optional[int] = None
    # Resolved from the start location during ingestion. NULL for player-owned
    # structures, whose /universe/structures/ route needs an ACL-scoped token — so a
    # client can show the system where one is known and say "system unknown" where it
    # is not, rather than being unable to tell the two apart.
    start_location_system_id: Optional[int] = None
    end_location_id: Optional[int] = None
    type: str
    title: Optional[str] = None
    for_corporation: bool
    date_issued: datetime
    date_expired: datetime
    price: Optional[float] = None
    # Courier collateral: what the hauler puts up against the cargo. Filterable
    # (min_collateral/max_collateral) and sortable, so clients must be able to read
    # the value they are sorting and filtering on.
    collateral: float
    reward: Optional[float] = None
    volume: Optional[float] = None
    start_location_name: Optional[str] = None
    issuer_name: Optional[str] = None
    issuer_corporation_name: Optional[str] = None
    is_ship_contract: bool
    items: List[ContractItemSchema] = []

    model_config = ConfigDict(from_attributes=True)


class ContractListResponse(PaginatedResponse[ContractSchema]):
    """A page of contracts plus the coverage figure the system_ids filter needs.

    A bare total hides that system_ids can only ever match the locations we resolved:
    a search returning 3 results reads as "there are 3" when it may mean "there are 3
    we can place, and 40 more we cannot". Publishing the residual next to the number
    is the convention the EVE tooling ecosystem already uses for partial data —
    Adam4EVE prints a NoP (number of participants) column beside its aggregates,
    EVE Tycoon labels each row with the appraisal method behind it.
    """

    unknown_system_excluded: Optional[int] = Field(
        default=None,
        description=(
            "How many contracts matched every other filter but were excluded because "
            "their start location has no known solar system (player-owned structures, "
            "which need an ACL-scoped token to resolve). Null when system_ids was not "
            "applied — no results were dropped for that reason, which is different from "
            "none having been."
        ),
    )


class ContractType(str, Enum):
    """Every contract type ESI can emit (confirmed against the committed spec
    snapshot). Typed as an enum so an unknown value 422s instead of silently
    matching nothing — the defect class this feature exists to remove (§17.8)."""

    item_exchange = "item_exchange"
    auction = "auction"
    courier = "courier"
    loan = "loan"
    unknown = "unknown"


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
    # NOTE (ESI-3): min_runs/max_runs are applied, but against ContractItem.raw_quantity —
    # a field ESI returns only on the AUTHENTICATED contract-item routes, not on the public
    # one this ingestion reads. The column is NULL under public ingestion, so both bounds
    # match zero rows until a user's own contracts are ingested.
    # Making them work for PUBLIC contracts requires ingesting the public `runs` field; note
    # that on that route an original OMITS `runs` rather than sending -1, so the documented
    # sentinel never appears.
    min_runs: Optional[int] = Field(
        default=None,
        ge=-1,
        description=(
            "Minimum runs for BPCs. "
            "(NO MATCHES — filters an always-NULL column; do not expose in clients)"
        ),
    )
    max_runs: Optional[int] = Field(
        default=None,
        ge=-1,
        description=(
            "Maximum runs for BPCs. "
            "(NO MATCHES — filters an always-NULL column; do not expose in clients)"
        ),
    )
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
    # NOTE: system_ids has PARTIAL coverage. Ingestion resolves start locations through
    # the public /universe/stations/ route, which answers for NPC stations only; a
    # contract in a player-owned Upwell structure keeps a NULL system and can never
    # match. A 5.9% sample of production (2026-08-01) put NPC stations at 99.80% of The
    # Forge's contracts, but that ratio is a property of THIS region — structure-based
    # trade dominates null/lowsec, so the unresolvable share rises sharply with coverage.
    # The list response's unknown_system_excluded field publishes the residual per query.
    system_ids: Optional[List[int]] = Field(
        default=None,
        description=(
            "List of solar system IDs to filter by. Partial coverage: contracts in NPC "
            "stations carry a resolved system, contracts in player-owned structures do "
            "not and never match. The response's unknown_system_excluded field reports "
            "how many results were dropped for that reason."
        ),
    )
    station_ids: Optional[List[int]] = Field(
        default=None, description="List of station IDs to filter by."
    )
    type_ids: Optional[List[int]] = Field(
        default=None, description="List of ship type IDs to filter by."
    )
    contract_type: Optional[List[ContractType]] = Field(
        default=None, description="Contract types to include (repeatable)."
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
