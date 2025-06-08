import enum
from sqlalchemy import Column, Integer, String, Boolean, Enum as SAEnum
from sqlalchemy.orm import relationship

from fastapi_app.db import Base


class UserType(enum.Enum):
    EVE_SSO = "EVE_SSO"
    LOCAL = "LOCAL"  # Indicates a locally managed account (not via EVE SSO)
    # SERVICE_ACCOUNT = "SERVICE_ACCOUNT" # Example for future extension


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    username = Column(
        String, unique=True, index=True, nullable=False
    )  # E.g., EVE Character Name or local admin username
    email = Column(String, unique=True, index=True, nullable=False)  # Must be unique
    hashed_password = Column(
        String, nullable=True
    )  # Nullable for EVE SSO users or if not applicable
    is_active = Column(Boolean, default=True)
    eve_character_id = Column(
        Integer, unique=True, index=True, nullable=True
    )  # EVE Online Character ID, nullable for non-EVE/admin users
    user_type = Column(SAEnum(UserType), nullable=False, index=True)
    is_admin = Column(Boolean, default=False, nullable=False)
    is_test_user = Column(Boolean, default=False, nullable=False)

    # Example of a relationship, if we add other models later
    # items = relationship("Item", back_populates="owner")

    def __repr__(self):
        return f"<User(id={self.id}, username='{self.username}', email='{self.email}')>"
