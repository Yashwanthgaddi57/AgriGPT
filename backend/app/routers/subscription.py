"""Subscription endpoints: plans catalog, Razorpay checkout, activation.

Security model:
  - The browser only ever receives the public key id and the order id.
  - Plan activation happens ONLY in POST /subscription/verify after the
    Razorpay checkout signature (HMAC-SHA256 with the key secret) has been
    verified server-side AND the payment's status is confirmed as `captured`
    via the Razorpay API. A forged success callback therefore grants nothing.
"""
import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.core import razorpay_client
from app.core.config import settings
from app.core.database import get_db
from app.core.deps import CurrentUser
from app.core.exceptions import NotFoundError, ValidationError
from app.core.plans import ALL_PLANS, COOPERATIVE, FREE, PLAN_LIMITS, PLAN_META, PRO, plan_limits
from app.core.plans_service import usage_summary, user_plan
from app.models.payment import Payment
from app.models.user import User
from sqlalchemy.orm import Session

router = APIRouter(prefix="/subscription", tags=["subscription"])
logger = logging.getLogger("app.api.subscription")


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
        "payments_enabled": settings.payments_enabled,
    }


@router.get("")
async def my_subscription(user: CurrentUser, db: Session = Depends(get_db)):
    plan = user_plan(user)
    return {
        "plan": plan,
        "meta": PLAN_META[plan],
        "limits": plan_limits(plan),
        "usage": usage_summary(db, user),
    }


class CheckoutRequest(BaseModel):
    plan: str = Field(pattern="^(pro|cooperative)$")


class CheckoutResponse(BaseModel):
    order_id: str
    amount_inr: int
    currency: str
    key_id: str
    plan: str


class VerifyRequest(BaseModel):
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str


def _plan_amount_paise(plan: str) -> int:
    """Order amount in paise straight from the plan catalog (no frontend input)."""
    meta = PLAN_META[plan]
    price = meta.get("price_inr")
    if not price:  # None (custom-priced) or 0 (free) — not purchasable
        raise ValidationError("That plan is not available for online purchase.")
    return int(price) * 100


def _activate_plan(db: Session, user: User, plan: str) -> None:
    user.plan = plan
    db.add(user)
    db.flush()


@router.post("/checkout", response_model=CheckoutResponse)
async def checkout(payload: CheckoutRequest, user: CurrentUser, db: Session = Depends(get_db)):
    """Open a Razorpay order for a paid plan.

    Returns the browser-side checkout parameters. The plan price is taken
    from the server-side catalog — the client never dictates the amount.
    """
    if not razorpay_client.is_configured():
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
    if payload.plan != PRO:
        # Only Pro is purchasable today; Cooperative is "Contact us".
        raise ValidationError("That plan is not available for online purchase.")
    if user_plan(user) == payload.plan:
        raise ValidationError(f"You are already on the {PLAN_META[payload.plan]['name']} plan.")

    amount = _plan_amount_paise(payload.plan)
    order = await razorpay_client.create_order(
        amount_paise=amount,
        receipt=f"agrigpt-{payload.plan}-{uuid.uuid4().hex[:12]}",
        notes={"user_id": str(user.id), "email": user.email, "plan": payload.plan},
    )

    payment = Payment(
        user_id=user.id,
        plan=payload.plan,
        amount_inr=amount,
        status="created",
        razorpay_order_id=order["id"],
    )
    db.add(payment)
    db.commit()

    return CheckoutResponse(
        order_id=order["id"],
        amount_inr=amount,
        currency="INR",
        key_id=razorpay_client.public_key_id(),
        plan=payload.plan,
    )


@router.post("/verify")
async def verify(payload: VerifyRequest, user: CurrentUser, db: Session = Depends(get_db)):
    """Verify a Razorpay checkout result and activate the paid plan.

    Triple check before activation:
      1. The order exists in our payments table AND belongs to this user.
      2. HMAC-SHA256(order|payment, key_secret) == signature (constant-time).
      3. Razorpay's own API says the payment is `captured`.
    """
    if not razorpay_client.is_configured():
        raise NotFoundError("Payments are not configured.")

    row = (
        db.query(Payment)
        .filter(
            Payment.razorpay_order_id == payload.razorpay_order_id,
            Payment.user_id == user.id,
        )
        .first()
    )
    if row is None:
        raise NotFoundError("Unknown or mismatched order.")

    if not razorpay_client.verify_checkout_signature(
        payload.razorpay_order_id, payload.razorpay_payment_id, payload.razorpay_signature
    ):
        row.status = "failed"
        db.commit()
        logger.warning("Signature verification failed for order %s (user %s)", payload.razorpay_order_id, user.id)
        raise ValidationError("Payment verification failed. If you were charged, contact support.")

    # Second opinion from the gateway: only a captured payment activates.
    pay = await razorpay_client.fetch_payment(payload.razorpay_payment_id)
    if pay is None or pay.get("status") != "captured":
        row.status = "failed"
        db.commit()
        raise ValidationError("Payment is not complete yet. Please try again in a moment.")

    row.razorpay_payment_id = payload.razorpay_payment_id
    row.razorpay_signature = payload.razorpay_signature
    row.status = "paid"
    row.paid_at = datetime.now(timezone.utc)

    _activate_plan(db, user, row.plan)
    db.commit()
    logger.info("Plan %s activated for user %s (payment %s)", row.plan, user.id, payload.razorpay_payment_id)

    return {
        "message": f"{PLAN_META[row.plan]['name']} activated.",
        "plan": row.plan,
        "verified": True,
    }


@router.post("/webhook")
async def webhook(request: Request, db: Session = Depends(get_db)):
    """Razorpay server-to-server events (payment.captured, payment.failed).

    Hardening layer on top of checkout verification: re-syncs payment state
    even if the farmer closed the browser before /verify returned. Requires
    RAZORPAY_WEBHOOK_SECRET; silently ignored when unset.
    """
    body = await request.body()
    signature = request.headers.get("X-Razorpay-Signature", "")
    if not razorpay_client.verify_webhook_signature(body, signature):
        return JSONResponse(status_code=400, content={"detail": "bad signature"})

    try:
        event = await request.json()
    except Exception:
        return JSONResponse(status_code=400, content={"detail": "invalid json"})

    kind = event.get("event", "")
    entity = (event.get("payload", {}).get("payment", {}) or {}).get("entity", {}) or {}
    order_id = entity.get("order_id", "")
    if not order_id:
        return {"handled": False}

    row = db.query(Payment).filter(Payment.razorpay_order_id == order_id).first()
    if row is None:
        return {"handled": False}

    if kind == "payment.captured" and row.status != "paid":
        pay = await razorpay_client.fetch_payment(entity.get("id", ""))
        if pay is not None and pay.get("status") == "captured":
            row.status = "paid"
            row.razorpay_payment_id = entity.get("id") or row.razorpay_payment_id
            row.paid_at = datetime.now(timezone.utc)
            user = db.get(User, row.user_id)
            if user is not None and user_plan(user) != row.plan:
                _activate_plan(db, user, row.plan)
            db.commit()
    elif kind == "payment.failed" and row.status == "created":
        row.status = "failed"
        db.commit()
    return {"handled": True}
