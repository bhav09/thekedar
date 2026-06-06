"""Core orchestration logic for M3–M5 workflows."""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session
from thekedar_shared.audit import log_audit, log_cost, log_message
from thekedar_shared.db import AgentRun, PendingApproval, TicketCodeLink, Workspace
from thekedar_shared.schemas import MessageEvent
from thekedar_shared.settings import Settings
from thekedar_shared.workspace import WorkspaceService

from thekedar_orchestrator.coder_pipeline import CoderPipeline
from thekedar_orchestrator.integrations.github_client import GitHubClient
from thekedar_orchestrator.integrations.jira_client import JiraClient
from thekedar_orchestrator.integrations.workstation import WorkstationManager
from thekedar_orchestrator.ticket_utils import extract_issue_key

logger = logging.getLogger(__name__)


class OrchestratorServices:
    def __init__(self, settings: Settings, session_factory) -> None:
        self._settings = settings
        self._session_factory = session_factory
        self._workspace = WorkspaceService(session_factory)
        self._jira = JiraClient(settings)
        self._github = GitHubClient(settings)
        self._workstation = WorkstationManager(settings, session_factory)
        self._coder = CoderPipeline(settings, session_factory, self._github, self._workstation)

    def seed(self) -> None:
        self._workspace.seed_defaults()

    def _with_dashboard(self, text: str) -> str:
        return f"{text}\n\nDashboard: {self._settings.dashboard_url}"

    async def run(
        self,
        message: MessageEvent,
        workflow: str,
        run_id: str,
        correlation_id: str | None,
    ) -> dict:
        session = self._session_factory()
        try:
            log_message(
                session,
                message.tenant_id,
                message.channel.value,
                "inbound",
                message.text,
            )
            session.commit()
        finally:
            session.close()

        workspace = self._workspace.resolve(message)
        if workspace is None:
            return {
                "workflow": workflow,
                "reply": (
                    "Unknown workspace. Contact admin to register your "
                    "Slack team or WhatsApp number."
                ),
                "current_node": "resolve_workspace",
            }

        if workflow == "architect":
            return await self._run_architect(message, workspace, run_id)
        if workflow == "coder":
            return await self.run_coder_pipeline(message, run_id, correlation_id)
        if workflow == "status":
            return await self._run_status(message, workspace)
        return self._help_reply()

    async def _run_architect(
        self, message: MessageEvent, workspace: Workspace, run_id: str
    ) -> dict:
        text = message.text.lower()
        session = self._session_factory()
        try:
            if ("create" in text and "epic" in text) or "create issue" in text:
                summary = message.text.split(":", 1)[-1].strip()[:120] or "New task from Thekedar"
                issue = await self._jira.create_issue(workspace.jira_project_key, summary)
                self._upsert_ticket_link(
                    session, workspace.tenant_id, issue.key, issue.summary, issue.status
                )
                log_audit(session, workspace.tenant_id, message.user_id, "jira.create", issue.key)
                log_cost(session, workspace.tenant_id, "llm", 0.02, run_id)
                session.commit()
                return {
                    "workflow": "architect",
                    "reply": self._with_dashboard(f"Created {issue.key}: {issue.summary}"),
                    "current_node": "jira_create",
                    "issue_key": issue.key,
                }

            issue_key = extract_issue_key(message.text)
            if issue_key:
                issue = await self._jira.get_issue(issue_key)
                if issue:
                    self._upsert_ticket_link(
                        session, workspace.tenant_id, issue.key, issue.summary, issue.status
                    )
                    session.commit()
                    return {
                        "workflow": "architect",
                        "reply": f"{issue.key}: {issue.summary} [{issue.status}]",
                        "current_node": "jira_query",
                        "issue_key": issue.key,
                    }

            jql = (
                f'project = "{workspace.jira_project_key}" '
                'AND status != Done ORDER BY updated DESC'
            )
            issues = await self._jira.search(jql, max_results=5)
            lines = [f"• {i.key}: {i.summary} ({i.status})" for i in issues]
            for issue in issues:
                self._upsert_ticket_link(
                    session, workspace.tenant_id, issue.key, issue.summary, issue.status
                )
            log_cost(session, workspace.tenant_id, "llm", 0.01, run_id)
            session.commit()
            return {
                "workflow": "architect",
                "reply": self._with_dashboard("Open issues:\n" + "\n".join(lines)),
                "current_node": "jira_search",
            }
        finally:
            session.close()

    async def run_coder_pipeline(
        self,
        message: MessageEvent,
        run_id: str,
        correlation_id: str | None,
    ) -> dict:
        workspace = self._workspace.resolve(message)
        if workspace is None:
            return {
                "workflow": "coder",
                "reply": (
                    "Unknown workspace. Contact admin to register your "
                    "Slack team or WhatsApp number."
                ),
                "current_node": "resolve_workspace",
            }

        issue_key = extract_issue_key(message.text)
        if not issue_key:
            return {
                "workflow": "coder",
                "reply": "Please include a Jira issue key (e.g. THE-42) for @Coder tasks.",
                "current_node": "parse_issue",
            }

        session = self._session_factory()
        try:
            run = session.get(AgentRun, run_id)
            if run:
                run.workflow = "coder"
                run.issue_key = issue_key
                session.commit()
        finally:
            session.close()

        return await self._coder.run_until_pause(message, workspace, run_id)

    async def resume_coder_run(
        self,
        run_id: str,
        approval_id: str,
        decision: str,
        user_message: str | None = None,
    ) -> dict:
        return await self._coder.resume(run_id, approval_id, decision, user_message)

    def resolve_pending_approval(
        self, message: MessageEvent, approval_id: str | None
    ) -> PendingApproval | None:
        workspace = self._workspace.resolve(message)
        if workspace is None:
            return None
        session = self._session_factory()
        try:
            if approval_id:
                item = session.get(PendingApproval, approval_id)
                if (
                    item
                    and item.tenant_id == workspace.tenant_id
                    and item.status == "pending"
                ):
                    return item
                return None
            return (
                session.query(PendingApproval)
                .filter_by(tenant_id=workspace.tenant_id, status="pending")
                .filter(
                    PendingApproval.approval_type.in_(
                        ("impact_review", "plan_review", "publish_review")
                    )
                )
                .order_by(PendingApproval.created_at.desc())
                .first()
            )
        finally:
            session.close()

    async def _run_status(self, message: MessageEvent, workspace: Workspace) -> dict:
        session = self._session_factory()
        try:
            from thekedar_shared.db import AgentRun, WorkstationHealth

            runs = (
                session.query(AgentRun)
                .filter_by(tenant_id=workspace.tenant_id)
                .order_by(AgentRun.created_at.desc())
                .limit(3)
                .all()
            )
            ws = session.query(WorkstationHealth).filter_by(tenant_id=workspace.tenant_id).first()
            ws_state = ws.state if ws else "unknown"
            run_lines = [f"• {r.workflow} [{r.status}] {r.trigger_text[:60]}" for r in runs]
            body = f"Workstation: {ws_state}\nRecent runs:\n" + ("\n".join(run_lines) or "none")
            return {
                "workflow": "status",
                "reply": self._with_dashboard(body),
                "current_node": "status",
            }
        finally:
            session.close()

    def _help_reply(self) -> dict:
        return {
            "workflow": "help",
            "reply": (
                "Thekedar agents:\n"
                "• @Architect — Jira query/create\n"
                "• @Coder — context → impact → plan → code → report (include TICKET-123)\n"
                "• @Status — dashboard snapshot\n"
                "• Reply `approve` / `reject` or `create pr` to continue pending runs\n"
                f"Dashboard: {self._settings.dashboard_url}"
            ),
            "current_node": "summarize",
        }

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
        ci_status: str = "pending",
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
        link.ci_status = ci_status
        return link
