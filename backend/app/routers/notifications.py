"""Notification endpoints."""
from fastapi import APIRouter

from app.core.deps import CurrentUser, DBSession
from app.schemas.ai_features import MarkReadRequest
from app.services.notification_service import NotificationService

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("")
async def list_notifications(user: CurrentUser, db: DBSession, unread_only: bool = False, limit: int = 50):
    items = NotificationService(db).list_for_user(str(user.id), unread_only, limit)
    return {"items": items, "unread_count": NotificationService(db).unread_count(str(user.id))}


@router.post("/mark-read")
async def mark_read(payload: MarkReadRequest, user: CurrentUser, db: DBSession):
    count = NotificationService(db).mark_read(str(user.id), payload.ids)
    return {"marked": count}


@router.get("/unread-count")
async def unread_count(user: CurrentUser, db: DBSession):
    return {"count": NotificationService(db).unread_count(str(user.id))}
