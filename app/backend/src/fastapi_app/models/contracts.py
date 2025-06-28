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
from typing import Optional, Any, Dict, List # Dict and List for relationship type hints if needed, Any for JSON
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


class Contract(Base):
    __tablename__ = 'contracts'

    contract_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    title: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    price: Mapped[float] = mapped_column(Numeric, nullable=False)
    collateral: Mapped[float] = mapped_column(Numeric, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    contract_type: Mapped[str] = mapped_column(String, nullable=False)
    issuer_id: Mapped[int] = mapped_column(Integer, nullable=False)
    issuer_corporation_id: Mapped[int] = mapped_column(Integer, nullable=False)
    start_location_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    start_location_system_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    start_location_region_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    end_location_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True) # Optional for courier contracts
    for_corporation: Mapped[bool] = mapped_column(Boolean, nullable=False)
    date_issued: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    date_expired: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    date_completed: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    reward: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    volume: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Denormalized data for search performance
    start_location_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    issuer_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    issuer_corporation_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    is_ship_contract: Mapped[bool] = mapped_column(Boolean, default=False) 
    item_processing_status: Mapped[str] = mapped_column(String, default='PENDING_ITEMS', index=True)
    items_last_fetched_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    contract_esi_etag: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    items: Mapped[List["ContractItem"]] = relationship(back_populates="contract", cascade="all, delete-orphan")

    __table_args__ = (
        Index('ix_contracts_type_status', 'contract_type', 'status'),
        Index('ix_contracts_start_location_name', 'start_location_name'),
        Index('ix_contracts_title', 'title'),
        Index('ix_contracts_is_ship_contract', 'is_ship_contract'),
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
    is_singleton: Mapped[bool] = mapped_column(Boolean, nullable=False)
    is_blueprint_copy: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    raw_quantity: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Denormalized data from other sources
    type_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    category: Mapped[Optional[str]] = mapped_column(String, nullable=True) # e.g., 'ship'
    market_group_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    contract: Mapped["Contract"] = relationship(back_populates="items")

    __table_args__ = (
        Index('ix_contract_items_contract_id', 'contract_id'),
        Index('ix_contract_items_type_id', 'type_id'),
    )

    def __repr__(self):
        return f"<ContractItem(record_id={self.record_id}, type_id={self.type_id}, quantity={self.quantity})>"
