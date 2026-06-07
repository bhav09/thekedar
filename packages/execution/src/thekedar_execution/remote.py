"""Remote execution abstraction and implementations."""

from __future__ import annotations

import logging
import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, TYPE_CHECKING

if TYPE_CHECKING:
    from thekedar_shared.settings import Settings

logger = logging.getLogger(__name__)


@dataclass
class WorkstationEndpoint:
    host: str | None
    instance_id: str | None
    port: int = 22


@dataclass
class CommandResult:
    exit_code: int
    stdout: str
    stderr: str


@dataclass
class SyncResult:
    success: bool
    summary: str
    commits_behind: int = 0


class RemoteExecutor(Protocol):
    async def ensure_ready(self, tenant_id: str, config_id: str | None) -> WorkstationEndpoint: ...
    async def run_command(self, tenant_id: str, cmd: list[str], cwd: str, timeout_s: int) -> CommandResult: ...
    async def get_git_sha(self, tenant_id: str, repo_path: str) -> str | None: ...
    async def sync_repo(self, tenant_id: str, repo: str, branch: str) -> SyncResult: ...
    async def run_tests(self, tenant_id: str, repo_path: str) -> tuple[str, str]: ...
    def repo_mount_path(self, tenant_id: str, repo: str) -> str: ...


class LocalRemoteExecutor:
    """Local remote executor — runs command locally using standard subprocess."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def ensure_ready(self, tenant_id: str, config_id: str | None) -> WorkstationEndpoint:
        return WorkstationEndpoint(host="localhost", instance_id="local")

    async def run_command(self, tenant_id: str, cmd: list[str], cwd: str, timeout_s: int) -> CommandResult:
        logger.info("Local command: %s in %s", cmd, cwd)
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=cwd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            try:
                stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout_s)
                return CommandResult(
                    exit_code=proc.returncode or 0,
                    stdout=stdout.decode(errors="replace"),
                    stderr=stderr.decode(errors="replace"),
                )
            except asyncio.TimeoutError:
                proc.kill()
                await proc.communicate()
                return CommandResult(
                    exit_code=-1,
                    stdout="",
                    stderr="Command timed out",
                )
        except Exception as e:
            return CommandResult(
                exit_code=-1,
                stdout="",
                stderr=f"Failed to execute locally: {str(e)}",
            )

    async def get_git_sha(self, tenant_id: str, repo_path: str) -> str | None:
        try:
            import subprocess
            res = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=repo_path,
                capture_output=True,
                text=True,
                check=True,
            )
            return res.stdout.strip()
        except Exception:
            return None

    async def sync_repo(self, tenant_id: str, repo: str, branch: str) -> SyncResult:
        path = self.repo_mount_path(tenant_id, repo)
        if not Path(path).exists():
            return SyncResult(success=False, summary=f"Local path {path} does not exist", commits_behind=0)
        try:
            import subprocess
            # Mock or local sync behaviour (git pull, checkout main, rebase main, checkout branch)
            # Use fetch origin and rebase to ensure main is up to date
            subprocess.run(["git", "fetch", "origin", "main"], cwd=path, capture_output=True)
            subprocess.run(["git", "checkout", "main"], cwd=path, capture_output=True)
            subprocess.run(["git", "pull", "--rebase", "origin", "main"], cwd=path, capture_output=True)
            res = subprocess.run(["git", "checkout", branch], cwd=path, capture_output=True)
            if res.returncode != 0:
                subprocess.run(["git", "checkout", "-b", branch], cwd=path, capture_output=True)

            commits_behind = 0
            res = subprocess.run(["git", "rev-list", "--count", f"HEAD..origin/main"], cwd=path, capture_output=True, text=True)
            if res.returncode == 0:
                try:
                    commits_behind = int(res.stdout.strip())
                except ValueError:
                    pass

            return SyncResult(success=True, summary="Sync completed locally", commits_behind=commits_behind)
        except Exception as e:
            return SyncResult(success=False, summary=f"Local sync failed: {str(e)}", commits_behind=0)

    async def run_tests(self, tenant_id: str, repo_path: str) -> tuple[str, str]:
        path = Path(repo_path)
        if not path.is_dir():
            return "failed", f"Repo directory {repo_path} does not exist"

        if (path / "pyproject.toml").is_file() or (path / "pytest.ini").is_file():
            cmd = ["uv", "run", "pytest", "tests", "-q", "--tb=short"]
            import shutil
            if not shutil.which("uv"):
                cmd = ["python", "-m", "pytest", "tests", "-q", "--tb=short"]
        elif (path / "package.json").is_file():
            cmd = ["npm", "test"]
        else:
            return "passed", "No test runner detected — skipped"

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=str(path),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        stdout, _ = await proc.communicate()
        output = stdout.decode(errors="replace")[:2000]
        status = "passed" if proc.returncode == 0 else "failed"
        return status, output or status

    def repo_mount_path(self, tenant_id: str, repo: str) -> str:
        if self._settings.local_repo_path:
            return str(Path(self._settings.local_repo_path).resolve())
        return str(Path.cwd().resolve())


class InProcessFakeRemoteExecutor:
    """Fake remote executor for hermetic unit testing."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self.commands_run: list[tuple[str, list[str]]] = []
        self.scripted_git_sha: str | None = "fake-sha-12345"
        self.scripted_ensure_ready: WorkstationEndpoint = WorkstationEndpoint(host="fake-host", instance_id="fake-instance")
        self.scripted_sync_result: SyncResult = SyncResult(success=True, summary="Fake sync completed", commits_behind=0)
        self.scripted_test_status: str = "passed"
        self.scripted_test_output: str = "Fake tests passed"
        self.scripted_cmd_results: dict[str, CommandResult] = {}

    async def ensure_ready(self, tenant_id: str, config_id: str | None) -> WorkstationEndpoint:
        return self.scripted_ensure_ready

    async def run_command(self, tenant_id: str, cmd: list[str], cwd: str, timeout_s: int) -> CommandResult:
        self.commands_run.append((tenant_id, cmd))
        cmd_str = " ".join(cmd)
        if cmd_str in self.scripted_cmd_results:
            return self.scripted_cmd_results[cmd_str]
        return CommandResult(exit_code=0, stdout="Fake execution output", stderr="")

    async def get_git_sha(self, tenant_id: str, repo_path: str) -> str | None:
        return self.scripted_git_sha

    async def sync_repo(self, tenant_id: str, repo: str, branch: str) -> SyncResult:
        return self.scripted_sync_result

    async def run_tests(self, tenant_id: str, repo_path: str) -> tuple[str, str]:
        return self.scripted_test_status, self.scripted_test_output

    def repo_mount_path(self, tenant_id: str, repo: str) -> str:
        if self._settings.local_repo_path:
            return str(Path(self._settings.local_repo_path).resolve())
        return str(Path.cwd().resolve() / "fake_repos" / tenant_id / repo.split("/")[-1])


