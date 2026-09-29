"""Supabase admin client (service role) and auth helpers via REST API."""
from typing import Any

import httpx

from app.core.config import settings

_admin: Any = None


class SupabaseAuthError(RuntimeError):
    """Auth failure with the upstream Supabase error code attached."""

    def __init__(self, message: str, error_code: str | None = None):
        super().__init__(message)
        self.error_code = error_code or ""


def get_admin_client():
    """Service-role Supabase client for backend DB/storage/auth operations."""
    global _admin
    if _admin is None:
        from supabase import create_client

        _admin = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_KEY)
    return _admin


def _supabase_msg(resp: httpx.Response) -> str:
    """Extract Supabase's human-readable error message from a response."""
    if resp.headers.get("content-type", "").startswith("application/json"):
        try:
            return resp.json().get("msg", resp.text)
        except Exception:
            pass
    return resp.text


def _service_key_ok() -> bool:
    """True when SUPABASE_SERVICE_KEY looks like a real service-role secret.

    Supabase service-role keys come in two forms: the modern 3-segment JWT
    (eyJ...) and the legacy sb_secret_... string. The render.yaml default is
    the placeholder 'your-service-role-key', which the admin API rejects with
    'invalid JWT'. Detect that and fall back to the anon signup path instead
    of breaking signup when the secret isn't configured.
    """
    key = (settings.SUPABASE_SERVICE_KEY or "").strip()
    if not key or "your" in key.lower():
        return False
    return key.count(".") == 2 or key.startswith("sb_secret_")


def _normalize_session(resp_json: dict) -> dict:
    """Unify the two Supabase response shapes into one auth contract.

    The anon /auth/v1/signup and admin /auth/v1/admin/users responses nest
    the session under a "session" key, but the password-grant
    /auth/v1/token?grant_type=password response is flat (access_token at the
    top level). Handle both so callers always get a flat session dict.
    """
    sess = resp_json.get("session")
    if not isinstance(sess, dict) or not sess:
        sess = resp_json
    user = resp_json.get("user") or {}
    return {
        "access_token": sess.get("access_token"),
        "refresh_token": sess.get("refresh_token"),
        "expires_in": sess.get("expires_in"),
        "token_type": sess.get("token_type", "bearer"),
        "user": user,
        "message": resp_json.get("message", ""),
    }


async def _admin_signup_and_signin(
    client: httpx.AsyncClient,
    email: str,
    password: str,
    admin_headers: dict,
    anon_headers: dict,
    user_data: dict,
) -> dict:
    """Create an UNCONFIRMED user via the admin API, then sign in if allowed.

    The user is created with email_confirm=False, so no Supabase mail is sent
    on signup. When verification is required the caller emails its own 6-digit
    code (see app/core/email_verification.py) and the account stays unable to
    sign in until admin_confirm_email succeeds. Otherwise the account is
    confirmed immediately and this returns a session.
    """
    create = await client.post(
        "/auth/v1/admin/users",
        headers=admin_headers,
        json={
            "email": email,
            "password": password,
            "email_confirm": False,
            "user_metadata": user_data,
        },
    )
    already_registered = create.status_code >= 400 and "already" in _supabase_msg(create).lower() and "registered" in _supabase_msg(create).lower()
    if create.status_code >= 400 and not already_registered:
        raise RuntimeError(_supabase_msg(create))

    session = await client.post(
        "/auth/v1/token?grant_type=password",
        headers=anon_headers,
        json={"email": email, "password": password},
    )
    if session.status_code >= 400 and "confirm" in _supabase_msg(session).lower():
        # Older deploy left the account unconfirmed; confirm it, then retry.
        await _mark_email_confirmed(client, admin_headers, email)
        session = await client.post(
            "/auth/v1/token?grant_type=password",
            headers=anon_headers,
            json={"email": email, "password": password},
        )
    if session.status_code >= 400:
        # The account exists but this password doesn't work (or it is a
        # Google-only account). Give the farmer an actionable answer instead
        # of a raw "Invalid login credentials".
        existing = await admin_get_user_by_email(email)
        if existing is not None:
            providers = (existing.get("app_metadata") or {}).get("providers") or [
                (existing.get("app_metadata") or {}).get("provider")
            ]
            google_linked = any(p == "google" for p in providers if p)
            if google_linked:
                # Admin API redacts encrypted_password, so we cannot know
                # whether a password exists — offer both paths neutrally.
                raise RuntimeError(
                    "An account with this email already exists. Sign in with "
                    "your password, or use 'Continue with Google'. Forgot your "
                    "password? Use 'Forgot password' to set a new one."
                )
            raise RuntimeError(
                "An account with this email already exists. Please sign in "
                "instead, or reset your password if you forgot it."
            )
        raise RuntimeError(_supabase_msg(session))
    return _normalize_session(session.json())


