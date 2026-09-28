"""Location resolution: exact farmer coordinates drive everything.

Resolution order (most precise wins):
  1. Primary farm's saved coordinates (map pin / GPS, most field-specific)
  2. Profile coordinates (saved on the user row)
  3. District/village name geocoding (least precise fallback)

Everything downstream — weather, mandi prices, vendors, AI context —
consumes `resolve_location()` output rather than guessing independently.
"""
import logging
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models.farm import Farm
from app.models.user import User
from app.services.geo_service import geocode_forward

logger = logging.getLogger("app.geo")


@dataclass
class FarmerLocation:
    latitude: float
    longitude: float
    precision: str  # "gps" | "map_pin" | "district"
    label: str  # human-readable, e.g. "Ozar, Nashik, Maharashtra"
    village: str | None = None
    district: str | None = None
    state: str | None = None

    def to_dict(self) -> dict:
        return {
            "latitude": self.latitude,
            "longitude": self.longitude,
            "precision": self.precision,
            "label": self.label,
            "village": self.village,
            "district": self.district,
            "state": self.state,
        }


def resolve_location(db: Session, user: User, farm_id: str | None = None) -> FarmerLocation:
    """Best-known coordinates for a farmer, with precision metadata."""
    # 1) Explicit farm (or primary farm) coordinates
    farm_q = db.query(Farm).filter(Farm.user_id == user.id)
    farm: Farm | None = None
    if farm_id:
        farm = farm_q.filter(Farm.id == farm_id).first()
    if farm is None:
        farm = farm_q.order_by(Farm.created_at.asc()).first()

    if farm is not None and farm.latitude is not None and farm.longitude is not None:
        return FarmerLocation(
            latitude=float(farm.latitude),
            longitude=float(farm.longitude),
            precision="map_pin",
            label=", ".join(filter(None, [farm.village, farm.district, farm.state])) or farm.name,
            village=farm.village,
            district=farm.district,
            state=farm.state,
        )

    # 2) Profile coordinates (set via GPS capture or map pin on /profile)
    if user.latitude is not None and user.longitude is not None:
        label = ", ".join(filter(None, [user.village, user.district, user.state])) or "Saved location"
        return FarmerLocation(
            latitude=float(user.latitude),
            longitude=float(user.longitude),
            precision="gps",
            label=label,
            village=user.village,
            district=user.district,
            state=user.state,
        )

    # 3) District/village text only (no coords saved). Callers wanting the
    # network-geocoded fallback should use resolve_location_async.
    text = ", ".join(filter(None, [user.village, user.district, user.state])) or user.district or "Nashik, Maharashtra"
    return FarmerLocation(
        latitude=_FALLBACK["lat"],
        longitude=_FALLBACK["lng"],
        precision="district",
        label=text,
        village=user.village,
        district=user.district,
        state=user.state,
    )


_FALLBACK = {"lat": 19.9975, "lng": 73.7898}  # Nashik


async def resolve_location_async(
    db: Session, user: User, farm_id: str | None = None
) -> FarmerLocation:
    """Async variant: falls back to geocoding district text when no saved pin."""
    loc = resolve_location(db, user, farm_id)
    if loc.precision != "district":
        return loc

    text = ", ".join(filter(None, [user.village, user.district, user.state]))
    if not text:
        text = user.district or "Nashik, Maharashtra"
    geo = await geocode_forward(text)
    if geo:
        return FarmerLocation(
            latitude=geo["latitude"],
            longitude=geo["longitude"],
            precision="district",
            label=geo.get("name") or text,
            village=user.village,
            district=user.district or geo.get("admin1"),
            state=user.state or geo.get("admin1"),
        )
    return loc
