"""Disease detection report model."""
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Numeric, String, Text, func
from app.core.database import GUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, JSONType


class DiseaseReport(Base):
    __tablename__ = "disease_reports"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    farm_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("farms.id", ondelete="SET NULL"))
    crop: Mapped[str] = mapped_column(Text, nullable=False)
    image_path: Mapped[str | None] = mapped_column(Text)
    image_url: Mapped[str | None] = mapped_column(Text)
    disease_name: Mapped[str] = mapped_column(Text, nullable=False)
    is_healthy: Mapped[bool] = mapped_column(Boolean, default=False)
    confidence: Mapped[float] = mapped_column(Numeric(5, 2), default=0)
    severity: Mapped[str] = mapped_column(String(20), default="low")
    severity_score: Mapped[float] = mapped_column(Numeric(5, 2), default=0)
    symptoms: Mapped[str | None] = mapped_column(Text)
    cause: Mapped[str | None] = mapped_column(Text)
    treatment: Mapped[str | None] = mapped_column(Text)
    prevention: Mapped[str | None] = mapped_column(Text)
    spread_risk: Mapped[str | None] = mapped_column(Text)
    alternatives: Mapped[list | None] = mapped_column(JSONType)  # alternative explanations
    followup_status: Mapped[str | None] = mapped_column(String(30))  # open | monitoring | treated | resolved
    notes: Mapped[str | None] = mapped_column(Text)  # farmer's own follow-up notes
    model: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="disease_reports")
