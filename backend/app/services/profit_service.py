"""Profit prediction service."""
import asyncio
import logging
import uuid

from sqlalchemy.orm import Session

from app.ai.claude_client import get_claude
from app.ai.prompts import PROFIT_OPTIMIZATION_SYSTEM
from app.core.config import settings
from app.core.exceptions import AIError
from app.models.profit_prediction import ProfitPrediction
from app.schemas.ai_features import ProfitPredictionRequest

logger = logging.getLogger("app.services.profit")


class ProfitService:
    def __init__(self, db: Session):
        self.db = db

    async def predict(self, user_id: str, req: ProfitPredictionRequest) -> ProfitPrediction:
        claude = get_claude()
        total_cost = (
            req.seed_cost
            + req.labor_cost
            + req.fertilizer_cost
            + req.irrigation_cost
            + req.transportation_cost
            + req.other_cost
        )
        prompt = (
            f"Crop: {req.crop}\n"
            f"Farm size: {req.farm_size_acres} acres\n"
            f"Season: {req.season or 'unspecified'}\n"
            f"Itemized costs (INR): seed={req.seed_cost}, labor={req.labor_cost}, "
            f"fertilizer={req.fertilizer_cost}, irrigation={req.irrigation_cost}, "
            f"transport={req.transportation_cost}, other={req.other_cost}. "
            f"Total: {total_cost}\n\n"
            "Produce the profit projection JSON with best/average/worst scenarios."
        )
        try:
            data = await asyncio.to_thread(
                claude.complete_json,
                system=PROFIT_OPTIMIZATION_SYSTEM,
                messages=[{"role": "user", "content": prompt}],
            )
        except Exception as e:
            logger.exception("Profit prediction failed")
            raise AIError(f"Profit prediction failed: {e}") from e

        scenarios = data.get("scenarios", {})
        prediction = ProfitPrediction(
            user_id=uuid.UUID(user_id),
            farm_id=uuid.UUID(req.farm_id) if req.farm_id else None,
            crop=req.crop,
            farm_size_acres=req.farm_size_acres,
            season=req.season,
            seed_cost=req.seed_cost,
            labor_cost=req.labor_cost,
            fertilizer_cost=req.fertilizer_cost,
            irrigation_cost=req.irrigation_cost,
            transportation_cost=req.transportation_cost,
            other_cost=req.other_cost,
            total_cost=total_cost,
            expected_yield_quintals=float(data.get("expected_yield_quintals", 0)),
            expected_price_per_quintal=float(data.get("expected_price_per_quintal", 0)),
            expected_revenue=float(data.get("expected_revenue", 0)),
            expected_profit=float(data.get("expected_profit", 0)),
            roi=float(data.get("roi_percent", 0)),
            risk_score=float(data.get("risk_score", 0)),
            confidence_score=float(data.get("confidence_score", 0)),
            scenarios=scenarios,
            model=settings.ANTHROPIC_MODEL,
        )
        self.db.add(prediction)
        self.db.flush()
        return prediction
