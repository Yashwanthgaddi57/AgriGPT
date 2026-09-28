"""Farm schemas."""
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.common import UUIDCoercionMixin
from app.schemas.user import SoilType, WaterAvailability


class FarmCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    district: str | None = None
    state: str | None = None
    village: str | None = None
    area_acres: float = Field(gt=0, le=100000)
    soil_type: SoilType = "unknown"
    water_source: WaterAvailability = "rainfed"
    current_crop: str | None = None
    current_season: Literal["kharif", "rabi", "zaid"] | None = None
    planting_date: date | None = None  # when current_crop was sown
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)


class FarmUpdate(BaseModel):
    name: str | None = None
    district: str | None = None
    state: str | None = None
    village: str | None = None
    area_acres: float | None = Field(default=None, gt=0, le=100000)
    soil_type: SoilType | None = None
    water_source: WaterAvailability | None = None
    current_crop: str | None = None
    current_season: Literal["kharif", "rabi", "zaid"] | None = None
    planting_date: date | None = None
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)


class FarmOut(UUIDCoercionMixin):
    id: str
    user_id: str
    name: str
    district: str | None
    state: str | None
    village: str | None
    area_acres: float
    soil_type: str
    water_source: str
    current_crop: str | None
    current_season: str | None
    planting_date: date | None = None
    latitude: float | None
    longitude: float | None
    created_at: datetime

    class Config:
        from_attributes = True
