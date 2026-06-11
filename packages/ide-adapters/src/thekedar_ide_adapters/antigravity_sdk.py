"""Google Antigravity SDK adapter."""

from __future__ import annotations

import base64
import json
import logging
from pathlib import Path
from typing import Any

from thekedar_context.schemas import ExecutionPlan, GlobalContext
from thekedar_ide_adapters.base import checkout_branch, repo_path
from thekedar_ide_adapters import CodingResult
from thekedar_ide_adapters.mock import MockIDEAdapter
from thekedar_ide_adapters.prompt import build_ide_prompt, post_run_metrics
from thekedar_shared.settings import Settings
from thekedar_shared.exceptions import ConfigurationError

logger = logging.getLogger(__name__)

# Try to import SDK - preview status
SDK_AVAILABLE = False
try:
    from google.antigravity import Agent, LocalAgentConfig
    from google.antigravity.hooks.policy import allow, ask_user, deny
    SDK_AVAILABLE = True
except ImportError:
    Agent = None  # type: ignore
    LocalAgentConfig = None  # type: ignore
    deny = None  # type: ignore
    allow = None  # type: ignore
    ask_user = None  # type: ignore


class AntigravitySdkAdapter:
    """Agent runtime built atop the google-antigravity Python SDK."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._fallback = MockIDEAdapter(settings)

    async def healthcheck(self) -> bool:
        return SDK_AVAILABLE

    async def run_task(
        self, plan: ExecutionPlan, context: GlobalContext, branch: str
    ) -> CodingResult:
        repo = repo_path(self._settings, tenant_id=context.tenant_id, repo=context.repo)
        if repo is None:
            return CodingResult(success=False, summary="No repo", error="missing repo path")

        if not await self.healthcheck():
            if self._settings.environment in ("staging", "prod"):
                raise ConfigurationError(
                    "google-antigravity SDK not importable on remote VM - check bootstrap"
                )
            logger.warning("Antigravity SDK not importable locally - using mock adapter")
            return await self._fallback.run_task(plan, context, branch)

        checkout_branch(repo, branch)

        # 1. Build bounded prompt
        prompt = build_ide_prompt(plan, context, branch)

        # 2. Set up policies
        policies = [
            deny("*"),
            allow("view_file"),
            allow("edit_file"),
            allow("search_directory"),
        ]

        # In staging/prod, force command executions to require human-in-the-loop approvals
        if self._settings.environment in ("staging", "prod"):
            policies.append(ask_user("run_command", handler=self._approval_handler))
        else:
            policies.append(allow("run_command"))

        # 3. Formulate custom retrieval tool (In-Process dynamic Layer 1)
        def search_codebase_context(query: str, chunk_types: list[str] | None = None) -> str:
            """Query the indexed codebase Context Index for symbols, documents, and security details."""
            from thekedar_shared.db import init_db
            from thekedar_context.retriever import ContextRetriever
            from thekedar_context.schemas import ContextQuery

            session_factory = init_db(self._settings.database_url)
            session = session_factory()
            try:
                retriever = ContextRetriever(self._settings)
                query_obj = ContextQuery(
                    tenant_id=context.tenant_id,
                    repo=context.repo,
                    keywords=[query],
                    chunk_types=chunk_types or [],
                )
                hits = retriever.query(session, query_obj)
                max_results = self._settings.context_retval_max_results
                return json.dumps(hits[:max_results], indent=2)
            except Exception as err:
                logger.error("Context retrieval tool error: %s", err)
                return f"Error retrieving context: {str(err)}"
            finally:
                session.close()

        # 4. Construct MCP configurations
        from thekedar_shared.mcp_registry import McpRegistry
        mcp_registry = McpRegistry(self._settings)
        mcp_servers = []

        # Connect Context MCP server
        mcp_servers.append({
            "name": "thekedar-context-mcp",
            "command": "python",
            "args": ["-m", "thekedar_context.context_mcp"],
        })

        # Connect GitHub MCP if enabled
        if self._settings.github_mcp_enabled:
            github_client_cfg = mcp_registry.get_bifrost_client_config(context.tenant_id, "github")
            if github_client_cfg:
                mcp_servers.append({
                    "name": "github",
                    "url": github_client_cfg.get("connection_string"),
                    "headers": github_client_cfg.get("headers", {}),
                })

        # 5. Build agent configuration
        config = LocalAgentConfig(
            system_instructions=(
                "You are an elite automated codebase developer. Resolve the requested plan "
                "safely and thoroughly. Run tests to confirm modifications. Write concise, correct code."
            ),
            workspace_path=str(repo),
            policies=policies,
            mcp_servers=mcp_servers,
            tools=[search_codebase_context],
        )

        agent = Agent(config)

        # 6. Stream and inspect execution hooks
        if self._settings.antigravity_stream_events:
            @agent.hook("on_step")
            def stream_agent_events(step_info: Any) -> None:
                # Log step information/reasoning to websocket or run artifacts database
                try:
                    from thekedar_shared.db import init_db, RunArtifact
                    session_factory = init_db(self._settings.database_url)
                    session = session_factory()
                    try:
                        artifact = RunArtifact(
                            run_id=context.snapshot_id,
                            tenant_id=context.tenant_id,
                            artifact_type="agent_step",
                            payload_json=json.dumps({
                                "step": getattr(step_info, "name", "step"),
                                "thought": getattr(step_info, "thought", ""),
                                "tool_calls": getattr(step_info, "tool_calls", []),
                            })
                        )
                        session.add(artifact)
                        session.commit()
                    finally:
                        session.close()
                except Exception as ev_err:
                    logger.warning("Failed to log streamed agent step event: %s", ev_err)

        # 7. Execute coding run
        try:
            result = await agent.run(prompt)
            if not result.success:
                return CodingResult(
                    success=False,
                    summary="Antigravity SDK run finished with failure status",
                    error=result.error or "Unknown SDK error",
                )
        except Exception as exec_err:
            logger.exception("Antigravity SDK runtime exception occurred")
            return CodingResult(
                success=False,
                summary="Antigravity SDK execution aborted due to exception",
                error=str(exec_err),
            )

        return post_run_metrics(repo, branch, success=True, summary=f"Antigravity SDK completed on {branch}")

    def _approval_handler(self, command: str, context_details: Any) -> bool:
        """Mid-run safety policy approval bridge to Slack/WhatsApp thread."""
        from thekedar_shared.db import init_db, PendingApproval
        from thekedar_orchestrator.policy_gate import is_destructive_command
        from datetime import datetime, UTC
        session_factory = init_db(self._settings.database_url)
        session = session_factory()
        
        is_dest = is_destructive_command(command)
        summary = f"Agent requested command execution: `{command}`"
        if is_dest:
            summary = f"🚨 WARNING: DESTRUCTIVE Command requested: `{command}`"

        try:
            # Create a mid-run pending approval
            approval = PendingApproval(
                tenant_id=self._settings.default_tenant_id,
                approval_type="tool_review",
                stage="coding",
                summary=summary,
                payload_json=json.dumps({"command": command, "destructive": is_dest}),
                status="pending",
                created_at=datetime.now(UTC),
            )
            session.add(approval)
            session.commit()
            approval_id = approval.id
        finally:
            session.close()

        # Block synchronously or poll database until user responds
        import time
        import anyio
        timeout_limit = 900  # 15 minutes timeout limit
        elapsed = 0

        logger.info("Antigravity SDK agent paused, awaiting command approval: %s", command)
        while elapsed < timeout_limit:
            time.sleep(5)
            elapsed += 5

            session = session_factory()
            try:
                row = session.get(PendingApproval, approval_id)
                if row:
                    if row.status == "approved":
                        logger.info("Command execution approved mid-run: %s", command)
                        return True
                    elif row.status == "rejected":
                        logger.warning("Command execution rejected mid-run: %s", command)
                        return False
            except Exception as e:
                logger.error("Error checking mid-run tool approval status: %s", e)
            finally:
                session.close()

        logger.warning("Mid-run tool approval timed out after 15 minutes - command denied")
        return False
