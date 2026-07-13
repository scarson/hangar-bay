# ABOUTME: EVE-SSO user with an encrypted ESI token vault; owner_hash tracks character ownership.
# ABOUTME: character_id uses BigInteger — EVE character IDs are 64-bit and overflow a 32-bit Integer.
from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from ..db import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    character_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True, nullable=False)
    character_name: Mapped[str] = mapped_column(String(255), nullable=False)
    owner_hash: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    esi_access_token: Mapped[Optional[str]] = mapped_column(Text, nullable=True)            # Fernet ciphertext
    esi_access_token_expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    esi_refresh_token: Mapped[Optional[str]] = mapped_column(Text, nullable=True)           # Fernet ciphertext
    esi_scopes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)                  # empty in F004; F005+ fills
    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return f"<User(id={self.id}, character_id={self.character_id}, character_name='{self.character_name}')>"
