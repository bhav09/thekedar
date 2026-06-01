"""GitHub REST API client for branch/PR workflow."""

from __future__ import annotations

import logging
from dataclasses import dataclass

import httpx
from thekedar_shared.settings import Settings

logger = logging.getLogger(__name__)


@dataclass
class PullRequestResult:
    number: int
    url: str
    branch: str
    title: str


class GitHubClient:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    @property
    def configured(self) -> bool:
        return self._settings.github_token is not None

    def _headers(self) -> dict[str, str]:
        token = (
            self._settings.github_token.get_secret_value()
            if self._settings.github_token
            else ""
        )
        return {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    async def create_branch(self, repo: str, branch: str, from_ref: str = "main") -> bool:
        if not self.configured:
            logger.info("GitHub mock branch: %s -> %s", repo, branch)
            return True

        async with httpx.AsyncClient(timeout=15.0) as client:
            ref_url = f"https://api.github.com/repos/{repo}/git/ref/heads/{from_ref}"
            ref_resp = await client.get(ref_url, headers=self._headers())
            ref_resp.raise_for_status()
            sha = ref_resp.json()["object"]["sha"]

            create_url = f"https://api.github.com/repos/{repo}/git/refs"
            create_resp = await client.post(
                create_url,
                headers=self._headers(),
                json={"ref": f"refs/heads/{branch}", "sha": sha},
            )
            if create_resp.status_code == 422:
                return True
            create_resp.raise_for_status()
        return True

    async def create_pull_request(
        self,
        repo: str,
        title: str,
        head: str,
        body: str,
        base: str = "main",
    ) -> PullRequestResult:
        if not self.configured:
            url = f"https://github.com/{repo}/pull/1"
            logger.info("GitHub mock PR: %s", url)
            return PullRequestResult(number=1, url=url, branch=head, title=title)

        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                f"https://api.github.com/repos/{repo}/pulls",
                headers=self._headers(),
                json={"title": title, "head": head, "base": base, "body": body},
            )
            response.raise_for_status()
            data = response.json()
        return PullRequestResult(
            number=int(data["number"]),
            url=str(data["html_url"]),
            branch=head,
            title=title,
        )

    async def get_pr_ci_status(self, repo: str, pr_number: int) -> str:
        if not self.configured:
            return "success"
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(
                f"https://api.github.com/repos/{repo}/pulls/{pr_number}",
                headers=self._headers(),
            )
            if response.status_code != 200:
                return "unknown"
            mergeable = response.json().get("mergeable")
        return "success" if mergeable else "pending"
