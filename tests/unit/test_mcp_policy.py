"""MCP policy engine tests."""

from pathlib import Path

import pytest
from thekedar_mcp_policy.engine import McpPolicyEngine
from thekedar_mcp_policy.loader import load_policy_config
from thekedar_mcp_policy.models import McpServerConfig, PolicyConfig


@pytest.fixture
def engine() -> McpPolicyEngine:
    config = PolicyConfig(
        servers=[
            McpServerConfig(
                name="github",
                image="ghcr.io/github/github-mcp-server:v1.1.2",
                toolsets=["repos", "issues"],
                allowed_tools=["list_repositories", "get_issue"],
            )
        ]
    )
    return McpPolicyEngine(config)


def test_blocks_globally_denied_tool(engine: McpPolicyEngine) -> None:
    decision = engine.evaluate_tool("github", "delete_repository", {})
    assert not decision.allowed
    assert "globally denied" in decision.reason


def test_blocks_unknown_server(engine: McpPolicyEngine) -> None:
    decision = engine.evaluate_tool("unknown", "list_repositories", {})
    assert not decision.allowed
    assert "Unknown MCP server" in decision.reason


def test_blocks_tool_not_in_allowlist(engine: McpPolicyEngine) -> None:
    decision = engine.evaluate_tool("github", "create_pull_request", {})
    assert not decision.allowed
    assert "allowlist" in decision.reason


def test_allows_allowlisted_tool(engine: McpPolicyEngine) -> None:
    decision = engine.evaluate_tool("github", "list_repositories", {})
    assert decision.allowed


def test_blocks_destructive_shell(engine: McpPolicyEngine) -> None:
    decision = engine.evaluate_shell("rm -rf /")
    assert not decision.allowed


def test_blocks_force_push(engine: McpPolicyEngine) -> None:
    decision = engine.evaluate_shell("git push origin main --force")
    assert not decision.allowed


def test_blocks_sensitive_path_in_args(engine: McpPolicyEngine) -> None:
    decision = engine.evaluate_tool("github", "read_file", {"path": "/app/.env"})
    assert not decision.allowed


def test_load_registry_from_repo() -> None:
    root = Path(__file__).resolve().parents[2]
    registry = root / "config" / "mcp-servers.yaml"
    config = load_policy_config(registry)
    assert any(s.name == "github" for s in config.servers)


def test_cli_registry_github_image() -> None:
    root = Path(__file__).resolve().parents[2]
    config = load_policy_config(root / "config" / "mcp-servers.yaml")
    github = next(s for s in config.servers if s.name == "github")
    assert "github-mcp-server" in github.image
    assert "context" in github.toolsets


def test_empty_allowed_tools_denies_all_in_prod() -> None:
    config = PolicyConfig(
        servers=[
            McpServerConfig(
                name="github",
                image="ghcr.io/github/github-mcp-server:v1.1.2",
                toolsets=["repos"],
                allowed_tools=[],
            )
        ]
    )
    engine = McpPolicyEngine(config)
    decision = engine.evaluate_tool("github", "list_repositories", {})
    assert not decision.allowed
    assert "not in allowlist" in decision.reason
