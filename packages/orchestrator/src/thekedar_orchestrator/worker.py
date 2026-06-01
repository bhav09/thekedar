"""Process inbound queue messages and approval resume events."""

from __future__ import annotations

import logging
import uuid

import redis.asyncio as aioredis
from thekedar_resilience.health_registry import ProviderHealthRegistry
from thekedar_shared.audit import log_message
from thekedar_shared.checkpoint import RunCheckpointStore
from thekedar_shared.db import AgentRun, init_db
from thekedar_shared.observability import bind_log_context, clear_log_context
from thekedar_shared.run_ledger import RunLedger
from thekedar_shared.schemas import Channel, MessageEvent
from thekedar_shared.settings import Settings

from thekedar_orchestrator.approval_commands import parse_approval_command
from thekedar_orchestrator.graph import build_graph
from thekedar_orchestrator.integrations.workstation import WorkstationManager
from thekedar_orchestrator.outbox import deliver_pending
from thekedar_orchestrator.replies import send_reply
from thekedar_orchestrator.services import OrchestratorServices

logger = logging.getLogger(__name__)


class OrchestratorWorker:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._session_factory = init_db(settings.database_url)
        self._services = OrchestratorServices(settings, self._session_factory)
        self._graph = build_graph(self._services)
        self._redis: aioredis.Redis | None = None
        self._checkpoints: RunCheckpointStore | None = None
        self._ledger = RunLedger(self._session_factory)
        self._registry: ProviderHealthRegistry | None = None

    async def process_payload(self, payload: dict) -> None:
        correlation_id = payload.get("correlation_id")
        run_id = str(uuid.uuid4())
        bind_log_context(
            correlation_id=str(correlation_id or ""),
            run_id=str(run_id),
        )
        try:
            if payload.get("type") == "resume":
                await self._process_resume(payload)
                return

            message = MessageEvent.model_validate(payload["message"])
            bind_log_context(tenant_id=message.tenant_id)

            approval_cmd = parse_approval_command(message.text)
            if approval_cmd:
                pending = self._services.resolve_pending_approval(
                    message, approval_cmd.approval_id
                )
                if pending and pending.run_id:
                    await self._process_resume(
                        {
                            "run_id": pending.run_id,
                            "approval_id": pending.id,
                            "decision": approval_cmd.decision,
                            "user_message": approval_cmd.user_message,
                        }
                    )
                    return

            step_id = self._ledger.begin_step(run_id, message.tenant_id, "parse_intent")
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
            self._ledger.complete_step(
                step_id,
                {"message": message.model_dump(mode="json")},
            )

            await self._execute_graph(message, run_id, correlation_id)
        finally:
            clear_log_context()

    async def _process_resume(self, payload: dict) -> None:
        run_id = str(payload.get("run_id") or "")
        approval_id = str(payload.get("approval_id") or "")
        decision = str(payload.get("decision") or "approved")
        user_message = payload.get("user_message")

        session = self._session_factory()
        try:
            run = session.get(AgentRun, run_id)
            tenant_id = run.tenant_id if run else self._settings.default_tenant_id
        finally:
            session.close()

        self._ledger.begin_step(run_id, tenant_id, "resume", approval_id=approval_id)
        result = await self._services.resume_coder_run(
            run_id, approval_id, decision, user_message
        )
        await self._finalize_run(run_id, result)

        session = self._session_factory()
        try:
            run = session.get(AgentRun, run_id)
            if run:
                message = MessageEvent(
                    channel=Channel(run.channel),
                    message_id=run_id,
                    thread_id="",
                    user_id=run.user_id,
                    tenant_id=run.tenant_id,
                    text=run.trigger_text,
                    idempotency_key=f"resume-out:{run_id}",
                )
                reply = str(result.get("reply") or "")
                log_message(session, run.tenant_id, run.channel, "outbound", reply)
                await send_reply(
                    self._settings,
                    message,
                    reply,
                    approval_id=result.get("approval_id"),
                    session=session,
                    run_id=run_id,
                )
                session.commit()
                if self._registry:
                    await deliver_pending(
                        self._session_factory, self._settings, registry=self._registry
                    )
        finally:
            session.close()

    async def _execute_graph(
        self,
        message: MessageEvent,
        run_id: str,
        correlation_id: str | None,
    ) -> None:
        step_id = self._ledger.begin_step(run_id, message.tenant_id, "execute_graph")
        try:
            result = await self._graph.ainvoke(
                {
                    "message": message.model_dump(mode="json"),
                    "run_id": run_id,
                    "correlation_id": correlation_id,
                }
            )
            await self._finalize_run(run_id, result)
            reply = str(result.get("reply") or "")
            session = self._session_factory()
            log_message(session, message.tenant_id, message.channel.value, "outbound", reply)
            await send_reply(
                self._settings,
                message,
                reply,
                approval_id=result.get("approval_id"),
                session=session,
                run_id=run_id,
            )
            session.commit()
            session.close()
            if self._registry:
                await deliver_pending(
                    self._session_factory, self._settings, registry=self._registry
                )
            self._ledger.complete_step(step_id, {"status": result.get("status")})
        except Exception:
            logger.exception("Agent run failed")
            session = self._session_factory()
            run = session.get(AgentRun, run_id)
            if run:
                run.status = "failed"
                session.commit()
            session.close()
            self._ledger.fail_step(step_id, error_class="permanent", error_message="graph failed")
            raise

    async def _finalize_run(self, run_id: str, result: dict) -> None:
        reply = str(result.get("reply") or "")
        workflow = str(result.get("workflow") or "help")
        status = str(result.get("status") or "completed")

        session = self._session_factory()
        run = session.get(AgentRun, run_id)
        if run:
            run.workflow = workflow
            run.current_node = str(result.get("current_node") or "summarize")
            if status == "awaiting_approval":
                run.status = "awaiting_approval"
            elif status == "failed":
                run.status = "failed"
            elif status == "rejected":
                run.status = "rejected"
            else:
                run.status = status if status in ("coding", "report_ready") else "completed"
            run.reply_text = reply
            run.issue_key = result.get("issue_key")
            run.pr_url = result.get("pr_url")
            run.branch_name = result.get("branch_name")
            session.commit()
        session.close()

        if self._redis and self._checkpoints:
            if status == "awaiting_approval":
                await self._checkpoints.save(run_id, result)
            elif status in ("completed", "rejected", "failed"):
                await self._checkpoints.delete(run_id)

    def bind_redis(self, redis: aioredis.Redis) -> None:
        self._redis = redis
        self._checkpoints = RunCheckpointStore(
            redis, session_factory=self._session_factory
        )
        self._registry = ProviderHealthRegistry(self._settings, redis)

    def seed(self) -> None:
        self._services.seed()

    @property
    def session_factory(self):
        return self._session_factory

    async def check_ready(self) -> tuple[bool, str]:
        if self._redis is None:
            return False, "redis not bound"
        try:
            await self._redis.ping()
        except Exception as exc:
            return False, f"redis: {exc}"
        session = self._session_factory()
        try:
            session.execute(__import__("sqlalchemy").text("SELECT 1"))
        except Exception as exc:
            return False, f"postgres: {exc}"
        finally:
            session.close()
        from thekedar_orchestrator.integrations.github_client import GitHubClient

        gh = GitHubClient(self._settings)
        if self._settings.strict_integrations and not await gh.ping():
            return False, "github unreachable"
        return True, "ready"


def run_hibernate_monitor(settings: Settings) -> None:
    session_factory = init_db(settings.database_url)
    manager = WorkstationManager(settings, session_factory)
    count = manager.hibernate_idle()
    logger.info("Hibernated %s workstation(s)", count)
