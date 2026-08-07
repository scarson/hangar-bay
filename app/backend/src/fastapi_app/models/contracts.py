from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    Float,
    Integer,
    String,
    Boolean,
    ForeignKey,
    Index,
    Numeric,
)
from sqlalchemy.orm import relationship
from sqlalchemy import JSON
from sqlalchemy.orm import Mapped, mapped_column

from ..db import Base
from typing import Optional, Any, Dict, List  # Dict and List for relationship type hints if needed, Any for JSON
from datetime import datetime


class EsiMarketGroupCache(Base):
    __tablename__ = 'esi_market_group_cache'

    market_group_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(String, nullable=False)
    parent_group_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey('esi_market_group_cache.market_group_id'), nullable=True)
    # The full JSON response from ESI, for future-proofing
    raw_esi_response: Mapped[Any] = mapped_column(JSON, nullable=False)

    __table_args__ = (Index('ix_esi_market_group_cache_parent_group_id', 'parent_group_id'),)

    def __repr__(self):
        return f"<EsiMarketGroupCache(market_group_id={self.market_group_id}, name='{self.name}')>"


class EsiTaxonomyCache(Base):
    """Dogma category/group display names, keyed (kind, esi_id).

    Criterion 3.5's option list needs names, and the enrichment pipeline only holds
    them transiently. kind is 'category' or 'group'; ids share an integer space with
    market groups, which is why EsiMarketGroupCache is not reused (spec §5.2).
    """
    __tablename__ = 'esi_taxonomy_cache'

    kind: Mapped[str] = mapped_column(String, primary_key=True)
    esi_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    # The owning category for kind='group'; NULL for kind='category'.
    parent_category_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class Contract(Base):
    __tablename__ = 'contracts'

    contract_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    title: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    price: Mapped[float] = mapped_column(Numeric, nullable=False)
    collateral: Mapped[float] = mapped_column(Numeric, nullable=False)
    # Contract lifecycle state, and when it reached a terminal one. Both belong to ESI's
    # AUTHENTICATED character/corporation contract routes; the public route carries neither,
    # so under public ingestion status holds a placeholder and date_completed stays NULL for
    # every row. They fill in when a user's own contracts are ingested. Nothing may filter,
    # sort, or serialize on them until then — a predicate over a column the writer never
    # populates returns an empty page that reads as "no matches" (ESI-3).
    status: Mapped[str] = mapped_column(String, nullable=False)
    type: Mapped[str] = mapped_column(String, nullable=False)
    issuer_id: Mapped[int] = mapped_column(Integer, nullable=False)
    issuer_corporation_id: Mapped[int] = mapped_column(Integer, nullable=False)
    start_location_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    start_location_system_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    # NULL where the destination is a player structure (no tokenless resolution
    # route) — measured ~5% of Forge couriers. Written by ingestion for the
    # reward-per-jump follow-on; nothing in F008 reads it.
    end_location_system_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    start_location_region_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    end_location_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)  # Optional for courier contracts
    for_corporation: Mapped[bool] = mapped_column(Boolean, nullable=False)
    date_issued: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    date_expired: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    date_completed: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)   # authenticated-route field; see status above
    reward: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    volume: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    # Auction-only: the price that ends the auction immediately. ESI omits it for
    # non-auctions and for auctions without one; absence must stay distinguishable
    # from zero (ESI-3), so nullable with no default.
    buyout: Mapped[Optional[float]] = mapped_column(Numeric, nullable=True)
    # Courier-only: contracted days to deliver once accepted.
    days_to_complete: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Denormalized data for search performance
    start_location_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    end_location_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    issuer_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    issuer_corporation_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    is_ship_contract: Mapped[bool] = mapped_column(Boolean, default=False)
    item_processing_status: Mapped[str] = mapped_column(String, default='PENDING_ITEMS', index=True)
    # Stamped on successful enrichment. Bumping ENRICHMENT_VERSION re-queues the corpus
    # through the normal budgeted path — the deliberate replacement for the refetch
    # loop's accidental self-healing, which this repo has relied on twice.
    # Only meaningful while item_processing_status = 'COMPLETED': an ENRICHMENT_INCOMPLETE
    # row keeps whatever version it last stamped, which says nothing about its items.
    enrichment_version: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    items_last_fetched_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    contract_esi_etag: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    # Stamped with the run's timestamp on every upsert, so a contract that stops appearing
    # in ESI's public list (sold or withdrawn) stops being restamped and can be told apart
    # from a live one. NULL means "never observed by a stamping run" and is treated as
    # visible — see contract_service._apply_contract_filters.
    last_seen_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    items: Mapped[List["ContractItem"]] = relationship(back_populates="contract", cascade="all, delete-orphan")

    __table_args__ = (
        Index('ix_contracts_type_status', 'type', 'status'),
        Index('ix_contracts_start_location_name', 'start_location_name'),
        Index('ix_contracts_title', 'title'),
        Index('ix_contracts_is_ship_contract', 'is_ship_contract'),
        # Indexes for sorting and filtering performance
        Index('ix_contracts_price', 'price'),
        Index('ix_contracts_date_issued', 'date_issued'),
        # Every list query filters date_expired > now(), so this one is on the hot path
        # for all of them, not just for sorting by "Time left".
        Index('ix_contracts_date_expired', 'date_expired'),
        # Serves the per-region watermark lookup (max(last_seen_at) grouped by region).
        Index('ix_contracts_region_last_seen', 'start_location_region_id', 'last_seen_at'),
        Index('ix_contracts_collateral', 'collateral'),
        Index('ix_contracts_volume', 'volume'),
        Index('ix_contracts_buyout', 'buyout'),
        Index('ix_contracts_days_to_complete', 'days_to_complete'),
    )

    def __repr__(self):
        return f"<Contract(contract_id={self.contract_id}, title='{self.title}')>"


