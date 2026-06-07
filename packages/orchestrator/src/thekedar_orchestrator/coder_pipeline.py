"""M7 coder pipeline — context, impact, plan, code, test, report, publish."""

from __future__ import annotations

import json
import logging
import uuid
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session
from thekedar_context.indexer import RepoIndexer
from thekedar_context.retriever import ContextRetriever
from thekedar_context.schemas import (
    CompletionReport,
    ExecutionPlan,
    GlobalContext,
    ImpactReport,
)
from thekedar_execution.router import ExecutionRouter, ExecutionUnavailable
from thekedar_orchestrator.approval_helpers import create_approval
from thekedar_orchestrator.impact import ImpactAnalyzer
from thekedar_orchestrator.integrations.github_client import GitHubClient
from thekedar_orchestrator.integrations.workstation import WorkstationManager
from thekedar_orchestrator.plan import PlanGenerator
from thekedar_orchestrator.report import ReportGenerator
from thekedar_orchestrator.ticket_utils import extract_issue_key
from thekedar_shared.audit import log_audit, log_cost
from thekedar_shared.db import AgentRun, RunArtifact, TicketCodeLink, Workspace
from thekedar_shared.schemas import Channel, MessageEvent
from thekedar_shared.settings import Settings
from thekedar_shared.workspace import WorkspaceService

logger = logging.getLogger(__name__)

STAGE_IMPACT = "impact"
STAGE_PLAN = "plan"
STAGE_PUBLISH = "publish"


