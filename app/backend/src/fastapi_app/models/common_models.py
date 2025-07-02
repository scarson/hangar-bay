import enum
from sqlalchemy import Integer, String, Boolean, Enum as SAEnum, ForeignKey, Float, JSON, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import Optional, Any

from ..db import Base


class UserType(enum.Enum):
    EVE_SSO = "EVE_SSO"
    LOCAL = "LOCAL"  # Indicates a locally managed account (not via EVE SSO)
    # SERVICE_ACCOUNT = "SERVICE_ACCOUNT" # Example for future extension


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)  # E.g., EVE Character Name or local admin username
    email: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)  # Must be unique
    hashed_password: Mapped[Optional[str]] = mapped_column(String, nullable=True)  # Nullable for EVE SSO users or if not applicable
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    eve_character_id: Mapped[Optional[int]] = mapped_column(Integer, unique=True, index=True, nullable=True)  # EVE Online Character ID, nullable for non-EVE/admin users
    user_type: Mapped[UserType] = mapped_column(SAEnum(UserType), nullable=False, index=True)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_test_user: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Example of a relationship, if we add other models later
    # items = relationship("Item", back_populates="owner")

    def __repr__(self):
        return f"<User(id={self.id}, username='{self.username}', email='{self.email}')>"


class EsiTypeCache(Base):
    """Cache for ESI type information, particularly for ships and items.
    
    Stores comprehensive type data from ESI including ship attributes,
    descriptions, and metadata needed for detailed contract views.
    """
    __tablename__ = "esi_type_cache"

    type_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    name: Mapped[str] = mapped_column(String, nullable=False, index=True)
    description: Mapped[str] = mapped_column(String, nullable=False)
    category_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    group_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    market_group_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    
    # Ship/item physical properties
    mass: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    volume: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    capacity: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    
    # Visual representation
    icon_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    graphic_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    
    # Publishing status
    published: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    
    # Comprehensive attribute data from ESI
    dogma_attributes: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    dogma_effects: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    
    # Store the complete ESI response for future-proofing
    raw_esi_response: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)

    __table_args__ = (
        Index('ix_esi_type_cache_name', 'name'),
        Index('ix_esi_type_cache_category_id', 'category_id'),
        Index('ix_esi_type_cache_group_id', 'group_id'),
        Index('ix_esi_type_cache_market_group_id', 'market_group_id'),
        Index('ix_esi_type_cache_published', 'published'),
        # Composite index for common query patterns
        Index('ix_esi_type_cache_category_published', 'category_id', 'published'),
    )

    def __repr__(self):
        return f"<EsiTypeCache(type_id={self.type_id}, name='{self.name}')>"
