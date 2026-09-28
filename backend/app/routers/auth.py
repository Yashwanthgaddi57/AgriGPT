"""Authentication endpoints: Supabase Auth in production, local fallback for local runs."""
import httpx
import logging

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
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
    admin_get_user_by_email,
    supabase_reset_password,
    supabase_send_verification,
    supabase_sign_in,
    supabase_sign_up,
)
from app.schemas.auth import (
    ForgotPasswordRequest,
    LoginRequest,
    MessageResponse,
    RegisterRequest,
)

router = APIRouter(prefix="/auth", tags=["auth"])
logger = logging.getLogger("app.api.auth")


@router.post("/register", response_model=MessageResponse, status_code=status.HTTP_201_CREATED)
async def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    """Create an auth user. Local mode: immediately active.

    Production uses the Supabase admin API to create the user confirmed and
    mints a session via the password grant, so signup returns tokens directly
    (no confirmation email — see supabase_sign_up for the rate-limit rationale).
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

    # In production, send the verification email explicitly (single targeted
    # email, well within Supabase's free-tier rate limit) and tell the
    # client to wait for the user to click it.
    if settings.ENVIRONMENT == "production":
        redirect_to = f"{settings.FRONTEND_APP_URL.rstrip('/')}/auth/verify"
        sent = await supabase_send_verification(payload.email, redirect_to)
        content: dict = {
            "message": (
                "Registration successful. Check your inbox for the verification "
                "link — click it, then sign in."
            ),
            "email": payload.email,
            "needs_email_confirmation": True,
            "verification_sent": sent,
        }
        return JSONResponse(status_code=status.HTTP_201_CREATED, content=content)

    # Development: user was auto-confirmed — sign them in immediately.
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
                "Please confirm your email first — check your inbox for the "
                "verification link before signing in."
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


@router.post("/verify-email", response_model=MessageResponse)
async def verify_email(payload: dict) -> dict:
    """Confirm an email via the verification token Supabase emailed the user."""
    token = (payload or {}).get("token")
    if not token:
        raise AuthError("token is required")
    try:
        async with httpx.AsyncClient(base_url=settings.SUPABASE_URL, timeout=15) as client:
            resp = await client.post(
                "/auth/v1/verify",
                headers={"apikey": settings.SUPABASE_ANON_KEY},
                json={"token": token, "type": "signup"},
            )
    except Exception as e:
        raise AuthError("Verification failed") from e
    if resp.status_code >= 400:
        raise AuthError("Invalid or expired verification link")
    return {"message": "Email verified. You can now sign in."}


@router.post("/resend-verification", response_model=MessageResponse)
async def resend_verification(payload: dict) -> dict:
    """Re-send the verification email for a registered account."""
    email = (payload or {}).get("email", "").strip().lower()
    if not email:
        raise AuthError("email is required")
    redirect_to = f"{settings.FRONTEND_APP_URL.rstrip('/')}/auth/verify"
    sent = await supabase_send_verification(email, redirect_to)
    if not sent:
        raise AuthError("Could not send verification email")
    return {"message": "Verification email sent if the account exists."}


@router.post("/forgot-password", response_model=MessageResponse)
async def forgot_password(payload: ForgotPasswordRequest):
    if local_auth_enabled():
        return {
            "message": "Local mode: password resets are managed by the administrator. "
            "Delete backend/agrigpt_local.db and re-register to reset credentials."
        }
    redirect = f"{settings.FRONTEND_APP_URL.rstrip('/')}/auth/reset-password"
    try:
        await supabase_reset_password(payload.email, redirect)
    except Exception as e:
        raise AuthError(str(e)) from e
    return {"message": "Password reset email sent if the account exists."}
