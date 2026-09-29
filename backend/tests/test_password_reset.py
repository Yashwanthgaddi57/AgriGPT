"""Password reset flow tests (app-issued single-use tokens).

Supabase admin calls are patched, so nothing here touches a real project.
What is under test is our contract: who gets a token, how a link is consumed,
and that the password change actually reaches the auth provider.
"""
import pytest

from app.core import password_reset as pr
from app.models.password_reset import PasswordResetToken
from app.routers import auth as auth_router


@pytest.fixture(autouse=True)
def clean_tokens(db_session):
    db_session.query(PasswordResetToken).delete()
    db_session.commit()
    yield
    db_session.query(PasswordResetToken).delete()
    db_session.commit()


@pytest.fixture
def supabase_mode(monkeypatch):
    monkeypatch.setattr(auth_router, "local_auth_enabled", lambda: False)


def test_token_is_stored_hashed_and_single_use(db_session, monkeypatch):
    issued: list[str] = []

    async def known(email):
        return {"id": "user-1", "email": email}

    async def fake_send(to, url):
        issued.append(url.split("token=")[1])
        return True

    monkeypatch.setattr(pr, "admin_get_user_by_email", known)
    monkeypatch.setattr(pr, "send_password_reset_email", fake_send)

    import asyncio

    asyncio.run(pr.issue_password_reset(db_session, "Farmer@Example.com"))
    row = db_session.query(PasswordResetToken).one()
    token = issued[0]
    # A leaked DB must not hand out a working link.
    assert token not in row.token_hash
    assert row.email == "farmer@example.com"

    email = pr.consume_reset_token(db_session, token)
    assert email == "farmer@example.com"
    with pytest.raises(pr.ResetError, match="already been used"):
        pr.consume_reset_token(db_session, token)


def test_new_request_voids_the_previous_link(db_session, monkeypatch):
    import asyncio

    urls: list[str] = []

    async def known(email):
        return {"id": "user-1", "email": email}

    async def fake_send(to, url):
        urls.append(url.split("token=")[1])
        return True

    # issue_password_reset now returns a tuple; capture the token via the URL.

    monkeypatch.setattr(pr, "admin_get_user_by_email", known)
    monkeypatch.setattr(pr, "send_password_reset_email", fake_send)

    asyncio.run(pr.issue_password_reset(db_session, "farmer@example.com"))
    asyncio.run(pr.issue_password_reset(db_session, "farmer@example.com"))

    with pytest.raises(pr.ResetError, match="invalid or has already been used"):
        pr.consume_reset_token(db_session, urls[0])
    # The newest link works.
    assert pr.consume_reset_token(db_session, urls[1]) == "farmer@example.com"


def test_expired_link_is_rejected(db_session, monkeypatch):
    from datetime import datetime, timedelta, timezone

    import asyncio

    captured: list[str] = []

    async def known(email):
        return {"id": "user-1", "email": email}

    async def fake_send(to, url):
        captured.append(url.split("token=")[1])
        return True

    monkeypatch.setattr(pr, "admin_get_user_by_email", known)
    monkeypatch.setattr(pr, "send_password_reset_email", fake_send)

    asyncio.run(pr.issue_password_reset(db_session, "farmer@example.com"))
    row = db_session.query(PasswordResetToken).one()
    row.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    db_session.commit()

    with pytest.raises(pr.ResetError, match="expired"):
        pr.consume_reset_token(db_session, captured[0])


def test_forgot_password_is_silent_for_unknown_accounts(client, supabase_mode, monkeypatch):
    async def unknown(email):
        return None

    async def should_not_send(to, url):
        raise AssertionError("no email may be sent for an unknown account")

    # The endpoint calls issue_password_reset, which resolves these on the
    # password_reset module — patch there, not on the router.
    monkeypatch.setattr(pr, "admin_get_user_by_email", unknown)
    monkeypatch.setattr(pr, "send_password_reset_email", should_not_send)

    resp = client.post("/api/v1/auth/forgot-password", json={"email": "nobody@example.com"})
    assert resp.status_code == 200
    # Same response as for a known account — no account probing.
    assert "If an account exists" in resp.json()["message"]


def test_reset_password_endpoint_changes_the_password(client, db_session, supabase_mode, monkeypatch):
    import asyncio

    pushed: list[tuple[str, str]] = []
    token_holder: list[str] = []

    async def known(email):
        return {"id": "user-1", "email": email}

    async def fake_send(to, url):
        token_holder.append(url.split("token=")[1])
        return True

    async def fake_update(email, password):
        # The router hands over the email; resolving it to a user id is the
        # real apply_password_change's job (patched out here).
        pushed.append((email, password))
        return True

    monkeypatch.setattr(pr, "admin_get_user_by_email", known)
    monkeypatch.setattr(pr, "send_password_reset_email", fake_send)
    # The router resolves apply_password_change on itself (direct import).
    monkeypatch.setattr(auth_router, "apply_password_change", fake_update)

    asyncio.run(pr.issue_password_reset(db_session, "farmer@example.com"))

    resp = client.post(
        "/api/v1/auth/reset-password",
        json={"token": token_holder[0], "password": "brand-new-pw-1"},
    )
    assert resp.status_code == 200
    assert pushed == [("farmer@example.com", "brand-new-pw-1")]


def test_reset_password_rejects_short_passwords(client, supabase_mode):
    resp = client.post(
        "/api/v1/auth/reset-password",
        json={"token": "whatever", "password": "short"},
    )
    assert resp.status_code == 422  # schema-level min length


def test_reset_password_rejects_bogus_tokens(client, supabase_mode):
    resp = client.post(
        "/api/v1/auth/reset-password",
        json={"token": "not-a-real-token", "password": "brand-new-pw-1"},
    )
    assert resp.status_code == 401
    assert "invalid" in resp.json()["error"]["detail"].lower()
