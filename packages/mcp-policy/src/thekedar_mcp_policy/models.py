"""Policy configuration models."""

from pydantic import BaseModel, Field


class McpServerConfig(BaseModel):
    name: str
    image: str
    digest: str | None = None
    toolsets: list[str] = Field(default_factory=list)
    allowed_tools: list[str] = Field(default_factory=list)
    transport: str = "stdio"
    port: int | None = None


class PolicyConfig(BaseModel):
    """Loaded from config/mcp-servers.yaml + policy rules."""

    servers: list[McpServerConfig] = Field(default_factory=list)
    blocked_shell_patterns: list[str] = Field(
        default_factory=lambda: [
            r"rm\s+-rf",
            r"git\s+push\s+.*--force",
            r"git\s+push\s+-f\b",
            r"mkfs\.",
            r":\(\)\s*\{\s*:\s*\|\s*:\s*&\s*\}\s*;",
            r">\s*/dev/sd",
            r"chmod\s+-R\s+777\s+/",
            r"curl\s+.*\|\s*(ba)?sh",
        ]
    )
    blocked_path_patterns: list[str] = Field(
        default_factory=lambda: [
            r"\.env$",
            r"\.env\.",
            r"id_rsa",
            r"\.pem$",
            r"secrets?/",
            r"credentials\.json",
        ]
    )
    global_denied_tools: list[str] = Field(
        default_factory=lambda: [
            "delete_repository",
            "force_push",
        ]
    )
