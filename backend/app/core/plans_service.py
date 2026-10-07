"""Server-side plan-limit enforcement.

Reads the user's plan from the DB row and enforces **per-account** usage
quotas on expensive endpoints: each free account gets a fixed one-time
allowance of AI calls (a rolling window is NOT used — counters count every
row the account has ever created). The frontend may hide buttons, but limits
are enforced HERE so direct API calls cannot bypass them.
"""
import logging
import uuid

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


def _count_lifetime(db: Session, model, user_id: str) -> int:
    """Total rows the account has ever created — the per-account quota basis.

    No date filter on purpose: the allowance is one-time per account, not a
    monthly/daily window, so nothing ever 'refills'.
    """
    uid = uuid.UUID(str(user_id))
    return db.query(func.count(model.id)).filter(model.user_id == uid).scalar() or 0


def _count_lifetime_chat(db: Session, user_id: str) -> int:
    """Per-account copilot usage: FARMER messages only (role == 'user')."""
    from app.models.chat import ChatMessage

    uid = uuid.UUID(str(user_id))
    return (
        db.query(func.count(ChatMessage.id))
        .filter(ChatMessage.user_id == uid, ChatMessage.role == "user")
        .scalar()
        or 0
    )


_USAGE_MODEL = {
    "crop_recommendations": Recommendation,
    "disease_scans": DiseaseReport,
    "market_analyses": MarketPrediction,
    "profit_predictions": ProfitPrediction,
}


def check_quota(db: Session, user: User, feature: str) -> None:
    """Raise PlanLimitExceeded (HTTP 429) when the per-account quota is used up.

    Raises nothing for unlimited plans.
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
    used = _count_lifetime(db, model, str(user.id))
    if used >= limit:
        raise PlanLimitExceeded(
            f"You've used all {limit} included on the {plan} plan. "
            "Upgrade to Pro for unlimited usage."
        )


def check_chat_quota(db: Session, user: User) -> None:
    """Per-account copilot allowance (free capped, pro unlimited)."""
    plan = user_plan(user)
    if is_unlimited(plan, "chat_messages"):
        return
    limit = plan_limits(plan).get("chat_messages")
    if not limit:
        return
    used = _count_lifetime_chat(db, str(user.id))
    if used >= limit:
        raise PlanLimitExceeded(
            f"You've used all {limit} copilot messages included on the {plan} plan. "
            "Upgrade to Pro for unlimited chats."
        )


def usage_summary(db: Session, user: User) -> dict:
    """Current usage vs quota for GET /subscription."""
    plan = user_plan(user)
    out: dict[str, dict] = {}
    for feature, model in _USAGE_MODEL.items():
        limit = plan_limits(plan).get(feature)
        out[feature] = {
            "used": _count_lifetime(db, model, str(user.id)),
            "limit": limit,  # -1 = unlimited
        }
    # Chat counts farmer messages only, same basis as the enforcement check.
    chat_limit = plan_limits(plan).get("chat_messages")
    out["chat_messages"] = {
        "used": _count_lifetime_chat(db, str(user.id)),
        "limit": chat_limit,
    }
    return out
