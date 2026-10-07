"""Local-auth-mode email verification (6-digit code) flow.

These tests run WITHOUT the supabase_mode patch, i.e. exactly how the app
behaves on a no-Supabase local run: registration creates an unconfirmed
account and emails a code; /auth/verify-email flips the local flag; login
stays blocked until then.
"""
import pytest

from app.core.config import settings
from app.core.email_verification import deliver_verification_code
from app.core.local_auth import authenticate_local_user, register_local_user
from app.models.email_verification import EmailVerificationCode
from app.models.user import User
from app.routers import auth as auth_router

REGISTER_BODY = {
    "email": "localfarmer@example.com",
    "password": "Sunflower9!",
    "name": "Local Farmer",
}


@pytest.fixture(autouse=True)
def local_mode(db_session, monkeypatch):
    """Force the local-auth path (it is the default, but be explicit)."""
    monkeypatch.setattr(auth_router, "local_auth_enabled", lambda: True)
    monkeypatch.setattr(settings, "EMAIL_VERIFICATION_RESEND_COOLDOWN_SECONDS", 0)


@pytest.fixture(autouse=True)
def reset_rate_limits():
    """Hermetic rate limiting: the register endpoint allows 10/min per IP,
    and the whole suite shares one TestClient IP with the in-memory fallback
    counters. Reset them per test and keep Redis out of the picture."""
    from app.core import middleware as mw

    mw._group_windows.clear()
    mw._memory_windows.clear()
    mw._redis_dead_until = float("inf")
    yield
    mw._group_windows.clear()
    mw._memory_windows.clear()
    mw._redis_dead_until = 0.0


@pytest.fixture(autouse=True)
def clean_state(db_session):
    db_session.query(EmailVerificationCode).delete()
    db_session.query(User).delete()
    db_session.commit()
    yield
    db_session.query(EmailVerificationCode).delete()
    db_session.query(User).delete()
    db_session.commit()


# --------------------------------------------------------------------------
# /auth/register (local mode)
# --------------------------------------------------------------------------


def test_register_creates_unconfirmed_account_and_sends_code(client, db_session, monkeypatch):
    monkeypatch.setattr(
        auth_router,
        "deliver_verification_code",
        _stub_delivery(True),
    )
    resp = client.post("/api/v1/auth/register", json=REGISTER_BODY)
    assert resp.status_code == 201
    body = resp.json()
    # No tokens: the account must not be signed in before the code is checked.
    assert "access_token" not in body
    assert body["needs_email_confirmation"] is True
    assert body["verification_sent"] is True
    assert _stub_delivery.captured_email == "localfarmer@example.com"

    user = db_session.query(User).filter(User.email == "localfarmer@example.com").one()
    assert user.email_verified is False


def test_register_returns_dev_code_only_when_delivery_fails_in_dev(
    client, monkeypatch
):
    monkeypatch.setattr(auth_router, "deliver_verification_code", _stub_delivery(False))
    resp = client.post("/api/v1/auth/register", json=REGISTER_BODY)
    assert resp.status_code == 201
    body = resp.json()
    assert body["verification_sent"] is False
    # Dev escape hatch so the flow stays testable without a mail provider.
    assert body["dev_code"].isdigit()


def test_duplicate_email_still_conflict(client, monkeypatch):
    monkeypatch.setattr(auth_router, "deliver_verification_code", _stub_delivery(True))
    assert client.post("/api/v1/auth/register", json=REGISTER_BODY).status_code == 201
    resp = client.post("/api/v1/auth/register", json=REGISTER_BODY)
    assert resp.status_code == 401  # AuthError, not a silent re-register


# --------------------------------------------------------------------------
# Login gating (local mode)
# --------------------------------------------------------------------------


def test_login_blocked_until_code_confirmed(client, db_session, monkeypatch):
    monkeypatch.setattr(auth_router, "deliver_verification_code", _stub_delivery(True))
    client.post("/api/v1/auth/register", json=REGISTER_BODY)

    # Correct password, unconfirmed email -> blocked with a "confirm" message
    # (the frontend login page keys its verification banner off this text).
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": REGISTER_BODY["email"], "password": REGISTER_BODY["password"]},
    )
    assert resp.status_code == 401
    assert "confirm" in resp.json()["error"]["detail"].lower()


