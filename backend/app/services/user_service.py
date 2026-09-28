"""User profile service."""
from sqlalchemy.orm import Session

from app.models.user import User
from app.schemas.user import ProfileUpdate


class UserService:
    def __init__(self, db: Session):
        self.db = db

    def update_profile(self, user: User, data: ProfileUpdate) -> User:
        for field, value in data.model_dump(exclude_unset=True, exclude_none=True).items():
            setattr(user, field, value)
        user.onboarding_completed = True
        self.db.add(user)
        self.db.flush()
        return user
