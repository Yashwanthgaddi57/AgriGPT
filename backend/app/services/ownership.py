"""Ownership helper for caller-supplied farm_id values.

create_expense / create_harvest / disease.analyze all accept a client-supplied
`farm_id`. Until now that value was trusted blindly, so User A could attach
an expense to User B's farm (201, A's user_id on B's farm_id) — a P0 IDOR.

Every caller-supplied farm_id must be resolved against the authenticated user
before being persisted. Unknown/foreign ids raise NotFoundError so the caller
gets a 404 and the resource is never created.
"""
import uuid as uuidlib

from sqlalchemy import select

from app.core.exceptions import NotFoundError
from app.models.farm import Farm


def resolve_owned_farm(db, user, farm_id: str | None):
    """Return the caller's Farm for `farm_id`, or None when no farm is given.

    Raises NotFoundError when a farm_id is supplied but does not belong to
    the authenticated user (prevents cross-user resource attachment).
    """
    if not farm_id:
        return None
    try:
        fid = uuidlib.UUID(str(farm_id))
    except (ValueError, TypeError):
        raise NotFoundError("Farm not found")
    farm = db.execute(
        select(Farm).where(
            Farm.id == fid,
            Farm.user_id == uuidlib.UUID(str(user.id)),
        )
    ).scalar_one_or_none()
    if farm is None:
        raise NotFoundError("Farm not found")
    return farm