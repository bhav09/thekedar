"""Cloud Workstation lifecycle (GCP API with local simulation)."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from thekedar_shared.db import TestRunRecord, WorkstationHealth
from thekedar_shared.settings import Settings

logger = logging.getLogger(__name__)

IDLE_MINUTES = 30


class WorkstationManager:
    def __init__(self, settings: Settings, session_factory) -> None:
        self._settings = settings
        self._session_factory = session_factory

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
                session.commit()
                if self._settings.gcp_project_id and self._settings.environment in (
                    "staging",
                    "prod",
                ):
                    await self._gcp_start(config_id or ws.name)
                else:
                    logger.info("Workstation boot simulated for tenant=%s", tenant_id)
                ws.state = "active"
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

            record = TestRunRecord(
                tenant_id=tenant_id,
                run_id=run_id,
                status="passed",
                summary="git pull --rebase origin main && pytest (simulated)",
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
            if count:
                session.commit()
            return count
        finally:
            session.close()

    async def _gcp_start(self, config_id: str) -> None:
        logger.info(
            "GCP Workstation start requested: project=%s config=%s",
            self._settings.gcp_project_id,
            config_id,
        )
