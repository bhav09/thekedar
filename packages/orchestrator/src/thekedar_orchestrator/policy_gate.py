"""MCP policy checks before side-effecting operations."""

from __future__ import annotations

from pathlib import Path

from thekedar_mcp_policy.engine import McpPolicyEngine
from thekedar_mcp_policy.loader import load_policy_config
from thekedar_shared.settings import Settings


class PolicyViolation(Exception):
    pass


def enforce_mcp_policy(
    settings: Settings,
    server: str,
    tool: str,
    arguments: dict | None = None,
) -> None:
    registry = Path(settings.mcp_registry_path)
    if not registry.exists():
        return
    engine = McpPolicyEngine(load_policy_config(registry))
    decision = engine.evaluate_tool(server, tool, arguments)
    if not decision.allowed:
        raise PolicyViolation(decision.reason)
