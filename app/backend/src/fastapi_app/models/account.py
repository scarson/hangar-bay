# ABOUTME: M3 per-user account tables — saved searches, watchlist items, notifications — FK'd to users.id (ondelete CASCADE).
# ABOUTME: Notifications carry the uq_notifications_watchlist_dedup partial unique index the matcher relies on for ON CONFLICT dedup.
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    false,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from ..db import Base


class SavedSearch(Base):
    __tablename__ = "saved_searches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    search_parameters: Mapped[Any] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    __table_args__ = (UniqueConstraint("user_id", "name", name="uq_saved_searches_user_name"),)


class WatchlistItem(Base):
    __tablename__ = "watchlist_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    type_id: Mapped[int] = mapped_column(Integer, nullable=False)
    type_name: Mapped[str] = mapped_column(String(255), nullable=False)
    max_price: Mapped[Optional[float]] = mapped_column(Numeric(20, 2), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    __table_args__ = (UniqueConstraint("user_id", "type_id", name="uq_watchlist_items_user_type"),)


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    type: Mapped[str] = mapped_column(String(50), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    # contract_id is NOT a foreign key: contracts are upsert-only external data, and a
    # pruned/wiped contract must never cascade-delete a user's notification history (design §4.2).
    contract_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    watch_type_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    price: Mapped[Optional[float]] = mapped_column(Numeric(20, 2), nullable=True)
    is_read: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=false())
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index("ix_notifications_user_is_read", "user_id", "is_read"),
        Index("ix_notifications_user_created_at", "user_id", "created_at"),
        # Partial unique index — the matcher's ON CONFLICT dedup target. The predicate keeps
        # the constraint from binding future notification types whose dedup columns are NULL
        # (NULLs are distinct in Postgres unique indexes); the matcher always populates both
        # dedup columns for watchlist_match rows (design §4.4).
        Index(
            "uq_notifications_watchlist_dedup",
            "user_id",
            "contract_id",
            "watch_type_id",
            unique=True,
            postgresql_where=text("type = 'watchlist_match'"),
        ),
    )
