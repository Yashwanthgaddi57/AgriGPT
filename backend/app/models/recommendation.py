"""Crop recommendation result model."""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Numeric, String, Text, func
from app.core.database import GUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, JSONType


class Recommendation(Base):
    __tablename__ = "recommendations"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    farm_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("farms.id", ondelete="SET NULL"))
    location: Mapped[str] = mapped_column(Text, nullable=False)
    season: Mapped[str] = mapped_column(Text, nullable=False)
    farm_size_acres: Mapped[float] = mapped_column(Numeric(10, 2), default=0)
    soil_type: Mapped[str] = mapped_column(String(20), default="unknown")
    water_source: Mapped[str] = mapped_column(String(20), default="rainfed")
    budget_inr: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    crops: Mapped[list] = mapped_column(JSONType, default=list)
    model: Mapped[str | None] = mapped_column(Text)
    prompt_tokens: Mapped[int | None] = mapped_column()
    completion_tokens: Mapped[int | None] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="recommendations")
