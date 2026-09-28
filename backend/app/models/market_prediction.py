"""Market prediction model."""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Numeric, Text, func
from app.core.database import GUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, JSONType


class MarketPrediction(Base):
    __tablename__ = "market_predictions"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    crop: Mapped[str] = mapped_column(Text, nullable=False)
    market: Mapped[str | None] = mapped_column(Text)
    current_price: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    price_unit: Mapped[str] = mapped_column(Text, default="INR/quintal")
    trend_weekly: Mapped[float] = mapped_column(Numeric(6, 2), default=0)
    trend_monthly: Mapped[float] = mapped_column(Numeric(6, 2), default=0)
    trend_quarterly: Mapped[float] = mapped_column(Numeric(6, 2), default=0)
    demand_forecast: Mapped[str | None] = mapped_column(Text)
    supply_forecast: Mapped[str | None] = mapped_column(Text)
    price_forecast_7d: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    price_forecast_14d: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    price_forecast_30d: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    recommendation: Mapped[str] = mapped_column(Text, default="hold")
    confidence: Mapped[float] = mapped_column(Numeric(5, 2), default=0)
    reasoning: Mapped[str | None] = mapped_column(Text)
    price_history: Mapped[list] = mapped_column(JSONType, default=list)
    data_source: Mapped[str | None] = mapped_column(Text)  # agmarknet_market|agmarknet_district|agmarknet_state|agmarknet_national|baseline
    source_meta: Mapped[dict | None] = mapped_column(JSONType, default=dict)  # scope, commodity, mandi-level modal prices
    model: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="market_predictions")
