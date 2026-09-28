"""Web push notifications (optional, VAPID-gated).

Farmers subscribe once from the browser; the scheduler and alert flows call
`push_to_user` to deliver weather/market/disease alerts. Silent no-ops when
VAPID keys are not configured (local dev, tests).
"""
import json
import logging

from sqlalchemy.orm import Session

from app.core.config import settings

logger = logging.getLogger("app.push")


def push_enabled() -> bool:
    return bool(settings.VAPID_PUBLIC_KEY and settings.VAPID_PRIVATE_KEY)


def push_to_user(db: Session, user_id: str, title: str, body: str, url: str = "/dashboard") -> int:
    """Send a push to all of a user's subscriptions. Returns delivered count."""
    if not push_enabled():
        return 0
    from pywebpush import WebPushException, webpush

    from app.models.push_subscription import PushSubscription

    subs = (
        db.query(PushSubscription)
        .filter(PushSubscription.user_id == user_id)
        .all()
    )
    delivered = 0
    payload = json.dumps({"title": title, "body": body, "url": url})
    for sub in subs:
        try:
            webpush(
                subscription_info={
                    "endpoint": sub.endpoint,
                    "keys": {"p256dh": sub.p256dh, "auth": sub.auth},
                },
                data=payload,
                vapid_private_key=settings.VAPID_PRIVATE_KEY,
                vapid_claims={"sub": settings.VAPID_SUBJECT},
            )
            delivered += 1
        except WebPushException as e:
            code = getattr(e.response, "status_code", None)
            if code in (404, 410):  # subscription expired -> prune
                db.delete(sub)
                db.flush()
            else:
                logger.warning("Web push failed (%s): %s", code, str(e)[:120])
        except Exception as e:
            logger.warning("Web push error: %s", e)
    return delivered
