"""Interactive project initialization."""

from __future__ import annotations

import secrets
import shutil
from pathlib import Path
from typing import Annotated

import typer
import yaml


def _repo_root() -> Path:
    cwd = Path.cwd()
    for candidate in [cwd, *cwd.parents]:
        if (candidate / "pyproject.toml").exists() and (candidate / "packages").is_dir():
            return candidate
    return cwd


def init_command(
    mode: Annotated[
        str,
        typer.Option("--mode", help="local-demo | local-live | gcp"),
    ] = "local-demo",
    yes: Annotated[bool, typer.Option("--yes", help="Skip overwrite prompt")] = False,
) -> None:
    """Generate .env, workspace.yaml, and print next steps."""
    root = _repo_root()
    env_example = root / ".env.example"
    env_path = root / ".env"
    workspace_example = root / "config" / "workspace.example.yaml"
    workspace_path = root / "config" / "workspace.yaml"

    if env_path.exists() and not yes:
        overwrite = typer.confirm(".env already exists. Overwrite?", default=False)
        if not overwrite:
            typer.echo("Keeping existing .env")
            return

    jwt_secret = secrets.token_urlsafe(32)
    whatsapp_verify = secrets.token_urlsafe(16)
    demo_mode = mode == "local-demo"
    require_sig = mode == "gcp"

    tenant_id = "default"
    workspace_name = "My Team"
    jira_key = "THE"
    github_org = "myorg"
    github_repo = "myrepo"
    slack_team = "T001"

    if not yes and mode != "local-demo":
        workspace_name = typer.prompt("Workspace name", default=workspace_name)
        jira_key = typer.prompt("Jira project key", default=jira_key)
        github_org = typer.prompt("GitHub org", default=github_org)
        github_repo = typer.prompt("GitHub repo", default=github_repo)
        slack_team = typer.prompt("Slack team ID", default=slack_team)

    env_lines = env_example.read_text() if env_example.exists() else ""
    overrides = {
        "THEKEDAR_ENVIRONMENT": "local" if mode != "gcp" else "staging",
        "THEKEDAR_DEMO_MODE": "true" if demo_mode else "false",
        "THEKEDAR_JWT_SECRET": jwt_secret,
        "WHATSAPP_VERIFY_TOKEN": whatsapp_verify,
        "THEKEDAR_REQUIRE_WEBHOOK_SIGNATURE": "true" if require_sig else "false",
        "THEKEDAR_DEFAULT_TENANT_ID": tenant_id,
    }
    env_path.write_text(_merge_env(env_lines, overrides))

    workspace_path.parent.mkdir(parents=True, exist_ok=True)
    if workspace_example.exists() and not workspace_path.exists():
        shutil.copy(workspace_example, workspace_path)

    workspace_path.write_text(
        yaml.safe_dump(
            {
                "workspaces": [
                    {
                        "tenant_id": tenant_id,
                        "name": workspace_name,
                        "jira_project_key": jira_key,
                        "github_org": github_org,
                        "github_repos": [github_repo],
                        "slack_team_id": slack_team,
                    }
                ]
            },
            sort_keys=False,
        )
    )

    typer.secho("Created .env and config/workspace.yaml", fg=typer.colors.GREEN)
    typer.echo("\nNext steps:")
    typer.echo("  ./scripts/bootstrap.sh --demo" if demo_mode else "  ./scripts/bootstrap.sh")
    typer.echo("  uv run thekedar doctor")
    if mode != "local-demo":
        typer.echo("  ./scripts/tunnel.sh")


def _merge_env(base: str, overrides: dict[str, str]) -> str:
    lines = base.splitlines()
    keys_written: set[str] = set()
    out: list[str] = []
    for line in lines:
        if "=" in line and not line.strip().startswith("#"):
            key = line.split("=", 1)[0].strip()
            if key in overrides:
                out.append(f"{key}={overrides[key]}")
                keys_written.add(key)
                continue
        out.append(line)
    for key, value in overrides.items():
        if key not in keys_written:
            out.append(f"{key}={value}")
    return "\n".join(out).rstrip() + "\n"
