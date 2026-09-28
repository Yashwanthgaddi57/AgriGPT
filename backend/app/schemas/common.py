"""Shared response schemas."""
import uuid
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, field_validator

T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int
    pages: int


class UUIDCoercionMixin(BaseModel):
    """Coerces UUID objects to strings before validation (ORM -> API)."""

    @field_validator("*", mode="before", check_fields=False)
    @classmethod
    def coerce_uuid_to_str(cls, v: Any) -> Any:
        if isinstance(v, uuid.UUID):
            return str(v)
        if isinstance(v, list):
            return [cls.coerce_uuid_to_str(x) for x in v]
        return v
