"""Load MCP server registry and policy from YAML."""

from pathlib import Path

import yaml

from thekedar_mcp_policy.models import McpServerConfig, PolicyConfig


def load_policy_config(path: Path) -> PolicyConfig:
    raw = yaml.safe_load(path.read_text()) or {}
    servers_raw = raw.get("servers") or []
    servers = [McpServerConfig.model_validate(item) for item in servers_raw]
    extra = {k: v for k, v in raw.items() if k != "servers"}
    return PolicyConfig(servers=servers, **extra)
