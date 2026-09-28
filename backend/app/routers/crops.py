"""Crop recommendation endpoints."""
from fastapi import APIRouter

from app.core.deps import CurrentUser, DBSession, Pagination
from app.core.plans_service import check_quota
from app.services.activity_service import log_activity
from app.services.agent_log_service import log_agent_run
from app.services.crop_service import CropService
from app.services.ownership import resolve_owned_farm
from app.schemas.ai_features import CropRecommendationRequest

router = APIRouter(prefix="/crops", tags=["crops"])


@router.post("/recommend")
async def recommend(payload: CropRecommendationRequest, user: CurrentUser, db: DBSession):
    check_quota(db, user, "crop_recommendations")
    # P0 IDOR fix: a client-supplied farm_id must belong to THIS user.
    owned = resolve_owned_farm(db, user, payload.farm_id)
    if owned is not None:
        payload = payload.model_copy(update={"farm_id": str(owned.id)})
    service = CropService(db)
    rec = await service.recommend(str(user.id), payload)
    log_activity(db, str(user.id), "crop.recommended", "recommendation", str(rec.id), {"location": payload.location})
    log_agent_run(
        db,
        agent="crop_recommendation",
        action="recommend",
        user_id=str(user.id),
        input_data=payload.model_dump(),
        latency_ms=None,
        tokens=(rec.prompt_tokens or 0) + (rec.completion_tokens or 0),
    )
    return rec


@router.get("/history")
async def history(user: CurrentUser, db: DBSession, pagination: Pagination):
    from app.models.recommendation import Recommendation
    import uuid as uuidlib

    q = (
        db.query(Recommendation)
        .filter(Recommendation.user_id == uuidlib.UUID(str(user.id)))
        .order_by(Recommendation.created_at.desc())
    )
    total = q.count()
    items = q.offset(pagination.offset).limit(pagination.page_size).all()
    return {"items": items, "total": total, "page": pagination.page, "page_size": pagination.page_size}
