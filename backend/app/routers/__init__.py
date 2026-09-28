"""API v1 router aggregation."""
from fastapi import APIRouter

from app.routers import (
    admin,
    analytics,
    auth,
    chat,
    crops,
    dashboard,
    disease,
    farm_engine,
    geo,
    market,
    notifications,
    profit,
    push,
    subscription,
    users,
    weather,
)

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(geo.router)
api_router.include_router(dashboard.router)
api_router.include_router(crops.router)
api_router.include_router(disease.router)
api_router.include_router(profit.router)
api_router.include_router(market.router)
api_router.include_router(weather.router)
api_router.include_router(chat.router)
api_router.include_router(notifications.router)
api_router.include_router(analytics.router)
api_router.include_router(subscription.router)
api_router.include_router(farm_engine.router)
api_router.include_router(admin.router)
api_router.include_router(push.router)
