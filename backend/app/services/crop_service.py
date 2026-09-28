"""Crop recommendation service."""
import asyncio
import logging
import uuid

from sqlalchemy.orm import Session

from app.ai.claude_client import get_claude
from app.ai.prompts import CROP_RECOMMENDATION_SYSTEM
from app.core.exceptions import AIError
from app.models.recommendation import Recommendation
from app.schemas.ai_features import CropRecommendationItem, CropRecommendationRequest

logger = logging.getLogger("app.services.crop")


class CropService:
    def __init__(self, db: Session):
        self.db = db

    async def recommend(self, user_id: str, req: CropRecommendationRequest) -> Recommendation:
        claude = get_claude()
        prompt = (
            f"Location: {req.location}\n"
            f"Season: {req.season}\n"
            f"Farm size: {req.farm_size_acres} acres\n"
            f"Soil: {req.soil_type}\n"
            f"Water: {req.water_source}\n"
            f"Budget: INR {req.budget_inr}\n\n"
            "Recommend exactly 5 crops ranked by expected profit."
        )
        try:
            data = await asyncio.to_thread(
                claude.complete_json,
                system=CROP_RECOMMENDATION_SYSTEM,
                messages=[{"role": "user", "content": prompt}],
            )
        except AIError:
            raise
        except Exception as e:
            logger.exception("Claude call failed")
            raise AIError(f"Crop recommendation failed: {e}") from e

        crops = []
        for c in data.get("crops", [])[:5]:
            try:
                crops.append(CropRecommendationItem(**c))
            except Exception:
                logger.warning("Skipping malformed crop item: %s", c)

        if not crops:
            raise AIError("AI returned no valid crop recommendations")

        rec = Recommendation(
            user_id=uuid.UUID(user_id),
            farm_id=uuid.UUID(req.farm_id) if req.farm_id else None,
            location=req.location,
            season=req.season,
            farm_size_acres=req.farm_size_acres,
            soil_type=req.soil_type,
            water_source=req.water_source,
            budget_inr=req.budget_inr,
            crops=[c.model_dump() for c in crops],
            model=settings_model(),
            prompt_tokens=claude.last_usage.get("prompt_tokens"),
            completion_tokens=claude.last_usage.get("completion_tokens"),
        )
        self.db.add(rec)
        self.db.flush()
        return rec


def settings_model() -> str | None:
    from app.core.config import settings

    return settings.ANTHROPIC_MODEL
