"""MCP gateway diagnostics."""

from pathlib import Path
from typing import Annotated

import httpx
import typer
from thekedar_mcp_policy.engine import McpPolicyEngine
from thekedar_mcp_policy.loader import load_policy_config
from thekedar_shared.settings import get_settings

app = typer.Typer(name="mcp", help="MCP gateway commands")


def _repo_root() -> Path:
    cwd = Path.cwd()
    for candidate in [cwd, *cwd.parents]:
        if (candidate / "config" / "mcp-servers.yaml").exists():
            return candidate
    return cwd


@app.command("ping")
def ping(
    server: Annotated[str, typer.Argument(help="MCP server name (e.g. github)")],
    config_path: Annotated[
        Path | None,
        typer.Option("--config", help="Path to mcp-servers.yaml"),
    ] = None,
) -> None:
    """Verify MCP server registry, policy engine, and gateway connectivity."""
    settings = get_settings()
    root = _repo_root()
    registry_path = config_path or root / "config" / "mcp-servers.yaml"

    if not registry_path.exists():
        typer.secho(f"Registry not found: {registry_path}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)

    policy_config = load_policy_config(registry_path)
    engine = McpPolicyEngine(policy_config)

    pin_errors = engine.validate_server_pins()
    if pin_errors:
        for err in pin_errors:
            typer.secho(f"PIN ERROR: {err}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)

    if server not in engine.servers:
        typer.secho(
            f"Unknown server '{server}'. Registered: {', '.join(engine.servers) or '(none)'}",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(code=1)

    server_cfg = engine.servers[server]
    typer.secho(f"✓ Registry: {server_cfg.name} → {server_cfg.image}", fg=typer.colors.GREEN)
    if server_cfg.digest:
        typer.echo(f"  digest: {server_cfg.digest[:24]}...")
    typer.echo(f"  toolsets: {', '.join(server_cfg.toolsets) or '(default)'}")

    typer.secho("✓ Policy engine loaded", fg=typer.colors.GREEN)

    bifrost_url = settings.bifrost_url.rstrip("/")
    if _bifrost_reachable(bifrost_url):
        typer.secho(f"✓ Bifrost gateway reachable at {bifrost_url}", fg=typer.colors.GREEN)
    else:
        typer.secho(
            f"⚠ Bifrost not reachable at {bifrost_url}",
            fg=typer.colors.YELLOW,
        )
        typer.echo("  Start local stack: docker compose up bifrost")

    if server == "github":
        _ping_github(settings.github_token.get_secret_value() if settings.github_token else None)

    typer.secho(f"\nMCP ping '{server}' complete.", fg=typer.colors.GREEN)


def _bifrost_reachable(base_url: str) -> bool:
    paths = ("/health", "/api/health", "/")
    try:
        with httpx.Client(timeout=5.0) as client:
            for path in paths:
                response = client.get(f"{base_url}{path}")
                if response.status_code < 500:
                    return True
    except httpx.HTTPError:
        return False
    return False


def _ping_github(token: str | None) -> None:
    if not token:
        typer.secho(
            "⚠ GITHUB_TOKEN not set — skipping GitHub API check",
            fg=typer.colors.YELLOW,
        )
        return

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.get("https://api.github.com/user", headers=headers)
            response.raise_for_status()
            login = response.json().get("login", "unknown")
        typer.secho(f"✓ GitHub API authenticated as {login}", fg=typer.colors.GREEN)
    except httpx.HTTPError as exc:
        typer.secho(f"✗ GitHub API check failed: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc
