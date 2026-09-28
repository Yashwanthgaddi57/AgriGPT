"""User profile and farm endpoints."""
from fastapi import APIRouter

from app.core.deps import CurrentUser, DBSession
from app.models.farm import Farm
from app.schemas.farm import FarmCreate, FarmOut, FarmUpdate
from app.schemas.user import ProfileOut, ProfileUpdate
from app.services.activity_service import log_activity
from app.services.farm_service import FarmService
from app.services.user_service import UserService

router = APIRouter(tags=["users"])


@router.get("/profile", response_model=ProfileOut)
async def get_profile(user: CurrentUser):
    return user


@router.patch("/profile", response_model=ProfileOut)
async def update_profile(payload: ProfileUpdate, user: CurrentUser, db: DBSession):
    updated = UserService(db).update_profile(user, payload)
    log_activity(db, str(user.id), "profile.updated", "user", str(user.id))
    return updated


# ---------------- Farms ----------------
@router.get("/farms", response_model=list[FarmOut])
async def list_farms(user: CurrentUser, db: DBSession):
    return FarmService(db).list_farms(str(user.id))


@router.post("/farms", response_model=FarmOut, status_code=201)
async def create_farm(payload: FarmCreate, user: CurrentUser, db: DBSession):
    farm = FarmService(db).create_farm(str(user.id), payload)
    log_activity(db, str(user.id), "farm.created", "farm", str(farm.id), {"name": farm.name})
    return farm


@router.get("/farms/{farm_id}", response_model=FarmOut)
async def get_farm(farm_id: str, user: CurrentUser, db: DBSession):
    return FarmService(db).get_farm(str(user.id), farm_id)


@router.patch("/farms/{farm_id}", response_model=FarmOut)
async def update_farm(farm_id: str, payload: FarmUpdate, user: CurrentUser, db: DBSession):
    farm = FarmService(db).update_farm(str(user.id), farm_id, payload)
    log_activity(db, str(user.id), "farm.updated", "farm", farm_id)
    return farm


@router.delete("/farms/{farm_id}", status_code=204)
async def delete_farm(farm_id: str, user: CurrentUser, db: DBSession):
    FarmService(db).delete_farm(str(user.id), farm_id)
    log_activity(db, str(user.id), "farm.deleted", "farm", farm_id)
