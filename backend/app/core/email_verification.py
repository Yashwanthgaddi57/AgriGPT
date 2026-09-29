"""Issue and check the 6-digit codes that confirm a signup.

Codes are generated here and stored only as a SHA-256 hash. A new code
supersedes any outstanding one, so the newest email is always the one that
works, and each code is single-use, time-limited, and attempt-limited.
"""
import hashlib
import logging
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.email_verification import EmailVerificationCode
from app.services.email_service import send_verification_code_email

logger = logging.getLogger("app.core.email_verification")

WRONG_CODE_MESSAGE = (
    "That code is wrong or has expired. Check it, or request a new one."
)


class VerificationError(Exception):
    """A signup code could not be issued or accepted. The message is user-facing."""


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _aware(dt: datetime) -> datetime:
    """SQLite hands back naive datetimes; treat stored values as UTC."""
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt


def _hash_code(code: str) -> str:
    return hashlib.sha256(code.strip().encode("utf-8")).hexdigest()


def generate_code() -> str:
    """A uniformly random 000000-999999 code."""
    return f"{secrets.randbelow(1_000_000):06d}"


def _live_code(db: Session, email: str) -> EmailVerificationCode | None:
    return (
        db.query(EmailVerificationCode)
        .filter(
            EmailVerificationCode.email == email,
            EmailVerificationCode.consumed_at.is_(None),
        )
        .order_by(EmailVerificationCode.created_at.desc())
        .first()
    )


def seconds_until_resend_allowed(db: Session, email: str) -> int:
    """Whole seconds left on the resend cooldown; 0 when a new code is allowed."""
    email = email.strip().lower()
    existing = _live_code(db, email)
    if existing is None:
        return 0
    age = (_utcnow() - _aware(existing.created_at)).total_seconds()
    remaining = settings.EMAIL_VERIFICATION_RESEND_COOLDOWN_SECONDS - age
    return max(0, int(remaining) + 1) if remaining > 0 else 0


def issue_verification_code(db: Session, email: str) -> str:
    """Create a fresh code, invalidating any outstanding one.

    Raises VerificationError while the resend cooldown is still running so a
    user cannot spam the provider (or their own inbox).
    """
    email = email.strip().lower()
    wait = seconds_until_resend_allowed(db, email)
    if wait > 0:
        raise VerificationError(
            f"Please wait {wait} more second{'s' if wait != 1 else ''} "
            "before requesting a new code."
        )

    now = _utcnow()
    # Supersede older codes so only the most recent email works.
    db.query(EmailVerificationCode).filter(
        EmailVerificationCode.email == email,
        EmailVerificationCode.consumed_at.is_(None),
    ).update({"consumed_at": now}, synchronize_session=False)

    code = generate_code()
    db.add(
        EmailVerificationCode(
            email=email,
            code_hash=_hash_code(code),
            expires_at=now + timedelta(minutes=settings.EMAIL_VERIFICATION_TTL_MINUTES),
        )
    )
    db.commit()
    return code


def verify_verification_code(db: Session, email: str, code: str) -> None:
    """Accept `code` for `email`, consuming it. Raises VerificationError otherwise."""
    email = email.strip().lower()
    code = (code or "").strip()
    if not code:
        raise VerificationError("Enter the 6-digit code we emailed you.")

    row = _live_code(db, email)
    if row is None:
        raise VerificationError(WRONG_CODE_MESSAGE)

    if row.attempts >= settings.EMAIL_VERIFICATION_MAX_ATTEMPTS:
        raise VerificationError("Too many attempts. Request a new code.")

    if _aware(row.expires_at) <= _utcnow():
        raise VerificationError("That code has expired. Request a new one.")

    if not secrets.compare_digest(row.code_hash, _hash_code(code)):
        # Count the miss so brute-forcing a 6-digit code is bounded.
        row.attempts += 1
        db.commit()
        raise VerificationError(WRONG_CODE_MESSAGE)

    row.consumed_at = _utcnow()
    db.commit()


async def deliver_verification_code(db: Session, email: str) -> tuple[bool, str]:
    """Issue a code and email it. Returns (delivered, code).

    `delivered` is False when no configured provider accepted the mail.
    Outside production the code is also logged, and the caller may surface it
    as `dev_code` so the flow stays testable without a provider; production
    never writes a code to logs or responses.
    """
    code = issue_verification_code(db, email)
    sent = await send_verification_code_email(email, code)
    if not sent and not settings.is_production:
        logger.warning(
            "DEV ONLY — email delivery unavailable, so the verification code for %s "
            "is printed here: %s (expires in %s minutes)",
            email,
            code,
            settings.EMAIL_VERIFICATION_TTL_MINUTES,
        )
    return sent, code
