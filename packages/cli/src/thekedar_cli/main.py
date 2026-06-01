"""CLI entrypoint."""

import typer

from thekedar_cli.commands import mcp

app = typer.Typer(name="thekedar", help="Thekedar headless MCP orchestrator CLI")
app.add_typer(mcp.app, name="mcp")


def run() -> None:
    app()


if __name__ == "__main__":
    run()
