"""Mandi (wholesale market) and agri-vendor directory models."""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Index, Integer, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, GUID, JSONType


class Mandi(Base):
    __tablename__ = "mandis"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    city: Mapped[str | None] = mapped_column(Text)
    district: Mapped[str | None] = mapped_column(Text)
    state: Mapped[str | None] = mapped_column(Text)
    latitude: Mapped[float] = mapped_column(Numeric(9, 6), nullable=False)
    longitude: Mapped[float] = mapped_column(Numeric(9, 6), nullable=False)
    major_crops: Mapped[list] = mapped_column(JSONType, default=list)  # e.g. ["onion","cotton"]
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Vendor(Base):
    """An agricultural service/business point (vendor directory + OSM cache).

    Categories: seeds | pesticide | fertilizer | agri_store | equipment |
    market | feed | fpo | services | produce_buyer.

    `source`/`source_id` give every imported record a stable identity so the
    same shop is never stored twice (see `upsert_vendor`).
    """

    __tablename__ = "vendors"
    # One row per (source, source_id): re-importing the same OSM element or
    # provider record updates it instead of creating a duplicate marker.
    __table_args__ = (Index("uq_vendors_source", "source", "source_id", unique=True),)

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    subcategory: Mapped[str | None] = mapped_column(String(60))
    description: Mapped[str | None] = mapped_column(Text)
    phone: Mapped[str | None] = mapped_column(Text)
    website: Mapped[str | None] = mapped_column(Text)
    address: Mapped[str | None] = mapped_column(Text)
    city: Mapped[str | None] = mapped_column(Text)
    district: Mapped[str | None] = mapped_column(Text, index=True)
    state: Mapped[str | None] = mapped_column(Text, index=True)
    pincode: Mapped[str | None] = mapped_column(String(12))
    latitude: Mapped[float] = mapped_column(Numeric(9, 6), nullable=False, index=True)
    longitude: Mapped[float] = mapped_column(Numeric(9, 6), nullable=False, index=True)
    # Ratings are only ever set when a real provider supplies them — never guessed.
    rating: Mapped[float | None] = mapped_column(Numeric(3, 1))
    review_count: Mapped[int | None] = mapped_column(Integer)
    opening_hours: Mapped[str | None] = mapped_column(Text)
    crops: Mapped[list] = mapped_column(JSONType, default=list)  # specialty crops
    source: Mapped[str | None] = mapped_column(String(40), default="directory")
    source_id: Mapped[str | None] = mapped_column(String(80))
    last_updated: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), onupdate=func.now())
