"""Dashboard aggregate endpoint."""
from fastapi import APIRouter

from app.core.deps import CurrentUser, DBSession
from app.services.dashboard_service import get_dashboard

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("")
@router.get("/")
async def dashboard(user: CurrentUser, db: DBSession):
    return await get_dashboard(db, user)
