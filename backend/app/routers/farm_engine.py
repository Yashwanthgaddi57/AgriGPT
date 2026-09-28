"""Decision engine + farm economics endpoints (Parts 4-5, 17-20)."""
import uuid as uuidlib
from datetime import date

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.core.deps import CurrentUser, DBSession
from app.models.disease_report import DiseaseReport
from app.models.expense import EXPENSE_CATEGORIES, Expense
from app.models.farm import Farm
from app.models.harvest import Harvest
from app.models.profit_prediction import ProfitPrediction
from app.models.recommendation import Recommendation
from app.services.activity_service import log_activity
from app.services.decision_engine import build_today_plan
from app.services.ownership import resolve_owned_farm
from app.services.market_service import price_snapshot

router = APIRouter(prefix="/farm", tags=["farm-engine"])


# ---------------- Today's Farm Plan (Decision Engine) ----------------
@router.get("/today")
async def today_plan(user: CurrentUser, db: DBSession):
    """TODAY'S FARM PLAN — deterministic priorities from live data."""
    return await build_today_plan(db, user)


# ---------------- Expenses (Part 19) ----------------
class ExpenseCreate(BaseModel):
    category: str
    amount_inr: float = Field(gt=0)
    description: str | None = Field(default=None, max_length=300)
    spent_on: date
    farm_id: str | None = None


class HarvestCreate(BaseModel):
    crop: str = Field(min_length=1, max_length=80)
    harvest_date: date | None = None
    actual_yield_quintals: float | None = Field(default=None, ge=0)
    selling_price_per_quintal: float | None = Field(default=None, ge=0)
    market_name: str | None = Field(default=None, max_length=120)
    revenue_inr: float | None = Field(default=None, ge=0)
    notes: str | None = Field(default=None, max_length=500)
    farm_id: str | None = None


@router.get("/expenses")
async def list_expenses(user: CurrentUser, db: DBSession, limit: int = 100):
    uid = uuidlib.UUID(str(user.id))
    items = (
        db.query(Expense)
        .filter(Expense.user_id == uid)
        .order_by(Expense.spent_on.desc())
        .limit(limit)
        .all()
    )
    total = sum(float(e.amount_inr or 0) for e in items)
    by_category: dict[str, float] = {}
    for e in items:
        by_category[e.category] = by_category.get(e.category, 0) + float(e.amount_inr or 0)

    # per-acre using the primary farm (or profile size)
    farm = db.query(Farm).filter(Farm.user_id == uid).first()
    acres = float(farm.area_acres) if farm and farm.area_acres else float(user.farm_size_acres or 0)

    return {
        "items": items,
        "total": total,
        "per_acre": (total / acres) if acres > 0 else 0,
        "by_category": by_category,
    }


@router.post("/expenses", status_code=201)
async def create_expense(payload: ExpenseCreate, user: CurrentUser, db: DBSession):
    if payload.category not in EXPENSE_CATEGORIES:
        from app.core.exceptions import ValidationError

        raise ValidationError(f"Category must be one of: {', '.join(EXPENSE_CATEGORIES)}")
    # P0 IDOR fix: a client-supplied farm_id must belong to THIS user.
    owned = resolve_owned_farm(db, user, payload.farm_id)
    expense = Expense(
        user_id=uuidlib.UUID(str(user.id)),
        farm_id=owned.id if owned else None,
        category=payload.category,
        amount_inr=payload.amount_inr,
        description=payload.description,
        spent_on=payload.spent_on,
    )
    db.add(expense)
    db.flush()
    log_activity(db, str(user.id), "expense.created", "expense", str(expense.id), {"category": payload.category})
    return expense


@router.delete("/expenses/{expense_id}", status_code=204)
async def delete_expense(expense_id: str, user: CurrentUser, db: DBSession):
    deleted = (
        db.query(Expense)
        .filter(Expense.id == uuidlib.UUID(expense_id), Expense.user_id == uuidlib.UUID(str(user.id)))
        .delete(synchronize_session=False)
    )
    if not deleted:
        from app.core.exceptions import NotFoundError

        raise NotFoundError("Expense not found")


# ---------------- Harvest (Part 20) ----------------
@router.get("/harvests")
async def list_harvests(user: CurrentUser, db: DBSession, limit: int = 50):
    uid = uuidlib.UUID(str(user.id))
    items = (
        db.query(Harvest)
        .filter(Harvest.user_id == uid)
        .order_by(Harvest.harvest_date.desc().nullslast(), Harvest.created_at.desc())
        .limit(limit)
        .all()
    )
    return {"items": items}


@router.post("/harvests", status_code=201)
async def create_harvest(payload: HarvestCreate, user: CurrentUser, db: DBSession):
    # P0 IDOR fix: a client-supplied farm_id must belong to THIS user.
    owned = resolve_owned_farm(db, user, payload.farm_id)
    # Revenue can be derived deterministically if yield+price given.
    revenue = payload.revenue_inr
    if revenue is None and payload.actual_yield_quintals is not None and payload.selling_price_per_quintal is not None:
        revenue = payload.actual_yield_quintals * payload.selling_price_per_quintal
    harvest = Harvest(
        user_id=uuidlib.UUID(str(user.id)),
        farm_id=owned.id if owned else None,
        crop=payload.crop,
        harvest_date=payload.harvest_date,
        actual_yield_quintals=payload.actual_yield_quintals,
        selling_price_per_quintal=payload.selling_price_per_quintal,
        market_name=payload.market_name,
        revenue_inr=revenue,
        notes=payload.notes,
    )
    db.add(harvest)
    db.flush()
    log_activity(db, str(user.id), "harvest.created", "harvest", str(harvest.id), {"crop": payload.crop})
    return harvest


