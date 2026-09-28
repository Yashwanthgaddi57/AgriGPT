"""JWT verification for Supabase Auth tokens and password hashing utilities."""
from datetime import datetime, timezone
from typing import Any

import jwt
from fastapi import HTTPException, status
from jwt import PyJWKClient

from app.core.config import settings

# Cache Supabase's JWKS so we can verify RS256 tokens without secrets.
_jwks_client: PyJWKClient | None = None


def _get_jwks_client() -> PyJWKClient:
    global _jwks_client
    if _jwks_client is None:
        _jwks_client = PyJWKClient(f"{settings.SUPABASE_URL}/auth/v1/.well-known/jwks.json")
    return _jwks_client


def decode_supabase_jwt(token: str) -> dict[str, Any]:
    """Verify a Supabase access token (RS256 via JWKS, HS256 fallback to JWT secret)."""
    try:
        header = jwt.get_unverified_header(token)
    except jwt.PyJWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
        ) from e

    try:
        alg = header.get("alg")
        if alg in ("RS256", "ES256"):
            # Supabase asymmetric signing keys (new projects default to ES256,
            # legacy projects use RS256) — verified via the public JWKS.
            signing_key = _get_jwks_client().get_signing_key_from_jwt(token)
            payload: dict[str, Any] = jwt.decode(
                token,
                signing_key.key,
                algorithms=[alg],
                audience="authenticated",
                options={"verify_exp": True},
            )
        else:
            payload = jwt.decode(
                token,
                settings.SUPABASE_JWT_SECRET,
                algorithms=["HS256"],
                audience="authenticated",
                options={"verify_exp": True},
            )
    except jwt.ExpiredSignatureError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
        ) from e
    except jwt.PyJWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
        ) from e

    if payload.get("role") not in ("authenticated", "service_role"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient role",
        )
    return payload


def token_expiry(token: str) -> datetime:
    payload = jwt.decode(token, options={"verify_signature": False})
    exp = payload.get("exp")
    return datetime.fromtimestamp(exp, tz=timezone.utc) if exp else datetime.now(tz=timezone.utc)
