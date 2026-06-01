"""Process inbound queue messages."""

from __future__ import annotations

import logging
import uuid

from thekedar_shared.db import AgentRun, WorkstationHealth, init_db
from thekedar_shared.schemas import MessageEvent
from thekedar_shared.settings import Settings

from thekedar_orchestrator.graph import build_graph
from thekedar_orchestrator.replies import send_reply

logger = logging.getLogger(__name__)


class OrchestratorWorker:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._graph = build_graph()
        self._session_factory = init_db(settings.database_url)

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

        try:
            result = self._graph.invoke({"message": message.model_dump(mode="json")})
            reply = str(result.get("reply") or "")
            workflow = str(result.get("workflow") or "help")

            run.workflow = workflow
            run.current_node = str(result.get("current_node") or "summarize")
            run.status = "completed"
            run.reply_text = reply
            session.commit()

            await send_reply(self._settings, message, reply)
        except Exception as exc:
            logger.exception("Agent run failed")
            run.status = "failed"
            run.reply_text = str(exc)
            session.commit()
            raise
        finally:
            session.close()

    def seed_workstation_health(self) -> None:
        session = self._session_factory()
        existing = session.query(WorkstationHealth).filter_by(tenant_id="default").first()
        if existing is None:
            session.add(
                WorkstationHealth(
                    tenant_id="default",
                    name="thekedar-ws-default",
                    state="sleeping",
                    region="us-central1",
                )
            )
            session.commit()
        session.close()
