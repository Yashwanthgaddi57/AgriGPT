"""Test data factories."""
import uuid
from datetime import datetime, timezone

from app.models.disease_report import DiseaseReport
from app.models.farm import Farm
from app.models.profit_prediction import ProfitPrediction
from app.models.user import User


def make_user(db, **overrides) -> User:
    uid = uuid.uuid4()
    user = User(
        id=uid,
        email=f"farmer-{uid.hex[:8]}@example.com",
        name=overrides.get("name", "Test Farmer"),
        district=overrides.get("district", "Nashik"),
        state=overrides.get("state", "Maharashtra"),
        village=overrides.get("village", "Ozar"),
        farm_size_acres=overrides.get("farm_size_acres", 5),
        soil_type=overrides.get("soil_type", "black"),
        water_availability=overrides.get("water_availability", "borewell"),
        onboarding_completed=True,
    )
    db.add(user)
    db.flush()
    return user


def make_farm(db, user, **overrides) -> Farm:
    farm = Farm(
        user_id=user.id,
        name=overrides.get("name", "North Plot"),
        area_acres=overrides.get("area_acres", 4),
        soil_type=overrides.get("soil_type", "black"),
        water_source=overrides.get("water_source", "borewell"),
        current_crop=overrides.get("current_crop", "cotton"),
        current_season="kharif",
    )
    db.add(farm)
    db.flush()
    return farm


def make_profit_prediction(db, user, **overrides) -> ProfitPrediction:
    p = ProfitPrediction(
        user_id=user.id,
        crop=overrides.get("crop", "cotton"),
        farm_size_acres=overrides.get("farm_size_acres", 5),
        total_cost=overrides.get("total_cost", 50000),
        expected_yield_quintals=overrides.get("expected_yield_quintals", 50),
        expected_price_per_quintal=overrides.get("expected_price_per_quintal", 7000),
        expected_revenue=overrides.get("expected_revenue", 350000),
        expected_profit=overrides.get("expected_profit", 300000),
        roi=overrides.get("roi", 600),
        scenarios={"best": {}, "average": {}, "worst": {}},
    )
    db.add(p)
    db.flush()
    return p


def make_disease_report(db, user, **overrides) -> DiseaseReport:
    r = DiseaseReport(
        user_id=user.id,
        crop=overrides.get("crop", "cotton"),
        disease_name=overrides.get("disease_name", "Leaf Curl Virus"),
        is_healthy=False,
        confidence=92.5,
        severity=overrides.get("severity", "medium"),
        severity_score=40,
    )
    db.add(r)
    db.flush()
    return r
