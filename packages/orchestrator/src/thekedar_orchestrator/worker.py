"""Process inbound queue messages."""

from __future__ import annotations

import logging
import uuid

from thekedar_shared.audit import log_message
from thekedar_shared.db import AgentRun, init_db
from thekedar_shared.schemas import MessageEvent
from thekedar_shared.settings import Settings

from thekedar_orchestrator.graph import build_graph
from thekedar_orchestrator.integrations.workstation import WorkstationManager
from thekedar_orchestrator.replies import send_reply
from thekedar_orchestrator.services import OrchestratorServices

logger = logging.getLogger(__name__)


class OrchestratorWorker:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._session_factory = init_db(settings.database_url)
        self._services = OrchestratorServices(settings, self._session_factory)
        self._graph = build_graph(self._services)

    async def process_payload(self, payload: dict) -> None:
        message = MessageEvent.model_validate(payload["message"])
        correlation_id = payload.get("correlation_id")
        run_id = str(uuid.uuid4())
        session = self._session_factory()

        run = AgentRun(
            id=run_id,
            tenant_id=message.tenant_id,
            channel=message.channel.value,
            user_id=message.user_id,
            workflow="running",
            status="running",
            current_node="parse_intent",
            trigger_text=message.text,
            correlation_id=correlation_id,
        )
        session.add(run)
        session.commit()
        session.close()

        try:
            result = await self._graph.ainvoke(
                {
                    "message": message.model_dump(mode="json"),
                    "run_id": run_id,
                    "correlation_id": correlation_id,
                }
            )
            reply = str(result.get("reply") or "")
            workflow = str(result.get("workflow") or "help")
            status = str(result.get("status") or "completed")

            session = self._session_factory()
            run = session.get(AgentRun, run_id)
            if run:
                run.workflow = workflow
                run.current_node = str(result.get("current_node") or "summarize")
                run.status = "awaiting_approval" if status == "awaiting_approval" else "completed"
                run.reply_text = reply
                run.issue_key = result.get("issue_key")
                run.pr_url = result.get("pr_url")
                log_message(session, message.tenant_id, message.channel.value, "outbound", reply)
                session.commit()
            session.close()

            await send_reply(self._settings, message, reply)
        except Exception as exc:
            logger.exception("Agent run failed")
            session = self._session_factory()
            run = session.get(AgentRun, run_id)
            if run:
                run.status = "failed"
                run.reply_text = str(exc)
                session.commit()
            session.close()
            raise

    def seed(self) -> None:
        self._services.seed()


def run_hibernate_monitor(settings: Settings) -> None:
    session_factory = init_db(settings.database_url)
    manager = WorkstationManager(settings, session_factory)
    count = manager.hibernate_idle()
    logger.info("Hibernated %s workstation(s)", count)
