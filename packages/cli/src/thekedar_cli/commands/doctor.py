"""Health and credential checks."""

from __future__ import annotations

from typing import Annotated

import httpx
import typer
from thekedar_shared.settings import Settings, get_settings


def doctor_command(
    ingress_url: Annotated[str | None, typer.Option(help="Webhook ingress URL")] = None,
    dashboard_url: Annotated[str | None, typer.Option(help="Dashboard URL")] = None,
) -> None:
    """Validate Thekedar services and integrations."""
    settings = get_settings()
    ingress = ingress_url or settings.webhook_ingress_url
    dashboard = dashboard_url or settings.dashboard_url

    checks: list[tuple[str, bool, str, bool]] = []
    name, ok, detail = _check_http("webhook-ingress /health", f"{ingress.rstrip('/')}/health")
    checks.append((name, ok, detail, True))
    checks.append((*_check_dashboard_auth(dashboard, settings), True))
    checks.append((*_optional("Slack token", _check_slack(settings)), False))
    checks.append((*_optional("Jira API", _check_jira(settings)), False))
    checks.append((*_optional("GitHub token", _check_github(settings)), False))
    bifrost_url = f"{settings.bifrost_url.rstrip('/')}/health"
    checks.append((*_optional("Bifrost", _check_http_bool(bifrost_url)), False))

    failed = 0
    for name, ok, detail, required in checks:
        color = typer.colors.GREEN if ok else typer.colors.RED
        typer.secho(f"{'PASS' if ok else 'FAIL'}  {name}: {detail}", fg=color)
        if not ok and required:
            failed += 1

    if settings.demo_mode:
        typer.secho(
            "Demo mode enabled — mock integrations when tokens missing",
            fg=typer.colors.YELLOW,
        )

    if failed:
        raise typer.Exit(code=1)


def _check_http(name: str, url: str) -> tuple[str, bool, str]:
    ok, detail = _check_http_bool(url)
    return name, ok, detail


def _check_http_bool(url: str) -> tuple[bool, str]:
    try:
        response = httpx.get(url, timeout=5.0)
        return response.status_code == 200, f"HTTP {response.status_code}"
    except httpx.HTTPError as exc:
        return False, str(exc)


def _check_dashboard_auth(dashboard: str, settings: Settings) -> tuple[str, bool, str]:
    try:
        token_resp = httpx.post(
            f"{dashboard.rstrip('/')}/api/v1/auth/token",
            json={"tenant_id": settings.default_tenant_id},
            timeout=5.0,
        )
        if token_resp.status_code != 200:
            return "dashboard auth", False, f"token HTTP {token_resp.status_code}"
        token = token_resp.json()["access_token"]
        widget_resp = httpx.get(
            f"{dashboard.rstrip('/')}/api/v1/widgets/active-runs",
            headers={"Authorization": f"Bearer {token}"},
            timeout=5.0,
        )
        if widget_resp.status_code != 200:
            return "dashboard widgets", False, f"widgets HTTP {widget_resp.status_code}"
        return "dashboard API", True, "auth + widgets OK"
    except httpx.HTTPError as exc:
        return "dashboard API", False, str(exc)


def _optional(name: str, result: tuple[bool, str]) -> tuple[str, bool, str]:
    ok, detail = result
    if detail == "not configured":
        return f"{name} (optional)", True, "skipped"
    return name, ok, detail


def _check_slack(settings: Settings) -> tuple[bool, str]:
    if not settings.slack_bot_token:
        return True, "not configured"
    try:
        response = httpx.post(
            "https://slack.com/api/auth.test",
            headers={"Authorization": f"Bearer {settings.slack_bot_token.get_secret_value()}"},
            timeout=10.0,
        )
        body = response.json()
        return bool(body.get("ok")), body.get("error", "ok")
    except httpx.HTTPError as exc:
        return False, str(exc)


def _check_jira(settings: Settings) -> tuple[bool, str]:
    if not settings.jira_base_url or not settings.jira_email or not settings.jira_api_token:
        return True, "not configured"
    url = f"{settings.jira_base_url.rstrip('/')}/rest/api/3/myself"
    try:
        response = httpx.get(
            url,
            auth=(settings.jira_email, settings.jira_api_token.get_secret_value()),
            timeout=10.0,
        )
        return response.status_code == 200, f"HTTP {response.status_code}"
    except httpx.HTTPError as exc:
        return False, str(exc)


def _check_github(settings: Settings) -> tuple[bool, str]:
    if not settings.github_token:
        return True, "not configured"
    try:
        response = httpx.get(
            "https://api.github.com/user",
            headers={"Authorization": f"Bearer {settings.github_token.get_secret_value()}"},
            timeout=10.0,
        )
        return response.status_code == 200, f"HTTP {response.status_code}"
    except httpx.HTTPError as exc:
        return False, str(exc)
