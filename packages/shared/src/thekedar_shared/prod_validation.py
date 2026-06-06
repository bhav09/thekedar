"""Production/staging configuration validation."""

from __future__ import annotations

from thekedar_shared.exceptions import ConfigurationError
from thekedar_shared.settings import Settings


def validate_production_settings(settings: Settings) -> list[str]:
    """Return list of validation errors (empty if OK)."""
    errors: list[str] = []
    if settings.environment not in ("staging", "prod"):
        return errors

    if settings.demo_mode:
        errors.append("THEKEDAR_DEMO_MODE must be false in staging/prod")

    if settings.llm_provider == "mock":
        errors.append("THEKEDAR_LLM_PROVIDER=mock is not allowed in staging/prod")

    if not settings.jwt_secret:
        errors.append("THEKEDAR_JWT_SECRET is required in staging/prod")

    if settings.strict_integrations:
        if not settings.github_token:
            errors.append("GITHUB_TOKEN is required when strict integrations enabled")
        if not settings.slack_bot_token and not settings.whatsapp_access_token:
            errors.append("SLACK_BOT_TOKEN or WHATSAPP_ACCESS_TOKEN required")

    return errors


def assert_production_settings(settings: Settings) -> None:
    errors = validate_production_settings(settings)
    if errors:
        raise ConfigurationError("; ".join(errors))


def allows_demo_mocks(settings: Settings) -> bool:
    """True when silent mock integrations are permitted."""
    if settings.environment in ("staging", "prod"):
        return False
    return settings.demo_mode