class ContractItem(Base):
    __tablename__ = 'contract_items'

    record_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    contract_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('contracts.contract_id'), nullable=False)
    type_id: Mapped[int] = mapped_column(Integer, nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    is_included: Mapped[bool] = mapped_column(Boolean, nullable=False)
    is_blueprint_copy: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    # Dogma taxonomy, resolved during enrichment from the type→group→category chain
    # that already computes the ship flag. Names live in esi_taxonomy_cache.
    category_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    group_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    # Blueprint-copy fields from the PUBLIC item route. A blueprint ORIGINAL omits
    # `runs` entirely rather than sending -1 (ESI-3) — absence means original.
    runs: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    material_efficiency: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    time_efficiency: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    # Join key to /dogma/dynamic/items/{type_id}/{item_id} for the abyssal
    # follow-on; written now so that work needs no corpus re-ingest.
    item_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)

    # Assembled-vs-stacked, and the blueprint run/copy marker. Both belong to ESI's
    # AUTHENTICATED character/corporation contract-ITEM routes; the public item route
    # carries neither, so under public ingestion is_singleton takes its mapping default and
    # raw_quantity stays NULL for every row. They fill in when a user's own contracts are
    # ingested. Until then no filter may read them — min_runs/max_runs once read
    # raw_quantity and returned an empty result that looked like "no BPCs match" rather
    # than a dead control (ESI-3). A public contract's run count comes from the public
    # `runs` column above, which enrichment ingests.
    is_singleton: Mapped[bool] = mapped_column(Boolean, nullable=False)
    raw_quantity: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Denormalized data from other sources
    type_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    category: Mapped[Optional[str]] = mapped_column(String, nullable=True)  # e.g., 'ship'
    market_group_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    contract: Mapped["Contract"] = relationship(back_populates="items")

    __table_args__ = (
        Index('ix_contract_items_contract_id', 'contract_id'),
        Index('ix_contract_items_type_id', 'type_id'),
        # Indexes for BPC filtering
        Index('ix_contract_items_is_blueprint_copy', 'is_blueprint_copy'),
        Index('ix_contract_items_raw_quantity', 'raw_quantity'),
        # Indexes for the taxonomy and blueprint filter families (correlated EXISTS
        # probes at corpus scale — same rationale as is_blueprint_copy above).
        Index('ix_contract_items_category_id', 'category_id'),
        Index('ix_contract_items_group_id', 'group_id'),
        Index('ix_contract_items_runs', 'runs'),
        Index('ix_contract_items_material_efficiency', 'material_efficiency'),
        Index('ix_contract_items_time_efficiency', 'time_efficiency'),
    )

    def __repr__(self):
        return f"<ContractItem(record_id={self.record_id}, type_id={self.type_id}, quantity={self.quantity})>"
