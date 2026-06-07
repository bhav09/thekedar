"""Health and credential checks."""

from __future__ import annotations

from typing import Annotated

import httpx
import typer
from thekedar_shared.prod_validation import validate_production_settings
from thekedar_shared.settings import Settings, get_settings


def doctor_command(
    ingress_url: Annotated[str | None, typer.Option(help="Webhook ingress URL")] = None,
    dashboard_url: Annotated[str | None, typer.Option(help="Dashboard URL")] = None,
    strict: Annotated[
        bool, typer.Option("--strict", help="Fail if prod integrations unhealthy")
    ] = False,
) -> None:
    """Validate Thekedar services and integrations."""
    settings = get_settings()
    ingress = ingress_url or settings.webhook_ingress_url
    dashboard = dashboard_url or settings.dashboard_url

    checks: list[tuple[str, bool, str, bool]] = []
    name, ok, detail = _check_http("webhook-ingress /health", f"{ingress.rstrip('/')}/health")
    checks.append((name, ok, detail, True))
    ready_name, ready_ok, ready_detail = _check_http(
        "webhook-ingress /ready", f"{ingress.rstrip('/')}/ready"
    )
    checks.append((ready_name, ready_ok, ready_detail, strict))
    checks.append((*_check_dashboard_auth(dashboard, settings), True))
    checks.append((*_integration_check("Slack token", _check_slack(settings), settings, strict), strict))
    checks.append((*_integration_check("Jira API", _check_jira(settings), settings, strict), strict))
    checks.append((*_integration_check("GitHub token", _check_github(settings), settings, strict), strict))
    bifrost_url = f"{settings.bifrost_url.rstrip('/')}/health"
    checks.append((*_optional("Bifrost", _check_http_bool(bifrost_url)), False))
    checks.append((*_check_ide_adapter(settings), False))
    checks.append((*_check_gcp_workstations(settings), strict))

    if strict or settings.strict_integrations:
        for err in validate_production_settings(settings):
            checks.append((f"config: {err[:40]}", False, err, True))

    failed = 0
    for name, ok, detail, required in checks:
        color = typer.colors.GREEN if ok else typer.colors.RED
        typer.secho(f"{'PASS' if ok else 'FAIL'}  {name}: {detail}", fg=color)
        if not ok and required:
            failed += 1

    if settings.demo_mode and settings.environment == "local":
        typer.secho(
            "Demo mode enabled — mock integrations when tokens missing (local only)",
            fg=typer.colors.YELLOW,
        )
    elif settings.environment in ("staging", "prod"):
        typer.secho(
            f"Environment: {settings.environment} — fail-closed prod rules active",
            fg=typer.colors.BLUE,
        )

    if failed:
        raise typer.Exit(code=1)


def _integration_check(
    name: str,
    result: tuple[bool, str],
    settings: Settings,
    strict: bool,
) -> tuple[str, bool, str]:
    ok, detail = result
    if detail == "not configured":
        if strict or settings.strict_integrations or settings.environment in ("staging", "prod"):
            return name, False, "required but not configured"
        return f"{name} (optional)", True, "skipped"
    return name, ok, detail


def _check_http(name: str, url: str) -> tuple[str, bool, str]:
    ok, detail = _check_http_bool(url)
    return name, ok, detail


def _check_http_bool(url: str) -> tuple[bool, str]:
    try:
        response = httpx.get(url, timeout=5.0)
        if response.status_code == 200:
            body = response.json() if "application/json" in response.headers.get("content-type", "") else {}
            if isinstance(body, dict) and body.get("status") in ("ready", "ok"):
                return True, f"HTTP {response.status_code}"
            if isinstance(body, dict) and body.get("status") == "not_ready":
                return False, body.get("detail", "not_ready")
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


def _check_ide_adapter(settings: Settings) -> tuple[str, bool, str]:
    import shutil

    adapter = settings.ide_adapter.lower()
    tools = {
        "cursor": ["cursor", "cursor-agent"],
        "vscode": ["code", "code-server"],
        "claude": ["claude"],
        "antigravity": ["agy", "antigravity"],
        "mock": [],
        "auto": ["claude", "cursor", "agy"],
    }
    if adapter == "mock" or settings.demo_mode:
        if settings.environment in ("staging", "prod"):
            return "IDE adapter", False, "mock/demo not allowed in staging/prod"
        return "IDE adapter (demo/mock)", True, "mock mode"
    names = tools.get(adapter, tools["auto"])
    for name in names:
        if shutil.which(name):
            return f"IDE adapter ({adapter})", True, f"found {name}"
    if settings.local_ide_enabled:
        return (
            f"IDE adapter ({adapter})",
            False,
            "CLI not found — install or set THEKEDAR_IDE_ADAPTER=mock",
        )
    return f"IDE adapter ({adapter})", True, "skipped (local IDE disabled)"


def _check_gcp_workstations(settings: Settings) -> tuple[str, bool, str]:
    if settings.remote_executor != "gcp":
        return "GCP Workstations (remote executor)", True, "not configured (using non-gcp executor)"
    if not settings.gcp_project_id:
        return "GCP Workstations (project ID)", False, "GCP_PROJECT_ID required but missing"

    try:
        from google.cloud import workstations_v1
        client = workstations_v1.WorkstationsClient()
        location_path = f"projects/{settings.gcp_project_id}/locations/{settings.gcp_region or 'us-central1'}"
        client.list_workstation_clusters(parent=location_path, page_size=1)
        return "GCP Workstations reachability", True, f"client initialized + reached location: {settings.gcp_region}"
    except Exception as e:
        return "GCP Workstations reachability", False, f"Failed: {str(e)}"

