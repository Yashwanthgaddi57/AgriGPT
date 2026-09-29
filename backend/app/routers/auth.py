"""Authentication endpoints: Supabase Auth in production, local fallback for local runs."""
import logging

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.email_verification import (
    VerificationError,
    deliver_verification_code,
    seconds_until_resend_allowed,
    verify_verification_code,
)
from app.core.password_reset import (
    ResetError,
    apply_password_change,
    consume_reset_token,
    issue_password_reset,
)
from app.core.exceptions import AuthError, ConflictError
from app.core.local_auth import (
    authenticate_local_user,
    decode_local_token,
    issue_local_tokens,
    local_auth_enabled,
    register_local_user,
    revoke_local_token,
)
from app.core.supabase_client import (
    SupabaseAuthError,
    admin_confirm_email,
    admin_get_user_by_email,
    supabase_sign_in,
    supabase_sign_up,
)
from app.schemas.auth import (
    ForgotPasswordRequest,
    LoginRequest,
    MessageResponse,
    RegisterRequest,
    ResetPasswordRequest,
    VerifyEmailRequest,
)

router = APIRouter(prefix="/auth", tags=["auth"])
logger = logging.getLogger("app.api.auth")


@router.post("/register", response_model=MessageResponse, status_code=status.HTTP_201_CREATED)
async def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    """Create an auth user. Local mode: immediately active.

    When email verification is required the user is created unconfirmed and
    a 6-digit code is emailed; the client sends the farmer to /auth/verify.
    Otherwise signup returns tokens directly.
    """
    if local_auth_enabled():
        try:
            user = register_local_user(db, payload.model_dump())
        except ValueError as e:
            raise AuthError(str(e)) from e
        tokens = issue_local_tokens(user)
        return JSONResponse(
            status_code=status.HTTP_201_CREATED,
            content={
                "message": "Registration successful.",
                **tokens,
            },
        )

    metadata = {
        "name": payload.name,
        "phone": payload.phone,
        "district": payload.district,
        "state": payload.state,
        "village": payload.village,
        "farm_size_acres": payload.farm_size_acres,
        "soil_type": payload.soil_type,
        "water_availability": payload.water_availability,
    }
    try:
        await supabase_sign_up(payload.email, payload.password, metadata)
    except ConflictError:
        raise
    except Exception as e:
        logger.warning("Register failed for %s: %s", payload.email, str(e)[:200])
        raise AuthError(str(e)) from e

    # Verification required: email our own 6-digit code and tell the client to
    # collect it. No tokens are returned until the code is confirmed.
    if settings.email_verification_required:
        sent, code = await deliver_verification_code(db, payload.email)
        content: dict = {
            "message": (
                "Registration successful. We emailed you a 6-digit code — "
                "enter it to activate your account."
            ),
            "email": payload.email,
            "needs_email_confirmation": True,
            "verification_sent": sent,
        }
        if not sent:
            # Be explicit rather than letting the farmer wait for mail that
            # will never arrive. Outside production the code is also logged.
            content["message"] = (
                "Registration successful, but we could not send the verification "
                "email. Request a new code from the verification screen."
            )
            if not settings.is_production:
                # Dev-only escape hatch: lets the whole flow be exercised with
                # any email address before a provider (Brevo) is configured.
                content["dev_code"] = code
        return JSONResponse(status_code=status.HTTP_201_CREATED, content=content)

    # Verification off: user was auto-confirmed — sign them in immediately.
    session = await supabase_sign_in(payload.email, payload.password)
    return JSONResponse(
        status_code=status.HTTP_201_CREATED,
        content={
            "message": "Registration successful.",
            "access_token": session["access_token"],
            "refresh_token": session["refresh_token"],
            "expires_in": session.get("expires_in", 3600),
            "token_type": session.get("token_type", "bearer"),
            "user": session.get("user", {}),
        },
    )


@router.post("/login")
async def login(payload: LoginRequest, db: Session = Depends(get_db)):
    """Password grant: local DB in local mode, Supabase Auth in production."""
    email = payload.email.strip().lower()
    logger.info("Login attempt for %s", email)
    if local_auth_enabled():
        user = authenticate_local_user(db, payload.email, payload.password)
        if not user:
            logger.warning("Login failed (local mode) for %s: invalid credentials", email)
            raise AuthError("Invalid email or password")
        return JSONResponse(status_code=200, content=issue_local_tokens(user))

    try:
        session = await supabase_sign_in(payload.email, payload.password)
    except SupabaseAuthError as e:
        code = getattr(e, "error_code", "") or ""
        msg = str(e).lower()

        logger.warning("Login failed for %s: code=%s msg=%s", email, code, str(e)[:200])

        if code == "email_not_confirmed" or "confirm" in msg or "confirmation" in msg:
            raise AuthError(
                "Please confirm your email first — enter the 6-digit code we "
                "emailed you, or request a new one."
            ) from e

        if code == "over_request_rate_limit" or "rate limit" in msg:
            raise AuthError("Too many attempts. Please wait a minute and try again.") from e

        # invalid_credentials: return a single, uniform message so attackers
        # cannot enumerate registered accounts by observing error text.
        raise AuthError("Invalid email or password") from e

    return JSONResponse(
        status_code=200,
        content={
            "access_token": session["access_token"],
            "refresh_token": session["refresh_token"],
            "expires_in": session.get("expires_in", 3600),
            "token_type": "bearer",
            "user": session.get("user", {}),
        },
    )


