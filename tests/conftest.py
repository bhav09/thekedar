"""Shared pytest fixtures."""

from __future__ import annotations

import os

import pytest
from thekedar_orchestrator.services import OrchestratorServices
from thekedar_shared.auth import create_access_token
from thekedar_shared.db import init_db
from thekedar_shared.schemas import Channel, MessageEvent
from thekedar_shared.settings import Settings, get_settings

os.environ.setdefault("THEKEDAR_ALLOW_DEFAULT_SEED", "true")
os.environ.setdefault("THEKEDAR_DEMO_MODE", "true")
os.environ.setdefault("THEKEDAR_ENVIRONMENT", "local")
os.environ.setdefault("THEKEDAR_LOCAL_IDE", "1")
os.environ.setdefault("THEKEDAR_LLM_PROVIDER", "mock")
_repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
os.environ.setdefault("THEKEDAR_LOCAL_REPO_PATH", _repo_root)
get_settings.cache_clear()


@pytest.fixture
def test_settings() -> Settings:
    return Settings(
        THEKEDAR_ENVIRONMENT="local",
        THEKEDAR_DEMO_MODE=True,
        THEKEDAR_DATABASE_URL="sqlite:///:memory:",
        THEKEDAR_DASHBOARD_URL="http://localhost:8081",
    )


@pytest.fixture
def session_factory(test_settings: Settings):
    return init_db(test_settings.database_url)


@pytest.fixture
def orchestrator_services(test_settings: Settings, session_factory):
    services = OrchestratorServices(test_settings, session_factory)
    services.seed()
    return services


@pytest.fixture
def auth_token(test_settings: Settings) -> str:
    return create_access_token(test_settings, tenant_id="default")


@pytest.fixture
def auth_headers(auth_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {auth_token}"}


@pytest.fixture
def other_tenant_token(test_settings: Settings) -> str:
    return create_access_token(test_settings, tenant_id="other")


@pytest.fixture
def sample_slack_message() -> MessageEvent:
    return MessageEvent(
        channel=Channel.SLACK,
        message_id="m1",
        thread_id="C123",
        user_id="U123",
        tenant_id="T001",
        text="@Architect list open issues",
        mentioned_agents=["Architect"],
        idempotency_key="slack:m1",
    )


@pytest.fixture
def sample_coder_message() -> MessageEvent:
    return MessageEvent(
        channel=Channel.SLACK,
        message_id="m2",
        thread_id="C123",
        user_id="U123",
        tenant_id="T001",
        text="@Coder fix THE-42 login bug",
        mentioned_agents=["Coder"],
        idempotency_key="slack:m2",
    )
