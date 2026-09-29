"""Transactional email delivery.

Provider order:
  1. Brevo  (BREVO_API_KEY) — 300 emails/day free, and a single verified
     *sender email* is enough (no domain DNS required), so codes reach any
     farmer's inbox.
  2. Resend (RESEND_API_KEY) — used when only a Resend key is configured.
     Note Resend's test sender (onboarding@resend.dev) delivers solely to the
     account owner's own address; any other recipient needs a verified domain.

Both are plain REST calls via httpx — no SDKs.
"""
import logging
import os

import httpx

from app.core.config import settings

logger = logging.getLogger("app.services.email")

BREVO_ENDPOINT = "https://api.brevo.com/v3/smtp/email"
RESEND_ENDPOINT = "https://api.resend.com/emails"


class EmailDeliveryError(RuntimeError):
    """Raised when every configured provider rejected the send."""


def _brand_shell(title: str, body_html: str) -> str:
    """Shared professional template: green header bar, card body, plain footer."""
    return f"""\
<!doctype html>
<html>
  <body style="margin:0;padding:0;background:#f3f4f6;font-family:system-ui,-apple-system,'Segoe UI',Roboto,Arial,sans-serif;">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f3f4f6;padding:24px 12px;">
      <tr><td align="center">
        <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:520px;background:#ffffff;border-radius:12px;overflow:hidden;border:1px solid #e5e7eb;">
          <tr><td style="background:#15803d;padding:18px 28px;">
            <span style="color:#ffffff;font-size:18px;font-weight:700;letter-spacing:.3px;">🌱 AgriGPT</span>
            <span style="color:#bbf7d0;font-size:12px;padding-left:8px;">AI-Powered Farm Intelligence</span>
          </td></tr>
          <tr><td style="padding:28px;">
            <h2 style="margin:0 0 12px;font-size:19px;color:#111827;">{title}</h2>
            {body_html}
          </td></tr>
          <tr><td style="padding:16px 28px;background:#f9fafb;border-top:1px solid #e5e7eb;">
            <p style="margin:0;font-size:12px;color:#6b7280;line-height:1.5;">
              You received this email because a request was made at AgriGPT.
              If this wasn't you, ignore this message — nothing will change.<br>
              AgriGPT · support@agrigpt.app
            </p>
          </td></tr>
        </table>
      </td></tr>
    </table>
  </body>
</html>"""


def render_verification_code_html(code: str, ttl_minutes: int) -> str:
    body = f"""\
<p style="margin:0 0 16px;color:#374151;font-size:14px;line-height:1.6;">
  Welcome to AgriGPT! Use this code to verify your email and activate your account:
</p>
<p style="margin:0 0 18px;">
  <span style="font-size:32px;letter-spacing:12px;font-weight:700;color:#111827;background:#f0fdf4;border:1px solid #bbf7d0;border-radius:8px;padding:12px 18px;display:inline-block;">{code}</span>
</p>
<p style="margin:0;color:#6b7280;font-size:13px;line-height:1.6;">
  This code expires in {ttl_minutes} minutes and can be used only once.
  You can request a new one from the verification screen.
</p>"""
    return _brand_shell("Confirm your email", body)


def render_password_reset_html(reset_url: str, ttl_minutes: int) -> str:
    body = f"""\
<p style="margin:0 0 16px;color:#374151;font-size:14px;line-height:1.6;">
  We received a request to reset the password for your AgriGPT account.
  Click the button below to choose a new one:
</p>
<p style="margin:0 0 18px;">
  <a href="{reset_url}"
     style="display:inline-block;background:#15803d;color:#ffffff;text-decoration:none;
            font-weight:600;font-size:14px;border-radius:8px;padding:12px 24px;">
     Reset my password
  </a>
</p>
<p style="margin:0 0 6px;color:#6b7280;font-size:13px;line-height:1.6;">
  Or paste this link into your browser:<br>
  <a href="{reset_url}" style="color:#15803d;word-break:break-all;">{reset_url}</a>
</p>
<p style="margin:12px 0 0;color:#6b7280;font-size:13px;line-height:1.6;">
  This link expires in {ttl_minutes} minutes and can be used only once.<br>
  Didn't request a reset? You can safely ignore this email — your password stays unchanged.
</p>"""
    return _brand_shell("Reset your password", body)


def _from_header() -> str:
    # A display name on the sender address (and on Resend it must match the
    # configured sender exactly), so keep whatever the operator set.
    return settings.EMAIL_FROM


async def _send_brevo(to: str, subject: str, html: str) -> bool:
    key = (settings.BREVO_API_KEY or "").strip()
    if not key:
        return False
    name, _, addr = _from_header().partition("<")
    addr = addr.rstrip(">").strip() or name
    resp = await httpx.AsyncClient(timeout=20).post(
        BREVO_ENDPOINT,
        headers={"api-key": key, "Content-Type": "application/json"},
        json={
            "sender": {"name": name.strip() or "AgriGPT", "email": addr},
            "to": [{"email": to}],
            "subject": subject,
            "htmlContent": html,
        },
    )
    if resp.status_code >= 400:
        logger.warning("Brevo rejected mail to %s: HTTP %s %s", to, resp.status_code, resp.text[:300])
        return False
    return True


async def _send_resend(to: str, subject: str, html: str) -> bool:
    key = (settings.RESEND_API_KEY or "").strip()
    if not key:
        return False
    resp = await httpx.AsyncClient(timeout=20).post(
        RESEND_ENDPOINT,
        headers={"Authorization": f"Bearer {key}"},
        json={"from": _from_header(), "to": [to], "subject": subject, "html": html},
    )
    if resp.status_code >= 400:
        logger.warning("Resend rejected mail to %s: HTTP %s %s", to, resp.status_code, resp.text[:300])
        return False
    return True


async def send_email(to: str, subject: str, html: str) -> bool:
    """Send one HTML email through the first configured provider."""
    if settings.BREVO_API_KEY.strip():
        if await _send_brevo(to, subject, html):
            return True
    if settings.RESEND_API_KEY.strip():
        if await _send_resend(to, subject, html):
            return True
    logger.warning(
        "Email not delivered to %s (%s): no configured provider accepted it.",
        to,
        subject,
    )
    return False


async def send_verification_code_email(to: str, code: str) -> bool:
    return await send_email(
        to,
        f"{code} is your AgriGPT verification code",
        render_verification_code_html(code, settings.EMAIL_VERIFICATION_TTL_MINUTES),
    )


async def send_password_reset_email(to: str, reset_url: str) -> bool:
    return await send_email(
        to,
        "Reset your AgriGPT password",
        render_password_reset_html(reset_url, settings.PASSWORD_RESET_TTL_MINUTES),
    )
