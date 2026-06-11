"""Application settings — single source for env config (no hardcoded secrets)."""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from thekedar_shared.exceptions import ConfigurationError


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

    # M7 — context, IDE execution, LLM
    local_ide_enabled: bool = Field(default=False, alias="THEKEDAR_LOCAL_IDE")
    local_repo_path: str | None = Field(default=None, alias="THEKEDAR_LOCAL_REPO_PATH")
    ide_adapter: str = Field(default="auto", alias="THEKEDAR_IDE_ADAPTER")
    llm_provider: str = Field(default="mock", alias="THEKEDAR_LLM_PROVIDER")
    context_reindex_hours: int = Field(default=24, alias="THEKEDAR_CONTEXT_REINDEX_HOURS")
    approval_ttl_hours: int = Field(default=72, alias="THEKEDAR_APPROVAL_TTL_HOURS")
    max_coding_iterations: int = Field(default=25, alias="THEKEDAR_MAX_CODING_ITERATIONS")

    # Antigravity & SDK integration
    antigravity_mode: str = Field(default="auto", alias="THEKEDAR_ANTIGRAVITY_MODE")
    antigravity_stream_events: bool = Field(default=False, alias="THEKEDAR_ANTIGRAVITY_STREAM_EVENTS")
    context_max_tokens_per_pack: int = Field(default=8000, alias="THEKEDAR_CONTEXT_MAX_TOKENS_PER_PACK")
    context_retval_max_results: int = Field(default=10, alias="THEKEDAR_CONTEXT_RETRIEVAL_MAX_RESULTS")
    github_mcp_enabled: bool = Field(default=True, alias="THEKEDAR_GITHUB_MCP_ENABLED")
    github_mcp_tool_allowlist: str = Field(
        default="get_issue,get_pull_request,get_file_contents",
        alias="THEKEDAR_GITHUB_MCP_TOOL_ALLOWLIST"
    )
    context_max_age_minutes: int = Field(default=1440, alias="THEKEDAR_CONTEXT_MAX_AGE_MINUTES")
    max_cost_per_run_usd: float = Field(default=10.0, alias="THEKEDAR_MAX_COST_PER_RUN_USD")
    max_tokens_per_run: int = Field(default=1000000, alias="THEKEDAR_MAX_TOKENS_PER_RUN")
    opt_in_db_sandbox: bool = Field(default=False, alias="THEKEDAR_OPT_IN_DB_SANDBOX")
    sandbox_db_url: str = Field(default="sqlite:///:memory:", alias="THEKEDAR_SANDBOX_DB_URL")

    # M5 — remote execution and GCP workstations configuration
    remote_executor: str = Field(default="local", alias="THEKEDAR_REMOTE_EXECUTOR")
    workstation_repo_root: str = Field(default="/home/user/repos", alias="THEKEDAR_WORKSTATION_REPO_ROOT")
    gcp_workstation_cluster_id: str | None = Field(default=None, alias="GCP_WORKSTATION_CLUSTER_ID")
    gcp_workstation_config_id: str | None = Field(default=None, alias="GCP_WORKSTATION_CONFIG_ID")
    workstation_ssh_user: str = Field(default="user", alias="THEKEDAR_WORKSTATION_SSH_USER")
    vscode_task_mode: str = Field(default="disabled", alias="THEKEDAR_VSCODE_TASK_MODE")
    vscode_task_timeout_s: int = Field(default=1800, alias="THEKEDAR_VSCODE_TASK_TIMEOUT_S")

    # GitHub webhooks
    github_webhook_secret: SecretStr | None = Field(default=None, alias="GITHUB_WEBHOOK_SECRET")

    # Service URLs (doctor / bootstrap)
    webhook_ingress_url: str = Field(
        default="http://localhost:8080", alias="THEKEDAR_WEBHOOK_INGRESS_URL"
    )

    # M8 — resilience and fail-closed prod
    llm_primary: str = Field(default="gemini", alias="THEKEDAR_LLM_PRIMARY")
    llm_fallback: str = Field(default="", alias="THEKEDAR_LLM_FALLBACK")
    provider_retry_max: int = Field(default=3, alias="THEKEDAR_PROVIDER_RETRY_MAX")
    circuit_failure_threshold: int = Field(
        default=5, alias="THEKEDAR_CIRCUIT_FAILURE_THRESHOLD"
    )
    circuit_open_seconds: int = Field(default=60, alias="THEKEDAR_CIRCUIT_OPEN_SECONDS")
    outbox_max_attempts: int = Field(default=8, alias="THEKEDAR_OUTBOX_MAX_ATTEMPTS")
    allow_default_seed: bool = Field(default=False, alias="THEKEDAR_ALLOW_DEFAULT_SEED")
    strict_integrations: bool = Field(default=False, alias="THEKEDAR_STRICT_INTEGRATIONS")
    mcp_fallback_direct_github: bool = Field(
        default=True, alias="THEKEDAR_MCP_FALLBACK_DIRECT_GITHUB"
    )
    validate_on_startup: bool = Field(default=False, alias="THEKEDAR_VALIDATE_ON_STARTUP")
    otel_enabled: bool = Field(default=False, alias="THEKEDAR_OTEL_ENABLED")
    otel_exporter_endpoint: str | None = Field(
        default=None, alias="OTEL_EXPORTER_OTLP_ENDPOINT"
    )

    @model_validator(mode="after")
    def _validate_staging_prod(self) -> Settings:
        if self.environment in ("staging", "prod"):
            if self.demo_mode:
                raise ConfigurationError("THEKEDAR_DEMO_MODE must be false in staging/prod")
            if self.llm_provider == "mock":
                raise ConfigurationError(
                    "THEKEDAR_LLM_PROVIDER=mock is not allowed in staging/prod"
                )
        return self


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    if settings.validate_on_startup and settings.environment in ("staging", "prod"):
        from thekedar_shared.prod_validation import assert_production_settings

        assert_production_settings(settings)
    return settings
