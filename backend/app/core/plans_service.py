"""Server-side plan-limit enforcement.

Reads the user's plan from the DB row and enforces monthly (or daily, for
chat) usage quotas on expensive endpoints. The frontend may hide buttons,
but limits are enforced HERE so direct API calls cannot bypass them.
"""
import logging
import uuid
from datetime import date, datetime, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.exceptions import ValidationError
from app.core.plans import FREE, PLAN_LIMITS, is_unlimited, plan_limits
from app.models.disease_report import DiseaseReport
from app.models.market_prediction import MarketPrediction
from app.models.profit_prediction import ProfitPrediction
from app.models.recommendation import Recommendation
from app.models.user import User

logger = logging.getLogger("app.plans")


class PlanLimitExceeded(ValidationError):
    status_code = 429
    detail = "Plan limit reached"


def user_plan(user: User) -> str:
    plan = (getattr(user, "plan", None) or FREE).lower()
    return plan if plan in PLAN_LIMITS else FREE


def _count_this_month(db: Session, model, user_id: str) -> int:
    uid = uuid.UUID(str(user_id))
    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    return (
        db.query(func.count(model.id))
        .filter(model.user_id == uid, model.created_at >= month_start)
        .scalar()
        or 0
    )


def _count_today(db: Session, model, user_id: str) -> int:
    uid = uuid.UUID(str(user_id))
    today_start = datetime.combine(date.today(), datetime.min.time(), tzinfo=timezone.utc)
    q = db.query(func.count(model.id)).filter(
        model.user_id == uid, model.created_at >= today_start
    )
    # Chat quota counts FARMER messages only (role == 'user'), not the
    # assistant's replies — otherwise "20 messages/day" would really be 10 turns.
    if hasattr(model, "role"):
        q = q.filter(model.role == "user")
    return q.scalar() or 0


_USAGE_MODEL = {
    "crop_recommendations": Recommendation,
    "disease_scans": DiseaseReport,
    "market_analyses": MarketPrediction,
    "profit_predictions": ProfitPrediction,
}


def check_quota(db: Session, user: User, feature: str) -> None:
    """Raise PlanLimitExceeded (HTTP 429) when the monthly quota is exhausted.

    Raises nothing for unlimited plans. Chat uses check_chat_quota (daily).
    """
    plan = user_plan(user)
    if is_unlimited(plan, feature):
        return
    limit = plan_limits(plan).get(feature)
    if limit is None:  # unknown feature -> do not block
        return
    model = _USAGE_MODEL.get(feature)
    if model is None:
        return
    used = _count_this_month(db, model, str(user.id))
    if used >= limit:
        raise PlanLimitExceeded(
            f"You've reached the {plan} plan limit of {limit} this month. "
            "Upgrade to Pro for unlimited usage."
        )


def check_chat_quota(db: Session, user: User) -> None:
    """Daily quota on farmer-sent messages (free capped, pro unlimited)."""
    from app.models.chat import ChatMessage

    plan = user_plan(user)
    if is_unlimited(plan, "chat_messages_per_day"):
        return
    limit = plan_limits(plan).get("chat_messages_per_day")
    if not limit:
        return
    used = _count_today(db, ChatMessage, str(user.id))
    if used >= limit:
        raise PlanLimitExceeded(
            f"You've reached the {plan} plan limit of {limit} copilot messages per day. "
            "Upgrade to Pro for unlimited chats."
        )


def usage_summary(db: Session, user: User) -> dict:
    """Current usage vs quota for GET /subscription."""
    plan = user_plan(user)
    out: dict[str, dict] = {}
    for feature, model in _USAGE_MODEL.items():
        limit = plan_limits(plan).get(feature)
        out[feature] = {
            "used": _count_this_month(db, model, str(user.id)),
            "limit": limit,  # -1 = unlimited
        }
    return out
