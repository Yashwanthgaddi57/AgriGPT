"""Notification service: in-app, email (Resend), alert generation."""
import asyncio
import logging
import uuid
from datetime import datetime, timezone

import httpx
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.notifications import Notification

logger = logging.getLogger("app.services.notifications")


class NotificationService:
    def __init__(self, db: Session):
        self.db = db

    def create(
        self,
        user_id: str,
        type_: str,
        title: str,
        body: str,
        link: str | None = None,
        channel: str = "in_app",
        send_email: bool = False,
    ) -> Notification:
        n = Notification(
            user_id=uuid.UUID(user_id),
            type=type_,
            channel=channel,
            title=title,
            body=body,
            link=link,
            sent_at=datetime.now(timezone.utc) if channel != "in_app" else None,
        )
        self.db.add(n)
        self.db.flush()

        if send_email and settings.RESEND_API_KEY:
            self._send_email(user_id, title, body)
        return n

    def _send_email(self, user_id: str, title: str, body: str) -> None:
        """Best-effort transactional email via Resend — fire-and-forget.

        The HTTP call runs on a worker thread so request handlers never wait
        on the email provider (a 10s Resend stall must not slow the API).
        """
        from app.models.user import User

        user = self.db.get(User, uuid.UUID(user_id))
        if not user:
            return
        payload = {
            "from": "AgriSphere AI <alerts@agrisphere.ai>",
            "to": [user.email],
            "subject": title,
            "html": f"<h2>{title}</h2><p>{body}</p><p>— AgriSphere AI</p>",
        }
        headers = {"Authorization": f"Bearer {settings.RESEND_API_KEY}"}
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None
        if loop is not None:
            _bg_tasks.add(asyncio.create_task(_post_email(headers, payload)))
        else:
            # No running loop (sync scheduler context) — quick blocking call.
            try:
                httpx.post("https://api.resend.com/emails", headers=headers, json=payload, timeout=10)
            except Exception as e:
                logger.warning("Email send failed: %s", e)

    def list_for_user(self, user_id: str, unread_only: bool = False, limit: int = 50) -> list[Notification]:
        q = self.db.query(Notification).filter(Notification.user_id == uuid.UUID(user_id))
        if unread_only:
            q = q.filter(Notification.is_read.is_(False))
        return q.order_by(Notification.created_at.desc()).limit(limit).all()

    def mark_read(self, user_id: str, ids: list[str]) -> int:
        return (
            self.db.query(Notification)
            .filter(
                Notification.user_id == uuid.UUID(user_id),
                Notification.id.in_([uuid.UUID(i) for i in ids]),
            )
            .update({"is_read": True}, synchronize_session=False)
        )

    def unread_count(self, user_id: str) -> int:
        return (
            self.db.query(Notification)
            .filter(Notification.user_id == uuid.UUID(user_id), Notification.is_read.is_(False))
            .count()
        )


# Strong references so fire-and-forget tasks are not garbage-collected mid-send.
_bg_tasks: set[asyncio.Task] = set()


async def _post_email(headers: dict, payload: dict) -> None:
    try:
        await asyncio.to_thread(
            httpx.post, "https://api.resend.com/emails", headers=headers, json=payload, timeout=10
        )
    except Exception as e:
        logger.warning("Email send failed: %s", e)
