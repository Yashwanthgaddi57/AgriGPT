"""Admin endpoints: agent observability (admin role required)."""
import uuid as uuidlib

from fastapi import APIRouter

from app.core.deps import CurrentUser, DBSession, Pagination
from app.core.exceptions import AgriSphereError
from app.models.agent_log import AgentLog

router = APIRouter(prefix="/admin", tags=["admin"])


class Forbidden(AgriSphereError):
    status_code = 403
    detail = "Admin access required"


@router.get("/agent-logs")
async def agent_logs(user: CurrentUser, db: DBSession, pagination: Pagination):
    if getattr(user, "role", "") != "admin":
        raise Forbidden()
    q = db.query(AgentLog).order_by(AgentLog.created_at.desc())
    total = q.count()
    items = q.offset(pagination.offset).limit(pagination.page_size).all()
    return {"items": items, "total": total, "page": pagination.page, "page_size": pagination.page_size}


@router.get("/users/{user_id}/agent-logs")
async def user_agent_logs(user_id: str, user: CurrentUser, db: DBSession, pagination: Pagination):
    if getattr(user, "role", "") != "admin":
        raise Forbidden()
    q = (
        db.query(AgentLog)
        .filter(AgentLog.user_id == uuidlib.UUID(user_id))
        .order_by(AgentLog.created_at.desc())
    )
    total = q.count()
    items = q.offset(pagination.offset).limit(pagination.page_size).all()
    return {"items": items, "total": total, "page": pagination.page, "page_size": pagination.page_size}
