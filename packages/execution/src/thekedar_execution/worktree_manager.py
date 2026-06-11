"""Git worktree manager for parallel agent checkouts with concurrency constraints."""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)


class ConcurrencyLimitExceeded(Exception):
    pass


class GitWorktreeManager:
    """Creates, lists, and purges git worktrees to enable parallel agent checkouts."""

    def __init__(self, base_repo_path: Path, max_concurrency: int = 3) -> None:
        self.base_repo_path = base_repo_path.resolve()
        self.max_concurrency = max_concurrency

    def _run_git(self, args: list[str], cwd: Path | None = None) -> str:
        try:
            res = subprocess.run(
                ["git"] + args,
                cwd=cwd or self.base_repo_path,
                capture_output=True,
                text=True,
                check=True,
            )
            return res.stdout.strip()
        except subprocess.CalledProcessError as e:
            logger.error("Git command failed: %s. Stderr: %s", " ".join(args), e.stderr)
            raise RuntimeError(f"Git command failed: {e.stderr.strip()}") from e

    def active_worktrees(self) -> list[dict[str, str]]:
        """Lists active git worktrees on the main repository."""
        if not self.base_repo_path.is_dir():
            return []
        try:
            output = self._run_git(["worktree", "list", "--porcelain"])
            worktrees = []
            current: dict[str, str] = {}
            for line in output.splitlines():
                if not line.strip():
                    if current:
                        worktrees.append(current)
                        current = {}
                    continue
                parts = line.split(" ", 1)
                if len(parts) == 2:
                    current[parts[0]] = parts[1]
            if current:
                worktrees.append(current)
            return worktrees
        except Exception as e:
            logger.error("Failed to list git worktrees: %s", e)
            return []

    def allocate_worktree(self, run_id: str, branch: str) -> Path:
        """Allocates a new git worktree for a parallel run. Enforces concurrency cap."""
        worktrees = self.active_worktrees()
        
        # Enforce concurrency cap (subtracting main branch worktree)
        active_cap_count = len([w for w in worktrees if "worktree" in w]) - 1
        if active_cap_count >= self.max_concurrency:
            raise ConcurrencyLimitExceeded(
                f"Concurrency cap of {self.max_concurrency} parallel runs reached for repo at {self.base_repo_path}"
            )

        worktree_dir = self.base_repo_path.parent / f"worktree_{run_id}"
        
        logger.info("Allocating git worktree for run %s on branch %s at %s", run_id, branch, worktree_dir)
        try:
            # git worktree add <path> <branch>
            # If the branch already exists, check it out, otherwise create it (-b)
            try:
                self._run_git(["worktree", "add", "-b", branch, str(worktree_dir)])
            except Exception:
                # If branch already exists, add without -b
                self._run_git(["worktree", "add", str(worktree_dir), branch])
            return worktree_dir
        except Exception as e:
            logger.exception("Failed to allocate worktree")
            raise RuntimeError(f"Failed to allocate worktree: {e}") from e

    def prune_worktree(self, run_id: str) -> None:
        """Cleans up and removes a run's git worktree from disk and repository."""
        worktree_dir = self.base_repo_path.parent / f"worktree_{run_id}"
        if not worktree_dir.exists():
            return

        logger.info("Pruning git worktree for run %s at %s", run_id, worktree_dir)
        try:
            self._run_git(["worktree", "remove", "-f", str(worktree_dir)])
            self._run_git(["worktree", "prune"])
        except Exception as e:
            logger.error("Failed to prune worktree: %s", e)
