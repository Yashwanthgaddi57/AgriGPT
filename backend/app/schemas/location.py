"""Location & vendor schemas."""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class LocationUpdate(BaseModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    source: Literal["gps", "map_pin"] = "map_pin"
    # Optional reverse-geocoded address parts from the client
    village: str | None = None
    district: str | None = None
    state: str | None = None


class LocationOut(BaseModel):
    latitude: float
    longitude: float
    precision: str
    label: str
    village: str | None
    district: str | None
    state: str | None


class MandiOut(BaseModel):
    id: str
    name: str
    city: str | None
    district: str | None
    state: str | None
    distance_km: float
    major_crops: list[str]


class VendorOut(BaseModel):
    id: str
    name: str
    category: str
    description: str | None
    phone: str | None
    address: str | None
    city: str | None
    district: str | None
    state: str | None
    latitude: float
    longitude: float
    crops: list[str]
    distance_km: float
    raw_distance_km: float = 0.0
    matches_crop: bool
    source: str = "directory"
    # True only for the nearest-3 fallback shown when the requested radius had
    # no vendors at all — the UI must label these as outside the radius.
    beyond_radius: bool = False
    # Extra fields from the agri-service directory (all optional: absent data is
    # simply omitted, never invented).
    subcategory: str | None = None
    website: str | None = None
    pincode: str | None = None
    rating: float | None = None
    review_count: int | None = None
    opening_hours: str | None = None


class NearbyVendorsOut(BaseModel):
    location: LocationOut
    radius_km: int = 50  # requested radius, strictly applied
    total: int  # count of items actually within radius_km
    items: list[VendorOut]


class AgriServiceOut(BaseModel):
    """One nearby agricultural business, shaped for the map + result list.

    Every optional field is omitted (null) rather than guessed when the source
    has no data — the UI hides what is missing instead of inventing it.
    """

    id: str
    name: str
    category: str
    subcategory: str | None = None
    description: str | None = None
    latitude: float
    longitude: float
    address: str | None = None
    village: str | None = None
    city: str | None = None
    district: str | None = None
    state: str | None = None
    pincode: str | None = None
    phone: str | None = None
    website: str | None = None
    rating: float | None = None
    review_count: int | None = None
    opening_hours: str | None = None
    distance_km: float
    crops: list[str] = []
    matches_crop: bool = False
    beyond_radius: bool = False
    # Human-readable data source + the raw machine value behind it.
    source: str = "OpenStreetMap"
    source_kind: str = "osm"
    last_updated: datetime | None = None


class AgriNearbyOut(BaseModel):
    """`GET /agri/nearby` response."""

    results: list[AgriServiceOut]
    location: LocationOut
    radius_km: int
    total: int
    categories: list[str] = []
    note: str | None = None
