"""Analytics endpoints."""
import uuid as uuidlib

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.core.deps import CurrentUser, DBSession, Pagination
from app.models.activity import Activity
from app.services.activity_service import log_activity
from app.services.analytics_service import get_kpis

router = APIRouter(prefix="/analytics", tags=["analytics"])


class EventRequest(BaseModel):
    event: str = Field(min_length=1, max_length=80)
    metadata: dict | None = None


# Allowlist so the endpoint cannot be abused as arbitrary storage.
ALLOWED_EVENTS = {
    "signup_started", "signup_completed", "farm_profile_completed",
    "crop_plan_started", "crop_plan_completed", "disease_scan_started",
    "disease_scan_completed", "profit_calculator_used", "market_page_viewed",
    "subscription_page_viewed", "subscription_started", "subscription_completed",
    "voice_input_used", "tts_used", "plan_wizard_started", "plan_wizard_completed",
}


@router.post("/events")
async def track_event(payload: EventRequest, user: CurrentUser, db: DBSession):
    """Privacy-conscious product-analytics events (first-party only).

    Stores the event name + coarse metadata in the existing activities table.
    No PII beyond what is already in the session.
    """
    if payload.event not in ALLOWED_EVENTS:
        return {"tracked": False}
    log_activity(db, str(user.id), f"event.{payload.event}", "analytics", None, payload.metadata or {})
    return {"tracked": True}


@router.get("/kpis")
async def kpis(user: CurrentUser, db: DBSession):
    return get_kpis(db, str(user.id))


@router.get("/activities")
async def activities(user: CurrentUser, db: DBSession, pagination: Pagination):
    q = (
        db.query(Activity)
        .filter(Activity.user_id == uuidlib.UUID(str(user.id)))
        .order_by(Activity.created_at.desc())
    )
    total = q.count()
    items = q.offset(pagination.offset).limit(pagination.page_size).all()
    return {"items": items, "total": total, "page": pagination.page, "page_size": pagination.page_size}
