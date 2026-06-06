"""Jira Cloud REST client (Atlassian Rovo MCP-compatible API surface)."""

from __future__ import annotations

import logging
from dataclasses import dataclass

import httpx
from thekedar_shared.exceptions import IntegrationError
from thekedar_shared.prod_validation import allows_demo_mocks
from thekedar_shared.settings import Settings

logger = logging.getLogger(__name__)


@dataclass
class JiraIssue:
    key: str
    summary: str
    status: str


class JiraClient:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    @property
    def configured(self) -> bool:
        return bool(
            self._settings.jira_base_url
            and self._settings.jira_email
            and self._settings.jira_api_token
        )

    def _require_configured(self) -> None:
        if not self.configured:
            if allows_demo_mocks(self._settings):
                return
            raise IntegrationError(
                "jira",
                "Jira credentials not configured — set JIRA_* env vars",
            )

    def _auth(self) -> tuple[str, str] | None:
        if not self.configured or not self._settings.jira_api_token:
            return None
        return (self._settings.jira_email or "", self._settings.jira_api_token.get_secret_value())

    async def search(self, jql: str, max_results: int = 10) -> list[JiraIssue]:
        self._require_configured()
        if not self.configured:
            return [
                JiraIssue(key="THE-1", summary="Auth epic (mock)", status="In Progress"),
                JiraIssue(key="THE-42", summary="Login bug (mock)", status="To Do"),
            ]

        from thekedar_resilience.retry import with_retry

        @with_retry(self._settings.provider_retry_max)
        async def _search() -> list[JiraIssue]:
            url = f"{self._settings.jira_base_url.rstrip('/')}/rest/api/3/search/jql"
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(
                    url,
                    auth=self._auth(),
                    json={"jql": jql, "maxResults": max_results, "fields": ["summary", "status"]},
                )
                response.raise_for_status()
                data = response.json()

            issues: list[JiraIssue] = []
            for item in data.get("issues") or []:
                fields = item.get("fields") or {}
                status = (fields.get("status") or {}).get("name") or "Unknown"
                issues.append(
                    JiraIssue(
                        key=str(item.get("key") or ""),
                        summary=str(fields.get("summary") or ""),
                        status=status,
                    )
                )
            return issues

        return await _search()

    async def create_issue(
        self,
        project_key: str,
        summary: str,
        description: str = "",
        issue_type: str = "Task",
    ) -> JiraIssue:
        self._require_configured()
        if not self.configured:
            key = f"{project_key}-999"
            logger.info("Jira mock create: %s — %s", key, summary)
            return JiraIssue(key=key, summary=summary, status="To Do")

        from thekedar_resilience.retry import with_retry

        @with_retry(self._settings.provider_retry_max)
        async def _create() -> JiraIssue:
            url = f"{self._settings.jira_base_url.rstrip('/')}/rest/api/3/issue"
            payload = {
                "fields": {
                    "project": {"key": project_key},
                    "summary": summary,
                    "description": {
                        "type": "doc",
                        "version": 1,
                        "content": [
                            {
                                "type": "paragraph",
                                "content": [{"type": "text", "text": description or summary}],
                            }
                        ],
                    },
                    "issuetype": {"name": issue_type},
                }
            }
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(url, auth=self._auth(), json=payload)
                response.raise_for_status()
                key = response.json().get("key", "")
            return JiraIssue(key=key, summary=summary, status="To Do")

        return await _create()

    async def get_issue(self, issue_key: str) -> JiraIssue | None:
        results = await self.search(f'key = "{issue_key}"', max_results=1)
        return results[0] if results else None