class CoderPipeline:
    def __init__(
        self,
        settings: Settings,
        session_factory,
        github: GitHubClient,
        workstation: WorkstationManager,
    ) -> None:
        self._settings = settings
        self._session_factory = session_factory
        self._github = github
        self._workstation = workstation
        self._retriever = ContextRetriever(settings)
        self._indexer = RepoIndexer()
        self._impact = ImpactAnalyzer(settings, self._retriever)
        self._planner = PlanGenerator()
        self._reporter = ReportGenerator()
        self._execution = ExecutionRouter(settings, workstation)
        self._workspace = WorkspaceService(session_factory)

    def _repo_path(self) -> Path | None:
        if self._settings.local_repo_path:
            return Path(self._settings.local_repo_path)
        return Path.cwd()

    def _with_dashboard(self, text: str) -> str:
        return f"{text}\n\nDashboard: {self._settings.dashboard_url}"

    def _save_artifact(self, session: Session, run_id: str, tenant_id: str, kind: str, data: dict) -> None:
        session.add(
            RunArtifact(
                run_id=run_id,
                tenant_id=tenant_id,
                artifact_type=kind,
                payload_json=json.dumps(data),
            )
        )

    async def run_until_pause(self, message: MessageEvent, workspace: Workspace, run_id: str) -> dict:
        state = await self._advance(
            {
                "message": message.model_dump(mode="json"),
                "run_id": run_id,
                "tenant_id": workspace.tenant_id,
                "repo": self._primary_repo(workspace),
                "issue_key": extract_issue_key(message.text),
                "plan_amendment_count": 0,
            },
            workspace,
        )
        return state

    async def resume(
        self,
        run_id: str,
        approval_id: str,
        decision: str,
        user_message: str | None = None,
    ) -> dict:
        session = self._session_factory()
        try:
            run = session.get(AgentRun, run_id)
            if run is None:
                return {"reply": "Run not found", "status": "failed"}

            from thekedar_shared.db import PendingApproval

            approval = session.get(PendingApproval, approval_id)
            if approval is None:
                return {"reply": "Approval not found", "status": "failed"}

            if approval.status == "rejected":
                return {"reply": "Approval was rejected", "status": "rejected"}

            if approval.status == "pending":
                approval.status = "approved" if decision == "approved" else "rejected"
                session.commit()

            if approval.status != "approved" or decision == "rejected":
                run.status = "rejected"
                session.commit()
                return {
                    "reply": self._with_dashboard(f"Run cancelled at {approval.stage} stage."),
                    "status": "rejected",
                    "workflow": "coder",
                    "current_node": "rejected",
                }

            resume_message = MessageEvent(
                channel=Channel(run.channel),
                message_id=run_id,
                thread_id="",
                user_id=run.user_id,
                tenant_id=run.tenant_id,
                text=run.trigger_text,
                mentioned_agents=["Coder"],
                idempotency_key=f"resume:{run_id}",
            )
            workspace = self._workspace.resolve(resume_message)
            if workspace is None:
                workspace = session.query(Workspace).filter_by(tenant_id=run.tenant_id).first()
            if workspace is None:
                return {"reply": "Workspace not found", "status": "failed"}

            repo = self._primary_repo(workspace)
            ctx = self._retriever.load_global_context(
                session, workspace.tenant_id, repo, run.context_snapshot_id
            )
            if ctx is None:
                return {"reply": "Context snapshot missing", "status": "failed"}

            state: dict[str, Any] = {
                "message": resume_message.model_dump(mode="json"),
                "run_id": run_id,
                "tenant_id": workspace.tenant_id,
                "repo": repo,
                "issue_key": run.issue_key,
                "context_snapshot_id": run.context_snapshot_id,
                "global_context": ctx.model_dump(),
                "branch_name": run.branch_name,
                "user_message": user_message,
                "plan_amendment_count": 0,
            }

            if user_message and "override" in user_message.lower():
                state["override_stale_context"] = True

            if approval.payload_json:
                payload = json.loads(approval.payload_json)
                if approval.stage == STAGE_IMPACT:
                    state["impact_report"] = payload
                    state["resume_from"] = "after_impact"
                elif approval.stage == STAGE_PLAN:
                    state["impact_report"] = self._load_artifact(session, run_id, "impact")
                    state["execution_plan"] = payload
                    state["resume_from"] = "after_plan"
                    
                    if self._settings.environment in ("staging", "prod"):
                        snapshot = self._retriever.latest_snapshot(session, workspace.tenant_id, repo)
                        workstation_sha = await self._workstation.get_git_sha(workspace.tenant_id, repo)
                        if (
                            snapshot
                            and workstation_sha
                            and snapshot.sha != workstation_sha
                            and not state.get("override_stale_context")
                        ):
                            return {
                                "reply": self._with_dashboard(
                                    f"Aborted: Cannot resume. Codebase context is stale! Snapshot SHA ({snapshot.sha[:7]}) "
                                    f"does not match Workstation HEAD ({workstation_sha[:7]}). "
                                    f"To bypass, reply with 'override'."
                                ),
                                "status": "failed",
                            }
                elif approval.stage == STAGE_PUBLISH:
                    state["impact_report"] = self._load_artifact(session, run_id, "impact")
                    state["execution_plan"] = self._load_artifact(session, run_id, "plan")
                    state["completion_report"] = payload
                    state["publish_intent"] = user_message or "create pr"
                    state["resume_from"] = "after_report"

            return await self._advance(state, workspace)
        finally:
            session.close()

    def _load_artifact(self, session: Session, run_id: str, kind: str) -> dict:
        row = (
            session.query(RunArtifact)
            .filter_by(run_id=run_id, artifact_type=kind)
            .order_by(RunArtifact.created_at.desc())
            .first()
        )
        if row is None:
            return {}
        return json.loads(row.payload_json)

    async def _advance(self, state: dict[str, Any], workspace: Workspace) -> dict:
        if state.get("resume_from") == "after_report":
            return await self._node_publish(state, workspace)

        if state.get("resume_from", "start") == "start":
            state = await self._node_load_context(state, workspace)
            if state.get("paused"):
                return state
            state = await self._node_assess_impact(state, workspace)
            if state.get("paused"):
                return state

        if not state.get("execution_plan"):
            state = await self._node_generate_plan(state, workspace)
            if state.get("paused"):
                return state

        if not state.get("coding_result"):
            state = await self._node_execute_coding(state, workspace)
            if state.get("status") == "failed":
                return state

        if not state.get("completion_report"):
            state = await self._node_run_tests_and_report(state, workspace)
            if state.get("paused") or state.get("status") == "failed":
                return state

        if state.get("publish_intent") or state.get("resume_from") == "after_report":
            return await self._node_publish(state, workspace)

        return state

    async def _node_load_context(self, state: dict, workspace: Workspace) -> dict:
        session = self._session_factory()
        try:
            repo = state["repo"]
            tenant_id = state["tenant_id"]
            run_id = state["run_id"]

            snapshot = self._retriever.latest_snapshot(session, tenant_id, repo)
            if self._retriever.needs_refresh(snapshot):
                repo_path = self._repo_path()
                if repo_path and repo_path.is_dir():
                    snapshot = self._indexer.index(session, tenant_id, repo, repo_path)

            ctx = self._retriever.load_global_context(session, tenant_id, repo)
            if ctx is None:
                return {
                    **state,
                    "reply": "Could not load codebase context. Run: thekedar context index",
                    "status": "failed",
                    "workflow": "coder",
                    "current_node": "load_context",
                }

            # Freshness contract: Compare snapshot.sha vs workstation HEAD
            workstation_sha = await self._workstation.get_git_sha(tenant_id, repo)
            staleness_warning = None
            if snapshot and workstation_sha and snapshot.sha != workstation_sha:
                staleness_warning = (
                    f"Warning: Codebase context is stale! Snapshot SHA ({snapshot.sha[:7]}) "
                    f"does not match Workstation HEAD ({workstation_sha[:7]})."
                )

            run = session.get(AgentRun, run_id)
            if run:
                run.context_snapshot_id = ctx.snapshot_id
                run.current_node = "load_context"
                session.commit()

            return {
                **state,
                "context_snapshot_id": ctx.snapshot_id,
                "global_context": ctx.model_dump(),
                "current_node": "assess_impact",
                "staleness_warning": staleness_warning,
            }
        finally:
            session.close()

    async def _node_assess_impact(self, state: dict, workspace: Workspace) -> dict:
        ctx = GlobalContext.model_validate(state["global_context"])
        message = MessageEvent.model_validate(state["message"])
        session = self._session_factory()
        try:
            report = await self._impact.assess_async(
                message.text, ctx, state.get("issue_key"), session=session, run_id=state["run_id"]
            )
            state["impact_report"] = report.model_dump()

            self._save_artifact(session, state["run_id"], state["tenant_id"], "impact", report.model_dump())
            approval = create_approval(
                session,
                tenant_id=state["tenant_id"],
                run_id=state["run_id"],
                approval_type="impact_review",
                stage=STAGE_IMPACT,
                summary=f"Impact review: {report.request_summary[:120]}",
                payload=report.model_dump(),
                channel_reply_token=message.reply_token,
            )
            run = session.get(AgentRun, state["run_id"])
            if run:
                run.status = "awaiting_approval"
                run.current_node = "await_impact"
            log_cost(session, state["tenant_id"], "llm", 0.03, state["run_id"])
            session.commit()
            approval_id = approval.id
        finally:
            session.close()

        summary_text = report.to_chat_summary(self._settings.dashboard_url, state["run_id"])
        if state.get("staleness_warning"):
            summary_text = f"⚠️ {state['staleness_warning']}\n\n" + summary_text
        reply = self._with_dashboard(
            summary_text
            + f"\n\nReply `approve {approval_id}` or use dashboard buttons."
        )
        return {
            **state,
            "reply": reply,
            "approval_id": approval_id,
            "awaiting_stage": STAGE_IMPACT,
            "paused": True,
            "status": "awaiting_approval",
            "workflow": "coder",
            "current_node": "await_impact",
        }

    async def _node_generate_plan(self, state: dict, workspace: Workspace) -> dict:
        user_msg = state.get("user_message") or ""
        impact = ImpactReport.model_validate(state["impact_report"])
        ctx = GlobalContext.model_validate(state["global_context"])

        plan = ExecutionPlan.model_validate(state["execution_plan"]) if state.get("execution_plan") else None
        if plan is None:
            require_files = self._settings.environment in ("staging", "prod") or (
                self._settings.strict_integrations
            )
            plan = self._planner.generate(
                state["message"]["text"],
                ctx,
                impact,
                state.get("issue_key"),
                require_files=require_files,
            )

        if user_msg and self._planner.is_amendment(user_msg):
            count = int(state.get("plan_amendment_count") or 0)
            if count < 3:
                plan = self._planner.apply_amendment(plan, user_msg)
                state["plan_amendment_count"] = count + 1

        message = MessageEvent.model_validate(state["message"])
        session = self._session_factory()
        try:
            self._save_artifact(session, state["run_id"], state["tenant_id"], "plan", plan.model_dump())
            approval = create_approval(
                session,
                tenant_id=state["tenant_id"],
                run_id=state["run_id"],
                approval_type="plan_review",
                stage=STAGE_PLAN,
                summary=f"Plan: {plan.summary[:120]}",
                payload=plan.model_dump(),
                channel_reply_token=message.reply_token,
            )
            run = session.get(AgentRun, state["run_id"])
            if run:
                run.status = "awaiting_approval"
                run.current_node = "await_plan"
                run.branch_name = plan.branch_name
            log_cost(session, state["tenant_id"], "llm", 0.02, state["run_id"])
            session.commit()
            approval_id = approval.id
        finally:
            session.close()

        summary_text = plan.to_chat_summary(self._settings.dashboard_url, state["run_id"])
        if state.get("staleness_warning"):
            summary_text = f"⚠️ {state['staleness_warning']}\n\n" + summary_text
        reply = self._with_dashboard(summary_text)
        return {
            **state,
            "execution_plan": plan.model_dump(),
            "reply": reply,
            "approval_id": approval_id,
            "awaiting_stage": STAGE_PLAN,
            "paused": True,
            "status": "awaiting_approval",
            "workflow": "coder",
            "current_node": "await_plan",
            "branch_name": plan.branch_name,
        }

    async def _node_execute_coding(self, state: dict, workspace: Workspace) -> dict:
        iterations = state.get("coding_iterations", 0) + 1
        state["coding_iterations"] = iterations
        if iterations > self._settings.max_coding_iterations:
            return {
                **state,
                "reply": self._with_dashboard(f"Aborted: exceeded maximum coding iterations ({self._settings.max_coding_iterations})"),
                "status": "failed",
                "workflow": "coder",
                "current_node": "execute_coding",
            }

        plan = ExecutionPlan.model_validate(state["execution_plan"])
        ctx = GlobalContext.model_validate(state["global_context"])
        branch = plan.branch_name

        # Check environment and SHA mismatch (SHA gate)
        session = self._session_factory()
        try:
            repo = state["repo"]
            tenant_id = state["tenant_id"]
            snapshot = self._retriever.latest_snapshot(session, tenant_id, repo)
            workstation_sha = await self._workstation.get_git_sha(tenant_id, repo)
            
            if (
                self._settings.environment in ("staging", "prod")
                and snapshot
                and workstation_sha
                and snapshot.sha != workstation_sha
                and not state.get("override_stale_context")
            ):
                return {
                    **state,
                    "reply": self._with_dashboard(
                        f"Aborted: Codebase context is stale! Snapshot SHA ({snapshot.sha[:7]}) "
                        f"does not match Workstation HEAD ({workstation_sha[:7]}). "
                        f"Please re-index your context or reply with 'override' to bypass."
                    ),
                    "status": "failed",
                    "workflow": "coder",
                    "current_node": "execute_coding",
                }
        finally:
            session.close()

        session = self._session_factory()
        try:
            run = session.get(AgentRun, state["run_id"])
            if run:
                run.status = "coding"
                run.current_node = "execute_coding"
                session.commit()
        finally:
            session.close()

        await self._workstation.ensure_ready(workspace.tenant_id, workspace.cloud_workstation_config_id)
        pre_test = await self._workstation.sync_repo_and_test(workspace.tenant_id, state["run_id"])
        if pre_test.status != "passed":
            return {
                **state,
                "reply": self._with_dashboard(f"Aborted: baseline tests failed — {pre_test.summary}"),
                "status": "failed",
                "workflow": "coder",
                "current_node": "sync_repo",
            }

        try:
            executor = self._execution.select(workspace)
        except ExecutionUnavailable as exc:
            return {
                **state,
                "reply": self._with_dashboard(str(exc)),
                "status": "failed",
                "workflow": "coder",
                "current_node": "select_executor",
            }

        coding = await executor.run_coding(plan, ctx, branch, state["run_id"])
        state["coding_result"] = {
            "success": coding.success,
            "summary": coding.summary,
            "files_changed": coding.files_changed,
            "tests_added": coding.tests_added,
            "tests_updated": coding.tests_updated,
            "commits_ahead": coding.commits_ahead,
            "error": coding.error,
        }
        state["current_node"] = "run_tests"
        state["branch_name"] = branch
        return state

    async def _node_run_tests_and_report(self, state: dict, workspace: Workspace) -> dict:
        plan = ExecutionPlan.model_validate(state["execution_plan"])
        impact = ImpactReport.model_validate(state["impact_report"])
        from thekedar_ide_adapters import CodingResult

        coding = CodingResult(**state["coding_result"])

        try:
            executor = self._execution.select(workspace)
            test_status, test_summary = await executor.run_tests(workspace.tenant_id, state["run_id"])
        except ExecutionUnavailable:
            test_status, test_summary = "failed", "No executor"

        session = self._session_factory()
        try:
            from thekedar_shared.db import TestRunRecord

            session.add(
                TestRunRecord(
                    tenant_id=state["tenant_id"],
                    run_id=state["run_id"],
                    status=test_status,
                    summary=test_summary[:2000],
                )
            )
            log_cost(session, state["tenant_id"], "compute", 0.2, state["run_id"])
            session.commit()
        finally:
            session.close()

        if not coding.success or coding.commits_ahead <= 0:
            return {
                **state,
                "reply": self._with_dashboard(
                    "Coding finished but no commits were produced. Publish blocked."
                ),
                "status": "failed",
                "workflow": "coder",
                "current_node": "coding_failed",
            }

        if test_status != "passed":
            return {
                **state,
                "reply": self._with_dashboard(f"Tests failed — publish blocked.\n{test_summary[:500]}"),
                "status": "failed",
                "workflow": "coder",
                "current_node": "tests_failed",
            }

        compare_url = f"https://github.com/{state['repo']}/compare/main...{plan.branch_name}"
        report = self._reporter.generate(
            plan,
            impact,
            coding,
            test_status,
            test_summary,
            cost_usd=0.25,
            compare_url=compare_url,
        )
        state["completion_report"] = report.model_dump()

        message = MessageEvent.model_validate(state["message"])
        session = self._session_factory()
        try:
            self._save_artifact(
                session, state["run_id"], state["tenant_id"], "report", report.model_dump()
            )
            approval = create_approval(
                session,
                tenant_id=state["tenant_id"],
                run_id=state["run_id"],
                approval_type="publish_review",
                stage=STAGE_PUBLISH,
                summary=f"Publish: {report.summary[:120]}",
                payload=report.model_dump(),
                channel_reply_token=message.reply_token,
            )
            run = session.get(AgentRun, state["run_id"])
            if run:
                run.status = "report_ready"
                run.current_node = "await_publish"
            session.commit()
            approval_id = approval.id
        finally:
            session.close()

        reply = self._with_dashboard(
            report.to_chat_summary(self._settings.dashboard_url, state["run_id"])
        )
        return {
            **state,
            "reply": reply,
            "approval_id": approval_id,
            "awaiting_stage": STAGE_PUBLISH,
            "paused": True,
            "status": "awaiting_approval",
            "workflow": "coder",
            "current_node": "await_publish",
        }

    async def _node_publish(self, state: dict, workspace: Workspace) -> dict:
        from thekedar_orchestrator.policy_gate import enforce_mcp_policy, PolicyViolation

        plan = ExecutionPlan.model_validate(state["execution_plan"])
        report = CompletionReport.model_validate(state["completion_report"])
        intent = (state.get("publish_intent") or state.get("user_message") or "create pr").lower()
        repo = state["repo"]
        branch = plan.branch_name
        issue_key = state.get("issue_key") or "TASK"

        try:
            enforce_mcp_policy(self._settings, "github", "create_branch", {"repo": repo, "branch": branch})
            if "push" not in intent or "pr" in intent:
                enforce_mcp_policy(self._settings, "github", "create_pull_request", {"repo": repo, "branch": branch})
        except PolicyViolation as exc:
            session = self._session_factory()
            try:
                run = session.get(AgentRun, state["run_id"])
                if run:
                    run.status = "failed"
                    run.current_node = "publish_failed"
                session.commit()
            finally:
                session.close()
            return {
                **state,
                "reply": f"Publish blocked by policy constraint: {exc}",
                "status": "failed",
                "workflow": "coder",
                "current_node": "publish_failed",
            }

        await self._github.create_branch(repo, branch)

        pr_url = None
        if "push" in intent and "pr" not in intent:
            action = f"Pushed branch `{branch}`"
        else:
            pr_body = (
                f"## Thekedar automated PR\n\n{report.summary}\n\n"
                f"Tests: {report.tests_passed} passed\n"
                f"Modules: {', '.join(report.modules_changed)}\n\n"
                f"Review diff in GitHub — not in chat."
            )
            pr = await self._github.create_pull_request(
                repo,
                f"{issue_key}: {plan.summary[:80]}",
                branch,
                pr_body,
            )
            pr_url = pr.url
            action = f"PR created: {pr.url}"

        session = self._session_factory()
        try:
            message = MessageEvent.model_validate(state["message"])
            self._upsert_ticket_link(
                session,
                workspace.tenant_id,
                issue_key,
                plan.summary,
                "In Review",
                branch_name=branch,
                pr_url=pr_url,
                pr_number=1 if pr_url else None,
            )
            log_audit(session, workspace.tenant_id, message.user_id, "github.publish", branch)
            run = session.get(AgentRun, state["run_id"])
            if run:
                run.status = "completed"
                run.current_node = "published"
                run.pr_url = pr_url
                run.branch_name = branch
            session.commit()
        finally:
            session.close()

        reply = self._with_dashboard(
            f"*Published*\n{action}\nBranch: `{branch}`\nCommits: {report.commits_ahead}"
        )
        return {
            **state,
            "reply": reply,
            "pr_url": pr_url,
            "status": "completed",
            "workflow": "coder",
            "current_node": "published",
            "issue_key": issue_key,
        }

    def _primary_repo(self, workspace: Workspace) -> str:
        import json

        repos = json.loads(workspace.github_repos or "[]")
        if not repos:
            return workspace.github_org
        return f"{workspace.github_org}/{repos[0]}" if workspace.github_org else repos[0]

    def _upsert_ticket_link(
        self,
        session: Session,
        tenant_id: str,
        issue_key: str,
        summary: str,
        status: str,
        *,
        branch_name: str | None = None,
        pr_url: str | None = None,
        pr_number: int | None = None,
    ) -> TicketCodeLink:
        link = (
            session.query(TicketCodeLink)
            .filter_by(tenant_id=tenant_id, issue_key=issue_key)
            .first()
        )
        if link is None:
            link = TicketCodeLink(tenant_id=tenant_id, issue_key=issue_key)
            session.add(link)
        link.issue_summary = summary
        link.issue_status = status
        if branch_name:
            link.branch_name = branch_name
        if pr_url:
            link.pr_url = pr_url
        if pr_number:
            link.pr_number = pr_number
        return link
