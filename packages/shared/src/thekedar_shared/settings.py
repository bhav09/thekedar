"""Application settings — single source for env config (no hardcoded secrets)."""

from functools import lru_cache

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    environment: str = Field(default="local", alias="THEKEDAR_ENVIRONMENT")
    log_level: str = Field(default="INFO", alias="THEKEDAR_LOG_LEVEL")
    demo_mode: bool = Field(default=False, alias="THEKEDAR_DEMO_MODE")

    # Service identity
    service_name: str = Field(default="thekedar", alias="THEKEDAR_SERVICE_NAME")

    # Redis (idempotency, rate limits)
    redis_url: str = Field(default="redis://localhost:6379/0", alias="THEKEDAR_REDIS_URL")

    # PostgreSQL
    database_url: str = Field(
        default="postgresql://thekedar:thekedar@localhost:5432/thekedar",
        alias="THEKEDAR_DATABASE_URL",
    )

    # Pub/Sub — use emulator locally
    pubsub_project_id: str | None = Field(default=None, alias="THEKEDAR_PUBSUB_PROJECT_ID")
    pubsub_emulator_host: str | None = Field(default=None, alias="PUBSUB_EMULATOR_HOST")
    inbound_topic: str = Field(
        default="thekedar.inbound.messages",
        alias="THEKEDAR_INBOUND_TOPIC",
    )
    inbound_subscription: str = Field(
        default="thekedar.inbound.messages-worker",
        alias="THEKEDAR_INBOUND_SUBSCRIPTION",
    )

    # Outbound messaging
    slack_bot_token: SecretStr | None = Field(default=None, alias="SLACK_BOT_TOKEN")
    whatsapp_access_token: SecretStr | None = Field(default=None, alias="WHATSAPP_ACCESS_TOKEN")
    whatsapp_phone_number_id: str | None = Field(default=None, alias="WHATSAPP_PHONE_NUMBER_ID")

    # Webhook verification
    slack_signing_secret: str | None = Field(default=None, alias="SLACK_SIGNING_SECRET")
    whatsapp_app_secret: str | None = Field(default=None, alias="WHATSAPP_APP_SECRET")
    whatsapp_verify_token: str | None = Field(default=None, alias="WHATSAPP_VERIFY_TOKEN")
    require_webhook_signature: bool = Field(
        default=False, alias="THEKEDAR_REQUIRE_WEBHOOK_SIGNATURE"
    )
    webhook_rate_limit_rps: int = Field(default=100, alias="THEKEDAR_WEBHOOK_RATE_LIMIT_RPS")
    max_request_body_bytes: int = Field(default=262144, alias="THEKEDAR_MAX_REQUEST_BODY_BYTES")

    # MCP gateway
    bifrost_url: str = Field(default="http://localhost:8090", alias="THEKEDAR_BIFROST_URL")
    github_token: SecretStr | None = Field(default=None, alias="GITHUB_TOKEN")
    mcp_registry_path: str = Field(
        default="config/mcp-servers.yaml",
        alias="THEKEDAR_MCP_REGISTRY_PATH",
    )

    # Dashboard / auth
    dashboard_url: str = Field(default="http://localhost:8081", alias="THEKEDAR_DASHBOARD_URL")
    jwt_secret: SecretStr | None = Field(default=None, alias="THEKEDAR_JWT_SECRET")
    default_tenant_id: str = Field(default="default", alias="THEKEDAR_DEFAULT_TENANT_ID")

    # Workspace config file (OSS onboarding)
    workspace_config_path: str = Field(
        default="config/workspace.yaml",
        alias="THEKEDAR_WORKSPACE_CONFIG_PATH",
    )

    # Jira / Atlassian
    jira_base_url: str | None = Field(default=None, alias="JIRA_BASE_URL")
    jira_email: str | None = Field(default=None, alias="JIRA_EMAIL")
    jira_api_token: SecretStr | None = Field(default=None, alias="JIRA_API_TOKEN")

    # GCP / Workstations
    gcp_project_id: str | None = Field(default=None, alias="GCP_PROJECT_ID")
    gcp_region: str = Field(default="us-central1", alias="GCP_REGION")

    # GitHub webhooks
    github_webhook_secret: SecretStr | None = Field(default=None, alias="GITHUB_WEBHOOK_SECRET")

    # Service URLs (doctor / bootstrap)
    webhook_ingress_url: str = Field(
        default="http://localhost:8080", alias="THEKEDAR_WEBHOOK_INGRESS_URL"
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
