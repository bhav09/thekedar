"""Additional M8 integration and resilience tests."""

from __future__ import annotations

import pytest
from thekedar_orchestrator.integrations.github_client import GitHubClient
from thekedar_orchestrator.integrations.jira_client import JiraClient
from thekedar_orchestrator.llm.router import LLMRouter
from thekedar_resilience.health_registry import ProviderHealthRegistry
from thekedar_shared.exceptions import IntegrationError
from thekedar_shared.observability import StructuredFormatter, bind_log_context, clear_log_context
from thekedar_shared.prod_validation import assert_production_settings, validate_production_settings
from thekedar_shared.settings import Settings


def test_github_mock_when_demo(session_factory) -> None:
    settings = Settings(THEKEDAR_ENVIRONMENT="local", THEKEDAR_DEMO_MODE=True)
    client = GitHubClient(settings)
    assert client.configured is False


@pytest.mark.asyncio
async def test_github_fail_closed_without_token() -> None:
    settings = Settings(
        THEKEDAR_ENVIRONMENT="local",
        THEKEDAR_DEMO_MODE=False,
        GITHUB_TOKEN=None,
    )
    client = GitHubClient(settings)
    with pytest.raises(IntegrationError):
        await client.create_pull_request("org/repo", "title", "branch", "body")


@pytest.mark.asyncio
async def test_jira_fail_closed_without_creds() -> None:
    settings = Settings(THEKEDAR_ENVIRONMENT="local", THEKEDAR_DEMO_MODE=False)
    client = JiraClient(settings)
    with pytest.raises(IntegrationError):
        await client.search("project = THE")


@pytest.mark.asyncio
async def test_llm_router_returns_none_in_mock_local() -> None:
    settings = Settings(THEKEDAR_ENVIRONMENT="local", THEKEDAR_LLM_PROVIDER="mock")
    router = LLMRouter(settings)
    result = await router.complete("summarize impact")
    assert result is None


@pytest.mark.asyncio
async def test_provider_health_registry_opens_circuit() -> None:
    settings = Settings(THEKEDAR_CIRCUIT_FAILURE_THRESHOLD=2)
    registry = ProviderHealthRegistry(settings)
    await registry.record_failure("slack_api")
    await registry.record_failure("slack_api")
    snap = registry.snapshot()
    assert snap["slack_api"] == "open"


def test_structured_log_formatter_includes_context() -> None:
    bind_log_context(tenant_id="t1", run_id="r1")
    fmt = StructuredFormatter()
    import logging

    record = logging.LogRecord("n", logging.INFO, "", 0, "hello", (), None)
    payload = fmt.format(record)
    assert "t1" in payload
    assert "r1" in payload
    clear_log_context()


def test_validate_production_requires_jwt() -> None:
    settings = Settings(
        THEKEDAR_ENVIRONMENT="staging",
        THEKEDAR_DEMO_MODE=False,
        THEKEDAR_LLM_PROVIDER="gemini",
    )
    errors = validate_production_settings(settings)
    assert any("JWT" in e for e in errors)


def test_assert_production_raises() -> None:
    settings = Settings(
        THEKEDAR_ENVIRONMENT="staging",
        THEKEDAR_DEMO_MODE=False,
        THEKEDAR_LLM_PROVIDER="gemini",
    )
    with pytest.raises(Exception):
        assert_production_settings(settings)


def test_settings_m8_defaults() -> None:
    settings = Settings(THEKEDAR_ALLOW_DEFAULT_SEED=False)
    assert settings.provider_retry_max == 3
    assert settings.outbox_max_attempts == 8
    assert settings.allow_default_seed is False


def test_workspace_seed_gated_without_flag(session_factory, monkeypatch) -> None:
    from thekedar_shared.db import Workspace
    from thekedar_shared.workspace import WorkspaceService

    monkeypatch.setenv("THEKEDAR_ALLOW_DEFAULT_SEED", "false")
    monkeypatch.setenv("THEKEDAR_WORKSPACE_CONFIG_PATH", "/nonexistent/workspace.yaml")
    from thekedar_shared import settings as settings_mod

    settings_mod.get_settings.cache_clear()
    service = WorkspaceService(session_factory)
    service.seed_defaults()
    session = session_factory()
    count = session.query(Workspace).count()
    session.close()
    settings_mod.get_settings.cache_clear()
    assert count == 0


