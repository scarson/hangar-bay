import enum
from sqlalchemy import Integer, String, Boolean, Enum as SAEnum, ForeignKey # Keep ForeignKey if used by relationships
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import Optional

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
