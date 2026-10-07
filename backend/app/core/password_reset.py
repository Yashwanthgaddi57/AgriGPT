"""App-issued password reset: single-use links emailed via our provider.

Same threat model as the signup codes: only a hash of the token is stored,
a token is single-use and time-limited, and the link itself carries all the
state so no session is needed to change the password. Supabase remains the
password authority — the change is applied through the service-role admin API.
"""
import hashlib
import hmac
import logging
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.local_auth import hash_password, local_auth_enabled
from app.core.supabase_client import admin_get_user_by_email, admin_update_password
from app.models.password_reset import PasswordResetToken
from app.models.user import User
from app.services.email_service import send_password_reset_email

logger = logging.getLogger("app.core.password_reset")


class ResetError(Exception):
    """A reset link could not be issued or honoured. The message is user-facing."""


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _aware(dt: datetime) -> datetime:
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt


def _secret() -> str:
    """Pepper for token hashing; the DB alone cannot validate a token.

    Order: RESET_TOKEN_SECRET -> local JWT secret -> SUPABASE_JWT_SECRET.
    """
    return (
        settings.RESET_TOKEN_SECRET
        or (settings.SUPABASE_JWT_SECRET if settings.SUPABASE_JWT_SECRET != "your-supabase-jwt-secret" else "")
        or "agrigpt-reset-pepper"
    )


def _hash_token(token: str) -> str:
    return hmac.new(_secret().encode(), token.strip().encode(), hashlib.sha256).hexdigest()


def generate_reset_token() -> str:
    # 32 url-safe bytes ~ 256 bits of entropy: not brute-forceable, so unlike
    # the 6-digit code there is no attempt counter here.
    return secrets.token_urlsafe(32)


async def issue_password_reset(db: Session, email: str) -> tuple[bool, str | None]:
    """Create a reset link for `email` and email it.

    Returns (delivered, reset_url). `reset_url` is only populated for dev
    environments when delivery was not possible, so the flow stays testable
    without a provider; production gets (False, None) and never a URL.
    """
    email = email.strip().lower()
    if local_auth_enabled():
        return await _issue_local_reset(db, email)
    user = await admin_get_user_by_email(email)
    if user is None:
        # Unknown address: say nothing and send nothing (no account probing).
        return True, None

    token = generate_reset_token()
    # Single outstanding token per account: a new request voids the old link.
    db.query(PasswordResetToken).filter(
        PasswordResetToken.email == email,
        PasswordResetToken.consumed_at.is_(None),
    ).update({"consumed_at": _utcnow()}, synchronize_session=False)
    db.add(
        PasswordResetToken(
            email=email,
            token_hash=_hash_token(token),
            expires_at=_utcnow() + timedelta(minutes=settings.PASSWORD_RESET_TTL_MINUTES),
        )
    )
    db.commit()

    base = settings.FRONTEND_APP_URL.rstrip("/")
    reset_url = f"{base}/auth/reset-password?token={token}"
    sent = await send_password_reset_email(email, reset_url)
    if not sent:
        if not settings.is_production:
            logger.warning(
                "DEV ONLY — email delivery unavailable, so the password reset link "
                "for %s is returned to the caller instead: %s",
                email,
                reset_url,
            )
            return False, reset_url
        return False, None
    return True, None


def consume_reset_token(db: Session, token: str) -> str:
    """Validate a reset token and return the email it belongs to. Single use."""
    token = (token or "").strip()
    if not token:
        raise ResetError("This reset link is invalid. Request a new one.")

    row = (
        db.query(PasswordResetToken)
        .filter(
            PasswordResetToken.token_hash == _hash_token(token),
            PasswordResetToken.consumed_at.is_(None),
        )
        .order_by(PasswordResetToken.created_at.desc())
        .first()
    )
    if row is None:
        raise ResetError("This reset link is invalid or has already been used. Request a new one.")
    if _aware(row.expires_at) <= _utcnow():
        raise ResetError("This reset link has expired. Request a new one.")

    row.consumed_at = _utcnow()
    db.commit()
    return row.email


async def apply_password_change(email: str, new_password: str) -> bool:
    """Push the new password to Supabase via the service-role admin API."""
    if local_auth_enabled():
        return _apply_local_password_change(email, new_password)
    user = await admin_get_user_by_email(email)
    if not user or not user.get("id"):
        return False
    return await admin_update_password(user["id"], new_password)


# ---------------------------------------------------------------------------
# Local auth mode (no Supabase): reset tokens still work, the emailed link
# points at the same frontend page, but the password is updated in the local
# users table instead of Supabase Auth.
# ---------------------------------------------------------------------------


def _local_user_exists(db: Session, email: str) -> bool:
    from sqlalchemy import text

    try:
        row = db.execute(
            text("select 1 from users where lower(email) = :email limit 1"),
            {"email": email},
        ).first()
        return row is not None
    except Exception:
        return False


async def _issue_local_reset(db: Session, email: str) -> tuple[bool, str | None]:
    """Local-mode variant: token table + email, skipping the Supabase lookup."""
    if not _local_user_exists(db, email):
        # Unknown address: say nothing and send nothing (no account probing).
        return True, None

    token = generate_reset_token()
    db.query(PasswordResetToken).filter(
        PasswordResetToken.email == email,
        PasswordResetToken.consumed_at.is_(None),
    ).update({"consumed_at": _utcnow()}, synchronize_session=False)
    db.add(
        PasswordResetToken(
            email=email,
            token_hash=_hash_token(token),
            expires_at=_utcnow() + timedelta(minutes=settings.PASSWORD_RESET_TTL_MINUTES),
        )
    )
    db.commit()

    base = settings.FRONTEND_APP_URL.rstrip("/")
    reset_url = f"{base}/auth/reset-password?token={token}"
    sent = await send_password_reset_email(email, reset_url)
    if not sent:
        if not settings.is_production:
            logger.warning(
                "DEV ONLY — email delivery unavailable, so the password reset link "
                "for %s is returned to the caller instead: %s",
                email,
                reset_url,
            )
            return False, reset_url
        return False, None
    return True, None


def _apply_local_password_change(email: str, new_password: str) -> bool:
    """Update the password hash in the local users/credentials tables."""
    from app.core.database import get_session_factory

    db = get_session_factory()()
    try:
        user = db.query(User).filter(User.email == email).first()
        if user is None:
            return False
        from app.core.local_auth import _set_password_hash

        _set_password_hash(user, hash_password(new_password))
        db.commit()
        return True
    except Exception:
        db.rollback()
        return False
    finally:
        db.close()
