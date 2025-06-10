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
)
from sqlalchemy.orm import relationship
from sqlalchemy import JSON

from ..db import Base

class EsiMarketGroupCache(Base):
    __tablename__ = 'esi_market_group_cache'

    market_group_id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    description = Column(String, nullable=False)
    parent_group_id = Column(Integer, ForeignKey('esi_market_group_cache.market_group_id'), nullable=True)
    # The full JSON response from ESI, for future-proofing
    raw_esi_response = Column(JSON, nullable=False)

    __table_args__ = (Index('ix_esi_market_group_cache_parent_group_id', 'parent_group_id'),)

    def __repr__(self):
        return f"<EsiMarketGroupCache(market_group_id={self.market_group_id}, name='{self.name}')>"


class Contract(Base):
    __tablename__ = 'contracts'

    contract_id = Column(BigInteger, primary_key=True, autoincrement=False)
    issuer_id = Column(Integer, nullable=False)
    issuer_corporation_id = Column(Integer, nullable=False)
    start_location_id = Column(BigInteger, nullable=False)
    end_location_id = Column(BigInteger, nullable=True) # Optional for courier contracts

    type = Column(String, nullable=False)
    status = Column(String, nullable=False)
    title = Column(String, nullable=True)
    for_corporation = Column(Boolean, nullable=False)
    date_issued = Column(DateTime, nullable=False)
    date_expired = Column(DateTime, nullable=False)
    date_completed = Column(DateTime, nullable=True)

    price = Column(Float, nullable=True)
    reward = Column(Float, nullable=True)
    volume = Column(Float, nullable=True)

    # Denormalized data for search performance
    start_location_name = Column(String, nullable=True)
    issuer_name = Column(String, nullable=True)
    issuer_corporation_name = Column(String, nullable=True)
    is_ship_contract = Column(Boolean, default=False, nullable=False)

    items = relationship("ContractItem", back_populates="contract", cascade="all, delete-orphan")

    __table_args__ = (
        Index('ix_contracts_type_status', 'type', 'status'),
        Index('ix_contracts_start_location_name', 'start_location_name'),
        Index('ix_contracts_title', 'title'),
        Index('ix_contracts_is_ship_contract', 'is_ship_contract'),
    )

    def __repr__(self):
        return f"<Contract(contract_id={self.contract_id}, title='{self.title}')>"


class ContractItem(Base):
    __tablename__ = 'contract_items'

    record_id = Column(BigInteger, primary_key=True, autoincrement=True)
    contract_id = Column(BigInteger, ForeignKey('contracts.contract_id'), nullable=False)
    type_id = Column(Integer, nullable=False)
    quantity = Column(Integer, nullable=False)
    is_included = Column(Boolean, nullable=False)
    is_singleton = Column(Boolean, nullable=False)
    raw_quantity = Column(Integer, nullable=True)

    # Denormalized data from other sources
    type_name = Column(String, nullable=True)
    category = Column(String, nullable=True) # e.g., 'ship'
    market_group_id = Column(Integer, nullable=True)

    contract = relationship("Contract", back_populates="items")

    __table_args__ = (
        Index('ix_contract_items_contract_id', 'contract_id'),
        Index('ix_contract_items_type_id', 'type_id'),
    )

    def __repr__(self):
        return f"<ContractItem(record_id={self.record_id}, type_id={self.type_id}, quantity={self.quantity})>"