async def _anon_signup(
    client: httpx.AsyncClient,
    email: str,
    password: str,
    anon_headers: dict,
    user_data: dict,
) -> dict:
    """Standard anon signup (email-confirmation path). Respects project settings."""
    resp = await client.post(
        "/auth/v1/signup",
        headers=anon_headers,
        json={"email": email, "password": password, "data": user_data},
    )
    if resp.status_code >= 400:
        msg = _supabase_msg(resp)
        if "rate limit" in msg.lower():
            raise RuntimeError(
                "Too many signup attempts right now. Please wait a few minutes and try again."
            )
        raise RuntimeError(msg)
    return _normalize_session(resp.json())


async def supabase_sign_up(email: str, password: str, metadata: dict | None = None) -> dict:
    """Create an auth user (unconfirmed) and return a normalized user payload.

    Admin path (when SUPABASE_SERVICE_KEY is a real service-role JWT): creates
    the user with email_confirm=False so Supabase's free-tier email rate
    limit is NOT hit on signup (the admin API does not send one). The
    verification email is sent separately via /auth/v1/admin/generate_link,
    which is a single targeted email — well within the rate limit.

    Anon fallback (when the service key is unset/placeholder): the standard
    email-confirmation signup. This keeps registration working on projects
    where the service key hasn't been configured yet — the result simply has
    `access_token=None` and needs_email_confirmation=True.

    `metadata` is stored as user_metadata so get_current_user can hydrate the
    full profile on the first authenticated request.
    """
    key = (settings.SUPABASE_SERVICE_KEY or "").strip()
    legacy = key.startswith("sb_secret_")
    admin_headers = {
        "apikey": key if legacy else settings.SUPABASE_ANON_KEY,
        "Authorization": f"Bearer {key}",
    }
    anon_headers = {"apikey": settings.SUPABASE_ANON_KEY}
    user_data = metadata or {}

    async with httpx.AsyncClient(base_url=settings.SUPABASE_URL, timeout=30) as client:
        if _service_key_ok():
            return await _admin_create_user(
                client, email, password, admin_headers, user_data
            )
        return await _anon_signup(client, email, password, anon_headers, user_data)


async def _admin_create_user(
    client: httpx.AsyncClient,
    email: str,
    password: str,
    admin_headers: dict,
    user_data: dict,
) -> dict:
    """Create a user via the admin API.

    When email verification is not required the user is created already
    confirmed so local signups work without an SMTP server. When it is
    required the user is left unconfirmed and the caller emails its own
    6-digit code (see app/core/email_verification.py); the account only
    becomes signable once admin_confirm_email() succeeds.
    """
    from app.core.config import settings
    from app.core.exceptions import ConflictError

    # Verification off -> auto-confirm, so signup can't be blocked by an
    # unconfigured SMTP server. Verification on -> leave unconfirmed; login
    # stays blocked until the emailed code is entered.
    auto_confirm = not settings.email_verification_required
    create = await client.post(
        "/auth/v1/admin/users",
        headers=admin_headers,
        json={
            "email": email,
            "password": password,
            "email_confirm": auto_confirm,
            "user_metadata": user_data,
        },
    )
    already_registered = (
        create.status_code >= 400
        and "already" in _supabase_msg(create).lower()
        and "registered" in _supabase_msg(create).lower()
    )
    if create.status_code >= 400 and not already_registered:
        raise RuntimeError(_supabase_msg(create))
    if create.status_code >= 400:
        raise ConflictError(
            "An account with this email already exists. Sign in instead, "
            "or use 'Forgot password' if you don't remember your password."
        )
    return _normalize_session(create.json())


async def _admin_signup_and_signin(
    client: httpx.AsyncClient,
    email: str,
    password: str,
    admin_headers: dict,
    anon_headers: dict,
    user_data: dict,
) -> dict:
    """Deprecated: use _admin_create_user instead."""
    return await _admin_create_user(client, email, password, admin_headers, user_data)


async def _mark_email_confirmed(client: httpx.AsyncClient, admin_headers: dict, email: str) -> None:
    """Best-effort: confirm an existing user found by email. Never raises."""
    try:
        listed = await client.get(
            "/auth/v1/admin/users",
            headers=admin_headers,
            params={"email": email},
        )
        if listed.status_code != 200:
            return
        for u in listed.json().get("users", []):
            if (u.get("email") or "").lower() == email.lower():
                await client.put(
                    f"/auth/v1/admin/users/{u['id']}",
                    headers=admin_headers,
                    json={"email_confirm": True},
                )
                return
    except Exception:
        pass


