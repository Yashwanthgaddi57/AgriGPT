"""Local auth fallback for no-Docker runs without a Supabase project.

When SUPABASE_URL is not configured (placeholder), auth endpoints fall back to
this module: users are stored in the local DB with salted PBKDF2 hashes and
access tokens are self-signed HS256 JWTs with the same claims shape as
Supabase tokens (`sub`, `email`, `role=authenticated`, `exp`), so the rest of
the app (deps.get_current_user) works unchanged.
"""
import hashlib
import logging
import os
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.user import User

logger = logging.getLogger("app.auth.local")

_PBKDF2_ITERATIONS = 120_000


def local_auth_enabled() -> bool:
    """True when Supabase is not configured -> use local password auth."""
    return "YOUR_PROJECT_REF" in settings.SUPABASE_URL or not settings.SUPABASE_URL


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), _PBKDF2_ITERATIONS)
    return f"pbkdf2${_PBKDF2_ITERATIONS}${salt}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        _, iterations, salt, digest = stored.split("$")
        candidate = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), salt.encode(), int(iterations)
        )
        return secrets.compare_digest(candidate.hex(), digest)
    except Exception:
        return False


def _jwt_secret() -> str:
    """Stable secret for local tokens; persisted so restarts keep sessions valid."""
    env = os.environ.get("LOCAL_JWT_SECRET")
    if env:
        return env
    secret_file = os.path.join(os.path.dirname(__file__), "..", "..", ".local_jwt_secret")
    secret_file = os.path.abspath(secret_file)
    try:
        if os.path.exists(secret_file):
            with open(secret_file) as f:
                return f.read().strip() or _ephemeral_secret()
        secret = secrets.token_urlsafe(48)
        with open(secret_file, "w") as f:
            f.write(secret)
        return secret
    except Exception:
        return _ephemeral_secret()


def _ephemeral_secret() -> str:
    return settings.SUPABASE_JWT_SECRET or "agrigpt-local-dev-secret"


def issue_local_tokens(user: User) -> dict[str, Any]:
    """Create access/refresh tokens shaped like Supabase's session payload."""
    now = datetime.now(timezone.utc)
    expires_in = 3600 * 24  # 24h locally
    jti = secrets.token_urlsafe(16)
    payload = {
        "sub": str(user.id),
        "email": user.email,
        "role": "authenticated",
        "jti": jti,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=expires_in)).timestamp()),
    }
    access_token = jwt.encode(payload, _jwt_secret(), algorithm="HS256")
    refresh_token = secrets.token_urlsafe(48)
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "expires_in": expires_in,
        "token_type": "bearer",
        "user": {
            "id": str(user.id),
            "email": user.email,
            "user_metadata": {
                "name": user.name,
                "phone": user.phone,
                "district": user.district,
                "state": user.state,
                "village": user.village,
            },
        },
    }


def revoke_local_token(db: Session, jti: str) -> None:
    """Blacklist a local JWT by its JTI so it is rejected on use."""
    from sqlalchemy import text

    _ensure_revoked_table(db)
    db.execute(
        text(
            "insert or ignore into revoked_tokens (jti, revoked_at) "
            "values (:jti, datetime('now'))"
        ),
        {"jti": jti},
    )
    db.flush()


def is_token_revoked(db: Session, jti: str) -> bool:
    from sqlalchemy import text

    _ensure_revoked_table(db)
    row = db.execute(
        text("select 1 from revoked_tokens where jti = :jti"), {"jti": jti}
    ).first()
    return row is not None


def _ensure_revoked_table(db: Session) -> None:
    from sqlalchemy import text

    db.execute(
        text(
            "create table if not exists revoked_tokens ("
            "jti varchar(32) primary key, revoked_at datetime not null)"
        )
    )
    db.flush()


def decode_local_token(token: str) -> dict[str, Any]:
    return jwt.decode(token, _jwt_secret(), algorithms=["HS256"])


def register_local_user(db: Session, data: dict[str, Any]) -> User:
    """Create a local user immediately active (no email confirmation)."""
    existing = db.query(User).filter(User.email == data["email"]).first()
    if existing:
        raise ValueError("A user with this email already exists")
    user = User(
        id=uuid.uuid4(),
        email=data["email"],
        name=data.get("name") or data["email"].split("@")[0],
        phone=data.get("phone"),
        district=data.get("district"),
        state=data.get("state"),
        village=data.get("village"),
        farm_size_acres=data.get("farm_size_acres") or 0,
        soil_type=data.get("soil_type") or "unknown",
        water_availability=data.get("water_availability") or "rainfed",
        onboarding_completed=True,
    )
    db.add(user)
    db.flush()
    # Password hash stored in the phone-free metadata table only exists in
    # Supabase; locally we keep hashes in a dedicated side table via JSON file
    # to avoid schema drift -> stored on the User row's reserved field.
    _set_password_hash(user, hash_password(data["password"]))
    db.flush()
    return user


def authenticate_local_user(db: Session, email: str, password: str) -> User | None:
    user = db.query(User).filter(User.email == email).first()
    if not user:
        # Constant-time-ish: still hash to avoid trivial user enumeration timing
        verify_password(password, hash_password("dummy"))
        return None
    stored = _get_password_hash(user)
    if not stored or not verify_password(password, stored):
        return None
    return user


# ---------------------------------------------------------------------------
# Password hash storage: local-only side table created lazily on SQLite.
# Keeps the User model identical between Supabase and local deployments.
# ---------------------------------------------------------------------------
_PWHASH_TABLE = "local_credentials"


def _ensure_pwhash_table(db: Session) -> None:
    from sqlalchemy import text

    db.execute(
        text(
            f"create table if not exists {_PWHASH_TABLE} ("
            "user_id varchar(36) primary key, password_hash text not null)"
        )
    )


def _set_password_hash(user: User, password_hash: str) -> None:
    from sqlalchemy import text

    _ensure_pwhash_table(user._sa_instance_state.session)
    user._sa_instance_state.session.execute(
        text(
            f"insert or replace into {_PWHASH_TABLE} (user_id, password_hash) "
            "values (:uid, :ph)"
        ),
        {"uid": str(user.id), "ph": password_hash},
    )


def _get_password_hash(user: User) -> str | None:
    from sqlalchemy import text

    session = user._sa_instance_state.session
    if session is None:
        return None
    _ensure_pwhash_table(session)
    row = session.execute(
        text(f"select password_hash from {_PWHASH_TABLE} where user_id = :uid"),
        {"uid": str(user.id)},
    ).first()
    return row[0] if row else None