@pytest.mark.asyncio
async def test_redis_bus_publish_consume() -> None:
    import fakeredis.aioredis

    from thekedar_shared.bus import RedisMessageBus

    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    bus = RedisMessageBus(redis)
    await bus.publish_inbound({"hello": "world"})
    msg = await bus.consume_inbound(timeout=1)
    assert msg == {"hello": "world"}


def test_run_step_unique_per_attempt(session_factory) -> None:
    from thekedar_shared.db import RunStep
    from thekedar_shared.run_ledger import RunLedger

    ledger = RunLedger(session_factory)
    s1 = ledger.begin_step("r1", "t", "code")
    ledger.fail_step(s1, error_class="transient", error_message="503", pending_retry=True)
    s2 = ledger.begin_step("r1", "t", "code")
    session = session_factory()
    rows = session.query(RunStep).filter_by(run_id="r1", step="code").all()
    session.close()
    assert len(rows) == 2


def test_dlq_message_persisted(session_factory) -> None:
    from thekedar_shared.db import DlqMessage

    session = session_factory()
    session.add(DlqMessage(source="inbound", payload_json='{"a":1}', status="pending"))
    session.commit()
    count = session.query(DlqMessage).count()
    session.close()
    assert count == 1


def test_outbound_notification_failed_status(session_factory) -> None:
    from thekedar_shared.db import OutboundNotification

    session = session_factory()
    session.add(
        OutboundNotification(
            tenant_id="t",
            channel="slack",
            destination="C1",
            body='{"text":"hi"}',
            status="failed",
            retry_count=8,
        )
    )
    session.commit()
    row = session.query(OutboundNotification).first()
    session.close()
    assert row is not None
    assert row.status == "failed"


def test_classify_connect_error() -> None:
    import httpx
    from thekedar_resilience.errors import ErrorClass, classify_error

    assert classify_error(httpx.ConnectError("down")) == ErrorClass.TRANSIENT


def test_circuit_success_resets() -> None:
    from thekedar_resilience.circuit_breaker import CircuitBreaker

    cb = CircuitBreaker(name="x", failure_threshold=2)
    cb.record_failure()
    cb.record_success()
    cb.record_failure()
    assert not cb.is_open


def test_error_class_enum_values() -> None:
    from thekedar_resilience.errors import ErrorClass

    assert ErrorClass.TRANSIENT.value == "transient"


def test_configuration_error_type() -> None:
    from thekedar_shared.exceptions import ConfigurationError, IntegrationError

    err = IntegrationError("slack", "missing token")
    assert err.provider == "slack"
    assert isinstance(ConfigurationError("bad"), Exception)


@pytest.mark.asyncio
async def test_idempotency_duplicate_detection() -> None:
    import fakeredis.aioredis
    from thekedar_shared.idempotency import IdempotencyStore

    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    store = IdempotencyStore(redis)
    assert await store.claim("dup-key") is True
    assert await store.is_claimed("dup-key") is True
    assert await store.claim("dup-key") is False


def test_plan_amendment_requires_files() -> None:
    from thekedar_context.schemas import ExecutionPlan
    from thekedar_orchestrator.plan import PlanGenerator
    from thekedar_shared.exceptions import IntegrationError

    plan = ExecutionPlan(
        summary="s",
        files_to_touch=[],
        branch_name="b",
        test_strategy="t",
    )
    with pytest.raises(IntegrationError):
        PlanGenerator().apply_amendment(plan, "no file paths here")


def test_llm_provider_chain_parsing() -> None:
    settings = Settings(
        THEKEDAR_LLM_PRIMARY="gemini",
        THEKEDAR_LLM_FALLBACK="openai,anthropic",
        THEKEDAR_LLM_PROVIDER="gemini",
        THEKEDAR_ENVIRONMENT="local",
    )
    router = LLMRouter(settings)
    providers = router._providers()
    assert providers[0] == "gemini"
    assert "openai" in providers


def test_strict_integrations_flag() -> None:
    settings = Settings(THEKEDAR_STRICT_INTEGRATIONS=True, THEKEDAR_ENVIRONMENT="local")
    assert settings.strict_integrations is True
