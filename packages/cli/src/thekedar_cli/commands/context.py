"""Context indexing CLI commands."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from thekedar_context.indexer import RepoIndexer
from thekedar_context.retriever import ContextRetriever
from thekedar_shared.db import init_db
from thekedar_shared.settings import get_settings

app = typer.Typer(name="context", help="Codebase context indexing")


@app.command("index")
def index_command(
    repo: Annotated[str, typer.Option(help="GitHub repo OWNER/NAME")] = "thekedar/thekedar",
    tenant: Annotated[str, typer.Option(help="Tenant id")] = "default",
    path: Annotated[Path | None, typer.Option(help="Local repo path")] = None,
) -> None:
    """Index repository into global context store."""
    settings = get_settings()
    session_factory = init_db(settings.database_url)
    session = session_factory()
    try:
        repo_path = path or Path(settings.local_repo_path or Path.cwd())
        snapshot = RepoIndexer().index(session, tenant, repo, repo_path)
        typer.secho(
            f"Indexed {repo} @ {snapshot.sha[:8]} ({snapshot.id})",
            fg=typer.colors.GREEN,
        )
    finally:
        session.close()


@app.command("status")
def status_command(
    repo: Annotated[str, typer.Option(help="GitHub repo OWNER/NAME")] = "thekedar/thekedar",
    tenant: Annotated[str, typer.Option(help="Tenant id")] = "default",
) -> None:
    """Show latest context snapshot status."""
    settings = get_settings()
    session_factory = init_db(settings.database_url)
    session = session_factory()
    try:
        retriever = ContextRetriever(settings)
        snapshot = retriever.latest_snapshot(session, tenant, repo)
        if snapshot is None:
            typer.secho("No snapshot — run: thekedar context index", fg=typer.colors.YELLOW)
            raise typer.Exit(code=1)
        typer.echo(f"Snapshot: {snapshot.id}")
        typer.echo(f"SHA: {snapshot.sha}")
        typer.echo(f"Branch: {snapshot.branch}")
        typer.echo(f"Indexed: {snapshot.indexed_at.isoformat()}")
    finally:
        session.close()


@app.command("refresh")
def refresh_command(
    repo: Annotated[str, typer.Option(help="GitHub repo OWNER/NAME")] = "thekedar/thekedar",
    tenant: Annotated[str, typer.Option(help="Tenant id")] = "default",
    path: Annotated[Path | None, typer.Option(help="Local repo path")] = None,
) -> None:
    """Force re-index of repository context."""
    index_command(repo=repo, tenant=tenant, path=path)
