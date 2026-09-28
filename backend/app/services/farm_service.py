"""Farm CRUD service."""
import uuid

from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.models.farm import Farm
from app.schemas.farm import FarmCreate, FarmUpdate


class FarmService:
    def __init__(self, db: Session):
        self.db = db

    def list_farms(self, user_id: str) -> list[Farm]:
        return (
            self.db.query(Farm)
            .filter(Farm.user_id == uuid.UUID(user_id))
            .order_by(Farm.created_at.desc())
            .all()
        )

    def create_farm(self, user_id: str, data: FarmCreate) -> Farm:
        farm = Farm(user_id=uuid.UUID(user_id), **data.model_dump())
        self.db.add(farm)
        self.db.flush()
        return farm

    def get_farm(self, user_id: str, farm_id: str) -> Farm:
        farm = (
            self.db.query(Farm)
            .filter(Farm.id == uuid.UUID(farm_id), Farm.user_id == uuid.UUID(user_id))
            .first()
        )
        if not farm:
            raise NotFoundError("Farm not found")
        return farm

    def update_farm(self, user_id: str, farm_id: str, data: FarmUpdate) -> Farm:
        farm = self.get_farm(user_id, farm_id)
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(farm, field, value)
        self.db.flush()
        return farm

    def delete_farm(self, user_id: str, farm_id: str) -> None:
        farm = self.get_farm(user_id, farm_id)
        self.db.delete(farm)
