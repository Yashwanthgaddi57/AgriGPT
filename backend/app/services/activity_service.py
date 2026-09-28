"""Activity logging service."""
import uuid

from sqlalchemy.orm import Session

from app.models.activity import Activity


def log_activity(
    db: Session,
    user_id: str,
    action: str,
    entity_type: str | None = None,
    entity_id: str | None = None,
    metadata: dict | None = None,
) -> None:
    db.add(
        Activity(
            user_id=uuid.UUID(user_id),
            action=action,
            entity_type=entity_type,
            entity_id=uuid.UUID(entity_id) if entity_id else None,
            metadata_json=metadata or {},
        )
    )
