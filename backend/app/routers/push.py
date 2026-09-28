"""Web push subscription endpoints."""
from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.core.deps import CurrentUser, DBSession
from app.services.push_service import push_enabled

router = APIRouter(prefix="/push", tags=["push"])


class SubscribeRequest(BaseModel):
    endpoint: str = Field(min_length=10)
    keys_p256dh: str = Field(min_length=10)
    keys_auth: str = Field(min_length=6)


@router.get("/config")
async def push_config():
    """Public key for the browser's pushManager.subscribe (null when disabled)."""
    from app.core.config import settings

    return {"enabled": push_enabled(), "public_key": settings.VAPID_PUBLIC_KEY or None}


@router.post("/subscribe", status_code=201)
async def subscribe(payload: SubscribeRequest, user: CurrentUser, db: DBSession):
    from sqlalchemy.exc import IntegrityError

    from app.models.push_subscription import PushSubscription

    sub = PushSubscription(
        user_id=user.id,
        endpoint=payload.endpoint,
        p256dh=payload.keys_p256dh,
        auth=payload.keys_auth,
    )
    db.add(sub)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()  # already subscribed from this browser
    return {"ok": True}


@router.delete("/subscribe", status_code=204)
async def unsubscribe(payload: SubscribeRequest, user: CurrentUser, db: DBSession):
    from app.models.push_subscription import PushSubscription

    db.query(PushSubscription).filter(
        PushSubscription.user_id == user.id, PushSubscription.endpoint == payload.endpoint
    ).delete()
    return None
