"""Startup validation for security-sensitive settings."""

from thekedar_shared.settings import Settings


def validate_settings(settings: Settings) -> None:
    if settings.environment in ("staging", "prod"):
        if settings.jwt_secret is None:
            raise RuntimeError("THEKEDAR_JWT_SECRET must be set in staging/prod")
        if not settings.require_webhook_signature:
            raise RuntimeError(
                "THEKEDAR_REQUIRE_WEBHOOK_SIGNATURE must be true in staging/prod"
            )