async def supabase_sign_in(email: str, password: str) -> dict:
    async with httpx.AsyncClient(base_url=settings.SUPABASE_URL, timeout=15) as client:
        resp = await client.post(
            "/auth/v1/token?grant_type=password",
            headers={"apikey": settings.SUPABASE_ANON_KEY},
            json={"email": email, "password": password},
        )
        if resp.status_code >= 400:
            try:
                body = resp.json()
                detail = body.get("msg", resp.text)
                code = body.get("error_code", "")
            except Exception:
                detail, code = resp.text, ""
            raise SupabaseAuthError(detail, code)
        return resp.json()


async def admin_confirm_email(email: str) -> bool:
    """Mark an account's email as confirmed via the service-role admin API.

    Called once the app-owned 6-digit code has been checked. Supabase remains
    the source of truth for who may sign in, so a valid code only counts if
    this succeeds. Returns False on any failure — the caller must not treat a
    failed confirmation as a verified account.
    """
    user = await admin_get_user_by_email(email)
    if not user or not user.get("id"):
        return False

    key = (settings.SUPABASE_SERVICE_KEY or "").strip()
    legacy = key.startswith("sb_secret_")
    try:
        async with httpx.AsyncClient(base_url=settings.SUPABASE_URL, timeout=15) as client:
            resp = await client.put(
                f"/auth/v1/admin/users/{user['id']}",
                headers={
                    "apikey": key if legacy else settings.SUPABASE_ANON_KEY,
                    "Authorization": f"Bearer {key}",
                },
                json={"email_confirm": True},
            )
    except Exception:
        return False
    return resp.status_code < 400


async def admin_update_password(user_id: str, new_password: str) -> bool:
    """Set a new password for an auth user via the service-role admin API."""
    key = (settings.SUPABASE_SERVICE_KEY or "").strip()
    legacy = key.startswith("sb_secret_")
    try:
        async with httpx.AsyncClient(base_url=settings.SUPABASE_URL, timeout=15) as client:
            resp = await client.put(
                f"/auth/v1/admin/users/{user_id}",
                headers={
                    "apikey": key if legacy else settings.SUPABASE_ANON_KEY,
                    "Authorization": f"Bearer {key}",
                },
                json={"password": new_password},
            )
    except Exception:
        return False
    return resp.status_code < 400


async def supabase_is_email_confirmed(email: str) -> bool | None:
    """Return True/False if the user exists, None if the lookup fails."""
    user = await admin_get_user_by_email(email)
    if user is None:
        return None
    return bool(user.get("email_confirmed_at"))


async def admin_get_user_by_email(email: str) -> dict | None:
    """Service-role lookup, used to give users actionable login errors.

    Returns the raw admin user object, or None if not found / lookup fails
    (lookup failure must never block the standard error path).
    """
    key = (settings.SUPABASE_SERVICE_KEY or "").strip()
    legacy = key.startswith("sb_secret_")
    try:
        async with httpx.AsyncClient(base_url=settings.SUPABASE_URL, timeout=15) as client:
            resp = await client.get(
                "/auth/v1/admin/users",
                params={"per_page": 200},
                headers={
                    "apikey": key if legacy else settings.SUPABASE_ANON_KEY,
                    "Authorization": f"Bearer {key}",
                },
            )
            if resp.status_code != 200:
                return None
            for u in resp.json().get("users", []):
                if (u.get("email") or "").lower() == email.strip().lower():
                    return u
    except Exception:
        return None
    return None


async def supabase_reset_password(email: str, redirect_to: str) -> None:
    async with httpx.AsyncClient(base_url=settings.SUPABASE_URL, timeout=30) as client:
        resp = await client.post(
            "/auth/v1/recover",
            headers={"apikey": settings.SUPABASE_ANON_KEY},
            json={"email": email, "redirect_to": redirect_to},
        )
        if resp.status_code >= 400:
            raise RuntimeError("Failed to send password reset email")


async def upload_disease_image(user_id: str, filename: str, content: bytes) -> str:
    """Upload to the disease-images bucket under user folder; returns public URL."""
    client = get_admin_client()
    path = f"{user_id}/{filename}"
    client.storage.from_("disease-images").upload(
        path,
        content,
        {"content-type": "image/jpeg", "upsert": "true"},
    )
    return client.storage.from_("disease-images").get_public_url(path)
