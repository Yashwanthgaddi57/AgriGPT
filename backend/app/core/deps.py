"""Shared FastAPI dependencies."""
from typing import Annotated

from fastapi import HTTPException, status

from fastapi import Depends, Query
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.exceptions import NotFoundError
from app.core.local_auth import decode_local_token, is_token_revoked, local_auth_enabled
from app.core.security import decode_supabase_jwt
from app.models.user import User

bearer_scheme = HTTPBearer(auto_error=True)

DBSession = Annotated[Session, Depends(get_db)]


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Decode JWT (local HS256 or Supabase), auto-provision profile, return User."""
    if local_auth_enabled():
        try:
            payload = decode_local_token(credentials.credentials)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token",
            ) from e
        jti = payload.get("jti")
        if jti and is_token_revoked(db, jti):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has been revoked",
            )
    else:
        payload = decode_supabase_jwt(credentials.credentials)
    auth_user_id: str = payload["sub"]
    email: str = payload.get("email") or ""

    user = db.get(User, auth_user_id)
    if user is None and email:
        # Same email may already exist under a different local id (e.g. the
        # user was registered before Supabase auth was wired up). Reuse it
        # instead of hitting the users.email unique constraint.
        user = db.execute(
            select(User).where(User.email == email)
        ).scalar_one_or_none()
    if user is None:
        # Auto-provision profile on first authenticated request
        meta = payload.get("user_metadata") or {}
        user = User(
            id=auth_user_id,
            email=email or f"{auth_user_id}@placeholder.local",
            name=meta.get("name") or email.split("@")[0] if email else "Farmer",
            phone=meta.get("phone"),
            district=meta.get("district"),
            state=meta.get("state"),
            village=meta.get("village"),
            farm_size_acres=meta.get("farm_size_acres") or 0,
            soil_type=meta.get("soil_type") or "unknown",
            water_availability=meta.get("water_availability") or "rainfed",
        )
        db.add(user)
        db.flush()
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


class PaginationParams:
    def __init__(
        self,
        page: int = Query(1, ge=1),
        page_size: int = Query(20, ge=1, le=100),
    ):
        self.page = page
        self.page_size = page_size
        self.offset = (page - 1) * page_size


Pagination = Annotated[PaginationParams, Depends(PaginationParams)]


def get_user_or_404(db: Session, user_id: str) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise NotFoundError("User not found")
    return user
