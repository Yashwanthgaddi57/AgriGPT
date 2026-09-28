"""Profit prediction model."""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Numeric, Text, func
from app.core.database import GUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, JSONType


class ProfitPrediction(Base):
    __tablename__ = "profit_predictions"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    farm_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("farms.id", ondelete="SET NULL"))
    crop: Mapped[str] = mapped_column(Text, nullable=False)
    farm_size_acres: Mapped[float] = mapped_column(Numeric(10, 2), default=0)
    season: Mapped[str | None] = mapped_column(Text)
    seed_cost: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    labor_cost: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    fertilizer_cost: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    irrigation_cost: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    transportation_cost: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    other_cost: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    total_cost: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    expected_yield_quintals: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    expected_price_per_quintal: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    expected_revenue: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    expected_profit: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    roi: Mapped[float] = mapped_column(Numeric(8, 2), default=0)
    risk_score: Mapped[float] = mapped_column(Numeric(5, 2), default=0)
    confidence_score: Mapped[float] = mapped_column(Numeric(5, 2), default=0)
    scenarios: Mapped[dict] = mapped_column(JSONType, default=dict)
    model: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="profit_predictions")
