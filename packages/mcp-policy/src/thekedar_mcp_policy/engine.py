"""Policy evaluation for MCP tools and shell commands."""

import re
from dataclasses import dataclass
from typing import Any

from thekedar_mcp_policy.models import McpServerConfig, PolicyConfig


@dataclass(frozen=True)
class PolicyDecision:
    allowed: bool
    reason: str


class McpPolicyEngine:
    """Enforces allowlists and blocks destructive operations before MCP invocation."""

    def __init__(self, config: PolicyConfig) -> None:
        self._config = config
        self._servers = {s.name: s for s in config.servers}
        self._shell_patterns = [re.compile(p, re.IGNORECASE) for p in config.blocked_shell_patterns]
        self._path_patterns = [re.compile(p, re.IGNORECASE) for p in config.blocked_path_patterns]

    @property
    def servers(self) -> dict[str, McpServerConfig]:
        return dict(self._servers)

    def evaluate_tool(
        self,
        server: str,
        tool: str,
        arguments: dict[str, Any] | None = None,
    ) -> PolicyDecision:
        if tool in self._config.global_denied_tools:
            return PolicyDecision(False, f"Tool '{tool}' is globally denied")

        server_cfg = self._servers.get(server)
        if server_cfg is None:
            return PolicyDecision(False, f"Unknown MCP server '{server}' — not in registry")

        if server_cfg.allowed_tools and tool not in server_cfg.allowed_tools:
            return PolicyDecision(
                False,
                f"Tool '{tool}' not in allowlist for server '{server}'",
            )

        args = arguments or {}
        for value in _flatten_values(args):
            if isinstance(value, str):
                path_decision = self._check_sensitive_path(value)
                if not path_decision.allowed:
                    return path_decision
                shell_decision = self.evaluate_shell(value)
                if not shell_decision.allowed:
                    return shell_decision

        return PolicyDecision(True, "allowed")

    def evaluate_shell(self, command: str) -> PolicyDecision:
        normalized = command.strip()
        if not normalized:
            return PolicyDecision(True, "empty command")

        for pattern in self._shell_patterns:
            if pattern.search(normalized):
                return PolicyDecision(False, f"Blocked shell pattern matched: {pattern.pattern}")

        return PolicyDecision(True, "allowed")

    def validate_server_pins(self) -> list[str]:
        """Return list of validation errors for server registry (digest pins in prod)."""
        errors: list[str] = []
        for server in self._config.servers:
            if not server.image:
                errors.append(f"Server '{server.name}' missing image")
            if server.digest and not server.digest.startswith("sha256:"):
                errors.append(f"Server '{server.name}' digest must start with sha256:")
        return errors

    def _check_sensitive_path(self, path: str) -> PolicyDecision:
        for pattern in self._path_patterns:
            if pattern.search(path):
                return PolicyDecision(False, f"Sensitive path blocked: {path}")
        return PolicyDecision(True, "allowed")


def _flatten_values(data: Any) -> list[Any]:
    if isinstance(data, dict):
        result: list[Any] = []
        for value in data.values():
            result.extend(_flatten_values(value))
        return result
    if isinstance(data, list):
        result = []
        for item in data:
            result.extend(_flatten_values(item))
        return result
    return [data]
