"""Schemas for AI feature requests and responses."""
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.schemas.common import UUIDCoercionMixin
from app.schemas.user import SoilType, WaterAvailability


# ---------------- Crop Recommendation ----------------
class CropRecommendationRequest(BaseModel):
    location: str = Field(min_length=2, max_length=120)
    farm_size_acres: float = Field(gt=0, le=100000)
    soil_type: SoilType = "unknown"
    water_source: WaterAvailability = "rainfed"
    budget_inr: float = Field(ge=0)
    season: Literal["kharif", "rabi", "zaid", "summer", "winter", "monsoon"] = "kharif"
    farm_id: str | None = None


class CropRecommendationItem(BaseModel):
    crop_name: str
    investment_inr: float
    expected_revenue_inr: float
    expected_profit_inr: float
    risk_score: float = Field(ge=0, le=100)
    confidence_score: float = Field(ge=0, le=100)
    yield_quintals_per_acre: float | None = None
    duration_days: int | None = None
    why_recommended: str
    risks: list[str] = []


class CropRecommendationResponse(BaseModel):
    id: str
    location: str
    season: str
    crops: list[CropRecommendationItem]
    model: str | None
    created_at: datetime


# ---------------- Disease Detection ----------------
class DiseaseReportResponse(UUIDCoercionMixin):
    id: str
    crop: str
    image_url: str | None
    disease_name: str
    is_healthy: bool
    confidence: float
    severity: str
    severity_score: float
    symptoms: str | None
    cause: str | None
    treatment: str | None
    prevention: str | None
    spread_risk: str | None
    alternatives: list[str] | None = None
    followup_status: str | None = None
    notes: str | None = None
    created_at: datetime

    class Config:
        from_attributes = True


class DiseaseFollowupUpdate(BaseModel):
    followup_status: Literal["open", "monitoring", "treated", "resolved"] | None = None
    notes: str | None = Field(default=None, max_length=2000)


# ---------------- Profit Prediction ----------------
class ProfitPredictionRequest(BaseModel):
    crop: str = Field(min_length=2, max_length=80)
    farm_size_acres: float = Field(gt=0, le=100000)
    season: Literal["kharif", "rabi", "zaid"] | None = None
    seed_cost: float = Field(ge=0)
    labor_cost: float = Field(ge=0)
    fertilizer_cost: float = Field(ge=0)
    irrigation_cost: float = Field(ge=0)
    transportation_cost: float = Field(ge=0)
    other_cost: float = Field(default=0, ge=0)
    farm_id: str | None = None


class ProfitScenario(BaseModel):
    yield_quintals: float
    price_per_quintal: float
    revenue_inr: float
    profit_inr: float
    roi_percent: float


class ProfitPredictionResponse(UUIDCoercionMixin):
    id: str
    crop: str
    farm_size_acres: float
    total_cost: float
    expected_yield_quintals: float
    expected_price_per_quintal: float
    expected_revenue: float
    expected_profit: float
    roi: float
    risk_score: float
    confidence_score: float
    scenarios: dict[str, ProfitScenario]
    created_at: datetime

    class Config:
        from_attributes = True


# ---------------- Market Intelligence ----------------
class MarketPredictionRequest(BaseModel):
    crop: str = Field(min_length=2, max_length=80)
    market: str | None = Field(default=None, max_length=120)


class MarketPricePoint(BaseModel):
    date: str
    price: float


class MarketPredictionResponse(UUIDCoercionMixin):
    id: str
    crop: str
    market: str | None
    current_price: float
    price_unit: str
    trend_weekly: float
    trend_monthly: float
    trend_quarterly: float
    demand_forecast: str | None
    supply_forecast: str | None
    price_forecast_7d: float
    price_forecast_14d: float
    price_forecast_30d: float
    recommendation: Literal["sell_now", "wait_1_week", "wait_2_weeks", "hold"]
    confidence: float
    reasoning: str | None
    price_history: list[MarketPricePoint]
    data_source: str | None = None
    source_meta: dict | None = None
    created_at: datetime

    class Config:
        from_attributes = True


# ---------------- Weather ----------------
class WeatherDay(BaseModel):
    date: str
    temp_c: float
    feels_like_c: float
    humidity: float
    wind_kph: float
    precip_mm: float
    precip_probability: float
    condition: str


class WeatherOut(BaseModel):
    location: str
    days: list[WeatherDay]
    ai_recommendation: str | None
    action: str | None  # plant_now | delay_planting | harvest_now | irrigate | none
    alerts: list[str] = []


# ---------------- Chat ----------------
class ChatMessageCreate(BaseModel):
    content: str = Field(min_length=1, max_length=4000)
    agent: str | None = None  # optional explicit agent routing
    session_id: str | None = None  # continue an existing conversation
    language: str | None = Field(default=None, max_length=10)  # ISO code hint: en|hi|te|ta|kn|mr


class ChatMessageOut(UUIDCoercionMixin):
    id: str
    role: str
    content: str
    agent: str | None
    created_at: datetime

    class Config:
        from_attributes = True


class ChatSessionCreate(BaseModel):
    title: str = Field(default="New conversation", max_length=200)


class ChatSessionOut(UUIDCoercionMixin):
    id: str
    title: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ---------------- Notifications ----------------
class NotificationOut(UUIDCoercionMixin):
    id: str
    type: str
    channel: str
    title: str
    body: str
    link: str | None
    is_read: bool
    created_at: datetime

    class Config:
        from_attributes = True


class MarkReadRequest(BaseModel):
    ids: list[str] = Field(min_length=1)


# ---------------- Analytics ----------------
class AnalyticsKpis(BaseModel):
    expected_revenue: float
    expected_profit: float
    disease_frequency: float  # reports per month
    yield_growth: float  # percent vs prior period
    profit_growth: float
    weather_risk: float  # 0-100
    recommendation_accuracy: float  # 0-100
    profit_prediction_accuracy: float  # 0-100


class ActivityOut(BaseModel):
    id: str
    action: str
    entity_type: str | None
    entity_id: str | None
    metadata: dict[str, Any]
    created_at: datetime

    class Config:
        from_attributes = True
