"""Weather record model."""
import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Numeric, Text, func
from app.core.database import GUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class WeatherRecord(Base):
    __tablename__ = "weather_records"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    farm_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("farms.id", ondelete="SET NULL"))
    location: Mapped[str | None] = mapped_column(Text)
    latitude: Mapped[float | None] = mapped_column(Numeric(9, 6))
    longitude: Mapped[float | None] = mapped_column(Numeric(9, 6))
    record_date: Mapped[date] = mapped_column(Date, nullable=False)
    temp_c: Mapped[float | None] = mapped_column(Numeric(6, 2))
    feels_like_c: Mapped[float | None] = mapped_column(Numeric(6, 2))
    humidity: Mapped[float | None] = mapped_column(Numeric(6, 2))
    wind_kph: Mapped[float | None] = mapped_column(Numeric(6, 2))
    precip_mm: Mapped[float | None] = mapped_column(Numeric(8, 2))
    precip_probability: Mapped[float | None] = mapped_column(Numeric(5, 2))
    condition: Mapped[str | None] = mapped_column(Text)
    alert: Mapped[str | None] = mapped_column(Text)
    ai_recommendation: Mapped[str | None] = mapped_column(Text)
    action: Mapped[str | None] = mapped_column(Text)
    model: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="weather_records")
