"""User profile model synced with Supabase auth.users."""
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Numeric, String, Text, func
from app.core.database import GUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True)
    email: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    phone: Mapped[str | None] = mapped_column(Text)
    district: Mapped[str | None] = mapped_column(Text)
    state: Mapped[str | None] = mapped_column(Text)
    village: Mapped[str | None] = mapped_column(Text)
    latitude: Mapped[float | None] = mapped_column(Numeric(9, 6))
    longitude: Mapped[float | None] = mapped_column(Numeric(9, 6))
    location_source: Mapped[str | None] = mapped_column(String(20))  # gps | map_pin | geocoded
    farm_size_acres: Mapped[float] = mapped_column(Numeric(10, 2), default=0)
    soil_type: Mapped[str] = mapped_column(String(20), default="unknown")
    water_availability: Mapped[str] = mapped_column(String(20), default="rainfed")
    language: Mapped[str] = mapped_column(String(10), default="en")
    avatar_url: Mapped[str | None] = mapped_column(Text)
    role: Mapped[str] = mapped_column(String(30), default="farmer")
    plan: Mapped[str] = mapped_column(String(20), default="free")  # free | pro | cooperative
    onboarding_completed: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    farms = relationship("Farm", back_populates="owner", cascade="all, delete-orphan")
    recommendations = relationship("Recommendation", back_populates="user", cascade="all, delete-orphan")
    disease_reports = relationship("DiseaseReport", back_populates="user", cascade="all, delete-orphan")
    profit_predictions = relationship("ProfitPrediction", back_populates="user", cascade="all, delete-orphan")
    market_predictions = relationship("MarketPrediction", back_populates="user", cascade="all, delete-orphan")
    weather_records = relationship("WeatherRecord", back_populates="user", cascade="all, delete-orphan")
    chat_sessions = relationship("ChatSession", back_populates="user", cascade="all, delete-orphan")
    notifications = relationship("Notification", back_populates="user", cascade="all, delete-orphan")
    activities = relationship("Activity", back_populates="user", cascade="all, delete-orphan")
    expenses = relationship("Expense", back_populates="user", cascade="all, delete-orphan")
    harvests = relationship("Harvest", back_populates="user", cascade="all, delete-orphan")
