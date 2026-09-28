"""Dashboard aggregate schema."""
from pydantic import BaseModel

from app.schemas.ai_features import (
    NotificationOut,
    ProfitScenario,
    WeatherDay,
)


class DashboardWidget(BaseModel):
    current_crop: str | None
    current_season: str | None
    expected_revenue: float
    expected_profit: float
    risk_score: float
    disease_alerts: int
    weather_alerts: list[str]
    market_recommendations: list[dict]


class ChartSeries(BaseModel):
    label: str
    value: float


class DashboardCharts(BaseModel):
    revenue_projection: list[ChartSeries]
    profit_projection: list[ChartSeries]
    yield_estimation: list[ChartSeries]
    demand_forecast: list[ChartSeries]
    weather_forecast: list[WeatherDay]


class DashboardResponse(BaseModel):
    widgets: DashboardWidget
    charts: DashboardCharts
    notifications: list[NotificationOut]


class ScenarioLite(BaseModel):
    best: ProfitScenario | None = None
    average: ProfitScenario | None = None
    worst: ProfitScenario | None = None