class GcpWorkstationRemoteExecutor:
    """GCP Workstation remote executor (SSH remote execution) - implemented fully in Phase C."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def ensure_ready(self, tenant_id: str, config_id: str | None) -> WorkstationEndpoint:
        from thekedar_execution.gcp_workstations import GcpWorkstationClient
        client = GcpWorkstationClient(self._settings)

        state = await client.get_state(tenant_id, config_id)
        if state != "STATE_RUNNING":
            await client.start(tenant_id, config_id)

        # Retrieve the latest workstation details to get host and uid
        client_api = client._get_client()
        name = client.get_workstation_resource_name(tenant_id, config_id)
        loop = asyncio.get_running_loop()
        workstation = await loop.run_in_executor(
            None, lambda: client_api.get_workstation(name=name)
        )
        return WorkstationEndpoint(
            host=workstation.host,
            instance_id=workstation.uid
        )

    async def run_command(self, tenant_id: str, cmd: list[str], cwd: str, timeout_s: int) -> CommandResult:
        import shlex
        import asyncio

        project = self._settings.gcp_project_id or "mock-project"
        location = self._settings.gcp_region or "us-central1"
        cluster = self._settings.gcp_workstation_cluster_id or "mock-cluster"
        config = self._settings.gcp_workstation_config_id or "mock-config"

        # Sanitize tenant_id for GCP resource name
        clean_tenant = "".join(c.lower() if c.isalnum() else "-" for c in tenant_id)
        clean_tenant = clean_tenant.strip("-")
        workstation_id = f"thekedar-ws-{clean_tenant}"

        bash_cmd = " ".join(shlex.quote(c) for c in cmd)
        full_cmd = f"cd {shlex.quote(cwd)} && {bash_cmd}"

        gcloud_cmd = [
            "gcloud", "workstations", "ssh",
            workstation_id,
            "--project", project,
            "--region", location,
            "--cluster", cluster,
            "--config", config,
            "--command", full_cmd
        ]

        try:
            proc = await asyncio.create_subprocess_exec(
                *gcloud_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            try:
                stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout_s)
                return CommandResult(
                    exit_code=proc.returncode or 0,
                    stdout=stdout.decode(errors="replace"),
                    stderr=stderr.decode(errors="replace")
                )
            except asyncio.TimeoutError:
                try:
                    proc.kill()
                except ProcessLookupError:
                    pass
                return CommandResult(
                    exit_code=-1,
                    stdout="",
                    stderr=f"Command timed out after {timeout_s}s"
                )
        except Exception as e:
            return CommandResult(
                exit_code=-1,
                stdout="",
                stderr=f"Failed to execute gcloud ssh: {str(e)}"
            )

    async def get_git_sha(self, tenant_id: str, repo_path: str) -> str | None:
        res = await self.run_command(tenant_id, ["git", "rev-parse", "HEAD"], repo_path, timeout_s=30)
        if res.exit_code == 0:
            return res.stdout.strip()
        return None

    async def sync_repo(self, tenant_id: str, repo: str, branch: str) -> SyncResult:
        mount_path = self.repo_mount_path(tenant_id, repo)
        
        # Check if directory exists
        check_dir_res = await self.run_command(tenant_id, ["test", "-d", mount_path], cwd="/", timeout_s=30)
        
        if check_dir_res.exit_code != 0:
            # Clone from GitHub
            parent_dir = str(Path(mount_path).parent)
            await self.run_command(tenant_id, ["mkdir", "-p", parent_dir], cwd="/", timeout_s=30)
            
            repo_url = f"https://github.com/{repo}.git"
            clone_res = await self.run_command(tenant_id, ["git", "clone", repo_url, mount_path], cwd="/", timeout_s=90)
            if clone_res.exit_code != 0:
                return SyncResult(success=False, summary=f"Clone failed: {clone_res.stderr or clone_res.stdout}", commits_behind=0)
        
        # Fetch & Sync main, pull, then branch
        await self.run_command(tenant_id, ["git", "fetch", "origin"], cwd=mount_path, timeout_s=60)
        await self.run_command(tenant_id, ["git", "checkout", "main"], cwd=mount_path, timeout_s=30)
        await self.run_command(tenant_id, ["git", "pull", "--rebase", "origin", "main"], cwd=mount_path, timeout_s=60)
        
        checkout_res = await self.run_command(tenant_id, ["git", "checkout", branch], cwd=mount_path, timeout_s=30)
        if checkout_res.exit_code != 0:
            await self.run_command(tenant_id, ["git", "checkout", "-b", branch], cwd=mount_path, timeout_s=30)
            
        commits_behind = 0
        rev_res = await self.run_command(tenant_id, ["git", "rev-list", "--count", "HEAD..origin/main"], cwd=mount_path, timeout_s=30)
        if rev_res.exit_code == 0:
            try:
                commits_behind = int(rev_res.stdout.strip())
            except ValueError:
                pass
                
        return SyncResult(success=True, summary="Sync completed on GCP Workstation", commits_behind=commits_behind)

    async def run_tests(self, tenant_id: str, repo_path: str) -> tuple[str, str]:
        # Check test run files
        check_pyproject = await self.run_command(tenant_id, ["test", "-f", "pyproject.toml"], cwd=repo_path, timeout_s=10)
        check_package_json = await self.run_command(tenant_id, ["test", "-f", "package.json"], cwd=repo_path, timeout_s=10)
        
        if check_pyproject.exit_code == 0:
            check_uv = await self.run_command(tenant_id, ["which", "uv"], cwd=repo_path, timeout_s=10)
            if check_uv.exit_code == 0:
                cmd = ["uv", "run", "pytest", "tests", "-q", "--tb=short"]
            else:
                cmd = ["python", "-m", "pytest", "tests", "-q", "--tb=short"]
        elif check_package_json.exit_code == 0:
            cmd = ["npm", "test"]
        else:
            return "passed", "No test runner detected — skipped"
            
        test_res = await self.run_command(tenant_id, cmd, cwd=repo_path, timeout_s=180)
        status = "passed" if test_res.exit_code == 0 else "failed"
        output = test_res.stdout or test_res.stderr or ""
        return status, output[:2000]

    def repo_mount_path(self, tenant_id: str, repo: str) -> str:
        root = self._settings.workstation_repo_root or "/home/user/repos"
        repo_slug = repo.split("/")[-1]
        return f"{root}/{tenant_id}/{repo_slug}"


_global_executor: RemoteExecutor | None = None


def select_remote_executor(settings: Settings) -> RemoteExecutor:
    global _global_executor
    if _global_executor is not None:
        return _global_executor
    mode = (settings.remote_executor or "local").lower()
    if mode == "fake":
        return InProcessFakeRemoteExecutor(settings)
    elif mode == "gcp":
        return GcpWorkstationRemoteExecutor(settings)
    else:
        return LocalRemoteExecutor(settings)


def set_global_executor(executor: RemoteExecutor | None) -> None:
    global _global_executor
    _global_executor = executor
