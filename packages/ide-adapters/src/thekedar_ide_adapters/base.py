"""Shared adapter utilities."""

from __future__ import annotations

import logging
import shutil
import subprocess
from pathlib import Path

from thekedar_shared.settings import Settings
from thekedar_shared.exceptions import ConfigurationError

logger = logging.getLogger(__name__)


def repo_path(
    settings: Settings,
    *,
    tenant_id: str | None = None,
    repo: str | None = None,
) -> Path | None:
    if settings.local_repo_path:
        return Path(settings.local_repo_path).resolve()

    if settings.environment in ("staging", "prod"):
        if not tenant_id or not repo:
            raise ConfigurationError("tenant_id and repo are required for cloud repo_path in staging/prod")
        root = settings.workstation_repo_root or "/home/user/repos"
        repo_slug = repo.split("/")[-1]
        return Path(root) / tenant_id / repo_slug

    return Path.cwd().resolve()


def command_available(name: str) -> bool:
    return shutil.which(name) is not None


def run_git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
    )


def commits_ahead(repo: Path, branch: str, base: str = "main") -> int:
    result = run_git(repo, "rev-list", "--count", f"{base}..{branch}")
    if result.returncode != 0:
        return 0
    try:
        return int(result.stdout.strip())
    except ValueError:
        return 0


def checkout_branch(repo: Path, branch: str, base: str = "main") -> bool:
    run_git(repo, "fetch", "origin", base)
    run_git(repo, "checkout", base)
    run_git(repo, "pull", "--rebase", "origin", base)
    if run_git(repo, "checkout", branch).returncode != 0:
        run_git(repo, "checkout", "-b", branch)
    return True
