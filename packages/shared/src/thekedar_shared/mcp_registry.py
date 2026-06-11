"""MCP Registry loader and tenant auth injector."""

from __future__ import annotations

import logging
import os
import yaml
from pathlib import Path
from typing import Any

from thekedar_shared.settings import Settings

logger = logging.getLogger(__name__)


class McpRegistry:
    """Loads and wires MCP Server configurations with per-tenant tokens."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def get_tenant_github_token(self, tenant_id: str) -> str | None:
        """Fetches a tenant's GitHub Personal Access Token from Secret Manager, falling back to Env/Settings."""
        # 1. Check for environment variable specific to tenant
        env_var_name = f"GITHUB_TOKEN_{tenant_id.upper().replace('-', '_')}"
        env_token = os.environ.get(env_var_name)
        if env_token:
            return env_token

        # 2. Check for GCP Secret Manager if configured
        if self._settings.gcp_project_id and self._settings.environment in ("staging", "prod"):
            try:
                from google.cloud import secretmanager
                client = secretmanager.SecretManagerServiceClient()
                secret_name = f"projects/{self._settings.gcp_project_id}/secrets/github_token_{tenant_id}/versions/latest"
                response = client.access_secret_version(name=secret_name)
                token = response.payload.data.decode("utf-8").strip()
                if token:
                    return token
            except Exception as e:
                logger.warning(
                    "Failed to fetch GitHub token from GCP Secret Manager for tenant %s: %s",
                    tenant_id,
                    e,
                )

        # 3. Fallback to global setting GITHUB_TOKEN
        if self._settings.github_token:
            return self._settings.github_token.get_secret_value()

        # 4. Fallback to generic env
        return os.environ.get("GITHUB_TOKEN")

    def load_servers(self, tenant_id: str) -> list[dict[str, Any]]:
        """Loads and returns all configured MCP servers with tenant-scoped authentication."""
        reg_path = Path(self._settings.mcp_registry_path)
        if not reg_path.exists():
            logger.warning("MCP Registry file %s does not exist", reg_path)
            return []

        try:
            with open(reg_path) as f:
                data = yaml.safe_load(f) or {}
            servers = data.get("servers", [])
        except Exception as e:
            logger.error("Failed to parse MCP Registry: %s", e)
            return []

        resolved_servers = []
        github_token = self.get_tenant_github_token(tenant_id)

        for s in servers:
            name = s.get("name", "")
            server_config = dict(s)

            if name == "github":
                # Inject token securely
                if github_token:
                    server_config["token"] = github_token
                    # If utilizing HTTP transport for Bifrost
                    server_config["connection_string"] = "https://api.githubcopilot.com/mcp/"
                    server_config["headers"] = {"Authorization": f"Bearer {github_token}"}
                else:
                    logger.warning("No GitHub token resolved for tenant %s", tenant_id)

            resolved_servers.append(server_config)

        return resolved_servers

    def get_bifrost_client_config(self, tenant_id: str, server_name: str) -> dict[str, Any] | None:
        """Constructs Bifrost API compatible client JSON payload for a server."""
        servers = self.load_servers(tenant_id)
        server = next((s for s in servers if s.get("name") == server_name), None)
        if not server:
            return None

        # Build client JSON matching config/bifrost/github-mcp-client.json schema
        token = server.get("token") or ""
        allowlist = self._settings.github_mcp_tool_allowlist.split(",") if server_name == "github" else ["*"]

        return {
            "name": server_name,
            "connection_type": server.get("transport", "http"),
            "connection_string": server.get("connection_string", ""),
            "auth_type": "bearer" if token else "none",
            "token": token,
            "tools_to_execute": allowlist,
        }
