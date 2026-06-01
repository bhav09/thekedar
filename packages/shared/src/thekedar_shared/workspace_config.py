"""Load workspace definitions from YAML config."""

from __future__ import annotations

import json
from pathlib import Path

import yaml

from thekedar_shared.db import Workspace


def load_workspace_config(path: Path) -> list[dict]:
    if not path.exists():
        return []
    data = yaml.safe_load(path.read_text()) or {}
    workspaces = data.get("workspaces") or []
    if not isinstance(workspaces, list):
        return []
    return [w for w in workspaces if isinstance(w, dict)]


def seed_workspaces_from_config(session_factory, config_path: str) -> int:
    entries = load_workspace_config(Path(config_path))
    if not entries:
        return 0

    session = session_factory()
    count = 0
    try:
        for entry in entries:
            tenant_id = str(entry.get("tenant_id") or "default")
            existing = session.query(Workspace).filter_by(tenant_id=tenant_id).first()
            github_url = entry.get("github_project_url")
            org = str(entry.get("github_org") or "")
            repos = entry.get("github_repos") or []
            
            if github_url:
                from thekedar_shared.workspace import parse_github_url
                parsed = parse_github_url(github_url)
                if parsed:
                    org, repos = parsed

            if existing is None:
                session.add(
                    Workspace(
                        tenant_id=tenant_id,
                        name=str(entry.get("name") or tenant_id),
                        jira_project_key=str(entry.get("jira_project_key") or "THE"),
                        github_org=org,
                        github_repos=json.dumps(repos),
                        github_project_url=github_url,
                        slack_team_id=entry.get("slack_team_id"),
                        whatsapp_phone_number_id=entry.get("whatsapp_phone_number_id"),
                        cloud_workstation_config_id=entry.get("cloud_workstation_config_id"),
                        budget_monthly_usd=float(entry.get("budget_monthly_usd") or 100.0),
                    )
                )
                count += 1
        if count:
            session.commit()
        return count
    finally:
        session.close()
