"""Cloud Workstation lifecycle (GCP API with local simulation)."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from thekedar_shared.db import TestRunRecord, WorkstationHealth
from thekedar_shared.settings import Settings
from thekedar_execution.remote import select_remote_executor

logger = logging.getLogger(__name__)

IDLE_MINUTES = 30


class WorkstationManager:
    def __init__(self, settings: Settings, session_factory) -> None:
        self._settings = settings
        self._session_factory = session_factory

    async def get_git_sha(self, tenant_id: str = "default", repo: str | None = None) -> str | None:
        executor = select_remote_executor(self._settings)
        repo_to_use = repo
        if not repo_to_use:
            session = self._session_factory()
            try:
                from thekedar_shared.db import Workspace
                workspace = session.query(Workspace).filter_by(tenant_id=tenant_id).first()
                if workspace:
                    from thekedar_shared.workspace import WorkspaceService
                    workspace_service = WorkspaceService(self._session_factory)
                    repo_to_use = workspace_service.primary_repo(workspace)
            finally:
                session.close()

        if not repo_to_use:
            repo_to_use = "default-repo"

        path = executor.repo_mount_path(tenant_id, repo_to_use)
        return await executor.get_git_sha(tenant_id, path)

    async def ensure_ready(self, tenant_id: str, config_id: str | None) -> WorkstationHealth:
        session = self._session_factory()
        try:
            ws = session.query(WorkstationHealth).filter_by(tenant_id=tenant_id).first()
            if ws is None:
                ws = WorkstationHealth(
                    tenant_id=tenant_id,
                    name=config_id or f"thekedar-ws-{tenant_id}",
                    state="sleeping",
                    region=self._settings.gcp_region,
                )
                session.add(ws)

            if ws.state in ("sleeping", "stopped"):
                ws.state = "booting"
                ws.boot_started_at = datetime.now(UTC)
                session.commit()
                
                try:
                    executor = select_remote_executor(self._settings)
                    endpoint = await executor.ensure_ready(tenant_id, config_id)
                    ws.host = endpoint.host
                    ws.instance_id = endpoint.instance_id
                    ws.state = "active"
                    ws.last_error = None
                    
                    try:
                        from thekedar_shared.events import DomainEvent, EventType
                        event = DomainEvent(
                            type=EventType.WORKSTATION_STATE_CHANGED,
                            tenant_id=tenant_id,
                            payload={"state": "active", "host": ws.host, "instance_id": ws.instance_id}
                        )
                        logger.info("Emitting event: %s", event.model_dump_json())
                    except Exception as ev_err:
                        logger.warning("Failed to emit event: %s", ev_err)

                    if ws.boot_started_at:
                        boot_started = ws.boot_started_at
                        if boot_started.tzinfo is None:
                            boot_started = boot_started.replace(tzinfo=UTC)
                        latency = (datetime.now(UTC) - boot_started).total_seconds()
                        logger.info("[METRIC] workstation_boot_latency_s: %f", latency)
                except Exception as e:
                    ws.state = "stopped"
                    ws.last_error = str(e)
                    session.commit()
                    try:
                        from thekedar_shared.events import DomainEvent, EventType
                        event = DomainEvent(
                            type=EventType.WORKSTATION_STATE_CHANGED,
                            tenant_id=tenant_id,
                            payload={"state": "stopped", "error": str(e)}
                        )
                        logger.info("Emitting event: %s", event.model_dump_json())
                    except Exception as ev_err:
                        logger.warning("Failed to emit event: %s", ev_err)
                    raise

            ws.last_activity_at = datetime.now(UTC)
            session.commit()
            session.refresh(ws)
            return ws
        finally:
            session.close()

    async def sync_repo_and_test(self, tenant_id: str, run_id: str | None) -> TestRunRecord:
        session = self._session_factory()
        try:
            ws = session.query(WorkstationHealth).filter_by(tenant_id=tenant_id).first()
            if ws:
                ws.commits_behind_main = 0
                ws.last_activity_at = datetime.now(UTC)

            # 1. Fetch workspace config to find the primary repo
            from thekedar_shared.workspace import WorkspaceService
            from thekedar_shared.db import Workspace
            workspace_service = WorkspaceService(self._session_factory)
            workspace = session.query(Workspace).filter_by(tenant_id=tenant_id).first()
            
            repo = "default-repo"
            if workspace:
                repo = workspace_service.primary_repo(workspace)

            # 2. Get remote executor and run sync + tests
            executor = select_remote_executor(self._settings)
            mount_path = executor.repo_mount_path(tenant_id, repo)
            if ws:
                ws.repo_path = mount_path
                session.commit()

            logger.info("Syncing repository: %s for tenant: %s", repo, tenant_id)
            sync_res = await executor.sync_repo(tenant_id, repo, "main")
            if ws and sync_res.success:
                ws.commits_behind_main = sync_res.commits_behind
                logger.info("[METRIC] context_staleness_total: %d", ws.commits_behind_main)
            elif not sync_res.success:
                logger.info("[METRIC] workstation_sync_failures: 1")

            status, summary = await executor.run_tests(tenant_id, mount_path)

            # Trigger workstation-side indexing job post sync_repo
            from thekedar_context.indexer import RepoIndexer
            if sync_res.success:
                from pathlib import Path
                p = Path(mount_path)
                if p.is_dir():
                    RepoIndexer().index(session, tenant_id, repo, p)

            record = TestRunRecord(
                tenant_id=tenant_id,
                run_id=run_id,
                status=status,
                summary=summary,
            )
            session.add(record)
            session.commit()
            session.refresh(record)
            return record
        finally:
            session.close()

    def hibernate_idle(self) -> int:
        session = self._session_factory()
        count = 0
        try:
            cutoff = datetime.now(UTC) - timedelta(minutes=IDLE_MINUTES)
            rows = (
                session.query(WorkstationHealth)
                .filter(WorkstationHealth.state == "active")
                .filter(WorkstationHealth.last_activity_at < cutoff)
                .all()
            )
            for ws in rows:
                ws.state = "sleeping"
                count += 1
                try:
                    from thekedar_shared.events import DomainEvent, EventType
                    event = DomainEvent(
                        type=EventType.WORKSTATION_STATE_CHANGED,
                        tenant_id=ws.tenant_id,
                        payload={"state": "sleeping"}
                    )
                    logger.info("Emitting event: %s", event.model_dump_json())
                except Exception as ev_err:
                    logger.warning("Failed to emit event: %s", ev_err)
            if count:
                session.commit()
            return count
        finally:
            session.close()

    async def _gcp_start(self, config_id: str) -> None:
        # Keep as informational log - real GCP boot is delegated via GcpWorkstationRemoteExecutor
        logger.info(
            "GCP Workstation start requested: project=%s config=%s",
            self._settings.gcp_project_id,
            config_id,
        )
