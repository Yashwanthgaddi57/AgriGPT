"""Sentry + error tracking initialization (env-gated, fail-soft).

Set SENTRY_DSN to activate. Without it, everything is a no-op so local dev
and tests stay clean. Traces sample rate is conservative by default.
"""
import logging

logger = logging.getLogger("app.observability")


def init_observability() -> None:
    from app.core.config import settings

    dsn = (settings.SENTRY_DSN or "").strip()
    if not dsn or dsn.startswith("your-"):
        return
    try:
        import sentry_sdk
        from sentry_sdk.integrations.fastapi import FastAPIIntegration
        from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration

        sentry_sdk.init(
            dsn=dsn,
            environment=settings.ENVIRONMENT,
            traces_sample_rate=settings.SENTRY_TRACES_SAMPLE_RATE,
            send_default_pii=False,
            integrations=[FastAPIIntegration(), SqlalchemyIntegration()],
        )
        logger.info("Sentry initialized [%s]", settings.ENVIRONMENT)
    except Exception as e:
        logger.warning("Sentry init failed (continuing without): %s", e)
