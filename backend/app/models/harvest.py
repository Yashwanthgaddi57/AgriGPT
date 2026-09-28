"""Harvest model — actual outcomes for estimated-vs-actual comparison (Part 18/20)."""
import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Numeric, Text, func
from app.core.database import GUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Harvest(Base):
    __tablename__ = "harvests"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    farm_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("farms.id", ondelete="SET NULL"))
    crop: Mapped[str] = mapped_column(Text, nullable=False)
    harvest_date: Mapped[date | None] = mapped_column(Date)
    actual_yield_quintals: Mapped[float | None] = mapped_column(Numeric(12, 2))
    selling_price_per_quintal: Mapped[float | None] = mapped_column(Numeric(12, 2))
    market_name: Mapped[str | None] = mapped_column(Text)
    revenue_inr: Mapped[float | None] = mapped_column(Numeric(14, 2))
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="harvests")
