"""Subscription endpoints: plans catalog + current usage.

Payment processing is NOT integrated yet. The checkout endpoint returns 501
so the frontend can honestly direct farmers to contact sales / waitlist
instead of faking a payment success. When a payment provider is added, wire
webhook-verified activation into activate_plan() below (never trust a
frontend success callback).
"""
from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.core.deps import CurrentUser, DBSession
from app.core.plans import ALL_PLANS, PLAN_LIMITS, PLAN_META, plan_limits
from app.core.plans_service import usage_summary, user_plan

router = APIRouter(prefix="/subscription", tags=["subscription"])


@router.get("/plans")
async def plans():
    """Plan catalog for the pricing page. Single source of truth."""
    return {
        "plans": [
            {
                "id": pid,
                **PLAN_META[pid],
                "limits": PLAN_LIMITS[pid],
            }
            for pid in ALL_PLANS
        ],
        "payments_enabled": False,
    }


@router.get("")
async def my_subscription(user: CurrentUser, db: DBSession):
    plan = user_plan(user)
    return {
        "plan": plan,
        "meta": PLAN_META[plan],
        "limits": plan_limits(plan),
        "usage": usage_summary(db, user),
    }


@router.post("/checkout")
async def checkout(user: CurrentUser):
    """Placeholder until a payment provider is integrated.

    Returns 501 Not Implemented — the UI must not fake a successful payment.
    """
    return JSONResponse(
        status_code=501,
        content={
            "error": {
                "code": "PaymentsNotImplemented",
                "detail": (
                    "Online payments are coming soon. To upgrade, contact "
                    "support or join the Pro waitlist."
                ),
                "path": "/api/v1/subscription/checkout",
            }
        },
    )
