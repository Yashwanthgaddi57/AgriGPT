"""Farm analytics service: KPIs from user history."""
import uuid
from datetime import date, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.disease_report import DiseaseReport
from app.models.market_prediction import MarketPrediction
from app.models.profit_prediction import ProfitPrediction
from app.models.recommendation import Recommendation
from app.services.dashboard_service import _season_now


def get_kpis(db: Session, user_id: str) -> dict:
    uid = uuid.UUID(user_id)
    now = date.today()
    month_ago = now - timedelta(days=30)
    two_months_ago = now - timedelta(days=60)

    # ---- Profit predictions this vs last month ----
    preds = (
        db.query(ProfitPrediction)
        .filter(ProfitPrediction.user_id == uid)
        .order_by(ProfitPrediction.created_at.desc())
        .limit(24)
        .all()
    )
    expected_revenue = float(preds[0].expected_revenue or 0) if preds else 0
    expected_profit = float(preds[0].expected_profit or 0) if preds else 0

    prev = [
        p for p in preds if two_months_ago <= p.created_at.date() < month_ago
    ]
    curr = [p for p in preds if p.created_at.date() >= month_ago]
    prev_profit = sum(float(p.expected_profit or 0) for p in prev) / len(prev) if prev else 0
    curr_profit = sum(float(p.expected_profit or 0) for p in curr) / len(curr) if curr else 0
    profit_growth = ((curr_profit - prev_profit) / prev_profit * 100) if prev_profit else 0

    # Yield growth: average predicted yield this month vs last month
    prev_yield = sum(float(p.expected_yield_quintals or 0) for p in prev) / len(prev) if prev else 0
    curr_yield = sum(float(p.expected_yield_quintals or 0) for p in curr) / len(curr) if curr else 0
    yield_growth = ((curr_yield - prev_yield) / prev_yield * 100) if prev_yield else 0

    # ---- Disease frequency (reports last 30 days) ----
    disease_count = (
        db.query(DiseaseReport)
        .filter(DiseaseReport.user_id == uid, DiseaseReport.created_at >= month_ago)
        .count()
    )
    disease_frequency = float(disease_count)

    # ---- Weather risk: heuristic from forecast data availability + season ----
    season = _season_now()
    season_risk = {"kharif": 55, "rabi": 35, "zaid": 45}.get(season, 50)
    weather_risk = float(season_risk)

    # ---- Accuracy scores: confidence of latest AI outputs ----
    latest_pred = preds[0] if preds else None
    profit_prediction_accuracy = float(latest_pred.confidence_score or 0) if latest_pred else 0

    latest_rec = (
        db.query(Recommendation)
        .filter(Recommendation.user_id == uid)
        .order_by(Recommendation.created_at.desc())
        .first()
    )
    rec_accuracy = 0.0
    if latest_rec and latest_rec.crops:
        scores = [float(c.get("confidence_score", 0)) for c in latest_rec.crops]
        rec_accuracy = sum(scores) / len(scores) if scores else 0

    return {
        "expected_revenue": expected_revenue,
        "expected_profit": expected_profit,
        "disease_frequency": disease_frequency,
        "yield_growth": round(yield_growth, 2),
        "profit_growth": round(profit_growth, 2),
        "weather_risk": weather_risk,
        "recommendation_accuracy": round(rec_accuracy, 2),
        "profit_prediction_accuracy": round(profit_prediction_accuracy, 2),
    }
