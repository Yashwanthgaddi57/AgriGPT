"""Email-verification (6-digit code) flow tests.

The codes are generated and stored by this backend, so these tests exercise
our own contract rather than a Supabase template: how a code is issued, when
it is accepted, and what /auth/register and /auth/verify-email return.
Supabase and the local-auth check are patched, so nothing here touches a real
project.
"""
from datetime import datetime, timedelta, timezone

import pytest

from app.core.config import settings
from app.core.email_verification import (
    VerificationError,
    generate_code,
    issue_verification_code,
    verify_verification_code,
)
from app.models.email_verification import EmailVerificationCode
from app.routers import auth as auth_router

SESSION = {
    "access_token": "access-token",
    "refresh_token": "refresh-token",
    "expires_in": 3600,
    "token_type": "bearer",
    "user": {"id": "user-1"},
}


@pytest.fixture(autouse=True)
def clean_codes(db_session):
    """The in-memory engine is shared across tests, so clear codes each time."""
    db_session.query(EmailVerificationCode).delete()
    db_session.commit()
    yield
    db_session.query(EmailVerificationCode).delete()
    db_session.commit()


@pytest.fixture
def supabase_mode(monkeypatch):
    """Force the Supabase (non-local) auth path."""
    monkeypatch.setattr(auth_router, "local_auth_enabled", lambda: False)


@pytest.fixture
def no_cooldown(monkeypatch):
    """Disable the resend cooldown unless a test is specifically about it."""
    monkeypatch.setattr(settings, "EMAIL_VERIFICATION_RESEND_COOLDOWN_SECONDS", 0)


# --------------------------------------------------------------------------
# Code issuing and checking
# --------------------------------------------------------------------------


def test_generated_code_is_six_digits():
    for _ in range(50):
        code = generate_code()
        assert len(code) == 6 and code.isdigit()


def test_code_is_stored_hashed_not_in_clear(db_session, no_cooldown):
    code = issue_verification_code(db_session, "Farmer@Example.com")
    row = db_session.query(EmailVerificationCode).one()
    # A leaked database must not hand out working codes.
    assert code not in row.code_hash
    assert len(row.code_hash) == 64
    # The address is normalised so casing can't create two live codes.
    assert row.email == "farmer@example.com"


def test_code_expires(db_session, no_cooldown):
    code = issue_verification_code(db_session, "farmer@example.com")
    row = db_session.query(EmailVerificationCode).one()
    row.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    db_session.commit()

    with pytest.raises(VerificationError, match="expired"):
        verify_verification_code(db_session, "farmer@example.com", code)


def test_attempt_limit_locks_out_even_the_right_code(db_session, no_cooldown, monkeypatch):
    monkeypatch.setattr(settings, "EMAIL_VERIFICATION_MAX_ATTEMPTS", 3)
    code = issue_verification_code(db_session, "farmer@example.com")

    for _ in range(3):
        with pytest.raises(VerificationError, match="wrong or has expired"):
            verify_verification_code(db_session, "farmer@example.com", "000000")

    # Guessing must not become easier by simply trying more.
    with pytest.raises(VerificationError, match="Too many attempts"):
        verify_verification_code(db_session, "farmer@example.com", code)


def test_new_code_supersedes_the_previous_one(db_session, no_cooldown):
    first = issue_verification_code(db_session, "farmer@example.com")
    second = issue_verification_code(db_session, "farmer@example.com")

    with pytest.raises(VerificationError, match="wrong or has expired"):
        verify_verification_code(db_session, "farmer@example.com", first)

    # The newest email is always the one that works.
    verify_verification_code(db_session, "farmer@example.com", second)


def test_a_used_code_cannot_be_replayed(db_session, no_cooldown):
    code = issue_verification_code(db_session, "farmer@example.com")
    verify_verification_code(db_session, "farmer@example.com", code)

    with pytest.raises(VerificationError, match="wrong or has expired"):
        verify_verification_code(db_session, "farmer@example.com", code)


def test_resend_cooldown_blocks_an_immediate_reissue(db_session, monkeypatch):
    monkeypatch.setattr(settings, "EMAIL_VERIFICATION_RESEND_COOLDOWN_SECONDS", 60)
    issue_verification_code(db_session, "farmer@example.com")

    with pytest.raises(VerificationError, match="wait"):
        issue_verification_code(db_session, "farmer@example.com")


def test_empty_code_is_rejected(db_session):
    issue_verification_code(db_session, "farmer@example.com")
    with pytest.raises(VerificationError, match="6-digit"):
        verify_verification_code(db_session, "farmer@example.com", "   ")


def test_unknown_email_has_no_code(db_session):
    with pytest.raises(VerificationError, match="wrong or has expired"):
        verify_verification_code(db_session, "nobody@example.com", "123456")


