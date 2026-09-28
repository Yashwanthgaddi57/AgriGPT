"""Central plan configuration — single source of truth for pricing & limits.

Used by:
  - backend enforcement (plan_limits service)
  - GET /api/v1/subscription/plans (frontend pricing page reads this)
  - rate-limit tiers (middleware)

Pricing/limits live HERE only; never hard-code them in frontend components.
"""

FREE = "free"
PRO = "pro"
COOPERATIVE = "cooperative"

# Monthly usage allowances. -1 = unlimited.
PLAN_LIMITS: dict[str, dict[str, int]] = {
    FREE: {
        "crop_recommendations": 5,
        "disease_scans": 10,
        "chat_messages_per_day": 20,
        "market_analyses": 3,
        "profit_predictions": 5,
    },
    PRO: {
        "crop_recommendations": -1,
        "disease_scans": -1,
        "chat_messages_per_day": -1,
        "market_analyses": -1,
        "profit_predictions": -1,
    },
    COOPERATIVE: {
        "crop_recommendations": -1,
        "disease_scans": -1,
        "chat_messages_per_day": -1,
        "market_analyses": -1,
        "profit_predictions": -1,
    },
}

# Marketing-facing metadata. `features` describe what each tier includes;
# anything listed here must actually exist in the product today.
PLAN_META: dict[str, dict] = {
    FREE: {
        "name": "Kisan Free",
        "price_inr": 0,
        "period": "forever",
        "description": "Core AI tools for smallholders.",
        "features": [
            "5 crop plans / month",
            "10 disease scans / month",
            "Weather intelligence",
            "AI Copilot (20 messages/day)",
            "Profit calculator",
        ],
    },
    PRO: {
        "name": "Pro Farmer",
        "price_inr": 299,
        "period": "per month",
        "description": "For serious growers who want every edge.",
        "features": [
            "Unlimited crop plans",
            "Unlimited disease scans + health history",
            "Market intelligence & sell/wait guidance",
            "AI Copilot (unlimited)",
            "Priority support queue",
        ],
        "cta": "Go Pro",
        "highlight": True,
    },
    COOPERATIVE: {
        "name": "Cooperative / FPO",
        # Not a purchasable product yet: the org dashboard is in development.
        # price_inr None renders as "Early access" / "Contact us" everywhere.
        "price_inr": None,
        "period": "early access",
        "description": "For FPOs, NGOs and agri-program teams.",
        "features": [
            "Organization dashboard (in development)",
            "Multi-farmer management*",
            "Aggregated analytics & reports*",
            "Admin controls*",
        ],
        "cta": "Contact us",
        "highlight": False,
        # * = organization features are on the roadmap; marked with * on the
        # pricing page so nothing is promised that does not exist yet.
    },
}

ALL_PLANS = [FREE, PRO, COOPERATIVE]


def plan_limits(plan: str) -> dict[str, int]:
    return PLAN_LIMITS.get(plan, PLAN_LIMITS[FREE])


def is_unlimited(plan: str, feature: str) -> bool:
    return plan_limits(plan).get(feature, 0) == -1
