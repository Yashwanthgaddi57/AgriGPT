"""Background scheduler: generates weather + market + agro-action alerts for active users.

Three alert kinds, all fail-soft and rate-limited by the scheduler interval:
  - weather alerts   (existing) — from WeatherService.get_intelligence
  - market alerts    (new)      — price moves vs last week via price_snapshot
  - agro actions     (new)      — plant/irrigate/harvest actions from the weather agent
"""
import asyncio
import logging
from datetime import datetime, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy.orm import Session as SASession

from app.core.config import settings

logger = logging.getLogger("app.scheduler")
scheduler = AsyncIOScheduler(timezone="UTC")

# Suppress repeat alerts: remember (user, kind, dedup key) -> last sent date.
# In-memory only — prevents same-day duplicates within a process lifetime.
_alert_dedup: dict[tuple[str, str, str], str] = {}


def _already_sent_today(user_id: str, kind: str, key: str) -> bool:
    today = datetime.now(timezone.utc).date().isoformat()
    return _alert_dedup.get((user_id, kind, key)) == today


def _mark_sent(user_id: str, kind: str, key: str) -> None:
    _alert_dedup[(user_id, kind, key)] = datetime.now(timezone.utc).date().isoformat()


async def generate_alerts() -> None:
    """Scan active users, create weather/market/agro-action notifications."""
    from app.core.database import get_session_factory
    from app.models.user import User
    from app.services.market_service import price_snapshot, resolve_price_context
    from app.services.notification_service import NotificationService
    from app.services.weather_service import WeatherService

    db: SASession = get_session_factory()()
    try:
        users = (
            db.query(User)
            .filter(User.onboarding_completed.is_(True))
            .limit(200)
            .all()
        )
        notif_service = NotificationService(db)
        sent_count = 0

        for user in users:
            uid = str(user.id)
            location = user.district or user.village
            try:
                # ---------------- Weather + agro actions ----------------
                if location:
                    wx_service = WeatherService(db)
                    wx = await wx_service.get_intelligence(uid, location, save=False)
                    for alert in wx.get("alerts", [])[:2]:
                        key = f"wx:{alert[:80]}"
                        if _already_sent_today(uid, "weather", key):
                            continue
                        notif_service.create(
                            user_id=uid,
                            type_="weather",
                            title="Weather alert",
                            body=alert,
                            link="/dashboard/weather",
                        )
                        _mark_sent(uid, "weather", key)
                        sent_count += 1

                    # Agro action from the weather agent (heuristic or AI)
                    action = (wx.get("action") or "none").replace("_", " ")
                    recommendation = wx.get("ai_recommendation")
                    if action and action != "none":
                        key = f"action:{action}"
                        if not _already_sent_today(uid, "action", key):
                            notif_service.create(
                                user_id=uid,
                                type_="action",
                                title="Farm action suggested",
                                body=recommendation or f"Suggested action for today: {action}.",
                                link="/dashboard/weather",
                            )
                            _mark_sent(uid, "action", key)
                            sent_count += 1

                # ---------------- Market alerts ----------------
                ctx = resolve_price_context(db, user)
                crops = ctx["crops"][:4]  # keep the pass fast
                for crop in crops:
                    # Worker thread: data.gov.in calls are blocking and must
                    # never stall the event loop serving live requests.
                    snap = await asyncio.to_thread(
                        price_snapshot, crop, state=ctx["state"], district=ctx["district"]
                    )
                    trend = float(snap.get("trend_weekly_pct") or 0)
                    if abs(trend) < 5:  # only meaningful moves
                        continue
                    direction = "up" if trend > 0 else "down"
                    place = ctx["district"] or ctx["state"] or "your region"
                    title = f"{crop.capitalize()} price {direction} {abs(trend):.0f}% this week"
                    body = (
                        (
                            "Sell soon — prices are rising and may soften. "
                            if trend > 0
                            else "Consider selling now or negotiating hard — the trend is against waiting. "
                        )
                        + f"Current: Rs {snap['price']:,.0f}/quintal in {place} "
                        + f"(source: {'live mandi data' if snap.get('is_live') else 'model estimate'})."
                    )
                    key = f"mkt:{crop}:{direction}"
                    if _already_sent_today(uid, "market", key):
                        continue
                    notif_service.create(
                        user_id=uid,
                        type_="market",
                        title=title,
                        body=body,
                        link="/dashboard/market",
                    )
                    _mark_sent(uid, "market", key)
                    sent_count += 1

            except Exception as e:
                logger.warning("Alert generation failed for user %s: %s", user.id, e)

            # Commit per user. Each notification insert takes a write lock and
            # the rest of the pass makes slow network calls (weather, mandi
            # prices), so a single transaction spanning every user held the
            # lock for the whole pass and locked live requests out of SQLite.
            db.commit()

        db.commit()
        logger.info(
            "Alert generation pass complete: %d users, %d notifications", len(users), sent_count
        )
    finally:
        db.close()


def start_scheduler() -> None:
    if not settings.SCHEDULER_ENABLED:
        return
    try:
        scheduler.add_job(
            generate_alerts,
            IntervalTrigger(minutes=settings.SCHEDULER_INTERVAL_MINUTES),
            id="generate_alerts",
            replace_existing=True,
        )
        scheduler.start()
        logger.info("Scheduler started (interval=%s min)", settings.SCHEDULER_INTERVAL_MINUTES)
    except Exception as e:
        # Scheduler is optional (e.g. restricted environments); never block startup.
        logger.warning("Scheduler disabled: %s", e)


def stop_scheduler() -> None:
    if scheduler.running:
        scheduler.shutdown(wait=False)
