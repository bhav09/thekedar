"""CLI entrypoint."""

import typer

from thekedar_cli.commands.bootstrap import bootstrap_command
from thekedar_cli.commands.context import app as context_app
from thekedar_cli.commands.doctor import doctor_command
from thekedar_cli.commands.init_cmd import init_command
from thekedar_cli.commands.mcp import app as mcp_app
from thekedar_cli.commands.ops import app as ops_app

app = typer.Typer(name="thekedar", help="Thekedar headless MCP orchestrator CLI")
app.add_typer(mcp_app, name="mcp")
app.add_typer(context_app, name="context")
app.add_typer(ops_app, name="ops")
app.command("init")(init_command)
app.command("doctor")(doctor_command)
app.command("bootstrap")(bootstrap_command)


def run() -> None:
    app()


if __name__ == "__main__":
    run()