# --------------------------------------------------------------------------
# /auth/register
# --------------------------------------------------------------------------


def test_register_requires_verification_when_enabled(client, supabase_mode, monkeypatch):
    delivered: list[str] = []

    async def fake_signup(email, password, metadata=None):
        return {"access_token": None, "user": {"id": "user-1"}}

    async def fake_deliver(db, email):
        delivered.append(email)
        return True, "654321"

    async def unexpected_sign_in(email, password):
        raise AssertionError("signup must not sign in before the code is verified")

    monkeypatch.setattr(auth_router, "supabase_sign_up", fake_signup)
    monkeypatch.setattr(auth_router, "deliver_verification_code", fake_deliver)
    monkeypatch.setattr(auth_router, "supabase_sign_in", unexpected_sign_in)
    monkeypatch.setattr(settings, "REQUIRE_EMAIL_VERIFICATION", True)

    resp = client.post(
        "/api/v1/auth/register",
        json={"email": "farmer@example.com", "password": "sup3rsecret", "name": "Ramesh"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["needs_email_confirmation"] is True
    assert body["verification_sent"] is True
    assert "access_token" not in body
    assert "dev_code" not in body  # delivery succeeded -> no dev escape hatch
    assert delivered == ["farmer@example.com"]


def test_register_exposes_dev_code_only_in_dev_without_delivery(
    client, supabase_mode, monkeypatch
):
    async def fake_signup(email, password, metadata=None):
        return {"access_token": None, "user": {"id": "user-1"}}

    async def failed_deliver(db, email):
        return False, "123456"

    monkeypatch.setattr(auth_router, "supabase_sign_up", fake_signup)
    monkeypatch.setattr(auth_router, "deliver_verification_code", failed_deliver)
    monkeypatch.setattr(settings, "REQUIRE_EMAIL_VERIFICATION", True)
    monkeypatch.setattr(settings, "ENVIRONMENT", "development")

    resp = client.post(
        "/api/v1/auth/register",
        json={"email": "farmer@example.com", "password": "sup3rsecret", "name": "Ramesh"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["verification_sent"] is False
    # Never claim mail is coming when the provider refused it.
    assert "could not send" in body["message"]
    # Dev-only escape hatch so the flow is testable without a mail provider.
    assert body["dev_code"] == "123456"


def test_register_never_exposes_dev_code_in_production(client, supabase_mode, monkeypatch):
    async def fake_signup(email, password, metadata=None):
        return {"access_token": None, "user": {"id": "user-1"}}

    async def failed_deliver(db, email):
        return False, "123456"

    monkeypatch.setattr(auth_router, "supabase_sign_up", fake_signup)
    monkeypatch.setattr(auth_router, "deliver_verification_code", failed_deliver)
    monkeypatch.setattr(settings, "REQUIRE_EMAIL_VERIFICATION", True)
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")

    resp = client.post(
        "/api/v1/auth/register",
        json={"email": "farmer@example.com", "password": "sup3rsecret", "name": "Ramesh"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["verification_sent"] is False
    # Production must never leak the code, whatever the delivery state.
    assert "dev_code" not in body


def test_register_signs_in_when_verification_disabled(client, supabase_mode, monkeypatch):
    async def fake_signup(email, password, metadata=None):
        return {"access_token": None, "user": {"id": "user-1"}}

    async def fake_sign_in(email, password):
        return SESSION

    async def unexpected_deliver(db, email):
        raise AssertionError("no verification email when verification is off")
        return True, ""  # pragma: no cover

    monkeypatch.setattr(auth_router, "supabase_sign_up", fake_signup)
    monkeypatch.setattr(auth_router, "supabase_sign_in", fake_sign_in)
    monkeypatch.setattr(auth_router, "deliver_verification_code", unexpected_deliver)
    monkeypatch.setattr(settings, "REQUIRE_EMAIL_VERIFICATION", False)
    monkeypatch.setattr(settings, "ENVIRONMENT", "development")

    resp = client.post(
        "/api/v1/auth/register",
        json={"email": "farmer@example.com", "password": "sup3rsecret", "name": "Ramesh"},
    )
    assert resp.status_code == 201
    assert resp.json()["access_token"] == "access-token"


# --------------------------------------------------------------------------
# /auth/verify-email
# --------------------------------------------------------------------------


def test_verify_email_confirms_the_account(client, db_session, supabase_mode, no_cooldown, monkeypatch):
    confirmed: list[str] = []

    async def fake_confirm(email):
        confirmed.append(email)
        return True

    monkeypatch.setattr(auth_router, "admin_confirm_email", fake_confirm)
    code = issue_verification_code(db_session, "farmer@example.com")

    resp = client.post(
        "/api/v1/auth/verify-email",
        json={"email": "farmer@example.com", "code": code},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["verified"] is True
    assert body["email"] == "farmer@example.com"
    assert confirmed == ["farmer@example.com"]
    # Confirming activates the account; it does not mint a session, because no
    # password is available at this point.
    assert "access_token" not in body


def test_verify_email_rejects_wrong_code(client, db_session, supabase_mode, no_cooldown, monkeypatch):
    async def should_not_be_called(email):
        raise AssertionError("a wrong code must not reach Supabase")

    monkeypatch.setattr(auth_router, "admin_confirm_email", should_not_be_called)
    issue_verification_code(db_session, "farmer@example.com")

    resp = client.post(
        "/api/v1/auth/verify-email",
        json={"email": "farmer@example.com", "code": "000000"},
    )
    assert resp.status_code == 401
    # The message must not assert the code expired when the user mistyped it.
    assert "wrong or has expired" in resp.json()["error"]["detail"]


def test_verify_email_reports_a_failed_confirmation(client, db_session, supabase_mode, no_cooldown, monkeypatch):
    async def refused(email):
        return False

    monkeypatch.setattr(auth_router, "admin_confirm_email", refused)
    code = issue_verification_code(db_session, "farmer@example.com")

    resp = client.post(
        "/api/v1/auth/verify-email",
        json={"email": "farmer@example.com", "code": code},
    )
    assert resp.status_code == 401
    # A correct code is not enough if the account could not be activated.
    assert "couldn't activate" in resp.json()["error"]["detail"]


def test_verify_email_without_code_is_rejected(client, supabase_mode):
    resp = client.post("/api/v1/auth/verify-email", json={"email": "farmer@example.com"})
    assert resp.status_code == 401
    assert "6-digit" in resp.json()["error"]["detail"]


def test_verify_email_without_email_is_rejected(client, supabase_mode):
    resp = client.post("/api/v1/auth/verify-email", json={"code": "123456"})
    assert resp.status_code == 401
    assert "6-digit" in resp.json()["error"]["detail"]


def test_verify_email_unavailable_in_local_mode(client):
    # local_auth_enabled() is True by default here (placeholder SUPABASE_URL).
    resp = client.post(
        "/api/v1/auth/verify-email",
        json={"email": "farmer@example.com", "code": "123456"},
    )
    assert resp.status_code == 401


# --------------------------------------------------------------------------
# /auth/resend-verification
# --------------------------------------------------------------------------


def test_resend_is_generic_for_an_unknown_email(client, supabase_mode, monkeypatch):
    async def unknown(email):
        return None

    async def should_not_send(db, email):
        raise AssertionError("no code may be issued for an unknown account")

    monkeypatch.setattr(auth_router, "admin_get_user_by_email", unknown)
    monkeypatch.setattr(auth_router, "deliver_verification_code", should_not_send)

    resp = client.post("/api/v1/auth/resend-verification", json={"email": "nobody@example.com"})
    assert resp.status_code == 200
    # Identical wording to the known-account case, so this cannot be used to
    # discover which addresses are registered.
    assert "if that account exists" in resp.json()["message"]


def test_resend_sends_a_new_code_for_a_known_email(client, supabase_mode, monkeypatch):
    sent: list[str] = []

    async def known(email):
        return {"id": "user-1", "email": email}

    async def fake_deliver(db, email):
        sent.append(email)
        return True, "111222"

    monkeypatch.setattr(auth_router, "admin_get_user_by_email", known)
    monkeypatch.setattr(auth_router, "deliver_verification_code", fake_deliver)

    resp = client.post("/api/v1/auth/resend-verification", json={"email": "farmer@example.com"})
    assert resp.status_code == 200
    assert "if that account exists" in resp.json()["message"]
    assert sent == ["farmer@example.com"]


# --------------------------------------------------------------------------
# Configuration flag
# --------------------------------------------------------------------------


def test_email_verification_required_flag(monkeypatch):
    monkeypatch.setattr(settings, "REQUIRE_EMAIL_VERIFICATION", False)
    monkeypatch.setattr(settings, "ENVIRONMENT", "development")
    assert settings.email_verification_required is False

    # Production always requires it, so a deploy can't ship open signups.
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    assert settings.email_verification_required is True

    # Development can opt in to exercise the real flow.
    monkeypatch.setattr(settings, "ENVIRONMENT", "development")
    monkeypatch.setattr(settings, "REQUIRE_EMAIL_VERIFICATION", True)
    assert settings.email_verification_required is True


def test_email_delivery_configured_flag(monkeypatch):
    monkeypatch.setattr(settings, "RESEND_API_KEY", "")
    assert settings.email_delivery_configured is False
    monkeypatch.setattr(settings, "RESEND_API_KEY", "re_test_key")
    assert settings.email_delivery_configured is True
