"""Razorpay checkout/verify flow — offline, signatures computed locally.

Covers the security-critical paths: no keys -> 501, wrong-user order -> 404,
bad signature -> 422, valid signature + captured payment -> plan activated.
"""
import hashlib
import hmac
import uuid

import pytest

from app.models.payment import Payment
from tests.factories import make_user

SECRET = "test-razorpay-secret"


@pytest.fixture
def auth_client(client, sample_user):
    from app.core.deps import get_current_user
    from app.main import fastapi_app

    fastapi_app.dependency_overrides[get_current_user] = lambda: sample_user
    yield client
    fastapi_app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture
def razorpay_keys(monkeypatch):
    from app.core import razorpay_client

    monkeypatch.setattr(razorpay_client, "is_configured", lambda: True)
    monkeypatch.setattr(razorpay_client, "public_key_id", lambda: "rzp_test_key")


@pytest.fixture
def fake_order(monkeypatch):
    """Patch order creation: no network, deterministic order id."""
    from app.core import razorpay_client

    async def fake_create_order(amount_paise, receipt, notes=None):
        # Unique per call: the shared in-memory DB keeps rows across tests and
        # razorpay_order_id is UNIQUE.
        return {"id": f"order_{uuid.uuid4().hex[:12]}", "status": "created"}

    monkeypatch.setattr(razorpay_client, "create_order", fake_create_order)


def _sig(order_id: str, payment_id: str) -> str:
    return hmac.new(SECRET.encode(), f"{order_id}|{payment_id}".encode(), hashlib.sha256).hexdigest()


@pytest.fixture
def secret_key(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "RAZORPAY_KEY_SECRET", SECRET)


def test_checkout_501_when_not_configured(auth_client):
    resp = auth_client.post("/api/v1/subscription/checkout", json={"plan": "pro"})
    assert resp.status_code == 501


def test_checkout_rejects_free_plan(auth_client, razorpay_keys):
    resp = auth_client.post("/api/v1/subscription/checkout", json={"plan": "free"})
    assert resp.status_code == 422


def test_checkout_rejects_cooperative(auth_client, razorpay_keys):
    """Cooperative is 'Contact us' — not purchasable online."""
    resp = auth_client.post("/api/v1/subscription/checkout", json={"plan": "cooperative"})
    assert resp.status_code == 422


def test_checkout_creates_order_and_payment_row(auth_client, sample_user, db_session, razorpay_keys, fake_order):
    resp = auth_client.post("/api/v1/subscription/checkout", json={"plan": "pro"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["amount_inr"] == 29900  # ₹299 from the server-side catalog
    assert body["currency"] == "INR"
    assert body["key_id"] == "rzp_test_key"  # public key only, never the secret

    row = db_session.query(Payment).filter(Payment.razorpay_order_id == body["order_id"]).one()
    assert row.user_id == sample_user.id
    assert row.status == "created"


def test_verify_unknown_order_404(auth_client, razorpay_keys):
    resp = auth_client.post(
        "/api/v1/subscription/verify",
        json={
            "razorpay_order_id": "order_unknown",
            "razorpay_payment_id": "pay_x",
            "razorpay_signature": "deadbeef",
        },
    )
    assert resp.status_code == 404


def test_verify_bad_signature_422(auth_client, sample_user, db_session, razorpay_keys, secret_key, fake_order):
    order_id = auth_client.post("/api/v1/subscription/checkout", json={"plan": "pro"}).json()["order_id"]
    resp = auth_client.post(
        "/api/v1/subscription/verify",
        json={
            "razorpay_order_id": order_id,
            "razorpay_payment_id": "pay_fake",
            "razorpay_signature": "0" * 64,
        },
    )
    assert resp.status_code == 422
    row = db_session.query(Payment).filter(Payment.razorpay_order_id == order_id).one()
    assert row.status == "failed"


def test_verify_not_captured_422(
    auth_client, sample_user, db_session, razorpay_keys, secret_key, fake_order, monkeypatch
):
    from app.core import razorpay_client

    checkout = auth_client.post("/api/v1/subscription/checkout", json={"plan": "pro"}).json()

    async def fake_fetch(payment_id):
        return {"status": "authorized"}

    monkeypatch.setattr(razorpay_client, "fetch_payment", fake_fetch)
    resp = auth_client.post(
        "/api/v1/subscription/verify",
        json={
            "razorpay_order_id": checkout["order_id"],
            "razorpay_payment_id": "pay_ok",
            "razorpay_signature": _sig(checkout["order_id"], "pay_ok"),
        },
    )
    assert resp.status_code == 422


def test_verify_captured_activates_pro(
    auth_client, sample_user, db_session, razorpay_keys, secret_key, fake_order, monkeypatch
):
    from app.core import razorpay_client

    assert sample_user.plan == "free"
    checkout = auth_client.post("/api/v1/subscription/checkout", json={"plan": "pro"}).json()

    async def fake_fetch(payment_id):
        return {"status": "captured"}

    monkeypatch.setattr(razorpay_client, "fetch_payment", fake_fetch)
    resp = auth_client.post(
        "/api/v1/subscription/verify",
        json={
            "razorpay_order_id": checkout["order_id"],
            "razorpay_payment_id": "pay_ok",
            "razorpay_signature": _sig(checkout["order_id"], "pay_ok"),
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["verified"] is True and body["plan"] == "pro"
    db_session.refresh(sample_user)
    assert sample_user.plan == "pro"
    row = db_session.query(Payment).filter(Payment.razorpay_order_id == checkout["order_id"]).one()
    assert row.status == "paid" and row.paid_at is not None


def test_verify_cannot_use_other_users_order(client, sample_user, db_session, razorpay_keys, secret_key, monkeypatch):
    """IDOR check: an order created by user B cannot be verified by user A."""
    from app.core import razorpay_client
    from app.core.deps import get_current_user
    from app.main import fastapi_app

    other = make_user(db_session, email="payer-b@example.com")
    db_session.add(
        Payment(
            user_id=other.id,
            plan="pro",
            amount_inr=29900,
            razorpay_order_id="order_belongs_to_b",
        )
    )
    db_session.flush()

    fastapi_app.dependency_overrides[get_current_user] = lambda: sample_user
    try:
        async def fake_fetch(payment_id):
            return {"status": "captured"}

        monkeypatch.setattr(razorpay_client, "fetch_payment", fake_fetch)
        resp = client.post(
            "/api/v1/subscription/verify",
            json={
                "razorpay_order_id": "order_belongs_to_b",
                "razorpay_payment_id": "pay_b",
                "razorpay_signature": _sig("order_belongs_to_b", "pay_b"),
            },
        )
        assert resp.status_code == 404
    finally:
        fastapi_app.dependency_overrides.pop(get_current_user, None)


def test_webhook_bad_signature_rejected(client):
    resp = client.post(
        "/api/v1/subscription/webhook",
        content=b'{"event":"payment.captured"}',
        headers={"X-Razorpay-Signature": "invalid", "Content-Type": "application/json"},
    )
    assert resp.status_code == 400
