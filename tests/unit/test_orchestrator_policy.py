"""Orchestrator MCP policy integration."""

import pytest
from thekedar_orchestrator.policy_gate import PolicyViolation, enforce_mcp_policy
from thekedar_shared.settings import Settings


def test_policy_allows_github_tools(tmp_path) -> None:
    registry = tmp_path / "mcp-servers.yaml"
    registry.write_text(
        """
servers:
  - name: github
    image: ghcr.io/github/github-mcp-server:v1.1.2
    allowed_tools: [create_branch, create_pull_request]
"""
    )
    settings = Settings(THEKEDAR_MCP_REGISTRY_PATH=str(registry), THEKEDAR_DEMO_MODE=True)
    enforce_mcp_policy(settings, "github", "create_branch", {"branch": "thekedar/THE-1-x"})


def test_policy_denies_unknown_server(tmp_path) -> None:
    registry = tmp_path / "mcp-servers.yaml"
    registry.write_text("servers:\n  - name: github\n    image: x\n")
    settings = Settings(THEKEDAR_MCP_REGISTRY_PATH=str(registry), THEKEDAR_DEMO_MODE=True)
    with pytest.raises(PolicyViolation):
        enforce_mcp_policy(settings, "unknown", "any_tool")
