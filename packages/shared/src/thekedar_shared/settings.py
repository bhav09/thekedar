"""Application settings — single source for env config (no hardcoded secrets)."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    environment: str = Field(default="local", alias="THEKEDAR_ENVIRONMENT")
    log_level: str = Field(default="INFO", alias="THEKEDAR_LOG_LEVEL")

    # Service identity
    service_name: str = Field(default="thekedar", alias="THEKEDAR_SERVICE_NAME")

    # Redis (idempotency, rate limits) — wired in M2
    redis_url: str = Field(default="redis://localhost:6379/0", alias="THEKEDAR_REDIS_URL")

    # PostgreSQL — wired in M2
    database_url: str = Field(
        default="postgresql://thekedar:thekedar@localhost:5432/thekedar",
        alias="THEKEDAR_DATABASE_URL",
    )

    # Pub/Sub — use emulator locally
    pubsub_project_id: str | None = Field(default=None, alias="THEKEDAR_PUBSUB_PROJECT_ID")
    pubsub_emulator_host: str | None = Field(
        default=None, alias="PUBSUB_EMULATOR_HOST"
    )
    inbound_topic: str = Field(
        default="thekedar.inbound.messages",
        alias="THEKEDAR_INBOUND_TOPIC",
    )

    # Webhook verification (M2)
    slack_signing_secret: str | None = Field(default=None, alias="SLACK_SIGNING_SECRET")
    whatsapp_app_secret: str | None = Field(default=None, alias="WHATSAPP_APP_SECRET")
    whatsapp_verify_token: str | None = Field(default=None, alias="WHATSAPP_VERIFY_TOKEN")


@lru_cache
def get_settings() -> Settings:
    return Settings()