@router.delete("/harvests/{harvest_id}", status_code=204)
async def delete_harvest(harvest_id: str, user: CurrentUser, db: DBSession):
    deleted = (
        db.query(Harvest)
        .filter(Harvest.id == uuidlib.UUID(harvest_id), Harvest.user_id == uuidlib.UUID(str(user.id)))
        .delete(synchronize_session=False)
    )
    if not deleted:
        from app.core.exceptions import NotFoundError

        raise NotFoundError("Harvest not found")


# ---------------- Estimated vs Actual (Part 18) ----------------
@router.get("/estimated-vs-actual")
async def estimated_vs_actual(user: CurrentUser, db: DBSession):
    """Latest profit estimate vs latest recorded harvest + recorded expenses."""
    uid = uuidlib.UUID(str(user.id))
    latest_est = (
        db.query(ProfitPrediction)
        .filter(ProfitPrediction.user_id == uid)
        .order_by(ProfitPrediction.created_at.desc())
        .first()
    )
    latest_harvest = (
        db.query(Harvest)
        .filter(Harvest.user_id == uid)
        .order_by(Harvest.created_at.desc())
        .first()
    )
    expenses = (
        db.query(Expense)
        .filter(Expense.user_id == uid)
        .with_entities(Expense.amount_inr)
        .all()
    )
    actual_cost = float(sum((e[0] or 0) for e in expenses)) if expenses else 0

    def _f(v):
        return float(v) if v is not None else None

    estimated = {
        "crop": latest_est.crop if latest_est else None,
        "yield_quintals": _f(latest_est.expected_yield_quintals) if latest_est else None,
        "price_per_quintal": _f(latest_est.expected_price_per_quintal) if latest_est else None,
        "revenue": _f(latest_est.expected_revenue) if latest_est else None,
        "cost": _f(latest_est.total_cost) if latest_est else None,
        "profit": _f(latest_est.expected_profit) if latest_est else None,
    }
    actual = {
        "crop": latest_harvest.crop if latest_harvest else None,
        "yield_quintals": _f(latest_harvest.actual_yield_quintals) if latest_harvest else None,
        "price_per_quintal": _f(latest_harvest.selling_price_per_quintal) if latest_harvest else None,
        "revenue": _f(latest_harvest.revenue_inr) if latest_harvest else None,
        "cost": actual_cost if actual_cost > 0 else None,
        "profit": (
            (float(latest_harvest.revenue_inr or 0) - actual_cost)
            if latest_harvest and latest_harvest.revenue_inr is not None and actual_cost > 0
            else None
        ),
    }

    def _delta(k):
        if estimated[k] is None or actual[k] is None:
            return None
        return round(actual[k] - estimated[k], 2)

    return {
        "estimated": estimated,
        "actual": actual,
        "difference": {
            k: _delta(k)
            for k in ("yield_quintals", "price_per_quintal", "revenue", "cost", "profit")
        },
        "has_comparison": bool(latest_est and latest_harvest),
    }


# ---------------- Farm Timeline (Part 17) ----------------
@router.get("/timeline")
async def farm_timeline(user: CurrentUser, db: DBSession, limit: int = 60):
    """Unified farm memory: harvests, scans, plans, estimates, alerts."""
    uid = uuidlib.UUID(str(user.id))
    events: list[dict] = []

    harvests = (
        db.query(Harvest).filter(Harvest.user_id == uid)
        .order_by(Harvest.created_at.desc()).limit(limit // 4).all()
    )
    for h in harvests:
        events.append({
            "date": (h.harvest_date or h.created_at.date()).isoformat(),
            "type": "harvest",
            "title": f"{h.crop.capitalize()} harvested",
            "detail": (
                f"Yield {float(h.actual_yield_quintals or 0):.1f} q at ₹{float(h.selling_price_per_quintal or 0):,.0f}/q"
                if h.actual_yield_quintals else "Harvest recorded"
            ),
        })

    scans = (
        db.query(DiseaseReport).filter(DiseaseReport.user_id == uid)
        .order_by(DiseaseReport.created_at.desc()).limit(limit // 4).all()
    )
    for s in scans:
        events.append({
            "date": s.created_at.date().isoformat(),
            "type": "scan",
            "title": f"Crop scan: {s.disease_name}",
            "detail": f"{s.crop} · {s.confidence:.0f}% confidence" + ("" if s.is_healthy else " · follow-up advised"),
        })

    recs = (
        db.query(Recommendation).filter(Recommendation.user_id == uid)
        .order_by(Recommendation.created_at.desc()).limit(limit // 4).all()
    )
    for r in recs:
        top = r.crops[0].get("crop_name") if r.crops else None
        events.append({
            "date": r.created_at.date().isoformat(),
            "type": "plan",
            "title": "Farm plan created",
            "detail": f"Top option: {top}" if top else "Crop options generated",
        })

    preds = (
        db.query(ProfitPrediction).filter(ProfitPrediction.user_id == uid)
        .order_by(ProfitPrediction.created_at.desc()).limit(limit // 4).all()
    )
    for p in preds:
        events.append({
            "date": p.created_at.date().isoformat(),
            "type": "estimate",
            "title": f"Profit estimate for {p.crop}",
            "detail": f"Cost ₹{float(p.total_cost or 0):,.0f} · expected profit ₹{float(p.expected_profit or 0):,.0f}",
        })

    events.sort(key=lambda e: e["date"], reverse=True)
    return {"items": events[:limit]}
