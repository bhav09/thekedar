"""Fail-closed production config tests."""

from __future__ import annotations

import pytest
from thekedar_shared.exceptions import ConfigurationError
from thekedar_shared.prod_validation import allows_demo_mocks, validate_production_settings
from thekedar_shared.settings import Settings


def test_staging_rejects_demo_mode() -> None:
    with pytest.raises(ConfigurationError):
        Settings(THEKEDAR_ENVIRONMENT="staging", THEKEDAR_DEMO_MODE=True)


def test_staging_rejects_mock_llm() -> None:
    with pytest.raises(ConfigurationError):
        Settings(THEKEDAR_ENVIRONMENT="prod", THEKEDAR_DEMO_MODE=False, THEKEDAR_LLM_PROVIDER="mock")


def test_allows_demo_mocks_local_only() -> None:
    settings = Settings(THEKEDAR_ENVIRONMENT="local", THEKEDAR_DEMO_MODE=True)
    assert allows_demo_mocks(settings) is True

    settings_prod = Settings(
        THEKEDAR_ENVIRONMENT="prod",
        THEKEDAR_DEMO_MODE=False,
        THEKEDAR_LLM_PROVIDER="gemini",
    )
    assert allows_demo_mocks(settings_prod) is False


def test_validate_production_strict_integrations() -> None:
    settings = Settings(
        THEKEDAR_ENVIRONMENT="staging",
        THEKEDAR_DEMO_MODE=False,
        THEKEDAR_LLM_PROVIDER="gemini",
        THEKEDAR_STRICT_INTEGRATIONS=True,
    )
    errors = validate_production_settings(settings)
    assert any("GITHUB_TOKEN" in e for e in errors)
