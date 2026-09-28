"""Profit prediction endpoints."""
import uuid as uuidlib

from fastapi import APIRouter

from app.core.deps import CurrentUser, DBSession, Pagination
from app.core.plans_service import check_quota
from app.models.profit_prediction import ProfitPrediction
from app.schemas.ai_features import ProfitPredictionRequest
from app.services.activity_service import log_activity
from app.services.ownership import resolve_owned_farm
from app.services.profit_service import ProfitService

router = APIRouter(prefix="/profit", tags=["profit"])


@router.post("/predict")
async def predict(payload: ProfitPredictionRequest, user: CurrentUser, db: DBSession):
    check_quota(db, user, "profit_predictions")
    # P0 IDOR fix: a client-supplied farm_id must belong to THIS user.
    owned = resolve_owned_farm(db, user, payload.farm_id)
    if owned is not None:
        payload = payload.model_copy(update={"farm_id": str(owned.id)})
    pred = await ProfitService(db).predict(str(user.id), payload)
    log_activity(db, str(user.id), "profit.predicted", "profit_prediction", str(pred.id), {"crop": payload.crop})
    return pred


@router.get("/predictions")
async def list_predictions(user: CurrentUser, db: DBSession, pagination: Pagination):
    q = (
        db.query(ProfitPrediction)
        .filter(ProfitPrediction.user_id == uuidlib.UUID(str(user.id)))
        .order_by(ProfitPrediction.created_at.desc())
    )
    total = q.count()
    items = q.offset(pagination.offset).limit(pagination.page_size).all()
    return {"items": items, "total": total, "page": pagination.page, "page_size": pagination.page_size}


@router.get("/predictions/{prediction_id}")
async def get_prediction(prediction_id: str, user: CurrentUser, db: DBSession):
    pred = (
        db.query(ProfitPrediction)
        .filter(
            ProfitPrediction.id == uuidlib.UUID(prediction_id),
            ProfitPrediction.user_id == uuidlib.UUID(str(user.id)),
        )
        .first()
    )
    if not pred:
        from app.core.exceptions import NotFoundError

        raise NotFoundError("Prediction not found")
    return pred
