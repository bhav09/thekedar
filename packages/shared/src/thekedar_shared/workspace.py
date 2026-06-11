"""Workspace resolution and seed data."""

from __future__ import annotations

import json
from pathlib import Path

from thekedar_shared.db import Workspace
from thekedar_shared.schemas import Channel, MessageEvent
from thekedar_shared.settings import get_settings
from thekedar_shared.workspace_config import seed_workspaces_from_config


class WorkspaceService:
    def __init__(self, session_factory) -> None:
        self._session_factory = session_factory

    def resolve(self, message: MessageEvent) -> Workspace | None:
        session = self._session_factory()
        try:
            ws = None
            if message.channel == Channel.SLACK:
                ws = session.query(Workspace).filter_by(slack_team_id=message.tenant_id).first()
            elif message.channel == Channel.WHATSAPP:
                ws = (
                    session.query(Workspace)
                    .filter_by(whatsapp_phone_number_id=message.tenant_id)
                    .first()
                )
            if ws is None:
                ws = session.query(Workspace).filter_by(tenant_id=message.tenant_id).first()
            return ws
        finally:
            session.close()

    def seed_defaults(self) -> None:
        settings = get_settings()
        config_path = Path(settings.workspace_config_path)
        if config_path.exists():
            seed_workspaces_from_config(self._session_factory, settings.workspace_config_path)
            return

        if settings.environment != "local" or not settings.allow_default_seed:
            return

        session = self._session_factory()
        try:
            if session.query(Workspace).count() == 0:
                session.add(
                    Workspace(
                        tenant_id="default",
                        name="Default Workspace",
                        jira_project_key="THE",
                        github_org="thekedar",
                        github_repos=json.dumps(["thekedar"]),
                        slack_team_id="T001",
                        whatsapp_phone_number_id="PN123",
                        cloud_workstation_config_id="thekedar-ws-default",
                        budget_monthly_usd=100.0,
                    )
                )
                session.commit()
        finally:
            session.close()

    def primary_repo(self, workspace: Workspace) -> str:
        repos = json.loads(workspace.github_repos or "[]")
        if not repos:
            return workspace.github_org
        return f"{workspace.github_org}/{repos[0]}" if workspace.github_org else repos[0]


import re

def parse_github_url(url: str | None) -> tuple[str, list[str]] | None:
    if not url:
        return None
    url = url.strip()
    match = re.search(r"github\.com[:/]([^/]+)/([^/]+?)(?:\.git|/)?$", url, re.IGNORECASE)
    if match:
        org = match.group(1)
        repo = match.group(2)
        return org, [repo]
    return None
