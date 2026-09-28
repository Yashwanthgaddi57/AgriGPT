"""AgriSphere AI — FastAPI application entrypoint."""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.database import init_db
from app.core.exceptions import register_exception_handlers
from app.core.logging import configure_logging
from app.core.middleware import get_middlewares
from app.routers import api_router
from app.scheduler import start_scheduler, stop_scheduler

configure_logging()
logger = logging.getLogger("app.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting %s [%s]", settings.PROJECT_NAME, settings.ENVIRONMENT)
    from app.core.observability import init_observability

    init_observability()
    if settings.is_production:
        # Die loudly on dangerous misconfig (local-auth fallback, SQLite, placeholder secrets)
        settings.assert_production_ready()
    init_db()
    # Seed mandi + vendor directories (idempotent, any database)
    try:
        from app.core.database import get_session_factory
        from app.services.seed_geo_data import seed_geo_data

        db = get_session_factory()()
        try:
            counts = seed_geo_data(db)
            db.commit()
            if counts["mandis_added"] or counts["vendors_added"]:
                logger.info("Seeded geo directory: %s", counts)
        finally:
            db.close()
    except Exception as e:
        logger.warning("Geo seed skipped: %s", e)
    start_scheduler()
    yield
    stop_scheduler()
    logger.info("Shutdown complete")


app = FastAPI(
    title=settings.PROJECT_NAME,
    version="1.0.0",
    description="AI-Powered Farmer Income Optimization Platform",
    lifespan=lifespan,
    docs_url="/docs",
    openapi_url="/openapi.json",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Custom middleware
for mw in get_middlewares():
    app.add_middleware(mw)

register_exception_handlers(app)

# Routes
app.include_router(api_router, prefix=settings.API_V1_PREFIX)


@app.get("/health", tags=["system"])
@app.get("/api/v1/health", tags=["system"])
async def health() -> dict:
    return {"status": "ok", "service": settings.PROJECT_NAME, "environment": settings.ENVIRONMENT}