def test_verify_then_login_succeeds_and_token_works(client, db_session, monkeypatch):
    monkeypatch.setattr(auth_router, "deliver_verification_code", _stub_delivery(True))
    client.post("/api/v1/auth/register", json=REGISTER_BODY)

    code = (
        db_session.query(EmailVerificationCode)
        .filter(EmailVerificationCode.email == REGISTER_BODY["email"])
        .one()
    )
    # The stored hash must not reveal the code; grab it from the stub.
    real_code = _stub_delivery.captured_code

    resp = client.post(
        "/api/v1/auth/verify-email",
        json={"email": REGISTER_BODY["email"], "code": real_code},
    )
    assert resp.status_code == 200
    assert resp.json()["verified"] is True

    user = db_session.query(User).filter(User.email == REGISTER_BODY["email"]).one()
    assert user.email_verified is True

    login = client.post(
        "/api/v1/auth/login",
        json={"email": REGISTER_BODY["email"], "password": REGISTER_BODY["password"]},
    )
    assert login.status_code == 200
    token = login.json()["access_token"]

    me = client.get("/api/v1/profile", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["email"] == REGISTER_BODY["email"]


def test_wrong_code_never_activates(client, db_session, monkeypatch):
    monkeypatch.setattr(auth_router, "deliver_verification_code", _stub_delivery(True))
    client.post("/api/v1/auth/register", json=REGISTER_BODY)

    resp = client.post(
        "/api/v1/auth/verify-email",
        json={"email": REGISTER_BODY["email"], "code": "000000"},
    )
    assert resp.status_code == 401
    user = db_session.query(User).filter(User.email == REGISTER_BODY["email"]).one()
    assert user.email_verified is False


def test_resend_verification_works_in_local_mode(client, db_session, monkeypatch):
    monkeypatch.setattr(auth_router, "deliver_verification_code", _stub_delivery(True))
    client.post("/api/v1/auth/register", json=REGISTER_BODY)
    db_session.query(EmailVerificationCode).delete()
    db_session.commit()

    # Unknown address gets the same generic response (no probing).
    unknown = client.post(
        "/api/v1/auth/resend-verification", json={"email": "ghost@example.com"}
    )
    assert unknown.status_code == 200
    assert db_session.query(EmailVerificationCode).count() == 0

    known = client.post(
        "/api/v1/auth/resend-verification", json={"email": REGISTER_BODY["email"]}
    )
    assert known.status_code == 200
    assert db_session.query(EmailVerificationCode).count() == 1


def test_verification_disabled_signs_in_immediately(client, db_session, monkeypatch):
    monkeypatch.setattr(settings, "REQUIRE_EMAIL_VERIFICATION", False)
    resp = client.post("/api/v1/auth/register", json=REGISTER_BODY)
    assert resp.status_code == 201
    body = resp.json()
    # Legacy behaviour preserved when the flag is explicitly off.
    assert body["access_token"]
    user = db_session.query(User).filter(User.email == REGISTER_BODY["email"]).one()
    assert user.email_verified is True


def test_register_sends_real_email_through_service_layer(db_session, monkeypatch):
    """Integration: deliver_verification_code issues one hashed code and mails it."""
    captured: dict = {}

    async def fake_send(to, code):
        captured["to"] = to
        captured["code"] = code
        return True

    monkeypatch.setattr(
        "app.core.email_verification.send_verification_code_email", fake_send
    )
    register_local_user(db_session, {**REGISTER_BODY})

    import asyncio

    sent, code = asyncio.run(
        deliver_verification_code(db_session, REGISTER_BODY["email"])
    )
    assert sent is True
    assert len(code) == 6
    assert captured == {"to": REGISTER_BODY["email"], "code": code}
    rows = db_session.query(EmailVerificationCode).all()
    assert len(rows) == 1
    assert code not in rows[0].code_hash  # stored hashed, never in clear


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------


def _stub_delivery(should_send: bool):
    async def _impl(db, email):
        from app.core.email_verification import issue_verification_code

        code = issue_verification_code(db, email)
        _stub_delivery.captured_code = code
        _stub_delivery.captured_email = email
        return should_send, code

    _impl.captured_code = None
    _impl.captured_email = None
    return _impl
