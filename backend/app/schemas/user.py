"""User request/response schemas."""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field

from app.schemas.common import UUIDCoercionMixin

SoilType = Literal["black", "alluvial", "loamy", "clay", "sandy", "silt", "laterite", "red", "peaty", "unknown"]
WaterAvailability = Literal["rainfed", "canal", "borewell", "well", "river", "pond", "none"]


class ProfileComplete(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    phone: str | None = Field(default=None, max_length=20)
    district: str | None = Field(default=None, max_length=120)
    state: str | None = Field(default=None, max_length=120)
    village: str | None = Field(default=None, max_length=120)
    farm_size_acres: float = Field(default=0, ge=0, le=100000)
    soil_type: SoilType = "unknown"
    water_availability: WaterAvailability = "rainfed"
    language: str = "en"


class ProfileUpdate(ProfileComplete):
    # name is NOT required on update: the onboarding wizard PATCHes profile
    # fields only (state/district/size/soil/water/language) and must not 422
    # just because it doesn't echo the name back. Absent fields are untouched
    # (the service uses exclude_unset).
    name: str | None = Field(default=None, min_length=1, max_length=120)  # type: ignore[assignment]


class ProfileOut(UUIDCoercionMixin):
    id: str
    email: EmailStr
    name: str
    phone: str | None
    district: str | None
    state: str | None
    village: str | None
    farm_size_acres: float
    soil_type: str
    water_availability: str
    language: str
    avatar_url: str | None
    role: str
    plan: str = "free"
    onboarding_completed: bool
    created_at: datetime

    class Config:
        from_attributes = True
