"""CLI entrypoint."""

import typer

from thekedar_cli.commands.bootstrap import bootstrap_command
from thekedar_cli.commands.doctor import doctor_command
from thekedar_cli.commands.init_cmd import init_command
from thekedar_cli.commands.mcp import app as mcp_app

app = typer.Typer(name="thekedar", help="Thekedar headless MCP orchestrator CLI")
app.add_typer(mcp_app, name="mcp")
app.command("init")(init_command)
app.command("doctor")(doctor_command)
app.command("bootstrap")(bootstrap_command)


def run() -> None:
    app()


if __name__ == "__main__":
    run()
