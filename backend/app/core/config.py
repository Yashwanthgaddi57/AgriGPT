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

    # Supabase
    SUPABASE_URL: str = "https://YOUR_PROJECT_REF.supabase.co"
    SUPABASE_SERVICE_KEY: str = "your-service-role-key"
    SUPABASE_ANON_KEY: str = "your-anon-key"
    SUPABASE_JWT_SECRET: str = "your-supabase-jwt-secret"
    SUPABASE_DB_URL: str = "postgresql+psycopg://postgres:postgres@localhost:5432/agrisphere"

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
