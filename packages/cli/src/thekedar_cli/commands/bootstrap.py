"""Bootstrap local stack."""

from __future__ import annotations

import subprocess
import time
from pathlib import Path
from typing import Annotated

import httpx
import typer


def _repo_root() -> Path:
    cwd = Path.cwd()
    for candidate in [cwd, *cwd.parents]:
        if (candidate / "docker-compose.yml").exists():
            return candidate
    return cwd


def bootstrap_command(
    demo: Annotated[bool, typer.Option("--demo", help="Enable demo mode env")] = False,
    skip_docker: Annotated[bool, typer.Option("--skip-docker")] = False,
) -> None:
    """Install deps and start local Thekedar stack."""
    root = _repo_root()
    typer.echo("Syncing Python dependencies…")
    subprocess.run(["uv", "sync", "--all-packages", "--dev"], cwd=root, check=True)

    if not skip_docker:
        cmd = ["docker", "compose", "up", "-d", "--build"]
        typer.echo("Starting Docker Compose…")
        subprocess.run(cmd, cwd=root, check=True)
        _wait_for_health()

    typer.echo("Running doctor…")
    subprocess.run(["uv", "run", "thekedar", "doctor"], cwd=root, check=False)
    typer.secho("Bootstrap complete.", fg=typer.colors.GREEN)
    typer.echo("Dashboard: http://localhost:8081")


def _wait_for_health(timeout: int = 120) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            httpx.get("http://localhost:8080/health", timeout=2.0)
            httpx.post(
                "http://localhost:8081/api/v1/auth/token",
                json={"tenant_id": "default"},
                timeout=2.0,
            )
            return
        except httpx.HTTPError:
            time.sleep(2)
    typer.secho("Warning: services did not become healthy in time", fg=typer.colors.YELLOW)