@router.post("/logout", response_model=MessageResponse)
async def logout(payload: dict, db: Session = Depends(get_db)) -> dict:
    """Revoke the current session.

    In local mode the HS256 token is blacklisted by its JTI so subsequent
    requests with the same token are rejected. In production (Supabase) the
    JWT is stateless and cannot be revoked server-side, so this endpoint is
    a best-effort no-op that simply clears the client-side session.
    """
    token = (payload or {}).get("access_token")
    if not token:
        raise AuthError("access_token is required")
    if local_auth_enabled():
        try:
            decoded = decode_local_token(token)
        except Exception:
            raise AuthError("Invalid token") from None
        jti = decoded.get("jti")
        if jti:
            revoke_local_token(db, jti)
    return {"message": "Logged out."}


@router.post("/verify-email")
async def verify_email(payload: VerifyEmailRequest, db: Session = Depends(get_db)) -> dict:
    """Confirm a signup with the 6-digit code we emailed.

    The code belongs to this backend, so it is checked against our own store
    and the account is only then marked confirmed in Supabase. No session is
    minted: the farmer signs in with the password they chose at signup.
    """
    if local_auth_enabled():
        raise AuthError("Email verification is not used in local auth mode.")

    email = (payload.email or "").strip().lower()
    code = (payload.code or "").strip()
    if not email or not code:
        raise AuthError("Enter the 6-digit code we emailed you.")

    try:
        verify_verification_code(db, email, code)
    except VerificationError as e:
        raise AuthError(str(e)) from e

    if not await admin_confirm_email(email):
        # The code was right but Supabase did not accept the confirmation, so
        # the account still cannot sign in — say so instead of claiming success.
        raise AuthError(
            "We couldn't activate that account. Please try again, or contact support."
        )

    return {
        "message": "Email verified. Sign in to continue.",
        "email": email,
        "verified": True,
    }


@router.post("/resend-verification")
async def resend_verification(payload: dict, db: Session = Depends(get_db)) -> dict:
    """Re-send the 6-digit signup code for an account."""
    email = (payload or {}).get("email", "").strip().lower()
    if not email:
        raise AuthError("email is required")
    if local_auth_enabled():
        raise AuthError("Email verification is not used in local auth mode.")

    # Same response either way, so this cannot be used to probe which emails
    # are registered.
    generic = {"message": "A new verification code is on its way if that account exists."}

    if await admin_get_user_by_email(email) is None:
        return generic

    wait = seconds_until_resend_allowed(db, email)
    if wait > 0:
        raise AuthError(
            f"Please wait {wait} more second{'s' if wait != 1 else ''} "
            "before requesting a new code."
        )

    try:
        sent, code = await deliver_verification_code(db, email)
    except VerificationError as e:
        raise AuthError(str(e)) from e
    if not sent:
        if not settings.is_production:
            # Dev-only escape hatch: surface the code so an unconfirmed
            # account can complete verification without a mail provider.
            return {
                "message": "DEV ONLY — email not configured; use this code.",
                "dev_code": code,
            }
        raise AuthError(
            "We couldn't send the verification email. Please try again in a moment."
        )
    return generic


@router.post("/forgot-password", response_model=MessageResponse)
async def forgot_password(payload: ForgotPasswordRequest, db: Session = Depends(get_db)):
    """Email a single-use reset link for the account (if it exists)."""
    if local_auth_enabled():
        return {
            "message": "Local mode: password resets are managed by the administrator. "
            "Delete backend/agrigpt_local.db and re-register to reset credentials."
        }
    try:
        sent, dev_url = await issue_password_reset(db, payload.email)
    except Exception as e:
        logger.warning("Password reset request failed for %s: %s", payload.email, str(e)[:200])
        raise AuthError("Could not send the reset email. Please try again in a moment.") from e

    if not sent and dev_url:
        # Dev-only escape hatch (never in production). The link rides inside
        # the message because the response model has a single field.
        return {"message": f"DEV ONLY — email not configured. Reset link: {dev_url}"}
    if not sent:
        raise AuthError("Could not send the reset email. Please try again in a moment.")
    # Identical response whether or not the account exists — no probing.
    return {"message": "If an account exists for that email, a reset link is on its way."}


@router.post("/reset-password", response_model=MessageResponse)
async def reset_password(payload: ResetPasswordRequest, db: Session = Depends(get_db)):
    """Consume a reset token and set the new password."""
    if local_auth_enabled():
        raise AuthError("Password reset is not used in local auth mode.")

    try:
        email = consume_reset_token(db, payload.token)
    except ResetError as e:
        raise AuthError(str(e)) from e

    if not await apply_password_change(email, payload.password):
        raise AuthError(
            "We couldn't update the password. The link may have expired — request a new one."
        )
    return {"message": "Password updated. Sign in with your new password."}
