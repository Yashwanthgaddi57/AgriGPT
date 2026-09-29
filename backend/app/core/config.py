"""Application configuration loaded from environment variables."""
import logging
from functools import lru_cache
from typing import Any

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # App
    PROJECT_NAME: str = "AgriGPT"
    ENVIRONMENT: str = "development"
    API_V1_PREFIX: str = "/api/v1"
    BACKEND_CORS_ORIGINS: list[str] = ["http://localhost:3000"]
    # Base URL of the frontend, used for password-reset email redirects.
    FRONTEND_APP_URL: str = "http://localhost:3000"
    # Require the 6-digit email code before an account can sign in. Defaults
    # to on in production; set REQUIRE_EMAIL_VERIFICATION=true in development
    # to exercise the real flow (needs Supabase SMTP configured).
    REQUIRE_EMAIL_VERIFICATION: bool = False

    # Supabase
    SUPABASE_URL: str = "https://YOUR_PROJECT_REF.supabase.co"
    SUPABASE_SERVICE_KEY: str = "your-service-role-key"
    SUPABASE_ANON_KEY: str = "your-anon-key"
    SUPABASE_JWT_SECRET: str = "your-supabase-jwt-secret"
    SUPABASE_DB_URL: str = "postgresql+psycopg://postgres:postgres@localhost:5432/agrigpt"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # AI
    # AI_PROVIDER: "anthropic" (direct API, sk-ant- key) or "bedrock" (AWS Bedrock API key)
    AI_PROVIDER: str = "anthropic"
    ANTHROPIC_API_KEY: str = ""
    ANTHROPIC_MODEL: str = "claude-sonnet-4-20250514"
    BEDROCK_API_KEY: str = ""
    BEDROCK_REGION: str = "us-east-1"
    BEDROCK_MODEL_ID: str = "us.anthropic.claude-sonnet-4-20250514-v1:0"
    AI_MAX_TOKENS: int = 4096
    AI_TEMPERATURE: float = 0.2

    # Weather
    OPENWEATHER_API_KEY: str = ""

    # Market data (data.gov.in Agmarknet feed; empty -> synthetic baseline fallback)
    DATA_GOV_API_KEY: str = ""

    # Email
    RESEND_API_KEY: str = ""
    # Brevo is the preferred provider: 300 emails/day free forever, and one
    # verified *sender email* is enough — no domain DNS required. Create the
    # key at app.brevo.com → SMTP & API → API keys, verify the sender under
    # Senders, then set BREVO_API_KEY + EMAIL_FROM.
    BREVO_API_KEY: str = ""
    # Sender for transactional mail. With Brevo this must be a sender verified
    # in the Brevo dashboard; with Resend it must be a verified domain.
    EMAIL_FROM: str = "AgriGPT AI <alerts@agrigpt.app>"
    # App-issued signup codes (see app/core/email_verification.py). These are
    # generated and emailed by this backend rather than by Supabase, so the
    # project's Supabase mailer template and its 2-emails/hour cap are not
    # involved at all.
    EMAIL_VERIFICATION_TTL_MINUTES: int = 10
    EMAIL_VERIFICATION_MAX_ATTEMPTS: int = 5
    EMAIL_VERIFICATION_RESEND_COOLDOWN_SECONDS: int = 60
    # App-issued password reset (same design as signup codes: single-use,
    # expiring, stored hashed — delivered as a signed link).
    PASSWORD_RESET_TTL_MINUTES: int = 30
    # Pepper for hashing reset tokens. Falls back to SUPABASE_JWT_SECRET when
    # empty; set a dedicated random value in production.
    RESET_TOKEN_SECRET: str = ""

    # Payments (Razorpay) — test-mode keys work with no KYC; live keys only
    # after Razorpay activation. When both are empty the checkout endpoint
    # returns 501 and the UI shows "payments coming soon" as before.
    RAZORPAY_KEY_ID: str = ""
    RAZORPAY_KEY_SECRET: str = ""
    # Webhook secret from the Razorpay dashboard (optional hardening layer;
    # checkout verification itself is signature-based and always required).
    RAZORPAY_WEBHOOK_SECRET: str = ""

    # Observability (Sentry, web push) — optional, off when empty
    SENTRY_DSN: str = ""
    SENTRY_TRACES_SAMPLE_RATE: float = 0.1
    VAPID_PUBLIC_KEY: str = ""
    VAPID_PRIVATE_KEY: str = ""
    VAPID_SUBJECT: str = "mailto:support@agrigpt.app"

    # Scheduler
    SCHEDULER_ENABLED: bool = True
    SCHEDULER_INTERVAL_MINUTES: int = 30

    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors(cls, v: Any) -> list[str]:
        if isinstance(v, str):
            v = v.strip()
            if v.startswith("["):
                import json

                return json.loads(v)
            return [o.strip() for o in v.split(",") if o.strip()]
        return v

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"

    @property
    def email_verification_required(self) -> bool:
        """True when a signup must be confirmed with an emailed code first."""
        return self.REQUIRE_EMAIL_VERIFICATION or self.is_production

    @property
    def email_delivery_configured(self) -> bool:
        """True when any provider key is present, i.e. mail can actually be sent."""
        return bool(self.BREVO_API_KEY.strip() or self.RESEND_API_KEY.strip())

    @property
    def payments_enabled(self) -> bool:
        """True when Razorpay keys are present, i.e. checkout can create orders."""
        return bool(self.RAZORPAY_KEY_ID.strip() and self.RAZORPAY_KEY_SECRET.strip())

    def assert_production_ready(self) -> None:
        """Fail loudly on misconfigurations that are silent security/data risks.

        Called at startup so a bad deploy dies immediately instead of serving
        production traffic with a local-auth fallback or a throwaway database.
        """
        errors: list[str] = []
        if "YOUR_PROJECT_REF" in self.SUPABASE_URL or not self.SUPABASE_URL:
            errors.append(
                "SUPABASE_URL is a placeholder — local-auth fallback would accept "
                "self-signed JWTs from anyone."
            )
        if self.SUPABASE_DB_URL.startswith("sqlite"):
            errors.append("SUPABASE_DB_URL is SQLite — local file storage is not acceptable in production.")

        # AI provider: an Anthropic key is only required when AI_PROVIDER is
        # "anthropic". Bedrock uses its own API key/region/model id.
        provider = (self.AI_PROVIDER or "").lower()
        if provider == "anthropic" and (
            not self.ANTHROPIC_API_KEY or self.ANTHROPIC_API_KEY.startswith("sk-ant-test")
        ):
            errors.append("ANTHROPIC_API_KEY is missing or a test key — AI agents would return fallbacks only.")
        if provider == "bedrock" and not self.BEDROCK_API_KEY:
            errors.append("BEDROCK_API_KEY is missing — AI agents would return fallbacks only.")

        # JWT verification: asymmetric (JWKS/ES256) verification is used when no
        # shared secret is configured, so a missing SUPABASE_JWT_SECRET is fine.
        # Only flag the placeholder case (someone pasted the example string).
        if self.SUPABASE_JWT_SECRET == "your-supabase-jwt-secret":
            errors.append("SUPABASE_JWT_SECRET is still the example placeholder.")

        if self.ENVIRONMENT == "production" and self.BACKEND_CORS_ORIGINS == ["http://localhost:3000"]:
            # Warn only: CORS misconfig blocks browsers but is not a data-risk,
            # and the frontend domain may legitimately not exist yet at deploy time.
            logging.getLogger(__name__).warning(
                "BACKEND_CORS_ORIGINS is still the local default — add your real "
                "frontend domain before launching."
            )
        if errors:
            raise RuntimeError(
                "Production readiness check failed:\n"
                + "\n".join(f"  - {e}" for e in errors)
                + "\nFix these before deploying with ENVIRONMENT=production."
            )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
