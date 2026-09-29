"""Razorpay REST client — order creation, checkout verification, webhooks.

Plain httpx calls (no SDK). The key secret never leaves the backend: the
browser only receives the public key id, and every activation path verifies
Razorpay's HMAC-SHA256 signature server-side before a plan is granted.

Test mode works without KYC — create keys at dashboard.razorpay.com under
Settings → API Keys (Test). Live keys replace them after activation.
"""
import hashlib
import hmac
import logging
from typing import Any

import httpx

from app.core.config import settings

logger = logging.getLogger("app.payments.razorpay")

ORDERS_URL = "https://api.razorpay.com/v1/orders"
PAYMENTS_URL = "https://api.razorpay.com/v1/payments/{payment_id}"


def is_configured() -> bool:
    """True when both key id and secret are present."""
    return settings.payments_enabled


def public_key_id() -> str:
    """Publishable key id for browser-side Checkout (NOT the secret)."""
    return settings.RAZORPAY_KEY_ID.strip()


def _auth() -> tuple[str, str]:
    """Basic-auth tuple Razorpay expects: (key_id, key_secret)."""
    return settings.RAZORPAY_KEY_ID.strip(), settings.RAZORPAY_KEY_SECRET.strip()


async def create_order(amount_paise: int, receipt: str, notes: dict[str, str] | None = None) -> dict[str, Any]:
    """Create a Razorpay order. Raises RuntimeError on gateway rejection."""
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.post(
            ORDERS_URL,
            auth=_auth(),
            json={
                "amount": amount_paise,
                "currency": "INR",
                "receipt": receipt,
                "notes": notes or {},
            },
        )
    if resp.status_code >= 400:
        logger.warning("Razorpay order creation failed: HTTP %s %s", resp.status_code, resp.text[:300])
        raise RuntimeError("Payment gateway rejected the order. Please try again in a moment.")
    return resp.json()


async def fetch_payment(payment_id: str) -> dict[str, Any] | None:
    """Fetch a payment's authoritative status, or None on failure.

    Used as a second opinion after checkout verification: the signature
    proves the payload came from Razorpay, and this call confirms the
    payment is actually captured before the plan is granted.
    """
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.get(PAYMENTS_URL.format(payment_id=payment_id), auth=_auth())
    except Exception:
        return None
    if resp.status_code != 200:
        return None
    return resp.json()


def verify_checkout_signature(order_id: str, payment_id: str, signature: str) -> bool:
    """HMAC-SHA256(order_id|payment_id, key_secret) must equal the signature.

    Constant-time comparison. This is Razorpay's documented checkout
    verification scheme; without it anyone could POST a fake payment id
    and claim Pro for free.
    """
    secret = settings.RAZORPAY_KEY_SECRET.strip().encode()
    expected = hmac.new(secret, f"{order_id}|{payment_id}".encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature or "")


def verify_webhook_signature(body: bytes, signature: str) -> bool:
    """HMAC-SHA256(raw_body, webhook_secret) must equal X-Razorpay-Signature."""
    secret = (settings.RAZORPAY_WEBHOOK_SECRET or "").strip().encode()
    if not secret:
        return False
    expected = hmac.new(secret, body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature or "")
